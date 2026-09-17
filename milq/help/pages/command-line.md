---
title: Command line
---
The installed application and the source tree answer to the same
arguments. From the source tree the command is `python3 run.py`; from an
installer it is the executable inside the application — on macOS
`/Applications/MIL-Q.app/Contents/MacOS/MIL-Q`.

```
MIL-Q [files...] [--selftest] [--digest]
MIL-Q --infusion-report PATH... --out FILE [--library FILE]
          [--components FILE] [--html] [--per-compound] [--csv FILE]
```

| Argument | Effect |
|---|---|
| `files` | raw data files to open — `.wiff`, `.mzML` — into the window, in place of the start prompt |
| `--selftest` | open the files, report what was read, and exit without a window |
| `--digest` | print a numeric fingerprint of each file, for comparing one build against another, and exit |
| `--infusion-report` | report every direct infusion in the given files and folders, and exit without a window |
| `--out` | where that report is written; required with `--infusion-report` |
| `--library` | an MSP or MGF of your own to search each averaged spectrum against |
| `--components` | a project (`.oqproj`) or a components CSV, for the formulas the compounds are explained from |
| `--html` | write the report as HTML rather than PDF |
| `--per-compound` | one document per compound rather than one with a section each |
| `--csv` | also write the summary table, one row per infusion |

## --selftest

Prints the version and the platform, whether the LIPID MAPS index is
installed, whether the SCIEX libraries are ready and where the .NET runtime
was found — or why they are unavailable — and then, for each file, how many
samples and channels were read, or the exception that stopped it. It is
what the installers run on themselves before being shipped, and the first
thing to run when a file will not open.

## --digest

For each file, one line per channel with a short hash of its time axis and
its total chromatogram, one per spectrum sampled, and one per integrated
peak with its area to nine decimals. Two builds that read the same file
should print byte-identical output; the release process compares the macOS
build, the Windows build and the source tree this way. From source on
macOS, from the CI disk image and from the Windows installer under
CrossOver, five real acquisitions gave the same output to the last digit.
The Windows build writes CRLF line endings, which is the only difference
`diff` will show.

## --infusion-report

The [[infusion-report]] for a whole folder, with nothing opened in the
[[explorer]]:

```
MIL-Q --infusion-report ~/data/bile-acids \
          --out ~/reports/bile-acids.pdf \
          --library ~/library/own-bileomics.msp \
          --components ~/methods/bile-acids.csv \
          --csv ~/reports/bile-acids.csv
```

A path may be a folder or a single file, and there may be several. The folder
is looked over by [[checking-files]] first, so a `.wiff` without its
`.wiff.scan` is named and **not opened** — its spectra cannot be read and the
report is a spectrum — and a `.wiff2` beside the data is reported as ignored
rather than read. Each remaining file is opened on its own and closed again
before the next one, so a folder of thirty infusions never holds thirty
readers. A run that is not an infusion is left out with the figures that say
so, in the words [[direct-infusion]] uses.

Every skip is printed with its reason, then the same summary line the
Infusions tab shows, then what was written. The exit status is 0 when at
least one document was written and 1 otherwise, so a script can tell an empty
folder from a reported one.

The document **opens on the folder rather than on its first compound**: the
cover in front of the per-compound pages names the folder, the day and the
version, prints every infusion on one row, sums those rows sentence by
sentence, lists what was left out and where each compound is — see *The cover
of a folder report* in [[infusion-report]]. It is in the same PDF as the
pages it introduces. `--per-compound` is the exception: there the pages are
in one file per compound, so the cover is written on its own as
`<out>-cover`, and lists no page numbers because it has none for them.

On a machine with no display — a build server, a session over ssh — set
`QT_QPA_PLATFORM=offscreen`: the document is drawn and laid out through Qt
whether or not anything is shown. On Windows that platform finds no fonts
on its own and drew every glyph as a box — a 47-page report with no text
in it — so the application points it at the system's font directory
(`QT_QPA_FONTDIR`) unless that is already set.

Measured on nine ZenoTOF bile-acid infusions, from source on macOS, with the
three CID runs as a library of one's own and the three formulas as a
components CSV: **31 s** for the whole folder — nine files read and one
58-page PDF written, a two-page cover and 56 of sections — at **1.2 GB** peak
resident memory (two runs: 30.8 and 31.5 s, 1.42 and 1.40 GB; measured again
for [[integration]], 52 and 42 s at 1.15 and 1.21 GB), and
`--per-compound` four documents of the same 58 pages, the cover two of
them and one document per compound the other 56. Written without a cover the
same nine sections come to 56 pages, so the cover costs the two it is. The
seconds are the one figure here that is not the program's: the same run on
the same files has taken anything from 27 s on an idle machine to 255 s on a
busy one. What is stable is
what it did — nine files read, none skipped, 58 pages — and what it held.
Nothing was skipped: all nine read as
infusions, including the two `_TESTEARTIGO` acquisitions, whose rows say what
is wrong with them rather than leaving them out. The summary line is the
Infusions tab's, to the digit: *3 compound(s) in 9 infusion(s); 4 of 9
precursor(s) confirmed within 25 ppm; 34 of 458 predicted ion(s) found across
7; 4 with an own record above 60*, and the cover's own paragraph sums the
same rows a sentence at a time — *4 of 9 precursor(s) confirmed within 25
ppm; 5 not: 2 whose method isolates 839.56, 2 with too little precursor
surviving fragmentation, 1 at +30.3 ppm.* and two more like it.

## The bootstrap

```
python3 -m milq.bootstrap --install
```

installs a .NET 8 runtime into `~/.dotnet` when the machine has none, and
fetches the compatibility assemblies Clearcore2 needs. It is needed once,
from source; the installers carry what they need. See [[installation]] and
[[how-wiff-is-read]].

## Scripting the data layer

The reader and the numerics work without the interface:

```
from milq import WiffFile

sample = WiffFile("run.wiff").sample(0)
channel = sample.channels[65]
rt, tic = channel.tic()
rt, xic = channel.xic(183.0137, tolerance=0.02)
mz, i = channel.spectrum(channel.scan_at_rt(13.14))
mz, i = channel.spectrum_rt_range(13.0, 13.3)
```

`milq.raw.open_raw(path)` returns the right reader for either format
with the same surface. `milq.quantify.process(entries, method)` runs
a method over a batch and returns the results set; `milq.report`
writes a report from a session; `milq.compare.compare_algorithms` runs
the comparison. The chemistry layer — `milq.chemistry` — parses
formulas, computes masses and isotope patterns and searches compositions,
and depends on neither the interface nor the vendor libraries.

Those are the modules themselves, and they are free to move. For a surface
that will not — a batch reprocessed and exported, a spectrum explained, a
library searched, a report written, in ten lines and with a stability
promise attached — use [[python-api]] instead.
