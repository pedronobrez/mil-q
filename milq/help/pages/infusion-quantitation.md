---
title: Quantitation by direct infusion
---
**Quantify…** on the *Infusions* tab measures each analyte against the
internal standard the method gives it, in the averaged spectrum of every open
[[direct-infusion]]. There is no column, so there is no peak, no retention
time and no width: the response is a height in one spectrum, and the number
that means something is the ratio of two of them.

That ratio then goes into the [[results-table]] and the [[calibration]] like
any other row. A dilution series of infusions fits a curve exactly as a
series of injections does, and the rows say what they are — the *Algorithm*
column reads `infusion`, the retention time is zero and the *Note* says which
basis produced the number.

## The three bases

The dialog asks what to take the ratio on, and the three answer different
questions:

- **Precursor** — the intact ion the adduct declares. The most specific
  number there is, and the first thing to disappear as the collision energy
  goes up.
- **Fragment** — the fragment m/z written in the component table, or, where
  none is written, the strongest ion that compound is predicted to give in
  *this* spectrum. The second of those is not a fixed ion, and the page says
  below why that matters.
- **Water-loss ladder** (the default) — every rung the [[lipid-maps]] prediction
  offers for this formula and adduct, summed: the intact adduct,
  the form the fragments carry, and each dehydration of it, including the
  rungs that shed a deuterium with a water.

Measured on the nine ZenoTOF bile-acid infusions, all product-ion
acquisitions of the deuterated standards themselves:

| acquisition | CE | precursor | fragment | ladder | rungs found |
|---|---|---|---|---|---|
| CA-d4, EAD | 12 | 12,271 | 12,271 | 12,982 | 11 of 11 |
| CA-d4, EAD | 22 | 9,415 | 9,618 | 27,754 | 11 of 11 |
| CA-d4, CID | 45 | 0 | 5,673 | 6,569 | 4 of 11 |
| DCA-d4, EAD | 22 | 5,582 | 5,582 | 15,677 | 9 of 11 |
| DCA-d4, CID | 40 | 7 | 3,109 | 3,839 | 7 of 11 |
| TDCA-d4, EAD | 22 | 5,235 | 5,235 | 15,338 | 6 of 10 |
| TDCA-d4, CID | 30 | 124 | 9,044 | 10,403 | 6 of 10 |

The pattern is why the ladder is the default. Under a soft activation the
precursor survives and all three agree to within a factor of two; under CID
it is gone — **0, 7 and 124 counts** on the three hard acquisitions — while
the ladder still carries five to ten thousand. A basis that reads zero at one
collision energy and twelve thousand at another is not a basis.

The two files named `…TESTEARTIGO` are on the table's other side: they
isolate **839.56**, which is no adduct of cholic acid-d4 at all, so all three
bases refuse with that sentence rather than reporting a number. The same
finding the [[infusion-report]] made about those two acquisitions.

## The cross-talk, and which way it goes

A d4 standard sits 4·(D−H) = **4.0251 Da** above its unlabelled analyte. The
analyte's own M+4 isotopologue — four carbon-13s — sits 4·(13C−12C) =
**4.0134 Da** above it. The two are **0.0117 Da apart**, which is 27 ppm at
m/z 430: a high-resolution instrument separates them and a unit-resolution
one does not, so whether the analyte reaches the standard's channel is
decided by the tolerance and by nothing else.

So the correction is computed from the formula, per ion, and summed over
whatever the tolerance actually admits. From the three standards to hand,
as a fraction of the *analyte's* own monoisotopic peak:

| pair | 10 ppm | 20 ppm | 25 ppm | 30 ppm | 50 ppm | unit window |
|---|---|---|---|---|---|---|
| cholic acid → CA-d4, `[M+NH4]+` | 0 | 0.00004% | 0.0014% | 0.018% | 0.058% | 0.058% |
| deoxycholic → DCA-d4, `[M+NH4]+` | 0 | 0.00004% | 0.0014% | 0.017% | 0.049% | 0.049% |
| taurodeoxycholic → TDCA-d4, `[M+H]+` | 0 | 0.0019% | 0.025% | 0.073% | 0.322% | 0.337% |

**The reverse is zero, and it is zero because it was computed.** The standard
is the heavier compound, so its isotope envelope climbs *away* from the
analyte's ions and reaches nothing of them — 0.00000% at every tolerance up
to a whole unit. The direction that matters is always the light compound
into the heavy one, which for a deuterated standard means the analyte into
the standard, and it grows with the analyte: 0.058% is nothing at a ratio of
one to one and 5.8% at a hundred to one.

The one thing the arithmetic cannot see is the **bottle**. A d4 standard
holds some d3 and d2, and those land 1.006 and 2.012 Da *below* the d4 ion —
on the analyte's side. No formula predicts how much: it is a property of the
material, not of the compound. A d3 shoulder is therefore measured as
analyte, and that is stated rather than corrected for.

## When the correction is zero because the instrument got there first

A product-ion acquisition isolates its precursor, and the isolation window is
narrower than a dalton — so the satellites never entered the collision cell
and there is nothing of one compound in the other's ions to take off.

That is measured rather than assumed. For each compound the predicted M+1 is
compared against the measured one, on the strongest ion that has no *other*
predicted ion where its M+1 would be. On the seven readable bile-acid
infusions the predicted M+1 is **26.4 – 29.6%** of the monoisotopic peak and
the measured one is **0.000 – 0.426%** — a transmission of **0.00 – 1.44%**.
Below ten per cent of the prediction the envelope is treated as absent, the
correction is reported as zero, and the reason is in the *Cross-talk*
column's tooltip and on the row's note. The same reading refuses the
isotopic purity solve and the satellite check on every matched fragment;
[[lipid-maps]] carries it per acquisition, with the one survey-bearing
injection that says an isolation window really does keep the M+1 out.

Where it does apply is a **survey-scan** infusion, or any acquisition whose
isolation window spans both compounds. There every isotopologue is
transmitted and the table above is the whole of the answer.

There is a second, closer overlap that only a labelled pair has. A d4
standard's fully dehydrated rung, having shed three labels with three waters,
keeps one deuterium and sits **1.00628 Da** above the analyte's own rung —
while the analyte's carbon-13 satellite of that same rung sits 1.00335 above
it. Those are **2.9 mDa apart**, eight ppm at m/z 356, and at any tolerance
looser than that they are one measurement. It is counted like any other leak,
and the tooltip names the rung it came from.

## What the curve does with it

Fitted over a synthetic five-level series with the ratios known — 1, 2, 5, 10
and 20 — the precursor and the ladder recover **every level at 100.000% with
r² = 1.0000000**. The fragment basis, left to pick the strongest ion in each
spectrum, gives r² = 0.895 and accuracies from −199% to +150%: it is a
different ion at different levels, because the tallest peak moved as the
analyte grew against the standard. **Write a fragment m/z in the component
table** and it is a fixed ion again; the rows say so when it is not, and
*Measure* names the samples it moved between.

The measurement itself is not saved with the project — pressing **Write into
results** is what puts the rows in, and that is one line in the
[[audit-trail]] naming the pairs, the basis and the tolerance. Reading and
averaging seven real infusions and measuring two pairs in each took 36
seconds, nearly all of it reading the files.

## What it cannot do

**It cannot separate isomers.** Deoxycholic and chenodeoxycholic acid are the
same formula, the same precursor and the same ladder. A chromatogram tells
them apart; a spray does not. Every ratio measured here is the ratio of
everything in the vial with that composition, and where the method's
component table names two isomers the rows for both will be the same number.
That is the single largest reason a chromatographic method exists.

**Ion suppression is shared, not removed.** The analyte and its standard are
sprayed together, which is exactly what makes the ratio worth having — a
matrix that halves one halves the other and the ratio survives. It also means
the pair cannot report that it happened: the responses fall together and the
ratio says nothing was wrong. The absolute responses in the table are what
show it, which is why they are in the table beside the ratio and not
underneath it. See [[internal-standards-and-qualifiers]] for the response
floor that turns "the standard was there" into something a row can fail on.

**There is no qualifier confirmation and no ion ratio.** Those need two
transitions of one compound acquired together; an infusion has one spectrum,
and the ladder rungs are not independent of each other.
