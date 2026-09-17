"""
The files are looked over before they are opened.

Everything here is names on disk — no reader is involved and none of the
files hold data — because that is exactly what the check is: what can be
known about a folder without decoding anything in it. The folder built by
`acquisitions` is the shape the real one has: `name.wiff`, `name.wiff.scan`
and `name.wiff2` per acquisition, and one companion renamed by hand.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.folder import (ABSENT, DUPLICATE, IGNORED,  # noqa: E402
                              MISSING_SCAN, STRAY_SCAN, UNREADABLE,
                              UNSUPPORTED, apply_rename, check_files,
                              guess_owner)


def write(folder, *names) -> None:
    for name in names:
        (folder / name).write_text("not data")


@pytest.fixture
def acquisitions(tmp_path):
    """Two good acquisitions and one whose companion was renamed by hand."""
    write(tmp_path,
          "Bile_01.wiff", "Bile_01.wiff.scan", "Bile_01.wiff2",
          "Bile_02.wiff", "Bile_02.wiff.scan", "Bile_02.wiff2",
          "Bile_mix1.wiff", "Bile.wiff_mix1.scan", "Bile_mix1.wiff2")
    return tmp_path


# --------------------------------------------------------------------------- #
# what a folder gives
# --------------------------------------------------------------------------- #
def test_a_folder_offers_its_supported_files_and_nothing_else(acquisitions):
    write(acquisitions, "sample.mzML", "readme.txt")
    report = check_files([acquisitions])
    assert [os.path.basename(p) for p in report.paths] == [
        "Bile_01.wiff", "Bile_02.wiff", "Bile_mix1.wiff", "sample.mzML"]
    assert report.folders == [str(acquisitions)]
    assert report.summary().startswith("4 files to open;")


def test_a_folder_is_not_walked_into(tmp_path):
    """An acquisition folder is flat; a tree below it is somebody else's."""
    write(tmp_path, "top.wiff", "top.wiff.scan")
    (tmp_path / "below").mkdir()
    write(tmp_path / "below", "deep.wiff", "deep.wiff.scan")
    report = check_files([tmp_path])
    assert [os.path.basename(p) for p in report.paths] == ["top.wiff"]


def test_a_clean_folder_reports_nothing(tmp_path):
    write(tmp_path, "a.wiff", "a.wiff.scan", "b.mzML")
    report = check_files([tmp_path])
    assert report.findings == []
    assert not report
    assert report.summary() == "2 files to open; nothing to report."


# --------------------------------------------------------------------------- #
# the .wiff without its .wiff.scan, and the stray that may be it
# --------------------------------------------------------------------------- #
def test_a_wiff_without_its_companion_is_named_with_what_it_costs(tmp_path):
    write(tmp_path, "lonely.wiff")
    finding, = check_files([tmp_path]).of_kind(MISSING_SCAN)
    assert "lonely.wiff has no lonely.wiff.scan beside it" in finding.finding
    assert "quantitation" in finding.finding
    assert "copy lonely.wiff.scan in" in finding.action
    assert not finding.renameable
    # it is still opened: the chromatograms and the method are in the .wiff
    assert check_files([tmp_path]).paths == [str(tmp_path / "lonely.wiff")]


def test_the_stray_is_paired_with_the_wiff_it_most_resembles(acquisitions):
    report = check_files([acquisitions])
    missing, = report.of_kind(MISSING_SCAN)
    stray, = report.of_kind(STRAY_SCAN)
    assert missing.name == "Bile_mix1.wiff"
    assert "Bile.wiff_mix1.scan" in missing.action
    assert stray.name == "Bile.wiff_mix1.scan"
    assert stray.renameable
    assert os.path.basename(stray.rename_to) == "Bile_mix1.wiff.scan"
    assert "a guess" in stray.action
    # the finding for the .wiff comes first: the problem, then the repair
    assert report.findings.index(missing) < report.findings.index(stray)


def test_the_pairing_prefers_the_wiff_that_needs_one(tmp_path):
    """A .wiff already holding its companion is not a candidate."""
    write(tmp_path, "run_a.wiff", "run_a.wiff.scan", "run_b.wiff",
          "run.wiff_b.scan")
    stray, = check_files([tmp_path]).of_kind(STRAY_SCAN)
    assert os.path.basename(stray.rename_to) == "run_b.wiff.scan"


def test_a_stray_that_resembles_nothing_is_reported_without_a_guess(tmp_path):
    write(tmp_path, "2024_bile.wiff", "orphan.scan")
    report = check_files([tmp_path])
    stray, = report.of_kind(STRAY_SCAN)
    assert not stray.renameable
    assert "belongs to no .wiff in this folder" in stray.finding
    assert "elsewhere" in stray.action


def test_guess_owner_takes_the_longest_shared_run_of_characters(tmp_path):
    candidates = [str(tmp_path / n) for n in ("alpha_x.wiff", "beta_y.wiff")]
    assert guess_owner(str(tmp_path / "alpha.wiff_x.scan"),
                       candidates).endswith("alpha_x.wiff")
    assert guess_owner(str(tmp_path / "beta.wiff_y.scan"),
                       candidates).endswith("beta_y.wiff")
    assert guess_owner(str(tmp_path / "zzz.scan"), candidates) == ""
    assert guess_owner(str(tmp_path / "anything.scan"), []) == ""


def test_a_stray_is_only_raised_for_a_folder_that_was_asked_about(acquisitions):
    """Picking two whole acquisitions by hand says what is wanted."""
    report = check_files([acquisitions / "Bile_01.wiff",
                          acquisitions / "Bile_02.wiff"])
    assert report.findings == []
    # name the broken one and the stray beside it is worth saying
    report = check_files([acquisitions / "Bile_mix1.wiff"])
    assert [f.kind for f in report.findings] == [MISSING_SCAN, STRAY_SCAN]


# --------------------------------------------------------------------------- #
# the rename
# --------------------------------------------------------------------------- #
def test_the_rename_repairs_the_pair(acquisitions):
    stray, = check_files([acquisitions]).of_kind(STRAY_SCAN)
    written = apply_rename(stray)
    assert os.path.basename(written) == "Bile_mix1.wiff.scan"
    assert not (acquisitions / "Bile.wiff_mix1.scan").exists()
    assert check_files([acquisitions]).findings == [
        f for f in check_files([acquisitions]).findings if f.kind == IGNORED]


def test_the_rename_never_writes_over_a_file_that_is_there(acquisitions):
    stray, = check_files([acquisitions]).of_kind(STRAY_SCAN)
    write(acquisitions, "Bile_mix1.wiff.scan")
    with pytest.raises(FileExistsError):
        apply_rename(stray)
    assert (acquisitions / "Bile.wiff_mix1.scan").exists()
    assert (acquisitions / "Bile_mix1.wiff.scan").read_text() == "not data"


def test_a_finding_with_no_rename_refuses_to_be_renamed(tmp_path):
    write(tmp_path, "lonely.wiff")
    finding, = check_files([tmp_path]).of_kind(MISSING_SCAN)
    with pytest.raises(ValueError):
        apply_rename(finding)


# --------------------------------------------------------------------------- #
# the formats that are passed over
# --------------------------------------------------------------------------- #
def test_wiff2_beside_its_wiff_costs_nothing_and_says_so(acquisitions):
    ignored = check_files([acquisitions]).of_kind(IGNORED)
    assert len(ignored) == 1
    assert "3 .wiff2 files" in ignored[0].finding
    assert "nothing is lost" in ignored[0].action


def test_the_wiff2_finding_says_what_the_container_holds(acquisitions):
    """
    "a different container" was true and unhelpful: it invited the reading
    that a reader is simply missing. What was measured is stronger — the
    format's own declared schema has seven tables and not one column for a
    spectrum, a peak or a chromatogram, and its header table holds the
    hashes of the `.wiff` and `.wiff.scan` beside it. The finding says that,
    so "nothing is lost" is backed by something.
    """
    ignored, = check_files([acquisitions]).of_kind(IGNORED)
    assert "no scan data" in ignored.finding
    assert "method" in ignored.finding


def test_a_wiff2_on_its_own_is_an_acquisition_that_will_not_open(tmp_path):
    write(tmp_path, "only.wiff2", "fine.wiff", "fine.wiff.scan")
    ignored, = check_files([tmp_path]).of_kind(IGNORED)
    assert "only.wiff2" in ignored.finding
    assert "no .wiff of the same name" in ignored.finding
    assert "fetch their .wiff" in ignored.action
    # and it must not suggest the .wiff2 could be opened instead: it holds
    # no spectra, so there is no reader that could be written for it
    assert "cannot stand in" in ignored.action


def test_a_named_wiff2_is_refused_rather_than_passed_to_the_wiff_reader(tmp_path):
    """`.wiff2` starts with `.wiff`; naming one outright must still refuse."""
    write(tmp_path, "only.wiff2")
    unsupported, = check_files([tmp_path / "only.wiff2"]).of_kind(UNSUPPORTED)
    assert "only.wiff2" in unsupported.finding
    assert "does not read" in unsupported.finding
    assert check_files([tmp_path / "only.wiff2"]).paths == []


def test_another_vendors_files_are_grouped_by_extension(tmp_path):
    write(tmp_path, "a.wiff", "a.wiff.scan", "x.raw", "y.raw", "z.raw", "w.raw",
          "t.tdf")
    findings = check_files([tmp_path]).of_kind(IGNORED)
    assert len(findings) == 2
    raws = next(f for f in findings if ".raw" in f.finding)
    assert "4 .raw files" in raws.finding and "and 1 more" in raws.finding
    assert "Thermo" in raws.finding
    assert "msconvert" in raws.action


def test_a_file_named_outright_that_nothing_reads_says_what_is_read(tmp_path):
    write(tmp_path, "spectra.raw")
    finding, = check_files([tmp_path / "spectra.raw"]).of_kind(UNSUPPORTED)
    assert "Thermo" in finding.finding
    assert ".mzml" in finding.action and ".wiff" in finding.action
    assert check_files([tmp_path / "spectra.raw"]).paths == []


# --------------------------------------------------------------------------- #
# duplicates, absences and permissions
# --------------------------------------------------------------------------- #
def test_a_file_already_open_is_not_added_again(tmp_path):
    write(tmp_path, "a.wiff", "a.wiff.scan")
    report = check_files([tmp_path / "a.wiff"], [str(tmp_path / "a.wiff")])
    assert report.paths == []
    assert report.of_kind(DUPLICATE)[0].finding.endswith("is open already")


def test_a_file_given_twice_is_opened_once(tmp_path):
    write(tmp_path, "a.wiff", "a.wiff.scan")
    report = check_files([tmp_path / "a.wiff", tmp_path, tmp_path / "a.wiff"])
    assert report.paths == [str(tmp_path / "a.wiff")]
    assert len(report.of_kind(DUPLICATE)) == 2


def test_a_path_that_is_not_there_says_so(tmp_path):
    report = check_files([tmp_path / "gone.wiff"])
    assert report.of_kind(ABSENT)[0].finding == "gone.wiff is not there"
    assert report.paths == []


@pytest.mark.skipif(os.getuid() == 0 if hasattr(os, "getuid") else True,
                    reason="root reads everything; Windows has no chmod")
def test_a_file_that_cannot_be_read_is_left_out(tmp_path):
    write(tmp_path, "closed.wiff", "closed.wiff.scan")
    os.chmod(tmp_path / "closed.wiff", 0o000)
    try:
        report = check_files([tmp_path / "closed.wiff"])
        assert report.paths == []
        assert report.of_kind(UNREADABLE)[0].name == "closed.wiff"
    finally:
        os.chmod(tmp_path / "closed.wiff", 0o600)


@pytest.mark.skipif(os.getuid() == 0 if hasattr(os, "getuid") else True,
                    reason="root reads everything; Windows has no chmod")
def test_a_companion_that_cannot_be_read_is_a_finding_of_its_own(tmp_path):
    write(tmp_path, "a.wiff", "a.wiff.scan")
    os.chmod(tmp_path / "a.wiff.scan", 0o000)
    try:
        report = check_files([tmp_path / "a.wiff"])
        assert report.paths == [str(tmp_path / "a.wiff")]
        assert report.of_kind(UNREADABLE)[0].name == "a.wiff.scan"
    finally:
        os.chmod(tmp_path / "a.wiff.scan", 0o600)


@pytest.mark.skipif(os.getuid() == 0 if hasattr(os, "getuid") else True,
                    reason="root reads everything; Windows has no chmod")
def test_a_folder_that_cannot_be_listed_is_a_finding(tmp_path):
    closed = tmp_path / "closed"
    closed.mkdir()
    os.chmod(closed, 0o000)
    try:
        report = check_files([closed])
        assert report.of_kind(UNREADABLE)[0].name == "closed"
        assert report.paths == []
    finally:
        os.chmod(closed, 0o700)


# --------------------------------------------------------------------------- #
# the dialog, offscreen, without exec
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_dialog_shows_every_finding_with_its_action(qapp, acquisitions):
    from milq.ui.folder_dialog import MARK, FolderDialog

    report = check_files([acquisitions])
    dialog = FolderDialog(report)
    assert dialog.table.rowCount() == len(report.findings)
    # the .wiff missing its companion is marked as the samples tree marks it
    assert dialog.table.item(0, 0).text() == f"{MARK} Bile_mix1.wiff"
    assert dialog.table.item(0, 2).text() == report.findings[0].action
    ignored = report.findings.index(report.of_kind(IGNORED)[0])
    assert not dialog.table.item(ignored, 0).text().startswith(MARK)
    assert dialog.summary.text() == report.summary()
    assert sorted(os.path.basename(p) for p in dialog.paths()) == [
        "Bile_01.wiff", "Bile_02.wiff", "Bile_mix1.wiff"]
    dialog.close()


def test_the_dialog_renames_the_selected_stray_and_checks_again(qapp,
                                                                acquisitions):
    from milq.ui.folder_dialog import FolderDialog

    report = check_files([acquisitions])
    dialog = FolderDialog(report)
    row = report.findings.index(report.of_kind(STRAY_SCAN)[0])
    dialog.table.selectRow(row)
    assert dialog.btn_rename.isEnabled()
    written = dialog.rename_selected(confirm=False)
    assert os.path.basename(written) == "Bile_mix1.wiff.scan"
    assert dialog.renamed == [written]
    # the check ran again: the missing companion and the stray are both gone
    assert dialog.report.of_kind(MISSING_SCAN) == []
    assert dialog.report.of_kind(STRAY_SCAN) == []
    assert dialog.table.rowCount() == len(dialog.report.findings)
    dialog.close()


def test_the_dialog_will_not_rename_over_a_file_that_is_there(qapp,
                                                              acquisitions,
                                                              monkeypatch):
    from PyQt6 import QtWidgets

    from milq.ui.folder_dialog import FolderDialog

    report = check_files([acquisitions])
    dialog = FolderDialog(report)
    dialog.table.selectRow(report.findings.index(report.of_kind(STRAY_SCAN)[0]))
    write(acquisitions, "Bile_mix1.wiff.scan")
    warned = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning",
                        lambda *args, **kwargs: warned.append(args[2]))
    assert dialog.rename_selected(confirm=False) == ""
    assert warned and "already there" in warned[0]
    assert (acquisitions / "Bile.wiff_mix1.scan").exists()
    dialog.close()


def test_a_row_with_no_rename_leaves_the_button_disabled(qapp, acquisitions):
    from milq.ui.folder_dialog import FolderDialog

    report = check_files([acquisitions])
    dialog = FolderDialog(report)
    dialog.table.selectRow(report.findings.index(report.of_kind(IGNORED)[0]))
    assert not dialog.btn_rename.isEnabled()
    assert dialog.rename_selected(confirm=False) == ""
    dialog.close()


def test_the_dialog_names_its_manual_page_and_offers_help(qapp, acquisitions):
    from PyQt6 import QtWidgets

    from milq.manual import manual
    from milq.ui.folder_dialog import HELP_PAGE, FolderDialog
    from milq.ui.help_window import help_page_for

    dialog = FolderDialog(check_files([acquisitions]))
    assert help_page_for(dialog) == HELP_PAGE
    assert HELP_PAGE in manual().pages
    assert dialog.buttons.button(
        QtWidgets.QDialogButtonBox.StandardButton.Help) is not None
    dialog.close()


# --------------------------------------------------------------------------- #
# the shell
# --------------------------------------------------------------------------- #
def test_the_shell_opens_a_clean_folder_without_a_dialog(qapp, tmp_path,
                                                         monkeypatch):
    from milq.ui.shell import MainShell

    write(tmp_path, "a.mzML", "b.mzML")
    shell = MainShell()
    monkeypatch.setattr(shell, "load_file", lambda path: opened.append(path))
    opened: list[str] = []
    shell.open_files([str(tmp_path)])
    assert [os.path.basename(p) for p in opened] == ["a.mzML", "b.mzML"]
    assert shell.settings.value("io/last_dir") == str(tmp_path)
    shell.close()


def test_the_shell_has_a_menu_entry_for_the_check(qapp):
    from milq.ui.shell import MainShell

    shell = MainShell()
    assert shell.act_check_folder.text() == "Check a folder…"
    shell.close()
