"""
Scans a spray lost, left out of an infusion's average.

An electrospray is not steady for the whole of a run: it arcs, a droplet
reaches the cone, the needle wets. Three of the nine real bile-acid infusions
carry a transient at scan 1 of 2.8 – 4.4 times the median, and one of them
two more bursts mid-run. Averaged in, those scans are a fifth of a per cent
of the run's scans and up to 2.8% of its ion current, and they are not what
the compound looks like.

What is tested here is `infusion.stable_scans` — that it catches a transient
at the front, a burst in the middle and the scans that are still coming back
after one, and that it leaves an ordinary spray alone — `infusion.average_stable`
— that it is the reader's own average when nothing is left out, and the mean
of the kept scans when something is — and what the application does with
both: the pane's title, *Include unstable scans*, and the report's header.

The figures behind the thresholds are in `milq/infusion.py`.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import infusion_report  # noqa: E402
from milq.infusion import (SPRAY_JUMP, SPRAY_RECOVERED,  # noqa: E402
                                STABILITY_WINDOW, ScanMask, average_stable,
                                mask_for, run_range, stable_scans)
from milq.samples import SampleEntry  # noqa: E402

from .test_infusion import (FakeChannel, FakeSample, _peak,  # noqa: E402
                            gradient_sample)

#: the real infusions cycle every 0.25 s
CYCLE = 0.25 / 60.0

#: what `DCA-d4_TOFMSMS_Mix1` does over its eight worst scans, as multiples of
#: the level it was holding: two scans of nothing, a spike, a half recovery, a
#: dropout, another half recovery, and a spike five times the level
BURST = (0.01, 0.03, 0.64, 2.57, 0.63, 0.13, 0.74, 4.68)


def spray(n: int = 240, transient: float = 4.5, burst_at: int | None = 120,
          tail=(), seed: int = 5) -> FakeSample:
    """
    A minute of spraying at 50,000 counts, with whatever went wrong in it.

    `transient` is the multiplier on scan 1 — the one every real ZenoTOF
    infusion that misbehaves carries. `burst_at` drops `BURST` in mid-run.
    `tail` is a burst that comes back slowly: the multipliers after the spike.
    """
    rng = np.random.default_rng(seed)
    rt = np.arange(n) * CYCLE + CYCLE
    y = 50_000.0 * rng.normal(1.0, 0.02, n)
    if transient:
        y[1] *= transient
    if burst_at is not None:
        for offset, factor in enumerate(BURST):
            y[burst_at + offset] *= factor
    for offset, factor in enumerate(tail):
        y[180 + offset] *= factor
    product = FakeChannel(0, rt, y, lambda i: _peak(343.0) + 0.4 * _peak(289.0),
                          precursor=430.34)
    return FakeSample([product])


def entry_for(sample: FakeSample) -> SampleEntry:
    return SampleEntry("/d/mix1.wiff", 0, "mix1", sample=sample)


# --------------------------------------------------------------------------- #
# the mask
# --------------------------------------------------------------------------- #
def test_the_mask_catches_a_transient_and_a_burst():
    channel = spray().channels[0]
    mask = stable_scans(channel)

    # scan 1 and the eight scans of the burst, and nothing else
    assert list(np.flatnonzero(~mask.keep)) == [1] + list(range(120, 128))
    assert (mask.n_scans, mask.kept, mask.excluded) == (240, 231, 9)
    assert mask.excluded == mask.n_scans - mask.kept
    assert bool(mask) is True

    # the three scans of the burst that never passed SPRAY_JUMP on their own
    # are in it because they had not come back: 0.64, 0.63 and 0.74 of the
    # level are past SPRAY_RECOVERED and short of SPRAY_JUMP
    for offset, factor in enumerate(BURST):
        if SPRAY_RECOVERED < abs(factor - 1) <= SPRAY_JUMP:
            assert not mask.keep[120 + offset]

    # said in times, a single scan named and a stretch bounded
    assert mask.ranges == "0.008 min; 0.504–0.533 min, 8 scans"
    assert mask.summary() == ("240 scans, 231 averaged; 9 left out: "
                              "0.008 min; 0.504–0.533 min, 8 scans")
    # and the kept scans' own scatter, which is what the threshold is clear of
    assert mask.scatter < SPRAY_JUMP / 10


def test_the_scans_still_coming_back_go_with_the_burst():
    """A spike, then two scans on the way back, then the spray again."""
    channel = spray(burst_at=None, tail=(3.0, 1.4, 1.3, 1.15)).channels[0]
    mask = stable_scans(channel)

    # the spike is the seed; 1.4 and 1.3 are past SPRAY_RECOVERED so they go
    # with it, and 1.15 is not, so the walk stops there
    assert list(np.flatnonzero(~mask.keep)) == [1, 180, 181, 182]
    assert mask.keep[183]
    assert "0.754–0.762 min, 3 scans" in mask.ranges


def test_a_steady_spray_keeps_every_scan():
    channel = spray(transient=0.0, burst_at=None).channels[0]
    mask = stable_scans(channel)

    assert mask.excluded == 0
    assert mask.kept == mask.n_scans == 240
    assert mask.ranges == ""
    assert bool(mask) is False
    assert mask.summary() == "240 scans, all averaged"
    assert mask.segments() == [(0, 239)]


def test_a_run_too_short_to_have_a_baseline_keeps_everything():
    rt = np.arange(4) * CYCLE
    channel = FakeChannel(0, rt, np.array([10.0, 90.0, 10.0, 10.0]),
                          lambda i: _peak(343.0), precursor=430.34)
    mask = stable_scans(channel)

    assert mask.excluded == 0
    assert "too short" in mask.note
    assert "all averaged" in mask.summary()


def test_a_channel_that_will_not_read_says_so_and_masks_nothing():
    class Broken:
        def tic(self):
            raise OSError("the .wiff.scan is not beside it")

    mask = stable_scans(Broken())
    assert mask.n_scans == 0
    assert "could not be read" in mask.note


def test_the_threshold_sits_in_a_plateau():
    """
    The count does not move over the range the real files put it in.

    On the nine bile-acid infusions the widest departure of an undisturbed
    spray is 0.316 and the smallest inside a real burst is 0.870, and every
    threshold between gives the same answer. The synthetic run reproduces
    that, which is what says a figure was chosen rather than fitted.
    """
    channel = spray().channels[0]
    counts = {stable_scans(channel, jump=jump).excluded
              for jump in (0.35, 0.4, 0.45, 0.5, 0.6, 0.75)}
    assert counts == {9}
    widths = {stable_scans(channel, window=w).excluded
              for w in (21, 31, 41)}
    assert widths == {9}


def test_a_chromatographic_run_is_not_masked():
    """
    A peak departs from its neighbours further than any spray does.

    `Average whole run` is offered on any channel, so the gate is the
    infusion verdict and not the arithmetic: on a twenty-minute gradient the
    rule on its own leaves out the only scans worth keeping.
    """
    sample = gradient_sample()
    channel = sample.channels[1]
    assert stable_scans(channel).excluded > 20        # the peaks themselves
    gated = mask_for(sample, channel)
    assert gated.excluded == 0
    assert "not read as a direct infusion" in gated.note


# --------------------------------------------------------------------------- #
# the average
# --------------------------------------------------------------------------- #
def test_a_full_mask_is_the_readers_own_average():
    channel = spray(transient=0.0, burst_at=None).channels[0]
    mask = stable_scans(channel)
    assert mask.excluded == 0

    theirs = channel.spectrum_rt_range(*run_range(channel))
    channel.reads.clear()
    mine = average_stable(channel, mask)

    assert mine[0] == pytest.approx(theirs[0], abs=1e-9)
    assert mine[1] == pytest.approx(theirs[1], rel=1e-9, abs=1e-9)
    # one read, over the whole run: the reader's arithmetic, not ours
    assert channel.reads == [(pytest.approx(channel.rt[0]),
                              pytest.approx(channel.rt[-1]))]


def test_the_stable_average_is_the_mean_of_the_kept_scans():
    channel = spray().channels[0]
    mask = stable_scans(channel)
    mz, intensity = average_stable(channel, mask)

    kept = [channel.spectrum(i)[1] for i in np.flatnonzero(mask.keep)]
    assert intensity == pytest.approx(np.mean(kept, axis=0), rel=1e-9)
    assert mz == pytest.approx(channel.mz)

    # one read per surviving stretch, and the stretches are the kept scans
    assert mask.segments() == [(0, 0), (2, 119), (128, 239)]
    assert len(channel.reads) == 3

    # and it is not the whole run's average: the burst was carrying signal
    whole = channel.spectrum_rt_range(*run_range(channel))[1]
    assert intensity.max() != pytest.approx(whole.max(), rel=1e-6)
    assert intensity.max() < whole.max()


def test_an_unreadable_channel_averages_to_nothing():
    class Empty:
        rt = np.zeros(0)

        def tic(self):
            return np.zeros(0), np.zeros(0)

    mz, intensity = average_stable(Empty(), ScanMask(np.zeros(0, dtype=bool),
                                                     np.zeros(0)))
    assert mz.size == intensity.size == 0


# --------------------------------------------------------------------------- #
# what the Explorer shows
# --------------------------------------------------------------------------- #
def _explorer(sample):
    from PyQt6 import QtWidgets

    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    session = Session()
    session.entries.append(entry_for(sample))
    explorer = ExplorerWorkspace(session)
    explorer.rebuild_tree()
    return app, explorer


def test_the_pane_averages_the_steady_scans_and_says_which():
    app, explorer = _explorer(spray())
    channel = explorer.active_ref.channel

    assert explorer.include_unstable_scans() is False
    assert ("240 scans, 231 averaged; 9 left out: 0.008 min; "
            "0.504–0.533 min, 8 scans" in explorer.spectrum.title)

    mz, intensity = explorer._current_spectrum()
    kept = [channel.spectrum(i)[1]
            for i in np.flatnonzero(stable_scans(channel).keep)]
    assert intensity.max() == pytest.approx(np.mean(kept, axis=0).max())

    explorer.deleteLater()
    app.processEvents()


def test_include_unstable_scans_puts_them_back():
    app, explorer = _explorer(spray())
    channel = explorer.active_ref.channel

    explorer.act_unstable.setChecked(True)
    assert explorer.include_unstable_scans() is True
    # the toggle redraws the whole-run average it is looking at
    assert "average of 240 scans" in explorer.spectrum.title
    assert "left out" not in explorer.spectrum.title
    whole = channel.spectrum_rt_range(*run_range(channel))[1]
    assert explorer._current_spectrum()[1].max() == pytest.approx(whole.max())

    explorer.act_unstable.setChecked(False)
    assert "9 left out" in explorer.spectrum.title

    explorer.deleteLater()
    app.processEvents()


def test_a_steady_spray_keeps_the_title_it_always_had():
    app, explorer = _explorer(spray(transient=0.0, burst_at=None))
    assert "average of 240 scans (infusion)" in explorer.spectrum.title
    assert "left out" not in explorer.spectrum.title
    explorer.deleteLater()
    app.processEvents()


# --------------------------------------------------------------------------- #
# what the report says
# --------------------------------------------------------------------------- #
def test_the_report_header_says_how_many_were_averaged():
    sample = spray()
    entry = entry_for(sample)
    report = infusion_report.report_for(entry, sample.channels[0],
                                        measure_precursor=False)

    assert report.scans == 240
    assert report.scans_averaged() == 231
    assert report.scans_cell() == "231 of 240"
    assert report.scans_line() == ("240 scans, 231 averaged; 9 left out: "
                                   "0.008 min; 0.504–0.533 min, 8 scans")
    html = infusion_report._identity(report)
    assert "Scans averaged" in html
    assert "231 averaged; 9 left out" in html

    # and the verdict carries a sentence about it, last, after the checks
    said = report.sentences()
    assert "9 scan(s) of 240 were left out of the average" in said[-1]
    assert f"{STABILITY_WINDOW} scans" in said[-1]


def test_the_report_of_a_steady_spray_says_nothing_about_scans():
    sample = spray(transient=0.0, burst_at=None)
    report = infusion_report.report_for(entry_for(sample), sample.channels[0],
                                        measure_precursor=False)

    assert report.scans_cell() == "240"
    assert report.scans_line() == "240 scans, all averaged"
    assert not any("left out of the average" in s for s in report.sentences())


def test_a_report_asked_for_the_whole_run_says_it_kept_them():
    sample = spray()
    report = infusion_report.report_for(entry_for(sample), sample.channels[0],
                                        measure_precursor=False,
                                        include_unstable=True)

    assert report.scans_averaged() == 240
    assert report.scans_cell() == "240"
    assert "9 unstable scan(s) kept on request" in report.scans_line()
    assert "averaged in anyway" in report.sentences()[-1]
