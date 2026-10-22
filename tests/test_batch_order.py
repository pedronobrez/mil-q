"""
Batch order: typed in the Samples table, saved with the project, and the
order every chart through the run follows; and the dilution factor set on
many rows at once.
"""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from milq import audit
from milq.components import Component
from milq.qc import batch_qc
from milq.quantify import PeakResult, ResultsSet
from milq.samples import SampleEntry, numbering_start, parse_batch_order
from milq.session import Session
from milq.ui.samples_workspace import (
    CLEAR_ORDER, COL, NUMBER_BY_TIME, NUMBER_IN_TABLE_ORDER, SamplesWorkspace,
)
from milq.validation import (
    acquisition_order, describe_order, order_counts, order_is_known,
)


class Timed:
    """A stand-in for an open sample: an acquisition time and no metadata."""

    def __init__(self, when: str = ""):
        self.acquisition_time = when
        self.name = "sample"

    def metadata(self) -> dict:
        return {"Acquired": self.acquisition_time}


def entry(name: str, when: str = "", order: int | None = None) -> SampleEntry:
    return SampleEntry(f"/d/{name}.wiff", 0, name,
                       sample=Timed(when) if when else None, batch_order=order)


def names(entries) -> list[str]:
    return [e.name for e in entries]


# -- the field ------------------------------------------------------------------ #
def test_positional_construction_is_unchanged():
    old = SampleEntry("/d/a.wiff", 1, "QC", "Quality Control", 25.0, 2.0,
                      "note", "treated")
    assert old.sample_group == "treated"
    assert old.batch_order is None


def test_the_batch_order_survives_a_save_and_reload():
    original = SampleEntry("/d/a.wiff", 0, "QC", batch_order=7)
    back = SampleEntry.from_dict(json.loads(json.dumps(original.to_dict())))
    assert back.batch_order == 7
    assert back == original


def test_an_older_project_without_the_field_still_loads():
    back = SampleEntry.from_dict({"path": "/d/a.wiff", "sample_index": 0,
                                  "name": "QC", "dilution_factor": 2})
    assert back.batch_order is None
    assert back.dilution_factor == 2.0


def test_a_saved_project_keeps_the_order(tmp_path):
    session = Session()
    session.entries = [entry("a", order=2), entry("b", order=1), entry("c")]
    path = tmp_path / "batch.oqproj"
    session.save_project(str(path))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [row["batch_order"] for row in saved["samples"]] == [2, 1, None]


@pytest.mark.parametrize("value, expected", [
    (3, 3), ("3", 3), (" 12 ", 12), (3.0, 3), ("4.0", 4),
    (None, None), ("", None), (0, None), (-2, None), (2.5, None),
    ("second", None), (True, None),
])
def test_only_a_whole_number_from_one_is_a_position(value, expected):
    assert parse_batch_order(value) == expected


# -- the order of the run -------------------------------------------------------- #
def test_without_a_batch_order_the_clock_decides_as_before():
    entries = [entry("late", "2026-09-04T10:30"), entry("early", "2026-09-04T09:00"),
               entry("untimed")]
    assert names(acquisition_order(entries)) == ["early", "late", "untimed"]


def test_a_full_batch_order_overrules_the_clock():
    entries = [entry("a", "2026-09-04T09:00", order=3),
               entry("b", "2026-09-04T10:00", order=1),
               entry("c", "2026-09-04T11:00", order=2)]
    assert names(acquisition_order(entries)) == ["b", "c", "a"]


def test_a_partial_batch_order_puts_the_numbered_first():
    entries = [entry("x", "2026-09-04T08:00"),          # earliest, unnumbered
               entry("n2", "2026-09-04T12:00", order=2),
               entry("y"),                              # no time, no number
               entry("n1", "2026-09-04T13:00", order=1),
               entry("z", "2026-09-04T07:00")]
    assert names(acquisition_order(entries)) == ["n1", "n2", "z", "x", "y"]


def test_equal_numbers_fall_to_the_clock_then_the_order_opened():
    entries = [entry("b", "2026-09-04T10:00", order=1),
               entry("a", "2026-09-04T09:00", order=1),
               entry("c", order=1), entry("d", order=1)]
    assert names(acquisition_order(entries)) == ["a", "b", "c", "d"]


def test_what_the_order_rests_on_is_said():
    full = [entry("a", order=1), entry("b", order=2)]
    timed = [entry("a", "t1"), entry("b", "t2")]
    partial = [entry("a", "t1", order=1), entry("b", "t2")]
    neither = [entry("a", "t1"), entry("b")]

    assert order_counts(full) == (2, 0)
    assert order_is_known(2, *order_counts(full))
    assert describe_order(2, *order_counts(full)) == "in batch order"

    assert order_is_known(2, *order_counts(timed))
    assert describe_order(2, *order_counts(timed)) == "in acquisition order"

    assert not order_is_known(2, *order_counts(partial))
    assert "batch order for 1 of 2" in describe_order(2, *order_counts(partial))

    assert not order_is_known(2, *order_counts(neither))
    assert "order opened" in describe_order(2, *order_counts(neither))


def test_batch_qc_charts_follow_the_batch_order_and_say_so():
    session = Session()
    session.set_components([Component(name="IS", precursor=500.0,
                                       fragment=184.07,
                                       is_internal_standard=True)])
    entries = [entry(f"S{i}", f"2026-09-04T{10 + i:02d}:00", order=5 - i)
               for i in range(5)]
    results = ResultsSet()
    for item in entries:
        results.results.append(PeakResult(
            sample_key=item.key, sample_name=item.name, component="IS",
            area=1000.0, height=500.0, rt=2.0))
    report = batch_qc(results, entries, session.method)
    assert report.numbered == 5 and report.ordered
    assert report.order == "in batch order"
    chart = report.charts[0]
    assert [p.sample for p in chart.injections] == ["S4", "S3", "S2", "S1", "S0"]


# -- numbering a stretch --------------------------------------------------------- #
def test_numbering_everything_starts_at_one():
    entries = [entry("a", order=4), entry("b")]
    assert numbering_start(entries, entries) == 1


def test_numbering_a_stretch_keeps_its_place_or_follows_the_rest():
    entries = [entry("a", order=1), entry("b", order=2), entry("c"),
               entry("d", order=9)]
    assert numbering_start(entries, [entries[2]]) == 10
    assert numbering_start(entries, entries[1:3]) == 2
    assert numbering_start([entry("a"), entry("b")], [entry("a")]) == 1


# -- the Samples workspace ------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def workspace(qapp):
    session = Session()
    session.entries = [
        entry("S0", "2026-09-04T11:00"),
        entry("S1", "2026-09-04T09:00"),
        entry("S2", "2026-09-04T10:00"),
        entry("S3"),
    ]
    widget = SamplesWorkspace(session)
    widget.resize(1400, 400)
    yield widget
    widget.close()


def select(widget, *rows):
    widget.table.clearSelection()
    model = widget.table.selectionModel()
    for row in rows:
        model.select(widget.table.model().index(row, 0),
                     QtCore.QItemSelectionModel.SelectionFlag.Select
                     | QtCore.QItemSelectionModel.SelectionFlag.Rows)


def orders(widget):
    return [e.batch_order for e in widget.session.entries]


def trail(widget):
    return [(e.target, e.before, e.after)
            for e in widget.session.audit.of(audit.SAMPLE_EDITED)]


def test_the_column_shows_the_order(workspace):
    workspace.session.entries[1].batch_order = 3
    workspace.reload()
    assert workspace.table.item(1, COL["Batch order"]).text() == "3"
    assert workspace.table.item(0, COL["Batch order"]).text() == ""


def test_numbering_every_row_in_table_order(workspace):
    workspace._number_rows(NUMBER_IN_TABLE_ORDER)
    assert orders(workspace) == [1, 2, 3, 4]
    assert workspace.table.item(3, COL["Batch order"]).text() == "4"
    assert trail(workspace)[0] == ("S0 · batch order", "", "1")
    assert len(trail(workspace)) == 4


def test_numbering_by_acquisition_time_puts_the_untimed_last(workspace):
    workspace._number_rows(NUMBER_BY_TIME)
    assert orders(workspace) == [3, 1, 2, 4]
    assert "no time" in workspace.status.text()


def test_numbering_a_selection_follows_the_numbered_rows(workspace):
    select(workspace, 0, 1)
    workspace._number_rows(NUMBER_IN_TABLE_ORDER)
    select(workspace, 3)
    workspace._number_rows(NUMBER_IN_TABLE_ORDER)
    assert orders(workspace) == [1, 2, None, 3]


def test_clearing_the_order(workspace):
    workspace._number_rows(NUMBER_IN_TABLE_ORDER)
    select(workspace, 2)
    workspace._number_rows(CLEAR_ORDER)
    assert orders(workspace) == [1, 2, None, 4]
    assert trail(workspace)[-1] == ("S2 · batch order", "3", "")


def test_a_typed_order_is_recorded_and_a_bad_one_refused(workspace):
    item = workspace.table.item(2, COL["Batch order"])
    item.setText("5")
    assert workspace.session.entries[2].batch_order == 5
    item.setText("2.5")
    assert workspace.session.entries[2].batch_order == 5
    assert item.text() == "5"
    assert trail(workspace) == [("S2 · batch order", "", "5")]


def test_sorting_the_rows_by_batch_order(workspace):
    workspace._number_rows(NUMBER_BY_TIME)
    workspace._sort_by_order()
    assert names(workspace.session.entries) == ["S1", "S2", "S0", "S3"]
    assert workspace.table.item(0, COL["Sample"]).text() == "S1"
    assert workspace.session.dirty


def test_a_dilution_applied_to_the_selection(workspace):
    workspace.session.entries[2].dilution_factor = 10.0
    workspace.reload()
    select(workspace, 0, 2, 3)
    workspace.dilution_edit.setText("10")
    workspace._apply_dilution()
    assert [e.dilution_factor for e in workspace.session.entries] == [
        10.0, 1.0, 10.0, 10.0]
    assert workspace.table.item(3, COL["Dilution"]).text() == "10"
    # one line per row the value changed; S2 already said 10
    assert trail(workspace) == [("S0 · dilution", "1", "10"),
                                ("S3 · dilution", "1", "10")]


@pytest.mark.parametrize("typed", ["0", "-2", "ten", ""])
def test_a_dilution_that_is_not_a_positive_number_is_refused(workspace, typed):
    select(workspace, 0, 1)
    workspace.dilution_edit.setText(typed)
    workspace._apply_dilution()
    assert [e.dilution_factor for e in workspace.session.entries] == [1.0] * 4
    assert trail(workspace) == []


def test_a_dilution_needs_a_selection(workspace):
    workspace.dilution_edit.setText("2")
    workspace._apply_dilution()
    assert [e.dilution_factor for e in workspace.session.entries] == [1.0] * 4
    assert "Select" in workspace.status.text()


def test_a_typed_dilution_of_zero_is_put_back(workspace):
    item = workspace.table.item(1, COL["Dilution"])
    item.setText("0")
    assert workspace.session.entries[1].dilution_factor == 1.0
    assert item.text() == "1"


def test_a_column_pasted_from_a_spreadsheet(workspace):
    workspace.table.setCurrentCell(0, COL["Dilution"])
    workspace._paste_text("2\n5\r\n-1\n4\n")
    assert [e.dilution_factor for e in workspace.session.entries] == [
        2.0, 5.0, 1.0, 4.0]
    assert "1 left as they were" in workspace.status.text()
    assert len(trail(workspace)) == 3


def test_one_value_pasted_into_every_selected_row(workspace):
    workspace.table.setCurrentCell(1, COL["Batch order"])
    select(workspace, 1, 3)
    workspace._paste_text("8")
    assert orders(workspace) == [None, 8, None, 8]


def test_a_block_pasted_across_columns_skips_the_read_only(workspace):
    workspace.table.setCurrentCell(0, COL["Group"])
    workspace._paste_text("control\tblank\t5\n"
                          "treated\tstandard\t7\n")
    entries = workspace.session.entries
    # Group, Actual conc., Dilution — the type column is a combo before Group
    assert entries[0].sample_group == "control"
    assert entries[1].sample_group == "treated"
    assert entries[0].actual_concentration is None     # "blank" is no number
    assert entries[0].dilution_factor == 5.0
    assert entries[1].dilution_factor == 7.0


def test_a_type_pasted_by_name(workspace):
    workspace.table.setCurrentCell(0, COL["Type"])
    workspace._paste_text("blank\nQuality Control\nnonsense")
    assert [e.sample_type for e in workspace.session.entries][:3] == [
        "Blank", "Quality Control", "Unknown"]
