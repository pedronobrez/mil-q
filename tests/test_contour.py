"""
The surface: retention time by m/z.

It is a picture, and a picture of measured data has one obligation — that
nothing in the file disappears from it. Most of what is tested here is that:
a peak in one scan of a long run survives being drawn on a screen with fewer
rows than the run has scans, and intensity lands in the cell whose time and
mass it actually had.
"""

import numpy as np
import pytest

from milq.contour import DEFAULT_BINS, Contour, build_contour


class _Info:
    def __init__(self, start_mass, end_mass, n_scans):
        self.start_mass = start_mass
        self.end_mass = end_mass
        self.n_scans = n_scans


class _Channel:
    """A channel whose scans are given outright, as (m/z, intensity) pairs."""

    def __init__(self, times, spectra, start_mass=100.0, end_mass=1000.0):
        self.rt = np.asarray(times, dtype=float)
        self._spectra = spectra
        self.info = _Info(start_mass, end_mass, len(spectra))
        self.reads = 0
        self.zeros_asked = []

    def spectrum(self, scan, add_zeros=True):
        self.reads += 1
        self.zeros_asked.append(add_zeros)
        mz, intensity = self._spectra[int(scan)]
        return np.asarray(mz, dtype=float), np.asarray(intensity, dtype=float)


def _flat(n=20, mz=500.0, height=100.0):
    return _Channel(np.linspace(0.0, 10.0, n),
                    [([mz], [height]) for _ in range(n)])


# --------------------------------------------------------------------------- #
def test_intensity_lands_in_the_cell_it_belongs_to():
    channel = _Channel([0.0, 1.0, 2.0],
                       [([200.0], [10.0]), ([760.5], [4000.0]), ([200.0], [10.0])])
    contour = build_contour(channel, bins=900)
    assert contour.intensity.shape == (3, 900)
    assert contour.at(1.0, 760.5) == pytest.approx(4000.0)
    assert contour.at(0.0, 760.5) == pytest.approx(0.0)
    assert contour.at(0.0, 200.0) == pytest.approx(10.0)


def test_signal_outside_the_mass_range_is_left_out():
    channel = _Channel([0.0], [([50.0, 500.0, 5000.0], [9.0, 7.0, 9.0])])
    contour = build_contour(channel, bins=100)
    assert contour.intensity.sum() == pytest.approx(7.0)


def test_a_one_scan_peak_survives_a_run_longer_than_the_screen():
    """
    The reason rows are averaged rather than skipped. Sampling every k-th
    scan would drop this peak entirely, and a picture that loses a peak is
    worse than no picture.
    """
    spectra = [([300.0], [1.0]) for _ in range(500)]
    spectra[377] = ([300.0], [9000.0])
    channel = _Channel(np.linspace(0.0, 20.0, 500), spectra)

    contour = build_contour(channel, bins=200, max_rows=50)
    assert contour.grouped == 10
    assert contour.intensity.shape[0] == 50
    assert "10 scans averaged" in contour.note
    # the spike is diluted across its group but is unmistakably still there
    peak_row = int(np.argmax(contour.intensity[:, np.argmax(contour.intensity.sum(0))]))
    assert peak_row == 37
    assert contour.intensity.max() > 800


def test_rows_are_the_mean_so_a_short_last_group_is_not_dimmer():
    """
    Seven scans in groups of two leaves a group of one. Summed, that last
    row would be half as bright for no reason in the data.
    """
    channel = _flat(n=7, height=100.0)
    contour = build_contour(channel, bins=100, max_rows=4)
    assert contour.grouped == 2
    column = contour.intensity.sum(axis=0).argmax()
    assert contour.intensity[:, column] == pytest.approx([100.0] * 4)


def test_the_row_time_is_the_middle_of_the_scans_in_it():
    channel = _flat(n=10)          # 0 to 10 minutes, ten scans
    contour = build_contour(channel, bins=100, max_rows=5)
    assert contour.grouped == 2
    assert contour.rt[0] == pytest.approx(np.mean([0.0, 10 / 9]))


def test_zeros_are_not_restored_because_they_change_nothing_here():
    """
    Adding points of intensity zero cannot change a histogram of intensity,
    so asking for them would triple the reading for the same grid.
    """
    channel = _flat(n=5)
    build_contour(channel, bins=100)
    assert channel.zeros_asked == [False] * 5


# --------------------------------------------------------------------------- #
# refusals and partial results
# --------------------------------------------------------------------------- #
def test_a_channel_with_no_scans_says_so():
    contour = build_contour(_Channel([], []))
    assert contour.is_empty and "no scans" in contour.note


def test_a_channel_with_no_mass_range_says_so():
    channel = _flat(n=5)
    channel.info.start_mass, channel.info.end_mass = 0.0, 0.0
    contour = build_contour(channel)
    assert contour.is_empty and "mass range" in contour.note


def test_a_time_range_with_no_scans_in_it_says_so():
    contour = build_contour(_flat(n=5), rt_range=(50.0, 60.0))
    assert contour.is_empty and "no scans between" in contour.note


def test_cancelling_returns_what_was_read_and_says_it_stopped():
    """
    Half a run is still worth looking at, so stopping is not the same as
    failing — but the picture has to admit it is half a run.
    """
    channel = _flat(n=100)
    contour = build_contour(channel, bins=100,
                            progress=lambda done, total: done < 30)
    assert not contour.is_empty
    assert contour.scans == 30
    assert "stopped after 30 of 100" in contour.note
    assert channel.reads == 30


def test_an_unreadable_scan_does_not_lose_the_rest():
    class _Broken(_Channel):
        def spectrum(self, scan, add_zeros=True):
            if int(scan) == 2:
                raise RuntimeError("bad scan")
            return super().spectrum(scan, add_zeros)

    channel = _Broken(np.linspace(0, 4, 5), [([500.0], [10.0])] * 5)
    contour = build_contour(channel, bins=100)
    assert contour.scans == 5
    assert contour.intensity[2].sum() == pytest.approx(0.0)
    assert contour.intensity[0].sum() == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# slices
# --------------------------------------------------------------------------- #
def test_a_band_of_mass_gives_back_its_chromatogram():
    spectra = [([760.5], [float(n)]) for n in range(10)]
    contour = build_contour(_Channel(np.linspace(0, 9, 10), spectra), bins=900)
    rt, y = contour.slice_rt(760.0, 761.0)
    assert rt.size == 10
    assert y == pytest.approx(np.arange(10.0))


def test_a_band_of_time_gives_back_its_spectrum():
    channel = _Channel([0.0, 1.0], [([300.0], [10.0]), ([300.0], [30.0])])
    contour = build_contour(channel, bins=900)
    mz, intensity = contour.slice_mz(0.0, 1.0)
    assert mz[int(np.argmax(intensity))] == pytest.approx(300.0, abs=1.0)
    assert intensity.max() == pytest.approx(20.0)      # the mean of the two


def test_a_point_outside_the_surface_has_no_value():
    contour = build_contour(_flat(n=5), bins=100)
    assert contour.at(1.0, 5000.0) is None
    assert Contour().at(1.0, 500.0) is None


def test_the_rectangle_is_where_the_image_goes():
    contour = build_contour(_flat(n=5), bins=DEFAULT_BINS)
    left, bottom, width, height = contour.rect
    assert (left, bottom) == pytest.approx((0.0, 100.0))
    assert (width, height) == pytest.approx((10.0, 900.0))


def test_a_value_on_a_bin_edge_reads_the_bin_it_was_counted_into():
    """
    numpy's histogram puts a value sitting exactly on an edge into the bin to
    its right. Looking it up by searching left reads the cell next door, and
    the readout under the cursor then disagrees with the picture under it.
    """
    edges_at = 200.0                      # exactly an edge for these bins
    channel = _Channel([0.0], [([edges_at], [10.0])], start_mass=100.0,
                       end_mass=1000.0)
    contour = build_contour(channel, bins=900)
    assert contour.at(0.0, edges_at) == pytest.approx(10.0)
    # and the ends of the range still land inside the grid
    assert contour.at(0.0, 100.0) is not None
    assert contour.at(0.0, 1000.0) is not None
