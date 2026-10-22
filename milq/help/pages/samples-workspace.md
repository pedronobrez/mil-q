---
title: The Samples workspace
---
The Samples workspace (Ctrl+4) is the batch table: one row per injection,
with everything about it that the raw file does not record. A `.wiff`
reports every injection as `kUnknown`, so the role each one plays — standard,
control, blank, unknown — its concentration and its dilution live here and
are saved with the project.

## Columns

| Column | Meaning | Editable |
|---|---|---|
| Batch order | the injection's place in the run, 1 for the first vial the instrument took; empty until somebody numbers it. Where it is set it decides the order of every chart through the run — see *Order* below | yes |
| File | the raw file's name | no |
| Sample | the display name; shortened from the file name by dropping the prefix every file shares | yes |
| Type | the sample's role, see below | yes |
| Group | the study group — control, treated, day 7; free text, because no vocabulary fits every study | yes |
| Actual conc. | the expected concentration, for standards and quality controls; in the method's concentration unit | yes |
| Dilution | the factor the reported concentration is multiplied by, because the curve describes the vial that was injected and the answer wanted is the original sample | yes |
| Vial | from the file | no |
| Acquired | the acquisition date and time, from the file — what puts the injections in the order the instrument ran them | no |
| Comment | free text | yes |

**Add data files…** and **Close all** are the same actions as in the File
menu.

## Editing many rows at once

| Control | What it does |
|---|---|
| **Set type of selected rows** ▸ **Apply** | the chosen type on every selected row |
| **Set group** ▸ **Apply** | the typed group on every selected row; the box offers the groups already in the batch |
| **Apply concentration to selection** | copies the first selected row's concentration onto the other selected rows — a set of standards injected at one level |
| **Set dilution** ▸ **Apply** | one dilution factor on every selected row; it has to be a number above zero, and anything else is refused with a message rather than read as 1 (`Enter` in the box applies it too) |
| **Batch order** ▸ **Number in table order** | 1, 2, 3… down the table |
| **Batch order** ▸ **Number by acquisition time** | 1, 2, 3… by the time each file carries; files that carry none are numbered last, in table order, and the message says how many |
| **Batch order** ▸ **Clear batch order** | removes the number |
| **Sort by batch order** | puts the rows themselves in the order of the run |

The **Batch order** choices act on the selected rows, or on every row when
none is selected. Every row numbered starts at 1. A selection keeps the
place it already had — renumbering rows 5 to 9 starts again at 5 — and a
selection with no numbers yet follows the highest number elsewhere in the
batch, so numbering a stretch never gives two rows the same number by
accident.

Rows are selected with a click, `Shift`-click for a range and `Ctrl`-click
(`⌘`-click on a Mac) to add one.

### Pasting from a spreadsheet

A column copied out of a spreadsheet pastes into the table with `Ctrl+V`
(`⌘V`): click the first cell to fill and paste, and the values go down the
column from there, one per row. A block of several columns fills to the
right as well. A single value pasted with several rows selected goes into
that column of every selected row.

Each pasted cell is taken exactly as though it had been typed: a dilution
of zero, a batch order of 2.5 or a concentration that is not a number is
left as it was, and the message counts the cells taken and the cells left.
A type is matched by name, ignoring capitals — `blank` is Blank. The File,
Vial and Acquired columns come from the file and are skipped.

Every value changed, one row at a time or many at once, is one line in the
[[audit-trail]]: the sample, the field, what it was and what it became. A
value set to what it already was records nothing.

The columns the file *does* record — the vial, the injection volume, the
acquisition method, the declustering potential — are read-only and shown in
the Explorer instead: see [[sample-information]].

## Sample types and what uses them

| Type | Used by |
|---|---|
| Unknown | reported against the curve; on an internal standard's control chart |
| Standard | defines the [[calibration]] curve, with its Actual conc.; the lowest and highest standards anchor [[detection-limits-and-carryover]]; on the control chart |
| Quality Control | the replicate set for [[batch-qc]] precision and for [[compare-algorithms]]; scored for accuracy against its Actual conc.; on the control chart |
| Blank | counted as a blank for carryover; on the control chart, since it carries the internal standard |
| Double Blank | a blank extracted without the internal standard: a blank for carryover, **not** on the control chart |
| Solvent | a solvent injection: a blank for carryover, **not** on the control chart |

The distinction on the last two is deliberate. Plotting an injection that
never saw the internal standard on that standard's chart puts a zero in the
middle of the run and makes a sound batch look as though it lost the
standard twice.

## Groups

A group is whatever the study calls it. The [[statistics]] page can group
by it, the [[metric-plot]] can colour by it, and the report's statistics
section can be laid out by it. A sample with no group is in no group: it
drops out of a by-group summary rather than being pooled into a phantom
"ungrouped" set.

## Order

Rows are in the order the files were opened until **Sort by batch order**
puts them in the order of the run; the Explorer's sample list and the next
processing follow the table.

The order of the run — what the [[batch-qc]] charts, the [[mass-drift]]
trend, the injection-order axis of the [[metric-plot]] and the blank after
the highest standard in [[detection-limits-and-carryover]] all read — is
decided like this:

1. **Every injection has a batch order**: the batch order. The chart says
   *in batch order*.
2. **None has one**: the acquisition times the files carry, as before; a
   file without a time goes last, in the order opened. The chart says *in
   acquisition order*, or, when some files carry no time, that the
   sequence is a guess.
3. **Some have one**: the numbered injections first, by number, then the
   others by acquisition time. Nothing is slotted *between* two numbered
   injections, because the numbers and the clock are two claims that need
   not agree, and interleaving them would make the order depend on which
   was believed at each step. The chart says how many of the injections
   were numbered, and that it is not the order of the run until all are.

Two injections given the same number are put in the order of their
acquisition times, then in the order opened.

The batch order is typed, not read: a `.wiff` carries the time an injection
was acquired but not its position in the sequence, and an mzML converted
elsewhere may carry neither. It is what to use when the clock is wrong, a
file was re-acquired later, or the files came without times. It is saved
with the project, and a project saved before it existed opens with no
batch order on any row. The [[report]]'s sample table and the exported
workbook's Samples sheet carry it as their first column.
