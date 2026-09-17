"""
An explanation's margin: what the compound explains against what its nearest
impostors explain.

`explain` says a candidate accounts for 63.6% of a spectrum. On its own that
number cannot be read. A long enough list of predicted masses covers a
spectrum by accident, and the share it reaches depends on how many ions the
prediction offered, how noisy the vial was and how wide the tolerance is —
none of which the number says. The only thing that makes it evidence is what
*something else* reaches on the same peaks with the same settings: a compound
that explains 63.6% where its nearest neighbour on the mass axis explains 20%
has been distinguished, and one that explains 63.6% where a neighbour explains
61% has not been distinguished by the spectrum at all, however good the fit
looks.

This is `library.py`'s reverse score in a different coat — a score with a
contrast beside it — and the contrast is drawn from the same place the
candidate came from: the LIPID MAPS records that fit the *written* precursor
at any adduct the channel's polarity allows, which is exactly the set the
ranked table already offers. The margin is the difference between the chosen
compound and the best of them, in points of the spectrum's intensity.

**Which neighbours count as impostors.** Not the chosen compound, not the
chosen compound at another adduct, and not an isomer carrying the same
formula. A record with the same formula predicts the same precursor, the same
neutral losses and — for the formula route — precisely the same list of
masses: same formula, same arithmetic, no contrast. Scoring it would put the
chosen compound's own number in the impostor column and report a margin of
zero for a spectrum that had never been in doubt. On a lipidomics batch that
is not an edge case but the ordinary one: each of the sphingolipid batch's
four named compounds had one or two same-formula records left out, and the
margin that means something is the one over a *different* formula. The count
of what was left out is carried and printed, because a margin measured over
sixteen neighbours when eighteen were found is a different statement from one
measured over eighteen.

The threshold is measured; see `THIN_MARGIN`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .explain import (FORMULA_LOSSES, TOLERANCE_PPM, Explanation, adduct_gate,
                      candidates_for, explain, formula_ions, scored,
                      significant_peaks)
from .matching import PRECURSOR_MATCH_DA

#: at most how many neighbours are scored, nearest by mass first.
#:
#: A cap and not a target. Ten was tried first and it *overstates the margin*:
#: mass ordering inside a 0.7 Da isolation window carries almost no
#: information — the four named sphingolipids sit 36 to 264 ppm from their own
#: written precursors, so the true compound is not the nearest either — and
#: the ten nearest left the best impostor outside on three of the four
#: channels. Measured: SM 34:1 read 17.5 points at ten neighbours against 16.2
#: over the whole pool, SM 36:1 read 11.2 against 2.1, and Cer 42:1 read 4.3
#: against 2.1. A margin that flatters itself by nine points because a rival
#: was not scored is worse than no margin.
#:
#: The whole gated pool is 16 to 25 candidates on those channels and costs
#: 0.1 to 0.5 s to score, so the cap is only a guard against a region of the
#: database nobody has met yet. Above 25 the answer stopped moving on every
#: spectrum measured: the pool itself runs out.
NEIGHBOURS = 50

#: below this many points of margin, the spectrum has not told the compound
#: apart from its neighbours, and the explanation is not evidence of identity
#: however large its share.
#:
#: Measured, not chosen. Eleven real spectra: the six bile-acid infusions of
#: `Bileomics` (CA-d4, DCA-d4 and TDCA-d4, each under CID and under EAD at
#: 22 eV, scored from the formula) and the four named sphingolipids of
#: injection 09 of the 26-injection batch (scored from the LIPID MAPS
#: drawing). The margins, sorted:
#:
#: ``-3.0  2.1  2.1  6.1 | 13.9  15.3  16.2  24.2  41.9  71.2``
#:
#: The gap in that list is between 6.1 and 13.9, so the line goes at **ten
#: points**. What falls below it are the four spectra where a rival explains
#: the same peaks for another reason: a ceramide written at 538.6 that
#: explains 9.5% where three lysophospholipids of a different formula explain
#: 11 to 12.4%, a sphingomyelin at 19.4% against a phosphatidic acid at
#: 17.3%, and a taurine-conjugated bile acid at 78.4% against a sodiated
#: lysoPC at 72.3%. That last one is a pure standard infused from a vial and
#: the flag is still right: the compound is known from the bottle, not from
#: this spectrum, and the margin is the only thing on the page that says so.
#:
#: It is a flag and not a verdict. A thin margin is as often a statement
#: about the acquisition — a written precursor 264 ppm from the compound, a
#: 0.7 Da isolation window, four product ions worth the name — as about the
#: compound.
THIN_MARGIN = 10.0


@dataclass(frozen=True)
class Impostor:
    """One neighbour on the mass axis, scored against the same peaks."""

    name: str
    formula: str
    adduct: str
    share: float
    matched: int
    predicted: int
    #: how far the written precursor sits from this candidate through that
    #: adduct — a neighbour is a neighbour *by mass*, and this is the distance
    precursor_ppm: float | None = None
    #: the shorthand species, where the record has one. A cell in a table of
    #: twenty columns does not hold
    #: `TG 17:1(9Z)/18:4(6Z,9Z,12Z,15Z)/18:4(6Z,9Z,12Z,15Z) [iso3]`, and
    #: `TG 39:1 [iso3]` is the same claim in a sixth of the width
    species: str = ""

    @property
    def label(self) -> str:
        """The impostor as the sentence names it: what, and as which ion."""
        return f"{self.name} as {self.adduct}" if self.adduct else self.name

    @property
    def short(self) -> str:
        """The same, narrow enough for a cell."""
        name = self.species or self.name
        return f"{name} as {self.adduct}" if self.adduct else name


@dataclass
class Margin:
    """What the chosen compound explains, against what its rivals explain."""

    compound: str = ""
    #: the chosen compound's share, rescored on the peaks handed over so that
    #: it and every impostor have the same denominator
    share: float = 0.0
    best: Impostor | None = None
    #: every neighbour scored, best first — the table behind the sentence
    others: list[Impostor] = field(default_factory=list)
    #: how many same-formula records were left out, and why there is no
    #: margin where there is none
    same_formula: int = 0
    note: str = ""

    @property
    def scored(self) -> int:
        return len(self.others)

    @property
    def points(self) -> float | None:
        """The margin in points of the spectrum's intensity, or None."""
        if self.best is None:
            return None
        return (self.share - self.best.share) * 100.0

    @property
    def measured(self) -> bool:
        return self.best is not None

    @property
    def thin(self) -> bool:
        """Under `THIN_MARGIN`: the spectrum has not told them apart."""
        points = self.points
        return points is not None and points < THIN_MARGIN

    def sentence(self) -> str:
        """The margin in one sentence, for a basis line or a verdict."""
        share = f"explains {self.share * 100:.1f}%"
        if self.best is None:
            return f"{share}; {self.note or 'no margin was measured'}"
        excluded = (f", {self.same_formula} same-formula isomer(s) left out"
                    if self.same_formula else "")
        thin = (f" — under {THIN_MARGIN:g} points, so this spectrum does not "
                f"tell them apart" if self.thin else "")
        return (f"{share}; the best of {self.scored} neighbour(s){excluded} "
                f"({self.best.label}) explains {self.best.share * 100:.1f}%: "
                f"a margin of {self.points:.1f} points{thin}")

    def column(self) -> str:
        """The same, short enough for a cell."""
        if self.best is None:
            return self.note or "not measured"
        thin = " (thin)" if self.thin else ""
        return f"{self.points:+.1f} pts vs {self.best.short}{thin}"


def cross_validate(peaks_mz, peaks_intensity, chosen: Explanation | None,
                   precursor: float | None, polarity: str = "",
                   database=None, n: int = NEIGHBOURS,
                   tolerance_ppm: float = TOLERANCE_PPM,
                   max_cuts: int = 1, max_losses: int = 2,
                   window: float = PRECURSOR_MATCH_DA,
                   unit: str = "Da") -> Margin:
    """
    The chosen explanation against the `n` nearest impostors, on the same peaks.

    `peaks_mz`/`peaks_intensity` are the spectrum as it was scored — the
    profile or the centroids, whichever the caller explained — and the peaks
    worth explaining are taken from them with `significant_peaks`, the same
    call every other route makes. The chosen explanation is then **rescored**
    on them from the ions it already carries: a share is a fraction of a
    total, and comparing one measured over one peak list against another
    measured over a different one is not a comparison at all. Where it was
    scored on these peaks in the first place — which is the ordinary case —
    the rescoring changes nothing.

    The neighbours are the LIPID MAPS records within `window` of the written
    precursor at every adduct `polarity` allows, gated by `explain.adduct_gate`
    exactly as `explain.rank_candidates` gates them, minus the chosen compound
    and anything carrying its formula. They are taken **nearest first by
    mass** and one per record, so twenty neighbours are twenty compounds and
    not one compound at twenty adducts; each is then explained with the settings handed in here, which are the settings
    the chosen compound was explained with or the margin is measuring the
    settings rather than the spectrum.
    """
    if chosen is None:
        return Margin(note="nothing was explained")
    peaks = significant_peaks(peaks_mz, peaks_intensity)
    mine = _rescored(chosen, peaks, tolerance_ppm)
    result = Margin(compound=chosen.name, share=mine.share)
    if not peaks:
        result.note = "no peak above the noise share to explain"
        return result
    if database is None:
        from . import lipidmaps

        database = lipidmaps.database()
    if database is None:
        result.note = "the LIPID MAPS database is not installed"
        return result
    if not precursor:
        result.note = "no precursor was written, so nothing says which "\
                      "compounds are neighbours"
        return result

    # the same enumeration the chosen compound was given. A formula offers
    # its precursor and a ladder of neutral losses — fifty-odd masses — and
    # a structure with one bond cut offers two thousand; scoring the rivals
    # the other way round measures the length of a list. See `_rival`.
    structural = _structural(chosen)
    near, same = neighbours(database, float(precursor), polarity,
                            formula=chosen.record.formula,
                            lm_id=chosen.record.lm_id, n=n,
                            window=window, unit=unit,
                            by_formula=not structural)
    result.same_formula = same
    for record, form, error in near:
        rival = _rival(record, form, error, peaks, structural, tolerance_ppm,
                       max_cuts, max_losses)
        if rival is None:
            continue
        result.others.append(Impostor(
            name=rival.name or record.species or record.formula,
            formula=record.formula, adduct=form.name,
            share=rival.share, matched=rival.matched,
            predicted=rival.predicted, precursor_ppm=error,
            species=record.abbrev or ""))
    result.others.sort(key=lambda i: (-i.share, -i.matched))
    if result.others:
        result.best = result.others[0]
    elif same:
        result.note = (f"the {same} other record(s) at this precursor carry "
                       f"the same formula, which is the same arithmetic and "
                       f"cannot contrast")
    else:
        result.note = ("no other structure in the database reaches this "
                       "precursor")
    return result


def for_report(report, sticks) -> Margin | None:
    """
    The margin for an infusion report, measured on the spectrum it was
    scored on.

    `sticks` is that spectrum as centroids — `infusion_report._sticks`, the
    same pair the explanation itself was made from — and is passed in rather
    than reached for, so this module still knows nothing about reports beyond
    the three fields it reads. None where nothing was explained, which is the
    ordinary case for a channel that is not the compound its file is named
    after.
    """
    explanation = getattr(report, "explanation", None)
    if explanation is None or sticks is None:
        return None
    return cross_validate(sticks[0], sticks[1], explanation,
                          getattr(report, "written_precursor", None),
                          str(getattr(report, "polarity", "") or ""))


def _rival(record, form, error, peaks, structural: bool,
           tolerance_ppm: float, max_cuts: int,
           max_losses: int) -> Explanation | None:
    """
    One neighbour scored by the same route as the compound it rivals.

    This is the one thing that makes the two shares comparable, and it was
    measured the hard way: scoring a bile acid's formula (56 predicted
    masses) against LIPID MAPS structures with one bond cut (700 to 2,900
    each) had the impostor win on five of the six real infusions, by up to
    33 points. Nothing was wrong with the spectra. A list of two thousand
    masses covers a 60-peak spectrum by accident, which is the whole reason
    a share needs a contrast — and a contrast drawn against a different kind
    of arithmetic is measuring the arithmetic. Enumerated the same way, on
    the same six spectra, the true compound won all six.

    It does not make the contrast fair in the other direction: two structures
    still offer very different numbers of masses — 779 and 4,392 among the
    sphingolipid batch's own candidates — so the impostor's count is carried
    on the row, and a margin lost to a candidate offering five times as many
    masses can be seen for what it is.
    """
    if structural:
        return explain(record, peaks, 1 if form.charge > 0 else -1,
                       tolerance_ppm, max_cuts, max_losses,
                       adduct=form, precursor_ppm=error)
    ions = formula_ions(record.formula, form.name, 0, FORMULA_LOSSES)
    if not ions:
        return None
    return scored(record, None, peaks, ions, tolerance_ppm, form.name, error)


def _rescored(chosen: Explanation, peaks, tolerance_ppm: float) -> Explanation:
    """The chosen explanation on these peaks, from the ions it already has."""
    if not chosen.ions:
        return chosen
    molecule = chosen.record.molecule() if chosen.record is not None else None
    return scored(chosen.record, molecule, peaks, chosen.ions, tolerance_ppm,
                  chosen.adduct, chosen.precursor_ppm)


def neighbours(database, precursor: float, polarity: str = "",
               formula: str = "", lm_id: str = "", n: int = NEIGHBOURS,
               window: float = PRECURSOR_MATCH_DA, unit: str = "Da",
               by_formula: bool = False):
    """
    The `n` records nearest the precursor that are not the compound itself.

    Returns `(records, same_formula)`: a list of `(record, adduct, ppm)`
    nearest first, and how many candidates were dropped for carrying
    `formula`. A record found at two adducts is offered once, at the adduct
    whose mass fits best — two adducts of one compound are two hypotheses
    about the same structure, and a list of ten that holds five compounds is
    not ten neighbours.

    `by_formula` collapses the rivals by composition as well, and is what the
    formula route asks for: with no drawing to cut up, `Wuhanic acid`,
    `FAHFA 12:1/3O(FA 12:0)` and an unnamed third record of `C24H44O4` are one
    arithmetic printed three times, and they came back at 56.5% each on the
    real DCA-d4 infusion. The structure route keeps them, because two isomers
    of one formula do cleave differently.
    """
    from .chemistry import (ADDUCTS_BY_NAME, adducts_of_polarity,
                            mass_error_ppm)

    forms = adducts_of_polarity(polarity or None)
    gate = adduct_gate(precursor)
    signs = {f.polarity for f in forms}
    core = {ADDUCTS_BY_NAME["[M+H]+" if sign > 0 else "[M-H]-"].name
            for sign in signs}
    wanted = _elements(formula)
    same = 0
    best: dict[str, tuple[float, object, object, float | None]] = {}
    for form in forms:
        for record in candidates_for(database, precursor, form.name, window,
                                     unit, limit=n + 8):
            theoretical = form.mz(record.exact_mass)
            distance = abs(float(precursor) - theoretical)
            if form.name not in core and distance > gate:
                continue
            if _elements(record.formula) == wanted:
                same += 1
                continue
            if lm_id and record.lm_id == lm_id:
                same += 1
                continue
            key = (record.formula if by_formula
                   else (record.lm_id or record.species))
            error = (mass_error_ppm(float(precursor), theoretical)
                     if record.exact_mass else None)
            if key not in best or distance < best[key][0]:
                best[key] = (distance, record, form, error)
    ordered = sorted(best.values(), key=lambda entry: entry[0])[:n]
    return [(record, form, error) for _d, record, form, error in ordered], same


def _structural(chosen: Explanation) -> bool:
    """Was this explained from a drawing, or from a formula alone?"""
    record = chosen.record
    return record is not None and record.molecule() is not None


def _elements(formula: str) -> dict:
    """A formula as counted atoms, so `C24H40O5` and `C24H40O5` are one."""
    from .chemistry import FormulaError, parse_formula

    try:
        return dict(parse_formula(formula or ""))
    except (FormulaError, ValueError):
        return {"?": formula}
