"""
Whether the mass axis moved during the run.

The survey scan is already read to measure each precursor's accurate mass
(`precursor.measure`). Done once per injection instead of once per batch,
the same measurement answers a different question: did the instrument's
calibration hold from the first injection to the last? A component whose
measured mass walks one way across the run is a mass axis drifting, and a
batch where every standard walks together is the instrument rather than any
compound — the same separation the quality charts make for response.

The reference is the batch's own median, not the written precursor: a
method value typed to two decimals is good to ±14 ppm at m/z 350 and says
nothing about drift, while the change across the run is measured against
itself to well under a ppm. Where a component carries a formula and an
adduct the exact mass is known too, and the median's error against it is
reported alongside — an offset, which is a different finding from a drift.

Measured, not corrected. What to do about it is `recalibrate.py`, which
reuses exactly these measurements: a trend that fails `same_ion` is not a
lock mass, and a trend with no formula has nothing to be corrected towards.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .components import Component
from .method import ProcessingMethod
from .precursor import CONSENSUS_SPREAD_PPM, PrecursorMeasurement, measure
from .qc import (DRIFT_CORRELATION, MIN_INJECTIONS, SPIKED_TYPES, _stamp,
                 spearman)
from .samples import SampleEntry
from .validation import acquisition_order

#: a fitted change across the run, in ppm, beyond which the axis drifted
#: rather than wandered. A TripleTOF holds a few ppm on a strong ion; ten
#: across a run is a calibration that has moved.
DRIFT_PPM = 10.0

#: what the per-injection median over the standards is charted under
MASS_INDEX = "instrument mass index"

#: the fewest standards worth taking a median across per injection
MIN_INDEX_STANDARDS = 3


@dataclass(frozen=True)
class MassPoint:
    """One injection's measurement of one component's mass."""

    order: int
    sample: str
    when: str
    #: the measured m/z, or the ppm itself for the index
    mz: float
    #: parts per million from the component's median over the run
    ppm: float
    intensity: float = 0.0
    corroborated: bool = True
    #: the sample's key, which is unique where its name need not be. Empty on
    #: the index, whose points are a median over components rather than one
    #: injection's measurement of one of them.
    key: str = ""


@dataclass
class MassTrend:
    """One component's measured mass through the run, in the order it was run."""

    component: str
    nominal: float = 0.0
    #: the exact m/z from formula and adduct, when the component carries them
    exact: float | None = None
    points: list[MassPoint] = field(default_factory=list)
    median: float | None = None
    #: the fitted change across the whole run, in ppm
    change: float | None = None
    correlation: float | None = None
    #: measurements the product-ion scan did not confirm
    unconfirmed: int = 0
    note: str = ""

    @property
    def same_ion(self) -> bool:
        """
        Whether the injections measured the same ion at all.

        Measured on a real batch: the internal standards whose survey signal
        was weak came back with spreads of 100 to 500 ppm between injections
        and one of them with a fitted "drift" of −351 ppm. That is not a
        mass axis moving; it is the search window catching whatever sat
        nearest in each injection. The limit is the one the precursor
        consensus already uses to say the samples disagree.
        """
        spread = self.spread_ppm
        return spread is None or spread <= CONSENSUS_SPREAD_PPM

    @property
    def measurable(self) -> bool:
        return (self.median is not None and len(self.points) >= MIN_INJECTIONS
                and self.same_ion)

    @property
    def error_ppm(self) -> float | None:
        """The median against the exact mass: an offset, not a drift."""
        if self.median is None or not self.exact:
            return None
        return (self.median - self.exact) / self.exact * 1e6

    @property
    def spread_ppm(self) -> float | None:
        if len(self.points) < 2:
            return None
        values = [point.ppm for point in self.points]
        return max(values) - min(values)

    @property
    def drifted(self) -> bool:
        """
        Whether the axis went one way, far enough to matter.

        Both conditions, as for a response: a large fitted change through
        scatter is a line fitted to noise, and a strong correlation over two
        ppm is a trend nobody recalibrates for.
        """
        return (self.measurable
                and self.change is not None and self.correlation is not None
                and abs(self.change) >= DRIFT_PPM
                and abs(self.correlation) >= DRIFT_CORRELATION)


@dataclass
class MassDrift:
    """The batch's mass axis, component by component and all together."""

    trends: list[MassTrend] = field(default_factory=list)
    index: MassTrend | None = None
    injections: int = 0
    timed: int = 0
    note: str = ""

    @property
    def ordered(self) -> bool:
        return self.injections > 0 and self.timed == self.injections

    @property
    def drifted(self) -> list[MassTrend]:
        return [trend for trend in self.trends if trend.drifted]

    @property
    def measured(self) -> list[MassTrend]:
        return [trend for trend in self.trends if trend.measurable]


def _fit(points: list[MassPoint]) -> tuple[float | None, float | None]:
    """The fitted change across the run and how monotonic it was."""
    if len(points) < MIN_INJECTIONS:
        return None, None
    order = np.array([point.order for point in points], dtype=float)
    values = np.array([point.ppm for point in points], dtype=float)
    if np.ptp(values) == 0:
        return 0.0, None
    slope = float(np.polyfit(order, values, 1)[0])
    return slope * (order.max() - order.min()), spearman(order, values)


def mass_trend(component: Component,
               measurements: list[tuple[SampleEntry, PrecursorMeasurement]]
               ) -> MassTrend:
    """
    One component's trend from its per-injection measurements, in run order.

    Points come from every injection where the survey found the ion; the
    ones the product-ion scan did not confirm are counted and kept, since a
    drift is a drift whether or not the confirming scan was strong enough.
    """
    trend = MassTrend(component=component.name, nominal=component.precursor,
                      exact=component.precursor_from_formula())
    found = [(entry, m) for entry, m in measurements if m.found]
    if not found:
        notes = {m.note for _, m in measurements if m.note}
        trend.note = sorted(notes)[0] if notes else "not measured"
        return trend
    masses = np.array([m.measured for _, m in found], dtype=float)
    trend.median = float(np.median(masses))
    for order, (entry, m) in enumerate(found, start=1):
        trend.points.append(MassPoint(
            order=order, sample=entry.name, when=_stamp(entry),
            mz=float(m.measured),
            ppm=(float(m.measured) - trend.median) / trend.median * 1e6,
            intensity=m.intensity,
            corroborated=m.product_mz is None or m.corroborated,
            key=entry.key))
    trend.unconfirmed = sum(1 for point in trend.points if not point.corroborated)
    if len(found) < MIN_INJECTIONS:
        trend.note = (f"measured in {len(found)} injection(s); "
                      f"{MIN_INJECTIONS} are needed to see a trend")
        return trend
    if not trend.same_ion:
        trend.note = (f"spread {trend.spread_ppm:,.0f} ppm between injections: "
                      f"not the same ion twice — a survey signal too weak, or "
                      f"an interference in the window")
        return trend
    trend.change, trend.correlation = _fit(trend.points)
    return trend


def mass_index(trends: list[MassTrend], ordered: list[SampleEntry]) -> MassTrend | None:
    """
    Every measured component taken together: per injection, the median of
    their deviations from their own medians.

    One component walking is a compound; every component walking together
    is the axis. Needs at least MIN_INDEX_STANDARDS components with a
    measurement in an injection for that injection to count.
    """
    usable = [trend for trend in trends if trend.median is not None and trend.same_ion]
    if len(usable) < MIN_INDEX_STANDARDS:
        return None
    by_sample: dict[str, list[float]] = {}
    for trend in usable:
        for point in trend.points:
            by_sample.setdefault(point.sample, []).append(point.ppm)
    index = MassTrend(component=MASS_INDEX, median=0.0)
    order = 0
    for entry in ordered:
        values = by_sample.get(entry.name, [])
        if len(values) < MIN_INDEX_STANDARDS:
            continue
        order += 1
        ppm = float(np.median(values))
        index.points.append(MassPoint(order=order, sample=entry.name,
                                      when=_stamp(entry), mz=ppm, ppm=ppm))
    if len(index.points) < MIN_INJECTIONS:
        index.note = (f"{len(index.points)} injection(s) with "
                      f"{MIN_INDEX_STANDARDS} or more components measured; "
                      f"{MIN_INJECTIONS} are needed")
        return index
    index.change, index.correlation = _fit(index.points)
    index.note = (f"the median over {len(usable)} components of each one's "
                  f"deviation from its own median")
    return index


def mass_drift(entries: list[SampleEntry], method: ProcessingMethod,
               components: list[str] | None = None,
               progress=None) -> MassDrift:
    """
    Measure every internal standard's precursor in every spiked injection,
    in the order the instrument ran them, and fit the change.

    Internal standards unless asked for others: they are in every vial at
    one amount, so their ion is there to measure in every injection. Every
    other component is welcome — a strong analyte drifts just as visibly —
    but an unknown that is absent from half the batch measures nothing in
    that half. `progress(done, total)` may return False to stop; the result
    is then None rather than half a batch presented as a whole.
    """
    ordered = [e for e in acquisition_order(entries) if e.is_loaded]
    report = MassDrift(injections=len(ordered),
                       timed=sum(1 for entry in ordered if _stamp(entry)))
    if not ordered:
        report.note = "no samples are open"
        return report
    if components is None:
        wanted = [c for c in method.components if c.is_internal_standard and c.is_valid]
        if not wanted:
            report.note = ("no internal standard is marked in the method, so "
                           "there is nothing that is in every injection to measure")
            return report
    else:
        names = set(components)
        wanted = [c for c in method.components if c.name in names and c.is_valid]

    total = len(wanted) * len(ordered)
    done = 0
    for component in wanted:
        measurements = []
        spiked = component.is_internal_standard
        for entry in ordered:
            if spiked and entry.sample_type not in SPIKED_TYPES:
                done += 1
                continue
            measurements.append((entry, measure(entry, component, method)))
            done += 1
            if progress is not None and progress(done, total) is False:
                return None
        report.trends.append(mass_trend(component, measurements))
    report.index = mass_index(report.trends, ordered)
    return report
