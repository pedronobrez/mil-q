---
title: Metric plot
---
The **Metric plot** tab of the [[analytics-workspace]] draws any numeric
column of the results against the row order, the injection order, or
another column, for one component or all of them.

| Control | Effect |
|---|---|
| **X** | *injection order* — the order the instrument ran the samples, from their acquisition times; *row order* — the order of the results table; or any numeric column |
| **Y** | any numeric column: area, height, S/N, area ratio, retention time, ΔRT, calculated concentration, accuracy… |
| **Component** | one component, or every component overlaid |
| **Colour by** | *sample group*, *sample type*, or *nothing* — with a legend, and *no group* for samples that have none |
| click a point | selects that row in the [[results-table]] and its panel in the [[peak-review]] grid |

## Uses

- **Area or ratio against injection order**, for an internal standard: the
  quickest look at whether the run held up. The [[batch-qc]] page does this
  with limits and verdicts.
- **Retention time against injection order**: drift of the column, and a
  peak that jumps between two neighbours.
- **Calculated concentration against actual**: the calibration seen from
  the samples' side.
- **Accuracy against S/N**: whether the failures are the weak peaks.
- **Coloured by sample group**: whether treated and control separate on a
  component, before any statistics are run.

Injection order used to be the order the results happened to be computed
in, which was the order the files were opened; it is now the acquisition
time, and where files carry none they are put last, in opening order.
