"""
The per-region label budget: `milq.labels`, and the two things that use
it — the spectrum pane and the printed comparison.

The rule these test is the one written down in `milq/labels.py`: the
visible mass axis is cut into equal windows, each may claim a few labels
tallest first, and the tallest peak of every window asks for room before any
window asks for a second. What is checked here is the arithmetic, on spectra
made up for the purpose; the constants themselves were chosen by rendering
real acquisitions and are argued for in that module.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq import labels as label_rule
from milq import spectra_compare as sc
from milq.ui.plots import SpectrumView, Trace
from milq.ui import plots


@pytest.fixture(autouse=True)
def _one_font_everywhere(monkeypatch):
    """The label width is what decides a collision, and the platform's
    default font made Windows draw a different set than macOS for the same
    spectrum; the pane tests pin it to one width."""
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


# --------------------------------------------------------------------------- #
# the rule itself
# --------------------------------------------------------------------------- #
def test_a_dense_cluster_does_not_starve_a_lone_tall_peak():
    """
    The complaint the rule exists for. Twenty peaks packed into the first
    tenth of the axis, all taller than the one peak at the far end: by
    height alone the lone peak is twenty-first and never gets a label.
    """
    cluster = [(120.0 + 0.4 * i, 100_000 - 100 * i) for i in range(20)]
    lone = (940.0, 40_000)
    chosen = label_rule.choose(cluster + [lone], 100.0, 1000.0)

    assert lone in chosen
    # and it is not an afterthought: it is the tallest of its region, so it
    # asks before any region asks for a second label
    assert chosen.index(lone) < label_rule.LABEL_REGIONS


def test_the_tallest_of_every_region_is_chosen_and_asks_first():
    peaks = []
    for region in range(label_rule.LABEL_REGIONS):
        base = 100.0 + region * 100.0
        # the tallest of a region is deliberately not in height order across
        # regions, so that "tallest of its region" cannot be read off the
        # global ranking
        for n in range(5):
            peaks.append((base + n, 10_000 + region * 500 - n * 100))
    chosen = label_rule.choose(peaks, 100.0, 900.0)

    tallest = {}
    for mz, height in peaks:
        region = label_rule.region_of(mz, 100.0, 900.0)
        if height > tallest.get(region, (0, 0))[1]:
            tallest[region] = (mz, height)
    first_round = chosen[:len(tallest)]
    assert set(tallest.values()) == set(first_round)


def test_a_region_may_not_spend_more_than_its_budget():
    peaks = [(120.0 + 0.5 * i, 100_000 - i) for i in range(30)]
    peaks.append((950.0, 50_000))
    chosen = label_rule.choose(peaks, 100.0, 1000.0)

    counted = {}
    for mz, _height in chosen:
        region = label_rule.region_of(mz, 100.0, 1000.0)
        counted[region] = counted.get(region, 0) + 1
    assert max(counted.values()) <= label_rule.LABEL_BUDGET


def test_peaks_outside_the_view_are_not_offered():
    peaks = [(150.0, 100_000), (5_000.0, 900_000)]
    chosen = label_rule.choose(peaks, 100.0, 1000.0)
    assert [mz for mz, _h in chosen] == [150.0]


def test_the_floor_is_a_fraction_of_the_tallest_in_view():
    """
    Relative to the view, not to the spectrum: zoomed past the base peak,
    2% of something off screen would leave nothing to name.
    """
    peaks = [(150.0, 1_000_000), (800.0, 900), (820.0, 10)]
    everything = label_rule.choose(peaks, 100.0, 1000.0, min_relative=0.02)
    assert [mz for mz, _h in everything] == [150.0]

    zoomed = label_rule.choose(peaks, 700.0, 900.0, min_relative=0.02)
    assert [mz for mz, _h in zoomed] == [800.0]


def test_an_empty_view_chooses_nothing():
    assert label_rule.choose([], 100.0, 1000.0) == []
    assert label_rule.choose([(150.0, 10.0)], 400.0, 500.0) == []


# --------------------------------------------------------------------------- #
# the pane
# --------------------------------------------------------------------------- #
def _crowded_pane(qapp):
    """
    A spectrum shaped like the real survey the rule was measured on: a dense
    cluster carrying every tall peak, and smaller peaks spread over the rest
    of the axis.
    """
    cluster = [(270.0 + 1.1 * i, 250_000 - 4_000 * i) for i in range(20)]
    spread = [(mz, 30_000) for mz in (150.0, 450.0, 560.0, 680.0, 790.0, 900.0)]
    mz, y = _sticks(cluster + spread)
    view = SpectrumView()
    view.resize(980, 420)
    view.set_traces([Trace("spec", "survey", mz, y, "#234b8c")])
    view.show()
    qapp.processEvents()
    view.autoscale()
    qapp.processEvents()
    return view


def _named(view):
    return sorted(round(item.mz, 2) for item in view._labels)


def test_the_pane_names_the_quiet_half_of_the_axis(qapp):
    view = _crowded_pane(qapp)
    try:
        named = _named(view)
        assert named, "nothing was labelled at all"
        # the cluster no longer owns every label
        assert any(mz > 400.0 for mz in named)
        assert max(named) > 500.0
    finally:
        view.close()


def test_zooming_in_names_more_peaks(qapp):
    """
    The regions follow the view, so a narrower view is a narrower region and
    more of the cluster gets named. This is why the choice is made again on
    every range change rather than once when the traces are set.
    """
    view = _crowded_pane(qapp)
    try:
        wide = len(view._labels)
        view.plot.setXRange(265.0, 295.0, padding=0)
        qapp.processEvents()
        close = len(view._labels)
        assert close > wide, f"{close} labels zoomed in against {wide} out"
    finally:
        view.close()


def test_the_pane_puts_the_labels_back_on_the_way_out(qapp):
    """Zooming out returns to the view it had, not to whatever the zoom left."""
    view = _crowded_pane(qapp)
    try:
        before = _named(view)
        view.plot.setXRange(265.0, 295.0, padding=0)
        qapp.processEvents()
        view.autoscale()
        qapp.processEvents()
        assert _named(view) == before
    finally:
        view.close()


def test_labels_can_still_be_turned_off(qapp):
    view = _crowded_pane(qapp)
    try:
        assert view._labels
        view.set_labels_enabled(False)
        qapp.processEvents()
        assert view._labels == []
        view.set_labels_enabled(True)
        qapp.processEvents()
        assert view._labels
    finally:
        view.close()


def test_no_two_labels_overlap(qapp):
    """The budget proposes; the collision rule still disposes."""
    view = _crowded_pane(qapp)
    try:
        boxes = sorted((item.sceneBoundingRect() for item in view._labels),
                       key=lambda r: r.left())
        for first, second in zip(boxes, boxes[1:]):
            assert second.left() >= first.right() - 0.5
    finally:
        view.close()


# --------------------------------------------------------------------------- #
# the printed comparison
# --------------------------------------------------------------------------- #
def test_the_print_uses_the_same_rule():
    cluster = [(270.0 + 1.1 * i, 250_000 - 4_000 * i) for i in range(20)]
    spread = [(mz, 30_000) for mz in (150.0, 450.0, 680.0, 900.0)]
    mz, y = _sticks(cluster + spread)
    comparison = sc.SpectrumComparison(
        traces=[sc.SpectrumTrace("one", mz, y, "#234b8c")])
    trace = comparison.traces[0]

    # six by height was what the print offered before the budget
    by_height = [p[0] for p in comparison.peaks(trace, most=6)]
    budgeted = [p[0] for p in comparison.label_peaks(trace, 100.0, 1000.0)]

    assert max(by_height) < 400.0        # every one of them inside the cluster
    assert max(budgeted) > 800.0
    counted = {}
    for peak in budgeted:
        region = label_rule.region_of(peak, 100.0, 1000.0)
        counted[region] = counted.get(region, 0) + 1
    assert max(counted.values()) <= label_rule.LABEL_BUDGET
