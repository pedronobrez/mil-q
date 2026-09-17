---
title: Collision energy
---
[[acquisition-schedule]] is the chromatographic half of *what should the
instrument be told to do*: the method implies an acquisition, and the
program says what it would cost before anybody types it in. This is the
infusion half. A tray of infusions of one standard is usually the same vial
sprayed at several collision energies and, on an instrument that has both,
under more than one activation — CID and EAD. Somebody then has to pick
one, and the pick is normally made by eye off whichever spectrum looked
busiest.

**Recommend energies…** on the [[infusion-report]] tab groups every
measured infusion by compound, activation and collision energy, and makes
**three** recommendations per compound, each with the figures it stands on.
Three, because they are three different questions and they do not have to
agree.

## The three questions

**For identification** — the most predicted ions found, *with the precursor
still standing above 100 counts*. Both halves are required. A spectrum with
fifteen fragments and no precursor left cannot say the fragments came from
the ion the method isolated — the isolation window may have caught a
neighbour, which is what [[accurate-precursor]] exists to catch — and a
spectrum with a tall precursor and two fragments has identified nothing. A
tie on the count is broken on the explained share, and the reason says so.

**For quantitation** — the energy whose *strongest fragment* holds the
largest share of the measured intensity, and gives the same share the next
time the vial is sprayed. A transition is one product ion: the energy that
puts 60% of the spectrum on one mass gives a transition six times the one
that scatters the same ions over twenty masses. Where the compound was
infused more than once at that condition, the share has to repeat to within
20% — the figure a control chart of the same standard calls a point out at,
and the one [[compare-infusions]] marks a base peak as moved at. Where it
was infused once, the reason says the share is one measurement and not a
repeat, rather than calling one measurement stable.

**For a library record** — the middle of the energies measured, at the
highest explained share among the ones in the middle. A record made at the
softest energy holds the precursor and little else and matches nothing; one
made at the hardest holds fragments too small for another instrument to
reproduce. The middle is a **position among the energies that were
acquired**, never a number between two of them.

## What is never offered

An energy nobody acquired. There is no interpolation and no "optimum"
between two measured points: what a compound does at 30 eV when it was
sprayed at 22 and 45 is a measurement nobody made. Where a compound was
sprayed at one condition only, the recommendation is *one energy measured;
nothing to choose between*, which is the truthful answer and not a failure.

## The table

One row per compound, activation and collision energy — a *condition*,
which is how [[standard-history]] cuts a standard's history into series and
how [[compare-infusions]] matches two days, for the same reason: 12 eV EAD
and 45 eV CID are two measurements of two different things. Where a
condition holds more than one infusion, every figure is the median over
them.

| Column | Meaning |
|---|---|
| Activation | as the file's name writes it; `unstated` where it writes none, which is not the same as CID |
| CE (eV) | the energy the acquisition declares, or the one the file's name writes |
| Ions found | of those predicted for the compound's formula — see [[lipid-maps]] |
| Explained | the share of the spectrum's intensity the prediction accounts for |
| Precursor height, % of base | what survived fragmentation, against the base peak |
| Base peak share, Fragment 1–3 | of the summed intensity of the measured peak list |
| Against other energies | this infusion's median cosine against the other conditions of the same compound |
| Considered | `no` on a row the isolation verdict contradicts, with what the method actually isolates |

The shares have two denominators and each is named where it is written. The
precursor's is the **base peak**, which is how anyone reading the trace
reads it. Every other share is of the **summed intensity of the peak list**
the table is measured on — the peaks at or above 1% of the base peak, which
is the list the scores and the records of your own are already made from.

## Rows that are shown and never recommended

A row whose file is named for one compound while its method isolates
something that is no adduct of it stays in the table, marked, and is never
recommended. It is not deleted because a pair of them is a finding about
the tray, and it is not recommended because it is not a measurement of the
compound on the label. Such a row never shares a condition with a kept one
either: averaging two compounds under one heading is exactly the harm the
verdict was written to catch.

## What comes off it

**Export CSV…** writes the table and the recommendations as one file in two
blocks — one row per condition, then one row per recommendation with its
reason, separated by a blank row, which is what a spreadsheet reads as the
end of a table.

The per-compound document (**Report…** on the same tab) gains a *Collision
energy* paragraph whenever the chosen rows hold more than one condition of
that compound. The dialog, the CSV and the page are the same arithmetic and
cannot disagree.

## A measured caution

On the bile-acid standards this was written against, the **explained share
is highest at the softest energy** — 85.0% at 12 eV EAD for one of them,
against 63.6% at 22 eV — because the surviving precursor is 82% of that
spectrum and the precursor is an ion the prediction accounts for. That is
why the library rule takes the middle energy first and the explained share
only among the candidates in the middle: the highest explained share on its
own would recommend the energy at which the compound barely fragmented.
