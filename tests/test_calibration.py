"""Tests for curve fitting and reading concentrations back off a curve."""

import numpy as np
import pytest

from milq import calibration as cal


def points(concentrations, responses, names=None):
    names = names or [f"STD{i + 1}" for i in range(len(concentrations))]
    return [
        cal.CalibrationPoint(f"s{i}", name, float(c), float(r))
        for i, (c, r, name) in enumerate(zip(concentrations, responses, names))
    ]


LEVELS = [1.0, 5.0, 10.0, 50.0, 100.0, 500.0]


# --- linear -------------------------------------------------------------------- #
def test_linear_recovers_slope_and_intercept():
    curve = cal.fit(points(LEVELS, [2 * c + 3 for c in LEVELS]))
    assert curve.coefficients[0] == pytest.approx(2.0)
    assert curve.coefficients[1] == pytest.approx(3.0)
    assert curve.r2 == pytest.approx(1.0)
    assert curve.r == pytest.approx(1.0)
    assert "y = 2x + 3" in curve.equation


def test_linear_through_zero_has_no_intercept():
    curve = cal.fit(points(LEVELS, [2 * c + 3 for c in LEVELS]),
                    cal.LINEAR_THROUGH_ZERO)
    assert len(curve.coefficients) == 1
    assert curve.equation.startswith("y = ")
    assert "+" not in curve.equation


def test_quadratic_recovers_its_coefficients():
    responses = [0.01 * c * c + 2 * c + 1 for c in LEVELS]
    curve = cal.fit(points(LEVELS, responses), cal.QUADRATIC)
    assert curve.coefficients[0] == pytest.approx(0.01, rel=1e-6)
    assert curve.coefficients[1] == pytest.approx(2.0, rel=1e-6)
    assert curve.r2 == pytest.approx(1.0)


def test_mean_response_factor():
    curve = cal.fit(points([1.0, 10.0], [2.0, 30.0]), cal.MEAN_RESPONSE_FACTOR)
    # response factors are 2 and 3, so the mean is 2.5
    assert curve.coefficients[0] == pytest.approx(2.5)


def test_negative_slope_gives_a_negative_r():
    curve = cal.fit(points(LEVELS, [-2 * c for c in LEVELS]))
    assert curve.r < 0
    assert curve.r2 == pytest.approx(1.0)


# --- reading back ---------------------------------------------------------------- #
def test_concentration_round_trip_linear():
    curve = cal.fit(points(LEVELS, [2 * c + 3 for c in LEVELS]))
    assert curve.concentration_at(curve.response_at(42.0)) == pytest.approx(42.0)


def test_concentration_round_trip_quadratic():
    responses = [0.01 * c * c + 2 * c + 1 for c in LEVELS]
    curve = cal.fit(points(LEVELS, responses), cal.QUADRATIC)
    assert curve.concentration_at(curve.response_at(42.0)) == pytest.approx(42.0, rel=1e-6)


def test_quadratic_picks_the_root_inside_the_range():
    """The other root of a curving calibration is far outside it and negative."""
    responses = [0.01 * c * c + 2 * c for c in LEVELS]
    curve = cal.fit(points(LEVELS, responses), cal.QUADRATIC)
    value = curve.concentration_at(curve.response_at(10.0))
    assert value == pytest.approx(10.0, rel=1e-6)
    assert value > 0


def test_concentration_is_none_for_an_unfitted_curve():
    curve = cal.fit(points([1.0], [2.0]))          # one point, linear
    assert not curve.is_fitted
    assert curve.concentration_at(5.0) is None
    assert "at least 2" in curve.note


def test_flat_curve_cannot_be_inverted():
    curve = cal.Calibration("x", coefficients=[0.0, 5.0])
    assert curve.concentration_at(5.0) is None


# --- weighting -------------------------------------------------------------------- #
def test_weighting_pulls_the_fit_towards_the_low_end():
    """A high standard biased upwards drags an unweighted fit off the bottom."""
    responses = [2 * c for c in LEVELS]
    responses[-1] *= 1.30                       # the top level reads 30% high
    unweighted = cal.fit(points(LEVELS, responses))
    weighted = cal.fit(points(LEVELS, responses), weighting=cal.WEIGHT_INVERSE_X2)
    low = 1.0
    assert abs(weighted.concentration_at(2 * low) - low) < \
           abs(unweighted.concentration_at(2 * low) - low)


def test_weights_ignore_a_zero_concentration():
    x = np.array([0.0, 1.0, 10.0])
    w = cal.weights_for(x, x, cal.WEIGHT_INVERSE_X)
    assert w[0] == 0.0 and np.all(np.isfinite(w))


def test_unweighted_is_all_ones():
    x = np.array([1.0, 2.0])
    assert np.all(cal.weights_for(x, x, cal.WEIGHT_NONE) == 1.0)


# --- accuracy and outliers --------------------------------------------------------- #
def test_accuracy_is_filled_for_every_point():
    curve = cal.fit(points(LEVELS, [2 * c for c in LEVELS]))
    assert all(p.accuracy == pytest.approx(100.0) for p in curve.points)


def test_outlier_removal_drops_the_bad_level_when_weighted():
    responses = [2 * c for c in LEVELS]
    responses[2] *= 2.0                          # 10 ng/mL reads double
    curve = cal.fit(points(LEVELS, responses), weighting=cal.WEIGHT_INVERSE_X2)
    cleaned = cal.remove_outliers(curve, tolerance=15.0)
    assert [p.sample_name for p in cleaned.points if not p.used] == ["STD3"]
    assert cleaned.r2 > curve.r2


def test_removal_picks_the_real_offender_not_the_worst_accuracy():
    """
    The lowest standard reads worst when a distorted fit shifts the intercept,
    even though the real offender is elsewhere. Removal is chosen by how much
    the fit improves, so the doubled level goes and the bottom one stays.
    """
    responses = [2 * c for c in LEVELS]
    responses[2] *= 2.0
    curve = cal.fit(points(LEVELS, responses))
    worst = min(curve.points, key=lambda p: p.accuracy)
    assert worst.sample_name == "STD1"          # by accuracy alone

    cleaned = cal.remove_outliers(curve, 15.0)
    assert [p.sample_name for p in cleaned.points if not p.used] == ["STD3"]
    assert cleaned.r2 > curve.r2


def test_removal_never_makes_the_fit_worse():
    """Four scattered points where no single removal helps much."""
    curve = cal.fit(points([2.0, 10.0, 25.0, 50.0], [4.0, 20.0, 150.0, 100.0]))
    cleaned = cal.remove_outliers(curve, 15.0)
    assert cleaned.r2 >= curve.r2


def test_outlier_removal_stops_at_the_floor():
    curve = cal.fit(points([1.0, 2.0, 3.0], [1.0, 9.0, 2.0]))
    cleaned = cal.remove_outliers(curve, tolerance=1.0)
    assert len(cleaned.used_points) >= 3          # never below the floor


def test_outlier_removal_leaves_a_good_curve_alone():
    curve = cal.fit(points(LEVELS, [2 * c for c in LEVELS]))
    cleaned = cal.remove_outliers(curve, tolerance=15.0)
    assert all(p.used for p in cleaned.points)


def test_excluding_a_point_changes_the_fit():
    responses = [2 * c for c in LEVELS]
    responses[-1] *= 2
    everything = cal.fit(points(LEVELS, responses))
    subset = points(LEVELS, responses)
    subset[-1].used = False
    without = cal.fit(subset)
    assert without.r2 > everything.r2
    assert without.coefficients[0] == pytest.approx(2.0)


# --- persistence --------------------------------------------------------------------- #
def test_curve_round_trip():
    curve = cal.fit(points(LEVELS, [2 * c + 1 for c in LEVELS]),
                    cal.QUADRATIC, cal.WEIGHT_INVERSE_X, component="Oxy")
    back = cal.Calibration.from_dict(curve.to_dict())
    assert back.component == "Oxy"
    assert back.regression == cal.QUADRATIC
    assert back.weighting == cal.WEIGHT_INVERSE_X
    assert back.coefficients == pytest.approx(curve.coefficients)
    assert [p.sample_name for p in back.points] == [p.sample_name for p in curve.points]


def test_identical_concentrations_are_refused():
    curve = cal.fit(points([5.0, 5.0, 5.0], [10.0, 11.0, 9.0]))
    assert not curve.is_fitted
    assert "same concentration" in curve.note
