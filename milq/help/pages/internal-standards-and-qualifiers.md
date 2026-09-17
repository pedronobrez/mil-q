---
title: Internal standards and qualifiers
---
## Internal standards

An internal standard is a compound spiked into every sample at the same
amount, so that its response tracks whatever the sample preparation and the
instrument did to that injection, and dividing an analyte's response by it
cancels the two.

In the [[method-workspace]], tick **IS** on the component that *is* the
standard, and write its name in the **Internal standard** column of every
analyte reported against it. A component pointed at a name that no
component carries, or at a component not ticked IS, is shown with the
problem in the [[results-table]]'s IS column rather than silently treated as
having no standard — an imported spreadsheet usually produces exactly that
mistake. The standard can also be changed from the results table itself,
where the IS column is a drop-down; every ratio, response and concentration
that came off the old standard is recomputed at once.

For each row the results carry the standard's area and height, the **area
ratio** and the **height ratio**. The ratio is what a [[calibration]] curve
is built from when a standard is set, and the raw area otherwise; the
**Response** column of the method says what the results table reports —
`area`, `ratio`, or `concentration` read off the curve.

A standard that is barely there normalises nothing, however well the
arithmetic is done. The [[batch-qc]] page charts every internal standard
across the run and says which ones the batch can actually use;
[[check-method]] says which standards lack a retention time and how many
components they carry.

## The response floor

**Min. response** on an internal standard is the smallest area it has to
give in an injection before a ratio to it means anything. It is declared
by whoever knows the method — what the standard gives when the run is
right — because nothing else can supply it: the batch cannot derive one
(measured on a real batch, the standards' precision did not track their
response), and signal-to-noise cannot stand in for one on a scheduled
acquisition, where the baseline is exact zeros and "S/N" is the height
against an arbitrary constant — see [[signal-to-noise]].

Once declared, three things read it:

- the standard's **control chart** on [[batch-qc]] is usable when its median
  clears the floor and not otherwise, in place of the S/N 10 rule; and on a
  usable chart the injections that fell under the floor are listed;
- every row normalised against the standard is checked at acceptance: an
  injection where the standard gave less than its floor is flagged
  *IS 40 below its floor of 100* and fails — see [[acceptance-criteria]];
- [[check-method]] warns of a standard that serves components and declares
  no floor.

The floor is an area in the same units as the results table, travels in the
CSV as `min_response`, and is saved with the project. **Suggest floors…** on
the [[batch-qc]] page proposes one from the batch — half of each standard's
median over the injections that were not failures, with its basis beside
it — for somebody to accept, since a proposal from one batch is evidence
and not the declaration.

## Qualifiers and ion ratios

A qualifier is a second transition of the same compound, acquired to
confirm that the peak in the quantifier is the compound and not an
interference: the two transitions should hold a fixed area ratio, and a
ratio far from it means something else is contributing.

Declare the qualifier as its own component, name the quantifier in
**Qualifier of**, and give the expected **Ion ratio %** — the qualifier's
area as a percentage of the quantifier's. After processing, each qualifier
row carries the measured ratio and a confidence:

| Confidence | Condition |
|---|---|
| Pass | the deviation from the expected ratio, relative to it, is within the tolerance (20% by default) |
| Marginal | beyond the tolerance but within the marginal band (30% by default) |
| Fail | beyond the marginal band |

The tolerance is written in the method defaults, or per qualifier in
**± ratio %**. A failed ion ratio is a flag on the row and makes its status
Fail; a marginal one makes the status Marginal when nothing else fails —
see [[acceptance-criteria]].

## Shared transitions

Two components declaring the same precursor and fragment — two isomers,
say — extract the same trace, and with nothing to separate them the
integration returns the same peak twice under two names. **Check method**
reports the pair, and [[suggest-from-data]] refuses to pre-tick a retention
time for either; the only thing that separates them is a retention time
that is different, and different on purpose.

## A standard in the same spray

Without a column the pairing is the same and the arithmetic is not: the
analyte and its standard are two heights in one averaged spectrum rather than
two integrated peaks, and a deuterated standard sits close enough to its
analyte for one to reach the other's ions. Which direction that goes, how
large it is, and when it cannot happen at all are measured in
[[infusion-quantitation]]. The response floor above matters more there, not
less — ion suppression is shared by the pair, so the ratio survives it and
only the absolute responses show it.
