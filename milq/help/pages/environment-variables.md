---
title: Environment variables
---
A handful of environment variables change what the application does
without a setting in a dialog. They are read when the program starts, so
set them before launching it — in a terminal with `export NAME=value`, or
for the installed application on macOS with `launchctl setenv NAME value`
before opening it from the Dock. Every `OPENQUANT_X` of the program's
earlier name is still read as `MILQ_X` where the new one is unset.

| Variable | Values | What it does |
|---|---|---|
| `MILQ_WIFF_CENTROID` | `local` (default), `sciex`, `0` | Who centroids a `.wiff` spectrum for labels, Explain, library search and a library record: this program, or SCIEX's own peak finder. `0` turns the vendor off as `local` does — the name MIL-X uses for the same switch. An mzML is always centroided by this program. |
| `MILQ_CACHE_DIR` | a folder | Where averaged spectra of unchanged files are kept when no project is open. |
| `MILQ_HOME` | a folder | Where the .NET runtime and the LIPID MAPS index live (default `~/.milq`, or `~/.openquant` where that already exists). |
| `MILQ_SETTINGS` | a file | An INI file used for the preferences instead of the system's store — what the test suite uses so it never writes into a person's own preferences. |
| `MILQ_REAL_DATA` | `1` | Runs the tests under `tests/real/`, which need acquisitions that are never in the repository. |
| `MILQ_TEST_WIFF` | a `.wiff` | The real IDA acquisition those tests and the command-line contract test read. |
| `MILQ_OPEN` | a `.oqproj` | Open this project at start. |
| `MILQ_OPEN_RAW` | a raw file or a folder | Open this file, or every `.wiff` and `.mzML` in this folder, at start, and show the Explorer. |
| `MILQ_SNAPSHOT` | a `.png` | Write the window to this picture after `MILQ_SNAPSHOT_DELAY` seconds (default 10), on workspace `MILQ_SNAPSHOT_TAB` (0–3, or `explorer`, `analytics`, `method`, `samples`), then quit — unless a probe is running. |
| `MILQ_UI_PROBE` | a `.json` | Write what the window shows to this file whenever it changes, and run the commands found in `<file>.commands` (below). |

## Driving the window from a script

An agent — or any script — should not have to drive the window by clicking
at coordinates read off a screenshot. With `MILQ_UI_PROBE=/tmp/probe.json`
the window writes, whenever anything changes, a JSON document of what it is
showing: the workspace, the project and whether it is saved, every open
sample (key, name, path, channels, any problem), the active channel (its
key, label, kind and precursor), the ticked channels, the extracted ion
chromatograms, the time range of the chromatogram, the spectrum's title,
the status line, and the outcome of the last command.

Commands go in `/tmp/probe.json.commands`: one JSON object, or a list of
them, each with an `id` and an `action`. The window reads the file within
half a second, deletes it, runs each command through the same code its
menus and buttons use, and writes the answer into the probe as
`last_command`: `{id, action, ok, message, completed_at}`. A command that
cannot be done is answered with `ok: false` and the reason; it never stops
the window. Write the file whole (a temporary name, then rename) so it is
never read half written.

| Action | Fields | Does |
|---|---|---|
| `select-workspace` | `name` (explorer, analytics, method, samples) or index | shows that workspace |
| `open-file` | `path` | opens a raw file, or a project |
| `select-channel` | `sample` (key, name or index), `channel` (index; omit for the sample's TIC) | ticks it and makes it active |
| `add-xic` | `mz` (a list or `"a, b"`), `tol`, `unit` (Da, ppm), `source` (`channel`, `ms1`, `ms2-all`, `gated:MZ[:TOL]`) | extracts as the Manual XIC tab does — see [[manual-xic]] |
| `clear-xics` | | removes them |
| `set-rt-range` | `start`, `end` (minutes) | the chromatogram's time range |
| `show-scan` | `scan` (0-based) | that scan of the active channel |
| `average` | `start`, `end` | the active channel averaged over that range |
| `export-chart` | `path`, `chart` (chromatogram, spectrum, contour), `format`, `scale`, `theme`, `background`, `type_size` | writes the chart as **Export as a picture…** would — see [[export]] |
| `save-project` | `path` (optional once the project has one) | saves it |

For example, to open a run, read one precursor's product scans across
every IDA slot, and keep the picture:

```
[{"id": "1", "action": "open-file", "path": "/data/run.wiff"},
 {"id": "2", "action": "select-channel", "sample": 0, "channel": 1},
 {"id": "3", "action": "add-xic", "mz": [136.0757], "tol": 0.01,
  "unit": "Da", "source": "gated:627.8457:0.05"},
 {"id": "4", "action": "export-chart", "path": "/tmp/xic.svg",
  "chart": "chromatogram", "theme": "light"}]
```

These are MIL-X's `MILX_UI_PROBE`, `MILX_OPEN`, `MILX_OPEN_RAW` and
`MILX_SNAPSHOT*`, with the same command-file protocol. For work that needs
no window at all, the command line is cheaper — see [[command-line]].

## Who centroids a `.wiff` spectrum

A profile spectrum has to become centroids — one stick per ion — before a
library can be searched with it, a structure scored against it or a record
written from it, and before a label can say a mass. For a `.wiff` the
instrument's software can do it: Clearcore2's spectral peak finder
(`MSExperiment.GetPeakArray`) fits each profile peak and reports its apex,
for one scan or for the average over a time range. MIL-Q's rule is to use
the instrument's arithmetic where the instrument offers it, and 1.1 was
first written with the vendor as the default. It was then measured, and
lost (below), so **this program's centroider is the default** and the
vendor's is a choice: with `MILQ_WIFF_CENTROID=sciex` the label on a peak
is the vendor's apex for the peak it sits on, **Centroid** draws the
vendor's sticks, and Explain, the library and a record take them. On the
command line `--centroid vendor` asks for them for one call.

The vendor is used only where the spectrum on screen is the reader's own: a
spectrum with a background subtracted, a difference from the run average
or the spray-masked average of a whole infusion is centroided by this
program, because the vendor never saw it.

What it was measured to change, on this machine:

- **Label masses.** On seventeen survey scans of a TripleTOF 5600 run, every
  label moved, by a median 1.5 ppm (90th percentile 4.1, at most 11.8).
- **Peak count.** One survey scan: 4,561 vendor peaks against 13,764 local
  maxima, at the same heights (median ratio 1.00 over the 200 tallest —
  MIL-X measured the vendor 1.27 times higher on a ZenoTOF 7600, so the
  instrument decides this, not the rule).
- **Library matching got worse on one batch.** On a sphingolipid
  product-ion batch, the same fragments measured in two injections
  differed by a median 7.0 ppm centroided here and 10.5 ppm by the vendor
  (83% and 73% within the 20 ppm search tolerance), and a record written
  from injection 01 was found first for injection 02 on 16 of 20 channels
  centroided here against 9 of 20 by the vendor — which is why it is not
  the default. The peptide screen ([[peptides]]) went the other way on
  a real IDA acquisition: somewhat more peptides accepted at 1% FDR from
  the vendor's centroids, the validation peptide found either way. `MILQ_WIFF_CENTROID=local`
  is what runs when nothing is set.

Quantitation reads extracted ion chromatograms and is not touched by any of
this. See [[spectral-library]] and [[how-wiff-is-read]].
