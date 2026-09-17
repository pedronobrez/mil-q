"""Choosing an internal standard from the Analytics workspace."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from milq.components import Component
from milq.quantify import PeakResult, ResultsSet
from milq.session import Session
from milq.ui.analytics import AnalyticsWorkspace


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def workspace():
    session = Session()
    session.set_components([
        Component(name="C17:0 standard", precursor=552.5, fragment=534.5245,
                  group="Cer", is_internal_standard=True),
        Component(name="SM(d18:1/12:0)", precursor=647.5, fragment=184.0733,
                  group="SM", is_internal_standard=True),
        Component(name="C16:0-Ceramide", precursor=538.5, fragment=264.2686,
                  group="Cer", internal_standard="C17:0 standard",
                  response="ratio"),
    ])
    results = ResultsSet()
    for name, area in (("C17:0 standard", 200.0), ("SM(d18:1/12:0)", 400.0),
                       ("C16:0-Ceramide", 100.0)):
        results.results.append(PeakResult(
            sample_key="s1", sample_name="Injection 1", component=name,
            area=area, height=area / 2))
    session.results = results
    widget = AnalyticsWorkspace(session)
    widget.resize(1400, 700)
    return widget


def test_the_choice_reaches_the_method(qapp, workspace):
    workspace._set_internal_standard("C16:0-Ceramide", "SM(d18:1/12:0)")
    component = workspace.session.method.by_name("C16:0-Ceramide")
    assert component.internal_standard == "SM(d18:1/12:0)"


def test_the_ratios_are_recomputed_against_the_new_standard(qapp, workspace):
    workspace._set_internal_standard("C16:0-Ceramide", "SM(d18:1/12:0)")
    result = workspace.session.results.get("s1", "C16:0-Ceramide")
    assert result.internal_standard == "SM(d18:1/12:0)"
    assert result.is_area == 400.0
    assert result.area_ratio == pytest.approx(0.25)


def test_clearing_the_standard_falls_back_to_the_raw_area(qapp, workspace):
    workspace._set_internal_standard("C16:0-Ceramide", "")
    result = workspace.session.results.get("s1", "C16:0-Ceramide")
    assert result.internal_standard == ""
    assert result.area_ratio is None


def test_the_table_hands_the_choice_to_the_workspace(qapp, workspace):
    from milq.ui.results_table import IS_COLUMN
    model = workspace.results.model
    row = next(r for r in range(model.rowCount())
               if model.result_at(r).component == "C16:0-Ceramide")
    model.setData(model.index(row, IS_COLUMN), "SM(d18:1/12:0)",
                  QtCore.Qt.ItemDataRole.EditRole)
    # the connection is queued so the model is not reset inside setData
    QtWidgets.QApplication.processEvents()
    assert (workspace.session.method.by_name("C16:0-Ceramide").internal_standard
            == "SM(d18:1/12:0)")


def test_a_long_analyte_name_is_readable_in_the_tree(qapp, workspace):
    tree = workspace.component_tree
    assert tree.textElideMode() == QtCore.Qt.TextElideMode.ElideNone
    item = tree.findItems("Cer", QtCore.Qt.MatchFlag.MatchExactly)[0].child(0)
    assert item.toolTip(0) == item.text(0)


def test_the_tree_column_grows_past_the_pane_for_a_long_name(qapp, workspace):
    tree = workspace.component_tree
    components = list(workspace.session.method.components)
    components[2].name = "LacCER(d18:1/24:1(15Z))" * 12
    workspace.session.set_components(components)
    # wider than the pane, so the name can be scrolled to rather than elided
    assert tree.columnWidth(0) > tree.viewport().width()


def test_short_names_still_fill_the_row(qapp, workspace):
    """
    A row is painted across its columns, not across the widget.

    Sized to its contents alone the column stops at the longest name, and the
    selection and the alternating stripes end in mid-air beside it.
    """
    tree = workspace.component_tree
    assert tree.columnWidth(0) >= tree.viewport().width()
