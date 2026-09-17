# Regressions over the real data

Every measured figure in `CLAUDE.md` and in the manual's *What was measured*
page came from running something on a real acquisition. Nothing in the rest of
the suite checks any of them: the fixtures are synthetic, by design, because
raw data is never committed. So the numbers are prose, and prose does not
fail. These tests are what makes a moved number fail.

They run only when the data is there, and the data is never here.

## Running them

```sh
MILQ_REAL_DATA=1 QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/real
```

or, equivalently, by selecting the marker:

```sh
QT_QPA_PLATFORM=offscreen python3 -m pytest -q -m real
```

Without either, everything under `tests/real` is **skipped** — which is how
CI, where no acquisition exists, runs `python -m pytest -q` unchanged. The
marker is applied in `tests/conftest.py` to every test in this directory, so a
new file here cannot forget it.

Each test also skips *itself*, naming the path it looked for, when its own
files are absent. A missing drive is a skip; a number that moved is a failure.

## Where the data is

`data.py` resolves each set from, in order: an environment variable, an
untracked `tests/real/data.local.json`, then a default where there is one.

| set | variable | default |
|---|---|---|
| five `260904_EICs_Isabela_*.wiff` — TripleTOF 5600, 81 channels | `MILQ_REAL_EICS` | the working directory (and, from a worktree, the main checkout) |
| nine ZenoTOF 7600 bile-acid infusions | `MILQ_REAL_INFUSIONS` | `/Volumes/NOBRE/Cyborg/Bileomics` |
| the 26-injection sphingolipid batch | `MILQ_REAL_BATCH` | none |
| its project, `.oqproj` | `MILQ_REAL_PROJECT` | none |
| eight ZenoTOF 7600 DIA runs | `MILQ_REAL_DIA` | none |
| two Thermo Orbitrap mzML (MTBLS13066) | `MILQ_REAL_ORBITRAP` | none |

Two of the six have a default because the repository already names them —
`milq/infusion.py` tabulates the infusions by path, and the `260904_EICs_*`
files sit in the working directory, ignored by git. **The rest are given no
default on purpose.** They are other people's unpublished acquisitions, one of
them named after the person who ran it, and a folder name is not something to
commit. Put them in `data.local.json`, which is ignored:

```json
{
  "batch": "/somewhere/Sphingolipids",
  "project": "/somewhere/Sphingolipids.oqproj",
  "dia": "/somewhere/DIA",
  "orbitrap": "/somewhere/mzml"
}
```

## What is asserted

| file | data | what it holds |
|---|---|---|
| `test_eics.py` | the five TripleTOF runs | the `--digest` fingerprint, 405/25/125 lines, the mzML round trip (577 TIC points from 23,722; 69 channels from properties, 81 from the cycle; identical spectra, chromatograms and peaks; extraction differing by a median 0.583% and never upwards), the stripped profile zeros |
| `test_sphingolipids.py` | the 26-injection batch | 3,666 rows and 2,638 peaks, one point per peak, the schedule, `check_method`, the 125 formulas and the 13 repairs that change no number, the three algorithms, the incremental identity, the lock mass, the control charts and floors, the detection margin, the own-library round trip, the workbook |
| `test_infusions.py` | the nine bile-acid infusions | the flatness, the spray mask, the noise floors, the ladder correction, CA-d4 at 14.0% → 63.6%, the margin against the impostors, the purity refusals, the summary of nine, the energy picks, the self-comparison, the mzML average |
| `test_dia.py` | the eight DIA runs | eight chromatographic verdicts, and 25 windows recovered from an mzML whose scan properties hold two |
| `test_orbitrap.py` | two Thermo mzML | the two stated gaps: a spray that ramps for ten seconds, and a stepped-precursor run |

## When one fails

A failure here is a **finding**, not a flaky test. Something the program reads,
integrates or scores has changed. Work out what changed and why before
touching the number; then move the constant in the same commit that explains
it, and say so in `CLAUDE.md`.

Where a figure had already moved when these tests were written, the *current*
value is asserted and the old one is quoted in the test's docstring, with what
is known about why. The ones that moved, as of this writing: the response
index (CLAUDE.md's "±18% with three exceptions" is now 0.437 – 2.081 with
four), the retention-time bands, the detection margin's before-and-after
(1,771 → 2,665 rows is now 1,647 → 2,638), the mass drift's error against its
formula (−4.0 → −4.8 ppm), one lock-mass refusal more than the five recorded,
and the top of the infusion correction range (+6.2 → +6.6 ppm).

## What is not covered

Measured figures that need something not to hand: the MassBank search (139,006
records, a 1.3 GB file nobody keeps), `standard_history` over the nine
infusions (9 records, 7 series), the batch comparison against the project as
it stood *before* the two retention times were corrected (that project was not
kept — the current one compares against itself instead), the report's page
counts, and everything about the packaged builds.
