---
title: What was measured
---
Every figure in this manual was produced by running something on real
data, not by reading code or repeating a vendor's claim. This page collects
them, with what they were measured on, so that a reader can decide how
far each one carries to their own instrument. Unless said otherwise the
data is one of three sets: five real acquisitions from a TripleTOF 5600 in
**negative** mode — a targeted MRM-HR method of 81 experiments across two
periods, about 24,000 spectra each; a batch of 26 injections on the same
instrument in **positive** mode, a scheduled sphingolipid method of 141
components and 11 internal standards sampled every 14.6 s; and nine
ZenoTOF 7600 direct infusions of bile-acid standards, **positive**,
product-ion scans with no survey scan at all. Which set a figure came from
is said beside it.

## The reader

- **Builds agree.** The `--digest` fingerprint from source on macOS, from
  the CI disk image and from the Windows installer under CrossOver is
  byte-identical: 405 channel chromatograms, 25 spectra, 125 integrated
  peaks with areas to nine decimals. All 405 channel hashes differ from one
  another, so those were five different acquisitions rather than one read
  five times.
- **Without the `.wiff.scan`, the `.wiff` opens and looks whole.** Measured
  on a ZenoTOF 7600 infusion file whose companion had been renamed by
  hand: the sample list, the metadata, the method parameters and the total
  ion chromatogram of every channel read normally; the base peak
  chromatogram, every extracted ion chromatogram and every spectrum
  failed, Clearcore2 reporting a missing 'scan' file for the spectra and a
  missing assembly (`OFX.Core.Contracts`) for the chromatograms. Nothing
  in the file itself says the companion is absent; only reading a scan
  does, which is why one is read when the file is opened.
- **A `.wiff2` holds no scan data, and that was measured before it was left
  out.** Clearcore2 raises `Invalid OLE structured storage file` on all nine
  `.wiff2` of a ZenoTOF 7600 folder — with the companions beside them, with
  each companion removed in turn, and when the file is renamed `.wiff`, so
  it is the container and not the extension — and its own
  `CheckDataFileIntegrity` calls every one of them `NotWiffFile`. The
  Clearcore2 assembly that writes the format declares its whole schema:
  seven tables, none with a column for a spectrum, a peak, an intensity or
  a chromatogram, and a `header` table of `wiff_hash`, `scan_hash` and
  `scan_size`. The sizes agree — over those nine the `.wiff.scan` spans
  1.67–9.88 MB (5.9×) and the `.wiff2` 303–406 kB (1.34×, five distinct
  values), correlating 0.989 with the `.wiff` and 0.748 with the scan data.
  Reading one acquisition's `.wiff` with the `.wiff2` beside it and with it
  deleted gave the same sample, the same experiment, the same 473-point TIC
  and the same 13,705-point first spectrum. See [[formats]].
- **Formats agree, except in one place.** Exported to mzML and read back:
  spectra, channel chromatograms, the run's TIC (577 points) and integrated
  areas identical; extracted ion chromatograms differ by a median 0.58% of
  peak height, at most 12%, always lower here, because SCIEX counts part of
  a peak whose points fall just outside the window. End to end, one
  component quantified from both formats: same retention time, same width,
  area 0.54% apart. Two attempts at the vendor's edge rule failed; the
  second was better on 41 channels and worse on 38.
- **ProteoWizard agrees.** msconvert reads what this writes, and its own
  mzML written from that reads back here with identical spectra and
  chromatograms.
- **Summing stored points instead of taking the vendor's total** moved
  every integrated area by 2%. The vendor's figure is used.
- **Channels from scan properties alone** gave 69 where the acquisition had
  81; from the cycle of acquisition, 81.
- **A stripped profile's zeros**, drawn without restoring them, put a peak
  label at 184.8466 for a peak at 185.0077.

## Integration

- **A window narrower than five points returned nothing**, whatever was in
  it; a peak of 44,875 counts read as noise. Giving the detector three scans
  either side took the rows with a peak from 1,771 to 2,665 and the
  components with any peak from 89 to 139 of 141.
- **The peak rule changed nothing on that method**: of 896 windows with a
  retention time, none held two peaks (a ±0.5 min window at 14.6 s is four
  points); the 593 windows that did hold two belonged to components with
  no time, where *nearest* has nothing to be near.
- **Phase sensitivity at 14.6 s** on synthetic peaks: a trapezoid varies
  with the scans' phase by 16.8% at 11.3 s width at half height, 5.1% at
  14.1 s, 1.1% at 17 s; a Gaussian fit is exact wherever it can be made,
  and can be made for 34 of 60 phases at 14.1 s and all 60 at 17 s. With
  Poisson noise on a thousand counts, at 14.1 s: trapezoid 5.8%, fit 3.0%.
- **A fit to two points** is biased low by seven per cent; a fit through
  three with three parameters is exact whatever the points are, and on the
  real batch that put a curve through an apex of 52,000 counts and
  neighbours of 44 and 98 and reported an area a third smaller. Hence the
  rule that the fit needs three points at or above 1% of the apex.
- **The three algorithms on the real batch**: valley 2,638 rows found;
  summation 857; Gaussian 2,638 with 2,238 fallen back, 2,169 because the
  peak was fewer than three points wide. Where fitted, the fit's area was
  a median 0.977 of the trapezoid's; no component moved by more than 20%.
  The internal standards' %CV was the same under all three. The algorithm
  does not move that batch's numbers; the sampling does.

## Sampling

- On the 26-injection batch, one scan every 14.6 s against peaks with **a
  median of one point** on them; 129 of 139 components typically under the
  three a fit needs, and 1 with five or more. Widths could be measured only
  on the wider peaks (two points above half height), and those read a
  median 14.6 s — one cycle — so every cycle time the sampling report
  recommends for that batch is an upper bound.

## The schedule

- The real method scheduled over its windows: 59 transitions with a time,
  at most 24 acquired at once, and a 3 s cycle still leaving 120 ms of dwell
  — against the 14.6 s the batch was acquired at with all 144 running
  unscheduled. 72 of its 141 precursors lie outside the 50–700 survey.

## The spectral library

- MassBank in NIST format, 139,006 records: read in 5 s, 1.3 GB held; a
  filtered search in milliseconds, an unfiltered one in 2–7 s. On the
  batch's product-ion spectra it named a C16 sphingomyelin (46 / 79), a C16
  ceramide (32 / 94), a C24:1 ceramide (11 / 90) and a C18 sphingomyelin
  (48 / 96) — plain and reverse scores — and nothing for the C17 standards
  the library lacks. Before the two-peak rule, a spectrum that was mostly
  184.07 scored 83 against a laxative on that one peak; before the
  unknown-precursor rule, 24,000 records with no precursor dominated every
  filtered search.

## Two batches

- The same 26 injections under the method before and after two internal
  standards' retention times were corrected: rows found 2,607 to 2,638,
  the standards' median %CV 101.8 to 87.7, and the two corrected standards
  from 8 and 3 rows to 23 each — the points per peak unchanged at one,
  since the acquisition was the same. What [[compare-batches]] is for.

## The mass axis

- On the 26-injection batch, whose survey scan covers 50–700, the one
  internal standard strong enough to measure — `SM(d18:1/12:0)` — held to
  −4.0 ppm across the run with a 16 ppm spread between injections. Nine
  others came back with spreads of 98 to 534 ppm: not the same ion twice.
  The first version of the measurement called one of them drifting by
  −351 ppm, which is why a spread over 25 ppm now stops a trend being
  fitted at all.
- Floors proposed from the same batch: 5,240 for that standard, 522 and 566
  for the two at about a thousand counts, and 2 to 25 for the rest — which
  is what their medians are.

## Noise

- Over 846 real traces, the median had three non-zero points in sixty-one
  and 9% had a baseline that varied at all. The noise could be measured for
  23% of the peaks found.
- With the one-count floor standing in for an unmeasurable noise, a
  standard of 30 counts reported S/N 30 and one of 42,400 reported 42,400.
- Noise measured inside the retention-time window read 16,944 where the
  trace's noise was 505: S/N 19 automatic against 531 by hand.

## Quality control

- A median absolute deviation of 0.8% made a standard 2.4% low a four-sigma
  outlier; hence the per-cent floors.
- An injection where every standard came back at a fifth of normal sat at
  2.6σ in a batch that varied by a third; hence the 50% rule.
- Of eleven internal standards, eight had a median response between 4 and
  52 counts and produced almost every flag; hence the S/N 10 gate.
- The standards separately scattered between 32% and 228%; the injection
  response index put the injections within ±18% with three exceptions.
- The batch supports no response floor: successive-injection scatter did
  not track median response.

## Retention-time estimation

Checked against the 54 components that already declared a time, the
estimate landed within one sampling interval for 45% of components under
100 counts, 54% between 100 and 1,000, 54% between 1,000 and 10,000, and
88% above 10,000. Nothing offered was above 10,000, so nothing was
pre-ticked.

## The report

The first version printed at a twelfth of its size. A hundred-page report
is laid out three times and takes about seventeen seconds.

## What it costs on one machine

Speed is a measurement like any other, so it is made the same way:
`tools/bench.py` in the source tree runs each piece of real work as a named
scenario, in its own process, timed on the wall clock with the process's
peak resident size. These are the five TripleTOF acquisitions on an Apple
M4 with 16 GB, Python 3.14, against the same scenarios run on version
0.9.0.

| What | 0.9.0 | now |
|---|---|---|
| centroid 25 profile spectra | 0.568 s | 0.045 s |
| the peak review grid reshaped 1x1 to 8x8 and back | 1.185 s, 400 MB | 0.212 s, 187 MB |
| the run as a contour grid | 0.182 s | 0.066 s |
| 25 spectra off a channel | 0.075 s | 0.034 s |
| average 100 scans | 0.287 s | 0.175 s |
| an extracted ion chromatogram | 0.047 s | 0.036 s |
| open five acquisitions in the window | 0.541 s | 0.444 s |
| 81 components integrated over five acquisitions | 0.523 s | 0.496 s |
| every algorithm compared over the batch | 0.665 s | 0.668 s |
| read one mzML end to end | 0.764 s | 0.699 s |
| six extractions off one mzML channel | 0.856 s | 0.707 s |
| every channel's base peak chromatogram, mzML | 1.738 s | 1.024 s |
| the `--digest` fingerprint of five acquisitions | 0.965 s | 0.909 s |
| the manual printed to PDF, 106 pages | 1.466 s | 1.462 s |

Two figures are not in that table because they are not measured on these
files. The main window, with a LIPID MAPS index installed, took about one
second and **688 MB** of memory to build, almost all of it the index being
read to print how many structures it holds; it now builds at **144 MB**
without reading it at all — see [[lipid-maps]]. And the nine bile-acid
infusions measured together in the Infusions tab, warm, went from 7.7 – 8.5
seconds to 1.7 — see [[infusion-report]].

The last three rows of the table are the honest part: the comparison, the
mzML reader and the printed manual barely moved, because what they spend
their time on is Qt's page layout and the parsing of 47 MB of XML, neither
of which is ours to make faster.

## These figures are tested

A number written on a page cannot fail. Since the acquisitions themselves are
never in the source repository — they belong to other people, and one of them
is unpublished — every figure above used to be prose that nothing checked.

The repository now carries `tests/real/`: one test per figure, run against the
same acquisitions, which fails when a number moves beyond the tolerance the
figure was written to. It is skipped unless the data is asked for and present
— `MILQ_REAL_DATA=1 pytest tests/real`, or `pytest -m real` — so it never
runs in continuous integration, where there is nothing to read. Each test
skips itself, naming the path it looked for, when its own files are elsewhere,
and each says in its own words which figure on this page or in `CLAUDE.md` it
is asserting.

Where a figure had already moved by the time it was covered, the test asserts
what the program does **now** and records the older figure beside it with what
is known about the difference. Six on this page and in `CLAUDE.md` are in that
position; `tests/real/README.md` lists them.

## The infusion path measured as one thing

Every figure above was measured on one stage in isolation. [[integration]]
runs the whole direct-infusion path end to end on the nine ZenoTOF
acquisitions instead — the folder check, the verdict, the mask, the
average, the noise floor, the isolation, the axis, the explanation, the
margin, the library, the report, the exports and the comparison — and
gives what each stage costs cold and warm, what the whole holds in memory,
and the places where two modules answered the same question differently.
Six of those disagreements are fixed and three are still open, with the
figures for each.

## Where the rest is written down

The source repository's `CLAUDE.md` records the same facts for whoever
changes the program, with the commit each one came from; the tests assert
most of them.
