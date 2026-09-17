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
| File | the raw file's name | no |
| Sample | the display name; shortened from the file name by dropping the prefix every file shares | yes |
| Type | the sample's role, see below | yes |
| Group | the study group — control, treated, day 7; free text, because no vocabulary fits every study | yes |
| Actual conc. | the expected concentration, for standards and quality controls; in the method's concentration unit | yes |
| Dilution | the factor the reported concentration is multiplied by, because the curve describes the vial that was injected and the answer wanted is the original sample | yes |
| Vial | from the file | no |
| Acquired | the acquisition date and time, from the file — what puts the injections in the order the instrument ran them | no |
| Comment | free text | yes |

Select rows and use **Set type of selected rows**, **Set group** or
**Apply concentration to selection** to edit several at once. **Add data
files…** and **Close all** are the same actions as in the File menu.

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

Rows are in the order the files were opened. Where the injections were run
in a different order, the acquisition times decide: the [[batch-qc]] page
and the injection-order axis of the metric plot sort by them and say when
some files carry no time.
