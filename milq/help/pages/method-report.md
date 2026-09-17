---
title: Method report
---
**Method report…** in the [[method-workspace]] writes everything this
program can say about a method *before* the method is run, as one PDF or
one HTML file. Nothing in it is a new check: it runs [[check-method]],
*Fill formulas from names*, *Repair precursors…* and the
[[acquisition-schedule]] and lays their answers out in one document — the
thing to hand to whoever wrote the method, to file beside it, or to read
six months later when a batch acquired under it is being defended.

It does not grade the method. There is no score, no badge and no traffic
light, and the closing section is a paragraph of plain sentences, each one
counting something measured higher up the page. A method with eighty-two
components that carry no retention time may be exactly right — it may be a
screening method — and a green tick would invite nobody to read the
eighty-two.

It does not change the method either. *Fill formulas from names* writes
into the cells it is given, so the report gives it **copies**: it can say
how many formulas could be derived without deriving any of them.

## The sections

| Section | What is in it |
|---|---|
| Components | the table as the method declares it — name, precursor, fragment, adduct, formula, RT ± window, IS, group, response floor, and where the formula came from. A row [[check-method|the check]] flagged carries `!` for a serious finding and `†` for a warning |
| What the check finds | every finding grouped by severity, with the count of *findings* in the heading, each one's explanation, and the components it names. Checks that could not run — the ones needing an open file — are listed as not run rather than passed |
| Formulas | how many components carry a formula, how many more their own names would supply, and every refusal with **both** masses: what the formula weighs and what the method wrote, in mDa and ppm, and whether the likelier error is the mass or the name |
| Lock-mass candidates | each internal standard carrying a formula, with its neutral mass, its adduct and the exact m/z that follows — and the sentence saying that being a candidate is not being a lock mass |
| The acquisition | with a file open: which channel serves each component ([[explorer-components-and-results|matching]] on precursor and time), what the survey scans cover, and which precursors fall outside them |
| The schedule | the [[acquisition-schedule]] the method implies: transitions with a time, how many are acquired at once at the busiest moment and when, and the dwell the target cycle leaves each of them |
| What the method is missing | the closing paragraph, one sentence per measurement |

## What needs a file, and what does not

The components, the findings that read the method against itself, the
formulas and the lock-mass candidates need nothing but the table. Open a
file and the report gains the acquisition section, the window check and
the survey ranges; process a batch and the schedule's **target cycle**
comes from the width the batch's own peaks measured
([[batch-qc|Sampling]]) instead of a round ten seconds. With nothing open
the document says which sections are missing and why.

The first open sample is the acquisition, which is the same one
[[check-method]] uses.

## Why a candidate is only a candidate

Whether a standard *could* anchor a mass axis is a property of the method:
it needs a formula and an adduct, because a precursor typed to one decimal
is good to a few hundred parts per million and the error a
[[mass-recalibration|recalibration]] corrects is a few. Whether it *is* a
lock mass is a property of a batch — the survey scan has to reach it, the
same ion has to be measured in every injection, and that ion has to sit
near the mass its own formula names. None of those three can be read from
a method, and the section says so in those words rather than implying an
answer.

Where a standard declares no adduct, the m/z is priced through the adduct
its written precursor reads as, marked with an asterisk. An adduct guessed
from a rounded mass is a guess: type it into the table.

## On the real method

The 141-component sphingolipid method, against the first injection of its
26-injection batch: 15 printed pages in about five seconds, the reading
itself a fraction of a second. Three serious findings and four warnings,
touching every one of the 141 rows — 89 with a serious finding, 52 with a
warning, none clean. No component carries a formula and 125 would take one
from their own name, leaving 16 whose name and written precursor
contradict each other, 3 of them by a whole dalton. No standard can be a
lock-mass candidate, because none carries a formula. All 141 components
are served by a channel of their own, and 72 precursors lie outside the
50–700 survey. Scheduled, 59 transitions with 82 left out for having no
time, at most 24 acquired at once at 4.70 min, and the cycle the batch's
own peaks suggest — 12.4 s — leaves each of those 24 about 512 ms of
dwell. Type 3 s instead and the same 24 get 120 ms, which is the figure in
[[measured-facts]].

## Where it goes

A PDF or an HTML file, chosen in the save dialog; the HTML opens in a
browser on its own. Writing one is recorded in the [[audit-trail]] as
*Method report*, with the number of components, the findings and the
acquisition it was built against. It is a different document from the
[[report|batch report]], which answers what a run measured; this one
answers what the method asks for.
