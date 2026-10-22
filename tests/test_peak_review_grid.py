"""
The review grid keeps its panels when its shape changes.

One `PeakPanel` costs about 5 ms to build, nearly all of it inside pyqtgraph,
and the grid holds up to 64 of them. Rebuilding every panel for each step of
the **Columns** and **Rows** spin boxes cost half a second at 8 x 8 — and the
spin boxes are stepped, so a drag from 3 to 8 paid it five times over. The
panels are interchangeable, so the grid now grows and shrinks a pool instead.

What is asserted here is that the panels really are reused, that the ones a
smaller shape does not need are hidden rather than left lying over the first
cell, and that the pool cannot grow without bound.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq.quantify import PeakResult  # noqa: E402
from milq.ui.peak_review import PeakReviewGrid  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _grid(qapp) -> PeakReviewGrid:
    grid = PeakReviewGrid()
    grid.resize(900, 600)
    grid.show()
    qapp.processEvents()
    return grid


def _items(count: int) -> list[tuple]:
    x = np.linspace(0.0, 10.0, 120)
    made = []
    for index in range(count):
        y = 1000.0 * np.exp(-((x - 5.0) ** 2) / 0.2) + 10.0
        made.append((PeakResult(sample_key=f"s{index}",
                                sample_name=f"Injection {index + 1}",
                                component="CA-d4"),
                     x, y, (4.5, 5.5)))
    return made


def test_growing_the_grid_keeps_the_panels_it_had(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    qapp.processEvents()
    before = list(grid.views)

    grid.col_spin.setValue(4)
    qapp.processEvents()
    after = list(grid.views)

    assert len(after) == 8
    assert after[:4] == before, "the four panels it already had were rebuilt"
    grid.close()


def test_shrinking_and_growing_again_builds_nothing(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(4)
    grid.row_spin.setValue(2)
    qapp.processEvents()
    wide = list(grid.views)

    grid.col_spin.setValue(1)
    grid.row_spin.setValue(1)
    qapp.processEvents()
    assert len(grid.views) == 1

    grid.col_spin.setValue(4)
    grid.row_spin.setValue(2)
    qapp.processEvents()
    assert set(grid.views) == set(wide), "a shape already used cost new panels"
    grid.close()


def test_a_panel_the_shape_dropped_is_hidden(qapp):
    """
    A child widget nobody lays out keeps the geometry it had.

    Which is how ninety combo boxes once ended up piled on one table cell.
    """
    grid = _grid(qapp)
    grid.col_spin.setValue(4)
    grid.row_spin.setValue(4)
    grid.set_items("CA-d4", _items(16))
    qapp.processEvents()

    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    qapp.processEvents()

    assert len(grid.views) == 4
    assert all(not panel.isVisible() for panel in grid._spare), (
        "a panel left out of the layout is still being drawn")
    grid.close()


def test_the_pool_cannot_outgrow_the_largest_shape(qapp):
    grid = _grid(qapp)
    largest = grid.col_spin.maximum() * grid.row_spin.maximum()
    for columns, rows in ((8, 8), (1, 1), (5, 3), (8, 8), (2, 2)):
        grid.col_spin.setValue(columns)
        grid.row_spin.setValue(rows)
        qapp.processEvents()
        assert len(grid.views) + len(grid._spare) <= largest
    grid.close()


def test_the_page_survives_a_change_of_shape(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    grid.set_items("CA-d4", _items(9))
    qapp.processEvents()
    assert grid.page_count == 3

    grid.col_spin.setValue(3)
    grid.row_spin.setValue(3)
    qapp.processEvents()
    assert grid.page_count == 1
    shown = [panel for panel in grid.views if panel.isVisible()]
    assert len(shown) == 9
    assert [panel.sample_key for panel in shown] == [f"s{i}" for i in range(9)]
    grid.close()


# -- what the grid shows, not just how many panels it has ------------------ #
def _items_of_heights(heights) -> list[tuple]:
    x = np.linspace(0.0, 10.0, 120)
    return [(PeakResult(sample_key=f"s{i}", sample_name=f"Injection {i + 1}",
                        component="CA-d4"),
             x, height * np.exp(-((x - 5.0) ** 2) / 0.2) + 10.0, (4.5, 5.5))
            for i, height in enumerate(heights)]


def test_same_y_gives_every_panel_the_same_ceiling(qapp):
    """
    Each panel fences itself to its own tallest point, and that fence was
    clamping the shared scale straight back: **Same Y** looked as though it
    did nothing. The ceiling now reaches the fence.
    """
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    grid.set_items("CA-d4", _items_of_heights([300, 1000, 1700, 2400]))
    qapp.processEvents()
    own = [p.getViewBox().viewRange()[1][1] for p in grid.views]
    assert max(own) > 2 * min(own), "the panels should start on their own scales"

    grid.chk_shared_y.setChecked(True)
    qapp.processEvents()
    shared = [p.getViewBox().viewRange()[1][1] for p in grid.views]
    assert max(shared) - min(shared) < 1.0, f"not one scale: {shared}"
    assert min(shared) > 2400, "the shared ceiling is below the tallest peak"

    grid.chk_shared_y.setChecked(False)
    qapp.processEvents()
    back = [p.getViewBox().viewRange()[1][1] for p in grid.views]
    assert max(back) > 2 * min(back), "switching it off did not give the scales back"
    grid.close()


def test_every_cell_is_the_same_size_after_a_change_of_shape(qapp):
    """
    A QGridLayout remembers every row and column it has ever had: at 4 x 3
    after 3 x 2 the rows measured 291, 197 and 90 pixels.
    """
    grid = _grid(qapp)
    grid.set_items("CA-d4", _items_of_heights([500] * 12))
    for columns, rows in ((3, 2), (4, 3), (2, 2), (3, 2), (1, 1), (4, 3)):
        grid.col_spin.setValue(columns)
        grid.row_spin.setValue(rows)
        qapp.processEvents()
        qapp.processEvents()
        cells = {(p.width(), p.height()) for p in grid.views if p.isVisible()}
        widths = {w for w, _ in cells}
        heights = {h for _, h in cells}
        # a pixel of rounding is the layout's; anything more is a stale row
        assert max(widths) - min(widths) <= 1, f"{columns}x{rows}: widths {widths}"
        assert max(heights) - min(heights) <= 1, f"{columns}x{rows}: heights {heights}"
        assert min(heights) > grid.container.height() // (rows + 1), (
            f"{columns}x{rows}: a row is starved at {min(heights)} px")
    grid.close()


# -- the page a refresh lands on ------------------------------------------- #
def test_a_refresh_of_the_same_set_keeps_the_page_and_the_selection(qapp):
    """
    Every manual integration ends in the workspace handing the grid its
    items again. That used to start at page 1, so a drag on page 3 put the
    operator back on page 1 after every peak.
    """
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    grid.set_items("CA-d4", _items(10), key="CA-d4")
    grid.set_page(2)
    grid.select("s9")
    grid.set_items("CA-d4", _items(10), key="CA-d4")
    qapp.processEvents()
    assert grid.page_label.text() == "3/3"
    assert [p.sample_key for p in grid.views if p.isVisible()] == ["s8", "s9"]
    assert grid._selected == "s9"

    # another component is another set, and starts at the beginning
    grid.set_items("CA", _items(10), key="CA")
    assert grid.page_label.text() == "1/3"

    # a set that got shorter keeps the nearest page it still has
    grid.set_page(2)
    grid.set_items("CA", _items(5), key="CA")
    assert grid.page_label.text() == "2/2"
    grid.close()


def test_a_lazy_refresh_keeps_its_page_too(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    made = _items(12)
    grid.set_lazy("All components", 12, lambda a, b: made[a:b])
    grid.set_page(1)
    grid.set_lazy("All components", 12, lambda a, b: made[a:b])
    assert grid.page_label.text() == "2/3"
    grid.close()


def _loaded_entry(name):
    from tests.test_matching import Sample
    from tests.test_quantify import TracedChannel

    from milq.samples import SampleEntry

    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([
        TracedChannel(1, 538.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
        TracedChannel(2, 566.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
    ])
    return entry


def test_a_manual_integration_on_a_later_page_stays_on_that_page(qapp):
    """The user's report, driven through the workspace as it happens."""
    from milq.components import Component
    from milq.session import Session
    from milq.ui.analytics import ROLE_NAME, AnalyticsWorkspace

    session = Session()
    session.set_components([
        Component(name="Cer A", precursor=538.5, fragment=264.2686,
                  group="Cer", rt=5.0, rt_halfwidth=1.0),
        Component(name="Cer B", precursor=566.5, fragment=264.2686,
                  group="Cer", rt=5.0, rt_halfwidth=1.0),
    ])
    session.entries = [_loaded_entry(f"S{i}") for i in range(5)]
    workspace = AnalyticsWorkspace(session)
    workspace.resize(1200, 800)

    def choose(name):
        it = QtWidgets.QTreeWidgetItemIterator(workspace.component_tree)
        while it.value():
            if it.value().data(0, ROLE_NAME) == name:
                workspace.component_tree.setCurrentItem(it.value())
                return
            it += 1

    try:
        workspace.process_batch()
        choose("Cer A")
        grid = workspace.grid
        grid.col_spin.setValue(1)
        grid.row_spin.setValue(2)
        grid.set_page(1)
        target = session.entries[2].key
        grid.select(target)
        assert grid.page_label.text() == "2/3"

        workspace._on_manual_range(target, 4.2, 5.8)
        assert session.results.get(target, "Cer A").manual
        assert grid.page_label.text() == "2/3", "the drag sent the grid to page 1"
        assert grid._selected == target
        shown = [p for p in grid.views if not p.isHidden()]
        assert target in [p.sample_key for p in shown]
        assert "✎" in next(p for p in shown if p.sample_key == target).title_text()

        choose("Cer B")
        assert grid.page_label.text() == "1/3", "a new component starts at page 1"
    finally:
        workspace.close()


# -- legibility --------------------------------------------------------------- #
@pytest.fixture
def app_font(qapp):
    """The application's font at a given size, put back afterwards."""
    original = QtWidgets.QApplication.font()

    def set_points(points):
        font = QtWidgets.QApplication.font()
        font.setPointSizeF(points)
        QtWidgets.QApplication.setFont(font)

    yield set_points
    QtWidgets.QApplication.setFont(original)


def test_the_type_follows_the_applications_font(qapp, app_font):
    """
    Fixed at 7 and 8 points the panels read at half the size of the 13-point
    table under them on a Mac.
    """
    sizes = []
    for points in (13.0, 20.0):
        app_font(points)
        grid = _grid(qapp)
        grid.set_items("CA-d4", _items(6))
        qapp.processEvents()
        panel = grid.views[0]
        sizes.append((panel.title_points(), panel.tick_points()))
        assert panel.title_points() >= 0.75 * points
        assert panel.tick_points() >= 0.7 * points
        grid.close()
    assert sizes[1][0] > sizes[0][0] and sizes[1][1] > sizes[0][1]


def test_a_small_panel_steps_down_but_never_past_the_floor(qapp, app_font):
    from milq.ui.peak_review import FONT_FLOOR_PT, panel_type

    roomy = panel_type(400, 300, base=13.0)
    small = panel_type(130, 80, base=13.0)
    assert small[0] < roomy[0] and small[1] < roomy[1]
    assert min(panel_type(60, 30, base=6.0)) >= FONT_FLOOR_PT


def _clipped(panel) -> list[str]:
    """What of a panel's plot falls outside what the panel shows."""
    view = panel.viewport().size()
    plot = panel.getPlotItem().geometry()
    problems = []
    if plot.width() > view.width() + 0.5 or plot.height() > view.height() + 0.5:
        problems.append(f"plot {plot.width():.0f}x{plot.height():.0f} in a "
                        f"{view.width()}x{view.height()} view")
    axis = panel.getAxis("bottom")
    if axis.style["showValues"]:
        from PyQt6 import QtGui
        needed = QtGui.QFontMetrics(axis.style["tickFont"]).height()
        if axis.height() < needed + axis.style["tickTextOffset"][1]:
            problems.append(f"time axis {axis.height():.0f} px for "
                            f"{needed} px of type")
    title = panel.getPlotItem().titleLabel
    if title.isVisible() and title.item.boundingRect().width() > view.width():
        problems.append(f"title {title.item.boundingRect().width():.0f} px "
                        f"in {view.width()}")
    return problems


@pytest.mark.parametrize("columns,rows,height", [
    (3, 3, 700), (6, 6, 700), (8, 8, 700), (3, 3, 260), (8, 8, 420)])
def test_nothing_in_a_panel_is_drawn_past_its_edge(qapp, app_font,
                                                   columns, rows, height):
    """
    The plot was sized to the widget and the border is a frame, so the
    bottom two pixels — four on the selected panel — were the time axis's
    numbers; a title set while a panel was wide held its plot wider than
    the cell; and a long title ran off both sides.
    """
    app_font(13.0)
    grid = _grid(qapp)
    grid.resize(1100, height)
    grid.col_spin.setValue(columns)
    grid.row_spin.setValue(rows)
    made = _items(columns * rows)
    for result, *_ in made:
        result.area, result.rt, result.snr = 1_234_567.0, 4.66, 15_010.0
        result.start_rt, result.end_rt = 4.5, 5.5
    grid.set_items("CA-d4", made)
    grid.select("s1")
    qapp.processEvents()
    qapp.processEvents()
    for panel in grid.views:
        assert not _clipped(panel), (panel.sample_key, _clipped(panel))
        # the sample and the time survive any width
        shown = panel.title_text()
        assert shown.startswith(panel.sample_key.replace("s", "Injection ")[:4])
        assert shown.endswith("4.66")
    grid.close()


def test_a_narrow_time_axis_gives_every_label_room(qapp, app_font):
    """At 8 x 8 the time axis printed `4.04.55.0`."""
    from PyQt6 import QtGui

    from milq.ui.peak_review import _PanelAxis

    app_font(13.0)
    axis = _PanelAxis("bottom")
    font = QtGui.QFont(QtWidgets.QApplication.font())
    font.setPointSizeF(11.0)
    axis.setStyle(tickFont=font)
    metrics = QtGui.QFontMetrics(font)
    for size in (60, 90, 130, 300):
        spacing = axis.tickSpacing(3.65, 5.65, size)[0][0]
        labels = int(2.0 // spacing) + 1
        width = max(metrics.horizontalAdvance(t)
                    for t in axis.tickStrings([3.65, 5.65], 1.0, spacing))
        assert max(1, labels - 1) * 2 * width <= size, (size, spacing)

    upright = _PanelAxis("left")
    upright.setStyle(tickFont=font)
    spacing = upright.tickSpacing(0.0, 3000.0, 30)[0][0]
    assert 3000.0 // spacing <= 1, "a 30-pixel axis drew 2000 over 1000"


# -- Same Y ------------------------------------------------------------------- #
def _tops(grid) -> list[float]:
    return [p.getViewBox().viewRange()[1][1] for p in grid.views
            if p.isVisible()]


def _items_with_a_neighbour(heights, neighbour=50_000.0) -> list[tuple]:
    """Peaks at 5 min; every other channel carries a tall stranger at 9."""
    x = np.linspace(0.0, 10.0, 400)
    made = []
    for i, height in enumerate(heights):
        y = height * np.exp(-((x - 5.0) ** 2) / 0.02) + 5.0
        if i % 2:
            y = y + neighbour * np.exp(-((x - 9.0) ** 2) / 0.02)
        result = PeakResult(sample_key=f"s{i}", sample_name=f"Injection {i + 1}",
                            component="CA-d4", area=height, height=height,
                            rt=5.0, start_rt=4.8, end_rt=5.2)
        made.append((result, x, y, (4.7, 5.3), (x, 3.0 * y)))
    return made


def test_same_y_is_the_tallest_point_shown_not_the_tallest_in_the_run(qapp):
    """
    The shared ceiling was the whole trace's maximum, so one channel carrying
    a tall neighbour minutes away flattened every peak on the grid — the
    switch looked as though it did nothing useful.
    """
    grid = _grid(qapp)
    grid.col_spin.setValue(3)
    grid.row_spin.setValue(2)
    grid.set_items("CA-d4", _items_with_a_neighbour([400, 800, 1200, 1600, 2000, 2400]))
    grid.chk_shared_y.setChecked(True)
    qapp.processEvents()
    tops = _tops(grid)
    assert max(tops) - min(tops) < 1e-6
    assert 2400 < tops[0] < 2400 * 1.2, f"ceiling {tops[0]:.0f}"
    grid.close()


def _shared(grid, qapp) -> list[float]:
    qapp.processEvents()
    tops = _tops(grid)
    assert tops, "nothing on screen"
    assert max(tops) - min(tops) < 1e-6, f"not one scale: {tops}"
    return tops


def test_same_y_holds_through_everything_that_redraws_the_grid(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    heights = [300, 3000, 600, 900, 1200, 1500, 1800, 2100, 200, 100]
    made = _items_with_a_neighbour(heights)
    grid.set_items("CA-d4", made, key="CA-d4")
    grid.chk_shared_y.setChecked(True)
    ceiling = _shared(grid, qapp)[0]
    assert ceiling > 3000

    grid.set_page(2)                               # paging: the set's scale
    assert _shared(grid, qapp)[0] == pytest.approx(ceiling)
    grid.col_spin.setValue(3)                      # a change of shape
    assert _shared(grid, qapp)[0] == pytest.approx(ceiling)
    grid.chk_is.setChecked(False)                  # the standard off and on
    assert _shared(grid, qapp)[0] == pytest.approx(ceiling)
    grid.chk_is.setChecked(True)
    assert _shared(grid, qapp)[0] == pytest.approx(ceiling)
    grid.set_items("CA-d4", made, key="CA-d4")      # a manual integration
    assert _shared(grid, qapp)[0] == pytest.approx(ceiling)
    grid.resize(700, 900)                          # the splitter dragged
    assert _shared(grid, qapp)[0] == pytest.approx(ceiling)
    grid.zoom_combo.setCurrentIndex(2)             # the whole run
    assert _shared(grid, qapp)[0] > 50_000
    grid.close()


def test_same_y_holds_on_a_lazy_page(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    made = _items_with_a_neighbour([100, 2000, 300, 400, 5000, 600])
    grid.set_lazy("All components", len(made), lambda a, b: made[a:b])
    grid.chk_shared_y.setChecked(True)
    assert _shared(grid, qapp)[0] == pytest.approx(2000 * 1.05, rel=0.02)
    grid.set_page(1)
    assert _shared(grid, qapp)[0] == pytest.approx(5000 * 1.05, rel=0.02)
    grid.close()


def test_a_zoom_in_one_panel_is_a_zoom_in_all_under_same_y(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(2)
    grid.set_items("CA-d4", _items_with_a_neighbour([500, 1000, 1500, 2000]))
    grid.chk_shared_y.setChecked(True)
    qapp.processEvents()
    grid.views[1].getViewBox().setYRange(0, 800, padding=0)
    tops = _shared(grid, qapp)
    assert tops[0] == pytest.approx(800)

    # and with it off, each panel keeps its own
    grid.chk_shared_y.setChecked(False)
    qapp.processEvents()
    grid.views[1].getViewBox().setYRange(0, 300, padding=0)
    assert _tops(grid)[0] != pytest.approx(300)
    grid.close()


def test_the_standard_is_scaled_to_what_the_panel_shows(qapp):
    """
    A panel's Y axis now stops at the tallest point in its window, so a
    standard still scaled to the analyte's tallest point over the whole run
    would stand fifty times the window's peak, off the top of the panel.
    """
    grid = _grid(qapp)
    grid.col_spin.setValue(2)
    grid.row_spin.setValue(1)
    grid.set_items("CA-d4", _items_with_a_neighbour([1000, 1000]))
    qapp.processEvents()
    for panel in grid.views:
        top = panel.getViewBox().viewRange()[1][1]
        _x, standard = panel._is_curve.getData()
        inside = (_x >= 4.5) & (_x <= 5.5)
        assert standard[inside].max() <= top
    grid.close()


# -- proportion --------------------------------------------------------------- #
def _rows_and_columns(grid):
    cells = [grid.grid.cellRect(r, c) for r in range(grid.row_spin.value())
             for c in range(grid.col_spin.value())]
    return ({cell.height() for cell in cells}, {cell.width() for cell in cells},
            cells)


@pytest.mark.parametrize("columns,rows", [(3, 2), (4, 3), (8, 8), (1, 1), (5, 7)])
@pytest.mark.parametrize("share", [700, 330, 160])
def test_every_row_and_column_is_the_same_size_however_tight(qapp, columns,
                                                             rows, share):
    """
    A panel asked for 90 x 90 at least — a QGraphicsView's own minimum — so
    at 8 x 8 the grid demanded 748 pixels: it pushed the results under it
    down to 114 and refused the splitter, and a grid with a title or an axis
    asking for more in one row had that row stand taller than the rest.
    """
    splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
    grid = PeakReviewGrid()
    splitter.addWidget(grid)
    splitter.addWidget(QtWidgets.QTableWidget(20, 5))
    splitter.resize(1000, 900)
    splitter.show()
    qapp.processEvents()
    grid.set_items("CA-d4", _items_of_heights([500] * (columns * rows - 1)))
    splitter.setSizes([share, 900 - share])
    grid.col_spin.setValue(columns)
    grid.row_spin.setValue(rows)
    for wanted in (share, share // 2 + 60):
        qapp.processEvents()
        assert abs(splitter.sizes()[0] - wanted) <= 8, (  # the handle
            f"asked the grid for {wanted} px, it took {splitter.sizes()[0]}")
        heights, widths, cells = _rows_and_columns(grid)
        assert max(heights) - min(heights) <= 1, f"rows {sorted(heights)}"
        assert max(widths) - min(widths) <= 1, f"columns {sorted(widths)}"
        inside = grid.container.rect()
        assert all(inside.contains(cell) for cell in cells), (
            f"a row runs off the grid: {cells[-1]} in {inside}")
        for panel in grid.views:
            if panel.isVisible():
                assert panel.height() in heights and panel.width() in widths
        # and again after the splitter is dragged
        splitter.setSizes([share // 2 + 60, 900 - share // 2 - 60])
    splitter.close()


def test_a_short_last_page_keeps_the_rows_of_a_full_one(qapp):
    grid = _grid(qapp)
    grid.col_spin.setValue(3)
    grid.row_spin.setValue(3)
    grid.set_items("CA-d4", _items_of_heights([500] * 11))
    qapp.processEvents()
    full = [(p.geometry().y(), p.height()) for p in grid.views[:3]]
    grid.set_page(1)
    qapp.processEvents()
    short = [(p.geometry().y(), p.height()) for p in grid.views[:3]]
    assert short == full, "the empty rows of the last page gave their space away"
    grid.close()


def test_a_long_title_does_not_make_its_panel_wider(qapp, app_font):
    app_font(13.0)
    grid = _grid(qapp)
    grid.col_spin.setValue(4)
    grid.row_spin.setValue(1)
    made = _items_of_heights([500] * 4)
    made[1][0].sample_name = "A very long sample name indeed, " * 4
    grid.set_items("CA-d4", made)
    grid.resize(900, 300)
    qapp.processEvents()
    widths = {p.width() for p in grid.views}
    assert max(widths) - min(widths) <= 1, widths
    grid.close()


def _items_with_a_standard(count: int, analyte=20.0, standard=80_000.0):
    """An analyte of 20 counts beside a standard of 80,000, as on PGA2."""
    x = np.linspace(0.0, 10.0, 120)
    made = []
    for index in range(count):
        y = analyte * np.exp(-((x - 5.0) ** 2) / 0.2)
        sy = standard * np.exp(-((x - 5.1) ** 2) / 0.2)
        made.append((PeakResult(sample_key=f"s{index}",
                                sample_name=f"KO0{index}",
                                component="PGA2", rt=5.0,
                                start_rt=4.5, end_rt=5.5, area=12.0,
                                height=analyte,
                                internal_standard="PGE2-d4",
                                is_area=48_000.0, is_height=standard),
                     x, y, (4.5, 5.5), (x, sy)))
    return made


def test_the_standard_is_read_in_its_own_counts_on_the_right(qapp):
    grid = _grid(qapp)
    grid.set_items("PGA2", _items_with_a_standard(4))
    qapp.processEvents()
    panel = grid.views[0]
    right, left = panel.getAxis("right"), panel.getAxis("left")
    assert right.isVisible()
    # the dashed trace is drawn at the analyte's height, and the right-hand
    # axis is the left one divided by what it was multiplied by
    _xs, drawn = panel._is_curve.getData()
    assert float(np.max(drawn)) == pytest.approx(20.0, rel=0.05)
    low, high = right.range
    assert high == pytest.approx(left.range[1] / panel._is_scale)
    assert 80_000.0 < high < 90_000.0
    tip = panel.toolTip()
    assert "PGE2-d4" in tip and "48,000" in tip and "80,000" in tip
    assert "right-hand axis" in tip

    # a zoom carries the right-hand axis with it
    panel.getViewBox().setYRange(0.0, 10.0, padding=0)
    assert right.range[1] == pytest.approx(10.0 / panel._is_scale)

    grid.chk_is.setChecked(False)
    qapp.processEvents()
    assert not panel.getAxis("right").isVisible()
    assert "right-hand axis" not in panel.toolTip()
    assert "PGE2-d4" in panel.toolTip()     # the numbers stay, the trace goes


def test_a_panel_without_a_standard_has_no_right_hand_axis(qapp):
    grid = _grid(qapp)
    grid.set_items("CA-d4", _items(2))
    qapp.processEvents()
    assert not grid.views[0].getAxis("right").isVisible()
