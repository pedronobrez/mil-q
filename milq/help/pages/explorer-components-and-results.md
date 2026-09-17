---
title: Components and results in the Explorer
---
The Explorer can run the method's component list over whatever is open,
which is the quick way to see one compound across a few files without
setting the batch up.

## The Components tab

The list is the [[method-workspace|method]]'s component table, read-only
here and shared with every workspace: precursor, fragment, retention time
and window, as the method declares them.

- **Double-click a row** to draw that component's XIC across every checked
  sample. The channel is chosen by the same rule the Analytics workspace
  uses — precursor, time coverage and mass range — and the mass window is
  the component's tolerance.
- **Extract and integrate all** runs every component over every checked
  sample and fills the Results tab. The integration is the same code path
  as a batch in Analytics, with the method's integration defaults.

## The Results tab

One row per component and sample: component, sample, channel, m/z,
retention time, area, height, width, signal-to-noise and a note saying why
a row is empty when it is (no matching channel, the channel does not cover
the expected time, no peak above noise). Sortable by any column; **Export
CSV…** writes what is shown. Double-clicking a row draws that row's trace.

These results are the Explorer's own. The batch's results — the ones the
[[results-table]], the calibration and the report use — are produced in the
[[analytics-workspace]] by **Process batch**, and the two are not the same
table.

## Detect peaks

**Detect peaks** on the Processing toolbar integrates every trace currently
drawn on the chromatogram — TICs, BPCs, XICs alike — with the automatic
detector at its default gates (a peak has to be at least 5% of the tallest
in the trace and at least three times the noise), marks each peak on the
plot and lists them in the Results tab. It is a survey, not a quantitation:
it does not know what compound a peak is, and it uses no retention-time
window. How the detector finds a peak's edges is described in
[[integration-parameters]].

## A range by hand

Shift+drag across a peak on the chromatogram and the status bar reports the
integration of exactly that range — area above a straight baseline drawn
between the ends, height, apex time and S/N. This is the same arithmetic
manual integration uses in the [[peak-review]] grid.
