---
title: Compare infusions
---
The tray of standards is sprayed again — a new vial, a new bottle of
solvent, the instrument back from service — and the question is whether the
spectra are the ones from last time. **Compare infusions…** on the
Infusions tab of [[analytics-workspace]] answers it: a reference project
against the infusions that are open, compound by compound and condition by
condition.

It is [[compare-batches]] for the other kind of batch. Where that one puts
two chromatographic runs of one method side by side, this puts two days of
[[direct-infusion]] side by side, and it asks the questions
[[standard-history]] asks of a library — with the same rules, so that
*moved* means one thing in this program and not two.

## The reference

A project file, `.oqproj`. It is read for the infusion summary it saved and
no raw file is opened, so a reference whose acquisitions have moved to
another disk is still a reference.

That needs the reference project to *hold* a summary. Press **Measure** on
the Infusions tab before saving it and the project carries what the table
showed — and, for every row, the averaged and centroided peak list, at the
floor and the ceiling a record of your own is written at
([[spectral-library]]: peaks above one per cent of the base peak, at most
two hundred of them, with the base peak's height in counts beside them). A
project saved without measuring holds nothing to compare against and says
so rather than showing an empty table.

The peaks are what the file pays for. Measured on three real infusions of
cholic acid-d4 — 12, 41 and 179 peaks stored — the project grew from 1,965
to 8,645 bytes: 19.4 bytes a peak, so a row carrying the full two hundred
costs about 4 kB. Reading one back takes 3 ms.

## Matching

A row is paired with the reference's row of the **same compound and the
same conditions**: the same activation, and a collision energy within half
an electronvolt. A 22 eV EAD spray is compared with the reference's 22 eV
EAD spray and never with its 12 eV one, for the reason [[standard-history]]
cuts a history into series at all — a spectrum measured at another energy
has other fragments, and scoring across energies measures the method rather
than the standard. Anything the other day does not have is listed as only
here or only there.

The compound, and the activation where the file name is the only thing that
says one, are read from the **file name on disk** rather than from the
sample's shortened name in the tables. The shortened name is what every
open sample shares taken off the front of it, which means it changes with
what else is open: the same acquisition read as *EAD…* beside two other
cholic-acid infusions and as *12CE…* beside one, and nothing matched
anything until the file name was used instead.

## What is compared

| Column | Meaning |
|---|---|
| Score, Reverse | the cosine of this day's peaks against the reference's stored peaks, and the cosine over the reference's peaks only — a high reverse with a low score is everything that was there plus something new |
| Matched | how many of the reference's peaks were found |
| Base m/z ref., now, Base Δ ppm | where the base peak sits, and how far it has moved. It is the strongest of the *stored* peaks, which is a centroid: it can sit a few thousandths from the base peak the Infusions tab reads off the profile trace, and it is the only one a reference read back out of a file could still be checked against |
| Height ref., now, Δ height % | the base peak in counts, and the change — the one figure a library record cannot hold and the one that says whether the standard is still giving what it gave |
| Ions ref., now | the ions a formula found of those it predicted, each day; see [[infusion-report]] |
| Δ precursor ppm | the change in the precursor's error against what the method wrote ([[accurate-precursor]]) |
| Δ record score | the change in the score of the best record in your own library |

## The mark

A row is marked *moved* on two rules, both borrowed:

- **the base peak is more than 50 ppm from the reference's.** That is not a
  mass error, it is a different ion — `standard_history`'s figure, and the
  distinction it exists to make.
- **its height is more than 20% from the reference's.** What a control
  chart of that standard would call out; see [[batch-qc]] for where the
  figure comes from.

The score is reported and is deliberately *not* a rule. A history judges a
cosine against the spread of its own series, and two days are two points,
which is not a spread.

## Measured

Two of the real acquisitions against three of the day before, all cholic
acid-d4: two rows matched at 12 and 22 eV EAD, and the third spray — 45 eV,
with no activation stated in its name — left only in the reference. Both matched rows moved. The base peak had gone from 430.3488
and 377.3015 to 839.2316 and 839.2343 — 950,000 and 1,224,000 ppm away,
which is a different precursor and not a drift — at 0.9% and 2.4% of the
reference's height, and the cosines were 0 of 12 and 7 of 41 peaks matched,
scoring 0.0 and 8.6. The same files reopened against themselves score
100.0, 0.0000 ppm and a ratio of 1.0000 on every row, which is the floor of
the measurement, and the comparison itself takes 6 ms.

**Export CSV…** writes every row and both lists of odd ones out, and while
the comparison stands the [[report]] carries it as an *Infusion comparison*
section.
