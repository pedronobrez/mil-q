"""
Quantify… on the Infusions tab: an analyte against its standard, in a spray.

The measurement is `infusion_quant.quantify_infusions` and nothing here does
any arithmetic of its own. What this adds is the three things a table needs
that a function does not: the basis to take the ratio on, a look at the rows
before anything is written, and a separate press to write them into the
session's results, with an audit entry saying which basis and what tolerance
produced them.

Writing is deliberately a second press. The rows replace whatever the
Results table held, and a measurement made on a spray is not the same kind of
number as an integrated peak — it is worth seeing before it lands.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from .. import audit
from ..infusion_quant import (BASES, ON_LADDER, QUANT_COLUMNS, TOLERANCE_PPM,
                              InfusionQuantitation, quantify_infusions,
                              row_cells, write_csv)
from ..quantify import apply_calibrations, build_calibrations
from ..session import Session
from .help_window import describe
from .settings import settings

HELP_PAGE = "infusion-quantitation"

#: what each basis is, in the words the dialog offers it by
BASIS_TEXT = {
    "precursor": "Precursor — the intact ion the adduct declares",
    "fragment": "Fragment — the written fragment, or the strongest predicted ion",
    "ladder": "Water-loss ladder — every rung summed (default)",
}


class InfusionQuantDialog(QtWidgets.QDialog):
    """The ratio table, and the press that writes it into the results."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.settings = settings()
        self.quantitation: InfusionQuantitation | None = None
        self.setWindowTitle("Quantify infusions")
        self.resize(1100, 520)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Each analyte of the method is measured against the internal "
            "standard it names, in the averaged spectrum of every open "
            "infusion. There is no peak and no retention time: the response "
            "is a height, and what one compound's isotope envelope puts into "
            "the other's ion is computed from the formula and taken off "
            "before the ratio — or reported as zero, with the reason, where "
            "the instrument removed it first.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Take the ratio on:"))
        self.basis = QtWidgets.QComboBox()
        for name in BASES:
            self.basis.addItem(BASIS_TEXT.get(name, name), name)
        self.basis.setCurrentIndex(BASES.index(ON_LADDER))
        self.basis.setToolTip(
            "The ladder is the default because it is where the signal is "
            "once the precursor has fragmented, and because it is a fixed "
            "set of ions rather than whichever peak is tallest")
        bar.addWidget(self.basis, 1)
        bar.addWidget(QtWidgets.QLabel("Tolerance:"))
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(1.0, 2000.0)
        self.tolerance.setDecimals(1)
        self.tolerance.setSuffix(" ppm")
        self.tolerance.setValue(TOLERANCE_PPM)
        self.tolerance.setToolTip(
            "How far a measured centroid may sit from a predicted ion — and "
            "the window the cross-talk is summed over, which is the same "
            "thing and has to be")
        bar.addWidget(self.tolerance)
        self.btn_measure = QtWidgets.QPushButton("Measure")
        bar.addWidget(self.btn_measure)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(QUANT_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(QUANT_COLUMNS))
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("Not measured yet — press Measure.")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_csv = QtWidgets.QPushButton("Export CSV…")
        self.btn_csv.setEnabled(False)
        buttons.addWidget(self.btn_csv)
        buttons.addStretch(1)
        self.btn_apply = QtWidgets.QPushButton("Write into results")
        self.btn_apply.setToolTip(
            "Replace the Results table with these rows and fit a curve "
            "wherever the samples carry a concentration")
        self.btn_apply.setEnabled(False)
        buttons.addWidget(self.btn_apply)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.btn_measure.clicked.connect(self.measure)
        self.btn_csv.clicked.connect(self.export_csv)
        self.btn_apply.clicked.connect(self.apply)

    # -- measuring ------------------------------------------------------------ #
    @property
    def on(self) -> str:
        return str(self.basis.currentData() or ON_LADDER)

    def measure(self) -> InfusionQuantitation:
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        try:
            self.quantitation = quantify_infusions(
                self.session, on=self.on,
                tolerance_ppm=float(self.tolerance.value()))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.reload()
        return self.quantitation

    def reload(self) -> None:
        quantitation = self.quantitation
        rows = quantitation.rows if quantitation is not None else []
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            cells = row_cells(row)
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                item.setToolTip(self._tooltip(row, column, text))
                self.table.setItem(index, column, item)
        self.table.resizeColumnsToContents()
        self.btn_csv.setEnabled(bool(rows))
        self.btn_apply.setEnabled(bool(rows))
        if quantitation is None:
            self.status.setText("Not measured yet — press Measure.")
        else:
            said = quantitation.summary()
            if quantitation.rows:
                said += f" · measured in {quantitation.seconds:.1f} s"
            self.status.setText(said)

    @staticmethod
    def _tooltip(row, column: int, text: str) -> str:
        """
        The whole sentence behind a cell that abbreviates one.

        The cross-talk column is a number and its reason is a paragraph — the
        ions that leak, which satellite each is, and how far it lands from
        the ion it reaches — so the number goes in the table and the
        paragraph here.
        """
        result = row.result
        if result is None:
            return text
        if QUANT_COLUMNS[column] in ("Cross-talk", "Ratio",
                                     "Ratio uncorrected"):
            return result.correction_note or result.note or text
        if QUANT_COLUMNS[column] in ("Analyte response", "Standard response"):
            response = (row.analyte_response
                        if QUANT_COLUMNS[column].startswith("Analyte")
                        else row.standard_response)
            return response.describe(row.on) if response is not None else text
        return text

    # -- what comes off it ---------------------------------------------------- #
    def apply(self) -> int:
        """Write the rows into the session's results and fit the curves."""
        quantitation = self.quantitation
        if quantitation is None or not quantitation.rows:
            self.status.setText("Measure first; there is nothing to write.")
            return 0
        session = self.session
        session.results = quantitation.results()
        curves = build_calibrations(session.results, session.entries,
                                    session.method,
                                    previous=session.calibrations)
        apply_calibrations(session.results, session.entries, session.method,
                           curves)
        session.calibrations = curves
        pairs = sorted({f"{row.analyte} / {row.standard}"
                        for row in quantitation.rows if row.standard})
        session.record(
            audit.INFUSION_QUANTITATION, ", ".join(pairs),
            after=f"{len(session.results)} row(s) on the {quantitation.on}",
            note=f"{len(quantitation.rows)} pair(s) over "
                 f"{len({r.sample_key for r in quantitation.rows})} "
                 f"infusion(s) at {quantitation.tolerance_ppm:g} ppm")
        session.notify_results_changed()
        fitted = sum(1 for curve in curves.values() if curve.is_fitted)
        self.status.setText(
            f"{len(session.results)} row(s) written to the Results table"
            + (f"; {fitted} calibration curve(s) fitted." if fitted else
               "; no sample carries a concentration, so no curve was fitted."))
        return len(session.results)

    def export_csv(self, path: str = "") -> str:
        quantitation = self.quantitation
        if quantitation is None or not quantitation.rows:
            self.status.setText("Measure first; there is nothing to export.")
            return ""
        if not path:
            start = os.path.join(
                self.settings.value("io/last_dir", "", type=str),
                "infusion-quantitation.csv")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export the infusion ratios", start, "CSV (*.csv)")
            if not path:
                return ""
            self.settings.setValue("io/last_dir", os.path.dirname(path))
        try:
            written = write_csv(quantitation, path)
        except OSError as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return ""
        self.status.setText(f"{len(quantitation.rows)} row(s) written to "
                            f"{os.path.basename(written)}.")
        return written
