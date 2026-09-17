"""
The check of what is about to be opened, for somebody to read first.

`folder.check_files` finds; this shows, and offers the one repair that can
be made from outside the files — renaming a stray `.scan` to the companion
a `.wiff` is missing. The rename is a guess from the names and is named as
one, so it is confirmed with both names in front of the reader and never
carried out on a file that is already there.

Nothing here opens anything. *Open anyway* accepts the dialog and hands
the shell the files the check would open; *Cancel* opens none of them.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from ..folder import (ABSENT, MISSING_SCAN, UNREADABLE, FolderReport,
                      apply_rename, check_files)
from .help_window import describe, open_manual

HELP_PAGE = "checking-files"

#: the kinds that stop the data being read at all, marked in the table
SERIOUS = {MISSING_SCAN, UNREADABLE, ABSENT}

#: what marks one. The mark, not a colour: the application's stylesheet
#: paints every cell's background itself, so a brush set on an item is not
#: drawn — and this is the mark the samples tree already carries for a
#: sample whose spectra cannot be read
MARK = "⚠"


class FolderDialog(QtWidgets.QDialog):
    """The findings, a rename for the ones that have one, and Open anyway."""

    COLUMNS = ["File", "Finding", "Suggested action"]

    def __init__(self, report: FolderReport, parent=None,
                 open_paths=()):
        super().__init__(parent)
        self.report = report
        self.open_paths = list(open_paths)
        #: every rename carried out here, oldest first
        self.renamed: list[str] = []
        self.setWindowTitle("Check the files")
        self.resize(1000, 520)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QtWidgets.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        # the finding and the action are sentences; elided to one line they
        # are unreadable, and the point of the table is that they are read
        self.table.setWordWrap(True)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table, 1)

        note = QtWidgets.QLabel(
            "Nothing has been opened yet, and nothing here is changed on its "
            "own: a rename is carried out only when it is asked for and "
            "confirmed, and it never writes over a file that is already "
            "there. The pairing of a stray .scan with a .wiff is a guess "
            "from the two names — nothing outside the files can settle it.")
        note.setWordWrap(True)
        note.setProperty("role", "hint")
        layout.addWidget(note)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Open
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Open).setText("Open anyway")
        self.btn_rename = self.buttons.addButton(
            "Rename…", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_rename.setToolTip(
            "Rename the stray .scan to the companion the .wiff is missing")
        self.btn_rename.clicked.connect(lambda: self.rename_selected())
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        layout.addWidget(self.buttons)

        self._fill()

    # -- the table ---------------------------------------------------------- #
    def _fill(self) -> None:
        report = self.report
        self.summary.setText(report.summary())
        self.table.setRowCount(len(report.findings))
        for row, finding in enumerate(report.findings):
            marked = (f"{MARK} {finding.name}" if finding.kind in SERIOUS
                      else finding.name)
            for column, text in enumerate([marked, finding.finding,
                                           finding.action]):
                item = QtWidgets.QTableWidgetItem(text)
                item.setToolTip(finding.path if column == 0 else text)
                self.table.setItem(row, column, item)
        self.table.resizeColumnToContents(0)
        self.table.resizeRowsToContents()
        if report.findings:
            renameable = [row for row, f in enumerate(report.findings)
                          if f.renameable]
            # the repair first, when there is one to make
            self.table.selectRow(renameable[0] if renameable else 0)
        self._selection_changed()

    def _selection_changed(self) -> None:
        finding = self.selected_finding()
        self.btn_rename.setEnabled(finding is not None and finding.renameable)

    def selected_finding(self):
        rows = {index.row() for index in self.table.selectedIndexes()}
        if len(rows) != 1:
            return None
        row = rows.pop()
        if 0 <= row < len(self.report.findings):
            return self.report.findings[row]
        return None

    # -- the one repair ------------------------------------------------------ #
    def rename_selected(self, confirm: bool = True) -> str:
        """
        Rename the selected stray to the name the guess proposes.

        Returns the new path, or "" if nothing was renamed. `confirm=False`
        skips the question, which is what a test wants and what a person
        never gets: the names are close enough to each other that seeing
        both of them written out is the whole safeguard.
        """
        finding = self.selected_finding()
        if finding is None or not finding.renameable:
            return ""
        old = os.path.basename(finding.rename_from)
        new = os.path.basename(finding.rename_to)
        if confirm:
            answer = QtWidgets.QMessageBox.question(
                self, "Rename this file?",
                f"Rename\n\n    {old}\n\nto\n\n    {new}\n\nin "
                f"{os.path.dirname(finding.rename_from)}?\n\n"
                f"The pairing is a guess from the two names. The file is "
                f"renamed on disk; nothing is copied and nothing is "
                f"overwritten.",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return ""
        try:
            written = apply_rename(finding)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Nothing was renamed", str(exc))
            return ""
        self.renamed.append(written)
        self.recheck()
        return written

    def recheck(self) -> FolderReport:
        """Run the check again over the same paths and rebuild the table."""
        self.report = check_files(self.report.requested, self.open_paths)
        self._fill()
        return self.report

    # -- what the shell asks for --------------------------------------------- #
    def paths(self) -> list[str]:
        """The files to open — after any rename, since the check was rerun."""
        return list(self.report.paths)
