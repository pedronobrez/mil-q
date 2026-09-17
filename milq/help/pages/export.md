---
title: Exporting to Excel and Skyline
---
Every table in the application exports itself as CSV, one file at a time.
Two exports go further: the whole batch as an Excel workbook, and the
method as a transition list another program can import. Neither replaces
[[report|the batch report]] — a report is what you keep, a workbook is what
you carry on working in.

## The workbook

**File ▸ Export workbook (Excel)…** writes one `.xlsx` with a sheet per
section. Only sections with something in them are written, so a project
that is a method and nothing else is two sheets rather than six, four of
them empty.

| Sheet | Holds |
|---|---|
| Results | every integrated row: sample, type and group, component, channel, m/z, RT and expected RT, area, height, width, S/N, points, algorithm, internal standard, ratio, concentration, accuracy, status, whether it was used or integrated by hand, its flags and its note — the columns of the [[results-table]], with nothing moved into a footnote |
| Calibration | per component: model, weighting, equation, slope, intercept, r², r, points used of points — see [[calibration]] |
| Statistics | the grouped means, standard deviations and %CV of the [[statistics]] page, by sample type |
| Batch QC | one row per control chart: centre, spread, S/N, floor, drift, ρ, how many injections were outside their limits, and the verdicts of [[batch-qc]] — the response index among them |
| Method | the component table of the [[method-workspace]], every column |
| Samples | the batch table of the [[samples-workspace]], and any sample whose spectra cannot be read |

Numbers are written as numbers, so a column sums, sorts and plots. Nothing
is rounded: a column shown to three decimals holds every digit the result
carries, which is the difference between this and a spreadsheet built by
pasting a report into one. Empty means not measured — not zero. Acquisition
times are text, because that is what the instrument wrote them as.

The writer is `milq/xlsx.py`: the format is a zip of XML parts, and the
part a table needs is small enough to write directly rather than take on a
dependency the installers would have to carry. Writing the same batch twice
gives byte-identical files.

**What was verified.** The tests unzip every file they write, parse every
part, and read the cells back — the types, the number formats, the bold
heading row, the frozen headings and the escaping of `<`, `&` and `>` —
rather than trusting that a zip of plausible XML is a workbook. Beyond the
suite, a workbook of a batch was read by two readers that had nothing to do
with writing it: `openpyxl`, which returned every value with its type and
format intact, and macOS's own Quick Look, which rendered it. And then
Excel itself: the workbook of the 26-injection batch (3,666 result rows,
398 kB) opened in Microsoft Excel for Mac, driven by AppleScript, which
read back the five sheets it holds — Results, Statistics, Batch QC,
Method, Samples; the batch has no calibration — the header row, the
first result row as written, and an area cell as a number rather than
text. LibreOffice has not been tried.

## The Skyline transition list

**Export for Skyline…** in the [[method-workspace]], beside
[[acquisition-schedule|Export schedule…]], writes the method as a
small-molecule transition list — the CSV Skyline's *Import Transition List*
reads.

| Column | From |
|---|---|
| Molecule List Name | the component's group, or `Molecules` |
| Molecule Name | the component's name |
| Precursor m/z | the precursor |
| Precursor Charge | the charge of the component's adduct, signed: `[M-H]-` is −1 |
| Product m/z | the fragment, or the precursor again where there is none |
| Product Charge | the precursor's polarity, singly charged |
| Explicit Retention Time | the expected retention time |
| Explicit Retention Time Window | twice the ± RT half width, since Skyline's window is the whole width |
| Note | `internal standard`, a qualifier's quantifier, and what a component is reported against |

Three of those the method does not carry outright. A component with no
**adduct** has no charge to write, and the cell is left empty rather than
filled with a guess: the status line says how many, and giving those
components an adduct fills them in. A **fragment's charge** is nowhere in
an MRM method, so it is written as singly charged with the precursor's
polarity — an assumption, and stated as one. A component with no
**retention time** is written without one, and Skyline will search the
whole run for it.

**The file has not been imported into Skyline here.** There is no copy of
Skyline on the machine this was written on. The column names are the
documented ones, read off the reader that consumes them in the ProteoWizard
source and off Skyline's own tutorials, and the values are the method's;
whether Skyline accepts the file is untested, and saying so is better than
implying otherwise. The [[design-principles]] say why. The same reservation
applies to the [[acquisition-schedule]], for the same reason.
