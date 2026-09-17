---
title: Compare batches
---
The day the schedule from [[acquisition-schedule]] is run, the question is
whether it helped. **Compare batches…** on the [[analytics-workspace]]
toolbar answers it: a reference project against the batch that is open,
component by component, on the things the change was meant to move.

## The reference

A project file, `.oqproj`. It is read for what it saved — the method, the
samples, the results — and no raw file is opened, so a reference whose
acquisitions have moved to another disk is still a reference. The open
batch is the current side.

Components are matched by name across the two methods. A component in one
method and not the other is listed as only there, and a standard added
since is compared as an analyte on the side that did not have it.

## What is compared

| Column | Meaning |
|---|---|
| Found ref., Found now | rows with a peak, each side |
| Points ref., Points now | the median number of points on the peak — at or above one per cent of its height — which is what a new schedule is meant to raise; see the *Sampling* tab of [[batch-qc]] |
| %CV ref., %CV now | the scatter over the rows meant to agree — every spiked injection for an internal standard, the quality controls for an analyte — which is what more points are meant to lower |
| Area ref., Area now, Δ area % | the median area each side, and the change; a component past 20% is marked, since a new schedule that changes the *level* of a response and not only its precision is worth knowing about |
| RT ref., RT now, ΔRT | the median retention time each side, and the shift — a column that has aged, or a gradient that changed |

The totals above the table give the same four figures over the whole
method, side by side. **Export CSV…** writes every row, and while the
comparison stands the [[report]] carries it as a *Batch comparison*
section — the document to take to the meeting after the scheduled run.

## Reading it

The comparison says what moved; it does not say why. A batch that found
more rows may have had a wider window or a better acquisition; a %CV that
fell may be more points on the peak or a better preparation. What it does
settle is whether the change made a difference at all, and on which
components — which is the question a schedule, a method edit or a new
column poses, and the one that a single batch cannot answer about itself.

The same shape as [[compare-algorithms]], which puts three algorithms
side by side on one batch; this puts two batches side by side on one
method. A tray of infused standards is a batch of another kind, and
[[compare-infusions]] puts two days of those side by side — matched by
compound and by collision energy, and scored on the spectra rather than on
the areas.
