"""Tests for the stacked chromatogram area and its linked time axis."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq.ui.chrom_area import ChromatogramArea
from milq.ui.plots import Trace


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def traces():
    x = np.linspace(0, 10, 200)
    return [
        Trace("a", "first", x, np.sin(x) + 2, "#1f77b4"),
        Trace("b", "second", x, np.cos(x) + 2, "#d62728"),
        Trace("c", "third", x, np.sin(2 * x) + 2, "#2ca02c"),
    ]


def test_single_pane_by_default(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    assert len(area.views) == 1
    assert len(area.views[0].traces) == 3


def test_stacking_gives_one_pane_per_trace(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    area.set_stacked(True)
    assert len(area.views) == 3
    assert [len(v.traces) for v in area.views] == [1, 1, 1]


def test_unstacking_returns_to_a_single_pane(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    area.set_stacked(True)
    area.set_stacked(False)
    assert len(area.views) == 1
    assert len(area.views[0].traces) == 3


def test_x_axis_is_linked_across_stacked_panes(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    area.set_stacked(True)
    area.views[0].plot.setXRange(3.0, 4.0, padding=0)
    for view in area.views[1:]:
        lo, hi = view.plot.getViewBox().viewRange()[0]
        assert lo == pytest.approx(3.0, abs=0.05)
        assert hi == pytest.approx(4.0, abs=0.05)


def test_options_survive_a_rebuild(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    area.set_smoothing(2.0)
    area.set_mirror(True)
    area.set_stacked(True)
    assert all(v.mirrored for v in area.views)
    assert all(v._smooth_sigma == 2.0 for v in area.views)


def test_conditioned_finds_a_trace_in_any_pane(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    area.set_stacked(True)
    found = area.conditioned("c")
    assert found is not None and found[0].size == 200


def test_background_range_is_shared(qapp, traces):
    area = ChromatogramArea()
    area.set_traces(traces)
    area.set_stacked(True)
    area.set_background_range(1.0, 2.0)
    assert area.background_range() == pytest.approx((1.0, 2.0))
    assert all(v.background_range() is not None for v in area.views)
