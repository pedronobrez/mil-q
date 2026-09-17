"""
The batch integrated every way, side by side.

A table of components says how far each algorithm's areas sit from the
reference and how well each repeated itself; a panel underneath draws one
sample's trace with every algorithm's integration on it, because a number
that says two algorithms disagree by forty per cent is only the start — the
reader wants to see which one is looking at the peak.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from ..compare import SENSITIVE_PERCENT, Comparison
from ..processing import ALGORITHM_LABELS, GaussianModel
from ..quantify import extract_xic
from ..session import Session

#: one colour per algorithm, in the order they are compared
COLOURS = ("#1f77b4", "#2ca02c", "#e08a1e", "#9467bd", "#8c564b")
ROLE_NAME = QtCore.Qt.ItemDataRole.UserRole


def _cell(text: str, right: bool = False, data=None) -> QtWidgets.QTableWidgetItem:
    item = QtWidgets.QTableWidgetItem(text)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    if right:
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                              | QtCore.Qt.AlignmentFlag.AlignVCenter)
    if data is not None:
        item.setData(ROLE_NAME, data)
    return item


class _NumericItem(QtWidgets.QTableWidgetItem):
    """Sorts by the number it carries rather than by its text."""

    def __lt__(self, other):
        mine = self.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        theirs = other.data(QtCore.Qt.ItemDataRole.UserRole + 1)
        if mine is None:
            return theirs is not None
        if theirs is None:
            return False
        return mine < theirs


def _numeric(value: float | None, decimals: int = 1) -> _NumericItem:
    item = _NumericItem("—" if value is None else f"{value:,.{decimals}f}")
    item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, value)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


class ComparisonDialog(QtWidgets.QDialog):
    """Show a comparison, and offer to adopt one of its algorithms."""

    sigAdopt = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, comparison: Comparison, parent=None):
        super().__init__(parent)
        self.session = session
        self.comparison = comparison
        self.setWindowTitle("Integration algorithms compared")
        self.resize(1180, 760)
        self.colours = {name: COLOURS[i % len(COLOURS)]
                        for i, name in enumerate(comparison.algorithms)}

        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel(comparison.summary())
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        legend = QtWidgets.QLabel(
            f"Δ is the median over the rows both algorithms found of "
            f"|area − reference area| / reference area. A component whose Δ "
            f"passes {SENSITIVE_PERCENT:.0f}% is marked: its number depends "
            f"on the decision as much as on the sample. %CV is the scatter "
            f"over the rows that were meant to agree — every spiked "
            f"injection for an internal standard, the quality controls for "
            f"an analyte — and is the one figure that can call an algorithm "
            f"better rather than different: same files, same noise, only "
            f"the arithmetic changed.")
        legend.setWordWrap(True)
        legend.setProperty("role", "hint")
        layout.addWidget(legend)

        # the component table is a dozen columns wide, so it gets the whole
        # width; the one-sample picture and its rows share the space below
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.components = QtWidgets.QTableWidget()
        self.components.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.components.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.components.setSortingEnabled(True)
        self.components.verticalHeader().hide()
        splitter.addWidget(self.components)

        below = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setMenuEnabled(False)
        theme.style_axes(self.plot, faint=True, tick_points=8)
        self.plot.addLegend(offset=(-10, 10))
        below.addWidget(self.plot)
        self.samples = QtWidgets.QTableWidget()
        self.samples.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.samples.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.samples.verticalHeader().hide()
        below.addWidget(self.samples)
        below.setStretchFactor(0, 1)
        below.setStretchFactor(1, 1)
        splitter.addWidget(below)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(QtWidgets.QLabel("Integrate the batch with"))
        self.choice = QtWidgets.QComboBox()
        for name in comparison.algorithms:
            self.choice.addItem(ALGORITHM_LABELS.get(name, name), name)
        buttons.addWidget(self.choice)
        self.btn_adopt = QtWidgets.QPushButton("Adopt and reprocess")
        self.btn_adopt.setToolTip(
            "Set this algorithm on the method — its defaults and every "
            "component's own settings — and integrate the batch again with "
            "it. Rows integrated by hand are kept")
        buttons.addWidget(self.btn_adopt)
        buttons.addStretch(1)
        self.btn_help = QtWidgets.QPushButton("Help")
        buttons.addWidget(self.btn_help)
        self.btn_close = QtWidgets.QPushButton("Close")
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

        self.btn_close.clicked.connect(self.close)
        from .help_window import describe, open_manual
        describe(self, "compare-algorithms")
        self.btn_help.clicked.connect(lambda: open_manual(self, "compare-algorithms"))
        self.btn_adopt.clicked.connect(
            lambda: self.sigAdopt.emit(self.choice.currentData()))
        self.components.itemSelectionChanged.connect(self._component_changed)
        self.samples.itemSelectionChanged.connect(self._sample_changed)

        self._fill_components()
        if self.components.rowCount():
            self.components.selectRow(0)

    # -- components ------------------------------------------------------------- #
    def _fill_components(self) -> None:
        comparison = self.comparison
        algorithms = comparison.algorithms
        others = [a for a in algorithms if a != comparison.reference]
        headers = ["Component"]
        headers += [f"Found\n{ALGORITHM_LABELS.get(a, a)}" for a in algorithms]
        headers += [f"Δ median %\n{ALGORITHM_LABELS.get(a, a)}" for a in others]
        headers += [f"Δ max %\n{ALGORITHM_LABELS.get(a, a)}" for a in others]
        headers += [f"%CV\n{ALGORITHM_LABELS.get(a, a)}" for a in algorithms]
        headers += ["Note"]

        table = self.components
        table.setSortingEnabled(False)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(comparison.components))
        marked = QtGui.QColor(230, 150, 40, 60)
        for row, item in enumerate(comparison.components):
            label = item.component + (" (IS)" if item.is_internal_standard else "")
            table.setItem(row, 0, _cell(label, data=item.component))
            column = 1
            for algorithm in algorithms:
                figures = item.figures[algorithm]
                text = f"{figures.found}/{figures.total}"
                if figures.fallbacks:
                    text += f" ({figures.fallbacks} fell back)"
                table.setItem(row, column, _cell(text, right=True))
                column += 1
            for algorithm in others:
                delta = item.deltas[algorithm]
                cell = _numeric(delta.median_percent)
                if delta.sensitive:
                    cell.setBackground(marked)
                table.setItem(row, column, cell)
                column += 1
            for algorithm in others:
                table.setItem(row, column, _numeric(item.deltas[algorithm].max_percent))
                column += 1
            for algorithm in algorithms:
                figures = item.figures[algorithm]
                cell = _numeric(figures.precision)
                if figures.precision is not None:
                    cell.setToolTip(f"over {figures.replicates} replicate(s)")
                table.setItem(row, column, cell)
                column += 1
            notes = []
            for algorithm in others:
                delta = item.deltas[algorithm]
                if delta.only_other:
                    notes.append(f"{delta.only_other} found only by "
                                 f"{ALGORITHM_LABELS.get(algorithm, algorithm).lower()}")
                if delta.only_reference:
                    notes.append(f"{delta.only_reference} lost by "
                                 f"{ALGORITHM_LABELS.get(algorithm, algorithm).lower()}")
            table.setItem(row, column, _cell("; ".join(notes)))
        table.resizeColumnsToContents()
        table.setSortingEnabled(True)

    def _selected_component(self) -> str | None:
        rows = self.components.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.components.item(rows[0].row(), 0)
        return item.data(ROLE_NAME) if item else None

    def _component_changed(self) -> None:
        name = self._selected_component()
        self.samples.clearContents()
        self.samples.setRowCount(0)
        if name is None:
            return
        algorithms = self.comparison.algorithms
        headers = ["Sample"]
        for algorithm in algorithms:
            label = ALGORITHM_LABELS.get(algorithm, algorithm)
            headers += [f"Area\n{label}", f"RT\n{label}"]
        headers.append("Notes")
        self.samples.setColumnCount(len(headers))
        self.samples.setHorizontalHeaderLabels(headers)
        reference = self.comparison.results[self.comparison.reference]
        rows = reference.for_component(name)
        self.samples.setRowCount(len(rows))
        for row, base in enumerate(rows):
            self.samples.setItem(row, 0, _cell(base.sample_name, data=base.sample_key))
            column = 1
            notes = []
            for algorithm in algorithms:
                result = self.comparison.results[algorithm].get(base.sample_key, name)
                if result is not None and result.found:
                    self.samples.setItem(row, column, _numeric(result.area, 0))
                    self.samples.setItem(row, column + 1, _numeric(result.rt, 3))
                else:
                    self.samples.setItem(row, column, _cell("—", right=True))
                    self.samples.setItem(row, column + 1, _cell("—", right=True))
                if result is not None and result.note:
                    notes.append(f"{ALGORITHM_LABELS.get(algorithm, algorithm)}: "
                                 f"{result.note}")
                column += 2
            self.samples.setItem(row, column, _cell("; ".join(notes)))
        self.samples.resizeColumnsToContents()
        if rows:
            self.samples.selectRow(0)
        else:
            self.plot.clear()

    # -- one sample, every way ------------------------------------------------- #
    def _sample_changed(self) -> None:
        rows = self.samples.selectionModel().selectedRows()
        name = self._selected_component()
        if not rows or name is None:
            return
        item = self.samples.item(rows[0].row(), 0)
        if item is None:
            return
        self.draw(item.data(ROLE_NAME), name)

    def draw(self, sample_key: str, component_name: str) -> None:
        """One trace, with every algorithm's integration drawn on it."""
        plot = self.plot
        plot.clear()
        legend = plot.plotItem.legend
        if legend is not None:
            legend.clear()
        component = self.session.method.by_name(component_name)
        entry = self.session.entry_by_key(sample_key)
        if component is None or entry is None:
            return
        x, y, _channel = extract_xic(entry, component, self.session.method,
                                     self.session.cache,
                                     self.session.correction_for(sample_key))
        if x.size == 0:
            return
        plot.plot(x, y, pen=pg.mkPen(theme.foreground(), width=1.2), name="trace")
        window = component.rt_window()
        for algorithm in self.comparison.algorithms:
            result = self.comparison.results[algorithm].get(sample_key, component_name)
            colour = self.colours[algorithm]
            label = ALGORITHM_LABELS.get(algorithm, algorithm)
            if result is None or not result.found:
                continue
            inside = (x >= result.start_rt) & (x <= result.end_rt)
            if inside.sum() < 2:
                continue
            xs, ys = x[inside], y[inside]
            base = np.linspace(ys[0], ys[-1], xs.size)
            model = GaussianModel.from_dict(result.model)
            if model is None:
                top = plot.plot(xs, np.maximum(ys, base),
                                pen=pg.mkPen(colour, width=1.6),
                                name=f"{label}: {result.area:,.0f}")
                bottom = plot.plot(xs, base, pen=pg.mkPen(colour, width=1,
                                   style=QtCore.Qt.PenStyle.DashLine))
            else:
                reach = 3.0 * model.sigma
                dense = np.linspace(min(float(xs[0]), model.centre - reach),
                                    max(float(xs[-1]), model.centre + reach), 200)
                slope = ((base[-1] - base[0]) / (xs[-1] - xs[0])
                         if xs[-1] > xs[0] else 0.0)
                floor = base[0] + slope * (dense - xs[0])
                top = plot.plot(dense, model.evaluate(dense) + floor,
                                pen=pg.mkPen(colour, width=1.6),
                                name=f"{label}: {result.area:,.0f}  ({model.quality})")
                bottom = plot.plot(dense, floor, pen=pg.mkPen(colour, width=1,
                                   style=QtCore.Qt.PenStyle.DashLine))
            fill = QtGui.QColor(colour)
            fill.setAlpha(45)
            plot.addItem(pg.FillBetweenItem(top, bottom, brush=pg.mkBrush(fill)))
        if window is not None:
            band = pg.LinearRegionItem(window, brush=pg.mkBrush(120, 120, 200, 28),
                                       pen=pg.mkPen(None), movable=False)
            band.setZValue(-20)
            plot.addItem(band, ignoreBounds=True)
            span = window[1] - window[0]
            plot.setXRange(window[0] - span, window[1] + span, padding=0)
        plot.setTitle(f"{entry.name} — {component.label}", size="9pt",
                      color=theme.foreground())
