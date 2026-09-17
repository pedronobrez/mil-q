---
title: Peak review
---
The review grid is the view MultiQuant is built around: the same component
across the whole batch at once, so an outlier stands out against its
neighbours instead of having to be hunted down sample by sample.

## The panels

Each panel is one sample's chromatogram for the selected component — the
XIC, conditioned as the integration saw it. Its title gives the sample name,
the area, the signal-to-noise and the retention time; a `✎` marks a row
integrated by hand. A sample where nothing was found is drawn grey with the
reason in the title (*no peak above noise*, *channel does not cover
5.10–6.10 min*, *only 4 points to detect in*).

What is drawn on a found peak:

| Element | Meaning |
|---|---|
| shaded area | exactly what was integrated: the trace above the straight baseline drawn between the peak's two boundaries. The band alone said where the limits were, which a reader takes for the area — and on a peak a couple of points wide the two look nothing alike |
| dashed line | that baseline |
| thin vertical band | the boundaries |
| light band | the expected retention-time window, RT ± half-width |
| orange curve | the fitted Gaussian, when the area came from a fit — the shading then sits under the curve, because the curve's area is the number. See [[integration-algorithms]] |
| red dashed trace | the internal standard, with **Show IS** on |
| grey band | the noise region, when one is set |

## Controls

| Control | Effect |
|---|---|
| **Columns** and **Rows** | the grid's shape; paging appears when the batch is larger than a page. The panels are kept and re-placed rather than rebuilt, so a change of shape is immediate and does not resize the window — see [[workspaces]] |
| **Manual** | dragging across a panel integrates exactly that range (Shift+drag does the same without the switch) |
| **Show IS** | draw the internal standard behind the analyte, rescaled to its height — the two rarely share a magnitude, and only the shape and the time are being compared |
| **Same Y** | one intensity scale across the panels, so heights compare directly |
| **Zoom** | *Expected window*, tight on the *Peak*, or the *Whole run* |
| **Link X** | zooming one panel zooms them all |
| **Magnify peak** (toolbar) or double-click | one panel filling the pane |

The panels are fenced inside their own data: nothing lies outside a peak's
trace, and a panel this small is easy to lose one's place in.

## Manual integration

Drag across a peak with **Manual** on, or with Shift held. The range is
integrated as marked — a straight baseline between the two ends, the area
above it, no peak finding — and the row is marked manual with `✎`. A
manual row survives reprocessing while the settings it was drawn under
stand: adding an injection, changing another component, or reprocessing the
batch leaves it exactly as the operator set it. What does replace it is a
change to **its own** component's extraction or integration settings — a
different mass window, a different smoothing, another algorithm — because a
boundary drawn on one trace is not a decision about a different trace. It is
integrated again automatically, the status line and the [[audit-trail]] say
how many rows that was, and the drag can simply be repeated. Right-click the panel and
choose **Back to automatic integration** to let the detector have it again. Both
are written into the [[audit-trail]] with the boundaries and the area before
and after, so a peak somebody decided can be told from one the detector
found.

## The noise region

Right-click a panel with a stretch of baseline shaded and choose **Set
noise region from the shaded range**: that range becomes where the noise
behind the component's signal-to-noise is measured, peak-to-peak or by
standard deviation as the Integration panel says. **Apply** in that panel
keeps it. Why the region matters is on [[signal-to-noise]].

## Reading a grid

- A peak that moves from panel to panel while the expected window stays
  still is drifting retention; the [[batch-qc]] page charts it.
- A standard drawn behind the analyte with **Show IS** that peaks at a
  different time is a standard that is not the analyte's standard.
- A grey panel among found ones, with *no peak above noise*, in a sample
  that plainly has a peak, is usually a gate: see [[integration-parameters]].
