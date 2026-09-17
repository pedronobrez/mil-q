"""
The theme an export is written in, on the file dialog that writes it.

A figure goes somewhere: into a journal that prints in black and white, into
a slide with a dark ground, or onto paper as it always has. That is a
property of the destination and not of the application's own appearance, so
it is asked for where the file is named rather than taken from whichever
theme the window happens to be wearing — and it is remembered, because
whoever exports one figure for a manuscript is about to export six.

The choice lives under `export/theme` in the settings, one setting shared by
the report and the comparison: a person exporting a black and white figure
is exporting a black and white report. A dialog that cannot offer every
theme — a printed report has no dark version, see `report.print_document` —
says so by leaving it out of `allowed`, and a remembered theme it cannot
offer falls back to `paper` without disturbing what is stored.
"""

from __future__ import annotations

from PyQt6 import QtWidgets

from ..report import THEME_NAMES, theme_named
from .settings import settings as _settings

#: where the choice is kept
SETTING = "export/theme"

#: every theme, in the order they are offered
THEMES = ("paper", "mono", "dark")


def remembered(settings=None, allowed: tuple[str, ...] = THEMES) -> str:
    """The theme last exported in, or `paper` where that is not on offer."""
    store = settings if settings is not None else _settings()
    name = theme_named(store.value(SETTING, "paper", type=str))
    return name if name in allowed else "paper"


def remember(name: str, settings=None) -> None:
    """Keep a theme for the next export."""
    store = settings if settings is not None else _settings()
    store.setValue(SETTING, theme_named(name))


def add_theme_box(dialog, settings=None,
                  allowed: tuple[str, ...] = THEMES) -> QtWidgets.QComboBox:
    """
    Put a theme chooser on a file dialog, set to what was last used.

    Qt's own file dialog is a widget with a grid layout and a row can be
    added to it; the platform's is not, so the option is turned off here.
    That is the price of asking the question in the same place the file is
    named, and it is worth paying: a separate dialog before the save dialog
    is one more thing to dismiss on the way to every figure.
    """
    dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, True)
    box = QtWidgets.QComboBox(dialog)
    for name in allowed:
        box.addItem(THEME_NAMES[name], name)
    chosen = remembered(settings, allowed)
    box.setCurrentIndex(max(box.findData(chosen), 0))
    box.setToolTip("Paper is the drawing as it has always been. Black and "
                   "white is for a journal that prints in no colour: the "
                   "traces are told apart by line style and by two tones of "
                   "grey. Dark is for a screen or a slide.")
    label = QtWidgets.QLabel("Theme:", dialog)
    label.setBuddy(box)
    layout = dialog.layout()
    if isinstance(layout, QtWidgets.QGridLayout):
        row = layout.rowCount()
        layout.addWidget(label, row, 0)
        layout.addWidget(box, row, 1)
    else:                                   # pragma: no cover - not Qt's own
        layout.addWidget(label)
        layout.addWidget(box)
    return box


def chosen_theme(box) -> str:
    """What the chooser is on, as a theme name."""
    data = box.currentData()
    return theme_named(data)
