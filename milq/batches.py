"""
Two batches of the same method, side by side.

The day a schedule from `schedule.py` is run, the question is whether it
helped, and the answer is a comparison of the new batch against the old:
per component, how many rows were found, how many points sat on the peak,
how well the standards repeated, and where the peaks moved to. The same
shape as `compare.py`, which puts three algorithms side by side on one
batch; this puts two batches side by side on one method.

The reference is read from its project file without opening a raw file:
everything compared here is in the results the project saved, and a
reference whose acquisitions have moved to another disk is still a
reference.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field

import numpy as np

from .calibration import Calibration
from .compare import _precision, _replicate_set
from .method import ProcessingMethod
from .quantify import ResultsSet
from .samples import SampleEntry

#: a component whose median area moved by more than this between batches
#: is called out; the same figure the algorithm comparison uses
MOVED_PERCENT = 20.0


@dataclass
class BatchSnapshot:
    """What a comparison needs of a batch: no raw files."""

    name: str
    method: ProcessingMethod
    entries: list[SampleEntry]
    results: ResultsSet
    calibrations: dict[str, Calibration] = field(default_factory=dict)

    @property
    def injections(self) -> int:
        return len(self.entries)


def read_project(path: str | os.PathLike) -> BatchSnapshot:
    """A snapshot from a project file, opening nothing else."""
    path = str(path)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return BatchSnapshot(
        name=os.path.splitext(os.path.basename(path))[0],
        method=ProcessingMethod.from_dict(data.get("method", {})),
        entries=[SampleEntry.from_dict(row) for row in data.get("samples", [])],
        results=ResultsSet.from_list(data.get("results", [])),
        calibrations={name: Calibration.from_dict(row)
                      for name, row in (data.get("calibrations") or {}).items()},
    )


def snapshot(session, name: str | None = None) -> BatchSnapshot:
    """The open session as a snapshot."""
    if name is None:
        name = (os.path.splitext(os.path.basename(session.project_path))[0]
                if session.project_path else "current batch")
    return BatchSnapshot(name, session.method, list(session.entries),
                         session.results, dict(session.calibrations))


@dataclass(frozen=True)
class Side:
    """One component in one batch."""

    rows: int
    found: int
    median_area: float | None = None
    median_points: float | None = None
    median_rt: float | None = None
    precision: float | None = None
    replicates: int = 0

    @property
    def found_share(self) -> float | None:
        return self.found / self.rows if self.rows else None


@dataclass(frozen=True)
class ComponentDelta:
    component: str
    is_internal_standard: bool
    reference: Side
    current: Side

    @property
    def area_change(self) -> float | None:
        """Per cent change of the median area, current against reference."""
        if not self.reference.median_area or self.current.median_area is None:
            return None
        return (self.current.median_area - self.reference.median_area) \
            / self.reference.median_area * 100.0

    @property
    def moved(self) -> bool:
        change = self.area_change
        return change is not None and abs(change) > MOVED_PERCENT

    @property
    def rt_shift(self) -> float | None:
        if self.reference.median_rt is None or self.current.median_rt is None:
            return None
        return self.current.median_rt - self.reference.median_rt

    @property
    def points_change(self) -> float | None:
        if self.reference.median_points is None or self.current.median_points is None:
            return None
        return self.current.median_points - self.reference.median_points

    @property
    def precision_change(self) -> float | None:
        """Change in %CV; negative is better."""
        if self.reference.precision is None or self.current.precision is None:
            return None
        return self.current.precision - self.reference.precision


@dataclass
class BatchComparison:
    reference: str
    current: str
    reference_injections: int
    current_injections: int
    rows: list[ComponentDelta] = field(default_factory=list)
    #: components in one batch's method and not the other's
    only_reference: list[str] = field(default_factory=list)
    only_current: list[str] = field(default_factory=list)

    def _totals(self, pick) -> dict:
        sides = [pick(row) for row in self.rows]
        points = [s.median_points for s in sides if s.median_points is not None]
        precisions = [s.precision for s in sides if s.precision is not None]
        return {
            "rows": sum(s.rows for s in sides),
            "found": sum(s.found for s in sides),
            "components_found": sum(1 for s in sides if s.found),
            "median_points": float(np.median(points)) if points else None,
            "median_precision": float(np.median(precisions)) if precisions else None,
            "precise_components": len(precisions),
        }

    def totals(self) -> tuple[dict, dict]:
        return (self._totals(lambda r: r.reference),
                self._totals(lambda r: r.current))

    @property
    def moved(self) -> list[ComponentDelta]:
        return [row for row in self.rows if row.moved]

    def summary(self) -> str:
        ref, cur = self.totals()

        def points(side):
            return "—" if side["median_points"] is None else f"{side['median_points']:.0f}"

        def precision(side):
            return ("—" if side["median_precision"] is None
                    else f"{side['median_precision']:.1f}% over "
                         f"{side['precise_components']}")

        parts = [f"{self.reference} ({self.reference_injections} injections) "
                 f"against {self.current} ({self.current_injections}); "
                 f"{len(self.rows)} component(s) in both methods"]
        if self.only_reference or self.only_current:
            parts.append(f"{len(self.only_reference)} only in the reference, "
                         f"{len(self.only_current)} only in the current")
        parts.append(f"rows found {ref['found']:,} of {ref['rows']:,} against "
                     f"{cur['found']:,} of {cur['rows']:,}")
        parts.append(f"median points on the peak {points(ref)} against {points(cur)}")
        parts.append(f"median %CV of the replicates {precision(ref)} against "
                     f"{precision(cur)}")
        if self.moved:
            parts.append(f"{len(self.moved)} component(s) moved by more than "
                         f"{MOVED_PERCENT:.0f}% in median area")
        return "; ".join(parts) + "."


def _side(batch: BatchSnapshot, component, index: "_Index") -> Side:
    rows = index.rows_of.get(component.name, [])
    found = [r for r in rows if r.found]
    points = [float(r.points) for r in found if r.points is not None]
    precision, replicates = _precision(index.by_key, component,
                                       _replicate_set(component, batch.entries))
    return Side(
        rows=len(rows), found=len(found),
        median_area=float(np.median([r.area for r in found])) if found else None,
        median_points=float(np.median(points)) if points else None,
        median_rt=float(np.median([r.rt for r in found])) if found else None,
        precision=precision, replicates=replicates,
    )


@dataclass(frozen=True)
class _Index:
    """
    One batch's rows, looked up by component and by (sample, component).

    Both sides are asked about every shared component, and `_precision` about
    every replicate of each; done against the list itself that is a walk of
    every row per component per batch. Built once here instead.
    """

    rows_of: dict
    by_key: dict

    @classmethod
    def of(cls, batch: BatchSnapshot) -> "_Index":
        return cls(batch.results.by_component(), batch.results.by_key())


def compare_batches(current: BatchSnapshot, reference: BatchSnapshot) -> BatchComparison:
    """
    Every component the two methods share, measured in each batch.

    Components are matched by name. The reference's own method decides what
    an internal standard is on its side and the current's on its own, so a
    standard added since is compared as an analyte on the reference and
    noted as only in the current.
    """
    comparison = BatchComparison(
        reference=reference.name, current=current.name,
        reference_injections=reference.injections,
        current_injections=current.injections)
    ref_by_name = {c.name: c for c in reference.method.components if c.is_valid}
    cur_by_name = {c.name: c for c in current.method.components if c.is_valid}
    ref_index, cur_index = _Index.of(reference), _Index.of(current)
    for name, component in cur_by_name.items():
        other = ref_by_name.get(name)
        if other is None:
            comparison.only_current.append(name)
            continue
        comparison.rows.append(ComponentDelta(
            component=name,
            is_internal_standard=component.is_internal_standard,
            reference=_side(reference, other, ref_index),
            current=_side(current, component, cur_index)))
    comparison.only_reference = [name for name in ref_by_name if name not in cur_by_name]
    return comparison


CSV_HEADER = ["Component", "Internal standard",
              "Found (reference)", "Rows (reference)", "Found (current)",
              "Rows (current)", "Median area (reference)", "Median area (current)",
              "Area change %", "Points (reference)", "Points (current)",
              "%CV (reference)", "%CV (current)", "RT (reference)", "RT (current)",
              "RT shift"]


def write_csv(comparison: BatchComparison, path: str | os.PathLike) -> str:
    def cell(value, decimals=1):
        return "" if value is None else f"{value:.{decimals}f}"

    path = str(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for row in comparison.rows:
            r, c = row.reference, row.current
            writer.writerow([
                row.component, "yes" if row.is_internal_standard else "",
                r.found, r.rows, c.found, c.rows,
                cell(r.median_area, 0), cell(c.median_area, 0),
                cell(row.area_change), cell(r.median_points, 0),
                cell(c.median_points, 0), cell(r.precision), cell(c.precision),
                cell(r.median_rt, 3), cell(c.median_rt, 3), cell(row.rt_shift, 3)])
    return path
