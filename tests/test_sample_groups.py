"""The sample group: set in the Samples workspace, summarised in Statistics."""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from milq.components import Component
from milq.quantify import PeakResult, ResultsSet
from milq.samples import QC, SampleEntry, UNKNOWN
from milq.session import Session
from milq.statistics import (
    GROUP_BY_SAMPLE_GROUP, GROUPINGS, summarise,
)
from milq.ui.samples_workspace import COL, SamplesWorkspace


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_the_group_survives_a_save_and_reload():
    entry = SampleEntry("/d/a.wiff", 1, "QC", QC, 25.0, 2.0, "note",
                        sample_group="treated")
    back = SampleEntry.from_dict(json.loads(json.dumps(entry.to_dict())))
    assert back.sample_group == "treated"


def test_an_older_project_without_the_field_still_loads():
    back = SampleEntry.from_dict({"path": "/d/a.wiff", "sample_index": 0,
                                  "name": "QC"})
    assert back.sample_group == ""


# -- statistics ---------------------------------------------------------------- #
def batch():
    method_components = [Component(name="Cer", precursor=538.5, fragment=264.2686)]
    entries = [
        SampleEntry("/d/1.wiff", 0, "C1", sample_group="control"),
        SampleEntry("/d/2.wiff", 0, "C2", sample_group="control"),
        SampleEntry("/d/3.wiff", 0, "T1", sample_group="treated"),
        SampleEntry("/d/4.wiff", 0, "T2", sample_group="treated"),
        SampleEntry("/d/5.wiff", 0, "X1"),          # no group
    ]
    results = ResultsSet()
    for entry, area in zip(entries, (100.0, 120.0, 300.0, 340.0, 999.0)):
        results.results.append(PeakResult(
            sample_key=entry.key, sample_name=entry.name, component="Cer",
            area=area, height=area / 2))
    session = Session()
    session.set_components(method_components)
    return results, entries, session.method


def test_sample_group_is_offered_as_a_grouping():
    assert GROUP_BY_SAMPLE_GROUP in GROUPINGS


def test_summarising_by_sample_group():
    results, entries, method = batch()
    rows = summarise(results, entries, method, GROUP_BY_SAMPLE_GROUP, "area")
    by_group = {r.group: r for r in rows}
    assert set(by_group) == {"control", "treated"}
    assert by_group["control"].mean == pytest.approx(110.0)
    assert by_group["treated"].mean == pytest.approx(320.0)
    assert by_group["control"].used == 2


def test_an_ungrouped_sample_is_left_out_rather_than_pooled():
    results, entries, method = batch()
    rows = summarise(results, entries, method, GROUP_BY_SAMPLE_GROUP, "area")
    assert all(row.group for row in rows)
    assert sum(row.total for row in rows) == 4      # the fifth is not in a group


# -- the Samples workspace ------------------------------------------------------ #
@pytest.fixture
def workspace(qapp):
    session = Session()
    session.entries = [
        SampleEntry("/d/1.wiff", 0, "C1", sample_group="control"),
        SampleEntry("/d/2.wiff", 0, "C2"),
        SampleEntry("/d/3.wiff", 0, "T1", sample_group="treated"),
    ]
    widget = SamplesWorkspace(session)
    widget.resize(1200, 400)
    return widget


def combo(widget, row):
    return widget.table.cellWidget(row, COL["Group"])


def test_the_column_shows_the_group(qapp, workspace):
    assert combo(workspace, 0).currentText() == "control"
    assert combo(workspace, 1).currentText() == ""


def test_every_group_in_the_batch_is_on_offer(qapp, workspace):
    box = combo(workspace, 1)
    assert [box.itemText(i) for i in range(box.count())] == ["", "control", "treated"]


def test_a_new_group_can_be_typed_and_reaches_the_entry(qapp, workspace):
    box = combo(workspace, 1)
    box.setCurrentText("day 7")
    workspace._commit_group(1)
    assert workspace.session.entries[1].sample_group == "day 7"


def test_a_newly_typed_group_is_offered_to_the_other_rows(qapp, workspace):
    combo(workspace, 1).setCurrentText("day 7")
    workspace._commit_group(1)
    box = combo(workspace, 0)
    assert "day 7" in [box.itemText(i) for i in range(box.count())]


def test_a_group_can_be_applied_to_a_selection(qapp, workspace):
    workspace.table.selectRow(1)
    workspace.table.selectionModel().select(
        workspace.table.model().index(2, 0),
        QtCore.QItemSelectionModel.SelectionFlag.Select
        | QtCore.QItemSelectionModel.SelectionFlag.Rows)
    workspace.group_edit.setCurrentText("treated")
    workspace._apply_group()
    assert [e.sample_group for e in workspace.session.entries] == [
        "control", "treated", "treated"]


def test_the_status_line_names_the_groups(qapp, workspace):
    assert "control" in workspace.status.text()
    assert "1 ungrouped" in workspace.status.text()


def test_the_type_column_is_untouched(qapp, workspace):
    assert workspace.table.cellWidget(0, COL["Type"]).currentText() == UNKNOWN


def test_a_component_s_groups_are_listed_together():
    results, entries, method = batch()
    rows = summarise(results, entries, method, GROUP_BY_SAMPLE_GROUP, "area")
    assert [r.group for r in rows] == ["control", "treated"]


def test_groups_keep_the_order_the_batch_introduces_them_in():
    results, entries, method = batch()
    entries[0].sample_group = "treated"       # treated is now injected first
    entries[2].sample_group = "control"
    rows = summarise(results, entries, method, GROUP_BY_SAMPLE_GROUP, "area")
    assert [r.group for r in rows] == ["treated", "control"]


# -- two entries must never read the same ------------------------------------ #
def _entry(path, index=0, sample=None):
    from milq.samples import SampleEntry

    return SampleEntry(path=path, sample_index=index,
                       name=os.path.basename(path), sample=sample)


def test_the_same_acquisition_in_two_formats_is_told_apart():
    """
    Opening a .wiff and its mzML gave two rows called "1" and two traces in
    the legend called "1", with nothing to say which was which.
    """
    from milq.samples import shorten_names

    entries = [_entry("/data/demo_Sample_01.wiff"),
               _entry("/data/demo_Sample_01.mzML"),
               _entry("/data/demo_Sample_03.wiff")]
    shorten_names(entries)
    names = [e.name for e in entries]
    assert len(set(names)) == 3
    assert names[0] == "01 (wiff)"
    assert names[1] == "01 (mzML)"
    assert names[2] == "03"


def test_the_same_name_in_two_folders_is_told_apart():
    from milq.samples import shorten_names

    entries = [_entry("/data/monday/run.wiff"), _entry("/data/tuesday/run.wiff")]
    shorten_names(entries)
    assert {e.name for e in entries} == {"run (monday)", "run (tuesday)"}


def test_several_injections_in_one_file_keep_their_own_names():
    from milq.samples import shorten_names

    class Sample:
        def __init__(self, name):
            self.name = name

    entries = [_entry("/data/batch.wiff", 0, Sample("blank")),
               _entry("/data/batch.wiff", 1, Sample("QC01"))]
    shorten_names(entries)
    assert {e.name for e in entries} == {"batch (blank)", "batch (QC01)"}


def test_when_nothing_distinguishes_them_they_are_numbered():
    from milq.samples import shorten_names

    entries = [_entry("/data/run.wiff", 0), _entry("/data/run.wiff", 1)]
    shorten_names(entries)
    assert {e.name for e in entries} == {"run #1", "run #2"}
