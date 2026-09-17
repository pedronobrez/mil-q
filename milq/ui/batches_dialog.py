"""Two batches side by side: the totals, then every component."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..batches import MOVED_PERCENT, BatchComparison, write_csv
from .help_window import describe, open_manual

HELP_PAGE = "compare-batches"


class _NumericItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other):
        mine = self.data(QtCore.Qt.ItemDataRole.UserRole)
        theirs = other.data(QtCore.Qt.ItemDataRole.UserRole)
        if mine is None:
            return theirs is not None
        if theirs is None:
            return False
        return mine < theirs


def _numeric(value, decimals=1, suffix=""):
    item = _NumericItem("—" if value is None else f"{value:,.{decimals}f}{suffix}")
    item.setData(QtCore.Qt.ItemDataRole.UserRole, value)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


class BatchesDialog(QtWidgets.QDialog):
    COLUMNS = ["Component", "Found ref.", "Found now", "Points ref.", "Points now",
               "%CV ref.", "%CV now", "Area ref.", "Area now", "Δ area %",
               "RT ref.", "RT now", "ΔRT"]

    def __init__(self, comparison: BatchComparison, parent=None):
        super().__init__(parent)
        self.comparison = comparison
        self.setWindowTitle(f"{comparison.reference} against {comparison.current}")
        self.resize(1200, 720)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel(comparison.summary())
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        ref, cur = comparison.totals()
        totals = QtWidgets.QTableWidget(5, 3)
        totals.setHorizontalHeaderLabels(["", comparison.reference, comparison.current])
        totals.verticalHeader().hide()
        totals.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        rows = [
            ("Injections", comparison.reference_injections, comparison.current_injections, 0),
            ("Rows found", ref["found"], cur["found"], 0),
            ("Components with a peak", ref["components_found"], cur["components_found"], 0),
            ("Median points on the peak", ref["median_points"], cur["median_points"], 0),
            ("Median %CV of the replicates", ref["median_precision"], cur["median_precision"], 1),
        ]
        for index, (label, a, b, decimals) in enumerate(rows):
            totals.setItem(index, 0, QtWidgets.QTableWidgetItem(label))
            totals.setItem(index, 1, _numeric(a, decimals))
            totals.setItem(index, 2, _numeric(b, decimals))
        totals.resizeColumnsToContents()
        totals.setMaximumHeight(totals.rowHeight(0) * 5 + totals.horizontalHeader().height() + 4)
        layout.addWidget(totals)

        self.table = QtWidgets.QTableWidget(len(comparison.rows), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        marked = QtGui.QColor(230, 150, 40, 60)
        for index, row in enumerate(comparison.rows):
            r, c = row.reference, row.current
            name = QtWidgets.QTableWidgetItem(
                row.component + (" (IS)" if row.is_internal_standard else ""))
            self.table.setItem(index, 0, name)
            cells = [_numeric(r.found, 0), _numeric(c.found, 0),
                     _numeric(r.median_points, 0), _numeric(c.median_points, 0),
                     _numeric(r.precision), _numeric(c.precision),
                     _numeric(r.median_area, 0), _numeric(c.median_area, 0),
                     _numeric(row.area_change), _numeric(r.median_rt, 2),
                     _numeric(c.median_rt, 2), _numeric(row.rt_shift, 3)]
            for column, item in enumerate(cells, start=1):
                if column == 9 and row.moved:
                    item.setBackground(marked)
                self.table.setItem(index, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        note = QtWidgets.QLabel(
            f"Points are the points on the peak at or above one per cent of "
            f"its height; %CV is over the rows meant to agree — every spiked "
            f"injection for a standard, the quality controls for an analyte. "
            f"A component whose median area moved by more than "
            f"{MOVED_PERCENT:.0f}% is marked.")
        note.setWordWrap(True)
        note.setProperty("role", "hint")
        layout.addWidget(note)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Close
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setText(
            "Export CSV…")
        buttons.rejected.connect(self.reject)
        buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save
                       ).clicked.connect(self.export)
        layout.addWidget(buttons)
        self.saved_path = ""

    def export(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export the comparison",
            f"{self.comparison.reference}-vs-{self.comparison.current}.csv",
            "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        self.saved_path = write_csv(self.comparison, path)
