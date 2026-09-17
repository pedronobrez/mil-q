"""
The isotopic purity of a labelled standard, measured from its own spectrum.

A bottle of cholic acid-d4 comes with a certificate saying `98 atom % D`, and
nobody ever measures it. The number matters: an internal standard that is 4%
d3 puts 4% of its response one dalton below where the method looks for it, and
in a quantitative method that is a systematic bias nothing else in the batch
can see.

What is measured here is the **species distribution** — the fractions d0 … dn
of the standard's own ion population — and the atom fraction is derived from
it (`Purity.atom_percent`), because those are two different numbers and a
certificate quotes the second. A material that is 96% d4 and 4% d3 is
99.0 atom % D.

Why this is a deconvolution and not a ratio
-------------------------------------------

The dn ion and the d(n-1) ion are 1.00628 apart — the mass a deuterium adds
over the hydrogen it replaced. The **13C satellite** of the d(n-1) ion sits
1.00335 above it, which is 2.9 mDa below the dn ion. On the ZenoTOF
acquisitions this was written against the precursor peak is 10.2 mDa wide at
half height (R = 42,000 at m/z 430), so those two are one peak and no
instrument in an ordinary laboratory separates them.

That overlap is the whole problem. Every species' natural-abundance envelope
leaks into the position of the next species up, and on a 24-carbon skeleton
that leak is 27% of whatever the species below holds.

What it does to a reading was measured on exact synthetic envelopes rather
than guessed at, and it is not what one expects. For a d4 material of 95%
purity the peak heights normalised over d0 … dn give d4 = 94.81% where it is
95.00% — nearly right, because the d3 satellite that lands on d4 also inflates
the denominator and the two very nearly cancel. **What does not cancel is the
impurity**, which is the number a purity is actually bought on: d3 against d4
reads 4.44% where it is 4.21%, 5.4% too high, and on a d7 sphingolipid with 45
carbons (M+1 = 50%) it reads 4.63% against 4.21%, 10% too high. The
cancellation is also a coincidence of that particular normalisation and
nothing guarantees it: solving the envelope removes the whole question.

So the envelope is solved rather than read. Each species i contributes its own
natural pattern a0, a1, a2 … (from the formula, through
`chemistry.isotope_pattern`) starting at its own monoisotopic position, and
the measured intensity at nominal position j is

    m[j] = sum over i of  f[i] * a[j - i]

which is a lower-triangular convolution with n+1 unknowns and n+3 equations —
the two positions above the dn ion are what the satellites of dn itself have
to explain. It is solved as a **non-negative** least squares (`_nnls`),
because a negative fraction is not a composition and an unconstrained solve
returns them freely on a noisy envelope.

The check that says the envelope is not one
--------------------------------------------

A product-ion scan is the wrong place to do this and the spectrum says so
itself. The quadrupole isolates the precursor before the collision cell, and
an isolation window narrow enough to pick one species out of the d-ladder has
already removed the 13C satellites the deconvolution needs. The test is free,
because the natural pattern is already in hand: **the dn ion's own M+1
satellite must be there, at roughly the share the formula demands.** Where it
is not, the envelope has been through a mass filter — or the peak is too weak
for its satellite to rise out of the noise — and either way no fraction can be
read from it. `SATELLITE_SHARE` is the threshold and `Purity.usable` is the
answer.

Measured on the nine bile-acid infusions this was written against, all of them
product-ion scans with no survey scan at all:

| infusion | CE | M+1 measured | formula says | ratio |
|---|---|---|---|---|
| CA-d4 EAD | 12 eV | 0.006% | 26.6% | 0.00023 |
| CA-d4 EAD | 22 eV | 0.028% | 26.6% | 0.00104 |
| CA-d4 CID | 45 eV | 0.095% | 26.6% | 0.00357 |
| DCA-d4 EAD | 22 eV | 0.015% | 26.5% | 0.00058 |
| DCA-d4 CID | 40 eV | 0.150% | 26.5% | 0.00566 |
| TDCA-d4 EAD | 22 eV | 0.020% | 30.0% | 0.00065 |
| TDCA-d4 CID | 30 eV | 0.206% | 30.0% | 0.00687 |

Three orders of magnitude, on every file, in both activation modes. Not one of
these acquisitions can be asked what the purity is, and the module says so
rather than returning the number the peak heights would give.

That the satellite is missing also settles what is left. Transmission at
+1.003 Da is 0.00023 of transmission at the precursor on the 12 eV cholic
acid-d4 file; a quadrupole window symmetric about its centre would pass the
d3 rung at -1.006 Da at about the same share, and the 0.763% actually measured
there would then imply a d3 fraction of 3,300%. So either the isolation window
is asymmetric by three orders of magnitude — in which case the rungs below dn
are scaled by a transmission nobody knows — or what sits at that position is
not d3. Both readings end the measurement.

And the residue at the d(n-1) position **moves with the collision energy**: on
cholic acid-d4 it is 0.763% of the precursor at 12 eV, 0.328% at 22 eV and
0.067% at 45 eV, so the purity the envelope would give is 98.32%, 98.77% and
98.98% on three acquisitions of the same bottle. An isotopic composition
cannot depend on how hard the ion was hit. What is at that position is a
fragmentation channel — a hydrogen atom lost from the ammoniated molecule,
which EAD makes freely, and 1.5 mDa from where d3 would be — and the energy
dependence is what says so, since the two masses are far too close to be told
apart on a peak of a few hundred counts.

One thing the check does not catch: a material carrying **more** labels than
it was declared with. A d5 species sits exactly on dn's own M+1 satellite,
lifts the ratio above 1 rather than below the threshold, and is read as carbon
rather than as deuterium. `n_labels` has to be what the vendor made.

The ladder, and why it is a lower bound
---------------------------------------

Where the precursor did not survive its collision energy at all, the same
arithmetic can be run on the base peak of the water-loss ladder
(`[M+H-3H2O]+` and its -1D rung). It answers a different question and
`Purity.lower_bound` says so on the row: a dehydration can leave with a label
(`explain.LOSS_TAKES`), so a d4 molecule that lost a labelled hydroxyl
hydrogen arrives at the d3 position of the ladder and is counted as an
impurity that was never in the bottle.

How much that costs was measured on the same files, again with the check
switched off: on the ladder the d4 fraction comes out 36.7% (CA-d4, 12 eV),
90.1% (22 eV) and 85.0% (45 eV) — against 98.3 - 99.0% from the precursor of
the very same acquisitions — with DCA-d4 at 63.8% and 86.0% and TDCA-d4 at
79.1% and 87.7%. Up to a fifth of the fully-labelled molecules leave a label
behind with the water. The ladder can therefore only put a floor under the
purity, never measure it — and on these files it cannot do even that, because
the fragments inherit the mass filter that made them: the ladder rung's own
M+1 satellite is 0.015 - 0.63% where the formula says 26 - 30%.

Where this can be measured, then: an MS1 survey scan, or a full-scan infusion
with no quadrupole isolation in front of it. That is what the check is for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .chemistry import (NEUTRON_SPACING, Adduct, FormulaError, adduct_from_name,
                        format_formula, isotope_pattern, monoisotopic_mass,
                        parse_formula)
from .explain import D_MINUS_H

#: half-window each side of a rung, as a share of its mass. It has to hold the
#: whole profile peak and nothing of the next rung: measured on the ZenoTOF
#: infusions the precursor peak is 0.033 Da wide at 1% of its height (38 ppm
#: each side at m/z 430) and the rungs are 1.006 Da apart, so 60 ppm holds all
#: of one and none of the other. Measured on two of them: a half-window of
#: 0.020 Da takes 99.8 - 99.9% of the area a window six times wider takes, and
#: one of 0.010 Da takes 84 - 92% — which would be a purity that depended on
#: the resolving power.
TOLERANCE_PPM = 60.0

#: how much of the formula's own M+1 the dn ion has to actually show before
#: the envelope is treated as an isotope envelope. Below this the peak has
#: been through a mass filter, or is too weak for its satellite to be
#: measured, and no species fraction can be read from it. A quarter is a long
#: way under anything an unfiltered spectrum gives and two orders of magnitude
#: over what the nine product-ion infusions gave (0.0002 - 0.007); see the
#: module docstring for the table it was chosen from.
SATELLITE_SHARE = 0.25

#: the dn peak has to be at least this many times the floor to be measured at
#: all. Three, because the floor is itself the largest thing the spectrum
#: shows where nothing should be, and a rung level with it is not a peak.
MIN_OVER_FLOOR = 3.0

#: how many natural-abundance satellites of each species are modelled. Two is
#: enough: M+3 is under 2.1% of M for every formula here, and a third column
#: buys nothing the noise does not swamp.
SATELLITES = 2

#: where the envelope was read
PRECURSOR = "precursor"
LADDER = "ladder"


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Purity:
    """
    The species distribution of a labelled standard, and what it cost to say.

    `fractions` are d0 … dn and sum to 1 when `usable`; `purity` is the last
    of them and `at_least` the last two together, which is the pair a
    certificate quotes. `uncertainty` is on `purity`, from the floor. When
    `usable` is False everything measured is still on the object — the
    envelope is the evidence for the refusal — and `reason` says why no
    fraction was read from it.
    """

    formula: str = ""
    adduct: str = ""
    labels: int = 0
    #: the m/z of the fully-labelled ion the envelope was read from
    at: float = 0.0
    #: `PRECURSOR` or `LADDER`
    where: str = PRECURSOR
    #: the ion in words: `[M+NH4]+`, `[M+H]+ -3H2O`
    ion: str = ""
    #: the m/z each rung was measured at, d0 first, then the satellites above dn
    positions: tuple[float, ...] = ()
    #: the intensity summed over each rung's window, in the same order
    measured: tuple[float, ...] = ()
    #: the natural-abundance pattern of one species, its monoisotopic peak 1.0
    natural: tuple[float, ...] = ()
    #: d0 … dn, summing to 1
    fractions: tuple[float, ...] = ()
    purity: float | None = None
    at_least: float | None = None
    uncertainty: float | None = None
    floor: float = 0.0
    #: a ladder measurement can only put a floor under the purity
    lower_bound: bool = False
    usable: bool = False
    reason: str = ""

    # -- derived ------------------------------------------------------------- #
    @property
    def atom_percent(self) -> float | None:
        """
        The atom fraction of deuterium over the labelled positions, as a
        percentage — the number a certificate quotes.

        It is not the purity and it is always the larger of the two: a
        material that is 96% d4 and 4% d3 is 99.0 atom % D, because the
        3 of 4 the impurity does carry count.
        """
        if not self.usable or not self.fractions or self.labels <= 0:
            return None
        kept = sum(i * f for i, f in enumerate(self.fractions))
        return kept / self.labels * 100.0

    @property
    def satellite_ratio(self) -> float | None:
        """
        The dn ion's measured M+1 over the M+1 its formula demands.

        1.0 is an envelope the instrument left alone; the nine product-ion
        infusions measured 0.0002 to 0.007. This is what `usable` is decided
        on, and it is on the object so that a refusal can be checked rather
        than believed.
        """
        if len(self.measured) < self.labels + 2 or len(self.natural) < 2:
            return None
        top = self.measured[self.labels]
        if top <= 0 or self.natural[1] <= 0:
            return None
        return (self.measured[self.labels + 1] / top) / self.natural[1]

    def label(self) -> str:
        """`d4 96.2%, ≥d3 99.1%` — the pair, with nothing around it."""
        if not self.usable or self.purity is None:
            return ""
        n = self.labels
        head = f"d{n} {self.purity * 100:.1f}%"
        if n >= 1 and self.at_least is not None:
            head += f", ≥d{n - 1} {self.at_least * 100:.1f}%"
        return head

    def line(self) -> str:
        """
        The one line the Explain tab shows:

            Isotopic purity: d4 96.2%, ≥d3 99.1% (from the precursor at
            430.35; ±0.8%)

        and, where nothing could be read, the reason in the same place — a
        blank line where a measurement failed is the one outcome that cannot
        be reviewed.
        """
        if not self.usable:
            return f"Isotopic purity: not measured — {self.reason}."
        where = ("the precursor" if self.where == PRECURSOR
                 else f"the ladder rung {self.ion}")
        error = ("" if self.uncertainty is None
                 else f"; ±{self.uncertainty * 100:.1f}%")
        bound = ", a lower bound" if self.lower_bound else ""
        return (f"Isotopic purity: {self.label()} (from {where} at "
                f"{self.at:.2f}{error}{bound})")

    def field(self) -> str:
        """
        The one line a library record's `Isotopic_purity` field holds, or
        empty where nothing was measured.

        Empty rather than a reason, because a record is searched and compared
        and a field saying "not measured" would be matched, sorted and read
        as a value. The reason belongs on a page, not in a database.
        """
        if not self.usable or self.purity is None:
            return ""
        atom = self.atom_percent
        tail = f"; {atom:.2f} atom % D" if atom is not None else ""
        where = (f"the precursor at {self.at:.4f}" if self.where == PRECURSOR
                 else f"{self.ion} at {self.at:.4f}, a lower bound")
        return f"{self.label()}{tail} (from {where})"

    def sentences(self) -> list[str]:
        """What was measured, one sentence per statement, for a report."""
        if not self.usable:
            return [f"Isotopic purity was not measured: {self.reason}."]
        n = self.labels
        said = [
            f"The ion population is {self.purity * 100:.1f}% d{n}"
            + (f" and {self.at_least * 100:.1f}% d{n - 1} or better"
               if n >= 1 and self.at_least is not None else "")
            + f", solved from the envelope at {self.at:.4f} as {self.ion}"
            + ("" if self.uncertainty is None
               else f", ±{self.uncertainty * 100:.1f}% on the floor of "
                    f"{self.floor:,.0f} counts")
            + "."]
        atom = self.atom_percent
        if atom is not None:
            said.append(
                f"That is {atom:.2f} atom % D over the {n} labelled "
                f"positions, which is the quantity a certificate states and "
                f"is not the same number as the d{n} fraction above it.")
        if self.lower_bound:
            said.append(
                "This was read from a fragment and is a lower bound on the "
                "purity, not a measurement of it: a dehydration can leave "
                "with a label, so a fully labelled molecule that shed a "
                "labelled hydroxyl hydrogen arrives at the d"
                f"{n - 1} position and is counted here as an impurity that "
                "was never in the bottle.")
        return said


# --------------------------------------------------------------------------- #
# the arithmetic
# --------------------------------------------------------------------------- #
def _nnls(A: np.ndarray, b: np.ndarray, max_iter: int = 0) -> np.ndarray:
    """
    Lawson-Hanson non-negative least squares: the x >= 0 minimising |Ax - b|.

    Written out because this program has no scipy and the problem is tiny —
    five unknowns and seven equations for a d4 standard.

    The constraint is what a composition means, and it does not bind on a
    clean envelope: over 900 synthetic solves at noise from 0.05% to 2% of the
    base peak the unconstrained answer never went negative once, because every
    rung's residual after the subtraction is still positive. What makes it
    bind is an **unrelated ion in one of the windows**. A neighbour on the d0
    rung at 0.5% of the base peak puts the unconstrained d1 at -0.125%, and at
    5% at -1.21%; the same interference on d1 takes d2 to -0.24%. Those are
    the fractions a report would print.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float)
    n = A.shape[1]
    max_iter = max_iter or 3 * n
    passive = np.zeros(n, dtype=bool)
    x = np.zeros(n)
    scale = float(np.abs(A).max() * np.abs(b).max()) or 1.0
    tolerance = 1e-10 * scale
    for _outer in range(max_iter):
        gradient = A.T @ (b - A @ x)
        free = ~passive
        if not free.any() or gradient[free].max() <= tolerance:
            break
        passive[np.flatnonzero(free)[int(np.argmax(gradient[free]))]] = True
        for _inner in range(max_iter):
            trial = np.zeros(n)
            trial[passive] = np.linalg.lstsq(A[:, passive], b, rcond=None)[0]
            if trial[passive].min() > 0:
                x = trial
                break
            blocked = passive & (trial <= 0)
            step = float(np.min(x[blocked] / (x[blocked] - trial[blocked])))
            x = x + step * (trial - x)
            passive &= x > 0
            if not passive.any():
                break
        else:
            break
    return x


def _design(natural: np.ndarray, labels: int, rows: int) -> np.ndarray:
    """
    The convolution matrix: column i is species i's own pattern, shifted i up.

    This is the overlap written down. Column 3 of a d4 problem has the d3
    species' monoisotopic peak in row 3 and its 13C satellite in row 4 — the
    same row the d4 species' own monoisotopic peak is in, because the two are
    2.9 mDa apart and the instrument draws one peak.
    """
    A = np.zeros((rows, labels + 1))
    for i in range(labels + 1):
        for k, abundance in enumerate(natural):
            if i + k < rows:
                A[i + k, i] = abundance
    return A


def _rung_mz(top: float, labels: int, index: int) -> float:
    """
    Where rung `index` sits, counting d0 as 0 and dn as `labels`.

    Below dn the spacing is the label's own, 1.00628; above it the rungs are
    dn's natural satellites and the spacing is a neutron's, 1.00335. Using one
    spacing for both would put the second satellite 6 mDa out, which is half a
    peak width.
    """
    if index <= labels:
        return top - (labels - index) * D_MINUS_H
    return top + (index - labels) * NEUTRON_SPACING


def _band(mz: np.ndarray, intensity: np.ndarray, centre: float,
          half: float) -> float:
    inside = (mz >= centre - half) & (mz <= centre + half)
    return float(intensity[inside].sum()) if inside.any() else 0.0


def _floor_from(mz: np.ndarray, intensity: np.ndarray,
                positions, half: float) -> float:
    """
    The largest thing the spectrum shows where nothing should be.

    Half way between two rungs there is no ion of this compound, so whatever
    that window holds is the level a rung has to clear to be a measurement.
    The largest of them rather than the median: a floor is what the worst
    empty window says, and a median would let one rung sitting on a
    co-infused neighbour pass as a species.
    """
    if len(positions) < 2:
        return 0.0
    gaps = [_band(mz, intensity, (a + b) / 2.0, half)
            for a, b in zip(positions, positions[1:])]
    return max(gaps) if gaps else 0.0


def _labelled_counts(formula: str, n_labels: int) -> dict[str, int]:
    """The composition with the unplaced labels folded in, as `explain` does."""
    counts = dict(parse_formula(formula))
    if n_labels:
        counts["D"] = counts.get("D", 0) + n_labels
        counts["H"] = counts.get("H", 0) - n_labels
        if counts["H"] < 0:
            raise FormulaError(
                f"{formula} has fewer than {n_labels} hydrogens to label")
        counts = {element: n for element, n in counts.items() if n > 0}
    return counts


# --------------------------------------------------------------------------- #
def isotopic_purity(mz, intensity, formula: str, adduct, n_labels: int = 0,
                    tolerance_ppm: float = TOLERANCE_PPM,
                    floor: float | None = None,
                    where: str = PRECURSOR, ion: str = "",
                    lower_bound: bool = False) -> Purity:
    """
    The species distribution d0 … dn of a labelled standard, from one spectrum.

    `formula` is the neutral composition of the fully-labelled molecule, with
    the labels spelt out (`C24H36D4O5`) or declared through `n_labels` the way
    `explain.precursor_ions` takes them; `adduct` is the ion it was measured
    as, by name or as an `Adduct`. `floor` is the counts below which a rung is
    not a measurement, and is worked out from the spectrum's own empty windows
    when it is not given.

    The envelope is read at n+3 positions — d0 up to dn, then dn's own two
    natural satellites — and solved as a non-negative least squares against
    the pattern each species carries. **Each species' M+1 lands on the next
    species' monoisotopic position**, 2.9 mDa away and inside one peak width,
    which is why this is a solve and not a set of ratios; the module docstring
    has the arithmetic and what it was measured against.

    A `Purity` always comes back. `usable` says whether a fraction could be
    read, and where it could not the envelope is still on the object with the
    reason beside it.
    """
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if isinstance(adduct, str):
        adduct = adduct_from_name(adduct)
    if not isinstance(adduct, Adduct):
        return Purity(formula=formula, labels=int(n_labels), where=where,
                      ion=ion, lower_bound=lower_bound,
                      reason="that is not an adduct this program knows")
    try:
        counts = _labelled_counts(formula, int(n_labels))
    except (FormulaError, ValueError) as exc:
        return Purity(formula=formula, adduct=adduct.name, where=where,
                      ion=ion, lower_bound=lower_bound, reason=str(exc))
    labels = counts.get("D", 0)
    written = format_formula(counts)
    ion = ion or adduct.name
    top_mz = adduct.mz(monoisotopic_mass(counts))
    blank = Purity(formula=written, adduct=adduct.name, labels=labels,
                   at=top_mz, where=where, ion=ion, lower_bound=lower_bound)
    if labels <= 0:
        return _refuse(blank, "the compound carries no labels to count")
    if mz.size == 0 or mz.size != intensity.size:
        return _refuse(blank, "the spectrum is empty")

    half = top_mz * tolerance_ppm * 1e-6
    rows = labels + 1 + SATELLITES
    positions = tuple(_rung_mz(top_mz, labels, i) for i in range(rows))
    measured = tuple(_band(mz, intensity, p, half) for p in positions)
    pattern = isotope_pattern(counts, adduct, min_abundance=1e-4,
                              max_peaks=SATELLITES + 1)
    natural = _normalised(pattern, SATELLITES + 1)
    if floor is None:
        floor = _floor_from(mz, intensity, positions, half)
    floor = float(floor)
    blank = Purity(formula=written, adduct=adduct.name, labels=labels,
                   at=top_mz, where=where, ion=ion, positions=positions,
                   measured=measured, natural=natural, floor=floor,
                   lower_bound=lower_bound)

    top = measured[labels]
    if top <= 0 or top <= floor * MIN_OVER_FLOOR:
        return _refuse(
            blank,
            f"the d{labels} ion at {top_mz:.4f} is {top:,.0f} counts against a "
            f"floor of {floor:,.0f} — there is no envelope to solve")

    expected = natural[1] if len(natural) > 1 else 0.0
    got = measured[labels + 1] / top if len(measured) > labels + 1 else 0.0
    if expected > 0 and got < expected * SATELLITE_SHARE:
        return _refuse(
            blank,
            f"the d{labels} ion's own M+1 satellite is {got * 100:.3f}% of it "
            f"where the formula says {expected * 100:.1f}% — the envelope has "
            f"been through the quadrupole's isolation window, or is too weak "
            f"for its satellite to rise out of the noise, and no species "
            f"fraction can be read from what is left")

    fractions = _solve(measured, natural, labels, 0.0)
    total = float(sum(fractions))
    if total <= 0:
        return _refuse(blank, "the envelope solves to nothing")
    fractions = tuple(f / total for f in fractions)
    low = _fraction_at(measured, natural, labels, -floor)
    high = _fraction_at(measured, natural, labels, +floor)
    uncertainty = abs(high - low) / 2.0
    at_least = (fractions[labels] + fractions[labels - 1]
                if labels >= 1 else fractions[labels])
    return Purity(
        formula=written, adduct=adduct.name, labels=labels, at=top_mz,
        where=where, ion=ion, positions=positions, measured=measured,
        natural=natural, fractions=fractions, purity=fractions[labels],
        at_least=min(1.0, at_least), uncertainty=uncertainty, floor=floor,
        lower_bound=lower_bound, usable=True,
        reason=(f"solved from {len(measured)} rungs at "
                f"{tolerance_ppm:g} ppm over a floor of {floor:,.0f} counts"))


def _refuse(blank: Purity, reason: str) -> Purity:
    from dataclasses import replace

    return replace(blank, usable=False, reason=reason)


def _normalised(pattern, most: int) -> tuple[float, ...]:
    """The isotope pattern as abundances relative to its monoisotopic peak."""
    if not pattern:
        return (1.0,)
    base = pattern[0][1] or 1.0
    out = [abundance / base for _mz, abundance in pattern[:most]]
    while len(out) < most:
        out.append(0.0)
    return tuple(out)


def _solve(measured, natural, labels: int, shift: float) -> tuple[float, ...]:
    """
    The species fractions the envelope implies, `shift` counts of floor moved
    from the fully-labelled rung onto the ones below it.

    `shift` is how the uncertainty is taken: a floor's worth of intensity is
    the most that could be sitting on the wrong rung, so moving it from dn
    onto every rung below — and then the other way — brackets what the floor
    can do to the answer. It is the pessimistic direction on purpose; the
    floor is already the largest empty window in the envelope.
    """
    b = np.asarray(measured, dtype=float).copy()
    if shift:
        b[labels] = max(0.0, b[labels] + shift)
        for i in range(labels):
            b[i] = max(0.0, b[i] - shift)
    A = _design(np.asarray(natural, dtype=float), labels, len(b))
    return tuple(float(v) for v in _nnls(A, b))


def _fraction_at(measured, natural, labels: int, shift: float) -> float:
    fractions = _solve(measured, natural, labels, shift)
    total = float(sum(fractions))
    return fractions[labels] / total if total > 0 else 0.0


# --------------------------------------------------------------------------- #
# from a spectrum, without being told where to look
# --------------------------------------------------------------------------- #
@dataclass
class PurityAttempt:
    """Both readings, where both were possible, and which one to print."""

    precursor: Purity | None = None
    ladder: Purity | None = None
    tried: list[str] = field(default_factory=list)

    @property
    def best(self) -> Purity | None:
        """The precursor's reading when it stands, else the ladder's."""
        if self.precursor is not None and self.precursor.usable:
            return self.precursor
        if self.ladder is not None and self.ladder.usable:
            return self.ladder
        return self.precursor or self.ladder


def ladder_rungs(formula: str, adduct, n_labels: int = 0,
                 max_losses: int = 3):
    """
    The fully-labelled rungs of the water-loss ladder, strongest route first.

    Only the ions that kept every label: the envelope is read downwards from
    the fully-labelled species, so a rung that has already lost one is not the
    top of anything.
    """
    from .explain import precursor_ions

    ions = precursor_ions(formula, adduct, n_labels, max_losses)
    labels = max((getattr(i, "labels", 0) for i in ions), default=0)
    return [ion for ion in ions
            if ion.losses and getattr(ion, "labels", 0) == labels]


def purity_from_spectrum(mz, intensity, formula: str, adduct,
                         n_labels: int = 0,
                         tolerance_ppm: float = TOLERANCE_PPM,
                         floor: float | None = None) -> PurityAttempt:
    """
    Read the purity off the intact precursor, and off the ladder when it must.

    The precursor first, always: it is the only ion whose d-envelope is the
    bottle's own. Where the precursor did not survive its collision energy the
    strongest fully-labelled rung of the water-loss ladder is tried instead
    and comes back flagged `lower_bound` — see the module docstring for why
    that is a floor under the purity and not a measurement of it.
    """
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    attempt = PurityAttempt()
    attempt.precursor = isotopic_purity(
        mz, intensity, formula, adduct, n_labels,
        tolerance_ppm=tolerance_ppm, floor=floor, where=PRECURSOR)
    attempt.tried.append(PRECURSOR)
    if attempt.precursor.usable:
        return attempt

    best, best_height = None, 0.0
    for ion in ladder_rungs(formula, adduct, n_labels):
        half = ion.mz * tolerance_ppm * 1e-6
        height = _band(mz, intensity, ion.mz, half)
        if height > best_height:
            best, best_height = ion, height
    if best is None:
        return attempt
    attempt.ladder = isotopic_purity(
        mz, intensity, best.fragment.formula, _carrier(best, adduct),
        0, tolerance_ppm=tolerance_ppm, floor=floor,
        where=LADDER, ion=best.description, lower_bound=True)
    attempt.tried.append(LADDER)
    return attempt


def _carrier(ion, adduct) -> "Adduct | str":
    """The adduct a ladder rung is actually carrying, not the precursor's."""
    from .chemistry import core_adduct

    if isinstance(adduct, str):
        adduct = adduct_from_name(adduct)
    if adduct is None:
        return "[M+H]+"
    return core_adduct(adduct)
