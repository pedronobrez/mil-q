---
title: Acquisition schedule
---
The *Sampling* tab of [[batch-qc]] can say that a batch put one point on
each peak and what cycle time the peaks would need. Saying it is not the
same as fixing it. The fix is a **scheduled acquisition** — each transition
acquired only around its retention time, so that the instrument's cycle
is shared among fewer transitions at any moment and each gets more of it —
and the instrument software takes that as a table. **Export schedule…** in
the [[method-workspace]] builds the table from the method and says, before
it is saved, what a target cycle would leave each transition.

## What is in it

Every component with a retention time, acquired over its window
(RT ± half-width) — the same window the integration uses, and the one
[[suggest-from-data]] widens to what the sampling can resolve. Components
with no retention time cannot be scheduled and are listed as left out.

| Column | Meaning |
|---|---|
| ID, Group | the component and its group |
| Q1 (Da), Q3 (Da) | precursor and fragment; a component with no fragment is written with its precursor in both |
| RT (min) | the expected retention time |
| Window start, Window end (min) | when the transition is acquired |
| Dwell (ms) | what the target cycle leaves each transition at the busiest moment |
| Internal standard | `yes` on the standards |

## The arithmetic

At any moment the instrument cycles through the transitions whose windows
contain that moment, spending a **dwell** on each and a **pause** moving
between them, so the cycle time is the busiest moment's count × (dwell +
pause). Given a **target cycle**, the dwell follows; given a **dwell
floor** — the shortest dwell worth acquiring, since below it a transition's
counting statistics are worse than the peak it measures — the shortest
cycle the busiest moment allows follows too.

The dialog shows the busiest moment (how many at once, and when), the
dwell the target leaves, and, when that is under the floor, the cycle that
can actually be reached and what would change it: narrowing the windows
where they overlap, or dropping transitions. The dwell written is the
busiest moment's, for every row alike — a transition acquired alone could
have more, but a schedule that varies the dwell by moment is one the
instrument software does not take.

## The target cycle

Prefilled from what the batch measured: three points on the peak's flanks
— the minimum a Gaussian fit needs, at any phase of the scans — for peaks of
the median width the sampling report found. When most of the batch's peaks
were narrower than a cycle, that width is a bound on the wider ones and the
cycle that follows is an **upper bound**; the dialog says so, because the
number is going to be typed into an instrument. Type a shorter one, or the
one for ten points across the base, as the method warrants.

## Afterwards

When the scheduled batch has run, [[compare-batches]] puts it against the
one it was meant to improve on: points on the peak, the replicates' %CV,
rows found, and where the peaks moved.

## What the file is not

A plain CSV whose columns are named so that a spreadsheet maps onto the
vendor's table. It is not claimed to import directly into Analyst or SCIEX
OS, and no instrument-specific overhead is modelled beyond the pause. In
Analyst the detection window is a single method-wide setting rather than a
column: the widest window here is the one to type. The [[design-principles]]
say why a stated difference beats an invented import format.

The figures — transitions with a time, the busiest moment, the dwell the
target cycle leaves — are also a section of the [[method-report]], beside
everything else the method can be read to say before it is run.

## The other half of the acquisition

This page decides *when* each transition is acquired. What it is acquired
*at* — which collision energy, and under which activation — is the same
question asked of the infusions rather than of the separation, and
[[collision-energy]] answers it from the standards that were actually
sprayed.
