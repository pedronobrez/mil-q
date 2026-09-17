---
title: Statistics
---
The **Statistics** tab of the [[analytics-workspace]] summarises each
component over groups of samples: mean, standard deviation and coefficient
of variation, with the individual values behind them.

| Control | Effect |
|---|---|
| **Group by** | *concentration* (samples sharing an expected concentration — replicate standards, replicate QCs), *sample name*, *sample type*, or *sample group* |
| **Quantity** | *response* (what the method reports for the component), *area*, *height*, *calculated concentration*, *retention time*, *area ratio* |
| **Export CSV…** | the table as shown |

## The table

One row per component and group: the component, the group, `n` used of
`n` total, the mean, the sample standard deviation, the **%CV**, and — for
groups with an expected concentration — the mean accuracy. The value
columns to the right list each member of the group, so the figure can be
read against what produced it.

The standard deviation is the sample standard deviation (n − 1); a single
value has no spread to report. A row unticked in **Used** is counted in the
total but left out of the arithmetic, so excluding an injection shows as a
smaller *n* rather than a quietly different mean.

A component's groups sit together, so control, treated and day 7 can be
read off one another; results arrive sample by sample, which would otherwise
scatter every group of every component across the table.

## Grouping by sample group

A sample with no group is in no group: it drops out of the summary rather
than pooling every unlabelled injection into a phantom group. Groups are
free text set in the [[samples-workspace]].

## Precision, properly

For the question "how well did the batch repeat itself", the [[batch-qc]]
page's Precision tab is the stricter tool: it takes the quality controls
only — unknowns differ from one another by design and standards by
construction — and applies a limit. This page is the general summary.
