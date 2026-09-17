"""Tests for the view-level transforms of the plot panes.

These need a QApplication but no window is ever shown.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq.ui.plots import ChromatogramView, SpectrumView, Trace


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def two_traces():
    x = np.linspace(0, 10, 500)
    y1 = np.exp(-((x - 5) ** 2) / 0.1) * 1000
    y2 = np.exp(-((x - 5) ** 2) / 0.1) * 400
    return [
        Trace("a", "first", x, y1, "#1f77b4"),
        Trace("b", "second", x, y2, "#d62728"),
    ]


def test_mirror_flips_every_other_trace(qapp, two_traces):
    view = ChromatogramView()
    view.set_traces(two_traces)
    view.set_mirror(True)
    _, first = view._display(two_traces[0], 0)
    _, second = view._display(two_traces[1], 1)
    assert first.max() > 0
    assert second.min() < 0


def test_cascade_offsets_shift_x_and_y(qapp, two_traces):
    view = ChromatogramView()
    view.set_traces(two_traces)
    view.set_offsets(0.5, 20.0)
    x0, y0 = view._display(two_traces[0], 0)
    x1, y1 = view._display(two_traces[1], 1)
    assert x1[0] == pytest.approx(x0[0] + 0.5)
    assert y1.min() > y0.min()


def test_relative_labels_report_distance_to_marker(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    assert view._label_for(5.0) == "5.0000"
    view.add_marker(6.0, snap_to_peak=False)
    assert view._label_for(6.0) == "6.0000"      # sits on the marker
    assert view._label_for(5.0) == "-1.0000"     # one unit below it


def test_relative_labels_can_be_turned_off(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    view.add_marker(6.0, snap_to_peak=False)
    view.set_relative_labels(False)
    assert view._label_for(5.0) == "5.0000"


def test_marker_snaps_to_nearest_peak(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    view.add_marker(5.05)
    assert view.markers[0] == pytest.approx(5.0, abs=0.05)


def test_centroid_mode_shortens_the_axis(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    profile_x, _ = view.conditioned("a")
    view.set_centroid(True)
    centroid_x, _ = view.conditioned("a")
    assert centroid_x.size < profile_x.size
    assert view.centroided


def test_overlay_is_anchored_on_the_measured_monoisotopic_peak(qapp):
    """A minor ion's overlay must match its own height, not the base peak's."""
    mz = np.array([100.0, 200.0, 201.0034])
    intensity = np.array([10_000.0, 500.0, 100.0])  # base peak is elsewhere
    view = SpectrumView()
    view.set_traces([Trace("s", "spectrum", mz, intensity, "#1f77b4")])
    pattern = [(200.0, 1.0), (201.0034, 0.2)]
    scale = view._overlay_scale(pattern)
    assert scale == pytest.approx(500.0)          # anchored on m/z 200, not 10000
    assert scale * pattern[1][1] == pytest.approx(100.0)


def test_overlay_falls_back_to_the_base_peak_when_the_ion_is_absent(qapp):
    mz = np.array([100.0, 150.0])
    intensity = np.array([10_000.0, 500.0])
    view = SpectrumView()
    view.set_traces([Trace("s", "spectrum", mz, intensity, "#1f77b4")])
    assert view._overlay_scale([(400.0, 1.0)]) == pytest.approx(10_000.0)


def test_overlay_can_be_set_and_cleared(qapp):
    mz = np.linspace(100, 200, 100)
    view = SpectrumView()
    view.set_traces([Trace("s", "spectrum", mz, np.ones(100), "#1f77b4")])
    assert not view.has_overlay
    view.set_overlay([(150.0, 1.0), (151.0, 0.2)], "C10H20O")
    assert view.has_overlay
    view.clear_overlay()
    assert not view.has_overlay


def test_peak_panels_survive_repainting(qapp):
    """
    Regression: axis tick fonts built from an empty family name segfaulted Qt
    the moment a panel measured its tick labels.
    """
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakReviewGrid

    grid = PeakReviewGrid()
    grid.resize(900, 500)
    grid.show()
    x = np.linspace(12.0, 14.0, 300)
    y = np.exp(-((x - 13.0) ** 2) / 0.005) * 1000
    items = []
    for i in range(6):
        result = PeakResult(f"s{i}", f"sample {i}", "Oxy", area=1000.0 + i,
                            rt=13.0, start_rt=12.8, end_rt=13.2, snr=20.0)
        items.append((result, x, y, (12.7, 13.3)))
    grid.set_items("Oxy", items)
    for _ in range(5):
        qapp.processEvents()
        grid.grab()
    assert len(grid._items) == 6


def test_peak_grid_pages_and_selection(qapp):
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakReviewGrid

    grid = PeakReviewGrid()
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(1)
    x = np.linspace(0, 10, 50)
    items = [
        (PeakResult(f"s{i}", f"sample {i}", "Oxy", area=1.0, rt=5.0,
                    start_rt=4.0, end_rt=6.0), x, x * 0 + i, None)
        for i in range(5)
    ]
    grid.set_items("Oxy", items)
    assert grid.page_size == 2
    assert grid.page_count == 3
    grid.select("s4")           # last item, on the final page
    assert grid._page == 2
    grid.set_page(0)
    assert grid.page_label.text() == "1/3"


def test_peak_panel_reports_a_missing_peak(qapp):
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakPanel

    panel = PeakPanel()
    result = PeakResult("s1", "QC", "Oxy", note="no peak above noise")
    panel.set_data(result, np.linspace(0, 10, 20), np.zeros(20), None)
    assert not panel._band.isVisible()
    assert panel.sample_key == "s1"


def test_peak_grid_zoom_modes(qapp):
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakReviewGrid

    grid = PeakReviewGrid()
    result = PeakResult("s", "QC", "Oxy", area=10.0, rt=13.1,
                        start_rt=13.0, end_rt=13.2, snr=20.0)
    expected = (12.6, 13.6)

    grid.zoom_combo.setCurrentIndex(0)                  # expected window
    lo, hi = grid._x_range(result, expected)
    assert lo == pytest.approx(11.1) and hi == pytest.approx(15.1)

    grid.zoom_combo.setCurrentIndex(1)                  # tight on the peak
    lo, hi = grid._x_range(result, expected)
    assert lo == pytest.approx(12.8) and hi == pytest.approx(13.4)

    grid.zoom_combo.setCurrentIndex(2)                  # whole run
    assert grid._x_range(result, expected) is None


def test_peak_grid_zoom_without_an_expected_window(qapp):
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakReviewGrid

    grid = PeakReviewGrid()
    grid.zoom_combo.setCurrentIndex(0)
    missing = PeakResult("s", "QC", "Oxy")
    assert grid._x_range(missing, None) is None
    found = PeakResult("s", "QC", "Oxy", area=1.0, start_rt=5.0, end_rt=6.0)
    assert grid._x_range(found, None) == pytest.approx((4.0, 7.0))


def test_a_centroided_spectrum_is_not_centroided_a_second_time(qapp):
    """
    pick_peaks centroids around each maximum. Run over sticks that are already
    centroids it averages a stick with its neighbours, and the mass moves — a
    ceramide's 264.2668 was reported as 264.1181, 149 mDa out.
    """
    from milq.ui.plots import SpectrumView, Trace

    # one clean gaussian peak in profile, the way a TOF records it
    centre, width = 264.2668, 0.006
    x = np.linspace(centre - 0.05, centre + 0.05, 201)
    y = 100.0 * np.exp(-((x - centre) ** 2) / (2 * width ** 2))

    view = SpectrumView()
    view.resize(700, 300)
    view.set_traces([Trace("s", "peak", x, y, "#1f77b4")])
    for centroid in (False, True):
        view.set_centroid(centroid)
        qapp.processEvents()
        found = view.peaks_of_current(max_peaks=5)
        assert found, centroid
        assert found[0][0] == pytest.approx(centre, abs=2e-3), centroid
    view.close()


# -- how far the view may go -------------------------------------------------- #
@pytest.fixture
def fenced(qapp):
    from milq.ui.plots import ChromatogramView, Trace

    x = np.linspace(0, 21.5, 400)
    y = 1e6 * np.exp(-((x - 12) ** 2) / 2) + 5e4
    view = ChromatogramView()
    view.resize(800, 400)
    view.set_traces([Trace("a", "TIC", x, y, "#1f77b4")])
    view.autoscale()
    qapp.processEvents()
    yield view
    view.close()


def test_fit_lands_on_the_data_and_not_beside_it(qapp, fenced):
    lo, hi = fenced.plot.getViewBox().viewRange()[0]
    # it used to pad to -0.74 .. 22.17 around a run of 0 .. 21.5
    assert lo == pytest.approx(0.0, abs=1e-6)
    assert hi == pytest.approx(21.5, abs=0.01)


def test_panning_into_negative_time_is_refused(qapp, fenced):
    box = fenced.plot.getViewBox()
    box.setRange(xRange=(-50.0, -10.0), padding=0)
    qapp.processEvents()
    assert box.viewRange()[0][0] >= 0.0


def test_panning_below_zero_intensity_is_refused(qapp, fenced):
    box = fenced.plot.getViewBox()
    box.setRange(yRange=(-1e6, -1e5), padding=0)
    qapp.processEvents()
    assert box.viewRange()[1][0] >= 0.0


def test_zooming_out_past_the_data_is_refused(qapp, fenced):
    box = fenced.plot.getViewBox()
    box.setRange(xRange=(-500.0, 500.0), padding=0)
    qapp.processEvents()
    lo, hi = box.viewRange()[0]
    assert lo >= 0.0 and hi <= 21.6


def test_a_mirrored_trace_keeps_the_room_it_actually_uses(qapp):
    """The fence is against empty space, not against data that goes negative."""
    from milq.ui.plots import ChromatogramView, Trace

    x = np.linspace(0, 20, 200)
    view = ChromatogramView()
    view.resize(800, 400)
    view.set_traces([
        Trace("a", "sample", x, 1e6 * np.exp(-((x - 10) ** 2)), "#1f77b4"),
        Trace("b", "blank", x, 6e5 * np.exp(-((x - 11) ** 2)), "#d62728"),
    ])
    view.set_mirror(True)
    view.autoscale()
    qapp.processEvents()
    assert view.plot.getViewBox().viewRange()[1][0] < -1e5
    view.close()


def test_no_traces_leaves_the_view_unfenced(qapp):
    from milq.ui.plots import ChromatogramView

    view = ChromatogramView()
    view.resize(400, 300)
    view.autoscale()          # would raise if the empty case were not handled
    qapp.processEvents()
    view.close()


# -- what the review panel shows was integrated ------------------------------- #
def test_the_shaded_area_is_the_peak_over_its_baseline(qapp):
    """
    The band said where the limits were, which a reader takes for the area —
    and on a peak a couple of points wide the two look nothing alike.
    """
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakPanel

    x = np.linspace(0.0, 10.0, 400)
    y = 1000.0 * np.exp(-((x - 5.0) ** 2) / (2 * 0.1 ** 2)) + 50.0
    result = PeakResult(sample_key="s", sample_name="S", component="c",
                        area=100.0, height=1000.0, rt=5.0,
                        start_rt=4.6, end_rt=5.4)

    panel = PeakPanel()
    panel.resize(300, 200)
    panel.set_data(result, x, y, expected=(4.0, 6.0))
    qapp.processEvents()

    top_x, top_y = panel._area_top.getData()
    base_x, base_y = panel._area_base.getData()
    assert len(top_x) > 2
    assert top_x.min() >= 4.6 and top_x.max() <= 5.4
    # the same straight baseline the integration draws between the limits
    assert base_y[0] == pytest.approx(top_y[0], abs=1.0)
    assert base_y[-1] == pytest.approx(top_y[-1], abs=1.0)
    assert top_y.max() > base_y.max()
    panel.close()


def test_a_panel_with_no_peak_shades_nothing(qapp):
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakPanel

    x = np.linspace(0.0, 10.0, 100)
    y = np.zeros_like(x)
    panel = PeakPanel()
    panel.resize(300, 200)
    panel.set_data(PeakResult(sample_key="s", sample_name="S", component="c"),
                   x, y, expected=None)
    qapp.processEvents()
    assert len(panel._area_top.getData()[0] or []) == 0
    panel.close()


def test_a_review_panel_cannot_be_zoomed_off_its_trace(qapp):
    from milq.quantify import PeakResult
    from milq.ui.peak_review import PeakPanel

    x = np.linspace(2.0, 8.0, 200)
    y = 500.0 * np.exp(-((x - 5.0) ** 2) / (2 * 0.1 ** 2))
    panel = PeakPanel()
    panel.resize(300, 200)
    panel.set_data(PeakResult(sample_key="s", sample_name="S", component="c",
                              rt=5.0, start_rt=4.7, end_rt=5.3, height=500.0,
                              area=1.0),
                   x, y, expected=None)
    qapp.processEvents()
    box = panel.getViewBox()
    box.setRange(xRange=(-100.0, 100.0), padding=0)
    qapp.processEvents()
    lo, hi = box.viewRange()[0]
    assert lo >= 2.0 - 1e-6 and hi <= 8.0 + 1e-6
    panel.close()


# -- room above the tallest peak for its label ------------------------------- #
#
# The complaint that started these: on a short pane the m/z of the base peak
# was sliced in half by the top of the window. pyqtgraph pads an auto-ranged
# view by a share of the data range, and a share that clears a 21-pixel label
# in a tall pane does not clear it in a short one.


def _spectrum_trace():
    mz = np.linspace(200, 700, 4000)
    y = np.zeros_like(mz)
    for centre, height in [(264.2686, 1_000_000), (282.2791, 420_000),
                           (520.5087, 260_000)]:
        y += height * np.exp(-0.5 * ((mz - centre) / 0.02) ** 2)
    return Trace("s", "MS2", mz, y, "#234b8c")


def _clearance(view, labels) -> float:
    """Pixels between the top of the highest label and the top of the pane."""
    top = view.viewbox.sceneBoundingRect().top()
    return min(item.sceneBoundingRect().top() - top for item in labels)


@pytest.mark.parametrize("height", [220, 300, 400, 700])
def test_peak_labels_stay_inside_the_window(qapp, height):
    view = SpectrumView()
    view.resize(900, height)
    view.set_traces([_spectrum_trace()])
    view.show()
    qapp.processEvents()
    view.autoscale()
    qapp.processEvents()
    assert view._labels
    assert _clearance(view, view._labels) >= 0


def test_the_headroom_is_what_keeps_them_in(qapp):
    """Without it the same pane clips the label, so the room is doing the work."""
    view = SpectrumView()
    view.resize(900, 260)
    view.set_traces([_spectrum_trace()])
    view.show()
    view._headroom_px = lambda: 0.0          # the behaviour before the fix
    qapp.processEvents()
    view.autoscale()
    qapp.processEvents()
    assert _clearance(view, view._labels) < 0


def test_headroom_survives_being_made_shorter(qapp):
    """The room is measured in pixels, so shrinking the pane has to re-fence."""
    view = SpectrumView()
    view.resize(900, 700)
    view.set_traces([_spectrum_trace()])
    view.show()
    qapp.processEvents()
    view.autoscale()
    qapp.processEvents()
    view.resize(900, 230)
    qapp.processEvents()
    assert _clearance(view, view._labels) >= 0


def test_apex_labels_stay_inside_the_window(qapp, two_traces):
    """Chromatogram labels stack two rows high, and need room for both."""
    view = ChromatogramView()
    view.resize(900, 240)
    view.set_traces(two_traces)
    view.show()
    qapp.processEvents()
    view.autoscale()
    qapp.processEvents()
    assert view._apex_labels
    assert _clearance(view, view._apex_labels) >= 0


def test_match_labels_stay_inside_the_window(qapp):
    """A match label sits higher above the peak than an m/z label does."""
    view = SpectrumView()
    view.resize(900, 240)
    view.set_traces([_spectrum_trace()])
    view.show()
    qapp.processEvents()
    view.set_matches([(264.2686, "C16 base")], "#2ca02c")
    view.autoscale()
    qapp.processEvents()
    assert _clearance(view, view._match_labels) >= 0


def test_the_view_still_cannot_go_negative(qapp):
    """The extra room is on top; the floor stays where it was."""
    view = SpectrumView()
    view.resize(900, 300)
    view.set_traces([_spectrum_trace()])
    view.show()
    qapp.processEvents()
    view.autoscale()
    qapp.processEvents()
    (x_lo, _x_hi), (y_lo, _y_hi) = view.viewbox.viewRange()
    assert x_lo >= 0
    assert y_lo >= 0


def test_a_dying_pane_is_left_alone(qapp):
    """
    The stacked layout rebuilds by detaching every pane and deleting it later,
    and setParent(None) resizes the pane on its way out. Reaching into the
    view box of a pane that is being taken apart crashed Windows outright —
    an access violation, not an exception — because working out the range
    walks items that are already going. Nothing may run for a hidden pane.
    """
    import pyqtgraph as pg

    from milq.ui.chrom_area import ChromatogramArea
    from milq.ui.plots import BasePlot, colour

    host = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(host)
    area = ChromatogramArea()
    layout.addWidget(area)
    host.resize(900, 600)
    host.show()

    x = np.linspace(0, 22, 400)
    area.set_traces([Trace(f"t{i}", f"{i:02d}", x,
                           np.exp(-((x - 11) ** 2)) * 1e6, colour(i))
                     for i in range(3)])
    qapp.processEvents()

    hidden_panes = []
    walks = []
    inside = {"resize": 0}
    original = BasePlot._resized
    real_auto_range = pg.ViewBox.autoRange

    def watch(self, *args):
        if not self.isVisible():
            hidden_panes.append(self)
        inside["resize"] += 1
        try:
            return original(self, *args)
        finally:
            inside["resize"] -= 1

    def count_walk(self, *args, **kwargs):
        # only the walks a resize is responsible for; the rebuild ends with a
        # deliberate autoscale of the live panes, which is not the hazard
        if inside["resize"]:
            walks.append(self)
        return real_auto_range(self, *args, **kwargs)

    BasePlot._resized = watch
    pg.ViewBox.autoRange = count_walk
    try:
        area.set_stacked(True)
        qapp.processEvents()
        area.set_stacked(False)
        qapp.processEvents()
    finally:
        BasePlot._resized = original
        pg.ViewBox.autoRange = real_auto_range

    # the rebuild does resize panes on their way out — that is the hazard
    assert hidden_panes, "expected the rebuild to resize panes while hidden"
    # and no resize of any pane may ask the box to walk its items
    assert not walks, "a resize asked pyqtgraph to walk the items of a pane"
    host.close()


def test_refitting_on_resize_does_not_recurse(qapp):
    view = SpectrumView()
    view.resize(900, 600)
    view.set_traces([_spectrum_trace()])
    view.show()
    qapp.processEvents()
    view.autoscale()

    depth = {"max": 0, "now": 0}
    original = SpectrumView._resized

    def watch(self, *args):
        depth["now"] += 1
        depth["max"] = max(depth["max"], depth["now"])
        try:
            return original(self, *args)
        finally:
            depth["now"] -= 1

    SpectrumView._resized = watch
    try:
        for height in (240, 700, 210, 500):
            view.resize(900, height)
            qapp.processEvents()
    finally:
        SpectrumView._resized = original

    assert depth["max"] <= 1, f"re-entered the resize handler {depth['max']} deep"
    assert _clearance(view, view._labels) >= 0
