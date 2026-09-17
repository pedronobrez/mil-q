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
