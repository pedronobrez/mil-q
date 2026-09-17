---
title: Audit trail
---
Everything a batch is processed with is saved with the project — the method,
the integration parameters, the calibration. What is not saved anywhere else
is the sequence of decisions somebody made on top of that: this peak
integrated by hand, that standard dropped from the curve, this injection
retyped as a blank. Reopening a project six months later shows the answer and
not how it was arrived at.

The audit trail is that record. It is the **Audit trail** tab of the
[[analytics-workspace]], and also *File ▸ Audit trail…*, which asks the same
question of the project rather than of the workspace one happens to be in.

## What is recorded

One line per action, with the time it was taken, what was changed, and the
value before and after.

| Change | Recorded as |
|---|---|
| a peak integrated by hand on the [[peak-review]] grid | the component and sample, the boundaries and area before and after, and the range that was dragged |
| a row put back on automatic integration | the same, the other way round |
| a row's **Used** box in the [[results-table]] | used ↔ excluded, with the area |
| a standard included or excluded on a [[calibration]] curve | used ↔ excluded, with its concentration |
| **Remove outliers** on a curve | how many standards were excluded before and after, and the tolerance |
| a component added, removed or edited in the [[method-workspace]] | the column that was typed in, and what was in it |
| a default under that table — tolerance, units, ion-ratio bands | the same, once the typing has finished rather than once per digit |
| a sample's type, group, concentration, dilution, name or comment in the [[samples-workspace]] | the field, before and after |
| **Process batch**, and each reprocessing after a parameter change | what it was processed with, and how many rows came back |
| the mass-recalibration switch on [[mass-recalibration]] | on ↔ off |
| the project being saved | the path, with the row and sample counts |

Values are recorded as they were shown on screen, and kept short: the trail
is meant to be read at a glance, and a line that has to be unfolded is a line
nobody reads.

## Reading it

The table sorts on any column — the timestamps are ISO, so sorting *When* as
text sorts it as time — and the filter box narrows to the rows holding what
is typed, anywhere in them. Typing a component's name gives that component's
history; typing `Manual` gives every integration made by hand.

**Export CSV…** writes the whole trail, not the filtered view. A trail with
rows left out is not the thing it claims to be, and the filter is a way of
reading it rather than a way of choosing what happened.

The trail is also a section of the batch report, *Changes made by hand*,
printed whenever there is anything in it — see [[report]].

## What it is not

**This is not a regulated audit trail.** It carries no electronic signatures
and there are no user accounts: it records *what was done and when*, never
*who did it*. The project is a JSON file — see [[projects-and-files]] — that
anyone can open in a text editor, so nothing here would detect the record
being altered outside the application, and nothing here is evidence in the
sense 21 CFR Part 11 or Annex 11 mean it.

What it is for is the ordinary question a reviewer asks of a batch: which of
these numbers did a person decide, and what were they before? For that it is
enough, and it is what the software can honestly claim.

## What it does not record

Reading, sorting, filtering and zooming change nothing and are not recorded.
Neither is anything derived that the project does not keep — the algorithm
comparison, the mass-drift measurement, a spectral-library search — because
those are rebuilt on request rather than decided. The trail is append-only:
nothing in the application edits or deletes an entry, and a project saved
before this existed opens with an empty trail rather than an invented one.
