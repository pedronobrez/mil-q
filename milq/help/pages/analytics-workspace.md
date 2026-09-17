---
title: The Analytics workspace
---
The Analytics workspace (Ctrl+2) is the batch, quantitatively: every
component across every sample, the integration of each, the curves, the
statistics and the quality of the run. It is built the way MultiQuant is —
a component chosen on the left, one chromatogram per sample for it in the
middle, and the table underneath.

## Layout

**Left.** The component tree, grouped by the method's groups, with **All
components** at the top; a filter box above it; and two folding panels
beneath: **Integration** ([[integration-parameters]]) and **Acceptance**
([[acceptance-criteria]]). The panels start folded, because open they leave
the tree a few rows tall, and whether they were open is remembered.

**Centre.** The [[peak-review]] grid: one panel per sample for the selected
component, with the integrated area shaded.

**Bottom.** Eight tabs: [[results-table|Results]],
[[calibration|Calibration]], [[statistics|Statistics]],
[[metric-plot|Metric plot]], [[batch-qc|Batch QC]], [[mass-drift|Mass drift]],
[[infusion-report|Infusions]] and [[audit-trail|Audit trail]]. The last two
measure nothing until asked — *Infusions* carries its row count in the tab
name once it has, and is empty on a batch that holds no infused standard.

## The toolbar

| Button | Effect |
|---|---|
| **Process batch** | extract and integrate every valid component in every open sample, then fit the curves, read the concentrations and score the acceptance criteria. With results already in hand it reads only what changed — see *Processing only what changed* below |
| **Reprocess all…** (the arrow beside **Process batch**) | every row again from the files, keeping nothing, including the rows integrated by hand. It asks first when there are any |
| **Recalibrate** | refit every curve from the samples marked Standard and read the unknowns back off them, without reintegrating |
| **Compare algorithms…** | integrate the batch with every algorithm and put the answers side by side — see [[compare-algorithms]] |
| **Compare batches…** | a reference project against this batch, component by component — see [[compare-batches]] |
| **Magnify peak** | one panel filling the pane; double-clicking a panel does the same |

The status line to the right reports what was last done: how many rows
across how many samples, how many integrated, which standard and qualifier
the selected component has.

## What "processing" does, in order

1. For each sample and component, the channel is matched and the XIC
   extracted and conditioned (smoothing, baseline) with that component's
   integration settings.
2. The peak is found and integrated by the component's algorithm — see
   [[integration-parameters]] and [[integration-algorithms]].
3. Internal-standard ratios and qualifier ion ratios are computed — after
   the whole batch, since a standard's own peak has to exist before anything
   can be divided by it.
4. Curves are fitted from the standards, concentrations read off them and
   multiplied by each sample's dilution, and accuracies computed.
5. Every row is scored against its acceptance criteria.

A change to one component's integration settings reprocesses only that
component (or its group); everything downstream — ratios, curves,
concentrations, statuses — is recomputed each time.

## Processing only what changed

Adding one injection to a batch of twenty-six should read one injection, and
it does. Every integrated row records a **fingerprint**: a short digest of
everything that decides its numbers — the component's precursor, fragment,
tolerance, retention time and window, the integration parameters actually in
force for it, and that injection's mass correction. When **Process batch**
is pressed with results already in hand, each row's fingerprint is compared
against what the method says now:

| The row | What happens |
|---|---|
| fingerprint unchanged | **kept**, exactly as it stands; the file is not opened |
| a new injection, or a new component | **integrated** |
| its component's fingerprint changed | **integrated** again |
| its injection or its component is gone | **dropped** |

A kept row is not a guess. Its fingerprint says it was produced by the same
arithmetic a full run would produce now, which is why the whole set comes
back identical, row for row and field for field, to what processing the
batch from scratch gives. What is *not* in the fingerprint is anything that
does not change a number: renaming an injection or regrouping a component is
written onto the kept rows rather than bought with a second read.

**Rows integrated by hand are kept as they are** while their component's
fingerprint holds — that is the point of drawing a boundary. When the
component's settings change they are integrated again, and the status line
and the [[audit-trail]] both say how many: a boundary drawn on one trace is
not a decision about a different mass window, and leaving it would report a
peak nobody chose.

Measured on the real 26-injection, 141-component batch — 3,666 rows:

| | |
|---|---|
| processing the batch in full | **2.4 s** with the files in the operating system's cache; 12 s the first time, cold |
| one injection added: 3,525 kept, 141 integrated | **0.06 s** — 39 times faster |
| one component's window widened: 3,640 kept, 26 integrated | **0.03 s** |
| nothing changed at all: 3,666 kept, 0 integrated | **0.02 s** |
| deciding all of that, before anything is read | **under 10 ms**, with no file opened |

Everything derived is still recomputed over the whole set every time —
internal-standard ratios, ion ratios, curves, concentrations, acceptance and
the quality charts. That is arithmetic over rows rather than reads of files
and costs about 50 ms in all on this batch.

Three things it deliberately does not do. A change to a **method default**
reaches every component that inherits it, so almost nothing can be kept and
the run falls back to processing the batch in full — the audit line then
says *Batch processed* rather than *Batch reprocessed*. A row written by a
version from before fingerprints existed records nothing, so it is
integrated again; one full run gives the whole project its fingerprints and
every run after that is incremental. And a fingerprint says the **method**
has not changed — it cannot know whether the acquisition behind a path has
been replaced, which is what **Reprocess all…** is for.

A cancelled run leaves the rows it did not reach as they were. Their
fingerprints no longer match, so pressing **Process batch** again finishes
exactly what was left.

## Two-way linking

Clicking a panel in the grid selects its row in the results table;
selecting a row brings up that component in the tree and highlights its
panel; clicking a point on the metric plot or a row in Batch QC does the
same. The results table follows the tree: with one component selected it
shows that component's rows, with **All components** it shows everything.

## Reviewing a whole batch

**All components** in the tree puts every peak of every component in the
grid, a page at a time. Extracting all of them — 141 components across 26
samples — is around a hundred seconds of work to put nine on screen, so the
pages are built as they are turned rather than all at once.
