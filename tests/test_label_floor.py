"""
The label floor and the handle that sets it.

The floor is how tall a peak has to be, against the tallest one *in view*,
before its mass is written next to it. It starts at `LABEL_MIN_RELATIVE` and
the reader moves it — by dragging the triangle in the axis margin, or by
typing into the Explorer's spin box, either of which moves the other.

Everything here is arithmetic on made-up spectra. What the floor is worth on
real data is in `milq/ui/plots.py`, next to the constants it was
measured against.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq import labels as label_rule  # noqa: E402
from milq import spectra_compare as sc  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.ui import plots  # noqa: E402
from milq.ui.explorer import ExplorerWorkspace  # noqa: E402
from milq.ui.plots import SpectrumView, Trace  # noqa: E402


@pytest.fixture(autouse=True)
def _one_font_everywhere(monkeypatch):
    """The label width decides a collision, and the platform's default font
    made Windows draw a different set than macOS; pin it, as the budget
    tests do."""
    monkeypatch.setattr(plots, "_label_half_width", lambda text: 22.0)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def _sticks(peaks, low=100.0, high=1000.0, step=0.005, width=0.02):
    """A profile spectrum with a Gaussian at each (m/z, height)."""
    mz = np.arange(low, high, step)
    y = np.zeros_like(mz)
    for centre, height in peaks:
        y += height * np.exp(-0.5 * ((mz - centre) / width) ** 2)
    return mz, y


#: tall peaks and small ones, alternating along the axis and 200 Da apart —
#: far enough that the collision rule is not what decides, so that what a
#: test measures is the floor. The small ones are 0.5% of the tall: under
#: the default floor, over a lowered one.
TALL = [(150.0 + 200.0 * i, 100_000.0) for i in range(5)]
SMALL = [(250.0 + 200.0 * i, 500.0) for i in range(4)]


def _view(qapp, peaks=None, width=980, height=420):
    view = SpectrumView()
    view.resize(width, height)
    view.show()
    mz, y = _sticks(peaks if peaks is not None else TALL + SMALL)
    view.set_traces([Trace("spec", "spectrum", mz, y, "#1f77b4")])
    view.autoscale()
    qapp.processEvents()
    return view


def _drawn(view) -> list[float]:
    return sorted(round(float(t.mz), 2) for t in view._labels)


# --------------------------------------------------------------------------- #
# the floor itself
# --------------------------------------------------------------------------- #
def test_the_floor_starts_where_the_rule_says_and_lowering_it_names_more(qapp):
    view = _view(qapp)
    assert view.label_floor == label_rule.LABEL_MIN_RELATIVE
    at_default = _drawn(view)
    # the companions are 0.5% of the tall peaks: below the 2% floor
    assert at_default == sorted(round(mz, 2) for mz, _h in TALL)

    view.set_label_floor(0.002)
    qapp.processEvents()
    lowered = _drawn(view)
    assert len(lowered) > len(at_default)
    assert set(at_default) <= set(lowered)
    for mz, _h in SMALL:
        assert round(mz, 2) in lowered
    view.deleteLater()
    qapp.processEvents()


def test_raising_the_floor_names_fewer(qapp):
    view = _view(qapp, [(150.0, 100_000.0), (350.0, 30_000.0), (550.0, 3_000.0)])
    view.set_label_floor(0.02)
    qapp.processEvents()
    assert len(_drawn(view)) == 3
    view.set_label_floor(0.5)          # only peaks at half the tallest
    qapp.processEvents()
    assert _drawn(view) == [150.0]
    view.deleteLater()
    qapp.processEvents()


def test_the_floor_is_a_fraction_so_it_survives_a_zoom(qapp):
    """
    Zoomed into a quiet stretch the floor is measured against what is *there*,
    not against a base peak that is off screen — which is the whole reason it
    is stored as a fraction.
    """
    view = _view(qapp, [(150.0, 100_000.0), (600.0, 1_000.0), (640.0, 300.0)])
    view.plot.setXRange(560.0, 700.0, padding=0)
    qapp.processEvents()
    assert view._tallest_in_view() == pytest.approx(1_000.0, rel=0.05)
    view.set_label_floor(0.5)
    qapp.processEvents()
    assert _drawn(view) == [600.0]      # 640 is 30% of the tallest in view
    view.set_label_floor(0.2)
    qapp.processEvents()
    assert _drawn(view) == [600.0, 640.0]
    view.deleteLater()
    qapp.processEvents()


def test_the_floor_is_clamped_and_survives_nonsense(qapp):
    view = _view(qapp)
    view.set_label_floor(-3.0)
    assert view.label_floor == plots.FLOOR_MIN
    view.set_label_floor(9.0)
    assert view.label_floor == plots.FLOOR_MAX
    view.set_label_floor(float("nan"))
    assert view.label_floor == plots.FLOOR_MAX
    view.set_label_floor("not a number")
    assert view.label_floor == plots.FLOOR_MAX
    view.deleteLater()
    qapp.processEvents()


# --------------------------------------------------------------------------- #
# the handle
# --------------------------------------------------------------------------- #
def test_the_handle_sits_at_the_floor_in_the_axis_margin(qapp):
    view = _view(qapp)
    handle = view.floor_handle
    assert handle.isVisible()
    box = view.viewbox.sceneBoundingRect()
    # in the margin the axis reserves, never over the data
    assert handle.pos().x() <= box.left()
    assert handle.pos().x() > view.plot.getAxis("left").sceneBoundingRect().left()
    # and at the height the floor asks for
    top = view._tallest_in_view()
    expected = view.viewbox.mapViewToScene(
        QtCore.QPointF(0.0, top * view.label_floor)).y()
    at_default = float(handle.pos().y())
    assert at_default == pytest.approx(expected, abs=1.0)

    view.set_label_floor(0.5)
    qapp.processEvents()
    raised = view.viewbox.mapViewToScene(
        QtCore.QPointF(0.0, top * 0.5)).y()
    assert float(handle.pos().y()) == pytest.approx(raised, abs=1.0)
    assert float(handle.pos().y()) < at_default   # further up the screen
    view.deleteLater()
    qapp.processEvents()


def test_dragging_the_handle_down_moves_the_floor_and_names_more(qapp):
    view = _view(qapp)
    before = _drawn(view)
    start = view.floor_handle.pos().y()
    # drag towards the bottom of the plot: a lower floor
    view._floor_dragged(start + 40.0)
    qapp.processEvents()
    assert view.label_floor < label_rule.LABEL_MIN_RELATIVE
    assert view.floor_line.isVisible()      # the level is shown while dragging
    view.floor_handle.sigReleased.emit()
    qapp.processEvents()
    assert not view.floor_line.isVisible()
    after = _drawn(view)
    assert len(after) > len(before)
    assert set(before) <= set(after)
    view.deleteLater()
    qapp.processEvents()


def test_a_drag_leaves_the_pool_alone_until_the_mouse_comes_up(qapp):
    """
    Filling the pool walks every point of the spectrum; a drag would do it on
    every mouse move. So the drag reads the pool as it stands and the release
    fills it again.
    """
    view = _view(qapp)
    fills = []
    original = SpectrumView._after_traces_changed

    def counted(self):
        fills.append(1)
        original(self)

    SpectrumView._after_traces_changed = counted
    try:
        start = view.floor_handle.pos().y()
        for step in range(1, 6):
            view._floor_dragged(start + 8.0 * step)
        qapp.processEvents()
        assert fills == []
        view.floor_handle.sigReleased.emit()
        qapp.processEvents()
        assert len(fills) == 1
    finally:
        SpectrumView._after_traces_changed = original
    view.deleteLater()
    qapp.processEvents()


def test_double_clicking_the_handle_puts_the_floor_back(qapp):
    view = _view(qapp)
    view.set_label_floor(0.4)
    qapp.processEvents()
    assert view.label_floor == 0.4
    view.floor_handle.sigReset.emit()
    qapp.processEvents()
    assert view.label_floor == label_rule.LABEL_MIN_RELATIVE
    assert _drawn(view) == sorted(round(mz, 2) for mz, _h in TALL)
    view.deleteLater()
    qapp.processEvents()


def test_the_handle_goes_away_when_the_labels_do(qapp):
    view = _view(qapp)
    assert view.floor_handle.isVisible()
    view.set_labels_enabled(False)
    qapp.processEvents()
    assert not view.floor_handle.isVisible()
    view.set_labels_enabled(True)
    qapp.processEvents()
    assert view.floor_handle.isVisible()
    view.deleteLater()
    qapp.processEvents()


# --------------------------------------------------------------------------- #
# the spin box, the settings and the print
# --------------------------------------------------------------------------- #
def _explorer(qapp):
    explorer = ExplorerWorkspace(Session())
    mz, y = _sticks(TALL + SMALL)
    explorer.spectrum.set_traces([Trace("spec", "spectrum", mz, y, "#1f77b4")])
    explorer.spectrum.set_title("sample A · scan 3")
    explorer.spectrum.resize(980, 420)
    explorer.spectrum.autoscale()
    qapp.processEvents()
    return explorer


def test_the_spin_box_and_the_handle_stay_in_step(qapp):
    explorer = _explorer(qapp)
    assert explorer.floor_spin.value() == pytest.approx(
        label_rule.LABEL_MIN_RELATIVE * 100.0)

    explorer.floor_spin.setValue(0.50)
    qapp.processEvents()
    assert explorer.spectrum.label_floor == pytest.approx(0.005)

    explorer.spectrum.set_label_floor(0.25)
    qapp.processEvents()
    assert explorer.floor_spin.value() == pytest.approx(25.0)

    explorer.spectrum.reset_label_floor()
    qapp.processEvents()
    assert explorer.floor_spin.value() == pytest.approx(2.0)
    explorer.deleteLater()
    qapp.processEvents()


def test_the_floor_is_saved_and_restored(qapp):
    explorer = _explorer(qapp)
    explorer.floor_spin.setValue(0.75)
    explorer.save_settings()
    stored = explorer.settings.value("view/label_floor", type=float)
    assert stored == pytest.approx(0.75)
    explorer.deleteLater()
    qapp.processEvents()

    again = _explorer(qapp)
    assert again.floor_spin.value() == pytest.approx(0.75)
    assert again.spectrum.label_floor == pytest.approx(0.0075)
    again.floor_spin.setValue(label_rule.LABEL_MIN_RELATIVE * 100.0)
    again.save_settings()
    again.deleteLater()
    qapp.processEvents()


def test_the_printed_comparison_is_labelled_at_the_panes_floor(qapp):
    explorer = _explorer(qapp)
    explorer.pin_spectrum()
    explorer.floor_spin.setValue(0.20)
    qapp.processEvents()
    comparison = explorer.session.spectra_comparison
    assert comparison is not None
    assert comparison.label_floor == pytest.approx(0.002)

    trace = comparison.traces[0]
    named = [round(mz, 2) for mz, _h in comparison.label_peaks(trace, 100.0, 1000.0)]
    for mz, _h in SMALL:
        assert round(mz, 2) in named

    # and back up again: the small peaks are no longer offered
    explorer.floor_spin.setValue(2.0)
    qapp.processEvents()
    comparison = explorer.session.spectra_comparison
    assert comparison.label_floor == pytest.approx(0.02)
    named = [round(mz, 2) for mz, _h in comparison.label_peaks(trace, 100.0, 1000.0)]
    for mz, _h in SMALL:
        assert round(mz, 2) not in named
    explorer.deleteLater()
    qapp.processEvents()


def test_a_comparison_built_without_a_floor_keeps_the_default():
    mz, y = _sticks(TALL + SMALL)
    plain = sc.SpectrumComparison(traces=[
        sc.SpectrumTrace("one", mz, y), sc.SpectrumTrace("two", mz, y)])
    assert plain.label_floor == label_rule.LABEL_MIN_RELATIVE
    named = [round(m, 2) for m, _h in plain.label_peaks(plain.traces[0], 100.0, 1000.0)]
    assert round(SMALL[0][0], 2) not in named


def test_the_print_honours_a_floor_it_is_handed(qapp):
    """The paint is the last word: a peak the floor let through has to reach
    the page."""
    from PyQt6 import QtGui

    mz, y = _sticks(TALL + SMALL)
    pair = [sc.SpectrumTrace("one", mz, y), sc.SpectrumTrace("two", mz, y * 0.9)]
    high = sc.SpectrumComparison(traces=list(pair), title="t", label_floor=0.02)
    low = sc.SpectrumComparison(traces=list(pair), title="t", label_floor=0.002)
    counts = []
    for comparison in (high, low):
        image = sc.render_image(comparison, width=900, height=420)
        counts.append(_ink(image, QtGui))
    # more labels means more ink; the drawing is otherwise identical
    assert counts[1] > counts[0]


def _ink(image, QtGui) -> int:
    """Dark pixels over the whole drawing. The two renderings hold the same
    traces, so whatever differs is a label."""
    dark = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if QtGui.QColor(image.pixel(x, y)).lightness() < 160:
                dark += 1
    return dark
