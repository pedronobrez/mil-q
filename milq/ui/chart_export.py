"""
Every chart, exported as a picture the same way.

Right-click on any chart → **Export as a picture…**: SVG or PNG, a scale of
2–6× for a PNG, the theme (Light, Dark, or as on screen), the ground (the
theme's paper, plain white, or transparent) and the size of the type
(0.7–2.2× the screen's). The preview in the dialog is drawn by exactly the
code that writes the file — it *is* an export, to memory — so what is seen
is what is written. The choices are remembered, because whoever exports one
figure for a manuscript is about to export six. This is MIL-X's export,
with the same options, so a figure from either program looks the same.

A chart is drawn for its export by re-theming the live widget for the
length of the export (`style.forced_scheme`), scaling its type, rendering
through pyqtgraph's own exporters and putting everything back — the
widget is the figure, not a copy of it, so nothing on the chart can be left
out of the picture by accident.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, dataclass

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import style, theme
from .settings import settings as _settings

FORMATS = ("svg", "png")
THEMES = ("light", "dark", "screen")
GROUNDS = ("paper", "white", "transparent")
SCALE_RANGE = (2.0, 6.0)
TYPE_RANGE = (0.7, 2.2)
SETTING = "export/picture"


@dataclass
class ExportOptions:
    format: str = "png"
    scale: float = 3.0
    theme: str = "light"
    background: str = "paper"
    type_size: float = 1.0

    def clamped(self) -> "ExportOptions":
        return ExportOptions(
            self.format if self.format in FORMATS else "png",
            float(min(max(self.scale, SCALE_RANGE[0]), SCALE_RANGE[1])),
            self.theme if self.theme in THEMES else "light",
            self.background if self.background in GROUNDS else "paper",
            float(min(max(self.type_size, TYPE_RANGE[0]), TYPE_RANGE[1])))

    @classmethod
    def remembered(cls, settings=None) -> "ExportOptions":
        s = settings or _settings()
        made = cls()
        for name, default in asdict(made).items():
            value = s.value(f"{SETTING}/{name}", default)
            try:
                setattr(made, name, type(default)(value))
            except (TypeError, ValueError):
                pass
        return made.clamped()

    def remember(self, settings=None) -> None:
        s = settings or _settings()
        for name, value in asdict(self.clamped()).items():
            s.setValue(f"{SETTING}/{name}", value)


# --------------------------------------------------------------------------- #
def _plot_widget(chart) -> pg.PlotWidget:
    """The pyqtgraph widget of a chart: itself, or its `plot`."""
    if isinstance(chart, pg.PlotWidget):
        return chart
    plot = getattr(chart, "plot", None)
    if isinstance(plot, pg.PlotWidget):
        return plot
    raise TypeError(f"{type(chart).__name__} is not a chart this can export")


def _restyle(chart, plot: pg.PlotWidget) -> None:
    """Take the theme's colours: the chart's own `retheme`, or the plain one."""
    rethemer = getattr(chart, "retheme", None)
    if callable(rethemer) and chart is not plot:
        rethemer()
        return
    plot.setBackground(theme.background())
    theme.style_axes(plot)


class _TypeScaled:
    """Every piece of a chart's type scaled for the length of an export."""

    def __init__(self, plot: pg.PlotWidget, factor: float):
        self.plot, self.factor = plot, factor
        self.saved = []
        self.texts = []
        self.legend = []

    def __enter__(self):
        if abs(self.factor - 1.0) < 1e-6:
            return self
        for name in ("bottom", "left", "top", "right"):
            axis = self.plot.getAxis(name)
            if axis is None or not axis.isVisible():
                continue
            original = axis.style.get("tickFont")
            label_style = dict(axis.labelStyle)
            self.saved.append((axis, original, label_style))
            bigger = QtGui.QFont(original) if original is not None else QtGui.QFont()
            size = bigger.pointSizeF() if bigger.pointSizeF() > 0 else 9.0
            bigger.setPointSizeF(size * self.factor)
            axis.setStyle(tickFont=bigger)
            points = float(str(label_style.get("font-size", "9pt")).rstrip("pt") or 9)
            axis.setLabel(text=axis.labelText, units=axis.labelUnits,
                          **{**label_style, "font-size": f"{points * self.factor:.1f}pt"})

        # every other piece of text too — the legend and the labels on the
        # plot — as MIL-X's font scale does: a figure shrunk into a column
        # needs all of its words larger, not only the axes'
        for item in self.plot.getPlotItem().items + [self.plot.getPlotItem().legend]:
            if isinstance(item, pg.TextItem):
                font = item.textItem.font()
                self.texts.append((item, QtGui.QFont(font)))
                font.setPointSizeF((font.pointSizeF() if font.pointSizeF() > 0 else 9.0)
                                   * self.factor)
                item.setFont(font)
            elif isinstance(item, pg.LegendItem):
                for _sample, label in item.items:
                    opts = dict(label.opts)
                    self.legend.append((label, opts))
                    points = float(str(opts.get("size", "8pt")).rstrip("pt") or 8)
                    label.setText(label.text, **{**opts, "size": f"{points * self.factor:.1f}pt"})
        return self

    def __exit__(self, *_exc):
        for axis, tick, label_style in self.saved:
            axis.setStyle(tickFont=tick)
            axis.setLabel(text=axis.labelText, units=axis.labelUnits, **label_style)
        for item, font in self.texts:
            item.setFont(font)
        for label, opts in self.legend:
            label.setText(label.text, **opts)
        return False


def _ground(options: ExportOptions):
    if options.background == "transparent":
        return QtGui.QColor(0, 0, 0, 0)
    if options.background == "white":
        return QtGui.QColor("#ffffff")
    return QtGui.QColor(theme.background())


def export(chart, path: str, options: ExportOptions | None = None) -> str:
    """
    Write a chart to `path` as the options say; the suffix is the format's.

    Returns the path written. Raises `OSError` when nothing was written,
    because a picture that silently is not there is the worst outcome.
    """
    options = (options or ExportOptions()).clamped()
    plot = _plot_widget(chart)
    root, _ext = os.path.splitext(str(path))
    path = f"{root}.{options.format}"
    scheme = None if options.theme == "screen" else options.theme
    try:
        with style.forced_scheme(scheme):
            _restyle(chart, plot)
            with _TypeScaled(plot, options.type_size):
                QtWidgets.QApplication.processEvents()
                item = plot.getPlotItem()
                if options.format == "svg":
                    _write_svg(plot, item, path, _ground(options))
                else:
                    exporter = pg.exporters.ImageExporter(item)
                    params = exporter.parameters()
                    params["background"] = _ground(options)
                    width = max(int(item.sceneBoundingRect().width() * options.scale), 16)
                    params["width"] = width
                    exporter.export(path)
    finally:
        _restyle(chart, plot)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise OSError(f"the picture was not written: {path}")
    return path


def _write_svg(plot, item, path: str, ground: QtGui.QColor) -> None:
    """
    The plot's region of the scene, painted into Qt's SVG generator.

    Not pyqtgraph's `SVGExporter`: on the Explorer's chromatogram it raised
    in `correctCoordinates` ("not enough values to unpack") on one of the
    pane's items, and a picture that cannot be written is no export.
    """
    from PyQt6 import QtSvg

    source = item.sceneBoundingRect()
    generator = QtSvg.QSvgGenerator()
    generator.setFileName(path)
    size = QtCore.QSize(int(source.width()), int(source.height()))
    generator.setSize(size)
    generator.setViewBox(QtCore.QRect(QtCore.QPoint(0, 0), size))
    generator.setTitle(os.path.basename(path))
    painter = QtGui.QPainter(generator)
    try:
        target = QtCore.QRectF(0, 0, source.width(), source.height())
        if ground.alpha() > 0:
            painter.fillRect(target, ground)
        plot.scene().render(painter, target, source)
    finally:
        painter.end()


def preview(chart, options: ExportOptions) -> QtGui.QImage:
    """The export itself, written to a temporary PNG and read back."""
    shown = ExportOptions(**{**asdict(options.clamped()), "format": "png"})
    with tempfile.TemporaryDirectory() as folder:
        written = export(chart, os.path.join(folder, "preview.png"), shown)
        return QtGui.QImage(written)


# --------------------------------------------------------------------------- #
class ExportDialog(QtWidgets.QDialog):
    """The options, a live preview, and where to write."""

    def __init__(self, chart, name: str = "chart", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export as a picture")
        self.chart, self.name = chart, name
        start = ExportOptions.remembered()
        form = QtWidgets.QFormLayout()
        self.format = QtWidgets.QComboBox()
        self.format.addItems(["SVG", "PNG"])
        self.format.setCurrentIndex(FORMATS.index(start.format))
        self.scale = QtWidgets.QDoubleSpinBox()
        self.scale.setRange(*SCALE_RANGE)
        self.scale.setSingleStep(1.0)
        self.scale.setSuffix("×")
        self.scale.setValue(start.scale)
        self.theme = QtWidgets.QComboBox()
        self.theme.addItems(["Light", "Dark", "As on screen"])
        self.theme.setCurrentIndex(THEMES.index(start.theme))
        self.ground = QtWidgets.QComboBox()
        self.ground.addItems(["Paper", "White", "Transparent"])
        self.ground.setCurrentIndex(GROUNDS.index(start.background))
        self.type_size = QtWidgets.QDoubleSpinBox()
        self.type_size.setRange(*TYPE_RANGE)
        self.type_size.setSingleStep(0.1)
        self.type_size.setSuffix("×")
        self.type_size.setValue(start.type_size)
        form.addRow("Format:", self.format)
        form.addRow("Scale (PNG):", self.scale)
        form.addRow("Theme:", self.theme)
        form.addRow("Background:", self.ground)
        form.addRow("Type size:", self.type_size)
        self.preview = QtWidgets.QLabel()
        self.preview.setMinimumSize(360, 220)
        self.preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview, 1)
        layout.addWidget(buttons)
        for box in (self.format, self.theme, self.ground):
            box.currentIndexChanged.connect(self._refresh)
        for spin in (self.scale, self.type_size):
            spin.valueChanged.connect(self._refresh)
        self.written: str | None = None
        self._refresh()

    def options(self) -> ExportOptions:
        return ExportOptions(FORMATS[self.format.currentIndex()],
                             self.scale.value(), THEMES[self.theme.currentIndex()],
                             GROUNDS[self.ground.currentIndex()],
                             self.type_size.value()).clamped()

    def _refresh(self, *_args) -> None:
        self.scale.setEnabled(self.format.currentIndex() == 1)
        try:
            image = preview(self.chart, self.options())
        except Exception as exc:              # a preview must never kill the dialog
            self.preview.setText(f"No preview: {exc}")
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        self.preview.setPixmap(pixmap.scaled(
            self.preview.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation))

    def _save(self) -> None:
        options = self.options()
        suffix = options.format
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export as a picture", f"{self.name}.{suffix}",
            f"{suffix.upper()} (*.{suffix})")
        if not path:
            return
        try:
            self.written = export(self.chart, path, options)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Not written", str(exc))
            return
        options.remember()
        self.accept()


def open_dialog(chart, name: str = "chart", parent=None) -> str | None:
    dialog = ExportDialog(chart, name, parent)
    dialog.exec()
    return dialog.written


def action_for(chart, name: str, parent) -> QtGui.QAction:
    """The menu item, for a chart that builds its own context menu."""
    action = QtGui.QAction("Export as a picture…", parent)
    action.triggered.connect(lambda: open_dialog(chart, name, parent))
    return action


def install(chart, name: str = "chart") -> None:
    """
    Offer **Export as a picture…** on a chart's right-click menu: in
    pyqtgraph's own menu where the chart has one, otherwise as the chart's
    whole context menu.

    Decided once the event loop next turns, because most charts switch
    pyqtgraph's menu off after the widget is made, and an item added to a
    menu nobody can open is no item at all.
    """
    QtCore.QTimer.singleShot(0, lambda: _install_now(chart, name))


def _install_now(chart, name: str) -> None:
    try:
        plot = _plot_widget(chart)
    except (TypeError, RuntimeError):
        return
    if plot.property("milq_export_installed"):
        return
    plot.setProperty("milq_export_installed", True)
    viewbox = plot.getPlotItem().getViewBox()
    menu = getattr(viewbox, "menu", None)
    if viewbox.menuEnabled() and menu is not None:
        menu.addSeparator()
        menu.addAction(action_for(chart, name, menu))
        return
    plot.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

    def show(position):
        popup = QtWidgets.QMenu(plot)
        popup.addAction(action_for(chart, name, popup))
        popup.exec(plot.mapToGlobal(position))

    plot.customContextMenuRequested.connect(show)


import pyqtgraph.exporters  # noqa: E402,F401  (registers pg.exporters)
