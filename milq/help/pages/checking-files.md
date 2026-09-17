---
title: Checking files before opening them
---
Most of what goes wrong with a folder of acquisitions is visible in the
names of the files, before anything is read. *File ▸ Check a folder…*
looks, and so does adding files: when the check finds something, it is
shown first and nothing is opened until you say so.

Nothing is opened by the check itself. It lists the folder, asks whether
each file exists and can be read, and says what it found — no file is
decoded, so a folder of a hundred acquisitions is checked in the time it
takes to list it.

## What it looks for

| Finding | What it means | What to do |
|---|---|---|
| a `.wiff` with no `.wiff.scan` beside it | the acquisition opens and looks whole — method, sample list, every channel's chromatogram — and every spectrum, extracted ion chromatogram and integration fails. See [[formats]] | put the companion back; if the folder holds a stray, the row below offers the rename |
| a `.scan` belonging to no `.wiff` in the folder | usually the companion of one of these files, renamed by hand: `name.wiff_mix1.scan` beside `name_mix1.wiff` | **Rename** it to the name the `.wiff` is looking for |
| `.wiff2` files | the acquisition's method and the hashes of its two companions — measured to hold no spectrum, peak or chromatogram at all, and not read here. See [[formats]] | nothing, when the `.wiff` of the same name is beside it: that holds the same acquisition and is what is opened. With no `.wiff` beside it the acquisition cannot be opened, and the `.wiff2` cannot stand in for one |
| files of another vendor's format | `.raw`, `.d`, `.tdf` and the rest are not read here | convert them to mzML with ProteoWizard's `msconvert` |
| a file already open | adding it again would put a second copy of every sample in the batch | it is left out; close the batch first to read it again |
| a file that cannot be read, or is not there | permissions, or a file that moved since it was named | fix the permissions, or add it again from where it is now |

## The rename, and why it is a guess

Which stray `.scan` belongs to which `.wiff` cannot be *known* from
outside the files. Both are large, neither name contains the other, and
nothing in either name has to match. The pairing offered here is the one
whose name is most alike — the longest run of characters shared at the
front and at the back, compared against the companion each `.wiff` is
missing — and it is labelled a guess wherever it appears.

So the rename is never carried out on its own. Select the row, press
**Rename…**, and a question names the old file and the new one in full
before anything happens. A file already carrying the new name is never
written over: the rename is refused and says so, because a `.wiff.scan`
already there is either the right one, in which case the stray belongs to
something else, or the wrong one — and neither is worth losing to a guess.
After a rename the folder is checked again, so the row that said a
companion was missing disappears if that was the repair.

## Opening anyway

**Open anyway** opens what the check found to be openable: every supported
file that exists, can be read and is not already in the batch. A `.wiff`
whose companion is still missing is opened too — its chromatograms are
worth looking at, and the sample carries the reason its spectra cannot be
read wherever a spectrum would have been. **Cancel** opens nothing.

The same check runs when files are added with *File ▸ Add data files…*,
and it stays out of the way: a folder with nothing to report opens
straight away. See [[projects-and-files]] for what a project holds and
[[troubleshooting]] for symptoms after a file is open.
