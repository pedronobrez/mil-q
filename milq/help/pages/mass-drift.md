---
title: Mass drift
---
The **Mass drift** tab of the [[analytics-workspace]] asks whether the mass
axis moved during the run. Nothing is measured until **Measure** is pressed:
reading the survey spectrum of every internal standard in every injection
is a minute's work on a real batch, and a tab that did that on every change
to the results would be a tab nobody kept open.

## What is measured

For each internal standard — it is in every vial at one amount, so its ion
is there to measure in every injection — the precursor's mass is read from
the survey scan at the time the standard's own transition peaks, exactly as
the [[accurate-precursor]] page describes, once per injection rather than
once per batch. The injections are in the order the instrument ran them,
from their acquisition times.

The reference is **the batch's own median**, not the written precursor: a
method value typed to two decimals is good to ±14 ppm at m/z 350 and says
nothing about drift, while a change across the run is measured against
itself to well under a ppm. Where the component carries a formula and an
adduct, the exact mass is known too, and the median's **error** against it
is reported — an offset, which is a different finding from a drift.

## What the table says

| Column | Meaning |
|---|---|
| n | injections where the survey found the ion |
| Median m/z | the measured mass, median over the run |
| Exact m/z, Error ppm | from the formula and adduct, when the component has them, and how far the median sits from it |
| Spread ppm | the widest gap between injections |
| Change ppm | the change across the whole run, from a line fitted to the measurements |
| ρ | Spearman's correlation of the measurement with injection order: how monotonic the change was |
| Verdict | *drift +12.3 ppm*, *steady*, or why it could not be judged |

Before any of that, the injections have to have measured **the same ion**.
On a real batch the internal standards whose survey signal was weak came
back with spreads of 100 to 500 ppm between injections, and one of them
with a fitted "drift" of −351 ppm — the search window catching whatever sat
nearest in each injection, not an axis moving. A spread over 25 ppm, the
limit the [[accurate-precursor]] consensus already uses to say the samples
disagree, makes the component *not measurable* and the verdict says why.
Only the standards that clear it go into the index.

A component is called **drifting** when the fitted change is at least
10 ppm **and** goes one way (ρ beyond 0.5) — both conditions, as for a
response on the [[batch-qc]] page: a large fitted change through scatter is
a line fitted to noise, and a strong correlation over two ppm is a trend
nobody recalibrates for. Fewer than six injections cannot show a trend, and
the verdict says so.

## The instrument mass index

One component walking is a compound; every component walking together is
the axis. The index takes, per injection, the median over the standards of
each one's deviation from its own median, and charts it under the same
rules. It needs at least three standards measured in an injection for that
injection to count. It is listed first, because it is what an instrument
drift shows up in.

## The chart

The selected component's deviation in ppm against injection order, the
median as a solid line and ±10 ppm dashed, the fitted change as a dashed
trend. A point beyond ±10 ppm is drawn in the warning colour; clicking one
selects that sample in the [[peak-review]] grid.

## Measured, then corrected only on request

This page reports; on its own it changes no mass. What to do about what it
shows is [[mass-recalibration]], whose switch sits on this same tab: it
reuses exactly these measurements, so a standard that failed the same-ion
test here is not a lock mass there either. The traffic goes the other way
too: a standard whose measurements sit more than 50 ppm from its own formula
in most injections is not the ion the formula names, and the Verdict column
here says so — a check the same-ion test cannot make, since it only asks the
injections whether they agree with each other. A measurement the product-ion
scan did not confirm is kept and counted — a drift is a drift whether or not
the confirming scan was strong enough — and the count is on the row.

The measurement is not saved with the project; it is a minute to repeat.
While it stands, the [[report]] carries a *Mass drift* section with the
same table.
