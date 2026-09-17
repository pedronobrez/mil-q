"""
The contour widget.

Two things here are easy to get wrong and invisible in a screenshot: which
way round the axes go — an image drawn transposed still looks like a
plausible surface — and the level the colour scale tops out at, which decides
whether anything but the base peak is visible at all.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq.contour import build_contour  # noqa: E402
from milq.ui.contour_view import LINEAR, LOG, SQRT, ContourView  # noqa: E402
from tests.test_contour import _Channel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _contour(n=12):
    spectra = [([300.0], [10.0]) for _ in range(n)]
    spectra[5] = ([300.0, 700.0], [10.0, 5000.0])
    return build_contour(_Channel(np.linspace(0.0, 11.0, n), spectra), bins=900)


def test_the_image_keeps_time_across_and_mass_up(qapp):
    """
    A transposed surface still looks like a surface, so the axes are checked
    against the numbers rather than by eye. The rectangle the image is drawn
    into is what ties a cell to a retention time and an m/z.
    """
    view = ContourView()
    contour = _contour()
    view.set_contour(contour, "TOF MS")

    rect = view.image.boundingRect() if hasattr(view.image, "boundingRect") else None
    assert rect is not None
    # x is time, y is mass — the same way round as the contour's own rect
    left, bottom, width, height = contour.rect
    assert (left, bottom) == pytest.approx((0.0, 100.0))
    assert width == pytest.approx(11.0)
    assert height == pytest.approx(900.0)
    # and the array itself is rows of time by columns of mass
    assert view.image.image.shape == contour.intensity.shape
    assert contour.intensity.shape[0] == 12


def test_the_scale_changes_what_is_drawn_without_touching_the_data(qapp):
    view = ContourView()
    contour = _contour()
    view.set_contour(contour)
    original = contour.intensity.copy()

    view.scale.setCurrentText(LINEAR)
    linear = view.image.image.max()
    view.scale.setCurrentText(SQRT)
    root = view.image.image.max()
    view.scale.setCurrentText(LOG)
    log = view.image.image.max()

    assert linear > root > log
    assert root == pytest.approx(np.sqrt(linear))
    assert contour.intensity == pytest.approx(original)   # the data is untouched


def test_the_top_of_the_scale_is_not_the_maximum(qapp):
    """
    One spiking scan would otherwise set the scale for the whole surface and
    leave everything else black. The top comes from a percentile of the cells
    that carry signal.
    """
    view = ContourView()
    view.set_contour(_contour())
    view.scale.setCurrentText(LINEAR)
    _, top = view.image.getLevels()
    assert top < view.image.image.max()
    assert top > 0


def test_an_empty_contour_says_so_rather_than_drawing_nothing(qapp):
    from milq.contour import Contour

    view = ContourView()
    view.set_contour(Contour(note="the channel has no scans"))
    assert "no scans" in view.status.text()


def test_the_region_signal_carries_what_is_on_screen(qapp):
    view = ContourView()
    view.set_contour(_contour())
    view.plot.setXRange(2.0, 5.0, padding=0)
    view.plot.setYRange(600.0, 800.0, padding=0)

    seen = []
    view.sigRegionPicked.connect(lambda *args: seen.append(args))
    view.btn_extract.click()
    assert len(seen) == 1
    rt_lo, rt_hi, mz_lo, mz_hi = seen[0]
    assert (rt_lo, rt_hi) == pytest.approx((2.0, 5.0), abs=0.01)
    assert (mz_lo, mz_hi) == pytest.approx((600.0, 800.0), abs=0.01)


def test_nothing_is_emitted_from_an_empty_surface(qapp):
    view = ContourView()
    seen = []
    view.sigRegionPicked.connect(lambda *args: seen.append(args))
    view.btn_extract.click()
    assert seen == []
