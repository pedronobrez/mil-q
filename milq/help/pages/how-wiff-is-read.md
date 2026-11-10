---
title: How a .wiff file is read
---
The `.wiff` / `.wiff.scan` format is proprietary and has no public
specification. The only libraries able to decode it are SCIEX's own
**Clearcore2** assemblies — the same ones ProteoWizard's msconvert uses. They
are managed .NET assemblies, redistributed by the open-source package
alpharaw (MIT), and MIL-Q loads them through pythonnet.

## Off Windows

Clearcore2 normally does not work off Windows, because
`Clearcore2.StructuredStorage` opens the file through the Windows-only COM
API `StgOpenStorageEx`. The bootstrap works around that in three steps:

1. it locates a .NET 8 runtime, or installs one into `~/.dotnet`;
2. it downloads from NuGet the compatibility assemblies .NET Core does not
   ship — `System.Configuration.ConfigurationManager` and its dependencies —
   and registers a resolver for them;
3. by reflection it flips the private static field `StgStorage.sWindows` to
   `False`, which makes Clearcore2 use its managed structured-storage
   implementation (OpenMcdf) instead of the COM path.

With that, `.wiff` files are read natively on Apple Silicon, with no Docker,
no Wine and no Analyst installed. The culture is pinned to `en-US` while
the assemblies run, so a machine whose decimal separator is a comma reads
the same numbers as one whose separator is a point.

## Crossing from .NET to numpy

Clearcore2 hands back a .NET `double[]`, and every chromatogram, every
spectrum and every extracted ion chromatogram arrives that way. pythonnet
exports such an array as a plain C-contiguous buffer, so numpy can take the
whole thing in one copy; walking it with `list()` instead marshals one double
at a time across the managed boundary. Measured on one 1,143-point TOF scan
of a real acquisition: **0.194 ms the element at a time against 0.0009 ms
through the buffer**, the same doubles byte for byte. That crossing was 84%
of the cost of building a contour and two thirds of averaging a hundred
scans.

The array is **copied** out of the buffer rather than viewed through it. A
view would be faster still by a hair, and its memory belongs to the .NET
heap: correct while the array is alive, and a read of freed memory the moment
the collector takes it — which on macOS shows up as plausible numbers rather
than as a crash. Anything the buffer protocol refuses falls back to the
element walk, so a future Clearcore2 returning something else is slower and
never wrong.

## Shared access

Files are opened with `OpenFileMode.ReadOnlyShared`. Anything else takes an
exclusive lock, and a second window — or Analyst itself — cannot open the
same file.

## IDA: the precursor is per scan

IDA is SCIEX's data-dependent acquisition: a survey scan, then a number of
*dependent* experiments (`IDAType` Dependent or Confirmation) that each
cycle fills with one of the most intense ions the survey offered. Each
dependent experiment still declares a fixed mass (`FixedMasses`) like any
product-ion scan, and it is a placeholder — on a TripleTOF 5600 run the
eight slots declare 1.0, 2.0 … 8.0, the slot's number; on a ZenoTOF method
all 24 slots declare 829.5. The precursor actually isolated is on each
spectrum, `MassSpectrumInfo.ParentMZ`, and it changes almost every cycle.

So a dependent experiment is read as an **IDA slot**: it has no precursor
of its own, its tree label reads `TOF PI IDA slot 3`, and every scan
carries its own precursor (and its charge and collision energy, which in
IDA can roll with the precursor). A cycle whose `ParentMZ` is not positive
did not trigger the slot; it has no data points either. A slot is never
matched to a component by its placeholder, a spectrum shown from one says
which precursor it came from — `parent 627.8457` for one scan, or *mixes 37
precursors* for an average across cycles that isolated different things —
and Explain and the library search are handed the per-scan precursor, or
none when an average mixes them. To read one precursor's product scans
across every slot, use a gated source ([[manual-xic]]). *Export sample as
mzML* writes each scan's own precursor and leaves out the cycles a slot did
not trigger. SWATH windows, MRM and genuine fixed product-ion scans keep
their fixed mass. The rule is the one MIL-X follows (`docs/SCIEX-IDA.md`
there).

## What comes from the vendor and what does not

Totals, retention times and integrated areas that the vendor library
reports are used as reported: summing the stored points instead was measured
to move every integrated area by 2%. Profile spectra come back with the
zero-intensity points the library restores on the way out. Extracted ion
chromatograms are the one thing computed here rather than asked of the
library, and the one place the two disagree — see [[formats]]. A
spectrum is centroided by this program for labels, Explain and the
spectral library; `MILQ_WIFF_CENTROID=sciex` hands that to SCIEX's own peak
finder — see [[environment-variables]], which says why that is not the
default.

## Verified where

Reading a `.wiff` has been done, on real acquisitions, on macOS. Linux and
Windows run the test suite and start the application in continuous
integration, and a weekly job asks whether SCIEX's assemblies still load on
each — which does not depend on anything in this program — but the path
from "the assemblies load" to "an acquisition opens" is checked only on
macOS, and the Windows build's one real read was under CrossOver. See
[[installation]].

## Licensing

The code of MIL-Q is MIT. The Clearcore2 libraries belong to SCIEX and
are not open source — they are redistributable, the same arrangement
ProteoWizard relies on. There is no fully vendor-free `.wiff` reader today.
Where that matters, convert the files to mzML with msconvert and read the
mzML, which this program does with no vendor code at all.
