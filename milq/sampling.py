"""
How many points the acquisition put on each peak.

Three separate measurements on one batch pointed at the same place: the
retention-time estimates could not be trusted at low heights, no response
floor could be derived, and the choice of integration algorithm moved
nothing — because every transition was sampled once every 14.6 s and the
peaks were four to ten seconds wide. That is a property of the acquisition
schedule, and no processing can substitute for it. This module measures it
per component and says, in numbers, what cycle time the peaks would need.

The count comes from the integration: every peak carries how many of its
points sit at or above one per cent of its height — the points that are the
peak rather than its feet — and the Gaussian fit's own minimum is three of
them. The width at half height is the peak's reported width. The cycle time
is measured from the channel's own time axis rather than read from the
method, because the instrument's scheduling is what matters and the method
does not record it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .matching import match_channel
from .method import ProcessingMethod
from .processing import FWHM_PER_SIGMA, MIN_FIT_POINTS
from .quantify import ResultsSet
from .samples import SampleEntry

#: the textbook figure for quantitation: this many points across the peak's
#: base, taken as four sigma
BASE_POINTS = 10
#: a Gaussian's base, four sigma, in widths at half height
BASE_IN_FWHM = 4.0 / FWHM_PER_SIGMA
#: the fit needs sigma at or above half a cycle to be made at any phase of
#: the scans: cycle <= 2 sigma, which is this many widths at half height
FIT_IN_FWHM = 2.0 / FWHM_PER_SIGMA


@dataclass(frozen=True)
class ComponentSampling:
    component: str
    is_internal_standard: bool
    found: int
    #: the channel's cycle time, in seconds
    cycle: float | None = None
    #: median width at half height of the peaks found, in seconds
    width: float | None = None
    #: median number of points on the peak
    points: float | None = None
    #: rows whose peak had fewer points than a fit needs
    sparse: int = 0
    #: rows whose width could not be measured: one point above half height,
    #: so the peak is narrower than a cycle and its width is only bounded
    unmeasured: int = 0

    @property
    def sparse_share(self) -> float | None:
        return self.sparse / self.found if self.found else None

    @property
    def too_sparse(self) -> bool:
        """Whether the typical peak of this component cannot be fitted."""
        return self.points is not None and self.points < MIN_FIT_POINTS

    @property
    def cycle_for_fit(self) -> float | None:
        """The cycle at which every phase of the scans gives a fit, in seconds."""
        return None if self.width is None else self.width * FIT_IN_FWHM

    @property
    def cycle_for_base(self) -> float | None:
        """The cycle that puts BASE_POINTS across the peak's base, in seconds."""
        return None if self.width is None else self.width * BASE_IN_FWHM / BASE_POINTS


@dataclass
class SamplingReport:
    rows: list[ComponentSampling] = field(default_factory=list)
    note: str = ""

    @property
    def measured(self) -> list[ComponentSampling]:
        return [row for row in self.rows if row.points is not None]

    @property
    def sparse(self) -> list[ComponentSampling]:
        return [row for row in self.measured if row.too_sparse]

    @property
    def median_cycle(self) -> float | None:
        cycles = [row.cycle for row in self.rows if row.cycle is not None]
        return float(np.median(cycles)) if cycles else None

    @property
    def median_width(self) -> float | None:
        widths = [row.width for row in self.measured if row.width is not None]
        return float(np.median(widths)) if widths else None

    @property
    def unmeasured(self) -> int:
        """Rows across the batch whose peak was narrower than one cycle."""
        return sum(row.unmeasured for row in self.rows)

    @property
    def median_points(self) -> float | None:
        points = [row.points for row in self.measured]
        return float(np.median(points)) if points else None

    def summary(self) -> str:
        """The finding in a sentence or three."""
        if self.note:
            return self.note
        measured = self.measured
        if not measured:
            return "No integrated peak carries a point count yet; process the batch."
        cycle = self.median_cycle
        width = self.median_width
        counted = sum(row.found for row in measured)
        parts = [f"{len(measured)} component(s) measured"]
        if cycle is not None:
            parts.append(f"one scan every {cycle:.1f} s")
        parts.append(f"a median {self.median_points:.0f} point(s) on the peak")
        sparse = self.sparse
        if sparse:
            parts.append(f"{len(sparse)} component(s) typically under the "
                         f"{MIN_FIT_POINTS} a fit needs")
        unmeasured = self.unmeasured
        if unmeasured and counted:
            parts.append(f"{unmeasured:,} of {counted:,} peaks ({unmeasured / counted:.0%}) "
                         f"narrower than one cycle, so their width cannot be "
                         f"measured and the widths below are of the wider peaks only")
        if width is not None:
            fit = width * FIT_IN_FWHM
            base = width * BASE_IN_FWHM / BASE_POINTS
            parts.append(f"the measurable peaks are a median {width:.1f} s wide "
                         f"at half height; a cycle of {fit:.1f} s would let "
                         f"every peak of that width be fitted, and {base:.1f} s "
                         f"would put {BASE_POINTS} points across its base"
                         + (" — upper bounds, since the narrower peaks were "
                            "not measured" if unmeasured else ""))
        return "; ".join(parts) + "."


def _cycle(entries: list[SampleEntry], component,
           measured: dict | None = None) -> float | None:
    """
    The channel's cycle time, in seconds, from the first sample that has it.

    `measured` memoises the answer per channel rather than per component. The
    cycle is a property of the channel's own time axis, and a method's
    components crowd onto far fewer channels than there are components — on
    the 141-component method 59 transitions share a handful — so without it
    the same `np.median(np.diff(...))` over the same 339-point axis was
    computed once for every row of the report.
    """
    for entry in entries:
        if not entry.is_loaded:
            continue
        try:
            channel = match_channel(entry.sample, component)
        except Exception:
            channel = None
        if channel is None:
            continue
        # the entry's key and the channel's index identify the time axis;
        # the channel object itself is not hashable across readers
        token = (entry.key, getattr(channel, "index", id(channel)))
        if measured is not None and token in measured:
            return measured[token]
        times = np.asarray(channel.rt, dtype=float)
        cycle = (float(np.median(np.diff(times))) * 60.0
                 if times.size >= 2 else None)
        if cycle is None:
            continue
        if measured is not None:
            measured[token] = cycle
        return cycle
    return None


def sampling_report(results: ResultsSet, entries: list[SampleEntry],
                    method: ProcessingMethod) -> SamplingReport:
    """
    Points per peak for every component, from the batch's own results.

    Rows integrated before the point count existed carry none and are left
    out of the medians; the count of rows found still includes them, so a
    component measured on few of its rows shows a smaller n against its
    found.
    """
    report = SamplingReport()
    if not len(results):
        report.note = "no results yet; process the batch"
        return report
    rows_of = results.by_component()
    cycles: dict = {}
    for component in method.components:
        if not component.is_valid:
            continue
        rows = [r for r in rows_of.get(component.name, ()) if r.found]
        counted = [r for r in rows if r.points is not None]
        widths = [r.width * 60.0 for r in counted if r.width and r.width > 0]
        points = [float(r.points) for r in counted]
        # a width of zero is one point above half height: the peak is
        # narrower than a cycle, and its width is bounded, not measured
        unmeasured = sum(1 for r in counted if not r.width)
        report.rows.append(ComponentSampling(
            component=component.name,
            is_internal_standard=component.is_internal_standard,
            found=len(rows),
            cycle=_cycle(entries, component, cycles),
            width=float(np.median(widths)) if widths else None,
            points=float(np.median(points)) if points else None,
            sparse=sum(1 for r in counted if r.points < MIN_FIT_POINTS),
            unmeasured=unmeasured,
        ))
    if not report.measured:
        report.note = ("no integrated peak carries a point count; the batch "
                       "was processed by an earlier version — process it again")
    return report
