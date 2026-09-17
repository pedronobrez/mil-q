"""
The visual identity: one palette, one stylesheet, both themes.

Every colour in the interface comes from the tokens below rather than from a
literal scattered through a widget, so light and dark stay in step and the
accent can be changed in one place.

The accent is #234b8c — the project's own blue. It is used sparingly and only
where it means something: what is selected, what has focus, what is the primary
action. Everything else is neutral, on the principle that a screen full of
numbers should be read, not decorated.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

#: the project's blue, and the lighter cast it takes on a dark ground so it
#: stays legible without becoming a different colour
ACCENT = "#234b8c"
ACCENT_DARK_THEME = "#6f9be0"

LIGHT = {
    "canvas": "#f5f5f7",       # the window itself
    "surface": "#ffffff",      # panels, tables, fields
    "surface_alt": "#fafafc",  # alternating rows, headers
    "ink": "#1a1d21",
    "ink_muted": "#6b7280",
    "ink_faint": "#9aa1ac",
    "line": "#e3e5ea",         # hairlines
    "line_strong": "#cfd3da",
    "accent": ACCENT,
    "accent_hover": "#2c5aa6",
    "accent_press": "#1b3c70",
    "accent_soft": "#e7edf7",   # selection, checked rows
    "accent_ink": "#ffffff",
    "warning": "#a86a00",
    "danger": "#b03030",
}

DARK = {
    "canvas": "#161819",
    "surface": "#1e2124",
    "surface_alt": "#232629",
    "ink": "#e6e8eb",
    "ink_muted": "#9ba3ae",
    "ink_faint": "#6b7280",
    "line": "#2c3035",
    "line_strong": "#3c4148",
    "accent": ACCENT_DARK_THEME,
    "accent_hover": "#87b0ea",
    "accent_press": "#5b86d6",
    "accent_soft": "#22304a",
    "accent_ink": "#0f1113",
    "warning": "#e0a844",
    "danger": "#e07070",
}


def is_dark() -> bool:
    """
    Is the system asking for a dark interface?

    Read from the style hints rather than from the palette: applying our own
    palette makes it explicit, and Qt then stops updating it when the system
    theme changes — so a palette-based answer would be our own last answer.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    scheme = app.styleHints().colorScheme()
    if scheme == QtCore.Qt.ColorScheme.Dark:
        return True
    if scheme == QtCore.Qt.ColorScheme.Light:
        return False
    window = app.palette().color(QtGui.QPalette.ColorRole.Window)
    return window.lightness() < 128


class ThemeWatcher(QtCore.QObject):
    """
    Announces a change of system theme, once per change.

    Qt emits colorSchemeChanged and, separately, delivers a palette change
    event; both can arrive for one switch, so the last applied theme is
    remembered and an announcement only goes out when it actually differs.
    """

    sigThemeChanged = QtCore.pyqtSignal()

    def __init__(self, app: QtWidgets.QApplication, parent=None):
        super().__init__(parent)
        self._app = app
        self._dark = is_dark()
        app.styleHints().colorSchemeChanged.connect(self._check)
        app.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.ApplicationPaletteChange:
            self._check()
        return super().eventFilter(obj, event)

    def _check(self, *_args) -> None:
        dark = is_dark()
        if dark == self._dark:
            return
        self._dark = dark
        apply(self._app)
        self.sigThemeChanged.emit()


def tokens() -> dict[str, str]:
    return DARK if is_dark() else LIGHT


def token(name: str) -> str:
    return tokens()[name]


def wordmark_font(points: int = 30) -> QtGui.QFont:
    """
    The application name, set in the one place a display face belongs.

    A high-contrast serif reads as an identity rather than as a control; the
    rest of the interface stays in the system face, because a table of masses
    is there to be read quickly.
    """
    font = QtGui.QFont()
    font.setFamilies(["Didot", "Bodoni 72", "Hoefler Text", "Georgia", "serif"])
    font.setPointSize(points)
    font.setWeight(QtGui.QFont.Weight.Light)
    font.setLetterSpacing(QtGui.QFont.SpacingType.PercentageSpacing, 104)
    return font


def eyebrow_font(points: int = 9) -> QtGui.QFont:
    """Small, spaced and quiet: for labels that title a region."""
    font = QtGui.QFont()
    font.setPointSize(points)
    font.setWeight(QtGui.QFont.Weight.DemiBold)
    font.setCapitalization(QtGui.QFont.Capitalization.AllUppercase)
    font.setLetterSpacing(QtGui.QFont.SpacingType.PercentageSpacing, 112)
    return font


#: what a cell widget loses to QTableView::item's padding and the gridline.
#: resizeColumnsToContents measures the widget's own size hint and knows
#: nothing about either, so a combo ends up exactly this much too narrow.
CELL_WIDGET_INSET = 10


def fit_cell_widgets(table) -> None:
    """Widen any column holding a cell widget so the widget is not clipped."""
    for column in range(table.columnCount()):
        widget = table.cellWidget(0, column)
        if widget is None:
            continue
        # a widget that has not been polished reports the size hint it would
        # have without the stylesheet, which is smaller than what it will need
        widget.ensurePolished()
        if isinstance(widget, QtWidgets.QComboBox):
            # the default policy defers the hint to the first show, so before
            # then a freshly filled combo still reports the width of one item
            widget.setSizeAdjustPolicy(
                QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        table.setColumnWidth(
            column, max(table.columnWidth(column),
                        widget.sizeHint().width() + CELL_WIDGET_INSET))


def _icon_dir() -> Path:
    base = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.CacheLocation)
    path = Path(base or tempfile.gettempdir()) / "milq" / "icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _render(name: str, size: int, draw) -> str:
    """
    Draw a small indicator and hand back its path for the stylesheet.

    Qt style sheets cannot draw a chevron or a tick — the border triangle
    people reach for renders as a filled square here — and a checkbox with no
    tick in it is not a checkbox. Each glyph is written once at 1x and 2x, and
    Qt picks the retina one by the @2x name.
    """
    directory = _icon_dir()
    path = directory / f"{name}.png"
    for scale, target in ((1, path), (2, directory / f"{name}@2x.png")):
        pixmap = QtGui.QPixmap(size * scale, size * scale)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)
        draw(painter)
        painter.end()
        pixmap.save(str(target))
    return str(path).replace("\\", "/")


def _stroke(colour: str, width: float) -> QtGui.QPen:
    pen = QtGui.QPen(QtGui.QColor(colour))
    pen.setWidthF(width)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    return pen


def _chevron(name: str, colour: str, up: bool = False) -> str:
    def draw(painter: QtGui.QPainter) -> None:
        painter.setPen(_stroke(colour, 1.5))
        y_from, y_to = (9.0, 5.0) if up else (5.0, 9.0)
        painter.drawPolyline(QtCore.QPointF(3.0, y_from),
                             QtCore.QPointF(7.0, y_to),
                             QtCore.QPointF(11.0, y_from))
    return _render(name, 14, draw)


def _tick(name: str, colour: str) -> str:
    def draw(painter: QtGui.QPainter) -> None:
        painter.setPen(_stroke(colour, 1.9))
        painter.drawPolyline(QtCore.QPointF(3.2, 7.2),
                             QtCore.QPointF(6.0, 10.0),
                             QtCore.QPointF(10.8, 4.4))
    return _render(name, 14, draw)


def _dot(name: str, colour: str) -> str:
    def draw(painter: QtGui.QPainter) -> None:
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(colour)))
        painter.drawEllipse(QtCore.QPointF(7.0, 7.0), 2.6, 2.6)
    return _render(name, 14, draw)


def _chevron_right(name: str, colour: str) -> str:
    def draw(painter: QtGui.QPainter) -> None:
        painter.setPen(_stroke(colour, 1.5))
        painter.drawPolyline(QtCore.QPointF(5.0, 3.0),
                             QtCore.QPointF(9.0, 7.0),
                             QtCore.QPointF(5.0, 11.0))
    return _render(name, 14, draw)


def _double_chevron(name: str, colour: str) -> str:
    def draw(painter: QtGui.QPainter) -> None:
        painter.setPen(_stroke(colour, 1.5))
        for x in (3.0, 7.5):
            painter.drawPolyline(QtCore.QPointF(x, 3.5),
                                 QtCore.QPointF(x + 3.5, 7.0),
                                 QtCore.QPointF(x, 10.5))
    return _render(name, 14, draw)


def indicators() -> dict[str, str]:
    """The glyph paths for the current theme, drawn on demand."""
    t = tokens()
    suffix = "dark" if is_dark() else "light"
    return {
        "chevron": _chevron(f"chevron-{suffix}", t["ink_muted"]),
        "chevron_up": _chevron(f"chevron-up-{suffix}", t["ink_muted"], up=True),
        "chevron_accent": _chevron(f"chevron-accent-{suffix}", t["accent"]),
        "tick": _tick(f"tick-{suffix}", t["accent_ink"]),
        "dot": _dot(f"dot-{suffix}", t["accent_ink"]),
        "more": _double_chevron(f"more-{suffix}", t["accent"]),
        "chevron_right": _chevron_right(f"chevron-right-{suffix}", t["ink_muted"]),
    }


def stylesheet() -> str:
    """The whole interface, in one sheet, for the current light or dark theme."""
    t = tokens()
    icon = indicators()
    return f"""
/* -- surfaces ------------------------------------------------------------ */
QMainWindow, QDialog, QWizard {{
    background: {t['canvas']};
}}
QWidget {{
    color: {t['ink']};
    font-size: 13px;
}}
QToolTip {{
    background: {t['surface']};
    color: {t['ink']};
    border: 1px solid {t['line_strong']};
    padding: 5px 8px;
}}

/* -- text roles ---------------------------------------------------------- */
QLabel[role="caption"] {{
    color: {t['ink_muted']};
}}
QLabel[role="hint"] {{
    color: {t['ink_muted']};
    font-size: 11px;
}}
QLabel[role="warning"] {{
    color: {t['warning']};
}}
QLabel[role="danger"] {{
    color: {t['danger']};
    font-size: 11px;
}}
QLabel[role="strong"] {{
    font-weight: 600;
}}

/* -- workspace tabs: an underline, not a folder tab ---------------------- */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {t['line']};
    background: {t['canvas']};
}}
QTabBar {{
    qproperty-drawBase: 0;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {t['ink_muted']};
    padding: 7px 16px 8px 16px;
    margin: 0 2px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{
    color: {t['ink']};
}}
QTabBar::tab:selected {{
    color: {t['accent']};
    border-bottom: 2px solid {t['accent']};
}}

/* -- fields -------------------------------------------------------------- */
QLineEdit {{
    background: {t['surface']};
    border: 1px solid {t['line_strong']};
    border-radius: 6px;
    padding: 3px 8px;
    selection-background-color: {t['accent']};
    selection-color: {t['accent_ink']};
}}
/* the right padding is the drop-down's own width: the arrow is drawn inside
   the frame, so without it the text runs underneath and is clipped */
QComboBox {{
    background: {t['surface']};
    border: 1px solid {t['line_strong']};
    border-radius: 6px;
    padding: 2px 22px 2px 8px;
    selection-background-color: {t['accent']};
    selection-color: {t['accent_ink']};
}}
/* the buttons sit inside the frame, so the text needs their width back */
QAbstractSpinBox {{
    background: {t['surface']};
    border: 1px solid {t['line_strong']};
    border-radius: 6px;
    padding: 2px 20px 2px 8px;
    selection-background-color: {t['accent']};
    selection-color: {t['accent_ink']};
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border;
    width: 18px;
    border: none;
    background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-arrow {{
    image: url({icon['chevron_up']});
    width: 12px;
    height: 12px;
}}
QAbstractSpinBox::down-arrow {{
    image: url({icon['chevron']});
    width: 12px;
    height: 12px;
}}
QAbstractSpinBox::up-arrow:hover, QAbstractSpinBox::down-arrow:hover {{
    image: url({icon['chevron_accent']});
}}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{
    border: 1px solid {t['accent']};
}}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{
    color: {t['ink_faint']};
    background: {t['surface_alt']};
}}
QComboBox::drop-down {{
    border: none;
    width: 16px;
}}
QComboBox::down-arrow {{
    image: url({icon['chevron']});
    width: 14px;
    height: 14px;
    margin-right: 4px;
}}
QComboBox::down-arrow:on, QComboBox::down-arrow:hover {{
    image: url({icon['chevron_accent']});
}}
/* an editable combo puts a line edit inside the frame; without this it draws
   its own box and the first letter sits on the border */
QComboBox QLineEdit {{
    background: transparent;
    border: none;
    padding: 0 0 0 1px;
    selection-background-color: {t['accent']};
    selection-color: {t['accent_ink']};
}}
QComboBox QAbstractItemView {{
    background: {t['surface']};
    border: 1px solid {t['line_strong']};
    selection-background-color: {t['accent_soft']};
    selection-color: {t['ink']};
    padding: 2px;
}}

/* -- buttons ------------------------------------------------------------- */
QPushButton {{
    background: {t['surface']};
    color: {t['ink']};
    border: 1px solid {t['line_strong']};
    border-radius: 6px;
    padding: 5px 14px;
}}
QPushButton:hover {{
    border-color: {t['accent']};
    color: {t['accent']};
}}
QPushButton:pressed {{
    background: {t['accent_soft']};
}}
QPushButton:disabled {{
    color: {t['ink_faint']};
    border-color: {t['line']};
    background: {t['surface_alt']};
}}
QPushButton:checked {{
    background: {t['accent_soft']};
    border-color: {t['accent']};
    color: {t['accent']};
}}
QPushButton[primary="true"] {{
    background: {t['accent']};
    color: {t['accent_ink']};
    border: 1px solid {t['accent']};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background: {t['accent_hover']};
    border-color: {t['accent_hover']};
    color: {t['accent_ink']};
}}
QPushButton[primary="true"]:pressed {{
    background: {t['accent_press']};
}}
QPushButton[primary="true"]:disabled {{
    background: {t['line']};
    border-color: {t['line']};
    color: {t['ink_faint']};
}}

/* -- ticks and radios ---------------------------------------------------- */
QCheckBox, QRadioButton {{
    spacing: 7px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {t['line_strong']};
    background: {t['surface']};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {t['accent']};
}}
QCheckBox::indicator:checked {{
    background: {t['accent']};
    border-color: {t['accent']};
    image: url({icon['tick']});
}}
QCheckBox::indicator:indeterminate {{
    background: {t['accent_soft']};
    border-color: {t['accent']};
}}
QRadioButton::indicator:checked {{
    background: {t['accent']};
    border-color: {t['accent']};
    image: url({icon['dot']});
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {t['surface_alt']};
    border-color: {t['line']};
}}

/* -- tables -------------------------------------------------------------- */
QTableView, QTableWidget, QTreeWidget, QTreeView, QListView {{
    background: {t['surface']};
    alternate-background-color: {t['surface_alt']};
    border: 1px solid {t['line']};
    border-radius: 8px;
    gridline-color: {t['line']};
    selection-background-color: {t['accent_soft']};
    selection-color: {t['ink']};
    outline: none;
}}
QTableView::item, QTableWidget::item {{
    padding: 2px 4px;
    border: none;
}}
QTreeWidget::item, QTreeView::item, QListView::item {{
    padding: 3px 2px;
    border: none;
}}
QTreeWidget::item:selected, QTreeView::item:selected, QListView::item:selected {{
    background: {t['accent_soft']};
    color: {t['ink']};
}}
QHeaderView {{
    background: transparent;
}}
QHeaderView::section {{
    background: {t['surface_alt']};
    color: {t['ink_muted']};
    font-size: 11px;
    font-weight: 600;
    padding: 5px 6px;
    border: none;
    border-right: 1px solid {t['line']};
    border-bottom: 1px solid {t['line_strong']};
}}
QHeaderView::section:hover {{
    color: {t['accent']};
}}
QHeaderView::down-arrow {{
    image: url({icon['chevron']});
    width: 12px;
    height: 12px;
    subcontrol-position: center right;
    right: 4px;
}}
QHeaderView::up-arrow {{
    image: url({icon['chevron_up']});
    width: 12px;
    height: 12px;
    subcontrol-position: center right;
    right: 4px;
}}
QTableCornerButton::section {{
    background: {t['surface_alt']};
    border: none;
    border-bottom: 1px solid {t['line_strong']};
}}

/* -- toolbars: a band of type, not a chrome strip ------------------------ */
QToolBar {{
    background: {t['canvas']};
    border: none;
    border-bottom: 1px solid {t['line']};
    spacing: 1px;
    padding: 5px 8px;
}}
QToolBar::separator {{
    background: {t['line']};
    width: 1px;
    height: 1px;
    margin: 5px 7px;
}}
QToolBar::handle {{
    image: none;
    width: 10px;
    height: 10px;
}}
QToolBar QLabel {{
    color: {t['ink_muted']};
    padding-left: 4px;
}}
QToolButton {{
    background: transparent;
    color: {t['ink_muted']};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
}}
QToolButton:hover {{
    background: {t['surface']};
    border-color: {t['line']};
    color: {t['ink']};
}}
QToolButton:pressed {{
    background: {t['accent_soft']};
    border-color: {t['accent_soft']};
    color: {t['accent']};
}}
QToolButton:checked {{
    background: {t['accent_soft']};
    border-color: {t['accent_soft']};
    color: {t['accent']};
    font-weight: 600;
}}
QToolButton:checked:hover {{
    border-color: {t['accent']};
}}
QToolButton:disabled {{
    color: {t['ink_faint']};
}}
/* what is left over when a toolbar does not fit. Styling QToolButton alone
   leaves this one with no arrow at all, which hides the controls behind an
   invisible button */
QToolButton#qt_toolbar_ext_button {{
    qproperty-icon: url({icon['more']});
    background: {t['surface']};
    border: 1px solid {t['line_strong']};
    border-radius: 6px;
    padding: 3px 4px;
    margin-left: 4px;
}}
QToolButton#qt_toolbar_ext_button:hover {{
    border-color: {t['accent']};
    background: {t['accent_soft']};
}}
QToolButton::menu-indicator {{
    image: url({icon['chevron']});
    subcontrol-position: right center;
    width: 12px;
    height: 12px;
}}

/* -- grouping ------------------------------------------------------------ */
QGroupBox {{
    border: none;
    border-top: 1px solid {t['line']};
    margin-top: 16px;
    padding-top: 10px;
}}
/* a section that folds: the chevron says which way it goes */
QGroupBox::indicator {{
    width: 14px;
    height: 14px;
}}
QGroupBox::indicator:checked {{
    image: url({icon['chevron']});
}}
QGroupBox::indicator:unchecked {{
    image: url({icon['chevron_right']});
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    color: {t['ink_muted']};
    font-size: 11px;
    font-weight: 600;
    padding: 0 0 4px 2px;
}}
QGroupBox::title:hover {{
    color: {t['accent']};
}}
QSplitter::handle {{
    background: {t['line']};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QSplitter::handle:hover {{
    background: {t['accent']};
}}

/* -- menus and status ---------------------------------------------------- */
QMenuBar {{
    background: {t['canvas']};
    border-bottom: 1px solid {t['line']};
}}
QMenuBar::item {{
    padding: 4px 10px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background: {t['accent_soft']};
    color: {t['accent']};
}}
QMenu {{
    background: {t['surface']};
    border: 1px solid {t['line_strong']};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 22px 5px 14px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {t['accent_soft']};
    color: {t['accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {t['line']};
    margin: 4px 8px;
}}
QStatusBar {{
    background: {t['canvas']};
    border-top: 1px solid {t['line']};
    color: {t['ink_muted']};
}}
QStatusBar::item {{ border: none; }}

/* -- scrollbars: thin, and only as loud as they need to be --------------- */
QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
    margin: 0;
}}
QScrollBar:vertical {{ width: 11px; }}
QScrollBar:horizontal {{ height: 11px; }}
QScrollBar::handle {{
    background: {t['line_strong']};
    border-radius: 5px;
    min-height: 28px;
    min-width: 28px;
}}
QScrollBar::handle:hover {{
    background: {t['ink_faint']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0; border: none; background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* -- progress and wizard ------------------------------------------------- */
QProgressBar {{
    background: {t['surface_alt']};
    border: 1px solid {t['line']};
    border-radius: 5px;
    text-align: center;
    height: 8px;
}}
QProgressBar::chunk {{
    background: {t['accent']};
    border-radius: 4px;
}}
QWizard QWidget#qt_wizard_titlebar {{
    background: {t['surface']};
}}
"""


def apply(app: QtWidgets.QApplication) -> None:
    """Give the application its palette and stylesheet."""
    t = tokens()
    palette = app.palette()
    role = QtGui.QPalette.ColorRole
    palette.setColor(role.Window, QtGui.QColor(t["canvas"]))
    palette.setColor(role.Base, QtGui.QColor(t["surface"]))
    palette.setColor(role.AlternateBase, QtGui.QColor(t["surface_alt"]))
    palette.setColor(role.Text, QtGui.QColor(t["ink"]))
    palette.setColor(role.WindowText, QtGui.QColor(t["ink"]))
    palette.setColor(role.ButtonText, QtGui.QColor(t["ink"]))
    palette.setColor(role.Highlight, QtGui.QColor(t["accent_soft"]))
    palette.setColor(role.HighlightedText, QtGui.QColor(t["ink"]))
    palette.setColor(role.Link, QtGui.QColor(t["accent"]))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet())
