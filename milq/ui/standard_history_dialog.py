"""
One standard's own-library records as a control chart, over the days.

The Library tab counts the records of a library of one's own. This reads
them back: every record of one compound at one collision energy and
activation, in the order they were acquired, with the three charts
`standard_history` measures and the table they were drawn from.

Nothing here computes anything. The charts, the limits, the verdicts and
the CSV all come from `standard_history`, which is why the same figures can
be checked with no window open.
"""

from __future__ import annotations

import os

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from ..qc import OUTLIER_SIGMA, WARN_SIGMA, ControlChart
from ..standard_history import (METRICS, MIN_RECORDS, Series, StandardHistory,
                                axis_split_note, caveat, ppm_text,
                                read_history, verdict, write_csv)
from . import theme
from .help_window import describe, open_manual

HELP_PAGE = "standard-history"

POINT = "#234b8c"
POINT_OUT = "#a4262c"
POINT_WARN = "#c07a00"
CENTRE_PEN = "#4c8c4a"
TREND_PEN = "#a4262c"

RECORD_COLUMNS = ["Record", "Acquired", "File", "Precursor", "Base peak m/z",
                  "ppm from first", "Base peak intensity", "Score", "Reverse",
                  "vs previous", "Out on", "Mass axis"]
CHART_COLUMNS = ["Chart", "n", "Centre", "Spread", "Drift", "ρ", "Verdict"]


class StandardHistoryDialog(QtWidgets.QDialog):
    """The history of one compound in a library of one's own."""

    def __init__(self, path: str = "", history: StandardHistory | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Standard history")
        describe(self, HELP_PAGE)
        self.resize(1000, 720)
        self.history = history
        self.path = path or (history.path if history else "")
        self.saved_path = ""

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Every record your own library holds of one compound, in the "
            "order it was acquired, scored against the first of them. "
            "Records are grouped by collision energy and activation: a "
            "spectrum measured at another energy has other fragments, and "
            "an absolute intensity is comparable only within one method. "
            f"Limits are drawn from {MIN_RECORDS} records upwards; below "
            "that the charts say so rather than draw a limit through two "
            "points.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Compound"))
        self.compound = QtWidgets.QComboBox()
        self.compound.setMinimumWidth(160)
        bar.addWidget(self.compound)
        bar.addWidget(QtWidgets.QLabel("Series"))
        self.series = QtWidgets.QComboBox()
        self.series.setMinimumWidth(200)
        self.series.setToolTip(
            "One collision energy and activation. A record at 22 eV EAD is "
            "not compared with one at 45 eV CID")
        bar.addWidget(self.series, 1)
        bar.addWidget(QtWidgets.QLabel("Chart"))
        self.metric = QtWidgets.QComboBox()
        self.metric.addItems(list(METRICS))
        self.metric.setMinimumWidth(220)
        bar.addWidget(self.metric)
        layout.addLayout(bar)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Record, in acquisition order")
        self.plot.setToolTip(
            f"Solid line the median, dotted {WARN_SIGMA:g}σ, dashed "
            f"{OUTLIER_SIGMA:g}σ — the Batch QC rule: a record is out "
            f"only when it is both past {OUTLIER_SIGMA:g}σ and far "
            f"enough from the centre to act on")
        theme.style_axes(self.plot)
        self._lines: list[pg.InfiniteLine] = []
        self._trend = self.plot.plot(
            [], [], pen=pg.mkPen(TREND_PEN, width=1.2,
                                 style=QtCore.Qt.PenStyle.DashLine))
        self._scatter = pg.ScatterPlotItem(size=9, pen=pg.mkPen(theme.axis()))
        self.plot.addItem(self._scatter)
        body.addWidget(self.plot)

        self.records = _table(RECORD_COLUMNS)
        self.records.setToolTip(
            "Score and Reverse are against the first record of this series; "
            "'vs previous' is against the record before it, which is what "
            "says whether a change happened at one verification or crept in")
        self.charts = _table(CHART_COLUMNS)
        self.charts.setToolTip("Click a row to draw that chart")
        self.charts.cellClicked.connect(self._chart_row_clicked)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.records, "Records")
        self.tabs.addTab(self.charts, "Charts")
        body.addWidget(self.tabs)
        body.setSizes([420, 300])
        layout.addWidget(body, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Close
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.btn_save = self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.btn_save.setText("Export CSV…")
        self.btn_save.clicked.connect(self.save)
        #: offered only where a compound was split across two mass axes, and
        #: it does not rewrite anything itself: it closes and asks the
        #: Library tab, which owns the file, the folders the acquisitions
        #: were opened from and the corrections in force
        self.rewrite_requested = False
        self.btn_rewrite = self.buttons.addButton(
            "Rewrite from files…",
            QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_rewrite.setToolTip(
            "These records sit on different mass axes and are charted "
            "separately for it. Rewriting reads every record whose "
            "acquisition is still on disk again and writes them all onto "
            "the axis in force now")
        self.btn_rewrite.setVisible(False)
        self.btn_rewrite.clicked.connect(self._ask_for_rewrite)
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        layout.addWidget(self.buttons)

        self.compound.currentTextChanged.connect(self._reload_series)
        self.series.currentIndexChanged.connect(self._draw)
        self.metric.currentTextChanged.connect(self._draw)
        self.reload()

    # -- content --------------------------------------------------------------- #
    def reload(self) -> None:
        if self.history is None:
            if not self.path or not os.path.exists(self.path):
                self._empty("No library of your own to read yet.")
                return
            try:
                self.history = read_history(self.path)
            except OSError as exc:
                self._empty(f"Could not read {os.path.basename(self.path)}: {exc}")
                return
        if not self.history.series:
            self._empty(f"{os.path.basename(self.path)} holds no records.")
            return
        self.compound.blockSignals(True)
        self.compound.clear()
        self.compound.addItems(self.history.compounds)
        self.compound.blockSignals(False)
        self._reload_series()

    def _empty(self, message: str) -> None:
        self.status.setText(message)
        self.btn_save.setEnabled(False)

    def _reload_series(self, *_args) -> None:
        if self.history is None:
            return
        wanted = self.compound.currentText()
        self.series.blockSignals(True)
        self.series.clear()
        for series in self.history.for_compound(wanted):
            self.series.addItem(f"{series.conditions} — {series.summary_line()}",
                                series)
        self.series.blockSignals(False)
        self.series.setCurrentIndex(0 if self.series.count() else -1)
        self._draw()

    def current_series(self) -> Series | None:
        data = self.series.currentData()
        return data if isinstance(data, Series) else None

    def _draw(self, *_args) -> None:
        series = self.current_series()
        self._clear()
        if series is None:
            self._empty("Nothing to chart.")
            return
        self.btn_save.setEnabled(True)
        self._fill_records(series)
        self._fill_charts(series)
        self._draw_chart(series.charts[self.metric.currentText()])
        said = [series.label, series.summary_line(), caveat(series)]
        # a series cut off from another by the mass axis says so, and says
        # what puts the two back together — the button is on the Library tab
        # and this dialog is opened from it, so it offers the same one
        split = axis_split_note(self.history.split_with(series)) \
            if self.history is not None else ""
        if split:
            said.append(split)
        self.btn_rewrite.setVisible(bool(split))
        self.status.setText(" · ".join(part for part in said if part))

    def _fill_records(self, series: Series) -> None:
        flagged = series.flagged
        self.records.setRowCount(len(series.records))
        for row, record in enumerate(series.records):
            cells = [
                record.name, record.when or "—", record.file or "—",
                _number(record.precursor, 4), _number(record.base_mz, 4),
                ppm_text(record) or "—",
                _number(record.base_intensity, 0),
                _percent(record.score), _percent(record.reverse),
                (f"{_percent(record.previous_score)} / "
                 f"{_percent(record.previous_reverse)}"),
                "; ".join(flagged.get(record.label, [])) or "",
                record.axis_label,
            ]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column >= 3:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 10 and text:
                    item.setForeground(pg.mkColor(theme.danger()))
                self.records.setItem(row, column, item)
        self.records.resizeColumnsToContents()

    def _fill_charts(self, series: Series) -> None:
        self.charts.setRowCount(len(METRICS))
        for row, metric in enumerate(METRICS):
            chart = series.charts[metric]
            unit = chart.limits.unit
            cells = [metric, f"{len(chart.injections):,}",
                     _number(chart.centre, 3), _number(chart.sigma, 3),
                     "—" if chart.drift is None else f"{chart.drift:+,.1f}{unit}",
                     _number(chart.correlation, 3), verdict(chart)]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if 1 <= column <= 5:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 6 and (chart.out or chart.drifted):
                    item.setForeground(pg.mkColor(theme.danger()))
                self.charts.setItem(row, column, item)
        self.charts.resizeColumnsToContents()

    # -- the chart ------------------------------------------------------------- #
    def _clear(self) -> None:
        self._scatter.setData([])
        self._trend.setData([], [])
        for line in self._lines:
            self.plot.removeItem(line)
        self._lines.clear()
        self.records.setRowCount(0)
        self.charts.setRowCount(0)

    def _draw_chart(self, chart: ControlChart) -> None:
        self.plot.setLabel("left", chart.component)
        if not chart.injections:
            return
        spots = []
        for point in chart.injections:
            brush = POINT
            if point.out:
                brush = POINT_OUT
            elif point.warned:
                brush = POINT_WARN
            spots.append({"pos": (point.order, point.value),
                          "brush": pg.mkBrush(brush)})
        self._scatter.setData(spots)
        if not chart.measurable:
            return
        self._line_at(chart.centre, CENTRE_PEN, 1.4,
                      QtCore.Qt.PenStyle.SolidLine)
        if not chart.sigma:
            return
        for sigma, pen, width, style in (
                (WARN_SIGMA, theme.muted(), 1.0, QtCore.Qt.PenStyle.DotLine),
                (OUTLIER_SIGMA, POINT_OUT, 1.2, QtCore.Qt.PenStyle.DashLine)):
            for sign in (1, -1):
                self._line_at(chart.centre + sign * sigma * chart.sigma,
                              pen, width, style)
        if chart.drifted:
            order = np.array([p.order for p in chart.injections], dtype=float)
            values = np.array([p.value for p in chart.injections], dtype=float)
            self._trend.setData(order, np.polyval(np.polyfit(order, values, 1),
                                                  order))

    def _line_at(self, y: float, colour: str, width: float, style) -> None:
        line = pg.InfiniteLine(pos=y, angle=0,
                               pen=pg.mkPen(colour, width=width, style=style))
        self.plot.addItem(line)
        self._lines.append(line)

    def _chart_row_clicked(self, row: int, _column: int) -> None:
        item = self.charts.item(row, 0)
        if item is not None:
            self.metric.setCurrentText(item.text())

    def _ask_for_rewrite(self) -> None:
        """Close, and let the Library tab do the writing."""
        self.rewrite_requested = True
        self.accept()

    # -- out ------------------------------------------------------------------- #
    def save(self) -> None:
        if self.history is None:
            return
        compound = self.compound.currentText()
        stem = compound or os.path.splitext(os.path.basename(self.path))[0]
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export the standard history", f"{stem}-history.csv",
            "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        self.saved_path = write_csv(self.history, path, compound)
        self.status.setText(f"Written to {os.path.basename(self.saved_path)}: "
                            f"every record of {compound}, with what each "
                            f"chart says above the rows.")


def _table(columns: list[str]) -> QtWidgets.QTableWidget:
    table = QtWidgets.QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setDefaultSectionSize(22)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _number(value, decimals: int = 2) -> str:
    return "—" if value is None else f"{value:,.{decimals}f}"


def _percent(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}"
