"""
Everything the application can say about a method before the method is run,
on one document.

The checks exist already and each of them is reachable from somewhere in the
Method workspace: *Check method* reads the table against itself, *Fill
formulas from names* says which names carry their composition, *Repair
precursors…* says where a formula and a mass contradict each other, *Export
schedule…* says what a target cycle leaves each transition. What has been
missing is the page that holds all of them at once — the thing somebody takes
to the person who wrote the method, or files beside it, or reads six months
later when a batch acquired under it is being defended.

So this builds no new check. It runs the ones that exist, on a method and,
where one is open, on an acquisition, and lays the answers out in the order a
reader needs them: what the method declares, what is wrong with it, what it
could know about its own chemistry, which of its standards could anchor a
mass axis, what the instrument would actually do with it.

Two things it deliberately will not do
--------------------------------------

**It does not grade the method.** There is no score, no badge and no traffic
light. The closing section is a paragraph of sentences, each one summing a
measurement that was made higher up the page, and every one of them is a
count rather than a judgement. A method with eighty-two components that have
no retention time may be perfectly fine — it may be a screening method — and
a green tick on the page would invite nobody to read the eighty-two.

**It does not move anything.** `fill_formulas` writes into the cells it is
given, so it is given *copies*: the report says how many formulas could be
derived without deriving them into the method. Nothing here has a side
effect on the session, which is also what lets it be built with no window.

What needs a batch, and what does not
-------------------------------------

The component table, the findings that read the method against itself, the
formulas and the lock-mass *candidates* need nothing but the method.

Given an acquisition — the first open sample — the report can also say which
channel serves each component (`matching.match_channel`), what the survey
scans cover and which precursors fall outside them.

Given a batch — results already processed — the schedule's target cycle comes
from what the batch's own peaks measured (`sampling.py` through
`schedule.suggested_cycle`) rather than from a round number. Without one the
schedule is still built, at `DEFAULT_CYCLE`, and says where that number came
from.

A lock mass is the clearest case of the difference. Whether a standard *could*
be a lock mass is a property of the method: it needs a formula and an adduct,
because a written precursor typed to one decimal is good to a few hundred ppm
and the error being corrected is a few. Whether it *is* one is a property of a
batch: `mass_drift` has to measure the same ion in most injections and
`recalibrate.lock_mass_refusal` has to find it near the mass its own formula
names. This document reports the first and says, in those words, that the
second is not something a method can answer.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass, field, replace

from . import __version__
from .chemistry import (ADDUCTS_BY_NAME, FormulaError, identify_adduct,
                        monoisotopic_mass, parse_formula)
from .components import (Component, FormulaFill, FormulaProposal,
                         PrecursorRepair, fill_formulas, precursor_repairs)
from .health import SERIOUS, MethodHealth, check_method
from .method import ProcessingMethod
from .recalibrate import MAX_LOCK_ERROR_PPM
from .report import _STYLE, _escape, _heading, _number, _table, print_document
from .sampling import SamplingReport, sampling_report
from .schedule import Schedule, build_schedule, suggested_cycle

#: the target cycle used when no batch has measured a peak width to start
#: from. Ten seconds is the schedule dialog's own fallback; it is stated on
#: the page as a fallback rather than printed as though it were derived.
DEFAULT_CYCLE = 10.0

#: what marks a flagged row in the component table. A column of check names
#: would be the width of the rest of the table put together, and the findings
#: section names every component under every check it belongs to, so the
#: table carries a mark and the legend says where to read it.
SERIOUS_MARK = "!"
WARNING_MARK = "†"

#: at most this many transitions of the busiest moment are named. The point
#: of naming them at all is that they are what has to be thinned to reach a
#: shorter cycle; past a screenful the CSV from *Export schedule…* is the
#: place to read them.
BUSIEST_LISTED = 30

#: at most this many components are listed after a sentence that counts them.
NAMES_LISTED = 8

#: the sections, in order, with their headings. Numbered where the document
#: is built, so a section left out closes the gap rather than leaving one.
SECTIONS = {
    "components": "Components",
    "findings": "What the check finds",
    "formulas": "Formulas",
    "lock": "Lock-mass candidates",
    "acquisition": "The acquisition",
    "schedule": "The schedule",
    "closing": "What the method is missing",
}


# --------------------------------------------------------------------------- #
# what is held
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LockCandidate:
    """An internal standard that carries enough chemistry to be a lock mass."""

    component: Component
    formula: str
    #: the neutral monoisotopic mass of the formula
    neutral: float | None
    #: the adduct the m/z is taken through, and whether the method declared it
    adduct: str
    declared: bool
    #: the exact m/z of that adduct, against the precursor the method writes
    exact: float | None
    written: float
    #: why no adduct could be settled on, where none could
    note: str = ""

    @property
    def error_ppm(self) -> float | None:
        """How far the written precursor sits from the exact mass."""
        if self.exact is None or not self.exact or not self.written:
            return None
        return (self.written - self.exact) / self.exact * 1e6

    @property
    def usable(self) -> bool:
        return self.exact is not None


@dataclass
class Formulas:
    """What the table knows, and could know, about what it is made of."""

    #: components whose Formula cell is already filled
    carried: list[Component] = field(default_factory=list)
    #: formulas `fill_formulas` would write into the empty cells
    derivable: list[FormulaProposal] = field(default_factory=list)
    #: names nothing could be read from
    underivable: list[Component] = field(default_factory=list)
    #: every contradiction between a formula and a precursor, both ways in
    refusals: list[PrecursorRepair] = field(default_factory=list)

    @property
    def refused_only(self) -> list[PrecursorRepair]:
        """
        The refusals that leave a Formula cell empty.

        A component that carries a formula and contradicts its own precursor
        is a refusal too — `precursor_repairs` finds it either way — but it
        is not a *missing* formula, and counting it as one would say the
        method knows less about itself than it does.
        """
        return [r for r in self.refusals if r.writes_formula]

    @property
    def missing(self) -> list[str]:
        """Every component still without a formula after the fill."""
        names = [c.name for c in self.underivable]
        names += [r.component.name for r in self.refused_only]
        return sorted(set(names))


@dataclass(frozen=True)
class Served:
    """One component against the channel the acquisition would give it."""

    component: str
    #: the channel's own label, or "" when nothing serves it
    channel: str = ""
    index: int | None = None
    #: True when the match is a survey scan rather than a channel of its own
    survey: bool = False
    #: how far the channel's precursor sits from the component's, in Da
    gap: float | None = None


@dataclass
class Acquisition:
    """What one open sample says about the method it would run."""

    name: str = ""
    file: str = ""
    channels: int = 0
    served: list[Served] = field(default_factory=list)
    #: the mass ranges the survey scans cover, as written for a reader
    survey_ranges: list[str] = field(default_factory=list)
    #: components whose precursor no survey covers
    outside_survey: list[str] = field(default_factory=list)

    @property
    def on_own_channel(self) -> list[Served]:
        return [s for s in self.served if s.channel and not s.survey]

    @property
    def on_survey(self) -> list[Served]:
        return [s for s in self.served if s.survey]

    @property
    def unserved(self) -> list[Served]:
        return [s for s in self.served if not s.channel]


@dataclass
class MethodReport:
    """One method, read every way this application can read one."""

    method: ProcessingMethod
    components: list[Component] = field(default_factory=list)
    health: MethodHealth = field(default_factory=MethodHealth)
    #: component name → the findings that name it
    flags: dict[str, list] = field(default_factory=dict)
    formulas: Formulas = field(default_factory=Formulas)
    lock_masses: list[LockCandidate] = field(default_factory=list)
    acquisition: Acquisition | None = None
    schedule: Schedule | None = None
    #: where the schedule's target cycle came from
    cycle_basis: str = ""
    sampling: SamplingReport | None = None
    title: str = "Method report"
    generated: str = ""

    # -- what is in it ------------------------------------------------------- #
    @property
    def internal_standards(self) -> list[Component]:
        return [c for c in self.components if c.is_internal_standard]

    @property
    def served_by(self) -> dict[str, list[str]]:
        """Which components each internal standard normalises."""
        served: dict[str, list[str]] = {}
        for component in self.components:
            if component.internal_standard:
                served.setdefault(component.internal_standard, []).append(
                    component.name)
        return served

    @property
    def timed(self) -> list[Component]:
        return [c for c in self.components if c.rt is not None]

    @property
    def flagged(self) -> list[str]:
        return sorted(self.flags)

    def severity(self, name: str) -> str:
        """The worst severity flagged against a component, or ""."""
        findings = self.flags.get(name) or []
        if any(f.severity == SERIOUS for f in findings):
            return SERIOUS
        return "warning" if findings else ""

    # -- the closing paragraph ------------------------------------------------ #
    def closing(self) -> list[str]:
        """
        What the method is missing, one sentence per measurement.

        Every sentence here is a count of something reported above, and none
        of them adds up to a verdict: a method is fit for a purpose this
        program has never been told. The last sentence says so, because a
        page of counts read quickly turns into a grade in the reader's head
        unless something stops it.
        """
        said: list[str] = []
        total = len(self.components)
        timed = len(self.timed)
        said.append(
            f"The method declares {total:,} component(s), of which {timed:,} "
            f"carry a retention time and {total - timed:,} do not; a component "
            f"with no time is searched over the whole run and takes the "
            f"largest peak in it.")

        formulas = self.formulas
        missing = formulas.missing
        said.append(
            f"{len(formulas.carried):,} carry a formula and "
            f"{len(formulas.derivable):,} more could take one from their own "
            f"name, leaving {len(missing):,} with none — "
            f"{len(formulas.underivable):,} whose name says nothing this can "
            f"read, and {len(formulas.refused_only):,} whose name and written "
            f"precursor contradict each other.")
        if formulas.refusals:
            whole = [r for r in formulas.refusals if r.whole_dalton]
            said.append(
                f"{len(formulas.refusals):,} formula(s) and precursor(s) "
                f"disagree by more than the written mass is good to, "
                f"{len(whole):,} of them by a whole dalton or more — where the "
                f"instrument acquired the mass as written, so the name is as "
                f"likely to be the error as the number.")

        standards = self.internal_standards
        served = self.served_by
        working = [c for c in standards if served.get(c.name)]
        floored = [c for c in working if c.min_response is not None]
        said.append(
            f"{len(standards):,} internal standard(s) are declared and "
            f"{len(working):,} of them normalise something; "
            f"{len(floored):,} of those {len(working):,} declare a minimum "
            f"response, without which a ratio has nothing to say how much of "
            f"the standard an injection had to show.")
        usable = [c for c in self.lock_masses if c.usable]
        said.append(
            f"{len(usable):,} standard(s) carry the formula and adduct a lock "
            f"mass needs; whether any of them is one cannot be read from a "
            f"method, only measured across a batch's injections.")

        health = self.health
        said.append(
            f"Checked against itself and against what is open, the method "
            f"raises {len(health.serious):,} serious finding(s) and "
            f"{len(health.warnings):,} warning(s) over {health.components:,} "
            f"valid component(s)"
            + (f", with {len(health.skipped):,} check(s) not run for want of "
               f"an open acquisition." if health.skipped else "."))

        acquisition = self.acquisition
        if acquisition is None:
            said.append(
                "No acquisition was open, so nothing here says which channel "
                "would serve which component, what the survey scans cover, or "
                "how many points a window would hold.")
        else:
            said.append(
                f"Against {acquisition.name or 'the open acquisition'}, "
                f"{len(acquisition.on_own_channel):,} component(s) are served "
                f"by a channel of their own, {len(acquisition.on_survey):,} "
                f"fall back to a survey scan and "
                f"{len(acquisition.unserved):,} are served by nothing that was "
                f"acquired.")
            if acquisition.survey_ranges:
                said.append(
                    f"The survey scans cover "
                    f"{', '.join(acquisition.survey_ranges)}, outside which "
                    f"{len(acquisition.outside_survey):,} precursor(s) lie: "
                    f"for those the accurate mass, the LIPID MAPS annotation "
                    f"and the mass drift cannot be measured, though the "
                    f"transition itself is unaffected.")
            else:
                said.append(
                    "The acquisition has no survey scan, so no precursor can "
                    "be measured accurately, annotated from LIPID MAPS, or "
                    "followed for drift.")

        schedule = self.schedule
        if schedule is not None and schedule.slots:
            dwell = schedule.dwell_ms
            sentence = (
                f"Scheduled, the method is {len(schedule.slots):,} transition(s) "
                f"with {len(schedule.unscheduled):,} left out for having no "
                f"time, at most {schedule.busiest:,} acquired at once")
            if schedule.busiest_at is not None:
                sentence += f" at {schedule.busiest_at:.2f} min"
            if dwell is not None and schedule.feasible:
                sentence += (f"; a cycle of {schedule.target_cycle:.1f} s "
                             f"leaves each {dwell:.0f} ms of dwell.")
            elif dwell is not None:
                sentence += (f"; a cycle of {schedule.target_cycle:.1f} s would "
                             f"leave {dwell:.0f} ms, under the "
                             f"{schedule.min_dwell_ms:.0f} ms floor, and the "
                             f"shortest that moment allows is "
                             f"{schedule.achievable_cycle:.1f} s.")
            else:
                sentence += "."
            said.append(sentence)
        elif schedule is not None:
            said.append(
                "Nothing can be scheduled: no component carries a retention "
                "time, so there is no window to acquire any of them over.")

        said.append(
            "None of the above is a verdict. Each sentence counts something "
            "that was measured on this page, and whether what is missing "
            "matters is a question about the purpose of the method, which "
            "this program has not been told.")
        return said


# --------------------------------------------------------------------------- #
# building it
# --------------------------------------------------------------------------- #
@dataclass
class _Loaded:
    """
    A stand-in with the two attributes `health` reads off a sample entry.

    Written rather than imported so that a bare reader sample — what a test
    has, and what somebody scripting this has — goes through exactly the same
    checks as an entry from an open project.
    """

    sample: object

    @property
    def is_loaded(self) -> bool:
        return True


def _entries_for(acquisition):
    """
    `check_method` and `matching` want sample entries; the report takes
    either an entry or a bare reader sample, so that a caller with a
    `SampleEntry` and a caller with an open file both work.
    """
    if acquisition is None:
        return None, None
    sample = getattr(acquisition, "sample", None)
    if sample is None and hasattr(acquisition, "channels"):
        sample, entry = acquisition, None
    else:
        entry = acquisition
    if sample is None:
        return None, None
    if entry is not None and getattr(entry, "is_loaded", False):
        return [entry], sample
    return [_Loaded(sample)], sample


def _sample_name(acquisition, sample) -> tuple[str, str]:
    """What to call the acquisition on the page: its name and its file."""
    name = (getattr(acquisition, "name", "")
            or getattr(sample, "name", "") or "")
    path = (getattr(acquisition, "path", "")
            or getattr(sample, "path", "") or "")
    return str(name), (os.path.basename(str(path)) if path else "")


def _lock_candidates(standards: list[Component]) -> list[LockCandidate]:
    """
    Each internal standard that carries a formula, priced through an adduct.

    The adduct the method declares is used where there is one. Where there is
    not, the written precursor is asked which adduct it *is*
    (`chemistry.identify_adduct`) rather than a protonated molecule being
    assumed: on a real method a channel written 430.35 is an ammonium adduct,
    and pricing it as `[M+H]+` puts the lock mass 17 Da from the ion.
    """
    candidates: list[LockCandidate] = []
    for component in standards:
        if not component.formula:
            continue
        try:
            neutral = monoisotopic_mass(parse_formula(component.formula))
        except FormulaError:
            candidates.append(LockCandidate(
                component, component.formula, None, "", False, None,
                component.precursor,
                note=f"{component.formula} is not a formula this can read"))
            continue
        adduct = ADDUCTS_BY_NAME.get(component.adduct)
        declared = adduct is not None
        note = ""
        if adduct is None and component.precursor > 0:
            choice = identify_adduct(component.formula, component.precursor)
            adduct = choice.adduct
            note = ("no adduct declared; read off the written precursor — "
                    + choice.reason) if adduct is not None else choice.reason
        if adduct is None:
            candidates.append(LockCandidate(
                component, component.formula, neutral, "", False, None,
                component.precursor,
                note=note or ("no adduct declared and no precursor to read one "
                              "off: the formula has no m/z")))
            continue
        candidates.append(LockCandidate(
            component, component.formula, neutral, adduct.name, declared,
            adduct.mz(neutral), component.precursor, note=note))
    return candidates


def _serving(components: list[Component], sample) -> list[Served]:
    """Which channel of this acquisition would carry each component."""
    from .matching import match_channel

    served: list[Served] = []
    for component in components:
        try:
            channel = match_channel(sample, component)
        except Exception:                     # a report must still be built
            channel = None
        if channel is None:
            served.append(Served(component.name))
            continue
        info = channel.info
        label = getattr(info, "short_label", "") or getattr(info, "name", "")
        precursor = info.precursor
        served.append(Served(
            component.name, str(label), getattr(channel, "index", None),
            survey=precursor is None,
            gap=None if precursor is None
            else abs(float(precursor) - component.precursor)))
    return served


def _sampling_for(batch, method: ProcessingMethod) -> SamplingReport | None:
    """The batch's sampling, from a session, a report, or nothing."""
    if batch is None:
        return None
    if isinstance(batch, SamplingReport):
        return batch
    results = getattr(batch, "results", None)
    entries = getattr(batch, "entries", None)
    if results is None or entries is None or not len(results):
        return None
    try:
        return sampling_report(results, list(entries), method)
    except Exception:                         # a report must still be built
        return None


def build(method: ProcessingMethod, acquisition_sample=None, batch=None,
          database=None, title: str = "") -> MethodReport:
    """
    Read a method every way this application can, and hold the answers.

    `acquisition_sample` is an open sample — a `SampleEntry` or a reader
    sample — and unlocks the checks that need to know what was acquired.
    `batch` is a session, or a `SamplingReport`, whose measured peak widths
    give the schedule a target cycle instead of a round number. `database` is
    a `lipidmaps.LipidDatabase`, or a callable returning one, consulted only
    for a name that is not lipid shorthand at all.

    Nothing here writes to the method. `fill_formulas` is run over copies,
    so the report can say how many formulas *could* be derived without
    quietly deriving them.
    """
    components = [c for c in method.components if c.is_valid]
    entries, sample = _entries_for(acquisition_sample)
    health = check_method(method, entries)

    flags: dict[str, list] = {}
    for finding in health.findings:
        for name in finding.components:
            flags.setdefault(name, []).append(finding)

    # copies: `fill_formulas` writes into the cells it is given, and the
    # point of this section is to say what *would* be filled. The proposals
    # it returns therefore carry the copy, not the method's component, which
    # is why `_provenance` looks a proposal up by name against the real row
    fill: FormulaFill = fill_formulas([replace(c) for c in components],
                                      database)
    formulas = Formulas(
        carried=list(fill.kept), derivable=list(fill.filled),
        underivable=list(fill.underived),
        refusals=precursor_repairs(components, database))

    sampling = _sampling_for(batch, method)
    cycle, basis = suggested_cycle(sampling)
    if cycle is None:
        cycle = DEFAULT_CYCLE
        basis = (f"No batch has been processed, so the target cycle below is "
                 f"{DEFAULT_CYCLE:.0f} s — a round number and not a "
                 f"measurement. Process a batch and the cycle comes from the "
                 f"width its own peaks measured; see Batch QC \u25b8 Sampling.")
    else:
        basis = "Starting from " + basis
    schedule = build_schedule(method, cycle)

    acquisition = None
    if sample is not None:
        from .health import survey_coverage

        name, file = _sample_name(acquisition_sample, sample)
        outside, ranges = survey_coverage(components, entries)
        acquisition = Acquisition(
            name=name, file=file, channels=len(getattr(sample, "channels", [])),
            served=_serving(components, sample),
            survey_ranges=list(ranges), outside_survey=sorted(outside))

    return MethodReport(
        method=method, components=components, health=health, flags=flags,
        formulas=formulas,
        lock_masses=_lock_candidates([c for c in components
                                      if c.is_internal_standard]),
        acquisition=acquisition, schedule=schedule, cycle_basis=basis,
        sampling=sampling,
        title=title or "Method report",
        generated=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"))


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def _names(names, limit: int = NAMES_LISTED) -> str:
    names = list(names)
    shown = ", ".join(_escape(name) for name in names[:limit])
    if len(names) > limit:
        shown += f", and {len(names) - limit:,} more"
    return shown


def _title_block(report: MethodReport, title: str) -> str:
    standards = len(report.internal_standards)
    acquisition = report.acquisition
    where = (acquisition.file or acquisition.name) if acquisition else "—"
    return (
        f'<p class="eyebrow">MIL-Q {_escape(__version__)} · method '
        f'report</p><h1>{_escape(title)}</h1>'
        f'<table class="ident" width="100%" cellpadding="4" cellspacing="0">'
        f'<tr><td class="label" width="18%">Components</td>'
        f'<td width="32%">{len(report.components):,}'
        f'{f" ({standards:,} internal standards)" if standards else ""}</td>'
        f'<td class="label" width="18%">Generated</td>'
        f'<td width="32%">{_escape(report.generated)}</td></tr>'
        f'<tr class="alt"><td class="label">Acquisition</td>'
        f'<td>{_escape(where)}</td>'
        f'<td class="label">Findings</td>'
        f'<td>{len(report.health.serious):,} serious, '
        f'{len(report.health.warnings):,} warning(s)</td></tr></table>')


def _contents(titles: list[str], pages: dict[str, int] | None) -> str:
    if len(titles) < 2:
        return ""
    rows = []
    for number, title in enumerate(titles):
        stripe = ' class="alt"' if number % 2 else ""
        page = "" if not pages else str(pages.get(title, ""))
        cell = (f'<td class="num" width="8%">{page}</td>'
                if pages is not None else "")
        rows.append(f'<tr{stripe}><td>{_escape(title)}</td>{cell}</tr>')
    return ('<h2 class="plain">Contents</h2>'
            '<table class="contents" width="60%" cellpadding="3" '
            f'cellspacing="0">{"".join(rows)}</table>')


def _sub(title: str, breaks: set[str] | None = None) -> str:
    """
    A sub-heading, marked to start a fresh page when it was left stranded.

    `report._heading` does this for a section's h2, and `report._orphan_headings`
    looks at h3s as well — but a heading with no `break` class cannot be
    pushed, so the reflow pass would find the stranded heading, add it to
    `breaks`, and change nothing. Every h3 here introduces a table, and a
    table heading alone at the foot of a page is the thing this document has
    most of. `infusion_report._sub` is the same three lines for the same
    reason; a shared one would belong in `report`, which another change is in
    the middle of.
    """
    css = ' class="break"' if breaks and title in breaks else ""
    return f"<h3{css}>{_escape(title)}</h3>"


def _provenance(component: Component,
                proposals: dict[str, FormulaProposal]) -> str:
    """
    Where this row's formula came from, or what could supply one.

    Three words at most, and measured. The first version wrote the derived
    formula into the cell — `the name would give C42H79NO13` — which wrapped
    to three lines, and a table row is as tall as its tallest cell: the
    141-component method's component table went from six printed pages to
    eight and the whole document from fifteen to seventeen, for a formula
    the Formulas section already tabulates with both masses beside it.
    """
    if component.formula:
        if component.lm_id:
            return f"LIPID MAPS {component.lm_id}"
        return "the method"
    proposal = proposals.get(component.name)
    if proposal is None:
        return "—"
    return "the name" if proposal.agrees else "refused"


def _components(title: str, report: MethodReport,
                breaks: set[str] | None = None) -> str:
    """
    The table as the method declares it, with the flagged rows marked.

    A column of check names would be wider than everything else put
    together, so a flagged row carries a mark and the section that follows
    names every component under every check it belongs to.
    """
    proposals = {p.component.name: p for p in
                 report.formulas.derivable
                 + [r.proposal for r in report.formulas.refusals]}
    rows = []
    serious = warned = 0
    for component in report.components:
        severity = report.severity(component.name)
        if severity == SERIOUS:
            mark, serious = SERIOUS_MARK, serious + 1
        elif severity:
            mark, warned = WARNING_MARK, warned + 1
        else:
            mark = ""
        name = _escape(component.name)
        if mark:
            # a non-breaking space, so the mark never wraps onto a line of
            # its own under a name the column is too narrow for
            name += f'&nbsp;<span class="{"bad" if severity == SERIOUS else "mark"}">' \
                    f'{mark}</span>'
        rows.append([
            name, _escape(component.group or "—"),
            _number(component.precursor, 4), _number(component.fragment, 4),
            _escape(component.adduct or "—"),
            _escape(component.formula or "—"),
            (f"{component.rt:.2f} ± {component.rt_halfwidth:g}"
             if component.rt is not None else "—"),
            ("yes" if component.is_internal_standard
             else _escape(component.internal_standard or "—")),
            ("—" if component.min_response is None
             else _number(component.min_response, 0)),
            _escape(_provenance(component, proposals)),
        ])
    legend = (
        f'<p class="foot"><span class="bad">{SERIOUS_MARK}</span> '
        f'{serious:,} row(s) carry a serious finding, '
        f'<span class="mark">{WARNING_MARK}</span> {warned:,} a warning; '
        f'the checks that flagged them are named in the next section. '
        f'<b>IS</b> reads <i>yes</i> for an internal standard and otherwise '
        f'names the standard the row is normalised against. <b>Floor</b> is '
        f'the minimum response a standard has to give. <b>From</b> is where '
        f'the formula came from; the formulas the names would give, with '
        f'both masses, are in the Formulas section.</p>')
    return (_heading(title, breaks) + _table(
        ["Component", "Group", "Precursor", "Fragment", "Adduct", "Formula",
         "RT ± window", "IS", "Floor", "From"],
        rows, right={2, 3, 6, 8}, empty="The method has no valid components.",
        widths=["15%", "9%", "9%", "9%", "8%", "12%", "10%", "9%", "7%",
                "12%"]) + legend)


def _findings(title: str, report: MethodReport,
              breaks: set[str] | None = None) -> str:
    """
    Every finding, grouped by severity, with the count in the heading.

    The counts are of *findings*, not of components: one shared transition
    naming thirty-five components is one thing wrong with the method and
    thirty-five rows that inherit it, and a heading that said thirty-five
    would suggest thirty-five separate problems.
    """
    health = report.health
    parts = [_heading(title, breaks)]
    if health.sound:
        parts.append('<p class="empty">Nothing in the method contradicts '
                     'itself.</p>')
    for severity, label in ((SERIOUS, "Serious"), ("warning", "Warnings")):
        findings = (health.serious if severity == SERIOUS else health.warnings)
        if not findings:
            continue
        parts.append(_sub(f"{label} \u2014 {len(findings):,}", breaks))
        for finding in findings:
            parts.append(
                f'<p><b>{_escape(finding.summary)}</b> '
                f'<span class="aside">({_escape(finding.check)})</span></p>'
                f'<p class="foot">{_escape(finding.detail)}</p>'
                f'<p class="foot"><i>{_names(finding.components)}</i></p>')
    if health.skipped:
        parts.append(_sub(f"Not checked \u2014 {len(health.skipped):,}", breaks))
        for note in health.skipped:
            parts.append(f'<p class="foot">{_escape(note)}</p>')
        parts.append(
            '<p class="meta">A method that passes with half its checks unrun '
            'has not passed. Open an acquisition and build the report again.</p>')
    return "".join(parts)


def _formulas(title: str, report: MethodReport,
              breaks: set[str] | None = None) -> str:
    """
    What the table is made of: carried, derivable, refused, unreadable.

    The refusals are the section's reason for existing. A name and a mass
    that contradict each other mean one of the two is wrong, and the two do
    different work — the mass picks the acquisition channel, the formula is
    the true mass a recalibration corrects towards — so both numbers are
    printed and neither is chosen here.
    """
    formulas = report.formulas
    parts = [_heading(title, breaks)]
    total = len(report.components)
    parts.append(
        f'<p>{len(formulas.carried):,} of {total:,} component(s) carry a '
        f'formula. Reading the lipid shorthand in the names of the rest would '
        f'fill {len(formulas.derivable):,} more, leaving '
        f'{len(formulas.missing):,} with none. Nothing was written: this is '
        f'what <i>Fill formulas from names</i> would do, run over copies.</p>')
    if formulas.derivable:
        rows = [[_escape(p.component.name), _escape(p.formula),
                 _escape(p.source), _number(p.theoretical, 4),
                 _number(p.written, 4),
                 "—" if p.error_ppm is None else f"{p.error_ppm:+,.1f}"]
                for p in formulas.derivable]
        parts.append(_sub("Derivable from the name", breaks))
        parts.append(_table(
            ["Component", "Formula", "Source", "Formula m/z", "Written",
             "Δ ppm"], rows, right={3, 4, 5},
            widths=["22%", "18%", "18%", "14%", "14%", "14%"]))
    if formulas.refusals:
        rows = []
        for repair in formulas.refusals:
            rows.append([
                _escape(repair.component.name), _escape(repair.formula),
                _escape(repair.source), _number(repair.theoretical, 4),
                _number(repair.written, 4),
                f"{repair.difference * 1000:+,.1f}",
                "—" if repair.error_ppm is None
                else f"{repair.error_ppm:+,.1f}",
                "the name" if repair.whole_dalton else "the mass",
            ])
        parts.append(_sub(f"Refused \u2014 {len(formulas.refusals):,}", breaks))
        parts.append(
            '<p class="foot">The formula\'s mass against the one the method '
            'writes. Under half a dalton the two are one compound written to '
            'fewer places and the mass is the thing to repair; a whole dalton '
            'or more apart they are two different compounds, and since the '
            'instrument acquired the mass as written, the likelier error is '
            'the name. <i>Repair precursors…</i> in the Method workspace puts '
            'the question row by row and offers both answers.</p>')
        parts.append(_table(
            ["Component", "Formula", "Source", "Formula m/z", "Written",
             "Δ mDa", "Δ ppm", "Likelier error"], rows,
            right={3, 4, 5, 6},
            widths=["18%", "15%", "14%", "12%", "12%", "10%", "10%", "9%"]))
    if formulas.underivable:
        parts.append(
            f'<p class="foot">{len(formulas.underivable):,} name(s) are not '
            f'lipid shorthand and nothing could be read from them: '
            f'<i>{_names(c.name for c in formulas.underivable)}</i>.</p>')
    return "".join(parts)


def _lock(title: str, report: MethodReport,
          breaks: set[str] | None = None) -> str:
    """
    The standards that could anchor a mass axis, and why that is only could.

    A method can say a standard has a formula and an adduct, which is what a
    lock mass needs to have a true mass at all. It cannot say the standard
    measures that mass: `mass_drift` has to find the same ion in most
    injections and `recalibrate.lock_mass_refusal` has to find it near where
    the formula puts it. Both of those need a batch, and saying so is the
    point of this section.
    """
    candidates = report.lock_masses
    parts = [_heading(title, breaks)]
    standards = report.internal_standards
    usable = [c for c in candidates if c.usable]
    parts.append(
        f'<p>{len(usable):,} of {len(standards):,} internal standard(s) carry '
        f'both a formula and an adduct, so a true mass can be computed for '
        f'them. A written precursor cannot stand in: one typed to a single '
        f'decimal is good to a few hundred parts per million, which is a '
        f'hundred times the error a recalibration corrects.</p>')
    rows = []
    for candidate in candidates:
        rows.append([
            _escape(candidate.component.name), _escape(candidate.formula),
            _number(candidate.neutral, 4),
            _escape(candidate.adduct or "—")
            + ("" if candidate.declared else
               ' <span class="mark">*</span>' if candidate.adduct else ""),
            _number(candidate.exact, 4), _number(candidate.written, 4),
            "—" if candidate.error_ppm is None
            else f"{candidate.error_ppm:+,.1f}",
        ])
    parts.append(_table(
        ["Standard", "Formula", "Neutral mass", "Adduct", "Exact m/z",
         "Written", "Δ ppm"], rows, right={2, 4, 5, 6},
        empty="No internal standard carries a formula, so the method offers "
              "no lock mass at all.",
        widths=["20%", "16%", "14%", "14%", "13%", "12%", "11%"]))
    unusable = [c for c in candidates if not c.usable]
    if any(not c.declared and c.adduct for c in candidates):
        parts.append(
            '<p class="foot"><span class="mark">*</span> the method declares '
            'no adduct for this standard and the one shown was read off its '
            'written precursor. An adduct guessed from a rounded mass is a '
            'guess: type the adduct into the method.</p>')
    for candidate in unusable:
        parts.append(f'<p class="foot">{_escape(candidate.component.name)}: '
                     f'{_escape(candidate.note)}</p>')
    parts.append(
        f'<p class="meta">Being a candidate is not being a lock mass. A '
        f'standard qualifies only across a batch: its precursor has to be '
        f'measurable in the survey scan, the same ion has to be measured in '
        f'every injection, and the ion has to sit within '
        f'{MAX_LOCK_ERROR_PPM:.0f} ppm of the mass its own formula names. '
        f'None of those three can be read from a method — process a '
        f'batch and see Analytics ▸ Mass drift.</p>')
    return "".join(parts)


def _acquisition(title: str, report: MethodReport,
                 breaks: set[str] | None = None) -> str:
    """Which channel would serve each component, and what the survey covers."""
    acquisition = report.acquisition
    parts = [_heading(title, breaks)]
    if acquisition is None:
        return "".join(parts + ['<p class="empty">No sample was open.</p>'])
    own, survey = acquisition.on_own_channel, acquisition.on_survey
    unserved = acquisition.unserved
    parts.append(
        f'<p>{_escape(acquisition.name or acquisition.file or "The open sample")}'
        f' was acquired on {acquisition.channels:,} channel(s). Of '
        f'{len(acquisition.served):,} component(s), {len(own):,} are served by '
        f'a channel of their own, {len(survey):,} fall back to a survey scan '
        f'and {len(unserved):,} are served by nothing that was acquired. A '
        f'component matched to a survey scan is extracted from a full scan '
        f'rather than from its transition, which is a different measurement '
        f'with a different background.</p>')
    if acquisition.survey_ranges:
        parts.append(
            f'<p class="foot">The survey scans cover '
            f'{_escape(", ".join(acquisition.survey_ranges))} '
            f'— {len(acquisition.outside_survey):,} precursor(s) lie '
            f'outside them: <i>{_names(acquisition.outside_survey)}</i>.</p>')
    else:
        parts.append('<p class="foot">This acquisition has no survey scan, so '
                     'no precursor can be measured accurately, annotated from '
                     'LIPID MAPS, or followed for drift.</p>')
    rows = [[_escape(s.component),
             _escape(s.channel) if s.channel else
             '<span class="bad">nothing serves it</span>',
             "—" if s.index is None else f"{s.index:,}",
             "survey" if s.survey else ("channel" if s.channel else "—"),
             "—" if s.gap is None else f"{s.gap:.4f}"]
            for s in acquisition.served]
    parts.append(_sub("Channel per component", breaks))
    parts.append(_table(
        ["Component", "Channel", "#", "Kind", "Δ Da"], rows,
        right={2, 4}, widths=["30%", "34%", "8%", "13%", "15%"]))
    return "".join(parts)


def _schedule(title: str, report: MethodReport,
              breaks: set[str] | None = None) -> str:
    """The scheduled acquisition the method implies, and its busiest moment."""
    schedule = report.schedule
    parts = [_heading(title, breaks)]
    if schedule is None:
        return "".join(parts + ['<p class="empty">Nothing to schedule.</p>'])
    parts.append(f'<p>{_escape(schedule.summary())}</p>')
    parts.append(f'<p class="foot">{_escape(report.cycle_basis)}</p>')
    if not schedule.slots:
        return "".join(parts)
    rows = [
        ["Transitions with a time", f"{len(schedule.slots):,}"],
        ["Left out for having none", f"{len(schedule.unscheduled):,}"],
        ["Most acquired at once", f"{schedule.busiest:,}"
         + (f" at {schedule.busiest_at:.2f} min"
            if schedule.busiest_at is not None else "")],
        ["Target cycle", f"{schedule.target_cycle:.1f} s"],
        ["Dwell each at that moment",
         "—" if schedule.dwell_ms is None
         else f"{schedule.dwell_ms:.0f} ms"],
        ["Dwell floor", f"{schedule.min_dwell_ms:.0f} ms"],
        ["Shortest cycle that moment allows",
         "—" if schedule.achievable_cycle is None
         else f"{schedule.achievable_cycle:.1f} s"],
        ["Widest window",
         "—" if schedule.widest_window is None
         else f"±{schedule.widest_window / 2:.2f} min"],
    ]
    parts.append(_table(None, rows, right={1},
                        widths=["55%", "45%"]))
    if schedule.busiest_at is not None:
        at = schedule.busiest_at
        together = sorted(slot.component for slot in schedule.slots
                          if slot.start <= at <= slot.end)
        parts.append(
            f'<p class="foot">Acquired together at {at:.2f} min: '
            f'<i>{_names(together, BUSIEST_LISTED)}</i>. These are what has '
            f'to be thinned, or their windows narrowed where they overlap, '
            f'for a shorter cycle.</p>')
    if schedule.unscheduled:
        parts.append(
            f'<p class="foot">{len(schedule.unscheduled):,} component(s) have '
            f'no retention time and cannot be scheduled: '
            f'<i>{_names(sorted(schedule.unscheduled))}</i>.</p>')
    parts.append(
        '<p class="meta">The table itself is written by <i>Export '
        'schedule…</i> in the Method workspace, as a CSV whose columns map '
        'onto the vendor\'s. In Analyst the detection window is one '
        'method-wide setting rather than a column: the widest window above is '
        'the one to type.</p>')
    return "".join(parts)


def _closing(title: str, report: MethodReport,
             breaks: set[str] | None = None) -> str:
    """
    One paragraph, the sentences run together, and no badge.

    A known blemish, measured and left standing: on the real method this
    heading lands 146 units above the foot of page 14 — the heading itself
    fits, and not one line of the paragraph does, so Qt paints the whole
    paragraph on page 15 and the heading sits alone. `report._orphan_headings`
    does not call that stranded, because it asks whether the *following
    block* starts on a later page and this one starts, by the layout's
    arithmetic, on the same one; the rule it would need is whether the
    following block's first *line* fits. That rule belongs in the shared
    printer, not here, and this document is printed through it unchanged.
    """
    sentences = " ".join(_escape(sentence) for sentence in report.closing())
    return _heading(title, breaks) + f"<p>{sentences}</p>"


def build_html(report: MethodReport, title: str = "",
               contents: dict[str, int] | None = None,
               breaks: set[str] | None = None) -> str:
    """
    The whole thing as one HTML document.

    `contents` and `breaks` are what `report.print_document` works out for
    itself — None for no page column, `{}` to reserve one, the mapping on the
    final pass — so this document and the batch report are printed through
    the same code.
    """
    title = title or report.title
    order = [key for key in SECTIONS
             if key != "acquisition" or report.acquisition is not None]
    titles = {key: f"{number}. {SECTIONS[key]}"
              for number, key in enumerate(order, start=1)}
    builders = {"components": _components, "findings": _findings,
                "formulas": _formulas, "lock": _lock,
                "acquisition": _acquisition, "schedule": _schedule,
                "closing": _closing}
    parts = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'>",
             f"<title>{_escape(title)}</title>",
             f"<style>{_STYLE}</style></head><body>",
             _title_block(report, title),
             _contents(list(titles.values()), contents)]
    for key in order:
        parts.append(builders[key](titles[key], report, breaks))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(report: MethodReport, path: str | os.PathLike, **kwargs) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(report, **kwargs))
    return path


def write_pdf(report: MethodReport, path: str | os.PathLike, **kwargs) -> str:
    """The document on A4 portrait pages, through the batch report's printer."""
    title = kwargs.pop("title", "") or report.title
    return print_document(
        lambda contents, breaks: build_html(report, title=title,
                                            contents=contents, breaks=breaks),
        path, title)
