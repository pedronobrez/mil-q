"""Tests for the Results table's column sizing and internal-standard chooser."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtWidgets

from milq.components import Component
from milq.quantify import PeakResult, ResultsSet
from milq.session import Session
from milq.ui import theme
from milq.ui.results_table import (
    FIELD_INDEX, IS_COLUMN, MAX_AUTO_WIDTH, ResultsTable,
)

COMPONENT_COLUMN = FIELD_INDEX["component"]


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def table():
    session = Session()
    session.set_components([
        Component(name="C17:0 standard", precursor=552.5, fragment=534.5245,
                  is_internal_standard=True),
        Component(name="SM(d18:1/12:0)", precursor=647.5, fragment=184.0733,
                  is_internal_standard=True),
        Component(name="C16:0-Ceramide", precursor=538.5, fragment=264.2686,
                  internal_standard="C17:0 standard"),
    ])
    results = ResultsSet()
    for name, standard in (("C17:0 standard", ""), ("SM(d18:1/12:0)", ""),
                           ("C16:0-Ceramide", "C17:0 standard")):
        results.results.append(PeakResult(
            sample_key="s1", sample_name="Injection 1", component=name,
            area=1000.0, height=100.0, internal_standard=standard))
    session.results = results
    widget = ResultsTable(session)
    widget.resize(1400, 400)
    widget.reload()
    return widget


def row_of(table, component):
    for row in range(table.model.rowCount()):
        if table.model.result_at(row).component == component:
            return row
    raise AssertionError(component)


def cell(table, component, column=IS_COLUMN):
    return table.model.index(row_of(table, component), column)


def test_an_analyte_can_be_pointed_at_another_standard(qapp, table):
    flags = table.model.flags(cell(table, "C16:0-Ceramide"))
    assert flags & QtCore.Qt.ItemFlag.ItemIsEditable


def test_a_standard_is_not_quantified_against_one(qapp, table):
    flags = table.model.flags(cell(table, "C17:0 standard"))
    assert not flags & QtCore.Qt.ItemFlag.ItemIsEditable


def test_the_editor_offers_the_components_ticked_is(qapp, table):
    delegate = table.view.itemDelegateForColumn(IS_COLUMN)
    index = table.proxy.mapFromSource(cell(table, "C16:0-Ceramide"))
    combo = delegate.createEditor(table.view, None, index)
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "", "C17:0 standard", "SM(d18:1/12:0)"]


def test_choosing_one_reports_the_component_and_the_standard(qapp, table):
    seen = []
    table.sigInternalStandardChanged.connect(lambda c, s: seen.append((c, s)))
    table.model.setData(cell(table, "C16:0-Ceramide"), "SM(d18:1/12:0)",
                        QtCore.Qt.ItemDataRole.EditRole)
    assert seen == [("C16:0-Ceramide", "SM(d18:1/12:0)")]


def test_choosing_the_same_one_changes_nothing(qapp, table):
    seen = []
    table.sigInternalStandardChanged.connect(lambda c, s: seen.append((c, s)))
    table.model.setData(cell(table, "C16:0-Ceramide"), "C17:0 standard",
                        QtCore.Qt.ItemDataRole.EditRole)
    assert seen == []


def break_the_reference(table):
    """Point a component at a standard nothing answers to, as an import can."""
    from milq.quantify import link_internal_standards
    table.session.method.by_name("C16:0-Ceramide").internal_standard = "never typed"
    link_internal_standards(table.session.results, table.session.method)


def test_a_standard_that_no_component_answers_to_is_shown_and_marked(qapp, table):
    break_the_reference(table)
    index = cell(table, "C16:0-Ceramide")
    # link_internal_standards left the result blank; the method's text is what
    # tells the analyst the reference is broken
    assert table.model.data(index, QtCore.Qt.ItemDataRole.DisplayRole) == "never typed"
    brush = table.model.data(index, QtCore.Qt.ItemDataRole.ForegroundRole)
    assert brush.color() == QtGui.QColor(theme.warning())
    assert "never typed" in table.model.data(index, QtCore.Qt.ItemDataRole.ToolTipRole)


def test_a_standard_that_was_never_ticked_is_is_marked_too(qapp, table):
    # by_name resolves it, so the ratio is real — but nobody declared it a
    # standard, which is what an imported spreadsheet keeps producing
    from milq.quantify import link_internal_standards
    table.session.method.by_name("C17:0 standard").is_internal_standard = False
    link_internal_standards(table.session.results, table.session.method)
    index = cell(table, "C16:0-Ceramide")
    assert table.model.data(index, QtCore.Qt.ItemDataRole.DisplayRole) == "C17:0 standard"
    brush = table.model.data(index, QtCore.Qt.ItemDataRole.ForegroundRole)
    assert brush.color() == QtGui.QColor(theme.warning())
    assert "not ticked IS" in table.model.data(
        index, QtCore.Qt.ItemDataRole.ToolTipRole)


def test_the_editor_keeps_a_broken_reference_on_offer(qapp, table):
    break_the_reference(table)
    delegate = table.view.itemDelegateForColumn(IS_COLUMN)
    index = table.proxy.mapFromSource(cell(table, "C16:0-Ceramide"))
    combo = delegate.createEditor(table.view, None, index)
    assert combo.findText("never typed") >= 0


def test_a_long_component_name_widens_its_column(qapp, table):
    narrow = table.view.columnWidth(COMPONENT_COLUMN)
    table.session.results.results[0].component = "LacCER(d18:1/24:1(15Z))" * 3
    table._fitted_shape = None
    table.reload()
    assert narrow < table.view.columnWidth(COMPONENT_COLUMN) <= MAX_AUTO_WIDTH


def test_a_dragged_width_survives_a_reload(qapp, table):
    table.view.setColumnWidth(COMPONENT_COLUMN, 400)
    table._fitted_shape = None
    table.reload()
    assert table.view.columnWidth(COMPONENT_COLUMN) == 400


def test_the_fit_is_skipped_when_the_batch_has_not_changed(qapp, table):
    table.view.setColumnWidth(COMPONENT_COLUMN, 77)
    table.reload()   # same shape: the numbers may have changed, the rows have not
    assert table.view.columnWidth(COMPONENT_COLUMN) == 77


def test_the_results_carry_the_sample_group(qapp, table):
    from milq.samples import SampleEntry
    entry = SampleEntry("/d/1.wiff", 0, "Injection 1", sample_group="treated")
    table.session.entries = [entry]
    for result in table.session.results:
        result.sample_key = entry.key
    index = table.model.index(row_of(table, "C16:0-Ceramide"),
                              FIELD_INDEX["sample_group"])
    assert table.model.data(index, QtCore.Qt.ItemDataRole.DisplayRole) == "treated"
