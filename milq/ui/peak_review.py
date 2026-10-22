"""
Peak review: one chromatogram per sample for the selected component.

This is the view MultiQuant is built around — the same analyte across the whole
batch at once, so an outlier stands out against its neighbours instead of
having to be hunted down sample by sample.
"""

from __future__ import annotations

import html

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

#: a panel's type as a share of the application's font. At a fixed 7 points
#: for the ticks and 8 for the title the panels read at half the size of the
#: results table under them — 13 points on a Mac — and the bottom axis was
#: measured for the small type while the title row was a fixed 30 pixels.
TITLE_SCALE = 0.92
TICK_SCALE = 0.85
#: a panel smaller than this (width, height in pixels) — an 8 x 8 grid, or a
#: grid squeezed by the splitter — steps its type down by `COMPACT_SCALE`
COMPACT_BELOW = (240, 160)
COMPACT_SCALE = 0.85
#: never below this, however small the panel: past it nothing is read at all
FONT_FLOOR_PT = 8.0
#: the least plot a panel keeps between its title and its time axis; below it
#: the axis's numbers go, rather than the trace
MIN_PLOT_PX = 28
#: between the fields of a panel's title
TITLE_GAP = "   "
#: the top of a panel's Y axis over the tallest point it shows
HEADROOM = 1.05


def panel_type(width: int, height: int,
               base: float | None = None) -> tuple[float, float]:
    """
    The title's and the ticks' point sizes for a panel of this size.

    Derived from the application's font rather than fixed, so a panel is read
    in the same type as the table beside it, a little smaller, and never
    below `FONT_FLOOR_PT`.
    """
    if base is None:
        app = QtWidgets.QApplication.instance()
        font = app.font() if app is not None else QtGui.QFont()
        base = font.pointSizeF()
        if base <= 0:            # a font sized in pixels has no point size
            base = font.pixelSize() * 0.75 if font.pixelSize() > 0 else 10.0
    scale = 1.0
    if width < COMPACT_BELOW[0] or height < COMPACT_BELOW[1]:
        scale = COMPACT_SCALE
    return (max(FONT_FLOOR_PT, base * TITLE_SCALE * scale),
            max(FONT_FLOOR_PT, base * TICK_SCALE * scale))


def _font(points: float) -> QtGui.QFont:
    # a QFont built from an empty family name crashes Qt when an axis measures
    # its tick labels, so start from the application's font
    app = QtWidgets.QApplication.instance()
    font = QtGui.QFont(app.font()) if app is not None else QtGui.QFont()
    font.setPointSizeF(points)
    return font


def visible_extent(x: np.ndarray, y: np.ndarray,
                   span: tuple[float, float] | None) -> tuple[float, float]:
    """
    The lowest and highest point of a trace inside `span`, the low end never
    above zero.

    Inside the span, not over the whole run: a channel carrying a tall
    neighbour minutes away put every panel's ceiling at that neighbour, and
    with **Same Y** on the whole grid was drawn flat.
    """
    if not len(x) or not len(y):
        return 0.0, 0.0
    finite = np.isfinite(x) & np.isfinite(y)
    if span is not None:
        inside = finite & (x >= span[0]) & (x <= span[1])
        if inside.any():
            finite = inside
    if not finite.any():
        return 0.0, 0.0
    return min(0.0, float(np.min(y[finite]))), float(np.max(y[finite]))


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


class _PanelAxis(pg.AxisItem):
    """
    An axis that spaces its labels for the type they are drawn in.

    pyqtgraph asks for at least two and a quarter intervals whatever the
    axis's length, so a 130-pixel time axis at a readable size printed
    `4.04.55.0`, and a 30-pixel intensity axis drew 2000 over 1000. Here the
    major spacing steps 1, 2, 5, 10 until every label has its own width and
    as much again between it and the next — or, upright, half its height —
    and a short axis keeps one label rather than none.
    """

    def tickSpacing(self, minVal, maxVal, size):
        levels = super().tickSpacing(minVal, maxVal, size)
        span = abs(maxVal - minVal)
        if not levels or self._tickSpacing is not None or span == 0 or size <= 0:
            return levels
        font = self.style["tickFont"] or QtGui.QFont()
        metrics = QtGui.QFontMetrics(font)
        spacing = levels[0][0]
        coarsened = False
        for _ in range(12):
            if self.orientation in ("left", "right"):
                room = metrics.height() * 1.5
            else:
                labels = self.tickStrings([minVal, maxVal], 1.0, spacing)
                room = 2 * max(metrics.horizontalAdvance(t) for t in labels)
            if max(1, int(span // spacing)) * room <= size:
                break
            spacing = _next_nice(spacing)
            coarsened = True
        if not coarsened:
            return levels
        # one level: a finer one would be labelled again wherever pyqtgraph
        # found room, which is what is being prevented
        return [(spacing, 0)]


def _next_nice(step: float) -> float:
    """The next of 1, 2, 5, 10, 20, 50… above `step`."""
    power = 10.0 ** np.floor(np.log10(step))
    mantissa = round(step / power, 6)
    for nice in (2.0, 5.0, 10.0):
        if mantissa < nice:
            return nice * power
    return 20.0 * power


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
                         viewBox=self.viewbox,
                         axisItems={"bottom": _PanelAxis("bottom"),
                                    "left": _PanelAxis("left"),
                                    "right": _PanelAxis("right")})
        self.sample_key = ""
        self.showGrid(x=True, y=True, alpha=0.12)
        self.setMenuEnabled(False)
        self.hideButtons()
        theme.style_axes(self, faint=True)
        # the grid shares its space by stretch alone: a panel that asked for
        # a size of its own — a QGraphicsView's 90 x 90, a long title — made
        # its row the one that would not shrink, and a grid squeezed by the
        # splitter ran its last rows off the bottom. Kept when hidden, so the
        # empty cells of a short last page hold their place.
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                       QtWidgets.QSizePolicy.Policy.Ignored)
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)
        self.setMinimumSize(0, 0)
        # the title spans the whole panel, not just the plot beside the Y
        # axis: that column is all a narrow panel has, and an 8 x 8 grid's
        # titles were being cut to make room for the axis numbers under them
        item = self.getPlotItem()
        item.layout.removeItem(item.titleLabel)
        item.layout.addItem(item.titleLabel, 0, 0, 1, 3)
        self._title = ("", "", [], theme.foreground())  # name, note, parts, colour
        self._type: tuple | None = None   # (title pt, tick pt, values shown)
        self._top = 0.0                   # the highest value the Y axis labels
        #: what the internal standard was multiplied by to be drawn at the
        #: analyte's height; None when no standard is drawn
        self._is_scale: float | None = None
        # the standard's own counts, in its colour, on the right: the dashed
        # trace is drawn at the analyte's height, and read against the left
        # axis a standard of 80,000 counts looked like one of 20
        right = self.getAxis("right")
        right.setPen(pg.mkPen(IS_PEN))
        right.setTextPen(pg.mkPen(IS_PEN))
        right.unlinkFromView()      # its range is set from the left's
        self.hideAxis("right")

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
        self.viewbox.sigYRangeChanged.connect(self._sync_is_axis)
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

    def fence(self, x: np.ndarray, y: np.ndarray,
              ceiling: float | None = None, floor: float | None = None) -> None:
        """
        Keep the panel inside its own data, as the Explorer's plots are.

        Nothing lies outside a peak's trace, and a panel this small is easy to
        lose your place in. `ceiling` is the top of the Y axis when the grid
        shares one — **Same Y** — and it has to reach the fence, because a
        limit set from this panel's own tallest point is exactly what stops
        a shared scale from being shown: `setYRange` to the grid's ceiling
        was clamped straight back to the panel's own, and the switch looked
        as though it did nothing. `floor` is the same at the bottom: the
        lowest point of any panel, which one whose trace never dips below
        zero would otherwise clamp away.
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
        if ceiling is not None and ceiling > y_high:
            y_high = float(ceiling)
        if floor is not None and floor < y_low:
            y_low = float(floor)
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
        self._set_internal_standard(np.empty(0), None)
        self.setToolTip("")
        self._band.hide()
        self._expected.hide()
        self._clear_area()
        self._title = ("", "", [], theme.foreground())
        self._type = None
        self.setTitle(None)

    def set_data(self, result: PeakResult, x: np.ndarray, y: np.ndarray,
                 expected: tuple[float, float] | None,
                 internal_standard: tuple[np.ndarray, np.ndarray] | None = None,
                 ceiling: float | None = None,
                 scale_to: float | None = None,
                 floor: float | None = None) -> None:
        """
        `ceiling` is the grid's shared top under **Same Y**; `scale_to` the
        analyte's height where the panel looks, which the internal standard
        is rescaled to.
        """
        self.sample_key = result.sample_key
        found = result.found
        self._curve.setData(x, y, pen=pg.mkPen(FOUND_PEN if found else MISSING_PEN,
                                               width=1.3))
        self._set_internal_standard(y, internal_standard, scale_to)
        if found:
            self._band.setRegion((result.start_rt, result.end_rt))
            self._band.show()
            self._show_area(x, y, result.start_rt, result.end_rt,
                            GaussianModel.from_dict(result.model))
        else:
            self._band.hide()
            self._clear_area()
        self.fence(x, y, ceiling, floor)
        if expected is not None:
            self._expected.setRegion(expected)
            self._expected.show()
        else:
            self._expected.hide()

        if found:
            manual = " ✎" if result.manual else ""
            ratio = f"{result.snr:,.0f}" if result.snr is not None else "—"
            # in the order they are given up when the panel is too narrow:
            # the time and the S/N are what the grid is scanned for, the area
            # is in the table under it
            self._title = (f"{result.sample_name}{manual}", "",
                           [f"{result.rt:.2f}", f"S/N {ratio}",
                            f"{result.area:,.0f}"],
                           theme.foreground())
        else:
            self._title = (result.sample_name, result.note or "not found", [],
                           "#e06666" if theme.is_dark() else "#b03030")
        self.setToolTip(self._tooltip(result))
        self._type = None
        self._fit_type()

    def _tooltip(self, result: PeakResult) -> str:
        """
        The numbers behind the panel, the standard's in its own counts.

        Its area and height are the ones the ratio was taken against; the
        drawn trace is the standard multiplied to the analyte's height, which
        is said too, so the dashed line is never read as a measurement.
        """
        lines = [result.sample_name]
        if result.found:
            lines.append(f"Area {result.area:,.0f} · height {result.height:,.0f}"
                         f" · RT {result.rt:.2f} min")
        else:
            lines.append(result.note or "not found")
        if result.internal_standard:
            area = (f"{result.is_area:,.0f}" if result.is_area is not None
                    else "—")
            height = (f"{result.is_height:,.0f}" if result.is_height is not None
                      else "—")
            lines.append(f"Internal standard {result.internal_standard}: "
                         f"area {area} · height {height}")
            if self._is_scale is not None:
                lines.append(f"Dashed trace drawn ×{self._is_scale:.3g} to "
                             f"the analyte's height; its counts are on the "
                             f"right-hand axis")
        return "\n".join(lines)

    # -- type ------------------------------------------------------------------- #
    def title_text(self) -> str:
        """The title as it is drawn, after whatever the width took from it."""
        return getattr(self, "_title_shown", "")

    def title_points(self) -> float:
        return self._type[0] if self._type else 0.0

    def tick_points(self) -> float:
        return self._type[1] if self._type else 0.0

    def resizeEvent(self, event):
        # fitted before the view sizes its plot, not after: pyqtgraph resizes
        # the view inside its own constructor, before this panel's
        # attributes exist, hence the guard
        if "_type" in self.__dict__:
            self._fit_type()
        self._fit_scene()

    def _fit_scene(self) -> None:
        """
        Size the plot to the viewport, not to the widget.

        pyqtgraph sizes it to the widget, which is right with no frame; the
        panel's border is a frame, so the plot was two pixels taller than
        what shows of it, and four on the selected panel — taken off the
        bottom, which is where the time axis's numbers are.
        """
        if self.closed:
            return
        if self.autoPixelRange:
            viewport = self.viewport().size()
            self.range = QtCore.QRectF(0, 0, viewport.width(), viewport.height())
        pg.GraphicsView.setRange(self, self.range, padding=0,
                                 disableAutoPixel=False)
        self.updateMatrix()

    def _fit_type(self) -> None:
        """
        Size the title and the axes for the panel as it is now.

        Every height the panel's layout reserves is measured from the font
        it will be drawn in: the title row was a fixed 30 pixels and the time
        axis was sized from the type's first draw, so a short panel pushed
        its tick labels out of the bottom. Below `MIN_PLOT_PX` of plot the
        time axis gives up its numbers, never the trace.
        """
        width, height = self.width(), self.height()
        title_pt, tick_pt = panel_type(width, height)
        tick_font = _font(tick_pt)
        title_font = _font(title_pt)
        tick_h = QtGui.QFontMetrics(tick_font).height()
        title_h = QtGui.QFontMetrics(title_font).height() + 2
        bottom_h = tick_h + 5
        values = height - title_h - bottom_h >= MIN_PLOT_PX
        wanted = (title_pt, tick_pt, values, width, self._top, self._is_scale)
        if self._type == wanted:
            return
        self._type = wanted

        bottom, left = self.getAxis("bottom"), self.getAxis("left")
        for axis in (bottom, left):
            axis.setStyle(tickFont=tick_font, showValues=True)
        bottom.setStyle(showValues=values)
        bottom.setHeight(bottom_h if values else 4)
        # wide enough for the longest label the axis can print, so it is
        # never cut on the left and every panel on one scale lines up
        metrics = QtGui.QFontMetrics(tick_font)
        widest = max(metrics.horizontalAdvance(f"{self._top:.0f}"),
                     metrics.horizontalAdvance("0000"))
        left.setWidth(widest + 10)
        right = self.getAxis("right")
        right.setStyle(tickFont=tick_font)
        # with the time axis's numbers gone the panel is too small for a
        # second scale too; the standard's counts are still in the tooltip
        if self._is_scale and values:
            self.showAxis("right")
            right.setWidth(max(metrics.horizontalAdvance(
                f"{self._top / self._is_scale:.0f}"),
                metrics.horizontalAdvance("0000")) + 10)
        else:
            self.hideAxis("right")

        item = self.getPlotItem()
        name, note, parts, colour = self._title
        if not name and not note:
            self.setTitle(None)
            self._title_shown = ""
            return
        shown = self._elided(name, note, parts, title_font, width - 18)
        self._title_shown = shown
        # the title is HTML, which folds a run of spaces into one and ran
        # the area into the S/N
        self.setTitle(html.escape(shown).replace(TITLE_GAP, "&nbsp;" * 3),
                      color=colour, size=f"{title_pt:.1f}pt")
        # a label asks for its text's width as its least, and a plot cannot
        # be narrower than its title: a title set while the panel was wider
        # held one panel's plot at 240 pixels in a 179-pixel cell, drawn
        # off the right-hand edge. The text is already cut to the room.
        item.titleLabel.setMinimumWidth(0)
        item.titleLabel.setMaximumHeight(title_h)
        item.layout.setRowFixedHeight(0, title_h)

    @staticmethod
    def _elided(name: str, note: str, parts: list[str],
                font: QtGui.QFont, room: int) -> str:
        """
        The longest title that fits `room` pixels: whole fields dropped from
        the end first, then the name — or the reason nothing was found —
        cut with an ellipsis.
        """
        metrics = QtGui.QFontMetrics(font)
        gap = TITLE_GAP
        if note:
            full = f"{name}{gap}{note}"
            if metrics.horizontalAdvance(full) <= room:
                return full
            return metrics.elidedText(full, QtCore.Qt.TextElideMode.ElideRight,
                                      max(room, 0))
        # `parts` come most wanted first and are drawn the other way round,
        # name · area · S/N · RT, so the time is the last to go
        for keep in range(len(parts), 0, -1):
            text = gap.join([name] + parts[:keep][::-1])
            if metrics.horizontalAdvance(text) <= room:
                return text
        tail = f"{gap}{parts[0]}" if parts else ""
        cut = metrics.elidedText(name, QtCore.Qt.TextElideMode.ElideRight,
                                 max(room - metrics.horizontalAdvance(tail), 0))
        return cut + tail

    def show_view(self, span: tuple[float, float], low: float, top: float) -> None:
        """
        Put the axes where the grid says, and leave them there.

        Ranges are set outright rather than auto-ranged, so nothing the
        ViewBox does later — a resize, a trace added, the panel shown —
        takes a shared scale back to the panel's own.
        """
        box = self.getViewBox()
        box.disableAutoRange()
        if span[1] > span[0]:
            box.setXRange(span[0], span[1], padding=0)
        if top <= low:
            top = low + 1.0
        box.setYRange(low, top, padding=0)
        if abs(top - self._top) > 1e-9:
            self._top = top
            self._type = None
            self._fit_type()

    def _set_internal_standard(self, y: np.ndarray,
                               trace: tuple[np.ndarray, np.ndarray] | None,
                               scale_to: float | None = None) -> None:
        """
        Draw the internal standard behind the analyte, rescaled to it.

        The two rarely share a magnitude — a labelled standard is often far the
        taller — so plotting both on one axis would flatten the analyte. Only
        the shape and the retention time are being compared here, so the
        standard is normalised to the analyte's height.
        """
        if trace is None or trace[0].size == 0:
            self._is_curve.setData([], [])
            self._is_scale = None
            self.hideAxis("right")
            return
        is_x, is_y = trace
        peak = float(np.max(is_y)) if is_y.size else 0.0
        target = (scale_to if scale_to is not None
                  else float(np.max(y)) if y.size else 0.0)
        scale = target / peak if peak > 0 and target > 0 else 1.0
        self._is_curve.setData(is_x, is_y * scale)
        self._is_scale = scale
        self._type = None         # `_fit_type` decides whether the axis fits
        self._sync_is_axis()

    def _sync_is_axis(self, *_args) -> None:
        """The right-hand axis is the left one divided by the standard's scale."""
        if not self._is_scale:
            return
        low, high = self.getViewBox().viewRange()[1]
        self.getAxis("right").setRange(low / self._is_scale,
                                       high / self._is_scale)

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
        # the border is a frame, and a wider one is a smaller viewport
        self._fit_scene()

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
        #: what the items are of — a component — so a refresh of the same
        #: set can keep its page
        self._key: str | None = None
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
        panel.getViewBox().sigYRangeChanged.connect(
            lambda _vb, rng, p=panel: self._link_y(p, rng))
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
        # a QGridLayout remembers every row and column it has ever had and
        # shares the space by size hint among them: at 4 x 3 after 3 x 2
        # the rows measured 291, 197 and 90 pixels. Equal stretch on what
        # is in use and none on the rest is what "a grid" means.
        for row in range(max(rows, self.grid.rowCount())):
            self.grid.setRowStretch(row, 1 if row < rows else 0)
        for column in range(max(columns, self.grid.columnCount())):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
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

    def _link_y(self, source: PeakPanel, rng) -> None:
        """
        Under **Same Y** a zoom in one panel is a zoom in all of them: a
        wheel over one panel otherwise left it on a scale of its own, and
        the grid no longer compared heights while still saying it did.
        """
        if not self._shared_y or self._syncing:
            return
        self._syncing = True
        try:
            for panel in self._panels:
                if panel is not source and panel.sample_key:
                    panel.getViewBox().setYRange(rng[0], rng[1], padding=0)
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
    def set_items(self, title: str, items: list[tuple],
                  key: str | None = None) -> None:
        """
        `items` are (result, x, y, expected window, internal standard trace)
        tuples, one per sample; the last entry may be None.

        `key` says what the items are of, the title when not given. The same
        key again is a refresh — a manual integration, a reprocessing — and
        keeps the page and the selection; another key starts at the first
        page. Every refresh used to start there, so integrating a peak by
        hand on page 3 put the operator back on page 1 after each drag.
        """
        self.title.setText(title)
        same = self._is_refresh(title if key is None else key)
        self._items = list(items)
        self._fetch = None
        self._total = 0
        self._show(same)

    def _is_refresh(self, key: str) -> bool:
        same = key == self._key
        self._key = key
        return same

    def _show(self, same: bool) -> None:
        if same:
            self.set_page(self._page)      # clipped, if the set got shorter
        else:
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
        same = self._is_refresh(title)
        self._items = []
        self._fetch = fetch
        self._total = int(total)
        self._show(same)

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

        views = [self._view_of(item) for item in page_items]
        ceiling = low_all = 0.0
        if self._shared_y:
            # the tallest point any panel shows, over the whole set so the
            # scale holds from page to page; a lazy source would have to
            # build every page for that, so it spans the page in view
            source = (views if self._fetch is not None
                      else [self._view_of(item) for item in self._items])
            ceiling = max((top for _span, _low, top in source), default=0.0)
            low_all = min((low for _span, low, _top in source), default=0.0)

        # the panels' own range signals would otherwise carry each panel's
        # span to every other one while the page is being filled
        self._syncing = True
        try:
            for panel, item, (span, low, top) in zip(self._panels, page_items,
                                                     views):
                result, x, y, expected = item[:4]
                is_trace = item[4] if len(item) > 4 and self._show_is else None
                shared = self._shared_y and ceiling > 0
                panel.set_data(result, x, y, expected, is_trace,
                               ceiling=ceiling * HEADROOM if shared else None,
                               scale_to=top if top > 0 else None,
                               floor=low_all if shared else None)
                panel.set_noise_region(self._noise_region)
                panel.set_selected(result.sample_key == self._selected)
                if shared:
                    panel.show_view(span, low_all, ceiling * HEADROOM)
                else:
                    panel.show_view(span, low, top * HEADROOM)
                panel.show()
        finally:
            self._syncing = False
        for panel in self._panels[len(page_items):]:
            panel.clear_panel()
            panel.set_selected(False)
            panel.hide()

        self.page_label.setText(f"{self._page + 1}/{max(self.page_count, 1)}")
        self.btn_prev.setEnabled(self._page > 0)
        self.btn_next.setEnabled(self._page + 1 < self.page_count)

    def _view_of(self, item) -> tuple[tuple[float, float], float, float]:
        """The time span a panel shows, and the lowest and highest point in it."""
        result, x, y, expected = item[:4]
        span = self._x_range(result, expected)
        if span is None:
            finite = np.isfinite(x)
            span = ((float(np.min(x[finite])), float(np.max(x[finite])))
                    if finite.any() else (0.0, 1.0))
        low, top = visible_extent(x, y, span)
        return span, low, top

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
