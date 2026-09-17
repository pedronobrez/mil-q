"""
What a batch's numbers owe to the algorithm that integrated them.

A peak area is a measurement and a decision: where the peak begins and ends,
and what is done with the points in between. Two attempts at reproducing the
vendor's own boundary rule are in this project's history and both were
wrong, and a single change to where the detector may look made 894 rows of a
real batch appear from nothing. If the number moves that much with a
processing decision, the size of that movement is part of the result.

This runs the same batch through every algorithm and puts the answers side
by side, per component: how many rows each one found, how far the areas
sit from the reference, and how well each repeated itself on the things that
were meant to repeat — the internal standards, spiked into every vial at one
amount, and the quality controls. That last figure is the one that can say
an algorithm is better rather than merely different: same files, same noise,
same instrument, only the arithmetic changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .calibration import Calibration
from .method import ProcessingMethod
from .processing import ALGORITHM_LABELS, ALGORITHMS
from .quantify import (ResultsSet, XicCache, apply_calibrations,
                       build_calibrations, process)
from .samples import BLANK, QC, STANDARD, UNKNOWN, SampleEntry

#: a component whose median area moves by more than this between algorithms
#: is one whose number depends on the decision as much as on the sample
SENSITIVE_PERCENT = 20.0

#: fewer replicates than this and a coefficient of variation is anecdote
MIN_REPLICATES = 3

#: sample types an internal standard is spiked into at the same amount, so
#: its area is meant to repeat across them
SPIKED_TYPES = (UNKNOWN, STANDARD, QC, BLANK)


@dataclass(frozen=True)
class Figures:
    """One algorithm on one component, over the whole batch."""

    algorithm: str
    found: int
    total: int
    #: rows where the algorithm could not run and said so — a Gaussian with
    #: too few points above the baseline leaves the valley area standing
    fallbacks: int = 0
    #: of those, the ones where the peak was too few points wide to fit —
    #: the sampling's doing rather than the algorithm's
    too_sparse: int = 0
    median_area: float | None = None
    #: coefficient of variation over the rows that were meant to agree
    precision: float | None = None
    replicates: int = 0
    #: fit of the calibration curve, when there is one
    r2: float | None = None


@dataclass(frozen=True)
class Delta:
    """One algorithm against the reference, on one component."""

    algorithm: str
    #: rows both algorithms found, which is where an area can be compared
    both: int
    median_percent: float | None = None
    max_percent: float | None = None
    only_reference: int = 0
    only_other: int = 0

    @property
    def sensitive(self) -> bool:
        return (self.median_percent is not None
                and self.median_percent > SENSITIVE_PERCENT)


@dataclass
class ComponentComparison:
    component: str
    is_internal_standard: bool
    figures: dict[str, Figures] = field(default_factory=dict)
    deltas: dict[str, Delta] = field(default_factory=dict)

    @property
    def sensitive(self) -> bool:
        return any(delta.sensitive for delta in self.deltas.values())


@dataclass(frozen=True)
class Totals:
    """One algorithm over the whole method."""

    algorithm: str
    found: int
    rows: int
    components_found: int
    fallbacks: int
    too_sparse: int
    #: how many components moved by more than SENSITIVE_PERCENT against the
    #: reference; zero for the reference itself
    sensitive: int
    #: median of the components' precisions, where measurable
    median_precision: float | None
    precise_components: int


@dataclass
class Comparison:
    """The batch integrated every way, and the differences."""

    reference: str
    algorithms: tuple[str, ...]
    results: dict[str, ResultsSet]
    calibrations: dict[str, dict[str, Calibration]]
    components: list[ComponentComparison]
    rows: int = 0

    @property
    def sensitive(self) -> list[ComponentComparison]:
        return [c for c in self.components if c.sensitive]

    def totals(self, algorithm: str) -> Totals:
        figures = [c.figures[algorithm] for c in self.components
                   if algorithm in c.figures]
        precisions = [f.precision for f in figures if f.precision is not None]
        return Totals(
            algorithm=algorithm,
            found=sum(f.found for f in figures),
            rows=sum(f.total for f in figures),
            components_found=sum(1 for f in figures if f.found),
            fallbacks=sum(f.fallbacks for f in figures),
            too_sparse=sum(f.too_sparse for f in figures),
            sensitive=sum(1 for c in self.components
                          if algorithm in c.deltas and c.deltas[algorithm].sensitive),
            median_precision=(float(np.median(precisions)) if precisions else None),
            precise_components=len(precisions),
        )

    def summary(self) -> str:
        """A paragraph a reader can act on, in plain words."""
        reference = ALGORITHM_LABELS.get(self.reference, self.reference)
        parts = [f"{self.rows:,} rows integrated {len(self.algorithms)} ways; "
                 f"the reference is {reference.lower()}."]
        for algorithm in self.algorithms:
            totals = self.totals(algorithm)
            label = ALGORITHM_LABELS.get(algorithm, algorithm)
            piece = f"{label}: {totals.found:,} rows found"
            if totals.fallbacks:
                piece += f", {totals.fallbacks:,} of them fallen back to the valley area"
                if totals.too_sparse:
                    piece += (f" ({totals.too_sparse:,} because the peak was fewer "
                              f"than three points wide)")
            if totals.median_precision is not None:
                piece += (f"; median %CV {totals.median_precision:.1f} over "
                          f"{totals.precise_components} component(s) with replicates")
            if algorithm != self.reference:
                piece += (f"; {totals.sensitive} component(s) moved by more than "
                          f"{SENSITIVE_PERCENT:.0f}%")
            parts.append(piece + ".")
        return " ".join(parts)


# --------------------------------------------------------------------------- #
def with_algorithm(method: ProcessingMethod, algorithm: str) -> ProcessingMethod:
    """
    A copy of the method with every component on one algorithm.

    The defaults and every per-component override alike: a component that
    carries its own settings would otherwise keep the old algorithm quietly
    and the comparison would not be comparing what it says.
    """
    copy = ProcessingMethod.from_dict(method.to_dict())
    copy.defaults.algorithm = algorithm
    for component in copy.components:
        if component.integration is not None:
            component.integration.algorithm = algorithm
    return copy


def adopt_algorithm(method: ProcessingMethod, algorithm: str) -> int:
    """Set an algorithm on the method in place; returns how many components
    carried an override that was changed with it."""
    method.defaults.algorithm = algorithm
    touched = 0
    for component in method.components:
        if component.integration is not None and \
                component.integration.algorithm != algorithm:
            component.integration.algorithm = algorithm
            touched += 1
    return touched


def _replicate_set(component, entries: list[SampleEntry]) -> list[SampleEntry]:
    """
    The injections a component's area was meant to repeat over.

    An internal standard is spiked into every vial at one amount, so every
    spiked injection is a replicate of it. An analyte only repeats over the
    quality controls — unknowns differ by design and standards by
    construction.
    """
    if component.is_internal_standard:
        return [e for e in entries if e.sample_type in SPIKED_TYPES]
    return [e for e in entries if e.sample_type == QC]


def _precision(by_key: dict, component, replicates: list[SampleEntry]
               ) -> tuple[float | None, int]:
    """
    The %CV of one component over the injections it was meant to repeat on.

    `by_key` is `ResultsSet.by_key()`, built once by the caller: asking the
    set itself walked every row for every replicate of every component of
    every algorithm.
    """
    values = []
    for entry in replicates:
        row = by_key.get((entry.key, component.name))
        if row is not None and row.found:
            values.append(row.area)
    if len(values) < MIN_REPLICATES:
        return None, len(values)
    array = np.array(values, dtype=float)
    mean = float(array.mean())
    if mean == 0:
        return None, len(values)
    return abs(float(array.std(ddof=1)) / mean * 100.0), len(values)


def _figures(algorithm: str, rows: list, by_key: dict,
             curves: dict[str, Calibration],
             component, entries: list[SampleEntry]) -> Figures:
    found = [r for r in rows if r.found]
    # a row the algorithm could not run on is labelled with what did run
    fell = [r for r in found if r.algorithm and r.algorithm != algorithm]
    sparse = sum(1 for r in fell if "above the baseline" in r.note
                 or "narrower than the sampling" in r.note)
    precision, replicates = _precision(by_key, component,
                                       _replicate_set(component, entries))
    curve = curves.get(component.name)
    return Figures(
        algorithm=algorithm, found=len(found), total=len(rows),
        fallbacks=len(fell), too_sparse=sparse,
        median_area=(float(np.median([r.area for r in found])) if found else None),
        precision=precision, replicates=replicates,
        r2=(curve.r2 if curve is not None and curve.is_fitted else None),
    )


def _delta(algorithm: str, reference_rows: list, other_by_key: dict,
           component) -> Delta:
    """
    How far one algorithm's areas sit from the reference's, per component.

    Both sides arrive indexed. Looking the counterpart up with
    `ResultsSet.get` walked the whole result list for every row — 3,666 rows
    against 3,666, once per component and once per algorithm — which is the
    quadratic `by_key` was written for and which had survived here.
    """
    percents = []
    only_reference = only_other = 0
    for row in reference_rows:
        counterpart = other_by_key.get((row.sample_key, row.component))
        found_other = counterpart is not None and counterpart.found
        if row.found and found_other:
            percents.append(abs(counterpart.area - row.area) / row.area * 100.0)
        elif row.found:
            only_reference += 1
        elif found_other:
            only_other += 1
    array = np.array(percents, dtype=float)
    return Delta(
        algorithm=algorithm, both=len(percents),
        median_percent=(float(np.median(array)) if percents else None),
        max_percent=(float(array.max()) if percents else None),
        only_reference=only_reference, only_other=only_other,
    )


def compare_algorithms(entries: list[SampleEntry], method: ProcessingMethod,
                       cache: XicCache | None = None,
                       algorithms: tuple[str, ...] = ALGORITHMS,
                       progress=None,
                       corrections: dict | None = None) -> Comparison | None:
    """
    Integrate the batch once per algorithm and compare the answers.

    Every run is automatic — a row the operator integrated by hand is not
    any algorithm's answer — and every run is calibrated on its own results,
    so the r² of each curve is that algorithm's. The reference is the
    algorithm the method's defaults name, which is what the batch is
    currently reported with.

    `progress(done, total)` is called as the rows go by; returning False
    stops the comparison, which then comes back as None rather than as a
    comparison of unequal runs.

    `corrections` is passed to every run alike, so what is compared stays the
    arithmetic and nothing else — the point of the exercise.
    """
    reference = method.defaults.algorithm
    algorithms = tuple(dict.fromkeys((reference, *algorithms)))
    loaded = [e for e in entries if e.is_loaded]
    components = [c for c in method.components if c.is_valid]
    per_run = len(loaded) * len(components)
    total = per_run * len(algorithms)

    results: dict[str, ResultsSet] = {}
    calibrations: dict[str, dict[str, Calibration]] = {}
    for index, algorithm in enumerate(algorithms):
        cancelled = False

        def report(done: int, _total: int, offset=index * per_run) -> bool:
            nonlocal cancelled
            if progress is not None and progress(offset + done, total) is False:
                cancelled = True
                return False
            return True

        run = process(loaded, with_algorithm(method, algorithm), cache,
                      progress=report, corrections=corrections)
        if cancelled:
            return None
        curves = build_calibrations(run, loaded, method)
        apply_calibrations(run, loaded, method, curves)
        results[algorithm] = run
        calibrations[algorithm] = curves

    # indexed once per algorithm, not once per component per algorithm
    rows_of = {a: results[a].by_component() for a in algorithms}
    keyed = {a: results[a].by_key() for a in algorithms}

    compared: list[ComponentComparison] = []
    for component in components:
        item = ComponentComparison(component.name, component.is_internal_standard)
        for algorithm in algorithms:
            item.figures[algorithm] = _figures(
                algorithm, rows_of[algorithm].get(component.name, []),
                keyed[algorithm], calibrations[algorithm], component, loaded)
            if algorithm != reference:
                item.deltas[algorithm] = _delta(
                    algorithm, rows_of[reference].get(component.name, []),
                    keyed[algorithm], component)
        compared.append(item)
    return Comparison(reference=reference, algorithms=algorithms,
                      results=results, calibrations=calibrations,
                      components=compared, rows=per_run)
