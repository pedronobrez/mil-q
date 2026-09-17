---
title: Signal-to-noise
---
Signal-to-noise appears in four places — the detector's gate, the
[[acceptance-criteria]], the [[batch-qc]] charts and the [[results-table]] —
and in all of them it is the peak's height divided by a measurement of the
noise. What the noise is, and when it cannot be measured, is the whole
subject of this page.

## Where the noise is measured

**Over the whole chromatogram**, when no noise region is set. It is
deliberately *not* measured inside the retention-time window: that stretch
is mostly peak, so its point-to-point spread reports the peak's own slope.
On real data that read 16,944 where the trace's actual noise was 505, and
the same peak came out at S/N 19 automatically against 531 by hand.

**Over a noise region**, when one is set from the [[peak-review]] grid:
right-click a panel with a stretch of baseline shaded and choose *Set noise
region from the shaded range*. **Noise as** in the Integration panel picks
the measure: *peak-to-peak* takes the full swing of the region and is the
stricter, more conservative reading; *standard deviation* is the gentler
one. Both are in use in laboratories, so which one a number came from has
to be stated alongside it, and the panel does.

## How the automatic estimate works

The noise is the median absolute deviation of the point-to-point
differences, scaled to a standard deviation — a robust estimator that a
peak cannot inflate. In a low-count XIC more than half the differences are
exactly zero, which zeroes the median; the fallback is the standard
deviation of the lower half of the points, which rarely contains a peak.

## When it cannot be measured

**The estimate is "not measured" when there is nothing to measure**, and
that is the ordinary case on a scheduled acquisition rather than the
exception. Over 846 real traces, the median trace had three non-zero points
in sixty-one, and only 9% had a baseline that varied at all. A trace the
instrument reports as exact zeros has a baseline below its reporting
threshold; there is no noise there to measure, and a number invented for
it would not be a ratio to anything.

So the signal-to-noise of a row is empty, shown as `—`, when the baseline
could not be measured. On the batch this was measured on, it could be for
23% of the peaks found.

## What the gates do without it

The detector still needs a floor to reject the smallest peaks, so where the
noise cannot be measured it uses one count as the noise. That keeps the
gate — a single-count spike on an otherwise zero trace is still rejected —
but it means **Min. S/N** is then an absolute intensity threshold wearing a
signal-to-noise name: a peak of 30 counts on a trace of zeros clears
S/N 3 at "S/N 30". Measured on a real batch, an internal standard of 30
counts and one of 42,400 counts would have reported S/N 30 and 42,400 under
that rule. The gate is kept; the number it rejects on is not reported as a
ratio.

The same applies to the acceptance criteria's minimum S/N and to the QC
charts' quantifiable threshold: both are gated on absolute height with an
arbitrary constant when the baseline is zero. What that question actually
needs is a floor on the internal standard's absolute response, and a batch
of the kind this was developed on does not supply one — its precision does
not track its response. So the method declares it: **Min. response** on
the standard, read by the charts, the acceptance and the method check. See
[[internal-standards-and-qualifiers]] and [[batch-qc]].

## The noise floor of an infusion

Everything above is about a chromatogram. A [[direct-infusion]] has none: what
is looked at is the average of every scan of the run, and *noise* there means
the height below which a peak of that average is background rather than a
measurement. That floor used to be a hundred counts, fixed, because it was
written for one survey scan of a TripleTOF. An average of four hundred scans
of a ZenoTOF is not that scan, and on the nine bile-acid infusions to hand the
**base peak of the whole averaged spectrum is 109 counts on one of them** —
so the fixed floor was very nearly the top of the spectrum.

It is now measured off the acquisition itself, two ways, and both are printed.

**(a) The empty mass regions of the average.** Every centroid at or above a
tenth of a per cent of the base peak is found and half a dalton either side of
it set aside; what is left is between the isotope clusters and away from every
peak. The median, the median absolute deviation and the 99th percentile of the
measured points there describe the background, and the 99th percentile of the
*local maxima* among them is the height a noise **peak** reaches. That last
figure is the one the floor is taken from, because what the floor gates is the
tallest point of a window and not a point drawn at random: a percentile of
single points would let most of the background through. Points of exactly zero
are left out, so a file whose stripped zeros have been restored and one whose
have not give the same answer.

**(b) The scan-to-scan scatter of a quiet window.** The quietest half-dalton
window holding no peak at all — half a dalton because that is what the
precursor search reaches either side of a target — is extracted over the whole
run, the same window in every scan, and the standard deviation of its summed
intensity taken between scans. Averaging n scans divides noise by the root of
n, so that standard deviation is divided by it in turn, and both numbers are
reported: what one scan does, and what the averaging bought.

The floor is the larger of the two. Where neither can be measured the fixed
hundred counts stands and the record says so; where the measurement comes out
**under** the fixed hundred — which is every acquisition measured so far — the
measurement is used and the report says that too, because a constant that is
larger than the spectrum it gates is not a safety margin.

### What it measures

Nine ZenoTOF 7600 product-ion infusions of bile-acid standards, positive, no
survey scan, 146 to 473 scans each, averaged whole:

| | |
|---|---|
| base peak of the average | 109 – 12,271 counts |
| (a), the empty regions | 0.068 – 3.53 counts |
| (b), the scatter, scaled to the average | 0.026 – 0.36 counts |
| the floor taken | **0.068 – 3.53 counts**, (a) on nine of nine |
| what one scan scattered by, before averaging | 0.45 – 5.05 counts |
| the fixed floor it replaces | 100 counts |

The averaging is where the two estimates part company. On
`CA-d4_TOFMSMS_Mix1`, 473 scans, one scan's half-dalton window moves by 5.05
counts and the average of 473 of them by 5.05 / √473 = 0.23; the empty regions
of that same average reach 0.96. Estimate (a) can only see what is left after
the averaging, and (b) reads the averaging itself — which is why both are on
the record and the larger is taken.

Twelve chromatographic acquisitions for contrast, on another instrument and a
real gradient: a TripleTOF 5600, the strongest product-ion channel of each
averaged over the boundaries of its own largest peak. Eleven of the twelve are
measured, at (a) 0.69 to 20.1 counts against (b) 0.23 to 3.25 — (a) the larger
on eleven of eleven, as it was on the infusions. The loudest of them averages
the thirteen scans of a peak 567,000 counts tall and comes out at **20.1
counts**: three hundred times the floor of the quietest infusion, for the plain
reason that an average of thirteen scans is not an average of four hundred. The
fixed hundred was still five times too strict there.

The twelfth is where the fallback shows, on a real file rather than in a test.
Its strongest product channel holds a peak of 352 counts over three scans; the
average of those three has 167 measured points in 412 and no empty region wide
enough to measure in, so neither estimate can be made and **the fixed hundred
counts stands**, with the reason printed beside it. A quiet acquisition and an
acquisition with nothing in it are not the same thing, and only one of them
gets a measurement.

### Where the floor is applied

- the precursor read off an averaged product-ion spectrum, in
  [[infusion-report]] and [[accurate-precursor]] — a window holding less than
  the floor is reported as too little to measure, with the height that was
  found;
- the report's list of **unexplained peaks**: a peak under the floor is
  background and is not something the explanation failed to account for;
- a record written to a library of your own from an infusion, which is held to
  the floor as well as to its one per cent of the base peak — see
  [[spectral-library]];
- the label floor of an infusion pane, which starts at the higher of the
  drawing's 2% and the noise floor, with the status line saying which it was.

The floor is measured on **the same average the caller is looking at**, which
is why two of them can differ on one file. The Explorer pane averages the
whole run; the [[infusion-report]] averages the stable stretch of the spray
(*Scans a spray lost* in [[direct-infusion]]), so the scans an unstable spray
contributed are out of its average and out of its floor as well. On the nine
infusions the whole-run floors are 0.068 to 3.53 counts and the report's are
0.068 to 4.27
— the same on the six runs the mask left alone, and higher on the three it
trimmed, because throwing scans away is throwing away some of the averaging.
That is the answer being right rather than the numbers disagreeing: a floor
that described a different spectrum from the one printed would be the wrong
floor.

### What it does not say

The floor is one number for a whole spectrum, and a background is not the same
at every mass: on the two acquisitions of the nine that hold nothing at all,
the empty regions are the high-mass end where the detector saw nothing, so the
floor comes out at 0.07 and 0.13 counts and the peaks of the chemical
background — a hundred counts of it — stand far above it. **A peak above the
floor is a peak above the background, not the compound.** What says whether it
is the compound is its mass: on those two files the ion in the precursor's
window clears the floor by two orders of magnitude and sits 43 ppm from the
written precursor, and it is the parts per million that answers the question.

## Acceptance

An acceptance criterion on S/N that cannot be evaluated flags the row **S/N
not measured** rather than passing it quietly: a criterion that could not be
checked is not a criterion that passed, and saying nothing would let it read
as one.
