---
title: Extracted ion chromatograms
---
An extracted ion chromatogram (XIC) is the intensity of one mass across the
run: for every scan of a channel, the sum of the points inside a mass
window. There are four ways to ask for one.

## The Manual XIC tab

Type one or more masses, comma-separated (`183.1391, 313.2384`), a
tolerance and its unit — Da or ppm — and **Extract XIC**. Each mass becomes
a trace on the chromatogram, extracted from the active channel, or from
every checked channel with **Extract from every checked channel** ticked.
The **Active XICs** list names them; select one and press Delete to remove
it, or **Clear XICs** to remove all.

## From the spectrum

Shift+drag across an m/z range on the spectrum pane, then right-click and
**Extract XIC from selection**: the window is exactly the range selected.

## From the peak list

Double-click a row of the **Spectrum peaks** tab to extract that peak's mass
with the tolerance set in the Manual XIC tab.

## From a component

Double-click a row of the **Components** tab to draw that component's XIC
across every checked sample, in its own channel, with its own mass window.
See [[explorer-components-and-results]].

## The mass window

The window is `m/z ± tolerance`. In ppm the half-width is `m/z × ppm / 10⁶`,
so 20 ppm at 313.24 is ±6.3 mDa. The window sums the points **inside** it;
SCIEX's own extraction also counts part of a peak whose points fall just
outside, which is the one measured difference between this program and the
vendor's — a median 0.58% of peak height, at most 12%, always lower here.
See [[formats]] and [[measured-facts]].

## Which channel

An XIC lives in one channel. From the Manual XIC tab that is the active
channel; from a component it is the channel [[method-workspace|the method]]
matches to the component — by precursor, by whether the channel was
acquired at the expected retention time, and by whether its mass range
holds the target. A scheduled method can carry the same precursor in two
periods, which is why the time is part of the match.

## What the trace goes through

Smoothing and baseline removal from the Processing toolbar apply to an
XIC as to any other trace, and so do *Normalise*, *Mirror*, *Stack* and
*Cascade*. **Detect peaks** integrates it like any other trace.
