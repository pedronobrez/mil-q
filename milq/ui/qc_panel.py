"""
The batch as a control chart: what the run did between first and last.

Every other view in this program answers a question about one peak in one
sample. This one answers a question about the run — and it is the only view
where the horizontal axis is time in the sense that matters, the order the
instrument actually injected.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from . import theme
from ..qc import (ALWAYS_OUT_PERCENT, MIN_SNR, OUTLIER_SIGMA,
                  OUT_PERCENT, WARN_SIGMA, BatchQC, ControlChart,
                  batch_qc, exclude_failed, failed_injections)
from ..session import Session
from .flow_layout import FlowLayout

POINT = "#234b8c"
POINT_OUT = "#a4262c"
POINT_WARN = "#c07a00"
CENTRE_PEN = "#4c8c4a"
TREND_PEN = "#a4262c"


class QualityPanel(QtWidgets.QWidget):
    """
    An internal standard's response across the injection sequence.

    The same amount of it went into every vial, so anything the chart shows
    is the batch's own doing: an injection that failed, a source that
    gradually stopped ionising, a column that shifted halfway through.
    """

    sigSampleActivated = QtCore.pyqtSignal(str)        # sample key

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._report: BatchQC | None = None
        self._sampling = None
        self._chart: ControlChart | None = None
        self._keys: list[str] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        bar.addWidget(QtWidgets.QLabel("Component"))
        self.component = QtWidgets.QComboBox()
        self.component.setToolTip(
            "Internal standards first: the same amount goes into every vial, "
            "so their response is the one number whose variation belongs to "
            "the batch rather than to the study")
        bar.addWidget(self.component, 1)
        self.btn_refresh = QtWidgets.QPushButton("Recheck")
        bar.addWidget(self.btn_refresh)
        self.btn_exclude = QtWidgets.QPushButton("Exclude failed injections")
        self.btn_exclude.setToolTip(
            "Take the results of the injections where every internal "
            "standard went at once out of the statistics, marked with the "
            "reason. Rows integrated by hand are left alone")
        self.btn_exclude.setEnabled(False)
        bar.addWidget(self.btn_exclude)
        self.btn_floors = QtWidgets.QPushButton("Suggest floors…")
        self.btn_floors.setToolTip(
            "Propose a Min. response for each internal standard from what it "
            "gave in the injections that were not failures — half its median, "
            "shown with its basis, written only when ticked and applied")
        self.btn_floors.setEnabled(False)
        bar.addWidget(self.btn_floors)
        bar.addStretch(1)
        layout.addLayout(bar)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Injection")
        self.plot.setToolTip(
            f"Solid line the median, dotted {WARN_SIGMA:g}\u03c3, dashed "
            f"{OUTLIER_SIGMA:g}\u03c3. An injection is called out only when "
            f"it is past {OUTLIER_SIGMA:g}\u03c3 and at least "
            f"{OUT_PERCENT:g}% from the centre — a batch that repeats itself "
            f"well has a spread too small to flag on alone")
        self.plot.setLabel("left", "Response")
        theme.style_axes(self.plot)
        self._lines: list[pg.InfiniteLine] = []
        self._trend = self.plot.plot([], [], pen=pg.mkPen(TREND_PEN, width=1.2,
                                                          style=QtCore.Qt.PenStyle.DashLine))
        self._scatter = pg.ScatterPlotItem(size=9, pen=pg.mkPen(theme.axis()))
        self._scatter.sigClicked.connect(self._on_point_clicked)
        self.plot.addItem(self._scatter)
        body.addWidget(self.plot)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Component", "n", "Centre", "Spread", "S/N", "Drift %", "ρ",
             "Verdict"])
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Click a row to chart that component")

        self.precision = QtWidgets.QTableWidget(0, 4)
        self.precision.setHorizontalHeaderLabels(
            ["Component", "n", "Mean", "%CV"])
        self.precision.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.precision.verticalHeader().setDefaultSectionSize(20)
        self.precision.horizontalHeader().setStretchLastSection(True)
        self.precision.setToolTip(
            "Quality controls only: unknowns differ by design and standards "
            "by construction, so neither says anything about precision")

        self.sampling = QtWidgets.QTableWidget(0, 9)
        self.sampling.setHorizontalHeaderLabels(
            ["Component", "n", "Cycle (s)", "Width (s)", "Points", "Under 3",
             "Cycle for a fit (s)", "Cycle for 10 (s)", "Narrower than a cycle"])
        self.sampling.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sampling.verticalHeader().setDefaultSectionSize(20)
        self.sampling.horizontalHeader().setStretchLastSection(True)
        self.sampling.setToolTip(
            "How many points the acquisition put on each peak: those at or "
            "above one per cent of its height. A Gaussian fit needs three; "
            "textbooks ask for about ten across the base. The last two "
            "columns are the cycle times that would give each for peaks of "
            "that width — a property of the schedule, not of the processing")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.table, "Control charts")
        self.tabs.addTab(self.precision, "Precision")
        self.tabs.addTab(self.sampling, "Sampling")
        body.addWidget(self.tabs)
        body.setSizes([520, 260])
        layout.addWidget(body, 1)

        self.status = QtWidgets.QLabel("Nothing measured yet.")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.component.currentTextChanged.connect(self._draw_selected)
        self.btn_refresh.clicked.connect(self.reload)
        self.btn_exclude.clicked.connect(self._exclude_failed)
        self.btn_floors.clicked.connect(self._suggest_floors)
        self.table.cellClicked.connect(self._on_row_clicked)
        session.sigResultsChanged.connect(self.reload)
        session.sigMethodChanged.connect(self.reload)

    # -- content ------------------------------------------------------------ #
    def reload(self, *_args) -> None:
        if not len(self.session.results):
            self._report = None
            self._sampling = None
            self._clear()
            self.sampling.setRowCount(0)
            self.status.setText("Process the batch to see how it held up.")
            return
        self._report = batch_qc(self.session.results, self.session.entries,
                                self.session.method)
        self._fill_table()
        self._fill_precision()
        self._fill_sampling()
        self.btn_exclude.setEnabled(bool(failed_injections(self._report)))
        self.btn_floors.setEnabled(bool(self._report.charts))
        self._reload_components()
        self._describe()

    def _reload_components(self) -> None:
        previous = self.component.currentText()
        self.component.blockSignals(True)
        self.component.clear()
        self.component.addItems([c.component for c in self._charts()])
        index = self.component.findText(previous)
        self.component.setCurrentIndex(max(index, 0))
        self.component.blockSignals(False)
        self._draw_selected()

    def _exclude_failed(self) -> None:
        if self._report is None:
            return
        failed = failed_injections(self._report)
        if not failed:
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Exclude failed injections",
            f"Take every result of {len(failed)} injection(s) out of the "
            f"statistics?\n\n" + ", ".join(failed)
            + "\n\nEach row is marked with the reason and can be put back "
              "from the results table.")
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        changed = exclude_failed(self.session.results, self.session.entries,
                                 self._report)
        self.session.notify_results_changed()
        self.status.setText(f"{changed:,} result(s) excluded, from "
                            f"{len(failed)} injection(s).")

    def _suggest_floors(self) -> None:
        from ..qc import suggest_floors
        from .floor_dialog import FloorDialog

        if self._report is None:
            return
        proposals = suggest_floors(self.session.results, self.session.entries,
                                   self.session.method, self._report)
        if not proposals:
            self.status.setText("No internal standard to propose a floor for.")
            return
        dialog = FloorDialog(self.session, proposals, self)
        dialog.exec()
        if dialog.applied:
            self.status.setText(f"{dialog.applied} floor(s) written into the "
                                f"method; the charts read them now.")

    def _describe(self) -> None:
        report = self._report
        if report is None:
            return
        sparse = self._sampling.sparse if self._sampling else []
        if report.note:
            said = [report.note]
            if sparse:
                said.append(f"{len(sparse)} component(s) with fewer than three "
                            f"points on the peak — see Sampling")
            self.status.setText(" · ".join(said))
            return
        said = [f"{report.injections} injection(s)"]
        said.append("in acquisition order" if report.ordered else
                    f"in the order opened — only {report.timed} of "
                    f"{report.injections} carry an acquisition time, so the "
                    f"sequence is a guess")
        if report.drifted:
            said.append(f"{len(report.drifted)} drifting")
        if report.unusable:
            said.append(f"{len(report.unusable)} standard(s) cannot normalise")
        stray = sum(len(chart.out) for chart in report.out
                    if not chart.unusable)
        if stray:
            said.append(f"{stray} injection(s) outside their limits")
        if report.index is not None and report.index.out:
            said.append(f"{len(report.index.out)} injection(s) where every "
                        f"standard went together")
        if report.imprecise:
            said.append(f"{len(report.imprecise)} component(s) over the %CV limit")
        quiet = [c for c in report.charts if not c.quantifiable]
        floored = [c for c in quiet if c.floor is not None]
        if floored:
            said.append(f"{len(floored)} below the floor the method declares")
        if len(quiet) > len(floored):
            said.append(f"{len(quiet) - len(floored)} below S/N {MIN_SNR:g}")
        if sparse:
            said.append(f"{len(sparse)} component(s) with fewer than three "
                        f"points on the peak — see Sampling")
        if (not report.drifted and not stray and not report.imprecise
                and not quiet and not report.unusable):
            said.append("nothing outside its limits")
        self.status.setText(" · ".join(said))

    def _charts(self) -> list:
        """The index first: it is what an injection failure shows up in."""
        if not self._report:
            return []
        index = [self._report.index] if self._report.index is not None else []
        return index + list(self._report.charts)

    def _fill_table(self) -> None:
        charts = self._charts()
        self.table.setRowCount(len(charts))
        for row, chart in enumerate(charts):
            snr = f"{chart.snr:,.0f}" if chart.snr is not None else "—"
            cells = [chart.component, f"{len(chart.injections):,}"]
            if chart.measurable:
                cells += [f"{chart.centre:,.1f}", f"{chart.sigma:,.1f}", snr,
                          f"{chart.drift:,.1f}" if chart.drift is not None else "—",
                          f"{chart.correlation:.3f}"
                          if chart.correlation is not None else "—",
                          self._verdict(chart)]
            else:
                cells += ["—", "—", snr, "—", "—",
                          chart.note or "not measurable"]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column in (1, 2, 3, 4, 5, 6):
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 7 and (chart.drifted or chart.out):
                    item.setForeground(pg.mkColor(theme.danger()))
                self.table.setItem(row, column, item)
        self.table.setColumnWidth(0, 160)

    def _fill_sampling(self) -> None:
        from ..sampling import sampling_report

        self._sampling = sampling_report(self.session.results, self.session.entries,
                                         self.session.method)
        rows = sorted(self._sampling.measured, key=lambda r: (r.points, -r.found))
        self.sampling.setRowCount(len(rows))

        def number(value, decimals=1):
            return "—" if value is None else f"{value:,.{decimals}f}"

        for index, row in enumerate(rows):
            cells = [row.component + (" (IS)" if row.is_internal_standard else ""),
                     f"{row.found:,}", number(row.cycle), number(row.width),
                     number(row.points, 0),
                     f"{row.sparse} ({row.sparse_share:.0%})" if row.found else "—",
                     number(row.cycle_for_fit), number(row.cycle_for_base),
                     f"{row.unmeasured}"]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column in (0, 4) and row.too_sparse:
                    item.setForeground(pg.mkColor(theme.danger()))
                self.sampling.setItem(index, column, item)
        self.sampling.setColumnWidth(0, 200)
        self.sampling.setToolTip(self._sampling.summary())

    def _fill_precision(self) -> None:
        rows = [row for row in (self._report.precision if self._report else [])
                if row.measurable]
        rows.sort(key=lambda r: -(r.percent_cv or 0.0))
        self.precision.setRowCount(len(rows))
        for index, row in enumerate(rows):
            cells = [row.component, f"{row.replicates:,}", f"{row.mean:,.1f}",
                     f"{row.percent_cv:,.2f}"]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 3 and row.fails:
                    item.setForeground(pg.mkColor(theme.danger()))
                self.precision.setItem(index, column, item)
        self.precision.setColumnWidth(0, 200)

    @staticmethod
    def _verdict(chart: ControlChart) -> str:
        if not chart.quantifiable:
            return f"below S/N {MIN_SNR:g} — not quantified, so not flagged"
        if chart.unusable:
            return (f"cannot normalise: {len(chart.out)} of "
                    f"{len(chart.injections)} injections over "
                    f"{ALWAYS_OUT_PERCENT:g}% from the centre")
        said = []
        if chart.drifted:
            said.append(f"drift {chart.drift:+,.0f}%")
        if chart.out:
            said.append(f"{len(chart.out)} outside {OUTLIER_SIGMA:g}σ")
        if chart.excess_warnings:
            said.append(f"{len(chart.warned)} beyond {WARN_SIGMA:g}σ")
        if said:
            return "; ".join(said)
        return chart.note or "steady"

    # -- the chart ----------------------------------------------------------- #
    def _clear(self) -> None:
        self._scatter.setData([])
        self._trend.setData([], [])
        for line in self._lines:
            self.plot.removeItem(line)
        self._lines.clear()
        self.table.setRowCount(0)
        self.precision.setRowCount(0)
        self._keys = []

    def _draw_selected(self, *_args) -> None:
        name = self.component.currentText()
        chart = next((c for c in self._charts() if c.component == name), None)
        self._chart = chart
        self._clear()
        self._fill_table()
        if chart is None or not chart.injections:
            return

        self._keys = [point.sample for point in chart.injections]
        spots = []
        for index, point in enumerate(chart.injections):
            brush = POINT
            if point.out:
                brush = POINT_OUT
            elif point.warned:
                brush = POINT_WARN
            spots.append({"pos": (point.order, point.value),
                          "brush": pg.mkBrush(brush), "data": index})
        self._scatter.setData(spots)
        self.plot.setLabel("left", f"{name} response")

        if not chart.measurable or not chart.sigma:
            return
        # the centre and its limits, drawn rather than described: a point
        # three quarters of the way to the line is the thing worth seeing,
        # and no table shows that
        self._line_at(chart.centre, CENTRE_PEN, 1.4, QtCore.Qt.PenStyle.SolidLine)
        # the three-sigma line is the one a decision hangs on, so it is the
        # one drawn to be seen; two sigma is a hint and is drawn like one
        for sigma, pen, width, style in (
                (WARN_SIGMA, theme.muted(), 1.0, QtCore.Qt.PenStyle.DotLine),
                (OUTLIER_SIGMA, POINT_OUT, 1.2, QtCore.Qt.PenStyle.DashLine)):
            for sign in (1, -1):
                self._line_at(chart.centre + sign * sigma * chart.sigma,
                              pen, width, style)
        if chart.drifted:
            order = np.array([p.order for p in chart.injections], dtype=float)
            values = np.array([p.value for p in chart.injections], dtype=float)
            fit = np.polyfit(order, values, 1)
            self._trend.setData(order, np.polyval(fit, order))

    def _line_at(self, y: float, colour: str, width: float, style) -> None:
        line = pg.InfiniteLine(pos=y, angle=0,
                               pen=pg.mkPen(colour, width=width, style=style))
        self.plot.addItem(line)
        self._lines.append(line)

    # -- interaction --------------------------------------------------------- #
    def _on_row_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.component.setCurrentText(item.text())

    def _on_point_clicked(self, _scatter, spots) -> None:
        if not spots or self._chart is None:
            return
        index = spots[0].data()
        if not isinstance(index, int) or not 0 <= index < len(self._chart.injections):
            return
        point = self._chart.injections[index]
        entry = next((e for e in self.session.entries if e.name == point.sample),
                     None)
        if entry is not None:
            self.sigSampleActivated.emit(entry.key)
