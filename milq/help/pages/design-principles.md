---
title: Design principles
---
A few rules decided what this program does when two good things could not
both be had. They came out of the work — most of them out of a mistake —
and knowing them explains the choices a reader will meet.

## Measure before claiming

Every performance and fidelity number in this manual was produced by
running something, not by reading code. Two attempts at reverse-engineering
a vendor algorithm were made and both were wrong; the second looked right
until it was tested on data it had not been fitted to. See
[[measured-facts]].

## A stated difference beats an invented rule

Where behaviour could not be reproduced faithfully, the plain version ships
with the measured gap written down — the extraction rule on [[formats]] is
the example. A number that is 0.58% low and says so is worth more than one
that is sometimes right for reasons nobody can state.

## Never substitute this program's arithmetic for the instrument's

Totals, retention times and areas come from the vendor where the vendor
reports them. Summing the stored points instead moved every area by 2%.

## Say what could not be done

A criterion that could not be evaluated is not one that passed. A noise
that could not be measured is not one count. A fit that could not be made
is not a trapezoid under the fit's name. A carryover with no blank in the
right place is not a number from the nearest blank. In every case the row
says so — [[signal-to-noise]], [[integration-algorithms]],
[[detection-limits-and-carryover]] — and the [[report]] prints the reason
where a table would otherwise be empty.

## A flag that fires on every batch is read on none

The QC rules carry two conditions each — statistically unusual **and**
practically different — because either alone flagged ordinary injections
on real runs. See [[batch-qc]].

## Confidence is measured, not asserted

A proposal from the data carries the accuracy the same estimator achieved
on the parts of the batch where the answer was already known. When it had
not proved itself, nothing is pre-ticked. See [[suggest-from-data]].

## A policy nobody can review is not a policy

When the program decides something a reader might have decided otherwise —
proximity over size, a fit over a trapezoid, an exclusion — the row says
what it did and what it passed over.

## Nothing changes a saved project's numbers by surprise

Every new setting defaults to what the program did before it existed:
*largest* peak, *valley* integration. A batch reopened in a newer version
reports what it reported, and [[version-history]] says which version
brought each of them in.
