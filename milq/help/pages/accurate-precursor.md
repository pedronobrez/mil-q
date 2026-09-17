---
title: Accurate precursor mass
---
A method's precursor list is written by hand — `351.20`, `313.24` — and is
only good to the decimals it was typed with. Looking a lipid up from that
is asking a database for digits the number does not carry: at ±0.005 Da a
mass near 350 is uncertain by 14 ppm, and the search window fills with
whatever happens to sit nearby.

The survey scan holds the real number. Before a lipid search on behalf of a
component, the program finds the precursor ion in the full-scan (TOF MS)
channel **at the time the product-ion channel actually sees the peak**, and
uses the mass the instrument measured.

## How it is measured

1. The component's own transition is integrated to find when it elutes; that
   time anchors the search.
2. In the survey channel, the spectrum at that time is searched within
   ±0.25 Da of the written precursor — wide enough to absorb a hand-rounded
   value, well inside the roughly 1 Da that Q1 isolates, so a neighbouring
   nominal mass can never be picked up.
3. The peak found is centroided; a peak weaker than 100 counts is not
   trusted as a mass measurement. That hundred is a fixed floor written for
   a TripleTOF survey scan, and it is fixed only here: where the spectrum
   is the average of a whole [[direct-infusion]], the floor is measured off
   that acquisition instead and comes out far lower — see
   [[signal-to-noise]].
4. The same is done in every open sample. The samples have to agree to
   within 25 ppm to be measuring the same ion; the consensus is the median.
5. The **surviving precursor** in the product-ion scan — the unfragmented ion
   that passed Q1 — is measured too, and the two must agree to within
   25 ppm.

That last check matters. The survey sees everything eluting at that moment,
so a strong interference inside the search window can win; whatever
survives fragmentation must have passed through Q1's isolation window
first, which is the confirmation that the survey peak is the transition's
own precursor.

## What the mass is then used for

Where the survey can measure a precursor, a lipid search uses that mass at
±10 ppm. Where it cannot, the window falls back to the precursor's own
precision as written: a mass written as `351.20` is known to ±5 mDa, and
asking for 10 ppm of it would be inventing digits.

On real data the difference decides the answer. A transition written as
`325.20` matches `FA 18:3;O3` at nominal precision; the survey scan puts the
ion at 325.1887 and the product-ion scan agrees to within 1 ppm, which
rules that species out at 41 ppm.

## The survey confirms the adduct

The survey answers a second question the product-ion scan cannot. A channel
written `647.5` is a mass; which *ion* that mass is — protonated,
ammoniated, sodiated — is a deduction from the molecule's formula, and it is
wrong the moment the formula is. Q1 passed one mass and threw the isotopes
away with everything else, so the product-ion scan cannot settle it. The
survey holds both halves of the answer: the exact mass of every adduct the
molecule could have produced, and the isotope pattern that says whether what
sits there is a monoisotopic ion or somebody else's satellite.

Each candidate adduct is asked two things:

1. **Is it there?** The nearest peak within ±0.05 Da of the ion's exact
   mass, centroided, has to sit within **25 ppm** — the same figure the
   consensus above uses to say two measurements are of the same ion — and be
   at least 100 counts.
2. **Does it look like that ion?** The theoretical M, M+1 and M+2 are
   computed for the **ion's own composition**, the adduct's atoms included:
   `[M+NH4]+` carries a nitrogen and four hydrogens the molecule has not
   got, and `[M+Cl]-` carries an M+2 of 32% that the molecule has not got
   either. Each satellite is scored against the larger of measured and
   expected, and the satellites are averaged weighted by how much of the
   pattern each is — which puts about five sixths of the weight on M+1 for a
   lipid.

Both are reported for every candidate, present or not, because an adduct the
survey does not show is a measurement too.

### What it measured

Injection 01 of a 26-injection sphingolipid batch on a TripleTOF 5600,
positive, with a TOF MS 50–700 survey. The survey is averaged over the same
scans as the product spectrum — two of them, at one scan every 14.6 s.

These are **chromatographic** runs, not infusions: no infusion with a survey
scan was to hand, so the survey was averaged over each compound's own
elution, which is the same measurement an infusion makes over its whole run.
Nothing here is limited to infusions — any acquisition whose method carries a
full-scan channel over the precursor gets the same answer.

`SM(d18:1/12:0)`, C35H71N2O6P, written `647.5`, over its peak at 5.60 min:

| adduct | exact | found | Δ ppm | height | of the strongest | M+1 measured / expected | pattern |
|---|---|---|---|---|---|---|---|
| `[M+H]+` | 647.5123 | 647.5112 | −1.6 | 51,341 | 100% | 0.37 / 0.40 | 0.87 |
| `[M+Na]+` | 669.4942 | 669.4956 | +2.1 | 6,443 | 12.5% | 0.53 / 0.40 | 0.76 |
| `[M+K]+` | 685.4681 | 685.4571 | −16.1 | 223 | 0.4% | 2.76 / 0.40 | 0.13 |
| `[M+NH4]+` | 664.5388 | — | nearest 69 ppm away | — | — | — | — |

`Cer(d18:1/16:0)`, C34H67NO3, written `538.6`, over its peak at 4.89 min:

| adduct | exact | found | Δ ppm | height | of the strongest | M+1 measured / expected | pattern |
|---|---|---|---|---|---|---|---|
| `[M+H]+` | 538.5194 | 538.5197 | +0.6 | 7,690 | 100% | 0.33 / 0.38 | 0.77 |
| `[M+Na]+` | 560.5013 | 560.5071 | +10.4 | 1,025 | 13.3% | 0.67 / 0.38 | 0.55 |
| `[M+NH4]+` | 555.5459 | 555.5340 | −21.5 | 170 | 2.2% | 1.00 / 0.38 | 0.33 |
| `[M+K]+` | 576.4753 | — | nearest 60 ppm away | — | — | — | — |

Three things in those two tables are the whole of why the pattern is asked
at all.

**The mass alone admits an ion that is not there.** The ceramide's
`[M+NH4]+` is 21.5 ppm out, inside the 25 that says "same ion", and 170
counts, over the 100 that says "measurable". Its M+1 and M+2 come back at
1.00 and 1.00 of its M, which is what a stretch of flat noise looks like and
nothing else. The pattern scores it 0.33 and it ranks last.

**A satellite is where a lipid keeps its own family.** The ceramide's true
`[M+H]+` has an M+2 four times too big — 0.29 against 0.076 — because the
window at 540.53 holds the co-eluting **dihydroceramide**, C34H69NO3 at
540.5350, 17 ppm from the ceramide's own M+2 at 540.5259 and inside the same
0.02 Da. A rule that summed the satellites' errors would score the compound's
own adduct 0.43 and call it a disagreement; weighted per satellite it scores
0.77. Every lipid class has its saturated analogue two daltons up, so this is
not an accident of one batch.

**Several adducts of one molecule is the ordinary case, not an exception.**
Both compounds run at about `[M+H]+` 100%, `[M+Na]+` 13%, and that is worth
knowing: an eighth of the signal is on a channel nobody acquired.

### When it does not confirm

The same 647.5 channel has a **larger** peak at 9.26 min than at 5.60. The
survey at 9.26 shows nothing within 25 ppm of any adduct of the
sphingomyelin's formula: its nearest peak is 647.5575, +69.9 ppm from
`[M+H]+`, and no formula this program can build accounts for it as that
molecule. The adduct is then reported as read from the written mass alone,
which is what it always was.

Where the acquisition has **no survey at all** — the nine bile-acid
infusions, acquired as product-ion scans only — nothing changes and the
report says so: *no survey scan covering 430.35, so nothing independent says
which ion it is*. That is not a failure; it is the difference between an
adduct measured and an adduct deduced, written down.

The one thing the survey is allowed to overrule is a written precursor that
fits **nothing**. The ceramide above is written `538.6` for an ion of
538.5194 — 0.08 Da out, eighty times what an adduct is allowed. Without a
survey that is refused, because a typing mistake and a rounding cannot be
told apart. With one, the instrument has already said which ion was there,
so it is read as `[M+H]+` and the sentence says why: *0.0806 Da from the
written mass, inside the ±0.7 Da the quadrupole passes*.

## Where it appears

- [[annotate-from-lipid-maps]] — each proposal says whether its mass came
  from the survey or was written, and what window was used.
- the [[lipid-maps]] tab's Explain — the precursor typed there is what the
  candidates are looked up by;
- [[mass-drift]] — the same measurement made in every injection, to see
  whether the mass axis held through the run;
- [[mass-recalibration]] — correcting the axis from the standards that carry
  a formula. With it on, this measurement is reported raw and corrected side
  by side: the measured value is never overwritten, because the correction
  was fitted from it.
- the [[lipid-maps]] tab's Adduct box, on *from the precursor* — the line
  under it says whether the survey confirmed the adduct, and the
  [[infusion-report]] header and the Infusions tab carry the same in a cell
  each. A record written to a library of your own says in its comment which
  of the two it was.
