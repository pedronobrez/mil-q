"""
A direct infusion is not a chromatogram, and is not opened as one.

There is no column: the sample is sprayed for a minute or two and every
scan is the same spectrum plus noise. What is tested here is the verdict —
on a flat run, on a gradient, on a scheduled run whose total is flat
because its peaks are spread out, and on a run too short to judge — and
what the Explorer does with it: the tree says so, the product-ion channel
becomes the active one, and the spectrum pane opens on the average of
every scan, which is then what Explain and the library search read.

The thresholds and the figures behind them are in `milq/infusion.py`.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.infusion import (FLAT_FRACTION, MIN_JUDGED_SCANS,  # noqa: E402
                                MIN_SCANS, REFERENCE_PERCENTILE,
                                SETTLING_SECONDS, InfusionVerdict,
                                above_half_fraction, after_settling,
                                flat_fraction, is_infusion, run_range,
                                strongest_channel, verdict_for)
from milq.samples import SampleEntry  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

MZ = np.linspace(200.0, 800.0, 601)


def _peak(centre: float, width: float = 30.0) -> np.ndarray:
    return np.exp(-0.5 * ((MZ - centre) / width) ** 2)


class FakeChannel:
    """Enough of `wiff.Channel` for the verdict and the spectrum pane."""

    def __init__(self, index: int, rt: np.ndarray, tic: np.ndarray,
                 pattern, precursor=None, name="TOF PI", mz=None):
        self.index = index
        self.mz = MZ if mz is None else np.asarray(mz, dtype=float)
        self._rt = np.asarray(rt, dtype=float)
        self._y = np.asarray(tic, dtype=float)
        #: intensity pattern of scan i, before its total is applied
        self._pattern = pattern
        self.info = ChannelInfo(
            index=index, name=name,
            experiment_type="TOF PI" if precursor else "TOF MS",
            polarity="Negative", precursor=precursor,
            start_mass=float(self.mz[0]), end_mass=float(self.mz[-1]),
            n_scans=self._rt.size,
            collision_energy=35.0 if precursor else None)
        self.reads: list[tuple[float, float]] = []

    def tic(self):
        return self._rt, self._y

    @property
    def rt(self):
        return self._rt

    def _spectrum_at(self, scan: int) -> np.ndarray:
        return self._pattern(scan) * self._y[scan]

    def spectrum(self, scan, add_zeros=True):
        scan = int(np.clip(scan, 0, self._rt.size - 1))
        return self.mz, self._spectrum_at(scan)

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        self.reads.append((float(rt_start), float(rt_end)))
        first, last = self.scans_in_range(rt_start, rt_end)
        rows = [self._spectrum_at(i) for i in range(first, last + 1)]
        return self.mz, np.mean(rows, axis=0)

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self._rt - rt)))

    def rt_at_scan(self, scan):
        return float(self._rt[int(np.clip(scan, 0, self._rt.size - 1))])

    def scans_in_range(self, rt_start, rt_end):
        lo, hi = sorted((float(rt_start), float(rt_end)))
        idx = np.nonzero((self._rt >= lo) & (self._rt <= hi))[0]
        if idx.size == 0:
            centre = self.scan_at_rt((lo + hi) / 2)
            return centre, centre
        return int(idx[0]), int(idx[-1])

    def bpc(self, *args, **kwargs):
        return self._rt, self._y

    def xic(self, mz, tolerance=0.02, unit="Da"):
        return self._rt, self._y

    def xic_range(self, mz_lo, mz_hi):
        return self._rt, self._y

    def parameters(self):
        return {}


class FakeSample:
    """A sample whose total is the sum of its channels."""

    instrument = "ZenoTOF 7600"
    acquisition_time = "2026-09-09T09:00:00Z"
    problem = None

    def __init__(self, channels, name="mix1"):
        self.channels = channels
        self.name = name

    def tic(self):
        rt = self.channels[0].rt
        return rt, np.sum([c.tic()[1] for c in self.channels], axis=0)

    def metadata(self):
        return {"Sample": self.name}


def infusion_sample(n: int = 160, drift: float = 0.7) -> FakeSample:
    """
    A minute and a half of spraying: the same spectrum, a falling signal.

    A hundred and sixty scans rather than a round hundred and twenty so the
    suite is not balanced on `MIN_JUDGED_SCANS` itself; the floor is tested
    on its own, either side, further down.
    """
    rt = np.linspace(0.0, 1.5, n)
    fall = np.linspace(1.0, drift, n)
    rng = np.random.default_rng(3)
    survey = FakeChannel(0, rt, 4_000 * fall * rng.normal(1.0, 0.03, n),
                         lambda i: _peak(430.0, 8.0), name="TOF MS")
    product = FakeChannel(1, rt, 60_000 * fall * rng.normal(1.0, 0.03, n),
                          lambda i: _peak(343.0) + 0.4 * _peak(289.0),
                          precursor=430.34)
    weak = FakeChannel(2, rt, 900 * fall * rng.normal(1.0, 0.05, n),
                       lambda i: _peak(500.0), precursor=515.3)
    return FakeSample([survey, product, weak])


def short_infusion_sample(n: int = 150, spikes=(1, 2)) -> FakeSample:
    """
    A spray of `n` quarter-second scans that misbehaves as it starts.

    The real infusions cycle every 0.25 s, so a run of 150 scans lasts
    thirty-eight seconds — long enough to clear `MIN_JUDGED_SCANS` and short
    enough that one per cent of its scans is one of them. Two spikes rather
    than one because that is what it takes to reach the 99th percentile of a
    run this long: 0.99 x 149 lands between the second and third largest
    scans.
    """
    rt = np.linspace(0.0, n * 0.25 / 60.0, n)
    rng = np.random.default_rng(11)
    y = 50_000 * rng.normal(1.0, 0.02, n)
    for scan in spikes:
        y[scan] = y[scan] * 4
    product = FakeChannel(0, rt, y, lambda i: _peak(343.0), precursor=430.34)
    return FakeSample([product])


def short_gradient_sample(n: int = 40) -> FakeSample:
    """A fast gradient: one peak, forty scans, well under the floor."""
    rt = np.linspace(0.0, 2.0, n)
    shape = 40_000 * np.exp(-0.5 * ((rt - 1.2) / 0.08) ** 2) + 60.0
    survey = FakeChannel(0, rt, shape + 200.0,
                         lambda i: _peak(300.0), name="TOF MS")
    product = FakeChannel(1, rt, shape, lambda i: _peak(343.0),
                          precursor=430.34)
    return FakeSample([survey, product])


def gradient_sample(n: int = 200) -> FakeSample:
    """A 20-minute run with three peaks in it."""
    rt = np.linspace(0.0, 20.0, n)
    shape = sum(20_000 * np.exp(-0.5 * ((rt - c) / 0.25) ** 2)
                for c in (4.0, 9.5, 15.0))
    survey = FakeChannel(0, rt, shape + 300.0,
                         lambda i: _peak(300.0 + i), name="TOF MS")
    product = FakeChannel(1, rt, shape + 50.0,
                          lambda i: _peak(343.0 + i), precursor=430.34)
    return FakeSample([survey, product])


def scheduled_sample(n: int = 240) -> FakeSample:
    """
    Six transitions, each acquired over its own window.

    The sample total barely moves — which is exactly the run a rule reading
    the total alone would call an infusion.
    """
    rt = np.linspace(0.0, 12.0, n)
    channels = []
    for k, centre in enumerate((1.0, 3.0, 5.0, 7.0, 9.0, 11.0)):
        y = 30_000 * np.exp(-0.5 * ((rt - centre) / 1.1) ** 2) + 20.0
        channels.append(FakeChannel(k, rt, y, lambda i: _peak(343.0),
                                    precursor=400.0 + k))
    return FakeSample(channels)


# -- the measure ------------------------------------------------------------ #
def test_a_flat_trace_is_all_above_half_and_a_peak_is_not():
    assert above_half_fraction(np.full(50, 7.0)) == 1.0
    assert above_half_fraction(np.zeros(50)) == 0.0
    assert above_half_fraction(np.zeros(0)) == 0.0
    # a trace that is one narrow peak on nothing: only the peak clears half
    peak = np.full(100, 1.0)
    peak[45:55] = 100.0
    assert above_half_fraction(peak) == pytest.approx(0.10)


def test_one_spike_does_not_decide_a_whole_run():
    """
    The reference is the 99th-percentile scan, not the largest one.

    Measured on the real infusions: three of the nine carry a spray
    transient at scan 1 of 2.8 to 4.4 times the run's median, and against
    the largest scan a perfectly flat spray read 0.002 – 0.006 — under
    every one of the thirty-nine chromatographic runs. The two populations
    came out the wrong way round, and no threshold separates them.
    """
    assert REFERENCE_PERCENTILE == 99.0
    flat = np.full(500, 1.0)
    flat[1] = 4.0                       # the transient at the start of a run
    flat[300] = flat[301] = 3.0         # and a burst part way through
    assert above_half_fraction(flat) == pytest.approx(1.0)
    assert above_half_fraction(flat, percentile=100) == pytest.approx(0.006)
    # a run that really is one peak is unmoved by the change of reference
    peak = np.full(500, 1.0)
    peak[240:260] = 100.0
    assert above_half_fraction(peak) == pytest.approx(0.04)
    assert above_half_fraction(peak, percentile=100) == pytest.approx(0.04)


def test_an_infusion_with_a_spray_transient_is_still_an_infusion():
    """The shape of `CA-d4_TOFMSMS_Mix1`: flat, with one scan four times over."""
    sample = infusion_sample(n=473, drift=0.9)
    for channel in sample.channels:
        channel._y[1] = channel._y[1] * 4
    verdict = is_infusion(sample)
    assert verdict.infusion, verdict.reason
    assert verdict.above_half >= FLAT_FRACTION
    assert verdict.channel_above_half >= FLAT_FRACTION
    assert "99th-percentile scan" in verdict.reason


def test_the_settling_window_leaves_a_fixed_piece_of_the_front():
    """
    A share of the scans is not a fixed number of them on a short run.

    `after_settling` cuts by time, so the same first second goes whatever the
    cycle is — four scans at a quarter of a second, none worth cutting at
    14.6 s — and it refuses to cut at all when fewer than `MIN_SCANS` would
    be left, which is the only case where the window could be most of the run.
    """
    assert SETTLING_SECONDS == 1.0
    fast = np.linspace(0.0, 0.25 * 100 / 60.0, 100)     # 0.25 s scans
    assert after_settling(fast, np.ones(100))[1].size == 96
    slow = np.linspace(0.0, 14.61 * 60 / 60.0, 61)      # 14.6 s scans
    assert after_settling(slow, np.ones(61))[1].size == 60
    # a run so short that the window would eat it is left alone
    tiny = np.linspace(0.0, 0.25 * 10 / 60.0, 10)
    assert after_settling(tiny, np.ones(10))[1].size == 10


def test_the_settling_window_is_what_saves_a_short_infusion():
    """
    Measured on the nine real infusions truncated to their first 50 scans:
    the 99th percentile alone puts the worst at 0.0200, and the same
    percentile taken after the first second puts it at 1.0000. The reason is
    arithmetic — `np.percentile` interpolates, so on a short run the 99th is
    most of the way to the largest scan, and a spray transient is the largest
    scan.
    """
    sample = short_infusion_sample()
    x, y = sample.tic()
    assert above_half_fraction(y) < 0.05, "the percentile alone is thrown"
    assert flat_fraction(x, y) == pytest.approx(1.0)


# -- the verdict ------------------------------------------------------------ #
def test_a_flat_run_of_one_spectrum_is_an_infusion():
    verdict = is_infusion(infusion_sample())
    assert verdict.infusion and verdict and "infusion" in verdict.reason
    assert verdict.above_half >= FLAT_FRACTION
    assert verdict.channel_above_half >= FLAT_FRACTION
    assert verdict.n_scans == 160
    assert verdict.length_min == pytest.approx(1.5)
    # the strongest product-ion channel, not the survey it sits next to
    assert verdict.channel_index == 1


def test_a_gradient_is_refused_on_the_total_alone():
    verdict = is_infusion(gradient_sample())
    assert not verdict.infusion and not verdict
    assert "chromatographic" in verdict.reason
    assert verdict.above_half < 0.25


def test_a_scheduled_run_whose_total_is_flat_is_refused_on_its_channel():
    """The reason a second figure exists: the sum of peaks at different
    times is flatter than any one of them."""
    sample = scheduled_sample()
    verdict = is_infusion(sample)
    assert verdict.above_half >= FLAT_FRACTION, "the total really is flat"
    assert not verdict.infusion
    assert verdict.channel_above_half < FLAT_FRACTION
    assert "peaks at different times" in verdict.reason


def test_a_run_with_no_shape_at_all_is_not_one():
    rt = np.linspace(0.0, 0.1, 4)
    sample = FakeSample([FakeChannel(0, rt, np.full(4, 100.0),
                                     lambda i: _peak(343.0), precursor=430.3)])
    verdict = is_infusion(sample)
    assert not verdict.infusion and "too short" in verdict.reason
    assert verdict.n_scans == 4 and verdict.too_short
    assert MIN_SCANS == 8


def test_a_short_infusion_with_a_transient_is_still_an_infusion():
    """
    The point of the settling window, end to end.

    A hundred and fifty quarter-second scans of a spray that spat twice on
    the way in. Without the window the 99th percentile is dragged up by the
    spikes and the run reads under 5%; with it the run reads 100% and clears
    the floor at 120 scans.
    """
    verdict = is_infusion(short_infusion_sample())
    assert verdict.infusion, verdict.reason
    assert verdict.n_scans == 150 and not verdict.too_short
    assert verdict.above_half == pytest.approx(1.0)
    assert verdict.channel_above_half == pytest.approx(1.0)


def test_a_short_gradient_is_chromatographic_and_not_merely_short():
    """
    The floor gates the flat answer, never the other one.

    Forty scans is well under `MIN_JUDGED_SCANS`, but a run that shows a
    peak has said something positive about itself and is called on it —
    which is what keeps a real 61-scan run reading "chromatographic" with
    its figures rather than "too short to tell".
    """
    verdict = is_infusion(short_gradient_sample())
    assert not verdict.infusion and not verdict.too_short
    assert "chromatographic" in verdict.reason
    assert verdict.n_scans == 40 and verdict.above_half < FLAT_FRACTION


def test_a_flat_run_too_short_to_judge_says_so_and_is_not_an_infusion():
    """
    Measured on a real gradient, which is why this refusal exists.

    `260904_EICs_Isabela_S001` carries nothing until 8.9 minutes in, so its
    first hundred scans read 1.0000 on the sample total and 0.9388 on its
    strongest channel — an infusion's signature, on a gradient. Nothing on a
    chromatogram separates the two, so under `MIN_JUDGED_SCANS` a flat run
    is refused rather than guessed at, with both figures on the verdict.
    """
    sample = short_infusion_sample(n=MIN_JUDGED_SCANS - 1, spikes=())
    verdict = is_infusion(sample)
    assert not verdict.infusion and not bool(verdict)
    assert verdict.too_short
    assert "too short to tell" in verdict.reason
    assert "not an infusion" in verdict.reason
    # the figures are still there, and they are the flat ones
    assert verdict.above_half == pytest.approx(1.0)
    assert verdict.channel_above_half == pytest.approx(1.0)
    assert verdict.n_scans == MIN_JUDGED_SCANS - 1
    assert str(MIN_JUDGED_SCANS) in verdict.reason
    # one scan more and the same run is judged
    assert is_infusion(short_infusion_sample(n=MIN_JUDGED_SCANS,
                                             spikes=())).infusion


def test_a_sample_that_cannot_be_read_is_not_an_infusion():
    class Broken:
        channels: list = []

        def tic(self):
            raise RuntimeError("Could not open data stream.\n   at Clearcore2")

    verdict = is_infusion(Broken())
    assert not verdict.infusion
    assert verdict.reason == ("the run could not be read: Could not open "
                              "data stream.")


def test_no_spectrum_is_read_to_reach_a_verdict():
    """The verdict has to hold on a .wiff whose .wiff.scan is missing."""
    sample = infusion_sample()
    assert is_infusion(sample).infusion
    assert all(channel.reads == [] for channel in sample.channels)


def test_the_strongest_product_channel_wins_over_a_stronger_survey():
    sample = infusion_sample()
    sample.channels[0]._y = sample.channels[0]._y * 1000  # a huge survey
    assert strongest_channel(sample).index == 1
    # with no product-ion channel at all, the survey is what there is
    survey_only = FakeSample([sample.channels[0]])
    assert strongest_channel(survey_only).index == 0
    assert strongest_channel(FakeSample([])) is None


def test_the_verdict_is_measured_once_per_sample():
    sample = infusion_sample()
    calls = []
    original = FakeSample.tic

    def counted(self):
        calls.append(1)
        return original(self)

    FakeSample.tic = counted
    try:
        assert verdict_for(sample).infusion
        assert verdict_for(sample).infusion
        assert len(calls) == 1
    finally:
        FakeSample.tic = original
    assert verdict_for(None) == InfusionVerdict(False, "no sample")


def test_the_whole_run_is_the_range_to_average():
    channel = infusion_sample().channels[1]
    low, high = run_range(channel)
    assert (low, high) == (0.0, pytest.approx(1.5))


def test_the_verdict_survives_a_trip_through_mzml(tmp_path):
    """
    The same acquisition, written as mzML and read back by the other
    reader, is the same infusion.

    Nothing in an mzML says which experiment a scan belongs to, so its
    channels are inferred from the order of acquisition; the verdict has to
    come out of that as it came out of the file it was written from.
    """
    from milq import mzml

    path = tmp_path / "infusion.mzML"
    mzml.write_mzml(infusion_sample(), path)
    sample = mzml.MzmlFile(path).sample(0)
    assert len(sample.channels) == 3

    original = is_infusion(infusion_sample())
    verdict = is_infusion(sample)
    assert verdict.infusion
    assert verdict.n_scans == original.n_scans
    assert verdict.above_half == pytest.approx(original.above_half)
    assert verdict.channel_above_half == pytest.approx(
        original.channel_above_half)
    assert strongest_channel(sample).info.precursor == pytest.approx(430.34)


# -- the Explorer ------------------------------------------------------------ #
def _explorer(sample):
    from PyQt6 import QtWidgets
    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    session = Session()
    session.entries.append(SampleEntry("/d/mix1.wiff", 0, "mix1", sample=sample))
    explorer = ExplorerWorkspace(session)
    explorer.rebuild_tree()
    return app, explorer


def test_an_infusion_opens_on_the_average_of_the_whole_run():
    app, explorer = _explorer(infusion_sample())

    # the tree says so, beside the instrument, with the figures on hover
    sample_item = explorer.tree.topLevelItem(0).child(0)
    assert sample_item.text(0) == "mix1  (ZenoTOF 7600, infusion)"
    assert "half the maximum" in sample_item.toolTip(0)

    # its product-ion channel is checked and active, not the survey
    assert explorer.active_ref is not None
    assert explorer.active_ref.channel.index == 1
    checked = [r.channel.index for r in explorer._checked_refs()
               if r.channel is not None]
    assert checked == [1]

    # and the spectrum is the average of every scan, said so in the title
    assert ("mix1 · TOF PI 430.34 · average of 160 scans (infusion) · "
            "RT 0.000–1.500 min") == explorer.spectrum.title
    assert explorer.infusion_label.text() == "infusion"
    assert explorer.active_ref.channel.reads[-1] == (0.0, pytest.approx(1.5))

    # the chromatogram is still the TIC over time: the sample total and the
    # one channel that came in checked
    assert len(explorer.chrom.traces) == 2

    # and F1 on the marker opens the page that explains the verdict
    from milq.manual import manual
    from milq.ui.help_window import help_page_for
    assert help_page_for(explorer.infusion_label) == "direct-infusion"
    assert "direct-infusion" in manual().pages

    explorer.deleteLater()
    app.processEvents()


def test_what_explain_and_the_library_read_is_that_average():
    app, explorer = _explorer(infusion_sample())
    channel = explorer.active_ref.channel
    expected = channel.spectrum_rt_range(*run_range(channel))[1]

    mz, intensity = explorer._current_spectrum()
    # the pane restores a profile spectrum's zeros, so what comes back is the
    # average with points added at masses the instrument reported nothing for
    assert intensity.max() == pytest.approx(expected.max())
    assert intensity.max() != pytest.approx(channel.spectrum(0)[1].max())

    explorer.act_centroid.setChecked(False)
    mz, intensity, precursor, _context = explorer._library_spectrum()
    assert precursor == pytest.approx(430.34)
    # centroided sticks of the average: the base peak is the average's
    assert intensity.max() == pytest.approx(expected.max(), rel=1e-6)

    # Explain is handed the same spectrum and the channel's precursor
    explorer.explain_spectrum()
    # written with the digits the method carried and no more: 430.34 is
    # known to +/-0.005, and 430.3400 claims two decimals nobody measured
    assert explorer.lipid_panel.explain_precursor.text() == "430.34"
    assert len(explorer.lipid_panel._peaks) > 0

    explorer.deleteLater()
    app.processEvents()


def test_a_chromatographic_sample_opens_exactly_as_it_did():
    app, explorer = _explorer(gradient_sample())
    sample_item = explorer.tree.topLevelItem(0).child(0)
    assert sample_item.text(0) == "mix1  (ZenoTOF 7600)"
    # only the sample TIC comes in checked, and nothing was averaged
    assert [r.channel for r in explorer._checked_refs()] == [None]
    assert "infusion" not in explorer.spectrum.title
    assert explorer.infusion_label.text() == ""
    explorer.deleteLater()
    app.processEvents()


def test_average_whole_run_works_on_any_channel():
    app, explorer = _explorer(gradient_sample())
    explorer.active_combo.setCurrentIndex(explorer.active_combo.findData(
        next(k for k, r in explorer.refs.items()
             if r.channel is not None and r.channel.index == 1)))
    explorer.average_whole_run()
    assert "average of 200 scans (1–200) ·" in explorer.spectrum.title
    assert "(infusion)" not in explorer.spectrum.title
    assert explorer.active_ref.channel.reads[-1] == (0.0, pytest.approx(20.0))
    explorer.deleteLater()
    app.processEvents()


def test_average_whole_run_says_so_when_there_is_no_channel():
    app, explorer = _explorer(gradient_sample())
    explorer.active_ref = None
    messages = []
    explorer.sigStatus.connect(messages.append)
    explorer.average_whole_run()
    assert messages[-1] == "Pick an active channel first."
    explorer.deleteLater()
    app.processEvents()


# -- the accurate precursor -------------------------------------------------- #
def test_the_precursor_of_an_infusion_is_measured_over_the_whole_run():
    from milq.components import Component
    from milq.precursor import measure

    sample = infusion_sample()
    # the survey has to carry the precursor, on a grid fine enough to hold it
    fine = np.linspace(429.0, 431.0, 401)
    sample.channels[0] = FakeChannel(
        0, sample.channels[0].rt, sample.channels[0].tic()[1],
        lambda i: np.exp(-0.5 * ((fine - 430.3412) / 0.012) ** 2),
        name="TOF MS", mz=fine)
    entry = SampleEntry("/d/mix1.wiff", 0, "mix1", sample=sample)
    # a retention time copied in from a chromatographic method, well outside
    # a run that lasts ninety seconds
    component = Component("CA-d4", 430.34, 343.0, rt=8.0, rt_halfwidth=0.5)

    result = measure(entry, component)
    assert result.found, result.note
    assert result.measured == pytest.approx(430.34, abs=0.01)
    assert result.rt == pytest.approx(0.75, abs=0.02)
    # every scan of the survey went into the measurement, not three of them
    assert sample.channels[0].reads[-1] == (0.0, pytest.approx(1.5))


# --------------------------------------------------------------------------- #
# another vendor's file
# --------------------------------------------------------------------------- #
def test_an_mzml_infusion_from_another_vendor_reads_the_same(tmp_path):
    """
    The verdict reads chromatograms and never a spectrum, so it says the same
    thing about another vendor's mzML as about a `.wiff`.

    The file is built by `tests/test_mzml.py`: written with `write_mzml` and
    then re-written the way ProteoWizard writes a Thermo `.raw` — Thermo ids,
    seconds instead of minutes, an isolation window, HCD, and nothing saying
    which experiment a scan came from. Read back, it is one product-ion
    channel, and both figures land where a spray lands.
    """
    from milq import mzml
    from tests.test_mzml import (INFUSION_SCANS, _infusion_sample,
                                 _thermo_shaped)

    ours = tmp_path / "ours.mzML"
    mzml.write_mzml(_infusion_sample(), ours)
    path = _thermo_shaped(ours, tmp_path / "thermo.mzML")
    sample = mzml.MzmlFile(path).sample(0)

    verdict = is_infusion(sample)
    assert verdict.infusion
    assert verdict.above_half >= FLAT_FRACTION
    assert verdict.channel_above_half >= FLAT_FRACTION
    assert verdict.n_scans == INFUSION_SCANS
    assert verdict.channel_index == 0
    assert "an infusion" in verdict.reason

    channel = strongest_channel(sample)
    assert channel is sample.channels[0]
    assert not channel.info.is_ms1
    # the whole run, which is the only range an infusion has
    start, end = run_range(channel)
    assert (start, end) == pytest.approx((float(channel.rt[0]),
                                          float(channel.rt[-1])))
    # measured once and remembered, whatever the reader
    assert verdict_for(sample) is verdict_for(sample)
