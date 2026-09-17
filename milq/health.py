"""
What the method itself will fail at, before a batch is processed.

Everything reported here was found by hand on a real method over the course
of a day, and every one of them is mechanically detectable: eighty-two
components with no retention time, twenty-four sharing a transition with
nothing to separate them, an internal standard for a third of the panel with
no time of its own, windows narrower than the sampling can resolve.

None of it is about the data being bad. It is about the method asking for
something the acquisition cannot deliver, which is a different problem and
has a different fix — and one worth learning about before a batch is
processed rather than from the results afterwards.

The checks that need a batch open are skipped without one and say so, rather
than passing quietly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .components import WHOLE_DALTON, Component, formula_disagreement
from .method import ProcessingMethod
from .samples import SampleEntry

SERIOUS = "serious"
WARNING = "warning"

#: the fewest points across a retention-time window for a peak to be found in
#: it. Below five `detect_peaks` declines outright; below about eight there is
#: not enough of a peak to place its edges with any confidence.
COMFORTABLE_POINTS = 8


@dataclass(frozen=True)
class Finding:
    """One thing wrong with the method, and who it affects."""

    check: str
    severity: str
    summary: str
    components: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def count(self) -> int:
        return len(self.components)


@dataclass
class MethodHealth:
    findings: list[Finding] = field(default_factory=list)
    #: checks that could not run, and why
    skipped: list[str] = field(default_factory=list)
    components: int = 0

    @property
    def serious(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SERIOUS]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def sound(self) -> bool:
        return not self.findings


def _served_by(method: ProcessingMethod) -> dict[str, list[str]]:
    served: dict[str, list[str]] = defaultdict(list)
    for component in method.components:
        if component.internal_standard:
            served[component.internal_standard].append(component.name)
    return served


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def shares_transition(a: Component, b: Component) -> bool:
    """
    Whether the mass spectrometer sees these two as the same measurement.

    Both windows have to overlap: two components with the same precursor but
    different fragments are separate channels and are not in question.
    """
    if not _overlap(a.mass_window(), b.mass_window()):
        return False
    span = max(a.tolerance, b.tolerance)
    half = (a.precursor * span * 1e-6 if a.unit.lower() == "ppm" else span)
    return abs(a.precursor - b.precursor) <= half


def check_method(method: ProcessingMethod,
                 entries: list[SampleEntry] | None = None) -> MethodHealth:
    """
    Read the method against itself, and against the batch where one is open.

    The order of the findings is the order they cost somebody time in: what
    silently produces a wrong number first, then what produces no number.
    """
    components = [c for c in method.components if c.is_valid]
    health = MethodHealth(components=len(components))
    served = _served_by(method)
    internal = {c.name for c in method.components if c.is_internal_standard}

    # -- the method against itself ------------------------------------------ #
    shared: list[str] = []
    for index, a in enumerate(components):
        for b in components[index + 1:]:
            if not shares_transition(a, b):
                continue
            windows = (a.rt_window(), b.rt_window())
            if None in windows or _overlap(*windows):
                shared.extend([a.name, b.name])
    if shared:
        names = sorted(set(shared))
        health.findings.append(Finding(
            "shared transition", SERIOUS,
            f"{len(names)} components cannot be told apart",
            names,
            "They share a precursor and a fragment within tolerance, and "
            "their retention-time windows overlap or are missing. The "
            "instrument measures one trace for both, so both report the same "
            "number. Only a retention time separates them."))

    unnamed = [c.name for c in components
               if c.internal_standard and c.internal_standard not in internal]
    if unnamed:
        health.findings.append(Finding(
            "missing internal standard", SERIOUS,
            f"{len(unnamed)} components name an internal standard the method "
            f"does not have",
            sorted(unnamed),
            "Their ratios cannot be formed, so nothing they report is "
            "normalised."))

    blind = sorted(name for name in internal
                   if not next((c for c in components if c.name == name),
                               Component("", 1, 1)).rt and served.get(name))
    if blind:
        detail = "; ".join(f"{name} serves {len(served[name])}" for name in blind)
        health.findings.append(Finding(
            "internal standard without a time", SERIOUS,
            f"{len(blind)} internal standards have no retention time",
            blind,
            f"Each is searched over the whole run and the largest peak "
            f"anywhere wins, so the standard everything is divided by may be "
            f"a different peak in every injection. {detail}."))

    unfloored = sorted(name for name in internal
                       if served.get(name)
                       and next((c for c in components if c.name == name),
                                Component("", 1, 1)).min_response is None)
    if unfloored:
        health.findings.append(Finding(
            "internal standard without a response floor", WARNING,
            f"{len(unfloored)} internal standards declare no minimum response",
            unfloored,
            "Nothing says how much of the standard an injection has to show "
            "before a ratio to it means anything. The quality charts and the "
            "acceptance fall back to a signal-to-noise of ten, which on a "
            "scheduled acquisition — where the baseline is exact zeros and "
            "the noise cannot be measured — is an absolute height against an "
            "arbitrary constant. Set Min. response on each standard to what "
            "it gives when the run is right; the batch cannot derive it, "
            "though Batch QC \u25b8 Suggest floors\u2026 proposes a starting "
            "point from what it gave."))

    disagreeing = [formula_disagreement(c) for c in components]
    disagreeing = [d for d in disagreeing if d is not None]
    if disagreeing:
        # a whole dalton is the case where repairing the mass is the wrong
        # repair: the instrument acquired what was written — that number is
        # the channel the data is on — so it is the name that is in question
        apart = [d for d in disagreeing
                 if d.difference is not None
                 and abs(d.difference) >= WHOLE_DALTON]
        whole_dalton = ""
        if apart:
            whole_dalton = (
                f"{len(apart)} of them are a whole dalton or more apart, and "
                f"there the mass is likely to be the right one — it is what "
                f"the instrument was set to acquire — which makes the *name* "
                f"the error. The dialog offers a third answer for those rows, "
                f"Rename to: the names, in the same class and from LIPID MAPS, "
                f"whose formula does match the written mass. Renaming moves no "
                f"number, so nothing needs reprocessing. ")
        detail = "; ".join(
            f"{d.component.name} {d.formula} is {d.theoretical:.4f} and the "
            f"method says {d.written:.4f}" for d in disagreeing[:4])
        health.findings.append(Finding(
            "formula against precursor", SERIOUS,
            f"{len(disagreeing)} components have a formula that is not their "
            f"precursor",
            sorted(d.component.name for d in disagreeing),
            f"One of the two is wrong, and they are used for different "
            f"things: the precursor is what picks the acquisition channel "
            f"and, with no fragment written, what the extraction window is "
            f"built from; the formula is the true mass the mass "
            f"recalibration corrects towards. Each is further apart than the "
            f"written precursor's own last decimal allows. Method workspace "
            f"\u25b8 Repair precursors\u2026 lists them with both masses and "
            f"writes the formula's where a row is ticked \u2014 ticked "
            f"already where the two are under half a dalton apart, which is "
            f"one compound written to fewer places, and left for the person "
            f"to decide where they are a whole dalton or more apart, which is "
            f"two different compounds. {whole_dalton}{detail}."))

    unlocked = sorted(name for name in internal
                      if not next((c for c in components if c.name == name),
                                  Component("", 1, 1)).formula)
    if unlocked:
        health.findings.append(Finding(
            "internal standard without a formula", WARNING,
            f"{len(unlocked)} internal standards carry no formula",
            unlocked,
            "No lock mass for the recalibration: without a formula and an "
            "adduct nothing says where the standard's mass belongs, and the "
            "written precursor cannot stand in for it — a value typed to one "
            "decimal is good to a few hundred parts per million, which is a "
            "hundred times the error being corrected. Method workspace ▸ "
            "Fill formulas from names derives one where the name is lipid "
            "shorthand, and refuses where the precursor disagrees."))

    untimed = [c.name for c in components if not c.rt]
    if untimed:
        health.findings.append(Finding(
            "no retention time", WARNING,
            f"{len(untimed)} of {len(components)} components have no "
            f"retention time",
            sorted(untimed),
            "The window is the whole run and the largest peak in it is taken, "
            "whether or not it is the analyte."))

    # -- the method against the acquisition ---------------------------------- #
    if not entries:
        health.skipped.append(
            "how many points fall in each retention-time window — open a "
            "file and the window can be measured against the sampling")
        return health

    narrow = _narrow_windows(components, method, entries)
    if narrow:
        health.findings.append(Finding(
            "window too narrow", SERIOUS,
            f"{len(narrow)} components have a window the sampling cannot "
            f"resolve",
            sorted(narrow),
            f"Fewer than {COMFORTABLE_POINTS} scans fall inside it. A peak "
            f"cannot be placed, let alone integrated, on that few points; "
            f"widen the window or accept that the area is an estimate."))

    outside, ranges = _outside_survey(components, entries)
    if not ranges:
        health.skipped.append(
            "whether the survey scan covers each precursor — this acquisition "
            "has no survey scan, so the accurate mass, LIPID MAPS annotation "
            "and mass drift are not available for any component")
    elif outside:
        health.findings.append(Finding(
            "precursor outside the survey scan", WARNING,
            f"{len(outside)} components have a precursor no survey scan covers",
            sorted(outside),
            f"The survey scans cover {', '.join(ranges)}. The accurate mass, "
            f"the LIPID MAPS annotation and the mass drift cannot be measured "
            f"for these; the transition itself is unaffected."))
    return health


def survey_coverage(components: list[Component],
                    entries: list[SampleEntry] | None
                    ) -> tuple[list[str], list[str]]:
    """
    The finding above without the finding, for a caller with its own words.

    `method_report` prints both halves — the ranges the surveys cover and
    the precursors outside them — as a sentence rather than as a warning,
    and reaching into `_outside_survey` for that would be reaching into
    another module's private.
    """
    return _outside_survey(components, list(entries or []))


def _outside_survey(components: list[Component],
                    entries: list[SampleEntry]) -> tuple[list[str], list[str]]:
    """
    Components whose precursor no survey scan covers, and the ranges the
    survey scans do cover — empty when the acquisition has none.
    """
    from .precursor import survey_channel

    loaded = [e for e in entries if e.is_loaded]
    if not loaded:
        return [], []
    sample = loaded[0].sample
    ranges = sorted({f"{c.info.start_mass:.0f}\u2013{c.info.end_mass:.0f}"
                     for c in sample.channels if c.info.is_ms1})
    if not ranges:
        return [], []
    outside = [c.name for c in components
               if c.precursor > 0 and survey_channel(sample, c.precursor, c.rt) is None]
    return outside, ranges


def _narrow_windows(components: list[Component], method: ProcessingMethod,
                    entries: list[SampleEntry]) -> list[str]:
    """Components whose window holds too few scans to find a peak in."""
    from .matching import match_channel

    loaded = [e for e in entries if e.is_loaded]
    if not loaded:
        return []
    sample = loaded[0].sample
    narrow = []
    for component in components:
        window = component.rt_window()
        if window is None:
            continue
        try:
            channel = match_channel(sample, component)
        except Exception:
            channel = None
        if channel is None:
            continue
        times = np.asarray(channel.rt, dtype=float)
        if times.size == 0:
            continue
        inside = int(np.sum((times >= window[0]) & (times <= window[1])))
        if inside < COMFORTABLE_POINTS:
            narrow.append(component.name)
    return narrow
