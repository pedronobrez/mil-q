"""
One compound, infused, on two or three pages: the document that goes into the
notebook when a standard is validated.

A batch report answers what a run measured. This answers something smaller and
older: *is this vial what the label says it is?* Somebody sprays a standard,
looks at the average of the whole run, checks that the precursor is where the
formula puts it, that the fragments are the ones the structure allows, and that
the spectrum matches the record they made of the same compound last month —
and then has to put something on paper. Screenshots do not say what the label
floor was, and a bare spectrum does not say what was checked.

What is here, and what is deliberately not
------------------------------------------

The report **sums what was checked and nothing else**. Every sentence of the
verdict comes from a measurement that was actually made in this session:

- the precursor, from `precursor.measure` — the survey scan, with the
  product-ion scan as the same-ion check; and where the acquisition has no
  survey at all, from the averaged product-ion spectrum itself, said so in
  those words. Nine real infusions to hand have **one channel each and no
  survey**, so that is the ordinary case rather than the exception;
- the fragments, from whatever was run in the LIPID MAPS tab — a database
  record, a drawing of one's own, or a formula and its neutral losses. `n of
  m`, where m is how many ions the prediction offered, so the reader can see
  the denominator;
- the library, from whatever `SpectralLibrary.search` returned — score,
  reverse, matched, Δ ppm, and the record's own provenance as it was written;
- the collision energy, where the record carries one and it is not this
  acquisition's. A spectrum measured at another energy has other fragments,
  and a score that is low for that reason is not a compound that failed.

There is **no pass/fail badge**, and there will not be one. Identity is a
judgement made from evidence by a person who knows what the vial was supposed
to hold; a green tick invites nobody to read the rest of the page. Where
nothing was run the verdict says exactly that: the report is then a spectrum
and a peak table, which is a fair description of it.

The unexplained peaks are listed on purpose. An explanation that accounts for
40% of a spectrum has said nothing about the other 60%, and the intense part
of that other 60% is where a co-infused impurity — or a wrong compound —
shows itself.

The picture and the tables
--------------------------

The spectrum is drawn through `spectra_compare`, at the label floor the pane
was left at, so what is named on paper is what was named on screen; it is
embedded as a data URI, so an exported HTML report is one file that can be
mailed. Where other infusions of the same compound are open — the same name
prefix, or the ones the analyst ticked — they are drawn head to tail against
this one on a page of their own, each with its cosine against this spectrum
taken by `library.match`, which is the same arithmetic a library search uses.

Everything above is built from plain values: a `SampleEntry`, a channel, an
`Explanation`, a `LibraryHit`. Nothing here reads a widget, so a report can be
built and checked with no window, which is what `tests/test_infusion_report.py`
does. `from_explorer` is the thin adapter that takes what the Explorer already
holds and calls the same builder.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from dataclasses import dataclass, field

import numpy as np

from . import infusion as _infusion
from . import margin as _margin
from . import precursor as _precursor
from . import purity as _purity
from . import spectra_compare
from . import unexplained as _unexplained
from .components import Component
from .explain import Explanation
from .infusion import (InfusionVerdict, NoiseFloor, ScanMask, average_stable,
                       format_counts, mask_for, noise_floor_for, run_range,
                       stable_scans, strongest_channel, verdict_for)
from .library import PEAK_TOLERANCE_PPM, LibraryHit, match
from .report import (IMAGE_WIDTH, _escape, _heading, _number, _table,
                     picture_palette, print_document, style_for)
from .samples import SampleEntry
from .spectra_compare import LABEL_MIN_RELATIVE, SpectrumComparison

#: at most this many peaks in the table under the spectrum. A product scan
#: averaged over a whole run has hundreds above any floor worth setting; a
#: table of hundreds is an appendix, not a page of a notebook.
PEAKS_LISTED = 25

#: how tall a peak has to be, against its own spectrum's base peak, to count
#: towards one infusion's score against another. `library.NOISE_SHARE`, the
#: floor a library search itself applies, rather than the drawing's label
#: floor: the label floor decides what is worth *naming* on a picture and at
#: 2% a spectrum that is nearly all precursor offers three peaks to score on.
SCORE_SHARE = 0.01

#: at most this many peaks of either spectrum are scored against the other.
SCORE_PEAKS = 200

#: how many times the document may be laid out again to pull a heading onto
#: the page of what it introduces. More than the batch report's three: a
#: picture cannot be split, so a page here can be a third empty and moving
#: one figure over strands the next — and a batch of infusions has a figure
#: every few paragraphs. Each pass costs one layout, not a re-render.
REFLOWS = 8

#: at most this many unexplained peaks are named. They are listed strongest
#: first, so the ones that matter are the ones printed.
UNEXPLAINED_LISTED = 10

#: how much further down than the printed label floor the peak list handed to
#: `unexplained.annotate` reaches. The floor decides what is *annotated*; the
#: pool is the evidence, and the carbon-13 satellite that separates one
#: composition from another is about a hundredth of the peak it belongs to
#: while the floor is a fiftieth of the base peak. Ten is the same ratio the
#: spectrum pane already uses between its label floor and its own peak pool.
ANNOTATION_POOL = 10

#: at most this many peaks go into that pool. Reading further costs nothing
#: to find and everything to search against, and a satellite below the
#: thousandth-strongest peak of an averaged infusion is noise.
ANNOTATION_POOL_PEAKS = 1000

#: at most this many matched fragments are tabulated, strongest first.
FRAGMENTS_LISTED = 40

#: the tolerance the mass-axis paragraph counts its before and after at. Not
#: the 20 ppm the ladder is *matched* in — that window is wide enough to
#: absorb the error being measured, so counting in it would show nothing —
#: but the 5 ppm the LIPID MAPS tab's own-structure box defaults to, which is
#: the tolerance somebody would actually judge an identification at.
LADDER_CHECK_PPM = 5.0

#: how wide the head-to-tail pictures are drawn, in the pixels of the ninety-
#: six dots to the inch that Qt's `width` attribute means — the same measure
#: the batch report's compared spectra use.
PICTURE_WIDTH = IMAGE_WIDTH

#: how far apart two energies have to be before the report says they differ.
#: Vendors write a nominal energy and a spread; a difference of a fraction of
#: an electronvolt is the same setting written twice.
ENERGY_TOLERANCE_EV = 0.5

#: the names a library record may carry its collision energy under, matched
#: whole and without regard to case. MassBank, NIST and MoNA each spell it
#: differently, so more than one is needed — but matching on what a name
#: *contains* is worse than useless here: `Ion_source` ends in "ce".
ENERGY_KEYS = frozenset({"ce", "energy", "collision_energy",
                         "collisionenergy", "collision"})

#: where a name stops being the compound and starts being the acquisition.
#: `CA-d4_TOFMSMS_Mix1` and `CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1` are the
#: same compound infused twice, and the part before the first separator is
#: what says so.
_NAME_SPLIT = re.compile(r"[_ ]")


def compound_of(name: str) -> str:
    """
    The compound a sample's name starts with.

    A file name in a folder of infusions is the compound and then the
    conditions: `CA-d4_TOFMSMS_Mix1`. The prefix is what makes two of them
    the same compound, and it is only ever a proposal — the dialog lets the
    analyst pick which infusions are compared, because a naming convention
    is not a measurement.
    """
    stem = os.path.splitext(str(name or "").strip())[0]
    first = _NAME_SPLIT.split(stem, 1)[0]
    return first or stem


# --------------------------------------------------------------------------- #
# what the method isolates, against what the name says it should
# --------------------------------------------------------------------------- #
#: at most this many other compounds are named as fitting one isolated
#: precursor, the rest counted rather than listed. Measured on the real
#: 141-component method with its formulas filled in, asked about each of its
#: own written precursors: 97 of 141 have nought or one fit, 30 have two,
#: nine have three, one has four and two have five — so four lists every fit
#: for 139 of the 141 and elides one for the other two. Isobars are ordinary
#: in lipidomics and a cell that names nine of them has stopped being an
#: answer.
MOST_FITS = 4


def labelled_formula(formula: str, *names: str) -> tuple[str, int, str]:
    """
    A formula with the labels its name declares but its formula does not.

    A d4 standard is bought, named and filed as `CA-d4`, and the formula
    beside it is usually the unlabelled one: nothing in a component table
    has a column for four deuteriums. The name has them, and
    `chemistry.split_labels` reads a trailing `-d4`. Without this the
    arithmetic is out by 4.025 Da and no adduct fits the written precursor
    at all — which is a true statement about the formula as typed and a
    useless one about the compound.

    A formula that already spells its labels out is left alone: it has said
    what it is. Returns the formula, how many labels were added, and the
    clause that says so.
    """
    from .chemistry import (FormulaError, format_formula, parse_formula,
                            split_labels)

    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return formula, 0, ""
    if counts.get("D"):
        return formula, 0, ""
    for written in names:
        _stem, labels = split_labels(written or "")
        if labels and counts.get("H", 0) >= labels:
            counts["D"] = labels
            counts["H"] -= labels
            return (format_formula(counts), labels,
                    f", with the {labels} label(s) {written} is named for")
    return formula, 0, ""


@dataclass(frozen=True)
class Fit:
    """One compound and adduct whose mass is the precursor a method isolates."""

    name: str
    formula: str
    adduct: str
    mz: float
    error_ppm: float
    #: where the candidate came from, in words: the component table, your
    #: library, or the name on the file. A fit is worth exactly as much as
    #: the list it was found in, so the list travels with it
    source: str = ""

    def __str__(self) -> str:
        adduct = f" {self.adduct}" if self.adduct else ""
        return f"{self.name}{adduct} ({self.mz:.4f}, {self.error_ppm:+.1f} ppm)"


@dataclass(frozen=True)
class Isolation:
    """One product-ion channel: the precursor it isolates, and what fits it."""

    channel: int = 0
    channel_name: str = ""
    precursor: float = 0.0
    start_mass: float = 0.0
    end_mass: float = 0.0
    polarity: str = ""
    collision_energy: float | None = None
    #: how far a candidate could sit and still be counted, in daltons
    tolerance: float = 0.0
    #: adducts of the compound the file name proposes that fit this precursor
    named: tuple[Fit, ...] = ()
    #: everything else that fits, the component table before the library
    others: tuple[Fit, ...] = ()
    #: how many fits there were beyond the ones listed
    more: int = 0

    @property
    def agrees(self) -> bool:
        """Does the name's own compound have an adduct at this precursor?"""
        return bool(self.named)

    @property
    def fit(self) -> Fit | None:
        """The best of the other compounds that fit, or None."""
        return self.others[0] if self.others else None

    @property
    def window(self) -> str:
        return f"{self.start_mass:g}–{self.end_mass:g}"

    def __str__(self) -> str:
        return f"{self.precursor:g} over {self.window}"


@dataclass(frozen=True)
class IsolationVerdict:
    """
    Whether the compound a file is named after is the one its method isolates.

    The name is a proposal and the method is a measurement, and this is the
    arithmetic between them: the compound the name resolves to, its formula,
    and every adduct of that formula against the precursor each product-ion
    channel actually isolates. Where the name does not fit, the same
    precursor is offered to the component table and to the library of one's
    own, so the answer is not only *not this* but, where anything knows,
    *this instead*.

    Nothing here reads a spectrum. It compares two numbers that were both
    written down before the vial was sprayed, which is why it can be shown
    beside a file the moment it is opened.
    """

    #: the compound `compound_of` proposed from the file name
    proposed: str = ""
    #: what that name resolved to, labels included
    formula: str = ""
    #: in words: the standards table, LIPID MAPS, the lipid shorthand
    resolved_from: str = ""
    labels: int = 0
    isolations: tuple[Isolation, ...] = ()
    #: why nothing could be judged, when nothing could
    note: str = ""
    #: the same in a few words, for the cell the sentence will not fit in.
    #: Written where the note is written rather than cut out of it: a reason
    #: truncated at whatever punctuation happens to come first is a reason
    #: that changes meaning when somebody rewords the sentence
    brief: str = ""

    def __bool__(self) -> bool:
        return self.judged

    @property
    def judged(self) -> bool:
        return bool(self.formula and self.isolations)

    @property
    def agrees(self) -> bool:
        """Every product-ion channel isolates an adduct of the named compound."""
        return self.judged and all(i.agrees for i in self.isolations)

    @property
    def disagrees(self) -> bool:
        """No product-ion channel does. A method with several channels where
        only some fit is neither: it says so per channel instead."""
        return self.judged and not any(i.agrees for i in self.isolations)

    @property
    def fit(self) -> Fit | None:
        """The compound the method fits instead, where anything fits."""
        for isolation in self.isolations:
            if isolation.fit is not None:
                return isolation.fit
        return None

    # -- in words ------------------------------------------------------------- #
    def sentence(self) -> str:
        """
        What the name and the method say about each other, in one sentence.

        The sentence that goes on the report, into the tooltip and into the
        warning the shell puts up when a file is opened. It never says a file
        is wrong: it says what the name proposed, what the method isolates,
        and whether the two are the same arithmetic.
        """
        if not self.judged:
            return self.note
        joined = "; ".join(self._clause(i) for i in self.isolations)
        conjunction = "and" if self.agrees else "but"
        return (f"The file is named {self.proposed} {conjunction} the method "
                f"isolates {joined}.")

    def _clause(self, isolation: Isolation) -> str:
        """One channel's half of the sentence."""
        if isolation.agrees:
            fit = isolation.named[0]
            return (f"{isolation.precursor:g}, which is {fit.adduct} of "
                    f"{self.formula} ({fit.mz:.4f}, {fit.error_ppm:+.1f} ppm)")
        return (f"{isolation}, which is no adduct of {self.formula} within "
                f"±{isolation.tolerance:g} Da; it fits "
                f"{self._fits_text(isolation)}")

    @staticmethod
    def _fits_text(isolation: Isolation) -> str:
        if not isolation.others:
            return "nothing in the component table or the library"
        listed = ", ".join(f"{fit} from {fit.source}"
                           for fit in isolation.others)
        if isolation.more:
            listed += f", and {isolation.more} other(s)"
        return listed

    def column(self) -> str:
        """
        The same answer short enough for a cell, with the reason in the
        tooltip. A table column is a few characters wide and the sentence is
        a sentence; what has to survive the width is the precursor and
        whether it is the compound on the label.
        """
        if not self.judged:
            return self.brief or "not checked"
        parts = []
        for isolation in self.isolations:
            if isolation.agrees:
                fit = isolation.named[0]
                parts.append(f"{isolation.precursor:g} = {fit.adduct} of "
                             f"{self.proposed}")
            elif isolation.fit is not None:
                fit = isolation.fit
                parts.append(f"{isolation.precursor:g} = {fit.adduct} of "
                             f"{fit.name}, not {self.proposed}")
            else:
                parts.append(f"{isolation.precursor:g} — no adduct of "
                             f"{self.formula}, nothing fits")
        return "; ".join(parts)


def _library_fits(library, precursor: float, tolerance: float,
                  sign: int | None) -> list[Fit]:
    """
    Records of the analyst's own library whose precursor is this one.

    The record's **formula and adduct** where it carries them and the typed
    `PrecursorMZ` otherwise, which is `LibraryEntry.exact_precursor`'s whole
    reason for existing. The typed value is the coarse filter — the two agree
    to under a part per million in 96.8% of a real library — so a record far
    away is skipped before its formula is ever parsed, which is what keeps
    this cheap enough to run on every channel of every file.
    """
    from .chemistry import mass_error_ppm

    out: list[Fit] = []
    for entry in getattr(library, "entries", ()) or ():
        written = entry.precursor
        if written is not None and abs(float(written) - precursor) > tolerance + 0.5:
            continue
        mz = entry.exact_precursor
        if mz is None:
            mz = written
        if mz is None or abs(float(mz) - precursor) > tolerance:
            continue
        polarity = entry.polarity
        if sign is not None and polarity is not None and polarity != sign:
            continue
        out.append(Fit(name=entry.name, formula=entry.formula,
                       adduct=entry.precursor_type, mz=float(mz),
                       error_ppm=mass_error_ppm(precursor, float(mz)),
                       source="your library"))
    return out


def _component_fits(components, precursor: float, polarity) -> list[Fit]:
    """Components of the method whose formula has an adduct at this precursor."""
    from .chemistry import adducts_matching

    out: list[Fit] = []
    for component in components or ():
        written = str(getattr(component, "formula", "") or "")
        if not written:
            continue
        name = str(getattr(component, "name", "") or "")
        formula, _labels, _note = labelled_formula(written, name)
        for match_ in adducts_matching(formula, precursor, polarity or None):
            if match_.within:
                out.append(Fit(name=name or formula, formula=formula,
                               adduct=match_.name, mz=match_.mz,
                               error_ppm=match_.error_ppm,
                               source="the component table"))
    return out


def resolution_is_exact(resolved) -> bool:
    """
    Did the name resolve to *that* compound, or merely to one containing it?

    `lipidmaps.find_by_name` is a substring search, which is the right
    behaviour for somebody typing into a box and the wrong one for a check
    that fires by itself on every file opened. Measured against the installed
    LMSD: `PC` answers *PCTR3*, `CE` answers *cedrol*, `Cer` answers
    *Cerasin* and `TESTOL` answers *testolactone* — four sample names of the
    most ordinary kind, each resolved to a compound nobody was infusing, and
    each of them would then have contradicted whatever the method isolated.

    So a LIPID MAPS resolution counts only when the record's own name,
    abbreviation or LM_ID **is** the name, punctuation and case aside. The
    standards table is an exact key lookup and the lipid shorthand is parsed
    rather than searched, so both are exact by construction — and they are
    re-derived here rather than read off `NamedCompound.source`, whose
    wording is prose.
    """
    from .chemistry import formula_from_name, standard_named

    if resolved is None:
        return False
    compound = resolved.compound
    if standard_named(compound) is not None or formula_from_name(compound):
        return True
    record = resolved.record
    if record is None:
        return False
    want = _flat(compound)
    return any(_flat(getattr(record, field, "")) == want
               for field in ("name", "abbrev", "lm_id"))


def _isolation_for(channel, proposed: str, formula: str, components,
                   library) -> Isolation:
    """One product-ion channel measured against a formula and two lists."""
    from .chemistry import (ADDUCT_MATCH_DA, adducts_matching, polarity_sign)
    from .lipidmaps import mass_precision

    info = channel.info
    precursor = float(info.precursor)
    polarity = str(getattr(info, "polarity", "") or "")
    # `chemistry.adducts_matching`'s own tolerance, made explicit here so the
    # library half of the answer is asked the same question as the formula
    # half: `ADDUCT_MATCH_DA`, widened where the precursor was typed to fewer
    # places than that — `647.5` is known to ±0.05 and nothing closer can be
    # asked of it, while `430.35`'s own ±0.005 is finer and 0.05 stands
    tolerance = max(ADDUCT_MATCH_DA, mass_precision(precursor))
    named = tuple(
        Fit(name=proposed, formula=formula, adduct=m.name, mz=m.mz,
            error_ppm=m.error_ppm, source="the name on the file")
        for m in adducts_matching(formula, precursor, polarity or None)
        if m.within)
    others = (_component_fits(components, precursor, polarity)
              + _library_fits(library, precursor, tolerance,
                              polarity_sign(polarity) if polarity else None))
    others.sort(key=lambda fit: abs(fit.error_ppm))
    return Isolation(
        channel=int(info.index), channel_name=str(info.name or ""),
        precursor=precursor, start_mass=float(info.start_mass),
        end_mass=float(info.end_mass), polarity=polarity,
        collision_energy=info.collision_energy, tolerance=tolerance,
        named=named, others=tuple(others[:MOST_FITS]),
        more=max(len(others) - MOST_FITS, 0))


def what_the_method_isolates(sample, components=(), library=None,
                             name: str = "") -> IsolationVerdict:
    """
    Whether the compound in a file's name is the one its method isolates.

    `sample` is any reader's sample; `name` is the file's name, since a
    `.wiff` written by a manual acquisition calls its own sample `sample` and
    the compound is only ever in the file name. `components` is the method's
    table and `library` the analyst's own `SpectralLibrary`, both optional
    and both only ever consulted about a precursor the name does not fit —
    an answer of *not this, and nothing here knows what* is still an answer,
    and a much better one than silence.

    Every reason for not judging is returned rather than raised: a name
    nothing recognises, an acquisition with no product-ion channel, a
    formula that will not parse. The verdict then carries `note` and
    `judged` is False, because "the name could not be checked" and "the name
    is wrong" are different findings and a program that confuses them is
    worse than one that says neither.
    """
    from .chemistry import FormulaError, parse_formula
    from .explain import resolve_name

    written = str(name or getattr(sample, "name", "") or "")
    proposed = compound_of(written)
    if not proposed:
        return IsolationVerdict(note="the file has no name to propose a "
                                     "compound from",
                                brief="no name")
    channels = [c for c in getattr(sample, "channels", [])
                if getattr(c.info, "precursor", None) is not None]
    resolved = resolve_name(proposed)
    if resolved is None or not resolution_is_exact(resolved):
        near = ("" if resolved is None else
                f" — the nearest is {resolved.formula}, which is a compound "
                f"whose name merely contains it and not the compound itself")
        return IsolationVerdict(
            proposed=proposed,
            note=f"nothing knows the name {proposed} exactly: not the "
                 f"standards table, not LIPID MAPS and not the lipid "
                 f"shorthand, so there is no formula to check the method "
                 f"against{near}",
            brief=f"{proposed} is not a compound this knows")
    # the labels the name declares and the formula does not: `resolve_name`
    # answers `CA-d4` with cholic acid's own C24H40O5 and a count of four,
    # and four deuteriums are 4.025 Da — the difference between an adduct
    # that fits the written precursor and one that misses every one of them
    formula, labels, _note = labelled_formula(resolved.formula, proposed)
    try:
        parse_formula(formula)
    except (FormulaError, ValueError):
        return IsolationVerdict(
            proposed=proposed,
            note=f"{proposed} resolves to {formula!r}, which is not a "
                 f"formula this can read",
            brief=f"{formula} is not a readable formula")
    if not channels:
        return IsolationVerdict(
            proposed=proposed, formula=formula,
            resolved_from=resolved.source, labels=labels,
            note="this acquisition has no product-ion channel, so there is "
                 "no isolated precursor to check the name against",
            brief="nothing is isolated")
    return IsolationVerdict(
        proposed=proposed, formula=formula, resolved_from=resolved.source,
        labels=labels,
        isolations=tuple(
            _isolation_for(c, proposed, formula, components, library)
            for c in channels))


def name_disagreements(entries, components=(), library=None) -> list[str]:
    """
    One sentence per open infusion whose name and method disagree.

    What the shell puts up when a file is opened, and nothing else: an
    acquisition that is not an infusion is not asked (a chromatographic run
    is named after a sample, not a compound), a name nothing recognises is
    not a disagreement, and a method that isolates an adduct of the named
    compound says nothing at all.
    """
    said: list[str] = []
    for entry in entries or ():
        sample = getattr(entry, "sample", None)
        if sample is None:
            continue
        try:
            if not verdict_for(sample):
                continue
            verdict = what_the_method_isolates(
                sample, components, library,
                name=str(getattr(entry, "name", "") or ""))
        except Exception:               # a reader that cannot say
            continue
        if verdict.disagrees:
            said.append(f"{entry.name}: {verdict.sentence()}")
    return said


def energy_of(hit_or_entry) -> float | None:
    """
    The collision energy a library record carries, or None.

    The value is not always a number: MassBank writes `35 % (nominal)` and
    `40 eV`, so the first number in it is taken and the units around it
    ignored — which is the only thing that can be done without a table of
    every vendor's spelling, and is why the report prints the record's field
    as written beside the figure it compares.
    """
    entry = getattr(hit_or_entry, "entry", hit_or_entry)
    fields = getattr(entry, "fields", None) or {}
    for key, value in fields.items():
        flat = str(key).strip().lower().replace(" ", "_")
        if flat not in ENERGY_KEYS:
            continue
        found = re.search(r"[-+]?\d*\.?\d+", str(value))
        if found:
            try:
                return float(found.group())
            except ValueError:
                continue
    return None


# --------------------------------------------------------------------------- #
# what is held
# --------------------------------------------------------------------------- #
@dataclass
class Compared:
    """Another infusion of the same compound, drawn against this one."""

    label: str
    comparison: SpectrumComparison
    #: cosine over everything both spectra hold
    score: float = 0.0
    #: cosine asking only whether the other spectrum's peaks are in this one
    reverse: float = 0.0
    matched: int = 0
    of_other: int = 0
    #: how it was acquired, where the file says: collision energy, scans
    note: str = ""


@dataclass
class InfusionReport:
    """One compound, one infusion, and everything that was checked about it."""

    compound: str = ""
    # -- the header ---------------------------------------------------------- #
    file: str = ""
    sample: str = ""
    instrument: str = ""
    polarity: str = ""
    channel: str = ""
    #: the experiment's own name — `TOF PI`, `TOF MS` — where `channel` is
    #: the whole label with the precursor and the range in it. A table of
    #: many needs the short one and the document's header the long one.
    channel_name: str = ""
    #: the precursor as the method wrote it, to the decimals it was typed with
    written_precursor: float | None = None
    collision_energy: float | None = None
    scans: int = 0
    #: which scans went into the average and which the spray lost. None where
    #: nothing measured it — an older project, or a channel that would not
    #: read — and the report then says the scan count and nothing about it.
    mask: ScanMask | None = None
    #: the average was taken over every scan, unstable ones included, because
    #: the reader asked for it
    unstable_included: bool = False
    rt_range: tuple[float, float] | None = None
    adduct: str = ""
    verdict: InfusionVerdict | None = None
    #: whether the compound the file is named after is the one the method
    #: isolates — `what_the_method_isolates`, or None where nobody asked
    isolation: IsolationVerdict | None = None
    # -- the accurate precursor ---------------------------------------------- #
    #: `precursor.measure`, which reads the survey scan
    measurement: _precursor.PrecursorMeasurement | None = None
    #: the precursor read off the averaged product-ion spectrum itself — its
    #: mass and its height — for an acquisition with no survey scan to read it
    #: from. A different measurement, and the verdict names it as one.
    survivor: tuple[float, float] | None = None
    #: why there is no survivor, when there is not: a window that held
    #: nothing, or one that held too little to be a measurement
    survivor_note: str = ""
    #: the noise floor of this average, measured off the acquisition by
    #: `infusion.noise_floor`. None where it could not be measured at all,
    #: and `floor` then falls back to the fixed `precursor.MIN_INTENSITY`.
    noise_floor: NoiseFloor | None = None
    # -- what the survey says about the adduct -------------------------------- #
    #: the formula the adduct was weighed against, labels included
    formula: str = ""
    #: `chemistry.adduct_evidence` for every candidate adduct, best supported
    #: first. Empty where there was no survey to read, which is not the same
    #: as a survey that showed nothing.
    evidence: list = field(default_factory=list)
    #: the sentence the header cell abbreviates: why the adduct is or is not
    #: confirmed
    adduct_note: str = ""
    adduct_confirmed: bool = False
    #: the survey channel it was read from, as the file labels it
    survey_channel: str = ""
    # -- the spectrum -------------------------------------------------------- #
    #: the averaged spectrum, drawn for paper; one trace
    spectrum: SpectrumComparison | None = None
    label_floor: float = LABEL_MIN_RELATIVE
    # -- the mass axis ------------------------------------------------------- #
    #: the correction fitted from this infusion's own precursor ladder, or
    #: the refusal that says why there is none. Held whether or not it was
    #: applied: a vial that was looked at and left alone is a finding.
    correction: object | None = None
    #: whether the spectrum above is on the corrected axis. False with a
    #: correction present means the switch was off — the fit stands and the
    #: masses printed are the instrument's own.
    recalibrated: bool = False
    #: the same explanation run on the axis as measured, for the before and
    #: after. Only where a correction was applied; None otherwise.
    raw_explanation: Explanation | None = None
    #: the formula and adduct the ladder was predicted from, and where they
    #: came from. Kept so the paragraph can count the ladder's own ions
    #: before and after without asking the session a second time.
    axis_subject: "AxisSubject | None" = None
    # -- what was run -------------------------------------------------------- #
    explanation: Explanation | None = None
    #: what the prediction was made from, in words — the sentence that says
    #: what the denominator of "n of m" counts
    basis: str = ""
    deuterium: int = 0
    #: the isotopic purity of a labelled standard, where the compound carries
    #: labels and an ion could be identified to read the envelope at. Always
    #: present when it was attempted, `usable` or not: a refusal is the
    #: measurement's own finding and belongs on the page beside the rest
    purity: "_purity.Purity | None" = None
    hit: LibraryHit | None = None
    #: what the compound explains against what its nearest impostors explain
    #: — `margin.cross_validate`. None where nothing was explained, or where
    #: there was no database, no precursor or no neighbour to contrast with;
    #: the object then says which in its own words.
    margin: "_margin.Margin | None" = None
    library: str = ""
    compared: list[Compared] = field(default_factory=list)
    #: `energy.EnergyRecommendation.paragraph()` for this compound, where the
    #: chosen rows hold more than one collision energy of it. Written by
    #: `prepare_documents` rather than measured here: it is arithmetic over
    #: the *other* infusions of the same compound, which one report has no
    #: view of, and a compound infused once has none to write.
    energy_advice: str = ""
    taken: _dt.datetime = field(default_factory=_dt.datetime.now)
    #: what has already been picked off the averaged trace — the scoring
    #: peaks, the listed ones, the annotation pool, the centroids — keyed on
    #: the picking and holding the trace it was picked from, so a trace put
    #: in its place is picked afresh and a trace still standing is picked
    #: once. Measured before this existed: one report of nine infusions
    #: centroided each average five times and scored it three. Never saved.
    _picked: dict = field(default_factory=dict, repr=False, compare=False)

    # -- derived ------------------------------------------------------------- #
    @property
    def title(self) -> str:
        return self.compound or self.sample or "Infusion"

    @property
    def named_compound(self) -> str:
        """
        The compound this is, once the method has had its say.

        `compound_of` reads a file name, which is a proposal: somebody typed
        it, and on a manual acquisition it is the only place a compound is
        written at all. The method's isolated precursor is a measurement of
        the same question, so where the two disagree this reads the compound
        the method fits and flags the name — and where nothing fits, it says
        the name is not confirmed rather than repeating it as though it were.
        """
        verdict = self.isolation
        if verdict is None or not verdict.disagrees:
            return self.compound
        fit = verdict.fit
        if fit is not None:
            return f"{fit.name}, not {self.compound}"
        return f"not {self.compound}"

    @property
    def trace(self) -> spectra_compare.SpectrumTrace | None:
        traces = self.spectrum.traces if self.spectrum is not None else []
        return traces[0] if traces else None

    def peaks(self, most: int = PEAKS_LISTED) -> list[tuple[float, float]]:
        """
        The peaks of the averaged spectrum above the pane's label floor,
        strongest first.

        The floor is the one the drawing used, so the table and the picture
        name the same peaks — which is the whole reason the floor travels
        with the comparison rather than being a constant here.
        """
        return picked(self, most=most, min_relative=self.label_floor)

    def base_peak(self) -> tuple[float, float] | None:
        trace = self.trace
        return trace.base_peak if trace is not None else None

    @property
    def floor(self) -> float:
        """
        The height below which a peak of this average is noise.

        The measured one where there is a measurement, and the fixed
        `precursor.MIN_INTENSITY` where there is not. Read defensively: a
        report built by an older caller carries no measurement and still has
        to answer.
        """
        fixed = _precursor.MIN_INTENSITY
        value = getattr(self.noise_floor, "value", None)
        try:
            return float(value) if value is not None else fixed
        except (TypeError, ValueError):
            return fixed

    def unexplained(self, most: int = UNEXPLAINED_LISTED
                    ) -> list[tuple[float, float]]:
        """
        The intense peaks the explanation does not account for.

        Peaks under the measured noise floor are left out rather than listed:
        an explanation is not answerable for the background, and a list of
        unexplained noise reads as an explanation that failed.
        """
        if self.explanation is None:
            return []
        floor = self.floor
        left = self.explanation.unexplained(self.peaks(most=PEAKS_LISTED))
        return [p for p in left if float(p[1]) >= floor][:most]

    def annotations(self, most: int = UNEXPLAINED_LISTED) -> list:
        """
        The same peaks with what each of them might be — `unexplained.annotate`.

        The evidence is a peak list reaching `ANNOTATION_POOL` times further
        down than the printed floor, because the carbon-13 satellite that
        decides a composition is a hundredth of the peak it belongs to and
        the printed table starts at two per cent. Only the peaks above the
        floor are annotated; everything under it is there to be looked at.

        Cached: the sentence and the table both ask, and a constrained
        formula search is not free.
        """
        held = getattr(self, "_annotations", None)
        if held is not None and len(held) >= most:
            return held[:most]
        if self.explanation is None or self.spectrum is None:
            return []
        trace = self.trace
        if trace is None:
            return []
        pool = picked(self, most=ANNOTATION_POOL_PEAKS,
                      min_relative=max(self.label_floor / ANNOTATION_POOL, 1e-5))
        if not pool:
            return []
        formula = self.formula or getattr(self.explanation.record, "formula", "")
        rows = _unexplained.annotate(
            [mz for mz, _height in pool], [h for _mz, h in pool],
            self.explanation, formula,
            self.explanation.adduct or self.adduct, self.polarity,
            floor=self.label_floor, most=most)
        self._annotations = rows
        return rows

    def error_ppm(self) -> float | None:
        """How far the accurate precursor sits from the written one."""
        if self.written_precursor in (None, 0):
            return None
        if self.measurement is not None and self.measurement.found:
            return self.measurement.error_ppm
        if self.survivor is not None:
            return ((self.survivor[0] - self.written_precursor)
                    / self.written_precursor * 1e6)
        return None

    # -- the scans ----------------------------------------------------------- #
    def scans_line(self) -> str:
        """
        How many scans there were and how many were averaged, in one line.

        "473 scans, 464 averaged; 9 left out: 0.008 min; 1.069–1.099 min,
        8 scans" — the header's cell and the library record's comment read
        this, so a record and the paper beside it say the same thing.
        """
        mask = self.mask
        if mask is None or mask.n_scans == 0:
            return f"{self.scans:,}" if self.scans else "—"
        if self.unstable_included and mask.excluded:
            return (f"{mask.n_scans:,} scans, all averaged; "
                    f"{mask.excluded:,} unstable scan(s) kept on request: "
                    f"{mask.ranges}")
        return mask.summary()

    def scans_cell(self) -> str:
        """The scans column of a table of many: "464 of 473", or "473"."""
        mask = self.mask
        if mask is not None and mask.excluded and not self.unstable_included:
            return f"{mask.kept:,} of {mask.n_scans:,}"
        return f"{self.scans:,}" if self.scans else "—"

    def scans_averaged(self) -> int:
        """The scans the average was actually taken over."""
        mask = self.mask
        if mask is None or mask.n_scans == 0:
            return int(self.scans)
        return mask.n_scans if self.unstable_included else mask.kept

    def _scan_sentences(self) -> list[str]:
        mask = self.mask
        if mask is None or mask.n_scans == 0 or not mask.excluded:
            return []
        if self.unstable_included:
            return [f"{mask.excluded} scan(s) of {mask.n_scans} depart from "
                    f"the run's own level by more than "
                    f"{_infusion.SPRAY_JUMP:.0%} — {mask.ranges} — and were "
                    f"averaged in anyway, because *Include unstable scans* "
                    f"is on. The spectrum above is the whole run."]
        return [f"{mask.excluded} scan(s) of {mask.n_scans} were left out of "
                f"the average: {mask.ranges}. Each departs from the running "
                f"median of {_infusion.STABILITY_WINDOW} scans by more than "
                f"{_infusion.SPRAY_JUMP:.0%}, or follows one that does and "
                f"had not come back within {_infusion.SPRAY_RECOVERED:.0%} — "
                f"a spray that faltered, not a compound that changed. The "
                f"rest of the run repeats itself to "
                f"{mask.scatter:.1%} of its own level."]

    def energy_gap(self) -> tuple[float, float] | None:
        """This acquisition's energy and the record's, when they differ."""
        if self.hit is None or self.collision_energy is None:
            return None
        theirs = energy_of(self.hit)
        if theirs is None:
            return None
        if abs(theirs - float(self.collision_energy)) <= ENERGY_TOLERANCE_EV:
            return None
        return float(self.collision_energy), theirs

    # -- the verdict --------------------------------------------------------- #
    def sentences(self) -> list[str]:
        """
        What was checked, one sentence per check, and nothing else.

        Each sentence is a measurement or it is absent. There is no
        conclusion at the end because the conclusion is not this program's
        to draw: what a spectrum is worth depends on what the vial was
        supposed to hold, which is in somebody's notebook and not in the
        file.
        """
        said: list[str] = []
        # first, because it is the one check that can invalidate the others:
        # a precursor confirmed to a part per million and a library record at
        # 96 are both about whatever the method isolated, and if that is not
        # the compound on the label then neither sentence is about this vial
        said += self._isolation_sentences()
        said += self._precursor_sentences()
        said += self._adduct_sentences()
        said += self._fragment_sentences()
        said += self._purity_sentences()
        said += self._library_sentences()
        if not said:
            said.append(
                "Nothing was checked: no precursor was measured, no structure "
                "or formula was scored against this spectrum and no library "
                "was searched. What follows is the averaged spectrum and its "
                "peaks, which is all this report claims to be.")
        # last, because it is about the spectrum every other sentence was
        # measured on rather than about the compound — and it is not a check,
        # so it does not stop the sentence above from being written
        said += self._scan_sentences()
        return said

    def _isolation_sentences(self) -> list[str]:
        """
        What the name and the method say about each other, where it was asked.

        Silent when the verdict agrees and the name was resolved from a table
        rather than measured: a report that opens by saying the file is named
        what it is named has spent its first sentence on nothing. It speaks
        when the two disagree, which is the case worth a page.
        """
        verdict = self.isolation
        if verdict is None or not verdict.judged or verdict.agrees:
            return []
        return [verdict.sentence()]

    def _precursor_sentences(self) -> list[str]:
        written = (f"the written {self.written_precursor:.4f}"
                   if self.written_precursor else "the written precursor")
        measurement = self.measurement
        if measurement is not None and measurement.found:
            said = [f"{_confirms(measurement.error_ppm)}: "
                    f"the survey scan puts {written} at "
                    f"{measurement.measured:.4f}."]
            agreement = measurement.agreement_ppm
            if agreement is None:
                said[-1] += (" Nothing survived fragmentation to check it "
                             "against, so the survey is the only measurement.")
            elif measurement.corroborated:
                said[-1] += (f" The product-ion scan agrees to "
                             f"{agreement:+.1f} ppm, so the two are the same "
                             f"ion.")
            else:
                said[-1] += (f" The product-ion scan disagrees by "
                             f"{agreement:+.1f} ppm, past the "
                             f"{_precursor.AGREEMENT_PPM:g} ppm that says the "
                             f"same ion — the survey window may have caught a "
                             f"neighbour.")
            return said
        if self.survivor is not None:
            error = self.error_ppm()
            return [f"{_confirms(error)} in the "
                    f"product-ion scan itself: {written} survives "
                    f"fragmentation at {self.survivor[0]:.4f}, "
                    f"{self.survivor[1]:,.0f} counts. This acquisition has no "
                    f"survey scan, so there is nothing independent to check "
                    f"it against."]
        if self.survivor_note:
            return [f"Precursor not confirmed: {self.survivor_note}."]
        if measurement is not None:
            return [f"Precursor not confirmed: {measurement.note or 'not found'}."]
        return []

    def _adduct_sentences(self) -> list[str]:
        """
        What the survey scan says the written precursor is, if anything.

        An adduct is otherwise arithmetic on a number somebody typed: the
        method says 647.5, the molecule weighs 646.50, and the only ion that
        joins them is the protonated one — which is a deduction, not a
        measurement, and it is wrong the moment the formula is. A survey scan
        turns it into a measurement, by the exact mass and by the isotope
        pattern, and where the acquisition has no survey this says so instead
        of letting the deduction pass for one.
        """
        if not self.adduct_note:
            return []
        said = [self.adduct_note if self.adduct_note.endswith(".")
                else self.adduct_note + "."]
        others = [e for e in self.evidence
                  if e.present and e.name != self.adduct]
        if self.adduct_confirmed and others:
            from .chemistry import adduct_map

            said[-1] += (f" The survey shows this compound as "
                         f"{adduct_map(self.evidence)}, so the channel that "
                         f"was acquired is not the only one it would give.")
        return said

    def _fragment_sentences(self) -> list[str]:
        explanation = self.explanation
        if explanation is None:
            return []
        labels = (f", carrying up to {self.deuterium} unplaced label(s)"
                  if self.deuterium else "")
        if explanation.predicted:
            head = (f"{explanation.matched} of the {explanation.predicted} "
                    f"ions predicted for {explanation.name} were found")
        else:
            head = (f"{explanation.matched} peak(s) were accounted for by "
                    f"{explanation.name}")
        said = [f"{head}{labels}, {explanation.share * 100:.1f}% of the "
                f"spectrum's intensity."]
        listed = self.peaks()
        left = self.explanation.unexplained(listed)
        if left:
            said[-1] += (f" {len(left)} of the {len(listed)} strongest peaks "
                         f"above the label floor are not accounted for, the "
                         f"strongest at {left[0][0]:.4f}.")
            # what those peaks might be, where the module that says so is
            # present. Read defensively: a report built by an older caller,
            # or one whose spectrum is not held, has nothing to annotate.
            try:
                rows = self.annotations()
            except Exception:                   # a search that would not run
                rows = []
            if rows:
                counted = _unexplained.tally(rows).sentence()
                if counted:
                    said[-1] += f" {counted}"
        return said

    def _purity_sentences(self) -> list[str]:
        return [] if self.purity is None else self.purity.sentences()

    def _library_sentences(self) -> list[str]:
        hit = self.hit
        if hit is None:
            return []
        delta = ("" if hit.delta_ppm is None
                 else f", the precursors {hit.delta_ppm:+.1f} ppm apart")
        said = [f"Best library record “{hit.entry.name}” at score "
                f"{hit.score * 100:.0f}, reverse {hit.reverse * 100:.0f}, "
                f"{hit.matched} of its {hit.of_library} peak(s) matched"
                f"{delta}."]
        gap = self.energy_gap()
        if gap is not None:
            said.append(
                f"Collision energy differs from the record's "
                f"({gap[0]:g} against {gap[1]:g} eV): a spectrum taken at "
                f"another energy has other fragments, so a lower score here "
                f"is the energy and not necessarily the compound.")
        return said


# --------------------------------------------------------------------------- #
# building one
# --------------------------------------------------------------------------- #
def average_spectrum(channel, include_unstable: bool = False, sample=None,
                     cache=None, path: str = ""):
    """
    Every steady scan of a channel averaged into one spectrum, with the range
    and the mask that says which scans those were.

    An infusion has no chromatography to select over, so this is the whole of
    it — the same view `Explorer.average_whole_run` lands on, and the same
    arithmetic, so the pane and the paper cannot disagree.

    `include_unstable` averages the run as it comes, which is what this did
    before `infusion.stable_scans` existed and what *Include unstable scans*
    in the Explorer's Process menu asks for. The mask is measured and returned
    either way, so a report of the raw average can still say what it kept.

    `sample` is the channel's own sample where the caller has it, and it gates
    the mask on the infusion verdict (`infusion.mask_for`) — the peaks of a
    chromatographic run depart from their neighbours further than any spray
    ever does. Without one this trusts the caller that the channel is an
    infusion's, which every caller inside this module is.

    `cache` is a `spectrum_cache.AverageCache` and `path` the acquisition it
    keys on; with both, an average of a file that has not changed is read
    from disk instead of from the instrument's scans. The mask is measured
    either way — it costs one chromatogram and it is what the key is made
    of — and what is stored is the **raw** average, before any mass
    correction, because a correction belongs to the session and not to the
    file. Nothing else changes: a hit and a miss return the same arrays.
    """
    window = run_range(channel)
    if window is None:
        return None
    mask = (mask_for(sample, channel) if sample is not None
            else stable_scans(channel))
    key = ""
    if cache is not None and path:
        from . import spectrum_cache

        key = spectrum_cache.average_key(
            path, getattr(channel, "index", None), whole_run=True,
            rt_range=window, mask=mask, include_unstable=include_unstable)
        stored = cache.get(key)
        if stored is not None:
            return (stored[0], stored[1], window, mask)
    if include_unstable:
        mz, intensity = channel.spectrum_rt_range(*window)
    else:
        mz, intensity = average_stable(channel, mask)
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if key:
        cache.put(key, mz, intensity, getattr(mask, "ranges", "") or "")
    return mz, intensity, window, mask


class _Trace:
    """The little a `spectra_compare` trace needs: label, x, y, colour."""

    def __init__(self, label, x, y, colour):
        self.label, self.x, self.y, self.colour = label, x, y, colour


def one_spectrum(label: str, mz, intensity, title: str = "",
                 centroid: bool = False,
                 label_floor: float = LABEL_MIN_RELATIVE) -> SpectrumComparison:
    """One spectrum, drawn for paper."""
    return spectra_compare.from_traces(
        [_Trace(label, mz, intensity, "#234b8c")],
        title=title or label, centroid=centroid, label_floor=label_floor)


def head_to_tail(label: str, mz, intensity, other_label: str, other_mz,
                 other_intensity, title: str | None = None,
                 centroid: bool = False,
                 label_floor: float = LABEL_MIN_RELATIVE) -> SpectrumComparison:
    """
    Two spectra, the second drawn downwards.

    Normalised, because the two are never the same size — a library record is
    held relative to its base peak and a measured average is in counts — and
    a picture of one flat line under a tall one compares nothing.

    `title` of `""` draws none: in this document the heading above the figure
    already names it, and the same words twice, four lines apart, read as a
    mistake. None takes the default.
    """
    if title is None:
        title = f"{label} against {other_label}"
    return spectra_compare.from_traces(
        [_Trace(label, mz, intensity, "#234b8c"),
         _Trace(other_label, other_mz, other_intensity, "#a4262c")],
        title=title, normalise=True, mirror=True, centroid=centroid,
        label_floor=label_floor)


def _peak_arrays(peaks) -> tuple[np.ndarray, np.ndarray]:
    if not peaks:
        return np.zeros(0), np.zeros(0)
    mz = np.asarray([p[0] for p in peaks], dtype=float)
    intensity = np.asarray([p[1] for p in peaks], dtype=float)
    top = float(intensity.max()) if intensity.size else 0.0
    return mz, (intensity / top if top > 0 else intensity)


def score_against(peaks, other_peaks,
                  tolerance_ppm: float = PEAK_TOLERANCE_PPM):
    """
    Two measured spectra scored against each other.

    The same cosine a library search takes, on the same pairing rule, because
    "how alike are these two spectra" has one answer in this program and it
    should not have two. `reverse` here asks whether the other spectrum's
    peaks are in this one, which is what an infusion at a lower collision
    energy against one at a higher energy actually needs.
    """
    mz, intensity = _peak_arrays(peaks)
    other_mz, other_intensity = _peak_arrays(other_peaks)
    if mz.size == 0 or other_mz.size == 0:
        return 0.0, 0.0, ()
    return match(mz, intensity, other_mz, other_intensity, tolerance_ppm)


def _channel_note(channel, mask: ScanMask | None = None) -> str:
    info = getattr(channel, "info", None)
    if info is None:
        return ""
    energy = getattr(info, "collision_energy", None)
    if mask is not None and mask.excluded:
        bits = [f"{mask.kept:,} of {mask.n_scans:,} scans"]
    else:
        bits = [f"{info.n_scans:,} scans"]
    if energy:
        bits.append(f"CE {energy:g} eV")
    return ", ".join(bits)


def report_for(entry: SampleEntry, channel=None, compound: str = "",
               explanation: Explanation | None = None, basis: str = "",
               deuterium: int = 0, hit: LibraryHit | None = None,
               library: str = "", adduct: str = "",
               others: "list[tuple[SampleEntry, object]]" = (),
               label_floor: float = LABEL_MIN_RELATIVE,
               centroid: bool = False,
               spectrum: tuple | None = None,
               measure_precursor: bool = True,
               formula: str = "", components=(), own_library=None,
               session=None, recalibrated: bool = False,
               include_unstable: bool = False, cache=None) -> InfusionReport:
    """
    A report for one open infusion, reading the file for what it needs.

    `spectrum` is `(mz, intensity)` when the caller already has the averaged
    spectrum on screen — the Explorer does, conditioned the way the pane
    conditions it — and None to read and average it here. `others` are the
    infusions to compare against, each an `(entry, channel)` pair.

    `components` and `own_library` are what the isolation verdict is offered
    when the compound the file is named after does not fit the precursor the
    method isolates. Both are optional and neither is read for anything else:
    without them the verdict can still say *not this*, and with them it can
    sometimes say what instead.

    `cache` is a `spectrum_cache.AverageCache` for the averaged spectrum, or
    None to read it from the file every time. It is handed to `average_
    spectrum` and to the comparisons; a caller that already has the spectrum
    passes it in `spectrum` instead and the cache is not consulted at all.

    `session`, where it is given, is what the mass correction lives on: the
    axis is fitted from this infusion's own precursor ladder (`fit_axis`) and
    applied when the session's switch is on. `recalibrated` says the caller
    has already applied it to the `spectrum` handed in — the Explorer draws
    the corrected axis, so its report would otherwise correct it twice.
    """
    sample = getattr(entry, "sample", None)
    channel = channel if channel is not None else (
        strongest_channel(sample) if sample is not None else None)
    info = getattr(channel, "info", None)

    report = InfusionReport(
        compound=compound or compound_of(getattr(entry, "name", "")),
        file=getattr(entry, "filename", ""),
        sample=getattr(entry, "name", ""),
        instrument=str(getattr(sample, "instrument", "") or ""),
        adduct=adduct, formula=formula,
        explanation=explanation, basis=basis, deuterium=int(deuterium),
        hit=hit, library=library, label_floor=float(label_floor),
    )
    if sample is not None:
        try:
            report.verdict = verdict_for(sample)
        except Exception:                       # a reader that cannot say
            report.verdict = None
        try:
            report.isolation = what_the_method_isolates(
                sample, components, own_library,
                name=str(getattr(entry, "name", "") or ""))
        except Exception:                       # a reader that cannot say
            report.isolation = None
    if info is not None:
        report.polarity = str(getattr(info, "polarity", "") or "")
        report.channel = info.label
        report.channel_name = str(getattr(info, "name", "") or "")
        report.written_precursor = info.precursor
        report.collision_energy = info.collision_energy
        report.scans = int(info.n_scans)
    if channel is None:
        return report

    if spectrum is not None:
        mz, intensity = (np.asarray(spectrum[0], dtype=float),
                         np.asarray(spectrum[1], dtype=float))
        report.rt_range = run_range(channel)
        # the pane already averaged; the mask is measured again here so the
        # header can say what the pane's title says. It costs one chromatogram
        report.mask = mask_for(sample, channel)
        report.unstable_included = bool(include_unstable)
    else:
        averaged = average_spectrum(channel, include_unstable=include_unstable,
                                    sample=sample, cache=cache,
                                    path=str(getattr(entry, "path", "") or ""))
        if averaged is None:
            return report
        mz, intensity, report.rt_range, report.mask = averaged
        report.unstable_included = bool(include_unstable)
    # the mass axis, before anything reads a mass off it. Fitted from the
    # uncorrected average, which is why this comes before the correction is
    # applied and why a caller that has already applied one says so.
    if session is not None:
        report.axis_subject = axis_subject(
            session, report.compound, report.written_precursor,
            report.polarity)
        if recalibrated:
            report.correction = getattr(session, "mass_corrections", {}).get(
                getattr(entry, "key", ""))
        else:
            report.correction = fit_axis(session, entry, channel,
                                         spectrum=(mz, intensity),
                                         cache=cache)
        applied = None
        try:
            applied = session.correction_for(getattr(entry, "key", ""))
        except Exception:
            applied = None
        if applied is not None:
            report.recalibrated = True
            if not recalibrated:
                mz = np.asarray(applied.apply(mz), dtype=float)
    report.spectrum = one_spectrum(
        f"{report.sample} · {report.channel}", mz, intensity,
        title=f"{report.title} — averaged over the whole run",
        centroid=centroid, label_floor=label_floor)

    # what the acquisition says is noise, measured off it rather than fixed:
    # the average of hundreds of scans has neither the units nor the noise of
    # the single survey scan `precursor.MIN_INTENSITY` was written for. The
    # spectrum printed here is the one measured, spray mask included, and the
    # scan count goes with it: what averaging bought is the root of the scans
    # actually in the average, not of the scans in the range.
    try:
        report.noise_floor = noise_floor_for(
            channel, spectrum=(mz, intensity),
            scans=report.scans_averaged() or None)
    except Exception:                       # a reader that cannot say
        report.noise_floor = None

    # the accurate precursor. The survey first, because it is the independent
    # measurement; the averaged product-ion spectrum only where there is no
    # survey to read — nine real infusions to hand have no survey at all.
    if measure_precursor and report.written_precursor:
        component = Component(name=report.compound or "infused",
                              precursor=float(report.written_precursor))
        try:
            report.measurement = _precursor.measure(entry, component)
        except Exception:
            report.measurement = None
        if report.measurement is None or not report.measurement.found:
            _survivor(report, mz, intensity)

    # which adduct that written precursor is, asked of the survey scan
    # rather than deduced from the number. Only where a formula is known:
    # without one there is nothing for an adduct to be an adduct of.
    if formula:
        confirm_adduct(entry, report, formula, deuterium)
    _measure_purity(report, mz, intensity)

    # what the explanation is worth against its neighbours. Here rather than
    # in the caller because this is where the spectrum it was scored on is
    # — the same centroids `_sticks` hands the library search.
    report.margin = _margin.for_report(report, _sticks(report))

    mine = score_peaks(report)
    for other_entry, other_channel in others:
        other = _compared(report, mine, other_entry, other_channel,
                          centroid=centroid, label_floor=label_floor,
                          cache=cache)
        if other is not None:
            report.compared.append(other)
    return report


def survey_spectrum(entry, report: InfusionReport):
    """
    The survey scan of this acquisition over the same range as the spectrum.

    The same range on purpose: the product-ion average on the page and the
    survey it is checked against have to be the same moment of the same run,
    or the adduct is confirmed from somebody else eluting. For an infusion
    that range is the whole run, which is the whole of the measurement.

    Returns `(channel, mz, intensity)`, or None when the sample has no
    full-scan channel covering the precursor — the ordinary case on the nine
    bile-acid infusions, which were acquired as product-ion scans alone.
    """
    from .precursor import survey_channel

    sample = getattr(entry, "sample", None)
    precursor = float(report.written_precursor or 0.0)
    if sample is None or not precursor:
        return None
    window = report.rt_range
    middle = None if window is None else (window[0] + window[1]) / 2.0
    try:
        channel = survey_channel(sample, precursor, middle)
    except Exception:                       # a reader that cannot say
        return None
    if channel is None:
        return None
    span = window or run_range(channel)
    if span is None:
        return None
    try:
        mz, intensity = channel.spectrum_rt_range(float(span[0]), float(span[1]))
    except Exception:                       # a .wiff with no .wiff.scan
        return None
    return channel, mz, intensity


def confirm_adduct(entry, report: InfusionReport, formula: str,
                   deuterium: int = 0):
    """
    Ask the survey which adduct the written precursor is, and record it.

    The written precursor still says which adducts are candidates — the
    quadrupole isolated that mass — and the survey says which of them the
    instrument saw, by the exact mass and by the isotope pattern. What comes
    back goes on the report whichever way it falls: an adduct nobody could
    check is a different claim from one measured, and the report is a list of
    claims with their evidence.

    Returns the `chemistry.AdductChoice`, or None where there was no formula
    or no precursor to ask about.
    """
    from .chemistry import (FormulaError, format_formula, identify_adduct,
                            parse_formula)

    report.evidence = []
    report.adduct_confirmed = False
    report.survey_channel = ""
    precursor = float(report.written_precursor or 0.0)
    if not formula or not precursor:
        report.adduct_note = ""
        return None
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        report.adduct_note = f"“{formula}” is not a formula this can read"
        return None
    if deuterium and counts.get("H", 0) >= deuterium and not counts.get("D"):
        counts["D"] = counts.get("D", 0) + deuterium
        counts["H"] -= deuterium
    labelled = format_formula(counts)
    report.formula = labelled

    found = survey_spectrum(entry, report)
    polarity = report.polarity or None
    if found is None:
        choice = identify_adduct(labelled, precursor, polarity)
        report.adduct_note = (
            f"Adduct read from the written precursor alone: this acquisition "
            f"has no survey scan covering {precursor:g}, so nothing "
            f"independent says which ion it is — {choice.reason}")
        if choice.adduct is not None and not report.adduct:
            report.adduct = choice.adduct.name
        return choice
    channel, mz, intensity = found
    report.survey_channel = str(getattr(channel.info, "label", "") or "")
    choice = identify_adduct(labelled, precursor, polarity,
                             survey=(mz, intensity))
    report.evidence = list(choice.evidence)
    report.adduct_confirmed = bool(choice.confirmed)
    if choice.adduct is not None and (not report.adduct
                                      or choice.confirmed):
        report.adduct = choice.adduct.name
    lead = ("Adduct confirmed by the survey" if choice.confirmed
            else "Adduct not confirmed by the survey")
    report.adduct_note = f"{lead}: {choice.reason}"
    return choice


def _measure_purity(report: InfusionReport, mz=None, intensity=None,
                    formula: str = "", adduct: str = "",
                    deuterium: int | None = None) -> None:
    """
    The isotopic purity of a labelled standard, from the averaged spectrum.

    Only where three things are known: what the compound is made of, how it
    was ionised, and how many labels it carries. Two of those come from
    whatever was scored against the spectrum, so an infusion nobody explained
    is not asked — there is no formula to build the envelope from, and
    guessing one would be inventing the answer's own model. The arguments
    exist because the headless path knows all three a moment before the
    report does.

    It reads the **profile** spectrum, not the report's peak list: an isotope
    envelope's rungs are tenths of a per cent of the base peak and every peak
    list in this module starts at one per cent.

    A refusal is kept rather than dropped. On the nine bile-acid infusions
    this was written against it is the *only* outcome, because every one is a
    product-ion scan whose precursor the quadrupole isolated, and a page that
    silently omits the block cannot be told from a build that never had it.
    """
    explanation = report.explanation
    formula = formula or (explanation.record.formula
                          if explanation is not None else "")
    adduct = adduct or report.adduct
    if deuterium is None:
        deuterium = int(report.deuterium)
    if not formula or not adduct:
        return
    if mz is None or intensity is None:
        trace = report.trace
        if trace is None:
            return
        mz, intensity = trace.mz, trace.intensity
    try:
        attempt = _purity.purity_from_spectrum(mz, intensity, formula,
                                               adduct, int(deuterium))
    except Exception:                          # a formula the reader refuses
        return
    result = attempt.best
    if result is not None and result.labels > 0:
        report.purity = result


def _survivor(report: InfusionReport, mz, intensity) -> None:
    """
    The precursor in the averaged product-ion spectrum, where there is one.

    Held to the noise floor **measured off this acquisition**
    (`infusion.noise_floor`), and to the fixed `precursor.MIN_INTENSITY` only
    where nothing could be measured. Without a floor the window is a stretch
    of axis like any other and its tallest point is noise: measured on a real
    CID infusion of cholic acid-d4 at 45 eV, the ±0.25 Da window around the
    written 430.35 holds 84 counts and centroiding them reports the precursor
    70 ppm out of place. With a floor of 100 the same 84 counts are refused
    — and on that file the measured floor is 0.96 counts, so the 84 are
    eighty-eight times the background and the refusal was the constant
    talking, not the acquisition. A precursor that does not survive its own
    collision energy is still an ordinary finding; which of the two it is now
    comes from the file.
    """
    target = float(report.written_precursor or 0.0)
    if not target:
        return
    floor = report.floor
    found = _precursor.in_spectrum(mz, intensity, target, floor=floor)
    if found is not None:
        report.survivor = found
        return
    # nothing cleared the floor: what *was* there is the message, so it is
    # read again without the gate
    seen = _precursor.in_spectrum(mz, intensity, target)
    if seen is None:
        report.survivor_note = (
            f"nothing at all sits within ±{_precursor.SEARCH_WINDOW:g} Da of "
            f"{target:g} in the averaged product-ion spectrum")
        return
    height = seen[1]
    base = report.base_peak()
    share = (f", {height / base[1] * 100:.2f}% of the base peak"
             if base and base[1] else "")
    measured = getattr(report.noise_floor, "measured", False)
    how = ("the measured noise floor of" if measured
           else "the fixed floor of")
    report.survivor_note = (
        f"too little of the precursor survives this collision energy to "
        f"measure a mass — at most {format_counts(height)} counts{share} "
        f"within ±{_precursor.SEARCH_WINDOW:g} Da of {target:g}, below "
        f"{how} {format_counts(floor)} counts")


def _compared(report: InfusionReport, mine, other_entry,
              other_channel=None, centroid: bool = False,
              label_floor: float = LABEL_MIN_RELATIVE,
              cache=None) -> Compared | None:
    sample = getattr(other_entry, "sample", None)
    channel = other_channel if other_channel is not None else (
        strongest_channel(sample) if sample is not None else None)
    if channel is None:
        return None
    averaged = average_spectrum(channel,
                                include_unstable=report.unstable_included,
                                sample=sample, cache=cache,
                                path=str(getattr(other_entry, "path", "") or ""))
    if averaged is None:
        return None
    other_mz, other_intensity, _window, other_mask = averaged
    trace = report.trace
    if trace is None:
        return None
    label = str(getattr(other_entry, "name", "") or "")
    comparison = head_to_tail(
        trace.label, trace.mz, trace.intensity,
        f"{label} · {channel.info.label}", other_mz, other_intensity,
        title="", centroid=centroid, label_floor=label_floor)
    theirs = comparison.peaks(comparison.traces[1], most=SCORE_PEAKS,
                              min_relative=SCORE_SHARE)
    score, reverse, pairs = score_against(mine, theirs)
    return Compared(label=label, comparison=comparison, score=float(score),
                    reverse=float(reverse), matched=len(pairs),
                    of_other=len(theirs), note=_channel_note(channel, other_mask))


def from_explorer(explorer, compound: str = "", others=(),
                  measure_precursor: bool = True) -> InfusionReport | None:
    """
    A report from what the Explorer has on screen for its active channel.

    The pane's own spectrum rather than a fresh average, so the report shows
    what was looked at — background subtracted, recalibrated, smoothed, at the
    label floor the handle was left at. The explanation and the library hit
    are whichever the two panels last produced; where a panel produced none,
    that block is absent and the verdict does not mention it.

    Duck-typed on purpose: it reaches for attributes and settles for None, so
    the report module still has no import of the UI and can be exercised
    without one.
    """
    ref = getattr(explorer, "active_ref", None)
    if ref is None or getattr(ref, "channel", None) is None:
        return None
    spectrum = None
    try:
        spectrum = explorer._current_spectrum()
    except Exception:
        spectrum = None

    lipids = getattr(explorer, "lipid_panel", None)
    explanation = getattr(lipids, "current_explanation", None)
    if callable(explanation):
        explanation = explanation()
    basis = getattr(lipids, "explanation_basis", "") or ""
    # the panel measured it against the peaks it explained; measuring it a
    # second time here would cost the same seconds to reach the same answer
    measured_margin = getattr(lipids, "explanation_margin", None)
    deuterium = 0
    adduct = ""
    if lipids is not None:
        try:
            deuterium = int(lipids.own_deuterium.value())
            # what it was actually scored as. The explanation itself carries
            # it, which is the only source that cannot disagree with the
            # scoring: both paths read the adduct off the written precursor
            # rather than off the box, and the box may say "from the
            # precursor" — the name of a rule, not of an ion
            from .chemistry import adduct_from_name

            chosen = lipids.explain_adduct.currentText()
            adduct = str(getattr(explanation, "adduct", "")
                         or getattr(lipids, "explanation_adduct", "")
                         or (chosen if adduct_from_name(chosen) else ""))
        except Exception:
            deuterium, adduct = 0, adduct

    panel = getattr(explorer, "library_panel", None)
    hit = None
    library = ""
    own = None
    if panel is not None:
        try:
            hit = panel._current_hit()
            own = panel.library
            library = os.path.basename(getattr(own, "path", "") or "")
        except Exception:
            hit, library, own = None, "", None

    session = getattr(explorer, "session", None)
    components = getattr(getattr(session, "method", None), "components", ())

    floor = getattr(getattr(explorer, "spectrum", None), "label_floor",
                    LABEL_MIN_RELATIVE)
    centroid = bool(getattr(getattr(explorer, "spectrum", None), "centroided",
                            False))
    # the formula whatever was explained was explained from: without one
    # there is nothing for an adduct to be an adduct of, and the survey is
    # not asked
    formula = str(getattr(getattr(explanation, "record", None), "formula", "")
                  or "")
    # the pane's axis is already corrected exactly when a correction is in
    # force for this sample, so that — and not the switch alone — is what
    # says whether the report would be correcting it a second time. Only
    # where the pane actually handed a spectrum over: with none, the report
    # reads its own average and has to correct that itself.
    session = getattr(explorer, "session", None)
    corrected = False
    if session is not None and spectrum is not None:
        try:
            corrected = session.correction_for(ref.entry.key) is not None
        except Exception:
            corrected = False
    report = report_for(
        ref.entry, ref.channel, compound=compound, explanation=explanation,
        basis=basis, deuterium=deuterium, hit=hit, library=library,
        adduct=adduct, others=others, label_floor=float(floor),
        centroid=centroid, spectrum=spectrum,
        measure_precursor=measure_precursor, formula=formula,
        components=components, own_library=own,
        session=session, recalibrated=corrected,
        include_unstable=bool(getattr(explorer, "include_unstable_scans",
                                      lambda: False)()))
    if measured_margin is not None and report.explanation is not None:
        report.margin = measured_margin
    return report


def infusions_open(source) -> "list[tuple[SampleEntry, object]]":
    """
    Every open sample read as an infusion, with the channel to show it from.

    `source` is a session, or anything holding one — the Explorer does.
    Read from the session's entries rather than from a tree, so it is the
    same list whether a tree is filtered or not, and so the Analytics side
    can ask the same question without a widget in it.
    """
    session = getattr(source, "session", None)
    if session is None or not hasattr(session, "entries"):
        session = source
    found = []
    for entry in getattr(session, "entries", []):
        sample = getattr(entry, "sample", None)
        if sample is None:
            continue
        try:
            if not verdict_for(sample):
                continue
        except Exception:
            continue
        channel = strongest_channel(sample)
        if channel is not None:
            found.append((entry, channel))
    return found


# --------------------------------------------------------------------------- #
# every open infusion, one row each
# --------------------------------------------------------------------------- #
#: how far a measured precursor may sit from the written one and still be
#: counted in the summary line. `precursor.CONSENSUS_SPREAD_PPM` is the limit
#: the consensus and the mass drift already use to say two measurements are
#: of the same ion; a fourth number for the same question would be one too
#: many. It counts a row for a sentence — nothing is decided on it.
CONFIRMED_PPM = _precursor.CONSENSUS_SPREAD_PPM


def _confirms(error: float | None) -> str:
    """
    The opening of the precursor sentence: *confirmed* only within
    `CONFIRMED_PPM`, and *found but not confirmed* past it.

    The height gate and the mass are two different questions and the noise
    floor only answers the first. Measuring the floor off the acquisition
    rather than fixing it at a hundred counts is what made that separation
    visible: on the real bile-acid infusions four windows that the constant
    had refused outright now hold a measurable peak, and all four measure
    −30 to −70 ppm from the written mass. Something is there; it is not the
    precursor. The summary line already counted a row only within
    `CONFIRMED_PPM`, so a sentence saying *confirmed* at −70 ppm disagreed
    with the count above it.
    """
    if error is None:
        return "Precursor confirmed"
    if abs(error) <= CONFIRMED_PPM:
        return f"Precursor confirmed at {error:+.1f} ppm"
    return (f"Precursor found but not confirmed at {error:+.1f} ppm, past "
            f"the {CONFIRMED_PPM:g} ppm that says the same ion")

#: the library score the summary line counts a record at. Again a figure the
#: sentence is written with and not a threshold anything passes: a record of
#: one's own made from another activation of the same vial scored 6 to 61 on
#: the nine real infusions, and calling 6 a failure would be calling the
#: collision energy a failure.
COUNTED_SCORE = 0.60

#: the columns of the summary, in the order they are shown and exported.
#: One definition for the table, the CSV and the row's own sort keys.
SUMMARY_COLUMNS = (
    "Compound", "Sample", "Isolated", "Mode", "CE (eV)", "Scans",
    "Base peak m/z", "Precursor written", "Found m/z", "Δ ppm", "Height",
    "Adduct", "Ions found", "Margin", "Library record", "Score", "Reverse",
    "Matched",
    "Record Δ ppm", "Record CE", "Other infusions", "Mass axis", "File")

#: the columns of `SUMMARY_COLUMNS` that hold a number, and what to sort each
#: on. Keyed by the column's **name**: `keys()` used to hold the positions,
#: and inserting a column in the middle then moved every sort key one cell to
#: the right without anything failing.
_SORT_KEYS = ("CE (eV)", "Scans", "Base peak m/z", "Precursor written",
              "Found m/z", "Δ ppm", "Height", "Ions found", "Margin", "Score",
              "Reverse", "Matched", "Record Δ ppm", "Mass axis")

#: what goes in the report's table. A4 does not hold nineteen columns and a
#: table squeezed into it is a table nobody reads, so the precursor and the
#: record are each written as one cell there — the panel and the CSV carry
#: the parts.
REPORT_COLUMNS = ("Compound", "Sample", "Mode", "Scans", "Base peak m/z",
                  "Precursor", "Adduct", "Ions found", "Library record",
                  "Score", "Other infusions", "Mass axis")

_NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _flat(text) -> str:
    return _NOT_ALPHANUMERIC.sub("", str(text or "").lower())


def component_for(method, compound: str):
    """
    The component of the method that is this compound, or None.

    Matched on the name with case, spaces and punctuation set aside, because
    a file called `CA-d4_TOFMSMS_Mix1` and a component called `CA d4` are the
    same standard written by two people. Nothing else is guessed: a component
    that merely has a similar name is not this compound.
    """
    want = _flat(compound)
    if not want:
        return None
    for component in getattr(method, "components", []):
        if _flat(getattr(component, "name", "")) == want:
            return component
    return None


def picked(report: InfusionReport, most: int,
           min_relative: float) -> list[tuple[float, float]]:
    """
    `report.spectrum.peaks(report.trace, most, min_relative)`, picked once.

    The pick is remembered on the report against the trace object it was
    made from: the same trace asked the same question again is answered
    from memory, and a trace that has been replaced — recalibrated, or
    averaged again — is picked afresh. What comes back is a copy, so a
    caller that sorts or trims it changes nothing for the next.
    """
    trace = report.trace
    if trace is None or report.spectrum is None:
        return []
    key = ("peaks", int(most), float(min_relative),
           bool(report.spectrum.centroid))
    held = report._picked.get(key)
    if held is not None and held[0] is trace:
        return list(held[1])
    peaks = report.spectrum.peaks(trace, most=most, min_relative=min_relative)
    report._picked[key] = (trace, peaks)
    return list(peaks)


def score_peaks(report: InfusionReport) -> list[tuple[float, float]]:
    """The peaks an infusion is scored on: `SCORE_PEAKS` at `SCORE_SHARE`."""
    return picked(report, most=SCORE_PEAKS, min_relative=SCORE_SHARE)


def _sticks(report: InfusionReport):
    """
    The averaged spectrum as centroids: what a search and a score read.

    Centroided once per trace and remembered on the report, the way
    `picked` remembers a pick: the search, the margin, the explanation and
    the raw axis all read the same sticks, and centroiding a quarter of a
    million points is the cost of the report once the file is cached.
    """
    trace = report.trace
    if trace is None or trace.mz.size == 0:
        return None
    if report.spectrum is not None and report.spectrum.centroid:
        return trace.mz, trace.intensity
    held = report._picked.get("sticks")
    if held is not None and held[0] is trace:
        return held[1]
    from .processing import centroid_spectrum

    sticks = centroid_spectrum(trace.mz, trace.intensity)
    report._picked["sticks"] = (trace, sticks)
    return sticks


def raw_sticks(report: InfusionReport):
    """
    The report's centroids put back on the axis the instrument read.

    `MassCorrection.undo` rather than a second copy of the spectrum: an
    offset inverts exactly, so this is the measured masses to the last
    digit and costs one multiplication per peak instead of holding a
    quarter of a million points twice. None when there is nothing to undo.
    """
    sticks = _sticks(report)
    if sticks is None or not report.recalibrated or report.correction is None:
        return None
    return (np.asarray(report.correction.undo(sticks[0]), dtype=float),
            sticks[1])


def _report_note(report: InfusionReport) -> str:
    """How an infusion was acquired, in one cell — `_channel_note`'s words
    from the report rather than from a channel, since a report holds both."""
    mask = report.mask
    if mask is not None and mask.excluded and not report.unstable_included:
        bits = [f"{mask.kept:,} of {mask.n_scans:,} scans"]
    else:
        bits = [f"{report.scans:,} scans"] if report.scans else []
    if report.collision_energy:
        bits.append(f"CE {report.collision_energy:g} eV")
    return ", ".join(bits)


@dataclass
class InfusionRow:
    """One infusion in the summary: what was measured, and why not."""

    report: InfusionReport
    #: the peaks this infusion is scored on, at `SCORE_SHARE`, kept because
    #: picking them walks a quarter of a million points and every other
    #: infusion of the same compound needs them
    peaks: list = field(default_factory=list)
    #: the other infusions of the same compound: label, score, reverse,
    #: matched, of the other
    others: list = field(default_factory=list)
    #: why a cell is empty, one per column that can be. Short enough for a
    #: cell; the long form of the precursor's is on the report itself.
    precursor_note: str = ""
    explanation_note: str = ""
    library_note: str = ""
    others_note: str = ""
    #: what the compound's own records across energies make of this spectrum
    #: (`library.EnergyMatch`), or None where they could not say. Beside the
    #: single best record rather than instead of it — see `record`
    energy: object | None = None

    # -- what it is ---------------------------------------------------------- #
    @property
    def compound(self) -> str:
        """
        What the row is grouped and compared under: the file name's proposal.

        Deliberately the proposal and not `report.named_compound`. Grouping
        is what decides which infusions are scored against each other, and
        two files named after the same compound are worth comparing whatever
        their methods isolate — the pair that turned out not to be CA-d4 is
        only visible as a pair *because* they were still scored against the
        real ones. The cell says which is which; the grouping does not.
        """
        return self.report.compound

    @property
    def isolated(self) -> str:
        """What the method isolates, short enough for a cell."""
        verdict = self.report.isolation
        return "not checked" if verdict is None else verdict.column()

    @property
    def sample(self) -> str:
        return self.report.sample

    @property
    def mode(self) -> str:
        """Polarity and experiment, and not the whole channel label: the
        precursor and the mass range are columns of their own here, and a
        cell that repeats two other cells is width spent twice."""
        parts = [p for p in (self.report.polarity,
                             self.report.channel_name or self.report.channel)
                 if p]
        return " · ".join(parts)

    # -- what was measured --------------------------------------------------- #
    @property
    def confirmed(self) -> bool:
        """Measured, and within `CONFIRMED_PPM` of what was written."""
        error = self.report.error_ppm()
        return error is not None and abs(error) <= CONFIRMED_PPM

    @property
    def found(self) -> tuple[float, float] | None:
        """The precursor's measured mass and height, wherever it was read."""
        measurement = self.report.measurement
        if measurement is not None and measurement.found:
            return float(measurement.measured), float(measurement.intensity)
        return self.report.survivor

    @property
    def adduct(self) -> str:
        """
        The adduct and whether the survey confirmed it, in one cell.

        Three states and not two: confirmed, read off the written precursor
        with a survey that did not show it, and read off the written
        precursor because there was no survey to ask. The third is the
        ordinary case on a product-ion-only acquisition and it is not a
        failure — but it is not a confirmation either, and a cell that said
        only `[M+NH4]+` would let it pass for one.
        """
        report = self.report
        if not report.adduct and not report.adduct_note:
            return "—"                       # nothing was asked, so nothing said
        name = report.adduct or "—"
        if report.adduct_confirmed:
            return f"{name} confirmed"
        if report.evidence:
            return f"{name} not confirmed"
        if report.survey_channel:
            return f"{name}, survey unreadable"
        return f"{name}, no survey"

    @property
    def margin(self) -> str:
        """
        What the explanation is worth against its neighbours, in one cell.

        A share on its own is not readable — see `margin.py` — so the table
        carries the contrast beside "Ions found" rather than under it. The
        cell says why it is empty when it is: no explanation, no database,
        no other structure at that precursor.
        """
        result = self.report.margin
        if result is None:
            return self.explanation_note or "nothing run"
        return result.column()

    @property
    def score(self) -> float | None:
        return None if self.report.hit is None else self.report.hit.score

    @property
    def record(self) -> str:
        """
        The own-library cell: the best single record, and the energy profile
        where the profile says more than the record did.

        Mentioned only when it beats the record by `PROFILE_BETTER_BY`, and
        beaten is measured against the record's **reverse** score rather than
        its plain one. Both are the same question — are these ions there in
        these proportions — asked of the library's peaks; the plain cosine is
        dragged down by everything else in the vial, and a profile of a dozen
        ions compared against a record's plain score over hundreds would win
        every time by holding less. On the bile-acid infusions this fires on
        nothing: with two energies on file the sweep lands on one of them,
        and the profile then *is* that record's ions, scoring 0.56 where the
        record scored 0.56 and 1.00 where it scored 1.00.
        """
        from .library import PROFILE_BETTER_BY

        hit = self.report.hit
        name = hit.entry.name if hit is not None else (
            self.library_note or "no record")
        match = self.energy
        if match is None or getattr(match, "energy", None) is None:
            return name
        if hit is not None and (float(match.score)
                                < float(hit.reverse) + PROFILE_BETTER_BY):
            return name
        return f"{name} · {match.cell()}"

    @property
    def mass_axis(self) -> str:
        """
        What the recalibration did to this vial, in one cell.

        Says whether it was *applied* as well as what it was: a fit that
        stands with the switch off is a measurement of the axis and not a
        change to the numbers beside it, and a cell that read
        "−5.2 ppm, 4 rungs" either way would make the two look the same.
        """
        correction = self.report.correction
        if correction is None:
            return "not fitted"
        if not correction.usable:
            return correction.note.split(" \u00b7 ")[0] or "no lock mass"
        return correction.short + ("" if self.report.recalibrated
                                   else ", not applied")

    # -- the row ------------------------------------------------------------- #
    def cells(self) -> list[str]:
        report = self.report
        found = self.found
        error = report.error_ppm()
        explanation = report.explanation
        hit = report.hit
        base = report.base_peak()
        gap = report.energy_gap()
        return [
            report.named_compound,
            report.sample,
            self.isolated,
            self.mode,
            "—" if report.collision_energy is None
            else f"{report.collision_energy:g}",
            report.scans_cell(),
            f"{base[0]:,.4f}" if base else "no spectrum",
            f"{report.written_precursor:g}" if report.written_precursor
            else "none written",
            f"{found[0]:,.4f}" if found else (self.precursor_note
                                              or "not measurable"),
            f"{error:+.1f}" if error is not None else "—",
            f"{found[1]:,.0f}" if found else "—",
            self.adduct,
            (f"{explanation.matched} of {explanation.predicted}"
             if explanation is not None and explanation.predicted
             else f"{explanation.matched}" if explanation is not None
             else self.explanation_note or "nothing run"),
            self.margin,
            self.record,
            f"{hit.score * 100:.0f}" if hit is not None else "—",
            f"{hit.reverse * 100:.0f}" if hit is not None else "—",
            f"{hit.matched} of {hit.of_library}" if hit is not None else "—",
            (f"{hit.delta_ppm:+.1f}"
             if hit is not None and hit.delta_ppm is not None else "—"),
            (f"{gap[1]:g} vs {gap[0]:g}" if gap is not None
             else "same" if hit is not None and report.collision_energy
             else "—"),
            (", ".join(f"{label} {score * 100:.0f}/{reverse * 100:.0f}"
                       for label, score, reverse, _m, _o in self.others)
             if self.others else self.others_note or "—"),
            self.mass_axis,
            report.file,
        ]

    def keys(self) -> list:
        """
        What each cell sorts on: the number where there is one.

        A table sorted on its text puts 9 after 100 and "not measurable"
        wherever the alphabet says, which on a column of measurements is
        worse than not sorting at all.

        Keyed by column name through `_SORT_KEYS`: the positions were written
        out here once, and a column inserted in the middle then moved every
        one of them onto the cell next door with nothing failing.
        """
        report = self.report
        found = self.found
        error = report.error_ppm()
        explanation = report.explanation
        hit = report.hit
        base = report.base_peak()
        cells = self.cells()
        numbers = {
            "CE (eV)": report.collision_energy,
            "Scans": float(report.scans_averaged()) or None,
            "Base peak m/z": base[0] if base else None,
            "Precursor written": report.written_precursor,
            "Found m/z": found[0] if found else None,
            "Δ ppm": error,
            "Height": found[1] if found else None,
            "Ions found": (float(explanation.matched)
                           if explanation is not None else None),
            "Margin": (report.margin.points
                       if report.margin is not None else None),
            "Score": hit.score if hit is not None else None,
            "Reverse": hit.reverse if hit is not None else None,
            "Matched": float(hit.matched) if hit is not None else None,
            "Record Δ ppm": hit.delta_ppm if hit is not None else None,
            "Mass axis": (self.report.correction.offset_ppm
                          if self.report.correction is not None
                          and self.report.correction.usable else None),
        }
        keys: list = list(cells)
        for name in _SORT_KEYS:
            value = numbers[name]
            # a cell with no number sorts to the end either way round, which
            # is where a reason belongs in a column of measurements
            keys[SUMMARY_COLUMNS.index(name)] = (
                float("inf") if value is None else float(value))
        return keys

    def report_cells(self) -> list[str]:
        """The same row, narrow enough for A4."""
        report = self.report
        found = self.found
        error = report.error_ppm()
        explanation = report.explanation
        hit = report.hit
        base = report.base_peak()
        gap = report.energy_gap()
        precursor = (f"{found[0]:,.4f} ({error:+.1f} ppm)"
                     if found and error is not None
                     else f"{found[0]:,.4f}" if found
                     else self.precursor_note or "not measurable")
        record = self.record
        if gap is not None:
            record += f" — {gap[1]:g} eV against this run’s {gap[0]:g}"
        return [
            # the flagged name here too: the printed table is narrower than
            # the tab and carries no Isolated column, so this is the only
            # place on the page before the compound's own section where a
            # name the method contradicts can say so
            report.named_compound, report.sample,
            self.mode + (f", {report.collision_energy:g} eV"
                         if report.collision_energy is not None else ""),
            report.scans_cell(),
            f"{base[0]:,.4f}" if base else "no spectrum",
            precursor,
            self.adduct,
            (f"{explanation.matched} of {explanation.predicted}"
             if explanation is not None and explanation.predicted
             else self.explanation_note or "nothing run"),
            record,
            f"{hit.score * 100:.0f}" if hit is not None else "—",
            (", ".join(f"{label} {score * 100:.0f}"
                       for label, score, _r, _m, _o in self.others)
             if self.others else self.others_note or "—"),
            self.mass_axis,
        ]


@dataclass
class InfusionSummary:
    """Every open infusion, one row each, and what they add up to."""

    rows: list[InfusionRow] = field(default_factory=list)
    #: the library of one's own that was searched, as it was named
    library: str = ""
    #: why there are no rows, when there are none
    note: str = ""
    taken: _dt.datetime = field(default_factory=_dt.datetime.now)
    #: how long the measurement took, in seconds
    seconds: float = 0.0

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def compounds(self) -> list[str]:
        return list(dict.fromkeys(row.compound for row in self.rows))

    @property
    def confirmed(self) -> list[InfusionRow]:
        return [row for row in self.rows if row.confirmed]

    @property
    def counted(self) -> list[InfusionRow]:
        return [row for row in self.rows
                if row.score is not None and row.score >= COUNTED_SCORE]

    def summary(self) -> str:
        """
        What the table says, in one line.

        Counts only, and each with what it was counted against: a line that
        said "3 confirmed" without saying within what would be a verdict
        rather than a measurement.
        """
        if not self.rows:
            return self.note or "No infusion is open."
        said = [f"{len(self.compounds)} compound(s) in "
                f"{len(self.rows)} infusion(s)"]
        written = [row for row in self.rows if row.report.written_precursor]
        if written:
            said.append(f"{len(self.confirmed)} of {len(written)} precursor(s) "
                        f"confirmed within {CONFIRMED_PPM:g} ppm")
        else:
            said.append("no precursor is written in any of their methods")
        explained = [row for row in self.rows
                     if row.report.explanation is not None]
        if explained:
            found = sum(row.report.explanation.matched for row in explained)
            offered = sum(row.report.explanation.predicted for row in explained)
            said.append(f"{found} of {offered} predicted ion(s) found across "
                        f"{len(explained)}")
        if self.library:
            said.append(f"{len(self.counted)} with an own record above "
                        f"{COUNTED_SCORE * 100:.0f} in {self.library}")
        else:
            said.append("no library of your own is set")
        return "; ".join(said)


def cross_compare(reports, peaks=None, centroid: bool = False) -> None:
    """
    Every report of one compound drawn and scored against the others.

    Reads no file: both spectra are already held, so this is the picture and
    the cosine and nothing else. It exists because `report_for(others=…)`
    averages the other infusion again for every report that mentions it —
    nine infusions in three compounds would read twenty-seven runs where
    nine were acquired.
    """
    reports = list(reports)
    if peaks is None:
        peaks = [score_peaks(r) for r in reports]
    for index, report in enumerate(reports):
        report.compared = []
        trace = report.trace
        if trace is None:
            continue
        for other_index, other in enumerate(reports):
            other_trace = other.trace
            if other is report or other_trace is None:
                continue
            score, reverse, pairs = score_against(peaks[index],
                                                  peaks[other_index])
            report.compared.append(Compared(
                label=other.sample,
                comparison=head_to_tail(
                    trace.label, trace.mz, trace.intensity,
                    other_trace.label, other_trace.mz, other_trace.intensity,
                    title="", centroid=centroid,
                    label_floor=report.label_floor),
                score=float(score), reverse=float(reverse),
                matched=len(pairs), of_other=len(peaks[other_index]),
                note=_report_note(other)))


def _headless_explanation(session, report: InfusionReport, entry=None,
                          sticks=None):
    """
    What the component table alone can say about this spectrum.

    A formula and an adduct are enough for the precursor and its neutral
    losses — `explain.explain_formula`, the same call the LIPID MAPS tab
    makes for a formula of one's own. It is offered only where the compound
    is a component of the method **by name**: guessing a formula for a file
    name would be inventing the denominator of "n of m".

    `sticks` overrides the spectrum this reads, so the same explanation can
    be run twice — once on the corrected axis and once on the axis as
    measured — which is the before and after the mass-axis paragraph prints.
    """
    method = getattr(session, "method", None)
    component = component_for(method, report.compound)
    if component is None:
        return None, "", (f"{report.compound or 'this compound'} is not a "
                          f"component of the method")
    if not component.formula:
        return None, "", f"{component.name} carries no formula"
    formula, deuterium, labelled = _headless_labels(component, report)
    adduct, why = _headless_adduct(component, report, formula, entry)
    if not adduct:
        return None, "", why
    return _explained(report, component.name, component.formula, deuterium,
                      adduct, why, shown=formula, clause=labelled,
                      sticks=sticks)


def _explained(report: InfusionReport, name: str, formula: str,
               deuterium: int, adduct: str, why: str, shown: str = "",
               clause: str = "", sticks=None):
    """
    The prediction, the basis sentence and the purity, once the formula, the
    adduct and the label count are settled.

    The half of `_headless_explanation` that does not care where those three
    came from — the component table, or a dialog where somebody typed them.
    `formula` is the compound's own, unlabelled, because that is the pair
    `explain_formula` wants: the labels are handed over as a count and
    enumerated over the fragments rather than placed. `shown` is the same
    formula with them folded in, for the sentence a reader sees.
    """
    from .explain import explain_formula, formula_ions, significant_peaks

    if not formula_ions(formula, adduct):
        return None, "", f"{adduct} is not an adduct this program knows"
    sticks = _sticks(report) if sticks is None else sticks
    if sticks is None:
        return None, "", "no spectrum to explain"
    peaks = significant_peaks(*sticks)
    if not peaks:
        return None, "", "no peak above the noise share to explain"
    explanation = explain_formula(formula, adduct, peaks, name=name,
                                  deuterium=deuterium)
    basis = f"the formula {shown or formula} as {adduct}, {why}{clause}"
    # the isotopic purity is asked here rather than by the caller, because
    # this is the one place holding the composition, the adduct and the label
    # count at once — on this path the report carries none of the three. The
    # compound's *own* formula goes over with the labels declared beside it,
    # the same pair `explain_formula` was given: `shown` above already has
    # them folded in, and handing over both would count every label twice
    _measure_purity(report, formula=formula, adduct=adduct,
                    deuterium=deuterium)
    return explanation, basis, ""


def explain_as(report: InfusionReport, name: str, formula: str,
               adduct: str = "", deuterium: int = 0, entry=None):
    """
    This spectrum explained as a compound the method does not carry yet.

    `_headless_explanation` asks the component table, by name, and refuses
    where the table does not hold the compound: guessing a formula for a
    file name would be inventing the denominator of "n of m". A standard
    being entered from its bottle is the one case where that refusal is
    wrong — the formula is not a guess there, it was typed or resolved from
    the name the analyst wrote, and the labels are a field of their own
    rather than something read off a suffix. So the same three are taken
    directly here and go through the same prediction, the same purity
    measurement and the same basis sentence.

    `formula` is the compound's own, unlabelled; `deuterium` is the count of
    unplaced labels. `adduct` is what the caller has already identified —
    left empty, it is read off the channel's written precursor the way the
    component table's path reads it. Returns `(explanation, basis, note)`,
    with the explanation None and the note saying why where there is none.
    """
    from .components import Component

    formula = str(formula or "").strip()
    name = str(name or "") or report.compound
    if not formula:
        return None, "", f"{name or 'this compound'} carries no formula"
    deuterium = int(deuterium or 0)
    shown, placed = _with_labels(formula, deuterium)
    component = Component(name=name, formula=formula,
                          adduct=str(adduct or ""))
    adduct, why = _headless_adduct(component, report, shown, entry,
                                   source="as this standard was entered",
                                   carries="you expected")
    if not adduct:
        return None, "", why
    clause = (f", with the {placed} unplaced label(s) declared beside it"
              if placed else "")
    return _explained(report, name, formula, deuterium, adduct, why,
                      shown=shown, clause=clause)


def _with_labels(formula: str, labels: int) -> tuple[str, int]:
    """`standards.formula_with_labels`, imported where it is used: the two
    modules must fold labels into a formula the same way or the sentence
    under the table and the component written from it disagree."""
    from .standards import formula_with_labels

    return formula_with_labels(formula, labels)


def _headless_labels(component, report: InfusionReport):
    """
    The labels a component declares in its name but not in its formula.

    A d4 standard is bought, named and filed as `CA-d4`, and the formula
    beside it is usually the unlabelled one: nothing in the component table
    has a column for four deuteriums. The name has them, and
    `chemistry.split_labels` reads a trailing `-d4` the same way the LIPID
    MAPS tab does. Without this the arithmetic is out by 4.025 Da and no
    adduct fits the written precursor at all — which is a true statement
    about the formula as typed and a useless one about the compound.

    A formula that already spells its labels out is left alone: it has said
    what it is.

    The arithmetic is `labelled_formula`'s, which the isolation verdict uses
    on the same component table: a formula labelled one way here and another
    way there would have the report and the verdict disagreeing about the
    same compound.
    """
    return labelled_formula(component.formula, component.name,
                            report.compound)


def _headless_adduct(component, report: InfusionReport,
                     formula: str = "", entry=None,
                     source: str = "from the component table",
                     carries: str = "the component table carries"
                     ) -> tuple[str, str]:
    """
    The adduct to explain this infusion's formula with, and where it came from.

    The component table's own is used when it agrees with the channel's
    written precursor, because that is what the analyst declared. When it
    disagrees — or when the component carries none — the precursor is
    asked instead: it is the one number the instrument was actually given,
    and an ammoniated channel explained as [M+H]+ predicts every fragment
    17 Da away from anything in the spectrum. The reason travels with the
    answer, into the basis line under the table.

    Whatever comes out is written back onto the report, so the summary's
    Adduct cell names the ion the fragments were actually predicted from.
    A declared adduct that the survey contradicts still wins here — it is
    what the analyst said the channel was — but the evidence beside it says
    the survey disagreed, which is the whole point of measuring.

    `source` and `carries` are how the sentence names where the declared
    adduct came from. They are parameters because this is called with a
    component that is not in any table — the New standard dialog's, built
    from what the analyst ticked — and a basis line saying "from the
    component table" about a compound the method has never carried is a
    sentence nobody can check.
    """
    from .chemistry import adducts_matching, identify_adduct

    precursor = report.written_precursor or None
    declared = component.adduct or ""
    formula = formula or component.formula
    if precursor:
        # the survey where the acquisition has one: an adduct measured beats
        # an adduct deduced, and where there is no survey this is the same
        # call it always was, with the report saying so
        choice = (confirm_adduct(entry, report, formula) if entry is not None
                  else None)
        if choice is None:
            choice = identify_adduct(formula, float(precursor),
                                     report.polarity or None)
        if declared:
            fits = [m for m in adducts_matching(formula,
                                                float(precursor),
                                                report.polarity or None)
                    if m.within and m.name == declared]
            if fits:
                report.adduct = declared
                return declared, source
            if choice.adduct is not None:
                report.adduct = choice.adduct.name
                return choice.adduct.name, (
                    f"read off the written precursor — {choice.reason}, "
                    f"not the {declared} {carries}")
            return "", (f"{component.name} is written {declared}, and "
                        f"{choice.reason}")
        if choice.adduct is not None:
            report.adduct = choice.adduct.name
            return choice.adduct.name, f"read off the written precursor — {choice.reason}"
        return "", (f"{component.name} carries no adduct and {choice.reason}")
    if declared:
        report.adduct = declared
        return declared, source
    return "", f"{component.name} carries no adduct"


# --------------------------------------------------------------------------- #
# the mass axis, from this infusion's own precursor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AxisSubject:
    """What an infusion's ladder is predicted from, and where it came from."""

    formula: str = ""
    deuterium: int = 0
    adduct: str = ""
    #: the sentence that says which of the two below answered, and how
    why: str = ""

    def __bool__(self) -> bool:
        return bool(self.formula and self.adduct)


def axis_subject(session, compound: str, written_precursor: float | None,
                 polarity: str = "") -> AxisSubject:
    """
    The formula and adduct to build one infusion's lock-mass ladder from.

    The method's component table first, exactly as the explanation reads it,
    because a component the analyst filled in is a declaration. Where the
    method does not hold the compound the **name** is asked —
    `explain.resolve_name`, the standards table then LIPID MAPS then the
    lipid shorthand — which `_headless_explanation` deliberately refuses to
    do, and the difference is worth stating. A guessed formula is a bad
    denominator for "n of m found": it changes the number of ions offered
    and nothing in the answer says the guess was wrong. It is a safe source
    of a *lock mass*, because a lock mass has to be **found**: a wrong
    formula predicts masses that are not in the spectrum, no rung matches,
    and the fit refuses rather than correcting onto a compound that is not
    in the vial. The two questions have different failure modes and get
    different rules.

    The adduct comes from the written precursor either way, since that is
    the one number the instrument was actually given. The nine real
    infusions are named after the bottle — `CA-d4`, `DCA-d4`, `TDCA-d4` —
    and the standards table answers all three; the two isolating 839.56 get
    no adduct at all, which is the correct answer for a channel that is not
    the compound its file is named after.
    """
    from .chemistry import (FormulaError, format_formula, identify_adduct,
                            parse_formula)
    from .explain import resolve_name

    component = component_for(getattr(session, "method", None), compound)
    formula, deuterium, where = "", 0, ""
    if component is not None and component.formula:
        shim = InfusionReport(compound=compound,
                              written_precursor=written_precursor,
                              polarity=polarity)
        # `_headless_labels` returns the formula with the labels **already
        # folded in** together with how many it folded, and `deuterium` here
        # means "still to fold in". Taking its count as well folded them a
        # second time and made every d4 standard a d8 one: `C24H36D4O5`
        # became `C24H32D8O5`, no adduct of which is within 4 Da of the
        # 430.35 the channel isolates, so the ladder had nothing to look for
        # and every one of the nine real infusions refused its own axis with
        # "no lock mass". `_explained` says the same thing about the
        # explanation's path — "handing over both would count every label
        # twice" — and this is the place that did.
        formula, _folded, _labels = _headless_labels(component, shim)
        where = f"the method's formula for {component.name}"
    if not formula:
        # `resolve_name`, unlike `_headless_labels`, gives the **unlabelled**
        # formula of the stripped name beside the count, so this branch —
        # and only this branch — still has labels to fold in below.
        resolved = resolve_name(compound)
        if resolved is None:
            return AxisSubject(why=f"“{compound or 'this file'}” is not in the "
                                   f"method, in the standards table, in LIPID "
                                   f"MAPS or in the lipid shorthand, so "
                                   f"nothing says what mass to look for")
        formula, deuterium = resolved.formula, resolved.labels
        where = f"{compound} read from {resolved.source}"
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return AxisSubject(why=f"“{formula}” is not a formula this can read")
    if deuterium:
        if counts.get("H", 0) < deuterium:
            return AxisSubject(why=f"{formula} has fewer than the {deuterium} "
                                   f"hydrogen(s) its name replaces")
        counts["D"] = counts.get("D", 0) + deuterium
        counts["H"] -= deuterium
    labelled = format_formula(counts)
    if not written_precursor:
        return AxisSubject(formula=labelled, why=(
            f"{where}, but the channel writes no precursor, so nothing says "
            f"which adduct it was ionised as"))
    choice = identify_adduct(labelled, float(written_precursor),
                             polarity or None)
    if choice.adduct is None:
        return AxisSubject(formula=labelled,
                           why=f"{where}; {choice.reason}")
    return AxisSubject(formula=labelled, deuterium=0,
                       adduct=choice.adduct.name,
                       why=f"{where}; {choice.reason}")


def fit_axis(session, entry, channel, spectrum=None, refit: bool = False,
             cache=None):
    """
    One infusion's mass correction, fitted once and kept on the session.

    `session.mass_corrections[entry.key]` is where every correction in this
    program lives, so the extraction, the report and the mass-drift panel's
    table need nothing new to see this one. The fit is cached there — the
    refusals too, since a vial that was looked at and left alone is a row
    with a reason on it and not a missing row.

    `spectrum` is the **uncorrected** profile average when the caller has it
    already; the correction cannot be fitted from a corrected axis, which is
    why the Explorer passes what it read before applying anything.

    Returns the correction, or None where this is not an infusion or there is
    no session to keep it on.
    """
    from .processing import centroid_spectrum
    from .recalibrate import fit_infusion

    corrections = getattr(session, "mass_corrections", None)
    if corrections is None or entry is None or channel is None:
        return None
    key = getattr(entry, "key", "")
    if not refit and key in corrections:
        return corrections[key]
    sample = getattr(entry, "sample", None)
    try:
        if sample is None or not verdict_for(sample):
            return None
    except Exception:
        return None

    info = getattr(channel, "info", None)
    compound = compound_of(getattr(entry, "name", ""))
    subject = axis_subject(session, compound,
                           getattr(info, "precursor", None),
                           str(getattr(info, "polarity", "") or ""))
    name = str(getattr(entry, "name", "") or "")
    if not subject:
        from .recalibrate import LADDER_SOURCE, MassCorrection

        correction = MassCorrection(
            sample_key=key, sample_name=name, source=LADDER_SOURCE,
            unit="rung",
            note=f"no lock mass: {subject.why}; the axis stands as measured")
        corrections[key] = correction
        return correction

    if spectrum is None:
        averaged = average_spectrum(
            channel, sample=sample, cache=cache,
            path=str(getattr(entry, "path", "") or ""))
        if averaged is None:
            return None
        spectrum = (averaged[0], averaged[1])
    mz, intensity = centroid_spectrum(np.asarray(spectrum[0], dtype=float),
                                      np.asarray(spectrum[1], dtype=float))
    correction = fit_infusion(mz, intensity, subject.formula, subject.adduct,
                              deuterium=subject.deuterium,
                              sample_key=key, sample_name=name)
    if correction is None:
        return None
    correction.note = " · ".join(p for p in (subject.why, correction.note) if p)
    corrections[key] = correction
    return correction


def _best_record(library, report: InfusionReport):
    """The best record of the analyst's own library for this spectrum."""
    from .library import PRECURSOR_TOLERANCE_DA
    from .lipidmaps import mass_precision

    if library is None or not len(library):
        return None, "no library of your own is set"
    sticks = _sticks(report)
    if sticks is None:
        return None, "no spectrum to search"
    precursor = report.written_precursor or None
    tolerance = PRECURSOR_TOLERANCE_DA
    if precursor:
        # the channel's precursor is good to the decimals it was typed with:
        # `430.35` is known to ±0.005, and a filter tighter than that asks
        # for digits the method never carried
        tolerance = max(tolerance, mass_precision(precursor))
    hits = library.search(sticks[0], sticks[1], precursor,
                          precursor_tolerance=tolerance,
                          # the axis these centroids sit on, so the hit can
                          # say whether it and the record were written from
                          # the same one — see `library.axis_gap`
                          query_correction=(report.correction
                                            if report.recalibrated else None))
    if not hits:
        where = (f" within ±{tolerance:g} Da of {precursor:g}"
                 if precursor else "")
        return None, f"no record matched{where}"
    return hits[0], ""


def _energy_match(library, report: InfusionReport, compound: str):
    """
    What the compound's own records across energies make of this spectrum.

    `_best_record` asks which single record this is like, and a record does
    not travel between energies. This asks the other question —
    `library.search_energy`'s — of the one compound the row is grouped under,
    and returns the best-scoring activation that could say anything, or None.

    The activation is chosen by score rather than declared, because a `.wiff`
    does not carry one: `ChannelInfo.activation` is empty on every file this
    program has read, and a row cannot say whether its own infusion was EAD
    or a collision cell. What the profile can say is which of the recorded
    activations the spectrum looks like, at which energy, and that is what
    comes back.

    The compound is looked for under the **file name on disk** as well as
    under the name the row is grouped by, and for the reason
    `infusion_compare` gives: `samples.shorten_names` strips the prefix every
    open sample shares, so three infusions of one standard opened together
    are grouped as `EAD` and `Mix1` while the same three opened beside
    another compound are grouped as `CA-d4`. A library's records are named
    after the compound, so the file name is the one that finds them.
    """
    from .library import match_profile, profile_of

    if library is None or not len(library):
        return None
    sticks = _sticks(report)
    if sticks is None:
        return None
    wanted: list[str] = []
    for name in (compound, compound_of(report.file)):
        if name and name not in wanted:
            wanted.append(name)
    # a `SpectralLibrary` caches its profiles and every row of a compound
    # asks for the same one; anything else duck-typed as a list of records
    # still works, without the cache
    cached = getattr(library, "profile", None)
    for name in wanted:
        profile = (cached(name) if callable(cached)
                   else profile_of(library, name))
        if not profile.points:
            continue
        matches = match_profile(profile, sticks[0], sticks[1])
        found = next((one for one in matches if one.energy is not None), None)
        if found is not None:
            return found
    return None


def _precursor_reason(report: InfusionReport) -> str:
    """Why there is no measured precursor, short enough for a cell."""
    if not report.written_precursor:
        return "none written"
    note = report.survivor_note
    if note.startswith("nothing at all"):
        return f"nothing within ±{_precursor.SEARCH_WINDOW:g} Da"
    if note.startswith("too little"):
        # the height it did find is the part that fits, and the part worth
        # seeing: the whole sentence is on the report and in the tooltip
        found = re.search(r"at most ([\d,.]+) counts", note)
        return (f"under {format_counts(report.floor)} counts"
                if found is None else
                f"only {found.group(1)} counts survive")
    measurement = report.measurement
    if measurement is not None and measurement.note:
        return measurement.note
    return "not measurable"


def summarise(session, library=None, explanations=None,
              progress=None, include_unstable: bool = False,
              cache=None, on_row=None) -> InfusionSummary | None:
    """
    Every open infusion as one row: the summary that comes before the pages.

    One row per infused sample, grouped by the compound its name starts
    with. Each row is a whole `InfusionReport` — the same object the document
    is printed from, so the table and the pages cannot disagree — plus the
    two things a table of many has that a page of one does not: the mutual
    scores between infusions of the same compound, and a reason in every cell
    that could not be filled.

    `explanations` is what has already been run elsewhere, keyed by compound
    (the Explorer's LIPID MAPS tab); a compound with none is explained from
    the component table's formula and adduct where it has them. `library` is
    the analyst's own `SpectralLibrary`, or None for no library column.

    `progress(done, total, name)` is called **before** each infusion is read,
    with the number already finished and the sample about to be read, and
    once more when the last one is done; returning False stops the
    measurement, in which case this returns None. It is called before rather
    than after because what a progress dialog has to say is which file is
    being waited for, not which one has stopped being waited for.
    `on_row(row)` is called as each row is finished, so a table can fill
    itself one file at a time; the mutual scores of a compound's infusions
    are not in it yet, since they need every member of the group, so a caller
    that shows rows early has to read the finished summary again for those.

    `include_unstable` averages every scan rather than only the steady ones —
    the Explorer's *Include unstable scans* — and every row then says so.
    `cache` is a `spectrum_cache.AverageCache`, or None to read every average
    from its file.

    A file that raises on the way through is **one row saying so**, not a
    dead run: nine infusions where the fourth has lost its `.wiff.scan`
    should give eight measurements and a reason, which is what the headless
    folder route already does per file and what this could not do at all.
    """
    import time

    started = time.perf_counter()
    infusions = infusions_open(session)
    if not infusions:
        return InfusionSummary(note="No open sample reads as a direct "
                                    "infusion — see the manual on what makes "
                                    "one.")
    groups: dict[str, list] = {}
    for entry, channel in infusions:
        groups.setdefault(compound_of(getattr(entry, "name", "")),
                          []).append((entry, channel))

    given = {str(k): v for k, v in (explanations or {}).items()}
    name = os.path.basename(getattr(library, "path", "") or "") if library \
        else ""
    method = getattr(session, "method", None)
    rows: list[InfusionRow] = []
    done, total = 0, len(infusions)
    for compound, members in groups.items():
        made: list[InfusionRow] = []
        for entry, channel in members:
            if progress is not None and not progress(
                    done, total, str(getattr(entry, "name", "") or "")):
                return None
            try:
                row = _row_for(session, entry, channel, compound, method,
                               library, name, given, include_unstable, cache)
            except Exception as exc:                # one row, with the reason
                row = _failed_row(entry, channel, compound, exc)
            made.append(row)
            done += 1
            if on_row is not None:
                on_row(row)
        for row in made:
            for other in made:
                if other is row:
                    continue
                score, reverse, pairs = score_against(row.peaks, other.peaks)
                row.others.append((other.sample, float(score), float(reverse),
                                   len(pairs), len(other.peaks)))
            if not row.others and not row.others_note:
                row.others_note = "the only infusion of this compound"
        rows += made
    if progress is not None and not progress(done, total, ""):
        return None
    return InfusionSummary(rows=rows, library=name,
                           seconds=time.perf_counter() - started)


def _failed_row(entry, channel, compound: str, error: Exception) -> InfusionRow:
    """
    A row for an infusion that could not be measured, saying why.

    Everything the file name and the channel already gave is kept — the
    sample, the compound, the channel's written precursor — because a row
    identifying nothing would be indistinguishable from a row about another
    file. The reason goes in every cell that has a note, since which
    measurement failed is not knowable once the exception has been caught.
    """
    reason = f"{type(error).__name__}: {str(error).splitlines()[0]}" \
        if str(error).strip() else type(error).__name__
    report = InfusionReport(
        compound=compound or compound_of(getattr(entry, "name", "")),
        file=getattr(entry, "filename", ""),
        sample=getattr(entry, "name", ""),
    )
    info = getattr(channel, "info", None)
    if info is not None:
        report.polarity = str(getattr(info, "polarity", "") or "")
        report.channel = getattr(info, "label", "")
        report.channel_name = str(getattr(info, "name", "") or "")
        report.written_precursor = getattr(info, "precursor", None)
        report.collision_energy = getattr(info, "collision_energy", None)
        report.scans = int(getattr(info, "n_scans", 0) or 0)
    report.survivor_note = f"could not be measured — {reason}"
    return InfusionRow(report=report, precursor_note=reason,
                       explanation_note=reason, library_note=reason,
                       others_note=reason)


def _row_for(session, entry, channel, compound, method, library, name,
             given, include_unstable, cache) -> InfusionRow:
    """One infusion measured, which is the body of `summarise`'s loop."""
    report = report_for(entry, channel, compound=compound, library=name,
                        components=getattr(method, "components", ()),
                        own_library=library, session=session,
                        include_unstable=include_unstable, cache=cache)
    explanation = given.get(compound)
    note = ""
    if explanation is not None:
        report.explanation = explanation
        report.basis = "what was run in the LIPID MAPS tab"
    else:
        report.explanation, report.basis, note = \
            _headless_explanation(session, report, entry)
        # the same explanation on the axis as the instrument read it, so the
        # mass-axis paragraph can say what the correction bought rather than
        # only what it was
        raw = raw_sticks(report)
        if report.explanation is not None and raw is not None:
            report.raw_explanation = _headless_explanation(
                session, report, entry, sticks=raw)[0]
    hit, library_note = _best_record(library, report)
    report.hit = hit
    # the explanation only reached the report after `report_for` returned,
    # so its margin is measured here instead
    report.margin = _margin.for_report(report, _sticks(report))
    return InfusionRow(
        report=report,
        peaks=score_peaks(report),
        explanation_note=note, library_note=library_note,
        precursor_note=_precursor_reason(report),
        energy=_energy_match(library, report, compound))


def prepare_documents(rows) -> list[InfusionReport]:
    """
    The chosen rows as reports ready to print.

    Each is compared against the other **chosen** infusions of its own
    compound, and against nothing else: a document of two compounds should
    not draw one against the other, and a row left unticked was left unticked
    on purpose. The comparison is made here rather than in `summarise`
    because it holds a copy of both spectra per pair, which is a price worth
    paying for the handful of rows that are printed and not for every row of
    a table.
    """
    from .energy import recommend

    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row.compound, []).append(row)
    for members in groups.values():
        cross_compare([row.report for row in members],
                      [row.peaks for row in members])
        # the energies of the *chosen* rows, for the same reason the
        # comparison is of the chosen rows: a recommendation that ranked an
        # infusion the reader left unticked would be about another document.
        # Only where a choice was actually made — a compound infused at one
        # condition has nothing to choose between and says so in the table,
        # not in a paragraph of the page about the one vial
        written = {}
        for made in recommend(members):
            if not made.choices:
                continue
            paragraph = made.paragraph()
            for condition in made.conditions:
                for point in condition.points:
                    written[point.sample] = paragraph
        for row in members:
            row.report.energy_advice = written.get(row.report.sample, "")
    return [row.report for row in rows]


def write_summary_csv(summary: InfusionSummary, path: str | os.PathLike) -> str:
    """The summary as a CSV, in the order the table holds it."""
    import csv

    path = str(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SUMMARY_COLUMNS)
        for row in summary.rows:
            writer.writerow(row.cells())
    return path


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def _identity(report: InfusionReport) -> str:
    """What this is, from the file rather than from the file name."""
    def value(text) -> str:
        return _escape(text) if text else "—"

    written = ("—" if report.written_precursor is None
               else f"{report.written_precursor:g}")
    energy = ("—" if report.collision_energy is None
              else f"{report.collision_energy:g} eV")
    span = ("—" if report.rt_range is None
            else f"{report.rt_range[0]:.3f}–{report.rt_range[1]:.3f} min")
    accurate = "not measured"
    error = report.error_ppm()
    if report.measurement is not None and report.measurement.found:
        accurate = (f"{report.measurement.measured:.4f} "
                    f"({error:+.1f} ppm, survey scan)")
    elif report.survivor is not None:
        accurate = (f"{report.survivor[0]:.4f} ({error:+.1f} ppm, "
                    f"product-ion scan)")
    elif report.survivor_note or (report.measurement is not None
                                  and report.measurement.note):
        # the reason is a sentence and this is a cell: the verdict below is
        # where it is written out, and a table row that holds a paragraph
        # holds nothing readable
        accurate = "not confirmed — see below"
    rows = [
        ["File", value(report.file), "Sample", value(report.sample)],
        ["Instrument", value(report.instrument), "Polarity",
         value(report.polarity)],
        ["Channel", value(report.channel), "Collision energy", energy],
        ["Precursor, written", written, "Precursor, measured", accurate],
        ["Scans averaged", value(report.scans_line()), "Over", span],
        ["Adduct", value(report.adduct), "Read as", _read_as(report)],
        ["Named", value(report.compound), "Isolated", _isolated(report)],
        ["Adduct evidence", _adduct_cell(report), "Survey",
         value(report.survey_channel) if report.survey_channel
         else "none in this acquisition"],
    ]
    cells = []
    for number, row in enumerate(rows):
        stripe = ' class="alt"' if number % 2 else ""
        cells.append(
            f'<tr{stripe}><td class="label" width="18%">{row[0]}</td>'
            f'<td width="32%">{row[1]}</td>'
            f'<td class="label" width="18%">{row[2]}</td>'
            f'<td width="32%">{row[3]}</td></tr>')
    return (f'<table class="ident" width="100%" cellpadding="4" '
            f'cellspacing="0">{"".join(cells)}</table>')


def _sub(title: str, breaks: set[str] | None = None) -> str:
    """
    A sub-heading, marked to start a fresh page when it was left stranded.

    `report._heading` does this for the h2 of a section; here it has to reach
    the h3s as well, because in this document a sub-heading introduces a
    picture and a picture cannot be split. Without the class the reflow pass
    finds the stranded heading, adds it to `breaks`, and nothing happens —
    which is what left a page a third empty with the figure's title alone at
    the foot of the one before.
    """
    css = ' class="break"' if breaks and title in breaks else ""
    return f"<h3{css}>{_escape(title)}</h3>"


def _adduct_cell(report: InfusionReport) -> str:
    """Whether the survey confirmed the adduct, short enough for a cell."""
    if report.adduct_confirmed:
        best = next((e for e in report.evidence if e.name == report.adduct),
                    None)
        return ("confirmed by the survey"
                if best is None else
                _escape(f"confirmed by the survey: {best.confirmation}"))
    if report.evidence:
        return "not confirmed — see below"
    if report.adduct_note:
        return "no survey — see below"
    return "—"


def _isolated(report: InfusionReport) -> str:
    """
    What the method isolates, in the header cell beside the name it was
    filed under.

    The header is the block that says what this is *from the file rather
    than from the file name*, and the name is on it. Which of the two the
    reader should believe is exactly this cell's job.
    """
    verdict = report.isolation
    if verdict is None:
        return "not checked"
    return _escape(verdict.column())


def _read_as(report: InfusionReport) -> str:
    """The infusion verdict's own figures, in one cell."""
    verdict = report.verdict
    if verdict is None:
        return "—"
    if verdict.infusion:
        return (f"infusion — {verdict.channel_above_half * 100:.0f}% of this "
                f"channel above half maximum")
    return _escape(verdict.reason.split(" — ")[0])


def _picture(comparison: SpectrumComparison,
             width: int = PICTURE_WIDTH, theme: str = "paper") -> str:
    """
    One drawing, and nothing else in the block.

    Qt cannot split an image across a page, so a picture that does not fit
    moves whole and leaves the rest of the page empty. That is why every
    picture here follows its heading immediately and carries its caption
    underneath: `report._orphan_headings` sees the heading separated from
    the block after it and pushes the pair over together, which is the only
    machinery in this program that can move an image and its title as one.
    """
    height = int(round(width * spectra_compare.DEFAULT_HEIGHT
                       / spectra_compare.DEFAULT_WIDTH))
    palette = picture_palette(theme)
    return (f'<p><img src="'
            f'{spectra_compare.data_uri(comparison, palette=palette)}" '
            f'width="{width}" height="{height}" /></p>')


def _verdict(report: InfusionReport, breaks: set[str] | None = None) -> str:
    parts = [_sub("What was measured", breaks),
             '<p class="meta">Every sentence below is a measurement that was '
             'made. There is no overall pass or fail: whether this is the '
             'compound the vial should hold is a judgement for the person '
             'who filled it, made from the evidence on these pages.</p>']
    parts.append("<p>" + " ".join(_escape(s) for s in report.sentences())
                 + "</p>")
    return "".join(parts)


def _floor_sentence(report: InfusionReport) -> str:
    """The noise floor, in one sentence, for the foot of the spectrum."""
    floor = getattr(report, "noise_floor", None)
    if floor is None:
        return ""
    try:
        return floor.describe()
    except Exception:
        return ""


def _mass_axis_block(report: InfusionReport,
                     breaks: set[str] | None = None) -> str:
    """
    What the mass axis was doing, and what was done about it.

    Printed above the spectrum because it governs every mass printed below
    it, and printed even where nothing was corrected: "no lock mass" is a
    statement about this vial, and a page that simply omitted the paragraph
    would leave a reader unable to tell a corrected axis from an
    uncorrected one.
    """
    from .recalibrate import CONSENSUS_SPREAD_PPM, MIN_LADDER_RUNGS

    correction = report.correction
    if correction is None:
        return ""
    parts = [_sub("Mass axis", breaks),
             f'<p class="meta">A direct infusion has no second injection to '
             f'be read against, so it is recalibrated against itself: the '
             f'precursor and every rung of its own ladder — the core ion a '
             f'labile adduct leaves behind, the cumulative waters, and the '
             f'−1D rungs a labelled standard sheds — each of which is a mass '
             f'the formula already knows, measured here. The correction is '
             f'the intensity-weighted median of their errors, sign flipped, '
             f'and an offset only: the rungs of one precursor span the '
             f'waters it can lose, which is far short of the range they '
             f'would be used over. A rung disagreeing with the rest by more '
             f'than {CONSENSUS_SPREAD_PPM:g} ppm is a different ion in the '
             f'window and is dropped; under {MIN_LADDER_RUNGS} rungs, '
             f'nothing is corrected.</p>']
    # the note only where it is not the verdict already: a refusal's verdict
    # *is* its note, and printing it twice reads as two findings
    aside = ("" if correction.note == correction.verdict
             else f' <span class="meta">{_escape(correction.note)}</span>')
    parts.append(f'<p>{_escape(correction.verdict)}'
                 + (" It <b>is</b> applied to every mass on these pages."
                    if report.recalibrated else
                    " It is <b>not</b> applied: the masses on these pages "
                    "are the ones the instrument read.")
                 + aside + "</p>")
    before, after = correction.before_ppm, correction.after_ppm
    order = sorted(range(len(correction.lock_masses)),
                   key=lambda i: -correction.lock_masses[i].intensity)
    rows = []
    for index in order:
        rung = correction.lock_masses[index]
        rows.append([_escape(rung.component), _number(rung.theoretical, 4),
                     _number(rung.measured, 4), f"{before[index]:+.1f}",
                     f"{after[index]:+.1f}", _number(rung.intensity, 0)])
    parts.append(_table(
        ["Rung", "Theoretical m/z", "Measured m/z", "Δ ppm before",
         "Δ ppm after", "Intensity"], rows, right={1, 2, 3, 4, 5},
        empty="No rung of the ladder was found in this spectrum.",
        widths=["26%", "16%", "16%", "14%", "14%", "14%"]))
    parts.append(_ladder_before_after(report))
    parts.append(_ions_before_after(report))
    return "".join(parts)


def _ladder_before_after(report: InfusionReport) -> str:
    """
    How many of the ladder's own ions land on a peak, before and after.

    Counted at `LADDER_CHECK_PPM` and not at the window the rungs were
    *matched* in: that window has to be wide enough to hold the error being
    measured, so counting inside it would show nothing moving. This is the
    one before-and-after that can always be printed — its denominator is the
    precursor's own formula, which is what the paragraph is about — where
    the explanation's, below, needs an explanation to have been run.
    """
    from .explain import match_peaks, precursor_ions, significant_peaks

    subject, correction = report.axis_subject, report.correction
    if not subject or correction is None or not correction.usable:
        return ""
    now = _sticks(report)
    before = raw_sticks(report)
    if now is None or before is None:
        return ""
    ions = precursor_ions(subject.formula, subject.adduct, subject.deuterium)
    if not ions:
        return ""

    def found(sticks) -> int:
        # `significant_peaks` and not every stick in the window: a product
        # scan averaged over a whole run has thousands of baseline centroids
        # and a 5 ppm window somewhere in the middle of one will always hold
        # something. This is the same floor the explanation is scored on, so
        # the two sentences count the same peaks.
        return len(match_peaks(significant_peaks(*sticks), ions,
                               LADDER_CHECK_PPM))

    return (f'<p class="foot">Of the {len(ions):,} ion(s) '
            f'{_escape(subject.formula)} as {_escape(subject.adduct)} can '
            f'give without cutting a bond, {found(before)} landed on a peak '
            f'within {LADDER_CHECK_PPM:g} ppm on the axis as measured and '
            f'{found(now)} once corrected — counted over the peaks above '
            f'the noise share, which is the floor an explanation is scored '
            f'on.</p>')


def _ions_before_after(report: InfusionReport) -> str:
    """
    What the correction bought the explanation, in one sentence.

    The figure that matters is not the residual — the correction was fitted
    to make that small — but how many of the *other* predicted ions land on
    a peak once the axis has moved, at the tolerance the explanation was
    run at. Absent where the same explanation was not run both ways.
    """
    now, before = report.explanation, report.raw_explanation
    if now is None or before is None:
        return ""
    return (f'<p class="foot">At the tolerance this explanation was run at, '
            f'the axis as measured accounted for {before.matched} of '
            f'{before.predicted} predicted ion(s) and '
            f'{before.share * 100:.1f}% of the intensity; corrected, '
            f'{now.matched} of {now.predicted} and '
            f'{now.share * 100:.1f}%.</p>')


def _spectrum_block(report: InfusionReport,
                    breaks: set[str] | None = None,
                    theme: str = "paper") -> str:
    if report.spectrum is None or report.trace is None:
        return (_sub("Averaged spectrum", breaks)
                + '<p class="empty">No spectrum could be read from this '
                'channel.</p>')
    base = report.base_peak()
    peaks = report.peaks()
    parts = [_sub("Averaged spectrum", breaks),
             _picture(report.spectrum, theme=theme),
             f'<p class="foot">Every scan of the channel averaged into one '
             f'spectrum — an infusion has no chromatography to select over, '
             f'so this is the whole of the run. Peaks are labelled at '
             f'{report.label_floor:.2%} of the tallest in view, which is where '
             f'the label floor stood in the Explorer, so the masses printed '
             f'here are the masses that were on screen. '
             + _escape(_floor_sentence(report)) + '</p>']
    rows = []
    top = base[1] if base else 0.0
    for mz, height in peaks:
        rows.append([_number(mz, 4), _number(height, 0),
                     f"{height / top * 100:,.2f}" if top else "—"])
    parts.append(_table(["m/z", "Intensity", "Relative %"], rows,
                        right={0, 1, 2},
                        empty="No peak reaches the label floor.",
                        widths=["34%", "33%", "33%"]))
    if base:
        parts.append(
            f'<p class="foot">Base peak {base[0]:,.4f} at {base[1]:,.0f} '
            f'counts; {len(peaks):,} peak(s) listed of those at or above the '
            f'label floor, strongest first, at most {PEAKS_LISTED}.</p>')
    return "".join(parts)


def _explanation_block(report: InfusionReport,
                       breaks: set[str] | None = None) -> str:
    explanation = report.explanation
    if explanation is None:
        return ""
    labelled = (f" Deuterium is unplaced: every ion is offered carrying 0 to "
                f"{report.deuterium} label(s), and the column says how many "
                f"the fragment kept."
                if report.deuterium else "")
    parts = [_sub(f"Structural explanation — {explanation.name}", breaks)]
    basis = report.basis or (
        f"the formula {explanation.record.formula}" if explanation.record.formula
        else "the candidate structure")
    parts.append(
        f'<p class="meta">Predicted from {_escape(basis)}.'
        f'{labelled} A match is a predicted mass within the tolerance of a '
        f'measured peak; it is arithmetic on a formula, not a mechanism.</p>')
    rows = []
    for match_ in sorted(explanation.matches, key=lambda m: -m.intensity)[
            :FRAGMENTS_LISTED]:
        ion = match_.ion
        labels = getattr(ion, "labels", 0)
        rows.append([
            _escape(match_.best_route),
            _number(ion.mz, 4), _number(match_.mz, 4),
            f"{match_.error_ppm:+.1f}",
            f"{labels:d}" if report.deuterium else "—",
            _number(match_.intensity, 0)])
    parts.append(_table(
        ["Ion", "Theoretical m/z", "Measured m/z", "Δ ppm", "D kept",
         "Intensity"],
        rows, right={1, 2, 3, 4, 5},
        empty="No predicted ion landed on a measured peak.",
        widths=["34%", "14%", "14%", "10%", "10%", "18%"]))
    predicted = (f" of the {explanation.predicted:,} the prediction offered"
                 if explanation.predicted else "")
    parts.append(
        f'<p class="foot">{explanation.matched:,} ion(s) matched{predicted}, '
        f'accounting for {explanation.share * 100:.1f}% of the intensity of '
        f'the {explanation.considered:,} peak(s) that were scored.</p>')
    # the contrast: a share is not evidence until something else has been
    # scored on the same peaks. `margin.py` says what and by how much.
    if report.margin is not None:
        parts.append(f'<p class="foot">Margin — {_escape(explanation.name)} '
                     f'{_escape(report.margin.sentence())}.</p>')

    left = report.unexplained()
    parts.append(_sub("Peaks it does not account for", breaks))
    parts.append(
        '<p class="meta">The honest half of the answer. An explanation that '
        'accounts for part of a spectrum has said nothing about the rest, and '
        'a strong peak here is where a co-infused impurity, an adduct nobody '
        'predicted, or the wrong compound shows itself. Each is offered the '
        'best of three hypotheses — a known contaminant, a satellite of an '
        'ion that was matched, or a composition built from the precursor '
        'ion’s own atoms — with how far it sits from the measured mass. '
        'A row is a suggestion carrying its error, never an assignment.</p>')
    total = report.base_peak()
    top = total[1] if total else 0.0
    # the annotations, where the module that makes them is present and the
    # search would run; without them the table is the masses alone, as it was
    try:
        rows = report.annotations(most=len(left)) if left else []
    except Exception:                           # a search that would not run
        rows = []
    guesses = {round(row.mz, 4): row for row in rows}
    parts.append(_table(
        ["m/z", "Relative %", "What it might be", "Δ ppm"],
        [[_number(mz, 4),
          f"{height / top * 100:,.2f}" if top else "—",
          _escape(_guess_text(guesses.get(round(mz, 4)))),
          _guess_ppm(guesses.get(round(mz, 4)))]
         for mz, height in left],
        right={0, 1, 3},
        empty="Every peak above the label floor is accounted for.",
        widths=["16%", "14%", "56%", "14%"]))
    if rows:
        counted = _unexplained.tally(rows)
        parts.append(
            f'<p class="foot">{counted.accounted} of {counted.peaks} listed '
            f'peak(s) are accounted for by a satellite of something already '
            f'matched or by a known contaminant, {counted.formulas} by a '
            f'composition within the precursor’s own atoms, and '
            f'{counted.nothing} by nothing at all — a peak with no '
            f'sub-formula of the precursor is not a piece of this compound, '
            f'whatever else it is. Matched within '
            f'±{_unexplained.TOLERANCE_PPM:g} ppm.</p>')
    return "".join(parts)


def _guess_text(row) -> str:
    """What one unexplained peak might be, for the table's cell."""
    if row is None:
        return "—"
    said = row.label
    if getattr(row, "rivals", 0):
        said += f" ({row.rivals} other composition(s) reach it)"
    return said


def _guess_ppm(row) -> str:
    return "—" if row is None or row.error_ppm is None else f"{row.error_ppm:+.1f}"


def _purity_block(report: InfusionReport,
                  breaks: set[str] | None = None) -> str:
    """
    The isotopic purity, its envelope, and — where there is none — why not.

    The envelope table goes on the page whether or not a fraction came out of
    it, because the refusal is a statement about those numbers and a reader
    who cannot see them cannot check it.
    """
    result = report.purity
    if result is None:
        return ""
    n = result.labels
    parts = [_sub("Isotopic purity", breaks),
             f'<p class="meta">The species distribution of the labelled '
             f'standard — how much of it is d{n}, how much d{n - 1} and so on '
             f'— solved from the envelope at {_escape(result.ion)}, '
             f'{result.at:.4f}. It is a deconvolution and not a set of '
             f'ratios: each species’ carbon-13 satellite lands 2.9 mDa from '
             f'the next species’ own peak, which no ordinary instrument '
             f'separates. The atom % D underneath is the quantity a '
             f'certificate states and is a different number.</p>']
    names = [f"d{i}" for i in range(n + 1)] + ["M+1", "M+2"]
    top = result.measured[n] if len(result.measured) > n else 0.0
    rows = []
    for index, name in enumerate(names[:len(result.measured)]):
        share = (f"{result.measured[index] / top * 100:,.3f}"
                 if top else "—")
        fraction = ("—" if index >= len(result.fractions)
                    else f"{result.fractions[index] * 100:,.2f}")
        rows.append([name, _number(result.positions[index], 4),
                     _number(result.measured[index], 0), share, fraction])
    parts.append(_table(
        ["Rung", "m/z", "Intensity", f"% of d{n}", "Fraction %"], rows,
        right={1, 2, 3, 4},
        empty="No rung of the envelope could be read.",
        widths=["12%", "22%", "22%", "22%", "22%"]))
    if result.usable:
        atom = result.atom_percent
        parts.append(
            f'<p class="foot">d{n} {result.purity * 100:.1f}%'
            + (f', ≥d{n - 1} {result.at_least * 100:.1f}%' if n >= 1 else "")
            + (f', ±{result.uncertainty * 100:.1f}% on a floor of '
               f'{result.floor:,.0f} counts' if result.uncertainty is not None
               else "")
            + (f'; {atom:.2f} atom % D over the {n} labelled positions.'
               if atom is not None else ".")
            + (' Read from a fragment, so this is a lower bound: a '
               'dehydration can leave with a label.' if result.lower_bound
               else "")
            + '</p>')
    else:
        satellite = result.satellite_ratio
        measured = ("" if satellite is None else
                    f' The d{n} ion shows {satellite * 100:.2f}% of the '
                    f'carbon-13 satellite its own formula demands.')
        parts.append(
            f'<p class="foot">No purity was read from this envelope: '
            f'{_escape(result.reason)}.{measured} The rungs above are what '
            f'that judgement was made on.</p>')
    return "".join(parts)


def _library_block(report: InfusionReport,
                   breaks: set[str] | None = None,
                   theme: str = "paper") -> str:
    hit = report.hit
    if hit is None:
        return ""
    entry = hit.entry
    where = f" in {_escape(report.library)}" if report.library else ""
    parts = [_sub(f"Library — {entry.name}", breaks)]
    comparison = _hit_picture(report)
    if comparison is not None:
        parts.append(_picture(comparison, theme=theme))
        parts.append('<p class="foot">The measured spectrum above, the record '
                     'below, both drawn as centroids on their own base peak. '
                     'A record is already sticks, so nothing here is '
                     'centroided a second time — doing that averages a stick '
                     'with its neighbour and moves the mass.</p>')
    parts.append(
        f'<p class="meta">The best record{where}. The score is the cosine '
        f'over everything both spectra hold; the reverse asks only whether '
        f'the record’s peaks are in the measured one, so a high reverse with '
        f'a low score is this compound with company.</p>')
    delta = "—" if hit.delta_ppm is None else f"{hit.delta_ppm:+.1f}"
    parts.append(_table(
        ["Score", "Reverse", "Matched", "Record precursor", "Δ ppm"],
        [[f"{hit.score * 100:.0f}", f"{hit.reverse * 100:.0f}",
          f"{hit.matched} of {hit.of_library}",
          "—" if entry.precursor is None else _number(entry.precursor, 4),
          delta]],
        right={0, 1, 2, 3, 4},
        widths=["18%", "18%", "20%", "24%", "20%"]))

    provenance = []
    if entry.precursor_type:
        provenance.append(["Precursor type", _escape(entry.precursor_type)])
    if entry.formula:
        provenance.append(["Formula", _escape(entry.formula)])
    for key, value in (entry.fields or {}).items():
        provenance.append([_escape(key), _escape(value)])
    if entry.source:
        provenance.append(["Source", _escape(os.path.basename(entry.source))])
    parts.append(_sub("Where the record came from", breaks))
    parts.append(
        '<p class="meta">The record’s own fields, as they were written. A '
        'record whose provenance is not on the page cannot be checked against '
        'the acquisition it was made from.</p>')
    parts.append(_table(None, provenance,
                        empty="The record carries no fields of its own.",
                        widths=["28%", "72%"]))
    return "".join(parts)


def _hit_picture(report: InfusionReport) -> SpectrumComparison | None:
    """
    The measured spectrum against the record it matched, head to tail.

    A library record **is** centroids, and the measured average is profile, so
    the measured one is centroided here and the comparison is told they are
    sticks. Without that the picture is drawn as a polyline through the
    record's sticks and its labels are centroids taken *across* them: the
    first version of this page drew the cholic acid record as one spike
    labelled 359.6428, for a record whose base peak is 359.2870.
    """
    hit, trace = report.hit, report.trace
    if hit is None or trace is None or hit.entry.mz.size == 0:
        return None
    already = bool(report.spectrum.centroid) if report.spectrum else False
    mz, intensity = trace.mz, trace.intensity
    if not already:
        from .processing import centroid_spectrum

        mz, intensity = centroid_spectrum(mz, intensity)
    # no title inside the drawing: the heading above it says the same words,
    # and the legend already names which trace is which
    return head_to_tail(
        trace.label, mz, intensity,
        hit.entry.name, hit.entry.mz, hit.entry.intensity,
        title="", centroid=True, label_floor=report.label_floor)


def _compared_block(report: InfusionReport,
                    breaks: set[str] | None = None,
                    theme: str = "paper") -> str:
    if not report.compared:
        return ""
    parts = [_sub("Other infusions of the same compound", breaks),
             f'<p class="meta">Each one averaged over its own whole run and '
             f'drawn head to tail against this one, both on their own base '
             f'peak. The score is the same cosine a library search takes, '
             f'over the peaks at or above {SCORE_SHARE:.0%} of each '
             f'spectrum’s base peak — the floor a library search itself '
             f'uses, not the drawing’s label floor; the reverse asks whether '
             f'the other spectrum’s peaks are in this one, which is what an '
             f'infusion at a lower collision energy needs.</p>']
    parts.append(_table(
        ["Infusion", "Score", "Reverse", "Matched", "How it was acquired"],
        [[_escape(other.label), f"{other.score * 100:.0f}",
          f"{other.reverse * 100:.0f}",
          f"{other.matched} of {other.of_other}", _escape(other.note)]
         for other in report.compared],
        right={1, 2, 3},
        widths=["38%", "11%", "11%", "16%", "24%"]))
    for other in report.compared:
        parts.append(_sub(f"Against {other.label}", breaks))
        parts.append(_picture(other.comparison, theme=theme))
    return "".join(parts)


def _energy_block(report: InfusionReport,
                  breaks: set[str] | None = None) -> str:
    """
    Which of this compound's energies to use, and for what.

    Written only where the document holds more than one condition of the
    compound — `prepare_documents` fills the field and leaves it empty
    otherwise, so a compound infused once has no paragraph rather than a
    paragraph saying there was nothing to compare. The sentences are
    `energy.EnergyRecommendation.paragraph`'s, so the page, the dialog and
    the CSV cannot disagree about the same arithmetic.
    """
    if not report.energy_advice:
        return ""
    return "".join([
        _sub("Collision energy", breaks),
        '<p class="meta">Three questions and three answers, which do not '
        'have to be the same energy: the most predicted ions with the '
        'precursor still standing identifies, one fragment holding as much '
        'of the spectrum as it can quantifies, and the middle of the '
        'energies measured makes a record another instrument can match. '
        'Only the energies that were acquired are offered.</p>',
        f"<p>{_escape(report.energy_advice)}</p>"])


def build_section(report: InfusionReport, heading: str = "",
                  breaks: set[str] | None = None,
                  theme: str = "paper") -> str:
    """
    One compound: the heading, the header, the verdict and the blocks.

    An empty `heading` leaves the heading off entirely, which is what a
    document of one compound wants — its title block already names the
    compound, and a page whose first two lines are the same words twice
    reads as a mistake.
    """
    return "".join([
        _heading(heading, breaks) if heading else "",
        _identity(report),
        _verdict(report, breaks),
        _mass_axis_block(report, breaks),
        _spectrum_block(report, breaks, theme),
        _explanation_block(report, breaks),
        _purity_block(report, breaks),
        _library_block(report, breaks, theme),
        _compared_block(report, breaks, theme),
        _energy_block(report, breaks),
    ])


def _title_block(title: str, reports: list[InfusionReport]) -> str:
    """
    What this is, on the page rather than in a file name.

    One compound gets the eyebrow and the title alone: the identity table
    underneath already carries the file, the sample, the instrument and the
    time. Only a document of several needs a count in front of them.
    """
    from . import __version__

    head = (f'<p class="eyebrow">MIL-Q {_escape(__version__)} · direct '
            f'infusion report</p><h1>{_escape(title)}</h1>')
    if len(reports) < 2:
        return head
    when = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    files = len({r.file for r in reports if r.file})
    return (
        head
        + f'<table class="ident" width="100%" cellpadding="4" cellspacing="0">'
        f'<tr><td class="label" width="18%">Compounds</td>'
        f'<td width="32%">{len(reports):,}</td>'
        f'<td class="label" width="18%">Generated</td><td width="32%">{when}</td>'
        f'</tr><tr class="alt"><td class="label">Acquisitions</td>'
        f'<td>{files:,}</td><td class="label">Instrument</td>'
        f'<td>{_escape(reports[0].instrument) if reports else "—"}</td></tr>'
        f"</table>")


def _contents(headings: list[str], pages: dict[str, int] | None) -> str:
    if len(headings) < 2:
        return ""
    rows = []
    for number, heading in enumerate(headings):
        stripe = ' class="alt"' if number % 2 else ""
        page = "" if not pages else str(pages.get(heading, ""))
        cell = (f'<td class="num" width="8%">{page}</td>'
                if pages is not None else "")
        rows.append(f'<tr{stripe}><td>{_escape(heading)}</td>{cell}</tr>')
    return ('<h2 class="plain">Contents</h2>'
            '<table class="contents" width="60%" cellpadding="3" '
            f'cellspacing="0">{"".join(rows)}</table>')


def _as_list(reports) -> list[InfusionReport]:
    if isinstance(reports, InfusionReport):
        return [reports]
    return list(reports)


def default_title(reports: list[InfusionReport]) -> str:
    if len(reports) == 1:
        return f"{reports[0].title} — direct infusion"
    return "Direct infusion report"


def build_html(reports, title: str = "", contents: dict[str, int] | None = None,
               breaks: set[str] | None = None, theme: str = "paper") -> str:
    """
    One compound, or every one of them, as one HTML document.

    `contents` and `breaks` are what `report.print_document` works out for
    itself — None for no page column, `{}` to reserve one, the mapping on the
    final pass — so the two documents are printed through the same code and
    the heading that ends a page is chased in one place. `theme` is the
    batch report's: the same three style sheets and the same palette for
    every picture, since these pages are mostly pictures.
    """
    reports = _as_list(reports)
    title = title or default_title(reports)
    headings = ([f"{number}. {r.title}"
                 for number, r in enumerate(reports, start=1)]
                if len(reports) > 1 else [""] * len(reports))
    breaks = set(breaks or ())
    if len(reports) > 1:
        # a compound starts a page of its own: a section that begins half way
        # down the page under the end of another compound reads as one report
        breaks |= set(headings[1:])
    parts = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'>",
             f"<title>{_escape(title)}</title>",
             f"<style>{style_for(theme)}</style></head><body>",
             _title_block(title, reports),
             _contents(headings, contents)]
    for heading, report in zip(headings, reports, strict=True):
        parts.append(build_section(report, heading, breaks, theme))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(reports, path: str | os.PathLike, **kwargs) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(reports, **kwargs))
    return path


def write_pdf(reports, path: str | os.PathLike, **kwargs) -> str:
    """
    The report on A4 portrait pages, through the batch report's printer.

    One compound comes to one to three pages, depending on what was run; a
    batch is one section per compound, each starting on a page of its own.
    """
    reports = _as_list(reports)
    title = kwargs.pop("title", "") or default_title(reports)
    theme = kwargs.pop("theme", "paper")
    return print_document(
        lambda contents, breaks: build_html(reports, title=title,
                                            contents=contents, breaks=breaks,
                                            theme=theme),
        path, title, reflows=REFLOWS, theme=theme)
