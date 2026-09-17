"""
An infused standard written into the method, with what it learnt and where
each part came from.

An infusion is how a vial is verified: spray it, average the whole run, read
the precursor, see which fragments the structure allows, search the record
made of the same compound last month. `infusion_report.py` puts all of that
on paper. What it did not do was carry any of it forward — the analyst read
the pages and then typed the compound into the component table by hand, from
the same numbers, with nothing saying afterwards which of them were measured
and which were remembered.

This module is that carry. One infusion row becomes one `Component`:

- **name** from the compound the file is named after;
- **formula** from whatever the infusion was actually explained with,
  carrying the labels the name declares (`CA-d4` is four deuteriums the
  formula beside it almost never spells out);
- **adduct** from `chemistry.identify_adduct` against the channel's own
  written precursor, which is the one number the instrument was given;
- **precursor** the *exact* mass of that adduct — never the written one, see
  `Identification` below;
- **fragment** the base peak of the averaged product-ion spectrum, or a peak
  the analyst picks instead;
- **no retention time.** An infusion has none: there is no chromatography in
  it. The field stays empty and `health.check_method` already reports a
  standard without a time, which is the right place for it to be said.
- **provenance**, in words, so that six months later the row says which
  infusion it came from rather than looking like something somebody typed.

Nothing here writes over a typed value. A compound the method already carries
is *completed* — only its empty cells are filled — and where a value that is
already there disagrees with the infusion, the disagreement is reported and
the typed value is kept. `Plan` holds both lists and the dialog shows them
before anything is written.

Read defensively, on purpose: a row is asked for its attributes with
`getattr` and settles for nothing, so this module holds together while
`infusion_report.py` and `library.py` grow fields of their own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import chemistry
from .components import DEFAULT_TOLERANCE, Component

#: what a component made this way is grouped under, so the rows the standards
#: contribute can be picked out of a method that came from somewhere else
GROUP = "standards"

#: the default fragment: the tallest peak of the averaged product-ion
#: spectrum. A string rather than a number because it is a *rule* — which
#: peak is tallest is the spectrum's business — and because it is what the
#: dialog's first entry means.
BASE_PEAK = "base peak"

#: how many peaks the fragment box offers beside the base peak
FRAGMENT_CHOICES = 5

#: how far two masses may sit apart and still be the same number written
#: twice. Ten micro-daltons: `430.3465` typed to four decimals comes back as
#: itself, and the 3.5 mDa between a written `430.35` and the exact mass is
#: a hundred times this, so a disagreement worth showing is never mistaken
#: for a rounding of our own.
SAME_MASS_DA = 1e-5

#: how near the chosen fragment has to sit to the precursor before the row
#: says it *is* the precursor: the extraction window a component gets by
#: default, taken from `components` rather than written again here. Nearer
#: than that and the two masses would be pulled out by the same window,
#: which is the sense in which they are one ion.
PRECURSOR_AS_FRAGMENT_DA = DEFAULT_TOLERANCE


# --------------------------------------------------------------------------- #
# where it came from
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Provenance:
    """Which infusion a component was written from."""

    file: str = ""
    sample: str = ""
    channel: str = ""
    energy: float | None = None
    #: when the instrument acquired it, as the file writes it. Empty where
    #: the reader does not say — a component whose provenance carries no date
    #: is still worth having, and inventing today's date for it is not.
    acquired: str = ""
    #: the name of the record in the analyst's own library that this
    #: spectrum matched, where one was searched and one was found
    record: str = ""
    #: the bottle the standard was infused from, where somebody typed one.
    #: The one field here that is not in the acquisition: a component made
    #: from a vial is only traceable to that vial if the vial is named.
    lot: str = ""

    @property
    def text(self) -> str:
        """
        The one line the component carries and the audit entry repeats.

        Written as a sentence rather than as fields joined by pipes: it is
        read in a tooltip and in a trail, both of which are prose, and a row
        of empty separators is what a missing field looks like when it is
        not.
        """
        said = []
        if self.channel:
            said.append(f"channel {self.channel}")
        if self.energy is not None:
            said.append(f"{float(self.energy):g} eV")
        if self.file and self.file != self.sample:
            said.append(f"file {self.file}")
        if self.acquired:
            said.append(f"acquired {self.acquired}")
        if self.record:
            said.append(f"own record “{self.record}”")
        if self.lot:
            said.append(f"lot {self.lot}")
        head = f"From the infusion {self.sample}" if self.sample else \
            "From an infusion"
        return f"{head}: " + "; ".join(said) if said else head

    @property
    def short(self) -> str:
        """
        The same thing in what an audit entry has room for.

        `audit.MAX_LENGTH` is 160 characters and the full sentence is half as
        long again on a real file name, so the trail would show it cut in the
        middle of the acquisition time. What is dropped is the channel and
        the file — the channel is the compound's own precursor said twice and
        the file name repeats the sample — and what is kept is what
        identifies the acquisition: which infusion, at what energy, on what
        day. The component itself carries the whole sentence.
        """
        said = [f"from {self.sample}" if self.sample else "from an infusion"]
        if self.energy is not None:
            said.append(f"{float(self.energy):g} eV")
        if self.acquired:
            said.append(f"acquired {self.acquired}")
        if self.record:
            said.append(f"record “{self.record}”")
        if self.lot:
            said.append(f"lot {self.lot}")
        return ", ".join(said)


def provenance_of(report, acquired: str = "", lot: str = "") -> Provenance:
    """The provenance of one infusion report, read defensively."""
    hit = getattr(report, "hit", None)
    entry = getattr(hit, "entry", None)
    energy = getattr(report, "collision_energy", None)
    return Provenance(
        file=str(getattr(report, "file", "") or ""),
        sample=str(getattr(report, "sample", "") or ""),
        channel=str(getattr(report, "channel", "")
                    or getattr(report, "channel_name", "") or ""),
        energy=None if energy is None else float(energy),
        acquired=str(acquired or ""),
        record=str(getattr(entry, "name", "") or ""),
        lot=str(lot or ""),
    )


def acquisition_time(session, sample_name: str) -> str:
    """
    When the instrument acquired the sample of that name, or "".

    The report holds the sample's *name*, not its reader, so the date is
    fetched from the session by name here rather than being carried through
    `infusion_report`. Nothing is opened: an entry whose file is closed says
    nothing and the provenance leaves the date out.
    """
    for entry in getattr(session, "entries", ()) or ():
        if str(getattr(entry, "name", "")) != str(sample_name):
            continue
        sample = getattr(entry, "sample", None)
        try:
            return str(getattr(sample, "acquisition_time", "") or "")
        except Exception:                       # a reader that cannot say
            return ""
    return ""


# --------------------------------------------------------------------------- #
# what the infusion says the compound is
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Identification:
    """
    The formula, the adduct and the mass, and where each came from.

    **The precursor is the exact mass of the identified adduct, and not the
    number written on the channel.** The two are different claims. The
    written value — `430.35` — is what the instrument was actually given, so
    it is what picked the channel and what the acquisition is on; it is good
    only to the decimals somebody typed, ±0.005 here, which is 12 ppm. The
    exact mass — 430.3465 — is what the compound weighs as that adduct, and
    it is what an extraction window, a lock mass and a mass-accuracy check
    have to be built from. Writing the rounded one into the method would put
    a 12 ppm error into every one of those on purpose.

    So the exact mass is what the component carries and both are printed
    side by side wherever this is offered: the dialog's Note column, the
    audit entry and the provenance all say what was written and what was
    taken, and `error_ppm` is the distance between them. Nothing silently
    replaces a number the analyst can no longer see.
    """

    formula: str = ""
    #: deuterium the name declares and the formula did not spell out
    labels: int = 0
    adduct: str = ""
    #: the m/z of the formula as that adduct
    exact: float | None = None
    #: the channel's own precursor, as the method wrote it
    written: float | None = None
    formula_source: str = ""
    adduct_source: str = ""
    #: why there is no mass, when there is none
    refusal: str = ""

    def __bool__(self) -> bool:
        return self.exact is not None

    @property
    def error_ppm(self) -> float | None:
        """How far the written precursor sits from the exact mass."""
        if self.exact is None or not self.written:
            return None
        return (self.written - self.exact) / self.exact * 1e6

    @property
    def note(self) -> str:
        """The two masses side by side, in one line."""
        if self.exact is None:
            return self.refusal
        said = f"{self.adduct} of {self.formula} is {self.exact:.4f}"
        error = self.error_ppm
        if error is not None:
            said += (f"; the channel is written {self.written:g}, "
                     f"{error:+.1f} ppm")
        return said


def formula_with_labels(formula: str, labels: int) -> tuple[str, int]:
    """
    A formula with `labels` of its hydrogens replaced by deuterium, and how
    many were placed.

    A d4 standard is bought, named and filed as `CA-d4` and the formula
    written beside it is nearly always the unlabelled one — no component
    table has a column for four deuteriums. Without this the arithmetic is
    4.025 Da out and no adduct fits the channel at all. A formula that
    already spells its labels out has said what it is and is left alone.
    """
    if not formula:
        return "", 0
    try:
        counts = dict(chemistry.parse_formula(formula))
    except (chemistry.FormulaError, ValueError):
        return formula, 0
    if counts.get("D") or labels <= 0 or counts.get("H", 0) < labels:
        return formula, int(counts.get("D", 0) or 0)
    counts["D"] = labels
    counts["H"] -= labels
    return chemistry.format_formula(counts), labels


def _formula_from(report, method=None) -> tuple[str, int, str]:
    """
    The compound's formula, its unplaced labels, and where it came from.

    Three sources, in the order of how much they were checked against this
    spectrum: the explanation the report was actually scored with, the
    component the method already carries under the same name, and — where
    neither exists — the name itself through `explain.resolve_name`, which
    knows the bile-acid standards by the abbreviation on the bottle.
    """
    from .explain import resolve_name

    compound = str(getattr(report, "compound", "") or "")
    names = [n for n in (compound, str(getattr(report, "sample", "") or ""))
             if n]

    def with_labels(formula: str, source: str) -> tuple[str, int, str]:
        declared = int(getattr(report, "deuterium", 0) or 0)
        for written in names:
            if declared:
                break
            _stem, declared = chemistry.split_labels(written)
        formula, labels = formula_with_labels(formula, declared)
        return formula, labels, source

    explanation = getattr(report, "explanation", None)
    record = getattr(explanation, "record", None)
    formula = str(getattr(record, "formula", "") or "")
    if formula:
        return with_labels(formula, "the explanation this spectrum was scored "
                                    "against")
    # the formula the report was built with: what the analyst typed into the
    # dialog, labelled by `report_for`. A typed formula is a decision, and
    # resolving the name again behind it found a different compound on a
    # machine with LIPID MAPS installed (`Testol` → testolactone) and nothing
    # on one without, so the same file was refused for two different reasons
    built_with = str(getattr(report, "formula", "") or "")
    if built_with:
        return with_labels(built_with, "the formula this report was built with")
    existing = component_named(method, compound)
    if existing is not None and existing.formula:
        return with_labels(existing.formula, "the component table")
    named = resolve_name(compound) if compound else None
    if named is not None and getattr(named, "formula", ""):
        formula, labels = formula_with_labels(
            named.formula, int(getattr(named, "labels", 0) or 0))
        return formula, labels, getattr(named, "source", "") or "the name"
    return "", 0, ""


def identify(report, method=None) -> Identification:
    """
    What this infusion says the compound is: formula, adduct, exact mass.

    The adduct is read off the channel's written precursor
    (`chemistry.identify_adduct`) unless the report already carries one that
    fits — the LIPID MAPS tab's, which is what the spectrum was explained as.
    Where nothing fits, there is no mass and `refusal` says why in the
    sentence `identify_adduct` wrote: a component with a made-up precursor
    is worse than no component.
    """
    written = getattr(report, "written_precursor", None)
    written = float(written) if written else None
    polarity = str(getattr(report, "polarity", "") or "") or None
    formula, labels, formula_source = _formula_from(report, method)
    if not formula:
        return Identification(
            written=written,
            refusal=f"no formula for "
                    f"{getattr(report, 'compound', '') or 'this compound'}: "
                    f"the name resolves to nothing and the method does not "
                    f"carry it")

    declared = str(getattr(report, "adduct", "") or "")
    choice = None
    source = ""
    if written:
        choice = chemistry.identify_adduct(formula, written, polarity)
        if declared:
            fits = [m for m in chemistry.adducts_matching(formula, written,
                                                          polarity)
                    if m.within and m.name == declared]
            if fits:
                adduct, source = declared, "as this spectrum was explained"
            elif choice.adduct is not None:
                adduct, source = choice.adduct.name, (
                    f"read off the written precursor — {choice.reason}, "
                    f"not the {declared} the spectrum was explained as")
            else:
                return Identification(
                    formula=formula, labels=labels,
                    formula_source=formula_source, written=written,
                    refusal=f"explained as {declared}, and {choice.reason}")
        elif choice.adduct is not None:
            adduct, source = choice.adduct.name, (
                f"read off the written precursor — {choice.reason}")
        else:
            return Identification(
                formula=formula, labels=labels,
                formula_source=formula_source, written=written,
                refusal=choice.reason)
    elif declared:
        adduct, source = declared, "as this spectrum was explained"
    else:
        return Identification(
            formula=formula, labels=labels, formula_source=formula_source,
            refusal="the channel writes no precursor and nothing says which "
                    "adduct this is")

    exact = chemistry.mass_from_formula(formula, adduct)
    if exact is None:
        return Identification(
            formula=formula, labels=labels, formula_source=formula_source,
            adduct=adduct, adduct_source=source, written=written,
            refusal=f"{adduct} of {formula} is not a mass this can compute")
    return Identification(formula=formula, labels=labels, adduct=adduct,
                          exact=float(exact), written=written,
                          formula_source=formula_source, adduct_source=source)


# --------------------------------------------------------------------------- #
# the fragment
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FragmentChoice:
    """One peak of the averaged spectrum, offered as the fragment."""

    mz: float
    intensity: float
    #: what the explanation calls it, where the row has one
    label: str = ""
    #: is this the tallest peak of the spectrum?
    base: bool = False

    @property
    def text(self) -> str:
        said = f"{self.mz:.4f}"
        if self.base:
            said += " (base peak)"
        said += f" — {self.intensity:,.0f} counts"
        if self.label:
            said += f", {self.label}"
        return said


def fragment_choices(report, most: int = FRAGMENT_CHOICES
                     ) -> list[FragmentChoice]:
    """
    The peaks worth offering as the fragment, strongest first.

    The report's own peak list, which is the one above the label floor the
    pane was left at — so what is offered here is what was named on the
    picture, and a peak nobody could see on screen is not silently proposed
    as a transition. Each is labelled with the ion the explanation matched
    to it where there is one, because `359.2870` means nothing and
    `[M+H-3H2O]+` means the fragment somebody expected.
    """
    peaks = []
    try:
        peaks = list(report.peaks(most=max(int(most), 1)))
    except Exception:                           # a report with no spectrum
        peaks = []
    if not peaks:
        base = None
        try:
            base = report.base_peak()
        except Exception:
            base = None
        peaks = [base] if base else []
    labels = _explained_labels(report)
    top = max((float(p[1]) for p in peaks), default=0.0)
    out = []
    for mz, intensity in peaks[:max(int(most), 1)]:
        mz, intensity = float(mz), float(intensity)
        out.append(FragmentChoice(
            mz=mz, intensity=intensity,
            label=labels.get(round(mz, 4), ""),
            base=bool(top and intensity >= top)))
    return out


def _explained_labels(report) -> dict[float, str]:
    """What the explanation calls each peak it matched, keyed by m/z."""
    explanation = getattr(report, "explanation", None)
    matches = getattr(explanation, "matches", None) or ()
    labels: dict[float, str] = {}
    for match in matches:
        ion = getattr(match, "ion", None)
        name = str(getattr(ion, "description", "")
                   or getattr(ion, "name", "") or "")
        try:
            labels[round(float(match.mz), 4)] = name
        except (TypeError, ValueError, AttributeError):
            continue
    return labels


def _fragment_mass(report, fragment) -> float | None:
    """The chosen fragment as a mass, or None where there is nothing to take."""
    if fragment is None:
        return None
    if isinstance(fragment, FragmentChoice):
        return float(fragment.mz)
    if isinstance(fragment, (int, float)) and not isinstance(fragment, bool):
        return float(fragment)
    if str(fragment).strip().lower() == BASE_PEAK:
        # the tallest of the offered peaks and not `report.base_peak()`,
        # which is the tallest *point* of the profile trace: the two differ
        # by a fraction of a milli-dalton (377.3015 against 377.30176 on a
        # real infusion) and the one the dialog shows has to be the one the
        # component gets. The picked value is the better mass anyway — it is
        # a centroid rather than whichever sample happened to be highest.
        choices = fragment_choices(report, most=1)
        if choices:
            return float(choices[0].mz)
        try:
            base = report.base_peak()
        except Exception:
            base = None
        return float(base[0]) if base else None
    try:
        return float(str(fragment).replace(",", "."))
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# the component
# --------------------------------------------------------------------------- #
def report_of(row_or_report):
    """A row from the summary, or the report itself; either is accepted."""
    return getattr(row_or_report, "report", row_or_report)


def component_from_infusion(row_or_report, as_internal_standard: bool = True,
                            fragment=BASE_PEAK, acquired: str = "",
                            method=None, lot: str = "") -> Component | None:
    """
    One infusion as a component of the method.

    `row_or_report` is an `infusion_report.InfusionRow` or the
    `InfusionReport` inside it. `fragment` is `BASE_PEAK`, a mass, or a
    `FragmentChoice`.

    **The precursor is the exact mass of the identified adduct and not the
    value written on the channel.** The written number is what the instrument
    was given — it is the channel, and it is good only to the decimals it was
    typed with — while the exact mass is what the compound weighs as that
    adduct, and it is what a window, a lock mass and a mass-accuracy check
    are built from. The two are printed side by side wherever this is offered
    (`Identification.note`, the dialog, the audit entry), so nothing replaces
    a number the analyst cannot still see.

    **There is no retention time.** An infusion is not a separation and has
    none to give; the field stays empty rather than being filled with the
    middle of the run, and `health.check_method` reports a standard without
    one, which is where that belongs.

    None when the compound cannot be identified — no formula, or no adduct
    that fits the written precursor. A component with an invented mass is
    worse than no component, and `identify(...).refusal` is the sentence
    that says which.
    """
    report = report_of(row_or_report)
    name = str(getattr(report, "compound", "")
               or getattr(report, "sample", "") or "").strip()
    if not name:
        return None
    identification = identify(report, method)
    if identification.exact is None:
        return None
    return Component(
        name=name,
        precursor=float(identification.exact),
        fragment=_fragment_mass(report, fragment),
        rt=None,
        group=GROUP,
        formula=identification.formula,
        adduct=identification.adduct,
        is_internal_standard=bool(as_internal_standard),
        provenance=provenance_of(report, acquired, lot).text,
    )


def component_named(method, name: str) -> Component | None:
    """
    The method's component of that name, matched the way a person would.

    Exactly, then without regard to case or surrounding space. Nothing
    cleverer: `CA-d4` and `CA-d4 IS` are two rows somebody made on purpose,
    and guessing that they are one is how an infusion completes the wrong
    component.
    """
    components = list(getattr(method, "components", ()) or ())
    wanted = str(name or "").strip()
    if not wanted:
        return None
    for component in components:
        if component.name == wanted:
            return component
    flat = wanted.lower()
    for component in components:
        if str(component.name).strip().lower() == flat:
            return component
    return None


# --------------------------------------------------------------------------- #
# what writing it would do
# --------------------------------------------------------------------------- #
#: the fields an infusion can fill, as the method table names them
_FIELDS: tuple[tuple[str, str], ...] = (
    ("precursor", "Precursor"),
    ("fragment", "Fragment"),
    ("formula", "Formula"),
    ("adduct", "Adduct"),
    ("group", "Group"),
    ("provenance", "Provenance"),
)


def _empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, float):
        return value == 0.0
    return not value


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, abs_tol=SAME_MASS_DA)
    return str(a).strip() == str(b).strip()


def _shown(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}" if value else ""
    return str(value)


@dataclass
class Plan:
    """
    What writing one infusion into the method would do, before it does it.

    Three lists, and the dialog shows all three: what would be **filled**
    (empty cells only), what **disagrees** (a typed value the infusion would
    contradict, kept as it is), and why the row is **refused**, where it is.
    """

    proposed: Component | None
    identification: Identification
    provenance: Provenance
    #: the component this would complete; None when it would be a new row
    existing: Component | None = None
    #: (label, what would be written) for each empty cell filled
    fills: list[tuple[str, str]] = field(default_factory=list)
    #: (label, what the method says, what the infusion measured)
    differences: list[tuple[str, str, str]] = field(default_factory=list)
    #: whether the internal-standard box would be ticked
    internal_standard: bool = True
    refusal: str = ""

    @property
    def name(self) -> str:
        if self.proposed is not None:
            return self.proposed.name
        return self.existing.name if self.existing is not None else ""

    @property
    def is_new(self) -> bool:
        return self.existing is None

    @property
    def offered(self) -> bool:
        """Is there anything to write? A refused row never is."""
        if self.refusal or self.proposed is None:
            return False
        return self.is_new or bool(self.fills) or self._ticks_is

    @property
    def _ticks_is(self) -> bool:
        return bool(self.internal_standard and self.existing is not None
                    and not self.existing.is_internal_standard)

    @property
    def into(self) -> str:
        """New component, or the one it completes — the dialog's column."""
        if self.is_new:
            return "new component"
        if not self.fills and not self._ticks_is:
            return f"{self.existing.name}: nothing left to fill"
        return f"completes {self.existing.name}"

    @property
    def fragment_note(self) -> str:
        """
        Said where the fragment chosen is the precursor itself.

        At a soft activation the base peak of a product-ion scan is often the
        precursor that survived it: on the bile-acid infusions, CA-d4 at
        12 eV and TDCA-d4 at 22 eV both have their intact ion as the tallest
        peak. That is a legitimate transition and a poor one — it is the
        precursor measured twice, with none of the selectivity a fragment
        buys — so the row says so and leaves the choice where it belongs.
        """
        if self.proposed is None or self.proposed.fragment is None:
            return ""
        exact = self.identification.exact
        if exact is None:
            return ""
        if abs(self.proposed.fragment - exact) > PRECURSOR_AS_FRAGMENT_DA:
            return ""
        return ("the base peak is the precursor that survived, not a "
                "fragment — pick another peak for a transition that selects")

    @property
    def note(self) -> str:
        """The row's one line: the refusal, or the masses and the quarrels."""
        if self.refusal:
            return self.refusal
        said = [self.identification.note, self.fragment_note]
        for label, theirs, mine in self.differences:
            said.append(f"{label} {theirs} written, {mine} from the infusion "
                        f"— kept as written")
        return "; ".join(part for part in said if part)

    # -- writing it ---------------------------------------------------------- #
    def apply(self, method) -> Component | None:
        """
        Write it into the method and return the component that was written.

        A new component is appended; an existing one has its **empty** cells
        filled and nothing else touched. Returns None where there was nothing
        to write.

        A plan describes the method *as it was when the plan was made*, so
        applying one invalidates the others: two infusions of the same
        compound — the same vial at two collision energies — are one
        component, and after the first is written the second is a completion
        with nothing left to complete. Plan again between applies, which is
        what the dialog does.
        """
        if not self.offered or self.proposed is None:
            return None
        if self.existing is None:
            method.components.append(self.proposed)
            return self.proposed
        for name, label in _FIELDS:
            if not any(entry[0] == label for entry in self.fills):
                continue
            setattr(self.existing, name, getattr(self.proposed, name))
        if self._ticks_is:
            self.existing.is_internal_standard = True
        return self.existing

    @property
    def audit_before(self) -> str:
        """
        The component as it stood, for the trail — read before `apply`.

        A new row has nothing before it. A row being completed has whatever
        was already typed into it, which is the half of the entry that says
        the fill did not overwrite anything.
        """
        if self.existing is None:
            return ""
        fragment = ("" if self.existing.fragment is None
                    else f" → {self.existing.fragment:.4f}")
        if not self.existing.precursor:
            return "no precursor"
        return f"{self.existing.precursor:.4f}{fragment}"

    @property
    def audit_after(self) -> str:
        """
        What was written into the row, as the dialog showed it.

        The transition and what it was derived from for a new component; the
        cells that were filled, named, for one that was completed. Where the
        written precursor came from is the *note*'s business — this column
        is what the method now says.
        """
        if self.proposed is None:
            return ""
        if self.is_new:
            said = f"{self.proposed.precursor:.4f}"
            if self.proposed.fragment is not None:
                said += f" → {self.proposed.fragment:.4f}"
            if self.identification.formula:
                said += (f" · {self.identification.formula} "
                         f"{self.identification.adduct}".rstrip())
            return said
        return ", ".join(f"{label} {value}" for label, value in self.fills
                         ) or ("IS" if self._ticks_is else "")

    @property
    def audit_note(self) -> str:
        """
        The provenance and the two masses, in what the trail has room for.

        `Provenance.short` rather than the whole sentence, because
        `audit.MAX_LENGTH` is 160 characters and the whole sentence is half
        as long again on a real file name — the trail would show it cut in
        the middle of the acquisition time. The component keeps the full
        text and the project keeps the component.
        """
        said = [self.provenance.short]
        error = self.identification.error_ppm
        if error is not None:
            said.append(f"channel written {self.identification.written:g}, "
                        f"{error:+.1f} ppm")
        if self.differences:
            said.append("kept as written: "
                        + ", ".join(label for label, _t, _m in self.differences))
        return "; ".join(part for part in said if part)


def plan_for(row_or_report, method, as_internal_standard: bool = True,
             fragment=BASE_PEAK, acquired: str = "", lot: str = "") -> Plan:
    """
    What one infusion would write into `method`, without writing it.

    The component is built first and then measured against the method: a row
    the method does not have is a new component, and one it does have is
    completed cell by cell. A typed value is never a candidate for filling —
    only its disagreement with the infusion is reported — which is the same
    rule `components.fill_formulas` follows for the same reason.
    """
    report = report_of(row_or_report)
    identification = identify(report, method)
    provenance = provenance_of(report, acquired, lot)
    proposed = component_from_infusion(
        report, as_internal_standard=as_internal_standard, fragment=fragment,
        acquired=acquired, method=method, lot=lot)
    name = str(getattr(report, "compound", "")
               or getattr(report, "sample", "") or "").strip()
    existing = component_named(method, name)
    plan = Plan(proposed=proposed, identification=identification,
                provenance=provenance, existing=existing,
                internal_standard=bool(as_internal_standard))
    if proposed is None:
        plan.refusal = (identification.refusal
                        or "this row names no compound")
        return plan
    if existing is None:
        return plan
    for attribute, label in _FIELDS:
        mine = getattr(proposed, attribute)
        theirs = getattr(existing, attribute, None)
        if _empty(mine):
            continue
        if _empty(theirs):
            plan.fills.append((label, _shown(mine)))
        elif not _same(theirs, mine):
            plan.differences.append((label, _shown(theirs), _shown(mine)))
    return plan


def plans_for(rows, method, as_internal_standard: bool = True,
              acquired=None) -> list[Plan]:
    """
    One plan per row, in the order the rows were given.

    `acquired` is a mapping of sample name to acquisition time, or None; the
    dialog fills it from the session so that the provenance carries the day
    the instrument measured rather than the day somebody pressed the button.

    Every plan is made against the method as it stands, so they are a
    description of one moment: see `Plan.apply` before applying more than one
    of them.
    """
    dates = dict(acquired or {})
    return [plan_for(row, method,
                     as_internal_standard=as_internal_standard,
                     acquired=dates.get(
                         str(getattr(report_of(row), "sample", "")), ""))
            for row in rows]
