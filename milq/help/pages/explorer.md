---
title: The Explorer workspace
---
The Explorer is where raw data is looked at before anything is quantified:
the run as a whole, one channel at a time, one scan at a time. It is built
the way PeakView is — a chromatogram above, a spectrum below, and the
things one wants to do to either around them.

## Layout

**Samples and channels** (left dock, Ctrl+Shift+S) is a tree of the open
files. Each sample lists a *Sample TIC* node — the run's total ion
chromatogram — and every acquisition channel of its method, labelled with
the experiment's name, precursor, mass range and collision energy. Checking
a channel draws it; the **Active channel** selector at the top of the
window says which channel the spectrum pane and the extracted ion
chromatograms come from.

Above the tree: a **filter** box (type `313.2` to keep only channels
mentioning that mass), **Uncheck all**, **TOF MS only** (check the survey
scans and nothing else) and **Collapse all** (fold every sample shut — a
TripleTOF method is eighty channels per sample).

**Panels** (right dock, Ctrl+Shift+P) holds the side tabs, each reachable
by Ctrl+Shift+1 onwards or from the **Panels** menu:

| Tab | What it does | Page |
|---|---|---|
| Components | the method's component list, read-only, with *Extract and integrate all* | [[explorer-components-and-results]] |
| Results | what was integrated here, sortable and exportable | [[explorer-components-and-results]] |
| Manual XIC | extract any mass with a tolerance | [[manual-xic]] |
| Spectrum peaks | the peaks of the spectrum on screen; double-click one for its XIC | [[chromatograms-and-spectra]] |
| Mass calc | exact masses, adducts, isotope patterns | [[mass-calculator]] |
| Formula finder | compositions for a measured mass | [[formula-finder]] |
| LIPID MAPS | lipids for a mass, masses for a lipid, fragments, and explaining a spectrum | [[lipid-maps]] |
| Library | the spectrum on screen searched against an MSP or MGF spectral library | [[spectral-library]] |
| Sample | the acquisition's own metadata | [[sample-information]] |

The centre holds the chromatogram pane and, under it, the spectrum pane;
**View** at the top switches the upper pane between the chromatogram and
the [[contour-view]]. **TIC / BPC** chooses what the checked channels draw:
the total ion current of each scan or its base peak.

## Toolbars

**Main.** *Select range* makes dragging select instead of zoom (holding
Shift while dragging does the same without the switch); *Fit* rescales
both panes; *Add marker* and *Clear markers* place reference marks on the
spectrum.

**View.** *Normalise* scales every trace to its own maximum; *Mirror* flips
every other trace, sample against blank; *Stack* gives each trace its own
pane with the time axes locked; *Overview* adds a navigator under the
chromatogram showing the full range and where the current zoom sits;
*Labels* annotates spectrum peaks with their m/z; *RT labels* annotates
chromatogram apexes; *Relative labels* labels spectrum peaks by their
distance from a marker; *Legend* names the traces. **Cascade x / y** offset
overlaid traces along time and vertically, in minutes and per cent.

**Processing.** *Smooth (σ, scans)* and *Baseline (min)* condition every
trace — for the drawing, the integration and the export alike, so an area
always matches what is on screen; *Centroid* turns a profile spectrum into
sticks; *Set background* takes the selected chromatogram range as a blank
and subtracts its average spectrum from every spectrum shown; *Explain
spectrum* scores LIPID MAPS candidates against the spectrum (see
[[lipid-maps]]); *Detect peaks* integrates every trace on the chromatogram
and fills the Results tab; *Average whole run* averages every scan of the
active channel into one spectrum, and *Δ from average* — on an infusion only
— draws the scan on screen minus that average, with the average mirrored
below it (both see [[direct-infusion]]).

## The scan controls

**Scan** is the number of the scan whose spectrum is shown, 1 being the
active channel's first cycle; the arrows step through them and so do the
← and → keys; the retention time of the scan is shown beside it. **Average
selected range** replaces the single-scan spectrum with the average over
the range marked on the chromatogram, and *Average whole run* in the
Processing toolbar averages every scan of the active channel — which is
what a [[direct-infusion]] is opened as.

## Mouse conventions

In both panes: drag = rubber-band zoom, double-click = fit, right-click =
the plot's own menu (export as image, axis options), Shift+drag = select a
range. A single click on the chromatogram shows the spectrum of that scan.
The full set of gestures is on [[chromatograms-and-spectra]].

## Exports

Under the **File** menu: the chromatograms on screen as CSV, the spectrum on
screen as CSV, and the selected sample as mzML (see [[formats]]).

## Opening files here

Files opened from the Explorer, the Samples workspace or the File menu are
the same files: the tree here, the batch table there. Files are read from
disk once and every workspace shares the reader.
