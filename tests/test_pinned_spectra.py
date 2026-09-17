"""
Spectra held for comparison: the live one first, the pinned ones after.

What matters is that the first trace stays the live spectrum — every panel
reads it — and that the pinned ones survive the live one changing.
"""

import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtGui, QtWidgets  # noqa: E402

from milq.session import Session  # noqa: E402
from milq.ui.explorer import ExplorerWorkspace  # noqa: E402
from milq.ui.plots import Trace  # noqa: E402


def test_pinning_keeps_the_live_spectrum_first_and_the_pins_after():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    explorer = ExplorerWorkspace(Session())
    mz = np.linspace(100, 200, 50)
    first = Trace("spec", "spectrum", mz, np.ones(50), "#1f77b4")
    explorer.spectrum.set_traces([first])
    explorer.spectrum.set_title("sample A · scan 3")
    assert not explorer.act_unpin.isEnabled()
    explorer.pin_spectrum()
    assert explorer.act_unpin.isEnabled()
    assert [t.key for t in explorer.spectrum.traces] == ["spec", "pin1"]
    assert explorer.pinned_spectra[0].label == "sample A · scan 3"
    # the next live spectrum draws over the pin, and stays first
    second = Trace("spec", "spectrum", mz, np.ones(50) * 2, "#1f77b4")
    explorer.spectrum.set_traces(explorer._with_pins(second))
    assert [t.key for t in explorer.spectrum.traces] == ["spec", "pin1"]
    assert explorer._current_spectrum()[1].max() == 2.0
    explorer.pin_spectrum()
    assert [t.key for t in explorer.spectrum.traces] == ["spec", "pin1", "pin2"]
    assert explorer.pinned_spectra[1].colour != explorer.pinned_spectra[0].colour
    explorer.unpin_spectra()
    assert [t.key for t in explorer.spectrum.traces] == ["spec"]
    assert not explorer.act_unpin.isEnabled()
    explorer.deleteLater()
    app.processEvents()


def _explorer(app):
    explorer = ExplorerWorkspace(Session())
    mz = np.linspace(100.0, 200.0, 400)
    live = Trace("spec", "spectrum", mz,
                 np.exp(-0.5 * ((mz - 150.0) / 0.4) ** 2) * 1000.0, "#1f77b4")
    explorer.spectrum.set_traces([live])
    explorer.spectrum.set_title("sample A · scan 3")
    return explorer, mz


def test_the_report_gets_what_the_pane_shows_while_a_pin_stands():
    """
    The rule is that the report prints what the Explorer shows: pinning
    starts the comparison, the live spectrum changing refreshes it, and
    unpinning drops it. Nothing to keep in step by hand, and nothing stale.
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    explorer, mz = _explorer(app)
    session = explorer.session
    assert session.spectra_comparison is None
    assert not explorer.act_exp_cmp.isEnabled()

    explorer.pin_spectrum()
    comparison = session.spectra_comparison
    assert comparison is not None and comparison.stands
    assert explorer.act_exp_cmp.isEnabled()
    # the live trace is named by the pane's title, the way a pin is
    assert [t.label for t in comparison.traces] == ["sample A · scan 3"] * 2

    second = Trace("spec", "spectrum", mz,
                   np.exp(-0.5 * ((mz - 120.0) / 0.4) ** 2) * 500.0, "#1f77b4")
    explorer.spectrum.set_traces(explorer._with_pins(second))
    explorer.spectrum.set_title("sample B · scan 9")
    explorer.refresh_comparison()
    labels = [t.label for t in session.spectra_comparison.traces]
    assert labels == ["sample B · scan 9", "sample A · scan 3"]

    explorer.unpin_spectra()
    assert session.spectra_comparison is None
    assert not explorer.act_exp_cmp.isEnabled()
    explorer.deleteLater()
    app.processEvents()


def test_the_comparison_carries_the_two_switches():
    """Normalise and Mirror are how the comparison is read, so the picture
    has to be drawn the way the pane was drawing it."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    explorer, _mz = _explorer(app)
    explorer.pin_spectrum()
    assert explorer.session.spectra_comparison.mirror is False
    explorer.act_mirror.setChecked(True)
    explorer.act_norm.setChecked(True)
    comparison = explorer.session.spectra_comparison
    assert comparison.mirror and comparison.normalise
    assert "downwards" in comparison.summary()
    explorer.deleteLater()
    app.processEvents()


def test_the_comparison_is_exported_as_a_picture(tmp_path):
    """PNG at twice the size for print, SVG for a figure to be resized."""
    from milq.spectra_compare import DEFAULT_HEIGHT, DEFAULT_WIDTH, PRINT_SCALE

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    explorer, _mz = _explorer(app)
    assert explorer._write_comparison(str(tmp_path / "none.png")) is None

    explorer.pin_spectrum()
    png = explorer._write_comparison(str(tmp_path / "cmp.png"))
    image = QtGui.QImage(png)
    assert (image.width(), image.height()) == (
        int(DEFAULT_WIDTH * PRINT_SCALE), int(DEFAULT_HEIGHT * PRINT_SCALE))
    # the extension decides the format even when the filter did not
    svg = explorer._write_comparison(str(tmp_path / "cmp.svg"))
    assert svg.endswith(".svg") and open(svg, encoding="utf-8").read().startswith("<?xml")
    named = explorer._write_comparison(str(tmp_path / "vector"), svg=True)
    assert named.endswith(".svg")
    explorer.deleteLater()
    app.processEvents()
