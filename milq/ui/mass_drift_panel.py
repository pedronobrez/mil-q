"""
The mass axis through the run: each standard's measured mass, injection by
injection, and all of them together.

Nothing is measured until asked. Reading the survey spectrum of every
standard in every injection is a minute's work on a real batch, and a tab
that does that on every change to the results would be a tab nobody keeps
open.
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from . import theme
from ..mass_drift import DRIFT_PPM, MassDrift, MassTrend, mass_drift
from ..recalibrate import describe as describe_corrections
from ..recalibrate import MAX_LOCK_ERROR_PPM, fit_batch, lock_mass_refusal
from ..session import Session
from .flow_layout import FlowLayout

TREND_PEN = "#e08a1e"


class MassDriftPanel(QtWidgets.QWidget):
    """Measure on request; then a chart per component and a table of all."""

    sigSampleActivated = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._keys: list[str] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        bar.addWidget(QtWidgets.QLabel("Component"))
        self.component = QtWidgets.QComboBox()
        self.component.setToolTip(
            "The index first: every standard's deviation taken together, "
            "which is the instrument rather than any one compound")
        bar.addWidget(self.component, 1)
        self.btn_measure = QtWidgets.QPushButton("Measure")
        self.btn_measure.setToolTip(
            "Read every internal standard's precursor from the survey scan "
            "in every injection, in the order the instrument ran them, and "
            "fit the change. Takes a minute on a real batch, which is why it "
            "waits to be asked")
        bar.addWidget(self.btn_measure)
        self.recalibrate = QtWidgets.QCheckBox(
            "Recalibrate m/z from the internal standards")
        self.recalibrate.setToolTip(
            "Correct every mass by the offset the lock masses show in that "
            "injection. A lock mass is an internal standard carrying a "
            "formula and an adduct — the written precursor is not accurate "
            "enough to correct towards — whose measured ion held together "
            "across the run and sat within "
            f"{MAX_LOCK_ERROR_PPM:g} ppm of what that formula weighs. A "
            "standard further out than that is a different ion, however "
            "steadily it was measured. The correction moves the extraction "
            "window, never the instrument's own arithmetic.")
        bar.addWidget(self.recalibrate)
        bar.addStretch(1)
        layout.addLayout(bar)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Injection")
        self.plot.setLabel("left", "ppm from the run's median")
        self.plot.setToolTip(
            f"Dashed lines at ±{DRIFT_PPM:g} ppm. A run is called "
            f"drifting when the fitted change across it is at least that and "
            f"goes one way")
        theme.style_axes(self.plot)
        self._lines: list[pg.InfiniteLine] = []
        self._trend = self.plot.plot([], [], pen=pg.mkPen(
            TREND_PEN, width=1.2, style=QtCore.Qt.PenStyle.DashLine))
        self._scatter = pg.ScatterPlotItem(size=9, pen=pg.mkPen(theme.axis()))
        self._scatter.sigClicked.connect(self._on_point_clicked)
        self.plot.addItem(self._scatter)
        body.addWidget(self.plot)

        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Component", "n", "Median m/z", "Exact m/z", "Error ppm",
             "Spread ppm", "Change ppm", "ρ", "Verdict"])
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Click a row to chart that component")
        body.addWidget(self.table)

        self.corrections = QtWidgets.QTableWidget(0, 9)
        self.corrections.setHorizontalHeaderLabels(
            ["Injection", "Source", "Lock masses", "Offset ppm",
             "Slope ppm/kDa", "Median before", "Median after", "Worst after",
             "Verdict"])
        self.corrections.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.corrections.verticalHeader().setDefaultSectionSize(20)
        self.corrections.horizontalHeader().setStretchLastSection(True)
        self.corrections.setToolTip(
            "The correction fitted for each injection, and what the lock "
            "masses' own residuals were before and after it. One lock mass "
            "leaves no residual to show: the offset takes it to zero by "
            "construction, which is why the verdict names the count. A "
            "direct infusion has no second injection to be read against and "
            "is fitted from its own precursor ladder instead, which is what "
            "the Source column says.")
        body.addWidget(self.corrections)
        body.setSizes([380, 220])
        layout.addWidget(body, 1)

        self.status = QtWidgets.QLabel("Not measured yet — press Measure.")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.correction_status = QtWidgets.QLabel(describe_corrections({}))
        self.correction_status.setProperty("role", "caption")
        self.correction_status.setWordWrap(True)
        layout.addWidget(self.correction_status)

        self.component.currentTextChanged.connect(self._draw_selected)
        self.btn_measure.clicked.connect(self.measure)
        self.recalibrate.toggled.connect(self._on_recalibrate_toggled)
        self.table.cellClicked.connect(self._on_row_clicked)
        session.sigSamplesChanged.connect(self._invalidate)

        from .help_window import describe
        describe(self.corrections, "mass-recalibration")
        describe(self.recalibrate, "mass-recalibration")
        self._sync_switch()

    # -- measuring ------------------------------------------------------------ #
    def measure(self) -> None:
        method = self.session.method
        if not any(c.is_internal_standard for c in method.components):
            self.status.setText("Mark an internal standard in the method first: "
                                "it is in every injection, so it can be measured "
                                "in every one.")
            return
        loaded = self.session.loaded_entries
        if not loaded:
            self.status.setText("Open the batch first.")
            return
        dialog = QtWidgets.QProgressDialog("Measuring…", "Cancel", 0, 100, self)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)

        def report(done: int, total: int) -> bool:
            dialog.setMaximum(total)
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        result = mass_drift(self.session.entries, method, progress=report)
        dialog.reset()
        if result is None:
            self.status.setText("Measurement cancelled.")
            return
        self.session.mass_drift = result
        # the fit is free once the measurement exists, and a checkbox with
        # nothing behind it would be a switch that does nothing without
        # saying why
        self.session.mass_corrections = fit_batch(self.session, result)
        self.session.cache.clear()
        self.reload()

    def _invalidate(self) -> None:
        self.session.mass_drift = None
        self.session.mass_corrections = {}
        self.session.cache.clear()
        self.reload()

    # -- the switch ----------------------------------------------------------- #
    def _sync_switch(self) -> None:
        self.recalibrate.blockSignals(True)
        self.recalibrate.setChecked(bool(self.session.recalibrate))
        self.recalibrate.blockSignals(False)
        usable = any(c.usable for c in self.session.mass_corrections.values())
        self.recalibrate.setEnabled(usable or self.session.recalibrate)

    def _on_recalibrate_toggled(self, on: bool) -> None:
        self.session.set_recalibrate(on)
        if self.session.results.results:
            self.correction_status.setText(
                describe_corrections(self.session.mass_corrections)
                + " · process the batch again for the results to follow")

    # -- content -------------------------------------------------------------- #
    def reload(self) -> None:
        drift = self.session.mass_drift
        self._clear()
        self._sync_switch()
        self.correction_status.setText(
            describe_corrections(self.session.mass_corrections))
        # before the drift check: an infusion's correction is fitted from its
        # own precursor ladder when the Explorer averages it, with no drift
        # measurement anywhere, and a row that only appeared after Measure
        # was pressed would be a correction in force with nothing showing it
        self._fill_corrections()
        if drift is None:
            self.status.setText("Not measured yet — press Measure.")
            self.component.clear()
            return
        self._fill_table()
        previous = self.component.currentText()
        self.component.blockSignals(True)
        self.component.clear()
        self.component.addItems([t.component for t in self._trends()])
        index = self.component.findText(previous)
        self.component.setCurrentIndex(max(index, 0))
        self.component.blockSignals(False)
        self._draw_selected()
        self._describe()

    def _trends(self) -> list[MassTrend]:
        drift = self.session.mass_drift
        if drift is None:
            return []
        index = [drift.index] if drift.index is not None else []
        return index + list(drift.trends)

    def _describe(self) -> None:
        drift: MassDrift = self.session.mass_drift
        if drift.note:
            self.status.setText(drift.note)
            return
        said = [f"{drift.injections} injection(s)"]
        said.append("in acquisition order" if drift.ordered else
                    f"in the order opened — only {drift.timed} of "
                    f"{drift.injections} carry an acquisition time")
        measured = drift.measured
        said.append(f"{len(measured)} of {len(drift.trends)} component(s) "
                    f"measured in enough injections")
        if drift.drifted:
            said.append(f"{len(drift.drifted)} drifting by {DRIFT_PPM:g} ppm or more")
        if drift.index is not None and drift.index.drifted:
            said.append(f"the axis itself moved {drift.index.change:+.1f} ppm "
                        f"across the run")
        elif drift.index is not None and drift.index.measurable:
            said.append(f"the axis held: {drift.index.change:+.1f} ppm across the run")
        if measured and not drift.drifted:
            said.append("nothing drifted")
        refused = sum(1 for trend in drift.trends if lock_mass_refusal(trend))
        if refused:
            said.append(f"{refused} measuring an ion its formula does not name")
        self.status.setText(" · ".join(said))

    def _fill_table(self) -> None:
        trends = self._trends()
        self.table.setRowCount(len(trends))

        def number(value, decimals=1):
            return "—" if value is None else f"{value:,.{decimals}f}"

        for row, trend in enumerate(trends):
            is_index = trend.median == 0.0 and trend.exact is None and trend.nominal == 0.0
            verdict = trend.note or "steady"
            if trend.drifted:
                verdict = f"drift {trend.change:+.1f} ppm"
            # not a lock mass, and for a reason the drift itself cannot see:
            # the injections agree with each other about the wrong ion
            refusal = lock_mass_refusal(trend)
            if refusal:
                verdict = f"{verdict} \u00b7 {refusal}"
            cells = [trend.component, f"{len(trend.points)}",
                     "—" if is_index else number(trend.median, 4),
                     number(trend.exact, 4), number(trend.error_ppm),
                     number(trend.spread_ppm), number(trend.change),
                     number(trend.correlation, 3), verdict]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 8:
                    # the cell elides; the whole sentence is worth reading
                    item.setToolTip(text)
                    if trend.drifted or refusal:
                        item.setForeground(pg.mkColor(theme.danger()))
                self.table.setItem(row, column, item)
        self.table.setColumnWidth(0, 180)

    def _draw_selected(self, *_args) -> None:
        name = self.component.currentText()
        trend = next((t for t in self._trends() if t.component == name), None)
        self._clear_plot()
        if trend is None or not trend.points:
            return
        xs = [point.order for point in trend.points]
        ys = [point.ppm for point in trend.points]
        self._keys = [point.sample for point in trend.points]
        brushes = [pg.mkBrush(theme.danger() if abs(y) >= DRIFT_PPM else theme.accent())
                   for y in ys]
        self._scatter.setData(xs, ys, brush=brushes, data=self._keys)
        for level, style in ((0.0, QtCore.Qt.PenStyle.SolidLine),
                             (DRIFT_PPM, QtCore.Qt.PenStyle.DashLine),
                             (-DRIFT_PPM, QtCore.Qt.PenStyle.DashLine)):
            line = pg.InfiniteLine(level, angle=0,
                                   pen=pg.mkPen(theme.axis(), width=1, style=style))
            self.plot.addItem(line)
            self._lines.append(line)
        if trend.change is not None and len(xs) > 1:
            first, last = min(xs), max(xs)
            centre = sum(ys) / len(ys)
            self._trend.setData([first, last],
                                [centre - trend.change / 2, centre + trend.change / 2])
        self.plot.setTitle(f"{trend.component} — {trend.note or 'ppm from the median'}",
                           size="9pt", color=theme.foreground())

    def _clear_plot(self) -> None:
        self._scatter.setData([])
        self._trend.setData([], [])
        for line in self._lines:
            self.plot.removeItem(line)
        self._lines.clear()
        self._keys = []

    def _fill_corrections(self) -> None:
        """One row per injection, in the order the batch is held."""
        corrections = self.session.mass_corrections
        rows = [corrections[e.key] for e in self.session.entries
                if e.key in corrections]
        self.corrections.setRowCount(len(rows))

        def number(value, decimals=1):
            return "—" if value is None else f"{value:,.{decimals}f}"

        for row, correction in enumerate(rows):
            cells = [correction.sample_name, correction.source,
                     f"{len(correction.lock_masses)}",
                     number(correction.offset_ppm) if correction.usable else "—",
                     number(correction.slope_ppm_per_da * 1000, 2)
                     if correction.linear else "—",
                     number(correction.median_before),
                     number(correction.median_after),
                     number(correction.worst_after),
                     correction.verdict]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column in (2, 3, 4, 5, 6, 7):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 8:
                    # the cell elides and the reason is the whole of it
                    item.setToolTip(correction.note or text)
                    if not correction.usable:
                        item.setForeground(pg.mkColor(theme.axis()))
                self.corrections.setItem(row, column, item)
        self.corrections.setColumnWidth(0, 180)

    def _clear(self) -> None:
        self._clear_plot()
        self.table.setRowCount(0)
        self.corrections.setRowCount(0)

    # -- linking -------------------------------------------------------------- #
    def _on_row_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.component.setCurrentText(item.text())

    def _on_point_clicked(self, _plot, points) -> None:
        if points:
            name = points[0].data()
            entry = next((e for e in self.session.entries if e.name == name), None)
            if entry is not None:
                self.sigSampleActivated.emit(entry.key)
