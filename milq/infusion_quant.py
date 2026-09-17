"""
Quantitation without a column: an analyte against its deuterated standard in
the same spray.

A direct infusion has no chromatography, so there is no peak to integrate and
nothing to put on a time axis. What there is instead is one averaged spectrum
per acquisition holding both compounds at once, and the number that means
something is the ratio of two heights in it. That is the whole of this module:
pick the ions of each compound out of one spectrum, subtract what each puts
into the other, divide, and hand the result to `calibration.py` as an ordinary
row.

Three bases, because they answer different questions
----------------------------------------------------

`responses` measures the same compound three ways and the caller says which
one the ratio is taken on:

`precursor`
    the intact ion the adduct declares — the single most specific number,
    and the first thing to disappear as the collision energy goes up. On the
    three real CID acquisitions it measures **0, 7 and 124 counts**, which is
    nothing, against 5,235 – 12,271 on the four softer ones.
`fragment`
    the component's written fragment where it has one; failing that, the
    strongest ion *this compound* is predicted to give in *this* spectrum;
    and only with no formula at all, the whole spectrum's base peak, whose
    composition nothing knows. The middle case is not a fixed ion, which is
    a hazard rather than a convenience — see `_flag_moving_fragments`. And a
    fragment is silent altogether when the analyte and its standard
    fragment to the *same* piece: that is refused rather than reported (see
    `Ratio.refused`).
`ladder`
    every rung of the water-loss ladder `explain.precursor_ions` predicts,
    summed. On a bile acid under CID this is where the signal actually is:
    the precursor has gone and the intensity is spread over four or five
    dehydrations, so summing them is both the largest number and the most
    stable one against a change of collision energy — 3,839 – 27,754 counts
    over every one of the seven readable acquisitions.

Every ion is measured with its first two isotope peaks (M, M+1, M+2). The
**response** is the monoisotopic peak alone — that is what a concentration is
proportional to — and the satellites are measured because they are what the
correction below is made of.

The cross-talk, and which direction it goes
-------------------------------------------

A d4 standard sits 4·(D−H) = 4.0251 Da above its unlabelled analyte. The
analyte's own M+4 isotopologue sits 4·(13C−12C) = 4.0134 Da above it. The two
are **0.0117 Da apart** — 27 ppm at m/z 430 — so at a TOF's resolving power
they are separate peaks and at a quadrupole's unit window they are one, and
which of those it is depends entirely on the tolerance the caller asks for.
That is why `contribution` takes a tolerance in ppm and sums whatever falls
inside it rather than assuming a nominal-mass overlap.

The direction matters and only one direction exists. The **analyte is
lighter**, so its isotope envelope climbs into the standard's ions; the
standard's envelope climbs further away and reaches nothing of the analyte's.
`crosstalk` computes both anyway, from `chemistry.isotope_pattern` of each
ion's own residual composition, and prints what it finds — the reverse comes
back as exactly zero, and a zero that was computed is worth more than a zero
that was assumed.

What this arithmetic cannot see is isotopic *impurity*: a bottle of d4
standard holds some d3 and d2, and those land 1.006 and 2.012 Da below the
d4 ion, which is the analyte's side of the spectrum. No formula predicts how
much — it is a property of the bottle, not of the compound — so a d3 shoulder
is measured as analyte and this module says so rather than correcting for a
number nobody measured.

What it is not
--------------

An infusion cannot separate isomers. Deoxycholic and chenodeoxycholic acid
are the same formula, the same precursor and the same ladder; a chromatogram
tells them apart and a spray does not, so a ratio measured here is the ratio
of everything in the vial with that composition. Ion suppression is shared
rather than removed: the analyte and its standard are sprayed together, which
is exactly what makes the ratio worth having, and it also means a matrix that
suppresses one suppresses the other and the pair cannot report that it
happened.

Measured
--------

On the nine ZenoTOF 7600 bile-acid infusions, which hold the **deuterated
standards only** — so what could be measured is the response of a standard
against itself and the size of the cross-talk term, not a real
analyte/standard ratio. That ratio and the calibration over a dilution series
are exercised synthetically in `tests/test_infusion_quant.py`, and the manual
page says so.

The three responses per acquisition are in `infusion-quantitation.md`. Two
findings came out of measuring them.

**The precursor is not a basis.** 0, 7 and 124 counts under CID against
5,235 – 12,271 under EAD, from the same vials. The ladder holds 3,839 –
27,754 throughout, which is why it is the default.

**A product-ion acquisition has no isotope envelope to leak.** This was not
looked for. The predicted M+1 of these ions is 26.4 – 29.6% of the
monoisotopic peak; the measured M+1 is **0.000 – 0.426%**, a transmission of
0.00 – 1.44%, because Q1 selected the monoisotopic precursor and the
satellites never entered the collision cell. So on every acquisition to hand
the cross-talk term is identically zero — not because the arithmetic is
small but because the instrument removed it first — and `ISOTOPES_TRANSMITTED`
is the gate that says so instead of subtracting a leak that was never there.
The correction is for a survey-scan infusion, or for an isolation window wide
enough to pass both compounds.

What the arithmetic gives, as a fraction of the analyte's own monoisotopic
peak, is in `infusion-quantitation.md`: nothing at 10 ppm, 0.018 – 0.073% at
30 ppm and 0.049 – 0.337% over a unit window, and **0.00000% in the reverse
direction at every tolerance**.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .chemistry import (NEUTRON_SPACING, FormulaError, adduct_from_name,
                        adducts_matching, format_formula, identify_adduct,
                        isotope_pattern, parse_formula, split_labels)
from .components import Component
from .quantify import PeakResult, ResultsSet

#: the three things a ratio can be taken on
ON_PRECURSOR = "precursor"
ON_FRAGMENT = "fragment"
ON_LADDER = "ladder"
BASES = (ON_PRECURSOR, ON_FRAGMENT, ON_LADDER)

#: how far a measured centroid may sit from a predicted ion. The default is
#: the one the LIPID MAPS panel offers for a formula of one's own; the real
#: infusions sit +4 to +7 ppm high on their own axis, which is why it is not
#: tighter.
TOLERANCE_PPM = 10.0

#: how much of the isotope envelope is measured per ion. M+2 is the last one
#: worth reading on a molecule this size: C24's M+3 is 0.03% of M.
ENVELOPE_PEAKS = 3

#: how many peaks of the *predicted* envelope are computed when asking what
#: one compound puts into the other's ion. A d4 pair needs M+4 and the fine
#: structure is kept rather than merged (see `LEAK_MERGE_DA`), so this is a
#: count of fine-structure lines and not of nominal steps: cholic acid as
#: [M+NH4]+ has 40 of them at or below M+4.
LEAK_PEAKS = 120

#: abundances below this are not carried into a leak: 1 part in 10^7 of a
#: monoisotopic peak is under one count of anything ever measured here
LEAK_FLOOR = 1e-7

#: how close two isotopologues have to be before the leak arithmetic treats
#: them as one peak. `chemistry.isotope_pattern` defaults to 0.01 Da, which
#: is what a TOF actually records — and it is a hundred times too coarse for
#: *this* question. The whole of the d0/d4 problem is that 13C4 sits
#: 0.0111 Da from the d4 monoisotopic; merged at 0.01 the 13C4, 13C2+18O and
#: 18O2 lines come back as one centroid 0.0131 Da away, and the answer would
#: then depend on a merge nobody asked for rather than on the tolerance the
#: caller set. One millidalton keeps every line that a 10 ppm window can
#: separate at m/z 430 and still collapses nothing a spectrometer could.
LEAK_MERGE_DA = 0.001

#: how much of an ion's predicted M+1 has to be in the spectrum before its
#: isotope envelope is believed to be there at all, as a share of the
#: prediction. Below this the cross-talk correction is reported as zero with
#: its reason rather than applied: a product-ion scan of an isolated
#: precursor has had its satellites removed by Q1, and taking off a leak the
#: instrument already removed would make the answer worse. Measured on the
#: nine ZenoTOF bile-acid infusions — every one a product-ion acquisition —
#: the predicted M+1 is 26.4 to 29.6% of the monoisotopic peak and the
#: measured one is 0.000 to 0.426%, a transmission of 0.00 to 1.44%. Ten per
#: cent sits an order of magnitude above the worst of those and an order
#: below a full-scan spectrum, where the satellite is all there.
ISOTOPES_TRANSMITTED = 0.10

#: what `PeakResult.algorithm` says of a row that came from a spray rather
#: than from a peak
INFUSION = "infusion"


# --------------------------------------------------------------------------- #
# reading one ion out of a spectrum
# --------------------------------------------------------------------------- #
def peak_at(mz, intensity, target: float,
            tolerance_ppm: float = TOLERANCE_PPM):
    """
    What is inside `tolerance_ppm` of `target`: where it is, and how much.

    The position is the **tallest** centroid in the window — that is the
    identification, and `precursor.in_spectrum` answers the same question the
    same way. The intensity is the **sum** of every centroid in it, which is
    not the same thing and is the half that matters here.

    Summing rather than taking the tallest is what keeps the measurement and
    the cross-talk correction describing the same quantity. The correction
    computes how much of one compound's isotope envelope lands inside this
    window and takes it off; if the measurement were the tallest peak alone,
    then on an instrument that happens to resolve the two — a d4 standard's
    fully-dehydrated rung sits 2.9 mDa from the analyte's own M+1 of that
    rung — the interfering ion would never have been counted and subtracting
    it would make the answer worse. On a centroided spectrum whose peaks are
    further apart than the tolerance, which is the ordinary case, the sum and
    the tallest are the same number.

    None when the window holds nothing above zero.
    """
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if mz.size == 0 or mz.size != intensity.size:
        return None
    window = abs(target) * tolerance_ppm * 1e-6
    inside = (mz >= target - window) & (mz <= target + window)
    if not inside.any():
        return None
    heights = intensity[inside]
    total = float(heights.sum())
    if total <= 0.0:
        return None
    return float(mz[inside][int(np.argmax(heights))]), total


@dataclass(frozen=True)
class Envelope:
    """
    One predicted ion as the spectrum has it: M, M+1, M+2.

    `intensities` is one entry per isotope peak asked for, zero where nothing
    was inside the tolerance. `counts` is the ion's own residual composition
    where it is known, which is what makes the cross-talk computable; a
    fragment nobody can write a formula for has None and says so.
    """

    mz: float
    description: str
    intensities: tuple[float, ...] = ()
    found: tuple[float | None, ...] = ()
    counts: dict[str, int] | None = None
    adduct: str = ""
    note: str = ""

    @property
    def response(self) -> float:
        """The monoisotopic peak: what a concentration is proportional to."""
        return float(self.intensities[0]) if self.intensities else 0.0

    @property
    def total(self) -> float:
        """M + M+1 + M+2, as measured."""
        return float(sum(self.intensities))

    @property
    def found_mz(self) -> float | None:
        return self.found[0] if self.found else None

    @property
    def error_ppm(self) -> float | None:
        measured = self.found_mz
        if measured is None or not self.mz:
            return None
        return (measured - self.mz) / self.mz * 1e6

    @property
    def present(self) -> bool:
        return self.response > 0.0

    def satellite_share(self) -> tuple[float, ...]:
        """M+1 and M+2 as a share of M, for printing beside the prediction."""
        base = self.response
        if base <= 0:
            return tuple(0.0 for _ in self.intensities[1:])
        return tuple(float(i) / base for i in self.intensities[1:])


def envelope_at(mz, intensity, target: float, description: str = "",
                counts: dict[str, int] | None = None, adduct: str = "",
                tolerance_ppm: float = TOLERANCE_PPM,
                peaks: int = ENVELOPE_PEAKS) -> Envelope:
    """One ion and its first `peaks - 1` isotope satellites, as measured."""
    heights: list[float] = []
    masses: list[float | None] = []
    for step in range(max(1, peaks)):
        at = target + step * NEUTRON_SPACING
        hit = peak_at(mz, intensity, at, tolerance_ppm)
        heights.append(0.0 if hit is None else hit[1])
        masses.append(None if hit is None else hit[0])
    return Envelope(mz=float(target), description=description,
                    intensities=tuple(heights), found=tuple(masses),
                    counts=dict(counts) if counts else None, adduct=adduct)


# --------------------------------------------------------------------------- #
# which ions a compound is measured on
# --------------------------------------------------------------------------- #
def labels_of(component: Component, name: str = "") -> tuple[str, int]:
    """
    The formula to use and the deuteriums it does not spell out.

    A d4 standard is bought and filed as `CA-d4` and the formula beside it in
    the component table is nearly always the unlabelled one — nothing there
    has a column for four deuteriums. `chemistry.split_labels` reads the
    trailing `-d4`; a formula that already spells its labels is left alone,
    because it has said what it is.

    The formula comes back **as written**, because `explain.precursor_ions`
    does the substitution itself and handing it a labelled formula and a
    label count would count the same four deuteriums twice. Where the
    labelled composition is what is wanted — identifying the adduct from a
    written precursor 4 Da up, for one — `labelled_formula` builds it.
    """
    formula = str(getattr(component, "formula", "") or "")
    if not formula:
        return "", 0
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return formula, 0
    if counts.get("D"):
        return formula, 0
    for written in (name, getattr(component, "name", "")):
        _stem, labels = split_labels(str(written or ""))
        if labels and counts.get("H", 0) >= labels:
            return formula, labels
    return formula, 0


def labelled_formula(formula: str, deuterium: int) -> str:
    """`C24H40O5` and four labels written out as `C24H36D4O5`."""
    if not formula or not deuterium:
        return formula
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return formula
    if counts.get("D") or counts.get("H", 0) < deuterium:
        return formula
    counts["H"] -= deuterium
    counts["D"] = counts.get("D", 0) + deuterium
    return format_formula({k: v for k, v in counts.items() if v})


def adduct_for(component: Component, precursor: float | None = None,
               polarity=None, formula: str = "") -> tuple[str, str]:
    """
    The adduct to read this compound's ions as, and where it came from.

    The component table's own when it agrees with the written precursor,
    because that is what the analyst declared; otherwise the precursor is
    asked, since it is the one number the instrument was given. The same
    order the infusion report uses, kept here so that this module does not
    reach into that one's privates.
    """
    declared = str(getattr(component, "adduct", "") or "")
    formula = formula or str(getattr(component, "formula", "") or "")
    written = precursor if precursor else getattr(component, "precursor", 0.0)
    if written and formula:
        if declared:
            fits = [m for m in adducts_matching(formula, float(written),
                                                polarity)
                    if m.within and m.name == declared]
            if fits:
                return declared, "from the component table"
        choice = identify_adduct(formula, float(written), polarity)
        if choice.adduct is not None:
            if declared and choice.adduct.name != declared:
                return choice.adduct.name, (
                    f"read off the written precursor — {choice.reason}, not "
                    f"the {declared} the component table carries")
            return choice.adduct.name, (
                f"read off the written precursor — {choice.reason}")
        if declared:
            return declared, "from the component table"
        return "", choice.reason
    if declared:
        return declared, "from the component table"
    return "", f"{getattr(component, 'name', 'this component')} carries no adduct"


def _water_ladder(ions) -> list:
    """
    The rungs: the intact ion, the form the fragments carry, and every
    dehydration of it.

    `explain.precursor_ions` offers ammonia and carbon dioxide losses too. A
    ladder that mixed them in would be a different claim — that every one of
    those neutrals actually leaves — so only the ions whose losses are water
    (or nothing at all) are kept, which is the ladder the bile acids show.
    """
    kept = []
    for ion in ions:
        losses = tuple(getattr(ion, "losses", ()) or ())
        if all(loss == "H2O" for loss in losses):
            kept.append(ion)
    return kept


def _ion_counts(ion, adduct) -> dict[str, int] | None:
    """
    The composition whose isotope pattern this ion carries: the residual
    formula plus whatever the adduct added.

    The adduct is part of the ion and part of its envelope — an ammonium's
    nitrogen is 0.36% of M+1 on its own — so leaving it out would understate
    the satellite it predicts.
    """
    try:
        counts = dict(parse_formula(getattr(ion, "formula", "") or ""))
    except (FormulaError, ValueError):
        return None
    if not counts:
        return None
    added = getattr(adduct, "added", "") if adduct is not None else ""
    if added:
        try:
            for element, n in parse_formula(added).items():
                counts[element] = counts.get(element, 0) + n
        except (FormulaError, ValueError):
            pass
    return counts


@dataclass
class IonResponse:
    """One compound measured in one averaged spectrum, three ways."""

    component: str
    formula: str = ""
    adduct: str = ""
    adduct_basis: str = ""
    deuterium: int = 0
    tolerance_ppm: float = TOLERANCE_PPM
    precursor: Envelope | None = None
    fragment: Envelope | None = None
    ladder: list[Envelope] = field(default_factory=list)
    #: how much of this compound's predicted M+1 is actually in the
    #: spectrum, as a share of the prediction. 1.0 is a full-scan spectrum
    #: with its satellites intact; ~0 is a product-ion scan whose precursor
    #: was isolated, and there the cross-talk cannot happen at all. None
    #: when no ion was clean enough to measure it on — see
    #: `transmission_basis`.
    transmission: float | None = None
    transmission_basis: str = ""
    #: why a basis could not be measured, by basis
    notes: dict[str, str] = field(default_factory=dict)
    note: str = ""

    def envelopes(self, on: str) -> list[Envelope]:
        if on == ON_PRECURSOR:
            return [self.precursor] if self.precursor is not None else []
        if on == ON_FRAGMENT:
            return [self.fragment] if self.fragment is not None else []
        if on == ON_LADDER:
            return list(self.ladder)
        raise ValueError(f"{on!r} is not one of {BASES}")

    def response(self, on: str = ON_LADDER) -> float | None:
        """
        The monoisotopic intensity of the chosen basis, summed over its ions.

        None when the basis holds no ion at all — which is not the same as a
        measured zero, and is why this is not `0.0`.
        """
        envelopes = self.envelopes(on)
        if not envelopes:
            return None
        return float(sum(e.response for e in envelopes))

    def rungs_found(self) -> int:
        return sum(1 for e in self.ladder if e.present)

    def describe(self, on: str = ON_LADDER) -> str:
        value = self.response(on)
        if value is None:
            return self.notes.get(on, "not measured")
        if on == ON_LADDER:
            return (f"{value:,.0f} counts over {self.rungs_found()} of "
                    f"{len(self.ladder)} rung(s)")
        return f"{value:,.0f} counts"


def responses(peaks_mz, peaks_intensity, component: Component,
              adduct: str = "", deuterium: int | None = None,
              tolerance_ppm: float = TOLERANCE_PPM,
              polarity=None, precursor: float | None = None) -> IonResponse:
    """
    One compound's three responses in one averaged spectrum.

    `peaks_mz` / `peaks_intensity` are centroids — a profile trace describes
    the instrument's peak shape rather than the compound, and every height
    here is a peak height. `adduct` and `deuterium` may be left out and are
    then read off the component: the adduct from the written precursor, the
    labels from the name's trailing `-d4`.
    """
    from .explain import precursor_ions

    formula, named_labels = labels_of(component)
    if deuterium is None:
        deuterium = named_labels
    out = IonResponse(component=str(getattr(component, "name", "") or ""),
                      formula=formula, deuterium=int(deuterium),
                      tolerance_ppm=float(tolerance_ppm))
    mz = np.asarray(peaks_mz, dtype=float)
    intensity = np.asarray(peaks_intensity, dtype=float)
    if mz.size == 0 or mz.size != intensity.size:
        out.note = "the spectrum is empty"
        for basis in BASES:
            out.notes[basis] = out.note
        return out

    written = precursor if precursor else getattr(component, "precursor", 0.0)
    # the adduct is read off the *labelled* composition: a d4 standard's
    # written precursor is 4.0251 Da above anything the unlabelled formula
    # can be, and asked about the formula as typed no adduct fits at all
    spelt = labelled_formula(formula, int(deuterium))
    if adduct:
        out.adduct, out.adduct_basis = adduct, "as asked for"
    else:
        out.adduct, out.adduct_basis = adduct_for(component, written, polarity,
                                                  spelt)
    chosen = adduct_from_name(out.adduct) if out.adduct else None

    ions = []
    if not formula:
        reason = f"{out.component or 'this component'} carries no formula"
        out.notes[ON_PRECURSOR] = out.notes[ON_LADDER] = reason
    elif chosen is None:
        reason = out.adduct_basis or "no adduct could be identified"
        out.notes[ON_PRECURSOR] = out.notes[ON_LADDER] = reason
    else:
        ions = precursor_ions(formula, chosen, int(deuterium))
        if not ions:
            reason = f"{out.adduct} of {spelt} predicts no ion"
            out.notes[ON_PRECURSOR] = out.notes[ON_LADDER] = reason

    # -- the precursor ------------------------------------------------------ #
    intact = sorted((i for i in ions if not getattr(i, "losses", ())),
                    key=lambda i: -i.mz)
    if intact:
        named = [i for i in intact if getattr(i, "form", "") == chosen.name]
        ion = named[0] if named else intact[0]
        out.precursor = envelope_at(
            mz, intensity, float(ion.mz), description=ion.description,
            counts=_ion_counts(ion, chosen), adduct=out.adduct,
            tolerance_ppm=tolerance_ppm)
        if not out.precursor.present:
            out.notes[ON_PRECURSOR] = (
                f"nothing within {tolerance_ppm:g} ppm of "
                f"{out.precursor.mz:.4f}")

    # -- the ladder --------------------------------------------------------- #
    for ion in sorted(_water_ladder(ions), key=lambda i: -i.mz):
        out.ladder.append(envelope_at(
            mz, intensity, float(ion.mz), description=ion.description,
            counts=_ion_counts(ion, chosen), adduct=out.adduct,
            tolerance_ppm=tolerance_ppm))
    if ions and not out.ladder:
        out.notes[ON_LADDER] = f"{out.adduct} of {spelt} has no water ladder"
    elif out.ladder and not out.rungs_found():
        out.notes[ON_LADDER] = (f"none of the {len(out.ladder)} predicted "
                                f"rungs is in the spectrum")

    _measure_transmission(out)

    # -- the fragment ------------------------------------------------------- #
    # a written fragment first, because it is what the analyst declared; then
    # the strongest ion *this compound* is predicted to give, which is what
    # "base peak" means for one compound in a spectrum holding two; and only
    # with no formula at all, the spectrum's own base peak, whose composition
    # nothing knows and whose cross-talk therefore cannot be computed
    written_fragment = getattr(component, "fragment", None)
    if written_fragment:
        out.fragment = envelope_at(
            mz, intensity, float(written_fragment),
            description=f"fragment {float(written_fragment):g} as written",
            tolerance_ppm=tolerance_ppm)
        for rung in out.ladder:
            window = out.fragment.mz * tolerance_ppm * 1e-6
            if abs(rung.mz - out.fragment.mz) <= window:
                out.fragment = _named(out.fragment, rung)
                break
        if not out.fragment.present:
            out.notes[ON_FRAGMENT] = (
                f"nothing within {tolerance_ppm:g} ppm of "
                f"{float(written_fragment):g}")
    elif out.ladder and out.rungs_found():
        strongest = max(out.ladder, key=lambda e: e.response)
        out.fragment = Envelope(
            mz=strongest.mz,
            description=f"strongest predicted ion — {strongest.description}",
            intensities=strongest.intensities, found=strongest.found,
            counts=strongest.counts, adduct=out.adduct)
        # chosen by height, so it is not necessarily the same ion in the next
        # spectrum, and a curve fitted over a series would then be fitted on
        # a different ion at each level. Measured on a synthetic five-level
        # series: r² 0.89 and accuracies from -199% to +150% where the same
        # series on a written fragment or on the ladder recovers every level
        # exactly. Writing a fragment m/z in the component table fixes it.
        out.notes[ON_FRAGMENT] = (
            f"chosen by height in this spectrum ({strongest.mz:.4f}); write "
            f"a fragment m/z in the component table to hold the basis to one "
            f"ion across a series")
    else:
        top = int(np.argmax(intensity)) if intensity.size else -1
        if top >= 0 and intensity[top] > 0:
            out.fragment = envelope_at(
                mz, intensity, float(mz[top]),
                description="the spectrum's base peak",
                tolerance_ppm=tolerance_ppm,
            )
            out.notes[ON_FRAGMENT] = (
                "no formula and no written fragment, so this is the whole "
                "spectrum's base peak and its composition is unknown")
        else:
            out.notes[ON_FRAGMENT] = "the spectrum has no peak above zero"
    return out


def _measure_transmission(out: "IonResponse") -> None:
    """
    Ask the spectrum whether this compound's isotope envelope is in it.

    A d0 analyte can only put its M+4 into a d4 standard's ion if the
    instrument transmitted that M+4 in the first place, and a product-ion
    scan of an isolated precursor did not: Q1 passed the monoisotopic ion
    and the satellites never entered the collision cell. Measured on the
    seven readable bile-acid infusions, the predicted M+1 is 26.4 – 29.6% of
    the monoisotopic peak and the measured one 0.000 – 0.426%.

    So it is measured rather than assumed, on the strongest ion that has a
    composition and has **no other predicted ion** within a tolerance of its
    own M+1 — a d4 standard's rungs sit 1.006 Da apart and would otherwise
    be read as each other's satellites.
    """
    candidates = []
    seen: set[float] = set()
    for envelope in ([out.precursor] if out.precursor is not None else []) + out.ladder:
        if not envelope.present or not envelope.counts:
            continue
        if round(envelope.mz, 4) in seen:
            continue
        seen.add(round(envelope.mz, 4))
        candidates.append(envelope)
    if not candidates:
        out.transmission_basis = "no ion with a composition was measured"
        return
    for envelope in sorted(candidates, key=lambda e: -e.response):
        up = envelope.mz + NEUTRON_SPACING
        window = up * out.tolerance_ppm * 1e-6
        if any(abs(other.mz - up) <= window for other in candidates
               if other is not envelope):
            continue
        predicted, _step, _gap = contribution(envelope.counts, envelope.mz, up,
                                              out.tolerance_ppm)
        if predicted <= 0:
            continue
        measured = (envelope.intensities[1] / envelope.response
                    if len(envelope.intensities) > 1 and envelope.response
                    else 0.0)
        out.transmission = float(measured / predicted)
        out.transmission_basis = (
            f"{envelope.mz:.4f} predicts an M+1 of {predicted * 100:.2f}% "
            f"and measures {measured * 100:.3f}%")
        return
    out.transmission_basis = (
        "every measured ion has another predicted ion where its M+1 would "
        "be, so the envelope cannot be read")


def _named(envelope: "Envelope", rung: "Envelope") -> "Envelope":
    """A measured fragment given the composition of the rung it turned out
    to be — which is what makes its cross-talk computable rather than
    merely bounded."""
    return Envelope(mz=envelope.mz,
                    description=f"{envelope.description} — {rung.description}",
                    intensities=envelope.intensities, found=envelope.found,
                    counts=rung.counts, adduct=rung.adduct)


# --------------------------------------------------------------------------- #
# what one compound puts into the other's ion
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Leak:
    """One compound's isotope envelope reaching one of the other's ions."""

    source: str
    target: str
    source_mz: float
    target_mz: float
    #: abundance at the target mass relative to the source's own monoisotopic
    fraction: float
    #: the counts that implies, from the source's measured monoisotopic peak
    intensity: float
    #: which satellite of the source lands there — 1 for M+1, 4 for M+4
    step: int = 0
    gap_mda: float = 0.0

    def __str__(self) -> str:
        return (f"{self.source} M+{self.step} at {self.source_mz:.4f} reaches "
                f"{self.target} at {self.target_mz:.4f} "
                f"({self.gap_mda:+.1f} mDa): {self.fraction * 100:.4f}% of "
                f"its own peak, {self.intensity:,.1f} counts")


def contribution(counts: dict[str, int] | None, source_mz: float,
                 target_mz: float, tolerance_ppm: float = TOLERANCE_PPM,
                 peaks: int = LEAK_PEAKS):
    """
    How much of an ion of composition `counts`, sitting at `source_mz`, is
    measured at `target_mz` — as a fraction of its own monoisotopic peak.

    The pattern is computed from the composition and then anchored on the
    measured position rather than on a theoretical one, so the answer does
    not depend on whether the adduct's own mass was accounted for twice. Each
    satellite is placed by its **mass**, not by its nominal step, which is
    the whole point: the d0 analyte's M+4 and the d4 standard's M are
    0.0117 Da apart at m/z 430, so whether they are the same measurement is
    the tolerance's business and nobody else's.
    """
    if not counts:
        return 0.0, 0, 0.0
    pattern = isotope_pattern(counts, None, min_abundance=LEAK_FLOOR,
                              max_peaks=peaks, merge_tolerance=LEAK_MERGE_DA)
    if not pattern:
        return 0.0, 0, 0.0
    base_mass, base_abundance = pattern[0]
    if base_abundance <= 0:
        return 0.0, 0, 0.0
    window = abs(target_mz) * tolerance_ppm * 1e-6
    total, strongest, best_step, best_gap = 0.0, 0.0, 0, 0.0
    for mass, abundance in pattern:
        at = source_mz + (mass - base_mass)
        gap = at - target_mz
        if abs(gap) <= window:
            share = abundance / base_abundance
            if share > strongest:
                # the fine structure is kept, so "which satellite" is the
                # nominal step of the strongest line inside the window and
                # not its position in the list
                strongest = share
                best_step = int(round(mass - base_mass))
                best_gap = gap * 1000.0
            total += share
    return float(total), int(best_step), float(best_gap)


def crosstalk(source: IonResponse, target: IonResponse,
              on: str = ON_LADDER,
              tolerance_ppm: float | None = None) -> list[Leak]:
    """
    Every ion of `source` whose isotope envelope reaches an ion of `target`,
    on this basis.

    Both directions are worth asking even though only one of them can be
    non-zero: the lighter compound climbs into the heavier one's ions and the
    heavier one climbs away from everything. A computed zero is a statement;
    an assumed one is a habit.
    """
    tolerance = (target.tolerance_ppm if tolerance_ppm is None
                 else tolerance_ppm)
    if (source.transmission is not None
            and source.transmission < ISOTOPES_TRANSMITTED):
        # the instrument removed the envelope before it could reach anything.
        # Subtracting a leak that was never transmitted would not be a
        # correction, it would be a second error on top of none.
        return []
    leaks: list[Leak] = []
    for mine in source.envelopes(on):
        if mine.counts is None or mine.response <= 0:
            continue
        for theirs in target.envelopes(on):
            if theirs is None:
                continue
            window = abs(theirs.mz) * tolerance * 1e-6
            if abs(mine.mz - theirs.mz) <= window:
                continue        # the same ion, not a leak into another one
            fraction, step, gap = contribution(mine.counts, mine.mz, theirs.mz,
                                               tolerance)
            if fraction <= 0:
                continue
            leaks.append(Leak(source=source.component, target=target.component,
                              source_mz=mine.mz, target_mz=theirs.mz,
                              fraction=fraction,
                              intensity=fraction * mine.response,
                              step=step, gap_mda=gap))
    return leaks


# --------------------------------------------------------------------------- #
# the ratio
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Ratio:
    """An analyte over its internal standard, and what was taken off first."""

    on: str
    analyte: float | None = None
    standard: float | None = None
    #: counts taken off each, from the other compound's isotope envelope
    into_analyte: float = 0.0
    into_standard: float = 0.0
    leaks: tuple[Leak, ...] = ()
    note: str = ""
    #: the basis could not be used at all — no ion, or an ion the two
    #: compounds share. Kept apart from "the ratio happens to be None" so
    #: that a refusal reads as a refusal and not as a missing measurement.
    refused: bool = False
    #: why the cross-talk correction is what it is — including why it is
    #: zero, which on a product-ion acquisition is the usual answer and is
    #: a measurement rather than an omission
    correction_note: str = ""

    @property
    def corrected_analyte(self) -> float | None:
        if self.analyte is None:
            return None
        return max(0.0, self.analyte - self.into_analyte)

    @property
    def corrected_standard(self) -> float | None:
        if self.standard is None:
            return None
        return max(0.0, self.standard - self.into_standard)

    @property
    def raw(self) -> float | None:
        if not self.analyte or not self.standard:
            return None
        return float(self.analyte / self.standard)

    @property
    def value(self) -> float | None:
        if self.refused:
            return None
        analyte, standard = self.corrected_analyte, self.corrected_standard
        if analyte is None or not standard:
            return None
        return float(analyte / standard)

    @property
    def corrected(self) -> bool:
        return bool(self.into_analyte or self.into_standard)

    @property
    def shift_percent(self) -> float | None:
        """How far the correction moved the ratio, in per cent."""
        raw, value = self.raw, self.value
        if raw in (None, 0.0) or value is None:
            return None
        return (value - raw) / raw * 100.0

    def describe(self) -> str:
        if self.note:
            return self.note
        if self.value is None:
            return "no ratio"
        if not self.corrected:
            return (f"{self.value:.6g} on the {self.on} — "
                    + (self.correction_note or "no correction"))
        shift = self.shift_percent
        return (f"{self.value:.6g} on the {self.on}, from {self.raw:.6g} "
                f"before correction ({shift:+.3f}%): "
                f"{self.into_standard:,.1f} counts taken off the standard "
                f"and {self.into_analyte:,.1f} off the analyte")


def ratio(analyte: IonResponse, standard: IonResponse,
          on: str = ON_LADDER, tolerance_ppm: float | None = None) -> Ratio:
    """
    The analyte over its internal standard on one basis, cross-talk removed.

    A basis on which the two compounds land on the *same* ion is refused
    rather than reported: an unlabelled fragment shared by an analyte and its
    deuterated standard measures their sum, and dividing a sum by part of
    itself is not a ratio. That is the ordinary outcome of quantifying on a
    fragment that has lost every label, and it is why `ladder` is the
    default.
    """
    if on not in BASES:
        raise ValueError(f"{on!r} is not one of {BASES}")
    tolerance = (tolerance_ppm if tolerance_ppm is not None
                 else max(analyte.tolerance_ppm, standard.tolerance_ppm))
    mine, theirs = analyte.envelopes(on), standard.envelopes(on)
    if not mine or not theirs:
        missing = analyte if not mine else standard
        return Ratio(on=on, analyte=analyte.response(on),
                     standard=standard.response(on), refused=True,
                     note=missing.notes.get(on, f"no {on} ion to measure"))

    shared = [(a, b) for a in mine for b in theirs
              if abs(a.mz - b.mz) <= abs(b.mz) * tolerance * 1e-6]
    if shared:
        a, b = shared[0]
        return Ratio(on=on, analyte=analyte.response(on),
                     standard=standard.response(on), refused=True,
                     note=(f"{analyte.component} and {standard.component} "
                           f"share an ion at {a.mz:.4f} within "
                           f"{tolerance:g} ppm — the label is not on this "
                           f"piece, so the two cannot be told apart on the "
                           f"{on}"))

    into_standard = crosstalk(analyte, standard, on, tolerance)
    into_analyte = crosstalk(standard, analyte, on, tolerance)
    return Ratio(on=on, analyte=analyte.response(on),
                 standard=standard.response(on),
                 into_analyte=float(sum(leak.intensity for leak in into_analyte)),
                 into_standard=float(sum(leak.intensity for leak in into_standard)),
                 leaks=tuple(into_standard + into_analyte),
                 correction_note=_correction_note(analyte, standard,
                                                  into_standard, into_analyte))


def _correction_note(analyte: IonResponse, standard: IonResponse,
                     into_standard, into_analyte) -> str:
    """Why the correction is the size it is, zero included."""
    filtered = [r.component for r in (analyte, standard)
                if r.transmission is not None
                and r.transmission < ISOTOPES_TRANSMITTED]
    if filtered:
        basis = analyte if analyte.component in filtered else standard
        return (f"no correction: {', '.join(filtered)} has no isotope "
                f"envelope in this spectrum — {basis.transmission_basis}, a "
                f"transmission of {basis.transmission * 100:.2f}%, so the "
                f"satellites were removed before the collision cell and "
                f"nothing of one compound can reach the other's ions")
    if not into_standard and not into_analyte:
        return ("no isotopologue of either compound lands within the "
                "tolerance of any ion of the other")
    parts = []
    for leaks, into in ((into_standard, standard), (into_analyte, analyte)):
        if leaks:
            parts.append(f"into {into.component}: "
                         + "; ".join(str(leak) for leak in leaks))
    return " · ".join(parts)


# --------------------------------------------------------------------------- #
# a row the rest of the program can read
# --------------------------------------------------------------------------- #
@dataclass
class InfusionResult:
    """
    One analyte in one infusion: the two responses and the ratio between them.

    `to_peak_result` is how this reaches the Results table, the calibration
    and the report. It is a `quantify.PeakResult` with the time fields left
    at zero and `algorithm` set to `infusion`, and it is deliberately not a
    subclass: results are saved as dictionaries and read back through
    `PeakResult.from_dict`, so a subclass would survive one session and not
    the project. The response goes into `area` because that is the field
    every consumer already reads — `PeakResult.response`, `found`,
    `build_calibrations`, the Results table's *Area* column and the export —
    and putting an infusion's counts anywhere else would mean touching all
    of them. `note` says what the number is, so nothing reads it as an
    integrated area by mistake.
    """

    sample_key: str
    sample_name: str
    analyte: str
    standard: str = ""
    on: str = ON_LADDER
    analyte_response: IonResponse | None = None
    standard_response: IonResponse | None = None
    result: Ratio | None = None
    group: str = ""
    channel: str = "—"
    mz: float = 0.0
    actual_concentration: float | None = None

    @property
    def ratio(self) -> float | None:
        return self.result.value if self.result is not None else None

    @property
    def response(self) -> float | None:
        return (self.analyte_response.response(self.on)
                if self.analyte_response is not None else None)

    @property
    def standard_value(self) -> float | None:
        return (self.standard_response.response(self.on)
                if self.standard_response is not None else None)

    @property
    def correction(self) -> float:
        return self.result.into_standard if self.result is not None else 0.0

    @property
    def note(self) -> str:
        bits = [f"infusion, quantified on the {self.on}"]
        result = self.result
        if result is not None and result.note:
            bits.append(result.note)
        elif result is not None and result.corrected:
            shift = result.shift_percent
            moved = "" if shift is None else f" ({shift:+.3f}% on the ratio)"
            bits.append(f"cross-talk {result.into_standard:,.1f} counts off "
                        f"the standard{moved}")
        return "; ".join(bits)

    def to_peak_result(self) -> PeakResult:
        """The row as the Results table and the calibration read it."""
        response = self.response
        standard = self.standard_value
        row = PeakResult(
            sample_key=self.sample_key, sample_name=self.sample_name,
            component=self.analyte, group=self.group, channel=self.channel,
            mz=float(self.mz), rt=0.0, expected_rt=None,
            area=float(response or 0.0), height=float(response or 0.0),
            width=0.0, snr=None, start_rt=0.0, end_rt=0.0,
            algorithm=INFUSION, points=None, note=self.note,
            internal_standard=self.standard,
            is_area=None if standard is None else float(standard),
            is_height=None if standard is None else float(standard),
            area_ratio=self.ratio, height_ratio=self.ratio,
            actual_concentration=self.actual_concentration,
        )
        return row


def results_set(rows) -> ResultsSet:
    """A `ResultsSet` of infusion rows, plus one row per standard.

    The standard gets a row of its own because the Results table shows one
    row per component and a batch whose standards were invisible would look
    as though nothing had been measured in them.
    """
    out = ResultsSet()
    seen: set[tuple[str, str]] = set()
    for row in rows:
        out.results.append(row.to_peak_result())
        seen.add((row.sample_key, row.analyte))
    for row in rows:
        key = (row.sample_key, row.standard)
        if not row.standard or key in seen or row.standard_response is None:
            continue
        seen.add(key)
        value = row.standard_value
        out.results.append(PeakResult(
            sample_key=row.sample_key, sample_name=row.sample_name,
            component=row.standard, channel=row.channel,
            mz=float(row.standard_response.precursor.mz)
            if row.standard_response.precursor is not None else 0.0,
            rt=0.0, expected_rt=None, area=float(value or 0.0),
            height=float(value or 0.0), width=0.0, snr=None,
            algorithm=INFUSION, points=None,
            note=f"infusion, quantified on the {row.on} "
                 f"({row.standard_response.describe(row.on)})"))
    return out


# --------------------------------------------------------------------------- #
# a whole session
# --------------------------------------------------------------------------- #
@dataclass
class InfusionQuantitation:
    """Every analyte/standard pair over every open infusion."""

    rows: list[InfusionResult] = field(default_factory=list)
    on: str = ON_LADDER
    tolerance_ppm: float = TOLERANCE_PPM
    #: samples read but with nothing to quantify in them, and why
    skipped: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""
    seconds: float = 0.0

    def __len__(self) -> int:
        return len(self.rows)

    def results(self) -> ResultsSet:
        return results_set(self.rows)

    def summary(self) -> str:
        if not self.rows:
            return self.note or "nothing to quantify"
        samples = len({r.sample_key for r in self.rows})
        with_ratio = sum(1 for r in self.rows if r.ratio is not None)
        corrected = sum(1 for r in self.rows
                        if r.result is not None and r.result.corrected)
        said = (f"{len(self.rows)} pair(s) over {samples} infusion(s) on the "
                f"{self.on}; {with_ratio} with a ratio")
        if corrected:
            said += f", {corrected} corrected for isotope cross-talk"
        if self.skipped:
            said += f"; {len(self.skipped)} sample(s) skipped"
        return said


def pairs_of(method) -> list[tuple[Component, Component]]:
    """Every analyte of the method that names an internal standard."""
    out = []
    for component in getattr(method, "components", []):
        if getattr(component, "is_internal_standard", False):
            continue
        standard = method.internal_standard_for(component)
        if standard is not None:
            out.append((component, standard))
    return out


def centroids_of(channel, sample=None):
    """
    The channel's run averaged and centroided — the spectrum a response is read
    from.

    Centroids because every height here is a peak height: a profile trace
    hands back the instrument's peak shape, and reading one point of it as a
    response would make the answer depend on the resolving power.

    The scans the spray faltered on are left out, exactly as the Explorer,
    the [[infusion-report]] and a record of one's own leave them out. This
    used to average the whole run instead, so a response measured here and
    the same ion's height on the page beside it came off two different
    spectra: on the three of the nine real bile-acid infusions whose spray
    bursts, by 0.6%, 1.7% and 2.9% of the run's ion current. A ratio of two
    responses is meant to divide that sort of thing out, and it does not
    when the burst is in one vial's run and not the other's.

    `sample` is what says whether the mask applies at all — `mask_for` gates
    on the infusion verdict, since the same arithmetic on a gradient leaves
    out the only scans worth keeping. Without one the whole run is averaged,
    which is what this did before and is still right for a caller that
    cannot say.
    """
    from .infusion import average_stable, mask_for, run_range
    from .processing import centroid_spectrum

    window = run_range(channel)
    if window is None:
        return None
    if sample is None:
        mz, intensity = channel.spectrum_rt_range(*window)
    else:
        mz, intensity = average_stable(channel, mask_for(sample, channel))
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if mz.size == 0:
        return None
    return centroid_spectrum(mz, intensity)


def quantify_infusions(session, on: str = ON_LADDER,
                       tolerance_ppm: float = TOLERANCE_PPM,
                       progress=None) -> InfusionQuantitation:
    """
    Every open infusion, every analyte paired with its internal standard.

    Reads the session and nothing else: the infusions are the ones
    `infusion.verdict_for` calls infusions, the pairing is the component
    table's own IS assignment, and the concentration comes from the sample's
    row in the Samples workspace. Nothing is written anywhere — the caller
    decides what to do with the rows, which is what keeps this testable
    without a window.
    """
    import time

    from .infusion import strongest_channel, verdict_for

    started = time.perf_counter()
    method = getattr(session, "method", None)
    out = InfusionQuantitation(on=on, tolerance_ppm=float(tolerance_ppm))
    if method is None:
        out.note = "the session has no method"
        return out
    pairs = pairs_of(method)
    if not pairs:
        out.note = ("no component of the method names an internal standard "
                    "— set one in the Method workspace")
        return out

    entries = []
    for entry in getattr(session, "entries", []):
        sample = getattr(entry, "sample", None)
        if sample is None:
            continue
        try:
            if not verdict_for(sample):
                continue
        except Exception:
            continue
        entries.append(entry)
    if not entries:
        out.note = ("no open sample reads as a direct infusion — see the "
                    "manual on what makes one")
        return out

    done, total = 0, len(entries)
    for entry in entries:
        channel = strongest_channel(getattr(entry, "sample", None))
        sticks = (centroids_of(channel, getattr(entry, "sample", None))
                  if channel is not None else None)
        done += 1
        if progress is not None and progress(done, total) is False:
            out.note = "stopped"
            break
        if sticks is None:
            out.skipped.append((getattr(entry, "name", ""),
                                "no spectrum could be averaged"))
            continue
        mz, intensity = sticks
        info = getattr(channel, "info", None)
        polarity = str(getattr(info, "polarity", "") or "") or None
        label = str(getattr(info, "label", "") or "—")
        measured: dict[str, IonResponse] = {}

        def measure(component):
            name = str(getattr(component, "name", ""))
            if name not in measured:
                measured[name] = responses(mz, intensity, component,
                                           tolerance_ppm=tolerance_ppm,
                                           polarity=polarity)
            return measured[name]

        for component, standard in pairs:
            mine, theirs = measure(component), measure(standard)
            out.rows.append(InfusionResult(
                sample_key=getattr(entry, "key", ""),
                sample_name=getattr(entry, "name", ""),
                analyte=str(getattr(component, "name", "")),
                standard=str(getattr(standard, "name", "")),
                on=on, analyte_response=mine, standard_response=theirs,
                result=ratio(mine, theirs, on, tolerance_ppm),
                group=str(getattr(component, "group", "") or ""),
                channel=label,
                mz=float(mine.precursor.mz) if mine.precursor is not None
                else float(getattr(component, "precursor", 0.0) or 0.0),
                actual_concentration=getattr(entry, "actual_concentration",
                                             None),
            ))
    _flag_moving_fragments(out)
    out.seconds = time.perf_counter() - started
    return out


def _flag_moving_fragments(out: InfusionQuantitation) -> None:
    """
    Say so where a fragment basis landed on a different ion in different
    samples.

    A basis picked by height is not a fixed ion, and a curve fitted over a
    series of them is fitted on whatever happened to be tallest at each
    level. Nothing is refused — the rows stand and say what they are — but
    the note is on every row of the component it happened to.
    """
    if out.on != ON_FRAGMENT or not out.rows:
        return
    seen: dict[str, set[float]] = {}
    for row in out.rows:
        for name, response in ((row.analyte, row.analyte_response),
                               (row.standard, row.standard_response)):
            if response is None or response.fragment is None:
                continue
            seen.setdefault(name, set()).add(round(response.fragment.mz, 3))
    moved = {name for name, masses in seen.items() if len(masses) > 1}
    for row in out.rows:
        drifted = moved & {row.analyte, row.standard}
        if not drifted:
            continue
        if row.result is not None and not row.result.note:
            row.result = replace(
                row.result,
                note=f"the fragment basis is a different ion in different "
                     f"samples for {', '.join(sorted(drifted))} — write a "
                     f"fragment m/z, or quantify on the ladder")


#: the columns of the ratio table, in the order the panel shows them
QUANT_COLUMNS = ("Sample", "Analyte", "Standard", "Analyte response",
                 "Standard response", "Cross-talk", "Ratio",
                 "Ratio uncorrected", "Concentration", "Note")


def row_cells(row: InfusionResult) -> list[str]:
    """One `InfusionResult` as the panel's cells."""
    result = row.result
    def number(value, form="{:,.0f}"):
        return "—" if value is None else form.format(value)

    return [
        row.sample_name, row.analyte, row.standard or "—",
        number(row.response), number(row.standard_value),
        "—" if result is None or not result.corrected
        else f"{result.into_standard:,.1f}",
        number(row.ratio, "{:.6g}"),
        number(None if result is None else result.raw, "{:.6g}"),
        number(row.actual_concentration, "{:g}"),
        (result.note or result.correction_note if result is not None
         else row.note),
    ]


def write_csv(quantitation: InfusionQuantitation, path) -> str:
    """The ratio table as it stands."""
    import csv
    import os

    path = os.fspath(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(QUANT_COLUMNS)
        for row in quantitation.rows:
            writer.writerow(row_cells(row))
    return path


__all__ = [
    "BASES", "Envelope", "InfusionQuantitation", "InfusionResult",
    "IonResponse", "Leak", "ON_FRAGMENT", "ON_LADDER", "ON_PRECURSOR",
    "QUANT_COLUMNS", "Ratio", "TOLERANCE_PPM", "adduct_for", "centroids_of",
    "contribution", "crosstalk", "envelope_at", "labels_of", "pairs_of",
    "peak_at", "quantify_infusions", "ratio", "responses", "results_set",
    "row_cells", "write_csv",
]
