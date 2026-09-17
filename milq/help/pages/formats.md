---
title: File formats
---
Two formats are read: SCIEX `.wiff` and mzML. One is written: mzML.

## .wiff

A SCIEX acquisition is two files, `name.wiff` and `name.wiff.scan`, and
both are needed — the first holds the method and the index, the second the
spectra. The `.wiff` alone opens: the sample list, the method, the total
ion chromatogram of every channel and the acquisition parameters are in
it, and the tree fills as if nothing were wrong. What is not in it is the
scan data, so the first spectrum asked for fails — and with it every
extracted ion chromatogram, the base peak chromatogram, the contour and
the quantitation, which all read the scans. MIL-Q tries one spectrum
when the file is opened and, if it fails, says so at once: a warning when
the file is added, a *⚠* in front of the sample in the tree, with the reason on hover, the reason in the spectrum pane's title where a spectrum would be,
and a note on any result row that could not be extracted. The message
names the file that has to be beside the `.wiff` and, when the folder
holds a `.scan` that belongs to no `.wiff` there, names that too — a
companion renamed by hand (`name.wiff_mix1.scan` next to `name_mix1.wiff`)
is the usual way the pair comes apart, and renaming it to
`name_mix1.wiff.scan` is the whole repair — which [[checking-files]] finds
and offers before the file is opened at all. A `.wiff2` beside the pair is
not read here, and nothing is lost by that — see the section below for what
was measured. They are read through SCIEX's own Clearcore2 libraries, which are
the only software able to decode the format and are redistributed by the
open-source package alpharaw. How they are made to work off Windows is
described in [[how-wiff-is-read]].

A `.wiff` can hold several samples; each is opened as its own entry. Files
are opened in shared read-only mode, so Analyst or a second MIL-Q window
can open the same file at the same time.

Every acquisition channel — every experiment of the method — is listed
with its type, precursor, mass range and collision energy, as the file
declares them. Totals, retention times and integrated areas that the vendor
library reports are used as reported; nothing is recomputed from the stored
points where the instrument's own figure exists, because summing the stored
points instead was measured to move every integrated area by 2%.

## .wiff2

A SCIEX OS instrument writes a third file beside the pair, `name.wiff2`,
and on a ZenoTOF 7600 an acquisition arrives as a trio. It is not opened
here, and the reason is measured rather than assumed.

It is not the same kind of file. A `.wiff` is an OLE compound document; a
`.wiff2` is a password-protected SQLite database. Asked to open one,
Clearcore2 says `Invalid OLE structured storage file`, and its own
`CheckDataFileIntegrity` calls it `NotWiffFile`. That was true of all nine
`.wiff2` in the folder this was tested on, with the companions beside them
and with each companion taken away in turn, and it stayed true when the
file was renamed to `.wiff` — so it is the container, not the extension.

More to the point, there is nothing in it to read. The Clearcore2 assembly
that writes a `.wiff2` declares the whole schema, and it is seven tables:
`header`, `sample`, `method`, `device_method`, `device_descriptor`,
`device_identifier` and `method_parameters_info`. Not one column holds a
spectrum, a peak, an intensity or a chromatogram. What the `header` table
holds is `wiff_hash`, `scan_hash` and `scan_size` — the identity and size
of the two files beside it. The `.wiff2` is the acquisition's method and
its record of its companions, not its data.

The file sizes say the same thing. Across those nine acquisitions the
`.wiff.scan` — which really does hold the spectra — spans 1.67 to 9.88 MB,
a factor of 5.9, while the `.wiff2` spans 303 to 406 kB, a factor of 1.34,
over five distinct values. The `.wiff2` tracks the `.wiff` (correlation
0.989), not the scan data (0.748).

So the `.wiff` of the same name holds the acquisition, and opening it
loses nothing: read with the `.wiff2` beside it and with the `.wiff2`
deleted, the same file gave the same sample, the same single experiment,
the same 473-point total ion chromatogram and the same 13,705-point first
spectrum. A `.wiff2` with no `.wiff` beside it is an acquisition that
cannot be opened here at all, and no reader could be written for it from
this container — the spectra are not in it. [[checking-files]] says which
of the two cases a folder is in before anything is opened.

## mzML

mzML is the open format ProteoWizard's `msconvert` writes from any vendor's
files, so a Thermo `.raw`, an Agilent `.d` or a Bruker `.tdf` gets in by
being converted first. Both profile and centroid spectra are read, and
zero-intensity points a vendor stripped from a profile are restored — see
[[chromatograms-and-spectra]] for why that matters.

What the file states about each scan is read and shown, and none of it is
guessed: the polarity from `positive scan` or `negative scan`, the precursor
from `selected ion m/z` — or, where a converter wrote only an isolation
window, from its centre — the charge from `charge state`, the collision
energy, and **how the precursor was broken** from the `activation` element.
That last one is the thing a `.wiff` does not carry: SCIEX's library exposes
the energy and nothing that names the method, so a `.wiff` channel's
activation is blank while a converted Thermo file's says *beam-type
collision-induced dissociation*. Twenty-two electronvolts of that and
twenty-two of electron transfer are different experiments on the same
precursor, so the activation separates two channels that nothing else in the
scan tells apart. It all appears under the channel in the [[explorer]].

The instrument's name is read three ways, because vendors write it three
ways: as its own controlled-vocabulary term with an empty value, as the
generic *instrument model* term with the model in the value, and — which is
how ProteoWizard writes every Thermo file — in a `referenceableParamGroup`
that each instrument configuration only points at. Two real Thermo files,
an LTQ Orbitrap Elite and ProteoWizard's own LTQ FT example, both said
*unknown* until that reference was followed.

Averaging a range of scans **adds each scan up at the masses it measured**,
and puts nothing anywhere else. That is worth stating because the obvious
alternative is wrong: two scans of a time-of-flight do not share a mass
axis, so the average is over the union of theirs, and interpolating each
scan onto that union draws a straight line across every stretch a
zero-stripped profile spectrum has no points in — signal at masses where the
instrument reported none. Measured against SCIEX's own averaging of the same
146 scans over the same 221,847 masses, interpolation put 220,222 of them
higher and totalled **3.31 times** the vendor's spectrum; centroiding it
gave 670 peaks where the vendor's average gives 424. Adding the scans up
where they were measured reproduces the vendor's averaged spectrum exactly —
largest difference at any mass 0.0 — and is right for a centroided file too,
where interpolating between two sticks is worse still.

mzML has no notion of an acquisition *channel*. The channels are inferred,
and inferred from the order of acquisition rather than only from the
properties of the scans: a method can have two experiments that agree on MS
level, precursor, collision energy and mass range, and grouping by
properties alone gave 69 channels where the acquisition had 81. A scheduled
method repeats its experiments in a fixed cycle, so position in the cycle is
the experiment. The file this was developed against is a cycle of 44 run
339 times followed by a cycle of 37 run 238 times — 44 + 37 = 81 channels,
44 × 339 + 37 × 238 = 23,722 spectra. A cycle has to repeat at least four
times to be believed; data-dependent acquisition has no cycle and falls back
to the scan properties.

The **run's** total ion chromatogram follows the same answer. Where there is
a cycle, the experiments of one period are added cycle by cycle, because
that is what the instrument reports — 577 points for those 23,722 spectra,
not 23,722. Where there is no cycle, it is one point per spectrum, which is
what a data-dependent run's own software draws. Nothing else will do: a real
Thermo direct infusion stepping its isolation window across the precursor in
0.02 Da increments has 164 spectra and 82 inferred channels of one, two and
five scans, and grouping those by how many scans each had — the rule that
stood before — gave the run **eight points for 164 spectra**. The total was
right and the shape was fiction, and the shape is exactly what
[[direct-infusion]] reads to decide what a sample is.

An extracted ion chromatogram needs every scan of its channel, and each
scan is decoded straight from the file's bytes — the arrays' positions
and encodings are found the first time a scan is wanted, and the XML
parser is not run again for it. A channel once decoded is kept for the
next component that asks, under a budget of 256 MB for the whole
process, oldest channel out first; the file itself is mapped rather than
read into memory, so a batch of many open files costs the system's file
cache and not the application's. Measured on a synthetic 81-channel run
of 19,440 spectra on Windows 11: an extraction went from 32 ms to 11 ms
where the channel had to be decoded and to 0.1 ms where it had been, and
integrating 80 components over six such injections from 15.5 s to 4.8 s.
Nothing in the numbers changes: the same points are summed. The same measurement on a
real 107 MB acquisition on an Apple M4: all 23,722 spectra decode in 0.41 s
against 1.09 s the old way, and the 81 channels' extracted and base peak
chromatograms in 0.21 s against 1.03 s — with every one of 7,608,772 values
identical between the two routes.

## Infusions from mzML

An infusion from another instrument goes through the whole of
[[direct-infusion]] — detection, the average of the run, [[lipid-maps]], the
[[spectral-library]], the [[infusion-report]] — the same as a `.wiff`. The
verdict reads chromatograms and never a spectrum, so it cannot depend on the
format at all.

Checked end to end on one real ZenoTOF 7600 infusion of cholic acid-d4,
read three ways: from the `.wiff`, from the mzML this program exports from
it, and from that mzML re-written the way ProteoWizard writes a Thermo
`.raw` — Thermo scan ids, times in seconds, an isolation window, a charge
state, `beam-type collision-induced dissociation`, and nothing at all saying
which experiment a scan belongs to. All three give **one product-ion
channel**, precursor 430.34 at 22 eV, 146 scans over 0.61 min, both flatness
figures **1.0000**, an averaged spectrum whose base peak is 377.3018 at
9,618.10 counts and whose total is 360,596.6986, **424** centroids, **42**
peaks above the noise share, the precursor surviving at 430.3489 and 9,415
counts, and the formula explaining **8 of 56 predicted ions and 63.63%** of
the spectrum. Three differences, all of them the file rather than the
reader:

| | `.wiff` | its mzML | Thermo-shaped mzML |
|---|---|---|---|
| channel name | `TOF PI` | `TOF PI` | `MS2` |
| activation | *(not carried)* | collision-induced dissociation | beam-type collision-induced dissociation |
| points in the averaged spectrum | 289,103 | 221,847 | 221,847 |

The name is the acquisition method's, which mzML has nowhere to put — so
this program's own export keeps it in a parameter of its own and anybody
else's file is described by its MS level. The point count is the stripped
zeros: same masses wherever anything was measured, and the zeros put back
when the spectrum is drawn.

Two things a converted infusion can still be refused for, and both are the
acquisition rather than the format. A run of fewer than 120 scans is *too
short to tell* — a real Orbitrap infusion of 108 one-and-a-half-second scans
is under it. And [[direct-infusion]]'s figures ask whether the ion current
stays up, so an acquisition that deliberately sweeps — stepping the
isolation window across the precursor — is read as chromatographic, because
its ion current genuinely rises and falls: the real one measured above reads
**0.0123** where 0.75 is needed. **Average whole run** gives the same view
by hand on any sample.

## Writing mzML

`File ▸ Export sample as mzML…` in the Explorer writes the selected sample
spectrum for spectrum, with the total ion current the instrument reported
rather than one recomputed here. What survives the trip was measured on
five real 81-channel acquisitions read back through this program, and
cross-checked against ProteoWizard in both directions:

| | |
|---|---|
| spectra | identical, every channel, to the last digit |
| channel chromatograms | identical, every channel |
| the run's total ion chromatogram | identical, 577 points |
| integrated peak areas | identical |
| extracted ion chromatograms | **differ**, see below |

## The one difference: extracted ion chromatograms

SCIEX's own extraction counts part of a peak whose measured points fall
just outside the mass window; this program sums the points inside it. On
that acquisition the difference is a median 0.58% of peak height, at most
12%, and always lower here. End to end, quantifying one component from the
`.wiff` and from its mzML gives the same retention time and peak width and
an area 0.54% apart.

Two attempts were made at reproducing the vendor's edge rule. Both were
wrong: the second looked right on the windows it was derived from and, on
other windows, was better on 41 channels and worse on 38 — a coin toss. So
the plain rule ships and this paragraph is the warning. **Quantify a series
in one format.** See [[measured-facts]].

## Which format for what

| Task | Use |
|---|---|
| review and quantify SCIEX data | `.wiff` directly |
| data from another vendor | msconvert to mzML, then open the mzML |
| a series that must be compared over time | one format for the whole series |
| handing data to software that cannot read `.wiff` | export as mzML |

Raw files are never modified. Everything the program adds — sample types,
concentrations, the method, results — lives in the project file, see
[[projects-and-files]].
