---
title: Projects and files
---
## The project file

A project is one file, `name.oqproj`, JSON, readable by anything. It holds:

| Key | Content |
|---|---|
| `version` | the file format's version, currently 5 |
| `method` | the component table, the integration and acceptance defaults, the tolerance and units, the ion-ratio bands — everything on the [[method-workspace]] |
| `samples` | one entry per injection: the raw file's path and sample index, the display name, type, group, expected concentration, dilution and comment — everything on the [[samples-workspace]] |
| `results` | every row of the [[results-table]], including manual integrations, notes, the algorithm that produced each area, the points on the peak and, for a fitted peak, the model |
| `calibrations` | every curve: regression, weighting, coefficients, r², and each standard with whether it is used |
| `view` | how the Explorer's spectrum pane was left: each pinned spectrum as the *recipe* that made it — sample, channel, and scan or range of time, with the background window if one was subtracted — plus the label floor, Normalise, Mirror and Centroid, and the recipe of the spectrum that was live. See [[chromatograms-and-spectra]]; a project written before this existed opens with an empty pane |
| `audit` | what was changed by hand, in the order it was changed — see [[audit-trail]]; a project written before this existed has no key and opens with an empty trail |

It does **not** hold the raw data — the project points at the files by
path — nor the last algorithm comparison, which is derived and rebuilt on
request. **A pinned spectrum is saved as its recipe and never as its
points**, for the same reason: two whole-run averages of an infusion are
544,216 points, which is 20 MB written out and 3 KB as the two recipes that
made them, and a copy frozen into the document would stop being a reading of
the file it points at. They are read from the files again when the project
opens — measured on those two infusions, 5.9 s against the 3.2 s the files
take to open — and a pin whose file has moved stays in the list marked *not
available: file missing* rather than being dropped without a word.

A file that has moved is reported by name when the project opens, and the
project opens without it; see [[starting-a-project]].

## What sits beside a project

One directory, `name.oqcache/`, and it holds nothing you would lose by
deleting it: the averaged spectra of the infusions the project's files
carry, one `.npz` of masses and intensities each, so that a file which has
not changed is read once rather than on every **Measure**. It is beside the
project because the averages belong to that batch — found where the batch is
found, deleted with it, and left behind when the project is copied
elsewhere, since arrays that travelled without their files would be a
reading of nothing.

With **no project open** there is nowhere that belongs to them and the
system's own cache directory is used instead — see the table at the foot of
this page — which is the directory the operating system is entitled to
empty. The `cache/dir` setting overrules both.

An entry is retired when the file changes: the key holds the acquisition's
size and modification time and **its `.wiff.scan`'s**, which is where the
scans are. The directory is bounded at 512 MB, about a hundred and twenty
infusions, and over that the least recently used entries go first.
**File ▸ Clear cached spectra…** empties it and says how much went. Measured
on nine ZenoTOF infusions: 39.1 MB for the nine, and a second *Measure* in
about half the time of the first. See [[infusion-report]].

`*.oqcache/` is in the repository's `.gitignore`, with the raw data: it is
derived from files that are never committed and is rebuilt by asking again.

Projects written by the program under its earlier name, `.opvproj`, are
opened; nothing new is written with that suffix. A project written by an
older version opens in a newer one: fields the newer one added take their
defaults — a method saved before integration algorithms existed reads back
as *valley*, which is what it ran.

## Raw data

`.wiff` with its `.wiff.scan`, and mzML. Never modified. See [[formats]].
What a folder holds and what would go wrong in it — a companion that is
not there, a `.scan` under the wrong name, files no reader here can open —
is answered before anything is opened by *File ▸ Check a folder…*; see
[[checking-files]], which is also where the one repair, renaming a stray
`.scan`, is offered.

## CSV files

**The component table** — `Import CSV…` and `Export CSV…` in the Method
workspace; the layout and the accepted headers are on [[method-workspace]].

**Results** — `Export CSV…` under the results table writes the visible
columns of the visible rows; under the Statistics tab, the summary as
shown; in the Explorer, the Results tab's rows.

**Chromatograms and spectra** — `File ▸ Export chromatograms (CSV)…` writes
every trace on the Explorer's chromatogram as columns of time and
intensity; `Export spectrum (CSV)…` the spectrum on screen as m/z and
intensity.

## mzML

`File ▸ Export sample as mzML…` writes the selected sample spectrum for
spectrum; what survives the trip is on [[formats]].

## The report and the manual

`File ▸ Export report…` writes PDF or HTML — see [[report]]. `Help ▸ Export
manual as PDF…` writes this manual.

## Where the application keeps its own files

| What | Where |
|---|---|
| preferences | the platform's settings store, organisation `MIL-Q`, application `MIL-Q`: window geometry, last folder, folded panels, the start prompt |
| averaged spectra, with no project open | `~/Library/Caches/MIL-Q` on macOS, `%LOCALAPPDATA%\MIL-Q\Cache` on Windows, `$XDG_CACHE_HOME/milq` elsewhere — or wherever the `cache/dir` setting says |
| the .NET runtime, when installed by the bootstrap | `~/.dotnet` |
| downloaded NuGet assemblies, the LIPID MAPS index | `~/.milq`, or the directory named by the `OPENPEAKVIEW_HOME` environment variable |

Deleting `~/.milq` costs a download of the assemblies and the lipid
index the next time each is needed; nothing about any batch is in it.
Deleting the cache directory costs one cold **Measure**; nothing in it is a
measurement that cannot be made again from the files.
