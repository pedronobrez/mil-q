---
title: Python API
---
Everything the application does can be done from a script. `milq.api`
is a small surface over the modules underneath: open a file, quantify a
batch, explain a spectrum, search a library, write a report — without a
window, and without knowing that the session is a Qt object or that the
readers differ.

```
from milq import api
```

It is the only part of the package with a stability promise. **The names in
`api.__all__`, their methods, and their keyword names** will keep existing
and keep meaning what they mean; the dataclasses that come back keep their
field names and gain fields rather than losing them. `api.VERSION` is the
version of that promise — 1 — and is raised only when it is broken.
Everything underneath (`milq.quantify`, `milq.session`,
`milq.report`, the readers) is an internal and may move. The escape
hatch is deliberate: `Batch.session`, `Acquisition.sample` and
`Acquisition.file` hand back the objects beneath, and using them is opting
out of the promise.

Nothing here takes or returns a Qt object except `headless()`. What comes
back is plain dataclasses and numpy arrays.

## What is on it

| | |
|---|---|
| `api.open(path)` | one sample of a `.wiff` or an `.mzML`: `samples`, `channels`, `tic()`, `spectrum(scan)`, `average(rt0, rt1)`, `xic(mz)`, `is_infusion`, `infusion_average()` |
| `api.Batch` | `from_project(path)`, or files and a component table; then `process()`, `results`, `calibrate()`, `statistics()`, `export_xlsx()`, `report()`, `save_project()` |
| `api.explain(spectrum, …)` | what a formula, a name or a molfile accounts for in a spectrum |
| `api.Library` | `open(msp)`, `search(spectrum)`, `add(spectrum, name)` |
| `api.infusion_report(source, out)` | the direct-infusion document for a file, a folder or one sample |
| `api.headless()` | the offscreen `QApplication` the report and the document are drawn with |

Results come back three ways: as rows (`results.rows`, each a `Result`
dataclass), as dictionaries (`results.dicts()`), and as a table of plain
values (`results.table()`) with `columns` and `rows` — which is what
`pandas.DataFrame(table.rows, columns=table.columns)` takes, without this
package depending on pandas.

## A folder of infusions, explained and filed

Open every acquisition in a folder, keep the ones that read as direct
infusions, explain each from its own name, and write a record of each into
a library of your own.

```python
from pathlib import Path
from milq import api

library = api.Library.open("bile-acids.msp", create=True)
for path in sorted(Path("/Volumes/NOBRE/Cyborg/Bileomics").glob("*.wiff")):
    with api.open(path) as run:
        if not run.is_infusion:
            continue
        spectrum = run.infusion_average()
        said = api.explain(spectrum, name=run.compound)
        library.add(spectrum, name=run.name, formula=said.formula,
                    adduct=said.adduct)
        print(f"{run.compound:8} {said.matched:3d}/{said.predicted:<4d} ions, "
              f"{said.share:.0%} of the spectrum — {said.basis or said.note}")
print(len(library), "records written to", library.path)
```

Measured on nine ZenoTOF bile-acid infusions: **1 min 39 s** reading them
off an external disk for the first time, **23 s** with the same files in the
page cache. Nine records written. Two of the nine explain nothing, and say why —
those two files target 839.56, which is not an adduct of the compound their
name claims (see [[measured-facts]]):

```
CA-d4      0/0    ions, 0% of the spectrum — 839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da — closest [M+K]+ at 451.2758 (+388.2842 Da), [M+Na]+ at 435.3019 (+404.2581 Da)
CA-d4     15/882  ions, 71% of the spectrum — C24H36D4O5 as [M+NH4]+ (read off the precursor — 430.34 is [M+NH4]+ of C24H36D4O5 (430.3465, -15.1 ppm); [M+H]+ would be 413.3200), predicted from its structure, named from the standards table
TDCA-d4   12/2241 ions, 87% of the spectrum — C26H41D4NO6S as [M+H]+ (read off the precursor — 504.32 is [M+H]+ of C26H41D4NO6S (504.3291, -18.1 ppm); [M+NH4]+ would be 521.3557), predicted from its structure, named from the standards table
```

Three things the script does not have to say. `run.compound` is the part of
the file's name before the first underscore, which is how these files are
named and what the [[infusion-report]] groups by; `explain` resolves that
name through the standards table, LIPID MAPS and the lipid shorthand, reads
`-d4` as four labels the name does not place, and picks the adduct off the
channel's own precursor. And the spectrum is centroided before a record is
written from it, because a record made of profile points describes the
instrument's peak shape rather than the compound — see
[[spectral-library]].

## A project, reprocessed and exported

```python
from milq import api

batch = api.Batch.from_project("Sphingolipids-reprocessado.oqproj")
rows = batch.process()
print(f"{len(batch.samples)} injections, {len(batch.components)} components, "
      f"{len(rows)} rows, {len(rows.found)} with a peak, "
      f"{len(batch.calibrate())} curves fitted")
rows.table().to_csv("sphingolipids.csv")
batch.export_xlsx("sphingolipids.xlsx")
batch.report("sphingolipids.pdf")
batch.close()
```

Measured on the 26-injection sphingolipid batch — 141 components, its
`.wiff` files on a local disk: **3 min 3 s** for the whole script with the
files read cold, **26 s** with them cached. It printed

```
26 injections, 141 components, 3666 rows, 2638 with a peak, 0 curves fitted
```

and wrote a 678 KB CSV, a 408 KB workbook and a 180-page PDF. No curves
because no injection in that batch is marked as a standard: `calibrate()`
fits from the samples the project calls standards and reports nothing where
there are none. `report()` renders through Qt and makes the offscreen
application itself, so a plain script needs no `headless()`; hold one open
by hand when a script writes several documents, or wants Qt for something
of its own. On Windows the offscreen platform is given the system's fonts
(`QT_QPA_FONTDIR`, unless already set), because on its own it has none
and a report came out as boxes where the words should be.

## A spectrum against a library

```python
from milq import api

library = api.Library.open("bile-acids.msp")
with api.open("/Volumes/NOBRE/Cyborg/Bileomics/CA-d4_TOFMSMS_Mix1.wiff") as run:
    spectrum = run.infusion_average()
print(f"{run.compound}, precursor {spectrum.precursor}, "
      f"{len(library)} records searched")
for hit in library.search(spectrum, top=5):
    print(f"  {hit.score:5.2f} {hit.reverse:5.2f} {hit.matched:3d} of "
          f"{hit.of_library:3d}  {hit.name}")
```

**12 s** cold and **1.9 s** warm against the nine records the first script
wrote, of which the precursor filter admits three:

```
CA-d4, precursor 430.35, 9 records searched
   1.00  1.00 200 of 200  CA-d4_TOFMSMS_Mix1
   0.29  0.56  22 of  42  CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1
   0.06  0.29   8 of  12  CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_mix1
```

Its own record scores 1.00, as it must. The other two are the same vial
under other activations, and they score 0.29 and 0.06: **a record does not
travel between collision energies**, which is the same finding
[[standard-history]] is built on. The same call takes an MSP of any size:
the full MassBank export, 139,006 records, reads in about five seconds and
is searched in milliseconds once the precursor filter applies — measured for
[[spectral-library]], which is the same code this calls.

`search` takes the precursor and the polarity off the spectrum itself, and
its tolerance defaults to the precision the precursor was written to: a
channel that says `647.5` is not known to three decimals. Pass `precursor`,
`polarity` or `precursor_tolerance` to override any of that.

## The infusion document from a script

```
doc = api.infusion_report("/Volumes/NOBRE/Cyborg/Bileomics", "infusions.pdf")
```

Every sample of the file or folder that reads as a direct infusion becomes
a section — the averaged spectrum, the accurate precursor, the explanation
and the best record of a `library=` you pass — and what comes back is one
`InfusionLine` per section, so the numbers are readable without opening the
PDF. Measured: 13.7 s for one infusion with a library, 202 s for all nine.
Nothing that reads as chromatography is included, and a source with no
infusion in it raises rather than writing an empty document. See
[[infusion-report]] and [[direct-infusion]].

## Where the numbers come from

Nothing here is a second implementation. `process()` runs exactly what
[[analytics-workspace]] runs, `report()` writes exactly what
[[report|the report]] writes, and the readers are the ones described in
[[how-wiff-is-read]]. Everything on [[measured-facts]] is as true through a
script as through the window — including the one difference between
formats, which is why a series is quantified in one of them.

See also [[command-line]] for what the application does without a script at
all.
