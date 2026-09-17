"""
Three ways of arriving at an area, and what each one owes to the sampling.

The valley integrator is what this always did and is tested elsewhere; what
is tested here is that the other two are what they claim, that each one
fails out loud when it cannot run, and — the reason the Gaussian exists —
that its area is less at the mercy of where the scans landed than a
trapezoid over two or three points is. Those figures were measured before
they were asserted: at 14.6 s sampling a peak 14 s wide at half height gives
the trapezoid a 5% spread with the phase of the scans and the fit 0.2%.
"""

import numpy as np
import pytest

from milq import processing as pr
from milq.components import Component, IntegrationParams
from milq.method import ProcessingMethod
from milq.quantify import MANUAL, integrate_component, integrate_manually
from milq.samples import SampleEntry
from tests.test_matching import Channel, Sample

#: 14.6 s, the cycle of the acquisition this was built for
STEP = 14.6 / 60.0


def _gaussian(x, centre, sigma, height):
    return height * np.exp(-0.5 * ((x - centre) / sigma) ** 2)


# --------------------------------------------------------------------------- #
# the fit itself
# --------------------------------------------------------------------------- #
def test_a_well_sampled_gaussian_is_recovered_exactly():
    x = np.linspace(0, 2, 200)
    model = pr.fit_gaussian(x, _gaussian(x, 1.0, 0.05, 500.0))
    assert model is not None
    assert model.centre == pytest.approx(1.0, abs=1e-6)
    assert model.sigma == pytest.approx(0.05, rel=1e-6)
    assert model.height == pytest.approx(500.0, rel=1e-6)
    assert model.area == pytest.approx(500.0 * 0.05 * np.sqrt(2 * np.pi), rel=1e-6)
    assert model.r2 == pytest.approx(1.0, abs=1e-9)


def test_three_points_determine_the_fit_and_two_do_not():
    """
    Two positive points and a width make a Gaussian; two positive points
    alone settle wherever the fit started. Measured: a fit to two points at
    14.6 s sampling came back biased low by seven per cent, so it is not
    made.
    """
    x = np.arange(0, 7 * STEP, STEP)
    three = _gaussian(x, 3 * STEP, 0.1, 1000.0)
    three[three < 1] = 0
    assert int(np.sum(three > 0)) == 3
    assert pr.fit_gaussian(x, three) is not None

    two = _gaussian(x, 3.5 * STEP, 0.06, 1000.0)
    two[two < 1] = 0
    assert int(np.sum(two > 0)) == 2
    assert pr.fit_gaussian(x, two) is None


def test_three_points_of_which_two_are_the_peaks_feet_do_not_determine_it():
    """
    What a real internal standard looked like: 52,000 counts on one scan,
    44 and 98 on the scans beside it, and baseline blips of 20 and 39 a
    little further along. A curve through the three is exact and its width
    is taken from the noise.
    """
    x = np.arange(0, 7 * STEP, STEP)
    y = np.array([0.0, 0.0, 44.0, 52112.0, 98.0, 0.0, 0.0])
    assert pr.fit_gaussian(x, y) is None
    peak = pr.detect_peaks(x, y)[0]
    refined, note = pr.refine_gaussian(x, y, peak)
    assert refined is peak
    assert "narrower than the sampling resolves" in note
    # lift the neighbours onto the flanks and the same three points fit
    y[2], y[4] = 5000.0, 9000.0
    model = pr.fit_gaussian(x, y)
    assert model is not None and model.exact
    assert "exact through 3 points" in model.quality


def test_the_fit_is_less_sensitive_to_scan_phase_than_the_trapezoid():
    """
    The reason the algorithm exists. A peak 14 s wide at half height on a
    14.6 s cycle is two or three points, and where they land relative to
    the apex is an accident of the acquisition; a trapezoid over them moves
    with that accident and a fitted curve does not.
    """
    sigma = 0.10
    trapezoid, fitted, refused = [], [], 0
    for phase in np.linspace(0, STEP, 30, endpoint=False):
        x = np.arange(0, 12, STEP) + phase
        y = _gaussian(x, 6.0, sigma, 1000.0)
        y[y < 1] = 0
        peak = pr.detect_peaks(x, y)[0]
        refined, note = pr.refine_gaussian(x, y, peak)
        trapezoid.append(peak.area)
        if note:
            refused += 1
            assert "valley area kept" in note
        else:
            fitted.append(refined.area)
    trapezoid, fitted = np.array(trapezoid), np.array(fitted)
    true = 1000.0 * sigma * np.sqrt(2 * np.pi)
    assert trapezoid.std() / trapezoid.mean() > 0.03      # the problem is real
    # at this width the scans land on the flanks for about half the phases:
    # every fit that is made is exact, and every one that is not says so
    assert 5 <= len(fitted) <= 25 and refused == 30 - len(fitted)
    assert np.abs(fitted / true - 1).max() < 1e-3


def test_a_fit_that_cannot_be_made_leaves_the_valley_area_and_says_so():
    x = np.arange(0, 12, STEP)
    y = _gaussian(x, 6.0 + STEP / 2, 0.05, 1000.0)
    y[y < 1] = 0
    peak = pr.detect_peaks(x, y)[0]
    refined, note = pr.refine_gaussian(x, y, peak)
    assert refined is peak
    assert refined.algorithm == pr.ALGORITHM_VALLEY
    assert "Gaussian fit not possible" in note and "valley area kept" in note


def test_a_fitted_peak_carries_its_model_and_the_fit_algorithm():
    x = np.linspace(0, 4, 400)
    y = _gaussian(x, 2.0, 0.08, 800.0) + 3.0
    peak = pr.detect_peaks(x, y)[0]
    refined, note = pr.refine_gaussian(x, y, peak)
    assert note == ""
    assert refined.algorithm == pr.ALGORITHM_GAUSSIAN
    assert refined.model is not None
    assert refined.model.centre == pytest.approx(2.0, abs=0.01)
    assert refined.width == pytest.approx(pr.FWHM_PER_SIGMA * 0.08, rel=0.05)
    assert refined.apex_rt == pytest.approx(refined.model.centre)


def test_a_tailing_peak_is_fitted_with_a_lower_r2_rather_than_refused():
    """
    A Gaussian on a tailing peak is a stated approximation: the area stays
    within a few per cent and the r² says how far from Gaussian it was.
    """
    x = np.linspace(0, 6, 3000)
    sigma, tau = 0.08, 0.16
    from math import erf
    z = ((x - 3.0) / sigma - sigma / tau) / np.sqrt(2)
    y = np.exp(0.5 * (sigma / tau) ** 2 - (x - 3.0) / tau) * (1 + np.array([erf(v) for v in z]))
    y = 1000.0 * y / y.max()
    peak = pr.detect_peaks(x, y)[0]
    refined, note = pr.refine_gaussian(x, y, peak)
    assert note == ""
    assert refined.model.r2 < 0.99
    assert refined.area == pytest.approx(peak.area, rel=0.05)


def test_the_model_survives_a_round_trip_through_a_dict():
    model = pr.GaussianModel(1.5, 0.05, 300.0, 0.98, 7)
    assert pr.GaussianModel.from_dict(model.to_dict()) == model
    assert pr.GaussianModel.from_dict(None) is None
    assert pr.GaussianModel.from_dict({"centre": "x"}) is None


# --------------------------------------------------------------------------- #
# summation
# --------------------------------------------------------------------------- #
def test_summation_is_the_area_above_the_line_across_the_window():
    x = np.linspace(0, 10, 1001)
    y = _gaussian(x, 5.0, 0.1, 1000.0) + 20.0
    peak, note = pr.summation_peak(x, y, 4.0, 6.0)
    assert note == "" and peak is not None
    assert peak.algorithm == pr.ALGORITHM_SUMMATION
    assert peak.start_rt == pytest.approx(4.0) and peak.end_rt == pytest.approx(6.0)
    assert peak.area == pytest.approx(1000.0 * 0.1 * np.sqrt(2 * np.pi), rel=0.01)
    assert peak.height == pytest.approx(1000.0, rel=0.01)


def test_summation_honours_the_signal_to_noise_gate():
    x = np.linspace(0, 10, 1001)
    rng = np.random.default_rng(3)
    y = rng.normal(0, 2.0, x.size) + 50.0
    # the tallest of two hundred noise points sits about three and a half
    # noise units up, so the gate has to ask for more than that
    gated, note = pr.summation_peak(x, y, 4.0, 6.0, min_snr=5.0)
    assert gated is None and note == "no peak above noise"
    ungated, _ = pr.summation_peak(x, y, 4.0, 6.0, min_snr=0.0)
    assert ungated is not None


def test_summation_refuses_a_window_it_cannot_integrate():
    x = np.linspace(0, 10, 11)
    peak, note = pr.summation_peak(x, np.ones_like(x), 4.0, 4.5)
    assert peak is None and "three points" in note
    peak, note = pr.summation_peak(x, np.zeros_like(x), 2.0, 8.0)
    assert peak is None and "nothing above the baseline" in note


# --------------------------------------------------------------------------- #
# through the method, which is where the wiring can be wrong
# --------------------------------------------------------------------------- #
class _CoarseChannel(Channel):
    """One transition every 14.6 s, with a Gaussian peak of a given width."""

    def __init__(self, *args, apex=6.41, height=20000.0, sigma=0.13, **kwargs):
        super().__init__(*args, **kwargs)
        self.apex, self.height, self.sigma = apex, height, sigma

    def xic_range(self, mz_lo, mz_hi):
        y = _gaussian(self.rt, self.apex, self.sigma, self.height)
        y[y < 1] = 0
        return self.rt, y


def _batch(algorithm, rt=6.4, halfwidth=0.5, **channel):
    scans = int(round(12.0 / STEP))
    chan = _CoarseChannel(1, 703.6, 100.0, 800.0, 0.0, 12.0, n=scans, **channel)
    entry = SampleEntry("/d/QC01.wiff", 0, "QC01")
    entry.sample = Sample([chan])
    method = ProcessingMethod()
    method.defaults = IntegrationParams(algorithm=algorithm)
    method.replace_all([Component("C16_SM", 703.6, 184.0733, rt=rt,
                                  rt_halfwidth=halfwidth)])
    return entry, method


@pytest.mark.parametrize("algorithm", pr.ALGORITHMS)
def test_every_algorithm_finds_an_obvious_peak_and_signs_its_work(algorithm):
    entry, method = _batch(algorithm)
    result = integrate_component(entry, method.components[0], method)
    assert result.found, result.note
    assert result.algorithm == algorithm
    assert result.rt == pytest.approx(6.41, abs=STEP)


def test_the_three_algorithms_give_three_different_areas_from_one_file():
    """The unit tests prove each algorithm; this proves the setting reaches
    the integration, which is where a wiring mistake would hide."""
    areas = {}
    for algorithm in pr.ALGORITHMS:
        entry, method = _batch(algorithm)
        areas[algorithm] = integrate_component(entry, method.components[0], method).area
    assert len({round(a, 6) for a in areas.values()}) == 3
    # the fit is exact on this synthetic peak, and the closest of the three
    true = 20000.0 * 0.13 * np.sqrt(2 * np.pi)
    assert areas[pr.ALGORITHM_GAUSSIAN] == pytest.approx(true, rel=1e-3)
    assert abs(areas[pr.ALGORITHM_GAUSSIAN] - true) < abs(areas[pr.ALGORITHM_VALLEY] - true)


def test_a_fit_that_fell_back_is_labelled_with_what_ran():
    entry, method = _batch(pr.ALGORITHM_GAUSSIAN, sigma=0.05, apex=6.41 + STEP / 2)
    result = integrate_component(entry, method.components[0], method)
    assert result.found, result.note
    assert result.algorithm == pr.ALGORITHM_VALLEY
    assert result.model is None
    assert "valley area kept" in result.note


def test_summation_needs_a_window_and_says_so_without_one():
    entry, method = _batch(pr.ALGORITHM_SUMMATION, rt=None)
    result = integrate_component(entry, method.components[0], method)
    assert not result.found
    assert result.note == "summation needs a retention-time window"


def test_a_manual_row_is_signed_manual_whatever_the_method_says():
    entry, method = _batch(pr.ALGORITHM_GAUSSIAN)
    result = integrate_manually(entry, method.components[0], method, 6.0, 6.8)
    assert result.found and result.manual
    assert result.algorithm == MANUAL


def test_a_method_saved_before_the_setting_existed_reads_back_as_valley():
    data = ProcessingMethod().to_dict()
    del data["defaults"]["algorithm"]
    data["components"] = [{"name": "A", "precursor": 1.0, "fragment": 1.0,
                           "integration": {"smoothing": 1.0}}]
    method = ProcessingMethod.from_dict(data)
    assert method.defaults.algorithm == pr.ALGORITHM_VALLEY
    assert method.components[0].integration.algorithm == pr.ALGORITHM_VALLEY


def test_an_unknown_algorithm_falls_back_rather_than_failing():
    assert IntegrationParams(algorithm="magic").algorithm == pr.ALGORITHM_VALLEY


def test_the_setting_survives_a_round_trip_through_a_saved_method(tmp_path):
    method = ProcessingMethod()
    method.defaults.algorithm = pr.ALGORITHM_GAUSSIAN
    method.replace_all([Component("A", 1.0, 1.0,
                                  integration=IntegrationParams(
                                      algorithm=pr.ALGORITHM_SUMMATION))])
    path = tmp_path / "m.json"
    method.save(path)
    loaded = ProcessingMethod.load(path)
    assert loaded.defaults.algorithm == pr.ALGORITHM_GAUSSIAN
    assert loaded.components[0].integration.algorithm == pr.ALGORITHM_SUMMATION
