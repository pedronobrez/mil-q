"""
The audit trail, read-only.

What was changed by hand in this project, in the order it was changed:
a manual integration, a row excluded, a standard dropped from a curve, a
component or a sample edited, a reprocessing, a save. The panel shows the
trail and nothing else — there is no way in here to add, edit or delete an
entry, because a record somebody can rewrite is not a record.

Sortable by any column: the timestamps are ISO, so sorting the *When*
column as text sorts it as time. The filter box narrows to the rows holding
what is typed, anywhere in them, which is how one component's history is
picked out of a batch's.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtGui, QtWidgets

from ..audit import COLUMNS, write_csv
from ..session import Session
from .settings import settings
from .flow_layout import FlowLayout

#: the column the trail opens sorted on, and which way
SORT_COLUMN = 0
SORT_ORDER = QtCore.Qt.SortOrder.AscendingOrder


class AuditPanel(QtWidgets.QWidget):
    """The trail as a table, with a filter and an export."""

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter changes…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setToolTip(
            "Show the rows holding this, anywhere in them — a component, a "
            "sample, a kind of change")
        bar.addWidget(self.filter_edit, 1)
        self.btn_export = QtWidgets.QPushButton("Export CSV…")
        self.btn_export.setToolTip(
            "The whole trail, in the order it was made, as a CSV")
        bar.addWidget(self.btn_export)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        # read-only in the strongest sense Qt offers: no editing, and no
        # selection of a cell to type into
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        # stated rather than left to Qt: enabling sorting picks up whatever
        # indicator the header happens to hold, and the trail opens oldest
        # first because that is the order it happened in
        self.table.horizontalHeader().setSortIndicator(SORT_COLUMN, SORT_ORDER)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.filter_edit.textChanged.connect(self._apply_filter)
        self.btn_export.clicked.connect(self.export_csv)
        session.sigAuditChanged.connect(self.reload)

        from .help_window import describe
        describe(self, "audit-trail")
        self.reload()

    # -- the table ----------------------------------------------------------- #
    def reload(self) -> None:
        """Rebuild from the session's trail, keeping the sort that is on."""
        order = self.table.horizontalHeader().sortIndicatorOrder()
        column = self.table.horizontalHeader().sortIndicatorSection()
        # sorting is switched off while the rows are written: with it on, a
        # row moves as soon as its first cell is set and the rest of the
        # cells are then written into whatever row took its place
        self.table.setSortingEnabled(False)
        rows = self.session.audit.rows()
        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for index, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if text:
                    item.setToolTip(text)
                self.table.setItem(row, index, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(column, order)
        self.table.resizeColumnsToContents()
        self._apply_filter(self.filter_edit.text())

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        shown = 0
        for row in range(self.table.rowCount()):
            hit = not needle or any(
                needle in (self.table.item(row, column).text().lower()
                           if self.table.item(row, column) else "")
                for column in range(self.table.columnCount()))
            self.table.setRowHidden(row, not hit)
            shown += bool(hit)
        self._describe(shown)

    def _describe(self, shown: int) -> None:
        total = len(self.session.audit)
        if not total:
            self.status.setText(
                "Nothing has been changed by hand in this project yet. "
                "Integrations, exclusions, method and sample edits are "
                "recorded here as they are made.")
            return
        text = f"{total:,} change(s) recorded"
        if shown != total:
            text += f", {shown:,} shown"
        self.status.setText(
            text + " — a record of what was done, not an electronic "
                   "signature: see the manual.")

    # -- the export ---------------------------------------------------------- #
    def export_csv(self, path: str = "") -> str:
        """
        Write the trail out. Returns the path written, or an empty string.

        The whole trail, not the filtered view: a trail with rows left out is
        not the thing it claims to be, and the filter is a way of reading it
        rather than a way of choosing what happened.
        """
        if not len(self.session.audit):
            self._report("There is nothing to export yet.")
            return ""
        if not path:
            store = settings()
            stem = (os.path.splitext(
                os.path.basename(self.session.project_path))[0]
                if self.session.project_path else "batch")
            start = os.path.join(store.value("io/last_dir", "", type=str),
                                 f"{stem}-audit.csv")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export the audit trail", start, "CSV (*.csv)")
            if not path:
                return ""
            store.setValue("io/last_dir", os.path.dirname(path))
        written = write_csv(self.session.audit, path)
        self._report(f"{len(self.session.audit):,} change(s) written to "
                     f"{written}")
        return written

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)


class AuditDialog(QtWidgets.QDialog):
    """The same panel in a window of its own, for the shell's menu."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audit trail — changes made by hand")
        self.resize(1000, 560)
        layout = QtWidgets.QVBoxLayout(self)
        self.panel = AuditPanel(session, self)
        layout.addWidget(self.panel, 1)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(self._help)
        layout.addWidget(self.buttons)

        from .help_window import describe
        describe(self, "audit-trail")

    def _help(self) -> None:
        from .help_window import open_manual
        open_manual(self, "audit-trail")

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # F1 in a dialog reaches the shell's application-wide filter, but a
        # dialog opened without one has to answer for itself
        if event.matches(QtGui.QKeySequence.StandardKey.HelpContents):
            self._help()
            return
        super().keyPressEvent(event)
