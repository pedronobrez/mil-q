"""
An infusion read scan by scan: the film, and the difference from the average.

A spray has no chromatography, so the average of the whole run is what the
Explorer shows — and the average is exactly what hides a transient at the
first scan, a burst part way through, or a fragment that only appears once
the spray settles. Two things put those back: the contour as a film, with the
run's total ion current beside it, the scans left out of the average marked,
and a Play that steps the spectrum pane through the run; and a Δ mode that
draws the scan minus that average.

What is tested here is the arithmetic and the items actually drawn. The
figures measured on the real acquisitions are in `contour-view.md` and
`direct-infusion.md`.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import infusion as infusion_rules  # noqa: E402
from milq.infusion import after_settling, run_range  # noqa: E402
from milq.ui.contour_view import PLAY_RATE  # noqa: E402
from milq.ui.explorer import (VIEW_CHROMATOGRAM, VIEW_CONTOUR,  # noqa: E402
                                   excluded_scans)
from tests.test_infusion import (FakeChannel, FakeSample, MZ, _explorer,  # noqa: E402
                                 _peak, gradient_sample, infusion_sample)


def _film(sample):
    """An Explorer on this sample, with the contour built and showing."""
    app, explorer = _explorer(sample)
    explorer.view_combo.setCurrentText(VIEW_CONTOUR)
    return app, explorer


def _close(app, explorer):
    explorer.deleteLater()
    app.processEvents()


# -- the strip and the marker ------------------------------------------------ #
def test_the_strip_is_the_channels_own_chromatogram(qapp=None):
    app, explorer = _film(infusion_sample())
    view = explorer.contour_view
    channel = explorer.active_ref.channel

    assert view.film_shown
    assert not view.strip.isHidden()
    x, y = view.strip_curve.getData()
    # the instrument's own trace, one point per scan — not a row of the grid,
    # whose rows may be several scans averaged and whose bins are wider than
    # the instrument's steps
    assert x == pytest.approx(channel.tic()[0])
    assert y == pytest.approx(channel.tic()[1])
    _close(app, explorer)


def test_the_scans_left_out_of_the_average_are_marked(qapp=None):
    app, explorer = _film(infusion_sample())
    view = explorer.contour_view
    times, values = explorer.active_ref.channel.tic()

    expected = excluded_scans(times, values)
    assert expected.any()                       # the settling second
    marked_x, _marked_y = view.strip_excluded.getData()
    assert marked_x == pytest.approx(times[expected])
    # and shaded on the surface itself, one region per run of excluded scans
    assert len(view.excluded_regions) == 1
    assert "left out of the average" in view.film_note.text()
    _close(app, explorer)


def test_the_settling_window_is_what_is_left_out_without_stable_scans():
    """The fallback is the rule the verdict already uses, not a new one."""
    times = np.linspace(0.0, 1.5, 160)
    values = np.full(160, 1000.0)
    excluded = excluded_scans(times, values)
    kept, _ = after_settling(times, values)
    assert times[~excluded] == pytest.approx(kept)
    assert int(excluded.sum()) == times.size - kept.size


def test_stable_scans_decides_the_marker_when_the_module_has_it(monkeypatch):
    """
    `infusion.stable_scans` is being written elsewhere; whatever shape it
    hands back, it is the authority — the marker must draw the average that
    is actually in force rather than a second opinion.
    """
    times = np.linspace(0.0, 1.5, 20)
    values = np.full(20, 1000.0)
    chosen = np.ones(20, dtype=bool)
    chosen[[3, 4, 19]] = False

    monkeypatch.setattr(infusion_rules, "stable_scans",
                        lambda x, y: chosen, raising=False)
    assert list(np.nonzero(excluded_scans(times, values))[0]) == [3, 4, 19]

    # the same answer as scan numbers rather than as a mask
    monkeypatch.setattr(infusion_rules, "stable_scans",
                        lambda x, y: np.nonzero(chosen)[0], raising=False)
    assert list(np.nonzero(excluded_scans(times, values))[0]) == [3, 4, 19]

    # and one that cannot be read at all falls back rather than guessing
    monkeypatch.setattr(infusion_rules, "stable_scans",
                        lambda x, y: "every other one", raising=False)
    fallback = excluded_scans(times, values)
    assert times[~fallback] == pytest.approx(after_settling(times, values)[0])


def test_a_chromatographic_run_gets_no_film(qapp=None):
    """There is nothing to add: the chromatogram pane draws the same trace
    over peaks that mean something."""
    app, explorer = _film(gradient_sample())
    view = explorer.contour_view
    assert not view.film_shown
    assert view.strip.isHidden()
    assert view.btn_play.isHidden()
    assert view.excluded_regions == []
    _close(app, explorer)


# -- Play -------------------------------------------------------------------- #
def test_play_steps_the_scan_spin_box_and_stops_at_the_end(qapp=None):
    app, explorer = _film(infusion_sample(n=130))
    view = explorer.contour_view
    scans = explorer.active_ref.channel.info.n_scans

    explorer.scan_spin.setValue(1)
    view.btn_play.setChecked(True)
    assert view.playing
    # ten scans a second at 1x, and the speed multiplies it
    assert view._interval_ms() == pytest.approx(1000.0 / PLAY_RATE)
    view.speed.setCurrentIndex(2)
    assert view._interval_ms() == pytest.approx(1000.0 / (PLAY_RATE * 20))
    assert view.playing                          # changing speed does not stop

    # a frame moves the spin box, which is what draws the spectrum
    for expected in range(2, 6):
        view._advance()
        assert explorer.scan_spin.value() == expected
        assert explorer.current_scan == expected - 1
        assert f"scan {expected}/{scans}" in explorer.spectrum.title

    # and the last scan ends the film rather than wrapping round to the first
    for _ in range(scans * 2):
        view._advance()
    assert not view.playing
    assert not view.btn_play.isChecked()
    assert explorer.scan_spin.value() == scans
    assert view.current_scan() == scans - 1
    _close(app, explorer)


def test_play_from_the_last_scan_starts_again_at_the_first(qapp=None):
    app, explorer = _film(infusion_sample(n=130))
    view = explorer.contour_view
    explorer.scan_spin.setValue(130)
    view.btn_play.setChecked(True)
    assert explorer.scan_spin.value() == 1
    view.stop_play()
    assert not view.playing
    _close(app, explorer)


def test_the_cursor_follows_whatever_moved_the_scan(qapp=None):
    app, explorer = _film(infusion_sample(n=130))
    view, channel = explorer.contour_view, explorer.active_ref.channel
    explorer.scan_spin.setValue(11)
    assert view.current_scan() == 10
    assert view.film_cursor.value() == pytest.approx(channel.rt_at_scan(10))
    assert view.strip_cursor.value() == pytest.approx(channel.rt_at_scan(10))
    assert "scan 11/130" in view.film_scan.text()
    _close(app, explorer)


def test_leaving_the_contour_leaves_no_timer_running(qapp=None):
    app, explorer = _film(infusion_sample(n=130))
    view = explorer.contour_view
    view.btn_play.setChecked(True)
    assert view.playing

    # Pause is on the surface, so a film must not be left running behind the
    # chromatogram with nothing on screen to stop it
    explorer.view_combo.setCurrentText(VIEW_CHROMATOGRAM)
    assert not view.playing
    assert not view.btn_play.isChecked()

    explorer.view_combo.setCurrentText(VIEW_CONTOUR)
    view.btn_play.setChecked(True)
    explorer.clear_views()
    assert not view.playing
    assert not view.film_shown
    _close(app, explorer)


# -- Δ from the average ------------------------------------------------------ #
def _changing_sample(n: int = 20) -> FakeSample:
    """
    A spray whose spectrum changes half way through, on a flat total.

    Flat, so the verdict is an infusion; changing, so the difference from the
    average has something in it to find. The total never moves, which is the
    point: this is the thing the strip cannot show and the average hides.
    """
    rt = np.linspace(0.0, 1.5, n)
    total = np.full(n, 50_000.0)

    def pattern(scan: int) -> np.ndarray:
        shape = _peak(343.0) if scan < n // 2 else _peak(289.0)
        return shape / float(np.sum(shape))

    product = FakeChannel(0, rt, total, pattern, precursor=430.34)
    return FakeSample([product])


def test_the_delta_mode_is_the_scan_minus_the_run_average(qapp=None):
    app, explorer = _explorer(_changing_sample())
    channel = explorer.active_ref.channel
    average = channel.spectrum_rt_range(*run_range(channel))[1]

    explorer.act_delta.setChecked(True)
    explorer.scan_spin.setValue(3)

    traces = explorer.spectrum.traces
    assert [t.key for t in traces] == ["spec", "avg"]
    scan = channel.spectrum(2)[1]
    assert traces[0].y == pytest.approx(scan - average)
    assert traces[1].y == pytest.approx(average)
    assert traces[0].x == pytest.approx(traces[1].x)
    # the difference is what the pane is showing, and says so
    assert "Δ from the run average" in explorer.spectrum.title
    assert traces[0].label == "scan 3 − run average"

    # a scan from the other half of the run differs the other way round
    explorer.scan_spin.setValue(18)
    assert explorer.spectrum.traces[0].y == pytest.approx(
        channel.spectrum(17)[1] - average)
    _close(app, explorer)


def test_the_pair_is_mirrored_so_the_average_hangs_below(qapp=None):
    """Through the switch that already exists, not a second plot type."""
    app, explorer = _explorer(_changing_sample())
    explorer.act_mirror.setChecked(False)
    explorer.act_delta.setChecked(True)
    assert explorer.act_mirror.isChecked()
    assert explorer.spectrum.mirrored

    average = explorer.spectrum.traces[1]
    conditioned = explorer.spectrum.condition(average)[1]
    drawn_y = explorer.spectrum._display(average, 1)[1]
    assert drawn_y == pytest.approx(-conditioned)     # below the axis

    # and Mirror goes back to what it was when Δ is turned off
    explorer.act_delta.setChecked(False)
    assert not explorer.act_mirror.isChecked()
    assert [t.key for t in explorer.spectrum.traces] == ["spec"]
    _close(app, explorer)


def test_a_scan_the_same_as_the_average_leaves_nothing(qapp=None):
    """The whole claim of the mode: what is left is what changed."""
    n = 20
    rt = np.linspace(0.0, 1.5, n)
    shape = _peak(343.0)
    same = FakeChannel(0, rt, np.full(n, 50_000.0),
                       lambda i: shape / float(np.sum(shape)),
                       precursor=430.34)
    app, explorer = _explorer(FakeSample([same]))
    explorer.act_delta.setChecked(True)
    explorer.scan_spin.setValue(7)
    assert explorer.spectrum.traces[0].y == pytest.approx(
        np.zeros(MZ.size), abs=1e-9)
    _close(app, explorer)


def test_the_average_is_read_once_however_many_scans_are_stepped(qapp=None):
    """Play would be a slideshow otherwise: 473 scans of a 242,308-point
    average is what the real infusions cost."""
    app, explorer = _explorer(_changing_sample())
    channel = explorer.active_ref.channel
    explorer.act_delta.setChecked(True)
    before = len(channel.reads)
    for scan in range(2, 12):
        explorer.scan_spin.setValue(scan)
    assert len(channel.reads) == before      # nothing re-read
    _close(app, explorer)


def test_the_delta_is_offered_on_an_infusion_and_nowhere_else(qapp=None):
    app, explorer = _explorer(infusion_sample())
    assert explorer.act_delta.isEnabled()
    explorer.act_delta.setChecked(True)

    # moving to a chromatographic sample turns it off rather than leaving a
    # difference against the average of a gradient on screen
    explorer.session.entries.clear()
    explorer.clear_views()
    from milq.samples import SampleEntry
    explorer.session.entries.append(
        SampleEntry("/d/grad.wiff", 0, "grad", sample=gradient_sample()))
    explorer.rebuild_tree()
    assert not explorer.act_delta.isEnabled()
    assert not explorer.act_delta.isChecked()
    assert "avg" not in [t.key for t in explorer.spectrum.traces]
    _close(app, explorer)


def test_the_film_and_the_delta_leave_an_ordinary_view_alone(qapp=None):
    """Nothing about a chromatographic run changed."""
    app, explorer = _explorer(gradient_sample())
    explorer.view_combo.setCurrentText(VIEW_CONTOUR)
    assert not explorer.contour_view.contour().is_empty
    explorer.view_combo.setCurrentText(VIEW_CHROMATOGRAM)
    assert not explorer.contour_view.film_shown
    assert not explorer.act_delta.isEnabled()
    assert "avg" not in [t.key for t in explorer.spectrum.traces]
    _close(app, explorer)


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
