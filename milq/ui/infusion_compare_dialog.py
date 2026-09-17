"""Two days of infusions side by side: the totals, then every compound."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..infusion_compare import (MOVED_PERCENT, SAME_PEAK_PPM,
                                InfusionComparison, write_csv)
from .help_window import describe, open_manual

HELP_PAGE = "compare-infusions"


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
    item = _NumericItem("—" if value is None
                        else f"{value:,.{decimals}f}{suffix}")
    item.setData(QtCore.Qt.ItemDataRole.UserRole, value)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


def _text(value: str):
    item = QtWidgets.QTableWidgetItem(value)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    return item


class InfusionCompareDialog(QtWidgets.QDialog):
    """
    One row per infusion the two days share, and what each one has alone.

    `batches_dialog` for the other kind of batch, and deliberately the same
    window: the totals of each side, the rows underneath, the marked ones
    coloured, and the whole thing out as a CSV.
    """

    COLUMNS = ["Compound", "Conditions", "Score", "Reverse", "Matched",
               "Base m/z ref.", "Base m/z now", "Base Δ ppm",
               "Height ref.", "Height now", "Δ height %", "Ions ref.",
               "Ions now", "Δ precursor ppm", "Δ record score"]

    def __init__(self, comparison: InfusionComparison, parent=None):
        super().__init__(parent)
        self.comparison = comparison
        self.setWindowTitle(f"{comparison.reference} against "
                            f"{comparison.current}")
        self.resize(1240, 720)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel(comparison.summary())
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        ref, cur = comparison.totals()
        rows = [
            ("Infusions", ref["infusions"], cur["infusions"], 0),
            ("Compounds", ref["compounds"], cur["compounds"], 0),
            ("Precursors measured", ref["measured"], cur["measured"], 0),
            ("Median base-peak height", ref["median_height"],
             cur["median_height"], 0),
            ("Median peaks stored", ref["median_peaks"], cur["median_peaks"], 0),
            ("Median own-record score", ref["median_record"],
             cur["median_record"], 0),
        ]
        totals = QtWidgets.QTableWidget(len(rows), 3)
        totals.setHorizontalHeaderLabels(
            ["", comparison.reference, comparison.current])
        totals.verticalHeader().hide()
        totals.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for index, (label, a, b, decimals) in enumerate(rows):
            totals.setItem(index, 0, _text(label))
            totals.setItem(index, 1, _numeric(a, decimals))
            totals.setItem(index, 2, _numeric(b, decimals))
        totals.resizeColumnsToContents()
        totals.setMaximumHeight(totals.rowHeight(0) * len(rows)
                                + totals.horizontalHeader().height() + 4)
        layout.addWidget(totals)

        self.table = QtWidgets.QTableWidget(len(comparison.rows),
                                            len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        marked = QtGui.QColor(230, 150, 40, 60)
        for index, row in enumerate(comparison.rows):
            r, c = row.reference, row.current
            name = _text(row.compound)
            if row.moved:
                name.setToolTip(row.why)
            self.table.setItem(index, 0, name)
            self.table.setItem(index, 1, _text(row.conditions))
            cells = [
                _numeric(row.score * 100, 0), _numeric(row.reverse * 100, 0),
                _numeric(float(row.matched), 0),
                _numeric(r.base_mz, 4), _numeric(c.base_mz, 4),
                _numeric(row.base_gap_ppm), _numeric(r.base_height, 0),
                _numeric(c.base_height, 0), _numeric(row.intensity_change),
                _numeric(None if r.ions_found is None
                         else float(r.ions_found), 0),
                _numeric(None if c.ions_found is None
                         else float(c.ions_found), 0),
                _numeric(row.precursor_ppm_change),
                _numeric(row.record_score_change),
            ]
            # the cell of the rule that fired, and not every cell of a marked
            # row: a row coloured on the mass and a row coloured on the height
            # are two different findings, and the colour is where that shows
            change = row.intensity_change
            out = {7: not row.same_base_peak,
                   10: change is not None and abs(change) > MOVED_PERCENT}
            for column, item in enumerate(cells, start=2):
                if out.get(column):
                    item.setBackground(marked)
                    item.setToolTip(row.why)
                self.table.setItem(index, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        alone = []
        if comparison.only_reference:
            alone.append("only in the reference: "
                         + ", ".join(s.label
                                     for s in comparison.only_reference))
        if comparison.only_current:
            alone.append("only in this day: "
                         + ", ".join(s.label for s in comparison.only_current))
        if alone:
            odd = QtWidgets.QLabel("; ".join(alone) + ".")
            odd.setWordWrap(True)
            odd.setProperty("role", "hint")
            layout.addWidget(odd)

        note = QtWidgets.QLabel(
            f"Rows are matched by compound and by conditions: a spray at one "
            f"collision energy and activation is compared only with the "
            f"reference's at the same ones. The score is the cosine of this "
            f"day's peaks against the reference's stored peaks; the reverse "
            f"asks only whether the reference's peaks are still there. A row "
            f"is marked where the base peak is more than {SAME_PEAK_PPM:g} "
            f"ppm from the reference's — a different ion, not a mass error — "
            f"or where its height is more than {MOVED_PERCENT:g}% from it. "
            f"The score itself is not a rule: two days are two points, which "
            f"is not a spread.")
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

    def export(self, path: str = "") -> str:
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export the comparison",
                f"{self.comparison.reference}-vs-{self.comparison.current}.csv",
                "CSV (*.csv)")
            if not path:
                return ""
        if not path.lower().endswith(".csv"):
            path += ".csv"
        self.saved_path = write_csv(self.comparison, path)
        return self.saved_path
