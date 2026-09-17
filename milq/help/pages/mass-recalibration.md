---
title: Mass recalibration
---
[[mass-drift|Mass drift]] asks whether the instrument's mass axis *moved*
during the run, and answers against the batch's own median because that is
the only reference a run can supply for itself. Recalibration asks the other
half of the question — **is the axis in the right place at all** — and
corrects it if it is not.

The switch is *Recalibrate m/z from the internal standards*, on the
**Mass drift** tab of the Analytics workspace. It is off by default and is
saved with the project.

## What counts as a lock mass

A lock mass here is an internal standard that meets four conditions:

1. it carries a **formula and an adduct** in the [[method-workspace|method]],
   so its true mass is known. *Fill formulas from names* fills the empty
   Formula cells from the lipid shorthand in the names themselves —
   `SM(d18:1/12:0)`, `C16:0-Ceramide`, `PC 34:1` — and keeps each one only
   where it agrees with the precursor already written down;
2. its precursor lies inside the survey scan's mass range, so it can be
   measured — [[check-method|Check method]] lists the ones that do not;
3. its measured ion held together across the run, which is the same
   `same_ion` test the [[mass-drift|drift]] measurement applies: injections
   disagreeing by more than 25 ppm were not measuring one ion, and averaging
   them would recalibrate the instrument onto whatever happened to be
   nearest;
4. it measured that ion **near where the formula puts it** — within
   **50 ppm**, in most of its injections. Condition 3 asks the injections
   whether they agree with *each other*; it cannot ask whether they agree
   with the compound, and a standard whose ±0.25 Da window holds the same
   *wrong* ion in every injection agrees with itself perfectly. One past the
   limit is named in the table — *measures 237 ppm from its formula: not the
   ion the formula names* — and is not used, however steadily it was
   measured. Where a standard is inside the limit in most injections and past
   it in one, only that injection loses it, and that injection's row says so.

**Where 50 ppm comes from.** Measured over the 1,439 survey measurements the
real batch supplies — all 60 formula-bearing components inside its survey, in
every injection — the distance from the formula is bimodal: 19.5% of them
under 20 ppm, 53.5% past 200 ppm, and the floor of the trough between the two
lobes at 30–50 ppm, where a 10 ppm bin holds 1.0–1.4%. Fifty is that trough's
far edge, and it is twice the 25 ppm condition 3 already tolerates: an ion
allowed to wander a spread's worth may sit a spread's worth from the truth
and no further. The margins either side are each about a factor of five —
11.7 ppm in the honest lock mass's worst injection, 237 ppm for the impostor.

The **written precursor is deliberately refused**. A method that says `647.5`
is good to about 800 ppm at that mass; correcting a mass axis towards
somebody's rounding is worse than not correcting it. Type the formula.

## What is fitted

One correction per injection:

- an **offset** in ppm — the median of that injection's lock-mass errors,
  sign flipped;
- a **linear term** in ppm per dalton, but only where **four or more** lock
  masses span at least 100 Da *and* a leave-one-out test says the line
  predicts a held-out lock mass better than the plain offset does. A line
  through the points it is then scored on is exact and says nothing, which is
  the same warning the [[integration-algorithms|Gaussian fit]] carries; four
  rather than three, because holding one of three out leaves a line through
  two points, which is exact again.

A correction from **one** lock mass is an offset and the table says so: there
is no second measurement left over to check it against, and its residual goes
to zero by construction rather than by agreement.

## Where it applies

While the switch is on:

- the m/z axis of spectra in the [[explorer|Explorer]], whose title then
  reads `· recalibrated +3.2 ppm`;
- the [[accurate-precursor|accurate precursor]] measurement, which reports
  the raw and the corrected mass side by side — the measured value is never
  overwritten, because the correction was fitted from it;
- the extraction window of every [[manual-xic|XIC]] and every integrated
  peak. The window moves; the reader's own arithmetic does not. Rows carry
  the correction that was applied to them.

With the switch off nothing changes at all, and a project saved before this
existed reopens with it off.

## What the real batch said

Measured on the 26-injection sphingolipid batch this was written against
(TripleTOF 5600, a single 50–700 survey, one scan every 14.6 s).

**Formulas.** The method carried none. *Fill formulas from names* read 125 of
its 141 component names and 10 of its 11 internal standards, in
milliseconds and without opening a file:

| | |
|---|---|
| filled from the name | **125** of 141 |
| refused — the name's formula is not the written precursor | 16 |
| names that are not lipid shorthand | 0 |
| internal standards given a formula | **10** of 11 |

All sixteen refusals are the *precursor* being wrong rather than the name:
`dHCer(d18:0/12:0)` is written 484.465 against its formula's 484.4724
(15 ppm), `LacCER(d18:1/18:1(9Z))` exactly 2.0000 Da low, the thirteen
`HexCer_2OH` and long-chain ceramide rows about 0.13 Da. Each is listed with
both numbers, and the cell is left empty — see [[check-method]].

**Lock masses.** A formula was the missing half of the question and turns
out not to be the binding one. Of the 60 components that now carry a formula *and* lie
inside the survey, exactly **one** measures the same ion in injection after
injection:

| | |
|---|---|
| injections corrected | 25 of 26 |
| lock masses each | **1** (offset only) |
| median offset | **+4.8 ppm** (−4.4 to +11.7) |
| spread of the offsets | 16.1 ppm |

**What the formula gate refuses.** Five of the ten standards carrying a
formula are named as measuring an ion their formula does not: `Sphingosine
C17:0` at 383 ppm from it, `C17:0_Ceramide` at 237, `C12:0 _Ceramide` at 204,
`Cer1P (12:0)` at 91 and `Sphingosine-1-P C17:0` at 82 — the last of these
straddling its formula, with a median error of only −43 ppm and most of its
injections past the limit either side. Every one of them had already failed
condition 3 or was short of the injections a trend needs, so the fit below is
unchanged to the last decimal and not one injection lost a measurement: on
this batch the gate is a guard rather than a finding. The near miss says why
it is worth having. `Sphingosine C14:0`, an analyte rather than a standard,
holds its measurement to **52 ppm across 25 injections** — twice the same-ion
limit and no more — at a median **156 ppm** from its formula. That is one
ion, measured steadily, and it is not the compound; nothing but the formula
can say so.

The other ten standards fail for a reason no formula can fix: their survey
signal is too weak, so the ±0.25 Da search window catches a different
neighbour in each injection and they scatter by 98 to 534 ppm across the run
— and one lies outside the survey altogether. `C17:0_Ceramide` was found in
only five injections and its median sits 237 ppm from its own formula, which
is a different ion rather than a badly measured one. **Several lock masses
are not available on this batch at any formula coverage**, so the linear
term has still never fired on real data.

The figure that matters is what happens to *other* components. Fifty-one
analytes inside the survey now carry a formula — against fifteen when this
was first measured — and were measured in every injection: 1,228
measurements in all. Over all of them the median error is −247 ppm before and
−241 ppm after, because most are interferences rather than the compound and
nothing at the ppm scale touches those. Over the 197 measurements that were
within 25 ppm to begin with:

| | before | after |
|---|---|---|
| median error | −7.0 ppm | **−1.4 ppm** |
| median magnitude | 8.6 ppm | **6.8 ppm** |
| smaller after | | 122 of 197 |

So it moves the centre in the right direction, and it cannot be better than
the single lock mass it came from — whose own scatter of 16 ppm across the
run is larger than the 4.8 ppm it corrects by.

## It changes the numbers

Reprocessing that whole batch both ways, over ±20 ppm extraction windows, a
median 5 ppm shift moved **1,769 of 2,593 integrated areas**: a median
absolute change of 1.3%, 830 rows past 5%, and ten rows that no longer found
a peak. A time-of-flight instrument stores few points across a window that
narrow, so moving the window's edge takes whole points in or out.

Turning this on is a quantitative decision, not a display preference. Fit it,
read the per-injection table, and switch it on only when the lock masses
justify it — then process the batch again so the results follow.

## An infusion recalibrates on its own precursor

Everything above needs a **batch**: a compound of known composition measured
in injection after injection, so that one injection's error can be told from
another's. A [[direct-infusion|direct infusion]] is one acquisition of one
vial, and there is no second injection anywhere.

It does not need one. An infusion sprays the compound for a minute or two and
the average of the whole run holds the precursor **together with its own
fragments**, and arithmetic already knows where each of those belongs: the
intact adduct, the `[M+H]+` an ammonium leaves behind when it hands over its
proton, the ladder of cumulative water losses, and — for a labelled standard
— the rung beside each of those that shed a deuterium with the water. Those
are the same ions the [[lipid-maps|LIPID MAPS tab]] predicts for a formula.
Each one that is actually there is an independent measurement of a mass the
formula already knows, in the same acquisition, at a different mass.

So an infusion is recalibrated against **itself**. Nothing has to be typed:
the compound is the part of the file name before the first `_`, its formula
comes from the standards table, LIPID MAPS or the lipid shorthand, and the
adduct is read off the precursor the channel was given. The fit happens when
the Explorer averages the whole run, and the pane's title then reads
`· recalibrated −5.6 ppm from 8 rungs`.

### The rules

- a rung is matched to the **strongest peak within 20 ppm** of where the
  formula puts it, and only above 100 counts — the fixed floor the
  [[accurate-precursor|accurate precursor]] holds a survey scan to, because
  below it a window is a stretch of axis whose tallest point is noise. It
  is the one place on an infusion where the fixed hundred still stands
  rather than the floor measured off the acquisition ([[signal-to-noise]]),
  and the page says so rather than leaving two floors to be confused;
- the correction is the **intensity-weighted median** of the rungs' errors,
  sign flipped. Weighted, because a peak of twelve thousand counts locates
  its centroid better than one of a hundred; a median, because one rung
  caught on a neighbour should not drag the axis part of the way towards it;
- it is an **offset and nothing else**. The rungs of one precursor span the
  waters it can lose — 72 Da at the widest measured — against the 100 Da a
  slope needs before it is extrapolation, and the row says so with the
  file's own span;
- a rung disagreeing with the others by more than **25 ppm** is a different
  ion inside the window: it is dropped and named;
- under **two** rungs, nothing is corrected and the row says why. Two, not
  one: a single rung is the precursor measured against its own formula with
  nothing to check it, and an infusion has no other injection to be read
  against.

### What it applies to

While the switch is on, and behind the same switch as everything above: the
averaged spectrum in the [[explorer|Explorer]] and its title, the
[[lipid-maps|explanation]] — whose basis line then prints the strongest
rung's error raw *and* corrected — the [[spectral-library|record written to
your own library]], whose comment says the axis was moved and what by, the
per-compound [[infusion-report|infusion report]]'s *Mass axis* paragraph, the
*Mass axis* column of the Infusions tab, and a row of its own in the
per-injection table on the **Mass drift** tab with *from the precursor
ladder* as its source.

### What the nine real infusions said

Nine ZenoTOF 7600 bile-acid infusions, positive mode, one product-ion channel
each and **no survey scan at all**. The last four columns are the LIPID MAPS
explanation run at its own 5 ppm default, on the axis as measured and on the
corrected one:

| infusion | rungs | offset | spread | span | ions before | after | intensity before | after |
|---|---|---|---|---|---|---|---|---|
| CA-d4, EAD 12 eV | 3 | −5.3 ppm | 7.5 ppm | 54 Da | 2 of 56 | 2 of 56 | 2.8% | **83.7%** |
| CA-d4, EAD 22 eV | 8 | −5.6 | 6.3 | 72 | 5 of 56 | **8 of 56** | 14.0% | **63.6%** |
| CA-d4, CID 45 eV | 3 | +3.8 | 1.3 | 19 | 2 of 56 | 2 of 56 | 24.2% | 24.2% |
| DCA-d4, EAD 22 eV | 8 | −8.6 | 19.9 | 72 | 2 of 41 | **5 of 41** | 16.2% | **53.0%** |
| DCA-d4, CID 40 eV | 3 | +6.6 | 2.8 | 18 | 1 of 41 | **3 of 41** | 1.6% | **17.1%** |
| TDCA-d4, EAD 22 eV | 5 | −7.5 | 3.3 | 37 | 0 of 104 | **5 of 104** | 0.0% | **78.4%** |
| TDCA-d4, CID 30 eV | 4 | +2.0 | 2.2 | 37 | 4 of 104 | 4 of 104 | 72.1% | 72.1% |
| CA-d4, EAD 12 eV, `_TESTEARTIGO` | — | — | — | — | — | — | — | — |
| CA-d4, EAD 22 eV, `_TESTEARTIGO` | — | — | — | — | — | — | — | — |

Seven of the nine are corrected, from three to eight rungs each, by −8.6 to
+6.6 ppm. The three CID offsets read +3.6, +6.2 and +1.8 ppm when this table
was first written; re-measured for [[integration]] they read as above, to the
figures [[spectral-library]] quotes, with the same rungs. The two that are not
are the right refusal: the `_TESTEARTIGO` pair
is named for cholic acid-d4 and isolates **839.56**, which is none of that
formula's adducts, so there is no ladder to look for and the row reads *no
lock mass* with that reason. The sign is not the same for all seven — the
EAD acquisitions read high, the CID ones low — which is why this is fitted
per acquisition and never once for the instrument.

The figure that says it was worth doing is the last pair of columns. CA-d4 at
EAD 22 eV reaching **8 of 56 ions and 63.6% of the intensity at 5 ppm** is
exactly what that file gave at *10 ppm* on the uncorrected axis: the
correction buys back the tolerance that had been widened to absorb it, and a
tolerance absorbing an axis error is a tolerance testing nothing. Nothing got
worse: the two files that do not move were already inside 5 ppm at their
strongest rungs and come back identical to the tenth of a per cent.

### And a record of your own travels between activations

A record written from one infusion and searched with another of the same
compound — the [[spectral-library|own-library]] round trip — before and
after, at the search's default 20 ppm peak tolerance and at 5 ppm:

| record / query | peak tolerance | axis | score | reverse | matched | median &#124;Δ ppm&#124; |
|---|---|---|---|---|---|---|
| CA-d4 EAD 22 / EAD 12 | 20 ppm | as measured | 67.4 | 67.4 | 12 of 42 | 0.6 |
| | | recalibrated | 67.4 | 67.4 | 12 of 42 | 0.6 |
| DCA-d4 EAD 22 / CID 40 | 20 ppm | as measured | 33.4 | 70.0 | 21 of 39 | 12.3 |
| | | recalibrated | **34.5** | **71.3** | **23 of 39** | **2.6** |
| TDCA-d4 EAD 22 / CID 30 | 20 ppm | as measured | 61.5 | 69.4 | 8 of 32 | 8.6 |
| | | recalibrated | 61.5 | 69.4 | 8 of 32 | **2.1** |
| CA-d4 EAD 22 / EAD 12 | 5 ppm | as measured | 65.9 | 66.3 | 11 of 42 | 0.4 |
| | | recalibrated | 65.9 | 66.3 | 11 of 42 | 0.5 |
| DCA-d4 EAD 22 / CID 40 | 5 ppm | as measured | **no hit** | | | |
| | | recalibrated | **31.8** | **69.6** | **19 of 39** | 2.5 |
| TDCA-d4 EAD 22 / CID 30 | 5 ppm | as measured | **no hit** | | | |
| | | recalibrated | **61.0** | **69.1** | **7 of 32** | 1.9 |

At 20 ppm the scores barely move — a pairing that was already succeeding goes
on succeeding — but the *masses* agree far better: the median gap between a
paired record peak and the measured one it landed on falls from 12.3 to
2.6 ppm and from 8.6 to 2.1. At **5 ppm** that is the whole result. Two of
the three pairs do not match at all on the instrument's own axes, because the
two acquisitions sat 14.8 and 9.3 ppm apart from each other; both match once
each is corrected against its own precursor. CA-d4's pair was 0.3 ppm apart
to begin with and does not move, which is the control: the correction does
not manufacture agreement where there already was some.

### And the record says which axis it was written from

That table compares two spectra treated the same way. A library is not
treated all at once: it is appended to over months, some of it while this
was switched on and some of it while it was off. So a record of your own
**carries the correction that was in force when it was written**, in its
own comment — `recalibrated −5.2 ppm`, with what the correction stood on —
whether it was written from the spectrum pane, from a whole folder of
infusions at once, or by *Rewrite from files…*. A record that says nothing
was written from the numbers the instrument gave, and every record made
before this existed is exactly that.

From there it is read back rather than assumed:

- a **search** says which axis each side was written from and how the two
  combine, and warns where a correction one side carries and the other does
  not is wider than the tolerance its peaks were paired within. *Re-search
  with the axis matched* asks again with both on one axis;
- a **[[standard-history]]** keeps such records in separate series, so a
  correction is never charted as the standard changing;
- **Rewrite from files…** writes every record whose acquisition is still on
  disk from the axis in force now, which is what puts a library that was
  filled in both states back onto one.

The four combinations of a record's axis and a query's — both corrected,
neither, and each of the two mixtures — are measured on these same
acquisitions in [[spectral-library]]. The short version is that both
corrected is the best of the four every time, that neither is the worst,
and that **two spectra corrected by different amounts are not two axes**:
the pair whose corrections were 9.5 ppm apart agreed to 2.0 ppm per peak,
better than any other combination of that compound.

## See also

- [[direct-infusion]] — what makes a sample an infusion at all
- [[infusion-report]] — where the *Mass axis* paragraph is printed
- [[mass-drift]] — the measurement this is fitted from
- [[accurate-precursor]] — the survey measurement of one component's mass
- [[check-method]] — which precursors the survey can see at all
- [[report]] — the corrections table is printed under the mass section
