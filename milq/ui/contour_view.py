"""
The contour: retention time across, m/z up, intensity as colour.

The picture exists to show a neighbourhood — an interference half a dalton
from a target, a second species under the same peak, a contaminant ridge down
the whole run. So the parts that matter are the ones that decide what is
visible: the intensity scale, because chromatographic data spans four or five
decades and a linear ramp shows the base peak and nothing else, and the upper
level, because one saturated scan otherwise sets the scale for the entire
surface.

On an infusion the same surface is a film. There is no chromatography, so
nothing moves along the time axis except the spray itself: a fragment is a
ridge at constant m/z running the length of the run, and a spray transient is
a bright column one scan wide. The average that an infusion is read from
hides both. So the film mode adds the three things that say what the average
was made of — the total ion current as a strip on the same time axis, a mark
on the scans left out of that average, and a Play button that steps the
spectrum pane through the run at a fixed number of scans a second.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from ..contour import Contour
from .flow_layout import FlowLayout

#: how the intensities are compressed before they become colour. Square root
#: is the default because it lifts the minor ions into view without the
#: flattening that makes a log plot of chromatographic data look uniformly
#: grey; linear is there for the rare case of wanting the base peak alone.
LINEAR, SQRT, LOG = "linear", "square root", "logarithmic"
SCALES = (SQRT, LOG, LINEAR)

#: the intensity that becomes the top of the colour scale. Not the maximum:
#: a single saturated or spiking scan would then set the scale for everything
#: else and leave the rest of the surface black.
TOP_PERCENTILE = 99.7

MAPS = ("inferno", "viridis", "magma", "turbo", "CET-L9")

#: scans a second at 1x. The real infusions cycle every 0.25 s — four scans a
#: second — so ten a second is two and a half times life: a 473-scan run is
#: 47 seconds of film, and a one-scan burst is still one visible frame. What
#: is actually reached is what the file allows; measured, a frame costs
#: 52 ms on one real infusion and 89 ms on another, so 1x runs as asked and
#: 20x runs at about nineteen scans a second rather than two hundred.
PLAY_RATE = 10.0

#: what Play's speeds multiply that by
SPEEDS = ((" 1×", 1), (" 5×", 5), ("20×", 20))

#: the most excluded stretches shaded on the surface itself. The strip marks
#: every one of them whatever their number; the shading is there to be seen
#: at a glance, and forty translucent regions is already past that.
MAX_EXCLUDED_REGIONS = 40

#: how wide the left axis of both the strip and the surface is held. They are
#: two plots with one time axis, and pyqtgraph sizes each one's left axis to
#: its own tick text — "1.5e+06" against "450" — so without this the two
#: drawing areas start at different pixels and a burst in the strip does not
#: sit over the column it made. Linking the x range is not enough; the
#: alignment is geometry.
AXIS_WIDTH = 74


class ContourView(QtWidgets.QWidget):
    """A channel's scans as a surface, with a readout and a picker."""

    #: a point in the surface — retention time, m/z
    sigPointPicked = QtCore.pyqtSignal(float, float)
    #: the visible rectangle — rt low, rt high, m/z low, m/z high
    sigRegionPicked = QtCore.pyqtSignal(float, float, float, float)
    sigRebuildRequested = QtCore.pyqtSignal()
    #: Play asks for a scan, by index. The pane that owns the scan spin box
    #: is what actually moves; this widget knows only how many there are.
    sigScanRequested = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._contour = Contour()
        #: the film's own axes, None until `set_film`
        self._film_times: np.ndarray | None = None
        self._film_excluded: np.ndarray | None = None
        self._current_scan = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        bar = FlowLayout()
        bar.addWidget(QtWidgets.QLabel("Intensity"))
        self.scale = QtWidgets.QComboBox()
        self.scale.addItems(list(SCALES))
        self.scale.setToolTip(
            "Chromatographic intensity spans four or five decades. On a "
            "linear scale everything but the base peak is black")
        bar.addWidget(self.scale)
        bar.addWidget(QtWidgets.QLabel("Colours"))
        self.palette = QtWidgets.QComboBox()
        self.palette.addItems(list(MAPS))
        bar.addWidget(self.palette)
        self.btn_extract = QtWidgets.QPushButton("Extract this view")
        self.btn_extract.setToolTip(
            "Take the chromatogram and spectrum of the rectangle on screen: "
            "zoom to what you want, then press this")
        bar.addWidget(self.btn_extract)
        self.btn_rebuild = QtWidgets.QPushButton("Rebuild")
        self.btn_rebuild.setToolTip(
            "Read the scans again over the times and masses now on screen, "
            "so a region gets the full grid instead of a magnified one")
        bar.addWidget(self.btn_rebuild)
        bar.addStretch(1)
        self.readout = QtWidgets.QLabel("")
        self.readout.setProperty("role", "caption")
        bar.addWidget(self.readout)
        layout.addLayout(bar)

        layout.addLayout(self._build_film_bar())
        layout.addWidget(self._build_strip())

        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.setLabel("bottom", "Retention time", units="min")
        self.plot.setLabel("left", "m/z")
        theme.style_axes(self.plot)
        # an infusion lasts under a minute, and pyqtgraph then relabels the
        # axis in *milli*-minutes: 0.62 min drawn as 600 mmin. The unit here
        # is the one the instrument reports in and it does not change.
        self.plot.getAxis("bottom").enableAutoSIPrefix(False)
        self.plot.getAxis("left").setStyle(autoExpandTextSpace=False)
        self.plot.getAxis("left").setWidth(AXIS_WIDTH)
        self.image = pg.ImageItem()
        self.plot.addItem(self.image)
        self.plot.setMenuEnabled(False)

        pen = pg.mkPen(theme.muted(), width=1,
                       style=QtCore.Qt.PenStyle.DashLine)
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        for line in (self._vline, self._hline):
            line.setVisible(False)
            line.setZValue(10)
            self.plot.addItem(line, ignoreBounds=True)

        #: where the scan the spectrum pane is showing sits on the surface
        self.film_cursor = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen(theme.accent(), width=2))
        self.film_cursor.setVisible(False)
        self.film_cursor.setZValue(12)
        self.plot.addItem(self.film_cursor, ignoreBounds=True)
        #: the excluded stretches, shaded on the surface itself
        self._excluded_regions: list[pg.LinearRegionItem] = []

        layout.addWidget(self.plot, 1)

        self.status = QtWidgets.QLabel("No contour yet.")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        # the strip is the same time axis as the surface, so it is linked to
        # it rather than given its own: zooming the surface moves both, and a
        # burst stays over the column it made
        self.strip.setXLink(self.plot)

        self.scale.currentTextChanged.connect(self._redraw)
        self.palette.currentTextChanged.connect(self._redraw)
        self.btn_rebuild.clicked.connect(self.sigRebuildRequested)
        self.btn_extract.clicked.connect(self._emit_region)
        self.plot.scene().sigMouseMoved.connect(self._on_moved)
        self.plot.scene().sigMouseClicked.connect(self._on_clicked)

        self.btn_play.toggled.connect(self._play_toggled)
        self.speed.currentIndexChanged.connect(self._speed_changed)
        self._timer.timeout.connect(self._advance)

    # -- the film -------------------------------------------------------- #
    def _build_film_bar(self) -> QtWidgets.QHBoxLayout:
        """Play, its speed, and what is being left out of the average."""
        bar = FlowLayout()
        self.btn_play = QtWidgets.QToolButton()
        self.btn_play.setCheckable(True)
        self.btn_play.setText("▶ Play")
        self.btn_play.setToolTip(
            f"Step the spectrum pane through every scan of the run at "
            f"{PLAY_RATE:g} scans a second, times the speed beside this. "
            f"Press again to pause; it stops on its own at the last scan")
        bar.addWidget(self.btn_play)
        self.speed = QtWidgets.QComboBox()
        for text, factor in SPEEDS:
            self.speed.addItem(text, factor)
        self.speed.setToolTip("How much faster than the base rate Play runs")
        bar.addWidget(self.speed)
        self.film_scan = QtWidgets.QLabel("")
        self.film_scan.setMinimumWidth(210)
        bar.addWidget(self.film_scan)
        self.film_note = QtWidgets.QLabel("")
        self.film_note.setProperty("role", "caption")
        bar.addWidget(self.film_note)
        bar.addStretch(1)

        self._timer = QtCore.QTimer(self)
        # a repeating timer rather than a thread: reading a scan and drawing
        # it is what takes the time, and both have to happen on this thread
        # anyway. A tick that arrives while the last one is still drawing is
        # dropped by Qt, which is the right answer — the film runs slower
        # rather than falling behind itself.
        self._timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self._film_widgets = (self.btn_play, self.speed, self.film_scan,
                              self.film_note)
        for widget in self._film_widgets:
            widget.setVisible(False)
        return bar

    def _build_strip(self) -> QtWidgets.QWidget:
        """The run's total ion current, on the surface's own time axis."""
        self.strip = pg.PlotWidget(background=theme.background())
        self.strip.setFixedHeight(92)
        self.strip.setMenuEnabled(False)
        self.strip.setMouseEnabled(x=True, y=False)
        self.strip.hideAxis("bottom")   # the surface underneath carries it
        self.strip.setLabel("left", "TIC")
        theme.style_axes(self.strip, faint=True)
        self.strip.getAxis("left").setStyle(autoExpandTextSpace=False)
        self.strip.getAxis("left").setWidth(AXIS_WIDTH)
        self.strip_curve = pg.PlotCurveItem(pen=pg.mkPen(theme.accent(), width=1))
        self.strip.addItem(self.strip_curve)
        #: the scans left out of the average, drawn where they happened
        self.strip_excluded = pg.ScatterPlotItem(
            size=6, symbol="x", pen=pg.mkPen(theme.danger(), width=1),
            brush=pg.mkBrush(theme.danger()))
        self.strip_excluded.setZValue(5)
        self.strip.addItem(self.strip_excluded)
        self.strip_cursor = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(theme.accent(), width=2))
        self.strip_cursor.setVisible(False)
        self.strip.addItem(self.strip_cursor, ignoreBounds=True)
        self.strip.setVisible(False)
        return self.strip

    def set_film(self, times, tic, excluded=None, label: str = "") -> None:
        """
        Show the run as a film: the strip, the excluded scans and Play.

        `times` and `tic` are the channel's own chromatogram, one point per
        scan, so the strip is the instrument's arithmetic rather than the
        grid's — the surface's rows may be several scans averaged and its
        m/z bins are wider than the instrument's steps. `excluded` is a
        boolean per scan: True for a scan that is *not* in the average the
        infusion is read from.
        """
        times = np.asarray(times, dtype=float)
        values = np.asarray(tic, dtype=float)
        if times.size == 0 or times.size != values.size:
            self.clear_film()
            return
        self._film_times = times
        if excluded is None:
            excluded = np.zeros(times.size, dtype=bool)
        excluded = np.asarray(excluded, dtype=bool)
        if excluded.size != times.size:
            excluded = np.zeros(times.size, dtype=bool)
        self._film_excluded = excluded

        self.strip_curve.setData(times, values)
        self.strip_excluded.setData(times[excluded], values[excluded])
        self._shade_excluded(times, excluded)
        left = int(np.count_nonzero(excluded))
        self.film_note.setText(
            f"{left} scan(s) left out of the average, marked ✕"
            if left else "every scan is in the average")
        self.film_note.setToolTip(
            "The average an infusion is read from is not always every scan: "
            "the settling window at the front of the run is left out of the "
            "flatness measurement, and a spray transient is not the spray.")
        self.strip.setVisible(True)
        for widget in self._film_widgets:
            widget.setVisible(True)
        self.strip.setToolTip(
            f"{label + ': ' if label else ''}the total ion current of every "
            f"scan, on the same time axis as the surface")
        self.set_current_scan(min(self._current_scan, times.size - 1))

    def clear_film(self) -> None:
        """Back to an ordinary surface: no strip, no cursor, no Play."""
        self.stop_play()
        self._film_times = None
        self._film_excluded = None
        self.strip_curve.setData(np.zeros(0), np.zeros(0))
        self.strip_excluded.setData(np.zeros(0), np.zeros(0))
        self._shade_excluded(np.zeros(0), np.zeros(0, dtype=bool))
        self.strip.setVisible(False)
        self.film_cursor.setVisible(False)
        self.strip_cursor.setVisible(False)
        for widget in self._film_widgets:
            widget.setVisible(False)

    @property
    def film_shown(self) -> bool:
        return self._film_times is not None

    @property
    def excluded_regions(self) -> list:
        """The shaded stretches, for anything that wants to count them."""
        return list(self._excluded_regions)

    def _shade_excluded(self, times: np.ndarray, excluded: np.ndarray) -> None:
        """One translucent region per run of excluded scans, on the surface."""
        for region in self._excluded_regions:
            self.plot.removeItem(region)
        self._excluded_regions = []
        if times.size == 0 or not np.any(excluded):
            return
        colour = QtGui.QColor(theme.danger())
        colour.setAlpha(48)
        edges = np.diff(np.concatenate(([0], excluded.view(np.int8), [0])))
        starts = np.nonzero(edges == 1)[0]
        ends = np.nonzero(edges == -1)[0] - 1
        half = float(np.median(np.diff(times))) / 2.0 if times.size > 1 else 0.0
        for first, last in list(zip(starts, ends))[:MAX_EXCLUDED_REGIONS]:
            region = pg.LinearRegionItem(
                values=(times[first] - half, times[last] + half),
                brush=pg.mkBrush(colour), movable=False)
            region.setZValue(8)
            region.lines[0].setPen(pg.mkPen(None))
            region.lines[1].setPen(pg.mkPen(None))
            self.plot.addItem(region, ignoreBounds=True)
            self._excluded_regions.append(region)

    def set_current_scan(self, index: int) -> None:
        """Move the cursor to a scan — the pane showing it decides, not Play."""
        times = self._film_times
        if times is None or times.size == 0:
            return
        self._current_scan = int(np.clip(index, 0, times.size - 1))
        at = float(times[self._current_scan])
        for line in (self.film_cursor, self.strip_cursor):
            line.setPos(at)
            line.setVisible(True)
        left_out = (self._film_excluded is not None
                    and bool(self._film_excluded[self._current_scan]))
        self.film_scan.setText(
            f"scan {self._current_scan + 1}/{times.size} · {at:.4f} min"
            + (" · left out" if left_out else ""))

    def current_scan(self) -> int:
        return self._current_scan

    # -- Play ---------------------------------------------------------------- #
    @property
    def playing(self) -> bool:
        return self._timer.isActive()

    def _interval_ms(self) -> int:
        factor = self.speed.currentData() or 1
        return max(1, int(round(1000.0 / (PLAY_RATE * float(factor)))))

    def start_play(self) -> None:
        """Run the film from where the pane is, or from the start if it ended."""
        times = self._film_times
        if times is None or times.size < 2:
            self.btn_play.setChecked(False)
            return
        if self._current_scan >= times.size - 1:
            self._current_scan = 0
            self.sigScanRequested.emit(0)
        self._timer.start(self._interval_ms())
        self.btn_play.setText("❚❚ Pause")

    def stop_play(self) -> None:
        self._timer.stop()
        self.btn_play.setText("▶ Play")
        if self.btn_play.isChecked():
            self.btn_play.blockSignals(True)
            self.btn_play.setChecked(False)
            self.btn_play.blockSignals(False)

    def _play_toggled(self, playing: bool) -> None:
        self.start_play() if playing else self.stop_play()

    def _speed_changed(self, *_args) -> None:
        if self.playing:
            self._timer.start(self._interval_ms())

    def _advance(self) -> None:
        """One frame. The last scan stops the film rather than wrapping."""
        times = self._film_times
        if times is None or times.size == 0:
            self.stop_play()
            return
        following = self._current_scan + 1
        if following >= times.size:
            self.stop_play()
            return
        self.set_current_scan(following)
        self.sigScanRequested.emit(following)

    # -- content ------------------------------------------------------------- #
    def set_contour(self, contour: Contour, title: str = "") -> None:
        self._contour = contour
        if contour.is_empty:
            self.image.clear()
            self.status.setText(contour.note or "Nothing to draw.")
            return
        self._redraw()
        rt_lo, rt_hi = contour.rt_range
        mz_lo, mz_hi = contour.mz_range
        said = [f"{contour.scans:,} scans", f"{rt_lo:.2f}–{rt_hi:.2f} min",
                f"m/z {mz_lo:.1f}–{mz_hi:.1f}",
                f"{contour.intensity.shape[0]} × {contour.intensity.shape[1]} cells"]
        if contour.note:
            said.append(contour.note)
        self.status.setText(" · ".join(([title] if title else []) + said))
        self.plot.setXRange(rt_lo, rt_hi, padding=0)
        self.plot.setYRange(mz_lo, mz_hi, padding=0)

    def contour(self) -> Contour:
        return self._contour

    def view_ranges(self) -> tuple[float, float, float, float]:
        (x0, x1), (y0, y1) = self.plot.viewRange()
        return float(x0), float(x1), float(y0), float(y1)

    # -- drawing ------------------------------------------------------------- #
    def _redraw(self, *_args) -> None:
        contour = self._contour
        if contour.is_empty:
            return
        values = np.clip(contour.intensity, 0.0, None)
        mode = self.scale.currentText()
        if mode == SQRT:
            shown = np.sqrt(values)
        elif mode == LOG:
            shown = np.log1p(values)
        else:
            shown = values

        above = shown[shown > 0]
        top = (float(np.percentile(above, TOP_PERCENTILE)) if above.size
               else 1.0)
        if top <= 0:
            top = float(shown.max()) or 1.0

        self.image.setImage(shown, autoLevels=False, levels=(0.0, top))
        self.image.setColorMap(pg.colormap.get(self.palette.currentText()))
        left, bottom, width, height = contour.rect
        self.image.setRect(QtCore.QRectF(left, bottom, width, height))

    # -- interaction ---------------------------------------------------------- #
    def _point_at(self, position) -> tuple[float, float] | None:
        if self._contour.is_empty:
            return None
        if not self.plot.sceneBoundingRect().contains(position):
            return None
        point = self.plot.getViewBox().mapSceneToView(position)
        return float(point.x()), float(point.y())

    def _on_moved(self, position) -> None:
        found = self._point_at(position)
        if found is None:
            self._vline.setVisible(False)
            self._hline.setVisible(False)
            self.readout.setText("")
            return
        rt, mz = found
        self._vline.setPos(rt)
        self._hline.setPos(mz)
        self._vline.setVisible(True)
        self._hline.setVisible(True)
        intensity = self._contour.at(rt, mz)
        self.readout.setText(
            f"{rt:.3f} min · m/z {mz:.4f}"
            + (f" · {intensity:,.0f}" if intensity is not None else ""))

    def _on_clicked(self, event) -> None:
        found = self._point_at(event.scenePos())
        if found is not None:
            self.sigPointPicked.emit(*found)

    def _emit_region(self) -> None:
        if not self._contour.is_empty:
            self.sigRegionPicked.emit(*self.view_ranges())
