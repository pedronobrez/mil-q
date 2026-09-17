---
title: The infusion report
---
**Process ▸ Report this infusion…** writes one compound on two to four
pages: the document that goes in the notebook when a standard is validated.
A [[report]] answers what a batch measured; this answers something smaller
and older — *is this vial what the label says it is?* — and it answers it by
listing what was checked, not by passing or failing anything.

The action is offered only while the active sample is a [[direct-infusion]],
because everything on the page is the average of a whole run, which is a lie
about a chromatographic sample. **Process ▸ Report every infusion…** does the
same for every infusion open, one section per compound in one document, each
compound starting a fresh page.

## What each block holds

**The header** comes from the file rather than from its name: the
acquisition, the sample, the instrument, the polarity, the product-ion
channel with the precursor as the method wrote it, the collision energy, how
many scans were averaged and over what time — and the accurate precursor,
with its error in ppm and where it was measured. Where the acquisition has a
survey scan the measurement is [[accurate-precursor]]'s, with the product-ion
scan as the same-ion check. Where it has none — which is every one of the
nine real infusions this was built against; they carry one product-ion
channel each and nothing else — the precursor is read from the averaged
product-ion spectrum itself and the report says so in those words.

*Scans averaged* is the line [[direct-infusion]] describes: how many scans
the acquisition holds, how many went into the average and where the rest
went — *473 scans, 464 averaged; 9 left out: 0.008 min; 1.069–1.099 min, 8
scans*. Those are the scans where the spray faltered, and a report that left
them out says so on the header and again in one sentence of the verdict. With
**Process ▸ Include unstable scans** on, the same two places say instead that
they were kept on request, so a document says which average it is of.

**The averaged spectrum**, drawn for paper at the label floor the pane was
left at, so the masses printed are the masses that were on screen — see
[[chromatograms-and-spectra]] for the floor and how labels are placed. Under
it, the twenty-five strongest peaks above that floor with their intensities
and their share of the base peak, and one sentence saying what this
acquisition's **noise floor** was measured to be — the two estimates, the one
that was taken and what averaging the run bought. See
[[signal-to-noise]]; the floor is what the precursor gate, the unexplained
peaks and a record of your own are all held to, so the number they were held
to is printed with them rather than left to be guessed at.

**The adduct**, which everything under it hangs off. Which ion the channel's
written precursor *is* — protonated, ammoniated, sodiated — decides every
predicted mass, so the basis line names it, gives the exact mass of that
adduct and how far the written value sits from it in ppm, and says whether
it was read off the written precursor alone or confirmed against a survey
scan. Where no adduct of the formula reaches the written precursor, nothing
is explained and the line says which the closest misses were. See *Adducts*
in [[lipid-maps]] and [[accurate-precursor]].

**The structural explanation**, when one was run in the [[lipid-maps]] tab —
a curated record, a drawing of one's own, or a formula and its losses. Every
matched ion with its theoretical mass, the measured mass, the error in ppm
and, for an unplaced label, how many deuterium the fragment kept. Then, in a
table of its own, **the peaks it does not account for**: the honest half of
the answer, and where a co-infused impurity or the wrong compound shows
itself. Each of those carries what it might be — a known contaminant, a
satellite of an ion that *was* matched, or a composition assembled from the
precursor ion's own atoms — with the error of that guess in ppm, and the
sentence under the table says how many were accounted for either way. See
*What the unexplained peaks might be* below.

Under the matched ions the section carries **the margin** — what this
compound explains against what the best of its nearest impostors explains,
on the same peaks and by the same arithmetic:

> Margin — CA-d4 explains 63.6%; the best of 17 neighbour(s)
> (TG 17:1/18:4/18:4 as [M+2H]2+) explains 21.7%: a margin of 41.9 points

A share is not evidence until something else has been scored beside it, and
under ten points the sentence says so: the spectrum did not tell the two
compounds apart, whatever the share was. The Infusions tab carries the same
figure as a **Margin** column, with the whole list of rivals in its tooltip.
[[lipid-maps]] sets out which records count as impostors, why an isomer of
the same formula is not one, and the eleven real spectra the ten-point line
was measured on.

**The isotopic purity**, when the compound carries labels and an adduct was
identified — the number on the certificate that nobody measures. The block is
the envelope itself: every rung from d0 to dn with its *m/z*, its intensity,
its share of the fully-labelled ion and its fitted fraction, then the species
pair (`d4 96.2%, ≥d3 99.1%`) and the atom per cent, which is the quantity the
certificate states and is a different number. Where the envelope cannot be
solved the rungs are printed all the same with the reason under them, because
a refusal is a statement about those numbers and a reader who cannot see them
cannot check it. That is the outcome on every one of the nine real infusions,
for a reason [[lipid-maps]] sets out: a product-ion scan's precursor has been
through the quadrupole, and the carbon-13 satellites the solve needs went with
it.

**The library result**, when a search was run in the [[spectral-library]]
tab: the best record, its score and reverse score, how many of its peaks
matched, the precursor difference in ppm, the two spectra head to tail, and
the record's own fields as they were written — the file it was made from, the
collision energy and the date. A record whose provenance is not on the page
cannot be checked against the acquisition it came from.

**The mass axis**, always — whether it was corrected or not. A direct
infusion has no second injection to be read against, so it is recalibrated
against **itself**: the precursor is in the average together with its own
fragments, and arithmetic already knows where each of those belongs. The
paragraph names every rung that was found, its theoretical and measured
mass, its error before and after the correction and its height; the offset
and how many rungs it stood on; and, where the same explanation was run
both ways, how many predicted ions landed on a peak on the axis as measured
and on the corrected one. Where nothing was corrected the paragraph says
that instead, with the reason — a vial that was looked at and left alone is
a finding, and a page that omitted the paragraph would leave a reader unable
to tell a corrected axis from an uncorrected one. The rules and what the
nine real infusions gave are in
[[mass-recalibration|An infusion recalibrates on its own precursor]].

**Other infusions of the same compound**, when any are open: each averaged
over its own whole run and drawn head to tail against this one, with the same
cosine a library search takes. The dialog ticks those whose file name starts
with the same compound and lets any of them be ticked or unticked, because a
naming convention is not a measurement.

## What the verdict does and does not claim

*What was measured* is one sentence per check, and a check that was not run
gets no sentence:

- **"Precursor confirmed at +20.7 ppm…"**, or **"Precursor not confirmed:
  …"** with the reason. A window holding less than this acquisition's own
  measured noise floor is not a mass: it is reported as too little to measure,
  with the height that was found, rather than as a centroid taken over noise.
  The floor used to be a hundred counts whatever the instrument had done; it
  is now measured off the average — 0.068 to 4.27 counts on the nine
  infusions here, measured on the masked average this page prints, which is
  not quite the whole-run floor the [[explorer]] shows: see [[integration]]
  for the two side by side — and the sentence names which of the two it
  refused against. What
  clears the floor is a peak that is really there; whether it is the compound
  is the ppm beside it, which is a different question and gets a different
  number.
- **"8 of the 56 ions predicted for … were found"** — the denominator is how
  many ions the prediction offered, so the reader can see what the count is a
  share of, and the strongest unexplained peak is named beside it.
- **"Best library record … at score 29, reverse 39"**, with the precursors'
  difference in ppm.
- **"Collision energy differs from the record's (22 against 45 eV)"** — a
  spectrum taken at another energy has other fragments, so a low score there
  is the energy and not necessarily the compound.
- **"9 scan(s) of 473 were left out of the average: …"**, with the times, why
  each went and how well the rest of the run repeats itself. It is last
  because it is not a check on the compound: it is a fact about the spectrum
  the checks above were made on. A run whose spray never faltered gets no
  sentence.

There is no pass, no fail and no badge. Whether the vial holds what it should
is a judgement made from evidence by somebody who knows what was weighed into
it, and a green tick invites nobody to read the rest of the page. Where
nothing at all was run the verdict says exactly that, and the document is a
spectrum and a peak table — which is a fair description of it.

Every report written is recorded in the [[audit-trail]]: what was reported,
into which file, and which of the three checks stood behind it.

## Measured

Cholic acid-d4 infused into a ZenoTOF 7600, the same vial under two
activations, explained from the component table's `C24H40O5` — read as
`C24H36D4O5` from the four labels the name declares, and as `[M+NH4]+`
because that is what the channel's 430.35 is — and searched against a record
made from the CID run:

| | CID, 45 eV, 473 scans | EAD, 22 eV, 146 scans |
|---|---|---|
| base peak | 359.2870 | 377.3015 |
| precursor 430.35 in the product-ion spectrum | 430.3196 at 84 counts, 1.49%, **−70.7 ppm** (floor 1.43) | 430.3489 at 9,415 counts, **+20.7 ppm** |
| ions found, of 56 predicted | 2 — 24.2% of the intensity | 8 — 63.6% |
| against the CID record | 97 / 100, its own record — see below | **29 / 39**, 20 of 179 peaks |
| collision energy against the record | same | **22 against 45 eV** |
| against the same compound at 12 eV | 7 / 29 | 67 / 81 |

Measured on the EAD run, adding one block at a time: the spectrum and its
peaks alone, **two pages**; with the precursor, two; with the structural
explanation and its unexplained peaks, two; with the library record and its
head-to-tail picture, **three**; with one other infusion compared as well,
**four**. Each took between 0.3 and 1.0 s to lay out and print. Two compounds
in one document came to eight pages in two seconds.

The two rows worth reading twice are the last two of the CID column. Its
library score — 97, with every one of the record's peaks found — is a record
matched against the spectrum it was made from, which proves the file was
written and read back and nothing else; and
2 of 56 ions is what a formula with three neutral losses can say about a CID
spectrum whose ladder has already run to completion — the two it finds are
the three-water loss and the same ion with a label gone. Neither is a
failure of the compound, and the report is built so that the page says which
is which.

### Isotopic purity, on the same nine files

The purity block was run on all nine of the bile-acid infusions, and every
one of them came back *not measured* — with its own numbers on the page. The fully-labelled ion's carbon-13 satellite, which the
formula puts at 26.5 – 30.0% of it, measures 0.006 – 0.206%:

| infusion | d4 rung | M+1 measured | ratio to the formula | read |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | 83,712 | 0.006% | 0.0002 | not measured |
| CA-d4 EAD 22 eV | 66,655 | 0.028% | 0.0010 | not measured |
| CA-d4 CID 45 eV | 607 | 0.095% | 0.0036 | not measured |
| DCA-d4 EAD 22 eV | 38,178 | 0.015% | 0.0006 | not measured |
| DCA-d4 CID 40 eV | 296 | 0.150% | 0.0057 | not measured |
| TDCA-d4 EAD 22 eV | 36,447 | 0.020% | 0.0007 | not measured |
| TDCA-d4 CID 30 eV | 2,272 | 0.206% | 0.0069 | not measured |

The two `TESTEARTIGO` rows have no block at all: nothing identified an ion for
them — their method isolates 839.56, which is no adduct of the formula their
name declares, and *When the name and the method disagree*, below, is what
they turned out to be — so there is no envelope to print.

The number the envelope *would* have given, if the check were switched off, is
98.3 – 99.0% d4 on all seven precursors — which would sit comfortably above a
certificate's `≥98 atom % D` and would mean nothing, because it moves with the
collision energy: 98.32%, 98.77% and 98.98% for three acquisitions of the one
bottle of cholic acid-d4 at 12, 22 and 45 eV. The ladder, tried the same way,
gives 36.7%, 90.1% and 85.0% for those same three. **What the data says is
that these files cannot answer the question**, and the honest report of a
d4 standard's purity from this instrument needs one minute of TOF MS beside
the product-ion channel. [[lipid-maps]] has the arithmetic and the rest of the
evidence.

### What the unexplained peaks might be

Listing a peak nobody explained as a bare mass is honest and it is not
useful: the reader is handed `217.1880` and left to type it into something
else. So each of the listed peaks is offered the best of three hypotheses,
with its error in ppm beside it — a **known contaminant or solvent
cluster**, a **satellite of an ion that was matched** (its carbon-13 peak,
its sodiated or potassiated form, a water or ammonia loss from it, another
adduct or a dimer of the precursor), or a **composition built from the
precursor ion's own atoms**.

The third is the one worth explaining. A general formula search on a mass of
300 comes back with a list nobody reads, but a product-ion spectrum is not a
general search: a fragment cannot carry atoms the precursor has not got. The
element ranges are therefore the precursor ion's own composition — the
molecule's atoms plus whatever the adduct brought, with two hydrogens' slack
upwards for a rearrangement — so the question becomes *what could this
precursor have left behind at this mass*, and a peak with no answer at all
is a finding: whatever it is, it is not a piece of this compound.

Measured on four of the ZenoTOF bile-acid infusions, taking the strongest
twenty-five unexplained peaks of each:

| | unexplained above the floor | annotated | satellite | contaminant | composition | nothing | composition, median \|ppm\| |
|---|---|---|---|---|---|---|---|
| CA-d4, CID 45 eV | 126 | 25 | 1 | 0 | 24 | 0 | 8.9 |
| CA-d4, EAD 22 eV | 20 | 20 | 0 | 0 | 20 | 0 | 3.8 |
| DCA-d4, CID | 141 | 25 | 0 | 0 | 25 | 0 | 11.5 |
| TDCA-d4, CID | 9 | 9 | 0 | 0 | 9 | 0 | 5.5 |

Seventy-nine peaks, one satellite, no contaminant and no refusal; the
compositions ran from 0.2 to 16.6 ppm and the whole of each file took
between 0.02 and 0.07 s. The five strongest, one per file, are
`217.1879 → [C16H17D4]+` at −4.6 ppm (14.8% of the base peak, CA-d4 CID),
`78.0465 → [C6H6]+` at +0.8 ppm (22.5%, CA-d4 EAD), `95.0842 → [C7H11]+`
at −13.5 ppm (21.2%, DCA-d4), `343.2915 → [C24H31D4O]+` at −5.5 ppm (6.8%,
TDCA-d4) and, on the same file, `126.0211 → [C2H8NO3S]+` at −6.3 ppm — which
is protonated taurine, the fragment a taurine conjugate is named after.

Read the rest of the table with the same suspicion. Every row says how many
*other* compositions of the same precursor reach the same mass, and on
TDCA-d4's 343.2915 that is eleven: the constraint narrows the question, it
does not answer it. The large errors on the CID files are the files
themselves — those spectra sit several ppm off their own axis, which is what
[[mass-recalibration]] is for, and correcting the axis first tightens every
figure in the last column.

Two things about that table were decided by running it, not by reading it:

- **The Seven Golden Rules are not applied under 150 Da.** They bound the
  element ratios of a *molecule*, and the one that hurts caps H/C at 3.1.
  Protonated taurine is H/C = 4.0, so the rules refused the strongest real
  fragment of the TDCA-d4 file and the table said "no formula within the
  precursor's composition" about a piece the compound is named after.
- **An odd-electron composition is offered, marked, and ranked last.**
  `78.0465` is the strongest unexplained peak of the CA-d4 EAD run at 22.5%
  of the base peak, and it is the benzene cation at +0.8 ppm and nothing
  else. Electron activated dissociation makes radicals; a filter written for
  collision-induced spectra threw the answer away. It is ranked last because
  in a CID spectrum it is usually the wrong answer.

Contaminants earned their place by being rare rather than common. Over all
four files down to a hundredth of a per cent of the base peak — 3,187 peaks —
the table named five: a phthalate at 149.0233, a methanol cluster twice, a
formic acid cluster and an acetonitrile cluster. Nine were satellites of
matched ions and 710, a little over a fifth, had no sub-formula of the
precursor at all. A clean vial is supposed to look like that; the table is
there for the vial that does not.

The same annotations are not in the [[lipid-maps]] tab's own list, which
still shows the unexplained peaks as masses. There was no hook in the panel
to hang them on and the panel is being changed elsewhere; the report is where
they are.

## Every infusion at once: the Infusions tab

A report of one vial answers one question. A folder of nine asks a different
one — which of them measured its precursor, which found its fragments, which
matched the record made of the same compound last month — and that is a
table. The **Infusions** tab of the [[analytics-workspace]] is it: one row per
infused sample, grouped by the compound its file name starts with.

Nothing is measured until **Measure** is pressed: averaging a whole run,
centroiding a quarter of a million points, searching a library and scoring
every infusion of a compound against the others is a few seconds per compound,
and a tab that did that whenever the results changed is a tab nobody keeps
open. The row count appears in the tab's own name once it has.

The columns, in the order they are drawn: **Compound** and **Sample**;
**Isolated**, the mass the method actually isolates read against the name —
see *When the name and the method disagree*, below; **Mode** and **CE (eV)**;
**Scans**, how many were averaged — *464 of 473* where the spray lost some,
with the whole line on hover; **Base peak m/z**; then the precursor three
ways — **Precursor written** as the method wrote it, **Found m/z** as it was
measured back, **Δ ppm** between them and **Height**, what was in the window;
**Adduct**, the ion that precursor was read as; **Ions found** of those
predicted; **Margin**, this compound's share less its nearest impostor's,
with the whole list of rivals in the tooltip; then the best record of your
own library — **Library record**, **Score**, **Reverse**, **Matched** and
**Record Δ ppm**, with **Record CE** against this acquisition's energy;
**Other infusions**, the same compound scored each way; **Mass axis**, the
correction fitted from that vial's own precursor ladder, whether it was
applied, or the reason there is none ([[mass-recalibration]]); and **File**.
The report's own table is narrower — A4 does not hold twenty-three columns —
so it writes the precursor and the record as one cell each and leaves the
parts to the panel and the CSV.

### While Measure runs

**The window stays alive.** The measurement runs on a thread of its own, so
the window repaints, scrolls and answers while it works — measured on the
nine ZenoTOF bile-acid infusions by counting event-loop turns during the run:
**0.4 a second** when it ran on the window's own thread, **89 a second** with
it moved off. That is the difference between a beachball and a window.

A progress dialog names the file being read — *Reading
CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1 — 4 of 9 done* — and **Cancel** stops
it. Cancel is answered **between files, never inside one**: a file being
read is inside the reader and nothing here can interrupt it, so the one being
waited for finishes and the next is not started. What was already measured
**stays in the table**, and the line under it says so — *Cancelled: 4
infusion(s) measured before you stopped, kept as they stand.* Press
**Measure** again to do the rest; the files already done come back from the
cache.

**Rows appear as their files finish**, one at a time and in the order they
were measured, so the first result is on screen in a second or two rather
than everything arriving at the end. Sorting is off while the table is
filling — a table that reorders itself under you between one file and the
next is harder to read — and comes back with the finished summary, together
with the **Other infusions** column, which cannot be filled until the last
infusion of a compound is done.

**A file that fails is one row saying so**, not a stopped run. Nine
infusions where the fourth has lost its `.wiff.scan` are eight measurements
and a reason: the failing row keeps its compound, its sample and its channel
and carries the error in the cells that would otherwise have held
measurements.

The buttons that read the same files — *Measure*, *New standard…*,
*Quantify…* — are disabled while it runs, and the ones that act on the table
come back only if there is a table to act on.

### The cache of averaged spectra

Averaging every scan of an infusion is the expensive half of this, and
nothing about that average depends on the session: it is a function of the
file, the channel, which scans the spray was steady for and whether
[[direct-infusion]]'s *Include unstable scans* was asked for. So it is
written down. **A file that has not changed is read once**, and every later
*Measure* — and the Explorer's own *Average whole run*, and the folder route
of [[command-line]] — reads the average back from disk instead.

The entries live **beside the project**, in `<project>.oqcache/`: the
averages belong to that batch of files, so they are found where the batch is
found and can be deleted with it. With no project open there is nowhere that
belongs to them and the system's own cache directory is used
(`~/Library/Caches/MIL-Q` on macOS) — the directory the operating system
is entitled to empty. See [[projects-and-files]].

What is stored is the **raw** average, before any mass correction: a
correction belongs to the session's switch and is applied on the way out, so
turning [[mass-recalibration]] on and off costs nothing and cannot poison
what was stored. An entry is retired by the file changing — the key holds
the acquisition's size and modification time and **its `.wiff.scan`'s**,
which is where the scans actually are — and also by the channel, the range,
the spray mask and the unstable-scans switch, so two different averages of
one file are two entries.

**File ▸ Clear cached spectra…** empties it and says what went. Nothing is
lost that cannot be measured again; what it costs is the next *Measure*
being a cold one. The directory is bounded — 512 MB, about a hundred and
twenty infusions — and over the bound the least recently *used* entries are
dropped first.

Measured on the nine ZenoTOF bile-acid infusions, each *Measure* in a fresh
process:

| | *Measure* | cache |
|---|---|---|
| cold — nothing cached | 11.8 s | 9 read from file |
| warm — the same nine again | **1.6 – 1.7 s** | 9 from the cache |
| one `.wiff.scan` touched | 2.4 s | 8 from the cache, 1 re-read |
| twenty-seven infusions, cold | 32.5 s | 27 read from file |
| twenty-seven infusions, warm | **3.5 s** | 27 from the cache |

A warm *Measure* is a seventh of a cold one, and the cold one is what the
disk and the reader cost: the warm figure repeats to within a tenth of a
second, the cold one moves by seconds from one drive to another. The nine
averages take **39.1 MB** on disk, 4.3 MB each — against the 47 MB of
`.wiff.scan` they save reading. When the cache first existed a warm
*Measure* still took 7.7 – 8.5 s, and most of that was one line: the peak
picker asked every candidate maximum about every peak it had already kept,
and centroiding a quarter of a million points keeps seven thousand. It now
asks the two nearest, and each average is centroided and scored once per
report instead of five times and three — the same peaks, checked to the
last digit on these nine files. What is left is arithmetic, and the thread
is what stops it freezing the window.

Each row carries the compound and the sample, the mode and collision energy,
how many scans were averaged — *464 of 473* where the spray lost some, with
the whole line on hover — the base peak, the precursor as the method wrote
it and as it was measured back with its error in ppm and its height, the ions
found of those predicted, the best record of your own library with both scores
and the record's collision energy against this acquisition's, and the other
infusions of the same compound with the cosine each way, and the **Mass
axis** column — the correction fitted from that vial's own precursor ladder,
whether it was applied, or the reason there is none. See
[[mass-recalibration]].

Two of those come from somewhere the report of one vial gets them from a
person:

- **the explanation.** Where the [[lipid-maps]] tab has already explained the
  spectrum on screen, that explanation is used. Otherwise the compound is
  looked up in the component table by name and explained from its formula —
  [[annotate-from-lipid-maps]]'s formula path, run with nobody at the tab. Two
  things are read rather than taken as written, both for the same reason —
  a component table has no column for either. The **labels**: a component
  named `CA-d4` whose formula is the unlabelled `C24H40O5` is explained as
  `C24H36D4O5`, because the name says four and the arithmetic is otherwise
  out by 4.025 Da. And the **adduct**: the component's own is used where it
  agrees with the channel's written precursor, and where it does not, the
  precursor wins and the basis line says so — see *Adducts* in
  [[lipid-maps]]. A compound the method does not hold is not guessed at, and
  a precursor no adduct of the formula reaches is not explained at all: the
  cell says which.
- **the library.** The library of your own — the MSP that *Add spectrum to
  library…* appends to, see [[spectral-library]] — searched at the written
  precursor's own precision. A record made from one of these very infusions
  will match itself with every one of its peaks found, which says the file
  was written and read back and nothing else; the row worth reading is the
  same compound under another activation.

**A cell that could not be filled says why rather than being blank.** *only
84 counts survive* is not the same answer as *nothing within ±0.25 Da*, and
neither is the same as *CA-d4 is not a component of the method* — a table of
dashes cannot tell the three apart, and which one it is decides what to do
next. The whole sentence behind a shortened one is in the cell's tooltip.

The column headings sort on their numbers where they have them, so the
weakest precursor or the worst score is one click away.

**Report…** writes the per-compound document — the same one *Process ▸ Report
this infusion…* writes — for the rows selected, or for every row when none is
selected, one section per compound. Rows of the same compound chosen together
are drawn head to tail against each other in it; a row left unselected is left
out of the comparison as well as out of the document. **The whole table gets
the cover** described below and a selection does not, because every count on
that cover is a count of the whole table; the [[audit-trail]] line says which
of the two was written. **Export CSV…** writes
the whole table, every column, selection or no selection: a summary with rows
left out is not the thing it claims to be.

**Add all to library** writes one record per row into your own library —
the MSP *Add spectrum to library…* appends to, see [[spectral-library]]. The
table has already averaged, centroided and identified every row, so a record
is those very numbers with a name and a provenance on them: the compound the
row proposes, the adduct and formula it identified, the channel's collision
energy and activation, the day the file says it was acquired, and a comment
naming the acquisition, the channel and the scans averaged. A row whose
compound could not be proposed is skipped and named; so is a row already in
the file from the same acquisition and channel, which is the key that stops
the same measurement being written twice — press it again after opening two
more infusions and only those two are added. The line under the table says
what was written and what was not: *7 record(s) written, 2 skipped: …*.

The summary line under the table is the one sentence the table adds up to —
*3 compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm;
34 of 458 predicted ion(s) found across 7; 4 with an own record above 60 in
own-bileomics.msp* — counts only, each with what it was counted against. The
batch report prints the table and that line as its *Infusions* section, while
the measurement stands: see [[report]].

### Measured: the tab, on the same nine files

All nine opened at once — three compounds, five of them called `CA-d4` — with
the three CID runs written into a library of one's own and the three formulas
in the component table. **Measure** took **14.1 s**, 1.6 s an infusion; the
document of all nine came to 61 pages in 18 s, most of it the twenty
head-to-tail pictures that five infusions of one compound make.

| | precursor found | ions of predicted | own record |
|---|---|---|---|
| CA-d4 CID 45 eV | 430.3196, −70.7 ppm, 84 counts | 2 of 56 | 97, its own |
| CA-d4 EAD 22 eV | 430.3489, **+20.7 ppm** | 8 of 56 | **29** at 45 eV |
| CA-d4 EAD 12 eV | 430.3488, +20.4 ppm | 3 of 56 | **6** at 45 eV |
| DCA-d4 CID 40 eV | 414.3275, −30.1 ppm, 33 counts | 3 of 41 | 96, its own |
| DCA-d4 EAD 22 eV | 414.3525, +30.3 ppm | 8 of 41 | **33** at 40 eV |
| TDCA-d4 CID 30 eV | 504.3273, +14.4 ppm, 123 counts | 5 of 104 | 100, its own |
| TDCA-d4 EAD 22 eV | 504.3325, +24.9 ppm | 5 of 104 | **61** at 30 eV |

*3 compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm;
34 of 458 predicted ion(s) found across 7; 4 with an own record above 60.*

Four things in that table are worth reading rather than skipping:

- **the two rows not in it.** `CA-d4_TOFMSMS_EAD_12CE_…_TESTEARTIGO` and its
  22 eV twin carry the CA-d4 name and are not CA-d4 acquisitions: their method
  targets **839.56** over 100–1000, their base peak is 839.23, nine and
  seventeen counts sit in the precursor window — a hundred and thirty times
  their measured noise floors of 0.068 and 0.13 counts, so both are now
  measured, at **−43 ppm** — and no record of the library comes within
  ±0.02 Da of 839.56. Those two files are also where the floor's own limit
  shows: their empty regions are the high-mass end of an axis that holds
  nothing, so the floor is a fifteenth of a count while the chemical
  background peaks at a hundred, and a peak above the floor is a peak above
  the background rather than the compound. Their explanation cell now says
  the thing outright — *839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da —
  closest [M+K]+ at 451.2758* — rather than reporting nought ions of
  thirty-one, which was true and left the reader to work out why. The
  *across 7* in the line above is those two rows: an infusion nothing was
  explained for is not counted as one that found nothing. They score
  **73** against each other and **5 to 10** against the three real CA-d4
  files. The name prefix said one compound and the method said another, and
  the row is where that shows — which is the whole reason the compound is
  never anything but a proposal. The *Isolated* column now says it before
  anything is measured, and what the two files actually are is the section
  *When the name and the method disagree*, below.
- **the precursor survives the soft activations, and what is left of it under
  the hard ones is not the precursor.** Every EAD run of a compound measured
  its precursor, at +20.4 to +30.3 ppm. The three CID runs each hold something
  in the window too — 84, 33 and 123 counts — and against a fixed floor of a
  hundred the first two were refused as *too little to measure*. Against the
  floor this acquisition actually has, 1.43 and 0.75 counts, they are 59 and
  45 times the background and plainly there; so they are measured, and they
  come out at **−70.7 and −30.1 ppm**, which is 0.030 and 0.012 Da from the
  written mass. The height says a peak is there and the ppm says it is not the
  precursor, and the sentence on those rows now reads **"Precursor found but
  not confirmed at −70.7 ppm, past the 25 ppm that says the same ion"** —
  *confirmed* is a claim about identity and the summary line always reserved
  it for 25 ppm, so the sentence had to stop where the count does. Measuring
  four more precursors this way therefore added **none** to the four within
  25 ppm: the count on the summary line is unchanged, and what changed is
  that the page now says what is in the window instead of refusing to look.
- **the confirmed errors are all the same sign**, +14.4 to +24.9 ppm — and
  the two the measured floor newly let through in this table are the other
  one, −30.1 and −70.7 (and the two rows not in it, −43), which is a second
  reason to read them as something in the window rather than as the
  precursor. One of the positives, DCA-d4 at +30.3, is past the 25 ppm the
  line counts and is on the page all the same: the count is a sentence, not
  a verdict.
- **a formula finds two to eight ions, and which ones depends on the
  activation.** A formula offers the precursor, the form its fragments carry
  and their neutral losses, and nothing else; the rest of these spectra is
  ring cleavages. That is what the denominator is for. Over the seven real
  acquisitions: **34 of 458** predicted ions found, 2 of 56 on CA-d4 under
  CID against 8 of 56 under EAD at 22 eV, 3 of 41 and 8 of 41 for DCA-d4, 5
  of 104 both ways for TDCA-d4 — the soft activations keep the ladder and the
  hard ones have finished it. The row to compare against is the
  [[lipid-maps]] tab's, where the same compound as a *drawing* is scored
  against thousands of masses instead of dozens.

The library column is the one that says something the rest does not. A record
made from a run matches that run with **every one of its peaks found** —
*179 of its 179 peak(s) matched*, a reverse score of 100 — which proves the
file was written and read back. Its *forward* score is 97, 96 and 100 on the
three, not 100 throughout: the record is written at one per cent of the base
peak and the search reads every centroid, so the query holds peaks the record
was never given. [[integration]] has the three peak counts and why neither
side is wrong. The figures that mean anything here are 6, 29, 33 and 61 — the
same compound, the same vial, under another activation, and a record does not
travel between them.

## When the name and the method disagree

A `.wiff` written by a manual acquisition names its own sample `sample` and
its method `Untitled 1.msm`. Read by reflection, its experiment offers a
polarity, a mass range, a fixed mass, DP, CE, DPS and CES — and a
`TargetedCompoundInfo` that is empty, which is the field SCIEX OS writes a
compound into when a method has one. **On the nine real infusions nothing in
the file says what was sprayed.** The compound is in the file name and
nowhere else.

So the name is a proposal, and the precursor the method isolates is the one
measurement of the same question the file actually holds. MIL-Q compares
them. The compound the name starts with is resolved to a formula — the
standards table of bile acids and their conjugates, then LIPID MAPS, then
the lipid shorthand, the same three [[lipid-maps]] uses, with a trailing
`-d4` read as four labels the formula does not carry — and every adduct of
that formula is measured against the written precursor, at the precision the
precursor was typed with. Where the name fits, the **Isolated** column of the
Infusions tab and the report's header read *430.35 = [M+NH4]+ of CA-d4*.
Where it does not, the same precursor is offered to the component table and
to your own library, and the answer is one of two sentences:

> The file is named CA-d4 but the method isolates 839.56 over 100–1000,
> which is no adduct of C24H36D4O5 within ±0.05 Da; it fits nothing in the
> component table or the library.

> …it fits DCA-d4 [M+NH4]+ (414.3516, +2.0 ppm) from the component table.

The row's **Compound** cell then stops repeating the name: it reads *not
CA-d4*, or *DCA-d4, not CA-d4* where something fits, with the whole sentence
in the tooltip. The grouping does not change — two files named for the same
compound are worth scoring against each other whatever their methods isolate,
and the pair below is only visible *as* a pair because they still were.

The same check runs when a file is opened, and warns once per file, beside
the warning for a `.wiff` with no `.wiff.scan`. **It reads no spectrum**, so
it arrives before anything has been measured: on the nine real infusions it
takes **32 ms a file**, nearly all of it looking the name up in LIPID MAPS,
against the seconds the file itself takes to open. The component table costs
nothing measurable on top — 125 formulas through every adduct came to the
same 32 ms.

**A name is only accepted when it is the compound exactly.** LIPID MAPS is
searched by substring, which is right for somebody typing into a box and
wrong for a check that fires by itself: against the installed database `PC`
answers *PCTR3*, `CE` answers *cedrol*, `Cer` answers *Cerasin* and `TESTOL`
answers *testolactone*. Four sample names of the most ordinary kind, each
resolved to a compound nobody was infusing, and each would then have
contradicted whatever its method isolated. So a database name counts only
when the record's own name, abbreviation or LM_ID *is* the name; the
standards table is an exact lookup and the shorthand is parsed rather than
searched. A name nothing recognises is reported as *not checked* — which is
a different finding from *the name is wrong*, and the two are never
conflated.

### What the two `TESTEARTIGO` files are

They are the acquisitions this check was written for, and they are not
cholic acid-d4.

| | the two `_TESTEARTIGO` | `CA-d4_TOFMSMS_EAD_12CE_…_mix1` |
|---|---|---|
| isolated precursor | **839.56** | 430.34 |
| mass range | 100 – 1000 | 50 – 500 |
| declaration factor | 80 and 44 | 44 |
| base peak | 839.2316 / 839.2343 | 430.3490 |
| base peak height | **109 / 234 counts** | **12,271 counts** |
| centroids in the averaged spectrum | 7,101 / 5,281 | 234 |
| total ion current of the average | 18,537 / 40,453 | 156,716 |

Thousands of centroids at tens of counts each is what an empty acquisition
looks like: a spectrum of noise, centroided. The real infusion beside it has
234 centroids and one of them is fifty times taller than everything in the
other two files put together.

**Nothing anywhere fits 839.56 and nothing in the file supports what does.**
Every positive adduct of cholic, deoxycholic and taurodeoxycholic acid,
their glycine and taurine conjugates, each labelled and unlabelled, as
monomer and as dimer — seventy-two masses — gives exactly one hit at ±0.05
Da: **[2M+Na]+ of *unlabelled* cholic acid, 839.5644, −5.2 ppm**. LIPID MAPS
at ±0.01 Da adds seventeen records over two formulas, `C43H83O13P` as
`[M+H]+` and `C45H76NO10P` as `[M+NH4]+` — phosphatidylinositols and
phosphatidylserines, which nobody was infusing. And the file itself refuses
all of them: within ±0.05 Da of 839.56 the tallest centroid is **9 counts**
in one file and **17** in the other, 8% and 7% of a base peak that is itself
109 and 234. The one ion in the isolation window that is really there sits at
839.23, a third of a dalton — some four hundred parts per million — below
what the method asked for, so it is a neighbour the ±0.5 Da window caught and
not the target.

The conclusion the tab draws is the one the arithmetic supports: **the method
isolated a mass that was typed for something else, and got nothing.** The two
score 73 against each other — two noise spectra from the same source, taken
two minutes apart — and 5 to 10 against the three real CA-d4 files. The file
name is the only thing in either of them that says CA-d4, and it is wrong.

One smaller disagreement of the same kind, visible in the table above: the
12 eV file is named `…_44DP_…` and its method carries a declaration potential
of **80**. The name is a note somebody typed, in both cases, and the method
is what the instrument did.

## A folder at once

**File ▸ Report infusions in a folder…** asks the same question of a folder
that came off the instrument this morning, with nothing opened in the
[[explorer]] and no batch on screen. Point it at the folder, say where the
document goes, and — if you have them — an MSP of your own and a component
table, either a project or a components CSV; it writes the same per-compound
document, and the same summary table as a CSV if that is ticked.

Nothing is added to what is open. Each file is opened into a session of its
own, measured, and closed again before the next one is opened, so a folder of
thirty infusions never holds thirty readers; and a project already open is
left exactly as it was, with one line in its [[audit-trail]] saying a folder
was reported. With no project open there is no trail to write into, and none
is made.

The folder is looked over by [[checking-files]] before anything is opened. A
`.wiff` whose `.wiff.scan` is not beside it is **skipped**, because its
spectra cannot be read and the report is a spectrum; a `.wiff2` is reported as
ignored; a run that does not read as a [[direct-infusion]] is left out with
the flatness figures that say why. Every skip is listed with its reason: a
folder of nine reported as eight is only honest if the other one comes back
with the reason.

The same run is on the command line, for a folder that arrives every week —
see [[command-line]]:

```
MIL-Q --infusion-report ~/data/bile-acids --out ~/reports/bile.pdf \
          --library ~/library/own-bileomics.msp --csv ~/reports/bile.csv
```

### Measured: the folder, on the same nine files

The whole folder from the command line, with the three CID runs as the own
library and the three formulas as a components CSV: **9 files read, nothing
skipped, one 58-page PDF** — two of cover and 56 of sections — in **31 s** at
1.2 GB peak memory; `--per-compound` gives four documents, the cover and one
per compound, the same 58 pages. Written without a cover the same nine
sections come to 56, so the cover costs the two it is. The seconds are the
one figure here that is not the program's — the same run has taken anything
from 27 s on an idle machine to 255 s on a busy one. What is stable is what
it did. Every row is the one the Infusions
tab measured with the nine files open — 2 of 56 ions under CID and 8 of 56
under EAD for CA-d4, 29 and 6 and 61 against the own records, +14.4 to
+30.3 ppm where the precursor survived — which is the point: the folder route
and the open-batch route are the same measurement, and they agree to the
digit.

The two `_TESTEARTIGO` acquisitions are **not** skipped, and that is the
answer to the obvious question about them. They read as infusions, because
they are: 294 and 311 scans of a steady spray. What is wrong with them is not
visible from the chromatogram at all — their method isolates 839.56, their
base peak is 839.23, nine and seventeen counts sit in the precursor window,
and their explanation cell says *839.56 is none of the adducts of C24H36D4O5
within ±0.05 Da — closest [M+K]+ at 451.2758*. A rule that dropped them would
have to have known that in advance; the report is where it is found.

## The cover of a folder report

A folder report opens on the folder and not on its first compound. In front
of the per-compound pages, in the same PDF, is a cover of five blocks — and
it is in the same PDF because a cover in a file of its own is a file that
gets separated from what it covers.

**What this is.** The folder, the day, the version that wrote it, how many
files were read and how many were left out, how many infusions in how many
compounds, the library of your own where one was searched, and the summary
line the Infusions tab shows, to the digit. A document is read back a week
later detached from whatever made it.

**The infusions.** Every infusion on one row, in the columns the tab and the
batch [[report]]'s *Infusions* section use — one definition, so the three
cannot disagree — with a compound's acquisitions kept together even where the
folder came off the instrument with them interleaved. A cell that could not
be filled still says why rather than being blank, cut at a word where the
reason is a whole sentence; the whole of it is on that compound's own page,
which is what the contents list points at.

**What they add up to.** The table above summed, one sentence per column that
can be summed, each of them a count and what it was counted against. There is
no sentence at the end drawing them together and no pass or fail for the
folder, for the same reason there is none for a compound: what a spectrum is
worth depends on what the vial was supposed to hold.

**What was left out.** The skipped files with their reasons, printed whether
or not there are any — *nothing was left out* is a measurement too — and then
what [[checking-files]] found about the folder's own names before anything
was opened.

**The pages that follow.** Each section with the page it landed on. The
heading carries the sample as well as the compound, because a folder is where
one compound is infused five times and a contents list of five identical
lines sends the reader to page 3 to find out whether page 3 is the one they
wanted. The numbers are the pages the sections actually landed on: the
document is laid out once to find them and again to print them, which is the
machinery [[report]] already uses.

With `--per-compound` the cover is written as a file of its own, named
`-cover`, since the pages it introduces are in the others; it lists no page
numbers there, because it has none for them.

### Measured, on the nine

The paragraph the nine real infusions produce, in full:

> 4 of 9 precursor(s) confirmed within 25 ppm; 5 not: 2 whose method isolates
> 839.56, 3 at -70.7 and -30.1 and +30.3 ppm. Own records: 4 above 60, 3
> below — all across a collision-energy change; 2 matched no record at all. Predicted ions: 34 of 458 found across 7
> spectrum(s); 2 had nothing to predict from — no formula in the component
> table for that compound.

Every figure in it is on the page above it, and three of them are the ones
worth reading. The **2 whose method isolates 839.56** are the `_TESTEARTIGO`
acquisitions: a mass no other CA-d4 run in the folder isolates, so they are
not two failures of one ion but two measurements of another, and the sentence
says so with the mass rather than calling them unmeasured. The **4 above 60**
are the three records matched against the runs they were made from and one
more, which is why the sentence counts them rather than concluding from them.
And **2 had nothing to predict from** is the denominator kept honest: an
infusion nothing was predicted for is not counted as one that found nothing.

The cover came to **two pages** of the folder's 58 — the table of nine rows
fills the first and a little of the second — and takes **0.2 s** on its own:
it is written from the rows the run has already made, and reads no file.

## From the infusion to the method

A verified vial is worth something only if what was learnt about it reaches
the method. **Use in method…** on the Infusions tab writes the selected rows
— every row when none is selected — into the [[method-workspace]]'s
component table, one component per infusion, and says where each of them
came from.

What a component gets:

| Field | From |
|---|---|
| Name | the compound the file name starts with — the same prefix the table groups on |
| Formula | whatever the infusion was actually explained with, carrying the deuteriums the name declares: `CA-d4` is `C24H36D4O5`, not `C24H40O5` |
| Adduct | read off the channel's own written precursor, gated on the polarity — see [[lipid-maps]] on why an adduct is not an offset |
| Precursor | the **exact** mass of that adduct and of that formula |
| Fragment | the base peak of the averaged product-ion spectrum, or a peak you pick from the strongest few |
| IS | ticked, unless you untick it on the row |
| Group | `standards` |
| RT | **nothing.** An infusion is not a separation and has no retention time to give |
| Provenance | the sample, the channel, the collision energy, the file, the acquisition time and the record of your own that the spectrum matched |

The precursor is the one to be careful about. The channel says `430.35` and
the component gets `430.3465`, and those are two different claims. The
written value is what the instrument was given: it picked the channel, the
acquisition is on it, and it is good only to the decimals somebody typed —
±0.005 here, which is 12 ppm. The exact mass is what the compound weighs as
that adduct, and it is what a mass window, a lock mass
([[mass-recalibration]]) and a mass-accuracy check have to be built from.
Writing the rounded one into the method would put 12 ppm of error into all
three on purpose. So the exact mass is what is written and **both are shown**
— in the dialog's Note column, in the tooltip and in the [[audit-trail]] —
because nothing should silently replace a number you can no longer see.

Nothing typed is overwritten. A compound the method already carries is
*completed*: only its empty cells are filled, and where a value that is
already there disagrees with the infusion, the Note says so and the typed
value stays — `Precursor 430.3500 written, 430.3465 from the infusion —
kept as written`. Each row ticked is one entry in the [[audit-trail]] under
*Component from infusion*, with the provenance in the note.

That path starts from a table that has already been measured. The other way
round — a vial in your hand, nothing measured yet, and no component, record
or history for it at all — is [[new-standard]], which asks for the name, the
lot and the file and writes all three at once.

Two things the dialog will refuse or decline to do, both worth knowing:

- **a precursor no adduct fits is not written at all.** The row says why
  instead: *839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da —
  closest [M+K]+ at 451.2758*. A component with an invented mass is worse
  than no component.
- **a second infusion of the same compound has nothing left to write.** Two
  collision energies of one vial are one component, and the first of them
  fills the cells the second would have. The status line says which
  compounds those were rather than adding a second row under the same name.

### Measured, on the nine bile-acid infusions

The same nine ZenoTOF acquisitions as the rest of this page, with the three
CID runs written into a library of one's own first, so every row had a
record to name.

| Compound | Formula | Adduct | Written | Exact | Δ |
|---|---|---|---|---|---|
| CA-d4 | C24H36D4O5 | [M+NH4]+ | 430.35 (CID), 430.34 (EAD) | 430.3465 | +8.1, −15.1 ppm |
| DCA-d4 | C24H36D4O4 | [M+NH4]+ | 414.34 | 414.3516 | −28.0 ppm |
| TDCA-d4 | C26H41D4NO6S | [M+H]+ | 504.32 | 504.3291 | −18.1 ppm |

Every formula came from the standards table through the name, with the four
labels the `-d4` declares put in — without them nothing weighs 430 and no
adduct fits at all. Two of the three adducts are ammonium and the third is
not, which is exactly the kind of thing that cannot be assumed.

The fragments are the base peaks, and they are not the same peak at every
energy: CA-d4 gives **359.2870** at CID 45 eV and **377.3015** at EAD 22 eV,
TDCA-d4 gives **468.3072** at CID 30 eV. At EAD 12 eV CA-d4's tallest peak is
**430.3488** — the precursor that survived — and the row says so: *the base
peak is the precursor that survived, not a fragment*. It is a legitimate
transition and a poor one, and the fragment box is where you pick another.

**Seven of the nine were offered.** The two `_TESTEARTIGO` acquisitions were
refused, and for the reason this page already gives: they are named CA-d4 and
target 839.56, which is none of that formula's adducts. Ticking all seven
wrote **three** components, one per compound, because the second and third
infusion of each compound had nothing left to fill.

Then *Check method* on those three: **one finding** — `3 of 3 components have
no retention time`, which is the expected and correct answer for standards
that have only ever been infused, and the reason to run one of them up the
column next. The survey check was skipped, since these acquisitions have no
survey scan at all. Written the other way — all seven infusions as seven
separate rows, which this refuses to do — `check_method` also called the two
DCA-d4 rows a shared transition: both are 414.3516 → 361.30 within tolerance,
one at 22 eV and one at 40, and nothing but a retention time could tell them
apart.

## Which energy to keep

A tray is usually the same vial sprayed at several collision energies and,
where the instrument has both, under more than one activation.
**Recommend energies…** groups these rows by compound, activation and
energy and says which condition to use for identification, which for
quantitation and which for a library record — three different questions,
each with the figures it was decided on, and never an energy that was not
acquired. See [[collision-energy]].

## From a verification to a measurement

This report asks whether a vial is what its label says. **Quantify…** on the
same tab asks a different question — how much of one compound there is
against another in the same spray — and answers it with the two responses,
the isotope cross-talk between them and the ratio. See
[[infusion-quantitation]].

## The same standard, next month

This report is one verification. The record it names is written into your
own library, and [[standard-history]] reads the accumulated records of one
compound back as a control chart: the cosine against the first record, the
base peak's ppm from it, and the base peak's height, over the days they
were acquired.

The tray as a whole is the other half of that question, and
[[compare-infusions]] is where it is asked: this table against the one a
reference project saved, matched by compound and by conditions. Press
**Measure** before saving a project and the project keeps these figures and
every row's averaged peak list, which is what a later day is compared
against.

## The whole folder from a script

`api.infusion_report(folder, "infusions.pdf")` writes this document for
every infusion in a file or a folder without opening the application, and
returns one row per section so the numbers can be read without opening the
PDF — see [[python-api]].
