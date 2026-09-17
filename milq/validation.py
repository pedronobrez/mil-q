"""
What a method can measure, and what it drags from one injection to the next.

Two checks that a quantitative method is expected to answer and that this
could not: how low it can go, and whether the highest standard leaves anything
behind in the vial after it.

Neither invents a number where the data does not support one. A limit that
sits below the lowest calibrator has not been demonstrated by that curve, only
extrapolated from it, and says so; a carryover figure with no blank injected
after the top standard is not reported at all rather than computed from
whatever blank happened to be nearest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .calibration import Calibration
from .method import ProcessingMethod
from .quantify import ResultsSet
from .samples import SampleEntry

#: the multipliers of ICH Q2: the smallest signal that can be told from noise,
#: and the smallest that can be measured with acceptable precision
LOD_FACTOR = 3.3
LOQ_FACTOR = 10.0

#: regressions a limit can be derived from. A quadratic has no single slope,
#: and a mean response factor is not a regression at all.
LINEAR = ("linear", "linear through zero")

#: sample types that should contain none of the analyte
BLANK_TYPES = ("Blank", "Double Blank", "Solvent")

#: what regulators ask of a blank after the highest standard: no more than a
#: fifth of the signal at the lowest calibrated concentration
CARRYOVER_LIMIT = 20.0


# --------------------------------------------------------------------------- #
# how low the method goes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DetectionLimits:
    """The limits of detection and quantitation of one curve."""

    component: str
    lod: float | None = None
    loq: float | None = None
    sigma: float = 0.0
    slope: float = 0.0
    lowest_standard: float | None = None
    note: str = ""

    @property
    def measurable(self) -> bool:
        return self.lod is not None and self.loq is not None

    @property
    def extrapolated(self) -> bool:
        """
        Whether the limit sits below anything that was actually calibrated.

        A curve says nothing about concentrations nobody put on it. A limit of
        quantitation under the lowest standard is arithmetic, not evidence,
        and reporting it without saying so is how a method comes to claim a
        sensitivity it has never shown.
        """
        return (self.loq is not None and self.lowest_standard is not None
                and self.loq < self.lowest_standard)


def detection_limits(curve: Calibration,
                     lod_factor: float = LOD_FACTOR,
                     loq_factor: float = LOQ_FACTOR) -> DetectionLimits:
    """
    Limits from the scatter of the curve about its own line.

    ICH Q2 allows the standard deviation to come from blanks, from the
    intercept, or from the residuals; the residuals are used here because they
    are the only one every curve carries with it. Degrees of freedom are the
    points less the parameters fitted, so three points on a two-parameter line
    leave one — enough to compute and not enough to trust, which the note
    says.
    """
    name = curve.component
    if not curve.is_fitted:
        return DetectionLimits(name, note="no curve")
    if curve.regression not in LINEAR:
        return DetectionLimits(
            name, note=f"not derived for a {curve.regression}: it has no single slope")

    points = [p for p in curve.points if p.used]
    if len(points) < 3:
        return DetectionLimits(name, note="fewer than three standards")

    x = np.array([p.concentration for p in points], dtype=float)
    y = np.array([p.response for p in points], dtype=float)
    predicted = np.polyval(curve.coefficients, x)
    parameters = len(curve.coefficients)
    freedom = len(points) - parameters
    if freedom < 1:
        return DetectionLimits(name, note="no degrees of freedom left to measure scatter")

    sigma = float(np.sqrt(np.sum((y - predicted) ** 2) / freedom))
    slope = float(curve.coefficients[0])
    if slope == 0:
        return DetectionLimits(name, sigma=sigma, note="the curve has no slope")

    lowest = float(np.min(x)) if x.size else None
    notes = []
    if freedom < 3:
        notes.append(f"only {freedom} degree(s) of freedom")
    if curve.weighting and curve.weighting != "1":
        notes.append(f"fitted with {curve.weighting} weighting, residuals taken unweighted")
    return DetectionLimits(
        component=name,
        lod=abs(lod_factor * sigma / slope),
        loq=abs(loq_factor * sigma / slope),
        sigma=sigma, slope=slope, lowest_standard=lowest,
        note="; ".join(notes),
    )


def all_detection_limits(calibrations: dict[str, Calibration],
                         method: ProcessingMethod | None = None
                         ) -> list[DetectionLimits]:
    """Every curve's limits, internal standards left out — theirs are flat."""
    internal = ({c.name for c in method.components if c.is_internal_standard}
                if method else set())
    return [detection_limits(curve)
            for name, curve in sorted(calibrations.items())
            if curve is not None and name not in internal]


# --------------------------------------------------------------------------- #
# what the previous injection left behind
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Carryover:
    """Signal found in a blank that should not have contained any."""

    component: str
    blank: str
    follows: str
    blank_area: float
    reference_area: float
    reference: str
    percent: float
    limit: float = CARRYOVER_LIMIT

    @property
    def fails(self) -> bool:
        return self.percent > self.limit


@dataclass
class CarryoverReport:
    rows: list[Carryover] = field(default_factory=list)
    note: str = ""

    @property
    def failures(self) -> list[Carryover]:
        return [row for row in self.rows if row.fails]


def acquisition_order(entries: list[SampleEntry]) -> list[SampleEntry]:
    """
    The injections in the order the instrument ran them.

    The acquisition time is what says so; where a file does not carry one, the
    order the samples were opened in is the only thing left, and it is usually
    the same order.
    """
    def when(entry: SampleEntry):
        stamp = ""
        if entry.is_loaded:
            stamp = str(getattr(entry.sample, "acquisition_time", "") or "")
        return (stamp == "", stamp)

    return sorted(entries, key=when)


def carryover(results: ResultsSet, entries: list[SampleEntry],
              method: ProcessingMethod,
              limit: float = CARRYOVER_LIMIT) -> CarryoverReport:
    """
    Signal in the blank that follows the highest standard.

    The measure regulators ask for is that blank's response against the
    response at the lowest calibrated concentration — not against the standard
    that caused it, which would make a sensitive method look worse the higher
    its top calibrator went.

    A blank somewhere else in the run is not this test and is not reported as
    though it were. Neither is a run with no blank after the top standard: it
    comes back empty with a reason, because a carryover figure that nobody
    measured is worse than none.
    """
    ordered = acquisition_order(entries)
    standards = [e for e in ordered if e.sample_type == "Standard"
                 and e.actual_concentration is not None]
    if not standards:
        return CarryoverReport(note="no standards, so there is nothing to carry over")

    highest = max(standards, key=lambda e: e.actual_concentration)
    lowest = min(standards, key=lambda e: e.actual_concentration)

    position = ordered.index(highest)
    following = next((e for e in ordered[position + 1:]
                      if e.sample_type in BLANK_TYPES), None)
    if following is None:
        return CarryoverReport(
            note=f"no blank was injected after the highest standard "
                 f"({highest.name}); inject one to measure carryover")

    rows: list[Carryover] = []
    internal = {c.name for c in method.components if c.is_internal_standard}
    for component in method.components:
        if component.name in internal:
            continue
        blank_row = results.get(following.key, component.name)
        reference_row = results.get(lowest.key, component.name)
        if blank_row is None or reference_row is None:
            continue
        reference_area = reference_row.area or 0.0
        if reference_area <= 0:
            continue
        blank_area = blank_row.area or 0.0
        rows.append(Carryover(
            component=component.name, blank=following.name, follows=highest.name,
            blank_area=blank_area, reference_area=reference_area,
            reference=lowest.name,
            percent=blank_area / reference_area * 100.0, limit=limit))
    return CarryoverReport(rows=rows)
