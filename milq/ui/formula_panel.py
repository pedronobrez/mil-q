"""Formula finder: elemental compositions for a measured mass."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..chemistry import ADDUCTS, FormulaHit

#: elements offered in the search, with the default ranges for small molecules
DEFAULT_ELEMENTS: list[tuple[str, int, int]] = [
    ("C", 0, 60),
    ("H", 0, 120),
    ("N", 0, 4),
    ("O", 0, 12),
    ("S", 0, 2),
    ("P", 0, 2),
    ("Cl", 0, 0),
    ("Br", 0, 0),
    ("Na", 0, 0),
    ("D", 0, 0),
]

RESULT_COLUMNS = ["Formula", "m/z", "mDa", "ppm", "RDBE", "Isotope"]


class FormulaPanel(QtWidgets.QWidget):
    """Search parameters and the ranked candidate list."""

    sigSearch = QtCore.pyqtSignal(dict)
    sigOverlay = QtCore.pyqtSignal(object)  # FormulaHit
    sigSendToCalculator = QtCore.pyqtSignal(str)  # formula

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hits: list[FormulaHit] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        form = QtWidgets.QFormLayout()
        self.mz_edit = QtWidgets.QLineEdit()
        self.mz_edit.setPlaceholderText("313.2384")
        self.mz_edit.setToolTip(
            "Right-click a peak in the spectrum and choose "
            "“Find formula for this peak” to fill this in"
        )
        form.addRow("Measured m/z:", self.mz_edit)

        self.adduct_combo = QtWidgets.QComboBox()
        self.adduct_combo.addItems([a.name for a in ADDUCTS])
        self.adduct_combo.setCurrentText("[M-H]-")
        form.addRow("Adduct:", self.adduct_combo)

        tolerance = QtWidgets.QHBoxLayout()
        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setDecimals(3)
        self.tol_spin.setRange(0.001, 1000.0)
        self.tol_spin.setValue(10.0)
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["ppm", "Da"])
        tolerance.addWidget(self.tol_spin)
        tolerance.addWidget(self.unit_combo)
        form.addRow("Tolerance (±):", tolerance)

        rdbe_row = QtWidgets.QHBoxLayout()
        self.rdbe_min = QtWidgets.QDoubleSpinBox()
        self.rdbe_min.setRange(-10.0, 100.0)
        self.rdbe_min.setValue(-0.5)
        self.rdbe_min.setDecimals(1)
        self.rdbe_max = QtWidgets.QDoubleSpinBox()
        self.rdbe_max.setRange(-10.0, 100.0)
        self.rdbe_max.setValue(40.0)
        self.rdbe_max.setDecimals(1)
        rdbe_row.addWidget(self.rdbe_min)
        rdbe_row.addWidget(QtWidgets.QLabel("to"))
        rdbe_row.addWidget(self.rdbe_max)
        form.addRow("RDBE:", rdbe_row)
        layout.addLayout(form)

        self.even_electron = QtWidgets.QCheckBox("Even-electron only")
        self.even_electron.setChecked(True)
        self.even_electron.setToolTip(
            "Keep only integer RDBE values, which is what a closed-shell "
            "molecule has"
        )
        self.golden_rules = QtWidgets.QCheckBox("Apply element-ratio rules")
        self.golden_rules.setChecked(True)
        self.golden_rules.setToolTip(
            "Drop compositions with implausible H/C, N/C, O/C, P/C or S/C "
            "ratios (Kind & Fiehn's golden rules)"
        )
        self.use_isotopes = QtWidgets.QCheckBox("Rank by isotope pattern")
        self.use_isotopes.setChecked(True)
        self.use_isotopes.setToolTip(
            "Score each candidate against the isotope peaks of the spectrum "
            "on screen — usually what separates candidates above 300 Da"
        )
        for box in (self.even_electron, self.golden_rules, self.use_isotopes):
            layout.addWidget(box)

        layout.addWidget(QtWidgets.QLabel("Element ranges:"))
        self.elements = QtWidgets.QTableWidget(len(DEFAULT_ELEMENTS), 3)
        self.elements.setHorizontalHeaderLabels(["Element", "Min", "Max"])
        self.elements.horizontalHeader().setStretchLastSection(True)
        self.elements.verticalHeader().setVisible(False)
        self.elements.verticalHeader().setDefaultSectionSize(20)
        self.elements.setFixedHeight(len(DEFAULT_ELEMENTS) * 20 + 26)
        for row, (element, low, high) in enumerate(DEFAULT_ELEMENTS):
            name = QtWidgets.QTableWidgetItem(element)
            name.setFlags(name.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.elements.setItem(row, 0, name)
            self.elements.setItem(row, 1, QtWidgets.QTableWidgetItem(str(low)))
            self.elements.setItem(row, 2, QtWidgets.QTableWidgetItem(str(high)))
        layout.addWidget(self.elements)

        self.btn_search = QtWidgets.QPushButton("Search")
        font = self.btn_search.font()
        font.setBold(True)
        self.btn_search.setFont(font)
        layout.addWidget(self.btn_search)

        self.table = QtWidgets.QTableWidget(0, len(RESULT_COLUMNS))
        self.table.setHorizontalHeaderLabels(RESULT_COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.setToolTip(
            "Double-click to overlay that composition's isotope pattern"
        )
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "hint")
        layout.addWidget(self.status)

        self.btn_search.clicked.connect(self._emit_search)
        self.mz_edit.returnPressed.connect(self._emit_search)
        self.table.cellDoubleClicked.connect(self._row_activated)

    # -- parameters ------------------------------------------------------------- #
    def set_target(self, mz: float, adduct: str | None = None) -> None:
        self.mz_edit.setText(f"{mz:.4f}")
        if adduct:
            self.adduct_combo.setCurrentText(adduct)

    def ranges(self) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for row in range(self.elements.rowCount()):
            element = self.elements.item(row, 0).text()
            try:
                low = int(self.elements.item(row, 1).text())
                high = int(self.elements.item(row, 2).text())
            except (AttributeError, ValueError):
                continue
            if high > 0:
                out[element] = (max(low, 0), high)
        return out

    def _emit_search(self) -> None:
        text = self.mz_edit.text().strip().replace(",", ".")
        try:
            mz = float(text)
        except ValueError:
            self.status.setText("Type a measured m/z first.")
            return
        self.sigSearch.emit({
            "mz": mz,
            "adduct": self.adduct_combo.currentText(),
            "tolerance": self.tol_spin.value(),
            "unit": self.unit_combo.currentText(),
            "ranges": self.ranges(),
            "rdbe_range": (self.rdbe_min.value(), self.rdbe_max.value()),
            "even_electron": self.even_electron.isChecked(),
            "golden_rules": self.golden_rules.isChecked(),
            "use_isotopes": self.use_isotopes.isChecked(),
        })

    # -- results ----------------------------------------------------------------- #
    def set_results(self, hits: list[FormulaHit], note: str = "") -> None:
        self._hits = list(hits)
        self.table.setRowCount(len(hits))
        for row, hit in enumerate(hits):
            values = [
                hit.formula,
                f"{hit.mz:.5f}",
                f"{hit.error_mda:+.2f}",
                f"{hit.error_ppm:+.2f}",
                f"{hit.rdbe:g}",
                f"{hit.isotope_score * 100:.0f}" if hit.isotope_score else "—",
            ]
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.status.setText(note)

    @property
    def hits(self) -> list[FormulaHit]:
        return list(self._hits)

    def _row_activated(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._hits):
            self.sigOverlay.emit(self._hits[row])
            self.sigSendToCalculator.emit(self._hits[row].formula)
