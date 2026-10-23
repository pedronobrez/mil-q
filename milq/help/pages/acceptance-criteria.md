---
title: Acceptance criteria
---
The **Acceptance** panel of the [[analytics-workspace]] holds what a row has
to satisfy to pass review. Every limit of zero is off, so a fresh method
flags nothing until the criteria are actually stated.

| Criterion | Flag when |
|---|---|
| **Max ΔRT** (min) | the apex is further than this from the expected retention time |
| **Accuracy ±** (%) | for a sample with an expected concentration, the accuracy is further than this from 100%; or no concentration could be read at all |
| **Min. S/N** | the signal-to-noise is below this — or could not be measured, which is flagged as *S/N not measured* rather than passed, see [[signal-to-noise]] |

One more check runs without a criterion being set: a row normalised
against an internal standard that declares a **Min. response** is flagged
*IS 40 below its floor of 100* and fails when the standard gave less than
its floor in that injection — a ratio to a standard that is not there is
not a measurement. See [[internal-standards-and-qualifiers]].

**Apply to component** writes them as the selected component's own;
**Apply to every component** writes them as the method's defaults and
clears every override.

## Status

| Status | When |
|---|---|
| **Fail** | any flag, a failed ion ratio, or a row that did not integrate at all |
| **Marginal** | no flags, but the qualifier's ion ratio is in the marginal band |
| **Pass** | criteria were checked and nothing flagged |
| *(none)* | no criterion applied to this row |

A method that has not been given criteria reports **no status at all rather
than a green light**: a method that has not been told what to check has not
checked anything, and saying otherwise would be worse than saying nothing.
The one exception is a row that failed to integrate, which always fails. A
criterion that cannot be evaluated on a row — an accuracy on a sample with
no expected concentration — does not count as checked either.

The **Flags** column spells out the reasons: `RT +0.312 min`, `S/N 4`,
`accuracy 71%`, `ion ratio 44.1%`, `not integrated`, `no concentration`,
`S/N not measured`, `IS 40 below its floor of 100`. Ion ratios and their tolerances are explained on
[[internal-standards-and-qualifiers]].

## Whether a concentration can be reported

Four checks run on every row with a curve, whether or not any criterion is
set, because they are not criteria: they say whether the number in
**Calculated** is a measurement at all. Each fails the row.

| Flag | When |
|---|---|
| `negative concentration` | the curve read the response back below zero |
| `< LLOQ (1.85 ng/mL)` | under the lowest standard the curve uses — by concentration in the vial (the dilution factor taken back out), **or** by response, under what the lowest standard actually gave. The second catches a negative intercept carrying a response under the lowest standard's to a concentration above it |
| `> ULOQ (400 ng/mL)` | over the highest standard the curve uses |
| `the curve's intercept, not the sample's response` | the response is under a tenth of the curve's intercept, so the concentration is the intercept read back: every sample gives the same value, and it can be positive and look plausible |
| `IS PGE2-d4 5,000 here against 3 in the curve` | the internal standard in this row differs from its median over the calibration standards by more than ten times either way — spiked into one and not the other |
| `IS 5-oxo-ETE-d7 absent here, 107 in the curve` | the standard has no area in this row |
| `IS 12-epi-LTB4-d4 not above the solvents in the curve (5 against 1)` | the standard's median in the calibration standards is under ten times its median in the solvents and double blanks: it was not spiked at all |

The limits were measured on one eicosanoid batch: a standard present in
both kept within 1.4× (TXB2-d4, ~460 counts in the curve and ~440 in the
samples), and the mismatched ones were 1,500×, 50× and present on one side
only. Blanks, double blanks and solvents are expected to read nothing and
get none of the concentration flags; solvents and double blanks are not
spiked and get none of the standard's. A standard's own rows are not
flagged for its concentration. A project saved before these checks shows
them once anything is recalculated — **Calibrate** is enough.

## Reviewing by status

**Show** in the [[results-table]] narrows the table to one status; the
[[report]]'s summary counts them and its findings section lists what
failed. The statuses are recomputed whenever anything upstream changes — a
parameter, a curve, a standard — so a status is never older than the number
it judges.
