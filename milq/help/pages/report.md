---
title: The batch report
---
`File ▸ Export report…` writes the whole batch as a document: PDF for
handing over, HTML for keeping — the second opens in a browser long after
this application is gone, which is the point of a report as against an
export. It is built from the session rather than from the screen, so it
holds what was measured and not what happened to be on show.

## Sections

Numbered in the order printed; leaving one out closes the gap rather than
leaving a hole.

| Section | Holds |
|---|---|
| Summary | rows, samples, components; how many passed, were marginal, failed; excluded rows; and the findings — every failed row with its flags |
| Samples | the batch table: name, type, group, concentration, dilution, acquisition time |
| Method | the component table, the defaults, and the findings of [[check-method]] |
| Calibration | each curve's regression, weighting, equation, r², and its standards with accuracies; an internal standard's curve labelled as meaningless |
| Detection and quantitation limits | LOD and LOQ per component, with the notes of [[detection-limits-and-carryover]] |
| Carryover | the blank after the top standard, or why it was not measured |
| Batch quality | the control charts' verdicts, the injection response index, drift, and the precision of the QCs — [[batch-qc]] |
| Sampling | points per peak for every component, the cycle times the peaks would need, and how many peaks were narrower than a cycle — the *Sampling* tab of [[batch-qc]] |
| Mass drift | only when the [[mass-drift]] tab has measured: each standard's mass through the run and whether the axis held, and the per-injection corrections where [[mass-recalibration]] is on |
| Infusions | only while the *Infusions* tab of the [[analytics-workspace]] has measured: one row per infused sample — the precursor measured back off the acquisition, the ions found of those predicted, the best record of your own library, and each infusion scored against the others of the same compound — [[infusion-report]] |
| Infusion comparison | only while [[compare-infusions]] has been run: this day's tray against a reference project's, compound by compound and condition by condition |
| Compared spectra | only while the Explorer is holding spectra together: the head-to-tail picture, a table of the traces, and the masses they share within 10 ppm — [[chromatograms-and-spectra]] |
| Integration algorithms | only when [[compare-algorithms]] has been run: the totals per algorithm and the components that moved most |
| Batch comparison | only when [[compare-batches]] has been run: the totals side by side and the components in the order of how much they moved |
| Changes made by hand | only while there is a history to print: every hand edit in the order it was made, with the value before and after — the [[audit-trail]], and not an electronic signature |
| Results | every row: sample, component, RT, area, ratio, concentration, accuracy, status and flags |
| Statistics | the grouped summary of the [[statistics]] page, by sample type |

Two markers on sample names are explained in a legend under the table that
uses them: `†` for a row excluded from the statistics, `‡` for a row
integrated by hand. A column of "yes / no / by hand" costs more width than
it earns.

A section with nothing to show says so — *no standards, so there is nothing
to carry over* — rather than printing an empty table.

## The one picture

Everything else in a report is a number in a table. *Compared spectra* is
the exception, because two spectra head to tail are read as a shape and
not as a list, and it is printed only while the comparison stands — pin a
spectrum in the [[chromatograms-and-spectra]] pane and the section
appears, unpin and it goes. The picture is drawn from the data at the
moment the report is written, at twice the size it is printed at, and
travels inside the document: an HTML report is still one file that can be
mailed. Its peak labels are placed for paper: each one above the peak it
names and never over a trace or over another label, moved a line further
out with a leader down to its apex where the room is taken, and left out
altogether where there is no room within six lines — see
[[chromatograms-and-spectra]]. Under it are the traces, each with its base peak and how many
peaks it holds, and the masses every one of the spectra carries within 10
ppm with the height of each as a share of its own base peak — which is the
only way two spectra of different sizes compare in a table. A mass in one
and not in the other is a difference, and a difference is read off the
picture.

## Themes

The export dialog asks which theme the document is to be written in, and
remembers the answer for the next one. It changes how the report looks and
never what it says: the same sections, the same numbers, the same words.

| Theme | For |
|---|---|
| Paper | the report as it has always been — the project's blue for headings, striped rows, the pictures in the traces' own colours |
| Black and white | a journal that prints in no other colour, or a photocopier |

**Black and white** is more than a report with the colour taken out. Nothing
is tinted, because a 4% tint reproduces as either nothing or a smudge: the
striped rows and the shaded heading cells become rules instead, and a failed
row is bold where it was red. The pictures go with it — a black and white
report holding a four-colour spectrum is not a black and white report — so
the compared spectra are drawn in two tones and two line styles: the first
trace solid black (21:1 on white), the second dashed in #666666 (5.7:1), and,
where the drawing is centroids, a filled head on the first trace's tall
sticks and a hollow one on the second's, since a dash cannot show on a stick
one point wide. Measured on the two averaged CA-d4 spectra head to tail: with
the peak labels masked out, the upper trace's ink is a median grey of 0 and
the lower's 102, on a page that is 255, and the dash pattern is still a
dashed line after the figure is halved.

There is a third theme, **dark**, and it is for the HTML export only. A PDF
is a thing somebody prints, and a printer handed a dark page lays down a
whole sheet of toner with the letters knocked out of it, so the printed
export offers two themes and `report.write_pdf` refuses the third. On screen
it is the application's own dark ground with every colour lightened until it
clears 3:1 on it. The same three themes are offered for a figure on its own —
see [[chromatograms-and-spectra]], where the measured contrast figures are.

## The printed layout

A4 portrait; a title block; a table of contents with page numbers; a
running header naming the report from page two and a footer with the
version, the date and *Page n of N* on every page, because a page that
comes loose has to say what it belongs to. Table heading rows repeat on
every page a table spans.

The document is laid out more than once. A heading left stranded at the
foot of a page with its content overleaf is pushed to the next page and the
document laid out again — up to three times, since moving one heading can
strand another — and the table of contents needs a pass of its own because
page numbers do not exist until the pages do. A hundred-page report is
therefore laid out three times and takes about seventeen seconds, which is
why the export shows a wait cursor rather than looking hung.

## A note on what was once wrong

The first version of the report printed at a twelfth of its size: eight
sections in the top corner of a single otherwise blank page. The layout was
being measured at the screen's resolution and printed at the writer's. It is
fixed, and two tests open every PDF written — one counts pages, one looks
for ink below the half-way line — because nothing about it was visible in
the HTML.

The same printing machinery produces this manual's PDF, from
**Help ▸ Export manual as PDF…**.

A report is what you keep. What you carry on working in is the Excel
workbook of the same sections — see [[export]], which also covers the
Skyline transition list.

This report is of a batch. One compound sprayed on its own has no batch to
be part of, and gets a document of its own instead: [[infusion-report]],
written from the Explorer and printed through the same machinery. And the
method a batch was run under, read before anything is acquired at all, is
the [[method-report]] — same printer, same page, a different question.
