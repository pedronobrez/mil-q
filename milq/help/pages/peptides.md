---
title: Peptides on the command line
---
`milq peptide …` is a peptide toolkit with no window: masses, fragments,
the annotation of a spectrum, a non-specific digest, and a screen of every
data-dependent MS2 scan of a batch with a target–decoy false discovery
rate. It was written for endogenous peptides in HILIC ESI+ IDA data, and
nothing in it is specific to one sample type or protein. Every output follows the [[command-line]] contract: a `mil-cli/1`
document in JSON, or `--format tsv`. Every mass is monoisotopic.

## Writing a sequence

| Written | Means |
|---|---|
| `QPLAPVHNPISV` | the residues; I and L are isobaric (113.084064) and are reported as such |
| `pEPLAPVHNPISV`, `pE-PLAPVHNPISV` | `pE` is a pyroglutamate residue (111.032028, from Q or E alike) |
| `[pyroGlu]QPLAPVHNPISV`, `pGlu-QPLAPVHNPISV` | pyroGlu on the N-terminal Q (−17.026549) or E (−18.010565) |
| `S[Phospho]` | on S, T or Y, +79.966331 |
| `M[Oxidation]` | +15.994915 |
| `…V[Amidated]` | C-terminal amide, −0.984016 |
| `[Acetyl]-PEPTIDE` | N-terminal acetyl, +42.010565 |

## The subcommands

| Subcommand | What it gives |
|---|---|
| `peptide mass SEQ` | the monoisotopic mass and m/z at charges 1–4 (`--charges`) |
| `peptide fragments SEQ` | b, a and y ions, b−H2O and y−NH3, internal b-type ions and immonium ions, at charges 1–3, each named (`b3`, `y5+` for 2+, `int-PLA`, `imm-H`) |
| `peptide annotate SPECTRUM --seq SEQ --charge Z --tol-ppm 20` | every matched ion with its ppm error, a coverage map (`b`, `y` or `|` for both, `.` for neither, between each pair of residues), the share of the intensity explained, and the tallest peaks left unexplained. The spectrum is a TSV of m/z and intensity, an MSP, or a `milq spectrum` JSON — or `--from FILE --source gated:MZ --rt A:B` reads it from the raw file itself |
| `peptide digest FASTA --proteins ACC,… --nonspecific --len 4:40 --mods pyroglu-q,phospho-st,ox-m --max-mods 3 --charges 1-4` | every sub-sequence of the proteins with every modified form the options allow, with m/z per charge |
| `peptide screen FILES… --fasta F --proteins ACC,… [digest options] --ppm 15 --decoy reverse` | the screen, below |
| `peptide components SCREEN.tsv --out COMPONENTS.csv` | the accepted peptides as a component table for [[method-workspace|the method]] |

The digest's modifications are `pyroglu-q`, `pyroglu-e`, `phospho-st`,
`phospho-sty`, `ox-m`, `amidated` and `acetyl`.

## The screen

For every MS2 scan of every file, the precursor that scan isolated — its
own, per scan, which is what [[how-wiff-is-read|an IDA slot]] carries — is
refined from the survey scan at that time, and matched against the digest
within `--ppm` at the stated charge (or 1–4 where the file states none),
with isotope errors of −1, 0 and +1 allowed, because the instrument
sometimes picks the 13C peak. Each candidate is scored on the scan's
centroids (this program's, or SCIEX's peak finder with `MILQ_WIFF_CENTROID=sciex`, see
[[environment-variables]]): b, y, a, b−H2O and y−NH3 ions within
`--fragment-ppm` (20), the share of the intensity they explain, the
longest run of consecutive b or y ions, and a hyperscore in X!Tandem's
manner (the log of the matched b and y intensity plus the log factorials of
their counts). A candidate needs `--min-matched` (4) ions. The best
candidate of each scan is kept, target or decoy; the decoys are the
proteins reversed and digested the same way, and the q-value is the lowest
decoy-to-target ratio at or below each score.

It writes three files beside `--out PREFIX`: `PREFIX.tsv`, one row per
peptide and charge ranked by q-value (peptide, modifications, protein,
start–end, charge, m/z, RT, ppm, isotope error, ions matched, longest
series, share explained, score, q-value, number of scans, files, and the
strongest fragment); `PREFIX.json`, the summary; and `PREFIX.msp`, the best
spectrum of every accepted peptide — usable as a library in MIL-Q's own
[[spectral-library]], in MIL-X and in MS-DIAL. `peptide components` turns
the TSV into components (the precursor at its charge, the strongest
fragment, the retention time) so a batch is quantified by the ordinary
path.

## What it was measured to do

On a real TripleTOF 5600 HILIC ESI+ IDA acquisition, screening one protein
non-specifically from 4 to 40 residues with pyroGlu-Q, phospho-S/T and Met
oxidation, up to three per peptide: 2,364 MS2 scans against 72,406 target
candidates and their decoys in 11 s; over four such acquisitions, 10,180
scans in 44 s at 450 MB. The peptide the screen was asked to validate was
found at q < 0.01 in every one of them, with this program's centroids and
with SCIEX's (the vendor's took 75 s and accepted somewhat more peptides at
1%). The scorer was not tuned on it; the test in `tests/real/` that checks
it reads the peptide, the protein and the files from an untracked local
file, because the acquisitions are someone else's.

What a one-protein search means: the FDR is the false discovery rate among
matches to that protein's peptides, against its own reversal — it says
which spectra are that protein's peptides rather than chance, not that nothing
else in the sample explains them better. Search the proteome, or the
proteins the sample can hold together, before claiming a peptide is
unique.
