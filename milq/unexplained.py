"""
What the peaks nothing explained might be.

An explanation accounts for part of a spectrum and says nothing about the
rest, and the rest is where a co-infused impurity, an adduct nobody
predicted, or the wrong compound shows itself. Listing those peaks as bare
masses — which is what the report did — is honest and it is not useful: the
reader is handed `217.1880` and left to type it into something else.

So each strong peak the explanation missed is offered three hypotheses, and
the best one is written beside it.

**A known contaminant or a solvent cluster.** The background of an
electrospray source is the same everywhere and it is tabulated; a peak that
sits on one of those masses is almost never the compound. See `CONTAMINANTS`
for the table and where each mass comes from.

**A satellite of an ion the explanation did match.** A carbon-13 peak, the
sodiated or potassiated form of a protonated fragment, a water or ammonia
loss from it. These are the strongest of the three hypotheses because they
are anchored to a mass this spectrum has already accounted for — the
arithmetic is against a peak that is there, not against a table.

**A sub-formula of the precursor ion.** A general formula search on a mass
of 300 returns dozens of compositions and the answer is a list nobody reads.
But a product-ion spectrum is not a general search: *a fragment cannot carry
atoms the precursor has not got*. Constraining the element ranges to the
precursor ion's own composition — the molecule's atoms plus whatever the
adduct brought, with `EXTRA_H` hydrogens' slack either way for the
rearrangements that move them — turns the search from "what could this mass
be" into "what could this precursor have left behind at this mass", which is
a question with few answers. A peak with no answer at all is a finding in
its own right and is reported as one: it says the peak is not a piece of
this compound, whatever else it is.

The three are tried in that order and the closest in ppm among the named
ones wins; the sub-formula is reached only when nothing is named, because a
name is a specific hypothesis that can be wrong and a composition search
always returns something.

Nothing here identifies anything. A mass within 20 ppm of a phthalate is a
mass within 20 ppm of a phthalate, and every row carries its error so the
reader can see how much that is worth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .chemistry import (ADDUCTS_BY_NAME, ELECTRON_MASS, NEUTRON_SPACING,
                        PROTON_MASS, Adduct, FormulaError, adduct_from_name,
                        find_formulas, has_isotope_satellites,
                        ion_composition, isotope_pattern,
                        match_isotope_pattern, monoisotopic_mass,
                        parse_formula, passes_golden_rules, polarity_sign)
from .labels import LABEL_MIN_RELATIVE

#: how close a candidate mass has to sit to a measured one, in ppm. The same
#: window the structural explanation matches in, on purpose: a peak this
#: refuses at 25 ppm would have been matched by the explanation at 25 ppm,
#: and two tolerances for the same spectrum cannot both be the tolerance.
TOLERANCE_PPM = 20.0

#: hydrogens the fragment may carry beyond what the precursor ion holds.
#: Hydrogen rearrangement during fragmentation moves one or two — a McLafferty
#: transfer is one — so a sub-formula is allowed that much slack upwards. It
#: needs none downwards: every count already starts at zero.
EXTRA_H = 2

#: how far down a sub-formula search will look for compositions before it
#: gives up ranking them. Reached only for a peak near the precursor's own
#: mass, where almost every sub-formula of the precursor is in range.
MAX_FORMULAS = 500

#: how wide an isotope satellite is looked for, in Da. `chemistry` uses the
#: same figure for the survey's peaks and for the same reason: a TOF centroid
#: does not land on the theoretical mass to better than this.
ISOTOPE_TOLERANCE_DA = 0.02

#: below this mass the Seven Golden Rules are not applied to a sub-formula.
#:
#: The rules (Kind & Fiehn, 2007) bound the element ratios of a *molecule*,
#: and the one that hurts is H/C at most 3.1. A fragment is not a molecule
#: and a small one is nothing like a molecule: protonated taurine,
#: `[C2H8NO3S]+`, has H/C = 4.0 and is the diagnostic fragment of every
#: taurine-conjugated bile acid. It is the strongest unexplained peak of the
#: real TDCA-d4 infusion — m/z 126.0211, −6.7 ppm — and the golden rules
#: refused it, so the table said "no formula within the precursor's
#: composition" about a piece the precursor is named after. Above 150 the
#: rules cost nothing: no sub-formula of a bile acid reaches H/C 3.1 there.
#: They are kept at all because a mass with the slack of `EXTRA_H` hydrogens
#: can otherwise assemble a composition of hydrogen and little else.
GOLDEN_RULE_MASS = 150.0

# what kind of answer a row carries
CONTAMINANT = "contaminant"
SATELLITE = "satellite"
FORMULA = "formula"
NOTHING = "none"

#: what a peak with no hypothesis at all is called. It is a statement about
#: the precursor, not about the peak: whatever this mass is, it is not a
#: piece of this compound.
NO_FORMULA = "no formula within the precursor's composition"

# --------------------------------------------------------------------------- #
# the contaminant table
# --------------------------------------------------------------------------- #
#: the neutral formulas of the solvents whose clusters are offered, with the
#: name each cluster is written under. Held as formulas rather than as masses
#: so the arithmetic can be checked: `[2ACN+Na]+` is computed from
#: acetonitrile's own composition here, not copied from a table.
SOLVENTS: dict[str, str] = {
    "acetonitrile": "C2H3N",
    "DMSO": "C2H6OS",
    "methanol": "CH4O",
    "formic acid": "CH2O2",
}

#: how many solvent molecules a cluster may hold. Past three the cluster is
#: weaker than the noise it would be found in.
SOLVENT_CLUSTER = 3

#: fixed background masses, as m/z of the ion, by polarity.
#:
#: Sources, one per row:
#:
#: - **149.0233**, `[C8H5O3]+`, protonated phthalic anhydride: the fragment
#:   every phthalate ester gives, and the most reported contaminant in
#:   positive electrospray. Keller, Sürig, König & Unger, *Interferences and
#:   contaminants encountered in modern mass spectrometry*, Analytica Chimica
#:   Acta 627 (2008) 71–81, table 1.
#: - **391.2843**, `[C24H39O4]+`, protonated di(2-ethylhexyl) phthalate — the
#:   intact plasticiser whose fragment the row above is. Same table; the mass
#:   here is computed from the formula rather than copied.
#: - **371.1012** and **445.1200**, protonated cyclic polydimethylsiloxane,
#:   `[(C2H6OSi)n+H]+` at n = 5 and n = 6. The PDMS series of the same table,
#:   spaced by C2H6OSi = 74.0188; it comes off septa, tubing and column
#:   frits, and it is the background a clean blank still has.
#: - **112.9856**, `[C2F3O2]-`, trifluoroacetate: the negative-mode
#:   counterpart, from any laboratory that has ever used TFA in a mobile
#:   phase. Same source.
#:
#: Every mass is the ion's, electron included. The solvent clusters are not
#: here — they are computed from `SOLVENTS`.
CONTAMINANTS: dict[int, list[tuple[float, str]]] = {
    1: [
        (149.0233, "phthalate fragment [C8H5O3]+"),
        (391.2843, "di(2-ethylhexyl) phthalate [M+H]+"),
        (371.1012, "polysiloxane [(C2H6OSi)5+H]+"),
        (445.1200, "polysiloxane [(C2H6OSi)6+H]+"),
    ],
    -1: [
        (112.9856, "trifluoroacetate [C2F3O2]-"),
    ],
}

#: the mass a sodium costs when it replaces the proton of a protonated ion.
#: Not 22.989: an ion already carries its charge, so its sodiated form is an
#: exchange and sits 21.982 above it. The 22.989 figure belongs to a neutral,
#: which is where `PRECURSOR_FORMS` uses it.
NA_FOR_H = ADDUCTS_BY_NAME["[M+Na]+"].delta - PROTON_MASS
K_FOR_H = ADDUCTS_BY_NAME["[M+K]+"].delta - PROTON_MASS
#: water and ammonia, as neutral losses from a measured ion
WATER = monoisotopic_mass({"H": 2, "O": 1})
AMMONIA = monoisotopic_mass({"N": 1, "H": 3})

#: the forms of the precursor itself that a spectrum may still hold: the
#: other adducts of the same neutral, and the dimers that survive the
#: quadrupole's isolation window when the source makes them. Named by adduct,
#: with how many molecules of the neutral each carries.
PRECURSOR_FORMS: dict[int, list[tuple[str, int]]] = {
    1: [("[M+H]+", 1), ("[M+NH4]+", 1), ("[M+Na]+", 1), ("[M+K]+", 1),
        ("[M+H]+", 2), ("[M+NH4]+", 2), ("[M+Na]+", 2)],
    -1: [("[M-H]-", 1), ("[M+Cl]-", 1), ("[M+HCOO]-", 1), ("[M-H]-", 2)],
}


@dataclass(frozen=True)
class Candidate:
    """One named mass a peak might be, before any peak is looked at."""

    mz: float
    label: str
    kind: str
    #: where the mass came from, for the row's tooltip and the test that
    #: checks a mass was not invented
    basis: str = ""


@dataclass
class UnexplainedPeak:
    """One strong peak the explanation missed, and the best guess at it."""

    mz: float
    intensity: float
    #: the peak's height as a share of the tallest peak of the spectrum
    share: float
    kind: str = NOTHING
    label: str = NO_FORMULA
    #: how far the hypothesis sits from the measured mass. None where there
    #: is no hypothesis, which is not the same as an error of zero.
    error_ppm: float | None = None
    formula: str = ""
    rdbe: float | None = None
    #: the agreement between the composition's theoretical isotope pattern
    #: and the measured one, 0 to 1, or None where this spectrum carries no
    #: satellites to compare — the ordinary case in a product-ion scan
    isotope_score: float | None = None
    basis: str = ""
    #: other sub-formulas of the precursor that reach the same mass within
    #: the tolerance. A row with rivals is a composition, not an assignment.
    rivals: int = 0
    #: the composition is an odd-electron ion. Offered because an EAD
    #: spectrum is full of them, ranked below every even-electron rival, and
    #: marked because in a CID spectrum it is usually the wrong answer.
    radical: bool = False

    @property
    def accounted(self) -> bool:
        """Did anything at all explain this peak?"""
        return self.kind != NOTHING

    @property
    def named(self) -> bool:
        """Was it a named mass — a contaminant or a satellite — rather than
        a composition the search assembled?"""
        return self.kind in (CONTAMINANT, SATELLITE)

    @property
    def ppm_text(self) -> str:
        return "—" if self.error_ppm is None else f"{self.error_ppm:+.1f}"


# --------------------------------------------------------------------------- #
# the candidates
# --------------------------------------------------------------------------- #
def contaminant_masses(polarity: int) -> list[Candidate]:
    """
    The fixed background masses and the solvent clusters of one polarity.

    The clusters are built here rather than tabulated: `[nS+H]+`, `[nS+Na]+`
    and `[nS+NH4]+` for each solvent of `SOLVENTS` up to `SOLVENT_CLUSTER`
    molecules, in positive mode, and `[nS-H]-` in negative.
    """
    out = [Candidate(mz, label, CONTAMINANT, "tabulated background ion")
           for mz, label in CONTAMINANTS.get(polarity, [])]
    forms = (["[M+H]+", "[M+Na]+", "[M+NH4]+"] if polarity > 0 else ["[M-H]-"])
    for name, formula in SOLVENTS.items():
        try:
            counts = parse_formula(formula)
        except (FormulaError, ValueError):       # pragma: no cover - constant
            continue
        mass = monoisotopic_mass(counts)
        for n in range(1, SOLVENT_CLUSTER + 1):
            for form in forms:
                adduct = ADDUCTS_BY_NAME[form]
                written = form.replace("M", f"{n}M" if n > 1 else "M")
                out.append(Candidate(
                    adduct.mz(mass * n), f"{name} cluster {written}",
                    CONTAMINANT, f"{n} x {formula} as {form}"))
    return out


def precursor_forms(neutral_mass: float, polarity: int) -> list[Candidate]:
    """The other adducts and the dimers of the precursor's own neutral."""
    out = []
    for name, molecules in PRECURSOR_FORMS.get(polarity, []):
        adduct = ADDUCTS_BY_NAME[name]
        written = name.replace("M", f"{molecules}M" if molecules > 1 else "M")
        out.append(Candidate(adduct.mz(neutral_mass * molecules),
                             f"the precursor as {written}", SATELLITE,
                             f"{molecules} x M = {neutral_mass:.4f} as {name}"))
    return out


def satellites_of(mz: float, description: str, polarity: int,
                  offered: list[float] | None = None,
                  tolerance_ppm: float = TOLERANCE_PPM) -> list[Candidate]:
    """
    The masses one measured ion drags along with it.

    Built from the *measured* mass rather than the theoretical one: a
    satellite is a statement about where a peak sits relative to another peak
    on the same axis, and an axis that is 30 ppm out is 30 ppm out for both.

    `offered` is the theoretical masses the explanation already predicted. A
    water or ammonia loss the prediction already made is not offered again —
    it was scored and it did not match, and calling it a satellite afterwards
    would be the same arithmetic wearing a different name.
    """
    out = [
        Candidate(mz + NEUTRON_SPACING, f"13C satellite of {description}",
                  SATELLITE, f"{mz:.4f} + {NEUTRON_SPACING:.5f}"),
        Candidate(mz + NA_FOR_H, f"sodiated form of {description}",
                  SATELLITE, f"{mz:.4f} + Na - H"),
        Candidate(mz + K_FOR_H, f"potassiated form of {description}",
                  SATELLITE, f"{mz:.4f} + K - H"),
    ]
    for loss, mass in (("H2O", WATER), ("NH3", AMMONIA)):
        target = mz - mass
        if target <= 0:
            continue
        if offered and _within_any(target, offered, tolerance_ppm):
            continue
        out.append(Candidate(target, f"{description} -{loss}", SATELLITE,
                             f"{mz:.4f} - {loss}"))
    return out


def _within_any(mz: float, masses, tolerance_ppm: float) -> bool:
    window = mz * tolerance_ppm * 1e-6
    return any(abs(mz - float(other)) <= window for other in masses)


def named_candidates(explanation, precursor_formula: str = "",
                     adduct=None, polarity: int = 1,
                     tolerance_ppm: float = TOLERANCE_PPM) -> list[Candidate]:
    """
    Every named mass this spectrum could be expected to hold: the background,
    the precursor's other forms, and the satellites of what was matched.
    """
    out = contaminant_masses(polarity)
    counts = _precursor_counts(precursor_formula)
    if counts and adduct is not None:
        out.extend(precursor_forms(monoisotopic_mass(counts), polarity))
    matches = list(getattr(explanation, "matches", []) or [])
    offered = [ion.mz for ion in getattr(explanation, "ions", []) or []]
    for match_ in matches:
        out.extend(satellites_of(float(match_.mz), match_.best_route, polarity,
                                 offered, tolerance_ppm))
    return out


def _precursor_counts(formula: str) -> dict[str, int]:
    try:
        return parse_formula(formula or "")
    except (FormulaError, ValueError):
        return {}


# --------------------------------------------------------------------------- #
# the constrained formula search
# --------------------------------------------------------------------------- #
def sub_formula_ranges(precursor_formula: str, adduct: Adduct
                       ) -> dict[str, tuple[int, int]] | None:
    """
    The element ranges a fragment of this precursor ion may use.

    Every element is bounded above by what the precursor ion carries — its
    molecule's atoms plus what the adduct brought — and hydrogen by that plus
    `EXTRA_H`. Returns None when the formula cannot be read, which is the
    caller's signal that there is nothing to constrain with and no search to
    run: an unconstrained search here would defeat the point of the module.
    """
    counts = _precursor_counts(precursor_formula)
    if not counts:
        return None
    ion = ion_composition(counts, adduct)
    if not ion:
        return None
    ranges = {element: (0, n) for element, n in ion.items() if n > 0}
    ranges["H"] = (0, ranges.get("H", (0, 0))[1] + EXTRA_H)
    return ranges


def _merged_hydrogen(counts: dict[str, int]) -> dict[str, int]:
    """The composition with its deuterium counted as hydrogen.

    `passes_golden_rules` weighs hydrogen against carbon, and a labelled
    standard's deuterium is hydrogen for that purpose. Left apart, `C24D4` is
    a composition with no hydrogen at all and the rule that keeps H/C above
    0.1 throws away the very compounds this was written for.
    """
    out = {}
    for element, n in counts.items():
        key = "H" if element in ("D", "[2H]") else element
        out[key] = out.get(key, 0) + n
    return out


def sub_formulas(mz: float, ranges: dict[str, tuple[int, int]], charge: int,
                 tolerance_ppm: float = TOLERANCE_PPM,
                 spectrum: tuple[np.ndarray, np.ndarray] | None = None
                 ) -> list:
    """
    The compositions within `ranges` whose ion lands on `mz`, best first.

    The search is on the *ion's* composition, not on a neutral: the mass
    asked for is the measured one with the charge's electron put back, so
    what comes out is what the fragment is made of, adduct atoms included.
    That makes the ring-and-double-bond count half-integer for an
    even-electron singly charged ion — `[C24H37O3]+` is 6.5 — and a whole
    number is then the impossible one, which is the reverse of the rule a
    neutral search applies and the reason this does its own filtering.

    An odd-electron composition is offered too, marked `radical`, and always
    ranked below every even-electron one. It is not offered out of
    completeness: on the CA-d4 EAD spectrum the second strongest unexplained
    peak, 78.0465 at 22% of the base peak, is `[C6H6]+` at +1.3 ppm and
    nothing else — electron activated dissociation makes radicals, and a
    filter written for collision-induced spectra threw the answer away.

    Ranked by the isotope pattern where the spectrum carries satellites at
    this mass, and by mass error where it does not. A product-ion scan
    usually does not: the quadrupole isolated the monoisotopic precursor and
    the satellites never reached the detector.
    """
    sign = 1 if charge >= 0 else -1
    target = mz * max(abs(charge), 1) + sign * ELECTRON_MASS
    if target <= 0:
        return []
    hits = find_formulas(target, tolerance_ppm, "ppm", ranges,
                         rdbe_range=(-0.5, 60.0), even_electron=False,
                         golden_rules=False, max_results=MAX_FORMULAS)
    kept = []
    for hit in hits:
        if target >= GOLDEN_RULE_MASS and not passes_golden_rules(
                _merged_hydrogen(hit.counts)):
            continue
        hit.mz = (hit.neutral_mass - sign * ELECTRON_MASS) / max(abs(charge), 1)
        kept.append(hit)
    if not kept:
        return []
    satellites = False
    if spectrum is not None and spectrum[0].size:
        satellites = has_isotope_satellites(spectrum[0], spectrum[1], mz,
                                            charge=charge,
                                            tolerance=ISOTOPE_TOLERANCE_DA)
    if satellites:
        for hit in kept:
            pattern = [((mass - sign * ELECTRON_MASS) / max(abs(charge), 1), a)
                       for mass, a in isotope_pattern(hit.counts,
                                                      min_abundance=0.01,
                                                      max_peaks=5)]
            hit.isotope_score = match_isotope_pattern(
                spectrum[0], spectrum[1], pattern, ISOTOPE_TOLERANCE_DA)
        kept.sort(key=lambda hit: (is_radical(hit), -hit.isotope_score,
                                   abs(hit.error_ppm)))
    else:
        kept.sort(key=lambda hit: (is_radical(hit), abs(hit.error_ppm)))
    return kept


def is_radical(hit) -> bool:
    """
    Is this composition an odd-electron ion?

    A singly charged even-electron ion — anything made by moving a proton or
    a metal cation — has a half-integer ring-and-double-bond count when the
    count is taken over the *ion's* own atoms: `[C24H37O3]+` is 6.5,
    `[C24H40O5Na]+` is 4.5, `[C24H39O5]-` is 5.5. A whole number means an
    electron was gained or lost instead, which is what a radical is.
    """
    return abs(abs(float(hit.rdbe)) % 1.0 - 0.5) > 1e-6


# --------------------------------------------------------------------------- #
# the answer
# --------------------------------------------------------------------------- #
def annotate(peaks_mz, peaks_intensity, explanation=None,
             precursor_formula: str = "", adduct=None, polarity=None,
             tolerance_ppm: float = TOLERANCE_PPM,
             floor: float = LABEL_MIN_RELATIVE,
             most: int | None = None) -> list[UnexplainedPeak]:
    """
    The strong peaks `explanation` did not match, each with the best guess.

    `peaks_mz` and `peaks_intensity` are a peak list — as complete a one as
    the caller can give, because the satellites that decide a composition sit
    below the floor the report prints at. `floor` is a share of the tallest
    peak in that list and decides which peaks are *annotated*; everything in
    the list is evidence. `most` caps the answer, strongest first.

    `adduct` is a name or an `Adduct`; `polarity` is only consulted when the
    adduct is not given or cannot be read.
    """
    mz = np.asarray(peaks_mz, dtype=float)
    intensity = np.asarray(peaks_intensity, dtype=float)
    if mz.size == 0 or intensity.size == 0 or mz.size != intensity.size:
        return []
    base = float(intensity.max())
    if base <= 0:
        return []

    found = adduct if isinstance(adduct, Adduct) else adduct_from_name(adduct)
    sign = polarity_sign(polarity) if polarity is not None else None
    if found is not None and found.name != "M (neutral)":
        sign = found.polarity
    elif sign is None:
        sign = 1
    if found is None or found.name == "M (neutral)":
        found = ADDUCTS_BY_NAME["[M+H]+" if sign > 0 else "[M-H]-"]

    taken = {round(float(m.mz), 4)
             for m in (getattr(explanation, "matches", []) or [])}
    strong = [(float(m), float(i)) for m, i in zip(mz, intensity)
              if i >= base * floor and round(float(m), 4) not in taken]
    strong.sort(key=lambda pair: -pair[1])
    if most is not None:
        strong = strong[:int(most)]
    if not strong:
        return []

    candidates = named_candidates(explanation, precursor_formula, found, sign,
                                  tolerance_ppm)
    ranges = sub_formula_ranges(precursor_formula, found)

    out = []
    for peak_mz, height in strong:
        row = UnexplainedPeak(mz=peak_mz, intensity=height,
                              share=height / base)
        best = _closest(peak_mz, candidates, tolerance_ppm)
        if best is not None:
            candidate, error = best
            row.kind = candidate.kind
            row.label = candidate.label
            row.error_ppm = error
            row.basis = candidate.basis
        elif ranges is not None:
            hits = sub_formulas(peak_mz, ranges, sign, tolerance_ppm,
                                (mz, intensity))
            if hits:
                hit = hits[0]
                row.kind = FORMULA
                row.radical = is_radical(hit)
                row.label = (f"[{hit.formula}]{'+' if sign > 0 else '-'}"
                             + ("\u2022 (odd-electron)" if row.radical else ""))
                row.error_ppm = hit.error_ppm
                row.formula = hit.formula
                row.rdbe = hit.rdbe
                row.rivals = len(hits) - 1
                row.isotope_score = (hit.isotope_score
                                     if hit.isotope_score else None)
                row.basis = (f"a sub-formula of the precursor ion "
                             f"{_ion_text(precursor_formula, found)}")
        out.append(row)
    return out


def _ion_text(formula: str, adduct: Adduct) -> str:
    counts = _precursor_counts(formula)
    ion = ion_composition(counts, adduct) if counts else None
    if not ion:
        return adduct.name
    from .chemistry import format_formula

    return f"{format_formula(ion)} ({adduct.name})"


def _closest(mz: float, candidates: list[Candidate], tolerance_ppm: float
             ) -> tuple[Candidate, float] | None:
    """The named candidate nearest `mz`, with its error in ppm."""
    window = mz * tolerance_ppm * 1e-6
    best = None
    for candidate in candidates:
        if candidate.mz <= 0 or abs(mz - candidate.mz) > window:
            continue
        error = (mz - candidate.mz) / candidate.mz * 1e6
        if best is None or abs(error) < abs(best[1]):
            best = (candidate, error)
    return best


@dataclass
class Tally:
    """How the unexplained peaks came out, for the sentence that says so."""

    peaks: int = 0
    contaminants: int = 0
    satellites: int = 0
    formulas: int = 0
    nothing: int = 0
    rows: list[UnexplainedPeak] = field(default_factory=list)

    @property
    def accounted(self) -> int:
        return self.contaminants + self.satellites

    def sentence(self) -> str:
        """One sentence: how many were named, how many were composed, how
        many nothing reached."""
        if not self.peaks:
            return ""
        parts = []
        if self.satellites:
            parts.append(f"{self.satellites} a satellite or another form of "
                         f"something already matched")
        if self.contaminants:
            parts.append(f"{self.contaminants} a known contaminant or solvent "
                         f"cluster")
        if self.formulas:
            parts.append(f"{self.formulas} a composition within the "
                         f"precursor's own atoms")
        if not parts:
            return (f"None of the {self.peaks} could be accounted for: no "
                    f"contaminant, no satellite and no formula within the "
                    f"precursor's composition reaches any of them.")
        said = ", ".join(parts[:-1])
        said = f"{said} and {parts[-1]}" if said else parts[-1]
        tail = ("" if not self.nothing else
                f"; {self.nothing} of them nothing reaches at all, which "
                f"says those masses are not pieces of this compound")
        return f"Of those, {said}{tail}."


def tally(rows: list[UnexplainedPeak]) -> Tally:
    """Count a list of annotations by what accounted for each row."""
    out = Tally(peaks=len(rows), rows=list(rows))
    for row in rows:
        if row.kind == CONTAMINANT:
            out.contaminants += 1
        elif row.kind == SATELLITE:
            out.satellites += 1
        elif row.kind == FORMULA:
            out.formulas += 1
        else:
            out.nothing += 1
    return out
