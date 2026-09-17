---
title: LIPID MAPS
---
The **LIPID MAPS** tab of the [[explorer]] works against a local copy of the
LIPID MAPS Structure Database (LMSD), so that a mass can be turned into
candidate lipids, a lipid name into its ions, and a structure into the
fragments it could produce — none of it needing the network once the index
is built.

## The database

The first use offers **Download the database**. One 21 MB file from
lipidmaps.org becomes a 45 MB index of 49,969 curated structures — their
annotation and their connection tables — stored as
`~/.milq/lipidmaps/lmsd-index.sqlite`. LMSD is redistributed by LIPID
MAPS under CC BY 4.0 and is downloaded on request, not bundled.

The index is a database and is read a row at a time, not held in memory.
Measured on this machine over the 49,969 records: opening it takes 0.1 ms
and no measurable memory, an LM_ID 0.012 ms, a formula 0.058 ms, a mass
window 0.083 ms, and a name looked up whole 0.03 ms — a name searched as a
substring of every other is the one question still answered by reading
every name, at 5 ms. Before this the index was one compressed
document that had to be decoded whole before it could answer anything: 0.74
seconds and 591 MB, which the window paid on startup merely to print how
many structures were indexed. An index installed by an earlier version is
rewritten in place the first time it is opened, once, and nothing is
downloaded again.

Searches are restricted to structures built from C, H, N, O, P, S and Se.
LMSD holds organoarsenic and fluorinated lipids; they are valid records and
absurd candidates for a plasma panel, and a rounded precursor mass matches
one happily.

## Mass → lipid

Type an m/z, pick the adduct, set a tolerance in ppm or Da, and **Search
LIPID MAPS**. Results are grouped **by species, then by structure**: a
species — `PC 34:1`, say — with the isomers that share its formula listed
underneath, because a mass cannot separate them and a list that pretended
otherwise would be claiming more than was measured. Each row carries the
formula, the error in mDa and ppm, the LM_ID and the **adduct** it was found
at; the tooltip on the species gives the systematic name, and the one on the
adduct says what that adduct does when the ion breaks up.

The Adduct box starts on **every adduct**, its first entry: the mass is then
searched at each adduct the channel's polarity allows. That is the honest
default for a measured mass, because which ion the number *is* is the
question — 876.8015
out of a liver DIA run answers one species, `TG 52:2`, C55H102O6, as
`[M+NH4]+` at +0.0 ppm and 51 structures, and the same number searched as
`[M+H]+` answers nothing at all. A product spectrum then ranks what a mass
alone cannot separate: see *Explain*, below.

Right-clicking a spectrum peak and choosing **Find formula for this peak**
sends its mass here as well as to the [[formula-finder]].

## Lipid → mass

Type a name (`SM(d18:1/16:0)`, `Cer(d18:1/16:0)`) or an LM_ID
(`LMSP03010003`) and **Find the precursor**: the matching records are listed
with formula and neutral mass, and selecting one lists its ions — every
adduct, its m/z and charge. Double-click an ion to use its m/z as the
precursor elsewhere in the panel.

## Fragments

Given a lipid and a polarity, **Predict fragments** enumerates what
cleaving its bonds would leave. The structure comes from the database's
molfile — a plain connection table with 2D coordinates, which is everything
needed to enumerate cleavages and to picture one, so no chemistry toolkit is
involved. Hydrogens, implicit in the file, are counted from the valence
left on each atom and checked against the published formula: a structure
whose hydrogens do not add up is marked unreliable rather than allowed to
produce fragment masses that look exact and are wrong.

Up to two bonds are cut at once — what a ring needs to come apart; three is
a combinatorial explosion nobody would look for — and each piece may shed
the small neutrals the **losses** option lists (water, ammonia, and so on).
The table gives each fragment's m/z, the piece, the route that made it, how
many cuts it took, and how many other routes reach the same mass
(**Rivals**). A **target** m/z filters to the routes that land on it.

What this does *not* do is say which cleavages actually happen.
Enumerating bonds is arithmetic; predicting a spectrum is not. The list is
the set of masses worth looking for.

## Explain

### Explain, once

**Explain**, at the top of the tab, does not ask which route to try. It runs
all of them — the compound's name, LIPID MAPS at this precursor, the formula,
and a drawing if one is loaded — and shows the one that explains the most of
the spectrum, with every other route listed under it. The three routes below
it are still there for anyone who wants to pick one by hand.

It fills itself in. The precursor, the polarity and the survey come from the
channel the spectrum came off; the name and the formula come from the
component whose precursor this channel isolates, so a spectrum of a standard
the method declares needs nothing typed at all. Anything typed in the boxes
below wins, since whoever typed it meant it. A `-d4` on the name is read as
four labels the name does not place, and each route is given the count that
applies to *it*: PubChem's cholic acid-d4 places its four in the drawing and
needs none added, while the `C24H40O5` beside it in the component table needs
all four, and a single count for the whole spectrum skips the formula route
with the true and useless statement that 430.35 is no adduct of the
unlabelled molecule.

The **route table** under the candidates is the answer:

| Column | |
|---|---|
| Route | name, LIPID MAPS, formula, drawing |
| Adduct | the ion that route read the precursor as |
| Explains | the share of the spectrum's intensity it accounts for |
| Ions | how many of the ions it predicted were found, of how many it offered |
| ppm | how far the written precursor sits from it through that adduct |

Click a row and the candidate table above shows that route's answer instead.
A route with nothing to work from is a row too, greyed, with the reason in
its tooltip — *the LIPID MAPS database is not installed* and *no curated
structure sits within ±0.7 Da of that mass* are different answers, and a
route simply missing from the table says neither.

The line under the candidates names the route it came from:

> from the name CA-d4 → LMST04010001 as [M+NH4]+; 430.35 is [M+NH4]+ of
> C24H36D4O5 (430.3465, +8.1 ppm); [M+H]+ would be 413.3200

**The best is the largest share, and the ties are stated.** At the same share
a drawing beats a formula, because a formula has no bonds to cut and reached
that share with a shorter list of predictions; then a candidate whose
precursor sits inside the precision the precursor was written with beats one
outside; then the order the routes are asked in. Nothing else decides, and
nothing is worked out twice — the adduct identification, which is where the
survey is read and the isotope pattern scored, is done once per composition
and handed to every route that asks for it.

Every structure route is enumerated to the same limits, up to two bonds cut
and up to three neutral losses, and every route is scored at 20 ppm. Both are
deliberate: a share is a fraction of the same spectrum either way, so a route
allowed more cuts, or a wider window, would win a comparison it was handed
rather than one it earned. The 5 ppm in the box below is for a different
question — placing labels, where a deuterium is 1.55 mDa from the hydrogen it
replaced — and it still governs *Where the labels are*.

#### What it did on four real infusions

Four ZenoTOF infusions of deuterated bile-acid standards, each whole run
averaged and centroided, the name and formula as a component table would
carry them (`CA-d4`, `C24H40O5`), and a drawing only where there was one:
PubChem's cholic acid-d4, CID 16217616. One **Explain** took 2.6–4.7 s,
counted from the button.

| | Route | Adduct | Explains | Ions | ppm |
|---|---|---|---|---|---|
| **CA-d4, CID** | **name → LMST04010001** | [M+NH4]+ | **92.0%** | 53 of 3,837 | +8.1 |
| | LIPID MAPS | [M+NH4]+ | 78.1% | 41 of 3,274 | −32.4 |
| | drawing | [M+NH4]+ | 69.7% | 35 of 1,081 | +8.1 |
| | formula | [M+NH4]+ | 24.2% | 2 of 56 | +8.1 |
| **CA-d4, EAD 22 eV** | **LIPID MAPS → LMGL03013010** | [M+2H]2+ | **95.0%** | 34 of 4,030 | −9.6 |
| | name → LMST04010001 | [M+NH4]+ | 87.3% | 33 of 3,837 | −15.1 |
| | drawing | [M+NH4]+ | 82.4% | 23 of 1,081 | −15.1 |
| | formula | [M+NH4]+ | 63.6% | 8 of 56 | −15.1 |
| **DCA-d4, CID** | **name → LMST04010040** | [M+NH4]+ | **90.6%** | 54 of 3,282 | −28.0 |
| | LIPID MAPS | [M+Na]+ | 64.3% | 35 of 2,330 | +13.9 |
| | formula | [M+NH4]+ | 17.0% | 3 of 41 | −28.0 |
| | drawing | *no structure was loaded* | | | |
| **TDCA-d4, CID** | **name → LMST05040013** | [M+H]+ | **92.2%** | 18 of 8,463 | −18.1 |
| | LIPID MAPS | [M+Na]+ | 79.9% | 12 of 7,244 | +27.6 |
| | formula | [M+H]+ | 72.7% | 5 of 104 | −18.1 |
| | drawing | *no structure was loaded* | | | |

The name route names the right compound in all four and wins three of them:
cholic acid, deoxycholic acid and taurodeoxycholic acid, each reached through
the standards table from the abbreviation on the bottle and then drawn from
LIPID MAPS.

**The one it loses is what the Ions column is for.** On CA-d4 under EAD the
top row is a triacylglycerol read as a doubly-charged ion, and it explains
95.0% of the spectrum with **4,030** predicted masses against the right
compound's 3,837 — a long enough list of possible masses covers a spectrum by
accident, which is the same thing this page says about isomers and about
unexplained peaks. Read the share beside the count that produced it. A route
that offered fifty masses and explained most of the spectrum has said
something; one that offered four thousand has not necessarily.

Two of the settings were chosen against these files rather than argued.
Scoring at 5 ppm instead of 20 takes the route naming the right compound from
three of four down to one of four: these axes sit 4–7 ppm high, so tightening
drops the true compound's ions while the four-thousand-ion candidate still
covers the spectrum. And at one bond cut instead of two — the limit the
by-hand database search uses — the right compound wins two of the four
instead of three, with the scoring taking 0.2–0.9 s instead of 2.6–3.9.
The second cut buys one of these four answers and costs about three seconds.

### One route at a time

**Explain this spectrum** takes the spectrum on screen and the precursor
(filled in from the active channel, or typed), looks the precursor up in
LIPID MAPS, predicts the fragments of every candidate structure, and scores
each by **the share of the spectrum's intensity it accounts for**. Counting
matched peaks instead would reward a candidate that explains forty specks
of noise over one that explains the base peak, which is backwards: a
product spectrum is mostly a handful of ions that matter.

Peaks below 1% of the base peak are not counted against a candidate — a
product spectrum's baseline is full of them and nothing explains them — and
a predicted mass matches a measured one within 20 ppm. The candidates are
listed with what each explains; selecting one lists the matched peaks with
their measured mass, error, route and, where several losses form a ladder,
the ladder. The unexplained peaks are reported too: several candidates
usually explain the same peaks, because isomers fragment alike, and the
unexplained ones are the honest part of the answer.

In the panel they are a count. In the [[infusion-report]] they are a table,
and each row carries the best of three guesses at what the peak might be —
a known contaminant or solvent cluster, a satellite of an ion that *was*
matched, or a composition assembled from nothing but the precursor ion's own
atoms, since a fragment cannot carry an atom the precursor has not got. The
last of those is why the table is worth having: constraining the element
ranges to this precursor turns a formula search from "what could this mass
be" into "what could this precursor have left behind here", and a mass with
no answer is then a statement — it is not a piece of this compound. On the
real bile-acid infusions it named protonated taurine on the taurine
conjugate and the benzene radical cation on an EAD spectrum, both of which
the panel had listed as bare masses; the figures are on that page.

The **Adduct** box beside the precursor says which ion the precursor is, and
is used twice: to look the mass up in the database, and to say what each
candidate's own precursor ion is and what its fragments carry.

Left on **from the precursor**, where it starts, the database is searched at
every adduct the channel's polarity allows and each candidate carries the one
that found it — the **Adduct** column, with that adduct's behaviour in its
tooltip, and **ppm**, how far the written precursor sits from that candidate
through that adduct. The line under the table says it in words, the same
sentence the own-structure path writes from the same code:

> 703.6 is [M+H]+ of C39H79N2O6P (703.5749, +35.7 ppm); [M+NH4]+ would be
> 720.6014

Selecting another candidate rewrites it, because on this path each row may
have been found at a different adduct. Picking an adduct by hand searches
that one only. See *Adducts*, below: it is not a detail, since an ammoniated
precursor scored as a protonated one predicts every fragment 17 Da away from
anything in the spectrum.

**Explain spectrum** on the Processing toolbar does the same from the
chromatogram: it takes the spectrum of the current scan and its channel's
precursor.

### The satellites of a matched fragment

A ppm figure cannot say that a matched peak is the composition claimed. An
isobar is inside the tolerance by definition, and at 20 ppm a product-ion
spectrum offers plenty of them. The peak's own **isotope satellite** can:
a fragment carrying twenty carbons owes an M+1 of about 22% of itself, and a
peak that shows one in proportion is a peak of about that many carbons.

That is the check the survey already makes on the *precursor* — see *The
survey confirms it*, below — asked of every matched **fragment**, on the
product-ion spectrum itself. The **Isotopes** column of the candidate table
carries the count and its tooltip the sentence:

> 2 of 2 agree
>
> 2 of 2 matched ion(s) have a satellite that agrees, 0 disagree, 0
> unmeasurable.

Four verdicts, and the last is the one that matters most:

- **agrees** — the M+1, and the M+2 where there is one, are in proportion.
- **disagrees** — they are not. The match is **kept and printed**: an
  unexpected satellite has innocent causes (a co-eluting neighbour a
  millidalton away, a detector at the top of its range) as well as guilty
  ones, and the ranking is not the place to decide between them.
- **no satellite measurable** — the ion's own predicted M+1 would be
  smaller than this spectrum can show, or another predicted ion sits inside
  the window where its M+1 belongs. Neither is a disagreement, and saying so
  is the point.
- **none expected: precursor isolated monoisotopically** — the quadrupole
  passed the monoisotopic precursor and nothing else, so no fragment in this
  spectrum came from a molecule with a 13C in it. There is no satellite to
  look for, and a column of disagreements would be a picture of the
  instrument's own selection rather than evidence about the structure.

Which of those applies is measured before any fragment is read, off the
**precursor's own M+1** in the same spectrum — the way the isotopic purity
solve and the infusion cross-talk term already refuse themselves. Where the
collision energy has consumed the precursor, the **strongest matched
fragment** answers the same question, and the sentence says which was read.

#### What the data say

The measurement this was written to make. On the seven ZenoTOF 7600
bile-acid infusions — product-ion acquisitions with no survey — the
precursor's transmitted M+1 is **0.00 to 0.26% of what its composition
demands**, which is 26.4 to 30.0%:

| Infusion | CE | read off | height | M+1 measured | predicted | transmitted |
|---|---|---|---|---|---|---|
| CA-d4 | 45 | strongest fragment | 5,638 | 0.068% | 26.4% | 0.26% |
| CA-d4 | 22 | precursor | 9,415 | 0.000% | 27.0% | 0.00% |
| CA-d4 | 12 | precursor | 12,271 | 0.000% | 27.0% | 0.00% |
| DCA-d4 | 40 | strongest fragment | 3,019 | 0.060% | 26.4% | 0.23% |
| DCA-d4 | 22 | precursor | 5,582 | 0.000% | 26.9% | 0.00% |
| TDCA-d4 | 30 | precursor | 123 | 0.000% | 30.0% | 0.00% |
| TDCA-d4 | 22 | precursor | 5,235 | 0.000% | 30.0% | 0.00% |

All **34 matched ions across the seven** therefore read *none expected*, and
none of them is called a disagreement. Every one of the 34 had a composition
that could be worked out, and **12 of the 34** have another predicted ion
inside the window where their M+1 belongs — the same piece carrying one more
label. A deuterium is 1.00628 Da from the hydrogen it replaced against the
neutron's 1.00336, so a `+3D` rung's "M+1" is its `+4D` neighbour 2.9 mDa
away: read as a satellite those twelve give M+1 shares of
0.96, 1.12, 2.20, 2.63, 4.51, 7.99, 8.61, 11.27, 12.44, 12.57, 19.98 and
40.54 times their own peak. They are unmeasurable, and they say so.

The question a product-ion acquisition cannot answer on its own is whether
an isolation window ever passes the M+1. A TripleTOF 5600 sphingolipid
injection answers it, because it acquires a 50–700 survey beside the
product-ion channels. Over the same two scans across the peak of
SM(d18:1/12:0):

| | precursor | height | M+1 measured | predicted | transmitted |
|---|---|---|---|---|---|
| the 647.5 product-ion channel | 647.5121 | 1,064 | 0.31% | 39.6% | **0.8%** |
| the survey, same scans | 647.5103 | 58,462 | 29.23% | 39.6% | **73.7%** |

So the window does not pass it: two orders of magnitude between the two
readings of the same ion in the same acquisition. On the survey the same
rule then finds what it is for — both matched ions **agree**, at 0.70 and
0.99 — and on the product-ion channel both read *none expected*. The
ceramide channel of the same injection shows the third verdict: a 163-count
base peak, whose precursor's own M+1 would be 4 counts against the 10 that
spectrum can show, so nothing is claimed either way.

A composition is what a satellite has to be predicted from, and a predicted
ion does not simply carry one: a cleavage holds the piece's formula with the
hydrogens it moved and the neutrals it then shed recorded beside it, while a
precursor form holds the composition it already is with the adduct's atoms
outside it. So each reading is proposed and turned back into an m/z, and
kept only where it reproduces the ion's own mass. On the same two CA-d4
spectra scored against PubChem's drawing rather than against a formula —
882 predicted ions, 20 matched — every one of the 20 came back with a
composition, and the isolation was read off the precursor at 22 eV and off
the strongest fragment at 45, where the precursor is gone.

One thing an agreeing satellite does not do is confirm the route. On that
survey the second agreeing ion is `[M+H-2CO-CO2]+` at 547.5229, which scores
0.99 because it is *some* ion of about that many carbons — which it is,
whatever produced it. The satellite bounds the composition; the ladder and
the unexplained peaks are what argue for the route.

### A structure or formula of your own

The database does not hold everything — not a deuterated bile acid bought
as an internal standard, not a compound drawn last week. The group under
the Explain button takes one of two things:

- **A structure**, from a `.mol` or `.sdf` file (PubChem's download, a
  drawing program's save; MDL V2000). It gets the full treatment: the
  cleavages and the losses of the drawing, scored against the spectrum
  exactly as a database record is. A drawing that places its labels — an
  `M  ISO` block, or explicit D atoms, which is how a vendor's structure of
  a d4 standard is written — needs nothing more; its fragments come out at
  the right masses by themselves. Hydrogens written out as atoms of their
  own are folded into the atoms that carry them: PubChem writes all forty
  of a bile acid's, and cutting forty C–H bonds only produces forty pieces
  that differ from the whole molecule by one hydrogen, which a hydrogen
  shift already covers. The formula is unchanged by the folding, and
  deuterium the drawing places stays on the atom it was drawn on.
- **A formula**, when there is no drawing. A formula has no bonds to cut,
  so what can be said is the precursor ion and the ladder of small neutral
  losses it could shed — water, ammonia, carbon monoxide and dioxide,
  formic acid, up to three at once, each only where the formula has the
  atoms for it. Less than a structure gives, and said to be.
- **A name**, when there is neither. It is looked up in a table of
  standards, then in LIPID MAPS, then in the lipid shorthand, and brings
  back a formula, the database's drawing where there is one, and the label
  count a `-d4` on the end declares. See *A name of your own*, below.

Whichever of the three it is, the **Adduct** box says how the precursor was
ionised, and on automatic reads that off the channel's own written
precursor. It is not a detail: an ammoniated precursor scored as a
protonated one predicts every fragment 17 Da away from anything in the
spectrum. See *Adducts*, below.

**Deuterium, unplaced** is for a drawing or formula of the *unlabelled*
compound and a standard whose labels sit somewhere unknown. Each fragment
is then offered carrying none to all of the labels, and the spectrum says
how many it kept: a match at +2.0126 is a piece that kept two, written
`+2D` on its route. Enumerating every placement would be honest and
useless; enumerating the count is what the spectrum can confirm. A piece
is never offered more labels than it has hydrogens.

**Limits** sets how far the enumeration goes and how close a mass has to
be. Two cuts, because a steroid cut once is still in one piece; three
losses, because a trihydroxy bile acid sheds three waters and the
three-water ion is its base peak. The tolerance is **± 5 ppm** rather than
the 20 ppm a database candidate is scored at, and that is not a matter of
taste — see below.

The result lands in the same two tables as a database candidate — the
share of the spectrum explained, the matched peaks with their routes and
ladders — and the unexplained peaks remain the honest half of it.

### Where the labels are

A piece that kept two of four labels contains two of them; a piece that
kept none contains none. Every matched ion is therefore a statement about
*which* hydrogens are heavy, not only how many, and the block under the
tables collects those statements. A placement is a set of positions, one
per label; a placement survives an ion when the labels it puts inside that
piece are the number the piece kept. What comes back is how many placements
survive, which positions every survivor agrees on, and which positions
nothing separates.

Positions the observations cannot tell apart are grouped, because a tie
between two hydrogens that are inside exactly the same fragments is not a
result. Cholic acid offers 21 carbon-bound positions and **8,391** ways of
putting four labels on them.

Three rules decide what counts, and all three were measured rather than
assumed:

- **A hydrogen bound to oxygen or nitrogen is not offered.** It exchanges
  with the solvent long before the spectrum is recorded. The checkbox puts
  those positions back for anyone who wants to see what the spectrum would
  say if it did.
- **A neutral loss may take a label with it.** A dehydration leaves with
  the hydroxyl's own hydrogen and one more from the carbon beside it, so an
  ion that shed water bounds the count rather than fixing it; a
  decarboxylation takes no carbon-bound hydrogen and so says exactly. This
  is measured: in the CID spectrum below the base peak at m/z 359.2870 is
  the three-water loss keeping all four labels, and 358.2808 beside it at
  12.5% is the same ion keeping three. The two are 1.0062 apart, which is
  the 1.00628 of a deuterium against a hydrogen and not the 1.00783 of a
  hydrogen against nothing.
- **A hydrogen the piece lost on cleavage may also have been a label.**
  Assuming otherwise is tidier and wrong: with it assumed, an ion written
  `-2H` cannot have shed a label, and on the spectrum below the true
  placement then satisfied 43% of the evidence rather than 78% and was
  beaten by 96% of the possibilities rather than 79% — and the block named
  a methyl that carries no label as a position every survivor agreed on.

**A peak only counts when it says a number.** A deuterium is 1.55 mDa
heavier than the hydrogen it replaced, so the same piece with one more
label and one fewer hydrogen sits 1.55 mDa away — at m/z 359 that is
4.3 ppm. A window wider than the gap holds both and the match is decided by
which is nearer, which is a coin toss; those ions are counted and left out.
On the cholic acid-d4 spectrum, of the matched ions left out for this
reason: 48 of 53 at 20 ppm, 24 of 47 at 10 ppm, 4 of 26 at 5 ppm, none of
19 at 3 ppm. That is why the tolerance here defaults to 5 ppm.

### What it did on a real standard

Cholic acid-d4 infused on a ZenoTOF 7600 — the product-ion channel of the
ammonium adduct at m/z 430.35, CE 45, the whole 1.98 min run averaged (473
scans, flat throughout, an infusion by the test in [[direct-infusion]]) and
centroided: 811 centroids, 60 peaks above 1% of the base peak. The
structure is PubChem's cholic acid (CID 221493) with four unplaced labels;
the answer is known, because PubChem also holds the labelled standard (CID
16217616), whose `M  ISO` block puts the four on C2 and C4 — either side of
the C3 hydroxyl on ring A.

| | CID, CE 45 | EAD, 22 eV |
|---|---|---|
| peaks explained | 59.0% | 60.7% |
| ions matched | 26 | 24 |
| of those, saying a label count | 22 | 15 |
| left out as undecided | 4 | 9 |
| placements tied at the top | 580 | 2,625 |
| of 8,391, at | 93% of the evidence | 100% |
| positions every survivor agrees on | none | none |
| the vendor's own placement | 78% of the evidence | 92% |
| placements beating it | 6,589 (79%) | 6,224 (74%) |

The EAD column is a second infusion of the same standard, 22 eV, read the
same way: 146 scans over 0.61 min, 424 centroids, 42 peaks.

**It does not recover the answer.** Under CID the top placements put two
labels on a methyl and one on a carbon beside a different hydroxyl; under
EAD they spread over four positions in the middle of the ring system.
Neither is ring A, and the vendor's 2,2,4,4 is beaten by three quarters of
the possibilities in both activations. Read the tie — 580 and 2,625 placements — as the spectrum
bounding the labels rather than placing them, which is what the block says
when it reports that no position is in all of them. The reason is that a
matched mass is not a settled assignment: a piece reached by two cuts and three
losses is one of thousands of arithmetic possibilities, and the placement
that fits best is the one that rationalises whichever of those the matcher
picked.

Handed the labelled drawing instead, with nothing to infer, the same
spectra agree with it: every ion the placement predicts is where it should
be, 100% of the evidence in both files. What that costs is reach — the
placed drawing explains 35.5% of the CID spectrum against the unplaced
version's 59.0%, because the unplaced version is offered five times as many
masses to match. And the disagreement is reported rather than hidden: three
peaks in the CID spectrum and two in the EAD one fit a piece the placement
predicts *carrying a different number of labels*, one of them the 358.2836
already named above.

What the spectrum does say plainly is that a dehydration takes a label.
Under EAD the ladder is complete, and the share of each rung that has lost
one grows as the hydroxyls leave: 5.2% at the precursor, 5.0% after one
water, 8.0% after two, and 104% after three — the ion that lost a label is
then larger than the one that kept them all. Which hydroxyl left at which
rung would place the labels; the enumeration does not track that yet.

## The margin

A share on its own cannot be read. "Explains 63.6%" says nothing until
something else has been scored on the same peaks: a long enough list of
predicted masses covers a spectrum by accident, and how long that list is
depends on the compound, not on the evidence. So every explanation now
carries its **margin** — what the chosen compound explains, less what the
best of its nearest impostors explains — in the line under the tables, in
the per-compound section of the [[infusion-report]], and as a column of the
Infusions tab:

> explains 63.6%; the best of 17 neighbour(s) (TG 17:1/18:4/18:4 as
> [M+2H]2+) explains 21.7%: a margin of 41.9 points

The impostors are the LIPID MAPS records that fit the **written** precursor
at any adduct the channel's polarity allows — the same set the ranked table
draws from, gated the same way — with two kinds left out:

- **The compound itself**, at any adduct.
- **Anything carrying the same formula.** Same formula, same precursor, same
  neutral losses: the same arithmetic, and no contrast. Scoring it would put
  the chosen compound's own number in the impostor column and report a
  margin of zero for a spectrum that was never in doubt. In lipidomics this
  is the ordinary case rather than an edge one — each of the four named
  sphingolipids below has one or two — so the sentence says how many were
  left out, and a margin measured over sixteen neighbours where eighteen
  were found is not passed off as one measured over eighteen.

Each impostor is scored **the same way the compound was**: a formula against
formulas, a drawing against drawings. That is not tidiness. Scored the other
way round — a bile acid's 56 predicted masses against LIPID MAPS structures
offering 700 to 2,900 each — the impostor won five of the six real bile-acid
infusions, by up to 33 points, on spectra where nothing was wrong. A list of
two thousand masses covers a sixty-peak spectrum by accident. Enumerated
alike, the true compound won all six.

Under **10 points** the margin is called *thin*, and the sentence says the
spectrum does not tell the two compounds apart. Ten is where the gap is in
the eleven real spectra it was measured on.

### What it says on real data

Six infusions of deuterated bile acids, each explained from its formula
through the adduct its channel's written precursor names:

| Infusion | Written | Explains | Best impostor | It explains | Margin |
|---|---|---|---|---|---|
| CA-d4, CID 45 eV | 430.35 | 24.2% | TG 17:1/18:4/18:4 `[M+2H]2+` | 0.0% | **+24.2** |
| CA-d4, EAD 22 eV | 430.34 | 63.6% | TG 17:1/18:4/18:4 `[M+2H]2+` | 21.7% | **+41.9** |
| DCA-d4, CID 40 eV | 414.34 | 17.0% | 3-hydroxypalmitoleoylcarnitine `[M+H]+` | 1.6% | **+15.3** |
| DCA-d4, EAD 22 eV | 414.34 | 70.4% | Wuhanic acid `[M+NH4]+` | 56.5% | **+13.9** |
| TDCA-d4, CID 30 eV | 504.32 | 72.7% | a spirostenone `[M+NH4]+` | 1.5% | **+71.2** |
| TDCA-d4, EAD 22 eV | 504.32 | 78.4% | PC O-16:0/0:0 `[M+Na]+` | 72.3% | **+6.1** *thin* |

And the four named sphingolipids of one injection of a 26-injection batch,
explained from their LIPID MAPS drawings, where the written precursors sit
36 to 264 ppm from the compounds themselves:

| Channel | Compound | Explains | Best impostor | It explains | Margin |
|---|---|---|---|---|---|
| 703.60 | SM(d18:1/16:0) | 31.9% | PG 13:0/18:3 `[M+H]+` | 15.7% | **+16.2** |
| 731.70 | SM(d18:1/18:0) | 19.4% | PA 16:0/22:1 `[M+H]+` | 17.3% | **+2.1** *thin* |
| 538.60 | Cer(d18:1/16:0) | 9.5% | PE 22:0/0:0 `[M+H]+` | 12.4% | **−3.0** *thin* |
| 648.80 | Cer(d18:1/24:1) | 9.2% | Calyxoside `[M+H]+` | 7.1% | **+2.1** *thin* |

Read those four rows as they are meant to be read. The ceramide at 538.6 is
in that vial — it is a method component with a retention time, and the batch
was quantified on it — but *this spectrum* does not identify it: three
lysophospholipids of another formula account for more of the same peaks.
The margin does not say the compound is wrong. It says the compound was not
distinguished here, and that whatever supports the assignment has to come
from somewhere else: the retention time, the survey scan's exact mass, a
[[spectral-library]] record.

The same applies to TDCA-d4 at 6.1 points. That is a pure standard sprayed
from a vial, and the flag is still right: it is known from the bottle, not
from the spectrum, and before the margin was measured nothing on the page
said so.

A margin is measured over 16 to 29 neighbours on those spectra and costs
under half a second — a tenth of that on the formula route.

## Adducts

A precursor is a molecule plus whatever charged it, and which one decides
every mass underneath. The ZenoTOF infusion this was built against writes
its product-ion channel **430.35**, and cholic acid-d4 weighs 412.31: the
number is the *ammonium* adduct, `[M+NH4]+`, and its protonated form is
413.32 — seventeen daltons lower. Scored as `[M+H]+`, a drawing predicts a
precursor that is not in the spectrum and a water ladder shifted off every
rung that is; scored as `[M+NH4]+` by an arithmetic that simply adds 18.03
to everything, it predicts `[M+NH4-H2O]+`, which is not a species at all.
Both fail, and neither says why.

So an adduct here carries what it does when the ion breaks up, and the three
kinds behave differently:

- **A proton adduct** — `[M+H]+`, `[M-H]-`, `[M+2H]2+` — keeps its charge on
  whichever piece holds it. The fragments are the protonated, or
  deprotonated, pieces.
- **A labile adduct** — `[M+NH4]+`, and in negative mode `[M+HCOO]-`,
  `[M+CH3COO]-`, `[M+Cl]-` — is held by hydrogen bonds and nothing stronger.
  It leaves as a neutral (ammonia, formic acid, acetic acid, hydrogen
  chloride) and hands over a proton on the way, so the ion that fragments is
  `[M+H]+` or `[M-H]-`. The precursor is seen intact, then as the proton
  form, and the loss ladder hangs off *that*: `[M+NH4]+`, `[M+H]+ (-NH3)`,
  `[M+H-H2O]+`, `[M+H-2H2O]+`, `[M+H-3H2O]+`. Nothing keeps the ammonium
  while shedding a hydroxyl, because the ammonia is long gone by then.
- **A metal adduct** — `[M+Na]+`, `[M+K]+` — is a coordinate bond, and the
  metal stays on the piece that keeps the coordinating site, which the
  arithmetic cannot know. Both are offered, `[piece+Na]+` and `[piece+H]+`,
  and every ion says which was assumed.

Ions of the precursor are written as the form they are — `[M+NH4]+`,
`[M+H]+ (-NH3)`, `[M+H-3H2O]+`, with `+3D` after it when the piece kept
three of four labels. A *piece* is still written as what is left and how it
got there, `C23H37O3 -H2O`, because that is the only description a cleavage
has.

### Which adduct the precursor is

Left on **from the precursor**, the Adduct box under *Explain with this*
works it out: every adduct of the formula is measured against the channel's
written precursor, the polarity of the channel rules out the other sign, and
the line under the button says which one it is and how far off —

> 430.35 is [M+NH4]+ of C24H36D4O5 (430.3465, +8.1 ppm); [M+H]+ would be
> 413.3200

An adduct has to land within **0.05 Da**, widened to the precision the
precursor was written with when that is coarser. 0.05 is measured rather
than chosen: over the nine bile-acid infusions the worst gap between a
written precursor and its true adduct mass is 0.0117 Da — DCA-d4, written
`414.34` for an ammonium adduct of 414.3516 — because an instrument method
carries two decimals and does not always round them the same way; the same
compound is written `430.35` in one of these files and `430.34` in another.
0.05 covers that with room, and is still a fiftieth of the smallest gap
between two adducts of one molecule that could be confused for each other
(ammonium and sodium, 4.955 Da apart).

Where **nothing** lands within it, nothing is explained. The line names the
closest misses and their Δ, and the tables stay empty:

> Nothing explained: 430.35 is none of the adducts of C24H40O5 within
> ±0.05 Da — closest [M+Na]+ at 431.2768 (-0.9268 Da), [M+NH4]+ at 426.3214
> (+4.0286 Da).

That is the right answer and not a failure. The formula there is cholic acid
without its four labels, and explaining it anyway would predict every
fragment from a molecule the quadrupole never isolated — a table of
confident wrong routes, which is harder to disbelieve than an empty one.
Type the labels, or pick the adduct by hand from the same box, which then
says *chosen by hand* rather than pretending it was derived.

The polarity comes from the channel and is not typed anywhere: a positive
channel is never offered a negative adduct. With no precursor written at all
there is nothing to read it off, and the Adduct box at the top of the tab —
the one the database search uses — stands in, said out loud.

### The survey confirms it

Everything above is arithmetic on a number somebody typed. Where the
acquisition has a **survey scan** — a full-scan TOF MS channel covering the
precursor — the adduct stops being a deduction and becomes a measurement,
and the panel says which of the two you are looking at.

The survey of the same acquisition, averaged over the same scans as the
spectrum on screen, is asked about every candidate: the exact mass of the
ion, within 25 ppm and above 100 counts, and the isotope pattern of the
ion's own composition — the adduct's atoms included, since `[M+NH4]+`
carries a nitrogen the molecule has not got. The line under the button then
reads

> 647.5 is [M+H]+ of C35H71N2O6P (647.5123, −18.9 ppm); [M+NH4]+ would be
> 664.5388; confirmed by the survey: 647.5112, −1.6 ppm, isotopes agree, and
> the survey also shows [M+Na]+ 13%, [M+K]+ 0%

or, when it does not,

> …; the survey does not show it (the nearest peak is +69.9 ppm away, past
> ±25), so it is chosen from the written mass alone

The second clause is the point. A product-ion scan cannot check this at all:
Q1 passed one mass and threw the isotope satellites away with everything
else, so the spectrum on screen has no pattern to read. Nine bile-acid
infusions to hand were acquired as product-ion scans only, and on them this
sentence says *no survey scan covering 430.35, so nothing independent says
which ion it is* — which is what the adduct always was there, now written
down.

**The map is worth as much as the answer.** A survey usually shows a
compound as several ions at once, and each is reported with its height as a
share of the strongest: on the sphingolipid batch both the sphingomyelin and
the C16 ceramide run at about `[M+H]+` 100%, `[M+Na]+` 13%. An eighth of the
signal is on a channel nobody acquired, and a compound whose sodium adduct is
the bigger one will be quantified badly by anyone who assumed otherwise.

**The pattern decides what the mass cannot.** Two things can sit at one
mass: an ion, and the M+1 of something a dalton lighter. The ceramide's
`[M+NH4]+` above is 21.5 ppm out — inside the 25 ppm that says "the same
ion" — and 170 counts, over the 100 that says "measurable"; its M+1 and M+2
come back at 1.00 and 1.00 of its M, which is flat noise and not an isotope
pattern, and it ranks last. A d4 standard and its d3 impurity, 1.0063 Da
apart, are the same problem in reverse: both are on the mass to within
1 ppm, and only the pattern — 0.97 against 0.06 — says which of them the
peak belongs to.

The figures, the two real compounds and what the M+2 of a lipid actually
holds are on [[accurate-precursor]].

### A database candidate says which adduct found it

The same model runs on the database route, so a triacylglycerol annotated
`[M+NH4]+` is scored with the intact ammonium, the `[M+H]+` it hands over,
and the ladder off *that*, its diacylglycerol ions carrying a proton; a
`[M+Na]+` candidate offers both carriers. It is the own-structure path with
the drawing taken out of LMSD rather than off the disk — one enumeration, one
scoring, one sentence.

What the record route needs and the own route does not is a **gate**. A
product-ion channel is looked up over the isolation window, half a dalton,
because a method writes its precursor rounded — 538.6 for a ceramide whose
precursor is 538.52. At 700 Da half a dalton is 700 ppm and holds hundreds of
species, so running five adducts over it multiplies the candidates that
explain a noisy spectrum by accident. An adduct other than the proton one
therefore has to *name* the precursor — the same ±0.05 Da above — while the
proton adduct keeps the whole window, because it is the reading the method
wrote down and needs no identifying.

Measured on the sphingolipid batch's four named compounds, whole run
averaged and centroided, and on the ZenoTOF DIA window holding TG 52:2:

| channel | compound | as [M+H]+ | every adduct, gated |
|---|---|---|---|
| 703.6 | SM(d18:1/16:0) | rank 1, 31.9%, 6 of 885 | rank 1, 31.9%, 6 of 885 |
| 538.6 | Cer(d18:1/16:0) | rank 4, 9.5%, 6 of 779 | rank 4, 9.5%, 6 of 779 |
| 648.8 | Cer(d18:1/24:1) | rank 1, 9.2%, 6 of 1,153 | rank 1, 9.2%, 6 of 1,153 |
| 731.7 | SM(d18:1/18:0) | rank 1, 19.4%, 4 of 968 | rank 1, 19.4%, 4 of 968 |
| 876.80 | TG 52:2 | not listed | rank 2, 24.0%, 9 of 1,123 |

The four sphingolipids do not move, which is the point of the gate: their
written precursors sit 36 to 264 ppm from the compounds themselves, so no
mass rule can promote them and none should demote them either. Ungated they
went to ranks 1, 5, 5, 3, the new top rows being a doubly charged
glycosphingolipid at −171 ppm and a potassiated ceramide at +356 ppm, each
offering two to three times as many predicted ions.

The triacylglycerol is what the gate is for. A DIA window at 876.80 searched
as `[M+H]+` does not list `TG 52:2` at all — it is not a lipid at that
adduct, and the best candidate is a phosphatidylserine explaining 7.7%.
Searched at every adduct it comes back at −1.7 ppm explaining 24.0% of the
spectrum, with the intact `[M+NH4]+` at 876.8051 (+4.2 ppm) and the
diacylglycerol ions carrying protons: 577.5219 (+4.9), 603.5363 (+2.6),
605.5520 (+2.8). Above it sits a potassiated ceramide with 3,291 predicted
ions explaining 43.2% at +25.0 ppm — the long-list-by-accident caveat this
page keeps making, and the ppm column is what separates the two by a factor
of fifteen. A search takes 0.2 to 0.8 s either way.

### What it did on the real infusions

Three bile-acid standards infused on a ZenoTOF 7600 in **positive** mode,
the whole run averaged and centroided, scored at ±10 ppm. *Before* is the
same files through the same button with the adduct the channel declares,
which was as much as could be asked of it:

| infusion | written | read as | before | now |
|---|---|---|---|---|
| CA-d4, CID 45 eV | 430.35 | [M+NH4]+, +8.1 ppm | 0 of 31, 0.0% | 2 of 56, 24.2% |
| CA-d4, EAD 22 eV | 430.34 | [M+NH4]+, −15.1 ppm | 1 of 31, 21.7% | 8 of 56, 63.6% |
| CA-d4, EAD 12 eV | 430.34 | [M+NH4]+, −15.1 ppm | 1 of 31, 82.3% | 3 of 56, 85.0% |
| DCA-d4, CID 40 eV | 414.34 | [M+NH4]+, −28.0 ppm | 0 of 25, 0.0% | 3 of 41, 17.1% |
| DCA-d4, EAD 22 eV | 414.34 | [M+NH4]+, −28.0 ppm | 1 of 25, 15.8% | 7 of 41, 44.4% |
| TDCA-d4, CID 30 eV | 504.32 | [M+H]+, −18.1 ppm | 3 of 50, 66.5% | 4 of 104, 72.1% |
| TDCA-d4, EAD 22 eV | 504.32 | [M+H]+, −18.1 ppm | 3 of 50, 71.3% | 5 of 104, 78.4% |

Guessing right did not rescue it either: the same CA-d4 EAD spectrum scored
as `[M+H]+` gave 4 of 31 and 34.2%, because the ladder was then predicted
and the precursor — 98% of the base peak — was not. TDCA-d4 *is* a
protonated molecule, and it improves for the other reason on this page:
labels spelt into the formula now shed with the water, as unplaced ones
always did.

On CA-d4 under EAD at 22 eV the whole ladder is accounted for, each rung
twice:

| | measured | route |
|---|---|---|
| precursor | 430.3489 | `[M+NH4]+ +4D` |
| loses the ammonia | 413.3217 | `[M+H]+ (-NH3) +4D` |
| one water | 395.3118 | `[M+H-H2O]+ +4D` |
| two waters | 377.3015 | `[M+H-2H2O]+ +4D` |
| three waters | 359.2897 | `[M+H-3H2O]+ +4D` |
| one water, a label gone with it | 394.3035 | `[M+H-H2O]+ +3D` |
| two waters, a label gone | 376.2935 | `[M+H-2H2O]+ +3D` |
| three waters, a label gone | 358.2836 | `[M+H-3H2O]+ +3D` |

Under CID at 45 eV the ladder has already run to completion: only 359.2870
and 358.2808 are there above 1% of the base peak, and both are explained.

**A structure gains exactly one ion, and it can be the base peak.** The
cleavage enumeration already builds protonated pieces, which is what a
labile adduct's fragments are, so the only thing it could not reach was the
intact ammonium — and that ion is 98% of the base peak at 22 eV and the base
peak itself at 12 eV. PubChem's cholic acid-d4 (CID 16217616, whose
`M  ISO` block places the four labels), two cuts, three losses:

| | before | now |
|---|---|---|
| CID, 45 eV | 25 of 1080, 56.5% | 25 of 1081, 56.5% |
| EAD, 22 eV | 21 of 1080, 60.3% | 22 of 1081, 82.0% |
| EAD, 12 eV | 8 of 1080, 9.7% | 9 of 1081, 92.0% |

**The tolerance is the other half of it.** These spectra sit 4.1 to
7.1 ppm high on their own mass axis — the matched precursor's error in the
table above says so — and at the ±5 ppm this box defaults to, most of the
ladder falls outside the window: CA-d4 under EAD 22 eV gives 5 of 56 and
14.0% at 5 ppm against 8 of 56 and 63.6% at 10. The default is 5 because a
label is only 1.55 mDa from the hydrogen it replaced — *Where the labels
are*, above — so the two
questions pull opposite ways: widen it to read the ladder, tighten it to
count labels, and read the ppm the panel prints on the precursor to know
which side you are on.

## A name of your own

The **Name** box resolves a compound when there is no drawing and no formula
typed. Three places are asked, in order:

1. **A table of standards** bought by their trivial names: the bile acids
   and their glycine and taurine conjugates — cholic, deoxycholic,
   chenodeoxycholic, ursodeoxycholic, hyodeoxycholic and lithocholic acid,
   and the glyco- and tauro- forms of each — by name or by the abbreviation
   on the bottle (`TDCA`, `GCDCA`), because nothing in LIPID MAPS answers to
   `TDCA` and a `.wiff` is named after the bottle. The table gives the LIPID
   MAPS spelling, so the *drawing* still comes from the database; the
   formula it also carries is the fallback on a machine with no database
   installed. It stops at bile acids on purpose — every entry was checked
   against LMSD, and a table that grew by guesswork would be a list of
   formulas nobody measured.
2. **LIPID MAPS itself**, by name or LM_ID.
3. **The lipid shorthand**, which gives a formula and no structure.

A `-d4`, `_d5` or `(d4)` on the end is read as that many labels the name
does not place — the same number the *Deuterium, unplaced* box takes — and
is stripped before any of the three are asked. The `d` inside `SM(d18:1/16:0)`
and the `d` of `DCA` are not label counts, because the suffix is anchored to
the end of the name. A name none of the three knows is said to be unknown
rather than guessed at.

So `cholic acid-d4` typed into an infusion of CA-d4 becomes cholic acid,
C24H40O5, drawn as `LMST04010001`, with four unplaced labels, ionised as
`[M+NH4]+` because that is what 430.35 is. On the three compounds, at
±10 ppm:

| | CID | EAD, 22 eV |
|---|---|---|
| `cholic acid-d4` | 48 of 3,837, 85.7% | 33 of 3,837, 87.3% |
| `DCA-d4` | 48 of 3,282, 82.2% | 29 of 3,282, 88.6% |
| `TDCA-d4` | 17 of 8,463, 91.6% | 21 of 8,463, 91.2% |

Those shares are the highest on this page and mean the least, for the reason
*Where the labels are* gives above: four unplaced labels multiply the masses on offer
fivefold, and a long enough list of possible masses covers a spectrum by
accident. Read them beside the placed drawing's, not instead of it.

## Isotopic purity

A bottle of cholic acid-d4 comes with a certificate saying `98 atom % D`, and
nobody ever measures it. Where the compound carries labels — declared in
*Deuterium, unplaced*, spelt into the formula, placed by a drawing, or read
off a `-d4` on the end of a name — and an adduct was identified, a line
appears under the label inference:

    Isotopic purity: d4 96.2%, ≥d3 99.1% (from the precursor at 430.35; ±0.8%)

The number matters for a reason that has nothing to do with identity. An
internal standard that is four per cent d3 puts four per cent of its response
one dalton below where the method looks for it, and no other check in a batch
can see that.

**It is a deconvolution and not a set of ratios.** The d4 ion and the d3 ion
are 1.00628 apart, the mass a deuterium adds over the hydrogen it replaced.
The **carbon-13 satellite of the d3 ion** sits 1.00335 above it — 2.9 mDa
below the d4 ion — and on these acquisitions the precursor peak is 10.2 mDa
wide at half height (R = 42,000 at *m/z* 430). Those two are one peak, and no
instrument in an ordinary laboratory separates them. On a 24-carbon skeleton
that satellite is 27% of whatever the species below holds, so every rung of
the ladder leaks into the rung above it. The envelope is therefore solved —
each species' natural pattern, from the formula, fitted as a non-negative
least squares — rather than read.

Reading the peaks instead is not wrong the way one expects. Measured on exact
synthetic envelopes of a d4 material that is 95% pure: the heights normalised
over d0 – d4 give d4 = 94.81% where it is 95.00%, because the leak onto d4
also inflates the denominator and the two nearly cancel. **What does not
cancel is the impurity**, which is the number a purity is bought on: d3
against d4 reads 4.44% where it is 4.21%, five per cent high, and on a d7
sphingolipid with 45 carbons it reads 4.63% against 4.21%, ten per cent high.

**Two numbers, and they are not the same number.** `d4 96.2%` is the fraction
of molecules carrying all four labels. `98 atom % D` is the fraction of the
*labelled positions* that hold a deuterium, which counts the three that a d3
molecule does carry — so a material that is 96% d4 and 4% d3 is 99.0 atom % D.
The line gives the species pair; the report block underneath gives the atom
per cent as well, because that is what the certificate states.

### When it says it cannot

The check is free, because the natural pattern is already in hand: **the
fully-labelled ion's own M+1 satellite has to be there**, at roughly the share
the formula demands. Where it is not, the line says so instead of giving a
number:

    Isotopic purity: not measured — the d4 ion's own M+1 satellite is 0.006%
    of it where the formula says 26.6% …

That is not a rare case. It is what a **product-ion scan** looks like: the
quadrupole isolated the precursor before the collision cell, and a window
narrow enough to pick one species out of the d-ladder has already thrown away
the satellites the solve needs. Measured on the nine bile-acid infusions, all
of them product-ion scans with no survey scan at all:

| infusion | CE | M+1 measured | formula says | ratio |
|---|---|---|---|---|
| CA-d4 EAD | 12 eV | 0.006% | 26.6% | 0.0002 |
| CA-d4 EAD | 22 eV | 0.028% | 26.6% | 0.0010 |
| CA-d4 CID | 45 eV | 0.095% | 26.6% | 0.0036 |
| DCA-d4 EAD | 22 eV | 0.015% | 26.5% | 0.0006 |
| DCA-d4 CID | 40 eV | 0.150% | 26.5% | 0.0057 |
| TDCA-d4 EAD | 22 eV | 0.020% | 30.0% | 0.0007 |
| TDCA-d4 CID | 30 eV | 0.206% | 30.0% | 0.0069 |

Three orders of magnitude, on every file, under both activations. The same
threshold catches the other case it should: a precursor too weak for its own
27% satellite to rise out of the noise is a precursor whose envelope would be
read off noise.

The refusal is also what the files themselves argue for. On the 12 eV cholic
acid-d4 run, transmission one dalton *above* the precursor is 0.0002 of
transmission at it; a quadrupole window symmetric about its centre would pass
the d3 rung one dalton below at about the same share, and the 0.763% actually
measured there would then mean a d3 fraction of 3,300%. Either the window is
asymmetric by three orders of magnitude — in which case the rungs below d4 are
scaled by a transmission nobody knows — or what sits at that position is not
d3 at all. And the second is what the energy says: that residue is 0.763% of
the precursor at 12 eV, 0.328% at 22 eV and 0.067% at 45 eV, so the same
bottle would be 98.32%, 98.77% and 98.98% pure depending on how hard the ion
was hit. An isotopic composition cannot do that. What is there is a
fragmentation channel — a hydrogen atom lost from the ammoniated molecule,
which EAD makes freely, and 1.5 mDa from where d3 would be.

**What this needs is an MS1 survey scan**, or a full-scan infusion with no
quadrupole isolation in front of it. Acquire one minute of TOF MS beside the
product-ion channel and the same line answers.

### The ladder, and why it is only a floor

Where the precursor did not survive its collision energy at all, the same
arithmetic is offered on the strongest fully-labelled rung of the water-loss
ladder — `[M+H-3H2O]+` and its −1D rung — and the line says *a lower bound*.
It answers a different question: a dehydration can leave with a label, so a d4
molecule that shed a labelled hydroxyl hydrogen arrives at the d3 position and
is counted as an impurity that was never in the bottle. Measured on the same
files with the satellite check switched off, the ladder gives d4 fractions of
36.7%, 90.1% and 85.0% for cholic acid-d4 at 12, 22 and 45 eV, against
98.3 – 99.0% from the precursors of those very acquisitions — up to a fifth of
the fully-labelled molecules leave a label behind with the water. On these
files the ladder cannot even do that much, because the fragments inherit the
mass filter that made them: the ladder rung's own M+1 satellite is
0.015 – 0.63% where the formula says 26 – 30%.

### Where it goes

The line is in the panel; the **infusion report** carries the whole envelope —
every rung with its *m/z*, its intensity, its share of the fully-labelled ion
and its fitted fraction — with the atom per cent underneath, or the reason
there is none. See [[infusion-report]]. And *Add spectrum to library…* writes
it into the record as `Isotopic_purity`, because a record keeps its peaks
above one per cent of the base peak and an isotope envelope lives at tenths of
one per cent: nothing can recover the purity from a record afterwards, so it
is written while it is still known. See [[spectral-library]].

## Against a library

The **Library** tab beside this one asks the other question — what
somebody recorded from the compound, rather than what its structure could
produce — and the two are worth reading together: [[spectral-library]].

## Annotating a whole method

**Annotate from LIPID MAPS…** in the Method workspace proposes a species for
every component still named after its precursor, using the mass measured
from the survey scan where it can. See [[annotate-from-lipid-maps]] and
[[accurate-precursor]].
