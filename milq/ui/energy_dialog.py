"""
Which collision energy and activation explains a standard best.

The table `energy.recommend` builds, one row per condition, and the three
recommendations under it with the figures each stands on. Nothing is
measured here: every number comes off the summary the Infusions tab has
already taken, which is why this opens at once and why it says *measure
first* rather than measuring on its own.
"""

from __future__ import annotations

import html
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from ..energy import COLUMNS, EnergyRecommendation, recommend, summary_line
from ..energy import write_csv
from . import theme
from .help_window import describe, open_manual

HELP_PAGE = "collision-energy"

#: the columns that hold a number and are read right-aligned, by name
_RIGHT = {"CE (eV)", "Infusions", "Explained", "Precursor m/z",
          "Precursor height", "Precursor % of base", "Base peak m/z",
          "Base peak share", "Record score", "Against other energies"}

#: how wide a column may grow, in pixels. A cell that could not be filled
#: says why instead of being blank, and one of those reasons is a sentence —
#: `CA-d4 carries no adduct and 839.56 is none of the adducts of…`. The cell
#: keeps the whole sentence, and so does the CSV; only the column stops
#: growing, with the text in the tooltip where the width cut it off.
MAX_COLUMN = 320


class EnergyDialog(QtWidgets.QDialog):
    """Every compound's conditions, and the three picks per compound."""

    def __init__(self, summary, parent=None):
        super().__init__(parent)
        self.recommendations: list[EnergyRecommendation] = recommend(summary)
        self.saved_path = ""
        self.setWindowTitle("Recommend collision energies")
        self.resize(1100, 720)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Every infusion of a compound, grouped by activation and "
            "collision energy. The three recommendations are three different "
            "questions and they do not have to agree: identification wants "
            "the most predicted ions with the precursor still standing, "
            "quantitation wants one fragment holding as much of the spectrum "
            "as it can, and a library record wants the middle of the energies "
            "measured. Nothing between two measured energies is offered — an "
            "energy nobody acquired is not a measurement.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.status = QtWidgets.QLabel(summary_line(self.recommendations))
        self.status.setWordWrap(True)
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip(
            "One row per compound, activation and collision energy. A row "
            "the isolation verdict contradicts is shown and never "
            "recommended — the Considered cell says which and why")
        split.addWidget(self.table)

        self.advice = QtWidgets.QTextBrowser()
        self.advice.setOpenExternalLinks(False)
        split.addWidget(self.advice)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        layout.addWidget(split, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Close
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save).setText(
                "Export CSV…")
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save
                            ).clicked.connect(self.export_csv)
        layout.addWidget(self.buttons)

        self._fill()

    # -- content -------------------------------------------------------------- #
    def _fill(self) -> None:
        rows = [(recommendation, cells)
                for recommendation in self.recommendations
                for cells in recommendation.rows()]
        self.table.setRowCount(len(rows))
        # the theme's own muted ink rather than the palette's disabled role,
        # which the application's stylesheet leaves equal to the ordinary
        # text colour — a grey that is not grey marks nothing
        muted = QtGui.QColor(theme.muted())
        for index, (_recommendation, cells) in enumerate(rows):
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if COLUMNS[column] in _RIGHT:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                considered = cells[COLUMNS.index("Considered")]
                item.setToolTip(text if len(text) > 24 else considered)
                if considered.startswith("no"):
                    # the Considered cell is nineteen columns to the right
                    # and a reader should not have to scroll to it to see
                    # that a row is out of the choice
                    item.setForeground(muted)
                self.table.setItem(index, column, item)
        self.table.resizeColumnsToContents()
        for column in range(self.table.columnCount()):
            if self.table.columnWidth(column) > MAX_COLUMN:
                self.table.setColumnWidth(column, MAX_COLUMN)
        self.advice.setHtml(self._html())
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save).setEnabled(
                bool(self.recommendations))

    def _html(self) -> str:
        if not self.recommendations:
            return ("<p>Nothing to recommend from: press <b>Measure</b> on "
                    "the Infusions tab first.</p>")
        parts = []
        for recommendation in self.recommendations:
            parts.append(f"<h3>{html.escape(recommendation.compound)}</h3>")
            if recommendation.note:
                parts.append(f"<p>{html.escape(recommendation.note)}.</p>")
            parts.append("<ul>")
            for choice in recommendation.choices:
                parts.append(
                    f"<li><b>{html.escape(choice.purpose)}</b>: "
                    f"{html.escape(choice.label)} — "
                    f"{html.escape(choice.reason)}</li>")
            parts.append("</ul>")
            if recommendation.marked:
                parts.append(
                    f"<p>{len(recommendation.marked)} infusion(s) of this "
                    f"compound are in the table and out of the choice: the "
                    f"method there isolates something the file's name is not "
                    f"an adduct of.</p>")
        return "".join(parts)

    # -- what comes off it ----------------------------------------------------- #
    def export_csv(self, path: str = "") -> str:
        if not self.recommendations:
            return ""
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export the energy recommendations",
                "collision-energies.csv", "CSV (*.csv)")
            if not path:
                return ""
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.saved_path = write_csv(self.recommendations, path)
        except OSError as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return ""
        self.status.setText(f"Written to {os.path.basename(path)}.")
        return self.saved_path
