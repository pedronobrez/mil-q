"""
The noise floor of an infusion's averaged spectrum, measured rather than fixed.

A floor of a hundred counts is a statement about one survey scan of one
instrument. An infusion's spectrum is the average of every scan of the run,
and on the nine real bile-acid infusions the base peak of that average is
109 to 12,271 counts — so the constant is anywhere from a fiftieth of the
spectrum to the whole of it. What is here is the measurement that replaces
it: a synthetic infusion whose noise is known exactly, so that the two
estimates can be checked against the standard deviation they were built from
rather than against each other.

The synthetic acquisition is a background at a level of 5 counts with a
standard deviation of 0.5 in every scan, plus three peaks. Averaging n scans
divides the scatter by the root of n, which is the claim both estimates make
and the one the first tests read back.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import infusion, infusion_report as ir  # noqa: E402
from milq import precursor as _precursor  # noqa: E402
from milq.labels import LABEL_MIN_RELATIVE  # noqa: E402
from milq.library import entry_from_spectrum  # noqa: E402
from milq.processing import (empty_regions, quiet_window,  # noqa: E402
                                  spectrum_noise)
from milq.samples import SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.ui.explorer import ChannelRef, ExplorerWorkspace  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

#: the background every scan sits on, and how much it moves scan to scan
LEVEL = 5.0
NOISE_SD = 0.5
#: the mass axis: 0.01 Da steps, so a 0.5 Da window holds fifty points
STEP = 0.01
LOW, HIGH = 100.0, 500.0
PEAKS = {150.0: 20_000.0, 151.0: 6_000.0, 250.0: 3_000.0}


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _axis() -> np.ndarray:
    return np.arange(LOW, HIGH + STEP / 2, STEP)


def _peaks_on(mz: np.ndarray, peaks=PEAKS) -> np.ndarray:
    out = np.zeros(mz.size)
    for centre, height in peaks.items():
        out += height * np.exp(-0.5 * ((mz - centre) / 0.02) ** 2)
    return out


class NoisyChannel:
    """
    A synthetic infusion: `n` scans of one spectrum with known noise.

    Every scan is the same peaks plus `sd` of Gaussian scatter about `level`,
    so the average of n of them has a background of `level` and a scatter of
    `sd / sqrt(n)` — which is the number both estimates have to recover.
    """

    def __init__(self, n: int = 100, sd: float = NOISE_SD,
                 level: float = LEVEL, peaks=PEAKS, precursor=None,
                 seed: int = 7, index: int = 0):
        self.index = index
        self.mz = _axis()
        rng = np.random.default_rng(seed)
        self.scans = (_peaks_on(self.mz, peaks)
                      + rng.normal(level, sd, (n, self.mz.size)))
        self._rt = np.linspace(0.0, 2.0, n)
        self.info = ChannelInfo(
            index=index, name="TOF PI",
            experiment_type="Product" if precursor else "TOF MS",
            polarity="Positive", precursor=precursor,
            start_mass=LOW, end_mass=HIGH, n_scans=n,
            collision_energy=30.0 if precursor else None)

    # -- the surface the measurement uses ----------------------------------- #
    @property
    def rt(self):
        return self._rt

    def _inside(self, rt_start, rt_end):
        lo, hi = sorted((float(rt_start), float(rt_end)))
        return (self._rt >= lo) & (self._rt <= hi)

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        keep = self._inside(rt_start, rt_end)
        return self.mz, self.scans[keep].mean(axis=0)

    def spectrum(self, scan, add_zeros=True):
        return self.mz, self.scans[int(scan)]

    def xic_range(self, mz_lo, mz_hi):
        inside = (self.mz >= mz_lo) & (self.mz <= mz_hi)
        return self._rt, self.scans[:, inside].sum(axis=1)

    def tic(self):
        return self._rt, self.scans.sum(axis=1)

    def xic(self, mz, tolerance=0.02, unit="Da"):
        return self.xic_range(mz - tolerance, mz + tolerance)

    def bpc(self, *args, **kwargs):
        return self._rt, self.scans.max(axis=1)

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self._rt - rt)))

    def rt_at_scan(self, scan):
        return float(self._rt[int(np.clip(scan, 0, self._rt.size - 1))])

    def scans_in_range(self, rt_start, rt_end):
        idx = np.nonzero(self._inside(rt_start, rt_end))[0]
        return (int(idx[0]), int(idx[-1])) if idx.size else (0, 0)

    def parameters(self):
        return {}


class NoisySample:
    instrument = "ZenoTOF 7600"
    acquisition_time = "2026-09-10T09:00:00Z"
    problem = None

    def __init__(self, channels, name="infusion"):
        self.channels = list(channels)
        self.name = name

    def tic(self):
        rt = self.channels[0].rt
        return rt, np.sum([c.tic()[1] for c in self.channels], axis=0)

    def metadata(self):
        return {"Sample": self.name}


def _infusion(n: int = 150, peaks=PEAKS, precursor=None, sd: float = NOISE_SD):
    channel = NoisyChannel(n=n, peaks=peaks, precursor=precursor, sd=sd)
    entry = SampleEntry("/d/TESTOL_infusion.wiff", 0, "TESTOL_infusion")
    entry.sample = NoisySample([channel])
    return entry, channel


# --------------------------------------------------------------------------- #
# the two estimates
# --------------------------------------------------------------------------- #
def test_the_empty_regions_are_the_axis_away_from_every_peak():
    mz = _axis()
    intensity = _peaks_on(mz) + LEVEL
    empty = empty_regions(mz, intensity)
    # half a dalton either side of each of the three peaks is set aside, and
    # everything else is left
    assert not empty[np.argmin(np.abs(mz - 150.0))]
    assert not empty[np.argmin(np.abs(mz - 250.3))]
    assert empty[np.argmin(np.abs(mz - 200.0))]
    assert 0.9 < empty.mean() < 0.999


def test_the_empty_regions_recover_the_scatter_the_average_was_built_from():
    """(a): the MAD of the empty points is the per-scan SD over root n."""
    for n in (25, 100):
        channel = NoisyChannel(n=n)
        mz, intensity = channel.spectrum_rt_range(0.0, 2.0)
        noise = spectrum_noise(mz, intensity)
        assert noise is not None
        assert noise.sigma == pytest.approx(NOISE_SD / np.sqrt(n), rel=0.25)
        assert noise.median == pytest.approx(LEVEL, rel=0.02)
        # the tail the floor is taken from sits a couple of sigma above it
        assert LEVEL < noise.p99 < LEVEL + 4 * NOISE_SD / np.sqrt(n)
        assert noise.points > 1000 and noise.peaks >= len(PEAKS)
        # a noise peak stands taller than a noise point, and the floor is
        # taken from the peaks
        assert noise.peak_p99 > noise.p99
        assert noise.maxima > 1000


def test_the_scan_to_scan_scatter_recovers_it_too_and_says_what_n_bought():
    """(b): the SD of a quiet window's sum, divided by the root of n."""
    points = int(round(infusion.QUIET_WINDOW_DA / STEP)) + 1
    for n in (25, 100):
        channel = NoisyChannel(n=n)
        floor = infusion.noise_floor(channel)
        assert floor.window is not None
        expected = NOISE_SD * np.sqrt(points)
        assert floor.per_scan == pytest.approx(expected, rel=0.25)
        assert floor.scatter == pytest.approx(expected / np.sqrt(n), rel=0.25)
        assert floor.gain == pytest.approx(np.sqrt(n))
        assert floor.run_scans == n
        assert f"divides by {np.sqrt(n):,.1f}" in floor.describe()


def test_a_restored_zero_changes_neither_estimate():
    """
    A vendor's stripped zeros are a drawing instruction, not a measurement,
    so putting them back must not move a distribution of intensities.
    """
    channel = NoisyChannel(n=64)
    mz, intensity = channel.spectrum_rt_range(0.0, 2.0)
    padded_mz = np.sort(np.concatenate([mz, np.arange(510.0, 540.0, 0.01)]))
    padded = np.interp(padded_mz, mz, intensity, left=0.0, right=0.0)
    plain = spectrum_noise(mz, intensity)
    with_zeros = spectrum_noise(padded_mz, padded)
    assert with_zeros.p99 == pytest.approx(plain.p99, rel=1e-9)
    assert with_zeros.median == pytest.approx(plain.median, rel=1e-9)


def test_a_spectrum_with_nothing_empty_in_it_is_not_measured():
    mz = np.array([100.0, 100.01, 100.02])
    assert spectrum_noise(mz, np.array([1.0, 2.0, 1.0])) is None
    assert quiet_window(mz, np.array([1.0, 2.0, 1.0]), 0.5) is None


# --------------------------------------------------------------------------- #
# the floor that comes out of them
# --------------------------------------------------------------------------- #
def test_the_floor_is_the_larger_of_the_two_and_never_under_either():
    channel = NoisyChannel(n=100)
    floor = infusion.noise_floor(channel)
    assert floor.measured
    assert floor.value >= floor.from_empty
    assert floor.value >= floor.scatter
    assert floor.value == max(floor.from_empty, floor.scatter)
    assert floor.basis == "the empty regions of the average"
    assert floor.base_peak == pytest.approx(max(PEAKS.values()), rel=0.01)
    assert floor.relative == pytest.approx(floor.value / floor.base_peak)


def test_an_acquisition_quieter_than_the_fixed_floor_keeps_its_own_number():
    """
    The constant is not a safety margin when it is a fiftieth of the base
    peak: the measurement stands, and the record says it is under the fixed
    one rather than quietly raising itself to it.
    """
    channel = NoisyChannel(n=100)
    floor = infusion.noise_floor(channel)
    assert floor.value < _precursor.MIN_INTENSITY
    assert floor.quieter_than_fixed
    assert "under the fixed 100 counts" in floor.describe()


def test_a_channel_that_cannot_be_measured_falls_back_to_the_fixed_floor():
    class Unreadable(NoisyChannel):
        def spectrum_rt_range(self, *args, **kwargs):
            raise OSError("the .wiff.scan is not beside its .wiff")

    floor = infusion.noise_floor(Unreadable(n=20))
    assert not floor.measured
    assert floor.value == _precursor.MIN_INTENSITY
    assert "could not be read" in floor.note
    assert "the fixed 100 counts stands" in floor.describe()
    assert infusion.noise_floor_for(None).value == _precursor.MIN_INTENSITY


def test_the_floor_is_measured_once_per_channel():
    channel = NoisyChannel(n=40)
    first = infusion.noise_floor_for(channel)
    assert infusion.noise_floor_for(channel) is first
    # a spectrum handed in is measured and not remembered: it may have been
    # background subtracted, and that is not the channel's own floor
    mz, intensity = channel.spectrum_rt_range(0.0, 2.0)
    handed = infusion.noise_floor_for(channel, spectrum=(mz, intensity))
    assert handed is not first
    assert handed.value == pytest.approx(first.value, rel=1e-9)


# --------------------------------------------------------------------------- #
# where the floor applies
# --------------------------------------------------------------------------- #
def test_the_precursor_gate_honours_the_floor_it_is_given():
    mz = np.array([399.9, 399.95, 400.0, 400.05, 400.1])
    intensity = np.array([1.0, 20.0, 80.0, 20.0, 1.0])
    assert _precursor.in_spectrum(mz, intensity, 400.0)[1] == 80.0
    assert _precursor.in_spectrum(mz, intensity, 400.0, floor=10.0)[1] == 80.0
    assert _precursor.in_spectrum(mz, intensity, 400.0, floor=100.0) is None
    # no floor at all is still the ungated answer a caller may want
    assert _precursor.in_spectrum(mz, intensity, 400.0, floor=None) is not None


def test_a_record_of_ones_own_honours_an_absolute_floor_as_well():
    mz = np.array([100.0, 200.0, 300.0])
    intensity = np.array([1000.0, 40.0, 12.0])
    plain = entry_from_spectrum("own", mz, intensity)
    assert plain.peaks == 3                      # 1% of the base peak is 10…
    floored = entry_from_spectrum("own", mz, intensity, min_absolute=50.0)
    assert floored.peaks == 1                    # …and 50 counts is one peak
    assert floored.mz[0] == 100.0
    # the relative floor still applies where it is the higher of the two
    both = entry_from_spectrum("own", mz, intensity, min_relative=0.05,
                               min_absolute=1.0)
    assert both.peaks == 1


def test_the_report_measures_its_own_floor_and_confirms_what_clears_it(qapp):
    """
    Eighty-four counts is nothing against a fixed hundred and everything
    against a measured one. The synthetic acquisition's floor is a few
    counts, so a precursor of eighty-four is a measurement.
    """
    peaks = dict(PEAKS)
    peaks[430.35] = 84.0
    entry, channel = _infusion(peaks=peaks, precursor=430.35)
    report = ir.report_for(entry, channel)

    assert report.noise_floor is not None and report.noise_floor.measured
    assert report.floor < _precursor.MIN_INTENSITY
    assert report.survivor is not None
    assert report.survivor[1] == pytest.approx(84.0 + LEVEL, rel=0.05)
    said = report.sentences()[0]
    assert said.startswith("Precursor confirmed at")


def test_a_precursor_under_the_measured_floor_says_which_floor_it_was(qapp):
    """
    The refusal has to name the floor it refused against. A measured floor
    is a different sentence from the fixed one, because the reader's next
    question is whether the number came from the acquisition or from a
    constant — and on this synthetic run the background is five counts, so
    a floor is imposed here rather than measured, to hold the wording to a
    height that is certainly under it.
    """
    peaks = dict(PEAKS)
    peaks[430.35] = 40.0
    entry, channel = _infusion(peaks=peaks, precursor=430.35)
    report = ir.report_for(entry, channel)
    assert report.survivor is not None            # 40 counts clears its own

    report.survivor, report.survivor_note = None, ""
    report.noise_floor = infusion.NoiseFloor(value=1_000.0, measured=True,
                                             fixed=_precursor.MIN_INTENSITY)
    mz, intensity = channel.spectrum_rt_range(0.0, 2.0)
    ir._survivor(report, mz, intensity)

    assert report.survivor is None
    said = report.sentences()[0]
    assert "too little of the precursor survives" in said
    assert "below the measured noise floor of 1,000 counts" in said
    assert "counts survive" in ir._precursor_reason(report)


def test_a_refusal_against_the_fixed_floor_says_that_instead(qapp):
    entry, channel = _infusion(precursor=430.35)
    report = ir.report_for(entry, channel)
    report.survivor, report.survivor_note, report.noise_floor = None, "", None
    mz, intensity = channel.spectrum_rt_range(0.0, 2.0)
    ir._survivor(report, mz, intensity)

    assert report.floor == _precursor.MIN_INTENSITY
    assert "below the fixed floor of 100 counts" in report.sentences()[0]


def test_a_report_with_no_measurement_still_answers_with_the_fixed_floor(qapp):
    report = ir.InfusionReport(compound="Testol")
    assert report.noise_floor is None
    assert report.floor == _precursor.MIN_INTENSITY


def test_peaks_under_the_floor_are_not_listed_as_unexplained(qapp):
    """
    An explanation is not answerable for the background: a peak that is
    noise is not a peak it failed to account for.
    """
    entry, channel = _infusion(precursor=None)
    report = ir.report_for(entry, channel)

    class AllUnexplained:
        name = "Testol"
        predicted = 0
        matched = 0

        def unexplained(self, peaks):
            return list(peaks)

    report.explanation = AllUnexplained()
    report.label_floor = 1e-6            # every peak in view is offered
    listed = report.peaks(most=ir.PEAKS_LISTED)
    assert len(listed) == ir.PEAKS_LISTED
    # the measured floor of this run is a few counts and every peak in the
    # table clears it, which is the ordinary case; the filter is read back
    # against a floor set where it separates them
    assert all(height >= report.floor for _mz, height in listed)
    report.noise_floor = infusion.NoiseFloor(value=4_000.0, measured=True,
                                             fixed=_precursor.MIN_INTENSITY)
    left = report.unexplained(most=ir.PEAKS_LISTED)
    assert 0 < len(left) < len(listed)
    assert all(height >= 4_000.0 for _mz, height in left)


def test_an_infusion_pane_starts_at_the_higher_of_the_two_floors(qapp):
    """
    The drawing's two per cent knows nothing about the acquisition and the
    noise floor knows nothing about the drawing. The pane takes whichever is
    higher and says in the status line which it was.
    """
    entry, channel = _infusion(precursor=430.35)
    explorer = ExplorerWorkspace(Session())
    said: list[str] = []
    explorer.sigStatus.connect(said.append)
    ref = ChannelRef(entry, channel)
    floor = explorer.noise_floor(ref)
    assert floor is not None and floor.measured

    explorer._floor_from_noise(ref)
    assert explorer.spectrum.label_floor == pytest.approx(
        max(LABEL_MIN_RELATIVE, floor.relative), abs=1e-4)
    assert said and "Label floor" in said[-1]
    assert "noise floor" in said[-1]
    assert f"{infusion.format_counts(floor.value)} counts" in said[-1]
    explorer.deleteLater()
    qapp.processEvents()


def test_a_chromatographic_sample_has_no_floor_of_its_own(qapp):
    """
    The measurement is defined for the average of a whole run. A pane
    showing a chromatographic sample asks for none, and a record written
    from it keeps the relative floor it always had.
    """
    entry, channel = _infusion(n=40)          # under MIN_JUDGED_SCANS
    explorer = ExplorerWorkspace(Session())
    assert not infusion.verdict_for(entry.sample)
    assert explorer.noise_floor(ChannelRef(entry, channel)) is None
    explorer.deleteLater()
    qapp.processEvents()


def test_a_peak_that_clears_the_floor_but_misses_the_mass_is_not_confirmed(qapp):
    """
    The floor answers whether something is there and the ppm answers what it
    is. Measuring the floor rather than fixing it at a hundred counts let
    four real windows through that the constant had refused, and all four sit
    30 to 70 ppm from the written mass — so the sentence has to stop short of
    *confirmed*, which the summary line already reserved for
    `CONFIRMED_PPM`.
    """
    off = 430.35 * (1 + 70e-6)               # 70 ppm high, well past 25
    peaks = dict(PEAKS)
    peaks[off] = 84.0
    entry, channel = _infusion(peaks=peaks, precursor=430.35)
    report = ir.report_for(entry, channel)

    assert report.survivor is not None       # the height cleared the floor
    assert abs(report.error_ppm()) > ir.CONFIRMED_PPM
    said = report.sentences()[0]
    assert said.startswith("Precursor found but not confirmed at")
    assert f"past the {ir.CONFIRMED_PPM:g} ppm" in said
    # and the row the summary line counts is unchanged by the wording
    assert not ir.InfusionRow(report).confirmed


def test_the_average_says_how_many_scans_it_holds(qapp):
    """
    The report averages the stable stretch of the spray and prints that
    spectrum, so the floor measured under it has to divide by the root of the
    scans it actually holds. Counting the range instead would make (b)
    optimistic by the ratio of the roots and print a scan count the spectrum
    does not have.
    """
    channel = NoisyChannel(n=100)
    mz, intensity = channel.spectrum_rt_range(0.0, 2.0)
    whole = infusion.noise_floor(channel, spectrum=(mz, intensity))
    part = infusion.noise_floor(channel, spectrum=(mz, intensity), scans=25)

    assert whole.scans == 100 and part.scans == 25
    assert part.per_scan == pytest.approx(whole.per_scan, rel=1e-9)
    assert part.scatter == pytest.approx(whole.scatter * 2.0, rel=1e-9)
    assert "divides by 5.0" in part.describe()
    # (a) reads the spectrum and knows nothing about the count, so it stands
    assert part.from_empty == pytest.approx(whole.from_empty, rel=1e-9)
