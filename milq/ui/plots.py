"""Chromatogram and spectrum panes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from .. import labels as label_rule
from ..processing import (
    restore_profile_zeros,
    ChromPeak,
    centroid_spectrum,
    gaussian_smooth,
    pick_peaks,
    subtract_baseline,
)

#: the categorical colours after the first. They are chosen to be told apart
#: from one another, which is a different job from carrying the brand, so they
#: are left as they are.
PALETTE = [
    "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
    "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f",
]
ARROW_COLOUR = "#7a3fbf"


def colour(i: int) -> str:
    """
    The nth series colour. The first is the project's blue.

    Most plots here show one trace, or one trace that matters and some
    context — so the colour seen most often is the accent, and it follows the
    light or dark theme rather than being a literal.
    """
    index = i % (len(PALETTE) + 1)
    return theme.accent() if index == 0 else PALETTE[index - 1]


@dataclass
class Trace:
    """One curve drawn in a pane."""

    key: str
    label: str
    x: np.ndarray
    y: np.ndarray
    colour: str
    source: object | None = None  # originating Channel, when there is one
    #: how this spectrum was made — a `spectra_compare.SpectrumRecipe`, when
    #: the pane knows. It is what a pinned spectrum is saved as: the points
    #: are read from the file again rather than written into the project.
    recipe: object | None = None


def _label_half_width(text) -> float:
    """
    Half the width a label takes on screen, from the font it was given.

    A function of its own so the suite can pin it: the collision rule
    depends on it, and the platform's default font gave different label
    sets on Windows than on macOS for the same spectrum.
    """
    return float(text.boundingRect().width()) / 2.0


def _sticks(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Turn centroids into a single polyline of vertical sticks, split by NaN."""
    xs = np.repeat(x, 3)
    ys = np.empty(xs.size, dtype=np.float64)
    ys[0::3] = 0.0
    ys[1::3] = y
    ys[2::3] = np.nan
    return xs, ys


@lru_cache(maxsize=4)
def _label_height(points: int = 8) -> float:
    """
    The drawn height of one label, measured rather than derived from the font.

    A text item is taller than its font metrics say: the document it wraps
    carries margins of its own, eight pixels of them at this size. Guessing
    that difference is how a label ends up a few pixels outside the window,
    which is the whole of the complaint.
    """
    font = QtGui.QFont()
    font.setPointSize(points)
    probe = pg.TextItem("0123456789")
    probe.setFont(font)
    return float(abs(probe.boundingRect().height()))


#: clear space kept between two labels before one of them is dropped
LABEL_GAP = 5.0

#: how many maxima of a trace are kept as candidates for a label. The region
#: budget will never name more than a couple of dozen of them; the rest are
#: there so that zooming in has something to offer, and 200 is what a real
#: survey scan yields above 2% of its base peak in the first place.
LABEL_POOL = 200

#: how far down the pool reaches, as a fraction of the trace's base peak.
#: A label still needs the pane's label floor — `labels.LABEL_MIN_RELATIVE`
#: until the reader moves the handle — of the tallest peak *in view*; this is
#: only the floor on what is worth remembering, so that a stretch a hundred
#: times below the base peak is not empty when it fills the window.
#:
#: It is exactly a tenth of the default floor, and `SpectrumView._pool_floor`
#: keeps it that way as the handle moves: the floor is measured against the
#: tallest peak *in view* and the pool against the base peak of the whole
#: spectrum, so zoomed into a quiet stretch the pool is the lower of the two
#: and a floor dragged down with a fixed pool changes nothing at all. It was
#: measured changing nothing: over eighteen 100 Da windows of a real survey,
#: 57 labels at a 2% floor and 57 at 0.5% before the pool followed.
POOL_MIN_RELATIVE = 0.002

#: the most maxima the pool may hold once the floor has taken it below
#: `POOL_MIN_RELATIVE`. The pool is filled tallest first, so a cap reached
#: on a dense spectrum starves the quiet end of the axis of candidates —
#: which is the very thing the region budget exists to prevent.
MAX_POOL = 4000

#: the label floor, as a fraction of the tallest peak in view, may be dragged
#: between these — a hundredth of a per cent of the base peak, and the base
#: peak itself. The bottom is not zero because the pool below it is every
#: local maximum of a profile spectrum, noise included, and naming noise is
#: not what the reader is asking for.
FLOOR_MIN = 0.0001
FLOOR_MAX = 1.0

#: the handle beside the Y axis, in pixels: the triangle's width and height,
#: and the clear space the axis margin is widened by to hold it. The left
#: `pg.AxisItem` reserves `tickTextOffset` pixels between its tick text and
#: the axis line — five, measured — which is not room for a triangle, so the
#: offset is raised by this much and the triangle drawn in what that opens
#: up. Widening the margin rather than drawing over the plot is the point:
#: the handle must never cover data.
HANDLE_WIDTH = 9.0
HANDLE_HEIGHT = 12.0
HANDLE_SPACE = 12.0


class LabelThresholdHandle(QtWidgets.QGraphicsObject):
    """
    The triangle in the axis margin that sets the label floor, PeakView-style.

    It is a scene item rather than a plot item because it lives *outside* the
    view box, in the space the axis reserves — an item added to the box would
    be inside the data and would move with the data.

    It reports where it was dragged to in scene pixels and knows nothing
    about intensities; `SpectrumView` turns that into a fraction of the
    tallest peak in view, which is what a floor is stored as.
    """

    sigDragged = QtCore.pyqtSignal(float)   # scene y, while the mouse is down
    sigReleased = QtCore.pyqtSignal()
    sigReset = QtCore.pyqtSignal()          # double-clicked

    def __init__(self, colour: str | None = None, parent=None):
        super().__init__(parent)
        self._colour = colour or theme.accent()
        self._hover = False
        self.setZValue(200)
        self.setAcceptHoverEvents(True)
        self.setCursor(QtCore.Qt.CursorShape.SizeVerCursor)
        self.setToolTip(
            "Drag to set the intensity below which peaks are not labelled.\n"
            "Double-click to put it back where it started."
        )

    def set_colour(self, colour: str) -> None:
        self._colour = colour
        self.update()

    def boundingRect(self) -> QtCore.QRectF:
        # the apex is the origin, so the triangle hangs to the left of it
        return QtCore.QRectF(-HANDLE_WIDTH - 1.0, -HANDLE_HEIGHT / 2.0 - 1.0,
                             HANDLE_WIDTH + 2.0, HANDLE_HEIGHT + 2.0)

    def paint(self, painter, *_args) -> None:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        colour = QtGui.QColor(self._colour)
        painter.setBrush(QtGui.QBrush(colour))
        painter.setPen(QtGui.QPen(colour.lighter(150) if self._hover
                                  else colour, 1.0))
        painter.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(-HANDLE_WIDTH, -HANDLE_HEIGHT / 2.0),
            QtCore.QPointF(-HANDLE_WIDTH, HANDLE_HEIGHT / 2.0),
            QtCore.QPointF(0.0, 0.0),
        ]))

    # -- mouse ----------------------------------------------------------- #
    def hoverEnterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        event.accept()
        self.sigDragged.emit(float(event.scenePos().y()))

    def mouseReleaseEvent(self, event) -> None:
        event.accept()
        self.sigReleased.emit()

    def mouseDoubleClickEvent(self, event) -> None:
        event.accept()
        self.sigReset.emit()


class _DragViewBox(pg.ViewBox):
    """ViewBox that turns a horizontal drag into a range selection."""

    sigRangeDrag = QtCore.pyqtSignal(float, float, bool)  # x0, x1, finished

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.select_mode = False
        #: clear space to keep above the data, in pixels. Set by the plot that
        #: owns the box — see BasePlot._headroom_px.
        self.headroom_px = 0.0

    def suggestPadding(self, axis):
        """
        Room for the labels that sit on top of the tallest peak.

        pyqtgraph pads an auto-ranged view by a share of the data range. A
        label is a fixed number of pixels tall whatever the view holds, so a
        share that clears it in a tall pane still cuts it off in a short one —
        which is how the m/z of the base peak came to be sliced by the top of
        the window. The room is asked for in pixels and converted here.
        """
        padding = super().suggestPadding(axis)
        if axis != 1 or self.headroom_px <= 0:
            return padding
        height = float(self.height())
        if height <= 2 * self.headroom_px:
            return padding
        # padding p is added at both ends, so the top of a padded view is
        # height * p / (1 + 2p) pixels clear of the data. Solve that for p.
        return max(padding, self.headroom_px / (height - 2 * self.headroom_px))

    def mouseDragEvent(self, ev, axis=None):
        shift = bool(ev.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        left = ev.button() == QtCore.Qt.MouseButton.LeftButton
        if left and (self.select_mode or shift):
            ev.accept()
            x0 = float(self.mapToView(ev.buttonDownPos()).x())
            x1 = float(self.mapToView(ev.pos()).x())
            self.sigRangeDrag.emit(x0, x1, ev.isFinish())
            return
        super().mouseDragEvent(ev, axis)


class BasePlot(QtWidgets.QWidget):
    """Shared behaviour: grid, crosshair, legend, processing, markers, overview."""

    sigRangeSelected = QtCore.pyqtSignal(float, float)   # selection finished
    sigRangeDragging = QtCore.pyqtSignal(float, float)   # selection being dragged
    sigClicked = QtCore.pyqtSignal(float)                # single click at x
    sigFocused = QtCore.pyqtSignal()                     # user interacted here

    #: how close a peak must be to a marker to keep its absolute label
    marker_snap = 0.05

    def __init__(self, x_label: str, x_units: str, y_label: str, parent=None):
        super().__init__(parent)
        self._traces: list[Trace] = []
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._normalise = False
        self._smooth_sigma = 0.0
        self._mirror = False
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._stick_mode = False
        self._arrows: list[pg.InfiniteLine] = []
        self._match_marks = None
        self._match_labels: list = []
        self._relative_labels = True
        self._syncing_overview = False
        self._bounds: tuple[float, float, float, float] | None = None
        self._resizing = False

        self.viewbox = _DragViewBox()
        self.viewbox.sigResized.connect(self._resized)
        self.plot = pg.PlotWidget(viewBox=self.viewbox,
                                  background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", x_label, units=x_units or None)
        self.plot.setLabel("left", y_label)
        theme.style_axes(self.plot)
        self.legend = self.plot.addLegend(
            offset=(-10, 10), labelTextColor=theme.foreground(),
            brush=theme.legend_brush(), pen=theme.legend_pen(), verSpacing=-4,
        )
        self.legend.setLabelTextSize("8pt")

        self.region = pg.LinearRegionItem(
            brush=pg.mkBrush(60, 110, 200, 45),
            hoverBrush=pg.mkBrush(60, 110, 200, 70),
            pen=pg.mkPen("#3b6ec8", width=1),
        )
        self.region.setZValue(-10)
        self.region.hide()
        self.plot.addItem(self.region, ignoreBounds=True)
        self.region.sigRegionChangeFinished.connect(self._region_finished)
        self.region.sigRegionChanged.connect(self._region_moving)

        self.vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen(theme.faint_axis(), style=QtCore.Qt.PenStyle.DashLine),
        )
        self.vline.hide()
        self.plot.addItem(self.vline, ignoreBounds=True)

        self.readout = pg.TextItem(color=theme.foreground(), anchor=(0, 1))
        self.readout.setZValue(100)
        self.plot.addItem(self.readout, ignoreBounds=True)

        # navigator: always shows the full range, with the current view marked
        self.overview = pg.PlotWidget(background=theme.background())
        self.overview.setFixedHeight(64)
        self.overview.setMenuEnabled(False)
        self.overview.hideButtons()
        self.overview.getPlotItem().hideAxis("left")
        self.overview.getAxis("bottom").setPen(pg.mkPen(theme.faint_axis()))
        self.overview.getAxis("bottom").setTextPen(pg.mkPen(theme.muted()))
        self.overview.setMouseEnabled(x=False, y=False)
        self.overview_region = pg.LinearRegionItem(
            brush=pg.mkBrush(200, 120, 200, 55),
            hoverBrush=pg.mkBrush(200, 120, 200, 85),
            pen=pg.mkPen("#a05aa0", width=1),
        )
        self.overview.addItem(self.overview_region)
        self.overview.hide()
        self.overview_region.sigRegionChanged.connect(self._overview_moved)
        self.plot.getViewBox().sigXRangeChanged.connect(self._main_range_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.plot, 1)
        layout.addWidget(self.overview)

        self.viewbox.sigRangeDrag.connect(self._on_drag)
        self.plot.scene().sigMouseMoved.connect(self._on_move)
        self.plot.scene().sigMouseClicked.connect(self._on_click)

    # -- mouse mode ---------------------------------------------------------- #
    def set_select_mode(self, enabled: bool) -> None:
        self.viewbox.select_mode = enabled
        self.plot.setCursor(
            QtCore.Qt.CursorShape.SplitHCursor if enabled
            else QtCore.Qt.CursorShape.CrossCursor
        )

    # -- processing ---------------------------------------------------------- #
    def condition(self, trace: Trace) -> tuple[np.ndarray, np.ndarray]:
        """
        Data-level processing (baseline, smoothing, centroiding). This is what
        integration and export use, so area and height match what is on screen.
        Returns both axes because centroiding shortens the x axis.
        """
        y = trace.y
        if self._smooth_sigma > 0:
            y = gaussian_smooth(y, self._smooth_sigma)
        return trace.x, y

    def _display(self, trace: Trace, index: int) -> tuple[np.ndarray, np.ndarray]:
        """View-level processing (normalisation, mirroring, cascade offsets)."""
        x, y = self.condition(trace)
        if self._normalise and y.size:
            peak = float(np.max(np.abs(y)))
            if peak > 0:
                y = y / peak * 100.0
        if self._mirror and index % 2 == 1:
            y = -y
        if self._offset_x:
            x = x + index * self._offset_x
        if self._offset_y:
            y = y + index * self._offset_y / 100.0 * self._reference_height()
        return x, y

    def _reference_height(self) -> float:
        """Tallest conditioned trace, used as the unit for the Y cascade."""
        best = 0.0
        for trace in self._traces:
            _, y = self.condition(trace)
            if y.size:
                best = max(best, float(np.max(np.abs(y))))
        return best or 1.0

    def conditioned(self, key: str) -> tuple[np.ndarray, np.ndarray] | None:
        for trace in self._traces:
            if trace.key == key:
                return self.condition(trace)
        return None

    def set_normalised(self, enabled: bool) -> None:
        self._normalise = enabled
        self.plot.setLabel("left", "Intensity (%)" if enabled else self._y_label_raw())
        self.redraw()
        self.autoscale()

    def set_smoothing(self, sigma: float) -> None:
        self._smooth_sigma = max(0.0, float(sigma))
        self.redraw()

    def set_mirror(self, enabled: bool) -> None:
        self._mirror = enabled
        self.redraw()
        self.autoscale()

    def set_offsets(self, offset_x: float, offset_y: float) -> None:
        """Cascade the overlaid traces by `offset_x` in x and `offset_y` % in y."""
        self._offset_x = float(offset_x)
        self._offset_y = float(offset_y)
        self.redraw()
        self.autoscale()

    @property
    def mirrored(self) -> bool:
        return self._mirror

    # -- traces -------------------------------------------------------------- #
    def retheme(self) -> None:
        """
        Take the colours again after the system theme changed.

        pyqtgraph is told its colours once, at construction, so nothing here
        follows a stylesheet — every item that was given one has to be handed
        the new one.
        """
        self.plot.setBackground(theme.background())
        theme.style_axes(self.plot)
        self.legend.setLabelTextColor(theme.foreground())
        self.legend.setBrush(theme.legend_brush())
        self.legend.setPen(theme.legend_pen())
        self.vline.setPen(pg.mkPen(theme.faint_axis(),
                                   style=QtCore.Qt.PenStyle.DashLine))
        self.readout.setColor(theme.foreground())
        self.overview.setBackground(theme.background())
        self.overview.getAxis("bottom").setPen(pg.mkPen(theme.faint_axis()))
        self.overview.getAxis("bottom").setTextPen(pg.mkPen(theme.muted()))
        self.redraw()

    def set_traces(self, traces: list[Trace]) -> None:
        self._traces = list(traces)
        self.redraw()

    def redraw(self) -> None:
        self.clear_matches()
        for curve in self._curves.values():
            self.plot.removeItem(curve)
        self._curves.clear()
        self.legend.clear()
        for i, trace in enumerate(self._traces):
            x, y = self._display(trace, i)
            if self._stick_mode:
                x, y = _sticks(x, y)
                item = self.plot.plot(x, y, pen=pg.mkPen(trace.colour, width=1.2),
                                      name=trace.label, connect="finite")
            else:
                item = self.plot.plot(x, y, pen=pg.mkPen(trace.colour, width=1.4),
                                      name=trace.label, antialias=True)
            self._curves[trace.key] = item
        self._refresh_overview()
        self._apply_limits()
        self._after_traces_changed()

    def clear_traces(self) -> None:
        self.set_traces([])

    @property
    def traces(self) -> list[Trace]:
        return list(self._traces)

    def _y_label_raw(self) -> str:
        return "Intensity"

    def _after_traces_changed(self) -> None:
        pass

    # -- room for the labels above the data ----------------------------------- #
    def _headroom_px(self) -> float:
        """Pixels of clear space the topmost label needs. Nothing by default."""
        return 0.0

    @staticmethod
    def _label_height_px(points: int = 8) -> float:
        return _label_height(points)

    def _refresh_headroom(self) -> None:
        """Called when a label setting changes: the room needed changed with it."""
        self._apply_limits()

    def autoscale(self) -> None:
        self._apply_limits()
        self.plot.enableAutoRange()
        self.plot.autoRange()

    # -- how far the view may go --------------------------------------------- #
    def _apply_limits(self) -> None:
        """
        Fence the view to the data: no negative time, mass or intensity, and
        no zooming out past what was measured.

        Panning into empty space either side of a chromatogram is disorienting
        and never useful — there is nothing out there. The widest view is the
        whole of the data, which is also what Fit gives.
        """
        self._bounds = self._data_bounds()
        self._apply_limits_to(self._bounds)

    def _apply_limits_to(self, bounds) -> None:
        box = self.plot.getViewBox()
        pixels = self._headroom_px()
        self.viewbox.headroom_px = pixels
        if bounds is None:
            box.setLimits(xMin=None, xMax=None, yMin=None, yMax=None,
                          maxXRange=None, maxYRange=None)
            return
        x_low, x_high, y_low, y_high = bounds
        # zero stays reachable so a baseline is visible, and a mirrored or
        # baseline-subtracted trace keeps the negative room it actually uses
        x_low = min(0.0, x_low)
        y_low = min(0.0, y_low)
        if x_high <= x_low or y_high <= y_low:
            box.setLimits(xMin=None, xMax=None, yMin=None, yMax=None,
                          maxXRange=None, maxYRange=None)
            return
        # the fence has to allow whatever room the labels ask for, or the
        # padded auto-range gets clamped straight back onto the peak
        span = y_high - y_low
        head_room = span * 0.05
        height = float(box.height())
        if pixels > 0 and height > 2 * pixels:
            head_room = max(head_room, span * pixels / (height - 2 * pixels))
        # a mirrored trace hangs below zero with labels under its peaks, so
        # the room above the tallest peak is given below the deepest one too
        foot_room = head_room if y_low < 0 else 0.0
        box.setLimits(xMin=x_low, xMax=x_high,
                      yMin=y_low - foot_room, yMax=y_high + head_room,
                      maxXRange=x_high - x_low,
                      maxYRange=span + 2 * head_room + foot_room)

    def _resized(self, *_args) -> None:
        """
        Re-fence after a resize, because the headroom is measured in pixels.

        Shrinking the pane raises the share of the range a label occupies, and
        a fence computed for the old height would clamp the padding away — the
        same clipping, arriving one drag of the window later. The cached bounds
        are used rather than recomputed: conditioning every trace on each of
        the many resize events is work the answer does not need.

        A hidden pane is skipped, which is what keeps this away from a pane
        that is being destroyed. The stacked layout rebuilds by calling
        setParent(None) and deleteLater on every pane, and setParent(None)
        hides the widget as it makes it briefly a window of its own — which
        resizes it, and so lands here. Measured on a rebuild: the dying panes
        arrive hidden, and a legitimate top-level plot arrives visible, so
        visibility separates them where having a parent does not. A pane no
        one can see needs no room for its labels in any case.
        """
        if self._bounds is None or self._resizing or not self.isVisible():
            return
        self._resizing = True
        try:
            self._apply_limits_to(self._bounds)
            # A fitted view should stay fitted when the pane changes size: the
            # pane just changed how many pixels a share of the range is worth,
            # and pyqtgraph switches auto-range off as soon as a range has been
            # settled on, so nothing else will put the room back. A view the
            # reader has zoomed into is left where they put it — pulling it
            # back to the full extent on a window drag would be far worse than
            # a tight label.
            if self._is_fitted():
                self._fit_from_bounds()
        finally:
            self._resizing = False

    def _fit_from_bounds(self) -> None:
        """
        Re-fit from the extent already known, rather than asking for autoRange.

        autoRange walks every item in the box to work out where the data is.
        During a stacked rebuild that walk can reach an item belonging to a
        pane that is being destroyed, and Windows turns that into an access
        violation — a hard crash, not an exception. The bounds were computed
        when the traces were set and are cached; padding them is the same
        answer without the walk.
        """
        if self._bounds is None:
            return
        box = self.plot.getViewBox()
        x_low, x_high, y_low, y_high = self._bounds
        if x_high <= x_low or y_high <= y_low:
            return
        pad_x = box.suggestPadding(0) * (x_high - x_low)
        pad_y = box.suggestPadding(1) * (y_high - y_low)
        # the fence set just above clamps these back to the data where it
        # should — no negative time, mass or intensity
        box.setRange(xRange=(x_low - pad_x, x_high + pad_x),
                     yRange=(y_low - pad_y, y_high + pad_y),
                     padding=0)

    def _is_fitted(self) -> bool:
        """Whether the view is showing the whole of the data, rather than a zoom."""
        if self._bounds is None:
            return False
        x_low, x_high, _y_low, _y_high = self._bounds
        span = x_high - x_low
        if span <= 0:
            return False
        lo, hi = self.plot.getViewBox().viewRange()[0]
        # a fitted view is the data extent plus padding, so it is never
        # narrower than the data; anything appreciably narrower is a zoom
        return (hi - lo) >= span * 0.98

    def _data_bounds(self) -> tuple[float, float, float, float] | None:
        """The extent of everything on screen, after conditioning."""
        lows_x, highs_x, lows_y, highs_y = [], [], [], []
        for index, trace in enumerate(self._traces):
            x, y = self._display(trace, index)
            if not len(x) or not len(y):
                continue
            finite = np.isfinite(x) & np.isfinite(y)
            if not finite.any():
                continue
            lows_x.append(float(np.min(x[finite])))
            highs_x.append(float(np.max(x[finite])))
            lows_y.append(float(np.min(y[finite])))
            highs_y.append(float(np.max(y[finite])))
        if not lows_x:
            return None
        return (min(lows_x), max(highs_x), min(lows_y), max(highs_y))

    # -- overview navigator -------------------------------------------------- #
    def set_overview_visible(self, visible: bool) -> None:
        self.overview.setVisible(visible)
        if visible:
            self._refresh_overview()
            self._main_range_changed()

    def _refresh_overview(self) -> None:
        if not self.overview.isVisible():
            return
        for item in list(self.overview.getPlotItem().listDataItems()):
            self.overview.removeItem(item)
        for i, trace in enumerate(self._traces):
            x, y = self._display(trace, i)
            if self._stick_mode:
                x, y = _sticks(x, y)
                self.overview.plot(x, y, pen=pg.mkPen(trace.colour, width=0.8),
                                   connect="finite")
            else:
                self.overview.plot(x, y, pen=pg.mkPen(trace.colour, width=0.8))
        self.overview.enableAutoRange()
        self.overview.autoRange()

    def _main_range_changed(self, *_args) -> None:
        if not self.overview.isVisible() or self._syncing_overview:
            return
        self._syncing_overview = True
        try:
            lo, hi = self.plot.getViewBox().viewRange()[0]
            self.overview_region.setRegion((lo, hi))
        finally:
            self._syncing_overview = False

    def _overview_moved(self) -> None:
        if not self.overview.isVisible() or self._syncing_overview:
            return
        self._syncing_overview = True
        try:
            lo, hi = self.overview_region.getRegion()
            self.plot.getViewBox().setXRange(lo, hi, padding=0)
        finally:
            self._syncing_overview = False

    # -- markers (mass differences / neutral losses) ------------------------- #
    def add_marker(self, x: float, snap_to_peak: bool = True) -> None:
        """
        Add a reference marker. Other peak labels then read as the distance to
        the nearest marker, which is how neutral losses and isotope spacings
        are read off a spectrum.
        """
        if snap_to_peak:
            x = self._snap_to_peak(x)
        line = pg.InfiniteLine(
            pos=x, angle=90, movable=True,
            pen=pg.mkPen(ARROW_COLOUR, width=1.2),
            label=f"{x:.4f}",
            labelOpts={"color": ARROW_COLOUR, "position": 0.95, "movable": False},
        )
        line.sigPositionChanged.connect(self._marker_moved)
        self.plot.addItem(line, ignoreBounds=True)
        self._arrows.append(line)
        self._after_traces_changed()

    def _snap_to_peak(self, x: float) -> float:
        """Move the marker onto the tallest peak near where the user clicked."""
        if not self._traces:
            return x
        px, py = self.condition(self._traces[0])
        if px.size == 0:
            return x
        span = float(px[-1] - px[0]) or 1.0
        width = span * 0.01
        window = (px >= x - width) & (px <= x + width)
        if not window.any():
            return float(px[int(np.argmin(np.abs(px - x)))])
        local = np.nonzero(window)[0]
        return float(px[local[int(np.argmax(py[local]))]])

    def _marker_moved(self, line) -> None:
        line.label.setText(f"{float(line.value()):.4f}")
        self._after_traces_changed()

    def set_matches(self, matched: list[tuple[float, str]],
                    colour: str = "#2ca02c") -> None:
        """
        Mark the peaks a prediction accounts for.

        Drawn as its own scatter above the trace rather than by recolouring it:
        a measured spectrum should keep looking like what was measured, with
        the interpretation laid over the top and removable.
        """
        self.clear_matches()
        if not matched:
            return
        x = np.array([mz for mz, _ in matched], dtype=float)
        y = np.array([self._height_at(mz) for mz in x], dtype=float)
        self._match_marks = pg.ScatterPlotItem(
            x=x, y=y, symbol="t1", size=11,
            pen=pg.mkPen(colour, width=1.2), brush=pg.mkBrush(colour))
        self._match_marks.setZValue(60)
        self.plot.addItem(self._match_marks, ignoreBounds=True)
        for mz, label in matched:
            text = pg.TextItem(label, color=colour, anchor=(0.5, 1.6))
            text.setPos(mz, self._height_at(mz))
            text.setZValue(60)
            self.plot.addItem(text, ignoreBounds=True)
            self._match_labels.append(text)
        self._refresh_headroom()

    def clear_matches(self) -> None:
        if self._match_marks is not None:
            self.plot.removeItem(self._match_marks)
            self._match_marks = None
        for text in self._match_labels:
            self.plot.removeItem(text)
        self._match_labels.clear()
        self._refresh_headroom()

    def _height_at(self, mz: float) -> float:
        """The trace height at a mass, for placing a mark on top of the peak."""
        for trace in self._traces:
            x, y = self._display(trace, 0)
            if not len(x):
                continue
            index = int(np.argmin(np.abs(x - mz)))
            if abs(float(x[index]) - mz) < 0.5:
                return float(y[index])
        return 0.0

    def clear_markers(self) -> None:
        for line in self._arrows:
            self.plot.removeItem(line)
        self._arrows.clear()
        self._after_traces_changed()

    @property
    def markers(self) -> list[float]:
        return [float(line.value()) for line in self._arrows]

    def set_relative_labels(self, enabled: bool) -> None:
        self._relative_labels = enabled
        self._after_traces_changed()

    def _label_for(self, x: float) -> str:
        """
        Absolute value when there is no marker or the peak sits on one;
        otherwise the signed distance to the reference marker.
        """
        markers = self.markers
        if not markers or not self._relative_labels:
            return f"{x:.4f}"
        nearest = min(markers, key=lambda m: abs(m - x))
        if abs(nearest - x) <= self.marker_snap:
            return f"{x:.4f}"
        # prefer the first marker to the right, matching how losses are read
        to_right = [m for m in markers if m >= x]
        reference = min(to_right) if to_right else max(markers)
        return f"{x - reference:+.4f}"

    # -- interaction --------------------------------------------------------- #
    def _on_drag(self, x0: float, x1: float, finished: bool) -> None:
        lo, hi = sorted((x0, x1))
        self.region.show()
        self.region.blockSignals(True)
        self.region.setRegion((lo, hi))
        self.region.blockSignals(False)
        self.sigFocused.emit()
        if hi > lo:
            if finished:
                self.sigRangeSelected.emit(lo, hi)
            else:
                self.sigRangeDragging.emit(lo, hi)

    def _region_moving(self) -> None:
        if not self.region.isVisible():
            return
        lo, hi = self.region.getRegion()
        if hi > lo:
            self.sigRangeDragging.emit(float(lo), float(hi))

    def _region_finished(self) -> None:
        lo, hi = self.region.getRegion()
        if hi > lo:
            self.sigRangeSelected.emit(float(lo), float(hi))

    def _on_click(self, event) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        self.sigFocused.emit()
        if event.double():
            self.autoscale()
            return
        point = self.viewbox.mapSceneToView(event.scenePos())
        self.sigClicked.emit(float(point.x()))

    def _on_move(self, pos) -> None:
        if not self.plot.sceneBoundingRect().contains(pos):
            self.readout.setText("")
            return
        point = self.viewbox.mapSceneToView(pos)
        self.readout.setText(self._format_readout(point.x(), point.y()))
        rect = self.viewbox.viewRect()
        self.readout.setPos(rect.left(), rect.bottom())

    def _format_readout(self, x: float, y: float) -> str:
        return f"x={x:.4f}  y={y:,.0f}"

    def mark(self, x: float | None) -> None:
        if x is None:
            self.vline.hide()
        else:
            self.vline.setPos(x)
            self.vline.show()

    def hide_region(self) -> None:
        self.region.hide()

    def selected_range(self) -> tuple[float, float] | None:
        if not self.region.isVisible():
            return None
        lo, hi = self.region.getRegion()
        return float(lo), float(hi)

    def set_legend_visible(self, visible: bool) -> None:
        self.legend.setVisible(visible)


class ChromatogramView(BasePlot):
    """Top pane: TIC, BPC and XIC over time."""

    sigBackgroundChanged = QtCore.pyqtSignal()

    marker_snap = 0.02

    def __init__(self, parent=None):
        super().__init__("Time", "min", "Intensity, cps", parent)
        self._apex_labels: list[pg.TextItem] = []
        self._peak_items: list[pg.GraphicsObject] = []
        self._show_apex = True
        self._baseline_window = 0.0

        # range used as the blank to subtract from generated spectra
        self.background = pg.LinearRegionItem(
            brush=pg.mkBrush(230, 170, 40, 55),
            hoverBrush=pg.mkBrush(230, 170, 40, 80),
            pen=pg.mkPen("#c98a10", width=1, style=QtCore.Qt.PenStyle.DashLine),
        )
        self.background.setZValue(-20)
        self.background.hide()
        self.plot.addItem(self.background, ignoreBounds=True)
        self.background.sigRegionChangeFinished.connect(self.sigBackgroundChanged)

    def _y_label_raw(self) -> str:
        return "Intensity, cps"

    def _format_readout(self, x: float, y: float) -> str:
        return f"RT {x:.3f} min    {y:,.0f}"

    # -- chromatogram-specific processing ------------------------------------ #
    def condition(self, trace: Trace) -> tuple[np.ndarray, np.ndarray]:
        y = trace.y
        if self._baseline_window > 0:
            y = subtract_baseline(trace.x, y, self._baseline_window)
        if self._smooth_sigma > 0:
            y = gaussian_smooth(y, self._smooth_sigma)
        return trace.x, y

    def set_baseline(self, window: float) -> None:
        self._baseline_window = max(0.0, float(window))
        self.redraw()
        self.autoscale()

    # -- background range ----------------------------------------------------- #
    def set_background_range(self, rt0: float, rt1: float) -> None:
        self.background.setRegion(tuple(sorted((float(rt0), float(rt1)))))
        self.background.show()
        self.sigBackgroundChanged.emit()

    def clear_background_range(self) -> None:
        self.background.hide()
        self.sigBackgroundChanged.emit()

    def background_range(self) -> tuple[float, float] | None:
        if not self.background.isVisible():
            return None
        lo, hi = self.background.getRegion()
        return float(lo), float(hi)

    # -- integrated peak shading ---------------------------------------------- #
    def set_peak_markers(self, peaks: list[ChromPeak],
                         pen_colour: str = "#2ca02c") -> None:
        for item in self._peak_items:
            self.plot.removeItem(item)
        self._peak_items.clear()
        for peak in peaks:
            band = pg.LinearRegionItem(
                values=(peak.start_rt, peak.end_rt),
                brush=pg.mkBrush(44, 160, 44, 40),
                pen=pg.mkPen(pen_colour, width=1),
                movable=False,
            )
            band.setZValue(-15)
            self.plot.addItem(band, ignoreBounds=True)
            self._peak_items.append(band)

    def clear_peak_markers(self) -> None:
        self.set_peak_markers([])

    # -- apex labels ----------------------------------------------------------- #
    def _headroom_px(self) -> float:
        if not self._show_apex or not self._traces:
            return 0.0
        # labels alternate between one and two text heights above the apex so
        # that neighbouring traces do not overprint; the upper row sets the room
        stacked = 2.15 if len(self._traces) > 1 else 1.1
        return self._label_height_px() * stacked + 4.0

    def set_apex_labels(self, enabled: bool) -> None:
        self._show_apex = enabled
        self._after_traces_changed()
        self._refresh_headroom()

    def _after_traces_changed(self) -> None:
        for item in self._apex_labels:
            self.plot.removeItem(item)
        self._apex_labels.clear()
        traces = self.traces
        if not self._show_apex or len(traces) > 8:
            return
        for n, trace in enumerate(traces):
            x, y = self._display(trace, n)
            if y.size == 0 or float(np.max(np.abs(y))) <= 0:
                continue
            i = int(np.argmax(np.abs(y)))
            text = pg.TextItem(self._label_for(float(x[i])), color=trace.colour,
                               anchor=(0.5, 1.1 + 1.05 * (n % 2)))
            font = QtGui.QFont()
            font.setPointSize(8)
            text.setFont(font)
            text.setPos(float(x[i]), float(y[i]))
            self.plot.addItem(text, ignoreBounds=True)
            self._apex_labels.append(text)


class SpectrumView(BasePlot):
    """Bottom pane: mass spectrum of one scan or of an averaged range."""

    sigExtractRequested = QtCore.pyqtSignal(float, float)  # m/z range for an XIC
    sigIdentifyRequested = QtCore.pyqtSignal(float)        # send an m/z to the finder
    sigPinRequested = QtCore.pyqtSignal()                  # keep this spectrum on screen
    sigUnpinRequested = QtCore.pyqtSignal()
    sigLabelFloorChanged = QtCore.pyqtSignal(float)        # fraction of the tallest in view

    def __init__(self, parent=None):
        super().__init__("m/z", "", "Intensity, cps", parent)
        self._labels: list[pg.TextItem] = []
        #: (m/z, height, drawn downwards) for every peak that could be named
        self._candidates: list[tuple[float, float, bool]] = []
        #: the most labels one view may carry. The region budget is what
        #: usually decides, and it cannot offer more than this many.
        self._n_labels = label_rule.LABEL_REGIONS * label_rule.LABEL_BUDGET
        self._show_labels = True
        #: how tall a peak has to be, as a fraction of the tallest peak *in
        #: view*, to be worth a label. A fraction and not an intensity so
        #: that it survives a zoom, a normalise and the next spectrum.
        self._label_floor = label_rule.LABEL_MIN_RELATIVE
        #: the floor the pool was last filled at, so that lowering the floor
        #: past it refills rather than searching a pool that never held the
        #: small peaks
        self._pool_at: float | None = None
        # re-labelling removes and adds items, and removing one asks the box
        # to re-check its auto-range, which can come straight back here
        self._thinning = False
        self._centroid = False
        self._title = ""
        self._overlay: tuple[list[tuple[float, float]], str, str] | None = None
        self._overlay_items: list[pg.GraphicsObject] = []
        self.legend.setVisible(False)  # the title already names the spectrum

        # the label floor's handle, in the margin the axis reserves rather
        # than over the data — see LabelThresholdHandle
        axis = self.plot.getAxis("left")
        axis.setStyle(
            tickTextOffset=int(axis.style["tickTextOffset"][0] + HANDLE_SPACE))
        self.floor_handle = LabelThresholdHandle()
        self.floor_handle.hide()
        self.plot.scene().addItem(self.floor_handle)
        self.floor_handle.sigDragged.connect(self._floor_dragged)
        self.floor_handle.sigReleased.connect(self._floor_released)
        self.floor_handle.sigReset.connect(self.reset_label_floor)
        #: shown only while the handle is being dragged: a floor that stayed
        #: drawn across the spectrum would be one more line to mistake for
        #: data
        self.floor_line = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen(theme.accent(), width=1,
                         style=QtCore.Qt.PenStyle.DotLine))
        self.floor_line.setZValue(80)
        self.floor_line.hide()
        self.plot.addItem(self.floor_line, ignoreBounds=True)
        self.viewbox.sigResized.connect(self._resized_handle)

        # which labels fit depends on how far apart the peaks are on screen,
        # so it is decided again whenever the view moves
        self.viewbox.sigRangeChanged.connect(self._thin_labels)

    def _y_label_raw(self) -> str:
        return "Intensity, cps"

    def retheme(self) -> None:
        super().retheme()
        self.floor_handle.set_colour(theme.accent())
        self.floor_line.setPen(pg.mkPen(theme.accent(), width=1,
                                        style=QtCore.Qt.PenStyle.DotLine))

    def _format_readout(self, x: float, y: float) -> str:
        return f"m/z {x:.4f}    {y:,.0f}"

    def set_title(self, text: str) -> None:
        self._title = text
        self.plot.setTitle(text, color=theme.foreground(), size="10pt")

    @property
    def title(self) -> str:
        return self._title

    # -- centroiding ----------------------------------------------------------- #
    def condition(self, trace: Trace) -> tuple[np.ndarray, np.ndarray]:
        x, y = super().condition(trace)
        if self._centroid:
            return centroid_spectrum(x, y)
        # a profile spectrum whose zeros were stripped out draws a slope
        # across every empty stretch; putting them back is a drawing repair
        # and adds no intensity anywhere. Data that already has them is
        # returned unchanged.
        return restore_profile_zeros(x, y)

    def set_centroid(self, enabled: bool) -> None:
        self._centroid = enabled
        self._stick_mode = enabled
        self.redraw()
        self.autoscale()

    @property
    def centroided(self) -> bool:
        return self._centroid

    # -- labels ---------------------------------------------------------------- #
    def _headroom_px(self) -> float:
        # a peak label is anchored one text height above the apex, and a match
        # label 1.6 of them; the base peak carries whichever is on
        if self._show_labels and self._n_labels:
            factor = 1.6 if self._match_labels else 1.0
        elif self._match_labels:
            factor = 1.6
        else:
            return 0.0
        return self._label_height_px() * factor + 4.0

    def set_labels_enabled(self, enabled: bool) -> None:
        self._show_labels = enabled
        self._after_traces_changed()
        self._refresh_headroom()

    def set_label_count(self, n: int) -> None:
        self._n_labels = max(0, int(n))
        self._after_traces_changed()
        self._refresh_headroom()

    # -- the label floor and its handle ---------------------------------- #
    @property
    def label_floor(self) -> float:
        """The floor, as a fraction of the tallest peak in view."""
        return self._label_floor

    def set_label_floor(self, fraction: float, notify: bool = True,
                        refill: bool = True) -> None:
        """
        Move the floor. `fraction` is of the tallest peak *in view*.

        The pool is refilled when the floor moves, because a peak the pool
        never held cannot be named however low the floor goes — but only
        when `refill` allows it. A drag says no: filling the pool walks every
        point of the spectrum, 255,000 of them on an infusion's averaged
        product-ion scan, and it was measured at half a second. So the labels
        follow the mouse out of the pool as it stands and the pool is filled
        again when the button comes up.
        """
        try:
            value = float(fraction)
        except (TypeError, ValueError):
            return
        if not np.isfinite(value):
            return
        value = min(max(value, FLOOR_MIN), FLOOR_MAX)
        changed = value != self._label_floor
        self._label_floor = value
        if refill and self._pool_floor() != self._pool_at:
            self._after_traces_changed()
        else:
            self._thin_labels()
        self._place_floor_handle()
        if changed and notify:
            self.sigLabelFloorChanged.emit(value)

    def reset_label_floor(self) -> None:
        """Back to the default — 2% of the tallest peak in view."""
        self.set_label_floor(label_rule.LABEL_MIN_RELATIVE)

    def _pool_floor(self) -> float:
        """
        How far down the pool has to reach for this floor: a tenth of it,
        which is what `POOL_MIN_RELATIVE` already was for the default 2%.
        """
        return min(POOL_MIN_RELATIVE, max(self._label_floor, FLOOR_MIN) / 10.0)

    def _pool_size(self) -> int:
        """How many maxima to keep, once the floor has taken the pool down."""
        floor = max(self._pool_floor(), FLOOR_MIN)
        room = int(LABEL_POOL * POOL_MIN_RELATIVE / floor)
        return int(min(MAX_POOL, max(LABEL_POOL, room)))

    def _tallest_in_view(self) -> float | None:
        """
        The tallest candidate between the ends of the visible mass axis.

        The same ceiling `labels.choose` measures the floor against, read
        here so the handle sits exactly where the rule cuts.
        """
        if not self._candidates:
            return None
        (x_low, x_high), _y = self.viewbox.viewRange()
        heights = [height for mz, height, _below in self._candidates
                   if x_low <= mz <= x_high]
        top = max(heights) if heights else 0.0
        return top if top > 0 else None

    def _resized_handle(self, *_args) -> None:
        """
        The handle's place is in pixels, so a resize moves it even when the
        range has not changed.

        A hidden pane is skipped for the reason `_resized` gives: a stacked
        rebuild resizes the panes it is destroying, and they arrive here
        hidden.
        """
        if self.isVisible():
            self._place_floor_handle()

    def _place_floor_handle(self, *_args) -> None:
        """Put the handle at the floor's screen position, on every change."""
        top = self._tallest_in_view()
        if top is None or not self._show_labels or not self._n_labels:
            self.floor_handle.hide()
            self.floor_line.hide()
            return
        value = top * self._label_floor
        rect = self.viewbox.sceneBoundingRect()
        y = float(self.viewbox.mapViewToScene(
            QtCore.QPointF(0.0, value)).y())
        # a floor above the top of the view, or below its bottom, still has a
        # handle: it is dragged back from the edge it is pinned to
        y = min(max(y, rect.top()), rect.bottom())
        self.floor_handle.setPos(rect.left() - 1.0, y)
        self.floor_handle.show()
        self.floor_line.setPos(value)

    def _floor_dragged(self, scene_y: float) -> None:
        top = self._tallest_in_view()
        if not top:
            return
        point = QtCore.QPointF(self.viewbox.sceneBoundingRect().left(),
                               float(scene_y))
        value = float(self.viewbox.mapSceneToView(point).y())
        self.floor_line.show()
        self.set_label_floor(value / top, refill=False)

    def _floor_released(self) -> None:
        self.floor_line.hide()
        if self._pool_floor() != self._pool_at:
            self._after_traces_changed()

    def peaks_of_current(self, max_peaks: int = 50) -> list[tuple[float, float]]:
        traces = self.traces
        if not traces:
            return []
        x, y = self.condition(traces[0])
        # centroid mode has already reduced the profile to sticks; centroiding
        # again averages a stick with its neighbours and moves the mass — a
        # ceramide's 264.2668 was being reported as 264.1181
        return pick_peaks(x, y, max_peaks=max_peaks, min_relative=0.005,
                          min_distance=0.03, centroid=not self._centroid)

    # -- theoretical overlay ---------------------------------------------------- #
    def set_overlay(self, peaks: list[tuple[float, float]], label: str = "",
                    colour: str = "#7a3fbf") -> None:
        """
        Draw a theoretical isotope pattern over the measured spectrum, scaled to
        its base peak so the two can be compared by eye.
        """
        self._overlay = (list(peaks), label, colour) if peaks else None
        self._draw_overlay()

    def clear_overlay(self) -> None:
        self._overlay = None
        self._draw_overlay()

    @property
    def has_overlay(self) -> bool:
        return self._overlay is not None

    def _draw_overlay(self) -> None:
        for item in self._overlay_items:
            self.plot.removeItem(item)
        self._overlay_items.clear()
        if self._overlay is None:
            return
        peaks, label, colour = self._overlay
        scale = self._overlay_scale(peaks)
        xs, ys = [], []
        for mz, abundance in peaks:
            xs.extend([mz, mz, np.nan])
            ys.extend([0.0, abundance * scale, np.nan])
        curve = self.plot.plot(
            np.array(xs), np.array(ys), connect="finite",
            pen=pg.mkPen(colour, width=1.6, style=QtCore.Qt.PenStyle.DashLine),
        )
        curve.setZValue(-5)
        self._overlay_items.append(curve)
        if label:
            text = pg.TextItem(label, color=colour, anchor=(0, 0))
            font = QtGui.QFont()
            font.setPointSize(9)
            text.setFont(font)
            rect = self.viewbox.viewRect()
            text.setPos(rect.left(), rect.top())
            self.plot.addItem(text, ignoreBounds=True)
            self._overlay_items.append(text)

    def _overlay_scale(self, peaks: list[tuple[float, float]],
                       tolerance: float = 0.02) -> float:
        """
        Height for the theoretical pattern.

        It is anchored on the measured monoisotopic peak, not on the base peak
        of the spectrum: the ion being identified is often a minor one, and
        scaling to the tallest peak in the scan would either bury the overlay
        or make it tower over the data, in both cases making the satellite
        heights impossible to compare by eye.
        """
        traces = self.traces
        if not traces or not peaks:
            return 1.0
        x, y = self.condition(traces[0])
        if y.size == 0:
            return 1.0
        if self._normalise:
            peak = float(np.max(np.abs(y)))
            y = y / peak * 100.0 if peak > 0 else y
        target = peaks[0][0]
        window = (x >= target - tolerance) & (x <= target + tolerance)
        if window.any() and float(y[window].max()) > 0:
            return float(y[window].max()) / max(peaks[0][1], 1e-12)
        return float(np.max(y))

    def _after_traces_changed(self) -> None:
        """
        Find the peaks that could carry a label, once per set of traces.

        The peak finder walks every point — thirty thousand of them on an
        infusion product-ion scan — so it is not run again on a pan. What it
        yields is a pool that reaches further down than a label ever will;
        which of the pool are named is decided at the current view range, on
        every range change, by `_thin_labels`.
        """
        self._draw_overlay()
        self._candidates = []
        self._pool_at = self._pool_floor()
        if self._show_labels and self._n_labels:
            for n, trace in enumerate(self.traces):
                x, y = self._display(trace, n)
                below = bool(self._mirror and n % 2 == 1)
                for mz, intensity in pick_peaks(x, np.abs(y),
                                                max_peaks=self._pool_size(),
                                                min_relative=self._pool_floor(),
                                                min_distance=0.05):
                    self._candidates.append((mz, intensity, below))
        self._thin_labels()

    def _thin_labels(self, *_args) -> None:
        """
        Decide which peaks of the pool are named at the current view range.

        Two passes. First `labels.choose` gives every eighth of the visible
        mass axis a budget of three labels and orders them so that the tallest
        peak of each region asks for room before any region asks for a second
        — without it the twelve tallest peaks of a real survey scan were all
        inside the first eighth of the axis and half the spectrum was drawn
        and never named. Then the collision rule as before: a label that would
        print on top of one already placed is dropped, not overlapped. Two
        peaks a few millidaltons apart are one pixel apart on a full spectrum,
        and their labels drawn over one another are worse than unreadable —
        the result looks like a single wrong number.

        Both passes follow the view, which is the point of doing this on every
        range change rather than once: zoomed in, each region is narrower, the
        peaks in it are further apart in pixels, and more of them get named.

        A label at the right-hand end used to run off the edge — the precursor
        is at the end of its own scan window, so this was the normal case for
        a product ion spectrum. Widening the mass axis to fit the text would
        be showing masses that were never scanned; the text is anchored to its
        other side instead.
        """
        if self._thinning:
            return
        self._thinning = True
        try:
            self._retag_labels()
        finally:
            self._thinning = False

    def _retag_labels(self) -> None:
        """`_thin_labels` without the guard against being re-entered."""
        for item in self._labels:
            self.plot.removeItem(item)
        self._labels.clear()
        self._place_floor_handle()
        if not self._candidates:
            return
        box = self.viewbox
        width = float(box.width())
        (x_low, x_high), _y = box.viewRange()
        if width <= 0 or x_high <= x_low:
            return
        chosen = label_rule.choose(
            self._candidates, x_low, x_high,
            most=self._n_labels or None,
            min_relative=self._label_floor)
        scale = width / (x_high - x_low)
        taken: list[tuple[float, float]] = []
        for mz, intensity, below in chosen:
            sign = -1.0 if below else 1.0
            text = pg.TextItem(self._label_for(mz), color=theme.foreground(),
                               anchor=(0.5, 0.0 if below else 1.0))
            font = QtGui.QFont()
            font.setPointSize(8)
            text.setFont(font)
            text.setPos(mz, intensity * sign)
            text.mz = mz
            text.below = below
            half = _label_half_width(text)
            centre = (mz - x_low) * scale
            anchor_x = 0.5
            if centre - half < 0:
                anchor_x, left = 0.0, centre
            elif centre + half > width:
                anchor_x, left = 1.0, centre - 2 * half
            else:
                left = centre - half
            right = left + 2 * half
            if right < 0 or left > width:
                continue
            if any(left < other_right + LABEL_GAP and right > other_left - LABEL_GAP
                   for other_left, other_right in taken):
                continue
            text.setAnchor(pg.Point(anchor_x, 0.0 if below else 1.0))
            self.plot.addItem(text, ignoreBounds=True)
            self._labels.append(text)
            taken.append((left, right))

    def contextMenuEvent(self, event):
        selection = self.selected_range()
        menu = QtWidgets.QMenu(self)
        local = self.plot.mapFromGlobal(event.globalPos())
        position = float(self.viewbox.mapSceneToView(self.plot.mapToScene(local)).x())

        extract = menu.addAction("Extract XIC from selection")
        extract.setEnabled(selection is not None)
        identify = menu.addAction("Find formula for this peak")
        menu.addSeparator()
        add_marker = menu.addAction("Add marker here")
        clear_markers = menu.addAction("Clear markers")
        clear_markers.setEnabled(bool(self._arrows))
        clear_overlay = menu.addAction("Clear theoretical overlay")
        clear_overlay.setEnabled(self.has_overlay)
        reset_floor = menu.addAction("Reset label floor")
        reset_floor.setEnabled(
            self._label_floor != label_rule.LABEL_MIN_RELATIVE)
        menu.addSeparator()
        pin = menu.addAction("Pin this spectrum")
        pin.setEnabled(any(t.key == "spec" for t in self._traces))
        unpin = menu.addAction("Unpin spectra")
        unpin.setEnabled(any(t.key.startswith("pin") for t in self._traces))

        chosen = menu.exec(event.globalPos())
        if chosen is extract and selection:
            self.sigExtractRequested.emit(*selection)
        elif chosen is identify:
            self.sigIdentifyRequested.emit(self._snap_to_peak(position))
        elif chosen is add_marker:
            self.add_marker(position)
        elif chosen is clear_markers:
            self.clear_markers()
        elif chosen is clear_overlay:
            self.clear_overlay()
        elif chosen is reset_floor:
            self.reset_label_floor()
        elif chosen is pin:
            self.sigPinRequested.emit()
        elif chosen is unpin:
            self.sigUnpinRequested.emit()
