"""Colouring the metric plot by study group."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq.components import Component
from milq.quantify import PeakResult, ResultsSet
from milq.samples import QC, SampleEntry, UNKNOWN
from milq.session import Session
from milq.ui.metric_plot import (
    BY_SAMPLE_GROUP, BY_SAMPLE_TYPE, NO_COLOUR, UNGROUPED, UNGROUPED_COLOUR,
    MetricPlotPanel,
)
from milq.ui.plots import colour


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def panel(qapp):
    session = Session()
    session.set_components([Component(name="Cer", precursor=538.5,
                                      fragment=264.2686)])
    session.entries = [
        SampleEntry("/d/1.wiff", 0, "C1", UNKNOWN, sample_group="control"),
        SampleEntry("/d/2.wiff", 0, "C2", UNKNOWN, sample_group="control"),
        SampleEntry("/d/3.wiff", 0, "T1", UNKNOWN, sample_group="treated"),
        SampleEntry("/d/4.wiff", 0, "Q1", QC),      # no group
    ]
    results = ResultsSet()
    for entry, area in zip(session.entries, (100.0, 120.0, 300.0, 90.0)):
        results.results.append(PeakResult(
            sample_key=entry.key, sample_name=entry.name, component="Cer",
            area=area, height=area / 2))
    session.results = results
    widget = MetricPlotPanel(session)
    widget.resize(800, 400)
    widget.y_combo.setCurrentText("Area")
    return widget


def drawn(panel):
    """Each scatter's legend label and the number of points it holds."""
    labels = [label.text for _item, label in panel.legend.items]
    return list(zip(labels, [len(s.data) for s in panel._scatters]))


def test_points_are_split_by_study_group(qapp, panel):
    panel.colour_combo.setCurrentText(BY_SAMPLE_GROUP)
    assert drawn(panel) == [("control", 2), ("treated", 1), (UNGROUPED, 1)]


def test_each_group_gets_its_own_colour(qapp, panel):
    panel.colour_combo.setCurrentText(BY_SAMPLE_GROUP)
    brushes = [s.opts["brush"].color().name() for s in panel._scatters]
    assert brushes[:2] == [colour(0), colour(1)]
    assert len(set(brushes)) == 3


def test_a_sample_with_no_group_keeps_its_own_colour(qapp, panel):
    panel.colour_combo.setCurrentText(BY_SAMPLE_GROUP)
    ungrouped = panel._scatters[-1]
    assert ungrouped.opts["brush"].color().name() == UNGROUPED_COLOUR
    # and it does not consume a palette slot the real groups would have used
    assert colour(2) not in [s.opts["brush"].color().name()
                             for s in panel._scatters]


def test_colouring_by_sample_type_instead(qapp, panel):
    panel.colour_combo.setCurrentText(BY_SAMPLE_TYPE)
    assert drawn(panel) == [(UNKNOWN, 3), (QC, 1)]


def test_turning_the_colouring_off_draws_one_series(qapp, panel):
    panel.colour_combo.setCurrentText(NO_COLOUR)
    assert len(panel._scatters) == 1
    assert len(panel._scatters[0].data) == 4
    assert not panel.legend.isVisible()


def test_every_point_stays_clickable_across_the_series(qapp, panel):
    panel.colour_combo.setCurrentText(BY_SAMPLE_GROUP)
    seen = []
    panel.sigPointActivated.connect(lambda k, c: seen.append((k, c)))
    treated = panel._scatters[1]
    panel._on_clicked(treated, [treated.points()[0]])
    assert seen == [(panel.session.entries[2].key, "Cer")]


def test_the_status_counts_the_groups(qapp, panel):
    panel.colour_combo.setCurrentText(BY_SAMPLE_GROUP)
    assert "4 point(s)" in panel.status.text()
    assert "3 group(s)" in panel.status.text()
