"""
An acquisition schedule the method implies, for the instrument.

The sampling report can say that a batch put one point on each peak and
what cycle time the peaks would need. Saying it is not the same as fixing
it: the fix is a scheduled acquisition — each transition acquired only
around its retention time — and the instrument software takes that as a
table. This builds the table from the method, works out how many
transitions are ever acquired at once, and from a target cycle time
derives the dwell each would get, so that the schedule says whether the
target is reachable before anybody types it in.

The arithmetic is the plain one. At any moment the instrument cycles
through the transitions whose windows contain that moment, spending a
dwell on each plus a pause to move between them, so the cycle time is the
busiest moment's count times dwell plus pause. Given a target cycle, the
dwell follows; given a dwell floor, the cycle that can be reached follows.
No instrument-specific overhead is modelled, and the file is a plain CSV
whose columns are named so that a spreadsheet maps onto the vendor's
table — it is not claimed to import directly into any of them, and the
detection window in particular is a single method-wide setting in
Analyst, where the widest window here is the one to type.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field

from .method import ProcessingMethod
from .processing import MIN_FIT_POINTS
from .sampling import BASE_POINTS, SamplingReport

#: the pause between one transition and the next, in milliseconds — SCIEX's
#: default on a triple quadrupole, and about what a TOF spends switching
PAUSE_MS = 5.0

#: the shortest dwell worth acquiring, in milliseconds. Below this a
#: transition's counting statistics are worse than the peak it is meant to
#: measure.
MIN_DWELL_MS = 5.0


@dataclass(frozen=True)
class Slot:
    """One transition and when it is acquired."""

    component: str
    group: str
    precursor: float
    fragment: float
    rt: float
    start: float
    end: float
    is_internal_standard: bool = False


@dataclass
class Schedule:
    slots: list[Slot] = field(default_factory=list)
    #: components with no retention time, which cannot be scheduled
    unscheduled: list[str] = field(default_factory=list)
    target_cycle: float = 0.0
    pause_ms: float = PAUSE_MS
    min_dwell_ms: float = MIN_DWELL_MS
    #: the most transitions acquired at once, and when
    busiest: int = 0
    busiest_at: float | None = None
    note: str = ""

    @property
    def dwell_ms(self) -> float | None:
        """The dwell each transition gets at the busiest moment, for the
        target cycle; None when nothing is scheduled."""
        if not self.busiest or self.target_cycle <= 0:
            return None
        return self.target_cycle * 1000.0 / self.busiest - self.pause_ms

    @property
    def feasible(self) -> bool:
        dwell = self.dwell_ms
        return dwell is not None and dwell >= self.min_dwell_ms

    @property
    def achievable_cycle(self) -> float | None:
        """The shortest cycle the busiest moment allows at the dwell floor,
        in seconds."""
        if not self.busiest:
            return None
        return self.busiest * (self.min_dwell_ms + self.pause_ms) / 1000.0

    @property
    def widest_window(self) -> float | None:
        if not self.slots:
            return None
        return max(slot.end - slot.start for slot in self.slots)

    def concurrency(self) -> list[tuple[float, int]]:
        """How many transitions are acquired at once, as (time, count) steps."""
        events: list[tuple[float, int]] = []
        for slot in self.slots:
            events.append((slot.start, 1))
            events.append((slot.end, -1))
        # an end and a start at the same time: the end first, so a window
        # that closes as another opens is not counted twice
        events.sort(key=lambda e: (e[0], e[1]))
        profile: list[tuple[float, int]] = []
        count = 0
        for time, change in events:
            count += change
            profile.append((time, count))
        return profile

    def summary(self) -> str:
        if self.note:
            return self.note
        parts = [f"{len(self.slots)} transition(s) scheduled"]
        if self.unscheduled:
            parts.append(f"{len(self.unscheduled)} with no retention time left out")
        parts.append(f"at most {self.busiest} acquired at once"
                     + (f", at {self.busiest_at:.2f} min" if self.busiest_at is not None else ""))
        dwell = self.dwell_ms
        if dwell is not None:
            if self.feasible:
                parts.append(f"a cycle of {self.target_cycle:.1f} s gives each "
                             f"{dwell:.0f} ms of dwell")
            else:
                parts.append(f"a cycle of {self.target_cycle:.1f} s would leave "
                             f"{dwell:.0f} ms of dwell, under the {self.min_dwell_ms:.0f} ms "
                             f"floor; with {self.busiest} at once the shortest cycle is "
                             f"{self.achievable_cycle:.1f} s — narrow the windows where "
                             f"they overlap, or drop transitions")
        return "; ".join(parts) + "."


def build_schedule(method: ProcessingMethod, target_cycle: float,
                   pause_ms: float = PAUSE_MS,
                   min_dwell_ms: float = MIN_DWELL_MS) -> Schedule:
    """
    The schedule the method implies: every component with a retention time,
    acquired over its window, and what a target cycle buys each of them.
    """
    schedule = Schedule(target_cycle=target_cycle, pause_ms=pause_ms,
                        min_dwell_ms=min_dwell_ms)
    for component in method.components:
        if not component.is_valid:
            continue
        window = component.rt_window()
        if window is None:
            schedule.unscheduled.append(component.name)
            continue
        schedule.slots.append(Slot(
            component=component.name, group=component.group,
            precursor=component.precursor,
            fragment=component.fragment if component.fragment is not None
            else component.precursor,
            rt=component.rt, start=max(window[0], 0.0), end=window[1],
            is_internal_standard=component.is_internal_standard))
    schedule.slots.sort(key=lambda slot: (slot.rt, slot.component))
    if not schedule.slots:
        schedule.note = ("nothing to schedule: no component has a retention "
                         "time — Suggest from data… can propose them")
        return schedule
    busiest, at = 0, None
    for time, count in schedule.concurrency():
        if count > busiest:
            busiest, at = count, time
    schedule.busiest, schedule.busiest_at = busiest, at
    return schedule


def suggested_cycle(report: SamplingReport | None,
                    points: int = MIN_FIT_POINTS) -> tuple[float | None, str]:
    """
    A target cycle from what the batch measured, and where it came from.

    Three points on the flanks — the fit's minimum — or ten across the
    base. When the batch's peaks were mostly narrower than a cycle the width
    it measured is a bound on the wider ones, and the cycle that follows is
    an upper bound too; the note says so, since the schedule this produces
    will be typed into an instrument.
    """
    if report is None or report.median_width is None:
        return None, ("no measured peak width to start from — process a batch "
                      "and see Batch QC ▸ Sampling")
    width = report.median_width
    if points >= BASE_POINTS:
        cycle = width * (4.0 / 2.3548) / BASE_POINTS
        basis = f"{BASE_POINTS} points across the base"
    else:
        cycle = width * (2.0 / 2.3548)
        basis = f"{MIN_FIT_POINTS} points on the flanks, a fit at any phase"
    note = f"{basis} of peaks {width:.1f} s wide at half height"
    if report.unmeasured:
        note += (f" — an upper bound: {report.unmeasured:,} peaks were narrower "
                 f"than a cycle and their width could not be measured")
    return cycle, note


CSV_HEADER = ["ID", "Group", "Q1 (Da)", "Q3 (Da)", "RT (min)",
              "Window start (min)", "Window end (min)", "Dwell (ms)",
              "Internal standard"]


def write_csv(schedule: Schedule, path: str | os.PathLike) -> str:
    """
    The schedule as a CSV, one transition per row.

    The dwell written is the one the target cycle allows at the busiest
    moment, for every row alike: a transition acquired alone could have
    more, but a schedule that varies the dwell by moment is one the
    instrument software does not take.
    """
    path = str(path)
    dwell = schedule.dwell_ms
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for slot in schedule.slots:
            writer.writerow([
                slot.component, slot.group, f"{slot.precursor:.4f}",
                f"{slot.fragment:.4f}", f"{slot.rt:.2f}", f"{slot.start:.2f}",
                f"{slot.end:.2f}", "" if dwell is None else f"{dwell:.1f}",
                "yes" if slot.is_internal_standard else ""])
    return path
