---
title: Welcome
---
MIL-Q is open-source software for reviewing and quantifying liquid
chromatography – mass spectrometry data. It reads SCIEX `.wiff` files
directly and **mzML** from any instrument, and it does the two jobs that
SCIEX ships as two programs: qualitative review the way PeakView does it —
chromatograms, spectra, extracted ions, chemistry — and batch quantitation
the way MultiQuant does it — a component table, one chromatogram per sample
for every component, calibration curves, statistics and quality control.

This manual describes every part of the application, what each control
does, what each number means and, where a number was measured rather than
assumed, what was measured and on what. It is the same text in the
application's **Help ▸ Manual** window and in the printed copy that
**Help ▸ Export manual as PDF…** writes.

## How the manual is organised

| Section | What it covers |
|---|---|
| Getting started | [[installation]], [[formats]], [[starting-a-project]], and [[workspaces]] |
| Explorer | qualitative review: [[chromatograms-and-spectra]], the [[contour-view]], [[manual-xic]], and a sprayed standard from end to end — [[direct-infusion]], the [[infusion-report]], [[new-standard]], [[infusion-quantitation]] |
| Chemistry and annotation | the [[mass-calculator]], the [[formula-finder]], [[lipid-maps]], the [[spectral-library]], the [[standard-history]] and the [[accurate-precursor]] |
| Samples | the batch: [[samples-workspace]] |
| Method | the component table: [[method-workspace]], [[internal-standards-and-qualifiers]], [[check-method]], [[method-report]], [[suggest-from-data]], [[acquisition-schedule]], [[collision-energy]] |
| Analytics | quantitation: [[peak-review]], [[integration-parameters]], [[integration-algorithms]], [[calibration]], [[batch-qc]], [[mass-drift]], [[audit-trail]], the [[report]] |
| Reference | [[projects-and-files]], the [[command-line]], [[keyboard-shortcuts]], [[troubleshooting]], the [[glossary]] and the [[version-history]] |

## Getting to it

**F1** (⌘? on macOS) opens the manual on the page for where you are: the
panel that has the focus — the Integration panel, the results table, the
Batch QC tab, a side tab of the Explorer — or, failing that, the workspace
shown. Dialogs carry a **Help** button that does the same for their own
page. **Help ▸ Manual** opens it on the same rule, and **Contents** in the
manual's toolbar goes back to this page.

## Reading it

Pages link to one another the way notes in a vault do. A link is drawn in
the accent colour; clicking it opens that page, and **Back** returns. Every
page ends with the list of pages that link to it, so a topic can be
approached from either end of any link.

The search box at the top of the window matches words by prefix — typing
`integr` finds integration, integrated and integrator — and a page is listed
only when it contains every word typed. The first hit is opened with Enter,
and the page scrolls to the first occurrence of the query.

## In Portuguese

The manual is also written in Brazilian Portuguese. The **English /
Português** switch at the right of the manual window's toolbar changes the
language of everything the manual is: the contents tree, the page shown,
the text the search box looks through and the copy that **Export as PDF…**
writes. The choice is remembered between sessions. A page whose translation
has not been written yet is shown in English with a note saying so, so the
contents never has a hole in it. The application itself — its menus,
buttons, dialogs and column headings — stays in English, which is what the
rest of this manual describes.

## Conventions

- **Bold** names a control as it appears on screen: a button, a menu entry,
  a checkbox.
- `Code` is something typed, a file name, or a value exactly as the
  application shows it.
- Where a figure is quoted — a percentage, a count, a time — it was measured
  on real data, and the page says on what. Nothing in this manual is a
  vendor's claim repeated.
- Menu paths are written `File ▸ Export report…`.

## What MIL-Q is not

It is not a vendor-certified replacement for MultiQuant in a regulated
laboratory. There is an [[audit-trail]] — every edit made by hand, with the
value before and after — but it carries no electronic signatures and no user
accounts: it records what was done and when, never who did it. And it does
not reproduce SCIEX's own extraction rule exactly — see [[measured-facts]]
for the one place the two disagree, by how much, and why the plain rule
ships. Everything else in the feature lists of both vendor programs is here,
the [[spectral-library|library search]] and the
[[mass-recalibration|mass recalibration]] included, and the
[[design-principles]] say what was chosen when the two could not both be
had.

## Without the window

Everything the application does can be scripted: see [[python-api]] for the
ten-line versions of a batch reprocessed and exported, a spectrum
explained and a library searched, and [[command-line]] for what the
application itself answers to on the command line.
