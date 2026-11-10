"""
Who centroids a spectrum: the instrument's peak finder for a `.wiff`
(`MILQ_WIFF_CENTROID=sciex`), this program otherwise — and by default.
"""

import numpy as np
import pytest

from milq import centroiding


class VendorChannel:
    """A channel whose reader has a peak finder."""

    def __init__(self, sticks):
        self.sticks = sticks
        self.asked = []

    def vendor_centroids(self, scan=None, rt_start=None, rt_end=None):
        self.asked.append((scan, rt_start, rt_end))
        return self.sticks


class PlainChannel:
    def vendor_centroids(self, scan=None, rt_start=None, rt_end=None):
        return None


PROFILE = (np.array([99.98, 99.99, 100.00, 100.01, 100.02]),
           np.array([0.0, 50.0, 100.0, 50.0, 0.0]))
STICKS = (np.array([100.0012]), np.array([123.0]))


@pytest.mark.parametrize("value, mode", [
    (None, "local"), ("sciex", "sciex"), ("SCIEX", "sciex"), ("vendor", "sciex"),
    ("local", "local"),
    ("msdial", "local"), ("0", "0"), ("off", "0")])
def test_the_variable_names_the_mode(monkeypatch, value, mode):
    if value is None:
        monkeypatch.delenv(centroiding.ENV, raising=False)
    else:
        monkeypatch.setenv(centroiding.ENV, value)
    assert centroiding.mode() == mode


def test_this_program_centroids_by_default(monkeypatch):
    monkeypatch.delenv(centroiding.ENV, raising=False)
    channel = VendorChannel(STICKS)
    _mz, _h, how = centroiding.centroids(channel, *PROFILE, scan=7)
    assert how == "local" and channel.asked == []
    assert centroiding.vendor(channel, scan=7, force=True) is STICKS


def test_the_vendor_centroids_when_asked(monkeypatch):
    monkeypatch.setenv(centroiding.ENV, "sciex")
    channel = VendorChannel(STICKS)
    mz, height, how = centroiding.centroids(channel, *PROFILE, scan=7)
    assert how == "sciex" and mz[0] == pytest.approx(100.0012)
    assert channel.asked == [(7, None, None)]
    centroiding.centroids(channel, *PROFILE, rt_range=(1.0, 1.2))
    assert channel.asked[-1] == (None, 1.0, 1.2)


@pytest.mark.parametrize("value", ["local", "0"])
def test_the_variable_turns_the_vendor_off(monkeypatch, value):
    monkeypatch.setenv(centroiding.ENV, value)
    mz, _h, how = centroiding.centroids(VendorChannel(STICKS), *PROFILE, scan=0)
    assert how == "local" and mz[0] == pytest.approx(100.0, abs=1e-6)


def test_a_reader_without_a_peak_finder_is_centroided_here(monkeypatch):
    monkeypatch.delenv(centroiding.ENV, raising=False)
    _mz, _h, how = centroiding.centroids(PlainChannel(), *PROFILE, scan=0)
    assert how == "local"


def test_a_label_takes_the_vendors_apex_and_only_a_near_one():
    moved = centroiding.snap([100.0001, 150.0], (np.array([100.0012, 150.05]),
                                                   np.array([1.0, 1.0])))
    assert moved[0] == pytest.approx(100.0012)
    assert moved[1] == pytest.approx(150.0)          # 50 mDa is another peak


def test_an_mzml_has_no_vendor_peak_finder(tmp_path):
    from milq import mzml

    from tests.test_mzml import FakeSample, _ms1

    path = tmp_path / "x.mzML"
    mzml.write_mzml(FakeSample([_ms1()]), path)
    reader = mzml.MzmlFile(path)
    try:
        channel = reader.sample(0).channels[0]
        assert channel.vendor_centroids(scan=0) is None
        assert channel.vendor_centroids(rt_start=0.0, rt_end=1.0) is None
    finally:
        reader.close()


def test_the_pane_draws_and_names_the_vendors_sticks(qapp):
    from milq.ui.plots import SpectrumView, Trace

    view = SpectrumView()
    try:
        x = np.linspace(99.9, 100.1, 41)
        y = np.exp(-((x - 100.0) / 0.01) ** 2) * 1000.0
        trace = Trace("spec", "s", x, y, "#000000", None, None,
                      (np.array([100.0012]), np.array([1000.0])))
        view.set_traces([trace])
        assert view.peaks_of_current()[0][0] == pytest.approx(100.0012)
        view.set_centroid(True)
        sx, _sy = view.condition(trace)
        assert list(sx) == pytest.approx([100.0012])
    finally:
        view.deleteLater()


@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
