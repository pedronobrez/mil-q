---
title: Annotate from LIPID MAPS
---
A component table generated from the acquisition method names every
component after its precursor: `703.57`, `731.61`. **Annotate from LIPID
MAPS…** in the [[method-workspace]] proposes a species name for every
component still carrying such a name, and shows the proposals for review
before anything is written.

## What each proposal rests on

For every candidate component the precursor mass is first measured from the
survey scan, as [[accurate-precursor]] describes — at the time the
component's own transition peaks, confirmed by the surviving precursor in
the product-ion scan, and agreed across the open samples. The dialog's
columns say which mass was used:

| Column | Meaning |
|---|---|
| Use | tick to accept the proposal |
| Component | the component as named now |
| Mass used | the mass the search ran on |
| From | **survey** — measured from the TOF MS scan, searched at ±10 ppm; or **written** — the method's own value, searched at the precision it was written with |
| ± window | the search window that follows from that |
| Species | the species proposed |
| Structures | how many LMSD structures share that species — a mass cannot separate them |
| ppm | the error between the mass used and the species' ion |

A component is only **offered for automatic naming when exactly one species
fits the window**. Where two fit, the row is marked ambiguous and left
unticked; where none does, it says so. On a table whose precursors carry
one or two decimals, most rows come back marked *needs an accurate mass*
rather than guessed at, because at that precision the window holds several
species and the survey scan could not measure the ion.

## What is written

Accepting a proposal renames the component to the species, fills in its
formula, and records the LM_ID. The LM_ID travels with the component, into
the CSV export and the project, so the annotation can be traced back to the
database record it came from.

Nothing else changes: the precursor stays as written, because the measured
mass is a measurement of this batch and the method's value is what the
instrument was told to isolate.

## Adduct

The dialog assumes [M−H]⁻ — negative mode — unless told otherwise; the
same adduct list as the [[mass-calculator]] is available.
