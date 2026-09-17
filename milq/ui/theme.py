"""
Plot colours, taken from the same tokens as the rest of the interface.

The widgets are styled by a sheet; the plots are not, because pyqtgraph is told
its colours explicitly. Reading both from `style.py` keeps a white chromatogram
from being pasted into a dark window, and keeps the accent one colour.
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6 import QtGui

from .style import is_dark, token  # noqa: F401  (is_dark is part of this API)


def background() -> str:
    return token("surface")


def foreground() -> str:
    return token("ink")


def axis() -> str:
    return token("ink_muted")


def faint_axis() -> str:
    return token("line_strong")


def muted() -> str:
    return token("ink_muted")


def accent() -> str:
    return token("accent")


def line() -> str:
    return token("line")


def legend_brush():
    colour = QtGui.QColor(token("surface"))
    colour.setAlpha(212)
    return pg.mkBrush(colour)


def legend_pen():
    return pg.mkPen(token("line_strong"))


def apply_defaults() -> None:
    """Set pyqtgraph's global colours; call once the application exists."""
    pg.setConfigOptions(antialias=True, background=background(),
                        foreground=foreground())


def style_axes(plot, faint: bool = False, tick_points: int | None = None) -> None:
    """Give a plot widget the palette's axis and label colours."""
    pen = pg.mkPen(faint_axis() if faint else axis())
    text = pg.mkPen(muted() if faint else foreground())
    for name in ("bottom", "left"):
        item = plot.getAxis(name)
        item.setPen(pen)
        item.setTextPen(text)
        if tick_points is not None:
            # a QFont built from an empty family name crashes Qt when the axis
            # measures its tick labels, so start from the default font
            font = QtGui.QFont()
            font.setPointSize(tick_points)
            item.setStyle(tickFont=font)


def warning() -> str:
    """Colour for a value that is set but does not resolve to anything."""
    return token("warning")


def ink_faint() -> str:
    """For a value that is present but deliberately set aside."""
    return token("ink_faint")


def danger() -> str:
    return token("danger")
