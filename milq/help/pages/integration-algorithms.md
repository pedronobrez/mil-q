---
title: Integration algorithms
---
Once a peak has been found there is more than one way to arrive at its
area. Three are offered, chosen per component or for the whole method
under **Algorithm** in the [[integration-parameters]] panel, and every row
of the [[results-table]] says which one produced its number — the one that
actually ran, so a fit that could not be made and left the valley area
standing is labelled *valley* with the reason on the row.

## Valley to valley

The default, and what the program always did: walk out from the apex to
the valleys either side, draw a straight baseline between them, and take
the trapezoid area of the trace above it. Nothing in a saved project changes
its numbers by this being named. It is the right answer for a well-sampled
peak and the only answer for a peak of one point.

## Summation over the window

No peak finding at all. The component's retention-time window is the
boundary, the baseline is the line between its two ends, and whatever is
above it is the area. It is the arithmetic of manual integration applied to
the declared window, and what MultiQuant's algorithm of the same name does.

Its virtue is that no detection setting can move it: the method decided
the window and the window is the answer. Its cost is that it sums whatever
the window holds — on a ±0.5 min window of four scans, baseline as well as
peak — and that where the window's ends land on a peak's flanks the line
between them sits above the peak and there is nothing to sum. A component
with no retention time has no window, and the row says *summation needs a
retention-time window*. The signal-to-noise gate is honoured, measured the
way the detector measures it, so a window of baseline is not reported as a
peak; an operator who wants the sum regardless sets Min. S/N to zero.

## Gaussian fit

The peak is found as valley does it, and then a Gaussian is fitted to the
points inside its boundaries, above the same straight baseline; the model's
area — height × σ × √2π — is reported instead of the trapezoid's, and its
centre as the retention time, its full width at half height as the width.
The fit is Levenberg–Marquardt with the analytic Jacobian, started from the
parabola through the logarithms of the apex and its neighbours.

### Why it exists

On a trace sampled every fifteen seconds a peak is two or three points
wide, and a trapezoid over them depends on where the scans happened to land
relative to the apex, which is an accident of the acquisition. Measured on
synthetic peaks at 14.6 s sampling, over sixty phases of the scans:

| Width at half height | Trapezoid spread with phase | Fit, where it could be made |
|---|---|---|
| 11.3 s | 16.8% | exact (34 of 60 phases) |
| 14.1 s | 5.1% | exact, 0.00% spread (all 60) |
| 17.0 s | 1.1% | exact (all 60) |

With Poisson noise on a thousand-count peak, at 14.1 s wide: trapezoid
5.8%, fit 3.0%. Above 17 s both are limited by the counting noise and the
fit adds nothing. On a tailing peak the fit is a stated approximation: the
area stays within about 2% up to a tail twice the width of the core, and
the fit's r² says how far from Gaussian the peak was.

### When it is not made

The fit needs **three points on the peak** — above the baseline and at
least 1% of the apex. Two points and a width make a Gaussian, and the zeros
beside them say no more than that the width is small, so a fit to two
settles wherever it started: measured at 14.6 s sampling, biased low by
seven per cent. And a third point at a fraction of a per cent of the apex
is the peak's foot rather than its flank. On the batch this was written
for, the one internal standard with a real response — 52,000 counts on one
scan — had neighbours of 44 and 98, the same size as the baseline blips
further along the trace, and the first version of the fit put a curve
through those three points exactly, r² = 1.000, and reported an area a
third smaller. A width taken from three points with three parameters is a
width taken from the noise.

So a fit that is not determined by the peak is not made. The row keeps the
valley area, is labelled *valley*, and says why: *1 point(s) above the
baseline, 3 needed*, or *narrower than the sampling resolves: 2 point(s)
above 1% of the apex*. And a fit through exactly three points is reported
as **exact through 3 points** rather than with an r² that means nothing.
At 14.6 s between scans, a peak at least about 17 s wide at half height can
always be fitted, and a narrower one only when the scans land on its
flanks.

## Which to use

- A method whose peaks are several points wide: valley, or the fit where
  the [[compare-algorithms]] dialog shows it repeats better.
- Peaks one or two points wide: nothing does better than valley, and the
  comparison will say so in numbers rather than opinion.
- A reviewer who wants the window's whole content with no detection
  decision in it: summation.

What the choice did on a real batch — 400 of 2,638 rows fitted, 2,169 too
few points wide to fit, and no component moved by more than 20% — is on
[[measured-facts]]. The algorithm did not move that batch's numbers; the
sampling did.
