# MIL-Q — status and working notes

Open source review and quantitation for LC-MS data. A working replacement for
SCIEX PeakView (qualitative) and MultiQuant (quantitative), reading `.wiff`
directly and `.mzML` from any instrument.

This file is for picking the work up in a new session without rereading the
history. It records what is true, what was measured, and what is not settled.
`README.md` is for someone using the application; this is for someone changing
it.

**Version 1.0.2 released. 1943 tests. Public repository.**

The repository was recreated on 2026-09-07 to drop a history that showed a
person's name and unpublished results in its screenshots. Rewriting was not
enough: GitHub keeps `refs/pull/*` forever and two diagnostic pull requests
still pointed at the old commits. The previous repository is
`pedronobrez/openquant-archive`, private, and the installers built from it are
saved outside any repository in `~/Documents/OpenQuant-releases/v0.6.1`.
**Do not open a pull request from a branch carrying anything that must not be
public: closing it does not remove the ref.**

---

## Ground rules that came out of the work

These were learned the expensive way. Breaking one has cost a day before.

- **Measure before claiming.** Every performance and fidelity number in this
  file was produced by running something, not by reading code. Two attempts at
  reverse-engineering a vendor algorithm were made and both were wrong; the
  second looked right until it was tested on data it had not been fitted to.
- **A stated difference beats an invented rule.** Where behaviour could not be
  reproduced faithfully, the plain version ships with the measured gap written
  down. See the extraction note below.
- **Never substitute our arithmetic for the instrument's.** Totals, retention
  times and areas come from the vendor where the vendor reports them. Summing
  the stored points instead moved every integrated area by 2%.
- **Raw data is never committed.** `.wiff`, `.wiff.scan`, `.mzML`, `.csv` are
  ignored. Verified: no raw file has ever been in the history.
- **The manual ships with every version.** `milq/help/pages` is the
  reference the user feeds to NotebookLM; a release that changes what the
  application does changes the page that describes it, adds itself to
  `version-history.md`, and regenerates the PDF for the user (never
  committed). `tests/test_manual.py` fails on an unresolved `[[link]]`, a
  page under six hundred characters, or a file the index does not list.
- **`x or default` is a trap for a measured zero.** A scan with a total ion
  current of zero was read as missing metadata and dropped a whole channel
  onto a fallback, on three of five real files.

---

## Layout

```
milq/
  raw.py          open_raw(path) → the right reader by extension. The only
                  place that knows formats exist.
  wiff.py         SCIEX, through Clearcore2 over .NET
  mzml.py         mzML reader and writer
  bootstrap.py    brings up .NET and the SCIEX assemblies off Windows
  processing.py   smoothing, baselines, peak detection, centroiding,
                  restore_profile_zeros, and the three integration
                  algorithms: valley, summation, Gaussian fit
  quantify.py     extraction and integration of a component in a sample
  compare.py      the batch integrated every way, and the differences
  calibration.py  regressions and weightings
  statistics.py   grouped means, SD, %CV
  qc.py           control charts through the run, drift, replicate precision
  sampling.py     points per peak, per component, and the cycle time the
                  peaks would need
  mass_drift.py   each standard's measured mass through the run: did the
                  axis hold
  schedule.py     the scheduled acquisition the method implies, and what a
                  target cycle leaves each transition
  library.py      MSP/MGF spectral libraries, and a spectrum searched
                  against one: plain and reverse cosine
  recalibrate.py  a per-injection mass correction from the standards that
                  carry a formula, reusing mass_drift's measurements
  spectra_compare.py  the pinned spectra as data, drawn for paper: PNG,
                  SVG, and the report's picture
  infusion.py     is this sample a direct infusion (two flatness
                  figures, chromatograms only)
  infusion_report.py  one infused standard on two to four pages: the
                  checks summed, never a badge; and every open infusion
                  on one row
  standard_history.py  the own library's records of one compound as a
                  control chart over the days they were acquired
  infusion_batch.py  a folder of infusions reported without the Explorer,
                  one reader at a time (CLI --infusion-report)
  infusion_compare.py  two days of infusions, matched by compound and
                  conditions, the reference read from its project
  infusion_quant.py  an analyte against its standard in one spray
  standards.py    an infusion row written into the component table
  purity.py       the d0…dn envelope solved; refuses itself without
                  satellites
  api.py          the stable Python surface, imported lazily
  legacy.py       everything that knows the name before this one: the
                  OPENQUANT_* variables read as MILQ_*, the preferences
                  inherited once, and which home directory is used
  explain_any.py  one Explain: name, LIPID MAPS, formula and drawing
                  ranked alike, every route listed
  energy.py       which collision energy for identification, for
                  quantitation, for a record — three answers with reasons
  unexplained.py  a hypothesis for every strong peak nothing explained:
                  contaminant, satellite, or a sub-formula of the precursor
  margin.py       the chosen compound's share against its nearest
                  impostors, enumerated alike
  infusion_cover.py  the cover before a folder's per-compound pages
  spectrum_cache.py  raw averages of unchanged files, on disk beside the
                  project; ui/infusion_worker.py measures off the window
  audit.py        the trail of hand edits saved with the project
  labels.py       which peaks get a label: a budget per region of the
                  visible axis, shared by the pane and the print
  folder.py       what a folder holds and what would go wrong in it,
                  from the names alone
  xlsx.py         a dependency-free .xlsx writer; report.build_workbook
                  fills it
  skyline.py      the component table as a Skyline transition list
  batches.py      two batches of one method side by side, the reference
                  read from its project without opening raw files
  contour.py      the run as a retention time by m/z grid
  health.py       what the method will fail at, before it is run
  method_report.py  those checks, the formulas, the lock-mass candidates
                  and the schedule as one document that grades nothing
  suggest.py      retention times and windows the batch can supply
  components.py   the component table; method.py the processing method
  samples.py      SampleEntry, sample types and groups, name shortening
  matching.py     which channel serves a component
  chemistry.py    formulae, adducts, isotope patterns
  lipidmaps.py    LMSD index, name → precursor, mass → candidates
  structure.py    molfile parsing, bond cleavage enumeration
  explain.py      scores candidate structures against a measured spectrum
  precursor.py    confirms a precursor in the survey and product scans
  session.py      the open batch; project save and load (.oqproj)
  manual.py       the built-in manual: help/pages/*.md with [[wiki links]],
                  the search index, and the PDF (through report.print_document)
  help/pages/     the manual's pages, one Markdown file per page
  app.py          CLI: --selftest, --digest
  ui/             shell.py owns the window; new_standard_dialog.py the
                  bottle-to-component path; explorer / analytics /
                  method_workspace / samples_workspace are the four tabs;
                  help_window.py is Help ▸ Manual; settings.py the one
                  settings constructor;
                  help/pages/pt/ the Portuguese manual, same slugs
tools/bench.py    what the application costs here, scenario by scenario:
                  wall, CPU and peak RSS, `--profile <name>` (warm, after a
                  throwaway pass), `--json` and `--compare before after`. A
                  scenario whose data is not on this machine skips and says
                  so. Reaches into the main checkout for the acquisitions,
                  so it runs from a worktree.
packaging/        PyInstaller spec, DMG script, WiX source, wine/ shim; icons/ is the
                  suite's mark (the two co-eluting peaks), drawn by OpenDIAL's
                  tools/make_icon.py through packaging/make_icon.py and committed —
                  rerun it when the shared mark changes
```

### The reader protocol

Everything above `raw.py` asks a file for samples, a sample for channels, and
a channel for chromatograms and spectra. `MzmlChannel`, `MzmlSample` and
`MzmlFile` implement exactly the surface of `wiff.Channel`, `Sample` and
`WiffFile`, **signatures included** — checked by reflection, not by eye. No
code anywhere does `isinstance` on a reader or touches a reader's private
attributes. Keep it that way; a third format should need nothing but a new
module and an entry in `raw.FORMATS`.

---

## Verified facts

Run against five real acquisitions (81 channels each, ~24,000 spectra).

**Builds agree.** `--digest` prints a numeric fingerprint of what a build
reads. From source on macOS, from the CI disk image, and from the Windows
installer under CrossOver: byte-identical output, sha256 `ebdeebc2…`. 405
channel chromatograms, 25 spectra, 125 integrated peaks with areas to nine
decimals. All 405 channel hashes differ from one another, so those were five
different acquisitions rather than one read five times.

**Formats agree, except in one place.** Exporting a `.wiff` to mzML and
reading it back:

| | |
|---|---|
| spectra | identical, every channel |
| channel chromatograms | identical, every channel |
| the run's total ion chromatogram | identical, 577 points |
| chromatographic peak areas | identical |
| extracted ion chromatograms | **differ** |

The extraction is the exception and it reaches quantitation. SCIEX counts part
of a peak whose measured points fall just outside the mass window; this sums
the points inside. Median 0.58% of peak height, at most 12%, always lower.
End to end, quantifying one component from `.wiff` and from its mzML gives the
same retention time and the same peak width with the area differing by 0.54%.
**Quantify a series in one format.** Two attempts at reproducing the vendor's
edge rule are in the history and neither survived being tested on windows
other than the ones it was derived from — the second was a coin toss, better
on 41 channels and worse on 38.

**Windows 11 from source agrees with the suite, and found four things.**
Measured on a Ryzen 5 5500 with Python 3.12.10, PyQt6 6.11, pyqtgraph
0.14, pythonnet 3.1 on .NET Framework 4.8 (no .NET 8 installed; the SCIEX
assemblies load in 0.06 s warm, 13.7 s the first time). The suite: 1698
passed, 9 skipped, 0 errors, 3 min 04 s. There was no `.wiff` on the
machine, so the SCIEX read path is still measured only on macOS; the
numbers below are from a synthetic six-injection mzML batch shaped like
the real acquisition (81 channels, 19,440 spectra and 134 MB a file, 80
components), built by a script and never committed. What the machine
found: (1) `test_export_themes._pixels` returned a numpy view on a
`QImage` that had already gone — an access violation that took the whole
suite down, luck on macOS; (2) a `read_text()` with no encoding read the
source as cp1252; (3) Qt's offscreen platform has **no fonts on Windows**,
so every headless PDF was boxes (below); (4) seven teardown errors from
pyqtgraph ghost wrappers (below). The application itself: window up in
2.3 s, 1.8 s an mzML file, tab switches under the 250 ms measurement
floor, 555 MB private with six files open, 1.4 GB working set after
processing. Repository in OneDrive costs nothing measurable at import.

**ProteoWizard agrees.** msconvert reads what this writes, and its own mzML
written from that reads back here with identical spectra and chromatograms.
Converting a `.wiff` with msconvert itself fails under Wine (`getTWC()`, the
UV detector, is not implemented there) — untested on real Windows.

---

## Things that are subtle and will look like bugs

- **An mzML extraction reads bytes, not XML, and the file is a mapping.**
  `MzmlChannel.xic_range` decoded every scan of the channel through
  `ET.fromstring` on every call — 20.8 s of a 480-row synthetic batch were
  11 s of XML and `_params` walked 6.5 M tags — and nothing was kept, so
  the second component on a channel paid it again. Now `_binaries_of`
  finds each array's base64 span and encoding by `find` (a regex over the
  base64 body cost 2.2 s of a 5 s open, so no regex), the first time a
  scan is decoded (`MzmlFile._binaries_for`; at open it was 0.26 s of a
  1.5 s open on 19,440 spectra, for scans mostly never read); `_decode`
  goes slice → base64 → zlib → `frombuffer`, with the XML path kept for
  numpress and anything else it does not read; a channel's decoded scans
  are held flat (`_decoded`: masses, intensities, scan index) under
  `DECODED_BUDGET` (256 MB) **for the process** — one budget per file was
  the budget times the batch, 1.6 GB on six files — keyed by a per-file
  token, not `id()`, which a later file can be given again; an XIC is
  `np.bincount`, a BPC `np.maximum.at`. Measured: an XIC 32 ms → 11 ms
  cold, 0.1 ms held; 80 components × 6 injections 15.5 s → 7.0 s (4.8 s
  with the lookup at open time, which is where the 0.26 s a file went
  instead); the file is `mmap`ed rather than `read()` so a batch of many
  files is the system's cache and not the process — `close()` must close
  the map or Windows will not delete the file, and a test checks that.
  Open time is unchanged at 1.5 s a file, all of it the header parse
  (`ET` per spectrum, 1.4 s); a sidecar index would make a project reopen
  instant and is the next thing worth doing there.
- **Qt's offscreen platform finds no fonts on Windows.** `QFontDatabase`
  comes up with zero families, every glyph draws as a box, and a batch
  report written through `api.Batch.report` was 47 pages of black
  rectangles with no text to extract; the greyscale test of the printed
  comparison failed reading those boxes as ink at L 60. macOS and Linux
  read the desktop's font directories offscreen; Windows reads none.
  `api.offscreen_fonts()` sets `QT_QPA_FONTDIR` to the system's `Fonts`
  directory on Windows when the platform in force is offscreen and
  nothing has set it — called by `headless()`, `infusion_batch._app` and
  `tests/conftest.py` before the application is made. With it: 54
  families, the report 29 pages with text, the test at L 8 / 102. The
  GUI's own export is not affected: the windows platform has 149 families.
- **A widget left to the collector on Windows is torn down by Qt after its
  Python side is gone.** A `ChromatogramArea` built in a test with no
  parent and no `close()` sits in a reference cycle (lambdas capturing the
  views); `gc.collect()` in `_settle_qt` frees the wrappers in whatever
  order, and the C++ destruction of a `PlotItem` then asks its title
  `LabelItem` for `sizeHint`, `boundingRect` and a `resizeEvent` — on a
  wrapper sip has just re-made, whose `__init__` never ran. Seven
  teardown errors on Windows only, on pyqtgraph 0.13.7 and 0.14.0 alike,
  none under the windows platform in a real window rebuilding stacked
  panes. `conftest.py` guards the three methods for ghosts; the
  application is not touched.
- **A profile spectrum from mzML has fewer points than the same one from
  `.wiff`.** SCIEX strips the zeros when storing and puts them back when
  drawing. `processing.restore_profile_zeros` does the same for anything else,
  measuring the sampling interval from the file — the smallest quarter of the
  gaps are the ones inside peaks. Without it the baseline appears raised, and,
  worse, peak labels were centroids taken across the gaps: one read 184.8466
  for a peak at 185.0077.
- **mzML has no idea of an experiment.** Channels are inferred. Scan
  properties alone gave 69 channels where the acquisition has 81, because a
  method can have two entries agreeing on MS level, precursor, collision
  energy and mass range. `mzml.acquisition_cycles` recovers them from the
  order of acquisition: a scheduled method repeats a fixed cycle, and position
  in it is the entry. This file is a cycle of 44 run 339 times then one of 37
  run 238 times — 44 + 37 = 81 channels, 44·339 + 37·238 = 23,722 spectra.
  Data-dependent acquisition has no cycle; a cycle must repeat four times to
  be believed, and otherwise the properties are all there is.
- **The run's total ion chromatogram is summed by cycle, not by time.** The
  experiments of one cycle are measured one after another, so the union of
  their times is one point per spectrum — 23,722 where the instrument reports
  577.
- **`sWindows = False`.** `bootstrap` flips a private static field in
  Clearcore2 by reflection to force the managed structured-storage path.
  Without it nothing opens off Windows.
- **`OpenFileMode.ReadOnlyShared`.** Anything else takes an exclusive lock and
  a second window — or Analyst — cannot open the same file.
- **`processEvents()` does not drain deferred deletions.** `setCellWidget`
  marks the widget it replaces for `deleteLater`, and until a real event loop
  runs it the old one is still a visible child at the origin. Opening ten
  files rebuilds the samples table ten times and leaves ninety combo boxes
  piled on the first row's first cell — which is what the screenshots caught
  before they were regenerated with
  `sendPostedEvents(None, QEvent.Type.DeferredDelete)` first. The application
  is fine; anything that grabs or asserts on a widget tree is not, unless it
  flushes. `tests/conftest.py` does this after every test.
- **A control chart compares a standard against itself, and that is not
  enough on its own.** One standard's chart cannot tell an injection that
  failed from a compound that misbehaved: both are a point far from the
  centre. `qc.response_index` divides each internal standard by its own median
  and takes the median of those per injection, so all-standards-down-together
  is separable from one-standard-down-alone. On the batch it was written for,
  the standards taken separately scattered between 32% and 228% and looked
  hopeless; taken together the injections sat between 0.44 and 2.08 with four
  flagged (the original run of this measurement read ±18% with three
  exceptions; `tests/real/` asserts the current figure).
- **Flagging needs a floor and a ceiling, for opposite reasons.**
  `OUT_PERCENT` stops a batch that repeats itself well from flagging ordinary
  scatter. `ALWAYS_OUT_PERCENT` is its mirror: a batch whose own scatter is
  wide swallows a real failure, and an injection where every standard came
  back at a fifth of normal sat at 2.6 robust standard deviations. And when a
  third of a chart is out, `unusable` reports the chart rather than the
  injections — seventeen bad injections out of twenty-six is not a list of
  outliers, it is a standard that cannot normalise anything.
- **A proposal's confidence is measured, not asserted.** `suggest.suggest_times`
  runs the estimator on the components that already declare a retention time
  and reports, per peak-height band, how often it landed within one sampling
  interval — then attaches that band's figure to each proposal. On the real
  method it was 88% above ten thousand counts and 45% below a hundred, and
  because nothing offered was above ten thousand, **nothing was pre-ticked**.
  That is the intended outcome: the estimator did not prove itself at the
  heights that need it, and saying so is the point of calibrating at all.
- **A Gaussian fit through three points is exact, and that is a warning,
  not a result.** The fit was written because a trapezoid over a peak two
  or three points wide moves with where the scans landed: measured at 14.6 s
  sampling, 5% with the phase for a peak 14 s wide at half height, and the
  fit 0.00% wherever it could be made. Then it was run on the real batch
  and the one internal standard with a response — 52,000 counts — came back
  a third smaller than the trapezoid with r² = 1.000. The peak was one
  point; the neighbours were 44 and 98, the same size as the baseline blips
  further along the trace, and a curve through three points with three
  parameters passes through them whatever they are. So `fit_gaussian` needs
  three points at or above `MIN_SHAPE_FRACTION` of the apex — flanks, not
  feet — and `GaussianModel.exact` says when there were only three, so the
  dialog writes "exact through 3 points" where it would otherwise write an
  r² that means nothing. With that, on the batch: 400 of 2,638 rows fitted,
  2,238 fell back with the reason on the row, 2,169 of them because the
  peak was fewer than three points wide; where the fit was made its area
  was a median 0.977 of the trapezoid and no component moved by more than
  20%. The choice of algorithm does not move this batch's numbers; the
  sampling does, and the comparison is what says so with figures rather
  than with an opinion. `compare.py` runs every algorithm on the batch,
  each run calibrated on its own results, and reports per component the
  median |Δ| against the reference and the %CV over the rows meant to
  agree — the only figure that can call an algorithm better rather than
  different, since the files and the noise are the same and only the
  arithmetic changed.
- **The batch is one point per peak, and now says so.** `sampling.py`
  reads the point count every integrated peak carries (`ChromPeak.points`,
  `PeakResult.points`: points inside the boundaries at or above
  `MIN_SHAPE_FRACTION` of the height) and the cycle from the channel's own
  time axis. On the 26-injection batch: one scan every 14.6 s, a median of
  **one** point on the peak, 129 of 139 components typically under the three
  a fit needs, and 2,206 of 2,638 peaks (84%) with one point above half
  height — so their width cannot be measured, only bounded, and every cycle
  time the report recommends for that batch is an upper bound. The Batch QC
  tab *Sampling* and the report section of the same name carry it. Two
  things in the count that look wrong and are not: the valley walk's
  boundary is the first point at or below five per cent of the apex and
  becomes the baseline's end, so it never counts; and summation's
  boundaries are the window's ends, so a four-scan window leaves two.
- **A response floor is declared, not derived.** `Component.min_response`
  (CSV `min_response`, aliases in `_ALIASES`) is what an internal standard
  has to give before a ratio to it means anything. `ControlChart.floor`
  decides `quantifiable` outright when set and the S/N 10 rule stands only
  without one; `evaluate_acceptance` fails a row whose standard gave less
  than its floor in that injection; `health.check_method` warns of a serving
  standard with none. The batch cannot supply the number — measured, its
  precision did not track its response — which is why it is a method field.
- **A mass "drift" of −351 ppm is not a drift.** `mass_drift.py` reads
  every internal standard's precursor from the survey scan in every
  injection (`precursor.measure`, once per injection) and fits the change
  across the run against the batch's own median. On the 26-injection batch
  the first run called one standard drifting by −351 ppm with a spread of
  476 ppm between injections: a survey signal too weak, the ±0.25 Da window
  catching a different neighbour each time. So `MassTrend.same_ion` gates
  on `precursor.CONSENSUS_SPREAD_PPM` (25) — the limit the consensus already
  uses to say samples disagree — and a trend that fails it is not judged,
  says why, and stays out of the index. With that, the batch says what it
  can: `SM(d18:1/12:0)`, the one standard strong enough in a 50–700 survey,
  held to −4.8 ppm against its formula across the run with a 16 ppm spread; nine others cannot
  be measured; no index, since fewer than three standards qualify. The
  measurement is not saved with the project (a few seconds to repeat; three
  on that batch) and the report carries it only while it stands.
- **A floor is proposed, never derived.** `qc.suggest_floors` offers each
  standard half its median area over the spiked injections with the failed
  injections left out, to three figures, with its basis on the row; the
  dialog (`ui.floor_dialog`) pre-ticks only rows with `MIN_INJECTIONS`
  behind them. On the real batch that is 5,240 for the one usable standard
  and 2–25 counts for the others — which is what their medians are, and the
  dialog shows the median so nobody accepts a floor of 3 by mistake.
- **The schedule is where the sampling finding lands.** `schedule.py`
  takes every component with a retention time over its window, counts how
  many are acquired at once at the busiest moment (a sweep over window
  starts and ends, ends first at a tie), and turns a target cycle into the
  dwell each gets there — or, under the dwell floor, into the shortest cycle
  the busiest moment allows. On the real method: 59 transitions scheduled,
  82 left out for having no time, at most 24 at once at 4.70 min, and a
  cycle of 3 s still leaves 120 ms of dwell — against the 14.6 s the batch
  was acquired at with all 144 transitions running unscheduled the whole
  run. The starting cycle comes from `sampling.py`'s median width and is
  labelled an upper bound when the batch's peaks were narrower than a
  cycle, since it is going to be typed into an instrument. The CSV's
  columns are named to map onto the vendor's table; it is not claimed to
  import into Analyst, whose detection window is one method-wide setting.
- **`check_method` now says which precursors the survey cannot see.** On
  the real method 72 of 141 lie outside the 50–700 survey; the accurate
  mass, the annotation and the mass drift are not measurable for them. An
  acquisition with no survey at all is a skipped check, not 141 findings.
- **A library match has two scores because impurities exist.** `library.py`
  pairs each library peak, strongest first, to the nearest free measured
  peak within a ppm tolerance and reports the cosine over everything both
  spectra hold and the cosine over the library's peaks only; a high
  reverse with a low score is the compound with company. Records with no
  precursor are scored when a precursor filter is on and say so with an
  empty Δ ppm — the filter did not apply, which is not the same as passing
  it. Run against MassBank's 139,006 records (5 s to read, 1.3 GB held):
  three rules came out of it. Two matched peaks minimum, because a
  spectrum that was mostly 184.07 scored 83 against a laxative on that one
  peak. Records without a precursor left out of a filtered search unless
  asked, because 24,000 of them dominated every search. And the precursor
  tolerance at least the written value's precision, since the channel says
  `647.5`. With those, the batch's product spectra named the C16 and C18
  sphingomyelins and the C16 and C24:1 ceramides the library holds, at
  reverse scores of 79–96, in milliseconds; an unfiltered search walks a
  bin index of the peaks and takes 2–7 s.
- **A reference batch is read, not opened.** `batches.read_project` builds
  a snapshot from the JSON alone, so a batch whose acquisitions moved to
  another disk still compares. Reusing it on the real batch reproduced the
  corrected-method gain of 2026-09-07 as a comparison rather than a script.
- **Unplaced deuterium is enumerated by count, not by position.**
  `explain.with_labels` offers every predicted ion carrying 0 to n labels
  (`PredictedIon.labels`, written `+kD`), never more than the piece has
  hydrogens; the spectrum then says how many a fragment kept. A drawing
  that places its labels — PubChem's cholic acid-d4 carries an `M  ISO`
  block, and `structure._isotopes` reads it — needs n = 0 and gets the same
  intact mass (411.3054 checked both ways). `explain_structure` takes a
  molfile of one's own through the same scoring as a database record;
  `explain_formula` takes a formula alone and offers the precursor and up
  to three neutral losses, each only where the formula has the atoms, and
  says that a formula has no bonds to cut. Loss ions are written as what is
  left and how it got there: `C24H38O4 -H2O`.
- **A translated page is the same page, not another one.** `help/pages/pt/<slug>.md`
  carries the same file name as its English original, because the file name
  is the page's identity: `[[link]]`s keep the English slugs in every
  language and the renderer shows the target's title in the language being
  read. A slug with no translation is read from the English file and shown
  with a note rather than left out; the note lives in `Page.html` and not
  in `Page.text`, so search and the six-hundred-character rule measure the
  page and not the furniture. `INDEX` stays English and is translated
  through `SECTION_TITLES`; `report.print_document` takes a `strings` dict
  for the printed manual's furniture. Only the manual is translated — the
  application's menus and dialogs stay in English, which is what the pages
  describe — and every new English page needs its Portuguese links added,
  or `tests/test_manual.py` reports it as an island in the Portuguese manual.
- **A folder's problems are in its names, and `folder.py` reads only names.**
  `check_files` touches the disk through `listdir`, `exists` and `access`
  alone — everything worth warning about before an open is visible without
  decoding anything. Which stray `.scan` belongs to which `.wiff` cannot be
  known from outside the files, so `guess_owner` takes the longest run of
  characters shared at the front and the back, and the pairing is called a
  guess everywhere it appears; `apply_rename` refuses to write over a file
  that is there. Found by rendering the dialog rather than reading it: a
  `QTableWidgetItem` background is not drawn under the application's
  stylesheet, and a table of sentences needs `ElideNone` with
  `resizeRowsToContents`.
- **A record of one's own is a floor, a ceiling and a provenance.**
  `library.entry_from_spectrum` takes centroids only — a profile spectrum
  describes the instrument's peak shape, not the compound — drops peaks
  under `OWN_MIN_RELATIVE` (1%) and keeps at most `OWN_MAX_PEAKS` = 200.
  `write_msp` appends, giving a file that does not end in a blank line the
  separator it lacks. The Explorer's `spectrum_source` hook grew a fourth
  element (file, sample, channel, polarity, collision energy), read by
  length so the three-value form still works. Measured on the 26-injection
  batch: 14 records from injection 01 read back within 5·10⁻⁶ Da; injection
  02 put the right record first 14 of 14 times at reverse 45–96, every
  other record at most 42. The bile-acid infusions were on an unmounted
  drive; that measurement is still owed.
- **An infusion is flat twice, after the first second, against its
  99th-percentile scan.** `infusion.is_infusion` needs the fraction of the
  sample's TIC at or above half its reference *and* the same on the
  strongest product-ion channel both at `FLAT_FRACTION` (0.75), from
  chromatograms only. The infusion side was reasoned before it was
  measured: three of nine ZenoTOF bile-acid infusions came back at
  0.0021–0.0063 — below every one of 39 chromatographic runs — because of
  one spray transient at 0.0084 min, 2.8–4.4× the median; half of a spike
  is above everything else in a flat run. Two fixes, both measured:
  `REFERENCE_PERCENTILE` (99) instead of the largest scan, and
  `SETTLING_SECONDS` (1 s) dropped off the front, since truncating all 48
  acquisitions to 20–100 scans showed the percentile interpolating back
  towards the transient out to 80 scans. With both: infusions 1.0000 at
  every truncation from 20 to 250 scans and 0.9936 whole, chromatographic
  never past 0.1148, 48 of 48. Settling alone fails (DCA-d4's bursts at
  1.08 and 1.10 min give 0.0043) and a length-tied top-k median survives
  one spike but not three. The other half nothing fixes: a gradient cut
  off before anything elutes is flat too (`260904_EICs_Isabela_S001` is
  empty until 8.9 min and its first 100 scans read 1.0000 / 0.9388), so
  `MIN_JUDGED_SCANS` (120, between the 35 past which nothing else
  chromatographic reads flat and the shortest real infusion at 146) gates
  the *flat* answer only — a run showing structure is chromatographic at
  any length — and a shorter flat run is "too short to tell", not an
  infusion. The own library on the same files: records from the CID
  infusions of CA-d4, DCA-d4 and TDCA-d4 searched by the same compounds
  under EAD 22 eV put their own record first at 29.2, 33.3 and 61.5
  against a best wrong record of 14.1; a record does not travel between
  activations (CA-d4 at 12 eV scores 6.4 against the CID record).
- **A correction the size of its own uncertainty is still worth having, and
  still has to say so.** `recalibrate.py` fits a per-injection offset from
  the standards' measured precursors against their formula masses, reusing
  `mass_drift`'s measurements; a trend failing `same_ion` is not a lock
  mass, and the *written* precursor is refused as a reference (`647.5` is
  good to 800 ppm). On the 26-injection batch as it ships there is no lock
  mass — no standard carries a formula — and every injection reads "left as
  measured". Given the one formula that can be looked up: one lock mass,
  offset only, in 25 of 26 injections, median +4.8 ppm with a 16.1 ppm
  spread; the other components' errors within 25 ppm went from a median
  −8.7 to −3.3 ppm, smaller on 43 of 66. A linear term needs **four** lock
  masses: leave-one-out on three fits a line through two points, which is
  exact and predicts nothing, and a synthetic outlier pulled the offset
  from −5.2 to −49 ppm before the floor was raised. Where it reaches
  quantitation it moves the window, never the reader's arithmetic — and a
  5 ppm shift still moved 1,769 of 2,593 areas by a median 1.3% over
  ±20 ppm windows. Hence `session.recalibrate`, off by default, saved with
  the project, with a test that the switch off is identical row by row.
- **A picture in the report is drawn for paper, not grabbed off the screen.**
  `spectra_compare.py` holds the compared spectra as data and renders them
  with a QPainter of its own at `PRINT_SCALE = 2` — a genuine re-render
  (the title's ink goes from 9 rows to 19), chosen over pyqtgraph's
  ImageExporter, which takes its aspect from the widget and took 70 ms
  against 14. A trace colour lightened for a dark window is darkened until
  it clears 3:1 on white; a profile trace is thinned to the lowest and
  highest point per pixel column (an SVG of two TOF spectra went from
  3.8 MB to 94 KB and a one-point spike survives); `QTextDocument` draws an
  `<img>` from a path, a `file://` URL, a resource and a `data:` URI alike,
  and the data URI keeps an exported HTML report one file. There is no
  snapshot button: pinning starts the comparison, the live spectrum or a
  switch refreshes it, unpinning drops it, so the report prints what the
  Explorer shows.
- **An `.xlsx` is a zip of XML and the failure is silent.** `xlsx.py` writes
  one directly rather than take a dependency the installers would carry:
  inline strings so there is no shared-strings table to keep in step,
  numbers as numbers, `None` as an *absent* cell — not a zero, which is a
  measurement — and dates as text. Three things Excel refuses the whole
  workbook over without a word: a sheet name past 31 characters or holding
  `[]:*?/\`, a `fills` list whose first two entries are not `none` and
  `gray125`, and a duplicate sheet name — all fixed in `sheet_name` and
  `_styles`. An omitted cell means position in the row does not identify a
  column; the `r` reference does, which is what `tests/test_xlsx.py`'s
  reader resolves. Verified by reading back in the suite, by `openpyxl` out
  of repo, by macOS Quick Look, and by Microsoft Excel for Mac itself
  (driven by AppleScript: the batch's five sheets, the header, a row and a
  numeric cell read back); LibreOffice untried, and the `export` page says so — as it says no Skyline transition list has
  been imported into Skyline, only that its headers were read off the
  reader that consumes them in the ProteoWizard source.
- **The Dock icon is whoever spoke last.** *1.0.0 ships no layered icon:
  the document drew OpenQuant's two co-eluting peaks and MIL-Q's mark has
  not been redrawn for Icon Composer, so `make_liquid_icon.sh` says so and
  exits and the `.icns` from the identity kit is what the Dock shows. The
  finding below is why `app.py` still sets no window icon inside the
  bundle, and it is what to re-read when the document comes back.* The
  bundle carried a layered Liquid Glass icon (`packaging/icons/MIL-Q.icon`,
  compiled by Xcode 26's `actool` on the runner into `Assets.car`,
  `CFBundleIconName`), and
  `assetutil --info` and `NSWorkspace.icon(forFile:)` both showed it drawn
  in glass on macOS 26 — while the Dock showed the blue square for as long
  as the application ran. Qt hands `setWindowIcon` to the Dock as the
  application icon, and the flat `icon.png` covered the layered one. So
  `app.py` sets no window icon inside the macOS bundle; the window icon
  stays for source runs, Windows and Linux. Restarting the Dock, the icon
  services agent, re-registering with Launch Services and stamping the
  SDK were all tried first and changed nothing, because none of them was
  the cause.
- **A `.wiff2` is not an unread format, it is an empty one.** Measured on
  nine ZenoTOF 7600 trios: `CreateBatch` raises `Invalid OLE structured
  storage file` on all nine and Clearcore2's own `CheckDataFileIntegrity`
  calls them `NotWiffFile` — with the companions beside them, with each
  removed in turn, and renamed `.wiff` — so it is the container (a
  password-protected SQLite database) and not the extension.
  `PersistenceFactory.GetWiff2Schema()` returns seven tables (`header`,
  `sample`, `method`, `device_method`, `device_descriptor`,
  `device_identifier`, `method_parameters_info`) with no column for a
  spectrum, peak, intensity or chromatogram; `header` holds `wiff_hash`,
  `scan_hash`, `scan_size`. The acquisition is in the `.wiff`, which reads
  identically with the `.wiff2` deleted. So `raw.FORMATS` has no `.wiff2`.
  Dead ends if revisited: the Wiff2 metadata layer needs
  `System.Data.SQLite 1.0.98.0` and the SCIEX OS stack needs
  `OFX.Core.Contracts`, neither redistributed; and loading every sciex DLL
  breaks the working `.wiff` path with a `MarshalDirectiveException` —
  `bootstrap`'s three-assembly set is deliberate.
- **A trail of hand edits is only worth having if it says what it is not.**
  `audit.py` records one line per user action — when, what, target,
  before → after — appended where the change is made, never edited or
  deleted, saved under `audit` in the project (format 4; an older project
  opens with an empty trail). The method table is committed whole on every
  edit, so `component_changes` pairs by position when the lengths agree,
  which makes a rename read as a name changed rather than a removal plus
  an addition; a spin box emits per digit, so the method defaults record on
  `editingFinished`. It is **not** a regulated audit trail and the panel,
  the report section and `audit-trail.md` say so: no accounts, no
  signatures, no tamper evidence — it records what was done and when,
  never who.
- **Peak labels are budgeted by region, not just thinned by collision.**
  On a real TOF MS scan 268 maxima sit above 2% of the base peak, 105 of
  them in the first eighth of the axis, and the twelve tallest inside a
  stretch 118 Da wide — 50 px apart with 55 px of text — so eleven collided
  and the spectrum was drawn with one label. `labels.choose` cuts the
  visible axis into `LABEL_REGIONS` (8) windows with `LABEL_BUDGET` (3)
  labels each, claimed as a round of every region's tallest before any
  region asks for a second; the collision rule then runs unchanged.
  Measured, offered/drawn: survey 12/1 → 18/6, zoomed 12/4 → 23/7, a
  product-ion scan 12/6 → 20/7, the printed comparison 12/12 → 23/20.
  Past eight regions the extra label names the first point of the scan;
  past three per region the fourth peak does not fit. The pane chooses
  again on every range change over a pool the peak finder fills once, and
  the floor is 2% of the tallest peak *in view*.
- **A name says what a compound is made of; the precursor says whether you
  read it right.** `chemistry.formula_from_name` turns lipid shorthand into
  a formula (a class table plus the chains) and `components.fill_formulas`
  writes it into **empty** Formula cells only, never over a typed one and
  never over a precursor. Each derivation is checked against the written
  precursor to a whole unit in its last decimal (methods truncate: `286.2`
  for 286.2741) and a disagreement is reported rather than filled — a
  wrong formula is a wrong lock mass. On the real method: 125 of 141
  components and 10 of 11 standards, and 13 of the 16 refusals were the written
  precursor typed to fewer places (`dHCer(d18:0/12:0)` 15 ppm out), three
  a whole 1, 2 or 100 Da out; `check_method` reports both cases. The lock
  masses did not multiply: of 60 formula-bearing components inside the
  50–700 survey exactly one measures the same ion across the run, so the
  fit is still one lock mass at +4.8 ppm — the survey measurement is the
  binding constraint, not the formula. What the formulas bought is the
  check: 51 analytes with a theoretical mass instead of 15, and over their
  197 measurements within 25 ppm the correction moves the median error
  from −7.0 to −1.4 ppm. `lock_masses_from_drift` has no gate on a lock
  mass's error against its own formula yet; `C17:0_Ceramide` sat 237 ppm
  off and was one injection short of qualifying — hence the gate below.
- **A lock mass has to agree with the compound, not just with itself.**
  `same_ion` asks the injections whether they agree with each other; a
  standard whose ±0.25 Da window holds the same *wrong* ion every time
  passes it. `recalibrate.MAX_LOCK_ERROR_PPM` (50) is the other half: past
  it in most injections is `lock_mass_refusal` — "measures 237 ppm from its
  formula: not the ion the formula names" — on the verdict, the panel and
  the report. Fifty was measured: over 1,439 survey measurements of the
  batch's 60 formula-bearing in-survey components, |measured − formula| is
  bimodal, 19.5% under 20 ppm, 53.5% past 200, trough at 30–50, so 50 is
  the trough's far edge and twice `CONSENSUS_SPREAD_PPM`, with ~5× margin
  either side. On the batch it names five standards and changes no number
  (all five had already failed `same_ion` or the count); the near miss
  says why it exists — `Sphingosine C14:0` holds to 52 ppm across 25
  injections at 156 ppm from its formula, one steady ion that is not the
  compound. `check_method` cannot make this check: it never reads a survey.
- **A printed label goes beside a peak or nowhere.** The print places what
  `labels.choose` picked with a rule of its own: above the apex, never
  inside the peak, never over another label and never over any trace's
  ink — the topmost and bottommost point each trace reaches in every
  column of the drawing. A taken slot lifts the label one text height with
  a leader to its apex; past `MAX_LIFT` (6) it is dropped and
  `LabelLayout.dropped` counts it; `HEADROOM_LIFTS` (3) is taken out of
  the plot before the traces are drawn. Measured by counting trace-coloured
  pixels under every label: two CA-d4 product-ion averages 28 drawn with
  10 on the ink → 30 drawn, 13 lifted, 1 dropped, none on the ink; two
  surveys 21 with 13 on the ink → 17, 8 lifted, 8 dropped (the isotopes of
  a base peak that reaches the top), none on the ink.
- **A written precursor can be repaired from its formula, and on this batch
  that changes no number.** `components.precursor_repairs` lists every
  component whose formula contradicts its precursor; *Repair precursors…*
  writes both fields for the ticked rows, one audit entry each. Ticked
  under `WHOLE_DALTON` (0.5), unticked past it: the real method's 16
  refusals are either under 0.27 Da or a whole 1, 2 or 100 Da, nothing
  between. Applying the 13 sub-dalton ones and reprocessing left 338 of
  338 rows identical: every row carries a fragment, so `mass_window()` is
  the fragment's, and every repaired mass stayed inside
  `matching.PRECURSOR_MATCH_DA`, so no channel changed. A precursor's first
  job is picking the channel, not building the window — which is why the
  three whole-dalton repairs are the destructive ones: two left every
  product-ion channel for the survey and one landed on its isomer's
  channel; the instrument acquired the masses as written, so there the
  name is the mistake. What the 13 bought was formulas: 125 → 138 of 141,
  11 of 11 standards with a lock-mass candidate.
- **A label floor is a fraction of the view, and the pool has to follow it.**
  A peak needs `LABEL_MIN_RELATIVE` (2%) of the tallest peak *in view* to
  be named, and `SpectrumView`'s `LabelThresholdHandle` — PeakView's
  triangle, drawn in the space the left axis reserves once `tickTextOffset`
  is raised by twelve pixels — lets that be dragged; stored as a fraction,
  so it survives a zoom, a Normalise and the next spectrum. The trap:
  `POOL_MIN_RELATIVE` was 0.2% of the base peak of the *whole spectrum*
  while the floor is measured against the view, so zoomed into a quiet
  stretch dragging the floor down changed nothing (57 labels at 2% and at
  0.5% over eighteen 100 Da windows of a real survey); `_pool_floor` holds
  the pool at a tenth of the floor, and those windows give 57, 95, 95.
  Filling the pool walks every point (255,000 on an infusion average, half
  a second), so a drag reads the pool as it stands and refills on release.
  Measured: the CA-d4 precursor itself, m/z 430.3197 at 1.49% of the base
  peak, is unnamed at 2% and named at 0.5%; on a full-range survey the
  floor changes nothing, because the region budget runs out first.
  `SpectrumComparison.label_floor` carries it to the print.
- **A report of one infused standard sums the checks and refuses the
  badge.** `infusion_report.py` builds a two-to-four-page document from
  what the Explorer holds — the averaged spectrum at the pane's label floor
  with its top 25 peaks, the LIPID MAPS explanation with its *unexplained*
  peaks beside it, the library hit with the record's fields as written,
  other infusions of the same name prefix head to tail — and a verdict of
  one sentence per check, never a pass or fail. Three things came out of
  measuring it on the nine ZenoTOF bile-acid infusions, which are
  **positive mode** (CA-d4's 430.35 is `[M+NH4]+` of C24H36D4O5; 359.2870
  is `[M+H−3H2O]+`) and **have no survey scan at all**, so
  `precursor.measure` says nothing about them: the precursor is read from
  the averaged product-ion spectrum through `precursor.in_spectrum`, which
  now returns the height beside the mass, because without a floor the
  ±0.25 Da window at 45 eV holds 84 counts of nothing and centroids 70 ppm
  out. A library record is centroids — fed to `spectra_compare` as a
  profile trace it drew as one spike labelled 359.6428 — so the average is
  centroided for that figure. And Qt lays a block holding a picture out as
  though it fitted and draws it on the next page, so `_orphan_headings`
  also flags a following block carrying `OBJECT_CHARACTER` that straddles
  a boundary, and `_sub` puts the break class on an h3, which `_heading`
  never did. Measured on CA-d4: 7 of 97 predicted ions at 22 eV against 2
  of 97 at 45 eV, 29/39 against the CID record with the energy difference
  stated, 2→4 pages, 0.3–1.0 s each.
- **A library record states its precursor twice, and only one of them is a
  mass.** `PrecursorMZ` is what its author typed; `Formula` +
  `Precursor_type` is what the ion weighs. `LibraryEntry.exact_precursor`
  computes the second (`chemistry.adduct_from_name`, `mass_from_formula`);
  `search` admits a record on **either** mass, measures Δ ppm against the
  formula's where there is one (`LibraryHit.delta_basis`), and gates on the
  sign the adduct declares, keeping records that declare none.
  `precursor_disagrees` flags a record whose two numbers differ by more
  than a whole unit in the last written decimal and never by less than
  `DISAGREE_FLOOR_PPM` (25): over 449,525 records of a five-decimal lipid
  MSP, 96.8% sit inside 0.5 ppm of their formula and 309 inside 2, then
  nothing until one record 116,411 ppm out — half a unit calls 30% of that
  library broken, 25 ppm calls one and it is. On 143 real product-ion
  channels 2,414 of 2,415 hits took Δ from the formula, and the gate
  refused every record to a negative query while removing nothing from a
  positive one. On the bile-acid infusions no score or rank moved and
  DCA-d4's flattering +0.0 ppm became −28.0: record and query carried the
  same mistyped `414.34`, and its own scan measures 414.3525. `format_msp`
  writes `430.35`, not `430.3500`.
- **A fragment says how many labels it kept; it does not say which.**
  `explain.infer_labels` turns every matched ion into a constraint — a
  piece that kept *k* of *n* contains *k* — and enumerates placements over
  the positions no ion separates. Three gates came out of measuring it on
  a real CA-d4 infusion against PubChem's own 2,2,4,4-d4 drawing: a peak
  counts only when nothing else in its window carries a different count (a
  deuterium is 1.55 mDa from the hydrogen it replaced, so 48 of 53 matched
  ions are undecided at 20 ppm, 4 of 26 at 5, none of 19 at 3 — the
  own-structure path defaults to 5 ppm); a dehydration may take a label
  (359.2870 and 358.2808 are 1.0062 apart, D−H and not H); and a hydrogen
  lost on cleavage may be one too (assuming otherwise dropped the true
  placement from 78% of the evidence to 43%). **It still does not recover
  the answer**: 580 of 8,391 placements tie at 93% under CID and 2,625 at
  100% under EAD, no position is in all of them, and the vendor's own is
  beaten by 79% and 74% of the possibilities — a tie is the spectrum
  bounding the labels, not placing them. Handed the placed drawing both
  spectra agree at 100%. `structure.suppress_hydrogens` folds a molfile's
  explicit hydrogens into their atoms; that alone took what the drawing
  explains from 21% to 59%.
- **When the mass and the name disagree by a whole dalton, the name is the
  thing to fix.** `chemistry.names_for_mass` reads the shorthand backwards:
  the written name's own class (chains within ±4 carbons and ±3 double
  bonds, a hydroxyl on or off, the base's `d`/`t`/`m`, at most two chains
  changed), ranked by how little of the name each changes, then LIPID MAPS
  as a second list marked as another class; the repair dialog's *Rename
  to* column writes the name and formula, keeps every number, and records
  `Name renamed`. A whole-dalton row's decimals belong to the wrong
  compound, so the search matches the nominal mass (`NAME_MASS_TOLERANCE`
  0.5 Da): `LacCER(d18:1/18:1(9Z))` written 886.6407 against 888.6407 gets
  `LacCER(d18:1/18:2)` at −17.7 ppm, 204 names over four formulas, because
  a mass fixes the composition and never the chain split. The other two
  rows are answered by silence: a chain is 14 Da, a double bond 2, a
  hydroxyl 16, so nothing reaches a mass one *odd* dalton away —
  `LacCER(d18:0/18:1)` is a typed digit — and `C18:1 Cer` at 464.4 is out
  by a hundred. Renaming and reprocessing left 78 of 78 rows identical.
  The mass is asked about the totals before the chains are split: a
  triacylglycerol took 13 s the naive way, 0.06 s this way.
- **A summary of many infusions is a different claim from a report of one,
  and its cells have to say why they are empty.** `infusion_report.summarise`
  builds one row per open infusion, grouped by `compound_of`; the row *is*
  an `InfusionReport`, so the Infusions tab and the printed pages cannot
  disagree, plus the mutual cosines within a compound and a reason wherever
  a measurement could not be made. `report_for(others=…)` re-averages each
  other infusion once per report, so `cross_compare` scores from the
  averages already held. Measured on the nine ZenoTOF bile-acid infusions
  with the three CID runs as an own library: 14.1 s for nine; the document
  of all nine 61 pages in 18 s; 4 of 9 precursors within 25 ppm, all the
  softer activations (the CID runs left 33 and 84 counts and the cell says
  so); own records at 6, 29, 33 and 61 against the same vial under another
  activation. And it found what nobody had looked for: the two files named
  `CA-d4_…TESTEARTIGO` target **839.56**, not 430.35 — no record within
  ±0.02 Da, 0 of 31 ions, 73 against each other and 5–10 against the real
  CA-d4 files. `session.infusion_summary` is derived and not saved.
- **An own-library record is a verification, and reading the file back is
  a control chart.** `standard_history.py` orders every record of one
  compound by acquisition date, cuts them into series by collision energy
  and activation, and charts three metrics against the first record of the
  series — the cosine, the base peak's ppm from it, its absolute height —
  through `qc.chart_from_values`, `control_chart` split so the batch and
  the history cannot disagree about "out"; `qc.Limits` says whether a
  deviation is a share of the centre or a difference from it. Two fields
  are now written that nothing recovers later: `Acquired` (the comment
  only ever said the day the record was typed) and `Base_peak_intensity`.
  `MIN_RECORDS` is three, and below it the verdict is *too few to chart*.
  Measured on the nine bile-acid infusions: 9 records, 7 series, one day;
  CA-d4 against itself scores 67 (EAD 12 vs 22), 29 (EAD 22 vs CID 45), 6
  (EAD 12 vs CID 45), which is why series never cross an energy; the
  `_TESTEARTIGO` acquisitions, expected repeats, isolate 839.56 and the
  history said so with scores of 8 and 0 and *not the same ion* past
  `SAME_PEAK_PPM` (50). Six infusions cut into thirds give the floor: score
  98.7–100, base peak within 0.4 ppm, height within 4.5%.
- **A pinned spectrum is saved as its recipe, never as its points.**
  `spectra_compare.SpectrumRecipe` — sample key, channel index, scan or RT
  range, whole-run flag, the background window where one was subtracted —
  goes into the project under `view` (format 5, with the label floor, the
  pane's Normalise/Mirror/Centroid and the live spectrum's own recipe); an
  older project opens with defaults. Measured on two CA-d4 infusions pinned
  as whole-run averages: 544,216 points, 20 MB as JSON arrays against a
  3,016-byte project, reopened byte-identical in 5.9 s (the files take
  3.2 s to open), the comparison standing and the report's *Compared
  spectra* printing at once. Restoring waits for `sigViewRestored`, emitted
  by `load_project` after the samples are open; the pins are rebuilt before
  the live spectrum, because `_with_pins` reads the list as it stands; a
  pin is re-read with its own background window and its own injection's
  mass correction. A pin whose file is gone stays listed as "not
  available: file missing". Saving the view is part of saving the project
  (`Session.view_source`): no separate command, no audit entry.
- **An adduct is not an offset, it is what happens to the charge.** A
  channel written `430.35` is `[M+NH4]+` of cholic acid-d4, and scoring its
  drawing as `[M+H]+` puts every predicted fragment 17 Da from the
  spectrum, while adding 18.03 to everything predicts `[M+NH4−H2O]+`,
  which is not a species. `chemistry.Adduct.behaviour`: a **proton**
  adduct keeps its charge on the piece; a **labile** one (NH4⁺, and
  HCOO⁻/CH₃COO⁻/Cl⁻ in negative mode) leaves as a neutral and hands over a
  proton, so the ladder hangs off `[M+H]+`; a **metal** one is a
  coordinate bond, so both `[piece+Na]+` and `[piece+H]+` are offered and
  each ion says which. `identify_adduct` reads the adduct off the written
  precursor within `ADDUCT_MATCH_DA` (0.05 — the worst real gap is
  0.0117 Da, DCA-d4's `414.34` for 414.3516; the same compound is `430.35`
  in one file and `430.34` in another), gated on the channel's polarity,
  and where nothing fits it explains nothing and names the closest misses.
  Measured on the bile-acid infusions at 10 ppm: a formula alone on CA-d4
  EAD 22 eV went from 1 of 31 ions and 21.7% to 8 of 56 and 63.6%, the
  whole ladder with a −1D rung beside each; a drawing gains one ion, the
  intact ammonium, worth 60.3% → 82.0% at 22 eV and 9.7% → 92.0% at 12 eV,
  and nothing under CID where the precursor is gone. Those spectra sit
  +4–7 ppm high on their own axis, so the panel's 5 ppm default gives 5 of
  56 and the matched precursor's ppm is printed. `explain.resolve_name`
  takes a name through a bile-acid standards table (bottle abbreviations,
  `-d4` = four unplaced labels), then LIPID MAPS, then the shorthand.
- **A folder of infusions is reported one reader at a time, and every skip
  says why.** `infusion_batch.run` checks the folder with
  `folder.check_files`, opens each file into a `Session` of its own, calls
  `infusion_report.summarise` as the Infusions tab does, and closes the
  reader before the next — thirty infusions never mean thirty mapped
  `.wiff.scan`. A `.wiff` without its companion is skipped unopened; a run
  that is not an infusion is skipped with `verdict_for`'s figures.
  `_cross_score` puts back the one thing one file per session cannot know:
  each infusion scored against the others of its compound. On the nine
  bile-acid infusions the CLI gives 9 read, 0 skipped, one 48-page PDF in
  32 s at 890 MB, and the tab's summary line to the digit. Two silent
  failures found doing it: a `QApplication` nothing holds is collected the
  moment its factory returns (`_APP` keeps it), and `QPdfWriter` reports
  nothing when it cannot open its file, so every document is checked after
  it is written. Timings on this machine vary 3× under a load of twenty
  agents; pages, memory and rows repeat exactly.
- **A method report is the checks that exist, not a new one, and it refuses
  to grade.** `method_report.py` runs `check_method`, `fill_formulas`,
  `precursor_repairs`, `matching` and `build_schedule` over one method and
  prints the answers through `report.print_document`: the component table
  with every flagged row marked, the findings by severity, the formulas
  carried / derivable / refused with both masses, the standards that
  *could* be lock masses, and, with a sample open, which channel serves
  what and the schedule the method implies. The closing section is a
  paragraph of counts whose last sentence says the counts are not a
  verdict; `fill_formulas` is given `replace()` copies so nothing is
  written. Measured on the 141-component method against injection 01:
  0.29 s to read, 15 pages in 5.3 s, 3 serious findings and 4 warnings
  touching all 141 rows, 125 formulas derivable with 16 refused, no
  lock-mass candidate, 72 precursors outside the 50–700 survey, 59
  transitions scheduled / 82 left out / 24 at once at 4.70 min. The cycle
  it prints is 12.4 s (from `suggested_cycle`, the batch's measured width),
  not the 3 s of the schedule note; at 3 s the same 24 get 120 ms. Two
  things a render found: a provenance column carrying the derived formula
  wrapped to three lines and took the table from six pages to eight; and a
  closing heading whose paragraph has no *line* that fits ends page 14
  alone — `_orphan_headings` needs the first line's rule, in the printer.
- **An adduct deduced from a written precursor is not the same claim as one
  measured.** A product-ion scan cannot check which ion its precursor is —
  Q1 passed one mass and threw the isotopes away with it — so
  `chemistry.adduct_evidence` asks the survey of the same acquisition over
  the same scans: the nearest centroid within ±0.05 Da held to
  `CONSENSUS_SPREAD_PPM` and `MIN_INTENSITY`, and the M/M+1/M+2 of the
  **ion's own composition** (`[M+NH4]+` carries a nitrogen the molecule has
  not got, `[M+Cl]-` an M+2 of 32%). `identify_adduct(survey=…)` says
  "confirmed by the survey: 647.5112, −1.6 ppm, isotopes agree" or that it
  was chosen from the written mass alone. Measured on the sphingolipid
  survey: the mass alone admits an ion that is not there (the C16
  ceramide's `[M+NH4]+` sits 21.5 ppm out with 170 counts and satellites
  of 1.00/1.00, flat noise, ranked last by the pattern); and a satellite is
  where a lipid keeps its own family (the ceramide's true `[M+H]+` has an
  M+2 four times too big because the co-eluting dihydroceramide is 17 ppm
  from it), so `pattern_agreement` weights each satellite separately
  (0.77 against `match_isotope_pattern`'s 0.43); `PATTERN_AGREES` (0.50)
  sits in the trough between 0.33 and 0.55. The survey reports every
  adduct it shows (`[M+H]+` 100%, `[M+Na]+` 13% for both compounds) and may
  overrule a written precursor that fits nothing, but only inside
  `PRECURSOR_MATCH_DA`: `538.6` for 538.5194 is `[M+H]+` with a survey and
  refused without one. The bile-acid infusions have no survey; nothing
  changes there and the report says so.
- **A file name is a claim and the method is a measurement, and they can
  differ.** A manual acquisition names its sample `sample` and its method
  `Untitled 1.msm`; by reflection `TargetedCompoundInfo` is None and the
  compound parameters hold only DP/CE/DPS/CES — nothing in the file names a
  compound, so `compound_of` is a proposal. `infusion_report.
  what_the_method_isolates` checks it against every adduct of the name's
  formula, the component table and the own library: an `Isolated` column,
  a Named/Isolated header pair, a warning once per file after open. Two
  guards: `lipidmaps.find_by_name` is a substring search (`PC` answers
  *PCTR3*, `Cer` *Cerasin*), so `resolution_is_exact` requires the record's
  own name; and grouping stays on the proposal. The two `_TESTEARTIGO`
  files isolate 839.56: of 72 bile-acid adducts, monomer and dimer, only
  `[2M+Na]+` of unlabelled cholic acid fits (−5.2 ppm), and the files
  refuse it — 9 and 17 counts in the window, 7,101 and 5,281 centroids for
  a TIC of 18,537 and 40,453 against 234 and 156,716 for the real CA-d4.
  They are empty acquisitions of a mass typed for something else.
- **A shortened sample name is not an identity.** `samples.shorten_names`
  strips the prefix every open sample shares, so the same file is
  `EAD_22CE_mix1` beside two others and `22CE_mix1` beside one, and a
  comparison of two days matched nothing. `infusion_compare` reads the
  compound, activation and energy from the file name on disk, matches rows
  by compound *and* conditions, marks *moved* on `standard_history`'s two
  rules only (base peak past `SAME_PEAK_PPM`, height past `qc.OUT_PERCENT`)
  and never on the cosine (two days are two points). The summary and each
  row's top-200 centroids are saved under `infusions` when they stand:
  19.4 bytes a peak, 1,965 → 8,645 bytes for three infusions, read in 3 ms.
- **A database candidate says which adduct found it, and a non-proton
  adduct has to earn its place.** `explain(record, …)` is
  `explain_structure` with the molfile taken out of LMSD — one enumeration
  through `explain.scored`; `rank_candidates(adduct=None)` searches every
  adduct the polarity allows. The gate is the finding: a product-ion
  channel is looked up over ±0.5 Da, at 700 Da 700 ppm holding hundreds of
  species, so five adducts multiply accidental candidates — the four named
  sphingolipids went from ranks 1, 4, 1, 1 to 1, 5, 5, 3 ungated;
  `explain.adduct_gate` (a non-proton adduct must name the precursor within
  the written precision; the proton adduct keeps the window) restores them.
  What it buys: a DIA window at 876.80 lists TG 52:2 at −1.7 ppm explaining
  24.0%, where the `[M+H]+` search does not list it at all.
- **A verified vial is worth nothing until the method carries what it
  taught.** `standards.component_from_infusion`: the formula it was
  explained with (labels included — `CA-d4` is C24H36D4O5), the adduct
  read off the channel, the **exact** mass of that adduct as the precursor
  with the written value beside it, the base peak (or a chosen peak) as the
  fragment, no retention time, `Component.provenance` (saved, in the
  Method table's tooltip, kept in a Qt item role because the table commits
  whole on every keystroke). *Use in method…* completes an existing
  component without overwriting; a second infusion of a compound can only
  fill what the first left empty (seven rows → three components).
- **An infusion has no batch and does not need one: it recalibrates on its
  own precursor.** `recalibrate.fit_infusion` matches every ion
  `explain.precursor_ions` offers to the strongest centroid within
  `LADDER_TOLERANCE_PPM` (20) above `MIN_INTENSITY`; offset only
  (widest ladder 72 Da), the intensity-weighted median; `same_ion` rung by
  rung; under `MIN_LADDER_RUNGS` (2) nothing is corrected. `precursor.
  in_spectrum` cannot be reused: it refines across neighbours and read
  430.3489 as 429.7675 on sticks. On the nine bile-acid infusions 7 of 9
  corrected, 3–8 rungs, −8.6 to +6.2 ppm (EAD high, CID low — per
  acquisition); at 5 ppm CA-d4 EAD 22 eV goes 5 of 56 and 14.0% → 8 of 56
  and 63.6%; TDCA-d4 EAD 0 of 104 → 5 and 78.4%. An own record travels:
  DCA-d4's and TDCA-d4's do not match their own vial's other activation
  raw at 5 ppm and match at 31.8 and 61.0 corrected.
- **A figure is drawn for the page it is going on, not for the window.**
  `spectra_compare.Palette`: `PAPER`, `MONO` (solid black against dashed
  `#666666`, filled/hollow heads on sticks) and `DARK` (lightened, not
  darkened — `for_ground` takes the direction from the ground). In
  greyscale the two MONO traces are a median L of 0 and 102 and the dash
  survives halving; on `#1e2124` every colour clears 3:1. A head is ink, so
  labels over headed sticks lift (14 on paper, 28 in MONO). `report._STYLE`
  has the same three; the running header and footer are painted outside
  the style sheet (`FURNITURE`), and a dark PDF is refused.
- **An mzML average adds the scans up; it does not interpolate them.** Two
  TOF scans do not share a mass axis; `np.interp` onto the union drew a
  line across every zero-stripped gap: against SCIEX's own average of the
  same 146 scans, 220,222 of 221,847 masses higher, total 3.31×, 670
  centroids against 424. Accumulating reproduces the vendor to
  max |Δ| 0.0. `MzmlSample.tic` grouped channels by scan count (a
  164-spectrum Thermo infusion came back as 8 points); the period now comes
  from `acquisition_cycles`. The instrument sits in a
  `referenceableParamGroup` pwiz only points at; `<activation>` is read and
  is part of the channel key. Two real Thermo infusions still read
  chromatographic: a 108-scan Orbitrap spray ramps for ten seconds where
  `SETTLING_SECONDS` is 1 (0.8812 with ten), and a stepped-precursor
  DI-MS/MS run is a falling ion current by construction — stated gaps.
- **A spray is not steady for a whole run, and the average says which
  scans it lost.** `infusion.stable_scans`: a scan whose TIC departs from
  the running median of `STABILITY_WINDOW` (21) scans by more than
  `SPRAY_JUMP` (0.5), and the scans after it until back inside
  `SPRAY_RECOVERED` (0.25); measured plateau — widest departure of a steady
  spray 0.316, smallest inside a real burst 0.870, the count identical from
  0.35 to 0.85 and from 21 scans up (the window must exceed twice the
  longest burst). The base peak is 4–8× noisier and finds nothing the total
  misses. `average_stable` averages each surviving stretch through the
  reader and combines by scan count, so a mask excluding nothing is byte
  for byte the vendor's average. Three of nine files lose 1, 1 and 9 scans
  (0.6–2.8% of the ion current, base peak −0.6 to −2.9%); gated on the
  infusion verdict because on a gradient the same rule leaves out the only
  29 scans worth keeping.
- **A spray has no peak, so the response is a height, and a product-ion
  acquisition has no envelope to leak.** `infusion_quant.responses`
  measures a compound three ways — precursor, fragment, water-loss ladder
  summed — each with M, M+1, M+2, and `ratio` divides an analyte by its
  standard. The precursor is not a basis (0, 7 and 124 counts on the CID
  files); the ladder holds 3,839–27,754 throughout. A d4 standard sits
  4.0251 Da above its analyte and the analyte's M+4 sits 4.0134 above, so
  the cross-talk is the tolerance's business: 0 at 10 ppm, 0.049–0.337%
  over a unit window, 0.00000% in reverse. And Q1 kept only the
  monoisotopic precursor — predicted M+1 26–30%, measured 0.0–0.4% — so
  `ISOTOPES_TRANSMITTED` (10%) reports the correction as zero with its
  reason. A row is a plain `PeakResult` with `rt=0`, `algorithm="infusion"`;
  a synthetic five-level series recovers every level (r² = 1.0000000).
- **A row that says what produced it can be kept without re-reading the
  file.** `quantify.fingerprint` digests the `Component` fields that reach
  extraction, the `IntegrationParams` in force and the injection's mass
  correction; `process_incremental` keeps every row whose fingerprint
  stands. On the 26-injection batch adding one injection went from 2.4 s to
  0.06 s, identical to a full run over 3,666 rows × 36 fields; a widened
  window 0.03 s; a method default keeps nothing and falls back to a full
  run below `FULL_RUN_BELOW` (0.5). A hand-integrated row is kept while its
  fingerprint holds and re-integrated when it does not. Measuring it found
  `link_internal_standards` walking the list once per row (13 M
  comparisons); `ResultsSet.by_key` indexes it and the derived pass is
  50 ms over 3,666 rows.
- **A record of one's own carries its provenance, and that provenance is a
  key.** `library.provenance_comment`/`provenance_of` write and read the
  comment in one shape, and the pair (file, channel) says two records are
  the same measurement. *Add all to library* wrote 9 records in 0.01 s and
  0 the second time, all nine skipped with the reason; `rewrite_records`
  re-picks the peaks from the file the comment names — 9 of 9 rewritten
  with every peak identical — gaining `Acquired`, `Base_peak_intensity` and
  an exact `PrecursorMZ`; a record whose file is gone is kept, and the file
  is copied to `.msp.bak` first. Where no adduct was identified no formula
  is written either.
- **A d4 standard's isotopic purity is a deconvolution, and a product-ion
  scan cannot supply one.** `purity.py` solves the d0…dn envelope by
  non-negative least squares (hand-written, no scipy) because each
  species' 13C satellite lands 2.9 mDa from the next species' peak; reading
  rungs as fractions reads the impurity 5–10% high. The measurement vetoes
  itself (`SATELLITE_SHARE`) when the fully-labelled ion's M+1 is under a
  quarter of what the formula demands — on all seven real infusions it is
  0.006–0.206% against 26.5–30.0%: the quadrupole took the satellites. The
  residue at the d3 rung moves with the collision energy (0.763, 0.328,
  0.067% at 12, 22, 45 eV), so it is an H• loss 1.5 mDa from d3, not
  isotopic composition. Purity needs one minute of TOF MS beside the
  product-ion channel.
- **An infusion's average is what hides the spray, so the contour becomes a
  film.** On an infusion `ContourView` adds the channel's TIC as a strip,
  marks the scans left out, and Play (`PLAY_RATE` 10 scans/s × 1/5/20)
  steps the scan spin box; `Δ from average` draws scan − run average over
  the average mirrored. Measured on DCA-d4: 473 rows in 1.4 s, the three
  transients at 4.38×, 2.40× and 4.36× visible as columns; the Δ at a burst
  is the whole ladder up together (+118,209 at 361) and at a stable scan
  −523 at most. Read the Δ by mass, not by point (the grid moves a
  fraction of a point between scans, so a peak's residual is a dipole). A
  frame costs 52–89 ms only because the pane is not rescaled while playing.
- **The API is a promise; the modules are not.** `milq/api.py` is the
  only surface with one — `__all__`, methods, keyword names, dataclass
  fields; `api.VERSION` rises when that breaks. Every import is inside the
  function that needs it, so importing it starts neither Qt nor a session;
  `headless()` is the only Qt in a signature. A SCIEX sample is called
  `sample`, so an injection is named by the file's stem; a spectrum off a
  reader is a profile, so `Spectrum.centroid()` exists and records,
  searches and explanations centroid first; `Annotation.formula` is the
  labelled formula. `tests/test_api.py` extracts the manual's three scripts
  from `python-api.md` and runs them on synthetic mzML; a path it cannot
  stand in for fails the test rather than being skipped.
- **Asking every route at once is only honest if the routes are enumerated
  alike.** `explain_any.explain_any` runs the name, LIPID MAPS, formula and
  drawing routes on one spectrum and ranks them by explained share, ties
  stated (a drawing beats a formula; a precursor inside the written
  precision beats one outside; then route order), every loser still listed
  with its adduct, share, `n of m` ions and ppm. Two cuts, three losses and
  20 ppm are shared across the structure routes, because a route given
  more cuts or a wider window wins a comparison it was handed. Measured on
  four bile-acid infusions, 2.6–4.7 s each: the name route names the right
  compound in all four and wins three at 92.0/87.3/90.6/92.2%; at 5 ppm it
  wins one of four (those axes sit 4–7 ppm high). The one it loses is the
  warning: a triacylglycerol read as `[M+2H]2+` explains 95.0% of CA-d4's
  EAD spectrum from 4,030 predicted masses — hence the *Ions* column. The
  label count is per route: PubChem's drawing places its four labels and
  needs none, the component table's `C24H40O5` needs all four.
- **Three purposes do not want the same collision energy, and the highest
  explained share is a trap.** `energy.recommend` groups a tray's infusions
  by compound, activation and energy and picks separately for
  identification (most predicted ions *and* a precursor above
  `MIN_INTENSITY`), for quantitation (the largest share on one fragment,
  repeating within `qc.OUT_PERCENT` where sprayed twice) and for a library
  record (the middle *position* among the energies, then the share). On
  the nine bile-acid infusions EAD 22 eV takes all three for CA-d4 and
  DCA-d4; TDCA-d4 splits — EAD 22 eV identifies it, 30 eV quantifies it at
  63% of the intensity on 468.3071. The library rule takes the middle
  first because the share is highest where the compound barely fragmented
  (85.0% at EAD 12 eV against 63.6% at 22, the surviving precursor being
  82% of that spectrum). Nothing between two measured energies is offered;
  a row the method contradicts is shown, greyed, never recommended.
- **A peak nobody explained is worth a hypothesis, and the precursor is
  what makes it a short one.** `unexplained.annotate` offers each strong
  unmatched peak the best of a tabulated contaminant (Keller et al. 2008),
  a satellite of an ion that *was* matched (13C, +Na−H at 21.982 and +K−H
  at 37.956 — an exchange, not an addition — a water or ammonia loss, an
  adduct or dimer of the precursor), or a composition constrained to a
  sub-formula of the precursor ion. Two constants came out of the four
  bile-acid infusions, both of which had been hiding real answers: the
  Seven Golden Rules are not applied under `GOLDEN_RULE_MASS` (150),
  because they cap H/C at 3.1 and protonated taurine — `[C2H8NO3S]+`,
  126.0211 at −6.3 ppm on TDCA-d4 — is 4.0; and odd-electron compositions
  are offered, marked and ranked last, because 78.0465 is the strongest
  unexplained peak of the CA-d4 EAD run at 22.5% of the base peak and it is
  `[C6H6]+` at +0.8 ppm. On 79 peaks: 1 satellite, 0 contaminants, 78
  compositions at 0.2–16.6 ppm, 0.02–0.07 s a file; every row carries how
  many other sub-formulas reach the same mass. The report carries the
  table; the Explain tab still shows bare masses.
- **Two corrections are not two axes.** A record of one's own carries the
  correction in force when it was written (`LibraryEntry.recalibrated_ppm`
  from its comment) and a search is told the query's. The first version
  called the difference between two corrections a gap between two axes —
  measured on the three bile-acid standards, the pair whose corrections
  were furthest apart (+2.0 against −7.5 ppm) agreed best of all, 2.0 ppm
  per paired peak: each spectrum stands where its own lock masses put it.
  What is apart by construction is a correction one side carries and the
  other does not (`library.axis_gap`), which is what is warned on, what
  *Re-search with the axis matched* removes, and what splits a
  `standard_history` series past `PEAK_TOLERANCE_PPM`. Both corrected beats
  every other combination on all four queries — the median gap per paired
  peak falls from 9.8–13.0 ppm to 2.1–4.3 at 20 ppm, and at 5 ppm three of
  four queries have no hit with neither side corrected. Matching is a
  diagnosis, not a repair (61.0 → no hit onto an uncorrected record);
  *Rewrite from files…* is the repair.
- **A fragment's own isotope satellite is evidence, and usually there is
  none to have.** `explain.isotope_evidence` asks of every matched ion what
  `adduct_evidence` asks of the precursor: is the M+1 in proportion to the
  ion's own composition (`ion_counts`, each reading kept only where it
  reproduces the ion's m/z). A disagreement is printed beside the match
  and never removes it. On the seven ZenoTOF bile-acid infusions the
  precursor transmits 0.00–0.26% of the 26–30% M+1 its composition
  demands, so all 34 matched ions read *none expected* — fragments of a
  monoisotopically isolated precursor cannot carry a 13C. A survey-bearing
  TripleTOF injection answered whether any window passes the M+1: 0.8% in
  the 647.5 product-ion channel against 73.7% in the survey, where both
  matched ions agree at 0.70 and 0.99. Two gates: a satellite window must
  not hold another predicted ion (a `+3D` rung's "M+1" is its `+4D`
  neighbour 2.9 mDa away — 12 of 34 read 0.96–40× their own peak), and a
  predicted M+1 under `SATELLITE_DETECTABLE` × the median height is
  unmeasurable, not a disagreement.
- **A share is not evidence until something else has been scored beside
  it.** `margin.py` explains the LIPID MAPS records that fit the written
  precursor at every adduct the polarity allows — `rank_candidates`' own
  pool and gate — and reports the chosen compound's share less the best of
  theirs, in points, excluding the compound at any adduct and anything of
  its own formula (same arithmetic, no contrast). A rival is enumerated
  the way the compound was: scored the other way — a bile acid's 56
  predicted masses against structures offering 700–2,900 each — the
  impostor won five of six real infusions by up to 33 points; enumerated
  alike, the true compound won all six. Ten nearest by mass overstates it,
  because mass order inside a 0.7 Da window says nothing, so the whole
  gated pool is scored (14–29 candidates, 0.05–0.55 s). `THIN_MARGIN` = 10
  points, the one gap in eleven real spectra (−3.0 2.1 2.1 6.1 | 13.9 …
  71.2); what falls below is a Cer at 538.6 explaining 9.5% where three
  lysophospholipids explain 11–12.4%, and TDCA-d4 at 78.4% against a
  sodiated lysoPC at 72.3% — known from the bottle, not from its spectrum.
- **A record does not travel between energies, but the records together
  do.** A CA-d4 record at 45 eV scores 6 against the same vial at 12 eV —
  a hit list saying the compound is absent, which is false.
  `library.EnergyProfile` reads one compound's records as a curve: each
  ladder rung's share against collision energy, computed by `profile_of`
  from the records present and never written into them. Shares of the
  profile's own total, never of the base peak, because the base peak walks
  the ladder — the ammoniated precursor is 83.5% at EAD 12 eV,
  `[M+H−2H2O]+` 25.2% at 22, `[M+H−3H2O]+` 54.2% at 45. `search_energy`
  sweeps at `ENERGY_STEP_EV` and says "compatible with CA-d4 EAD at ~18 eV
  (measured at 12 and 22)" beside an unchanged hit list; nothing past the
  measured range, no activation crossed, one record is *no profile*.
  Membership is measured (`MIN_MATCHED` ladder ions), which keeps the
  839.56 files out. Two points per activation are the honest limit: with
  both, the optimum lands on one of them, so the line adds the energy and
  not a better score (`PROFILE_BETTER_BY`).
- **A fixed noise floor is a claim about one scan of one instrument.**
  `precursor.MIN_INTENSITY` (100) was written for a TripleTOF survey scan;
  an infusion's average has a base peak of 109 to 12,271 counts on the nine
  real files. `infusion.noise_floor` measures it two ways and keeps both:
  the empty mass regions of the average (`processing.spectrum_noise`, the
  99th percentile of the local maxima there) and the scan-to-scan scatter
  of the quietest half-dalton window divided by the root of the scans
  averaged — the count travelling with the spectrum, since the spray mask
  trims runs. The larger is taken; where neither can be made the fixed 100
  stands with the reason (one of twelve chromatographic averages has 167
  measured points in 412). Measured: 0.068–3.53 counts on the nine
  infusions, 28–1,500× quieter than the constant, (a) larger on nine of
  nine. Four windows the fixed floor refused hold a real peak, and all four
  sit 30–70 ppm from the written mass — so `infusion_report._confirms`
  stops at *found but not confirmed* past `CONFIRMED_PPM`: the height says
  a peak is there; the mass says what it is.
- **A standard is not entered until three things agree, and the third is
  not written.** `ui/new_standard_dialog.py` is the path from a bottle: the
  name resolved live, the lot, the infusion file (`is_infusion`), the
  polarity's adducts pre-ticked from `adducts_matching` against the
  channel's written precursor. **Create** writes the component and the
  own-library record (the new `lot` in its provenance) and nothing else —
  the history is the library read back. A ticked adduct that fits nothing
  is overruled by the one the written precursor reaches (a tick is an
  expectation, the channel a measurement); a compound the method already
  carries writes no component and still writes the record. Measured on
  CA-d4: 1 of 5 adducts reaches 430.35, 2.6 s to open, average and
  identify, 0.05–0.08 s to re-identify after an edit; on `_TESTEARTIGO`
  0 of 5, Create disabled, nothing written. The plan takes the formula the
  report was built with — the typed one — before it resolves the name
  again: CI found `Testol` reaching testolactone on a machine with LIPID
  MAPS installed and nothing on one without, two refusals for one file.
- **A summary of nine reports is four blocks and no fifth.**
  `infusion_cover.build_html` prints the folder, the rows, what they add up
  to, what was left out and where each compound is — then stops. A row
  whose method isolates a mass the compound's other runs do not is
  reported *by that mass* (three measurements of 430.34 and two of 839.56,
  not five of one ion with two failures); an infusion nothing was
  predicted for is not counted as one that found nothing. Visible only on
  the printed page: sentences run together needed capitals, and twelve
  columns on A4 broke `Compound` as `Compoun/d` and `839.2316` as
  `839.23`/`16` at the old widths — a measurement broken in half is worse
  than wrapped prose (`CELL_CHARACTERS` 48). On the nine infusions the
  cover is two pages of 58 and 0.2 s of 31; it reads no file.
- **An average of a file that has not changed is a function, so it is
  written down — and the arithmetic left is moved off the window.**
  `spectrum_cache.py` keys the raw average on the acquisition and its
  `.wiff.scan` by size and mtime, the channel, the range, the spray mask's
  bytes and `include_unstable`, stored as one `.npz` in `<project>.oqcache/`
  (or the system cache with no project; `cache/dir`, `MILQ_CACHE_DIR`,
  `CACHE_MAX_MB` 512, LRU, every failure a miss). Raw, before any mass
  correction, which is applied on read. Measured on the nine infusions:
  cold 12.6–20.9 s, warm 7.7–8.5 s, one `.scan` touched 8.9 s; 27 infusions
  55.1 → 23.5 s; 39.1 MB against 47 MB of `.wiff.scan`; arrays identical hit
  or miss. `ui/infusion_worker.MeasureTask` takes the rest off the GUI
  thread: event-loop turns went from 0.4 a second to 89, rows arrive as
  files finish, Cancel is answered between files. Clearcore2 tolerates two
  `.wiff` in two threads — the single sequential worker is our constraint
  (the session's samples memoise without locks). A modal
  `QProgressDialog.setValue` pumps the event loop and can close the dialog
  underneath its own handler.
- **A picker that asks every candidate about every peak kept is quadratic,
  and centroiding is where it shows.** With the file reads cached,
  `processing.pick_peaks` was 40 of the 53 s a profiled `summarise` took
  over the nine infusions — 292 M steps of the generator on the
  `min_distance` line, because `centroid_spectrum` picks with a ceiling of
  100,000 and the kept list reaches 7,101 on a TOF average, and every one
  of ten thousand candidates was compared with all of them. Now the kept
  masses are held sorted and a bisection asks the two neighbours, and the
  centroids are taken for every candidate at once (`centroids_at`: the
  window's weights added left to right from zero, as numpy adds a slice
  under eight points, a point past the end contributing a zero) — asserted
  bit for bit against `centroid_mz` and the old loop on 51,200 random cases
  and on the 27 distinct picks of the real report, 25,740 peaks identical.
  The other half was repetition: each report centroided its average five
  times (the margin, the search, the raw axis, the explanation) and scored
  it three (`report_for`, the row, `cross_compare`), so `picked` and
  `_sticks` remember the answer on the report against the trace object it
  came from, and a replaced trace is picked afresh. Measured: 81 picks →
  36, `pick_peaks` 40.2 s → 0.06 s under cProfile, a headless `summarise`
  without the disk cache 19.1 → 10.6 s wall, of which 8.9 s is now the
  reader. What is left in a warm Measure is the reader's `average_stable`
  when no cache is passed, and the noise floor still centroids twice at
  0.001 (`spectrum_noise` and `quiet_window` do not share their peaks).
- **Every number Clearcore2 returns crossed the managed boundary one double
  at a time.** `wiff._to_numpy` was `np.asarray(list(net_array))`, and
  pythonnet marshals each element of that `list()` separately: 0.194 ms for
  one 1,143-point TOF scan against 0.0009 ms taking the same array as a
  buffer — **216×**, the same doubles byte for byte. It was 84% of
  `build_contour` and two thirds of an average, and it sat under every
  chromatogram, spectrum and XIC in the program. `np.array(memoryview(x),
  dtype=np.float64, copy=True)` now, with the element walk kept as a
  fallback for anything the buffer protocol refuses (a `List<double>`
  raises `TypeError`, which is the whole guard). **The copy is the point:**
  `np.frombuffer` and `np.asarray` on the .NET object hand back a view whose
  memory is the managed heap's — right until the collector moves or frees
  it, and on macOS that reads as plausible numbers rather than as a crash.
  Measured, per-scenario, `tools/bench.py --repeats 3`: contour 0.201 →
  0.075 s, spectra 0.087 → 0.039, average 0.292 → 0.187, quantify 0.589 →
  0.490, digest 1.177 → 1.082; `--digest` byte-identical, sha256
  `6f0f2d42…` on this machine's five files.
- **The quadratic `by_key` was written for was still in three other
  places.** `ResultsSet.get` walks the whole list, and so does
  `for_component`; `compare._delta` called `get` once per row, `_precision`
  once per replicate, and `sampling_report`, `build_calibrations`,
  `compare._figures` and `batches._side` filtered the whole set once per
  component. `ResultsSet.by_component()` is `by_key`'s twin and the callers
  build both once. Measured on synthetic rows at the real batch's size
  (3,666): the per-component filter 0.010 → 0.0002 s and the per-row lookup
  0.106 → 0.0031 s, and both grow with the square — at 7,332 rows the walks
  are 0.032 s and 0.518 s while the indexes do not move. On the five
  `260904_EICs_*` (405 rows) it is worth 0.09 s of the comparison and
  nothing you would notice, which is exactly why it survived: **the shape
  is only visible at batch size, so measure it there or synthetically.**
  `sampling._cycle` had the same shape in a different dress — the cycle
  belongs to the channel's time axis, and it was re-measured once per
  component onto the same handful of channels; it memoises per channel now.
- **Two things that looked like the next win and were not.** mzML header
  reading builds one `ET.fromstring` per spectrum, 23,722 of them, and one
  `XMLPullParser` fed the whole run measures **0.494 s against 0.504 s** —
  the cost is parsing 47 MB of XML, not constructing parsers, so the
  rewrite buys 2% and is not worth the risk. This is the *headers*, read
  once at open; the *arrays* were a different question and rewriting those
  was worth it — see the extraction bullet below, which leaves this parse
  exactly where it was and says what would actually shorten an open. And `Channel.__init__` is 0.36
  ms of `GetMSExperiment` per channel, 405 of them to open five files: that
  is Clearcore2's, and every channel's `Details` is needed for matching
  anyway, so laziness would only move it. What did help on the mzML side
  was one walk instead of three — `_params`, `_minutes` and `_activation`
  each iterated every descendant of the same spectrum, so `_scan_facts`
  does all three in one pass (1,485,831 `_local` calls → 635,301, and
  `_local` memoises the namespace strip): 0.799 → 0.736 s, verified equal
  on all 23,722 spectra of the real file, three answers at a time.
- **A measured figure that nothing runs is prose.** Every number in this
  file came from a real acquisition and, until `tests/real/`, none was
  checked: the fixtures are synthetic by design, because raw data is never
  committed. `tests/real/` is 56 tests over five sets — the five
  `260904_EICs_*`, the 26-injection batch with its project, the nine
  ZenoTOF infusions, eight DIA runs, two Thermo mzML — each asserting one
  figure at the tolerance it was written to. `tests/conftest.py` marks
  everything under the directory `real` and skips it unless
  `MILQ_REAL_DATA=1` or `-m real`, so CI runs `pytest -q` unchanged;
  each test skips itself naming the path it wanted; only the two sets this
  repository already names carry a default path, the rest come from an
  environment variable or an untracked `tests/real/data.local.json`.
  Writing them found six figures that had moved: the response index (±18%
  with three exceptions is now 0.437–2.081 with four), the retention-time
  bands (33/36/53/71% over 18/11/17/7 components), the margin's
  before-and-after (1,771 → 2,665 rows is now 1,647 → 2,638),
  `SM(d18:1/12:0)`'s error against its formula (−4.0 → −4.8 ppm; the 16.1
  spread unchanged), a sixth lock-mass refusal (the repairs gave an
  eleventh standard a formula, 234 ppm off), and +6.2 → +6.6 ppm at the top
  of the infusion corrections. Each test asserts what the program does now
  and keeps the old number in its docstring with what is known about the
  difference.
- **Modules written in parallel answer one question twice, and only running
  them side by side finds it.** `tests/test_integration_path.py` runs the
  whole infusion path on a synthetic spray that *bursts* — without a burst
  the masked and unmasked routes agree for the wrong reason — and asserts
  the agreements rather than the values. Six disagreements came out of
  running it on the nine real ZenoTOF infusions (`help/pages/integration.md`
  has the timings and the figures): `axis_subject` folded a d4 standard's
  labels in twice (`labelled_formula` returns the folded formula *and* the
  count), so all nine refused their own axis with "no lock mass" while the
  isolation verdict on the same page named the compound right — fixed,
  seven of nine correct again at 3–8 rungs and −8.6 to +6.6 ppm, the CID
  offsets re-measured at +3.8, +6.6 and +2.0 ppm (the recalibration page
  had carried +3.6/+6.2/+1.8 from an earlier run); `records_from_summary`
  wrote the run's scan count where three other places write the averaged
  one; `folder._listdir` called macOS's `._name` a stray scan and would have
  opened a `._X.wiff`; `infusion_cover` asked for the ppm before the
  isolated mass, so `isolated_precursors` went dead the moment the measured
  noise floor let those windows report an error; and `api.infusion_average`
  and `infusion_quant.centroids_of` averaged the whole run where everything
  else masks it — 2.90% of the base peak on the worst file, and
  `api.infusion_report` explained the unmasked average and printed the
  masked one. Three stand: two measured noise floors (whole-run 0.068–3.53
  counts for the Explorer, the report's masked one 0.068–4.27), a record
  scoring 97 rather than 100 against its own run (179 record peaks against
  204 query peaks at ≥1%; reverse is 100 and every record peak is found),
  and the CLI and API documents predicting from a formula and from a
  drawing (8 of 56 against 15 of 882, each saying which). Reading and
  averaging is 25 of the 27 seconds for nine files; warm buys nothing but
  reopening them, because no averaged spectrum is cached across a process.
- **A widget's least width is the window's, and a bar of buttons has no
  least width of its own.** The Method workspace put thirteen buttons in a
  `QHBoxLayout`, whose minimum is all thirteen side by side: 1,994 pixels,
  which became the main window's, so on a 1512 by 913 laptop the window
  opened wider than the screen and could not be dragged back — the title bar
  moves the top left corner and the problem is at the bottom right. Worse,
  every layout invalidation re-applied it, so changing **Columns** or **Rows**
  in the peak review grid, which is done constantly, pushed the window out
  over the edge again; that is what it looked like from the outside, and the
  spin boxes had nothing to do with it. `ui/flow_layout.FlowLayout` asks for
  its *widest single item* and wraps the rest onto the next line, and the
  fourteen bars that were `QHBoxLayout` now say `FlowLayout` and nothing
  else changed — it takes `addStretch`, `addSpacing` and `addWidget(w, 1)`
  so the call sites read the same. The other two halves: each Explorer side
  panel goes in a `QScrollArea` (the LIPID MAPS panel alone wanted 712
  pixels of height, and a dock is as tall as its tallest tab), and a label
  holding a sentence gets `setWordWrap` (the calibration panel's "No
  standards for this component…" was 720 pixels of minimum width). Measured,
  the window's least size: **2,000 x 864 → 888 x 515**. `MainShell.
  size_for_screen` opens no larger than the screen and `fit_on_screen` pulls
  a geometry saved on a bigger one back inside it, because that geometry
  outlives the fix. `tests/test_window_fits_screen.py` fails if any
  workspace ever again asks for more than 1280 x 760.
- **A pyqtgraph panel costs 5 ms, and the grid holds 64 of them.** Changing
  **Columns** or **Rows** rebuilt every panel: 0.52 s at 8 x 8, paid once per
  *step* of the spin box, so dragging from 3 to 8 paid it five times. The
  panels are interchangeable — `_fill` hands each one its data — so
  `_relayout` now grows and shrinks a pool and re-places what it has, and a
  panel the new shape does not need is hidden and kept rather than deleted.
  Both spin boxes stop at 8, so the pool is bounded at 64 panels, about
  14 MB. Measured: 8 x 8 0.521 → 0.107 s, back to 3 x 2 0.166 → 0.008 s, the
  sequence's peak resident size 232 → 156 MB. A spare has to be hidden
  *before* it is left out of the layout, for the reason the ninety piled-up
  combo boxes above give. `_PanelViewBox(enableMenu=False)` is the other
  half: pyqtgraph builds the whole right-click menu in the ViewBox's
  constructor, and these panels have always called `setMenuEnabled(False)`
  straight afterwards — building and throwing away a menu 64 times.
- **A label that counts something is not a reason to load it.** The LIPID
  MAPS panel printed "49,969 curated structures indexed locally." and got the
  number by opening the whole database: 0.84 s and 570 MB of the window's
  1.02 s and 685 MB, before anybody had searched for anything. The count was
  already written in the index's header. `lipidmaps.record_count` reads it —
  off the database's `meta` table, or off the first 4 KB of an old index's
  gzip stream — and the window builds in 0.23 s at 146 MB. Then the loaded
  form was made cheap too, because a real search still has to load it. Four
  shapes over the same 49,969 records, each in a fresh process: today's
  nested dicts 0.74 s / 591 MB; the connection tables kept as JSON *text*
  0.25 s / 362 MB; ten parallel lists 0.11 s / 303 MB; **one SQLite file
  0.0001 s / 41 MB**, which also turns three linear walks into index lookups
  — `by_id` 0.312 → 0.012 ms and a name looked up whole (`precursor`,
  `resolve_name`) 18.8 → 0.03 ms. `search_mass` and `search_formula` are
  *slower* in absolute terms (0.023 → 0.083 and 0.001 → 0.058 ms): they now build
  records from disk instead of handing back objects already in memory, and
  that is the trade the 550 MB bought. `find_by_name` on a substring is
  still a walk — of a names table, in C, 18.8 → 5.3 ms — and it is skipped
  entirely when the exact and leading matches already fill the limit, since
  nothing ranked below them can reach the answer. The index costs 45 MB on
  disk against 8.4 MB gzipped; the connection tables are 51 MB of it stored
  plainly, so they are deflated per record (20 MB) and inflated only in
  `molecule()`, which is why `LipidRecord.structure` may be a dict, a string
  or bytes and `compact()` is the one place that knows. `records` is a lazy
  sequence, `id` is the position in mass order so every search answers in the
  order the list answered, and the connection is per thread because the
  measuring worker explains spectra off the window's thread. Verified before
  it was believed: 77,874 comparisons against the old in-memory
  implementation over the real index — all 49,969 records field for field,
  3,000 molfiles rebuilt both ways, 2,003 `by_id`, 2,002 `search_formula`,
  8,000 mass and m/z searches, 9,500 `find_by_name` and 400 `precursor` —
  0 disagreements. An index in the old format is rewritten in place the
  first time it is opened (2.4 s, once): a 21 MB download does not happen
  twice because the format changed.
- **One connection per thread is the usual advice and it cannot be closed.**
  A `sqlite3.Connection` belongs to the thread that made it, so a
  thread-local pool's `close` can only ever release the calling thread's —
  and the LIPID MAPS index is a file the program replaces (a reinstall) and
  a test writes and removes. On macOS and Linux removing a file something
  still has open is allowed and nothing is ever noticed; Windows refuses it,
  and the v0.10.0 tag went red on `WinError 32` with the measuring worker's
  connection still holding `_tmp-index.json.gz`. `_StoredDatabase` now keeps
  **one** connection, opened `check_same_thread=False` and taken under an
  `RLock`, so `close()` really does let go; a read is a millisecond at most,
  so taking turns costs nothing worth measuring, and a closed database
  reopens on the next question. `LipidDatabase.close()` exists on the plain
  kind too and does nothing, so nothing holding one has to know which it
  has. `tests/test_lipidmaps_index.py` asserts the *state* rather than the
  removal, because the removal passes on this machine either way.
- **A rename is a promise to read the old name, not to write it.**
  OpenQuant became MIL-Q in 1.0.0 — the targeted half of the *Multi-omics
  Identification Laboratory* family beside MIL-X, which was OpenDIAL. The
  precedent is this project's own OpenPeakView rename in 0.6.1, and the
  rule it set held: **the old name goes on being understood and is never
  written again.** `milq/legacy.py` is the only module that knows it, so
  retiring it later is deleting one file and three calls. Three things it
  promises, each with a test in `tests/test_the_old_name.py`: every
  `OPENQUANT_X` is read as `MILQ_X` where that is unset, at *package
  import* rather than in each entry point, because importing the package
  is the one thing the window, the command line, the API and the suite
  have in common (`OPENPEAKVIEW_HOME`, the name before last, is read as
  `MILQ_HOME`); the preferences are copied out of the *OpenQuant* store
  the first time the new one is found empty, and never again; and
  `~/.openquant` is **kept in place** where it exists rather than moved to
  `~/.milq`, because it holds a .NET runtime and a 45 MB index and moving
  either to satisfy a change of name is minutes of work and a download to
  redo if it goes wrong. `inherit_settings` takes the old store as a
  parameter for a reason that cost a test: the native store on macOS is a
  daemon with a cache, so a test that wrote through one `QSettings` and
  read through another was measuring `cfprefsd`. What did *not* change:
  `.oqproj` is still read and written, `.opvproj` still read, and the
  Windows installer keeps its `UpgradeCode` so that installing MIL-Q
  replaces an installed OpenQuant instead of leaving two. The mechanical
  half — 1,013 lowercase, 206 capitalised and 39 shouted occurrences over
  169 files — was one scripted pass with four historical statements held
  back by sentinel, because "renamed to OpenQuant from OpenPeakView" in
  the 0.6.1 row is a fact about the past and rewriting it would have made
  the record lie. **And one thing the pass got wrong, which is the reason
  to distrust a blanket rename:** an `Id` is not a name. `OpenQuantIcon`
  and `OpenQuantShortcut` in the WiX source became `MIL-QIcon` and
  `MIL-QShortcut`, and a WiX identifier takes `A-Za-z0-9_.` and nothing
  else — so the v1.0.0 tag built two installers of three and failed on the
  Windows runner with "not a legal identifier", minutes into a release.
  The test that reads the installer source asserted the identifier *by
  name*, so the rename changed the test too and it agreed with the broken
  file; `test_every_identifier_in_the_installer_is_one_wix_will_accept`
  asserts the **shape** instead, which no rename satisfies by accident.
  Anywhere a name doubles as an identifier is where to look first next
  time: the hyphen in MIL-Q is legal in a window title, a plist value and
  a `.desktop` field, and illegal in a WiX `Id`.
- **A panel's fence is what clips a shared axis, and a grid layout never
  forgets a row.** Two things the review grid got wrong once its panels
  were pooled rather than rebuilt. **Same Y** set every panel's Y range to
  the page's ceiling and every panel clamped it straight back, because
  `fence` had set `yMax` from the panel's own tallest point; the switch
  looked as though it did nothing. `fence(x, y, ceiling)` now takes the
  shared ceiling and the fence reaches it. And a `QGridLayout` remembers
  every row and column it has ever had and shares the space by size hint
  among them: at 4 x 3 after 3 x 2 the rows measured 291, 197 and 90
  pixels. `_relayout` sets equal stretch on the rows and columns in use
  and none on the rest, which is what "a grid" means. Found by the person
  using it, not by a test — the tests counted panels and never measured a
  cell; `tests/test_peak_review_grid.py` now measures both.
- **A `.wiff` without its `.wiff.scan` opens and looks whole.** The method,
  the metadata and every channel's TIC are in the `.wiff`; the scans are
  not, so the first spectrum throws, and so do BPC, XIC, the contour and
  the quantitation. Found on an infusion folder where one companion had
  been renamed by hand (`name.wiff_mix1.scan` beside `name_mix1.wiff`):
  the Explorer drew the chromatogram, and every attempt at a spectrum left
  the pane as it was, with the .NET exception on a console nobody has —
  PyQt6 printed it and carried on. `wiff.Sample.problem` reads one scan
  when the sample is opened and, on failure, `scan_problem` names the
  companion and any stray `.scan` in the folder; `SampleEntry.problem`
  carries it (never saved), the shell warns on open, the tree marks the
  sample, `_spectrum_unreadable` writes it where the spectrum would be,
  and an XIC or an integration reports it as the row's note. The probe is
  the only way to know: nothing in the `.wiff` says the companion is
  absent.
- **Pinned spectra are traces after the live one.** `explorer.pin_spectrum`
  copies the live trace (`key == "spec"`) with the pane's title as its
  label and appends it; `_with_pins` keeps the live one first, so every
  panel that reads `traces[0]` still reads the live spectrum and the base
  plot's Mirror — which flips odd-indexed traces — draws one pin head to
  tail with it. Normalise is per trace, which is what two samples need.
- **F1 walks the widget tree.** `ui.help_window.describe(widget, page)` sets
  a dynamic property; `help_page_for` walks up from the focused widget to
  the first one that has it; the shell installs an application-wide event
  filter so F1 pressed in a dialog — a separate window, out of reach of the
  menu's shortcut — resolves the same way. `tests/test_help_context.py`
  fails if a widget names a page the manual does not have.
- **`estimate_noise` returns None when it cannot measure**, and that is the
  ordinary case, not the exception. Over 846 real traces the median had three
  non-zero points in sixty-one and only 9% had a baseline that varied at all;
  a trace the instrument reports as exact zeros has a baseline below its
  reporting threshold and there is nothing there to measure. `ChromPeak.snr`
  and `PeakResult.snr` are `float | None` accordingly, and on that batch the
  S/N was measurable for 23% of the peaks found. `NOISE_FLOOR` still filters —
  it is an absolute intensity threshold wearing a signal-to-noise name, and it
  still rejects the smallest peaks — but what it rejects on is no longer
  reported as a ratio. An acceptance criterion on S/N that cannot be evaluated
  now flags "S/N not measured" rather than passing quietly.
  `estimate_noise` returns 0.000 for an XIC that is 85–97% zeros, which is
  what a scheduled MRM channel looks like, so `detect_peaks` falls back to
  `NOISE_FLOOR = 1.0` and the reported S/N becomes **the peak height divided
  by one** — measured on a real batch, an internal standard of 30 counts
  reported S/N 30, and one of 42,400 counts reported 42,400. Anything gated on
  S/N is therefore gated on absolute height with an arbitrary constant, which
  includes `IntegrationParams.min_snr`, `AcceptanceLimits.min_snr` and
  `qc.MIN_SNR`. The last of those was added specifically to stop control
  charts flagging standards that are barely present, and on that batch it
  changes nothing for exactly this reason. What that question actually needs
  is a per-method floor on the internal standard's absolute response; S/N
  cannot stand in for it.
- **The retention-time window is not what the detector may see.** It says
  where the apex may be. Handing `detect_peaks` exactly that window meant two
  things, both found by reprocessing a real batch: peaks were truncated at the
  boundary, and — worse — `detect_peaks` returns nothing below five points, so
  a ±0.5 min window on a method sampling one transition every 14.6 s holds
  four scans and came back empty **whatever was in it**. A peak of 44,875
  counts read as "no peak above noise". Whether a component was integrated at
  all depended on whether its window happened to catch four scans or five,
  which is set by the channel's start offset. `quantify.detection_range`
  gives the detector `MARGIN_SCANS` either side and the apex is required to
  land inside the declared window afterwards. On that batch it took the rows
  with a peak from 1,647 to 2,638 and the components with any peak at all from
  84 to 139 of 141 (first measured as 1,771 → 2,665 and 89 → 139; `tests/real/`
  asserts the current figures). The margin is small on purpose: everything inside it
  competes on relative height with the real peak.
- **A contour averages the scans it cannot draw, it does not skip them.**
  A long run has more scans than a screen has rows. Sampling every k-th scan
  is faster and loses a one-scan peak entirely, so `build_contour` averages
  each group into its row — the mean rather than the sum, because the last
  group is usually short and a row that is dimmer only for that is a lie
  about the data. It also asks for spectra with `add_zeros=False`: a
  histogram of intensities cannot be changed by adding points of intensity
  zero, and restoring them triples the reading for the same grid.
- **`Contour.at` searches its bin edges to the right**, because that is where
  numpy's histogram puts a value sitting exactly on an edge. Searching left
  reads the cell next door and the readout under the cursor disagrees with
  the picture under it — caught by a test, not by eye.
- **Nothing is quantified off the contour.** Its m/z bins are wider than the
  instrument's steps and its rows may be several scans averaged, so
  `Extract this view` goes back to the reader for both the XIC and the
  spectrum. `Contour.slice_rt` and `slice_mz` exist for drawing, and say so.
- **The window does not always hold one peak.** Integration used to take
  `peaks[0]` — `detect_peaks` sorts by area, so the largest in the window,
  with nothing consulting the expected retention time. With a co-eluting
  isomer or isobar inside a ±0.6 min window, which is ordinary in lipidomics,
  the taller peak won whether or not the method pointed at it.
  `processing.choose_peak` now takes a rule from `IntegrationParams`:
  `PEAK_LARGEST` stays the default so no saved project moves, and
  `PEAK_NEAREST` decides by the method's retention time among the peaks that
  already cleared the height and S/N gates — those gates, not the rule, are
  what stops it picking noise sitting on the expected time. When proximity
  overrules size the result carries a note saying what it passed over,
  because a policy that silently takes the smaller peak cannot be reviewed.
- **A control chart needs a floor under its spread, not just a sigma.**
  Measured on the demo batch: eleven injections repeating to within half a
  per cent give a median absolute deviation of about 0.8%, and three of those
  is an internal standard 2.4% low — an ordinary injection. Two of eleven came
  out as four-sigma outliers, and would have on almost every real batch. So
  `qc.Injection.out` needs both conditions, past 3σ **and** at least
  `OUT_PERCENT` from the centre; drift needs both a magnitude and a Spearman
  correlation for the same reason. A flag that fires on every batch is not
  read on any of them.
- **A `QTextDocument` printed to a `QPdfWriter` needs the writer as its
  layout's paint device.** Without one it measures type at the screen's 96
  dots to the inch while the page is sized in the writer's 1200, so every
  point size comes out at a twelfth of itself: the first version of the
  report put eight sections into the top corner of a single otherwise blank
  page. `report.write_pdf` sets it, and two tests open the PDF — one counts
  pages, one looks for ink below the half-way line — because nothing about
  this is visible in the HTML.
- **Qt's HTML is a subset and it fails silently.** `padding` on a table cell
  and `width` on a table do nothing; the `cellpadding` and `width`
  *attributes* do, the first in pixels at 96 dpi. `<thead>` repeats on every
  printed page, `page-break-before` works, `tr.alt td` works, and anything
  cleverer than `tag.class` does not. Every rule in `report._STYLE` was
  rendered and looked at.
- **Nothing in Qt keeps a heading with what it introduces.** `write_pdf`
  lays the document out, asks which headings ended a page with their content
  on the next, and lays it out again with those pushed over — up to
  `MAX_REFLOWS` times, since moving one heading can strand another. The table
  of contents needs its own pass for the same reason: page numbers do not
  exist until the pages do. A hundred-page report is therefore laid out three
  times and takes about seventeen seconds, which is why the export puts up a
  wait cursor.
- **The Windows build needs Windows 10 1703+ and will not run under Wine**
  without the shim in `packaging/wine/`. Qt6Core imports eighteen `ucnv_*`
  symbols from `icuuc.dll`, which Windows ships in System32 and the PyQt6
  wheel does not carry. The shim must never go in the installer: on real
  Windows an application-local copy is found before the genuine one, and a
  test enforces this.

---

## What is missing against PeakView and MultiQuant

Checked against the code, not the README. Everything in the README's feature
tables exists. These do not:

Since done: LOD/LOQ (`validation.detection_limits`), carryover
(`validation.carryover`), the report (`report.py`, `File ▸ Export report…`),
batch QC (`qc.py`, the `Batch QC` tab, and a report section), the contour
view (`contour.py`), and integration algorithms with a comparison mode
(`processing.ALGORITHMS`, `compare.py`, `Compare algorithms…`).

| Missing | Which tool | Worth it? |
|---|---|---|
| **Spectral library search** | PeakView | Structure-based annotation covers lipids better; a library would cover everything else |
| **Mass recalibration** | PeakView | Only matters if the instrument drifts |
| **Audit trail, e-signatures** | MultiQuant | Only for a regulated laboratory |

---

## Open questions

- **An internal standard's retention time does not match its method**, in the
  batch this was developed against. Recorded in `NOTES.local.md`, which is not
  tracked: it is an observation about somebody's unpublished method rather
  than about this software.
- **The Windows installer has never been run on real Windows.** CI builds it
  and proves the bundle starts and reads a `.wiff` on a GitHub runner; nobody
  has installed the MSI on a machine. The source tree has now run on a
  Windows 11 desktop (suite, window, mzML batch): see *Verified facts*.
- **Reading a `.wiff` has only ever been done on macOS.** Linux and Windows
  run the suite and start the application; the SCIEX path is checked only as
  far as "the assemblies load" — on the Windows 11 desktop they load on
  .NET Framework 4.8 with no .NET 8 present, and `python -m
  milq.bootstrap --install` used to refuse that machine for having no
  .NET 8 (`_main` now installs only off Windows). Copying one `.wiff` to
  that machine would close this question.
- **Two things measured on Windows and left for later.** Opening an mzML is
  1.5 s a file, all header parsing, so a 26-injection project reopens in
  about 40 s; a sidecar index beside the file (headers pickled with the
  file's size and mtime) would make that seconds. And the four workspaces
  with their sixteen pyqtgraph plots are built before the window shows
  (1.1 s of the 2.3 s to a first frame, warm); building a tab when it is
  first shown would halve that, and `addTab` under the application's
  stylesheet is 150 ms of it on its own.
- **The portability plan had phases 1, 2 and 4** which were described in an
  earlier session and are not written down anywhere in the repository. Phase 0
  (CI) and phase 3 (packaging) are done.

---

## Continuous integration

Private repositories get 2,000 free minutes a month and this was at 98%,
nearly two thirds of it macOS, which bills at ten times a Linux minute
(Windows at two). So:

- a push to `main` runs **Linux only** — about 6 billable minutes
- macOS and Windows run on a pull request, on a tag, and on request. A tag
  packages on **four** runners, not three: `macos-15-intel` is the Intel
  Mac and `macos-latest` the Apple Silicon one, and a bundle is the
  interpreter and every compiled extension for the machine that built it.
  **A label GitHub no longer offers is not refused, it is queued forever**:
  `macos-13` was the Intel runner until it was retired, and the first
  v1.0.2 build sat in the queue for forty minutes before anyone looked at
  `actions/runner-images`'s README, which is where the labels that exist
  today are listed (`macos-15-intel` and `macos-26-intel` for x64). That second macOS
  runner is the expensive line on the bill — macOS is ten times a Linux
  minute — and it is the price of an Intel build. `make_dmg.sh` names the
  disk image from `uname -m`, so the two do not collide, and the artefact
  is named for the **runner** rather than `runner.os`, which is "macOS" for
  both of them
- a tag's last job is `checksums`: it waits for every packaging runner,
  downloads the assets back **off the release** and publishes `SHA256SUMS`
  beside them. Off the release rather than out of the build because they
  are the same bytes and only one of them is what a person downloads
- the `.NET bootstrap` check runs **weekly**, on a tag, or on request; it
  asks whether SCIEX's assemblies still load, which does not depend on
  anything committed here
- markdown, `docs/` and the licence start nothing
- only the newest run for a ref finishes

A tag runs everything and publishes four installers and their checksums.
Estimated: 40 pushes, 2 releases and 4 weeks come to about 25% of the
allowance — the second macOS runner added roughly a twentieth of the month
per release.

**Releasing is one command.** `git tag -a vX.Y.Z -m "…" && git push origin
vX.Y.Z`. Bump `milq/__init__.py` in the same commit — `pyproject` and the
PyInstaller spec read it from there, and a tag whose version disagrees with the
package produces installers named after the wrong one.

---

## Where to look when something breaks

| Symptom | Look at |
|---|---|
| A `.wiff` will not open | `bootstrap.ensure()`; run `python -m milq.bootstrap --install` |
| Two builds disagree | `--digest` on both, `diff` the output; the Windows build writes CRLF |
| An mzML has the wrong number of channels | `mzml.acquisition_cycles`; a file with no repeating cycle falls back to scan properties |
| A spectrum looks like it has a raised baseline | `restore_profile_zeros` did not fire; the file is probably centroided |
| Areas differ between formats | expected, see above; check it is 0.5% and not 50% |
| The application will not quit | a modal dialog. `offer_start` used to do this and no longer does |
| CI burns minutes | check nothing added macOS to a push trigger |

---

## Test suite

1943 tests, three skipped (the layered icon document, which 1.0.0 does not ship, and 4 bundle-weight tests that need a built bundle), plus 56 under `tests/real/` that run only with `MILQ_REAL_DATA=1`. `QT_QPA_PLATFORM=offscreen python3 -m pytest -q`.

`ui/settings.py` is the one place a settings object is made, and
`tests/conftest.py` sets `MILQ_SETTINGS` before any widget exists so
the suite writes an INI file of its own. Before that every test that
loaded a library or closed the shell wrote into the person's real
preferences — a pytest temporary path was the remembered spectral
library on this machine — because the native store on macOS ignores
`setPath` and `setDefaultFormat` applies only to the no-argument
constructor. A test that needs a settings object asks the factory.

`tests/conftest.py` collects and flushes Qt's deferred deletions after every
test. Without it the suite segfaults on Linux in a different place on every
run: the modules share one `QApplication`, and Python's collector was freeing
C++ widgets it still held. macOS and Windows read the same freed memory
without noticing, which is luck rather than correctness.

Static analysis runs in CI: `ruff check milq tests --select F,E9,B019`.
It found a `NameError` that had been sitting in the statistics table.
