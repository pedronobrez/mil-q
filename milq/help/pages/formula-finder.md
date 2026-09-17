---
title: Formula finder
---
The **Formula finder** tab answers the reverse of the [[mass-calculator]]:
given a measured m/z, which elemental compositions could produce it? Open it
by right-clicking a spectrum peak and choosing **Find formula for this
peak**, from **Send m/z to formula finder** in the mass calculator, or by
typing an m/z.

## Inputs

| Field | Meaning |
|---|---|
| m/z and adduct | the measured ion and how it was formed; the neutral mass is what the search runs on |
| tolerance, ppm or Da | how far a candidate may be from the measurement; 10 ppm to start |
| RDBE range | ring-and-double-bond equivalents allowed, −0.5 to 40 by default |
| **Even-electron only** | keep compositions whose RDBE is a whole number plus a half — the closed-shell ions electrospray makes; radical ions have integer RDBE |
| **Apply element-ratio rules** | the heuristic ranges of H/C, O/C, N/C and so on that real molecules stay within — the "seven golden rules" |
| **Rank by isotope pattern** | score each candidate against the isotope satellites of the spectrum on screen |
| Element ranges | the minimum and maximum count of each element considered |

## Results

One row per composition: formula, m/z, error in mDa and ppm, RDBE, and the
isotope score. Exact mass alone rarely separates candidates above a few
hundred daltons; the relative heights of M+1 and M+2 usually do, which is
why the isotope score is there and why the table is sorted by it when it is
on.

## The isotope score needs a survey scan

The score compares the spectrum's satellite peaks with the pattern each
formula predicts. A product-ion scan has no satellites to compare — Q1
isolated the monoisotopic precursor before fragmentation — so run the finder
on a peak of the TOF MS survey channel. The panel checks which channel the
spectrum came from and says so rather than report meaningless scores.

## When the finder is the wrong tool

For lipids, a database is a better first question than a search over
compositions: the [[lipid-maps]] tab answers "which known lipid has this
mass" with structures attached, and the [[accurate-precursor]] page
explains how the mass to ask about is measured from the survey scan rather
than read off the method.
