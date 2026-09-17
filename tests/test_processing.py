"""Tests for the numeric helpers (no .wiff files required)."""

import numpy as np
import pytest

from milq import processing as pr


def gaussian(x, centre, sigma, height):
    return height * np.exp(-((x - centre) ** 2) / (2 * sigma**2))


@pytest.fixture
def chrom():
    x = np.linspace(0, 20, 2000)
    y = gaussian(x, 10.0, 0.1, 1000.0) + 5.0
    return x, y


def test_moving_average_preserves_length_and_smooths():
    y = np.array([0.0, 10.0, 0.0, 10.0, 0.0, 10.0, 0.0])
    out = pr.moving_average(y, 3)
    assert out.size == y.size
    assert out.std() < y.std()


def test_moving_average_noop_for_window_one():
    y = np.arange(5.0)
    assert np.array_equal(pr.moving_average(y, 1), y)


def test_gaussian_smooth_reduces_noise_keeps_peak(chrom):
    x, y = chrom
    rng = np.random.default_rng(0)
    noisy = y + rng.normal(0, 20, y.size)
    smooth = pr.gaussian_smooth(noisy, 5.0)
    assert smooth.size == y.size
    assert np.std(smooth - y) < np.std(noisy - y)


def test_local_maxima_finds_single_peak(chrom):
    x, y = chrom
    idx = pr.local_maxima(y)
    assert idx.size >= 1
    assert abs(x[idx[np.argmax(y[idx])]] - 10.0) < 0.05


def test_pick_peaks_merges_neighbours():
    mz = np.linspace(180, 186, 6000)
    y = gaussian(mz, 183.139, 0.004, 1000.0)
    peaks = pr.pick_peaks(mz, y, max_peaks=10, min_distance=0.03)
    assert len(peaks) == 1
    assert abs(peaks[0][0] - 183.139) < 0.005


def test_pick_peaks_orders_by_intensity():
    mz = np.linspace(100, 200, 20000)
    y = gaussian(mz, 120.0, 0.01, 500.0) + gaussian(mz, 150.0, 0.01, 900.0)
    peaks = pr.pick_peaks(mz, y, max_peaks=5)
    assert [round(p[0]) for p in peaks] == [150, 120]


def test_integrate_subtracts_flat_baseline(chrom):
    x, y = chrom
    stats = pr.integrate(x, y, 9.5, 10.5)
    expected = 1000.0 * 0.1 * np.sqrt(2 * np.pi)
    assert stats["area"] == pytest.approx(expected, rel=0.02)
    assert stats["height"] == pytest.approx(1000.0, rel=0.02)
    assert stats["apex_rt"] == pytest.approx(10.0, abs=0.02)


def test_integrate_empty_range_is_safe(chrom):
    x, y = chrom
    stats = pr.integrate(x, y, 5.0, 5.0)
    assert stats["area"] == 0.0


def test_signal_to_noise_high_for_clean_peak(chrom):
    x, y = chrom
    assert pr.signal_to_noise(x, y, 9.5, 10.5) > 50


def test_baseline_reduces_offset(chrom):
    x, y = chrom
    corrected = pr.subtract_baseline(x, y, window=2.0)
    assert abs(np.median(corrected)) < abs(np.median(y))
    assert corrected.max() == pytest.approx(1000.0, rel=0.05)


def test_detect_peaks_finds_two_peaks():
    x = np.linspace(0, 20, 4000)
    y = gaussian(x, 6.0, 0.08, 800.0) + gaussian(x, 12.0, 0.08, 400.0) + 2.0
    peaks = pr.detect_peaks(x, y, min_relative=0.05)
    assert len(peaks) == 2
    assert peaks[0].apex_rt == pytest.approx(6.0, abs=0.05)
    assert peaks[0].area > peaks[1].area
    assert peaks[0].start_rt < 6.0 < peaks[0].end_rt


def test_detect_peaks_empty_signal():
    x = np.linspace(0, 10, 100)
    assert pr.detect_peaks(x, np.zeros_like(x)) == []


def test_estimate_noise_falls_back_when_mad_is_zero():
    # quantised signal: more than half the differences are exactly zero
    y = np.array([0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 1.0, 0.0])
    assert pr.estimate_noise(y) > 0


def test_detect_peaks_rejects_single_count_spikes():
    # sparse low-count XIC: almost all zero, with a single-count spike
    x = np.linspace(0, 10, 200)
    y = np.zeros_like(x)
    y[100] = 1.0
    assert pr.detect_peaks(x, y, min_relative=0.05, min_snr=3.0) == []


def test_detect_peaks_keeps_real_peak_over_zero_baseline():
    """
    The peak is kept — the floor still filters — but no signal-to-noise is
    reported, because a baseline of exact zeros has nothing to measure. It
    used to report height over the floor of 1.0, which reads as a ratio and
    is not one: on 846 real traces the noise was measurable in nine per cent.
    """
    x = np.linspace(0, 10, 200)
    y = np.zeros_like(x)
    y[95:106] = [5, 12, 30, 70, 140, 200, 150, 80, 35, 14, 6]
    peaks = pr.detect_peaks(x, y, min_relative=0.05, min_snr=3.0)
    assert len(peaks) == 1
    assert peaks[0].height == pytest.approx(200.0, rel=0.05)
    assert peaks[0].snr is None


def test_a_measurable_baseline_still_gives_a_ratio():
    """The other half: where there is a baseline, the number means what it says."""
    rng = np.random.default_rng(4)
    x = np.linspace(0, 10, 400)
    y = 20.0 + rng.normal(0, 2.0, 400)
    y[195:206] += np.array([5, 12, 30, 70, 140, 200, 150, 80, 35, 14, 6])
    peaks = pr.detect_peaks(x, y, min_relative=0.05, min_snr=3.0)
    assert peaks                       # noise peaks may pass too; take the real one
    tallest = max(peaks, key=lambda p: p.area)
    assert tallest.snr is not None
    assert tallest.snr == pytest.approx(200 / 2.0, rel=0.5)


def test_signal_to_noise_is_finite_on_zero_noise():
    x = np.linspace(0, 10, 200)
    y = np.zeros_like(x)
    y[100] = 50.0
    assert np.isfinite(pr.signal_to_noise(x, y, 4.9, 5.1))


def test_centroid_spectrum_collapses_profile_peaks():
    mz = np.linspace(180, 200, 20000)
    y = gaussian(mz, 183.139, 0.004, 1000.0) + gaussian(mz, 195.140, 0.004, 400.0)
    cmz, ci = pr.centroid_spectrum(mz, y)
    assert cmz.size == 2
    assert np.all(np.diff(cmz) > 0)  # sorted by mass
    assert cmz[0] == pytest.approx(183.139, abs=0.002)
    assert cmz[1] == pytest.approx(195.140, abs=0.002)
    assert ci[0] > ci[1]


def test_centroid_spectrum_empty_input():
    cmz, ci = pr.centroid_spectrum(np.zeros(0), np.zeros(0))
    assert cmz.size == 0 and ci.size == 0


# --- noise regions and manual integration ------------------------------------- #
def test_noise_in_region_modes_differ():
    rng = np.random.default_rng(3)
    x = np.linspace(0, 10, 500)
    y = rng.normal(0, 5.0, x.size)
    peak_to_peak = pr.noise_in_region(x, y, 1.0, 9.0, pr.SNR_PEAK_TO_PEAK)
    deviation = pr.noise_in_region(x, y, 1.0, 9.0, pr.SNR_STANDARD_DEVIATION)
    # the full swing of a noisy stretch is several standard deviations wide
    assert peak_to_peak > deviation * 3
    assert deviation == pytest.approx(5.0, rel=0.2)


def test_noise_in_region_needs_enough_points():
    x = np.linspace(0, 10, 100)
    assert pr.noise_in_region(x, x, 5.0, 5.0) is None


def test_integrate_window_uses_exactly_the_given_range():
    x = np.linspace(0, 20, 2000)
    y = gaussian(x, 10.0, 0.1, 1000.0) + 5.0
    peak = pr.integrate_window(x, y, 9.5, 10.5)
    assert peak.start_rt == pytest.approx(9.5, abs=0.02)
    assert peak.end_rt == pytest.approx(10.5, abs=0.02)
    assert peak.apex_rt == pytest.approx(10.0, abs=0.02)
    assert peak.height == pytest.approx(1000.0, rel=0.02)


def test_integrate_window_ignores_a_taller_peak_outside_it():
    x = np.linspace(0, 20, 2000)
    y = gaussian(x, 5.0, 0.1, 5000.0) + gaussian(x, 15.0, 0.1, 500.0)
    peak = pr.integrate_window(x, y, 14.5, 15.5)
    assert peak.apex_rt == pytest.approx(15.0, abs=0.02)
    assert peak.height == pytest.approx(500.0, rel=0.02)


def test_integrate_window_rejects_a_sliver():
    x = np.linspace(0, 20, 2000)
    assert pr.integrate_window(x, x, 10.0, 10.0) is None


def test_integrate_window_uses_the_supplied_noise():
    x = np.linspace(0, 20, 2000)
    y = gaussian(x, 10.0, 0.1, 1000.0)
    loud = pr.integrate_window(x, y, 9.5, 10.5, noise=100.0)
    quiet = pr.integrate_window(x, y, 9.5, 10.5, noise=1.0)
    assert loud.snr == pytest.approx(quiet.snr / 100, rel=0.01)


def test_detect_peaks_accepts_an_external_noise_value():
    x = np.linspace(0, 20, 2000)
    y = gaussian(x, 10.0, 0.1, 100.0)
    assert pr.detect_peaks(x, y, min_snr=3.0, noise=1.0)
    assert pr.detect_peaks(x, y, min_snr=3.0, noise=1000.0) == []


# -- where a peak ends -------------------------------------------------------- #
def gaussian_on_flat(height=1000.0, centre=5.0, width=0.05, span=(0.0, 15.0),
                     points=600, baseline=0.0):
    x = np.linspace(*span, points)
    y = height * np.exp(-((x - centre) ** 2) / (2 * width ** 2)) + baseline
    return x, y


def test_a_peak_on_a_flat_baseline_keeps_its_own_boundaries():
    """
    Walking out "while not going up" reads a flat stretch as still descending.
    An XIC is mostly flat baseline, so the boundaries ran to the ends of the
    trace and a peak seconds wide was reported minutes wide.
    """
    x, y = gaussian_on_flat()
    peaks = pr.detect_peaks(x, y)
    assert peaks
    peak = peaks[0]
    assert peak.start_rt > 4.0 and peak.end_rt < 6.0
    assert (peak.end_rt - peak.start_rt) < 1.0


def test_the_boundaries_do_not_run_to_the_ends_of_the_trace():
    x, y = gaussian_on_flat(span=(0.0, 30.0), points=1200)
    peak = pr.detect_peaks(x, y)[0]
    assert peak.start_rt > float(x[0]) + 1.0
    assert peak.end_rt < float(x[-1]) - 1.0


def test_a_peak_on_a_raised_baseline_stops_at_the_baseline():
    """Two per cent of a tall apex can sit under the trace's own background."""
    x, y = gaussian_on_flat(height=2000.0, baseline=200.0)
    peak = pr.detect_peaks(x, y)[0]
    assert (peak.end_rt - peak.start_rt) < 1.0


def test_two_peaks_are_split_at_the_valley_between_them():
    x = np.linspace(0.0, 10.0, 800)
    y = (1000.0 * np.exp(-((x - 4.0) ** 2) / (2 * 0.08 ** 2))
         + 800.0 * np.exp(-((x - 5.0) ** 2) / (2 * 0.08 ** 2)))
    peaks = sorted(pr.detect_peaks(x, y), key=lambda p: p.apex_rt)
    assert len(peaks) >= 2
    assert peaks[0].end_rt <= peaks[1].start_rt + 0.05


def test_the_area_still_measures_the_peak():
    x, y = gaussian_on_flat(height=1000.0, width=0.05)
    peak = pr.detect_peaks(x, y)[0]
    # a gaussian's area is height * sigma * sqrt(2 pi)
    expected = 1000.0 * 0.05 * np.sqrt(2 * np.pi)
    assert peak.area == pytest.approx(expected, rel=0.05)


def _pick_peaks_one_at_a_time(mz, y, max_peaks, min_relative, centroid,
                              min_distance):
    """The picker as it was written: every candidate asked about every peak
    kept so far. The reference the bisection has to reproduce exactly."""
    idx = pr.local_maxima(y)
    if idx.size == 0:
        idx = np.array([int(y.argmax())])
    idx = idx[y[idx] >= y.max() * min_relative]
    order = idx[np.argsort(y[idx])[::-1]]
    peaks = []
    for i in order:
        m = pr.centroid_mz(mz, y, int(i)) if centroid else float(mz[i])
        if any(abs(m - kept) < min_distance for kept, _ in peaks):
            continue
        peaks.append((m, float(y[i])))
        if len(peaks) >= max_peaks:
            break
    return peaks


def test_centroids_at_is_centroid_mz_to_the_last_bit():
    rng = np.random.default_rng(3)
    n = 400
    mz = np.sort(rng.random(n)) * 1000
    for y in (rng.random(n) * 1e5, rng.integers(0, 9, size=n),
              (rng.random(n) * 7).astype(np.float32)):
        y = np.asarray(y)
        y[5:9] = 0  # a window whose weights sum to nothing
        got = pr.centroids_at(mz, y, np.arange(n))
        want = np.array([pr.centroid_mz(mz, y, i) for i in range(n)])
        assert np.array_equal(got, want)
    assert pr.centroids_at(mz, mz, np.zeros(0, dtype=int)).size == 0


def test_pick_peaks_bisection_reproduces_the_linear_scan():
    """Same peaks, same order, same floats — including the apex on an edge,
    ties, integer counts and a ceiling the picker never reaches."""
    rng = np.random.default_rng(11)
    cases = 0
    for trial in range(24):
        n = int(rng.integers(3, 600))
        mz = np.sort(rng.random(n)) * 500
        y = rng.random(n) * 1e4
        if trial % 3 == 1:
            y = rng.integers(0, 40, size=n)
        if trial % 4 == 0:
            y[0] = y.max() * 2
        if trial % 5 == 0:
            y[-1] = y.max() * 2
        for max_peaks in (1, 15, 100_000):
            for min_relative in (0.0, 0.01, 0.5):
                for centroid in (True, False):
                    for distance in (0.0, 0.005, 0.03, 5.0):
                        want = _pick_peaks_one_at_a_time(
                            mz, y, max_peaks, min_relative, centroid, distance)
                        got = pr.pick_peaks(mz, y, max_peaks=max_peaks,
                                            min_relative=min_relative,
                                            centroid=centroid,
                                            min_distance=distance)
                        assert got == want
                        assert all(type(m) is float and type(h) is float
                                   for m, h in got)
                        cases += 1
    assert cases == 24 * 3 * 3 * 2 * 4
