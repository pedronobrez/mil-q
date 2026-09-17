"""Tests for the Method table's column sizing and internal-standard chooser."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from milq.components import Component
from milq.session import Session
from milq.ui.method_workspace import (
    COL, MAX_AUTO_WIDTH, MethodWorkspace,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def make(components):
    session = Session()
    session.set_components(components)
    widget = MethodWorkspace(session)
    widget.resize(1400, 500)
    return widget


@pytest.fixture
def method():
    return [
        Component(name="C17:0 standard", precursor=552.5, fragment=534.5245,
                  is_internal_standard=True),
        Component(name="SM(d18:1/12:0)", precursor=647.5, fragment=184.0733,
                  is_internal_standard=True),
        Component(name="C16:0-Ceramide", precursor=538.5, fragment=264.2686,
                  internal_standard="C17:0 standard"),
        Component(name="C18:0-Ceramide", precursor=566.5, fragment=264.2686),
    ]


def choices(widget, row):
    combo = widget.table.cellWidget(row, COL["Internal standard"])
    return [combo.itemText(i) for i in range(combo.count())]


def test_only_rows_ticked_is_are_offered(qapp, method):
    widget = make(method)
    assert choices(widget, 2) == ["", "C17:0 standard", "SM(d18:1/12:0)"]


def test_a_standard_is_not_offered_to_itself(qapp, method):
    widget = make(method)
    assert "C17:0 standard" not in choices(widget, 0)


def test_ticking_a_row_adds_it_to_the_other_rows(qapp, method):
    widget = make(method)
    widget.table.item(3, COL["IS"]).setCheckState(QtCore.Qt.CheckState.Checked)
    assert "C18:0-Ceramide" in choices(widget, 2)


def test_unticking_a_row_leaves_the_rows_that_named_it_flagged(qapp, method):
    widget = make(method)
    widget.table.item(0, COL["IS"]).setCheckState(QtCore.Qt.CheckState.Unchecked)
    combo = widget.table.cellWidget(2, COL["Internal standard"])
    # the reference is kept and marked, never silently cleared
    assert combo.currentText() == "C17:0 standard"
    assert combo.styleSheet()
    assert widget.components()[2].internal_standard == "C17:0 standard"


def test_a_reference_with_no_row_survives_loading(qapp, method):
    method[2].internal_standard = "a standard that was never transcribed"
    widget = make(method)
    combo = widget.table.cellWidget(2, COL["Internal standard"])
    assert combo.currentText() == "a standard that was never transcribed"
    assert combo.styleSheet()
    assert widget.components()[2].internal_standard == method[2].internal_standard


def test_choosing_a_standard_reaches_the_method(qapp, method):
    widget = make(method)
    combo = widget.table.cellWidget(3, COL["Internal standard"])
    combo.setCurrentText("SM(d18:1/12:0)")
    assert widget.session.method.components[3].internal_standard == "SM(d18:1/12:0)"


def test_every_column_can_be_dragged(qapp, method):
    widget = make(method)
    header = widget.table.horizontalHeader()
    modes = {header.sectionResizeMode(c) for c in range(widget.table.columnCount())}
    assert modes == {QtWidgets.QHeaderView.ResizeMode.Interactive}


def test_a_long_name_below_the_fold_still_widens_the_column(qapp, method):
    method += [Component(name="x" * 200, precursor=300.0) for _ in range(60)]
    widget = make(method)
    assert widget.table.columnWidth(COL["Name"]) == MAX_AUTO_WIDTH


def test_a_dragged_width_survives_a_reload(qapp, method):
    widget = make(method)
    widget.table.setColumnWidth(COL["Name"], 480)
    widget.reload()
    assert widget.table.columnWidth(COL["Name"]) == 480


# --------------------------------------------------------------------------- #
# filling the formulas from the names
# --------------------------------------------------------------------------- #
def _filling_method():
    return [
        Component(name="SM(d18:1/12:0)", precursor=647.5, fragment=184.0733,
                  adduct="[M+H]+", is_internal_standard=True),
        Component(name="C16:0-Ceramide", precursor=538.5, fragment=264.2686,
                  adduct="[M+H]+"),
        Component(name="C25:0-Ceramide", precursor=664.4, fragment=264.2686,
                  adduct="[M+H]+"),
        Component(name="Mine", precursor=500.0, adduct="[M+H]+",
                  formula="C30H61NO3"),
    ]


def test_filling_formulas_writes_the_empty_cells_only(qapp, monkeypatch):
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: None)
    widget = make(_filling_method())
    widget.fill_formulas()
    formulas = [widget.table.item(row, COL["Formula"]).text()
                for row in range(widget.table.rowCount())]
    assert formulas == ["C35H71N2O6P", "C34H67NO3", "", "C30H61NO3"]
    assert [c.formula for c in widget.session.method.components] == formulas


def test_filling_formulas_leaves_every_precursor_alone(qapp, monkeypatch):
    """
    A formula and an adduct can stand in for a precursor when one is typed by
    hand, and here they must not: the precursor is what the derivation was
    checked against, and moving it would move every extraction window in the
    batch without anybody asking.
    """
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: None)
    widget = make(_filling_method())
    before = [widget.table.item(row, COL["Precursor"]).text()
              for row in range(widget.table.rowCount())]
    widget.fill_formulas()
    after = [widget.table.item(row, COL["Precursor"]).text()
             for row in range(widget.table.rowCount())]
    assert before == after
    assert [c.precursor for c in widget.session.method.components] == [
        647.5, 538.5, 664.4, 500.0]


def test_filling_formulas_says_what_it_could_not_do(qapp, monkeypatch):
    said = {}
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "setDetailedText",
                        lambda self, text: said.setdefault("detail", text))
    widget = make(_filling_method())
    widget.fill_formulas()
    assert "2 formula(s) filled in" in widget.status.text()
    assert "C25:0-Ceramide" in said["detail"] and "664.6602" in said["detail"]
