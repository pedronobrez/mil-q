"""The New Project wizard and the unsaved-work guard around it."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from milq.components import Component, save_components
from milq.samples import QC, STANDARD, SampleEntry, UNKNOWN
from milq.session import (
    PROJECT_SUFFIX, Session,
)
from milq.ui.new_project import (
    METHOD, METHOD_EMPTY, METHOD_IMPORT, PROJECT, SAMPLES, SUMMARY,
    NewProjectWizard, StartDialog,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def wizard(qapp, tmp_path):
    session = Session()
    widget = NewProjectWizard(session, str(tmp_path))
    yield widget
    widget.deleteLater()


# -- the project page ----------------------------------------------------------- #
def test_the_project_path_is_built_from_the_name_and_folder(qapp, wizard, tmp_path):
    page = wizard.page(PROJECT)
    page.name_edit.setText("cohort A")
    page.folder_edit.setText(str(tmp_path))
    assert page.project_path() == str(tmp_path / f"cohort A{PROJECT_SUFFIX}")


def test_the_suffix_is_not_doubled(qapp, wizard, tmp_path):
    page = wizard.page(PROJECT)
    page.name_edit.setText(f"cohort A{PROJECT_SUFFIX}")
    page.folder_edit.setText(str(tmp_path))
    assert page.project_path().count(PROJECT_SUFFIX) == 1


def test_a_name_is_required_before_moving_on(qapp, wizard, tmp_path):
    page = wizard.page(PROJECT)
    page.folder_edit.setText(str(tmp_path))
    assert not page.isComplete()
    page.name_edit.setText("cohort A")
    assert page.isComplete()


def test_a_folder_that_does_not_exist_is_refused(qapp, wizard, tmp_path):
    page = wizard.page(PROJECT)
    page.name_edit.setText("cohort A")
    page.folder_edit.setText(str(tmp_path / "nowhere"))
    assert not page.isComplete()


def test_an_existing_file_is_called_out_rather_than_blocked(qapp, wizard, tmp_path):
    target = tmp_path / f"cohort A{PROJECT_SUFFIX}"
    target.write_text("{}")
    page = wizard.page(PROJECT)
    page.name_edit.setText("cohort A")
    page.folder_edit.setText(str(tmp_path))
    assert page.isComplete()
    assert "overwritten" in page.preview.text()


# -- the samples page ----------------------------------------------------------- #
def batch_of(wizard, count=4):
    """Stand in for opening raw files, which needs the vendor libraries."""
    session = wizard.session
    session.entries = [
        SampleEntry(f"/d/s{i}.wiff", 0, f"S{i}") for i in range(count)]
    wizard.page(SAMPLES).initializePage()
    return session.entries


def test_the_page_lists_every_injection(qapp, wizard):
    batch_of(wizard, 3)
    assert wizard.page(SAMPLES).table.rowCount() == 3


def test_type_and_group_can_be_set_for_a_selection(qapp, wizard):
    entries = batch_of(wizard, 4)
    page = wizard.page(SAMPLES)
    page.table.selectRow(0)
    page.type_combo.setCurrentText(STANDARD)
    page.group_combo.setCurrentText("control")
    page._apply()
    assert entries[0].sample_type == STANDARD
    assert entries[0].sample_group == "control"
    assert entries[1].sample_type == UNKNOWN


def test_a_group_already_in_the_batch_is_offered_to_the_rest(qapp, wizard):
    entries = batch_of(wizard, 3)
    entries[0].sample_group = "treated"
    page = wizard.page(SAMPLES)
    page._refresh()
    combo = page.table.cellWidget(1, 3)
    assert "treated" in [combo.itemText(i) for i in range(combo.count())]


def test_removing_a_row_drops_the_injection(qapp, wizard):
    batch_of(wizard, 3)
    page = wizard.page(SAMPLES)
    page.table.selectRow(1)
    page._remove()
    assert [e.name for e in wizard.session.entries] == ["S0", "S2"]


def test_a_project_with_no_samples_is_allowed(qapp, wizard):
    assert wizard.page(SAMPLES).isComplete()


# -- the method page ------------------------------------------------------------ #
def test_importing_a_component_list(qapp, wizard, tmp_path, monkeypatch):
    csv = tmp_path / "method.csv"
    save_components(str(csv), [
        Component(name="IS", precursor=552.5, fragment=534.5,
                  is_internal_standard=True),
        Component(name="Cer", precursor=538.5, fragment=264.2686,
                  internal_standard="IS"),
    ])
    page = wizard.page(METHOD)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(csv), ""))
    page._browse()
    assert page.choice() == METHOD_IMPORT
    assert [c.name for c in page.components()] == ["IS", "Cer"]
    assert "2 component(s)" in page.import_label.text()
    assert "1 internal standard" in page.import_label.text()


def test_import_cannot_be_chosen_without_a_file(qapp, wizard):
    page = wizard.page(METHOD)
    page.radio_import.setChecked(True)
    assert not page.isComplete()


def test_an_empty_method_is_the_default(qapp, wizard):
    page = wizard.page(METHOD)
    assert page.choice() == METHOD_EMPTY
    assert page.components() == []
    assert page.isComplete()


def test_the_defaults_reach_the_method(qapp, wizard):
    from milq.method import ProcessingMethod
    page = wizard.page(METHOD)
    page.tol_spin.setValue(20.0)
    page.unit_combo.setCurrentText("ppm")
    page.conc_edit.setText("nmol/L")
    method = ProcessingMethod()
    page.apply_to(method)
    assert (method.tolerance, method.unit, method.concentration_unit) == (
        20.0, "ppm", "nmol/L")


def test_generating_from_the_acquisition_method_is_offered_only_with_samples(
        qapp, wizard):
    page = wizard.page(METHOD)
    page.initializePage()
    assert not page.radio_acquisition.isEnabled()
    assert "No sample is open" in page.acquisition_label.text()


# -- the summary ---------------------------------------------------------------- #
def test_the_summary_recaps_the_batch(qapp, wizard, tmp_path):
    entries = batch_of(wizard, 3)
    entries[0].sample_type = QC
    entries[0].sample_group = "control"
    wizard.page(PROJECT).name_edit.setText("cohort A")
    wizard.page(PROJECT).folder_edit.setText(str(tmp_path))
    page = wizard.page(SUMMARY)
    page.initializePage()
    assert "3 injection(s)" in page.summary.text()
    assert "control" in page.summary.text()
    assert "cohort A" in page.summary.text()


def test_an_empty_method_is_flagged_and_processing_is_not_offered(qapp, wizard,
                                                                  tmp_path):
    batch_of(wizard, 2)
    wizard.page(PROJECT).name_edit.setText("cohort A")
    wizard.page(PROJECT).folder_edit.setText(str(tmp_path))
    page = wizard.page(SUMMARY)
    page.initializePage()
    assert "method is empty" in page.warnings.text()
    assert not page.check_process.isEnabled()


def test_a_method_with_no_internal_standard_is_flagged(qapp, wizard, tmp_path,
                                                       monkeypatch):
    csv = tmp_path / "method.csv"
    save_components(str(csv), [Component(name="Cer", precursor=538.5,
                                         fragment=264.2686)])
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(csv), ""))
    wizard.page(METHOD)._browse()
    batch_of(wizard, 2)
    wizard.page(PROJECT).name_edit.setText("cohort A")
    wizard.page(PROJECT).folder_edit.setText(str(tmp_path))
    page = wizard.page(SUMMARY)
    page.initializePage()
    assert "internal standard" in page.warnings.text()


# -- cancelling ------------------------------------------------------------------ #
def test_cancelling_leaves_nothing_behind(qapp, wizard):
    batch_of(wizard, 3)
    wizard.reject()
    assert wizard.session.entries == []


# -- the start dialog ------------------------------------------------------------ #
def test_the_start_dialog_reports_the_choice(qapp):
    dialog = StartDialog()
    dialog._chose(StartDialog.NEW)
    assert dialog.choice == StartDialog.NEW
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_editing_a_row_does_not_stack_a_second_widget_on_it(qapp, wizard):
    """Replacing a cell widget only queues the old one for deletion."""
    batch_of(wizard, 3)
    page = wizard.page(SAMPLES)
    page.table.selectRow(0)
    page.type_combo.setCurrentText(STANDARD)
    page._apply()
    combos = page.table.viewport().findChildren(QtWidgets.QComboBox)
    assert len(combos) == page.table.rowCount() * 2
    assert page.table.cellWidget(0, 2).currentText() == STANDARD


def test_the_selftest_reports_without_opening_a_window(qapp, capsys):
    """
    A packaged application either reads a .wiff or it does not, and the build
    machine has no one to click. This is how CI finds out.
    """
    from milq.app import _selftest

    code = _selftest([])
    out = capsys.readouterr().out
    assert code == 0
    assert "MIL-Q" in out
    assert "LIPID MAPS index:" in out
    assert "SCIEX libraries:" in out
    # the index is an SQLite database, so a build without the sqlite3
    # extension cannot hold one at all — which is invisible until somebody
    # searches, on a machine nobody is watching. The line proves the reader
    # works whether or not an index is installed on this machine.
    assert "unreadable by this build" not in out


def test_a_file_it_cannot_read_is_a_failure_not_a_silence(qapp, tmp_path):
    """A build that packages the wrong assemblies must not exit zero."""
    from milq import app as app_module

    broken = tmp_path / "not-really.wiff"
    broken.write_text("nonsense")
    assert app_module._selftest([str(broken)]) == 1


# -- the start prompt must not hold the application hostage ------------------ #
def test_the_start_prompt_does_not_block_quitting(qapp):
    """
    It used to be shown with exec(), which runs an event loop of its own.
    While one is running the application cannot be quit by anything — not
    Cmd-Q, not the red button, not the Quit the system sends at logout. The
    only way out of a prompt offering to start some work was to answer it.
    """
    from milq.ui.shell import MainShell

    shell = MainShell()
    shell.settings.setValue("shell/skip_start", False)
    shell.show()
    shell.offer_start()
    qapp.processEvents()

    dialog = QtWidgets.QApplication.activeModalWidget()
    assert dialog is not None, "the prompt should be showing"
    assert dialog.windowModality() != QtCore.Qt.WindowModality.ApplicationModal

    assert shell.close(), "the window should close with the prompt still open"
    qapp.processEvents()
    assert not shell.isVisible()


def test_answering_the_start_prompt_still_does_what_it_says(qapp, monkeypatch):
    from milq.ui.shell import MainShell
    from milq.ui.new_project import StartDialog

    shell = MainShell()
    shell.settings.setValue("shell/skip_start", False)
    asked = []
    monkeypatch.setattr(MainShell, "new_project", lambda self: asked.append("new"))
    shell.offer_start()
    qapp.processEvents()

    dialog = QtWidgets.QApplication.activeModalWidget()
    dialog.choice = StartDialog.NEW
    dialog.accept()
    qapp.processEvents()

    assert asked == ["new"]
    shell.close()
