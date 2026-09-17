---
title: Spectral library
---
The **Library** tab of the [[explorer]] searches the spectrum on screen
against a spectral library — MassBank, MoNA, GNPS or NIST records, or a
laboratory's own — and lists the records that match.

It sits beside [[lipid-maps]] rather than replacing it. The *Explain* tab
there asks what a structure *could* produce; a library asks what somebody
*recorded* from the compound on an instrument. The two answer different
questions and disagree in useful ways: a structure explains a spectrum its
compound has never been measured for, and a library carries the intensity
pattern no enumeration of bonds predicts.

## Loading a library

**Load library…** takes an MSP file — the format NIST defines and MassBank,
MoNA and GNPS all export — or an MGF. The file is read once, the count of
records and how many carry a precursor is shown, and the path is
remembered so the library is there at the next start. Field names vary by
exporter (`PrecursorMZ`, `PRECURSORMZ`, `Precursor_type`, `Formula`) and are
read without regard to case; fields the program does not know are kept and
shown on hover.

## Searching

**Search the spectrum on screen** takes the spectrum the Explorer is
showing — centroided if it was a profile — and the active channel's
precursor, and scores every record whose precursor sits within
**Precursor ±** of it. The tolerance is at least the precision the channel's
precursor was written with: a method value of `647.5` is known to ±0.05,
and a filter of ±0.02 around it would be asking for digits it lacks.
A record states its precursor twice — as `PrecursorMZ`, and again as the
mass its `Formula` and `Precursor_type` give — and **either** statement
puts it in the window, so no record is lost because its own two numbers
disagree. A record that states neither is left out unless **Also records
with no precursor** is ticked — measured on MassBank, 24,000 of 139,000
records carry no written precursor, and a filter that admitted them all
had every search dominated by them; ticked, they are scored with their Δ
ppm shown as `—`, so the reader knows the filter could not apply to them.
Measured peaks under one per cent of the base peak are not matched
against; the baseline of a product spectrum is full of them.

An adduct also declares a charge sign, so a record can be asked whether it
belongs to the polarity the scan was measured in — and it is. Records
whose adduct is of the other sign are left out unless **Also the other
polarity** is ticked. The polarity is the active channel's, read from the
file: it is not typed anywhere, because a scan's polarity is a fact about
the acquisition and the only choice you have is whether to honour it. A
record that says nothing about its own polarity is kept either way — the
gate refuses what contradicts the query, never what is silent.

A record has to land at least **Matched peaks ≥** of its peaks to be
listed, two by default. One peak in common is a coincidence: on the same
batch a spectrum that was mostly the phosphocholine ion at 184.07 scored
83 against a laxative whose fragment sits 13 ppm away, and a one-peak
record matched on it was a perfect score for nothing.

Each library peak, strongest first, is paired to the nearest measured peak
still free within **Peaks ±** ppm, so a strong library ion is never robbed
of its match by a weak one listed earlier.

## The two scores

| Score | What it asks |
|---|---|
| **Score** | the cosine between the two spectra, over everything both hold, intensities square-rooted so that one base peak does not decide everything |
| **Reverse** | the same cosine, but only over the library's peaks: whether they are in the measured spectrum, with the measured spectrum's other peaks ignored |

A high reverse with a low score is a compound present with company — a
co-eluting impurity, or a survey scan with more than one ion in the
isolation window. A high score with everything matched is the record
itself. Both are shown as percentages; **Matched** is how many of the
record's peaks found a partner.

## Δ ppm, and which precursor it is measured against

`PrecursorMZ` is whatever the record's author typed — often two decimals,
sometimes truncated rather than rounded. `Formula` and `Precursor_type`
together give the mass the ion actually has, to as many decimals as the
elements do. Where a record carries both, Δ ppm is measured against
**that**, and the **Δ from** column says `formula`; where it does not, Δ
falls back to the written value and the column says `written`, so a number
is never read as more than it is.

It changes what the number means. Measured on a real infusion: cholic
acid-d4's record says `430.35` and the channel that searched it says
`430.34` — two decimals of the same ion, and against each other they read
**−23.2 ppm**, one typist against another. Against 430.3465, which is what
`C24H36D4O5` as `[M+NH4]+` weighs, the same search reads **−15.1 ppm**,
and that is the query's own truncation and nothing else.

A record whose two accounts of itself disagree by more than the written
one is good to says so on its row: the Precursor cell shows both, as
`414.3400 ≠ 414.3516`, and hovering explains. Which of the three — the
formula, the adduct, or the typed mass — is wrong cannot be told from
here, so this is reported and never repaired. "Good to" is a whole unit in
the last written decimal, since a method writes `286.2` for 286.2741 as
readily as it rounds, and never tighter than 25 ppm.

That floor was measured. On a 449,627-record in-silico lipid library whose
every record writes five decimals — claiming ±0.000005 Da — 96.8% of the
records sit inside 0.5 ppm of their own formula, 3.1% inside 1 ppm and 309
inside 2 ppm, which is the exporter's rounding, and then there is nothing
at all until **one** record 116,411 ppm out. Held to half a unit in the
last decimal, 30% of that library reads as broken; held to 25 ppm, one
record does — `TG d5 17:0/17:1/17:0`, whose `[M+NH4]+` record says
768.57491 where `C54H97D5O6` gives 869.8329, and whose `[M+H]+` record in
the same file is right. The flag found a genuinely wrong record in a
public library and nothing else.

## The matched peaks, and the overlay

Selecting a record lists its peaks against the measured ones — mass, mass,
ppm, and the share of each spectrum's base peak — and **Overlay on
spectrum** draws the record's peaks over the spectrum pane, scaled to its
base peak, the way the [[mass-calculator]] overlays an isotope pattern.
**Clear overlay** removes it.

## Two mass axes in one comparison

A record written while [[mass-recalibration]] was switched on carries peaks
the instrument never reported: every one of them was moved by a few parts
per million before the record was written, and its comment says so —
`recalibrated −5.2 ppm`. A record that says nothing was written from the
numbers the instrument gave. Both are legitimate; they are not the same
measurement, and a search between them has to say which is which.

So the **Axis** column on every hit says what the record was written from,
and — when the spectrum on screen is itself on a corrected axis, which the
Explorer passes with it — how the two combine:

| The two axes | What the hit says |
|---|---|
| neither corrected | *record and query both on the instrument's axis* |
| both corrected | *record corrected −5.2 ppm, query corrected −6.1 ppm: each on the axis its own lock masses define* |
| one of the two | *record on the instrument's axis, query corrected −5.6 ppm: 5.6 ppm apart by construction* |

**Two corrected spectra are on one axis, however far apart the corrections
were.** Each was moved onto the masses its own acquisition's lock masses
define, so the difference between the two corrections is how far apart the
two runs had drifted — which correcting them is what removed. What is
*apart by construction* is a correction one side carries and the other does
not: that one sits in every Δ ppm of the comparison and in every peak the
pairing had to decide on. Where it is wider than the **Peaks ±** tolerance
of the search, the row is marked and the line under the hits says so, in
those words: the score is then measuring the axes and not the compound.

**Re-search with the axis matched** asks the question again with the
spectrum moved onto the record's axis — a corrected query put back where
the instrument read it to meet an uncorrected record, or an uncorrected one
moved to meet a corrected record. Nothing on screen changes; the masses are
moved for that search only, and the line says which axis was used.

It is a diagnosis, not a repair. It takes out the difference that was put
there by the corrections; it does not put either side on the *right* axis,
and where the record is the uncorrected one it moves the query off its own
lock masses. Measured below, one hit of 61.0 became no hit at all that way.
What puts a whole library on one axis is **Rewrite from files…**.

### Measured: a record's axis against a query's, four ways

The three bile-acid standards, CID infusions written into a library of
their own twice — once from the axis the instrument reported and once with
the recalibration on — and each EAD infusion of the same compound searched
against both libraries, itself both ways. The corrections are each
acquisition's own precursor ladder ([[mass-recalibration]]): the CID
records **+3.8, +6.6 and +2.0 ppm**, the EAD queries **−5.3, −5.6, −8.6 and
−7.5 ppm**. Each cell is *score / median |Δ ppm| over the paired peaks*.

At the search's default **20 ppm** peak tolerance:

| query | both as measured | record raw, query corrected | record corrected, query raw | **both corrected** |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | 6.5 / 11.5 | 6.5 / 7.7 | 6.5 / 9.2 | **6.5 / 4.3** |
| CA-d4 EAD 22 eV | 29.3 / 10.8 | 29.3 / 5.2 | 29.3 / 7.0 | **29.6 / 3.5** |
| DCA-d4 EAD 22 eV | 34.3 / 13.0 | 35.3 / 4.6 | 35.3 / 6.4 | **35.5 / 2.4** |
| TDCA-d4 EAD 22 eV | 61.4 / 9.8 | 61.4 / 3.1 | 61.4 / 7.8 | **61.4 / 2.1** |

At **5 ppm**:

| query | both as measured | record raw, query corrected | record corrected, query raw | **both corrected** |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | **no hit** | 1.8 / 0.9 | 1.8 / 2.4 | **5.1 / 3.4** |
| CA-d4 EAD 22 eV | 1.0 / 3.4 | 16.5 / 2.1 | 15.9 / 2.5 | **26.6 / 2.5** |
| DCA-d4 EAD 22 eV | **no hit** | 13.8 / 4.1 | 2.7 / 4.3 | **33.5 / 2.2** |
| TDCA-d4 EAD 22 eV | **no hit** | 61.0 / 3.0 | 2.4 / 4.4 | **61.0 / 2.0** |

Three things come out of it, and one of them changed the program.

**Both corrected is the best of the four, every time.** At 20 ppm the
scores barely move — a pairing that was already succeeding goes on
succeeding — but the masses agree far better: the median gap per paired
peak falls from 9.8–13.0 ppm to 2.1–4.3. At 5 ppm that is the whole result:
three of the four queries have **no hit at all** when neither side is
corrected, and all four match when both are.

**And that is so although the two corrections are furthest apart there.**
TDCA-d4's record was corrected +2.0 ppm and its query −7.5 — 9.5 ppm
between them — and it gave the best agreement of the row, 2.0 ppm per peak.
The first version of this warned on that pair, on the arithmetic that two
different corrections must mean two different axes. The measurement says
otherwise, and the rule now is the one above: what counts is a correction
one side carries and the other does not.

**Matching the axis is not the same as correcting it.** TDCA-d4 at 5 ppm
against the uncorrected record scores 61.0 with the query corrected, and
**no hit** once the query is moved back onto the record's uncorrected axis
— because the record itself was 2.0 ppm out. Matching the axes removes the
difference the corrections put there and leaves whatever error each side
had of its own. It says how much of the agreement was the correction; it
does not manufacture agreement, and it is not the repair.

## Measured on MassBank

The full MassBank export in NIST format — 139,006 records, 137 MB — reads
in five seconds and takes about 1.3 GB of memory, since every record's
peaks are held as arrays ready to match. A filtered search answers in
milliseconds; one with no precursor filter, which has to consider every
record sharing two peaks with the query, in two to seven seconds.

Against the product-ion spectra of a real batch, the filtered search
returned the compound where the library had it — a C16 sphingomyelin at
score 46 and reverse 79, a C16 ceramide at 32 and 94, a C24:1 ceramide at
11 and 90, a C18 sphingomyelin at 48 and 96 — and nothing for the C17
internal standards, which are not in MassBank. The scores are low and the
reverse scores high because a product-ion scan on a TOF carries the
precursor, its isotopes and the whole low-mass region as well as the
fragments the record lists: on such spectra the reverse score is the one
to read, and the plain score says how much else was there.

## Measured on a large lipid library

The other library measured here is an in-silico lipid MSP of **449,627
records**, 224 MB, every one of them positive mode: 6.1 seconds to read,
2.2 GB held, and 5.9 seconds more the first time a search asks what the
formulas weigh — worked out once, on demand, so a library that is loaded
and never searched pays nothing.

**449,525 of 449,627 records (100.0%) carry a formula and an adduct that
both read.** The 102 that do not are all `[M]+`, a radical cation this
program does not model; they keep their written precursor and their
polarity, and their Δ says `written`.

Then the 143 product-ion channels of one real injection — a TripleTOF
5600, positive, one compound per channel — were each averaged, centroided
and searched against it over a ±0.5 Da window. 132 channels returned hits
and 11 returned none. **2,414 of the 2,415 hits listed had their Δ
measured against the formula** and one against the written value: the
`[M]+` case. The search took a median of 6 ms, and 5.8 s on the one
channel whose window holds most of the library.

The polarity gate on that batch removed **nothing** — every top-20 list
identical with it and without it, on all 132 channels — because a
positive-mode library queried by positive-mode scans has nothing to
refuse, which is the half of the gate that must not misfire. The other
half was measured by asking the same 143 channels for negative-mode
records: **zero hits**, all 449,627 records refused. The interesting
middle — a library holding both polarities, where the gate has something
to choose — was not measurable here: the MassBank figures above were taken
when that export was on the machine, and it is not there now.

## Your own library

A deuterated internal standard infused on purpose is in no public library.
The spectrum on screen is the only record of it there will ever be, so
**Add spectrum to library…** writes it into a library of your own: an MSP
file you choose once, appended to, and readable by anything that reads MSP
— including this program, MS-DIAL and MSPepSearch.

The first time, a file is asked for; after that the panel says how many
records it holds. The dialog asks only for what the acquisition cannot
supply and prefills everything it can:

| Field | Where it comes from |
|---|---|
| **Name** | yours. It is what a search will show, and a record without one is not read back at all |
| **Precursor m/z** | the active channel, or whatever is typed in **Precursor** above |
| **Adduct** | offered from the polarity that was run — `[M-H]-` for a negative method, `[M+H]+` for a positive one — and any other adduct may be typed. Change it if the ion was not the one offered |
| **Formula** | yours, if it is known; a record does not need one, but a record that has one is worth more |
| **Collision energy** | the channel information, where the instrument recorded one |
| **Comment** | the spectrum pane's own title — sample, channel, and the scans the average was taken over — with the file and today's date |

The spectrum is written as **centroids**: sticks, one per ion, not the
profile points. If the [[chromatograms-and-spectra]] pane is showing a
profile spectrum it is centroided on the way out, the same as for a search.
Peaks under one per cent of the base peak are dropped — the baseline of a
product scan is thousands of them, and a record carrying them matches
anything — and at most two hundred of what is left is kept, strongest
first. Intensities are stored relative to the base peak, as a percentage,
which is how every library format holds them.

The record goes into the file as NIST-style MSP: `Name`, `PrecursorMZ`,
`Precursor_type`, `Formula`, `Collision_energy`, `Comment`, `Num Peaks`,
then the peak list. `PrecursorMZ` is written with the precision it was
given and no more — `430.35` stays `430.35`, and is not padded out to
`430.3500`, which would claim four decimals a method value does not have
and have the record's own formula call it wrong. If the library loaded is
the file just written to, it is read again straight away, so the new
record can be searched for immediately — which is also the check that it
was written in a form the parser reads back.

**Give the record its formula and its adduct.** They are not labels: the
search computes the ion's real mass from them, measures Δ ppm against it,
and refuses the record to a scan of the other polarity. A record of your
own is the one library record you can be sure carries them.

**And the record knows which mass axis it was written from.** With
[[mass-recalibration]] switched on, the spectrum on screen is not the one
the instrument reported — every peak has been moved by a few parts per
million — so the comment carries `recalibrated −5.2 ppm` and what it stood
on, whether the record was written from the Explorer, from the whole folder
at once, or by a rewrite. A record that says nothing was written from the
instrument's own numbers, which is what every record made before this
existed was. From there the axis is read back everywhere it matters: a
search states the combination of the two axes and warns when they are
further apart than its own peak tolerance, and [[standard-history]] keeps a
corrected record and an uncorrected one in separate series when the
correction between them is large enough to break the pairing.

### One standard, from its bottle

A third way in, and the one that starts from the vial rather than from a
spectrum already on screen: [[new-standard]] asks for the name, the lot and
the infusion file and writes the record and the method's component together,
so a standard entered once is searchable, quantifiable and has a history from
the same moment. The record it writes carries one field these two do not —
the **lot**, in its comment — which is what says two records months apart are
of the same material.

### A whole folder in one go

A folder of infusions is nine spectra, and adding them one at a time from
the Explorer means nine dialogs. The **Infusions** tab has already averaged,
centroided and identified every one of them, so **Add all to library** on
that tab ([[infusion-report]]) writes one record per row into the same MSP —
the file chosen once, appended to, asked for the first time if it is not set
yet.

Each record takes its name from the compound the row proposes, its adduct
and formula from what the row identified, its collision energy and
activation from the channel, its `Acquired` from the file, and its peaks
from the very numbers the table was measured on. Nothing is read again and
nothing is centroided twice.

Two rows produce no record, and both say so on the line under the table
rather than being counted silently:

- **a row whose compound could not be proposed.** The compound is the part
  of the file name before the first separator, and a record nobody can find
  by name again is not a record.
- **a row already in the file.** The key is the **provenance in a record's
  comment: the acquisition file and the channel inside it**. Not the
  compound and not the name — the same vial infused twice is two
  measurements and belongs in the file twice, while the same channel of the
  same file written twice is one measurement written down twice, which turns
  a history into a chart of nothing. So pressing the button again after
  adding two more files adds those two files and nothing else.

The line reads *7 record(s) written, 2 skipped: …* with each skipped row
named and the reason beside it.

### Rewriting from the files

A library of your own is written a record at a time over months, and a
record written in March carries what March's version wrote: no `Acquired`,
no `Base_peak_intensity`, no formula, a precursor typed to two decimals.
The acquisitions are usually still on disk, so the record does not have to
stay that way. **Rewrite from files…**, beside **History…**, reads every
record whose comment names a file it can find, averages the same scans of
the same channel again, centroids it with the same floor and ceiling, and
writes the record back in place with everything this version writes —
including a `PrecursorMZ` that agrees with the record's own formula rather
than with whatever was typed.

Where files are looked for: the folders the open acquisitions were opened
from, the last folder anything was read from, and the library's own folder.
A comment names a file and never a path, because a path stops being true the
moment the acquisition is copied anywhere.

**A record whose file is gone is kept exactly as it is**, listed by name
with the reason, and so is one whose comment names no acquisition at all —
somebody else's records in the same file, for instance. The spectrum in such
a record is the last copy of that measurement, and losing it to a tidy-up is
the one thing here that cannot be undone.

**The library as it was is copied to `<name>.msp.bak` first**, before
anything is written over, and the summary line says so. Nothing is written
at all when there was nothing to rewrite.

Where [[mass-recalibration]] is switched on and the acquisition is one of the
open ones, the record is rewritten on the **corrected** mass axis and its
comment then says `recalibrated −5.2 ppm`: a mass axis that has been moved
and does not admit it is worse than one that is wrong.

### Measured on a folder of nine infusions

The nine ZenoTOF bile-acid infusions — three compounds, positive mode, one
product-ion channel each — measured in the Infusions tab and then written in
one press:

| | |
|---|---|
| rows measured | 9, in 35 s |
| **Add all to library** | **9 records written, none skipped, in 0.01 s** |
| pressed again | 0 written, 9 skipped, each *already in the file from …* |
| the file | 19 KB, 9 records |
| **Rewrite from files…** | **9 of 9 rewritten in 39 s** |
| peaks after the rewrite | **identical, every value of every record** |
| other fields after the rewrite | unchanged, 9 of 9 |

Add all costs nothing because the table had already done the work; the
rewrite costs 39 seconds because it averages nine whole runs again, which is
the same 35 seconds the measurement took in the first place. The peaks being
identical is the point of the comparison: the record is written from the
peaks the tab picked, and the rewrite picks them the same way from the same
scans, so a difference would mean one of the two was not reading what it
claimed to.

With the three compounds in the component table, seven of the nine records
carry a formula and an adduct — `C24H36D4O5` as `[M+NH4]+` for cholic
acid-d4, the four labels put back from the name — and their `PrecursorMZ` is
written as **430.34651**, what that ion weighs, rather than as the `430.35`
the method typed. None of the nine disagrees with itself.

The other two are the pair named `CA-d4_…TESTEARTIGO`, whose channel
isolates **839.56** and not 430.35 (see [[infusion-report]]). No adduct of
the formula reaches that mass, so those two records are written with **no
formula and no adduct at all** — only the measurement, the precursor the
instrument was given and the provenance saying which file and channel it
came from. That is the intended outcome: the file name says cholic acid-d4
and the acquisition says otherwise, and a record that carried the formula
anyway would put the compound's name on a spectrum of a different ion. Their
base peak is 109 counts, which the record's `Base_peak_intensity` says out
loud.

Then one acquisition was put out of reach — the same folder with that one
`.wiff` left out — and the library rewritten again: **8 rewritten, 1 kept**,
listed as *CA-d4 (CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_TESTEARTIGO.wiff is not
on disk)*, and that record came back with its peaks and every one of its
fields identical to what they were.

### Measured on three infused standards

The acquisitions this was written for: cholic acid-d4, deoxycholic acid-d4
and taurodeoxycholic acid-d4, infused one at a time into a ZenoTOF 7600 in
**positive** mode, product-ion scans, one channel each and no column. The
[[direct-infusion]] verdict calls all of them infusions, so each record is
the average of **every scan of the run** — 473, 473 and 257 of them, over
1.98, 1.98 and 1.07 minutes — centroided:

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| profile points in the average | 255,113 | 242,308 | 192,688 |
| centroids | 811 | 1,059 | 455 |
| at or above 1% of the base peak | 204 | 226 | 25 |
| peaks in the record | 200 | 200 | 25 |
| what bound it | the 200 ceiling | the 200 ceiling | the 1% floor |
| base peak | 359.2870 | 361.3017 | 468.3072 |

A search of a spectrum against a record of the same compound is one of the
three checks an [[infusion-report]] sums up, and its score, reverse score and
the record's own provenance are printed there beside the head-to-tail
picture.

Three records, 8,144 bytes, written in under a second. Read back, all three
returned with every field they were written with, the masses within
5·10⁻⁶ Da and the relative intensities within 5·10⁻⁷ — the rounding of the
text, and nothing else.

Then each compound was **re-acquired with electron-activated dissociation at
22 eV** and that average searched against the three records, which were
written from collision-induced dissociation at 45, 40 and 30 eV. This is a
harder question than the same channel of a different injection: the record
and the query are not merely two measurements, they are two ways of breaking
the molecule.

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| its own record came first | yes | yes | yes |
| its score | 29.2 | 33.3 | 61.5 |
| its reverse score | 38.8 | 43.8 | 68.7 |
| matched peaks | 22 of 200 | 19 of 200 | 8 of 25 |
| the best *wrong* record | 14.1 | 14.0 | 10.3 |
| Δ ppm against the record's formula | −15.1 | −28.0 | −18.1 |
| Δ ppm against its written precursor | −23.2 | +0.0 | +0.0 |

**A different compound does not match.** Searched against the other two
records with no precursor filter, the best wrong score anywhere is 14.1 with
a reverse of 31.2 — half to a sixth of what the compound's own record gives
— and CA-d4's spectrum returns **no match at all** against TDCA-d4's record,
fewer than two peaks in common. With the precursor filter the panel applies
by default there was exactly one record in the ±0.02 Da window each time and
it was the right one; the filter changes no score and no order here, only
which records were scored at all. A search takes 0.1 – 1.6 ms.

### What the formula and the adduct changed here

The three records were then written again **with their formulas and their
adducts** — `C24H36D4O5` `[M+NH4]+`, `C24H36D4O4` `[M+NH4]+`,
`C26H41D4NO6S` `[M+H]+` — and nothing about the matching moved: the same
scores, the same reverse scores, the same matched peaks, the right record
first each time. What moved is the Δ column, and one record grew a flag.

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| written precursor | 430.35 | 414.34 | 504.32 |
| what its formula and adduct weigh | 430.3465 | 414.3516 | 504.3291 |
| apart by | 3.5 mDa, +8.1 ppm | 11.6 mDa, −28.0 ppm | 9.1 mDa, −18.1 ppm |
| a two-decimal number is good to | ±10.8 mDa | ±10.4 mDa | ±12.6 mDa |
| flagged | no | **yes** | no |

CA-d4's Δ used to read −23.2 ppm — the record says `430.35` and the
channel that queried it says `430.34`, two decimals of the same ion, one
typist against another. Against 430.3465, which is what the ion weighs, it
reads −15.1 ppm, which is the query's own truncation.

DCA-d4 is the one worth reading. Its record and its query carry the *same*
typed number, `414.34`, so the old Δ was **+0.0 ppm** — perfect agreement
between two copies of the same mistake. Against the formula both are 28
ppm out, past the ±10.4 mDa a two-decimal number is good to, so the record
is flagged. And the acquisition settles which of the three is wrong: the
surviving precursor in DCA-d4's own EAD scan measures **414.3525**, 2.2
ppm from `C24H36D4O4` `[M+NH4]+` and 28 ppm from the method's `414.34`
(CA-d4's measures 430.3489, 5.6 ppm from its formula). The formula is
right and the typed mass is not — but that is the instrument saying so,
not the flag, which only reports that the two disagree.

TDCA-d4 at 9.1 mDa is not flagged and should not be: `504.3291` truncated
to two decimals is `504.32`, which is how methods write masses.

**A wrong adduct is caught outright.** The same CA-d4 record written
`[M-H]-` instead of `[M+NH4]+` — the ion these infusions were first
assumed to be — puts its formula 19.0446 Da from its own written
precursor, so it is flagged; and the polarity gate then refuses it to the
positive scan that would otherwise have matched it, one hit becoming none
until **Also the other polarity** is ticked.

**A record is one energy, and one way of breaking the molecule.** The same
CA-d4 spectrum re-acquired at 12 eV instead of 22, against the same
CID record, scores **6.4 with a reverse of 21.3 on 8 matched peaks** — from
29.2, 38.8 and 22 at 22 eV. Splitting the two causes apart: a record written
from CA-d4's own EAD 22 eV average scores 100.0 against itself (which is the
round trip, exact), **67.4** against its 12 eV average, and 29.1 with a
reverse of 55.7 against the CID 45 eV average. So the change of energy costs
about a third of the score and the change of activation costs most of the
rest. The ranking survives all of it — the right record was first every
time — but the number beside it does not travel between methods, and a
threshold picked on one is not a threshold on another.

### Measured on a sphingolipid batch

On a real batch of product-ion acquisitions — 26 injections of a method
whose 144 channels are one compound each, at its own collision energy,
which is the same shape as an infusion of a standard:

Fourteen records were written from the first injection, each the average
of all 61 scans of one channel, centroided. Eleven thousand to twenty-one
thousand profile points became 84 to 3,650 centroids and 7 to 82 peaks in
the record; the file is fourteen records in 13.9 kB, built in under two
seconds. Read back, all fourteen returned with every field they were
written with, the masses within 5·10⁻⁶ Da and the relative intensities
within 5·10⁻⁷ — the rounding of the text, and nothing else.

Then the **same channels of a different injection** were searched against
that library, with no precursor filter, so the match is spectral alone:

| | Injection 02 | Injection 13 |
|---|---|---|
| the right record came first | 14 of 14 | 14 of 14 |
| its score | 13–95, median 60 | 33–95, median 63 |
| its reverse score | 45–96, median 87 | 61–99, median 83 |
| the best *wrong* record | 42 | 42 |

A different compound does not match. The record made from the standard at
354.3 was searched against every one of the other thirteen channels of the
second injection: nine of them returned **no match at all** — fewer than
two peaks in common — and the best of the rest scored 19 with a reverse of
67, against 95 and 96 for its own channel. With the precursor filter the
panel applies by default, each search had exactly one record in the window
and found it.

The scores read low for the same reason as the MassBank figures above: a
product-ion scan on a TOF carries the precursor, its isotopes and the whole
low-mass region as well as the fragments, and none of that is in a record
built from a cleaner average. The reverse score is the one to read.

## Fragmentation across energies

A record is one spectrum at one collision energy, and a record does not
travel between energies: on the nine bile-acid infusions a cholic acid-d4
record measured under CID at 45 eV scores **6** against the same vial under
EAD at 12 eV and **29** against it at 22 eV. Read as a hit list that says
the compound is not there, which is false.

Where a compound has records at two or more energies of the same
activation, the panel adds one line under the hit list per compound and
activation:

> compatible with CA-d4 EAD at ~18 eV (score 0.71; measured at 12 and 22)

The line answers the other question. The hit list asks *which record is
this like*; this asks *what conditions would produce this*. It is added,
never a replacement: the hit list is unchanged.

### How the line is worked out

Each of the compound's records is reduced to the share of the intensity its
own ladder rungs carry — the water-loss ladder the record's `Formula` and
`Precursor_type` predict through [[lipid-maps]]'s enumeration, plus the
strongest fragments the records agree on. **Shares of the profile's total,
never of the record's base peak**, because the base peak itself walks down
the ladder as the energy rises (see the table below), and a number whose
own denominator changes rung cannot be interpolated through.

Each rung's share is then linear in energy between the two measured
energies that bracket it, and the panel sweeps the range at half an
electronvolt for the best fit. Three refusals are as important as the
answer:

* **Nothing is extrapolated.** Past the highest energy on file the ladder
  goes on walking downwards and no record says how fast. A spectrum
  measured beyond the range can only be reported at the end of it.
* **No two activations are interpolated across.** EAD records and collision
  cell records are separate profiles, and a record whose activation is not
  stated is a third — the same rule [[standard-history]] cuts its series on.
* **One record is one record.** With a single energy on file the line reads
  *one energy on file (22 eV): no profile*.

The score is the cosine over the profile's own ions, square-rooted the same
way the hit list's scores are. It is not the plain cosine: a profile holds
a dozen ions and a product-ion spectrum holds hundreds, so the plain cosine
would measure everything else in the vial. A `~` before the energy means it
was interpolated rather than measured.

### Measured on the nine bile-acid infusions

Cholic acid-d4 was infused at EAD 12 eV, EAD 22 eV and at 45 eV in a file
whose name states no activation. Its profile, as shares of the profile's
own total:

| Ion | m/z | EAD 12 eV | EAD 22 eV | 45 eV, unstated |
|---|---|---|---|---|
| `[M+NH4]+ +4D` | 430.3465 | 83.5% | 24.6% | 0.0% |
| `[M+H]+ (-NH3) +4D` | 413.3200 | 0.0% | 0.9% | 0.0% |
| `[M+H-H2O]+ +4D` | 395.3094 | 0.0% | 6.5% | 0.0% |
| `[M+H-H2O]+ +3D` | 394.3031 | 0.0% | 0.3% | 0.0% |
| `[M+H-2H2O]+ +4D` | 377.2988 | 1.5% | 25.2% | 1.7% |
| `[M+H-2H2O]+ +3D` | 376.2926 | 1.3% | 2.0% | 0.0% |
| `[M+H-3H2O]+ +4D` | 359.2883 | 0.0% | 6.2% | 54.2% |
| `[M+H-3H2O]+ +3D` | 358.2820 | 0.0% | 6.5% | 6.8% |
| twelve shared fragments under m/z 150, together | | 13.7% | 27.8% | 37.2% |

That is the ladder walking. At 12 eV the ammoniated precursor is 83.5% of
everything; at 22 eV it has handed a quarter of the intensity to
`[M+H-2H2O]+`; at 45 eV the precursor is gone entirely and `[M+H-3H2O]+`
is 54.2% with the small fragments taking most of the rest. **The base peak
is a different ion in all three files**, which is exactly why the profile
is held as shares of its own total.

Two of the nine files are named `CA-d4` and isolate 839.56 rather than
430.34. They are left out of CA-d4's profile with the reason on the row —
*holds fewer than 2 of the ladder's ions* — and nothing had to read a file
name to know it.

### What two energies per activation allow, and what they do not

Honestly: not much yet, on these files. Leave EAD 12 eV out of the library
and search it back, and the profile has one EAD record left and says *one
energy on file (22 eV): no profile*; the 45 eV record cannot help, because
its activation is unstated and no activation is interpolated across. Leave
EAD 22 eV out instead and the same thing happens with 12 eV. **Two records
of one activation is the minimum, and leaving either out takes it below the
minimum.**

With both EAD records present, the sweep does what it should: the 12 eV
spectrum comes back at 12 eV and the 22 eV spectrum at 22 eV, both at a
score of 1.00, and the two 839.56 files score 0.10 and 0.11. The 45 eV
spectrum comes back at 22 eV — the top of the EAD range, since nothing is
extrapolated — at 0.56, which is the same 0.56 its reverse score against
the 22 eV record alone was. That is the honest result of two points: the
best fit lands on one of the two records, so the line adds the *energy*,
which a hit list cannot state, and not a better score. A third energy under
one activation is what would make the interpolation worth its own number,
and nobody has acquired one yet.

What the arithmetic does when a spectrum genuinely sits between two
records was checked on these rungs by asking for the halfway shares: the
sweep answers 16.5 to 17 eV, and everything from 15 to 20 eV scores within
one per cent of the best. **So a proposal is good to a few electronvolts,
not to the half-volt step**, which is why it is written with a `~`.

Building a profile and sweeping it takes about 3 ms over a nine-record
library.

## What the library does not know

A record is one instrument's spectrum at one collision energy. A match is
evidence that the measured spectrum resembles that record; how much
resemblance is enough is the analyst's call, and the [[accurate-precursor]]
and the [[formula-finder]] are the independent checks on the precursor that
a library match does not make.

An energy profile does not lift that. It says which of the *recorded*
conditions a spectrum resembles and at what energy between them; it does
not say the compound is the right one, and it cannot propose an activation
nobody has recorded.

## Reading your own library back

A library of your own accumulates one record per verification of the same
standard. **History…**, beside the record count, reads those records back as
a control chart of the standard over time — see [[standard-history]].

## From a script

`api.Library.open(msp)`, `.search(spectrum)` and `.add(spectrum, name)` do
all of this without the window, taking the precursor and the polarity off
the spectrum and centroiding it before a record is written — see
[[python-api]].
