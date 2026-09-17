# MIL-Q

Open source quantitation and review for LC-MS data — SCIEX `.wiff` read
directly, and **mzML** from any instrument that ProteoWizard can convert. Qualitative review the way PeakView works — TIC, BPC, the
individual channels of the acquisition method, extracted ion chromatograms,
and mass spectra scan by scan or averaged over a selected region of a peak —
and batch quantitation the way MultiQuant does: a component table, peak review
across every sample at once, calibration curves and grouped statistics.

Developed and used on **macOS (Apple Silicon included)**. The suite and the
application both start on Linux and Windows in CI, and installers are built
for macOS on Apple Silicon and on Intel, for Windows and for Linux — four
disk images and archives, each carrying the application icon, published with
a `SHA256SUMS` taken over the files the release serves. The Linux tarball
includes an `install.sh` that adds a launcher entry. Reading a `.wiff` has
only ever been done on macOS, though:
that path loads SCIEX's .NET assemblies, and CI can only report that the
runtime and the assemblies come up, not that a real acquisition opens.

The Windows installer needs **Windows 10 1703 or newer**, and does not run
under Wine or CrossOver. Qt6Core in the PyQt6 wheel imports eighteen `ucnv_*`
symbols from `icuuc.dll` and the wheel ships no ICU of its own, because
Windows has provided one in System32 since that release — `icuuc.dll` and
`icuin.dll` forwarding to a 2.7 MB `icu.dll`. Wine implements neither, so the
loader stops at `Qt6Core.dll` with *"DLL load failed while importing QtCore:
Module not found"*, having mapped the file successfully.

There is a way round it: `packaging/wine/` holds an 8 KB stub `icuuc.dll`
exporting exactly those eighteen symbols, which is enough for Qt to load and
fall back to the codecs it implements itself. With it in place, CrossOver
26.3 on macOS ran the Windows build and read a real acquisition, returning
the same numbers as the macOS build. It is deliberately not in the installer:
on a real Windows machine an application-local `icuuc.dll` would be found
before the genuine one. See that directory for why and how.

MIL-Q is the targeted half of the **Multi-omics Identification Laboratory**:
[MIL-X](https://github.com/pedronobrez/mil-x) explores a sample and MIL-Q
quantifies one. Explore, then quantify — MIL-X writes the component list
MIL-Q reads.

*Formerly OpenQuant, and OpenPeakView before that. Nothing has to be moved by
hand: `OPENQUANT_*` variables are read as `MILQ_*`, the old preferences are
inherited the first time MIL-Q starts, an existing `~/.openquant` goes on
being used, and installing MIL-Q on Windows replaces an installed OpenQuant
rather than leaving two. Projects saved as `.oqproj` and `.opvproj` both
still open; new ones are written as `.oqproj`.*

![screenshot](docs/screenshot.png)

## Formats

`.wiff2`, which SCIEX OS writes beside the pair, is not opened and nothing is
lost: measured to hold the method and the hashes of its two companions,
with no spectrum or chromatogram in its schema. The `.wiff` of the same
name is the acquisition.

`.wiff` (with its `.wiff.scan`) is read through SCIEX's own libraries. `.mzML`
is read directly, which is how data from other instruments gets in: a Thermo
`.raw`, an Agilent `.d` or a Bruker `.tdf` becomes mzML through ProteoWizard's
msconvert and opens here.

`File ▸ Export sample as mzML…` writes the other way, spectrum for spectrum,
with the total ion current the instrument reported rather than one recomputed
here.

How much survives the trip was measured rather than assumed, and checked
against ProteoWizard as well as against ourselves: msconvert reads what this
writes, and what msconvert writes from it reads back here with the same
numbers. Exporting a real 81-channel acquisition and reading it back gives, on
all five injections of a batch:

| | |
|---|---|
| spectra | identical, every channel, to the last digit |
| channel chromatograms | identical, every channel |
| the run's total ion chromatogram | identical, 577 points |
| integrated peak areas | identical |
| extracted ion chromatograms | differ, see below |

Channels are worked out from the order of acquisition, not only from the
properties of the scans. A method can have two entries that agree on MS level,
precursor, collision energy and mass range — this panel runs some transitions
twice — and grouping by those alone gave 69 channels instead of 81. A
scheduled method repeats its experiments in a fixed cycle, so position in the
cycle is the entry: this acquisition is a cycle of 44 run 339 times followed
by one of 37 run 238 times, and 44 + 37 is the 81 the vendor's file declares.
Data-dependent acquisition has no such cycle and falls back to the properties.

The one difference is the extracted ion chromatogram. SCIEX's own extraction
counts part of a peak whose measured points fall just outside the window, and
this reads the points inside it — a median of 0.58% and at most 12% of peak
height on that acquisition, always lower. Two attempts at reproducing the
vendor's edge rule were made and neither survived being tested on windows
other than the ones it was derived from, so the plain rule is what ships and
this paragraph is the warning. Quantify a series in one format.


## Starting a project

`File ▸ New project…` walks through the batch in the order the work needs it:
where the project file goes, which raw files are in it and what each injection
is, and where the processing method comes from. The project file is written
when the wizard finishes, so there is a file to save into from the first
change rather than one to remember to create at the end. The title bar carries
a `•` while anything is unsaved, and nothing that would discard the session —
quitting, closing, opening another project — does so without offering to save.

## Workspaces

The window is organised the way SCIEX OS is, with the workspaces on tabs and a
single session behind them, so the sample list and the component table exist
once rather than once per view.

| Workspace | What it is for |
|---|---|
| **Explorer** | qualitative review of the raw data: chromatograms, contours, spectra, XICs, chemistry |
| **Analytics** | the batch, quantitatively: one chromatogram per sample for each component, and the results table |
| **Method** | the component table — what to extract, where, and how the result is reported |
| **Samples** | the batch: sample type, study group, expected concentration, dilution |

`Ctrl+1/2/3/4` switch between them. `File ▸ Save project` writes a `.oqproj`
holding the method, the batch and the results, so the annotation survives
closing the program — none of it is recorded in the raw file, where every
injection comes back as `kUnknown`.

![analytics workspace](docs/screenshot-analytics.png)

## What it does

### Analytics: reviewing a batch

| Feature | How |
|---|---|
| Process the batch | **Process batch** extracts and integrates every component in every open sample |
| One panel per sample | the review grid shows the selected component across the whole batch, so an outlier stands out against its neighbours |
| Grid layout | columns and rows, with paging when the batch is larger than a page |
| Zoom | the expected window, tight on the peak, or the whole run |
| **Same Y** | one intensity scale across the panels, so heights compare directly |
| **Link X** | zooming one panel zooms them all |
| **Magnify peak** | one panel filling the pane; double-clicking a panel does the same |
| **Manual** | drag across a peak to integrate exactly that range; the row is marked ✎ and survives reprocessing |
| Back to automatic | right-click a hand-integrated panel |
| **Suggest from data** | retention times from agreement between the open injections, and window widths from their sampling. The estimator is checked first against the components that already declare a time, and the confidence on every row is the accuracy it actually achieved at that peak height on this batch — so a proposal is ticked by somebody who can see what it rests on, and nothing is applied unticked |
| **Export schedule** | the scheduled acquisition the method implies — every component with a retention time over its window — with how many transitions are acquired at once at the busiest moment and the dwell a target cycle leaves each, or the shortest cycle the dwell floor allows. The target starts from what the batch measured, labelled a bound when its peaks were narrower than a cycle. A plain CSV whose columns map onto the vendor's table |
| **Method report…** | everything the application can say about a method before it is run, as one PDF or HTML: the component table with every flagged row marked, **Check method**'s findings by severity, the formulas carried and derivable with every refusal's two masses, the standards that could be lock masses — and, with a file open, which channel serves each component, what the survey covers, and the schedule the method implies. It grades nothing and changes nothing |
| **Incremental reprocessing** | every row records what produced it, so a reprocess keeps what has not changed: adding an injection to 26 takes 0.06 s instead of 2.4 s, identical field for field to a full run; `Reprocess all…` reads everything again |
| **Check method** | reads the method against itself and against the open files, before a batch is processed: components sharing a transition with nothing to separate them, internal standards with no retention time and how many components they carry, windows the sampling cannot resolve. Everything it reports would otherwise be learned from the results, which is later and harder |
| Integration parameters | per component, with **Update method for component** / **for group**, **Back to method defaults**, and copy/paste between components |
| Contour | **View ▸ Contour** draws the active channel as a surface — time across, m/z up, intensity as colour — so an interference beside a target or a ridge down the whole run is visible rather than inferred. Square root by default, because a linear ramp over four decades shows the base peak and nothing else. Click a spot for the spectrum under it; **Extract this view** takes the chromatogram and spectrum of the rectangle on screen, both from the reader rather than from the grid |
| Noise region | right-click a panel with a stretch of baseline shaded to measure S/N there, peak-to-peak or by standard deviation |
| Which peak | **Peak**: `largest` takes the biggest peak in the retention-time window, `nearest the expected RT` uses the method's time to decide. It matters when the window holds two — a co-eluting isomer or isobar, ordinary in lipidomics — where the taller peak is not necessarily the analyte. `largest` is the default, so no existing project changes its numbers; where proximity overrules size, the row says what it passed over |
| Which algorithm | **Algorithm**: `Valley to valley` walks out from the apex and takes the trapezoid above a straight baseline — what this always did, and the default. `Summation over the window` does no peak finding: the retention-time window is the boundary, which is the arithmetic of manual integration applied to the declared window. `Gaussian fit` finds the peak as valley does and reports the area of a curve fitted to the points inside its boundaries; on a trace sampled every fifteen seconds a peak is two or three points wide and a trapezoid over them moves with where the scans landed, which a fitted curve does not. The fit needs three points on the peak's flanks, and where it has fewer it leaves the valley area standing and says so on the row rather than reporting a curve through the noise. Every row says which algorithm produced its number |
| **Compare batches…** | a reference project against the open batch, component by component: rows found, points on the peak, the replicates' %CV, the median area and the retention time, with the components that moved marked — the question a new acquisition schedule poses. The reference is read from its project file without opening a raw file |
| **Export to Excel and Skyline** | `File ▸ Export workbook (Excel)…` writes the batch as one `.xlsx` — Results, Calibration, Statistics, Batch QC, Method and Samples, one sheet each, every number a number, written without a dependency and verified by reading back, by openpyxl out of repo, by macOS Quick Look and by Excel for Mac itself; `Export for Skyline…` in the Method workspace writes the component table as a small-molecule transition list in Skyline's documented columns, not yet imported into Skyline |
| **Audit trail** | every change made by hand — manual integrations, excluded rows, dropped calibration standards, method and sample edits, reprocessings — with the value before and after, in the project, on its own tab, in the report and as CSV. A record of what was done, not an electronic signature |
| **Compare algorithms…** | integrates the batch with every algorithm and puts the answers side by side: rows found, how far each component's areas moved against the reference, and the %CV of each algorithm over the rows that were meant to agree — the internal standards across every spiked injection, the quality controls for an analyte. That last figure is the one that can call an algorithm better rather than different: same files, same noise, only the arithmetic changed. Pick a sample and see every algorithm's integration drawn on the one trace; **Adopt and reprocess** puts the batch on the one you choose. The comparison goes into the report |
| **Show IS** | the internal standard drawn behind the analyte, rescaled to it, so retention times and shapes compare |
| Results table | one row per sample and component: RT, expected RT, ΔRT, area, height, width, S/N, and why a row is empty |
| Internal standards | mark a component as one, point analytes at it, and get IS area, area ratio and height ratio |
| Response | area or ratio to the internal standard, chosen per component in the Method workspace |
| Ion ratio | a qualifier transition is scored against its quantifier, with a Pass / Marginal / Fail traffic light |
| Two-way linking | clicking a panel selects its row, and selecting a row brings up that component and highlights its panel |
| Sorting, filtering, view modes | by sample or by component, with a free-text filter over every column |
| Columns | which ones are shown and to how many decimals |
| **Used** | exclude a row from the statistics without deleting it |
| Export | the visible columns of the visible rows, as CSV |
| **LOD / LOQ** | derived from each curve's scatter about its own line, 3.3σ/S and 10σ/S as ICH Q2 defines them; a limit that lands below the lowest standard is marked as extrapolated rather than demonstrated |
| **Carryover** | the blank injected after the highest standard, against the response at the lowest calibrated concentration, with a 20% limit. A run with no blank in that position reports that it was not measured, rather than a number from the nearest blank |
| **Sampling** | the third tab of Batch QC, and a report section: for every component, the cycle time of its channel, the width of its peaks, and how many points sit on the peak — counted at integration and carried on every row — with the cycle times that would give a fit three points and the base ten. A property of the acquisition schedule, and the one thing no processing substitutes for |
| **Response floor** | **Min. response** on an internal standard: what it has to give before a ratio to it means anything. The batch cannot derive it and S/N cannot stand in for it on a scheduled acquisition, so the method declares it; the control chart, the acceptance of every row normalised against the standard, and **Check method** all read it |
| **Suggest floors** | in Batch QC: a proposed **Min. response** per internal standard — half its median over the injections that were not failures, with the basis on the row — written only when ticked and applied |
| **Mass drift** | a sixth tab: every internal standard's precursor read from the survey scan in every injection, in run order, against the batch's own median; the change across the run, and an index over the standards for what the instrument did rather than any one compound. Injections that did not measure the same ion — a spread over 25 ppm — are said not to, rather than fitted. Measured on request, not saved |
| **Mass recalibration** | lock masses from the internal standards that carry a formula, fitted per injection: an offset, or a linear term where four or more span the range and leave-one-out says it helps; residuals before and after on every injection, applied to spectra, accurate-mass measurements and extraction windows behind one switch, off by default. On the batch this was written for, ten of the eleven standards get a formula from their names and the fit is still one lock mass — only one of the sixty formula-bearing components in the survey measures the same ion across the run — so the correction is the size of its own 16 ppm spread |
| **Fill formulas from names** | in the Method workspace: reads the lipid shorthand the component names carry — `SM(d18:1/12:0)`, `C16:0-Ceramide`, `PC 34:1`, `TG 52:2`, `h24:0`, `-d4` — and fills the empty Formula cells, which is what turns an internal standard into a lock mass. Only empty cells, never a typed formula and never a precursor; a formula is kept only where its mass agrees with the written precursor to its last decimal, and both numbers are listed where it does not. On the method this was written for, 125 of 141 components and 10 of 11 standards, and 13 of the 16 refusals were the written precursor typed to fewer places |
| **Repair precursors from formulas** | where a name's formula contradicts the written precursor, both masses side by side with the difference in mDa and ppm and the extraction window before and after; ticked for you under half a dalton, left to you past it, and every applied row recorded in the audit trail. On the method this was written for, 13 repairs changed no integrated number and gave every internal standard a formula; the three whole-dalton rows are the name being wrong, not the mass |
| **Batch QC** | control charts of the internal standards against the order the instrument injected, taken from the acquisition times. The centre is the median and the spread the median absolute deviation, so one bad injection cannot widen the limits meant to catch it; an injection is called out only when it is both beyond 3σ and at least 20% from the centre, and a run is called drifting only when the fitted change is at least 20% and goes one way. Plus the %CV of the quality controls |
| **Report** | `File ▸ Export report…` writes the whole batch — summary, samples, method, calibration, limits, carryover, per-component results and statistics — as A4 portrait PDF to hand over or HTML to keep. Numbered sections, a contents list with page numbers, and a heading row that repeats on every page. Built from the session rather than from the screen, so it holds what was measured and not what happened to be on show |

### Calibration

| Feature | How |
|---|---|
| Build a curve | mark samples as **Standard** in the Samples workspace and give them a concentration |
| Regressions | linear, linear through zero, quadratic, mean response factor |
| Weighting | 1, 1/x, 1/x², 1/y, 1/y² |
| Curve pane | the points, the fit, the equation, r and r², and each standard's back-calculated accuracy |
| Exclude a point | click it on the plot, or double-click its row |
| **Remove outliers** | drops standards outside a tolerance, one at a time |
| Concentrations | unknowns are read off the curve, multiplied by the dilution factor |
| Response | the curve is built from the ratio to the internal standard when there is one, and from the raw area otherwise |

![calibration](docs/screenshot-calibration.png)

### Review

| Feature | How |
|---|---|
| Acceptance criteria | max ΔRT, max accuracy deviation and min S/N, per component or for the whole method |
| Status | a Pass / Marginal / Fail light per row, with the reasons spelled out in **Flags** |
| Filter | **Show** narrows the table to Pass, Marginal, Fail or Not integrated |
| **Statistics** | mean, SD and **%CV** per component, grouped by concentration, sample name or sample type, with the individual values behind them |
| **Metric plot** | any numeric column against the row order or another column; clicking a point selects its row |

A method that has not been given criteria reports no status at all rather than a
green light — except for a row that failed to integrate, which always fails.

![review](docs/screenshot-review.png)


### Navigation and display

| Feature | How |
|---|---|
| **Check a folder** | `File ▸ Check a folder…`, and before files are added: what the folder holds and what would go wrong in it, from the names alone — a `.wiff` with no `.wiff.scan` beside it (which otherwise opens and looks whole until the first spectrum), a `.scan` that belongs to no `.wiff` there with the rename offered after a confirmation naming both files, `.wiff2` and other vendors' formats that will be passed over, files already open or not there. Nothing is opened by the check and nothing is renamed without being asked |
| Open several `.wiff` files and overlay them | `File ▸ Open .wiff` (multi-select) |
| TIC of the whole sample | the “Sample TIC” node in the tree |
| TIC or BPC per channel | check the channels and pick `TIC`/`BPC` |
| Individual method channels | every experiment is listed with precursor, mass range and CE |
| Filter channels | search box (type `313.2`, for instance) |
| Spectrum of one scan | single click on the chromatogram |
| Step scan by scan | ← → or the ◀ ▶ buttons |
| Average spectrum of a region | Shift + drag on the chromatogram |
| **Pin spectrum** | keep the spectrum on screen and draw the next one over it — another sample, scan or channel — each pinned one in its own colour and named in the legend; **Normalise** puts them on their own base peaks and **Mirror** draws every other one downwards, head to tail |
| **Label floor** | the triangle beside the spectrum's Y axis, or **Label floor (%)** in the View toolbar: how tall a peak must be against the tallest one in view before its m/z is written. Drag it down for the small peaks a 2% default hides — measured, the precursor of a deuterated bile-acid standard, at 1.49% of the base peak, is unnamed at 2% and named at 0.5%. A fraction of the view, not an intensity, so it survives a zoom and the next spectrum; double-click to reset; the printed comparison uses the same floor |
| **Export comparison** | the pinned spectra and the live one as one picture — PNG at twice the size for print, SVG to resize — drawn again for paper rather than grabbed off the screen; the same picture goes into the report under *Compared spectra*, with the traces and the masses they share within 10 ppm |
| **Print themes** | Paper, Black and white (line style where colour cannot be spent; measured distinguishable in greyscale at half size) and Dark for figures and the HTML report; a dark PDF is refused |
| **Direct infusion** | a sample with no chromatography is recognised when it is opened — both the sample's total ion chromatogram and its strongest product-ion channel flat, measured against 39 chromatographic runs — marked in the tree, its strongest product-ion channel made active, and the average of every scan shown at once, which is what Explain, the library search and a pin then read. **Average whole run** does the same on any channel |
| **Per-compound infusion report** | one infused standard on two to four pages — averaged spectrum, peaks, accurate precursor, structural explanation, library match and other infusions of the same compound head to tail — as PDF or HTML, with a verdict that sums what was checked and never passes or fails it. `Process ▸ Report this infusion…`, or every open infusion in one document |
| **Infusions tab** | every open infusion on one row — compound, mode and energy, scans, base peak, the written precursor measured back with its error and height, the ions found of those predicted, the best record of your own library with both scores and its collision energy against this run's, and each infusion scored against the others of the same compound. Measured on request; a cell that could not be filled says why. **Report…** writes the per-compound document for the rows chosen, **Export CSV…** the whole table, and the batch report prints it as its *Infusions* section |
| **Name against method** | an `Isolated` column and a warning at open when the file name's compound is not what the method isolates — found two acquisitions named CA-d4 whose method targets 839.56 |
| **Compare infusions…** | today's infusions against a reference project's saved summary, matched by compound and by conditions, marked on the standard-history rules; the reference is read from its project without a raw file |
| **Recommend energies…** | every infusion of a compound grouped by activation and collision energy, and which condition to use for identification, for quantitation and for a library record — three questions that need not agree, each with the figures it was decided on. An energy nobody acquired is never offered; a row the method contradicts is shown and never recommended |
| **Use in method…** | an infusion row written into the component table with its formula, the exact mass of the identified adduct beside the written one, a chosen fragment and its provenance |
| **New standard…** | a bottle to a working internal standard in one dialog — the name resolved as you type, the lot, an infusion file that has to read as one, the polarity's adducts ticked from the channel's own written precursor; writes the component and the record in your own library, one audit entry naming both, and refuses a precursor no adduct reaches with the closest misses named. `File ▸ New standard…` |
| **The noise floor, measured** | an infusion's floor is read from its own average — the empty mass regions and the scan-to-scan scatter — instead of a fixed 100 counts; 0.07–3.5 counts on nine real infusions, and a precursor that is found but 30–70 ppm off is reported as found and not confirmed |
| **Quantify…** | an analyte against its deuterated standard in the same spray — precursor, fragment or the water-loss ladder — with the isotope cross-talk computed and, where Q1 removed the satellites, reported as zero with its reason |
| **Add all to library / Rewrite from files…** | one record per infusion, never twice for the same file and channel; old records re-read from their files and rewritten with the fields newer versions write, the old file kept as `.bak` |
| **Isotopic purity** | the d0…dn envelope of a labelled standard solved as a non-negative least squares, with the pair a certificate quotes — and a refusal, with the rungs printed, where a product-ion scan has no satellites to solve from |
| **Recalibration of an infusion** | the mass axis of a spray corrected from its own precursor and water-loss ladder, behind the same switch as the batch's; CA-d4 at 5 ppm goes from 5 to 8 of 56 ions explained |
| **Scans a spray lost** | unstable scans (a burst past 50% of the running median, and the recovery after it) left out of the average and named on the title, the report and the record; `Process ▸ Include unstable scans` puts them back |
| **The film** | on an infusion the contour view gains the TIC strip, the excluded scans, Play at 1×/5×/20× stepping the scan box, and `Δ from average` drawing scan minus average over the average mirrored |
| **A folder of infusions at once** | point at the folder and get the per-compound document with nothing opened in the Explorer — `File ▸ Report infusions in a folder…` or `--infusion-report PATH… --out FILE [--library] [--components] [--html] [--per-compound] [--csv]`. The folder is checked first, a `.wiff` without its `.wiff.scan` is skipped rather than opened, a run that is not an infusion is left out with the figures that say why. One file read at a time. Nine ZenoTOF infusions: 48 pages in 32 s, the same table as the Infusions tab |
| **The cover of a folder report** | before the per-compound pages: the folder, one row per infusion, an aggregated verdict sentence by sentence, the skipped files with reasons and a contents list — two pages and 0.2 s on nine infusions |
| Live preview | the spectrum follows the highlight while you drag or resize it |
| Integration of the selection | area, height, apex and S/N in the status bar |
| **Stack** | one pane per trace with the time axes locked together |
| **Overview** | navigator showing the full range and where the current zoom sits |
| **Mirror** | flips every other trace — sample against blank |
| **Cascade** | offsets the overlaid traces in x (min) and y (%) |
| Sample and method information | **Sample** tab (vial, volume, method, batch, DP/CE) |
| Preferences | everything is remembered between sessions |

### Extraction and quantification

| Feature | How |
|---|---|
| Component table | **Method** workspace: name, group, precursor, fragment, RT, window, tolerance, formula, adduct, internal standard, response |
| Build the table from the acquisition method | **Generate from acquisition method** — one component per product-ion channel, instead of typing an 80-transition method by hand |
| Formula instead of a mass | type `C18H30D4O4` with an adduct and the precursor is computed — how a labelled internal standard is entered |
| Internal standards and qualifiers | mark a component as an internal standard, point analytes at it, or declare a transition the qualifier of another with its expected ion ratio |
| Import/export the list | CSV, headers in English or Portuguese |
| Batch extraction | **Extract and integrate all** runs the list over every checked sample |
| Show one compound | double-click a row for its XIC across all samples |
| Results table | RT, area, height, width, S/N and a note; sortable and exportable |
| Automatic peak detection | **Detect peaks** integrates everything on the chromatogram |
| Manual XIC | **Manual XIC** tab: list of m/z plus a tolerance in Da or ppm |
| XIC from the spectrum | Shift + drag on the spectrum → right-click → *Extract XIC* |
| XIC from the peak list | double-click a row of the **Spectrum peaks** tab |
| Export | `File ▸ Export chromatograms / spectrum (CSV)` |

### Processing and interpretation

| Feature | How |
|---|---|
| Gaussian smoothing | **Smooth (σ, scans)**; 0 turns it off |
| Baseline removal | **Baseline (min)**; use a window wider than the broadest peak |
| Background subtraction | select a blank range → **Set background** |
| **Centroid** | turns the profile spectrum into sticks |
| **Markers** | drop a marker on a peak; the others are then labelled with their distance to it, which is how neutral losses and isotope spacings are read |

### Lipid annotation

| Feature | How |
|---|---|
| Local LIPID MAPS index | one 21 MB download becomes a 45 MB index of 49,969 curated structures, read a row at a time rather than held in memory; lookups need no network and take under a millisecond |
| **Library** | the spectrum on screen searched against an MSP (NIST, MassBank, MoNA, GNPS) or MGF library, within a precursor tolerance: the cosine over both spectra and the reverse cosine over the library's peaks alone, so a co-eluting impurity is visible as a high reverse with a low score; the matched peaks, and the record overlaid on the spectrum |
| **Your own library** | the spectrum on screen written into an MSP of your own — name, precursor, adduct, formula, collision energy, and a comment naming the file, sample and scans it was averaged over — appended to a file chosen once, and searchable the moment it is written. Centroids only, peaks under 1% of the base peak dropped, at most 200 kept. Measured: records written from one injection put themselves first for 14 of 14 compounds when a different injection was searched against them, at reverse scores of 45–96, with every other compound's record at most 42 |
| **Where the labels are** | a deuterated standard's fragments say how many labels each piece kept; the placements consistent with all of them are enumerated, tied and reported, with the positions nothing separates named as such — measured on cholic acid-d4, the spectrum bounds the labels rather than placing them, and says so |
| **The adduct the precursor actually is** | a channel written `430.35` is `[M+NH4]+`, not `[M+H]+`: the adduct is read off the written precursor and the formula, the reason printed with its ppm and the alternative, and a precursor no adduct reaches is not explained at all rather than explained as the wrong ion. An ammonium or formate adduct leaves as a neutral, so the fragments are `[M+H]+`/`[M-H]-` and the loss ladder hangs off those; a sodium stays coordinated, so both carriers are offered. A **name** — `cholic acid-d4`, `TDCA-d4` — resolves through a table of bile-acid standards, then LIPID MAPS, then the lipid shorthand, with the label count read off the suffix |
| **Adducts on database records too** | a LIPID MAPS candidate is scored through the same adduct model as a drawing of your own, every adduct of the polarity searched with a gate that makes a non-proton adduct name the precursor; a triacylglycerol at `[M+NH4]+` is found where the `[M+H]+` search listed nothing |
| **Explain, once** | one button tries the compound's name, LIPID MAPS, the formula and a drawing, and shows the one that explains the most — with every other route beside it, its adduct, its share and how many of the masses it offered were found |
| **What the unexplained peaks might be** | every strong peak the explanation missed gets a hypothesis with its ppm — a known contaminant, a satellite of a matched ion, or a composition that is a sub-formula of the precursor — and how many rival compositions reach the same mass; a peak with none is reported as a statement about the compound |
| **Standard history** | every own-library record of one compound as a control chart over the days it was verified — the cosine against the first record, the base peak's ppm from it, and its absolute height, grouped by collision energy and activation, on the Batch QC rules. Library tab ▸ *History…*, with CSV |
| Candidates for a mass | **LIPID MAPS** tab, or right-click a spectrum peak → *Find formula for this peak* |
| Species, then structures | results group by species, with the isomers that share it underneath — a mass cannot separate them |
| Accurate mass from the data | before searching, each precursor is measured in the TOF MS survey scan at the time its own transition peaks, and cross-checked against the surviving precursor in the product-ion scan |
| Annotate a whole table | **Annotate from LIPID MAPS…** in the Method workspace proposes a species for every component still named after its precursor |
| Traceability | the LM_ID travels with the component and through the CSV |
| **A structure or formula of your own** | under Explain: a `.mol`/`.sdf` (PubChem's download) is scored like a database record, cleavages and losses; a formula alone gives the precursor and its neutral losses; **Deuterium, unplaced** offers each fragment carrying none to all of the labels and lets the spectrum say how many it kept — for a labelled standard drawn unlabelled |

Where the survey scan can measure a precursor, the search uses that mass at
±10 ppm. Where it cannot, the window falls back to the precursor's own
precision — a mass written as `351.20` is known to ±5 mDa, so asking for 10 ppm
of it would be inventing digits. On real data the difference decides the
answer: a transition written as `325.20` matches `FA 18:3;O3` at nominal
precision, but the survey scan puts the ion at 325.1887 and the product-ion
scan agrees to within 1 ppm, which rules that species out at 41 ppm.

A survey measurement is only used when the batch agrees on it to within 25 ppm
and the product-ion scan confirms it. That second check matters: the survey
sees everything eluting at that moment, so a strong interference inside the
search window can win, while whatever survives fragmentation must have passed
through Q1's isolation window first.

A component is only
offered for automatic naming when exactly one species fits that window. On a
component table generated from the acquisition method, where precursors carry
one or two decimals, that means most rows come back marked *needs an accurate
mass* rather than guessed at.

Searches are also restricted to structures built from C, H, N, O, P, S and Se.
LMSD holds organoarsenic and fluorinated lipids; they are valid records and
absurd candidates for a plasma oxylipin panel, and a rounded precursor mass
matches one happily.

### Chemistry

| Feature | How |
|---|---|
| Exact masses | **Mass calc** tab: monoisotopic, average, RDBE and the ion m/z for a formula |
| Formula syntax | groups and multipliers (`C6H4(NO2)2`), plus single isotopes — `[13C]`, or `D` for deuterium, so labelled internal standards work |
| Adducts | [M−H]⁻, [M+Cl]⁻, [M+HCOO]⁻, [M+CH₃COO]⁻, [M−2H]²⁻, [M+H]⁺, [M+NH₄]⁺, [M+Na]⁺, [M+K]⁺, [M+2H]²⁺ |
| Mass accuracy | type a measured m/z for the error in mDa and ppm |
| Theoretical isotope pattern | table of m/z and abundance, and **Overlay on spectrum** to compare it with the data |
| **Formula finder** | right-click a spectrum peak → *Find formula for this peak*, or type an m/z |
| Search constraints | tolerance in ppm or Da, per-element ranges, RDBE range, even-electron only, element-ratio rules |
| Isotope ranking | candidates are scored against the isotope satellites of the spectrum on screen |

Smoothing and baseline removal apply to the drawing, the integration and the
export alike, so area and height always match what is on screen.

Signal-to-noise is measured over the whole chromatogram, or over a noise region
if one is set — never inside the retention-time window, which is mostly peak
and would report the peak's own slope as noise.

Exact mass alone rarely separates candidates above a few hundred daltons; the
relative heights of M+1 and M+2 usually do, which is why the finder scores them.
That only works on a spectrum that has the satellites: a product-ion scan
isolates the monoisotopic precursor in Q1, so run the finder on the TOF MS
survey channel. The program checks for this and says so instead of reporting
meaningless scores.

Mouse conventions in both panes: drag = rubber-band zoom, double-click = fit,
right-click = pyqtgraph menu (export image, axis options and so on).

## Manual

**Help ▸ Manual** (F1) opens the full manual inside the application, on the
page for the panel that has the focus — the Integration panel, a Batch QC
tab, a side panel of the Explorer — and every dialog has a **Help** button
that does the same for its own page. It is forty-odd
pages covering every workspace, every control and every number, linked to one
another the way a note vault is — each page ends with the pages that link to
it — with a search box that matches by prefix. **Help ▸ Export manual as
PDF…** prints the whole set as one A4 document. The pages are Markdown under
`milq/help/pages`, and a test fails the build on a link to a page that
does not exist.

The manual exists in **English and Brazilian Portuguese**: the switch is in
the manual's toolbar and remembered, and the search and the PDF follow the
language shown. A page not yet translated is shown in English with a note.
The application's own menus and dialogs stay in English, which is what the
pages describe.

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 -m milq.bootstrap --install   # fetches the .NET runtime (~30 MB) into ~/.dotnet
```

The second command is needed once, and only if there is no .NET 8 runtime on
the machine yet.

## Usage

```bash
python3 run.py
```

or open files directly:

```bash
python3 run.py demo_QC01.wiff demo_STD_L1.wiff
```

## From Python

`milq.api` is a documented, stable surface over the same code the
window runs — open a file, quantify a batch, explain a spectrum, search a
library, write a report, with no Qt in any signature and no window
anywhere:

```python
from milq import api

batch = api.Batch.from_project("Sphingolipids.oqproj")
rows = batch.process()
print(f"{len(batch.samples)} injections, {len(batch.components)} components, "
      f"{len(rows)} rows, {len(rows.found)} with a peak, "
      f"{len(batch.calibrate())} curves fitted")
rows.table().to_csv("sphingolipids.csv")
batch.export_xlsx("sphingolipids.xlsx")
batch.report("sphingolipids.pdf")
batch.close()
```

`api.VERSION` versions the promise: the names in `api.__all__`, their
methods and their keyword names keep meaning what they mean, and the
dataclasses returned gain fields rather than losing them. Everything
underneath is an internal and may move. The manual's **Python API** page
has the other two ten-line scripts — a folder of infusions explained and
filed into a library of your own, and a spectrum searched against one —
each with what it printed and how long it took.

## Compound list

The **Compounds** tab reads a CSV with these columns (only `name` and
`precursor` are required):

```csv
name,precursor,fragment,rt,window,tolerance,unit
12,13-DiHOME,313.2384,183.1391,14.7,0.6,0.02,Da
9,10-DiHOME,313.2384,201.1496,14.2,0.6,20,ppm
```

Further columns cover the quantitative side: `is` marks a component as an
internal standard, `internal_standard` names the one an analyte is reported
against, `response` picks between `area` and `ratio`, and `qualifier_of` plus
`ion_ratio` declare a confirmation transition and the ratio it should hold.

With no `fragment` the XIC uses the precursor itself. With no `rt` the search
covers the whole run. The method channel is picked by precursor **and** by
retention time — necessary in scheduled methods, where the same precursor
appears in more than one period. When the matched channel does not cover the
requested time window, the result comes back with zero area and a note, rather
than a peak from some other time.

## How the .wiff file is read

The `.wiff`/`.wiff.scan` format is proprietary and has no public
specification. The only libraries able to decode it are SCIEX's own
**Clearcore2** assemblies — the same ones ProteoWizard/msconvert uses. They are
redistributed by the open source package
[`alpharaw`](https://github.com/MannLabs/alpharaw) (MIT) and are managed .NET
assemblies.

Off Windows they normally do not work, because `Clearcore2.StructuredStorage`
opens the file through the Windows-only COM API `StgOpenStorageEx`. The module
[`milq/bootstrap.py`](milq/bootstrap.py) works around that:

1. it locates (or installs) a .NET 8 runtime;
2. it downloads from NuGet the compatibility assemblies .NET Core does not ship
   (`System.Configuration.ConfigurationManager` and its dependencies) and
   registers a resolver for them;
3. by reflection it flips the static field `StgStorage.sWindows` to `False`,
   making Clearcore2 use its managed implementation (OpenMcdf) instead of the
   COM path.

With that, `.wiff` files are read natively on Apple Silicon, with no Docker, no
Wine and no Analyst installed. Files are opened with
`OpenFileMode.ReadOnlyShared`, so a second window — or Analyst itself — can
still open the same file.

The LIPID MAPS Structure Database is redistributed by LIPID MAPS under
CC BY 4.0 and is downloaded on request, not bundled.

**On licensing:** the code in this project is MIT. The Clearcore2 libraries
belong to SCIEX and are *not* open source — they are redistributable, the same
arrangement ProteoWizard relies on. There is no fully vendor-free `.wiff`
reader today. If that matters in your context, the alternative is to convert
the files to mzML with `msconvert` and read the mzML with
[`pyteomics`](https://github.com/levitsky/pyteomics).

## Layout

```
milq/
  bootstrap.py           .NET runtime setup and the Clearcore2 patch
  wiff.py                WiffFile / Sample / Channel → numpy arrays
  components.py          the component table (CSV)
  method.py              processing method: components plus project defaults
  samples.py             batch entries: sample type, concentration, dilution
  session.py             the state shared by every workspace, and the project file
  matching.py            picking the acquisition channel that carries a component
  quantify.py            extraction, integration, ratios and the results set
  calibration.py         curve fitting and reading concentrations back
  statistics.py          grouped mean, SD and %CV
  chemistry.py           formulas, exact masses, isotope patterns, formula finder
  lipidmaps.py           local LIPID MAPS index and mass lookup
  precursor.py           measuring a precursor's accurate mass from the survey scan
  processing.py          smoothing, baseline, centroiding, peak detection, S/N
  ui/shell.py            the window and its workspace tabs
  ui/explorer.py         Explorer workspace
  ui/analytics.py        Analytics workspace
  ui/peak_review.py      the grid of one chromatogram per sample
  ui/results_table.py    results model, table and column chooser
  ui/integration_panel.py per-component integration settings
  ui/calibration_panel.py the calibration curve
  ui/acceptance_panel.py per-component acceptance criteria
  ui/statistics_panel.py grouped statistics
  ui/metric_plot.py      column against column
  ui/method_workspace.py Method workspace
  ui/samples_workspace.py Samples workspace
  ui/plots.py            chromatogram and spectrum panes (pyqtgraph)
  ui/chrom_area.py       stacked panes with linked time axes
  ui/component_list.py   read-only component list for the Explorer
  ui/mass_calc_panel.py  mass calculator
  ui/formula_panel.py    formula finder
  ui/lipid_panel.py      lipid candidates for a mass
  ui/annotate_dialog.py  reviewing batch annotation proposals
  ui/results_panel.py    results table
  ui/sample_info.py      sample information
  app.py                 entry point
tests/                   pytest suite
```

Run the tests with `python3 -m pytest tests`, and check the reader against your
own files with `python3 selftest.py`.

The data layer works on its own, without any UI:

```python
from milq import WiffFile

sample = WiffFile("demo_QC01.wiff").sample(0)
channel = sample.channels[65]                        # TOF PI, precursor 325.20
rt, tic = channel.tic()
rt, xic = channel.xic(183.0137, tolerance=0.02)      # fragment
mz, i = channel.spectrum(channel.scan_at_rt(13.14))  # one scan
mz, i = channel.spectrum_rt_range(13.0, 13.3)        # average over a region
```

Profile spectra come back with the zero-intensity points restored
(`add_zeros=False` turns that off). SCIEX strips them from the file, and
without them a line plot runs straight from one peak to the next, making the
gaps look like signal.

The chemistry layer is independent of both the UI and the vendor libraries:

```python
from milq import chemistry as ch

counts = ch.parse_formula("C18H34O4")                # 12,13-DiHOME
ch.monoisotopic_mass(counts)                         # 314.245709
ch.ADDUCTS_BY_NAME["[M-H]-"].mz(_)                   # 313.238433
ch.isotope_pattern(counts, ch.ADDUCTS_BY_NAME["[M-H]-"])
ch.find_formulas(314.2457, tolerance=5, unit="ppm")  # candidate compositions
```

## Data

The `.wiff`/`.wiff.scan` files are not tracked (see `.gitignore`): they are
large binaries that change with every run. Keep them wherever you like and open
them from the menu.

The files used during development come from a TripleTOF 5600 in negative mode,
a targeted MRM-HR method with 81 experiments across 2 periods: `TOF MS`
(100–2000) plus 80 `TOF PI` channels, one per precursor.
