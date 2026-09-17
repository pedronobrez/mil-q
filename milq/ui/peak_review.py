"""
Peak review: one chromatogram per sample for the selected component.

This is the view MultiQuant is built around — the same analyte across the whole
batch at once, so an outlier stands out against its neighbours instead of
having to be hunted down sample by sample.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from ..processing import GaussianModel
from ..quantify import PeakResult
from .flow_layout import FlowLayout

FOUND_PEN = "#1f77b4"
#: a fitted curve, drawn over the points it was fitted to
MODEL_PEN = "#e08a1e"
#: how far past its boundaries a fitted curve is drawn, in sigmas
MODEL_REACH = 3.0
#: the integrated area. Blue, not green: green now marks a predicted fragment
#: found in a spectrum, and one colour cannot mean two things.
AREA_FILL = QtGui.QColor(35, 90, 175, 120)
AREA_EDGE = "#3b6ec8"
MISSING_PEN = "#b0b0b0"
IS_PEN = "#d62728"


class _PanelViewBox(pg.ViewBox):
    """ViewBox whose horizontal drag becomes a manual integration range."""

    sigRangeDrag = QtCore.pyqtSignal(float, float, bool)   # start, end, finished

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manual_mode = False

    def mouseDragEvent(self, ev, axis=None):
        shift = bool(ev.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        left = ev.button() == QtCore.Qt.MouseButton.LeftButton
        if left and (self.manual_mode or shift):
            ev.accept()
            start = float(self.mapToView(ev.buttonDownPos()).x())
            end = float(self.mapToView(ev.pos()).x())
            self.sigRangeDrag.emit(start, end, ev.isFinish())
            return
        super().mouseDragEvent(ev, axis)


class PeakPanel(pg.PlotWidget):
    """One sample's chromatogram, with its integrated peak shaded."""

    sigClicked = QtCore.pyqtSignal(str)        # sample key
    sigDoubleClicked = QtCore.pyqtSignal(str)
    sigManualRange = QtCore.pyqtSignal(str, float, float)   # key, start, end
    sigContextMenu = QtCore.pyqtSignal(str, object)         # key, global pos

    def __init__(self, parent=None):
        # `enableMenu=False` rather than `setMenuEnabled(False)` after the
        # fact: pyqtgraph builds the whole right-click menu in the ViewBox's
        # constructor, and building a menu nobody can open was 3 ms of the
        # 5.5 ms a panel cost — 64 panels' worth every time the grid's shape
        # changed.
        self.viewbox = _PanelViewBox(enableMenu=False)
        super().__init__(parent, background=theme.background(),
                         viewBox=self.viewbox)
        self.sample_key = ""
        self.showGrid(x=True, y=True, alpha=0.12)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.getAxis("left").setWidth(46)
        theme.style_axes(self, faint=True, tick_points=7)

        self._curve = self.plot([], [], pen=pg.mkPen(FOUND_PEN, width=1.3))
        self._is_curve = self.plot(
            [], [], pen=pg.mkPen(IS_PEN, width=1.0,
                                 style=QtCore.Qt.PenStyle.DashLine))
        self._is_curve.setZValue(-5)
        # the area actually integrated: the trace above the baseline drawn
        # between the limits. The band alone said where the limits were, which
        # a reader takes for the area — and on a peak a couple of points wide
        # the two look nothing alike.
        self._area_top = pg.PlotDataItem([], [])
        self._area_base = pg.PlotDataItem([], [])
        self._area = pg.FillBetweenItem(self._area_top, self._area_base,
                                        brush=pg.mkBrush(AREA_FILL))
        self._area.setZValue(-8)
        self.addItem(self._area)
        self._baseline = self.plot(
            [], [], pen=pg.mkPen(AREA_EDGE, width=1,
                                 style=QtCore.Qt.PenStyle.DashLine))
        self._baseline.setZValue(-7)
        # the fitted curve, when the area is a model's rather than the
        # trace's: the shading goes under the model, because that is the
        # number, and the trace stays on top so the two can be compared
        self._model = self.plot(
            [], [], pen=pg.mkPen(MODEL_PEN, width=1.4))
        self._model.setZValue(-6)
        self._band = pg.LinearRegionItem(brush=pg.mkBrush(0, 0, 0, 0),
                                         pen=pg.mkPen(AREA_EDGE, width=1),
                                         movable=False)
        self._band.setZValue(-10)
        self._band.hide()
        self.addItem(self._band, ignoreBounds=True)
        self._expected = pg.LinearRegionItem(brush=pg.mkBrush(120, 120, 200, 28),
                                             pen=pg.mkPen(None), movable=False)
        self._expected.setZValue(-20)
        self._expected.hide()
        self.addItem(self._expected, ignoreBounds=True)
        self._noise = pg.LinearRegionItem(brush=pg.mkBrush(150, 150, 150, 45),
                                          pen=pg.mkPen(theme.faint_axis(), width=1,
                                                       style=QtCore.Qt.PenStyle.DotLine),
                                          movable=False)
        self._noise.setZValue(-25)
        self._noise.hide()
        self.addItem(self._noise, ignoreBounds=True)
        self.viewbox.sigRangeDrag.connect(self._on_drag)
        self.set_selected(False)

    def _show_area(self, x: np.ndarray, y: np.ndarray,
                   start: float, end: float,
                   model: GaussianModel | None = None) -> None:
        """
        Shade what was integrated: the trace over its straight baseline, or
        the fitted curve over it when the area came from a fit.
        """
        inside = (x >= start) & (x <= end)
        if inside.sum() < 2:
            self._clear_area()
            return
        xs, ys = x[inside], y[inside]
        # the same baseline the integration used, so the picture and the
        # number cannot disagree
        base = np.linspace(ys[0], ys[-1], xs.size)
        self._baseline.setData(xs, base)
        if model is None:
            self._area_top.setData(xs, np.maximum(ys, base))
            self._area_base.setData(xs, base)
            self._model.setData([], [])
            return
        reach = MODEL_REACH * model.sigma
        lo = min(float(xs[0]), model.centre - reach)
        hi = max(float(xs[-1]), model.centre + reach)
        dense = np.linspace(lo, hi, 200)
        slope = (base[-1] - base[0]) / (xs[-1] - xs[0]) if xs[-1] > xs[0] else 0.0
        floor = base[0] + slope * (dense - xs[0])
        curve = model.evaluate(dense) + floor
        self._model.setData(dense, curve)
        self._area_top.setData(dense, curve)
        self._area_base.setData(dense, floor)

    def fence(self, x: np.ndarray, y: np.ndarray) -> None:
        """
        Keep the panel inside its own data, as the Explorer's plots are.

        Nothing lies outside a peak's trace, and a panel this small is easy to
        lose your place in.
        """
        box = self.getViewBox()
        if not len(x) or not len(y):
            box.setLimits(xMin=None, xMax=None, yMin=None, yMax=None,
                          maxXRange=None, maxYRange=None)
            return
        finite = np.isfinite(x) & np.isfinite(y)
        if not finite.any():
            return
        x_low, x_high = float(np.min(x[finite])), float(np.max(x[finite]))
        y_low = min(0.0, float(np.min(y[finite])))
        y_high = float(np.max(y[finite]))
        if x_high <= x_low or y_high <= y_low:
            return
        head_room = (y_high - y_low) * 0.08
        box.setLimits(xMin=x_low, xMax=x_high,
                      yMin=y_low, yMax=y_high + head_room,
                      maxXRange=x_high - x_low,
                      maxYRange=y_high - y_low + head_room)

    def _clear_area(self) -> None:
        self._area_top.setData([], [])
        self._area_base.setData([], [])
        self._baseline.setData([], [])
        self._model.setData([], [])

    def set_manual_mode(self, enabled: bool) -> None:
        self.viewbox.manual_mode = enabled
        self.setCursor(QtCore.Qt.CursorShape.SplitHCursor if enabled
                       else QtCore.Qt.CursorShape.ArrowCursor)

    def set_noise_region(self, region: tuple[float, float] | None) -> None:
        if region is None:
            self._noise.hide()
        else:
            self._noise.setRegion(region)
            self._noise.show()

    def _on_drag(self, start: float, end: float, finished: bool) -> None:
        if not self.sample_key or abs(end - start) <= 0:
            return
        self._band.setRegion(tuple(sorted((start, end))))
        self._band.show()
        if finished:
            self.sigManualRange.emit(self.sample_key, start, end)

    # -- content ---------------------------------------------------------------- #
    def clear_panel(self) -> None:
        self.sample_key = ""
        self._curve.setData([], [])
        self._is_curve.setData([], [])
        self._band.hide()
        self._expected.hide()
        self._clear_area()
        self.setTitle("")

    def set_data(self, result: PeakResult, x: np.ndarray, y: np.ndarray,
                 expected: tuple[float, float] | None,
                 internal_standard: tuple[np.ndarray, np.ndarray] | None = None) -> None:
        self.sample_key = result.sample_key
        found = result.found
        self._curve.setData(x, y, pen=pg.mkPen(FOUND_PEN if found else MISSING_PEN,
                                               width=1.3))
        self._set_internal_standard(y, internal_standard)
        if found:
            self._band.setRegion((result.start_rt, result.end_rt))
            self._band.show()
            self._show_area(x, y, result.start_rt, result.end_rt,
                            GaussianModel.from_dict(result.model))
        else:
            self._band.hide()
            self._clear_area()
        self.fence(x, y)
        if expected is not None:
            self._expected.setRegion(expected)
            self._expected.show()
        else:
            self._expected.hide()

        if found:
            manual = " ✎" if result.manual else ""
            ratio = f"{result.snr:,.0f}" if result.snr is not None else "—"
            title = (f"{result.sample_name}{manual}   {result.area:,.0f}"
                     f"   S/N {ratio}   {result.rt:.2f}")
            colour = theme.foreground()
        else:
            title = f"{result.sample_name}   {result.note or 'not found'}"
            colour = "#e06666" if theme.is_dark() else "#b03030"
        self.setTitle(title, color=colour, size="8pt")

    def _set_internal_standard(self, y: np.ndarray,
                               trace: tuple[np.ndarray, np.ndarray] | None) -> None:
        """
        Draw the internal standard behind the analyte, rescaled to it.

        The two rarely share a magnitude — a labelled standard is often far the
        taller — so plotting both on one axis would flatten the analyte. Only
        the shape and the retention time are being compared here, so the
        standard is normalised to the analyte's height.
        """
        if trace is None or trace[0].size == 0:
            self._is_curve.setData([], [])
            return
        is_x, is_y = trace
        peak = float(np.max(is_y)) if is_y.size else 0.0
        target = float(np.max(y)) if y.size else 0.0
        scale = target / peak if peak > 0 and target > 0 else 1.0
        self._is_curve.setData(is_x, is_y * scale)

    def integration_range(self) -> tuple[float, float] | None:
        """The range currently shaded on this panel, if any."""
        if not self._band.isVisible():
            return None
        lo, hi = self._band.getRegion()
        return float(lo), float(hi)

    def set_selected(self, selected: bool) -> None:
        self.setStyleSheet(
            f"border: 2px solid {theme.accent()}; border-radius: 6px;" if selected
            else f"border: 1px solid {theme.line()}; border-radius: 6px;"
        )

    # -- interaction -------------------------------------------------------------- #
    def mousePressEvent(self, event):
        if self.sample_key:
            self.sigClicked.emit(self.sample_key)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.sample_key:
            self.sigDoubleClicked.emit(self.sample_key)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self.sample_key:
            self.sigContextMenu.emit(self.sample_key, event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)


class PeakReviewGrid(QtWidgets.QWidget):
    """A page of peak panels, with the layout and paging controls."""

    sigSelected = QtCore.pyqtSignal(str)   # sample key
    sigMagnified = QtCore.pyqtSignal(str)
    sigManualRange = QtCore.pyqtSignal(str, float, float)
    sigContextMenu = QtCore.pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panels: list[PeakPanel] = []
        #: panels a smaller shape left over, kept for the next larger one
        self._spare: list[PeakPanel] = []
        self._items: list[tuple] = []   # (result, x, y, expected, is_trace)
        #: when set, items are fetched a page at a time instead of held here
        self._fetch = None
        self._total = 0
        self._page = 0
        self._selected = ""
        self._shared_y = False
        self._show_is = True
        self._manual_mode = False
        self._noise_region: tuple[float, float] | None = None
        self._margin = 3.0     # window widths shown on each side
        self._linked_x = True
        self._syncing = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        bar = FlowLayout()
        self.title = QtWidgets.QLabel("—")
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        bar.addWidget(self.title)
        bar.addStretch(1)
        self.col_spin = QtWidgets.QSpinBox()
        self.col_spin.setRange(1, 8)
        self.col_spin.setValue(3)
        bar.addPair("Columns", self.col_spin)
        self.row_spin = QtWidgets.QSpinBox()
        self.row_spin.setRange(1, 8)
        self.row_spin.setValue(2)
        bar.addPair("Rows", self.row_spin)
        bar.addSpacing(12)
        self.chk_manual = QtWidgets.QCheckBox("Manual")
        self.chk_manual.setToolTip(
            "Drag across a peak to integrate exactly that range "
            "(Shift + drag does the same at any time)")
        bar.addWidget(self.chk_manual)
        bar.addSpacing(12)
        self.chk_is = QtWidgets.QCheckBox("Show IS")
        self.chk_is.setChecked(True)
        self.chk_is.setToolTip(
            "Overlay the internal standard, rescaled to the analyte, so their "
            "retention times and shapes can be compared")
        bar.addWidget(self.chk_is)
        bar.addSpacing(12)
        self.chk_shared_y = QtWidgets.QCheckBox("Same Y")
        self.chk_shared_y.setToolTip(
            "One intensity scale for every panel, so heights compare directly")
        bar.addWidget(self.chk_shared_y)
        bar.addSpacing(12)
        self.zoom_combo = QtWidgets.QComboBox()
        self.zoom_combo.addItems(["Expected window", "Peak", "Whole run"])
        self.zoom_combo.setToolTip(
            "How much time each panel shows: the window the component is "
            "expected in, tight around the integrated peak, or everything")
        bar.addPair("Zoom", self.zoom_combo)
        bar.addSpacing(12)
        self.chk_link_x = QtWidgets.QCheckBox("Link X")
        self.chk_link_x.setChecked(True)
        self.chk_link_x.setToolTip("Zooming one panel zooms them all")
        bar.addWidget(self.chk_link_x)
        bar.addSpacing(12)
        self.btn_prev = QtWidgets.QToolButton()
        self.btn_prev.setText("◀")
        self.page_label = QtWidgets.QLabel("0/0")
        self.btn_next = QtWidgets.QToolButton()
        self.btn_next.setText("▶")
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.page_label)
        bar.addWidget(self.btn_next)
        layout.addLayout(bar)

        self.container = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        layout.addWidget(self.container, 1)

        self.col_spin.valueChanged.connect(self._relayout)
        self.row_spin.valueChanged.connect(self._relayout)
        self.chk_shared_y.toggled.connect(self._set_shared_y)
        self.chk_is.toggled.connect(self._set_show_is)
        self.chk_manual.toggled.connect(self.set_manual_mode)
        self.zoom_combo.currentIndexChanged.connect(lambda _i: self._fill())
        self.chk_link_x.toggled.connect(self._set_link_x)
        self.btn_prev.clicked.connect(lambda: self.set_page(self._page - 1))
        self.btn_next.clicked.connect(lambda: self.set_page(self._page + 1))
        self._relayout()

    # -- layout ------------------------------------------------------------------- #
    @property
    def views(self) -> list[PeakPanel]:
        return list(self._panels)

    @property
    def page_size(self) -> int:
        return self.col_spin.value() * self.row_spin.value()

    @property
    def item_count(self) -> int:
        return self._total if self._fetch is not None else len(self._items)

    @property
    def page_count(self) -> int:
        if not self.item_count:
            return 0
        return (self.item_count + self.page_size - 1) // self.page_size

    def _new_panel(self) -> PeakPanel:
        """One panel, wired to the grid."""
        panel = PeakPanel()
        panel.sigClicked.connect(self._on_panel_clicked)
        panel.sigDoubleClicked.connect(self.sigMagnified)
        panel.sigManualRange.connect(self.sigManualRange)
        panel.sigContextMenu.connect(self.sigContextMenu)
        panel.set_manual_mode(self._manual_mode)
        panel.getViewBox().sigXRangeChanged.connect(
            lambda _vb, rng, p=panel: self._link(p, rng))
        return panel

    def _relayout(self) -> None:
        """
        Re-place the panels for the current rows x columns, keeping them.

        A panel costs 5 ms to build — pyqtgraph's expense, not ours — so
        throwing all of them away and building `columns x rows` fresh ones
        took 0.52 s at 8 x 8, once per *step* of a spin box. The panels are
        interchangeable: `_fill` gives each one its data and clears the ones
        a short page does not reach, so a change of shape needs nothing but
        enough of them in the right cells.

        A panel the new shape does not need is kept, hidden and out of the
        layout, rather than deleted: both spin boxes stop at 8, so the pool
        cannot grow past 64 panels — about 14 MB — and going back to a shape
        already used costs nothing. It must be hidden before it is left out,
        because a child widget nobody is laying out keeps the geometry it had
        and would be drawn over the first cell.
        """
        columns, rows = self.col_spin.value(), self.row_spin.value()
        wanted = columns * rows

        while self.grid.count():           # detach, do not destroy
            self.grid.takeAt(0)
        while len(self._panels) > wanted:
            spare = self._panels.pop()
            spare.clear_panel()
            spare.hide()                   # out of the layout, still a child
            self._spare.append(spare)
        while len(self._panels) < wanted:
            self._panels.append(self._spare.pop() if self._spare
                                else self._new_panel())

        for index, panel in enumerate(self._panels):
            self.grid.addWidget(panel, index // columns, index % columns)
        self.set_page(self._page)

    def _link(self, source: PeakPanel, rng) -> None:
        if not self._linked_x or self._syncing:
            return
        self._syncing = True
        try:
            for panel in self._panels:
                if panel is not source and panel.sample_key:
                    panel.getViewBox().setXRange(rng[0], rng[1], padding=0)
        finally:
            self._syncing = False

    def _set_link_x(self, enabled: bool) -> None:
        self._linked_x = enabled

    def _set_shared_y(self, enabled: bool) -> None:
        self._shared_y = enabled
        self._fill()

    def _set_show_is(self, enabled: bool) -> None:
        self._show_is = enabled
        self._fill()

    def _show_area(self, x: np.ndarray, y: np.ndarray,
                   start: float, end: float,
                   model: GaussianModel | None = None) -> None:
        """
        Shade what was integrated: the trace over its straight baseline, or
        the fitted curve over it when the area came from a fit.
        """
        inside = (x >= start) & (x <= end)
        if inside.sum() < 2:
            self._clear_area()
            return
        xs, ys = x[inside], y[inside]
        # the same baseline the integration used, so the picture and the
        # number cannot disagree
        base = np.linspace(ys[0], ys[-1], xs.size)
        self._baseline.setData(xs, base)
        if model is None:
            self._area_top.setData(xs, np.maximum(ys, base))
            self._area_base.setData(xs, base)
            self._model.setData([], [])
            return
        reach = MODEL_REACH * model.sigma
        lo = min(float(xs[0]), model.centre - reach)
        hi = max(float(xs[-1]), model.centre + reach)
        dense = np.linspace(lo, hi, 200)
        slope = (base[-1] - base[0]) / (xs[-1] - xs[0]) if xs[-1] > xs[0] else 0.0
        floor = base[0] + slope * (dense - xs[0])
        curve = model.evaluate(dense) + floor
        self._model.setData(dense, curve)
        self._area_top.setData(dense, curve)
        self._area_base.setData(dense, floor)

    def fence(self, x: np.ndarray, y: np.ndarray) -> None:
        """
        Keep the panel inside its own data, as the Explorer's plots are.

        Nothing lies outside a peak's trace, and a panel this small is easy to
        lose your place in.
        """
        box = self.getViewBox()
        if not len(x) or not len(y):
            box.setLimits(xMin=None, xMax=None, yMin=None, yMax=None,
                          maxXRange=None, maxYRange=None)
            return
        finite = np.isfinite(x) & np.isfinite(y)
        if not finite.any():
            return
        x_low, x_high = float(np.min(x[finite])), float(np.max(x[finite]))
        y_low = min(0.0, float(np.min(y[finite])))
        y_high = float(np.max(y[finite]))
        if x_high <= x_low or y_high <= y_low:
            return
        head_room = (y_high - y_low) * 0.08
        box.setLimits(xMin=x_low, xMax=x_high,
                      yMin=y_low, yMax=y_high + head_room,
                      maxXRange=x_high - x_low,
                      maxYRange=y_high - y_low + head_room)

    def _clear_area(self) -> None:
        self._area_top.setData([], [])
        self._area_base.setData([], [])
        self._baseline.setData([], [])
        self._model.setData([], [])

    def set_manual_mode(self, enabled: bool) -> None:
        """Dragging inside a panel marks the integration range instead of panning."""
        self._manual_mode = enabled
        for panel in self._panels:
            panel.set_manual_mode(enabled)

    def set_noise_region(self, region: tuple[float, float] | None) -> None:
        self._noise_region = region
        for panel in self._panels:
            panel.set_noise_region(region)

    # -- content -------------------------------------------------------------------- #
    def set_items(self, title: str, items: list[tuple]) -> None:
        """
        `items` are (result, x, y, expected window, internal standard trace)
        tuples, one per sample; the last entry may be None.
        """
        self.title.setText(title)
        self._items = list(items)
        self._fetch = None
        self._total = 0
        self._page = 0
        self._fill()

    def set_lazy(self, title: str, total: int, fetch) -> None:
        """
        Show `total` peaks, asking `fetch(start, stop)` for a page at a time.

        Every peak of every component is 141 x 26 extractions on a real batch,
        about a hundred seconds of work to show nine of them. Only the page in
        view is built.
        """
        self.title.setText(title)
        self._items = []
        self._fetch = fetch
        self._total = int(total)
        self._page = 0
        self._fill()

    def clear(self) -> None:
        self.set_items("—", [])

    def set_page(self, page: int) -> None:
        self._page = int(np.clip(page, 0, max(self.page_count - 1, 0)))
        self._fill()

    def _fill(self) -> None:
        start = self._page * self.page_size
        if self._fetch is not None:
            page_items = self._fetch(start, start + self.page_size)
        else:
            page_items = self._items[start:start + self.page_size]

        ceiling = 0.0
        if self._shared_y:
            # a shared ceiling over a lazy source would mean building every
            # page, so it spans the page in view
            for item in (self._items or page_items):
                y = item[2]
                if y.size:
                    ceiling = max(ceiling, float(np.max(y)))

        for panel, item in zip(self._panels, page_items):
            result, x, y, expected = item[:4]
            is_trace = item[4] if len(item) > 4 and self._show_is else None
            panel.set_data(result, x, y, expected, is_trace)
            panel.set_noise_region(self._noise_region)
            panel.set_selected(result.sample_key == self._selected)
            panel.enableAutoRange()
            panel.autoRange()
            span = self._x_range(result, expected)
            if span is not None:
                panel.setXRange(*span, padding=0)
            if self._shared_y and ceiling > 0:
                panel.setYRange(0, ceiling * 1.05, padding=0)
            panel.show()
        for panel in self._panels[len(page_items):]:
            panel.clear_panel()
            panel.set_selected(False)
            panel.hide()

        self.page_label.setText(f"{self._page + 1}/{max(self.page_count, 1)}")
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._page + 1 < self.page_count)

    def _x_range(self, result, expected) -> tuple[float, float] | None:
        """
        The time span a panel shows.

        Defaulting to the whole run makes every peak a sliver: the point of the
        grid is comparing the same peak across samples, so the expected window
        is the useful default, with the run available when the peak has to be
        hunted down.
        """
        mode = self.zoom_combo.currentIndex()
        if mode == 2:
            return None
        if mode == 1 and result.found and result.end_rt > result.start_rt:
            width = result.end_rt - result.start_rt
            return result.start_rt - width, result.end_rt + width
        if expected is not None:
            width = max(expected[1] - expected[0], 1e-6)
            centre = (expected[0] + expected[1]) / 2
            half = width / 2 * (1 + self._margin)
            return centre - half, centre + half
        if result.found and result.end_rt > result.start_rt:
            width = result.end_rt - result.start_rt
            return result.start_rt - width, result.end_rt + width
        return None

    # -- selection --------------------------------------------------------------- #
    def _on_panel_clicked(self, sample_key: str) -> None:
        self.select(sample_key)
        self.sigSelected.emit(sample_key)

    def select(self, sample_key: str) -> None:
        """Highlight a sample, paging to it when it is not on screen."""
        self._selected = sample_key
        index = next((i for i, item in enumerate(self._items)
                      if item[0].sample_key == sample_key), None)
        if index is not None:
            page = index // self.page_size
            if page != self._page:
                self._page = page
                self._fill()
                return
        for panel in self._panels:
            panel.set_selected(panel.sample_key == sample_key)
