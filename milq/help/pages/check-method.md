---
title: Check method
---
**Check method** in the [[method-workspace]] reads the method against itself
and against the open files, and says what it will fail at before a batch is
processed. Everything it reports would otherwise be learned from the
results, which is later and harder.

## What is checked

| Finding | Severity | Meaning |
|---|---|---|
| shared transition | serious | two components declare the same precursor and fragment and have nothing — no retention time, or the same one — to separate them; the integration will return the same peak under both names |
| missing internal standard | serious | a component names a standard that no component carries, or one that is not ticked IS |
| internal standard without a time | serious | a standard with no retention time is searched over the whole run, and takes the largest peak anywhere in it; every component it normalises inherits that. The count of components it carries is given |
| internal standard without a response floor | warning | a standard that serves components declares no **Min. response**, so the quality charts and the acceptance fall back to a signal-to-noise of ten — which on a scheduled acquisition is an absolute height against an arbitrary constant. See [[internal-standards-and-qualifiers]] |
| formula against precursor | serious | a component's **Formula** and its **Precursor** are further apart than that precursor's own last written decimal allows. One of the two is wrong, and they do different work: the precursor picks the acquisition channel and, where no fragment is written, builds the extraction window; the formula is the true mass the [[mass-recalibration|recalibration]] corrects towards. *Repair precursors…* in the [[method-workspace]] lists them with both masses and writes the formula's where a row is ticked. A row a whole dalton or more out is the case where the mass is likely to be the right one — it is what the instrument was set to acquire — so there the *name* is the error, and the dialog offers the names whose formula does match the written mass |
| internal standard without a formula | warning | the standard cannot be a lock mass. Without a formula and an adduct nothing says where its mass belongs, and the written precursor cannot stand in — one typed to a single decimal is good to a few hundred parts per million, a hundred times the error being corrected. *Fill formulas from names* in the [[method-workspace]] derives one wherever the name is lipid shorthand |
| no retention time | warning | the component's window is the whole run, so the largest peak in the run is the component whatever it is |
| precursor outside the survey scan | warning | with files open: components whose precursor no survey scan covers, and the ranges the surveys do cover. The accurate mass, the LIPID MAPS annotation and the [[mass-drift]] cannot be measured for them; the transition itself is unaffected. An acquisition with no survey scan at all is reported under the skipped checks instead |
| window too narrow | warning | at the sampling interval measured from the open files, the ±window holds fewer than eight points; below five the detector declines outright |

Severities: a **serious** finding will produce wrong numbers; a **warning**
will produce numbers that are harder to defend.

## What is skipped, and said

Checks that need the files — the sampling interval, hence the window
check — are skipped when no sample is open, and the dialog lists what it
could not check rather than staying quiet about it. A method that "passes"
with half the checks unrun has not passed.

## Acting on the findings

- A shared transition needs a retention time on each component, and
  different ones.
- A standard with no time needs one: [[suggest-from-data]] estimates times
  from the open injections and says how far each estimate can be trusted.
- A window too narrow for the sampling can be widened by the same dialog,
  which computes the half-width that gives eight points.
- A missing standard is a spelling mistake or a missing tick, fixed in the
  table.
- A standard with no formula gets one from *Fill formulas from names* where
  its name says what it is made of; the rest are typed.
- A formula that disagrees with its precursor is a question only the person
  who wrote the method can answer — which of the two is right. *Repair
  precursors…* in the [[method-workspace]] puts the question row by row, with
  both masses, the difference in mDa and ppm and the extraction window before
  and after, and writes the formula's mass into the precursor where a row is
  ticked. It ticks the rows under half a dalton for you and leaves the rest
  to you, because under half a dalton is one compound written to fewer places
  and past it is two different compounds. On the batch this was developed
  against the disagreement was reported by *Fill formulas from names* rather
  than by this check — the check reads a formula the table already carries,
  and the fill refuses to write one it cannot confirm — and 13 of those 16
  refusals were the precursor written to fewer decimals than it deserved: `dHCer(d18:0/12:0)` carried
  484.465 against the 484.4724 of its own formula, 15 ppm out, and
  `C25:0-Ceramide` carried 664.4 against 664.6602, 392 ppm out. Repairing
  those thirteen changed no result in the batch at all — every row carries a
  fragment, so no window moved, and every repaired precursor stayed within
  the 0.7 Da that picks the acquisition channel — and it took the method from 125
  formulas to 138 of 141, and from 10 of its 11 internal standards carrying
  one to all 11. The other three
  were a whole dalton or more out, and repairing them took two of them off
  every acquired channel and onto the survey scan; the [[method-workspace]]
  has the figures. A whole-dalton disagreement is a question about the *name*
  as often as about the mass, and where it is, the finding says so and the
  dialog's *Rename to* column answers it: the names whose formula matches the
  mass that was written, the row's own class first and [[lipid-maps|LIPID
  MAPS]] after it. On the three whole-dalton rows of that method it offers
  `LacCER(d18:1/18:2)` for the `LacCER(d18:1/18:1(9Z))` written 886.6407,
  −17.7 ppm — and nothing at all for the other two, which is the more useful
  half of the answer. `LacCER(d18:0/18:1)` is out by one odd dalton, and a
  chain is 14 Da, a double bond 2 and a hydroxyl 16: no name in that class
  can be one dalton away, so the digit is the mistake rather than the
  compound. `C18:1 Cer` is out by a hundred, past what a misnamed chain can
  be. A rename moves no number — same precursor, same fragment, same window,
  same channel — and reprocessing the batch after it left 78 of 78 rows
  identical; what it buys is a row whose formula agrees with its own mass.

The check runs on the method as it is, so it can be run again after each
correction. The same findings appear at the head of the [[report]]'s
method section, so a report carries its own warnings, and the whole of
what is here — grouped by severity, with every flagged row marked in the
component table — is the second section of the [[method-report]].
