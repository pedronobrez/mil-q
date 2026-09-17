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

from PyQt6 import QtWidgets  # noqa: E402

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
