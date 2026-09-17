"""Mass calculator: exact masses, RDBE, adduct m/z and isotope pattern."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..chemistry import (
    ADDUCTS,
    ADDUCTS_BY_NAME,
    FormulaError,
    average_mass,
    isotope_pattern,
    mass_error_mda,
    mass_error_ppm,
    monoisotopic_mass,
    parse_formula,
    rdbe,
)
from .flow_layout import FlowLayout


class MassCalcPanel(QtWidgets.QWidget):
    """Type a formula, read its masses and compare its pattern with the data."""

    sigOverlay = QtCore.pyqtSignal(list, str)  # [(m/z, abundance)], label
    sigClearOverlay = QtCore.pyqtSignal()
    sigSendToFinder = QtCore.pyqtSignal(float, str)  # m/z, adduct name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern: list[tuple[float, float]] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        form = QtWidgets.QFormLayout()
        self.formula_edit = QtWidgets.QLineEdit()
        self.formula_edit.setPlaceholderText("C18H34O4")
        self.formula_edit.setToolTip(
            "Groups and multipliers work: C6H4(NO2)2.\n"
            "Single isotopes go in brackets — [13C] — and D means deuterium."
        )
        form.addRow("Formula:", self.formula_edit)

        self.adduct_combo = QtWidgets.QComboBox()
        self.adduct_combo.addItems([a.name for a in ADDUCTS])
        self.adduct_combo.setCurrentText("[M-H]-")
        form.addRow("Adduct:", self.adduct_combo)
        layout.addLayout(form)

        self.summary = QtWidgets.QTableWidget(4, 2)
        self.summary.horizontalHeader().setVisible(False)
        self.summary.verticalHeader().setVisible(False)
        self.summary.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.summary.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self.summary.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.summary.verticalHeader().setDefaultSectionSize(22)
        self.summary.setFixedHeight(4 * 22 + 4)
        for row, name in enumerate(
            ["Monoisotopic", "Average", "RDBE", "Ion m/z"]
        ):
            self.summary.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
        layout.addWidget(self.summary)

        accuracy = QtWidgets.QFormLayout()
        self.measured_edit = QtWidgets.QLineEdit()
        self.measured_edit.setPlaceholderText("measured m/z")
        accuracy.addRow("Measured:", self.measured_edit)
        self.error_label = QtWidgets.QLabel("—")
        self.error_label.setProperty("role", "strong")
        accuracy.addRow("Error:", self.error_label)
        layout.addLayout(accuracy)

        layout.addWidget(QtWidgets.QLabel("Isotope pattern:"))
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["m/z", "Abundance %"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setDefaultSectionSize(20)
        layout.addWidget(self.table, 1)

        buttons = FlowLayout()
        self.btn_overlay = QtWidgets.QPushButton("Overlay on spectrum")
        self.btn_clear = QtWidgets.QPushButton("Clear overlay")
        buttons.addWidget(self.btn_overlay)
        buttons.addWidget(self.btn_clear)
        layout.addLayout(buttons)

        self.btn_finder = QtWidgets.QPushButton("Send m/z to formula finder")
        layout.addWidget(self.btn_finder)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "danger")
        layout.addWidget(self.status)

        self.formula_edit.textChanged.connect(self.recompute)
        self.adduct_combo.currentTextChanged.connect(self.recompute)
        self.measured_edit.textChanged.connect(self._update_error)
        self.btn_overlay.clicked.connect(self._emit_overlay)
        self.btn_clear.clicked.connect(self.sigClearOverlay)
        self.btn_finder.clicked.connect(self._emit_to_finder)

    # -- computation ----------------------------------------------------------- #
    def recompute(self) -> None:
        text = self.formula_edit.text().strip()
        self._pattern = []
        if not text:
            self._set_summary(None)
            self.table.setRowCount(0)
            self.status.setText("")
            self._update_error()
            return
        try:
            counts = parse_formula(text)
        except FormulaError as exc:
            self.status.setText(str(exc))
            self._set_summary(None)
            self.table.setRowCount(0)
            self._update_error()
            return
        self.status.setText("")
        adduct = ADDUCTS_BY_NAME[self.adduct_combo.currentText()]
        mono = monoisotopic_mass(counts)
        self._set_summary({
            "Monoisotopic": f"{mono:.5f}",
            "Average": f"{average_mass(counts):.4f}",
            "RDBE": f"{rdbe(counts):g}",
            "Ion m/z": f"{adduct.mz(mono):.5f}",
        })
        self._pattern = isotope_pattern(counts, adduct, min_abundance=0.001,
                                        max_peaks=12)
        self.table.setRowCount(len(self._pattern))
        for row, (mz, abundance) in enumerate(self._pattern):
            for column, text_value in enumerate((f"{mz:.5f}", f"{abundance * 100:.2f}")):
                item = QtWidgets.QTableWidgetItem(text_value)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        self._update_error()

    def _set_summary(self, values: dict[str, str] | None) -> None:
        for row in range(self.summary.rowCount()):
            name = self.summary.item(row, 0).text()
            text = "—" if values is None else values.get(name, "—")
            item = QtWidgets.QTableWidgetItem(text)
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                  | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.summary.setItem(row, 1, item)

    def theoretical_mz(self) -> float | None:
        item = self.summary.item(3, 1)
        if item is None or item.text() == "—":
            return None
        return float(item.text())

    def _update_error(self) -> None:
        theoretical = self.theoretical_mz()
        text = self.measured_edit.text().strip().replace(",", ".")
        if theoretical is None or not text:
            self.error_label.setText("—")
            return
        try:
            measured = float(text)
        except ValueError:
            self.error_label.setText("—")
            return
        mda = mass_error_mda(measured, theoretical)
        ppm = mass_error_ppm(measured, theoretical)
        self.error_label.setText(f"{mda:+.2f} mDa    {ppm:+.2f} ppm")

    # -- actions ---------------------------------------------------------------- #
    def set_measured(self, mz: float) -> None:
        self.measured_edit.setText(f"{mz:.4f}")

    def _emit_overlay(self) -> None:
        if self._pattern:
            self.sigOverlay.emit(self._pattern, self.formula_edit.text().strip())

    def _emit_to_finder(self) -> None:
        text = self.measured_edit.text().strip().replace(",", ".")
        value = None
        if text:
            try:
                value = float(text)
            except ValueError:
                value = None
        if value is None:
            value = self.theoretical_mz()
        if value is not None:
            self.sigSendToFinder.emit(value, self.adduct_combo.currentText())
