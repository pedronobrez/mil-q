---
title: Workspaces and the session
---
The window is organised the way SCIEX OS is: the workspaces are tabs, and a
single session sits behind them. The open files, the sample list, the
component table, the results and the calibration curves exist once, so a
sample typed as a Standard in one place is a Standard everywhere and a
component edited in the Method workspace is what the Analytics workspace
integrates.

| Workspace | Shortcut | What it is for |
|---|---|---|
| **Explorer** | Ctrl+1 | qualitative review of the raw data: chromatograms, the [[contour-view]], spectra, extracted ions, chemistry — see [[explorer]] |
| **Analytics** | Ctrl+2 | the batch, quantitatively: one chromatogram per sample for each component, the results table, calibration, statistics and QC — see [[analytics-workspace]] |
| **Method** | Ctrl+3 | the component table — what to extract, where, and how the result is reported — see [[method-workspace]] |
| **Samples** | Ctrl+4 | the batch: sample type, study group, expected concentration, dilution — see [[samples-workspace]] |

The `Workspace` menu lists the same four. Every shortcut in the application
is collected in [[keyboard-shortcuts]].

## The menus

| Menu | Holds |
|---|---|
| File | New, Open and Save project; Add data files; Close all; Export report; the Explorer's exports (chromatograms and spectrum as CSV, sample as mzML); Quit |
| View | the Explorer's display switches: Fit, Normalise, Mirror, Stack, Overview, labels, legend |
| Panels | one entry per side panel of the Explorer, Ctrl+Shift+1 onwards |
| Process | Centroid, markers, background, Explain spectrum, Detect peaks |
| Workspace | the four tabs |
| Help | this manual (F1, on the page for where the focus is), the quick tips, and the manual as a PDF |

## Theme

The application follows the system into and out of dark mode while it is
running; the plots re-colour with it. The status bar names the theme in use
when it changes.

## What is remembered between sessions

Window geometry, the last folder a file was opened from or saved to,
whether the Integration and Acceptance panels of the Analytics workspace
were folded, and whether the start prompt was dismissed for good. Nothing
about a batch is remembered outside its project file.

## The window and the screen

The window opens at 1650 by 1000 pixels, or at the screen's size where the
screen is smaller, and it is brought back inside the screen when a geometry
saved on a larger one is restored. It can be made as small as 888 by 515
pixels: the toolbars wrap onto a second line as it narrows, and each of the
Explorer's side panels scrolls inside its dock rather than setting the
window's height.

Until version 0.9.0 the window could not be made narrower than 2,000 pixels
— thirteen buttons in the Method workspace's toolbar, side by side, and a
widget's least width is the window's — so on a 1512 by 913 laptop it opened
wider than the screen, and any change of layout, such as the **Columns** and
**Rows** of [[peak-review]], pushed it back out over the edge.

## The status bar

Every workspace reports what it last did in the status bar at the bottom of
the window — how many rows were processed, what a click integrated, why an
action did nothing. When something appears not to have happened, the status
bar usually says why.
