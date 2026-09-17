"""The calibration curve for the component under review."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from ..calibration import REGRESSIONS, WEIGHTINGS, Calibration
from .flow_layout import FlowLayout

POINT_USED = "#1f77b4"
POINT_EXCLUDED = "#c0c0c0"
CURVE_PEN = "#d62728"


class CalibrationPanel(QtWidgets.QWidget):
    """The curve, its standards, and the controls that shape it."""

    sigSettingsChanged = QtCore.pyqtSignal(str, str)   # regression, weighting
    sigPointToggled = QtCore.pyqtSignal(str)           # sample key
    sigAutoOutliers = QtCore.pyqtSignal(float)         # tolerance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curve: Calibration | None = None
        self._loading = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        bar.addWidget(QtWidgets.QLabel("Regression"))
        self.regression = QtWidgets.QComboBox()
        self.regression.addItems(list(REGRESSIONS))
        bar.addWidget(self.regression)
        bar.addWidget(QtWidgets.QLabel("Weighting"))
        self.weighting = QtWidgets.QComboBox()
        self.weighting.addItems(list(WEIGHTINGS))
        self.weighting.setToolTip(
            "Calibration ranges span decades; without weighting the top "
            "standard dominates the fit and the bottom of the range drifts")
        bar.addWidget(self.weighting)
        bar.addSpacing(12)
        self.btn_outliers = QtWidgets.QPushButton("Remove outliers")
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(1.0, 100.0)
        self.tolerance.setValue(15.0)
        self.tolerance.setSuffix(" %")
        self.tolerance.setToolTip("Accuracy a standard has to be within")
        bar.addWidget(self.btn_outliers)
        bar.addWidget(self.tolerance)
        bar.addStretch(1)
        layout.addLayout(bar)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Concentration")
        self.plot.setLabel("left", "Response")
        theme.style_axes(self.plot)
        self._line = self.plot.plot([], [], pen=pg.mkPen(CURVE_PEN, width=1.5))
        self._scatter = pg.ScatterPlotItem(size=10,
                                           pen=pg.mkPen(theme.axis()))
        self._scatter.sigClicked.connect(self._on_point_clicked)
        self.plot.addItem(self._scatter)
        body.addWidget(self.plot)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Sample", "Conc.", "Response", "Calculated", "Acc. %"])
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.setToolTip("Double-click a standard to include or exclude it")
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 90)
        body.addWidget(self.table)
        body.setSizes([560, 440])
        layout.addWidget(body, 1)

        self.status = QtWidgets.QLabel("No curve yet.")
        self.status.setProperty("role", "caption")
        # a sentence is not a width: without this the longest message this
        # panel can show — the one about marking samples as standards — set
        # the least width of the whole window
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.regression.currentTextChanged.connect(self._emit_settings)
        self.weighting.currentTextChanged.connect(self._emit_settings)
        self.btn_outliers.clicked.connect(
            lambda: self.sigAutoOutliers.emit(self.tolerance.value()))
        self.table.cellDoubleClicked.connect(self._on_row_activated)

    # -- content ------------------------------------------------------------------ #
    def show_curve(self, curve: Calibration | None, unit: str = "") -> None:
        self._curve = curve
        self.plot.setLabel("bottom", f"Concentration ({unit})" if unit
                           else "Concentration")
        if curve is None:
            self._scatter.setData([])
            self._line.setData([], [])
            self.table.setRowCount(0)
            self.status.setText(
                "No standards for this component — mark samples as Standard "
                "in the Samples workspace and give them a concentration.")
            return

        self._loading = True
        self.regression.setCurrentText(curve.regression)
        self.weighting.setCurrentText(curve.weighting)
        self._loading = False

        spots = [{
            "pos": (p.concentration, p.response),
            "brush": pg.mkBrush(POINT_USED if p.used else POINT_EXCLUDED),
            "symbol": "o" if p.used else "x",
            "data": p.sample_key,
        } for p in curve.points]
        self._scatter.setData(spots)

        if curve.is_fitted and curve.used_points:
            highest = max(p.concentration for p in curve.used_points)
            xs = np.linspace(0, highest * 1.05, 200)
            self._line.setData(xs, [curve.response_at(v) for v in xs])
        else:
            self._line.setData([], [])
        self.plot.enableAutoRange()
        self.plot.autoRange()

        self.table.setRowCount(len(curve.points))
        for row, point in enumerate(curve.points):
            values = [
                point.sample_name,
                f"{point.concentration:g}",
                f"{point.response:,.4g}",
                "—" if point.calculated is None else f"{point.calculated:,.4g}",
                "—" if point.accuracy is None else f"{point.accuracy:.1f}",
            ]
            for column, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if not point.used:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(theme.ink_faint())))
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, max(self.table.columnWidth(0), 80))

        if curve.is_fitted:
            excluded = len(curve.points) - len(curve.used_points)
            text = (f"{curve.equation}    r² = {curve.r2:.5f}    r = {curve.r:.5f}"
                    f"    {len(curve.used_points)} point(s)")
            if excluded:
                text += f", {excluded} excluded"
            self.status.setText(text)
        else:
            self.status.setText(curve.note or "Not enough standards to fit.")

    # -- interaction ---------------------------------------------------------------- #
    def _emit_settings(self, *_args) -> None:
        if not self._loading:
            self.sigSettingsChanged.emit(self.regression.currentText(),
                                         self.weighting.currentText())

    def _on_point_clicked(self, _scatter, spots) -> None:
        if spots:
            self.sigPointToggled.emit(str(spots[0].data()))

    def _on_row_activated(self, row: int, _column: int) -> None:
        if self._curve and 0 <= row < len(self._curve.points):
            self.sigPointToggled.emit(self._curve.points[row].sample_key)
