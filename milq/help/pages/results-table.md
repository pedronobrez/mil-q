---
title: Results table
---
The **Results** tab of the [[analytics-workspace]] is one row per sample and
component: what was measured, what it was measured against, and why a row
is empty when it is.

## Columns

| Column | Meaning |
|---|---|
| Sample, Type, Sample group | the injection, from the [[samples-workspace]] |
| Component, Group | from the [[method-workspace]] |
| Channel | the acquisition channel the peak was taken from |
| m/z | the centre of the mass window extracted |
| RT, Exp. RT, ΔRT | the apex time, the method's time, and the signed difference |
| Area, Height, Width | the peak; width is the full width at half height, in minutes |
| S/N | height over the noise, or `—` when the noise could not be measured — see [[signal-to-noise]] |
| Algorithm | which [[integration-algorithms|algorithm]] produced the area — *valley*, *summation*, *gaussian*, or *manual*; empty on rows from before this was recorded |
| Points | how many points inside the boundaries sit at or above one per cent of the peak's height — the peak rather than its feet; what the *Sampling* tab of [[batch-qc]] summarises |
| IS, IS area | the internal standard and its area in this sample; a standard that does not resolve is shown with the problem |
| Area ratio, Height ratio | the component over its standard |
| Response | what the method's Response column asks for: area, ratio or concentration |
| Ion ratio %, Exp. ratio %, Conf. | a qualifier's measured and expected ratio and its Pass / Marginal / Fail |
| Actual conc., Calc. conc., Accuracy % | the expected concentration, the one read off the curve (× dilution), and the second as a percentage of the first |
| Status, Flags | the [[acceptance-criteria]] verdict and its reasons |
| Used | untick to leave a row out of the statistics and the curve without deleting it |
| Note | why a row is empty, or what the integration decided — the notes are listed on [[integration-parameters]] |

The column names are the trade's: what each of them means in one line is in
the [[glossary]].

## Controls

| Control | Effect |
|---|---|
| **Show** | All, Pass, Marginal, Fail, or Not integrated |
| **View** | *By sample* or *By component* — which the rows are ordered and grouped by |
| the filter box | free text matched against every column |
| **Columns…** | which columns are shown, and to how many decimals |
| **Export CSV…** | the visible columns of the visible rows; the whole batch at once is [[export|the Excel workbook]] |
| a column header | sort |

## Editing in the table

The **IS** cell is a drop-down of the method's internal standards. Choosing
another re-points the component and recomputes every ratio, response and
calculated concentration that came off the old one at once, rather than
leaving them for the analyst to remember to refresh.

**Used** is a checkbox. A row unticked is counted in the totals of the
[[statistics]] page but left out of its arithmetic, so excluding an
injection shows up as a smaller *n* rather than quietly changing the mean
with no trace; the [[report]] marks such rows with a dagger.

## Linking

Selecting a row highlights its panel in the [[peak-review]] grid and, if
another component is selected in the tree, switches to it. The summary
line under the table counts the rows shown and how many are integrated.
