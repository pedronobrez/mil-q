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

## Reviewing by status

**Show** in the [[results-table]] narrows the table to one status; the
[[report]]'s summary counts them and its findings section lists what
failed. The statuses are recomputed whenever anything upstream changes — a
parameter, a curve, a standard — so a status is never older than the number
it judges.
