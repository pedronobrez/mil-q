---
title: The whole infusion path, measured as one thing
---
Every other page here describes one thing the program does. This one runs
all of them, in order, on the same nine acquisitions, and reports what the
whole path costs and where its parts disagree with each other.

That second half is the reason it exists. The infusion path is thirty-odd
modules written in parallel, and modules written in parallel answer the
same question twice. Two of them measure the noise floor. Three of them
say how many scans were averaged. Two of them say how many predicted ions
were found. Where the two answers differ, one of them is wrong on somebody's
screen — and nothing catches that except running them side by side and
comparing the numbers, which is what this page is.

The measurements are on the nine ZenoTOF 7600 bile-acid infusions the rest
of the manual is written against: one product-ion channel each, no survey
scan anywhere, 146 to 473 scans over 0.6 to 2.0 minutes. See
[[direct-infusion]] for what they are and [[measured-facts]] for the
figures the rest of the manual takes from them.

## The path

From a folder on disk to a document, a record and a component:

[[checking-files]] → open → [[direct-infusion]]'s verdict → the spray mask
→ the average → the noise floor → what the method isolates → the adduct →
the mass axis ([[mass-recalibration]]) → the explanation ([[lipid-maps]])
→ the margin → the unexplained peaks → the isotope evidence → the purity →
a record of one's own ([[spectral-library]], [[standard-history]]) → a
component ([[new-standard]]) → the collision energy ([[collision-energy]])
→ [[infusion-quantitation]] → the [[infusion-report]] and its folder cover
→ [[compare-infusions]] → [[python-api]].

## What it costs

Nine files, one process, from source on macOS. **Cold** is the first call
and **warm** is the same call again on the same open files.

| stage | cold | warm |
|---|---|---|
| import `milq` | 0.24 s | — |
| `folder.check_files` | 0.001 s | 0.001 s |
| open all nine | 0.258 s | 0.014 s |
| `is_infusion` ×9 | 0.009 s | 0.000 s |
| `strongest_channel` ×9 | 0.000 s | 0.000 s |
| `mask_for` ×9 | 0.014 s | 0.014 s |
| **`average_stable` ×9** | **10.94 s** | **11.10 s** |
| the whole run averaged instead, ×9 | 13.09 s | 13.54 s |
| **`noise_floor` ×9, on its own** | **14.58 s** | **13.99 s** |
| **`summarise` ×9, with a library** | **21.44 s** | **20.51 s** |
| the isolation verdict ×9 | 0.174 s | 0.174 s |
| `margin.cross_validate` ×9 | 1.64 s | 1.75 s |
| `unexplained.annotate` ×9 | 0.160 s | 0.071 s |
| `library.search` ×9 | 1.59 s | 1.59 s |
| `search_energy` ×9 | 1.59 s | 1.59 s |
| `records_from_summary`, `write_msp` | 0.001 s | 0.001 s |
| `standard_history.history_of` | 0.002 s | 0.001 s |
| `component_from_infusion` ×9 | 0.042 s | 0.041 s |
| `energy.recommend` | 0.001 s | 0.001 s |
| the cover's paragraph | 0.000 s | 0.000 s |
| the summary CSV | 0.002 s | 0.002 s |
| save the project | 0.001 s | 0.001 s |
| `compare_infusions` | 0.003 s | 0.003 s |
| `quantify_infusions` | 0.000 s | 0.000 s |

Peak resident memory for the whole of that in one process: **0.73 GB**.
The [[command-line]]'s folder route, which does the same work and lays out
a 58-page PDF as well, holds **1.15 and 1.21 GB** over two runs and takes
**52 s and 42 s** — the seconds being the one figure here that is the
machine's rather than the program's, as that page says.

Three things follow from the table, and only the third was expected.

**Reading and averaging is the whole cost.** `average_stable` and the
noise floor are 25 of the 27 seconds; every measurement made *on* the
averaged spectrum — the explanation, the margin, the library search, the
energy profile, the annotation, the comparison, the exports — comes to
under 5 s for all nine put together, and thirteen of the twenty-three
stages are under a hundredth of a second. Anything worth optimising on
this path is in `spectrum_rt_range`, and nothing else is worth optimising
at all.

**Warm buys nothing.** Only opening the files is cheaper the second time
(0.258 s → 0.014 s), because the `.wiff` handles stay open. Every stage
that reads spectra costs the same on the second pass as on the first:
10.94 → 11.10 s, 21.44 → 20.51 s. The reader does not keep an averaged
spectrum, so *Measure* on the Infusions tab pays the full price every time
it is pressed, and a script that averages a run twice reads it twice.

**Leaving the unstable scans out is faster than keeping them.** 10.94 s
against 13.09 s, because the mask's stretches hold fewer scans than the
run. The mask itself costs 1.6 ms a file — one chromatogram, no spectrum.

## Where two modules disagreed

Nine of these were found by running the path end to end and comparing the
numbers each stage reported for the same file. Six were small enough to
fix and are fixed; three are recorded below with their figures.

### The label count, folded in twice

`infusion_report.labelled_formula` returns a formula with the labels its
name declares **already folded in**, together with how many it folded —
`("C24H36D4O5", 4)` for a component named `CA-d4` carrying `C24H40O5`.
`axis_subject`, which chooses the formula the lock-mass ladder is built
from, took both and folded the four labels in a second time, so every d4
standard became a d8 one: `C24H32D8O5`, no adduct of which is within 4 Da
of the 430.35 the channel isolates.

The consequence was silent and total. **All nine infusions refused their
own mass axis** with *no lock mass … 430.34 is none of the adducts of
C24H32D8O5*, while the isolation verdict two lines above on the same page
said *430.34 = [M+NH4]+ of CA-d4* — the two routes reading one component
table and disagreeing about what the compound is. With the labels folded
once, **seven of the nine fit a correction** from 3 to 8 rungs, between
−8.6 and +6.6 ppm; the two `_TESTEARTIGO` acquisitions still refuse, which
is correct, and now name the right formula while doing it.

### The record's comment counted scans that were not in it

The pane's title, the report's header and the Infusions tab's *Scans*
column all say `464 of 473` on the DCA-d4 CID run. The comment on a record
written from that row said `average of 473 scans`: `records_from_summary`
wrote `report.scans`, which is how many the *run* holds, where the other
three write how many were averaged. Four accounts of one average, one of
them counting nine scans the spray had faltered on. It now writes
`scans_averaged()`, which is the number the other three already agree on.

### The folder check reported macOS's own metadata as a stray scan

Reading the nine off an external drive made
`._CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1.wiff.scan` — the AppleDouble file
the Finder writes beside every file on a volume that is not APFS, which is
where instrument data actually travels. It ends in `.scan` and its stem is
in no folder, so [[checking-files]] reported it as *a stray scan belonging
to no .wiff in this folder*: a finding about a file the user never made
and cannot act on. A `._X.wiff` would have been worse — `raw.is_supported`
says yes, and it would have gone into the list of files to open. Names
beginning with a dot are now left out when a folder is listed. A dot-file
named outright on the command line still goes through, because a path that
was given was meant.

### The cover stopped saying what was wrong with the two odd files

The folder report's cover sums its table a sentence at a time, and the
sentence for the precursors is meant to separate a mass error from a
different ion: *2 whose method isolates 839.56* is a different finding
from *1 at +30.3 ppm*. It asked for the error first and the isolation
second, so a row with any measurable error never reached the isolation
bucket. That was harmless until the noise floor was measured off the
acquisition instead of fixed at a hundred counts — after which **all five
unconfirmed rows had an error to report** and `isolated_precursors`, the
whole of which exists for these two files, became dead code. The cover
read:

> 4 of 9 precursor(s) confirmed within 25 ppm; 5 not: 5 between −70.7 and
> +30.3 ppm.

which reports the two `_TESTEARTIGO` acquisitions as an instrument
slightly out of calibration, when what happened is that their method
isolates a mass that is no adduct of the compound their name claims. The
isolation is now asked first, and it reads:

> 4 of 9 precursor(s) confirmed within 25 ppm; 5 not: 2 whose method
> isolates 839.56, 3 at −70.7 and −30.1 and +30.3 ppm.

`isolated_precursors` only answers where the compound has another cluster
that *did* confirm, so asking it first cannot swallow an ordinary miss.

### The API averaged a different spectrum from the application

`api.Acquisition.infusion_average` said in its own docstring that it was
"the view the Explorer opens an infusion on" and averaged the whole run
instead, spray bursts included. On the three of the nine whose spray
faltered it disagreed with the Explorer, with the [[infusion-report]] and
with `api.infusion_report` by 0.62%, 1.99% and 2.90% of the base peak, and
reported 473, 473 and 257 scans where the application reported 472, 464
and 256.

Worse, it disagreed with itself: `api.infusion_report` explained *that*
spectrum and searched the library with it, then called `report_for`, which
averages again with the mask, and **printed the masked spectrum beside the
figures measured off the unmasked one**. Both now use the mask, so the
document's picture and its numbers come off one array.

### Infusion quantitation measured responses off the bursts

`infusion_quant.centroids_of` averaged the whole run too, so a response
read for a ratio and the same ion's height on the page beside it came off
two different spectra — by 2.90% on the DCA-d4 CID run. A ratio of two
responses is meant to divide that sort of thing out and does not, because
the burst is in one vial's run and not the other's. It now takes the
sample as well and applies the mask where the sample reads as an infusion.
Measured on the nine, the base peak moves −0.62%, −1.99% and −2.90% on
the three files that lose scans and is unchanged, to the digit, on the
other six.

## Still open

### There are two noise floors, and both are right

`infusion.noise_floor_for(channel)` measures the floor from the **whole
run**, cached per channel; that is what the [[explorer]]'s label floor and
status line use. `report_for` measures it again from the **masked average
with the count of scans that went into it**, and that is what the
[[infusion-report]], its peak table and its precursor gate use. On the
nine:

| | whole run | the report's |
|---|---|---|
| lowest | 0.068 | 0.068 |
| highest | 3.53 | 4.27 |
| CA-d4 CID | 0.962 | 1.429 |
| DCA-d4 CID | 0.583 | 0.753 |
| TDCA-d4 CID | 2.447 | 4.272 |

Both are defensible — the second is measured on the spectrum actually
printed, which is the right thing for a page to gate its peaks on — and
the manual has quoted both ranges in different places without saying which
was which. This page is where they are named. Nothing is decided
differently by the two on these files, because a peak is either eighty
times the background or a tenth of it, and never in between. What would
decide something differently is a peak within a factor of two of the
floor, and none of the nine has one.

### A record does not match its own run at 100

The manual has said that a record of one's own scores 100 against the
spectrum it was made from, "which proves the file was written and read
back". Measured now: **97, 96 and 100** for the three CID runs. The reverse
score is 100 on all three and every one of the record's peaks is matched —
*179 of its 179 peak(s) matched* — so the round trip is exact and it is the
forward score that is not 100.

The cause is that the record and the query are picked from the same
spectrum by two different rules. A record is written from `row.peaks`,
which is `pick_peaks` at one per cent of the base peak, capped at 200,
merging maxima closer together than `OWN_MIN_DISTANCE`. The search reads
`_sticks`, which is every centroid of the profile. On the CA-d4 CID run
those are 179 peaks against 819 centroids, **204 of which are at or above
one per cent** — so the query holds 25 peaks at scoreable height that the
record was never written with, and a forward cosine over everything both
spectra hold cannot reach 1.

| | record peaks | centroids | of those, ≥1% | score | reverse |
|---|---|---|---|---|---|
| CA-d4 CID | 179 | 819 | 204 | 97 | 100 |
| DCA-d4 CID | 191 | 1,100 | 226 | 96 | 100 |
| TDCA-d4 CID | 25 | 470 | 25 | 100 | 100 |

Neither side is obviously wrong: a library search should see the whole
spectrum, and a record should not carry three hundred peaks. So nothing is
changed here, and what the manual should cite as proof of the round trip
is the **reverse** score and the *N of N* count, both of which are exact.

### The two infusion documents do not report the same ions

`python3 -m milq.app --infusion-report` and
`milq.api.infusion_report` both write "the infusion report" and both
are given the same nine files, and they do not agree about how much was
explained:

| | the CLI, and the Infusions tab | `api.infusion_report` |
|---|---|---|
| CA-d4 EAD 12 eV | 3 of 56, 85.0% | 4 of 882, 85.9% |
| CA-d4 EAD 22 eV | 8 of 56, 63.6% | 15 of 882, 71.2% |
| CA-d4 CID 45 eV | 2 of 56, 24.2% | 8 of 882, 32.5% |
| DCA-d4 CID 40 eV | 3 of 41, 17.0% | 7 of 882, 21.7% |
| TDCA-d4 CID 30 eV | 5 of 104, 72.7% | 12 of 2,241, 86.4% |

Both are correct and they are answering different questions. The CLI goes
through `summarise`, which explains from the **component table's formula**
and enumerates the precursor with up to three neutral losses — 56 ions for
cholic acid-d4. The API resolves the *name* through the standards table to
a LIPID MAPS record with a drawing and enumerates **bond cleavages** — 882
ions. Each says which it did, in its own basis line (*predicted from the
formula alone* against *predicted from its structure*), so neither is
lying; but the denominators are not comparable and the shares are not
either, and nothing outside this page said so. A reader comparing two
documents of the same vial should check the basis line before the
fraction. `explain_any` is a third answer again — it runs every route and
ranks them, and on the CA-d4 EAD 22 eV run it ranks a triacylglycerol at
[M+2H]2+ *first*, at 95.0%, over CA-d4's own 63.6%, while the margin on
the same page reports CA-d4 ahead of that same triacylglycerol by 41.9
points. The margin scores its rivals at the settings the chosen compound
was scored with; `explain_any` gives every route its own best settings.
Same spectrum, same rival, two orderings.

### The nine cannot exercise infusion quantitation

Each of the nine isolates one precursor, so an analyte and its internal
standard are never in the same acquisition. Pairing them anyway —
CA-d4 and DCA-d4 against TDCA-d4 — gives 18 pairs over 9 infusions with 6
ratios, and the ratios are formed against 0.24 counts of a standard that
is not in the vial. `quantify_infusions` is exercised on the synthetic
fixtures in `tests/test_infusion_quant.py` and on nothing real; see
[[infusion-quantitation]] for what it needs, which is one acquisition
carrying both.

## What still reproduces

Re-run against the current code, these came back unchanged, to the digit:

- the flatness figures, 0.9936 to 1.0000 on both measures for all nine;
- the spray mask: 1, 1 and 9 scans left out on the three CID runs and none
  on the other six, worth 0.61%, 1.66% and 2.78% of the run's ion current;
- every base peak, every precursor mass and every error in ppm the
  [[infusion-report]] tabulates — 430.3196 at −70.7 ppm and 84 counts,
  430.3489 at +20.7, 414.3275 at −30.1 and 33 counts, 504.3273 at +14.4
  and 123 counts;
- the ions found: 2, 8 and 3 of 56 for CA-d4, 3 and 8 of 41 for DCA-d4,
  5 and 5 of 104 for TDCA-d4;
- the margin sentence, word for word: *explains 63.6%; the best of 17
  neighbour(s) (TG 17:1(9Z)/18:4(6Z,9Z,12Z,15Z)/18:4(6Z,9Z,12Z,15Z)
  [iso3] as [M+2H]2+) explains 21.7%: a margin of 41.9 points*;
- the report floors the page quotes, 1.43 and 0.75 counts on the two CID
  runs, at 59 and 45 times the height in the precursor window;
- the summary line, to the digit: *3 compound(s) in 9 infusion(s); 4 of 9
  precursor(s) confirmed within 25 ppm; 34 of 458 predicted ion(s) found
  across 7; 4 with an own record above 60*;
- the folder document at **58 pages**, nine files read and none skipped;
- the project round trip: nine infusions saved as figures, read back
  without opening a file, and compared against themselves at a median 100
  forward and 100 reverse, the same ion in 9 of 9, nothing moved.

Three figures moved and the manual has been corrected: the own-record
self-scores (100 and 99 → 97 and 96, above), the cover's precursor
sentence, and the record's scan count.

## Doing it again

The path is exercised end to end, on the synthetic fixtures rather than on
anything real, by `tests/test_integration_path.py`. It asserts the
agreements this page is about rather than the values: that the record's
comment says what the report's header says, that the mass axis and the
isolation verdict name one formula, that the API's average is the
application's average, and that the noise floor a report gates on is the
one it printed. A figure changing is a measurement; those four changing is
a contradiction, and the test is there to make the difference visible.
