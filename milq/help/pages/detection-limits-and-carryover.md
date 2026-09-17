---
title: Detection limits and carryover
---
Two numbers a laboratory is asked to defend, computed where the data
supports them and withheld where it does not.

## Limits of detection and quantitation

For each component with a [[calibration]] curve, the limit of detection is
3.3σ/S and the limit of quantitation 10σ/S, as ICH Q2 defines them, where
S is the curve's slope and σ the standard deviation of the residuals about
its own line. ICH allows σ to come from blanks, from the intercept or from
the residuals; the residuals are used because they are the only one every
curve carries with it.

| Situation | What is reported |
|---|---|
| a linear or through-zero curve with three or more standards | LOD and LOQ, with σ and the slope |
| the same, with fewer than three degrees of freedom | the limits, and a note saying how few — three points on a two-parameter line leave one, enough to compute and not enough to trust |
| a weighted fit | the limits, noting that the residuals were taken unweighted |
| a quadratic | none: it has no single slope |
| fewer than three standards, or no curve, or a zero slope | none, with the reason |
| an internal standard | left out: its curve is flat by construction |

**Extrapolated.** A limit that lands below the lowest standard has not been
demonstrated by that curve, only extrapolated from it, and is marked as
such. A curve says nothing about concentrations nobody put on it, and
reporting a limit under the lowest calibrator without saying so is how a
method comes to claim a sensitivity it has never shown.

## Carryover

The measure regulators ask for: the blank injected **immediately after the
highest standard**, its response as a percentage of the response at the
**lowest calibrated concentration** — not against the standard that caused
it, which would make a sensitive method look worse the higher its top
calibrator went. The limit is 20%. Blank, Double Blank and Solvent all
count as blanks; internal standards are not checked.

The order of injection comes from the acquisition times. A blank somewhere
else in the run is not this test and is not reported as though it were;
and a run with no blank after the top standard comes back with *no blank
was injected after the highest standard; inject one to measure carryover*
rather than a number from the nearest blank. A carryover figure nobody
measured is worse than none.

## Where they appear

Both are sections of the [[report]] — *Detection and quantitation limits*
and *Carryover* — computed from the session when the report is written, so
they reflect the curves and results as they stand.
