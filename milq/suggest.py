"""
What the data proposes, where the method is silent or wrong.

`health` says what a method will fail at. This says what to do about the two
failures that the batch itself can answer: a component with no retention
time, and a window narrower than the sampling can resolve.

Nothing here changes a method. Every proposal comes back with what it rests
on — how many injections agree, how tall the peak is, how far a rival time
sits — so that accepting one is a decision somebody made rather than one the
program made quietly.

The estimator is calibrated before it is trusted, on the components of the
same method that already declare a time. That is the whole difference between
a number and a number worth acting on, and it is measured per batch rather
than assumed: on one real method the estimate landed within a sampling
interval of the declared time for 71% of components above ten thousand counts
and 22% of those below a hundred.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .components import Component
from .health import COMFORTABLE_POINTS, shares_transition
from .matching import match_channel
from .method import ProcessingMethod
from .processing import detect_peaks
from .quantify import XicCache, extract_xic, measured_noise
from .samples import SampleEntry

#: the fewest injections a time has to appear in before it is offered
MIN_SUPPORT = 0.5

#: intensity bands the estimator's accuracy is reported over. Peak height
#: is what decides whether a retention time means anything, and by how much,
#: so the confidence attached to a proposal is the accuracy actually measured
#: on the components of this batch that fall in the same band.
BANDS = ((0.0, 100.0), (100.0, 1_000.0), (1_000.0, 10_000.0),
         (10_000.0, float("inf")))


@dataclass(frozen=True)
class Estimate:
    """A retention time the data proposes for one component."""

    component: str
    rt: float | None = None
    support: int = 0
    injections: int = 0
    height: float = 0.0
    spread: float = 0.0
    #: how many injections back a clearly different time
    rival: int = 0
    declared: float | None = None
    note: str = ""

    @property
    def found(self) -> bool:
        return self.rt is not None

    @property
    def agreed(self) -> bool:
        return (self.found and self.injections > 0
                and self.support >= max(3, self.injections * MIN_SUPPORT))

    @property
    def ambiguous(self) -> bool:
        return self.rival >= self.support - 2

    @property
    def error(self) -> float | None:
        """Against the declared time, where there is one to check against."""
        if self.rt is None or self.declared is None:
            return None
        return self.rt - self.declared


@dataclass(frozen=True)
class Band:
    """How well the estimator did, on this batch, at this peak height."""

    low: float
    high: float
    components: int = 0
    within: float = 0.0
    median_error: float = 0.0

    def holds(self, height: float) -> bool:
        return self.low <= height < self.high


@dataclass
class Suggestions:
    estimates: list[Estimate] = field(default_factory=list)
    bands: list[Band] = field(default_factory=list)
    #: the sampling interval, in minutes; the measured time is no better
    step: float = 0.0
    injections: int = 0
    note: str = ""

    @property
    def missing(self) -> list[Estimate]:
        """Only the components with nothing in the method to begin with."""
        return [e for e in self.estimates if e.declared is None]

    @property
    def offered(self) -> list[Estimate]:
        return [e for e in self.missing if e.agreed and not e.ambiguous]

    def confidence(self, estimate: Estimate) -> Band | None:
        return next((b for b in self.bands if b.holds(estimate.height)), None)


# --------------------------------------------------------------------------- #
# retention times
# --------------------------------------------------------------------------- #
def _peaks_of(entry, component: Component, method: ProcessingMethod,
              cache: XicCache):
    """Every peak of the whole run, not only the tallest."""
    x, y, channel = extract_xic(entry, component, method, cache)
    if channel is None or x.size < 5:
        return [], None
    params = method.integration_for(component)
    peaks = detect_peaks(x, y, min_relative=params.min_relative_height,
                         min_snr=params.min_snr,
                         noise=measured_noise(x, y, params))
    step = float(np.median(np.diff(x))) if x.size > 1 else None
    return peaks, step


def estimate_time(component: Component, entries: list[SampleEntry],
                  method: ProcessingMethod,
                  cache: XicCache | None = None) -> Estimate:
    """
    Where a component elutes, from agreement between injections.

    A real peak appears at the same time in injection after injection; a
    noise peak does not. Every peak of every injection is pooled rather than
    only the tallest, so a small consistent peak is found underneath a large
    one that wanders — which is the case the tallest-peak rule gets wrong.
    """
    cache = cache if cache is not None else XicCache()
    found: list[tuple[float, float, float, int]] = []
    step = None
    for index, entry in enumerate(entries):
        peaks, this_step = _peaks_of(entry, component, method, cache)
        step = step or this_step
        for peak in peaks:
            found.append((peak.apex_rt, peak.area, peak.height, index))

    if not found or not step:
        return Estimate(component.name, injections=len(entries),
                        declared=component.rt or None,
                        note="no peak in any injection")

    times = np.array([f[0] for f in found])
    best, members = None, None
    for candidate in times:
        near = np.flatnonzero(np.abs(times - candidate) <= step)
        weight = (len({found[i][3] for i in near}),
                  float(sum(found[i][1] for i in near)))
        if best is None or weight > best:
            best, members = weight, near
    picked = [found[i] for i in members]
    rt = float(np.median([p[0] for p in picked]))

    # a clearly separate time with comparable support means the answer is not
    # one time but two, and offering either would be a coin toss
    far = np.abs(times - rt) > 2 * step
    rival = 0
    for candidate in times[far]:
        near = np.flatnonzero(np.abs(times - candidate) <= step)
        rival = max(rival, len({found[i][3] for i in near}))

    return Estimate(
        component=component.name, rt=rt, support=best[0],
        injections=len(entries),
        height=float(np.median([p[2] for p in picked])),
        spread=float(np.max([p[0] for p in picked])
                     - np.min([p[0] for p in picked])),
        rival=rival, declared=component.rt or None)


def _calibrate(estimates: list[Estimate], step: float) -> list[Band]:
    """
    How close the estimator came on the components that already declare a
    time, by peak height. This is what a proposal's confidence is: not a
    rule of thumb, but the accuracy measured on this batch.
    """
    known = [e for e in estimates
             if e.declared is not None and e.agreed and e.error is not None]
    bands = []
    for low, high in BANDS:
        inside = [e for e in known if low <= e.height < high]
        if not inside:
            bands.append(Band(low, high))
            continue
        errors = np.abs([e.error for e in inside])
        bands.append(Band(low, high, len(inside),
                          float(np.mean(errors <= step)),
                          float(np.median(errors))))
    return bands


def suggest_times(method: ProcessingMethod, entries: list[SampleEntry],
                  progress=None) -> Suggestions:
    """
    A retention time for every component, and how well that was done on the
    ones whose time is already known.
    """
    loaded = [e for e in entries if e.is_loaded]
    if not loaded:
        return Suggestions(note="no files are open")
    components = [c for c in method.components if c.is_valid]
    if not components:
        return Suggestions(note="the method has no components")

    cache = XicCache(max_entries=16384)
    estimates, step = [], 0.0
    for number, component in enumerate(components, start=1):
        estimate = estimate_time(component, loaded, method, cache)
        estimates.append(estimate)
        if not step:
            _, this = _peaks_of(loaded[0], component, method, cache)
            step = this or 0.0
        if progress is not None and progress(number, len(components)) is False:
            break
    estimates = _mark_shared(estimates, components, step)
    return Suggestions(estimates=estimates, bands=_calibrate(estimates, step),
                       step=step, injections=len(loaded))


def _mark_shared(estimates: list[Estimate], components: list[Component],
                 step: float) -> list[Estimate]:
    """
    Say when two proposals are the same peak seen twice.

    Components sharing a precursor and a fragment share one trace, so they
    are offered the same time — and accepting both does not separate them,
    it writes the same answer twice. Whoever accepts should know that is
    what they are doing.
    """
    by_name = {c.name: c for c in components}
    out = []
    for estimate in estimates:
        mine = by_name.get(estimate.component)
        if mine is None or estimate.rt is None:
            out.append(estimate)
            continue
        twins = [other.component for other in estimates
                 if other.component != estimate.component
                 and other.rt is not None
                 and abs(other.rt - estimate.rt) <= step
                 and other.component in by_name
                 and shares_transition(mine, by_name[other.component])]
        if twins:
            names = ", ".join(sorted(twins))
            note = (f"the same trace as {names}; this time does not separate "
                    f"them")
            out.append(Estimate(**{**estimate.__dict__, "note": note}))
        else:
            out.append(estimate)
    return out


# --------------------------------------------------------------------------- #
# windows
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class WindowSuggestion:
    """A half-width wide enough for a peak to be found in."""

    component: str
    current: float
    points_now: int
    suggested: float
    points_then: int


def suggest_windows(method: ProcessingMethod, entries: list[SampleEntry],
                    points: int = COMFORTABLE_POINTS
                    ) -> list[WindowSuggestion]:
    """
    Half-widths that hold enough scans, from the sampling the files actually
    have rather than from a rule.

    A window is a statement about where the apex may be. It is also, whether
    anyone meant it or not, a statement about how many points the integrator
    gets — and at 14.6 s a cycle, ±0.5 min is four.
    """
    loaded = [e for e in entries if e.is_loaded]
    if not loaded:
        return []
    sample = loaded[0].sample
    out = []
    for component in method.components:
        window = component.rt_window()
        if window is None or not component.is_valid:
            continue
        try:
            channel = match_channel(sample, component)
        except Exception:
            channel = None
        if channel is None:
            continue
        times = np.asarray(channel.rt, dtype=float)
        if times.size < 2:
            continue
        step = float(np.median(np.diff(times)))
        inside = int(np.sum((times >= window[0]) & (times <= window[1])))
        if inside >= points:
            continue
        # half a step of slack, so a window is not decided by where a scan
        # happens to land relative to the retention time
        wanted = round((points - 1) / 2.0 * step + step / 2.0, 2)
        if wanted <= component.rt_halfwidth:
            continue
        out.append(WindowSuggestion(
            component.name, component.rt_halfwidth, inside, wanted,
            int(np.sum((times >= component.rt - wanted)
                       & (times <= component.rt + wanted)))))
    return out
