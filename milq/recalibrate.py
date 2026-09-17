"""
Mass recalibration from the internal standards.

`mass_drift` asks whether the axis moved during the run and answers against
the batch's own median, which is the only reference a run can supply for
itself. This module asks the other half of the question — *is the axis in the
right place at all* — and that needs a reference the run cannot supply: a
theoretical mass.

So a lock mass here is an internal standard that carries a **formula and an
adduct**. The written precursor is deliberately refused: `647.5` typed into a
method is good to about 800 ppm at that mass and correcting towards it would
recalibrate the instrument onto somebody's rounding.
`Component.precursor_from_formula` — the monoisotopic mass of the formula
through the adduct, which is what `MassTrend.exact` carries — is the only
number worth correcting towards.

And a lock mass has to be near that number. `mass_drift`'s `same_ion` asks
whether the injections agree with *each other*; it cannot ask whether they
agree with the compound, so a standard whose search window holds the same
wrong ion in every injection passes it. `MAX_LOCK_ERROR_PPM` is the other
half of that test — see the histogram against the constant, and
`lock_mass_refusal`.

What is fitted, per injection:

* an **offset** in ppm, the median of the lock masses' errors, sign flipped;
* a **linear term** in ppm per dalton, and only where `MIN_SLOPE_LOCK_MASSES`
  lock masses spread over `MIN_MASS_SPAN` daltons justify one *and* it is
  measured to help. A line through the points it is then scored on is exact
  and says nothing — the same trap `processing.fit_gaussian` fell into — so
  the slope is kept only when **leave-one-out** prediction of a held-out lock
  mass beats the plain offset's. That is also why the floor is four lock
  masses rather than three: hold one of three out and the line is fitted
  through two points, which is exact again.

Nothing is refitted from corrected data and nothing rewrites a file. The
correction is a function of m/z (`MassCorrection.apply`), and where it
reaches quantitation it moves the **extraction window**, not the instrument's
arithmetic: `quantify.extract_xic` asks the reader for a window shifted by
`MassCorrection.undo` and the vendor sums exactly the points it would have
summed for that window. See CLAUDE.md on never substituting our arithmetic
for the instrument's.

## What the real batch says

Measured on the 26-injection sphingolipid batch this was written against
(TripleTOF 5600, one 50–700 TOF MS survey, one scan every 14.6 s):

* **The method carried no formula at all**, so this was dormant until
  `components.fill_formulas` — Method workspace ▸ *Fill formulas from names*
  — read the lipid shorthand in the names: **125 of 141 components and 10 of
  11 internal standards**, each kept only where its mass agreed with the
  precursor the method already carried. The 16 refusals are all the written
  precursor being wrong rather than the name, `dHCer(d18:0/12:0)` at
  484.465 against its formula's 484.4724 among them.
* **A formula was the missing half of the question and is not the binding
  one.** Of the 60 components that then carry a formula *and* lie inside the
  50–700 survey, exactly **one** measures the same ion in injection after
  injection: `SM(d18:1/12:0)`, C35H71N2O6P, [M+H]+ = 647.5123. `mass_drift`
  puts the other ten standards between 98 and 534 ppm of spread, which fails
  `same_ion`, one has no survey covering it, and `C17:0_Ceramide` was found
  in five injections with a median 237 ppm from its own formula — a
  different ion, not a badly measured one. So the fit is **one lock mass,
  offset only, in 25 of 26 injections**, every row says so, and several lock
  masses are not available on this batch at any formula coverage.
* **The formula gate names five of them and costs the fit nothing.**
  `MAX_LOCK_ERROR_PPM` refuses a standard measured past 50 ppm from its own
  formula in most of its injections: `Sphingosine C17:0` (383 ppm),
  `C17:0_Ceramide` (237), `C12:0 _Ceramide` (204), `Cer1P (12:0)` (91) and
  `Sphingosine-1-P C17:0` (82, its injections straddling the formula from
  either side). All five had already failed `same_ion` or the injection
  count, so `SM(d18:1/12:0)`'s figures below are unchanged to the last
  decimal and not one injection lost a point — measured both ways. The gate
  is a guard rather than a finding **on this batch**, and the near miss says
  why it is worth having: `Sphingosine C14:0` holds its measurement to
  52 ppm across 25 injections — twice the `same_ion` limit and no more — at
  a median 156 ppm from its formula. That is one ion, measured steadily,
  and it is not the compound. Nothing but the formula can say so.
* Those offsets: median **+4.8 ppm**, from −4.4 to +11.7, a spread of
  16.1 ppm — which is the same 16 ppm this batch's one standard scatters by
  between injections. **The correction is the size of its own uncertainty.**
  The lock mass's residual goes from a median −4.8 ppm to 0.0 by
  construction; with one lock mass there is nothing left over to check it
  against, which is why the verdict names the count.
* The figure that matters is the other components. Fifty-one analytes inside
  the survey now carry a formula — against the fifteen that could be derived
  by hand when this was first measured — and 1,228 measurements of them
  stand. Over all of them the median error is −247 ppm before and −241 ppm
  after: those are interferences, not the compound, and no ppm-scale
  correction touches them. Over the 197 measurements that were within 25 ppm
  to begin with — where the survey plausibly found the right ion — the
  median error goes from **−7.0 ppm to −1.4 ppm** and the median magnitude
  from **8.6 to 6.8 ppm**, smaller on 122 of 197. It moves the centre in the
  right direction and it cannot do better than the one lock mass it was
  fitted from.
* And it is **not cosmetic**. Reprocessing the whole batch both ways, over
  ±20 ppm extraction windows, a median shift of 5 ppm moved 1,769 of 2,593
  integrated areas: median |Δ| 1.3%, 830 rows past 5%, and ten rows lost
  their peak. A TOF stores few points across a window that narrow, so
  shifting its edge takes whole points in or out — the same edge effect
  CLAUDE.md records about the vendor's extraction. Switching this on is a
  quantitative decision, not a display preference, which is why the switch
  is saved with the project and off by default.

A batch with four or more standards that *hold the same ion* across the mass
range is what a linear term needs, and no such batch was available to
measure — this one has one such standard whether ten of them carry a formula
or none do. Until one is, `MIN_SLOPE_LOCK_MASSES`, `MIN_MASS_SPAN` and the
leave-one-out test are written and tested but have never fired on real data.

## A direct infusion has no batch, and does not need one

`fit_batch` needs injections: a compound of known composition measured over
and over, so that one injection's error can be told from another's. A direct
infusion is one acquisition of one vial and there is no second injection
anywhere. What it has instead is a **ladder** — the precursor in the same
spectrum as its own fragments, and `explain.precursor_ions` saying where each
of them belongs. `fit_infusion` reads it: every rung found is an independent
measurement of a mass the formula already knows, in the same acquisition, at
a different mass. See that function for the rules and `MIN_LADDER_RUNGS`,
`LADDER_TOLERANCE_PPM` for the two constants they turn on.

Measured on the nine ZenoTOF 7600 bile-acid infusions (positive, one
product-ion channel each and **no survey scan at all**), whole run averaged
and centroided, the formula and adduct from the file name through
`explain.resolve_name` and `chemistry.identify_adduct`. The last four columns
are `explain.explain_formula` run at **5 ppm** — the LIPID MAPS tab's own
default — on the axis as measured and on the corrected one:

| infusion | rungs | offset | spread | span | ions before | after | intensity before | after |
|---|---|---|---|---|---|---|---|---|
| `CA-d4 …EAD_12CE…mix1` | 3 | −5.3 ppm | 7.5 ppm | 54 Da | 2 of 56 | 2 of 56 | 2.8% | **83.7%** |
| `CA-d4 …EAD_22CE…mix1` | 8 | −5.6 | 6.3 | 72 | 5 of 56 | **8 of 56** | 14.0% | **63.6%** |
| `CA-d4_TOFMSMS_Mix1` (CID 45) | 3 | +3.6 | 1.3 | 19 | 2 of 56 | 2 of 56 | 24.2% | 24.2% |
| `DCA-d4 …EAD_22CE…mix1` | 8 | −8.6 | 19.9 | 72 | 2 of 41 | **5 of 41** | 16.2% | **53.0%** |
| `DCA-d4_TOFMSMS_Mix1` (CID 40) | 3 | +6.2 | 2.5 | 18 | 1 of 41 | **3 of 41** | 1.6% | **17.1%** |
| `TDCA-d4 …EAD_22CE…mix1` | 5 | −7.5 | 3.3 | 37 | 0 of 104 | **5 of 104** | 0.0% | **78.4%** |
| `TDCA-d4_TOFMSMS_Mix1` (CID 30) | 4 | +1.8 | 4.1 | 37 | 4 of 104 | 4 of 104 | 72.1% | 72.1% |
| `CA-d4 …EAD_12CE…TESTEARTIGO` | — | — | — | — | — | — | — | — |
| `CA-d4 …EAD_22CE…TESTEARTIGO` | — | — | — | — | — | — | — | — |

Seven of nine are corrected, from 3 to 8 rungs each, by −8.6 to +6.2 ppm. Two
are not, and it is the right refusal: the `_TESTEARTIGO` pair is named for
cholic acid-d4 and isolates **839.56**, which is none of that formula's
adducts, so `axis_subject` never reaches a ladder and the row reads *no lock
mass* with the reason. That the sign is not the same for all nine is worth
noting — the EAD acquisitions read high and the CID ones low — which is why
this is fitted per acquisition and not once for the instrument.

The figure that says it was worth doing is the last pair of columns.
`CA-d4 …EAD_22CE` reaching **8 of 56 ions and 63.6%** at 5 ppm is exactly
what the same file gave at *10 ppm* on the uncorrected axis: the correction
buys back the tolerance that had been widened to absorb it, and a tolerance
absorbing an axis error is a tolerance not testing anything. Nothing
*worsened*: the two files that do not move (both already inside 5 ppm at
their strongest rungs) come back identical to the tenth of a per cent.

Nothing is dropped by the spread rule on these nine — the widest
disagreement between rungs of one ladder is `DCA-d4 …EAD_22CE`'s 19.9 ppm,
inside `CONSENSUS_SPREAD_PPM` — so `_agreeing_rungs` is a guard here rather
than a finding, and only the synthetic tests have fired it.

## And it makes a record of one's own travel

A record written from one infusion and searched with another of the same
compound, both averages centroided, the record carrying its formula and
adduct — the whole own-library round trip, before and after:

| record / query | peak tol. | axis | score | reverse | matched | median &#124;Δ ppm&#124; |
|---|---|---|---|---|---|---|
| CA-d4 EAD 22 / EAD 12 | 20 ppm | as measured | 67.4 | 67.4 | 12 of 42 | 0.6 |
| | | recalibrated | 67.4 | 67.4 | 12 of 42 | 0.6 |
| DCA-d4 EAD 22 / CID 40 | 20 ppm | as measured | 33.4 | 70.0 | 21 of 39 | 12.3 |
| | | recalibrated | **34.5** | **71.3** | **23 of 39** | **2.6** |
| TDCA-d4 EAD 22 / CID 30 | 20 ppm | as measured | 61.5 | 69.4 | 8 of 32 | 8.6 |
| | | recalibrated | 61.5 | 69.4 | 8 of 32 | **2.1** |
| CA-d4 EAD 22 / EAD 12 | 5 ppm | as measured | 65.9 | 66.3 | 11 of 42 | 0.4 |
| | | recalibrated | 65.9 | 66.3 | 11 of 42 | 0.5 |
| DCA-d4 EAD 22 / CID 40 | 5 ppm | as measured | **no hit** | | | |
| | | recalibrated | **31.8** | **69.6** | **19 of 39** | 2.5 |
| TDCA-d4 EAD 22 / CID 30 | 5 ppm | as measured | **no hit** | | | |
| | | recalibrated | **61.0** | **69.1** | **7 of 32** | 1.9 |

At the library's default 20 ppm the scores barely move — a pairing that was
already succeeding goes on succeeding — but the masses agree far better: the
median gap between a paired library peak and the measured one it landed on
falls from 12.3 to 2.6 ppm and from 8.6 to 2.1. At **5 ppm** that difference
is the whole result. Two of the three pairs **do not match at all** on the
instrument's own axes, because the two acquisitions were 14.8 and 9.3 ppm
apart from each other, and both match once each is corrected against its own
precursor. CA-d4's pair was 0.3 ppm apart to begin with and is unmoved, which
is the control: the correction does not manufacture agreement where there was
already agreement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .mass_drift import MassDrift, MassTrend, mass_drift
from .precursor import CONSENSUS_SPREAD_PPM, MIN_INTENSITY

#: how far a lock mass may sit from its own formula before it is not the ion
#: the formula names. `same_ion` asks the injections whether they agree with
#: each other; a standard whose ±0.25 Da window holds the same *wrong* ion in
#: every injection agrees with itself perfectly and passes it.
#:
#: Measured: |measured − formula| over the 1,439 survey measurements the real
#: batch supplies — all 60 formula-bearing components inside its 50–700
#: survey, in every injection —
#:
#:       0– 10 ppm   203  14.1%  ##############
#:      10– 20        77   5.4%  #####
#:      20– 30        31   2.2%  ##
#:      30– 40        15   1.0%  #
#:      40– 50        20   1.4%  #
#:      50– 60        29   2.0%  ##
#:      60– 80        53   3.7%  ####
#:      80–100        35   2.4%  ##
#:     100–200       206  14.3%  ##############
#:        ≥ 200      770  53.5%  ######################################…
#:
#: — which is bimodal: a lobe of measurements of the compound under 20 ppm
#: (19.5% of them), a lobe of interferences that starts at 50 and runs to
#: 800, and the floor of the trough between the two at 30–50 ppm, where a
#: 10 ppm bin holds 1.0–1.4%. Fifty is that trough's far edge, and it is
#: twice `precursor.CONSENSUS_SPREAD_PPM` — the disagreement between
#: injections `same_ion` already tolerates. An ion allowed to wander a
#: spread's worth may sit a spread's worth from the truth, and no further.
#: The margins either side are both about a factor of five: this batch's one
#: honest lock mass is 11.7 ppm out in its worst injection, and the impostor
#: `C17:0_Ceramide` 237 ppm (measured 237.5; the 238 in earlier notes was
#: that rounded the wrong way).
MAX_LOCK_ERROR_PPM = 50.0

#: fewest lock masses before a linear term is even considered. Four, not
#: three, because the slope is only kept when leave-one-out prediction says
#: it helps: hold one of three out and the line is fitted through two points,
#: which is exact and predicts nothing. Four is the first count at which
#: dropping one still leaves an over-determined fit.
MIN_SLOPE_LOCK_MASSES = 4

#: daltons the lock masses must span before a linear term is considered. A
#: slope fitted over ten daltons and used over six hundred is extrapolation
#: wearing a fit's clothes.
MIN_MASS_SPAN = 100.0

#: how much better, in ppm of leave-one-out median absolute residual, the
#: line has to predict a held-out lock mass before its slope is kept. The
#: median rather than a root mean square for the same reason the offset is a
#: median: one lock mass caught on an interference should not decide the
#: shape of the correction for the rest.
SLOPE_MARGIN_PPM = 0.5

#: iterations of the fixed point that inverts `apply`. The perturbation is
#: parts per million, so this converges to machine precision immediately;
#: three is belt and braces for a steep linear term.
UNDO_ITERATIONS = 3

#: where a correction came from, in the words the table and the report print.
#: One string per source rather than a flag, because the two are fitted from
#: different evidence and a reader who cannot tell them apart cannot judge
#: either: a batch's correction stands on other compounds' standards, an
#: infusion's on the one compound in the vial.
BATCH_SOURCE = "from the internal standards"
LADDER_SOURCE = "from the precursor ladder"

#: how far either side of a predicted rung to look for it, in ppm. Twenty is
#: the window the identification itself uses — the precursor is confirmed at
#: this tolerance before anything is corrected — and a rung matched in a
#: window wider than the error being measured is a rung matched to whatever
#: was nearest. Note that this bounds every offset the fit can see, so
#: `MAX_LOCK_ERROR_PPM` cannot fire at the default: the ceiling is there for
#: a caller who widens the window, and it is the only thing that then stops
#: the ladder being fitted onto a neighbouring ion series.
LADDER_TOLERANCE_PPM = 20.0

#: fewest rungs before an infusion's axis is corrected at all. Two, not one:
#: a single rung is the precursor measured against its own formula and
#: nothing checks it, and unlike a batch — where one lock mass in twenty-six
#: injections is still one number the other injections can be read against —
#: an infusion is one acquisition and has no second opinion anywhere. Two
#: rungs of the same ladder at the same offset is the smallest evidence that
#: the axis moved rather than that one peak was misassigned.
MIN_LADDER_RUNGS = 2


@dataclass(frozen=True)
class LockMass:
    """One standard's measured mass in one injection, against its formula."""

    component: str
    #: from formula and adduct — never the method's written precursor
    theoretical: float
    #: what the survey scan read, uncorrected
    measured: float
    intensity: float = 0.0

    @property
    def error_ppm(self) -> float:
        """How far the instrument read it from where it belongs."""
        return (self.measured - self.theoretical) / self.theoretical * 1e6


@dataclass
class MassCorrection:
    """One injection's correction: what to add to a mass, in ppm."""

    sample_key: str = ""
    sample_name: str = ""
    #: ppm added at the pivot
    offset_ppm: float = 0.0
    #: ppm added per dalton away from the pivot; zero unless a slope was kept
    slope_ppm_per_da: float = 0.0
    pivot: float = 0.0
    lock_masses: list[LockMass] = field(default_factory=list)
    #: why there is no correction, or what the slope decision was
    note: str = ""
    #: what the correction stands on, in words — `BATCH_SOURCE` or
    #: `LADDER_SOURCE`. Printed in the panel and the report, because an
    #: offset fitted from other compounds' internal standards and one fitted
    #: from this vial's own fragment ladder are not the same claim.
    source: str = BATCH_SOURCE
    #: what one of `lock_masses` is called in a sentence. A batch's are lock
    #: masses; an infusion's are rungs of one ladder, and calling those
    #: "lock masses" would suggest independent compounds.
    unit: str = "lock mass"

    # -- the correction itself ------------------------------------------------ #
    @property
    def usable(self) -> bool:
        return bool(self.lock_masses)

    @property
    def linear(self) -> bool:
        return self.slope_ppm_per_da != 0.0

    def ppm_at(self, mz):
        """The correction in ppm at one mass, or over an array of them."""
        mz = np.asarray(mz, dtype=float)
        if not self.usable:
            return np.zeros_like(mz)
        return self.offset_ppm + self.slope_ppm_per_da * (mz - self.pivot)

    def apply(self, mz):
        """
        Measured masses to corrected ones.

        Adding k ppm is one multiplication by (1 + k/10⁶), so a mass that
        was k ppm out lands k²/10¹² short of exact — 0.000036 ppm at 6 ppm,
        which is 1·10⁻⁸ Da at m/z 300. That is why the residual after a
        single lock mass reads 0.0 rather than being identically zero.
        """
        mz = np.asarray(mz, dtype=float)
        if not self.usable:
            return mz
        return mz * (1.0 + self.ppm_at(mz) * 1e-6)

    def undo(self, mz):
        """
        Corrected masses back to measured ones — what a raw file holds.

        This is what the extraction uses: the window a component asks for is
        written in corrected space and the reader only knows measured space.
        A constant offset inverts in one step; a linear term makes `apply`
        quadratic, so the inverse is a fixed point, which converges at
        parts-per-million strengths immediately.
        """
        mz = np.asarray(mz, dtype=float)
        if not self.usable:
            return mz
        guess = mz
        for _ in range(UNDO_ITERATIONS):
            guess = mz / (1.0 + self.ppm_at(guess) * 1e-6)
        return guess

    # -- how well it did ------------------------------------------------------ #
    @property
    def before_ppm(self) -> list[float]:
        return [lock.error_ppm for lock in self.lock_masses]

    @property
    def after_ppm(self) -> list[float]:
        out = []
        for lock in self.lock_masses:
            corrected = float(self.apply(lock.measured))
            out.append((corrected - lock.theoretical) / lock.theoretical * 1e6)
        return out

    @property
    def median_before(self) -> float | None:
        return float(np.median(self.before_ppm)) if self.lock_masses else None

    @property
    def median_after(self) -> float | None:
        return float(np.median(self.after_ppm)) if self.lock_masses else None

    @property
    def worst_before(self) -> float | None:
        values = self.before_ppm
        return max(values, key=abs) if values else None

    @property
    def worst_after(self) -> float | None:
        values = self.after_ppm
        return max(values, key=abs) if values else None

    @property
    def spread_ppm(self) -> float | None:
        """
        How far apart the lock masses' own errors sat, before correcting.

        None for a single one, and that is the point: an offset from one
        measurement has no spread, so there is no figure to print and
        printing 0.0 would read as perfect agreement rather than as no
        agreement having been tested.
        """
        values = self.before_ppm
        if len(values) < 2:
            return None
        return float(max(values) - min(values))

    @property
    def span_da(self) -> float:
        """Daltons between the lowest and highest lock mass."""
        masses = [lock.theoretical for lock in self.lock_masses]
        return float(max(masses) - min(masses)) if len(masses) > 1 else 0.0

    @property
    def plural(self) -> str:
        """`unit`, agreeing with how many there are."""
        count = len(self.lock_masses)
        if count == 1:
            return self.unit
        return f"{self.unit}es" if self.unit.endswith("s") else f"{self.unit}s"

    @property
    def verdict(self) -> str:
        """
        One line saying what happened to this injection.

        The count of lock masses is part of the sentence, because a
        correction from one of them is an offset with nothing left over to
        check it against, and reading "corrected by +2.2 ppm" without that
        would suggest a measurement it is not. Where there is more than one
        the spread between them goes in for the same reason: it is the only
        figure on the line that says how much the correction can be trusted.
        """
        if not self.usable:
            return self.note or f"no usable {self.unit} — left as measured"
        count = len(self.lock_masses)
        if count == 1:
            shape = f"offset only, from one {self.unit} — nothing checks it"
        elif self.linear:
            shape = (f"a slope of {self.slope_ppm_per_da * 1000:+.2f} ppm "
                     f"per 1,000 Da")
        else:
            shape = "offset only"
        spread = self.spread_ppm
        said = (f"corrected by {self.offset_ppm:+.1f} ppm from "
                f"{count} {self.plural} ({shape})")
        if spread is not None:
            said += f", their own errors {spread:.1f} ppm apart"
        return said

    @property
    def short(self) -> str:
        """
        The correction in as few words as a title or a table cell holds.

        Says the count as well as the offset: a mass axis that has been moved
        and does not say what moved it is the one thing worse than a mass
        axis that is wrong.
        """
        if not self.usable:
            return f"no {self.unit}"
        return (f"recalibrated {self.offset_ppm:+.1f} ppm from "
                f"{len(self.lock_masses)} {self.plural}")

    def basis_sentence(self) -> str:
        """
        The correction and what it did to its own first rung, for a basis line.

        Both numbers, because only the pair says anything: "+0.4 ppm
        corrected" alone is a residual the correction was fitted to produce,
        and "+5.6 ppm raw" alone does not say the axis was moved. The rung
        quoted is the strongest — the one the offset mostly rests on.
        """
        if not self.usable:
            return self.note or f"no {self.unit} — the axis stands as measured"
        strongest = max(range(len(self.lock_masses)),
                        key=lambda i: self.lock_masses[i].intensity)
        lock = self.lock_masses[strongest]
        return (f"on an axis {self.short}; {lock.component} measured "
                f"{self.before_ppm[strongest]:+.1f} ppm raw, "
                f"{self.after_ppm[strongest]:+.1f} ppm corrected")

    def to_dict(self) -> dict:
        return {"sample_key": self.sample_key, "sample_name": self.sample_name,
                "offset_ppm": self.offset_ppm,
                "slope_ppm_per_da": self.slope_ppm_per_da,
                "pivot": self.pivot, "note": self.note, "source": self.source,
                "lock_masses": [lock.component for lock in self.lock_masses]}


# --------------------------------------------------------------------------- #
# fitting
# --------------------------------------------------------------------------- #
def _offset_loo(errors: np.ndarray) -> float:
    """Leave-one-out median absolute residual of the plain offset."""
    residuals = []
    for index in range(errors.size):
        others = np.delete(errors, index)
        residuals.append(abs(errors[index] - float(np.median(others))))
    return float(np.median(residuals))


def _line_loo(masses: np.ndarray, errors: np.ndarray) -> float | None:
    """
    Leave-one-out median absolute residual of a straight line through the rest.

    Each fit uses every lock mass but one and is asked to predict the one it
    never saw. That is the whole test: a line drawn through the points it is
    then scored on is exact and says nothing, which is why
    `MIN_SLOPE_LOCK_MASSES` is four rather than three.
    """
    residuals = []
    for index in range(masses.size):
        x = np.delete(masses, index)
        y = np.delete(errors, index)
        if x.size < 3 or float(np.ptp(x)) == 0.0:
            return None
        slope, intercept = np.polyfit(x, y, 1)
        residuals.append(abs(errors[index] - (slope * masses[index] + intercept)))
    return float(np.median(residuals))


def fit_correction(sample_key: str, sample_name: str,
                   lock_masses: list[LockMass]) -> MassCorrection:
    """
    One injection's correction from its lock masses.

    The offset is the median error rather than the mean: two lock masses
    agreeing and a third caught on an interference should not drag the axis
    a third of the way towards the interference.
    """
    correction = MassCorrection(sample_key=sample_key, sample_name=sample_name,
                                lock_masses=list(lock_masses))
    if not lock_masses:
        correction.note = "no usable lock mass — left as measured"
        return correction

    masses = np.array([lock.theoretical for lock in lock_masses], dtype=float)
    errors = np.array([lock.error_ppm for lock in lock_masses], dtype=float)
    correction.pivot = float(np.median(masses))
    correction.offset_ppm = -float(np.median(errors))

    span = float(np.ptp(masses))
    if len(lock_masses) < MIN_SLOPE_LOCK_MASSES:
        plural = "es" if len(lock_masses) != 1 else ""
        correction.note = (f"{len(lock_masses)} lock mass{plural}: fewer than "
                           f"{MIN_SLOPE_LOCK_MASSES}, so an offset is all that "
                           f"can be fitted and checked")
        return correction
    if span < MIN_MASS_SPAN:
        correction.note = (f"lock masses span {span:,.0f} Da; a slope needs "
                           f"{MIN_MASS_SPAN:,.0f} Da before it is anything "
                           f"but extrapolation")
        return correction

    plain = _offset_loo(errors)
    line = _line_loo(masses, errors)
    if line is None or line + SLOPE_MARGIN_PPM >= plain:
        held = "—" if line is None else f"{line:.2f}"
        correction.note = (f"a slope did not help: leave-one-out {held} ppm "
                           f"against {plain:.2f} ppm for the offset alone")
        return correction

    slope, intercept = np.polyfit(masses, errors, 1)
    correction.slope_ppm_per_da = -float(slope)
    correction.offset_ppm = -float(slope * correction.pivot + intercept)
    correction.note = (f"a slope helped: leave-one-out {line:.2f} ppm against "
                       f"{plain:.2f} ppm for the offset alone")
    return correction


# --------------------------------------------------------------------------- #
# an infusion, fitted from its own precursor
# --------------------------------------------------------------------------- #
def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """
    The median of `values` with each counted `weights` times.

    A median rather than a weighted mean for the reason the batch fit gives:
    one rung caught on a neighbour should not drag the axis a share of the
    way towards it. Weighted rather than plain because the rungs of one
    ladder are not equally well measured — a peak of twelve thousand counts
    locates its centroid better than one of a hundred and twenty — and on
    the real infusions the strong end of the ladder is where the precursor
    and the first dehydrations sit.
    """
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    total = float(weights.sum())
    if total <= 0:
        return float(np.median(values))
    running = np.cumsum(weights)
    return float(values[int(np.searchsorted(running, total / 2.0))])


def ladder_rungs(peaks_mz, peaks_intensity, formula: str, adduct,
                 deuterium: int = 0,
                 tolerance_ppm: float = LADDER_TOLERANCE_PPM,
                 min_intensity: float = MIN_INTENSITY) -> list[LockMass]:
    """
    Every ion of `explain.precursor_ions` this spectrum actually holds.

    The peaks must already be **centroids**. `precursor.in_spectrum` is the
    profile-data rule and refines across the points either side of the apex;
    run on sticks it averages a peak with its neighbours, which on the real
    infusions reported the cholic acid-d4 precursor at 429.7675 for a peak at
    430.3489 — a thousand ppm out, from a window that held the right ion.
    Here the match is the strongest stick inside the window and nothing else.

    A rung is kept only above `min_intensity`, the floor `precursor.measure`
    holds a survey scan to: a window is a stretch of axis like any other and
    its tallest point is noise until something is there.
    """
    from .explain import precursor_ions

    mz = np.asarray(peaks_mz, dtype=float)
    intensity = np.asarray(peaks_intensity, dtype=float)
    if mz.size == 0 or mz.size != intensity.size:
        return []
    out: list[LockMass] = []
    for ion in precursor_ions(formula, adduct, deuterium):
        window = ion.mz * tolerance_ppm * 1e-6
        inside = np.flatnonzero((mz >= ion.mz - window)
                                & (mz <= ion.mz + window))
        if inside.size == 0:
            continue
        best = int(inside[int(np.argmax(intensity[inside]))])
        if float(intensity[best]) < min_intensity:
            continue
        out.append(LockMass(component=ion.description, theoretical=float(ion.mz),
                            measured=float(mz[best]),
                            intensity=float(intensity[best])))
    return out


def fit_infusion(peaks_mz, peaks_intensity, formula: str, adduct,
                 deuterium: int = 0,
                 tolerance_ppm: float = LADDER_TOLERANCE_PPM,
                 sample_key: str = "", sample_name: str = "",
                 min_intensity: float = MIN_INTENSITY) -> MassCorrection | None:
    """
    A direct infusion's mass axis, corrected against its own precursor.

    `fit_batch` needs a batch: a compound of known composition measured in
    injection after injection, so that one injection's error can be told from
    another's. An infusion is one acquisition of one vial, and there is no
    second injection anywhere. What it has instead is a **ladder**: the
    precursor is in the spectrum with its own fragments, and
    `explain.precursor_ions` says exactly where each of them belongs —
    the intact adduct, the core `[M+H]+` a labile adduct leaves behind, the
    cumulative waters, and the −1D rungs a labelled standard sheds. Every
    rung that is found is an independent measurement of a mass the formula
    already knows, in the same acquisition, at a different mass.

    The correction is an **offset** and only an offset. The rungs of one
    precursor span the waters it can lose — 72 Da at the widest on the nine
    real infusions, against the `MIN_MASS_SPAN` of 100 Da a slope needs —
    and a line fitted over seventy daltons and used over five hundred is
    extrapolation wearing a fit's clothes. The note says so with the file's
    own span rather than leaving the reader to wonder.

    `same_ion`'s idea applies rung by rung. A rung whose error disagrees with
    the rest by more than `CONSENSUS_SPREAD_PPM` is not this axis measured
    badly, it is a different ion inside the window, and it is dropped and
    named. Below `MIN_LADDER_RUNGS` afterwards, or an offset past
    `MAX_LOCK_ERROR_PPM`, and nothing is corrected: the returned correction
    is not `usable`, `apply` is then the identity, and the reason is on it —
    a refusal that vanished would leave the panel a row short and the reader
    no wiser about which vial was left alone. None comes back only when
    there was nothing to fit *from*: no formula, no adduct this program
    knows, or no spectrum.

    The peaks must be centroids; see `ladder_rungs`.
    """
    if np.asarray(peaks_mz, dtype=float).size == 0:
        return None
    rungs = ladder_rungs(peaks_mz, peaks_intensity, formula, adduct,
                         deuterium=deuterium, tolerance_ppm=tolerance_ppm,
                         min_intensity=min_intensity)
    correction = MassCorrection(sample_key=sample_key, sample_name=sample_name,
                                source=LADDER_SOURCE, unit="rung")
    if not rungs:
        if not _ladder_offered(formula, adduct, deuterium):
            return None
        correction.note = (
            f"no rung of {formula} as {adduct} is in this spectrum within "
            f"±{tolerance_ppm:g} ppm and above {min_intensity:,.0f} counts: "
            f"no lock mass, and the axis stands as measured")
        return correction

    kept, dropped = _agreeing_rungs(rungs)
    said = []
    if dropped:
        said.append("dropped, disagreeing with the rest by more than "
                    f"{CONSENSUS_SPREAD_PPM:g} ppm: "
                    + "; ".join(f"{name} {error:+.1f} ppm"
                                for name, error in dropped))
    if len(kept) < MIN_LADDER_RUNGS:
        correction.lock_masses = []
        correction.note = " · ".join([
            f"{len(kept)} rung(s) of the ladder in this spectrum, fewer than "
            f"the {MIN_LADDER_RUNGS} an offset needs before anything checks "
            f"it: no lock mass, and the axis stands as measured", *said])
        return correction

    masses = np.array([rung.theoretical for rung in kept], dtype=float)
    errors = np.array([rung.error_ppm for rung in kept], dtype=float)
    weights = np.array([rung.intensity for rung in kept], dtype=float)
    offset = -_weighted_median(errors, weights)
    if abs(offset) > MAX_LOCK_ERROR_PPM:
        correction.lock_masses = []
        correction.note = " · ".join([
            f"the ladder sits {-offset:+,.0f} ppm from where the formula puts "
            f"it, past the {MAX_LOCK_ERROR_PPM:g} ppm beyond which it is a "
            f"different ion series rather than a mis-set axis: no lock mass, "
            f"and the axis stands as measured", *said])
        return correction

    correction.lock_masses = kept
    correction.pivot = float(np.median(masses))
    correction.offset_ppm = float(offset)
    span = correction.span_da
    # why there is no slope, with this file's own span in it. A ladder wide
    # enough for one has never been seen — three waters is 54 Da and the
    # widest measured is 72 — but saying so from the measurement rather than
    # from the assumption is what makes the sentence worth printing.
    said.insert(0, f"offset only: the {len(kept)} rungs span {span:,.0f} Da, "
                   + (f"under the {MIN_MASS_SPAN:,.0f} Da a slope needs "
                      f"before it is extrapolation" if span < MIN_MASS_SPAN
                      else "but a ladder is one precursor's own losses and is "
                           "fitted as an offset whatever it spans"))
    correction.note = " · ".join(said)
    return correction


def _ladder_offered(formula: str, adduct, deuterium: int) -> bool:
    """Whether there was a ladder to look for at all."""
    from .explain import precursor_ions

    return bool(precursor_ions(formula, adduct, deuterium))


def _agreeing_rungs(rungs: list[LockMass]
                    ) -> tuple[list[LockMass], list[tuple[str, float]]]:
    """
    The rungs that agree with each other, and the ones that do not.

    Each is judged against the weighted median of the *others*, so a rung
    cannot excuse itself by being in the sample it is compared with — the
    same leave-one-out shape `_offset_loo` uses, and the same limit
    `mass_drift.same_ion` uses to say two measurements are not of the same
    ion. Two rungs cannot judge each other: with one left over there is no
    median to disagree with, so both stand or neither does.
    """
    if len(rungs) < 3:
        return list(rungs), []
    errors = np.array([rung.error_ppm for rung in rungs], dtype=float)
    weights = np.array([rung.intensity for rung in rungs], dtype=float)
    kept, dropped = [], []
    for index, rung in enumerate(rungs):
        others = _weighted_median(np.delete(errors, index),
                                  np.delete(weights, index))
        if abs(errors[index] - others) > CONSENSUS_SPREAD_PPM:
            dropped.append((rung.component, float(errors[index])))
        else:
            kept.append(rung)
    return kept, dropped


def _error_ppm(measured: float, exact: float) -> float:
    """One measurement against the formula, in ppm."""
    return (measured - exact) / exact * 1e6


def lock_mass_refusal(trend: MassTrend) -> str | None:
    """
    Why this trend is not a lock mass for the run at all, or None.

    The sanity gate `same_ion` cannot supply: a standard measured past
    `MAX_LOCK_ERROR_PPM` from its own formula in *most* of its injections is
    not that compound being read badly, it is a different ion being read
    well, and a fit pulled towards it would recalibrate the batch onto an
    interference. Most rather than any, because one injection catching a
    neighbour is a bad injection — that one measurement is dropped where it
    happens, and the standard stands.

    Reported for any trend carrying a formula, whatever else it failed:
    `C17:0_Ceramide` on the real batch is one injection short of the count a
    trend needs *and* 237 ppm from its formula, and only the second of those
    says the number is not the compound.
    """
    if trend.exact is None or not trend.points:
        return None
    errors = [abs(_error_ppm(point.mz, trend.exact)) for point in trend.points]
    past = sum(1 for error in errors if error > MAX_LOCK_ERROR_PPM)
    if past * 2 <= len(errors):
        return None
    # the median of the distances rather than the distance of the median: the
    # figure quoted has to be one that justifies the refusal, and a trend
    # whose injections straddle the formula can have a small median error and
    # not one measurement near it. Most injections being past the limit makes
    # this median past it too, whatever the count is.
    return (f"measures {float(np.median(errors)):,.0f} ppm from its formula: "
            f"not the ion the formula names")


def lock_masses_from_drift(drift: MassDrift | None) -> dict[str, list[LockMass]]:
    """
    Reuse the mass-drift measurement: every trend that measured the same ion
    throughout, knows what mass it should have been, and measured it near
    that mass.

    A trend that failed `same_ion` is left out entirely. Its points are not
    one ion measured badly, they are different ions measured well, and
    averaging them would recalibrate onto whatever happened to be nearest. A
    trend `lock_mass_refusal` names is left out for the opposite reason: its
    injections agree, and agree about the wrong ion. What survives both is
    then filtered a third time, injection by injection, since a standard that
    is honest across the run can still have one measurement past the limit.
    """
    out: dict[str, list[LockMass]] = {}
    if drift is None:
        return out
    for trend in drift.trends:
        if trend.exact is None or trend.median is None or not trend.same_ion:
            continue
        if lock_mass_refusal(trend):
            continue
        for point in trend.points:
            if abs(_error_ppm(point.mz, trend.exact)) > MAX_LOCK_ERROR_PPM:
                continue
            out.setdefault(point.key or point.sample, []).append(LockMass(
                component=trend.component, theoretical=trend.exact,
                measured=point.mz, intensity=point.intensity))
    return out


def dropped_lock_masses(drift: MassDrift | None
                        ) -> dict[str, list[tuple[str, float]]]:
    """
    Per injection, the lock masses left out of *that* injection alone.

    A standard the run keeps but this injection's window read past
    `MAX_LOCK_ERROR_PPM`. The injection's correction says so rather than
    silently being fitted from fewer lock masses than the table above it
    shows — or, where it was the only one, rather than reading as an
    injection nothing was measured in.
    """
    out: dict[str, list[tuple[str, float]]] = {}
    if drift is None:
        return out
    for trend in drift.trends:
        if trend.exact is None or trend.median is None or not trend.same_ion:
            continue
        if lock_mass_refusal(trend):
            continue
        for point in trend.points:
            error = _error_ppm(point.mz, trend.exact)
            if abs(error) > MAX_LOCK_ERROR_PPM:
                out.setdefault(point.key or point.sample, []).append(
                    (trend.component, error))
    return out


def fit_batch(session, drift: MassDrift | None = None,
              progress=None) -> dict[str, MassCorrection]:
    """
    A correction per injection, keyed by sample key.

    The measurements come from `mass_drift` — the session's if one stands,
    otherwise one measured here — so a fit costs nothing after the drift has
    been looked at, and the two always agree about what was measured.

    Every loaded injection gets an entry, including the ones with no lock
    mass: an injection missing from the table would read as an injection
    nobody looked at.
    """
    if drift is None:
        drift = getattr(session, "mass_drift", None)
    if drift is None:
        drift = mass_drift(session.entries, session.method, progress=progress)
    if drift is None:                       # the operator cancelled
        return {}
    by_key = lock_masses_from_drift(drift)
    dropped = dropped_lock_masses(drift)
    out: dict[str, MassCorrection] = {}
    for entry in session.entries:
        if not entry.is_loaded:
            continue
        correction = fit_correction(entry.key, entry.name,
                                    by_key.get(entry.key, []))
        left_out = dropped.get(entry.key)
        if left_out:
            said = "; ".join(f"{name} {error:+,.0f} ppm"
                             for name, error in left_out)
            correction.note = " \u00b7 ".join(part for part in (
                correction.note,
                f"left out of this injection, past {MAX_LOCK_ERROR_PPM:g} ppm "
                f"from its own formula here: {said}") if part)
        out[entry.key] = correction
    return out


def describe(corrections: dict[str, MassCorrection]) -> str:
    """One line about the whole batch, for a status bar or a report."""
    if not corrections:
        return "Not fitted yet."
    usable = [c for c in corrections.values() if c.usable]
    if not usable:
        return (f"No lock mass in any of {len(corrections)} injection(s). A "
                f"lock mass is an internal standard carrying a formula and an "
                f"adduct, measuring the same ion throughout the run and "
                f"measuring it within {MAX_LOCK_ERROR_PPM:g} ppm of what that "
                f"formula weighs; nothing "
                f"here does, so nothing is corrected. Method workspace ▸ "
                f"Fill formulas from names supplies the formula where the "
                f"name is lipid shorthand; where the ion is what fails, no "
                f"formula can help.")
    counts = {len(c.lock_masses) for c in usable}
    offsets = np.array([c.offset_ppm for c in usable], dtype=float)
    spread = ("{}–{}".format(min(counts), max(counts)) if len(counts) > 1
              else f"{min(counts)}")
    # what one of them is called: a batch's are lock masses, an infusion's
    # are rungs of one ladder, and a line saying "8 lock mass(es)" of an
    # infusion would promise eight compounds where there is one
    units = {c.unit for c in usable}
    if len(units) == 1:
        one = units.pop()
        unit = f"{one}(es)" if one.endswith("s") else f"{one}(s)"
    else:
        unit = "lock mass(es)/rung(s)"
    said = [f"{len(usable)} of {len(corrections)} injection(s) corrected",
            f"{spread} {unit} each",
            f"median offset {float(np.median(offsets)):+.1f} ppm"]
    if max(counts) == 1:
        said.append("an offset from one lock mass has nothing to check it")
    return " · ".join(said)
