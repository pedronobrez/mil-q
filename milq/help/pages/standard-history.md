---
title: Standard history
---
A record written into your own library is a verification that has already
happened. Every time the standard is sprayed to check the vial, one more
record of the same compound goes into the same MSP — and after a few
months that file holds the only measurement of that standard over time
anybody has.

**History…**, beside the record count in the [[spectral-library]] tab,
reads it back. It is [[batch-qc]] asked of a library instead of a batch:
the same robust centre, the same two conditions a point has to meet before
it is called out, the same trend that needs both a size and a direction —
with the records in the order they were **acquired** rather than the order
they were typed in.

## What is grouped with what

The records of one compound are cut into **series** by collision energy and
activation, and nothing is ever compared across a series boundary. A
spectrum measured at another energy has other fragments and often another
base peak, so a cosine against it measures the method and not the standard;
an absolute intensity is comparable only within one method anyway. Measured
on one real infused standard, cholic acid-d4, the same compound in the same
vial scored **67 at EAD 12 eV against EAD 22 eV, 29 at EAD 22 eV against
CID 45 eV, and 6 at EAD 12 eV against CID 45 eV** — three numbers that say
nothing about the vial and everything about the collision cell.

The compound is the part of the record's name before the first separator,
as in the [[infusion-report]]. The activation is read from an
`Activation` field where an exporter wrote one and from the record's name
otherwise — `..._EAD_22CE_...` — because no field this program reads from a
`.wiff` carries it: the nine ZenoTOF infusions to hand all say `TOF PI` and
`Product`, and the electron energy appears only in the file name. A record
whose name does not say is grouped as *unstated*, never as CID.

### And by the mass axis it was written from

A record written while [[mass-recalibration]] was switched on carries peaks
the instrument never reported: they were moved by a few parts per million
first, and the record's comment says so. Scoring such a record against one
written from the instrument's own axis measures the correction and reports
it as the standard changing, so the axis is a series attribute exactly as
the energy is. The **Mass axis** column on the table says which each record
was, and a corrected series carries `axis corrected −5.2 ppm` in its name.

Two rules keep that from splitting histories that ought to be whole:

- **Two corrected records are one axis, however far apart the corrections
  were.** Each stands where its own acquisition's lock masses put it. Only
  a correction that one record carries and another does not can separate
  them — see the four-way measurement in [[spectral-library]], where the
  pair whose corrections were furthest apart agreed best of all.
- **And only when it is larger than the 20 ppm a search pairs peaks
  within.** Under that the two put every peak in the same window as each
  other, and two series would be a history broken in half over a fiftieth
  of a peak width; the difference still shows on the mass chart, which
  warns at 10 ppm and flags at 20.

Where a compound does come out as two series for this reason, the line
under the charts says which series there are, how much correction one
carries and the other does not, and that the repair is **Rewrite from
files…** — which reads every record whose acquisition is still on disk
again and writes them all from the axis in force now. The button is offered
on this window when that is what is wrong, and does the writing back on the
[[spectral-library]] tab, which owns the file.

On the real infusions nothing splits: every correction their own precursor
ladders give is inside the 20 ppm — the per-acquisition figures are in
[[mass-recalibration|An infusion recalibrates on its own precursor]] — so a
corrected record and an uncorrected one of the same standard stay one
series and say so in the series name — *axis corrected +6.6 ppm for 1 of 2,
the rest on the instrument's own*. That is the intended outcome. The split
itself is exercised only on made-up records, and the manual says so rather
than implying a measurement that was not made.

### The series boundary is not the end of the story

Those three numbers — 67, 29 and 6 — are the reason a series never crosses
an energy, and they are also a waste of three measurements. The same
records that cannot be charted against each other *can* be read as one
curve: how each fragment's share of the intensity moves as the energy
rises. That is the energy profile, it is computed from the records of one
compound with no series crossed, and it is what lets the
[[spectral-library]] tab say **compatible with CA-d4 EAD at ~18 eV**
instead of listing three records that all look wrong.

Cholic acid-d4's profile, rung by rung, is printed in
[[spectral-library|Fragmentation across energies]], on the same nine
infusions this page's figures come from. The one line of it that decides
how this page is drawn: **the base peak is a different ion in each of the
three files** — the ammoniated precursor at 12 eV, `[M+H-2H2O]+` at 22,
`[M+H-3H2O]+` at 45 — which is why a profile is held as shares of its own
total rather than relative to a base peak that moves, and why the *base
peak intensity* chart below is drawn inside a series and never across one.

The profile is computed from the records present and is never written into
them, so appending one more verification changes it with nothing to bring
up to date. See [[spectral-library]] for the interpolation, the two
refusals — nothing extrapolated past the measured range, no two activations
crossed — and what two energies per activation do and do not allow.

## The three charts

The first record of a series is the **reference**, and everything is
measured against it.

| Chart | What it asks | Flagged past |
|---|---|---|
| Score against the first record | does it still look like itself | 20% from the centre and 3σ, or 50% outright |
| Base peak, ppm from the first record | is the base peak still the same ion, in the same place | 20 ppm and 3σ, or 40 ppm outright |
| Base peak intensity | is it still giving what it gave | 20% and 3σ, or 50% outright |

The score is the cosine the library search itself uses, so "how alike are
these two spectra" has one answer in this program and not two; the reverse
cosine is kept beside it, because a standard that has picked up an impurity
has kept everything it had and gained something. The table also carries the
score against the **previous** record, which is what says whether a change
happened at one verification or crept in over several.

The mass chart is the one metric that cannot be a percentage of its own
centre — a median of zero ppm has no percentage of itself — so its limits
are written in ppm and its trend is a plain difference. A base peak more
than 50 ppm from the reference's is not charted at all: that is a different
ion, not a mass error, and the row says `not the same ion` with both masses
beside it. This is the [[mass-drift]] lesson in another place — a
measurement that cannot be shown to be of the same ion is not judged.

## Three records, not two

No limit is drawn through fewer than three records. Below that every chart
says **too few to chart** and the records are still listed, because a median
and a spread taken from two points are a line through two points and a
reader shown limits will read them. A batch gets six, and can: it is
acquired in an afternoon. A history accumulates one record per
verification, and six of those is a year.

## What a record has to carry

Two fields are written into every record made from this version onwards,
and neither can be recovered afterwards:

- **Acquired** — the day the instrument measured, taken from the file, not
  the day the record was typed in. A folder acquired over three months and
  written into a library in one afternoon is three months of history, and
  `added 2026-09-10` says nothing about the standard. It is shown, read
  only, in the *Add spectrum to library* dialog.
- **Base peak intensity** — the base peak's height in counts. Every library
  format holds peaks as a share of the base peak, so how big the spectrum
  was is lost the moment the record is written unless it is written too.

A record made before those existed is still read: it sorts by the order the
file holds it in, its intensity is left off that chart, and both facts are
said on the chart rather than passed over.

A third field is written by [[new-standard]] and by nothing else: the
**lot**, in the record's comment. It is not a measurement and nothing in an
acquisition holds it, which is exactly why it has to be typed when the
standard is entered — a history that spans a change of bottle is two
histories drawn as one, and the lot is the only thing that says where the
join is.

A standard entered through that dialog has its first history entry the moment
it is created, because the entry *is* the record: this page is the library
read back, and nothing writes a history separately.

## What was measured

Nine ZenoTOF bile-acid infusions, written into a library of their own and
read back: nine records, seven series, all acquired on one day. **Two
records at one energy is what the folder holds** — the `_TESTEARTIGO`
acquisitions were expected to be repeats of the `_mix1` ones at the same
energies, and are not. They isolated m/z 839.56 over a 100–1000 survey
where the `_mix1` infusions isolated 430.34 over 50–500, and the history
says so without being told: at EAD 22 eV the second record scored **8** with
a base peak at 839.2343 against 377.3015 — *not the same ion* — at 2.4% of
the first record's height; at 12 eV it scored **0** at 0.9% of it.

Because no real series reaches three records, the limits were exercised by
cutting six of the infusions into three consecutive thirds each — eighteen
records, six series, one standard at one energy per series, nothing changed
between them. That is the floor of the measurement: the score against the
first third was **98.7 to 100.0**, the base peak held to **0.4 ppm**, and
the base-peak height varied by **up to 4.5%**, which put one of the six
intensity charts one point past two sigma. One third of the cholic acid-d4
EAD 22 eV spray had its base peak change from the fragment at 377.3014 to
the precursor at 430.3489 — two peaks of nearly equal height, and which is
taller changes through a run. That record left the mass chart as *not the
same ion*, which is the intended answer.

Reading a library of nine records into a full history takes about 3 ms.

## What it is not

It is a control chart of one standard against itself, and shares the limit
[[batch-qc]] states: it cannot tell an instrument that changed from a vial
that did. Several standards falling together at one verification is what
says which, and that judgement is the analyst's — this draws the charts
that make it possible. **Export CSV…** writes every record with what each
chart said above the rows.

It also needs records, which means somebody has to have written them. The
same two rules — fifty ppm for *the same ion*, twenty per cent for *the
same response* — are applied to a whole tray at once by
[[compare-infusions]], which reads a reference day out of its project file
instead of out of a library, and needs nothing to have been added to one.

It also compares a series only with itself. Which of a standard's series is
worth keeping at all — which collision energy and activation identifies it,
which quantifies it and which belongs in a record — is a different question
from whether one of them has moved, and [[collision-energy]] is where it is
asked, of the infusions rather than of the records.
