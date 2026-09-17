---
title: Batch QC
---
Per-sample review cannot see a response that falls away across ninety
injections: every point is inside its limits and the batch is still not the
batch it started as. The **Batch QC** tab of the [[analytics-workspace]]
looks at the run as a run — the internal standards against the order the
instrument injected, the injections taken together, and the precision of
the quality controls.

## Injection order

The order comes from the acquisition times the files carry; where some
carry none, the tab says so and falls back to the order the files were
opened, which is usually the same order. A batch of fewer than six
injections cannot say what normal looks like, and the tab says that too.

## Control charts

One chart per internal standard: its area in every spiked injection —
Unknowns, Standards, Quality Controls and Blanks; not double blanks or
solvent injections, which never saw the standard and would put two zeros in
the middle of the run — against injection order, on the pattern of a
Levey–Jennings chart.

**The centre is the median and the spread the median absolute deviation**,
scaled to a standard deviation, so that one bad injection cannot widen the
limits meant to catch it. Then:

| Verdict | Condition |
|---|---|
| warned | beyond 2σ **and** at least 10% from the centre |
| out | beyond 3σ **and** at least 20% from the centre — or at least 50% from it however small the spread |
| drifted | the change fitted across the whole run is at least 20% of the centre **and** goes one way: Spearman's ρ beyond 0.5 |
| unusable | a third or more of the chart is out |

The two conditions on every verdict were learned on real batches. A batch
that repeats itself well has a spread so small that three of them is a
difference nobody would act on: measured on one run, a median absolute
deviation of 0.8% turned a standard 2.4% low — an ordinary injection — into
a four-sigma outlier, and would have on almost every batch. The 50% rule is
the mirror: a batch whose own scatter is wide swallows a real failure, and
an injection where every standard came back at a fifth of normal sat at
2.6σ. And when seventeen of twenty-six injections are out, listing
seventeen outliers misses what they say together, which is that nothing can
be normalised against this standard — so the chart is reported as unusable
rather than the injections.

A standard whose median signal-to-noise is below 10 is charted but not
flagged: below the limit of quantitation a small absolute change is a large
relative one, and every flag against it would be arithmetic on noise. On
the batch this was written for, eight of eleven standards had a median
response between 4 and 52 counts and produced almost every flag in the run.
Whether that gate does what it says depends on the noise being measurable
— see [[signal-to-noise]] — which is why a **response floor declared in the
method** replaces it: a standard with a **Min. response** is usable when
its median clears the floor and not otherwise, the verdict says *below its
floor of 100*, and on a usable chart the injections that fell under the
floor are listed. See [[internal-standards-and-qualifiers]].

## The injection response index

One standard's chart cannot tell an injection that failed from a compound
that misbehaved: both are a point far from the centre. The index divides
each internal standard by its own median and takes the median of those per
injection, so all-standards-down-together is separable from
one-standard-down-alone. It needs at least three standards to be a median
at all, and is charted under its own name with the same rules.

On the batch it was written for, the standards taken separately scattered
between 32% and 228% and looked hopeless; taken together the injections sat
within ±18% with three exceptions, one of them at 0.08 where every standard
had gone at once.

## Controls

| Control | Effect |
|---|---|
| **Component** | which chart is drawn; the table below lists every chart with its centre, spread, drift and verdict, and clicking a row draws it |
| **Recheck** | recompute from the current results |
| **Exclude failed injections** | untick every row of every injection the index calls out, marking each with the reason; enabled only when there are any, confirmed first, and rows integrated by hand are left alone — somebody looked at those |
| clicking a point | selects that sample in the [[peak-review]] grid |

## Precision

The second tab: for each component, the %CV of its response over the
quality controls — quality controls only, since unknowns differ by design
and standards by construction — against a limit of 15%, from at least three
replicates. A component with fewer says so.

## Sampling

The third tab measures the one thing three other findings kept running
into: how many points the acquisition put on each peak. For every
component, the cycle time of its channel (from the channel's own time
axis), the median width of its peaks at half height, and the median number
of **points on the peak** — points at or above one per cent of its height,
the ones that are the peak rather than its feet, counted at integration
and carried on every row of the [[results-table]]. A Gaussian fit needs
three of them ([[integration-algorithms]]); quantitation textbooks ask for
about ten across the base.

The last columns are the cycle times that would give each, for peaks of
that width: a fit at every phase of the scans needs the cycle no longer
than 0.85 of the width at half height, and ten points across a base of
four sigma need 0.17 of it. A peak with only one point above half height
has no measurable width — it is narrower than a cycle — and is counted in
the last column instead; the widths are then of the wider peaks only, and
the cycle times that follow are upper bounds.

On the batch this was written for: one scan every 14.6 s, **a median of one
point on the peak**, 129 of 139 components typically under the three a fit
needs. That is a property of the acquisition schedule, and nothing in the
processing substitutes for it — the [[report]] carries the same table under
*Sampling*, and **Export schedule…** in the Method workspace turns the
method into the table the instrument needs, with the cycle from here as
its starting point: [[acquisition-schedule]].

## Suggesting the floors

**Suggest floors…** proposes a **Min. response** for each internal standard
from what it gave in this batch: the median of its area over the spiked
injections, with the injections where every standard went at once left out
— those are what the floor exists to catch, and a median that included them
would be lower for it — and half of that median as the proposal, rounded to
three figures. Each row shows the basis: the median, how many injections
stood behind it, which were left out. Rows with fewer than six injections
come unticked. It is a proposal: the floor is what the standard gives when
the run is right, and whoever knows the method may put it higher or lower.
See [[internal-standards-and-qualifiers]].

## Mass drift

The neighbouring tab, [[mass-drift]], asks the same question of the mass
axis that the control charts ask of the response: did it hold from the
first injection to the last?

## In the report

The [[report]]'s *Batch quality* section carries the charts' verdicts, the
index, the drift, and the precision table, with the rules stated in the
section's own words.

The same arithmetic answers a slower question elsewhere. A standard infused
to verify a vial leaves one record in your own library each time, and
[[standard-history]] charts those records over the days they were acquired
— the same centre, the same two conditions before a point is out, and the
same trend rule, over records instead of injections.
