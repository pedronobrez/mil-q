---
title: Calibration
---
A calibration curve turns a response into a concentration. It is built from
the samples typed **Standard** in the [[samples-workspace]], each with its
**Actual conc.**, and applies to every other sample of the same component.

## The Calibration tab

For the component selected in the tree: the points, the fitted line, the
equation, r and r², and a table of the standards with each one's
back-calculated concentration and accuracy. The status line says how many
curves were fitted of how many components have standards.

| Control | Effect |
|---|---|
| **Regression** | *linear*, *linear through zero*, *quadratic*, *mean response factor* |
| **Weighting** | *1*, *1/x*, *1/x²*, *1/y*, *1/y²* |
| **Remove outliers** with its tolerance | drop standards whose accuracy is outside the tolerance, one at a time, worst first, refitting after each |
| click a point on the plot, or double-click a row | include or exclude that standard; the exclusion survives a refit |
| **Recalibrate** (toolbar) | refit every curve from the standards and read the unknowns back off them, without reintegrating |

The regression and weighting are properties of the component and are saved
in the method.

## What the curve is built from

The **ratio to the internal standard** when the component has one, and the
raw **area** otherwise. This is the measured quantity, distinct from the
method's *Response* column, which says what the results table reports.

## Minimum points

| Regression | Standards needed |
|---|---|
| linear | 2 |
| linear through zero | 1 |
| quadratic | 3 |
| mean response factor | 1 |

A curve with fewer is not fitted and the panel says so. With exactly as
many points as parameters the curve passes through them whatever they are;
the [[detection-limits-and-carryover]] page needs at least one degree of
freedom to say anything about scatter.

## Weighting

Least squares gives every point the same say, and the top standard's
absolute residual is usually the largest, so an unweighted fit is a fit to
the top of the range that misses at the bottom by a wide margin relative to
the concentration there. *1/x* and *1/x²* weight by concentration; *1/y*
and *1/y²* by response. A weighted fit is the usual choice for a range of
more than two decades; the report and the limits page say which weighting
a curve carries.

## Reading concentrations

Each sample's response is read off the curve and multiplied by its
**Dilution** factor — the curve describes the vial that was injected and
the answer wanted is the original sample. Where the curve cannot be
inverted (a quadratic with no real root in range, a zero slope) the
concentration is left empty. For samples with an expected concentration —
standards and quality controls — **Accuracy %** is the calculated
concentration as a percentage of the actual.

## An internal standard's own curve

An internal standard is spiked at the same amount into every standard, so
its response against concentration is flat and a curve through it means
nothing. The report labels such a curve as meaningless, and the limits page
leaves internal standards out.

## A curve from infusions

A curve does not need a chromatogram. A dilution series sprayed rather than
injected fits here in exactly the same way — the response is a height in an
averaged spectrum and the ratio to the internal standard is taken in that one
spectrum, which is what [[infusion-quantitation]] measures. The rows arrive
with no retention time and an *Algorithm* of `infusion`, and everything on
this page then applies unchanged.
