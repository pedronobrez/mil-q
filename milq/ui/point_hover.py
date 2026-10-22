"""
Which sample a point is: the hover every per-injection chart shares.

A control chart of twenty-six circles says that one injection went wrong
and not which. Each chart that draws one point per injection hands its
scatters to a `PointHover` with a function that turns a spot's `data` into
a sentence or two; hovering a point then enlarges and outlines it and shows
that text at once, rather than after the tool-tip delay.

pyqtgraph's own `tip` is not used. It writes the view box's tool tip, which
Qt shows only after its delay and only if nothing else claims the event,
and with several scatters in one plot each clears what the other wrote. So
`tip=None`, the text is collected from `sigHovered` across every scatter
attached, shown with `QToolTip.showText` straight away, and written into the
view box's tool tip as well, so that Qt's own delayed tool-tip event shows
the same text rather than the plot's general one.
"""

from __future__ import annotations

from typing import Callable

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme

#: the diameter of a hovered point, against the 9 the charts draw at
HOVER_SIZE = 14
#: the outline it gets
HOVER_PEN_WIDTH = 2.0
#: points under the cursor at once that are described; past this, a count
MAX_DESCRIBED = 3


def hoverable_scatter(**options) -> pg.ScatterPlotItem:
    """A scatter that reports hovers and draws the hovered point larger."""
    options.setdefault("size", 9)
    options.setdefault("pen", pg.mkPen(theme.axis()))
    return pg.ScatterPlotItem(
        hoverable=True, tip=None, hoverSize=HOVER_SIZE,
        hoverPen=pg.mkPen(theme.foreground(), width=HOVER_PEN_WIDTH),
        **options)


class PointHover(QtCore.QObject):
    """
    Shows what the points under the cursor are, across every scatter of one
    plot.

    `describe` takes a spot's `data` and returns its text, or an empty
    string for a point that has nothing to say.
    """

    def __init__(self, plot: pg.PlotWidget, describe: Callable[[object], str],
                 parent: QtCore.QObject | None = None):
        super().__init__(parent or plot)
        self.plot = plot
        self.describe = describe
        #: what each attached scatter has under the cursor, by the scatter
        self._under: dict[int, list[str]] = {}
        #: the text last shown; empty when nothing is hovered
        self.text = ""

    def attach(self, scatter: pg.ScatterPlotItem) -> None:
        scatter.sigHovered.connect(self._on_hovered)

    def reset(self) -> None:
        """Forget what was hovered: the points have just been replaced."""
        self._under.clear()
        self._show("", None)

    def _on_hovered(self, scatter, points, event=None) -> None:
        texts = []
        for point in list(points)[:MAX_DESCRIBED]:
            text = self.describe(point.data())
            if text:
                texts.append(text)
        if len(points) > MAX_DESCRIBED:
            texts.append(f"and {len(points) - MAX_DESCRIBED} more here")
        if texts:
            self._under[id(scatter)] = texts
        else:
            self._under.pop(id(scatter), None)
        shown = [text for under in self._under.values() for text in under]
        self._show("\n\n".join(shown), event)

    def _show(self, text: str, event) -> None:
        if text == self.text:
            return
        self.text = text
        view = self.plot.getPlotItem().getViewBox()
        view.setToolTip(text)
        if not text:
            QtWidgets.QToolTip.hideText()
            return
        where = None
        if event is not None and hasattr(event, "screenPos"):
            where = event.screenPos()
            if isinstance(where, QtCore.QPointF):
                where = where.toPoint()
        if not isinstance(where, QtCore.QPoint):
            where = QtGui.QCursor.pos()
        QtWidgets.QToolTip.showText(where, text, self.plot)


def signed(value: float | None, unit: str, decimals: int = 1) -> str:
    """`+12.3%` or `+4.2 ppm`: a deviation with its unit."""
    if value is None:
        return "—"
    space = "" if unit == "%" else " "
    return f"{value:+,.{decimals}f}{space}{unit}"
