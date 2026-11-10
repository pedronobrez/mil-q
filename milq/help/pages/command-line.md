---
title: Command line
---
MIL-Q answers on the command line in two ways. **`milq <subcommand>`** is
the suite's shared command-line contract — the same subcommands, flags and
output as MIL-X's `milx`, made for scripts and agents, with no window and
no Qt (it runs over SSH and in a small Linux VM). **`milq` with no
subcommand** is the application: it opens the window, or runs one of its
own reports (`--selftest`, `--digest`, `--infusion-report`). From the
source tree the command is `python3 run.py`; an installed `pip install .`
puts `milq` on the path. On macOS and Linux the installed application's own
executable takes the subcommands too
(`/Applications/MIL-Q.app/Contents/MacOS/MIL-Q info run.wiff`). On Windows it
does not print them: `MIL-Q.exe` is a windowed program, which Windows gives
no output stream, so there the command line is `pip install` — or
`python run.py` from the source.

## The contract subcommands

The contract is `docs/CLI-CONTRACT.md` in both repositories, byte for byte
the same; where the two programs differ, the contract wins. In short:

```
milq selftest [FILES...]
milq info FILE [--sample N|NAME]
milq scans FILE [--source S] [--rt A:B] [--parent MZ[:TOL]] [--ms-level N] [--count]
milq xic FILE --mz LIST [--tol 0.01] [--unit Da|ppm] [--source S] [--rt A:B]
         [--smooth N] [--summary | --trace] [--reference MZ@SOURCE]
milq spectrum FILE [--source S] (--scan N | --rt A:B) [--subtract A:B]...
         [--centroid vendor|local|none] [--top N] [--min-rel 0.01] [--msp PATH]
milq isotopes FILE --mz MZ [--charge Z] --rt A:B [--formula F] [--adduct A]
milq batch-xic PATHS... --mz LIST [--tol] [--unit] [--source] [--rt-window C±W]
milq convert FILE [--out PATH] [--centroid vendor|local]
milq serve (--stdio | --inbox DIR) [--allow-root DIR]... [--idle-exit MIN]
```

`milq peptide …` — masses, fragments, annotation, digestion and a
target–decoy screen of peptides — is on its own page: [[peptides]].

Every subcommand also takes `--format json|tsv` (JSON by default; TSV is the
document's main table), `--quiet` (nothing on stderr but errors), `--cache
DIR` (where the sidecar index is kept) and `--require` (exit 4 when nothing
is found).

A **source** says which scans are read: `ms1` (the survey), `channel:N`,
`ms2-all` (every product-ion scan, merged by time), or `gated:MZ[:TOL]` —
only the product-ion scans whose own precursor lies within TOL (0.05 Da by
default) of MZ, from every channel. The gate is what data-dependent data
needs: see [[how-wiff-is-read]] and [[manual-xic]].

Every JSON document starts with `schema` (`mil-cli/1`), `tool`, `version`,
`command` and `input` (the absolute path and the sample). Masses are given
to 4 decimals (6 for theoretical values), retention times in minutes to 4,
intensities as the reader reports them, always with a point for the decimal
mark. The same call gives the same bytes. An error is a JSON document on
stderr, `{"schema": "mil-cli/1", "error": "...", "message": "..."}`, and an
exit code: **2** bad arguments, **3** a file that cannot be read or a
`.wiff` without its `.wiff.scan`, **4** nothing found (only with
`--require`; an empty result is otherwise not an error), **5** an internal
error.

### What each one answers

| Subcommand | Answers |
|---|---|
| `selftest` | the platform, whether the SCIEX libraries load, and for each file whether it opens and a spectrum reads |
| `info` | the samples, and every channel: index, kind (`ms1`, `ida-slot`, `dda-events`, `swath`, `mrm`, `product`), label, scans, mass range, precursor (none for an IDA slot), isolation width, collision energy, polarity |
| `scans` | one row per scan: channel, scan, cycle, RT, MS level, **the precursor that scan isolated**, its isolation window, CE, TIC, points; `--count` gives counts per channel |
| `xic` | per m/z: the apex (the tallest point of the trace) with its RT and height, the bounds (outward to the first point at or below 5% of the apex, or to the valley before a rise of a tenth of it), the area between them (trapezoid, no baseline), FWHM, points across the peak, and S/N with the noise convention named — the definitions are printed in the document and are MIL-X's; with `--reference`, Pearson r over the reference peak's span, the apex ΔRT and the height ratio |
| `spectrum` | the peak list (m/z, intensity, % of base) and every scan it was made from with its precursor; `--subtract` takes off the mean of background windows; `--msp` also writes an MSP record |
| `isotopes` | M, M+1, M+2… measured beside their expected masses, the spacing error, and the expected abundances when `--formula` is given |
| `batch-xic` | one row per file, sample and m/z — how blanks and a compound's spread over a batch are checked; files and folders alike, with every file left out (a `.wiff` without its `.wiff.scan`, a stray `.scan`) listed under `skipped` |
| `convert` | an mzML that keeps each scan's precursor — `scans` on it gives the same precursors |

### Examples, measured

On a TripleTOF 5600 HILIC IDA run (one survey, eight dependent slots, 1,986
cycles):

```
$ milq scans run.wiff --source gated:707.22 --format tsv | head -2
channel  scan  cycle  rt      ms_level  parent_mz  isolation          ce    tic       points
5        160   160    1.137   2         707.2197   706.7197;707.7197  35.0  656159.0  4447
```

Fifteen scans in four different slots isolated 707.22 over the run.

```
$ milq xic run.wiff --mz 707.22 --tol 0.02 --reference 365.104@gated:707.22
"summary": [{"mz": 707.22, "found": true, "apex_rt": 1.3425,
  "apex_height": 3946742.86, "fwhm": 0.1419, "points_across_peak": 7,
  "sn": 19915.11, "vs_reference": {"pearson_r": 0.8695,
  "apex_delta_rt": -0.0339, "height_ratio": 14.774225}}]
```

— the precursor in the survey against its strongest fragment read from the
scans that isolated it.

```
$ milq isotopes run.wiff --mz 707.22 --rt 0:20 --tol 0.02
M 707.2208 100 · M+1 708.2259 23.7 · M+2 709.2254 7.3 · M+3 710.2287 1.5
```

### What a call costs

The first call on a file reads its headers and, for `scans`, the number of
points in every scan; both are written to a **sidecar index** keyed on the
file's path, size and modification time (and its `.wiff.scan`'s), so an
edited file is never answered from a stale entry. Measured here: `scans` on
the IDA `.wiff` 3.8 s cold, 1.3–1.8 s warm; `info` on its 70 MB mzML 1.4 s
cold, 0.5 s warm. About a second of every `.wiff` call is starting .NET,
which is what `serve` saves. The index lives in `index/` under the
application's cache, or where `--cache` or `MILQ_INDEX_DIR` says; deleting
it is safe.

## serve: running commands on the Mac from somewhere else

An agent working in a Linux VM sees the shared folders but cannot type into
a macOS terminal, and on Linux the SCIEX libraries may not read a `.wiff` at
all. So the Mac runs the jobs: start this once in a Terminal on the Mac —

```
milq serve --inbox ~/Documents/mil-jobs --allow-root ~/Documents/MIL-data
```

— and it watches `~/Documents/mil-jobs/inbox/`. A request is one file,
`inbox/<id>.json`, written whole (as `<id>.json.tmp`, then renamed):

```
{"schema": "mil-cli/1", "id": "0001", "command": "xic",
 "args": {"file": "/Users/me/Documents/MIL-data/run.wiff",
          "mz": [627.8457], "tol": 0.01, "source": "gated:627.8457"},
 "format": "json"}
```

The answer is `outbox/0001.json`, byte for byte what `milq xic …` would
print, and the request moves to `outbox/0001.request.json`; a request that
failed goes to `failed/` with its error document. `"batch": [ … ]` runs
several in order in one file. A `--trace`, an MSP or a TSV is written under
`outbox/<id>/` and listed in the answer.

It is an allow-list, not a shell: only the subcommands above and `peptide …`
run, inside the server's own process — no shell, no subprocess. Every path
a request names must lie (symlinks followed) inside an `--allow-root` or the
inbox folder (`path_outside_roots` otherwise), and nothing outside `outbox/`
is ever overwritten. One job runs at a time; a job past its `timeout_s`
(1,800 s by default) is answered `timeout` and abandoned. `STATUS.json` says
what is running and how long the queue is; `log.jsonl` has one line per job
(id, command, arguments, start, end, outcome, outputs, peak memory) and
never file contents. Create `STOP` in the folder, press Ctrl-C, or start
with `--idle-exit MIN` to end it after the current job; a job found in
`running/` when it starts was interrupted and goes to `failed/`. The files
stay open between jobs (up to four at once), which is what makes the second
request on a file fast.

`milq serve --stdio` does the same over a pipe: one JSON request per line
in, one document per line out.

### Starting it at login (optional)

`packaging/macos/io.github.pedronobrez.milq-serve.plist` is a `launchd`
agent that starts the server at login. Edit the two folders and the path to
`milq` in it (`which milq` prints it), then:

```
cp packaging/macos/io.github.pedronobrez.milq-serve.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/io.github.pedronobrez.milq-serve.plist
```

`launchctl unload` with the same path stops it. Nothing needs it: the
Terminal command above is the whole of the requirement.

### On Linux

On Ubuntu 22.04 (arm64 or x86-64), as an ordinary user:

```
python3 -m pip install --user --upgrade pip setuptools
python3 -m pip install --user numpy pythonnet certifi
python3 -m pip install --user --no-deps alpharaw
python3 -m pip install --user --no-deps .
python3 -m milq.bootstrap --install
milq selftest run.wiff
```

The first line matters: Ubuntu's own pip and setuptools install this
package as `UNKNOWN-0.0.0`. `alpharaw` goes in with `--no-deps` because it
carries the SCIEX assemblies and declares readers this program never
imports; `pip install .[cli]` lists the same four. The bootstrap puts .NET
8 in `~/.dotnet` without sudo. Measured on Ubuntu 22.04 arm64 with 3 GB:
the `.wiff` reads, with the same numbers as on macOS — see
[[measured-facts]]. Where `selftest` says it does not, the mzML route is
complete: `milq convert` on the Mac, then every subcommand on the mzML.

## The application's own arguments

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
