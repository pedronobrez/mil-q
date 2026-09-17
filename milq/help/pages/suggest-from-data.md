---
title: Suggest from data
---
**Suggest from data…** in the [[method-workspace]] proposes two things the
open injections can supply: retention times for components that have none,
and window half-widths that the sampling can resolve. Nothing is written
until a row is ticked and **Apply** pressed, and nothing comes pre-ticked
unless the estimate has proved itself on this batch.

## Retention times

For each component without a time, every peak in every open injection is
found — not only the tallest — and the estimate is the time at which the
most injections agree to within one sampling interval. Agreement across
injections, rather than intensity, is what decides whether a time means
anything: a transition sampled every fifteen seconds gives a peak of one or
two points, and intensity alone cannot tell a peak from a spike. A time is
offered only when at least half the injections support it.

### Calibrated, not asserted

Before proposing anything the estimator is run on the components that
**already declare a time**, and how often it landed within one sampling
interval of the declared time is recorded — in bands of peak height,
because height is what decides whether a time can be estimated at all:

| Peak height | On the batch this was written for |
|---|---|
| 0 – 100 counts | 45% within one interval (n = 20) |
| 100 – 1,000 | 54% (n = 13) |
| 1,000 – 10,000 | 54% (n = 13) |
| above 10,000 | 88% (n = 8) |

Each proposal then carries the accuracy the estimator achieved in **its own
height band on this batch**, and the dialog's first sentence states the
whole table. A row is pre-ticked only when its band has at least 60%
within one interval and enough components to have measured it. On that
batch, nothing offered was above ten thousand counts, so **nothing was
pre-ticked** — which is the intended outcome: the estimator had not proved
itself at the heights that needed it, and saying so is the point of
calibrating at all.

### Shared transitions

Two components declaring the same transition get the same estimate and are
marked with a note: accepting both writes the same response under two
names, and separates nothing. They are offered, so that the reader can
choose one, and never pre-ticked.

## Windows

The second tab lists every component whose ± window holds fewer than eight
points at the sampling interval measured from the files, with the
half-width that would give eight. On a method sampling one transition every
14.6 s, ±0.50 min holds four points and ±0.97 holds eight. These come
ticked: there is no uncertainty in them, only the arithmetic of the cycle
time. Why eight, and what happens below five, is on
[[integration-parameters]].

## Into a schedule

The windows this dialog widens are the windows [[acquisition-schedule]]
acquires over: a wider window is more points on the peak and, at the same
time, more transitions acquired at once. The schedule dialog says what that
does to the dwell.

## After applying

The method changes; the batch is not reprocessed until **Process batch** is
pressed in the [[analytics-workspace]]. **Check method** run afterwards
should no longer list the components that were given times.
