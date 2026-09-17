---
title: A new standard, from the bottle
---
**File ▸ New standard…**, and **New standard…** on the Infusions tab, is the
whole path from a vial to a working internal standard in one place: the
component in the method, the record in your own library, and with it the first
point of that standard's history.

Every step of it already existed and none of them was joined up. The vial was
infused; the [[direct-infusion|infusion]] was averaged; the
[[infusion-report|infusion report]] said what it was; *Use in method…* wrote
the component; *Add spectrum to library…* wrote the record; and the lot number
was written on the tube and nowhere else. Nothing carried a name typed once
through all of it, and nothing said afterwards that the component, the record
and the history entry are the same material.

## What you give, and what it reads

Four things are yours to give, because nothing in an acquisition holds them:

| You give | What it does |
|---|---|
| **Name** | resolved as you type — the bile-acid standards by the abbreviation on the bottle, then LIPID MAPS, then the lipid shorthand — into a formula, the LIPID MAPS identifier where there is one, and the labels a trailing `-d4` declares |
| **Bottle / lot** | goes into the component's provenance and into the record's comment. The one fact about a standard that no file holds and nothing recovers later: it is what says two records six months apart are the same material |
| **Infusion** | the acquisition. It has to read as an infusion — the two flatness figures of [[direct-infusion|a direct infusion]] — because everything here is the average of a whole run |
| **Expected adducts** | which ions this compound is expected to give |

Everything else is read off the file: the polarity, the channel and its
written precursor, the collision energy, the activation, how many scans there
are and the average of all of them.

The **formula** is filled in from the name and stays editable — a resolution
is a proposal and a typed formula is a decision. **Unplaced labels** is a
field of its own rather than something read off the name, because the labels
are handed to the prediction as a *count*: every predicted fragment is offered
carrying 0 to n of them and the spectrum says how many it kept. See
[[lipid-maps]] for why that is the only honest way to score a labelled
standard.

## The expected adducts

Once a file is chosen, every adduct of the polarity is listed with what it
would weigh for this formula and how far that sits from the precursor the
channel was actually given — and the ones that reach it are ticked. The whole
list is shown rather than only the fits, because a miss is as informative as a
hit: a precursor that is none of them means the formula, the labels or the
file is not this compound.

The best-fitting ticked adduct is the one the component is written as. Ticking
one that fits nothing is not silently ignored: it goes over as declared, and
where another adduct does reach the written precursor that one is taken
instead and the basis line under the preview says which tick it passed over —
the channel is a measurement and a tick is an expectation. Where none of them
reaches it, nothing is identified and nothing is written.

## What the preview shows

Nothing in it is typed. The adduct with the sentence that identified it —
confirmed against the survey scan where the acquisition has one, and read from
the written precursor alone where it has not; the exact mass of that adduct
beside the number the channel was written with, in ppm (see
[[accurate-precursor]]); the averaged spectrum's base peak and the next few
strongest, each labelled with the ion the explanation matched to it; how many
of the predicted ions were found and what share of the measured intensity they
account for; and the isotopic purity where the envelope could be solved — and
its refusal, in the same place, where it could not.

Under those is what pressing **Create** would write, so it can be read before
it is written.

## What Create writes

Two things, and nothing else:

1. **The component**, into the [[method-workspace|Method workspace]]'s
   table: the labelled formula, the adduct, the **exact** mass of that adduct
   as the precursor — never the rounded value the channel was typed with — the
   base peak as the fragment, no retention time (an infusion is not a
   separation and has none to give), the group `standards`, the
   internal-standard box ticked unless you untick it, and the provenance in
   words with the lot in it. A compound the method already carries has its
   **empty** cells filled and nothing else; see
   [[internal-standards-and-qualifiers]].
2. **The record**, appended to your own library — the same MSP the
   [[spectral-library|Library]] tab and the Infusions tab write into: the
   averaged, centroided spectrum with the formula, the adduct, the collision
   energy, the day the instrument measured, the base peak's absolute height
   and the provenance with the lot in its comment.

A compound the method already carries in full leaves no component to write,
and the record is written anyway: a second infusion of a standard is a second
verification of it, and a verification is a history entry. The status line
says which of the two will happen before **Create** is pressed, and the audit
entry says which did afterwards.

**The history is not written, because the history is the library read back.**
That is all [[standard-history|the standard history]] is: the records of one
compound ordered by the day they were acquired. The record just appended *is*
this standard's newest entry, and the audit line says how many the file now
holds of it. One entry in the [[audit-trail]] names all three.

## Where it refuses

Three refusals, and each disables **Create** and says why in the place it
belongs, rather than writing a component with an invented mass:

- **the file is not an infusion** — with the two figures that say so, per
  sample;
- **the name resolves to no formula and none was typed** — there is nothing
  for an adduct to be an adduct of;
- **the written precursor is no adduct of the formula** — the closest misses
  are named, with how far off each is.

## Measured

`cholic acid-d4`, lot `CDN-D-2452`, on a real ZenoTOF infusion
(`CA-d4_TOFMSMS_Mix1.wiff`, 473 scans, CE 45 eV, no survey scan). The name
resolved to `C24H40O5` from the standards table with 4 unplaced labels and
`LMST04010001`; one of the five positive adducts of `C24H36D4O5` reaches the
written `430.35` and it is `[M+NH4]+`, at 430.3465 — **+8.1 ppm** from the
number the channel was given, which is the difference between the mass the
instrument was told and the mass the compound is. The base peak is 359.2869 at
5,638 counts, matched as `[M+H-3H2O]+ +4D`; 2 of the 56 predicted ions were
found, accounting for 24.2% of the intensity at that collision energy; the
purity refused itself, because the quadrupole took the satellites the envelope
would have been read from. The component came out `430.3465 → 359.2869`,
`C24H36D4O5 [M+NH4]+`, no retention time; the record carries 179 peaks.

Opening the file, averaging the run and identifying the compound took **2.6
s** on a cold run and 1.6 s on a second one with the file cache warm; after
that, editing the name, the formula or an adduct re-identifies in **0.05 to
0.08 s**, because the average is kept and only the arithmetic is run again.
Writing the component, the record and the audit entry took **under 0.01 s**.

The refusal, on `CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_TESTEARTIGO.wiff` — a file
named after CA-d4 whose method isolates 839.56: **0 of 5** adducts of
`C24H36D4O5` reach it, the closest being `[M+K]+` at 451.2758, 388.2842 Da
away. **Create** is disabled, the preview says no component, no record and no
history entry, and nothing is written.