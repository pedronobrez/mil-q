"""
The audit trail: what was changed by hand, recorded where the change is made.

Two things are being checked. The first is the trail itself — that it round
trips through the project, that it only ever grows, and that a project
written before it existed opens with an empty one rather than an invented
one. The second is harder and is the point of the feature: that every place
in the interface where a person changes a number writes exactly one line, no
more and no fewer, which is why the tests below drive the widgets rather than
call the recorder.
"""

import csv
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq import audit, report  # noqa: E402
from milq.audit import AuditEntry, AuditTrail  # noqa: E402
from milq.calibration import Calibration, CalibrationPoint  # noqa: E402
from milq.calibration import fit as fit_curve  # noqa: E402
from milq.components import Component, IntegrationParams  # noqa: E402
from milq.quantify import PeakResult, ResultsSet  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.ui import style  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.apply(app)
    yield app


# --------------------------------------------------------------------------- #
# the trail on its own
# --------------------------------------------------------------------------- #
def test_an_entry_keeps_its_values_as_they_were_shown():
    entry = AuditEntry(when="2026-09-10T09:00:00", what=audit.SAMPLE_EDITED,
                       target="QC01 · concentration", before=None, after=75.0)
    assert entry.before == "" and entry.after == "75"
    assert entry.change == "75"
    assert entry.row[0] == "2026-09-10T09:00:00"


def test_a_long_value_is_cut_rather_than_wrapped():
    entry = AuditEntry(when=audit.now(), what="x", target="a" * 400)
    assert len(entry.target) == audit.MAX_LENGTH
    assert entry.target.endswith("…")


def test_a_timestamp_sorts_as_text_the_way_it_sorts_as_time():
    """The panel sorts the column as text, so the format has to carry it."""
    stamps = ["2026-09-09T23:59:59", "2026-09-10T00:00:01",
              "2026-10-01T08:00:00"]
    assert sorted(stamps) == stamps
    assert len(audit.now()) == len(stamps[0])


def test_the_trail_only_grows():
    trail = AuditTrail()
    trail.record("one", "a")
    first = trail.entries
    trail.record("two", "b")
    # the tuple handed out is a copy: a caller holding one cannot reach in
    assert len(first) == 1 and len(trail) == 2
    assert [e.what for e in trail] == ["one", "two"]
    assert first[0] is trail[0]
    for forbidden in ("remove", "delete", "clear", "pop", "insert"):
        assert not hasattr(trail, forbidden), forbidden
    with pytest.raises(Exception):
        trail[0].what = "three"


def test_a_trail_round_trips_through_a_dict():
    trail = AuditTrail()
    trail.record(audit.MANUAL_INTEGRATION, "PC 34:1 · QC01",
                 "not integrated", "11.2–11.6 min, area 4,500", "dragged")
    again = AuditTrail.from_dict(trail.to_dict())
    assert again.rows() == trail.rows()


def test_a_project_that_recorded_nothing_reads_as_nothing():
    assert len(AuditTrail.from_dict(None)) == 0
    assert len(AuditTrail.from_dict({})) == 0
    assert len(AuditTrail.from_dict({"entries": []})) == 0


# --------------------------------------------------------------------------- #
# what changed between two component tables
# --------------------------------------------------------------------------- #
def test_an_edited_field_names_the_column_and_both_values():
    before = [Component(name="PC 34:1", precursor=760.5851, rt=11.42)]
    after = [Component(name="PC 34:1", precursor=760.5851, rt=11.60)]
    changes = audit.component_changes(before, after)
    assert changes == [(audit.COMPONENT_EDITED, "PC 34:1 · RT", "11.42", "11.6")]


def test_a_rename_is_a_rename_and_not_a_removal_and_an_addition():
    before = [Component(name="new", precursor=760.5851)]
    after = [Component(name="PC 34:1", precursor=760.5851)]
    assert audit.component_changes(before, after) == [
        (audit.COMPONENT_EDITED, "PC 34:1 · name", "new", "PC 34:1")]


def test_a_component_added_or_removed_is_one_entry_that_describes_it():
    one = Component(name="PC 34:1", precursor=760.5851, fragment=184.0733,
                    rt=11.42)
    added = audit.component_changes([], [one])
    assert added == [(audit.COMPONENT_ADDED, "PC 34:1", "",
                      "760.5851 → 184.0733 RT 11.42")]
    removed = audit.component_changes([one], [])
    assert removed[0][0] == audit.COMPONENT_REMOVED and removed[0][3] == ""


def test_a_table_committed_unchanged_records_nothing():
    table = [Component(name="a", precursor=1.0),
             Component(name="b", precursor=2.0)]
    assert audit.component_changes(table, list(table)) == []


def test_the_settings_a_reprocessing_ran_with_are_one_line():
    line = audit.describe_integration(IntegrationParams(smoothing=3.0))
    assert "smoothing 3" in line and len(line) <= audit.MAX_LENGTH


# --------------------------------------------------------------------------- #
# the session and the project
# --------------------------------------------------------------------------- #
def test_recording_marks_the_project_unsaved_and_says_so(qapp):
    session = Session()
    seen = []
    session.sigAuditChanged.connect(lambda: seen.append(len(session.audit)))
    session._mark_clean()
    session.record(audit.SAMPLE_EDITED, "QC01 · comment", "", "spiked")
    assert session.dirty and seen == [1]


def test_the_trail_survives_a_save_and_a_load(qapp, tmp_path):
    session = Session()
    session.entries = [SampleEntry("/d/QC01.wiff", 0, "QC01")]
    session.record(audit.MANUAL_INTEGRATION, "PC 34:1 · QC01",
                   "not integrated", "11.2–11.6 min, area 4,500")
    path = str(tmp_path / "batch.oqproj")
    session.save_project(path)

    with open(path, encoding="utf-8") as handle:
        written = json.load(handle)
    assert [row["what"] for row in written["audit"]["entries"]] == [
        audit.MANUAL_INTEGRATION, audit.PROJECT_SAVED]

    other = Session()
    other.load_project(path)
    assert other.audit.rows() == session.audit.rows()
    # loading is not itself a change: the project comes back clean
    assert not other.dirty


def test_saving_is_itself_recorded_in_the_file_it_writes(qapp, tmp_path):
    """The saved project holds the record of its own saving."""
    session = Session()
    path = str(tmp_path / "batch.oqproj")
    session.save_project(path)
    saved = session.audit.of(audit.PROJECT_SAVED)
    assert len(saved) == 1 and saved[0].after == path
    assert not session.dirty, "the save that was just recorded is the save"


def test_a_project_written_before_this_existed_opens_with_an_empty_trail(
        qapp, tmp_path):
    path = tmp_path / "old.oqproj"
    path.write_text(json.dumps({"version": 3, "method": {}, "samples": [],
                                "results": [], "calibrations": {}}),
                    encoding="utf-8")
    session = Session()
    session.load_project(str(path))
    assert len(session.audit) == 0


def test_closing_everything_starts_a_new_trail_rather_than_emptying_one(qapp):
    session = Session()
    session.record(audit.SAMPLE_EDITED, "QC01 · type", "Unknown", "Blank")
    kept = session.audit
    session.close_all()
    assert len(session.audit) == 0 and len(kept) == 1


def test_the_recalibration_switch_is_recorded_once(qapp):
    session = Session()
    session.set_recalibrate(True)
    session.set_recalibrate(True)          # already on: nothing happened
    session.set_recalibrate(False)
    entries = session.audit.of(audit.RECALIBRATION)
    assert [(e.before, e.after) for e in entries] == [("off", "on"),
                                                      ("on", "off")]


# --------------------------------------------------------------------------- #
# the workspaces, driven
# --------------------------------------------------------------------------- #
def loaded_entry(name):
    """An entry with a live channel, so a peak can be integrated in it."""
    from tests.test_matching import Sample
    from tests.test_quantify import TracedChannel

    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([
        TracedChannel(1, 538.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
        TracedChannel(2, 566.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
    ])
    return entry


@pytest.fixture
def session(qapp):
    session = Session()
    session.set_components([
        Component(name="Cer A", precursor=538.5, fragment=264.2686,
                  group="Cer", rt=5.0, rt_halfwidth=1.0),
        Component(name="Cer B", precursor=566.5, fragment=264.2686,
                  group="Cer", rt=5.0, rt_halfwidth=1.0),
    ])
    session.entries = [loaded_entry(f"S{i}") for i in range(3)]
    return session


@pytest.fixture
def analytics(session):
    from milq.ui.analytics import AnalyticsWorkspace

    widget = AnalyticsWorkspace(session)
    widget.resize(1200, 800)
    yield widget
    widget.close()


def select(workspace, name):
    from milq.ui.analytics import ROLE_NAME

    it = QtWidgets.QTreeWidgetItemIterator(workspace.component_tree)
    while it.value():
        if it.value().data(0, ROLE_NAME) == name:
            workspace.component_tree.setCurrentItem(it.value())
            return True
        it += 1
    return False


def test_processing_the_batch_is_one_entry_saying_what_it_ran_with(analytics):
    analytics.process_batch()
    entries = analytics.session.audit.of(audit.PROCESSED)
    assert len(entries) == 1
    assert "6 row(s)" in entries[0].after
    assert "valley" in entries[0].note


def test_a_manual_integration_records_the_area_before_and_after(analytics):
    session = analytics.session
    analytics.process_batch()
    assert select(analytics, "Cer A")
    before = session.results.get(session.entries[0].key, "Cer A").area
    assert before > 0

    analytics._on_manual_range(session.entries[0].key, 4.2, 5.8)
    entries = session.audit.of(audit.MANUAL_INTEGRATION)
    assert len(entries) == 1, "one drag, one line"
    entry = entries[0]
    assert entry.target == "Cer A · S0"
    assert f"{before:,.0f}" in entry.before
    assert "area" in entry.after and "4.200–5.800 min" in entry.note
    assert session.results.get(session.entries[0].key, "Cer A").manual


def test_putting_a_row_back_on_the_detector_is_recorded_too(analytics):
    session = analytics.session
    analytics.process_batch()
    select(analytics, "Cer A")
    analytics._on_manual_range(session.entries[0].key, 4.2, 5.8)
    analytics._revert_manual(session.entries[0].key)
    entries = session.audit.of(audit.AUTOMATIC_INTEGRATION)
    assert len(entries) == 1 and entries[0].target == "Cer A · S0"


def test_excluding_a_row_from_the_results_table_is_one_entry(analytics):
    from milq.ui.results_table import USED_COLUMN

    session = analytics.session
    analytics.process_batch()
    model = analytics.results.model
    index = model.index(0, USED_COLUMN)
    model.setData(index, QtCore.Qt.CheckState.Unchecked.value,
                  QtCore.Qt.ItemDataRole.CheckStateRole)
    # ticking it to what it already is changes nothing and records nothing
    model.setData(index, QtCore.Qt.CheckState.Unchecked.value,
                  QtCore.Qt.ItemDataRole.CheckStateRole)
    entries = session.audit.of(audit.ROW_USED)
    assert len(entries) == 1
    assert (entries[0].before, entries[0].after) == ("used", "excluded")


def test_applying_an_integration_parameter_reprocesses_and_says_what_with(
        analytics):
    session = analytics.session
    analytics.process_batch()
    select(analytics, "Cer A")
    analytics._apply_to_component(IntegrationParams(smoothing=2.0))
    entries = session.audit.of(audit.REPROCESSED)
    assert len(entries) == 1
    assert entries[0].target == "Cer A"
    assert "smoothing 2" in entries[0].note and "row(s)" in entries[0].after


def _curve(session) -> Calibration:
    points = [CalibrationPoint(entry.key, entry.name, level, level * 100.0)
              for entry, level in zip(session.entries, (1.0, 5.0, 10.0))]
    curve = fit_curve(points, "linear", "1", "Cer A")
    session.calibrations["Cer A"] = curve
    return curve


def test_dropping_a_standard_from_a_curve_is_recorded_with_its_level(analytics):
    session = analytics.session
    curve = _curve(session)
    select(analytics, "Cer A")
    analytics._toggle_point(curve.points[1].sample_key)
    entries = session.audit.of(audit.CALIBRATION_POINT)
    assert len(entries) == 1
    assert entries[0].target == "Cer A · S1"
    assert (entries[0].before, entries[0].after) == ("used", "excluded")
    assert entries[0].note.startswith("5")


def test_putting_it_back_is_the_other_direction(analytics):
    session = analytics.session
    curve = _curve(session)
    select(analytics, "Cer A")
    analytics._toggle_point(curve.points[1].sample_key)
    analytics._toggle_point(curve.points[1].sample_key)
    entries = session.audit.of(audit.CALIBRATION_POINT)
    assert [(e.before, e.after) for e in entries] == [("used", "excluded"),
                                                      ("excluded", "used")]


def test_the_automatic_outlier_pass_records_how_many_it_dropped(analytics):
    session = analytics.session
    _curve(session)
    select(analytics, "Cer A")
    analytics._auto_outliers(15.0)
    entries = session.audit.of(audit.CALIBRATION_OUTLIERS)
    assert len(entries) == 1 and entries[0].target == "Cer A"
    assert "excluded" in entries[0].after and "15%" in entries[0].note


def test_choosing_an_internal_standard_in_the_table_is_a_method_edit(analytics):
    session = analytics.session
    analytics._set_internal_standard("Cer A", "Cer B")
    entries = session.audit.of(audit.COMPONENT_EDITED)
    assert len(entries) == 1
    assert entries[0].target == "Cer A · internal standard"
    assert entries[0].after == "Cer B"


# -- the method workspace ---------------------------------------------------- #
@pytest.fixture
def method_workspace(session):
    from milq.ui.method_workspace import MethodWorkspace

    widget = MethodWorkspace(session)
    yield widget
    widget.close()


def test_editing_a_cell_records_the_column_and_the_two_values(
        method_workspace):
    from milq.ui.method_workspace import COL

    session = method_workspace.session
    method_workspace.table.item(0, COL["RT"]).setText("6.25")
    entries = session.audit.of(audit.COMPONENT_EDITED)
    assert len(entries) == 1, "one cell, one line"
    assert entries[0].target == "Cer A · RT"
    assert (entries[0].before, entries[0].after) == ("5", "6.25")
    assert session.method.by_name("Cer A").rt == 6.25


def test_a_row_removed_from_the_table_is_recorded(method_workspace):
    session = method_workspace.session
    method_workspace.table.selectRow(1)
    method_workspace._remove_rows()
    entries = session.audit.of(audit.COMPONENT_REMOVED)
    assert len(entries) == 1 and entries[0].target == "Cer B"


def test_a_row_added_and_named_is_recorded_as_an_addition(method_workspace):
    from milq.ui.method_workspace import COL

    session = method_workspace.session
    method_workspace._add_row()
    row = method_workspace.table.rowCount() - 1
    method_workspace.table.item(row, COL["Precursor"]).setText("700.5")
    added = session.audit.of(audit.COMPONENT_ADDED)
    assert len(added) == 1 and added[0].target == "new"


def test_a_default_under_the_table_is_recorded_when_the_typing_stops(
        method_workspace):
    session = method_workspace.session
    method_workspace.tol_spin.setValue(0.5)      # as if each digit were typed
    method_workspace.tol_spin.setValue(0.05)
    assert session.audit.of(audit.METHOD_DEFAULT) == []
    method_workspace.tol_spin.editingFinished.emit()
    entries = session.audit.of(audit.METHOD_DEFAULT)
    assert len(entries) == 1, "one decision, one line"
    assert entries[0].target == "default tolerance"
    assert (entries[0].before, entries[0].after) == ("0.02", "0.05")


# -- the samples workspace ---------------------------------------------------- #
@pytest.fixture
def samples_workspace(session):
    from milq.ui.samples_workspace import SamplesWorkspace

    # the batch table reads a sample's metadata; the stub channels here have
    # none, and none of what this workspace edits comes off the file anyway
    for entry in session.entries:
        entry.sample = None
    widget = SamplesWorkspace(session)
    yield widget
    widget.close()


def test_a_sample_type_group_and_number_are_each_recorded_once(
        samples_workspace):
    from milq.ui.samples_workspace import COL

    session = samples_workspace.session
    samples_workspace.table.cellWidget(0, COL["Type"]).setCurrentText("Blank")
    samples_workspace.table.item(0, COL["Actual conc."]).setText("75")
    samples_workspace.table.item(1, COL["Dilution"]).setText("2")
    samples_workspace.table.item(1, COL["Comment"]).setText("spiked")
    group = samples_workspace.table.cellWidget(2, COL["Group"])
    group.setCurrentText("treated")
    samples_workspace._commit_group(2)

    entries = session.audit.of(audit.SAMPLE_EDITED)
    assert [(e.target, e.before, e.after) for e in entries] == [
        ("S0 · type", "Unknown", "Blank"),
        ("S0 · concentration", "", "75"),
        ("S1 · dilution", "1", "2"),
        ("S1 · comment", "", "spiked"),
        ("S2 · group", "none", "treated"),
    ]
    assert session.entries[0].sample_type == "Blank"
    assert session.entries[2].sample_group == "treated"


def test_retyping_a_value_as_it_already_was_records_nothing(samples_workspace):
    from milq.ui.samples_workspace import COL

    session = samples_workspace.session
    samples_workspace.table.item(0, COL["Dilution"]).setText("1")
    samples_workspace.table.cellWidget(0, COL["Type"]).setCurrentText("Unknown")
    assert session.audit.of(audit.SAMPLE_EDITED) == []


def test_a_concentration_copied_down_records_the_rows_it_filled(
        samples_workspace):
    session = samples_workspace.session
    session.entries[0].actual_concentration = 75.0
    samples_workspace.reload()
    samples_workspace.table.selectAll()
    samples_workspace._apply_concentration()
    entries = session.audit.of(audit.SAMPLE_EDITED)
    assert [e.target for e in entries] == ["S1 · concentration",
                                           "S2 · concentration"]
    assert all(e.after == "75" for e in entries)


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #
@pytest.fixture
def panel(session):
    from milq.ui.audit_panel import AuditPanel

    session.record(audit.MANUAL_INTEGRATION, "Cer A · S0", "not integrated",
                   "4.2–5.8 min, area 900", when="2026-09-10T09:00:00")
    session.record(audit.SAMPLE_EDITED, "S1 · type", "Unknown", "Blank",
                   when="2026-09-10T09:00:01")
    widget = AuditPanel(session)
    yield widget
    widget.close()


def test_the_panel_shows_every_change_and_is_read_only(panel):
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, 1).text() == audit.MANUAL_INTEGRATION
    assert panel.table.editTriggers() == \
        QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers


def test_it_follows_the_session(panel):
    panel.session.record(audit.PROJECT_SAVED, "batch.oqproj")
    assert panel.table.rowCount() == 3


def test_it_sorts_by_time_both_ways(panel):
    panel.table.sortItems(0, QtCore.Qt.SortOrder.DescendingOrder)
    assert panel.table.item(0, 2).text() == "S1 · type"
    panel.table.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)
    assert panel.table.item(0, 2).text() == "Cer A · S0"


def test_the_filter_narrows_to_what_holds_the_words(panel):
    panel.filter_edit.setText("Cer A")
    hidden = [panel.table.isRowHidden(r) for r in range(panel.table.rowCount())]
    assert hidden.count(False) == 1
    panel.filter_edit.setText("")
    assert not any(panel.table.isRowHidden(r)
                   for r in range(panel.table.rowCount()))


def test_the_status_line_says_it_is_not_a_signature(panel):
    assert "signature" in panel.status.text()


def test_the_export_writes_the_whole_trail_and_not_the_filtered_view(
        panel, tmp_path):
    panel.filter_edit.setText("Cer A")
    path = panel.export_csv(str(tmp_path / "trail.csv"))
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == list(audit.COLUMNS)
    assert len(rows) == 3, "the header and both changes"
    assert rows[1][1] == audit.MANUAL_INTEGRATION


def test_the_panel_names_its_manual_page(panel):
    from milq.ui.help_window import help_page_for

    assert help_page_for(panel) == "audit-trail"
    assert help_page_for(panel.table) == "audit-trail"


def test_the_shell_opens_it_from_the_file_menu(qapp):
    from milq.ui.shell import MainShell

    shell = MainShell()
    shell.session.record(audit.PROJECT_SAVED, "batch.oqproj")
    shell.show_audit()
    dialog = shell._audit_dialog
    assert dialog.panel.table.rowCount() == 1
    from milq.ui.help_window import help_page_for
    assert help_page_for(dialog) == "audit-trail"
    dialog.close()
    shell.close()


def test_the_analytics_workspace_carries_it_as_a_tab(analytics):
    labels = [analytics.bottom.tabText(i)
              for i in range(analytics.bottom.count())]
    assert "Audit trail" in labels
    analytics.session.record(audit.PROJECT_SAVED, "batch.oqproj")
    assert analytics.audit.table.rowCount() == 1


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
def _reported(session) -> str:
    return report.build_html(session, title="A batch")


def test_a_batch_nobody_touched_gets_no_section(qapp):
    session = Session()
    session.entries = [SampleEntry("/d/QC01.wiff", 0, "QC01")]
    assert "Changes made by hand" not in _reported(session)


def test_the_section_lists_the_trail_and_what_it_is_not(qapp):
    session = Session()
    session.entries = [SampleEntry("/d/QC01.wiff", 0, "QC01")]
    session.results = ResultsSet()
    session.results.results.append(
        PeakResult(sample_key="k", sample_name="QC01", component="PC 34:1"))
    session.record(audit.MANUAL_INTEGRATION, "PC 34:1 · QC01",
                   "not integrated", "11.2–11.6 min, area 4,500")
    document = _reported(session)
    assert "Changes made by hand</h2>" in document
    assert "PC 34:1 · QC01" in document and "11.2–11.6 min" in document
    assert "not an electronic signature" in document
    for column in audit.COLUMNS:
        assert f">{column}</th>" in document, column
    assert "no user accounts" in document


def test_a_name_that_looks_like_markup_is_escaped_here_too(qapp):
    session = Session()
    session.record(audit.SAMPLE_EDITED, "<b>QC</b> · type", "Unknown", "Blank")
    document = _reported(session)
    assert "&lt;b&gt;QC&lt;/b&gt;" in document and "<b>QC</b>" not in document


def test_the_sections_stay_numbered_without_gaps_with_it_in(qapp):
    session = Session()
    session.record(audit.PROJECT_SAVED, "batch.oqproj")
    document = report.build_html(session, sections=("summary", "audit"))
    assert ">1. Summary</h2>" in document
    assert ">2. Changes made by hand</h2>" in document
