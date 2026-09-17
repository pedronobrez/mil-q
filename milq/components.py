"""
Components of a processing method — the equivalent of MultiQuant's component
table.

A component says what to extract (precursor, fragment, tolerance), where the
peak is expected (retention time and half window), and how its result is
reported (raw area, ratio to an internal standard, or a concentration read off
a calibration curve).

It may also say what it is *made of*. `Component.formula` with an adduct is
the only thing that gives a component a true mass — the written precursor is
somebody's rounding, good to a few hundred ppm — and a true mass is what
`recalibrate.py` needs before an internal standard can be a lock mass.
Methods do not carry formulas, but they do carry names, and a lipid name in
shorthand says the composition outright. So `fill_formulas` reads
`chemistry.formulas_from_name` into the empty Formula cells and **checks
every one against the precursor already written down**, to that precursor's
own last decimal: a formula that disagrees is reported and dropped, because a
wrong formula is a wrong lock mass, which is worse than no lock mass.

On the real 141-component method: 125 filled and 10 of its 11 internal
standards, in milliseconds and without opening a file. Thirteen of the 16
refusals were the written precursor typed to fewer places than it deserved,
and `precursor_repairs` below is how those are corrected — deliberately, one
row at a time. The other three are a whole dalton or more out, and the batch
says the instrument acquired the mass as written, which puts the *name* in
question instead: a repair there would take the component off the channel its
data is on.
"""

from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, field, fields, replace

from .chemistry import (ADDUCTS_BY_NAME, FormulaError, NameSuggestion,
                        formulas_from_name, monoisotopic_mass, names_for_mass,
                        parse_formula)
from .processing import (ALGORITHM_VALLEY, ALGORITHMS, PEAK_CHOICES,
                         PEAK_LARGEST, SNR_MODES, SNR_PEAK_TO_PEAK)

#: how a component's result is reported
RESPONSE_AREA = "area"
RESPONSE_RATIO = "ratio"
RESPONSE_CONCENTRATION = "concentration"
RESPONSES = (RESPONSE_AREA, RESPONSE_RATIO, RESPONSE_CONCENTRATION)

DEFAULT_TOLERANCE = 0.02
DEFAULT_UNIT = "Da"


@dataclass
class AcceptanceLimits:
    """
    What a row has to satisfy to pass review.

    Every limit of zero is off, so a fresh method flags nothing until the
    criteria are actually stated.
    """

    #: largest allowed |measured RT - expected RT|, in minutes
    rt_tolerance: float = 0.0
    #: largest allowed |accuracy - 100|, in percent
    accuracy_tolerance: float = 0.0
    #: smallest acceptable signal-to-noise
    min_snr: float = 0.0

    @property
    def is_active(self) -> bool:
        return bool(self.rt_tolerance or self.accuracy_tolerance or self.min_snr)

    def copy(self) -> "AcceptanceLimits":
        return AcceptanceLimits(**asdict(self))


@dataclass
class IntegrationParams:
    """
    How one component's peaks are found and measured.

    The method carries a set of defaults and a component may override them, so
    a single awkward analyte can be tuned without disturbing the rest of the
    batch.
    """

    smoothing: float = 0.0
    baseline_window: float = 0.0
    min_relative_height: float = 0.05
    min_snr: float = 3.0
    #: stretch of baseline used to measure noise; None falls back to the
    #: automatic estimate over the whole trace
    noise_start: float | None = None
    noise_end: float | None = None
    snr_mode: str = SNR_PEAK_TO_PEAK
    #: which peak in the window is the component when there is more than one
    peak_choice: str = PEAK_LARGEST
    #: how the area is arrived at — see processing.ALGORITHMS. A method saved
    #: before this existed reads back as `valley`, which is what it ran.
    algorithm: str = ALGORITHM_VALLEY

    def __post_init__(self):
        if self.snr_mode not in SNR_MODES:
            self.snr_mode = SNR_PEAK_TO_PEAK
        if self.peak_choice not in PEAK_CHOICES:
            self.peak_choice = PEAK_LARGEST
        if self.algorithm not in ALGORITHMS:
            self.algorithm = ALGORITHM_VALLEY

    @property
    def noise_region(self) -> tuple[float, float] | None:
        if self.noise_start is None or self.noise_end is None:
            return None
        return self.noise_start, self.noise_end

    def copy(self) -> "IntegrationParams":
        return IntegrationParams(**asdict(self))

    def cache_key(self) -> tuple:
        """Only the parts that change the conditioned trace."""
        return (self.smoothing, self.baseline_window)

# Header aliases, English and Portuguese, keyed by dataclass field name. Lists
# written by earlier versions used Portuguese headers, so both keep working.
_ALIASES = {
    "name": {"name", "compound", "component", "analyte", "nome", "composto", "analito"},
    "group": {"group", "grupo"},
    "precursor": {"precursor", "q1", "precursor_mz", "parent", "precursormz"},
    "fragment": {"fragment", "q3", "product", "fragment_mz", "productmz",
                 "fragmento", "produto"},
    "rt": {"rt", "retention_time", "rt_min", "tr", "tempo"},
    "rt_halfwidth": {"window", "rt_window", "rt_halfwidth", "half_window",
                     "janela", "meia_janela", "tolerancia_rt"},
    "tolerance": {"tolerance", "tol", "mz_tolerance", "tolerancia"},
    "unit": {"unit", "tol_unit", "unidade"},
    "formula": {"formula", "chemical_formula", "molecular_formula",
                "elemental_formula", "composition", "formula_molecular",
                "formula_quimica"},
    "adduct": {"adduct", "aduto", "ion"},
    "is_internal_standard": {"is", "is_internal_standard", "internal_standard?",
                             "istd", "is_istd", "e_padrao_interno"},
    "internal_standard": {"internal_standard", "is_name", "istd_name",
                          "padrao_interno"},
    "response": {"response", "response_type", "resposta"},
    "concentration_unit": {"concentration_unit", "conc_unit", "units",
                           "unidade_concentracao"},
    "qualifier_of": {"qualifier_of", "qualifier", "qualificador_de",
                     "quantifier", "quantifier_name"},
    "ion_ratio": {"ion_ratio", "expected_ion_ratio", "razao_ionica"},
    "ion_ratio_tolerance": {"ion_ratio_tolerance", "ion_ratio_tol",
                            "tolerancia_razao_ionica"},
    "regression": {"regression", "curve", "fit", "regressao"},
    "weighting": {"weighting", "weight", "ponderacao", "peso"},
    "lm_id": {"lm_id", "lipidmaps", "lipidmaps_id", "lmid"},
    "min_response": {"min_response", "response_floor", "min_area", "floor",
                     "piso_resposta", "resposta_minima", "area_minima"},
    "provenance": {"provenance", "source", "origin", "procedencia",
                   "proveniencia", "origem"},
}

_TRUE = {"1", "true", "yes", "y", "sim", "is", "istd", "x"}


@dataclass
class Component:
    """One target of the processing method."""

    name: str
    precursor: float = 0.0
    fragment: float | None = None
    rt: float | None = None
    rt_halfwidth: float = 0.5
    tolerance: float = DEFAULT_TOLERANCE
    unit: str = DEFAULT_UNIT
    group: str = ""
    formula: str = ""
    adduct: str = ""
    is_internal_standard: bool = False
    internal_standard: str = ""
    response: str = RESPONSE_AREA
    concentration_unit: str = ""
    #: name of the quantifier component this one confirms, when it is a
    #: qualifier transition
    qualifier_of: str = ""
    #: expected qualifier/quantifier area ratio, in percent
    ion_ratio: float | None = None
    #: allowed relative deviation from `ion_ratio`, in percent; 0 uses the
    #: method default
    ion_ratio_tolerance: float = 0.0
    #: calibration
    regression: str = "linear"
    weighting: str = "1"
    #: LIPID MAPS identifier, when the component has been annotated
    lm_id: str = ""
    #: where this row came from, in words, when it was not typed by hand:
    #: `standards.component_from_infusion` writes the infusion it was read
    #: off — the file, the sample, the channel, the energy, the day, and the
    #: record of one's own that the spectrum matched. Free text and nothing
    #: else: it is read by a person in a tooltip and in the audit trail, and
    #: nothing in the program branches on it. A row somebody typed carries
    #: none, which is the truthful answer for it.
    provenance: str = ""
    #: for an internal standard: the smallest area it has to give in an
    #: injection before a ratio to it means anything. Declared by whoever
    #: knows the method, because a batch cannot derive it — measured, its
    #: precision did not track its response — and because signal-to-noise
    #: cannot stand in for it on a scheduled acquisition. None means no
    #: floor: the quality charts fall back to their S/N rule.
    min_response: float | None = None
    #: integration overrides for this component; None uses the method defaults
    integration: IntegrationParams | None = None
    #: acceptance overrides for this component; None uses the method defaults
    acceptance: AcceptanceLimits | None = None

    @property
    def is_qualifier(self) -> bool:
        return bool(self.qualifier_of)

    @property
    def calibration_response(self) -> str:
        """
        What a calibration curve is built from: the ratio to the internal
        standard when there is one, and the raw area otherwise. This is the
        measured quantity, distinct from `response`, which says what the
        results table reports.
        """
        return "ratio" if self.internal_standard else "area"

    def __post_init__(self):
        if self.response not in RESPONSES:
            self.response = RESPONSE_AREA
        if isinstance(self.integration, dict):
            known = {k: v for k, v in self.integration.items()
                     if k in IntegrationParams.__dataclass_fields__}
            self.integration = IntegrationParams(**known)
        if isinstance(self.acceptance, dict):
            known = {k: v for k, v in self.acceptance.items()
                     if k in AcceptanceLimits.__dataclass_fields__}
            self.acceptance = AcceptanceLimits(**known)
        if not self.precursor and self.formula:
            computed = self.precursor_from_formula()
            if computed is not None:
                self.precursor = computed

    # -- masses ---------------------------------------------------------------- #
    def precursor_from_formula(self) -> float | None:
        """
        Precursor m/z from the formula and adduct, or None if either is missing
        or unreadable. Lets a labelled internal standard be entered as
        `C18H30D4O4` instead of a hand-computed mass.
        """
        if not self.formula:
            return None
        try:
            counts = parse_formula(self.formula)
        except FormulaError:
            return None
        adduct = ADDUCTS_BY_NAME.get(self.adduct)
        if adduct is None:
            return None
        return adduct.mz(monoisotopic_mass(counts))

    @property
    def target_mz(self) -> float:
        """The mass actually extracted: the fragment, or the precursor if none."""
        return self.fragment if self.fragment is not None else self.precursor

    def mass_window(self) -> tuple[float, float]:
        """XIC m/z range, resolving the tolerance in Da or ppm."""
        mz = self.target_mz
        half = mz * self.tolerance * 1e-6 if self.unit.lower() == "ppm" else self.tolerance
        return mz - half, mz + half

    def rt_window(self) -> tuple[float, float] | None:
        """Expected time range, or None when no retention time was given."""
        if self.rt is None:
            return None
        return self.rt - self.rt_halfwidth, self.rt + self.rt_halfwidth

    # -- presentation ----------------------------------------------------------- #
    @property
    def label(self) -> str:
        base = self.name
        if self.is_internal_standard:
            base += " (IS)"
        if self.fragment is not None:
            return f"{base}  {self.precursor:.4f} → {self.fragment:.4f}"
        return f"{base}  {self.precursor:.4f}"

    @property
    def is_valid(self) -> bool:
        return bool(self.name) and self.precursor > 0


# --------------------------------------------------------------------------- #
# formulas from names
# --------------------------------------------------------------------------- #
#: how far a formula's mass may sit from the precursor the method already
#: carries, as a multiple of `lipidmaps.mass_precision` — which is half a
#: unit in the last written decimal, what a *rounded* number is good to. A
#: written mass is as often truncated: this method writes `286.2` for a
#: precursor of 286.2741 and `288.2` for one of 288.2897, so half a unit
#: would reject the compound over the way its own precursor was typed. A
#: whole unit still separates every reading that is actually in question,
#: since those differ by a double bond (2 Da), a methylene (14 Da) or a
#: hydroxyl (16 Da) — never by a tenth.
WRITTEN_UNITS = 2.0


def written_tolerance(precursor: float) -> float:
    """What a written precursor is good to, in Da — see `WRITTEN_UNITS`."""
    from .lipidmaps import mass_precision

    return WRITTEN_UNITS * mass_precision(precursor)


@dataclass(frozen=True)
class FormulaProposal:
    """A formula offered for a component, and how it fared against its mass."""

    component: Component
    formula: str
    #: where it came from: the component's own name, or a database record
    source: str = "the name"
    #: the m/z the formula and the component's adduct give, or None when
    #: there is no adduct to put it through
    theoretical: float | None = None
    #: what the method has typed in the precursor column
    written: float = 0.0
    #: how far the two may sit apart and still be the same compound
    allowed: float = 0.0

    @property
    def checkable(self) -> bool:
        return self.theoretical is not None and self.written > 0

    @property
    def difference(self) -> float | None:
        if not self.checkable:
            return None
        return self.theoretical - self.written

    @property
    def error_ppm(self) -> float | None:
        difference = self.difference
        if difference is None or not self.theoretical:
            return None
        return difference / self.theoretical * 1e6

    @property
    def agrees(self) -> bool:
        difference = self.difference
        return difference is not None and abs(difference) <= self.allowed

    @property
    def reason(self) -> str:
        """Why the formula was not taken, for the row that says so."""
        if self.theoretical is None:
            return "no adduct: the formula's mass cannot be put against the "\
                   "precursor, so nothing confirms it"
        if not self.written:
            return "no precursor written: nothing to confirm the formula"
        return (f"{self.formula} is {self.theoretical:.4f} through "
                f"{self.component.adduct}, and the method says "
                f"{self.written:.4f} — {abs(self.difference) * 1000:,.1f} mDa "
                f"apart, past the {self.allowed * 1000:,.1f} mDa the written "
                f"value is good to")


def propose_formula(component: Component, database=None) -> FormulaProposal | None:
    """
    A formula for one component, from its name, checked against its precursor.

    Every reading of the name (`chemistry.formulas_from_name`) is tried and
    the first that agrees with the written precursor is the answer. When none
    agrees the *nearest* is returned anyway, so the caller can say what it
    derived and how far off it was rather than only that nothing happened;
    `FormulaProposal.agrees` is what decides whether it may be used.

    `database` is a `lipidmaps.LipidDatabase` consulted only where the name
    is not shorthand at all — it goes through exactly the same check.
    """
    if not component.name:
        return None
    candidates = [(formula, "the name") for formula in
                  formulas_from_name(component.name)]
    if not candidates and database is not None:
        # a callable is resolved here and not before, so a table that is all
        # shorthand never pays for loading fifty thousand records
        found = (database() if callable(database) else database)
        found = found.find_by_name(component.name, limit=1) if found else []
        if found and found[0].formula:
            candidates = [(found[0].formula, f"LIPID MAPS {found[0].lm_id}")]
    if not candidates:
        return None

    allowed = written_tolerance(component.precursor)
    proposals = []
    for formula, source in candidates:
        theoretical = Component(name=component.name, precursor=component.precursor,
                                formula=formula,
                                adduct=component.adduct).precursor_from_formula()
        proposal = FormulaProposal(component=component, formula=formula,
                                   source=source, theoretical=theoretical,
                                   written=component.precursor, allowed=allowed)
        if proposal.agrees:
            return proposal
        proposals.append(proposal)
    return min(proposals, key=lambda p: abs(p.difference)
               if p.difference is not None else float("inf"))


@dataclass
class FormulaFill:
    """What filling a component table's formulas did, and did not do."""

    filled: list[FormulaProposal] = field(default_factory=list)
    #: derived, and thrown away because the written precursor said otherwise
    refused: list[FormulaProposal] = field(default_factory=list)
    underived: list[Component] = field(default_factory=list)
    kept: list[Component] = field(default_factory=list)

    @property
    def missing(self) -> int:
        """How many are still without one."""
        return len(self.refused) + len(self.underived)

    def summary(self) -> str:
        said = [f"{len(self.filled)} formula(s) filled in"]
        if self.refused:
            said.append(f"{len(self.refused)} refused by the written precursor")
        if self.underived:
            said.append(f"{len(self.underived)} not derivable from the name")
        if self.kept:
            said.append(f"{len(self.kept)} already had one, left alone")
        return ", ".join(said) + "."


def fill_formulas(components: list[Component], database=None) -> FormulaFill:
    """
    Give every component that has no formula the one its name implies.

    Only empty cells are written: a formula somebody typed is the method's,
    and a derivation from a name is a guess about it. Nothing else on the
    component moves either — in particular not the precursor, which is both
    the reference this was checked against and what the extraction window is
    built from.
    """
    fill = FormulaFill()
    for component in components:
        if component.formula:
            fill.kept.append(component)
            continue
        proposal = propose_formula(component, database)
        if proposal is None:
            fill.underived.append(component)
        elif proposal.agrees:
            component.formula = proposal.formula
            fill.filled.append(proposal)
        else:
            fill.refused.append(proposal)
    return fill


def formula_disagreement(component: Component) -> FormulaProposal | None:
    """
    The component's own formula against its own precursor, when they differ.

    None when they agree, when there is no formula, or when there is nothing
    to check it against.
    """
    if not component.formula:
        return None
    proposal = FormulaProposal(
        component=component, formula=component.formula, source="the method",
        theoretical=component.precursor_from_formula(),
        written=component.precursor,
        allowed=written_tolerance(component.precursor))
    if not proposal.checkable or proposal.agrees:
        return None
    return proposal


# --------------------------------------------------------------------------- #
# repairing the precursor from the formula
# --------------------------------------------------------------------------- #
#: how far apart the two masses have to be before the disagreement stops
#: being about how a number was written down. Under this a written precursor
#: is a rounding, a truncation or a typed decimal and the formula is simply
#: the same compound to more places; at or past it the two are different
#: compounds — a hydrogen, a double bond, a dropped digit — and which of them
#: the instrument actually acquired is not something arithmetic can settle.
#: On the real method every refusal is either under 0.27 Da or a whole
#: number out — two rows at exactly 1.0000 and 2.0000 Da, one at 100 Da from
#: a dropped digit. Nothing lands in between, which is why half a dalton can
#: divide the two without adjudicating anything.
WHOLE_DALTON = 0.5


@dataclass(frozen=True)
class PrecursorRepair:
    """
    A written precursor its own formula contradicts, and the repair offered.

    The repair is deliberately a *proposal*: `fill_formulas` refuses to touch
    a precursor precisely because it is what the formula was checked against,
    and nothing here changes that. What this adds is the other way out of the
    stand-off — when the formula is right, the written mass is the thing to
    correct — and it is only ever taken row by row, by hand, on record.
    """

    proposal: FormulaProposal

    @property
    def component(self) -> Component:
        return self.proposal.component

    @property
    def formula(self) -> str:
        return self.proposal.formula

    @property
    def source(self) -> str:
        return self.proposal.source

    @property
    def written(self) -> float:
        return self.proposal.written

    @property
    def theoretical(self) -> float:
        return self.proposal.theoretical

    @property
    def difference(self) -> float:
        return self.proposal.difference

    @property
    def error_ppm(self) -> float | None:
        return self.proposal.error_ppm

    @property
    def whole_dalton(self) -> bool:
        """Is this a different compound rather than a differently typed one?"""
        return abs(self.difference) >= WHOLE_DALTON

    @property
    def offered(self) -> bool:
        """
        Whether the row is ticked when the dialog opens.

        A sub-dalton difference is the same compound written down to fewer
        places and the repair is arithmetic. A whole dalton is not: it is a
        hydrogen, a double bond or a dropped digit, and only the person who
        wrote the method knows whether the name or the mass is the typo. Those
        rows are offered unticked: they can be applied, but somebody has to
        say so.
        """
        return not self.whole_dalton

    @property
    def writes_formula(self) -> bool:
        """Does applying this fill an empty Formula cell as well?"""
        return not self.component.formula

    @property
    def repaired(self) -> Component:
        """The component as it would be, without touching the one there is."""
        return replace(self.component, formula=self.formula,
                       precursor=self.theoretical)

    @property
    def window_before(self) -> tuple[float, float]:
        return self.component.mass_window()

    @property
    def window_after(self) -> tuple[float, float]:
        return self.repaired.mass_window()

    @property
    def moves_window(self) -> bool:
        """
        Whether the extraction window itself moves.

        It does only where the row has no fragment. A row that names one
        extracts on the fragment (`Component.target_mz`), so the window stays
        exactly where it was and the precursor does its work earlier, in
        `matching.match_channel`, which picks the acquisition channel whose
        own precursor is nearest within `PRECURSOR_MATCH_DA`. Moving a
        precursor by more than that changes which channel is read — or leaves
        the component with none — and that is a larger change than the window,
        not a smaller one.
        """
        return self.window_before != self.window_after

    @property
    def note(self) -> str:
        """
        Why this row is offered the way it is, in one line.

        Short on purpose, and short about the ordinary case in particular: a
        note that says the same sentence on sixteen rows is furniture. What
        the row carries is what is unusual about *it* — the size of the
        disagreement, whether the window moves with the repair, and whether
        the Formula cell is filled in as well.
        """
        if self.whole_dalton:
            said = (f"{abs(self.difference):.4f} Da apart: a different "
                    f"compound or a typed digit — say which")
        else:
            said = "the same compound, fewer places"
        if self.moves_window:
            said += "; the window moves with it"
        elif self.component.fragment is not None:
            said += "; the window is the fragment's and stays"
        if self.writes_formula:
            said += "; Formula filled in too"
        return said

    @property
    def audit_before(self) -> str:
        """The precursor as the method had it, written as the method wrote it."""
        return f"{self.written:.10g}"

    @property
    def audit_after(self) -> str:
        """
        The precursor as it now is, to four decimals.

        Four because that is what the dialog showed and what a mass is
        legible to; the component itself keeps every digit the formula gives.
        A trail records what was on screen, not a serialisation.
        """
        return f"{self.theoretical:.4f}"

    @property
    def audit_note(self) -> str:
        """The note the audit entry carries."""
        said = f"from formula {self.formula}, {self.source}"
        if self.error_ppm is not None:
            said += f", {self.error_ppm:+,.1f} ppm"
        if self.whole_dalton:
            said += "; a whole-dalton repair, accepted by hand"
        return said

    def apply(self) -> Component:
        """
        Write the formula and the precursor into the component.

        The only place in this module that moves a precursor. Both fields are
        written together on purpose: a precursor taken from a formula and the
        formula it was taken from are one statement, and a row carrying the
        first without the second cannot be checked again afterwards.
        """
        self.component.formula = self.formula
        self.component.precursor = self.theoretical
        return self.component

    # -- the other repair: the mass is right and the name is wrong ------------ #
    def suggestions(self, database=None) -> list[NameSuggestion]:
        """
        Names whose formula matches the *written* mass, best first.

        Only ever for a whole-dalton row. Under half a dalton the two masses
        are one compound written twice and there is nothing to rename; at a
        whole dalton the instrument acquired what was written — that mass
        is the channel — and the question turns round: which compound weighs
        what the method says, given that this one does not?

        The list is `chemistry.names_for_mass`: the written name's own class
        first, with the chains moved, then what LIPID MAPS holds at the same
        mass. Both are proposals about a name and neither touches a number.
        """
        if not self.whole_dalton:
            return []
        found = (database() if callable(database) else database) if database else None
        return names_for_mass(self.written, self.component.adduct,
                              like=self.component.name, database=found)

    def rename_note(self, suggestion: NameSuggestion) -> str:
        """The note the audit entry carries for a rename."""
        said = (f"formula {suggestion.formula} matches the written "
                f"{self.written:.4f} to {suggestion.error_ppm:+,.1f} ppm")
        if not suggestion.in_class:
            said += f", from {suggestion.source}"
        said += (f"; the name said {self.formula} at {self.theoretical:.4f}, "
                 f"{abs(self.difference):.4f} Da away, and the mass is what "
                 f"the instrument acquired")
        return said

    def apply_rename(self, suggestion: NameSuggestion) -> Component:
        """
        Write the offered name and its formula; leave the precursor alone.

        The mirror of `apply`, and the reason it exists: there the formula was
        believed and the mass corrected, here the mass is believed and the
        name corrected. Nothing in the extraction moves — same precursor, same
        fragment, same window, same channel — so no result goes stale. What
        changes is that the row now carries a formula that agrees with its own
        mass, which is what a lock mass is made of.
        """
        component = self.component
        component.name = suggestion.name
        component.formula = suggestion.formula
        if not suggestion.in_class and suggestion.source.startswith("LIPID MAPS "):
            component.lm_id = suggestion.source.split()[-1]
        return component


def precursor_repairs(components: list[Component],
                      database=None) -> list[PrecursorRepair]:
    """
    Every component whose formula and written precursor contradict each other.

    Both ways in are covered: a formula the method already carries
    (`formula_disagreement`) and one the name implies that `fill_formulas`
    refused to write (`propose_formula`). A component that agrees, that has no
    readable name and no formula, or that has nothing to check against, is not
    a repair and does not appear.
    """
    repairs: list[PrecursorRepair] = []
    for component in components:
        if component.formula:
            proposal = formula_disagreement(component)
        else:
            proposal = propose_formula(component, database)
            if proposal is not None and proposal.agrees:
                proposal = None
        if proposal is None or not proposal.checkable:
            continue
        repairs.append(PrecursorRepair(proposal))
    return repairs


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def _normalise_header(row: dict) -> dict:
    """Map CSV headers onto the dataclass field names."""
    out = {}
    for raw_key, value in row.items():
        if raw_key is None:
            continue
        key = raw_key.strip().lower().replace(" ", "_").replace("/", "_")
        for field_name, aliases in _ALIASES.items():
            if key in aliases:
                out[field_name] = value
                break
    return out


def _to_float(value, default=None):
    if value is None:
        return default
    text = str(value).strip().replace(",", ".")
    if not text:
        return default
    return float(text)


def _to_bool(value) -> bool:
    return str(value or "").strip().lower() in _TRUE


def load_components(path: str | os.PathLike) -> list[Component]:
    """
    Read a component list from CSV.

    Required: a name column, plus either a precursor column or a formula and
    adduct the precursor can be computed from. Everything else is optional. The
    delimiter is detected automatically among comma, semicolon and tab.
    """
    with open(path, newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [_normalise_header(row) for row in csv.DictReader(handle, dialect=dialect)]

    if not rows:
        return []
    if "name" not in rows[0]:
        raise ValueError("CSV has no name column (use 'name' or 'component').")
    if "precursor" not in rows[0] and "formula" not in rows[0]:
        raise ValueError("CSV has no precursor column and no formula column.")

    components: list[Component] = []
    for number, row in enumerate(rows, start=2):
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        unit = str(row.get("unit") or DEFAULT_UNIT).strip() or DEFAULT_UNIT
        response = str(row.get("response") or RESPONSE_AREA).strip().lower()
        try:
            component = Component(
                name=name,
                precursor=_to_float(row.get("precursor"), 0.0) or 0.0,
                fragment=_to_float(row.get("fragment")),
                rt=_to_float(row.get("rt")),
                rt_halfwidth=_to_float(row.get("rt_halfwidth"), 0.5) or 0.5,
                tolerance=_to_float(row.get("tolerance"), DEFAULT_TOLERANCE),
                unit="ppm" if unit.lower() == "ppm" else "Da",
                group=str(row.get("group") or "").strip(),
                formula=str(row.get("formula") or "").strip(),
                adduct=str(row.get("adduct") or "").strip(),
                is_internal_standard=_to_bool(row.get("is_internal_standard")),
                internal_standard=str(row.get("internal_standard") or "").strip(),
                response=response,
                concentration_unit=str(row.get("concentration_unit") or "").strip(),
                qualifier_of=str(row.get("qualifier_of") or "").strip(),
                ion_ratio=_to_float(row.get("ion_ratio")),
                ion_ratio_tolerance=_to_float(row.get("ion_ratio_tolerance"), 0.0) or 0.0,
                regression=str(row.get("regression") or "linear").strip() or "linear",
                weighting=str(row.get("weighting") or "1").strip() or "1",
                lm_id=str(row.get("lm_id") or "").strip(),
                min_response=_to_float(row.get("min_response")),
                provenance=str(row.get("provenance") or "").strip(),
            )
        except ValueError as exc:
            raise ValueError(f"CSV line {number}: {exc}") from exc
        if component.is_valid:
            components.append(component)
    return components


def _fmt(value: float | None) -> str:
    """
    Format without losing exact-mass precision: 12 significant digits. With
    fewer, an m/z such as 313.2384 would be written as 313.238 — an error of
    more than 1 ppm, enough to shift a narrow XIC window.
    """
    return "" if value is None else f"{value:.12g}"


CSV_HEADER = ["name", "group", "precursor", "fragment", "rt", "window",
              "tolerance", "unit", "formula", "adduct", "is",
              "internal_standard", "response", "concentration_unit",
              "qualifier_of", "ion_ratio", "ion_ratio_tolerance",
              "regression", "weighting", "lm_id", "min_response",
              "provenance"]


def save_components(path: str | os.PathLike, components: list[Component]) -> None:
    """Write the list to CSV with headers that `load_components` accepts."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for c in components:
            writer.writerow([
                c.name, c.group, _fmt(c.precursor), _fmt(c.fragment), _fmt(c.rt),
                _fmt(c.rt_halfwidth), _fmt(c.tolerance), c.unit, c.formula,
                c.adduct, "yes" if c.is_internal_standard else "",
                c.internal_standard, c.response, c.concentration_unit,
                c.qualifier_of, _fmt(c.ion_ratio), _fmt(c.ion_ratio_tolerance),
                c.regression, c.weighting, c.lm_id, _fmt(c.min_response),
                c.provenance,
            ])


COMPONENT_FIELDS = [f.name for f in fields(Component)]
