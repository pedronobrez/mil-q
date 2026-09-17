"""
Reading a product spectrum against what a structure could produce.

Enumerating cleavages says which masses are *possible*; it says nothing about
which happen. The spectrum in front of the analyst does. Matching one against
the other turns an unranked list of arithmetic into a ranked one, and the
ranking is evidence from this sample rather than a general model.

The score is the share of the spectrum's intensity that a candidate accounts
for. Counting matched peaks instead would reward a candidate that explains
forty specks of noise over one that explains the base peak, which is backwards:
a product spectrum is mostly a handful of ions that matter.

What this cannot do is prove a structure. Several candidates usually explain
the same peaks, because isomers fragment alike and because a long enough list
of possible masses will cover a spectrum by accident. The unexplained peaks are
the honest part of the answer, so they are reported too.

Everything here is scored *as an adduct*, and which one is not a detail: a
channel written 430.35 is the ammonium adduct of cholic acid-d4, and the same
spectrum scored as a protonated molecule predicts every fragment 17 Da away
from anything in it. `chemistry` holds the model — what each kind of adduct
does when the ion breaks up — and `chemistry.identify_adduct` reads the
adduct off the written precursor and refuses rather than guessing. This
module turns that into ions: `precursor_ions` for what a formula alone can
say, `structure_ions` for a drawing, `resolve_name` for a compound written
by name. A LIPID MAPS record is a drawing like any other — `explain` is
`explain_structure` with the molfile taken out of the database — and
`rank_candidates` will search every adduct the channel's polarity allows,
each candidate then carrying the one that found it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .lipidmaps import LipidDatabase, LipidRecord
from .structure import (NEUTRAL_LOSSES, PredictedIon, Structure, parse_molblock,
                        predict, suppress_hydrogens)

#: how close a predicted mass has to be to a measured one, in ppm. A TripleTOF
#: holds a few ppm on a strong product ion and rather less on a weak one.
TOLERANCE_PPM = 20.0

#: peaks below this share of the base peak are not counted against a candidate:
#: a product spectrum's baseline is full of them and nothing explains them
NOISE_SHARE = 0.01


@dataclass(frozen=True)
class PeakMatch:
    """One measured peak, and the predicted ion that lands on it."""

    mz: float
    intensity: float
    ion: PredictedIon
    #: the route the spectrum supports best, when it can tell them apart
    route: "Route | None" = None

    @property
    def best_route(self) -> str:
        return self.route.description if self.route else self.ion.description

    @property
    def error_ppm(self) -> float:
        if not self.ion.mz:
            return 0.0
        return (self.mz - self.ion.mz) / self.ion.mz * 1e6

    @property
    def error_mda(self) -> float:
        return (self.mz - self.ion.mz) * 1000.0


@dataclass
class Explanation:
    """What one candidate structure accounts for in a spectrum."""

    record: LipidRecord
    matches: list[PeakMatch] = field(default_factory=list)
    explained: float = 0.0        # intensity accounted for
    total: float = 0.0            # intensity that was there to account for
    considered: int = 0           # peaks above the noise share
    #: how many ions the prediction offered at all — the denominator of
    #: "n of m found". Without it `matched` is a count with nothing to be a
    #: share of, and a report that says "12 fragments found" has said how
    #: many were looked for only if it also says this.
    predicted: int = 0
    #: everything that was matched against, kept because a match means less
    #: on its own than it does beside the rivals that reach the same mass
    ions: list[PredictedIon] = field(default_factory=list)
    #: the adduct this was scored as, by name. A candidate list drawn from
    #: several adducts at once is a list of different hypotheses about the
    #: same number, and a row that does not say which is not readable.
    adduct: str = ""
    #: how far the written precursor sits from this candidate through that
    #: adduct, in ppm — None where nothing was searched for. It is the other
    #: half of the evidence: two adducts can both reach a precursor, and then
    #: the mass says which fits and the spectrum says which explains.
    precursor_ppm: float | None = None
    #: what each matched ion's own isotope satellites say, where the spectrum
    #: was asked (`isotope_evidence`). Empty until it is: scoring needs the
    #: peaks alone, and this needs the whole spectrum, satellites included.
    isotopes: dict = field(default_factory=dict)
    #: what Q1 let through, measured on the precursor's own M+1. None where
    #: it was not asked or could not be measured.
    isolation: "PrecursorIsolation | None" = None

    @property
    def behaviour(self) -> str:
        """What the adduct does when the ion breaks up, in one sentence."""
        from .chemistry import adduct_from_name, behaviour_text

        found = adduct_from_name(self.adduct)
        return behaviour_text(found) if found is not None else ""

    @property
    def share(self) -> float:
        """The fraction of the spectrum's intensity this accounts for."""
        return self.explained / self.total if self.total else 0.0

    @property
    def matched(self) -> int:
        return len(self.matches)

    @property
    def name(self) -> str:
        return self.record.name or self.record.abbrev

    @property
    def isotope_summary(self) -> str:
        """
        What the satellites of the matched ions said, in one sentence.

        Empty before `isotope_evidence` has been run against the spectrum,
        because nothing has been asked and a count of zero would read as an
        answer.
        """
        return isotope_sentence(self.isotopes, self.isolation)

    def unexplained(self, peaks) -> list[tuple[float, float]]:
        """The peaks it does not account for — the honest half of the answer."""
        taken = {round(m.mz, 4) for m in self.matches}
        return [(mz, height) for mz, height in peaks
                if round(mz, 4) not in taken]


@dataclass(frozen=True)
class Route:
    """One way of reaching a mass, and how the spectrum treats it."""

    description: str
    companions: tuple[float, ...] = ()      # masses it also predicts
    seen: tuple[float, ...] = ()            # of those, the ones measured

    @property
    def support(self) -> float:
        """The share of a route's companion ions that the spectrum shows."""
        return len(self.seen) / len(self.companions) if self.companions else 0.0


def companion_masses(structure: Structure, ion: PredictedIon,
                     description: str | None = None) -> list[float]:
    """
    The ions a route implies besides the one it explains.

    Losing two waters means the single-water ion exists too; losing carbon
    dioxide means something carrying that carboxyl should show up. A route
    that leaves no trace of its own intermediates is a worse explanation than
    one whose whole ladder is in the spectrum, and the spectrum is the only
    thing that can tell them apart.
    """
    if description is None or description == ion.description:
        # the ion's own route is on the ion; only a rival route has to be read
        # back out of the words, and an ion written as a form of the
        # precursor — `[M+H-3H2O]+` — has no words to read it out of
        losses = ion.losses
    else:
        losses = _losses_of(description)
    if not losses:
        return []
    charge = ion.charge or 1
    masses = []
    running = ion.mz
    for loss in reversed(losses):
        running += _loss_mass(loss) / abs(charge)
        masses.append(running)
    return masses


def routes_for(structure: Structure, ion: PredictedIon, peaks,
               tolerance_ppm: float = TOLERANCE_PPM) -> list[Route]:
    """
    Every route to one mass, ranked by how much of its ladder is present.

    This is what the enumerator alone could not settle: two routes reach the
    same number, and only the companion ions separate them.
    """
    measured = np.array(sorted(mz for mz, _height in peaks), dtype=float)
    found = []
    for description in (ion.description, *ion.alternatives):
        companions = companion_masses(structure, ion, description)
        seen = tuple(m for m in companions if _is_present(m, measured,
                                                          tolerance_ppm))
        found.append(Route(description=description,
                           companions=tuple(companions), seen=seen))
    found.sort(key=lambda r: (-r.support, len(r.companions)))
    return found


def _losses_of(description: str) -> tuple[str, ...]:
    return tuple(part[1:] for part in description.split()
                 if part.startswith("-") and part[1:] in NEUTRAL_LOSSES)


def _loss_mass(loss: str) -> float:
    from .chemistry import monoisotopic_mass, parse_formula

    return monoisotopic_mass(parse_formula(NEUTRAL_LOSSES[loss]))


def _is_present(mass: float, measured, tolerance_ppm: float) -> bool:
    if not len(measured):
        return False
    window = mass * tolerance_ppm * 1e-6
    index = int(np.searchsorted(measured, mass))
    for candidate in measured[max(index - 1, 0):index + 2]:
        if abs(candidate - mass) <= window:
            return True
    return False


def match_peaks(peaks, ions: list[PredictedIon],
                tolerance_ppm: float = TOLERANCE_PPM) -> list[PeakMatch]:
    """
    Pair measured peaks with predicted ions, nearest first.

    Each peak takes at most one ion and each ion at most one peak, so a dense
    prediction cannot claim the same peak several times over and look better
    for it.
    """
    if not len(peaks) or not ions:
        return []
    ordered = sorted(ions, key=lambda i: i.mz)
    masses = np.array([i.mz for i in ordered])
    used: set[int] = set()
    matches: list[PeakMatch] = []
    for mz, intensity in peaks:
        window = mz * tolerance_ppm * 1e-6
        lo = int(np.searchsorted(masses, mz - window, side="left"))
        hi = int(np.searchsorted(masses, mz + window, side="right"))
        best, distance = None, window
        for index in range(lo, hi):
            if index in used:
                continue
            gap = abs(masses[index] - mz)
            if gap <= distance:
                best, distance = index, gap
        if best is not None:
            used.add(best)
            matches.append(PeakMatch(mz=float(mz), intensity=float(intensity),
                                     ion=ordered[best]))
    return matches


def scored(record: LipidRecord, molecule: Structure | None, peaks,
           ions: list[PredictedIon], tolerance_ppm: float = TOLERANCE_PPM,
           adduct=None, precursor_ppm: float | None = None) -> Explanation:
    """
    A list of predicted ions measured against a spectrum.

    Every route into this module ends here — a database record, a drawing of
    one's own, a formula — so that what "explains 63.6%" means cannot depend
    on which of them asked. Only the enumeration differs, and each of them
    says in its own docstring what it enumerates.
    """
    matches = match_peaks(peaks, ions, tolerance_ppm)
    # where a mass has rival routes, let the spectrum pick between them: the
    # route whose own intermediates are present is the better explanation
    matches = [
        PeakMatch(mz=m.mz, intensity=m.intensity, ion=m.ion,
                  route=routes_for(molecule, m.ion, peaks, tolerance_ppm)[0])
        for m in matches
    ]
    total = sum(height for _mz, height in peaks)
    explained = sum(m.intensity for m in matches)
    return Explanation(record=record, matches=matches, explained=explained,
                       total=total, considered=len(peaks),
                       predicted=len(ions), ions=ions,
                       adduct=_adduct_name(adduct),
                       precursor_ppm=precursor_ppm)


def _adduct_name(adduct) -> str:
    if adduct is None:
        return ""
    return adduct if isinstance(adduct, str) else getattr(adduct, "name", "")


def explain(record: LipidRecord, peaks, charge: int = 1,
            tolerance_ppm: float = TOLERANCE_PPM,
            max_cuts: int = 1, max_losses: int = 2,
            adduct=None, deuterium: int = 0,
            precursor_ppm: float | None = None) -> Explanation | None:
    """
    How much of a spectrum one candidate structure accounts for.

    This is `explain_structure` with the drawing taken out of a LIPID MAPS
    record instead of off the disk — the same enumeration, the same adduct
    model, the same scoring. A database candidate found at an ammonium
    precursor is therefore scored with the ammonium ion on the list and the
    ladder hanging off the proton it hands over, which the cleavages alone
    cannot reach; a sodiated one is offered both carriers. Without an adduct
    the charge is a proton, which is what `charge` alone can say.
    """
    molecule = record.molecule()
    if molecule is None:
        return None
    ions = structure_ions(molecule, adduct=adduct, charge=charge,
                          max_cuts=max_cuts, max_losses=max_losses,
                          deuterium=deuterium)
    return scored(record, molecule, peaks, ions, tolerance_ppm, adduct,
                  precursor_ppm)


# --------------------------------------------------------------------------- #
# a structure, or a formula, that is not in the database
# --------------------------------------------------------------------------- #
#: what a deuterium adds over the hydrogen it replaces
D_MINUS_H = 2.01410177785 - 1.00782503223

#: the losses a formula alone can be asked about, up to this many at once.
#: One more than a structure gets, because a structure has cleavages as well
#: and a formula has only these.
FORMULA_LOSSES = 3


def with_labels(ions: list[PredictedIon], deuterium: int,
                at_least: int = 0) -> list[PredictedIon]:
    """
    The same ions carrying 0 to `deuterium` labels, when the structure was
    drawn unlabelled and nobody knows which hydrogens are heavy.

    A d4 bile acid bought as a standard is drawn by its vendor with four
    heavy hydrogens somewhere on the steroid; a fragment keeps between none
    and all of them. Enumerating every placement would be honest and
    useless; enumerating the count is what the spectrum can actually
    confirm — the ion at +2.0126 is a piece that kept two. A piece cannot
    keep more labels than it has hydrogens.
    """
    if deuterium <= 0:
        return list(ions)
    out: list[PredictedIon] = []
    for ion in ions:
        hydrogens = _hydrogen_count(ion.fragment.formula) + ion.hydrogens
        most = min(deuterium, max(hydrogens, 0))
        for k in range(at_least, most + 1):
            shift = k * D_MINUS_H / abs(ion.charge or 1)
            out.append(replace(ion, mz=ion.mz + shift, labels=k))
    return out


def _hydrogen_count(formula: str) -> int:
    from .chemistry import FormulaError, parse_formula

    try:
        counts = parse_formula(formula)
    except FormulaError:
        return 0
    return counts.get("H", 0) + counts.get("D", 0)


def custom_record(name: str, formula: str, molecule: Structure | None = None
                  ) -> LipidRecord:
    """A record for a structure or formula the database does not hold."""
    from .chemistry import FormulaError, monoisotopic_mass, parse_formula

    try:
        mass = monoisotopic_mass(parse_formula(formula)) if formula else 0.0
    except FormulaError:
        mass = 0.0
    return LipidRecord(lm_id="", name=name or formula or "your structure",
                       abbrev=name or formula, formula=formula, exact_mass=mass,
                       category="your own",
                       structure=molecule.to_compact() if molecule else None)


@dataclass(frozen=True)
class NamedCompound:
    """What a written name resolved to, and where it came from."""

    written: str
    #: the name with any label suffix taken off
    compound: str
    formula: str
    #: deuterium the name declares but does not place — the `4` of `-d4`
    labels: int = 0
    #: in words, for the basis line: a name resolved from a table is not the
    #: same evidence as one the analyst typed a formula for
    source: str = ""
    record: LipidRecord | None = None

    def molecule(self) -> Structure | None:
        return self.record.molecule() if self.record is not None else None


def resolve_name(text: str, database: "LipidDatabase | None" = None,
                 use_installed: bool = True) -> NamedCompound | None:
    """
    A compound written by name, resolved to a formula and — where there is
    one — a drawing.

    Three places are asked, in order. A **table of standards** the analyst
    buys by their trivial names: bile acids and their conjugates, by name or
    by the abbreviation on the bottle, because nothing in LIPID MAPS answers
    to `TDCA` and a `.wiff` is named after the bottle. What that table gives
    is the LIPID MAPS spelling, so the drawing still comes from the database
    when it is installed and the formula it also carries is the fallback for
    a machine without one. Then **LIPID MAPS itself**, by name or LM_ID.
    Then the **lipid shorthand**, which is a formula and no structure.

    A `-d4` on the end is read as four labels the name does not place — the
    number `explain.with_labels` enumerates — and is stripped before any of
    the three are asked. `None` means none of them knew the name, which the
    caller should say rather than guess at.
    """
    from . import lipidmaps
    from .chemistry import formula_from_name, split_labels, standard_named

    written = str(text or "").strip()
    if not written:
        return None
    compound, labels = split_labels(written)
    if database is None and use_installed:
        database = lipidmaps.database()

    def with_record(name: str, formula: str, source: str) -> NamedCompound:
        found = database.find_by_name(name, limit=1) if database else []
        record = found[0] if found else None
        if record is not None and record.formula:
            formula = record.formula
        return NamedCompound(written=written, compound=compound,
                             formula=formula, labels=labels, source=source,
                             record=record)

    known = standard_named(compound)
    if known is not None:
        formula, lm_name = known
        return with_record(lm_name, formula, "the standards table")
    if database is not None:
        found = database.find_by_name(compound, limit=1)
        if found and found[0].formula:
            return NamedCompound(written=written, compound=compound,
                                 formula=found[0].formula, labels=labels,
                                 source="LIPID MAPS", record=found[0])
    shorthand = formula_from_name(compound)
    if shorthand:
        return NamedCompound(written=written, compound=compound,
                             formula=shorthand, labels=labels,
                             source="the lipid shorthand")
    return None


def structure_ions(molecule: Structure, adduct=None, charge: int = 1,
                   max_cuts: int = 1, max_losses: int = 2,
                   deuterium: int = 0) -> list[PredictedIon]:
    """
    Everything a drawing plus an adduct can produce: the precursor as it was
    ionised, and every cleavage under the charge form its fragments carry.

    The enumerator's own arithmetic is already the protonated — or
    deprotonated — piece, which is exactly right for a proton adduct and for
    a labile one, whose adduct has left before anything breaks. So a
    labile adduct adds one ion the cleavages cannot reach, the intact
    [M+NH4]+ itself, and changes nothing else. A metal adduct runs the
    enumeration twice, once with the metal carrying the charge and once with
    a proton, because which piece keeps the metal is not something
    arithmetic can decide.

    The whole molecule's own ions are then relabelled as forms of the
    precursor — `[M+H-3H2O]+` rather than `C24H31D4O2` — since that is the
    name they are read by; a piece keeps the formula it is.

    That one ion is worth measuring. PubChem's cholic acid-d4 against its own
    infusions, two cuts and three losses at 10 ppm: 1,080 ions before and
    1,081 after, and what the extra one buys is 60.3% to 82.0% of the
    intensity under EAD at 22 eV and 9.7% to 92.0% at 12 eV, where the
    ammonium adduct *is* the base peak. Under CID at 45 eV it buys nothing —
    25 of 1,081 and 56.5% either way — because by then the precursor is
    gone.
    """
    from .chemistry import LABILE, adduct_from_name, fragment_adducts

    if isinstance(adduct, str):
        adduct = adduct_from_name(adduct)
    sign = adduct.polarity if adduct is not None else (1 if charge >= 0 else -1)
    carriers = fragment_adducts(adduct) if adduct is not None else (None,)
    ions: list[PredictedIon] = []
    for carrier in carriers:
        ions.extend(predict(molecule, charge=sign, max_cuts=max_cuts,
                            max_losses=max_losses,
                            carrier=carrier.carrier if carrier else ""))
    ions = [_as_precursor_form(ion, adduct, len(molecule.atoms))
            for ion in ions]
    # a metal adduct's own precursor is the uncut molecule the enumeration
    # already produced, carrying the metal; a labile one's is not reachable
    # from a cleavage at all, since the adduct has left by then
    if adduct is not None and adduct.behaviour == LABILE:
        intact = _intact_ion(molecule, adduct)
        if intact is not None:
            ions.append(intact)
    return with_labels(ions, deuterium)


def _intact_ion(molecule: Structure, adduct) -> PredictedIon | None:
    """The precursor as it was ionised — the one ion no cleavage reaches."""
    from .chemistry import FormulaError, monoisotopic_mass, parse_formula
    from .structure import Fragment

    try:
        counts = parse_formula(molecule.formula)
    except (FormulaError, ValueError):
        return None
    mass = monoisotopic_mass(counts)
    piece = Fragment(atoms=frozenset(range(len(molecule.atoms))),
                     formula=molecule.formula, mass=mass, cuts=())
    return PredictedIon(fragment=piece, mz=adduct.mz(mass),
                        charge=adduct.charge, hydrogens=0,
                        carrier=adduct.carrier, form=adduct.name)


def _as_precursor_form(ion: PredictedIon, adduct, atoms: int) -> PredictedIon:
    """
    An uncut molecule carrying the expected charge, renamed as the form of
    the precursor it is. A piece is left alone, and so is a whole molecule
    that reached its mass by moving hydrogens the charge cannot account
    for — `[M-H]+` is not a form anybody writes, and pretending it is would
    hide an assumption inside a tidy name.
    """
    from .chemistry import ADDUCTS_BY_NAME

    if ion.fragment.cuts or len(ion.fragment.atoms) != atoms:
        return ion
    if ion.carrier:
        carrier = next((a for a in ADDUCTS_BY_NAME.values()
                        if a.carrier == ion.carrier
                        and (a.charge > 0) == (ion.charge > 0)), None)
        if carrier is None or ion.hydrogens:
            return ion
    else:
        if ion.hydrogens != (1 if ion.charge > 0 else -1):
            return ion
        carrier = ADDUCTS_BY_NAME["[M+H]+" if ion.charge > 0 else "[M-H]-"]
    form = ion_form(carrier, ion.losses)
    if (adduct is not None and not ion.losses
            and adduct.name != carrier.name and adduct.leaves):
        form = f"{carrier.name} (-{adduct.leaves})"
    return replace(ion, form=form)


def explain_structure(molecule: Structure, peaks, name: str = "",
                      charge: int = 1, tolerance_ppm: float = TOLERANCE_PPM,
                      max_cuts: int = 1, max_losses: int = 2,
                      deuterium: int = 0, adduct=None) -> Explanation:
    """
    What a structure of one's own accounts for — a molfile from PubChem, a
    vendor's drawing, anything the database lacks.

    `deuterium` is the number of labels the drawing does not place; a
    drawing that places them (an `M  ISO` block, or explicit D atoms) needs
    none, and its fragments come out with the right masses by themselves.
    `adduct` is how the precursor was ionised; without one the charge is
    taken to be a proton, which is what `charge` alone can say.
    """
    record = custom_record(name, molecule.formula, molecule)
    ions = structure_ions(molecule, adduct=adduct, charge=charge,
                          max_cuts=max_cuts, max_losses=max_losses,
                          deuterium=deuterium)
    return scored(record, molecule, peaks, ions, tolerance_ppm, adduct)


def loss_text(losses: tuple[str, ...]) -> str:
    """`("H2O", "H2O", "H2O")` written as `-3H2O`, keeping the loss order."""
    out, seen = [], {}
    for loss in losses:
        if loss not in seen:
            seen[loss] = 0
            out.append(loss)
        seen[loss] += 1
    return "".join(f"-{seen[loss]}{loss}" if seen[loss] > 1 else f"-{loss}"
                   for loss in out)


def ion_form(adduct, losses: tuple[str, ...] = ()) -> str:
    """
    An adduct and what it then shed, written the way a method writes it:
    `[M+NH4]+`, `[M+H-3H2O]+`, `[M-H-CO2]-`.

    The losses go inside the bracket because that is where they belong: the
    thing that lost the water is the ion, not the charge.
    """
    name = adduct.name
    if "]" not in name:
        return name
    body, sign = name[1:].split("]", 1)
    return f"[{body}{loss_text(losses)}]{sign}"


def _with_losses(counts: dict[str, int], losses: tuple[str, ...]
                 ) -> dict[str, int] | None:
    """What is left of a composition after a combination of losses."""
    from .chemistry import parse_formula

    remaining = dict(counts)
    for loss in losses:
        for element, n in parse_formula(NEUTRAL_LOSSES[loss]).items():
            remaining[element] = remaining.get(element, 0) - n
            if remaining[element] < 0:
                return None
    return {element: n for element, n in remaining.items() if n > 0}


def precursor_ions(formula: str, adduct, deuterium: int = 0,
                   max_losses: int = FORMULA_LOSSES) -> list[PredictedIon]:
    """
    Every ion a precursor of this composition can give without cutting a
    bond: the intact adduct, the form its fragments carry, and the ladder of
    small neutrals that form can shed.

    Which ions those are is the adduct's business rather than arithmetic's,
    and the rule is in `chemistry`'s docstring. An ammoniated precursor is
    seen intact at [M+NH4]+ and then as [M+H]+, because the ammonia leaves
    as a neutral and hands over a proton; the ladder hangs off the [M+H]+,
    not off the ammonium, so `[M+NH4-H2O]+` is never offered. A sodiated one
    keeps its sodium, and the ladder is offered twice — once on the sodium
    and once on a proton — each ion saying which was assumed.

    The intact ion carries every label; a loss ion may have shed some of
    them with the leaving group, and `LOSS_TAKES` says how many each loss
    could take. The residual formula is corrected for the ones that left, so
    a rung written `+3D` is the composition it claims to be. Labels spelt
    into the formula (`C24H36D4O5`) count the same as labels declared as
    unplaced (`C24H40O5` with `deuterium=4`); before that they did not, and
    writing them out quietly switched the -1D rungs off.

    Measured on the ZenoTOF cholic acid-d4 infusions, whole run averaged and
    centroided, at 10 ppm: under EAD at 22 eV this finds 8 of the 56 ions it
    offers and 63.6% of the intensity — the whole ladder, 430.3489,
    413.3217, 395.3118, 377.3015, 359.2897, and 394.3035, 376.2935, 358.2836
    beside them, each having lost a label with a water. Scored as the
    ammonium adduct without this rule it found 1 of 31 and 21.7%, and as
    `[M+H]+` 4 of 31 and 34.2% — the ladder but not the precursor, which is
    98% of the base peak.
    """
    from .chemistry import (LABILE, FormulaError, adduct_from_name,
                            format_formula, fragment_adducts,
                            monoisotopic_mass, parse_formula)
    from .structure import Fragment, _loss_combinations

    if isinstance(adduct, str):
        adduct = adduct_from_name(adduct)
    if adduct is None:
        return []
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return []
    if not counts:
        return []
    if deuterium:
        counts["D"] = counts.get("D", 0) + deuterium
        counts["H"] = counts.get("H", 0) - deuterium
        if counts["H"] < 0:
            return []
    # a label is a label however it was written. `C24H36D4O5` typed out and
    # `C24H40O5` with four unplaced labels are the same four deuteriums, and
    # a dehydration can take one either way; before this, spelling them into
    # the formula quietly switched the -1D rungs off
    labelled = counts.get("D", 0)

    def ion(composition, carrier_adduct, losses, kept, form) -> PredictedIon:
        mass = monoisotopic_mass(composition)
        piece = Fragment(atoms=frozenset(), formula=format_formula(composition),
                         mass=mass, cuts=())
        return PredictedIon(
            fragment=piece, mz=carrier_adduct.mz(mass),
            charge=carrier_adduct.charge, hydrogens=0, losses=losses,
            labels=kept, carrier=carrier_adduct.carrier, form=form)

    ions = [ion(counts, adduct, (), labelled, adduct.name)]
    seen = {adduct.name}
    for carrier in fragment_adducts(adduct):
        if carrier.name not in seen:
            # the intact molecule under the fragments' own charge form. It is
            # a real ion when the adduct simply left — an ammonium hands over
            # its proton — and not one for a metal, where [M+H]+ would be a
            # different precursor rather than a product of this one.
            if adduct.behaviour == LABILE:
                ions.append(ion(counts, carrier, (), labelled,
                                f"{carrier.name} (-{adduct.leaves})"))
            seen.add(carrier.name)
        for combo in _loss_combinations(max_losses):
            if not combo:
                continue
            remaining = _with_losses(counts, combo)
            if remaining is None:
                continue
            shed = min(sum(LOSS_TAKES.get(loss, 0) for loss in combo), labelled)
            taken = sum(_hydrogen_count(NEUTRAL_LOSSES[loss]) for loss in combo)
            for kept in range(labelled - shed, labelled + 1):
                lost = labelled - kept
                composition = dict(remaining)
                if lost:
                    # a label that left went with the neutral, so the piece
                    # has one fewer D and one more ordinary H than it would
                    if composition.get("D", 0) < lost or taken < lost:
                        continue
                    composition["D"] -= lost
                    composition["H"] = composition.get("H", 0) + lost
                    composition = {k: v for k, v in composition.items() if v > 0}
                ions.append(ion(composition, carrier, tuple(combo), kept,
                                ion_form(carrier, tuple(combo))))
    return _collapse(ions)


def _collapse(ions: list[PredictedIon]) -> list[PredictedIon]:
    """
    One ion per mass, the simplest route first and the rivals kept beside it.

    Losing formic acid and losing water then carbon monoxide reach the same
    number to the fourth decimal, and offering both would count one ion
    twice: the denominator of "n of m found" would grow while nothing new
    became findable. `predict` collapses the cleavage routes for the same
    reason; this is that rule for the precursor's own.
    """
    routes: dict[int, list[PredictedIon]] = {}
    for candidate in ions:
        routes.setdefault(round(candidate.mz, 4), []).append(candidate)
    out = []
    for candidates in routes.values():
        candidates.sort(key=lambda i: (len(i.losses), i.description))
        head = candidates[0]
        others = tuple(name for name in
                       dict.fromkeys(i.description for i in candidates[1:])
                       if name != head.description)
        out.append(replace(head, alternatives=others))
    return sorted(out, key=lambda i: i.mz)


def formula_ions(formula: str, adduct_name: str, deuterium: int = 0,
                 max_losses: int = FORMULA_LOSSES) -> list[PredictedIon]:
    """
    The ions a formula alone allows — `precursor_ions` under the name the
    formula route has always called it by.

    A formula has no bonds to cut, so this is the whole of what can be said
    without a drawing: the precursor as it was ionised, the form its
    fragments carry, and the ladder of waters, ammonias and carbon dioxides
    that form could shed.
    """
    return precursor_ions(formula, adduct_name, deuterium, max_losses)


def explain_formula(formula: str, adduct_name: str, peaks, name: str = "",
                    deuterium: int = 0, tolerance_ppm: float = TOLERANCE_PPM,
                    max_losses: int = FORMULA_LOSSES) -> Explanation:
    """What a formula alone accounts for: the precursor and its losses."""
    ions = formula_ions(formula, adduct_name, deuterium, max_losses)
    record = custom_record(name, formula)
    return scored(record, None, peaks, ions, tolerance_ppm, adduct_name)


# --------------------------------------------------------------------------- #
# where the labels are
# --------------------------------------------------------------------------- #
#: how many carbon-bound hydrogens a neutral loss can take away with it.
#: A dehydration leaves with the hydroxyl's own hydrogen and one more from a
#: carbon beside it, which is measured rather than assumed — the three-water
#: loss of cholic acid-d4 is in the spectrum twice, once keeping four labels
#: and once keeping three. A decarboxylation takes no carbon-bound hydrogen
#: at all, so an ion that shed CO2 says exactly how many labels its piece had.
LOSS_TAKES: dict[str, int] = {"H2O": 1, "NH3": 1, "CO": 0, "CO2": 0,
                              "HCOOH": 1}

#: whether a hydrogen a piece *lost* on cleavage may have been a label.
#: Measured both ways against a drawing whose labels are known — PubChem's
#: cholic acid-d4 — and left on: with it off, a piece written `-2H` cannot
#: have shed a label, and on that CID spectrum the true placement satisfied
#: 43% of the evidence rather than 78% and was beaten by 96% of the
#: possibilities rather than 79%. It also stopped the inference naming a
#: position: with it off, every top placement agreed on a methyl that has
#: no label on it.
TRANSFERS_MOVE_LABELS = True

#: placements are enumerated over the positions the observations cannot tell
#: apart, so the count is far below the raw combinations; past this many the
#: molecule is too big to place and the inference says so instead of guessing
MAX_PLACEMENTS = 200_000

#: how many top placements are described
TOP_PLACEMENTS = 5


@dataclass(frozen=True)
class LabelSite:
    """
    Positions no matched ion can tell apart, and how many labels sit there.

    Two hydrogens that are inside exactly the same fragments are the same
    position as far as this spectrum is concerned. Grouping them is what
    keeps the enumeration small, and it is also the honest unit of the
    answer: nothing measured here separates them.
    """

    atoms: tuple[int, ...]          # indices into Structure.atoms
    capacities: tuple[int, ...] = ()   # what each of them could hold
    labels: int = 0                 # labels this placement puts on it
    description: str = ""

    @property
    def capacity(self) -> int:
        return sum(self.capacities)

    @property
    def single(self) -> bool:
        return len(self.atoms) == 1

    def text(self) -> str:
        if self.single:
            return f"{self.labels}× {self.description}"
        return (f"{self.labels} among {len(self.atoms)} positions nothing "
                f"here separates ({self.description}, …)")


@dataclass(frozen=True)
class LabelObservation:
    """
    One matched ion, read as a constraint on where the labels are.

    A piece that kept `kept` of the labels had that many of them inside it —
    exactly, when the ion is a cleavage, and at least that many when it also
    shed a neutral that could have carried one off (`shed`).
    """

    mz: float
    intensity: float
    description: str
    kept: int
    inside: frozenset[int]
    shed: int = 0
    weight: float = 0.0
    informative: bool = False
    #: nothing else within the tolerance reaches this peak with a different
    #: number of labels, so the count is read rather than picked
    decisive: bool = True

    def allows(self, count: int) -> bool:
        return self.kept <= count <= self.kept + self.shed


@dataclass(frozen=True)
class Placement:
    """One way of putting the labels on the molecule, and what it satisfies."""

    sites: tuple[LabelSite, ...]        # only the sites carrying a label
    score: float                        # share of matched intensity satisfied
    satisfied: int
    ways: int                           # position-by-position placements

    def text(self) -> str:
        return "; ".join(site.text() for site in self.sites)


@dataclass(frozen=True)
class AgreedPosition:
    """A position every top placement labels, and how many times."""

    atom: int
    labels: int
    description: str


@dataclass(frozen=True)
class LabelInference:
    """Where the labels can be, given what the fragments kept."""

    deuterium: int
    positions: tuple[int, ...] = ()
    observations: tuple[LabelObservation, ...] = ()
    placements: tuple[Placement, ...] = ()
    tied: int = 0
    agreed: tuple[AgreedPosition, ...] = ()
    unconstrained: tuple[int, ...] = ()
    #: labels the drawing itself places (`M  ISO`, or explicit D atoms)
    declared: tuple[int, ...] = ()
    #: the placement scored against the evidence rather than inferred from it:
    #: the drawing's own, or one handed in to be checked
    checked: tuple[int, ...] = ()
    checked_score: float | None = None
    checked_top: bool = False
    #: placements that satisfy strictly more of the evidence than it does
    checked_beaten: int = 0
    #: placements in all, position by position
    total: int = 0
    #: how much of the evidence there was to satisfy
    available: float = 0.0
    #: peaks only a different number of labels would explain
    shifted: tuple[tuple[float, str, int], ...] = ()
    heteroatoms: bool = False
    #: matched ions left out because something else within the tolerance
    #: reaches them carrying a different number of labels
    undecided: int = 0
    note: str = ""

    @property
    def informative(self) -> int:
        return sum(1 for o in self.observations if o.informative)

    @property
    def placed(self) -> bool:
        return bool(self.declared)

    @property
    def agreement(self) -> float:
        """The share of the evidence the best placement satisfies."""
        if not self.placements or not self.available:
            return 0.0
        return self.placements[0].score / self.available

    @property
    def checked_agreement(self) -> float:
        if self.checked_score is None or not self.available:
            return 0.0
        return self.checked_score / self.available

    @property
    def best(self) -> Placement | None:
        return self.placements[0] if self.placements else None

    def summary(self) -> str:
        """The finding in a sentence or two, for a panel or a report."""
        if self.note and not self.placements:
            return self.note
        n = self.deuterium
        parts = [
            f"{n} label(s) over {len(self.positions)} position(s): "
            f"{len(self.observations)} ion(s) say how many labels their piece "
            f"kept, {self.informative} of them tell placements apart."
        ]
        if self.undecided:
            parts.append(f"{self.undecided} more matched ion(s) are left out: "
                         "something else within the tolerance reaches them "
                         "with a different number of labels.")
        if self.tied > 1:
            parts.append(f"{self.tied:,} of {self.total:,} placements fit them "
                         f"equally well, at {self.agreement * 100:.0f}% of the "
                         "evidence.")
        elif self.tied == 1:
            parts.append(f"One placement of {self.total:,} fits them alone, at "
                         f"{self.agreement * 100:.0f}% of the evidence.")
        if self.agreed:
            parts.append("Every one of them labels " + ", ".join(
                f"{a.description} ({a.labels}×)" for a in self.agreed) + ".")
        else:
            parts.append("No position is in all of them.")
        if self.unconstrained:
            parts.append(f"{len(self.unconstrained)} position(s) are inside "
                         "every fragment or outside every one, so nothing "
                         "here places a label on them.")
        if self.checked:
            whose = ("The drawing places its labels itself"
                     if self.declared else "The placement asked about")
            where = ("is among the best" if self.checked_top else
                     f"is beaten by {self.checked_beaten:,} of them")
            parts.append(
                f"{whose}: that placement satisfies "
                f"{self.checked_agreement * 100:.0f}% of the evidence and "
                f"{where}.")
        if self.shifted:
            parts.append(f"{len(self.shifted)} peak(s) fit the same piece "
                         "carrying a different number of labels.")
        if self.note:
            parts.append(self.note)
        return " ".join(parts)


def label_positions(structure: Structure,
                    heteroatoms: bool = False) -> list[tuple[int, int]]:
    """
    Where a label could sit: (atom, how many it could hold).

    A heavy atom offers as many as it carries; a hydrogen still written out
    as an atom of its own offers itself. Heteroatom-bound hydrogens are left
    out by default: an O–D or an N–D exchanges with the solvent long before
    the spectrum is recorded, so a label drawn there is not one that survives
    to be measured.
    """
    out = []
    for index, atom in enumerate(structure.atoms):
        if atom.element in ("H", "D"):
            parents = structure.neighbours(index)
            if not parents:
                continue
            if heteroatoms or structure.atoms[parents[0]].element == "C":
                out.append((index, 1))
            continue
        capacity = atom.hydrogens + atom.deuterium
        if capacity > 0 and (heteroatoms or atom.element == "C"):
            out.append((index, capacity))
    return out


def placed_labels(structure: Structure) -> tuple[int, ...]:
    """
    The atoms a drawing marks as heavy hydrogen itself, one entry per label.

    An atom drawn with two of them is named twice, because that is what the
    placement says.
    """
    out: list[int] = []
    for index, atom in enumerate(structure.atoms):
        if atom.element == "D":
            out.append(index)
        out.extend([index] * atom.deuterium)
    return tuple(out)


def describe_position(structure: Structure, index: int) -> str:
    """
    A position named the way somebody reading a structure would name it.

    There is no ring lettering in a molfile, so this is the molfile's own
    numbering plus what the atom is next to — which is what actually matters
    when the question is whether the labels sit beside a hydroxyl.
    """
    atom = structure.atoms[index]
    if atom.element in ("H", "D"):
        parents = structure.neighbours(index)
        if not parents:
            return f"{atom.element}{index + 1}"
        return (f"{atom.element}{index + 1} on "
                f"{_describe_heavy(structure, parents[0])}")
    return _describe_heavy(structure, index)


def _describe_heavy(structure: Structure, index: int) -> str:
    atom = structure.atoms[index]
    hydrogens = atom.hydrogens + atom.deuterium + sum(
        1 for n in structure.neighbours(index)
        if structure.atoms[n].element in ("H", "D"))
    shape = f"{atom.element}H{hydrogens}" if hydrogens > 1 else (
        f"{atom.element}H" if hydrogens == 1 else atom.element)
    groups = structure.functional_groups([index])
    near = []
    if groups.get("carboxyl"):
        near.append("carboxyl")
    elif groups.get("carbonyl"):
        near.append("carbonyl")
    if any(structure.atoms[n].element == "O"
           and (structure.atoms[n].hydrogens
                or any(structure.atoms[h].element in ("H", "D")
                       for h in structure.neighbours(n)))
           for n in structure.neighbours(index)):
        near.append("bears the O–H")
    else:
        for neighbour in structure.neighbours(index):
            if structure.atoms[neighbour].element != "C":
                continue
            if any(structure.atoms[o].element == "O"
                   and (structure.atoms[o].hydrogens
                        or any(structure.atoms[h].element in ("H", "D")
                               for h in structure.neighbours(o)))
                   for o in structure.neighbours(neighbour)):
                near.append(f"next to C{neighbour + 1}–OH")
                break
    label = f"{atom.element}{index + 1} ({shape}"
    if near:
        label += ", " + ", ".join(near)
    return label + ")"


def infer_labels(explanation: Explanation, molecule: Structure,
                 deuterium: int = 0, peaks=None, heteroatoms: bool = False,
                 tolerance_ppm: float = TOLERANCE_PPM,
                 top: int = TOP_PLACEMENTS, ambiguous: bool = False,
                 transfers: bool = TRANSFERS_MOVE_LABELS,
                 proposed: tuple[int, ...] = ()) -> LabelInference:
    """
    Where the labels are, inferred from which fragments kept them.

    `with_labels` asks the spectrum how many labels a piece kept. That answer
    is also a statement about *which* labels: a piece that kept none of four
    contains none of them, and a piece that kept all four contains all four.
    Take a placement to be a set of positions and a fragment's observation to
    be a count, and every matched ion either agrees with a placement or rules
    it out.

    An ion only counts when it *says* a number. A deuterium is 1.55 mDa
    heavier than the hydrogen it replaced, so the same piece with one more
    label and one fewer hydrogen sits 1.55 mDa away, and a window wider than
    that holds both: the matcher takes the nearer, which decides nothing.
    Those ions are counted (`undecided`) and left out, unless `ambiguous`
    says to use them anyway.

    Two things a piece can do with a label on the way out, and both are
    allowed rather than assumed away. A neutral loss may carry one off where
    it can (`LOSS_TAKES`): a dehydration leaves with the hydroxyl's own
    hydrogen and one more from the carbon beside it, so it bounds the count
    rather than fixing it, while a decarboxylation takes no carbon-bound
    hydrogen and says exactly. And a hydrogen the piece *lost* on cleavage
    may have been a label (`TRANSFERS_MOVE_LABELS`), which is looser and was
    measured to be the honest reading.

    What comes back is the best placements, how many are tied, the positions
    every top placement agrees on, and the ones nothing here constrains.
    Where the drawing places the labels itself — or where `proposed` names a
    placement to check — that placement is scored against the same evidence
    and ranked against the rest rather than replaced by a guess.
    """
    declared = placed_labels(molecule)
    labels = deuterium or len(declared)
    if labels <= 0:
        return LabelInference(deuterium=0, heteroatoms=heteroatoms,
                              note="No labels to place.")

    positions = label_positions(molecule, heteroatoms)
    if not positions:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            note="The drawing has no position a label could sit on.")
    if sum(capacity for _atom, capacity in positions) < labels:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            positions=tuple(a for a, _c in positions),
            note=f"{labels} labels will not fit on the positions the drawing "
                 "offers.")

    every = _observations(explanation, molecule, declared, positions,
                          tolerance_ppm, transfers)
    observations = tuple(o for o in every if o.decisive or ambiguous)
    undecided = len(every) - len(observations)
    if not observations:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            positions=tuple(a for a, _c in positions), observations=every,
            undecided=undecided,
            note=(f"None of the {len(every)} matched ion(s) says how many "
                  "labels its piece kept: something else within the tolerance "
                  "reaches each of them with a different number. A label is "
                  "1.55 mDa from the hydrogen it replaced, and at "
                  f"{tolerance_ppm:g} ppm that gap is inside the window from "
                  f"m/z {1550 / max(tolerance_ppm, 1e-9):.0f} upwards: "
                  "narrow the tolerance and ask again."
                  if every else
                  "No matched ion carries a piece of the drawing, so there is "
                  "nothing to place the labels from."))

    sites = _sites(positions, observations, molecule)
    counted = _count_placements([s.capacity for s in sites], labels)
    if counted > MAX_PLACEMENTS:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            positions=tuple(a for a, _c in positions),
            observations=observations,
            note=f"{counted:,} placements over {len(sites)} distinguishable "
                 f"site(s) is past the {MAX_PLACEMENTS:,} this will enumerate "
                 "— too big a molecule to place this way.")

    found, satisfied_per_observation = _score_placements(sites, observations,
                                                         labels)
    observations = tuple(
        replace(o, informative=count < len(found))
        for o, count in zip(observations, satisfied_per_observation))

    best = max(score for score, _distribution in found)
    winners = [d for score, d in found if round(score, 9) >= round(best, 9)]
    tied = sum(_placement_ways(sites, distribution) for distribution in winners)

    placements = tuple(
        Placement(sites=tuple(
            replace(site, labels=count)
            for site, count in zip(sites, distribution) if count),
            score=best,
            satisfied=sum(1 for o in observations
                          if o.allows(_inside(o, sites, distribution))),
            ways=_placement_ways(sites, distribution))
        for distribution in winners[:top])

    agreed = _agreed(sites, winners, molecule)
    informative = [o for o in observations if o.informative]
    unconstrained = tuple(
        atom for site in sites
        if _constant(site, informative) for atom in site.atoms)

    checked = tuple(declared or proposed)
    checked_score, checked_top, beaten = None, False, 0
    if checked:
        checked_score = _score_of(checked, observations)
        checked_top = round(checked_score, 9) >= round(best, 9)
        beaten = sum(_placement_ways(sites, distribution)
                     for score, distribution in found
                     if round(score, 9) > round(checked_score, 9))

    shifted = _shifted_peaks(explanation, peaks, labels, tolerance_ppm)
    return LabelInference(
        deuterium=labels, positions=tuple(a for a, _c in positions),
        observations=observations, placements=placements, tied=tied,
        agreed=agreed, unconstrained=unconstrained, declared=declared,
        checked=checked, checked_score=checked_score, checked_top=checked_top,
        checked_beaten=beaten,
        total=sum(_placement_ways(sites, d) for _s, d in found),
        available=sum(o.weight for o in observations),
        shifted=shifted, heteroatoms=heteroatoms, undecided=undecided)


def _observations(explanation: Explanation, molecule: Structure,
                  declared: tuple[int, ...], positions, tolerance_ppm: float,
                  transfers: bool = False) -> tuple[LabelObservation, ...]:
    """Each matched ion, as what it says about the labels inside its piece."""
    candidates = {atom for atom, _capacity in positions}
    total = sum(m.intensity for m in explanation.matches) or 1.0
    masses, rivals = _constraints(explanation.ions, declared, candidates,
                                  transfers)
    out = []
    for match in explanation.matches:
        atoms = match.ion.fragment.atoms
        if not atoms:
            continue                       # a formula has no piece to speak of
        kept = match.ion.labels + sum(1 for a in declared if a in atoms)
        closeness = max(0.0, 1.0 - abs(match.error_ppm) / tolerance_ppm)
        shed = _shed_by(match.ion, transfers)
        inside = frozenset(candidates & set(atoms))
        out.append(LabelObservation(
            mz=match.mz, intensity=match.intensity,
            description=match.ion.description, kept=kept, inside=inside,
            shed=shed, weight=match.intensity / total * closeness,
            decisive=_decisive(masses, rivals, match.mz, (kept, shed, inside),
                               tolerance_ppm)))
    return tuple(out)


def _shed_by(ion: PredictedIon, transfers: bool) -> int:
    """How many labels the piece could have let go of on the way out."""
    shed = sum(LOSS_TAKES.get(loss, 0) for loss in ion.losses)
    if transfers:
        shed += max(-ion.hydrogens, 0)
    return shed


def _constraints(ions, declared, candidates, transfers: bool):
    """What each predicted ion would say about the labels, sorted by mass."""
    if not ions:
        return np.zeros(0), []
    rows = []
    for ion in ions:
        atoms = ion.fragment.atoms
        rows.append((ion.mz,
                     (ion.labels + sum(1 for a in declared if a in atoms),
                      _shed_by(ion, transfers),
                      frozenset(candidates & set(atoms)))))
    rows.sort(key=lambda row: row[0])
    return (np.array([mz for mz, _c in rows], dtype=float),
            [c for _mz, c in rows])


def _decisive(masses, rivals, mz: float, constraint, tolerance_ppm: float
              ) -> bool:
    """
    Whether a peak says something about the labels or merely gets an answer.

    Two ways a peak can fail to say anything, and both are common. A
    deuterium is 1.55 mDa heavier than the hydrogen it replaced, so the same
    piece with one more label and one fewer hydrogen sits 1.55 mDa away and
    a wider window holds both — the matcher then takes the nearer, which is
    a coin toss. And two different pieces can reach one mass while
    disagreeing about which atoms they contain, in which case the peak
    cannot say where anything is even when both agree on the count.

    So a peak counts only when every ion inside its window says the same
    thing: the same number of labels, shed the same way, over the same
    positions.
    """
    if not masses.size:
        return True
    window = mz * tolerance_ppm * 1e-6
    lo = int(np.searchsorted(masses, mz - window, side="left"))
    hi = int(np.searchsorted(masses, mz + window, side="right"))
    return all(rivals[index] == constraint for index in range(lo, hi))


def _sites(positions, observations, molecule: Structure) -> list[LabelSite]:
    """Positions grouped by the fragments they are inside — the real unit."""
    groups: dict[tuple[bool, ...], list[tuple[int, int]]] = {}
    for atom, capacity in positions:
        signature = tuple(atom in o.inside for o in observations)
        groups.setdefault(signature, []).append((atom, capacity))
    sites = []
    for members in groups.values():
        atoms = tuple(a for a, _c in members)
        sites.append(LabelSite(
            atoms=atoms, capacities=tuple(c for _a, c in members),
            description=describe_position(molecule, atoms[0])))
    sites.sort(key=lambda s: s.atoms[0])
    return sites


def _count_placements(capacities: list[int], labels: int) -> int:
    poly = _polynomial(capacities, labels)
    return poly[labels] if labels < len(poly) else 0


def _polynomial(capacities, limit: int) -> list[int]:
    """How many ways each number of labels fits, by generating polynomial."""
    poly = [1] + [0] * limit
    for capacity in capacities:
        out = [0] * (limit + 1)
        for index, value in enumerate(poly):
            if not value:
                continue
            for k in range(min(capacity, limit - index) + 1):
                out[index + k] += value
        poly = out
    return poly


def _placement_ways(sites, distribution) -> int:
    """How many position-by-position placements one distribution stands for."""
    total = 1
    for site, count in zip(sites, distribution):
        if not count:
            continue
        total *= _ways(site, count)
    return total


def _ways(site: LabelSite, count: int) -> int:
    """How many ways `count` labels fit on the positions of one site."""
    if len(site.atoms) == 1:
        return 1
    poly = _polynomial(list(site.capacities), count)
    return poly[count] if count < len(poly) else 0


def _inside(observation: LabelObservation, sites, distribution) -> int:
    return sum(count for site, count in zip(sites, distribution)
               if count and site.atoms[0] in observation.inside)


def _score_placements(sites, observations, labels: int):
    """Every distribution of the labels over the sites, scored."""
    masks = np.array([[1 if site.atoms[0] in o.inside else 0
                       for o in observations] for site in sites], dtype=int)
    low = np.array([o.kept for o in observations])
    high = np.array([o.kept + o.shed for o in observations])
    weights = np.array([o.weight for o in observations])
    capacities = [site.capacity for site in sites]
    room = [0] * (len(sites) + 1)
    for index in range(len(sites) - 1, -1, -1):
        room[index] = room[index + 1] + capacities[index]

    found: list[tuple[float, tuple[int, ...]]] = []
    satisfied = np.zeros(len(observations), dtype=int)
    distribution = [0] * len(sites)

    def walk(index: int, left: int, counts) -> None:
        if left == 0:
            for rest in range(index, len(sites)):
                distribution[rest] = 0
            hit = (counts >= low) & (counts <= high)
            satisfied[hit] += 1
            found.append((float(weights[hit].sum()), tuple(distribution)))
            return
        if index >= len(sites) or room[index] < left:
            return
        for count in range(min(capacities[index], left) + 1):
            distribution[index] = count
            walk(index + 1, left - count,
                 counts + count * masks[index] if count else counts)
        distribution[index] = 0

    walk(0, labels, np.zeros(len(observations), dtype=int))
    return found, satisfied


def _score_of(atoms, observations) -> float:
    """What one named placement — the drawing's own — satisfies."""
    chosen = list(atoms)
    counts = np.array([sum(1 for a in chosen if a in o.inside)
                       for o in observations])
    low = np.array([o.kept for o in observations])
    high = np.array([o.kept + o.shed for o in observations])
    weights = np.array([o.weight for o in observations])
    hit = (counts >= low) & (counts <= high)
    return float(weights[hit].sum())


def _agreed(sites, winners, molecule: Structure) -> tuple[AgreedPosition, ...]:
    """
    The positions every top placement labels, and how many times.

    A site holding more labels than the rest of it can take forces the
    remainder onto a named atom, which is the only way a position is
    pinned down when the site has several.
    """
    if not winners:
        return ()
    guaranteed: dict[int, int] = {}
    for site_index, site in enumerate(sites):
        for atom, capacity in zip(site.atoms, site.capacities):
            others = site.capacity - capacity
            least = min(max(0, distribution[site_index] - others)
                        for distribution in winners)
            if least > 0:
                guaranteed[atom] = least
    return tuple(
        AgreedPosition(atom=atom, labels=count,
                       description=describe_position(molecule, atom))
        for atom, count in sorted(guaranteed.items()))


def _constant(site: LabelSite, observations) -> bool:
    """A site inside every informative fragment, or outside every one."""
    if not observations:
        return True
    seen = {site.atoms[0] in o.inside for o in observations}
    return len(seen) == 1


def _shifted_peaks(explanation: Explanation, peaks, labels: int,
                   tolerance_ppm: float, limit: int = 12):
    """
    Peaks that fit a matched piece carrying a different number of labels.

    For a drawing that places its own labels this is the disagreement: the
    spectrum shows the piece with a count the placement does not allow. The
    three-water loss of cholic acid-d4 is the example — it is there twice.
    """
    if not peaks or not explanation.matches:
        return ()
    taken = {round(m.mz, 4) for m in explanation.matches}
    rest = [(mz, height) for mz, height in peaks if round(mz, 4) not in taken]
    if not rest:
        return ()
    out = []
    for mz, _height in sorted(rest, key=lambda p: p[0]):
        for match in explanation.matches:
            charge = abs(match.ion.charge or 1)
            for step in range(-labels, labels + 1):
                if step == 0:
                    continue
                predicted = match.ion.mz + step * D_MINUS_H / charge
                if abs(mz - predicted) <= predicted * tolerance_ppm * 1e-6:
                    out.append((float(mz), match.ion.description, step))
                    break
            else:
                continue
            break
        if len(out) >= limit:
            break
    return tuple(out)


def read_molfile(text: str) -> tuple[Structure | None, str]:
    """
    A structure from a `.mol` or `.sdf` file's text, and its name.

    The first record of an SDF; the name is the file's first line, which is
    where every drawing program and PubChem put it.

    Explicit hydrogens are folded into the atoms that carry them — PubChem
    writes all forty of a bile acid's — because a C–H cleavage is not a
    fragment anybody looks for and a table full of them matches a spectrum by
    accident. Deuterium the drawing places is kept, on the atom it sits on.
    """
    block = text.split("$$$$")[0]
    lines = block.splitlines()
    name = lines[0].strip() if lines else ""
    molecule = parse_molblock(block)
    return (suppress_hydrogens(molecule) if molecule is not None else None), name


def significant_peaks(mz, intensity, noise_share: float = NOISE_SHARE,
                      limit: int = 60) -> list[tuple[float, float]]:
    """The peaks worth explaining: above the noise share, strongest first."""
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if not mz.size:
        return []
    ceiling = float(intensity.max())
    if ceiling <= 0:
        return []
    keep = intensity >= ceiling * noise_share
    pairs = sorted(zip(mz[keep], intensity[keep]), key=lambda p: -p[1])
    return [(float(a), float(b)) for a, b in pairs[:limit]]


def candidates_for(database: LipidDatabase, precursor: float, adduct: str,
                   tolerance: float, unit: str = "ppm",
                   limit: int = 12) -> list[LipidRecord]:
    """
    Structures whose mass fits the precursor, one per species.

    A mass search answers with a family of isomers; taking one of each keeps
    the spectrum from being scored twelve times against the same formula.
    """
    seen: set[str] = set()
    chosen: list[LipidRecord] = []
    for match in database.search_mz(precursor, adduct, tolerance, unit):
        record = match.record
        if not record.structure:
            continue
        key = record.species
        if key in seen:
            continue
        seen.add(key)
        chosen.append(record)
        if len(chosen) >= limit:
            break
    return chosen


def adduct_gate(precursor: float) -> float:
    """
    How far a candidate found at an adduct *other than the proton one* may
    sit from the written precursor and still be offered, in Da.

    The same window `identify_adduct` uses to say which adduct a written
    number is — `ADDUCT_MATCH_DA`, widened to the precision the precursor was
    written with — because proposing that a channel was an ammonium adduct
    *is* an adduct identification and an identification needs the mass. The
    proton adduct is not gated: it is the reading the method wrote down.

    The gate is what makes a search over every adduct usable, and it was
    measured rather than assumed. A product-ion channel is matched over the
    isolation window (`matching.PRECURSOR_MATCH_DA`, 0.5 Da), which at 700 Da
    is 700 ppm and holds hundreds of species; running five adducts over it
    multiplies the candidates that explain a noisy spectrum by accident.
    Measured on the sphingolipid batch's four named compounds — whose written
    precursors are 36 to 264 ppm from the compounds themselves, so no mass
    rule can promote them — searching every adduct ungated moved them from
    ranks 1, 4, 1, 1 to 1, 5, 5, 3, the new top rows being a doubly charged
    glycosphingolipid at −171 ppm and a potassiated ceramide at +356 ppm with
    two to three times as many predicted ions each. Gated, all four come back
    at ranks 1, 4, 1, 1 with the same share and the same ions as the
    single-adduct search: the gate leaves the proton list exactly as it was
    and admits another adduct only where the mass says so. On the ZenoTOF DIA
    window holding TG 52:2 at 876.80 it admits the ammonium and the compound
    is found at 24.0% of the spectrum and −1.7 ppm, where a `[M+H]+` search
    does not list it at all.
    """
    from .chemistry import ADDUCT_MATCH_DA
    from .lipidmaps import mass_precision

    return max(ADDUCT_MATCH_DA, mass_precision(float(precursor)))


def rank_candidates(database: LipidDatabase, precursor: float, peaks,
                    adduct: str | None = "[M+H]+", tolerance: float = 20.0,
                    unit: str = "ppm", max_cuts: int = 1, max_losses: int = 2,
                    limit: int = 12, polarity=None) -> list[Explanation]:
    """
    Every candidate for the precursor, ordered by what it accounts for.

    This is the whole point of the exercise: the enumerator cannot say which
    cleavage happens, and the spectrum can.

    `adduct` may be left out (None), and then the search is run at every
    adduct the channel's polarity allows and each candidate carries the one
    it was found at. That is not a convenience: a triacylglycerol acquired at
    876.80 is not a lipid at all as `[M+H]+` — the database answers with
    nothing — and the ammonium is the only adduct that reaches it. A search
    fixed to one adduct cannot say so; it can only come back empty.

    An adduct other than the proton one then has to *name* the precursor —
    see `adduct_gate`, which is where that is measured. The proton adduct
    keeps the whole isolation window it always had, because that is the
    reading the method wrote down and needs no identifying.

    There is no charge argument: the sign is the adduct's own, and an adduct
    that did not declare one would not be an adduct.
    """
    from .chemistry import (ADDUCTS_BY_NAME, adduct_from_name,
                            adducts_of_polarity, mass_error_ppm)

    if adduct:
        forms = [f for f in [adduct_from_name(adduct)] if f is not None]
        gate, core = None, set()
    else:
        forms = adducts_of_polarity(polarity)
        gate = adduct_gate(precursor)
        # the proton adduct of each polarity being searched. A spectrum that
        # arrived with no polarity behind it is searched at both, and both
        # readings are then the written one rather than an identification.
        signs = {f.polarity for f in forms}
        core = {ADDUCTS_BY_NAME["[M+H]+" if sign > 0 else "[M-H]-"].name
                for sign in signs}
    found: list[Explanation] = []
    for form in forms:
        for record in candidates_for(database, precursor, form.name, tolerance,
                                     unit, limit):
            theoretical = form.mz(record.exact_mass)
            if (gate is not None and form.name not in core
                    and abs(float(precursor) - theoretical) > gate):
                continue
            error = (mass_error_ppm(float(precursor), theoretical)
                     if record.exact_mass else None)
            explanation = explain(record, peaks, 1 if form.charge > 0 else -1,
                                  TOLERANCE_PPM, max_cuts, max_losses,
                                  adduct=form, precursor_ppm=error)
            if explanation is not None:
                found.append(explanation)
    # what a candidate explains first, then how many peaks, then how well the
    # mass fits — the last only ever separates candidates the spectrum could
    # not, which on a channel with no product ions worth the name is all of them
    found.sort(key=lambda e: (-e.share, -e.matched,
                              abs(e.precursor_ppm or 0.0)))
    return found[:limit] if len(forms) > 1 else found


# --------------------------------------------------------------------------- #
# the isotope pattern as evidence for a fragment
# --------------------------------------------------------------------------- #
#: how many times over the noise an ion's *predicted* M+1 has to stand before
#: the spectrum is asked about it at all. Below it the satellite is not
#: absent, it is unmeasurable, and the two are different findings: a fragment
#: of 300 counts whose M+1 should be 18% of it has 54 counts of satellite to
#: show, which on a spectrum whose noise is 20 counts says nothing either way.
SATELLITE_DETECTABLE = 3.0

#: how much of an ion's predicted M+1 has to be there before the satellites
#: are believed to have been transmitted at all, as a share of the
#: prediction. This is `infusion_quant.ISOTOPES_TRANSMITTED` asked of the
#: precursor rather than of a cross-talk term, and it is the same
#: measurement: on a product-ion acquisition Q1 keeps the monoisotopic
#: precursor and the satellites never enter the collision cell.
ISOLATION_TRANSMITTED = 0.10

#: what one matched ion's satellites came to
ISOTOPES_AGREE = "agrees"
ISOTOPES_DISAGREE = "disagrees"
ISOTOPES_UNMEASURABLE = "no satellite measurable"
ISOTOPES_NONE_EXPECTED = "none expected: precursor isolated monoisotopically"

#: how near a proposed composition's m/z has to come to the ion's own before
#: the two are the same ion. Half a millidalton: the readings `ion_counts`
#: chooses between are a proton, a water or a deuterium apart, so nothing
#: needs a wider window and a wider one could take the wrong reading.
COMPOSITION_TOLERANCE_DA = 0.0005


@dataclass(frozen=True)
class PrecursorIsolation:
    """
    What the quadrupole let through, read off the precursor's own M+1.

    A product-ion spectrum of a monoisotopically isolated precursor cannot
    show a 13C satellite on any fragment, because every fragment in it came
    from a precursor that had no 13C in it to begin with. That is not a
    property of the fragments and it cannot be read off them one at a time;
    it is a property of the isolation, and this is where it is measured.
    """

    mz: float
    height: float = 0.0
    #: the ion's M+1 as a share of its own monoisotopic peak
    measured: float | None = None
    #: what its composition demands
    expected: float | None = None
    #: which ion this was read off, in words — the precursor itself, or the
    #: strongest matched fragment where the precursor is not in the spectrum
    basis: str = "the precursor"
    note: str = ""

    @property
    def transmission(self) -> float | None:
        """Measured M+1 over expected M+1 — what the window passed."""
        if self.measured is None or not self.expected:
            return None
        return self.measured / self.expected

    @property
    def monoisotopic(self) -> bool:
        """Did Q1 keep the monoisotopic precursor and nothing else?"""
        transmitted = self.transmission
        return transmitted is not None and transmitted < ISOLATION_TRANSMITTED

    @property
    def sentence(self) -> str:
        if self.measured is None or self.expected is None:
            return self.note or "the isolation was not measured"
        return (f"{self.basis}'s M+1 is {self.measured * 100:.2f}% of it "
                f"against {self.expected * 100:.1f}% predicted, a "
                f"transmission of {(self.transmission or 0.0) * 100:.1f}%")


@dataclass(frozen=True)
class IsotopeEvidence:
    """One matched ion held against its own isotope satellites."""

    ion: PredictedIon
    #: where the ion was measured, and how tall
    mz: float
    height: float = 0.0
    #: the ion's own composition, where it could be worked out
    composition: dict | None = None
    #: M, M+1, M+2 measured, as shares of M
    measured: tuple[float, ...] = ()
    #: the same from the composition
    expected: tuple[float, ...] = ()
    #: agreement over the satellites alone, 0 to 1 — `chemistry`'s own rule
    agreement: float | None = None
    verdict: str = ISOTOPES_UNMEASURABLE
    note: str = ""

    @property
    def agrees(self) -> bool:
        return self.verdict == ISOTOPES_AGREE

    @property
    def measurable(self) -> bool:
        return self.verdict in (ISOTOPES_AGREE, ISOTOPES_DISAGREE)

    @property
    def text(self) -> str:
        """The verdict with its numbers, for a row or a report."""
        if self.verdict == ISOTOPES_DISAGREE and len(self.measured) > 1 \
                and len(self.expected) > 1:
            return (f"disagrees: M+1 {self.measured[1]:.2f} measured vs "
                    f"{self.expected[1]:.2f} expected")
        if self.verdict == ISOTOPES_AGREE and len(self.measured) > 1:
            return f"agrees: M+1 {self.measured[1]:.2f}"
        return self.note or self.verdict


def ion_counts(ion: PredictedIon, adduct=None) -> dict[str, int] | None:
    """
    The atoms one predicted ion carries, checked against its own m/z.

    An isotope pattern has to be computed from a composition, and a predicted
    ion does not simply carry one. A cleavage ion holds the *piece's* formula
    with the hydrogens it moved, the neutrals it then shed and any labels
    kept recorded beside it; a precursor-form ion holds the composition it
    already is, with the adduct's own atoms outside it. Reconstructing either
    from the other's rule gives a composition that is wrong by a water or by
    a proton, and an isotope pattern computed from that is wrong quietly.

    So the composition is not deduced, it is *proposed and checked*: each
    reading is built, turned back into an m/z, and kept only if it reproduces
    the ion's own mass. `None` where none of them does, which is a fragment
    whose satellites are not measured rather than one that failed.
    """
    from .chemistry import (ELECTRON_MASS, FormulaError, adduct_from_name,
                            monoisotopic_mass, parse_formula)

    if isinstance(adduct, str) and adduct:
        adduct = adduct_from_name(adduct)
    try:
        base = dict(parse_formula(ion.fragment.formula))
    except (FormulaError, ValueError):
        return None
    if not base:
        return None
    charge = ion.charge or 1
    extras: list[dict[str, int]] = [{}]
    if ion.carrier:
        extras.append({ion.carrier: 1})
    added = getattr(adduct, "added", "")
    if added:
        try:
            extras.append(dict(parse_formula(added)))
        except (FormulaError, ValueError):
            pass
    extras.append({"H": 1})

    for shed in (True, False):
        for labelled in (True, False):
            counts = dict(base)
            counts["H"] = counts.get("H", 0) + ion.hydrogens
            if shed and ion.losses:
                counts = _with_losses(counts, ion.losses) or {}
            if labelled and ion.labels:
                if counts.get("H", 0) < ion.labels:
                    continue
                counts["H"] -= ion.labels
                counts["D"] = counts.get("D", 0) + ion.labels
            counts = {e: n for e, n in counts.items() if n > 0}
            if not counts:
                continue
            for extra in extras:
                whole = dict(counts)
                for element, n in extra.items():
                    whole[element] = whole.get(element, 0) + n
                whole = {e: n for e, n in whole.items() if n > 0}
                mass = monoisotopic_mass(whole)
                mz = (mass - charge * ELECTRON_MASS) / abs(charge)
                if abs(mz - ion.mz) <= COMPOSITION_TOLERANCE_DA:
                    return whole
    return None


def noise_floor(intensity) -> float:
    """
    What a peak has to beat here to be a peak at all: the median height.

    A centroided product-ion spectrum is mostly noise by count — a few ions
    that matter and hundreds of specks — so the median of the positive
    heights is the noise and not the signal. It is used for one thing only:
    deciding whether an ion's *predicted* satellite would have been visible,
    so that an unmeasurable satellite is reported as unmeasurable.
    """
    values = np.asarray(intensity, dtype=float)
    values = values[values > 0]
    if not values.size:
        return 0.0
    return float(np.median(values))


#: how near a satellite has to be read, whatever the tolerance says. Two
#: millidaltons: the thing a satellite window must not catch is the same
#: piece carrying one more deuterium, and a label is 1.00628 Da from the
#: hydrogen it replaced against the neutron's 1.00336 — 2.9 mDa apart. The
#: survey's own 20 mDa merges them, which is why this does not reuse it.
SATELLITE_WINDOW_DA = 0.002


def _satellite_ratios(mz, intensity, pattern, found_mz: float,
                      tolerance_ppm: float = TOLERANCE_PPM
                      ) -> tuple[float, ...]:
    """
    The measured M, M+1, M+2 of one ion, as shares of its M.

    `chemistry`'s own reading, moved onto the mass the ion was measured at
    rather than the mass it was predicted at: these spectra sit several ppm
    off their own axis, and a satellite window placed on the prediction would
    miss by that much at every rung together.

    The window is the caller's own tolerance and never narrower than
    `SATELLITE_WINDOW_DA`, which is what keeps a labelled piece's `-1D` rung
    out of the place its M+1 belongs.
    """
    from .chemistry import measured_ratios

    if not pattern:
        return ()
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    shift = found_mz - pattern[0][0]
    moved = [(mass + shift, abundance) for mass, abundance in pattern]
    window = max(found_mz * tolerance_ppm * 1e-6, SATELLITE_WINDOW_DA)
    # only the stretch the pattern covers. A candidate list is scored ion by
    # ion against a whole profile spectrum, and reading three windows out of
    # a quarter of a million points sixty times over is the difference
    # between a table that appears and one that arrives
    lo = int(np.searchsorted(mz, moved[0][0] - window, side="left"))
    hi = int(np.searchsorted(mz, moved[-1][0] + window, side="right"))
    return measured_ratios(mz[lo:hi], intensity[lo:hi], moved, window=window)


def _pattern_of(counts: dict, charge: int, max_peaks: int = 3):
    """The theoretical pattern of a composition, M scaled to 1."""
    from .chemistry import ELECTRON_MASS, isotope_pattern

    pattern = isotope_pattern(counts, min_abundance=0.0005,
                              max_peaks=max_peaks)
    if not pattern:
        return []
    base = pattern[0][1] or 1.0
    charge = charge or 1
    return [((mass - charge * ELECTRON_MASS) / abs(charge), abundance / base)
            for mass, abundance in pattern]


def _intact_of(explanation: Explanation, adduct) -> PredictedIon | None:
    """The precursor as it was ionised, among the ions that were offered."""
    named = adduct.name if adduct is not None else explanation.adduct
    # the heaviest of them, because a drawing whose labels are unplaced is
    # offered as the same intact ion carrying 0 to n of them and the
    # precursor of a d4 standard is the one carrying all four
    forms = [ion for ion in explanation.ions
             if ion.form and ion.form == named and not ion.losses]
    if forms:
        return max(forms, key=lambda i: i.mz)
    # nothing was scored as an adduct. An uncut molecule that reached its
    # mass by taking one hydrogen is still a precursor form — that is what
    # `_as_precursor_form` renames — and one that reached it by taking two
    # is an assumption about the cleavage, so the named ones come first
    uncut = [ion for ion in explanation.ions
             if not ion.losses and not ion.fragment.cuts]
    named_forms = [ion for ion in uncut if ion.form]
    if named_forms:
        return max(named_forms, key=lambda i: i.mz)
    return max(uncut, key=lambda i: i.mz) if uncut else None


def _peak_near(mz, intensity, target: float, tolerance_ppm: float):
    """
    The tallest centroid within the tolerance of a mass, and its height.

    `precursor.in_spectrum` answers the same question for a *profile*
    spectrum and cannot be reused here: it refines across the neighbouring
    points, which on sticks reads 430.3489 as 429.7675. These spectra are
    centroids by the time they reach this.
    """
    window = max(target * tolerance_ppm * 1e-6, ISOLATION_WINDOW_DA)
    inside = (mz >= target - window) & (mz <= target + window)
    if not inside.any():
        return None
    heights = intensity[inside]
    index = int(np.argmax(heights))
    return float(mz[inside][index]), float(heights[index])


#: how far either side of a predicted mass the ion itself may be looked for
#: when the tolerance is tighter than that. These spectra sit 4 to 7 ppm off
#: their own axis before `recalibrate.fit_infusion` is applied, and a
#: precursor missed for that reason would be read as an isolation that could
#: not be measured.
ISOLATION_WINDOW_DA = 0.005


def _transmission_at(ion: PredictedIon, mz, intensity, floor: float,
                     tolerance_ppm: float, basis: str, adduct=None,
                     at: float | None = None) -> PrecursorIsolation:
    """One ion's own M+1 against what its composition demands."""
    counts = ion_counts(ion, adduct)
    if not counts:
        return PrecursorIsolation(mz=ion.mz, basis=basis,
                                  note=f"{basis}'s composition is not known")
    pattern = _pattern_of(counts, ion.charge)
    if len(pattern) < 2:
        return PrecursorIsolation(mz=ion.mz, basis=basis,
                                  note=f"{basis} has no satellite to predict")
    found = _peak_near(mz, intensity, ion.mz if at is None else at,
                       tolerance_ppm)
    if found is None:
        return PrecursorIsolation(
            mz=ion.mz, basis=basis,
            note=f"{basis} is not in this spectrum, so what the quadrupole "
                 "passed cannot be read from it")
    found_mz, height = found
    would_be = height * pattern[1][1]
    if would_be < floor:
        return PrecursorIsolation(
            mz=found_mz, height=height, basis=basis,
            note=f"{basis}'s own M+1 would be {would_be:,.0f} counts, under "
                 f"the {floor:,.0f} this spectrum can show: what the "
                 "quadrupole passed cannot be read from it")
    measured = _satellite_ratios(mz, intensity, pattern, found_mz,
                                 tolerance_ppm)
    if len(measured) < 2:
        return PrecursorIsolation(mz=found_mz, height=height, basis=basis,
                                  note=f"{basis} has no satellite to read")
    return PrecursorIsolation(mz=found_mz, height=height, basis=basis,
                              measured=float(measured[1]),
                              expected=float(pattern[1][1]))


def precursor_isolation(explanation: Explanation, mz, intensity,
                        tolerance_ppm: float = TOLERANCE_PPM,
                        floor: float = 0.0) -> PrecursorIsolation | None:
    """
    What Q1 passed, measured on an M+1 in this spectrum.

    The question has to be asked before any fragment's satellites are read,
    because it decides what reading them means. A precursor isolated
    monoisotopically produces fragments that cannot carry a 13C: the
    satellite is not missing, it was never made, and a column of
    disagreements would be an artefact of the isolation rather than evidence
    about the structure.

    The precursor's own M+1 is the direct reading and is tried first. Where
    the precursor is not in the spectrum — the ordinary case at a collision
    energy high enough to consume it, and three of the seven bile-acid
    infusions — the **strongest matched fragment** answers the same question,
    because a fragment of a monoisotopically isolated precursor cannot carry
    a satellite either: whatever the window passed, the strongest ion in the
    spectrum is where it would show. `basis` says which was read, and it is
    printed rather than assumed, since the second reading is a fragment being
    used to say something about all the fragments.

    Either way the ion has to be tall enough for its own predicted M+1 to
    clear `floor`; below that nothing is claimed. `None` only where the
    prediction offers no intact precursor and nothing was matched.
    """
    from .chemistry import adduct_from_name

    adduct = adduct_from_name(explanation.adduct) if explanation.adduct else None
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    intact = _intact_of(explanation, adduct)
    read = None
    if intact is not None:
        read = _transmission_at(intact, mz, intensity, floor, tolerance_ppm,
                                "the precursor", adduct)
        if read.measured is not None:
            return read
    strongest = max(explanation.matches, key=lambda m: m.intensity,
                    default=None)
    if strongest is None or (intact is not None
                             and strongest.ion.mz == intact.mz):
        return read
    fallback = _transmission_at(strongest.ion, mz, intensity, floor,
                                tolerance_ppm, "the strongest matched fragment",
                                adduct, at=strongest.mz)
    if fallback.measured is None and read is not None:
        return read
    return fallback


def isotope_evidence(explanation: Explanation, mz, intensity,
                     tolerance_ppm: float = TOLERANCE_PPM,
                     detectable: float = SATELLITE_DETECTABLE
                     ) -> dict[PredictedIon, IsotopeEvidence]:
    """
    Each matched ion held against its own isotope satellites.

    The precursor's adduct is confirmed by the survey's isotope pattern
    (`chemistry.adduct_evidence`); this is the same question asked of every
    *fragment*, on the product-ion spectrum itself. A fragment of a lipid
    carries fifteen to thirty carbons and therefore an M+1 of 16 to 33%, and
    where that satellite is in the spectrum it is evidence that the peak is
    the composition claimed rather than an unrelated ion of the same mass —
    which no ppm figure can say, since an isobar is inside the tolerance by
    definition.

    Four things make the answer honest rather than tidy.

    **A monoisotopically isolated precursor has no satellites to give.**
    Measured first (`precursor_isolation`), and where Q1 kept the
    monoisotopic ion alone every fragment's verdict is *none expected*
    rather than a disagreement — the fragments of a 12C-only precursor
    cannot carry a 13C, and reading their flat M+1 as evidence against the
    structure would be reading the instrument's own selection. On all seven
    ZenoTOF bile-acid infusions that is what the data say: transmission
    0.00 – 0.43%, against `ISOLATION_TRANSMITTED`.

    **A satellite window that holds another predicted ion reads that ion.**
    A deuterium is 1.00628 Da from the hydrogen it replaced and a neutron
    1.00336, so the same piece carrying one more label sits 2.9 mDa from
    where its M+1 belongs: on the bile acids the `-1D` rungs read M+1 shares
    of 2.2, 7.9, 12.6 and 40.5 — their `+4D` neighbours, not their
    satellites. Those ions are unmeasurable and say so.

    **An unmeasurable satellite is not a disagreement.** The predicted M+1
    of an ion of 300 counts on a spectrum whose noise is 40 is not something
    the spectrum can be asked about, and `detectable` is where the asking
    stops.

    **A disagreement does not remove the match.** It is printed beside it.
    An unexpected satellite has several innocent causes and one guilty one,
    and the ranking is not the place to decide between them.

    The figures are in `lipid-maps.md`.
    """
    from .chemistry import PATTERN_AGREES, adduct_from_name, pattern_agreement

    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    floor = noise_floor(intensity) * float(detectable)
    isolation = precursor_isolation(explanation, mz, intensity, tolerance_ppm,
                                    floor)
    stripped = isolation is not None and isolation.monoisotopic
    adduct = adduct_from_name(explanation.adduct) if explanation.adduct else None
    others = np.array(sorted(ion.mz for ion in explanation.ions), dtype=float)

    found: dict[PredictedIon, IsotopeEvidence] = {}
    for match in explanation.matches:
        ion = match.ion
        counts = ion_counts(ion, adduct)
        if not counts:
            found[ion] = IsotopeEvidence(
                ion=ion, mz=match.mz, height=match.intensity,
                note="the ion's composition is not known")
            continue
        pattern = _pattern_of(counts, ion.charge)
        expected = tuple(round(a, 6) for _m, a in pattern)
        measured = _satellite_ratios(mz, intensity, pattern, match.mz,
                                     tolerance_ppm)
        common = dict(ion=ion, mz=match.mz, height=match.intensity,
                      composition=counts, measured=measured, expected=expected)
        if stripped:
            found[ion] = IsotopeEvidence(
                verdict=ISOTOPES_NONE_EXPECTED,
                note=f"none expected: {isolation.sentence}", **common)
            continue
        if len(expected) < 2:
            found[ion] = IsotopeEvidence(
                note="the composition has no satellite to predict", **common)
            continue
        rival = _rival_at(others, match.mz + (pattern[1][0] - pattern[0][0]),
                          ion.mz, tolerance_ppm)
        if rival is not None:
            found[ion] = IsotopeEvidence(
                note=f"another predicted ion is at {rival:.4f}, inside where "
                     "this one's M+1 belongs: the satellite cannot be read",
                **common)
            continue
        would_be = match.intensity * expected[1]
        if would_be < floor:
            found[ion] = IsotopeEvidence(
                note=f"its M+1 would be {would_be:,.0f} counts, under the "
                     f"{floor:,.0f} this spectrum can show", **common)
            continue
        agreement = pattern_agreement(measured, expected)
        if agreement is None:
            found[ion] = IsotopeEvidence(
                note="nothing to compare at M+1", **common)
            continue
        found[ion] = IsotopeEvidence(
            agreement=agreement,
            verdict=(ISOTOPES_AGREE if agreement >= PATTERN_AGREES
                     else ISOTOPES_DISAGREE), **common)
    explanation.isotopes = found
    explanation.isolation = isolation
    return found


def _rival_at(masses, target: float, own: float, tolerance_ppm: float
              ) -> float | None:
    """
    Another predicted ion sitting where this one's M+1 would be.

    The prediction is the only place a rival can be looked for: nothing else
    knows that the same piece carrying one more deuterium is 2.9 mDa from
    this piece's 13C satellite. The ion's own mass is excluded, since a
    prediction offering an ion is not a rival to itself.
    """
    if not masses.size:
        return None
    window = max(target * tolerance_ppm * 1e-6, SATELLITE_WINDOW_DA)
    lo = int(np.searchsorted(masses, target - window, side="left"))
    hi = int(np.searchsorted(masses, target + window, side="right"))
    for candidate in masses[lo:hi]:
        if abs(candidate - own) > window:
            return float(candidate)
    return None


def isotope_column(found: dict,
                   isolation: "PrecursorIsolation | None" = None) -> str:
    """
    The same finding in a table cell: three words at most.

    Empty where the spectrum was not asked, which is what a column has to
    show for a row nothing was measured on — not a zero.
    """
    if not found:
        return ""
    total = len(found)
    agree = sum(1 for e in found.values() if e.agrees)
    disagree = sum(1 for e in found.values() if e.verdict == ISOTOPES_DISAGREE)
    none = sum(1 for e in found.values()
               if e.verdict == ISOTOPES_NONE_EXPECTED)
    if none == total:
        return "none expected"
    if not agree and not disagree:
        return f"0 of {total} measurable"
    said = f"{agree} of {total} agree"
    return f"{said}, {disagree} disagree" if disagree else said


def isotope_sentence(found: dict,
                     isolation: "PrecursorIsolation | None" = None) -> str:
    """
    What the satellites of the matched ions came to, in a sentence.

    Empty where nothing was asked, because a count of nothing reads as an
    answer and it is not one.
    """
    if not found:
        return ""
    total = len(found)
    agree = sum(1 for e in found.values() if e.agrees)
    disagree = sum(1 for e in found.values() if e.verdict == ISOTOPES_DISAGREE)
    none = sum(1 for e in found.values()
               if e.verdict == ISOTOPES_NONE_EXPECTED)
    if none == total:
        said = isolation.sentence if isolation is not None else ""
        return (f"None of the {total} matched ion(s) can carry a satellite: "
                f"{said}." if said
                else f"None of the {total} matched ion(s) can carry a satellite.")
    rest = total - agree - disagree - none
    parts = [f"{agree} of {total} matched ion(s) have a satellite that agrees, "
             f"{disagree} disagree, {rest} unmeasurable"]
    if none:
        parts.append(f"{none} could not carry one")
    said = "; ".join(parts) + "."
    if isolation is not None and isolation.measured is None:
        said += (f" What the quadrupole passed was not measured: "
                 f"{isolation.note}.")
    if disagree:
        said += (" A disagreeing satellite is printed, not removed: the "
                 "isolation may have stripped it.")
    return said
