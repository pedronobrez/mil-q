"""
Calibration curves: fitting a response against known concentrations and
reading unknowns back off the fit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

LINEAR = "linear"
LINEAR_THROUGH_ZERO = "linear through zero"
QUADRATIC = "quadratic"
MEAN_RESPONSE_FACTOR = "mean response factor"
REGRESSIONS = (LINEAR, LINEAR_THROUGH_ZERO, QUADRATIC, MEAN_RESPONSE_FACTOR)

WEIGHT_NONE = "1"
WEIGHT_INVERSE_X = "1/x"
WEIGHT_INVERSE_X2 = "1/x²"
WEIGHT_INVERSE_Y = "1/y"
WEIGHT_INVERSE_Y2 = "1/y²"
WEIGHTINGS = (WEIGHT_NONE, WEIGHT_INVERSE_X, WEIGHT_INVERSE_X2,
              WEIGHT_INVERSE_Y, WEIGHT_INVERSE_Y2)

#: smallest number of standards each regression can be fitted from
MINIMUM_POINTS = {
    LINEAR: 2,
    LINEAR_THROUGH_ZERO: 1,
    QUADRATIC: 3,
    MEAN_RESPONSE_FACTOR: 1,
}


class CalibrationError(ValueError):
    """Raised when a curve cannot be fitted from the points given."""


@dataclass
class CalibrationPoint:
    """One standard injection on the curve."""

    sample_key: str
    sample_name: str
    concentration: float
    response: float
    used: bool = True
    calculated: float | None = None
    accuracy: float | None = None

    def to_dict(self) -> dict:
        return {"sample_key": self.sample_key, "sample_name": self.sample_name,
                "concentration": self.concentration, "response": self.response,
                "used": self.used}


def weights_for(x: np.ndarray, y: np.ndarray, weighting: str) -> np.ndarray:
    """
    Regression weights.

    Calibration ranges usually span decades, and unweighted least squares then
    lets the top standard dominate the fit while the bottom of the range —
    where the accuracy actually matters — drifts. 1/x and 1/x² are the usual
    corrections.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        if weighting == WEIGHT_INVERSE_X:
            w = 1.0 / np.abs(x)
        elif weighting == WEIGHT_INVERSE_X2:
            w = 1.0 / (x.astype(float) ** 2)
        elif weighting == WEIGHT_INVERSE_Y:
            w = 1.0 / np.abs(y)
        elif weighting == WEIGHT_INVERSE_Y2:
            w = 1.0 / (y.astype(float) ** 2)
        else:
            return np.ones_like(x, dtype=float)
    w = np.asarray(w, dtype=float)
    w[~np.isfinite(w)] = 0.0
    return w


@dataclass
class Calibration:
    """A fitted curve for one component."""

    component: str
    regression: str = LINEAR
    weighting: str = WEIGHT_NONE
    #: polynomial coefficients, highest order first
    coefficients: list[float] = field(default_factory=list)
    r2: float = 0.0
    r: float = 0.0
    points: list[CalibrationPoint] = field(default_factory=list)
    note: str = ""

    @property
    def used_points(self) -> list[CalibrationPoint]:
        return [p for p in self.points if p.used]

    @property
    def is_fitted(self) -> bool:
        return bool(self.coefficients)

    @property
    def equation(self) -> str:
        if not self.coefficients:
            return "—"
        c = self.coefficients
        if len(c) == 3:
            return f"y = {c[0]:.6g}x² + {c[1]:.6g}x + {c[2]:.6g}"
        if len(c) == 2:
            return f"y = {c[0]:.6g}x + {c[1]:.6g}"
        return f"y = {c[0]:.6g}x"

    def response_at(self, concentration: float) -> float:
        return float(np.polyval(self.coefficients, concentration))

    def concentration_at(self, response: float) -> float | None:
        """
        Read a concentration back off the curve.

        A quadratic has two roots; the one inside the calibrated range is the
        answer, and a response that lands outside the curve entirely gives
        None rather than an extrapolated guess.
        """
        if not self.coefficients or response is None:
            return None
        c = list(self.coefficients)
        if len(c) == 1:                      # y = ax
            return None if c[0] == 0 else float(response / c[0])
        if len(c) == 2:                      # y = ax + b
            return None if c[0] == 0 else float((response - c[1]) / c[0])
        a, b, offset = c                     # y = ax² + bx + c
        if a == 0:
            return None if b == 0 else float((response - offset) / b)
        discriminant = b * b - 4 * a * (offset - response)
        if discriminant < 0:
            return None
        root = np.sqrt(discriminant)
        candidates = [(-b + root) / (2 * a), (-b - root) / (2 * a)]
        concentrations = [p.concentration for p in self.used_points] or [0.0]
        lo, hi = min(concentrations), max(concentrations)
        inside = [v for v in candidates if lo - abs(lo) - 1e-9 <= v <= hi * 2]
        pool = inside or candidates
        return float(min(pool, key=lambda v: abs(v - (lo + hi) / 2)))

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "regression": self.regression,
            "weighting": self.weighting,
            "coefficients": list(self.coefficients),
            "r2": self.r2,
            "r": self.r,
            "note": self.note,
            "points": [p.to_dict() for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Calibration":
        points = [CalibrationPoint(**row) for row in data.get("points", [])]
        return cls(
            component=data.get("component", ""),
            regression=data.get("regression", LINEAR),
            weighting=data.get("weighting", WEIGHT_NONE),
            coefficients=list(data.get("coefficients", [])),
            r2=float(data.get("r2", 0.0)),
            r=float(data.get("r", 0.0)),
            points=points,
            note=data.get("note", ""),
        )


def fit(points: list[CalibrationPoint], regression: str = LINEAR,
        weighting: str = WEIGHT_NONE, component: str = "") -> Calibration:
    """Fit a curve through the standards that are still in use."""
    curve = Calibration(component=component, regression=regression,
                        weighting=weighting, points=list(points))
    used = curve.used_points
    minimum = MINIMUM_POINTS.get(regression, 2)
    if len(used) < minimum:
        curve.note = f"needs at least {minimum} standard(s)"
        return curve

    x = np.array([p.concentration for p in used], dtype=float)
    y = np.array([p.response for p in used], dtype=float)
    if np.allclose(x, x[0]):
        curve.note = "every standard has the same concentration"
        return curve

    w = weights_for(x, y, weighting)
    if not np.any(w > 0):
        curve.note = "weighting leaves no usable point"
        return curve

    if regression == MEAN_RESPONSE_FACTOR:
        valid = x != 0
        if not np.any(valid):
            curve.note = "mean response factor needs a non-zero standard"
            return curve
        factors = y[valid] / x[valid]
        weights = w[valid]
        slope = float(np.average(factors, weights=weights)
                      if np.any(weights > 0) else np.mean(factors))
        curve.coefficients = [slope]
    elif regression == LINEAR_THROUGH_ZERO:
        denominator = float(np.sum(w * x * x))
        if denominator == 0:
            curve.note = "cannot fit through zero"
            return curve
        curve.coefficients = [float(np.sum(w * x * y) / denominator)]
    else:
        degree = 2 if regression == QUADRATIC else 1
        # numpy applies the weights to the residuals, so they enter as roots
        coefficients = np.polyfit(x, y, degree, w=np.sqrt(w))
        curve.coefficients = [float(v) for v in coefficients]

    predicted = np.polyval(curve.coefficients, x)
    residual = float(np.sum(w * (y - predicted) ** 2))
    mean = float(np.average(y, weights=w)) if np.any(w > 0) else float(np.mean(y))
    total = float(np.sum(w * (y - mean) ** 2))
    curve.r2 = float(1.0 - residual / total) if total > 0 else 0.0
    sign = 1.0 if curve.coefficients[0] >= 0 else -1.0
    curve.r = sign * float(np.sqrt(max(curve.r2, 0.0)))

    for point in curve.points:
        point.calculated = curve.concentration_at(point.response)
        point.accuracy = (
            point.calculated / point.concentration * 100.0
            if point.calculated is not None and point.concentration else None
        )
    return curve


def remove_outliers(curve: Calibration, tolerance: float = 15.0,
                    minimum_points: int | None = None) -> Calibration:
    """
    Drop standards that fall outside the accuracy tolerance.

    One point at a time, refitting in between, because a single bad level
    distorts the fit enough to make its neighbours look wrong too.

    The point dropped is the one whose removal most improves the fit, not
    simply the one with the worst accuracy. Those are not the same: a distorted
    fit throws off the intercept, and the lowest standard — where a small
    absolute error is a large relative one — then reads worst even though the
    real offender is elsewhere. Removal stops as soon as no candidate improves
    the fit, so a bad point is never traded for a worse one.
    """
    floor = minimum_points or max(MINIMUM_POINTS.get(curve.regression, 2), 3)
    working = fit(curve.points, curve.regression, curve.weighting, curve.component)
    while True:
        used = working.used_points
        if len(used) <= floor or not working.is_fitted:
            return working
        offenders = [
            p for p in used
            if p.accuracy is not None and abs(p.accuracy - 100.0) > tolerance
        ]
        if not offenders:
            return working

        best: Calibration | None = None
        best_point: CalibrationPoint | None = None
        for candidate in offenders:
            trial_points = [
                CalibrationPoint(p.sample_key, p.sample_name, p.concentration,
                                 p.response, p.used and p is not candidate)
                for p in working.points
            ]
            trial = fit(trial_points, working.regression, working.weighting,
                        working.component)
            if trial.is_fitted and (best is None or trial.r2 > best.r2):
                best, best_point = trial, candidate
        if best is None or best.r2 <= working.r2 or best_point is None:
            return working
        for point in working.points:
            if point.sample_key == best_point.sample_key:
                point.used = False
        working = fit(working.points, working.regression, working.weighting,
                      working.component)
