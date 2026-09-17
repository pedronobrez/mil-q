"""
Chromatogram area: one pane, or one pane per trace with linked time axes.

Stacking is PeakView's "split traces into separate panes" combined with
"link graph x-axis": each sample gets its own vertical space and its own
intensity scale, while zooming or panning any of them moves all of them
together, so the same retention time is always under the same screen column.
"""

from __future__ import annotations

import numpy as np
from PyQt6 import QtCore, QtWidgets

from ..processing import ChromPeak
from .plots import ChromatogramView, Trace


#: the least a stacked pane can be and still be a chromatogram. Twenty-six
#: samples in the height of one plot gives each about thirty pixels — one tick
#: label, no axis, the trace a smear — so past that many the area scrolls
#: instead of dividing further.
MIN_STACKED_PANE = 110


class ChromatogramArea(QtWidgets.QWidget):
    """Holds the chromatogram panes and keeps their display options in sync."""

    # the str carries the key of the pane's own trace ("" when not stacked)
    sigClicked = QtCore.pyqtSignal(str, float)
    sigRangeSelected = QtCore.pyqtSignal(str, float, float)
    sigRangeDragging = QtCore.pyqtSignal(str, float, float)
    sigBackgroundChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._traces: list[Trace] = []
        self._stacked = False
        self._syncing = False
        self._options = {
            "normalised": False,
            "smoothing": 0.0,
            "baseline": 0.0,
            "mirror": False,
            "offsets": (0.0, 0.0),
            "apex_labels": True,
            "legend": True,
            "select_mode": False,
            "overview": False,
            "relative_labels": True,
        }

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.splitter)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

        self._views: list[ChromatogramView] = []
        self._keys: list[str] = []
        self._active = 0
        self._add_view("")

    # -- panes ---------------------------------------------------------------- #
    def _add_view(self, key: str) -> ChromatogramView:
        view = ChromatogramView()
        self._apply_options(view)
        view.sigClicked.connect(lambda x, v=view: self._on_clicked(v, x))
        view.sigRangeSelected.connect(lambda a, b, v=view: self._on_selected(v, a, b))
        view.sigRangeDragging.connect(lambda a, b, v=view: self._on_dragging(v, a, b))
        view.sigFocused.connect(lambda v=view: self._set_active(v))
        view.sigBackgroundChanged.connect(self.sigBackgroundChanged)
        view.plot.getViewBox().sigXRangeChanged.connect(
            lambda _vb, rng, v=view: self._link_x(v, rng)
        )
        self.splitter.addWidget(view)
        self._views.append(view)
        self._keys.append(key)
        return view

    def _rebuild(self) -> None:
        """Recreate the panes for the current trace set and stacking mode."""
        background = self.background_range()
        for view in self._views:
            view.setParent(None)
            view.deleteLater()
        self._views.clear()
        self._keys.clear()
        self._active = 0

        if self._stacked and self._traces:
            for trace in self._traces:
                view = self._add_view(trace.key)
                view.set_traces([trace])
        else:
            view = self._add_view("")
            view.set_traces(self._traces)

        if background is not None:
            for view in self._views:
                view.background.blockSignals(True)
                view.set_background_range(*background)
                view.background.blockSignals(False)
        self._keep_panes_readable()
        self.autoscale()

    def _keep_panes_readable(self) -> None:
        """Scroll rather than shrink once the panes would stop being legible."""
        wanted = len(self._views) * MIN_STACKED_PANE if self._stacked else 0
        self.splitter.setMinimumHeight(wanted if wanted > self.scroll.height() else 0)

    def set_stacked(self, enabled: bool) -> None:
        if enabled == self._stacked:
            return
        self._stacked = enabled
        self._rebuild()

    @property
    def stacked(self) -> bool:
        return self._stacked

    @property
    def views(self) -> list[ChromatogramView]:
        return list(self._views)

    @property
    def active_view(self) -> ChromatogramView:
        return self._views[min(self._active, len(self._views) - 1)]

    @property
    def active_key(self) -> str:
        return self._keys[min(self._active, len(self._keys) - 1)]

    def _set_active(self, view: ChromatogramView) -> None:
        if view in self._views:
            self._active = self._views.index(view)

    # -- x axis linking -------------------------------------------------------- #
    def _link_x(self, source: ChromatogramView, rng) -> None:
        if self._syncing or len(self._views) < 2:
            return
        self._syncing = True
        try:
            for view in self._views:
                if view is not source:
                    view.plot.getViewBox().setXRange(rng[0], rng[1], padding=0)
        finally:
            self._syncing = False

    def set_x_range(self, lo: float, hi: float) -> None:
        self._views[0].plot.setXRange(lo, hi)

    # -- signal relays --------------------------------------------------------- #
    def _on_clicked(self, view: ChromatogramView, x: float) -> None:
        self._set_active(view)
        self.sigClicked.emit(self._key_of(view), x)

    def _on_selected(self, view: ChromatogramView, x0: float, x1: float) -> None:
        self._set_active(view)
        self.sigRangeSelected.emit(self._key_of(view), x0, x1)

    def _on_dragging(self, view: ChromatogramView, x0: float, x1: float) -> None:
        self._set_active(view)
        self.sigRangeDragging.emit(self._key_of(view), x0, x1)

    def _key_of(self, view: ChromatogramView) -> str:
        return self._keys[self._views.index(view)] if view in self._views else ""

    # -- traces ---------------------------------------------------------------- #
    def set_traces(self, traces: list[Trace]) -> None:
        self._traces = list(traces)
        if self._stacked:
            self._rebuild()
        else:
            self._views[0].set_traces(self._traces)

    def clear_traces(self) -> None:
        self.set_traces([])

    @property
    def traces(self) -> list[Trace]:
        return list(self._traces)

    def conditioned(self, key: str) -> tuple[np.ndarray, np.ndarray] | None:
        for view in self._views:
            found = view.conditioned(key)
            if found is not None:
                return found
        return None

    # -- display options ------------------------------------------------------- #
    def _apply_options(self, view: ChromatogramView) -> None:
        view.set_normalised(self._options["normalised"])
        view.set_smoothing(self._options["smoothing"])
        view.set_baseline(self._options["baseline"])
        view.set_mirror(self._options["mirror"])
        view.set_offsets(*self._options["offsets"])
        view.set_apex_labels(self._options["apex_labels"])
        view.set_legend_visible(self._options["legend"])
        view.set_select_mode(self._options["select_mode"])
        view.set_overview_visible(self._options["overview"])
        view.set_relative_labels(self._options["relative_labels"])

    def _broadcast(self, option: str, value, method: str) -> None:
        self._options[option] = value
        for view in self._views:
            getattr(view, method)(*value) if isinstance(value, tuple) else \
                getattr(view, method)(value)

    def set_normalised(self, enabled: bool) -> None:
        self._broadcast("normalised", enabled, "set_normalised")

    def set_smoothing(self, sigma: float) -> None:
        self._broadcast("smoothing", float(sigma), "set_smoothing")

    def set_baseline(self, window: float) -> None:
        self._broadcast("baseline", float(window), "set_baseline")

    def set_mirror(self, enabled: bool) -> None:
        self._broadcast("mirror", enabled, "set_mirror")

    def set_offsets(self, offset_x: float, offset_y: float) -> None:
        self._broadcast("offsets", (float(offset_x), float(offset_y)), "set_offsets")

    def set_apex_labels(self, enabled: bool) -> None:
        self._broadcast("apex_labels", enabled, "set_apex_labels")

    def set_legend_visible(self, visible: bool) -> None:
        self._broadcast("legend", visible, "set_legend_visible")

    def set_select_mode(self, enabled: bool) -> None:
        self._broadcast("select_mode", enabled, "set_select_mode")

    def set_overview_visible(self, visible: bool) -> None:
        self._broadcast("overview", visible, "set_overview_visible")

    def set_relative_labels(self, enabled: bool) -> None:
        self._broadcast("relative_labels", enabled, "set_relative_labels")

    @property
    def mirrored(self) -> bool:
        return self._options["mirror"]

    # -- markers and shading ---------------------------------------------------- #
    def add_marker(self, x: float) -> None:
        self.active_view.add_marker(x)

    def clear_markers(self) -> None:
        for view in self._views:
            view.clear_markers()

    def set_peak_markers(self, peaks: list[ChromPeak]) -> None:
        for view in self._views:
            view.set_peak_markers(peaks)

    def clear_peak_markers(self) -> None:
        for view in self._views:
            view.clear_peak_markers()

    # -- selection and background ----------------------------------------------- #
    def selected_range(self) -> tuple[float, float] | None:
        return self.active_view.selected_range()

    def set_background_range(self, rt0: float, rt1: float) -> None:
        for view in self._views:
            view.background.blockSignals(view is not self._views[0])
            view.set_background_range(rt0, rt1)
            view.background.blockSignals(False)

    def clear_background_range(self) -> None:
        for view in self._views:
            view.background.blockSignals(view is not self._views[0])
            view.clear_background_range()
            view.background.blockSignals(False)

    def background_range(self) -> tuple[float, float] | None:
        return self._views[0].background_range() if self._views else None

    # -- misc -------------------------------------------------------------------- #
    def mark(self, x: float | None) -> None:
        for view in self._views:
            view.mark(x)

    def autoscale(self) -> None:
        for view in self._views:
            view.autoscale()
