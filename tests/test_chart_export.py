"""Every chart exports as a picture, with MIL-X's options."""

import os

import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6 import QtWidgets

from milq.ui import chart_export
from milq.ui.chart_export import ExportOptions


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def chrom(qapp):
    from milq.ui.plots import ChromatogramView, Trace

    view = ChromatogramView()
    view.resize(500, 320)
    x = np.linspace(0, 10, 200)
    view.set_traces([Trace("a", "a", x, np.exp(-(x - 5) ** 2), "#1f77b4")])
    view.show()
    qapp.processEvents()
    yield view
    view.close()
    view.deleteLater()


@pytest.mark.parametrize("fmt", ["png", "svg"])
@pytest.mark.parametrize("theme", ["light", "dark", "screen"])
def test_every_theme_writes_both_formats(chrom, tmp_path, fmt, theme):
    path = chart_export.export(chrom, tmp_path / "c.anything",
                               ExportOptions(fmt, 2, theme, "paper", 1.0))
    assert path.endswith(f".{fmt}") and os.path.getsize(path) > 1000


def test_the_ground_and_the_theme_are_what_was_asked(chrom):
    dark = chart_export.preview(chrom, ExportOptions("png", 2, "dark", "paper", 1))
    light = chart_export.preview(chrom, ExportOptions("png", 2, "light", "paper", 1))
    white = chart_export.preview(chrom, ExportOptions("png", 2, "dark", "white", 1))
    clear = chart_export.preview(chrom, ExportOptions("png", 2, "light", "transparent", 1))
    assert dark.pixelColor(2, 2).lightness() < 64
    assert light.pixelColor(2, 2).name() == "#ffffff"
    assert white.pixelColor(2, 2).name() == "#ffffff"
    assert clear.pixelColor(2, 2).alpha() == 0


def test_the_scale_sets_the_pixels(chrom):
    two = chart_export.preview(chrom, ExportOptions("png", 2, "light", "paper", 1))
    six = chart_export.preview(chrom, ExportOptions("png", 6, "light", "paper", 1))
    assert six.width() == pytest.approx(3 * two.width(), rel=0.02)


def test_the_chart_is_put_back(chrom):
    before = chrom.plot.backgroundBrush().color().name()
    tick = chrom.plot.getAxis("bottom").style.get("tickFont")
    chart_export.preview(chrom, ExportOptions("png", 2, "dark", "paper", 2.0))
    assert chrom.plot.backgroundBrush().color().name() == before
    assert chrom.plot.getAxis("bottom").style.get("tickFont") == tick


def test_options_are_clamped_and_remembered(qapp):
    from milq.ui.settings import settings

    ExportOptions("svg", 9, "dark", "transparent", 5).remember(settings())
    again = ExportOptions.remembered(settings())
    assert again == ExportOptions("svg", 6.0, "dark", "transparent", 2.2)


def test_install_offers_the_item_where_the_chart_has_a_menu_and_where_not(qapp):
    with_menu = pg.PlotWidget()
    without = pg.PlotWidget()
    without.setMenuEnabled(False)
    chart_export.install(with_menu, "a")
    chart_export.install(without, "b")
    qapp.processEvents()
    texts = [a.text() for a in with_menu.getPlotItem().getViewBox().menu.actions()]
    assert "Export as a picture…" in texts
    assert without.contextMenuPolicy() == chart_export.QtCore.Qt.ContextMenuPolicy.CustomContextMenu
    for widget in (with_menu, without):
        widget.deleteLater()


def test_the_dialog_previews_what_it_would_write(chrom, qapp):
    dialog = chart_export.ExportDialog(chrom, "chrom")
    try:
        assert dialog.preview.pixmap() is not None
        assert not dialog.preview.pixmap().isNull()
        dialog.format.setCurrentIndex(0)                  # SVG: no scale
        assert not dialog.scale.isEnabled()
    finally:
        dialog.deleteLater()


def test_the_type_size_reaches_the_legend_and_the_labels(chrom):
    from milq.ui.chart_export import _TypeScaled

    item = chrom.plot.getPlotItem()
    texts = [i for i in item.items if isinstance(i, pg.TextItem)]
    before = [t.textItem.font().pointSizeF() for t in texts]
    legend = [label.opts.get("size") for _s, label in item.legend.items]
    with _TypeScaled(chrom.plot, 2.0):
        during = [t.textItem.font().pointSizeF() for t in texts]
        assert all(d == pytest.approx(2 * (b if b > 0 else 9.0)) for b, d in zip(before, during))
        if legend:
            assert item.legend.items[0][1].opts["size"] != legend[0]
    assert [t.textItem.font().pointSizeF() for t in texts] == before
    assert [label.opts.get("size") for _s, label in item.legend.items] == legend
