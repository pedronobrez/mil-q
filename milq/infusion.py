"""
Telling a direct infusion from a chromatographic run, from the sample alone.

In an infusion there is no column. The analyte is sprayed for a minute or two
and every scan is the same spectrum plus noise, so the chromatogram carries no
information and the thing worth looking at is the average of the whole run. In
a chromatographic run the opposite holds: the ion current is concentrated into
peaks, and a spectrum only means something over one of them.

The verdict is two figures of the same shape, and nothing else:

`above_half`
    the fraction of the sample's total ion chromatogram sitting at or above
    half its own maximum.
`channel_above_half`
    the same measure on the one channel the average would be shown from —
    the product-ion channel carrying the most signal, or the survey when the
    method has no product scan.

That "maximum" is the **99th percentile** of the scans that are left after
the first `SETTLING_SECONDS` of acquisition, not the largest of them. See
*The spike that inverted the two populations* below: the largest scan is one
scan, and on three of nine real infusions it was two to four times the median
and dragged both figures to 0.002 – 0.006, under every chromatographic run
measured. The settling window is the same finding on a short run, where one
per cent of the scans is one scan again — see *Short runs* below, and
`MIN_JUDGED_SCANS`, which is where the verdict says it cannot tell.

A peak is by definition narrow against the run it sits in, so a run with a
peak in it spends most of its scans well under half the apex; a spray that
merely drifts stays above it from the first scan to the last. Both have to be
flat. The sample total alone is not enough — a scheduled method acquires each
transition over its own window, and the sum of many peaks at different times
is flatter than any of them — and one channel alone is not enough either,
since a single transition of a blank is flat because it is empty. Neither
statistic reads a spectrum, so the verdict costs one chromatogram per channel,
works on a `.wiff` whose `.wiff.scan` is missing, and says the same thing
about a file and about its mzML.

The spike that inverted the two populations
-------------------------------------------

The first version of this module took the largest scan as the maximum, and
was written with only the chromatographic population measured. When the nine
bile-acid infusions were finally read, **three of the nine measured 0.0021,
0.0039 and 0.0063 on both figures** — lower than every one of the thirty-nine
chromatographic runs. The two populations were not merely overlapping, they
were the wrong way round, and no value of `FLAT_FRACTION` separates them.

The cause is one scan. All three carry a transient at scan index 1, 0.0084 min
in, of 2.8 to 4.4 times the run's median total; `DCA-d4_TOFMSMS_Mix1` carries
two more mid-run, at 1.08 and 1.10 min. Half of a spike is above everything
else in the run, so a perfectly flat spray measured as though nothing in it
ever reached half its own height. The statistic was wrong, not the threshold.

So the reference is the **99th percentile** of the scans, `REFERENCE_PERCENTILE`,
rather than the largest of them. The choice is measured, not assumed:

| reference | infusions (9) | chromatographic (39) | margin |
|---|---|---|---|
| the largest scan | 0.0021 – 1.0000 | 0.0041 – 0.0984 | **−0.096**, inverted |
| 99.5th percentile | 0.6385 – 1.0000 | 0.0061 – 0.0984 | +0.540 |
| **99th percentile** | **0.9937 – 1.0000** | **0.0143 – 0.1148** | **+0.879** |
| 95th percentile | 0.9937 – 1.0000 | 0.0714 – 0.2623 | +0.731 |
| 90th percentile | 0.9937 – 1.0000 | 0.1148 – 0.4098 | +0.584 |

(each figure the smaller of the two the verdict reads). 99.5 is not enough
because `DCA-d4_TOFMSMS_Mix1`'s three spiked scans are 0.63% of its 473; the
widest margin measured is 0.895 at the 99.2nd percentile and 99 is the round
number next to it. Going lower costs margin from the other end, because
setting aside a real peak's apex lifts the chromatographic figures too.

Short runs: the settling window and the floor
---------------------------------------------

The paragraph that used to stand here said that below about a hundred scans
the 99th percentile is the largest scan again, and left it as a stated gap.
It was then measured, by truncating all forty-eight acquisitions to their
first 20, 30, 50, 75 and 100 scans and reading both figures off the shortened
run. The gap is real, it is wider than "about a hundred", and it has a second
half nobody had looked for.

**Where the 99th percentile breaks** — the smaller of the two figures, worst
and best of each population. A file appears at a length only if it has that
many scans, which is why the twenty-six 14.6-minute runs (61 scans each) drop
out past 50:

| first N scans | files | infusions (9) | chromatographic |
|---|---|---|---|
| 20 | 48 | **0.0500** – 1.0000 | 0.0000 – 0.9500 (39) |
| 30 | 48 | **0.0333** – 1.0000 | 0.0345 – 0.9667 (39) |
| 50 | 48 | **0.0200** – 1.0000 | 0.0204 – 0.6735 (39) |
| 75 | 22 | **0.3333** – 1.0000 | 0.0270 – 0.8919 (13) |
| 100 | 22 | 0.9900 – 1.0000 | 0.0202 – 0.9394 (13) |
| the whole run | 48 | 0.9937 – 1.0000 | 0.0143 – 0.1148 (39) |

The break is the same three spiked infusions as before, for the same reason:
`np.percentile` interpolates, so at 50 scans the 99th percentile sits about
half way from the second largest scan to the largest and a 4.4× transient
takes the reference with it. The populations are inverted again — margin
−0.900 at 20 scans, −0.654 at 50 — and it holds to 80 scans, not to 100.

**And the second half.** Every one of those lengths also has a
chromatographic run reading 0.93 – 1.00, because a gradient cut off before
anything elutes is flat, and flat is the whole of what these two figures
measure. At 20 scans the current rule calls seven of forty-eight wrong: three
infusions read as chromatographic, and **four chromatographic runs read as
infusions**.

**The rule.** Every candidate was scored by its margin — worst infusion minus
worst chromatographic run, both on the smaller figure — at every length:

| reference | 20 | 30 | 50 | 75 | 100 | whole run |
|---|---|---|---|---|---|---|
| 99th percentile (before) | −0.900 | −0.933 | −0.654 | −0.559 | +0.051 | +0.879 |
| largest scan, first second dropped | 0.000 | 0.000 | +0.521 | +0.384 | +0.418 | **−0.096** |
| median of the top ⌈1%⌉+2 scans | +0.050 | 0.000 | +0.082 | +0.054 | +0.051 | +0.879 |
| the same, first second dropped | 0.000 | 0.000 | +0.104 | +0.069 | +0.061 | +0.877 |
| **99th percentile, first second dropped** | 0.000 | 0.000 | **+0.313** | **+0.110** | **+0.061** | **+0.877** |

So the simplest honest rule is the one that wins: keep the percentile and
drop the first `SETTLING_SECONDS` of acquisition, which is where the
transient is — scan 1, 0.0084 min, at a quarter-second cycle. The two
alternatives were measured and both fail somewhere. Dropping the first second
*alone*, with the largest scan back as the reference, fails at full length:
`DCA-d4_TOFMSMS_Mix1` carries two more bursts at 1.08 and 1.10 min, which no
settling window reaches, and it reads **0.0043**. And the median of the top
⌈1% of n⌉+2 scans — a reference tied to the run's length, which is the other
obvious way to make the top robust — survives one spike anywhere but not
three: on that same file truncated to 300 scans, where all three bursts are
in and k is 5, the median of the top five *is* a burst and the file reads
**0.0100**.

With the first second dropped the infusion side stops moving with the length
at all — 1.0000 at every truncation from 20 scans to 250, 0.9936 on the whole
run:

| first N scans | infusions (9) | chromatographic |
|---|---|---|
| 20 | 1.0000 – 1.0000 | 0.0000 – 1.0000 (39) |
| 30 | 1.0000 – 1.0000 | 0.0357 – 1.0000 (39) |
| 50 | 1.0000 – 1.0000 | 0.0208 – 0.6875 (39) |
| 75 | 1.0000 – 1.0000 | 0.0274 – 0.8904 (13) |
| 100 | 1.0000 – 1.0000 | 0.0211 – 0.9388 (13) |
| the whole run | 0.9936 – 1.0000 | 0.0145 – 0.1167 (39) |

**The floor.** The right-hand column is the part no reference statistic
fixes, and it is why `MIN_JUDGED_SCANS` exists. `260904_EICs_Isabela_S001`'s
total ion chromatogram is empty until 8.9 minutes in. Truncated to its first
100 scans it reads **1.0000 on the sample total and 0.9388 on its strongest
channel** — an infusion's signature exactly, on a gradient. No statistic on a
chromatogram separates those, because there is nothing there to separate:
both are a flat line. Read scan by scan that file is flat to 107 scans
(4.08 min), not flat from 108 to 153, flat again from 154 to 234
(5.84 – 8.93 min), and never after 235.

So **0.75 does not separate the two populations at any length below 240
scans**. That is the measured floor and it is above the shortest real
infusion, which has 146 scans, so putting the floor there would refuse a
genuine call. The floor goes where the rest of the measurement supports it:
**apart from that one file, no chromatographic run of the thirty-nine reads
flat past 35 scans**, and the shortest infusion has 146, so
`MIN_JUDGED_SCANS` is **120** — clear of 35 by a wide margin and 26 scans
below 146. S001's second stretch is above 120 and no floor that keeps the
146-scan infusion can reach it; that is stated rather than fixed.

The floor gates the flat answer only, never the other one. A run that shows
structure is chromatographic at any length — that is a positive finding, and
it is what keeps the twenty-six 61-scan runs reading "chromatographic" with
their figures rather than "too short to tell". A run that shows none is an
infusion only when there is enough of it for "none" to mean something. With
that, and the settling window (**wrong** is a verdict of the other kind, not
a refusal):

| first N scans | files | before: inf / chrom / **wrong** | after: inf / chrom / **wrong** / too short |
|---|---|---|---|
| 20 | 48 | 6 / 35 / **7** | 0 / 35 / **0** / 13 |
| 30 | 48 | 6 / 35 / **7** | 0 / 35 / **0** / 13 |
| 50 | 48 | 6 / 39 / **3** | 0 / 39 / **0** / 9 |
| 75 | 22 | 7 / 12 / **3** | 0 / 12 / **0** / 10 |
| 100 | 22 | 9 / 12 / **1** | 0 / 12 / **0** / 10 |
| 120 | 22 | 9 / 13 / **0** | 9 / 13 / **0** / 0 |
| 200 | 21 | 8 / 12 / **1** | 8 / 12 / **1** / 0 |
| the whole run | 48 | 9 / 39 / **0** | 9 / 39 / **0** / 0 |

The floor is bought with a real loss and it is on that table: a genuine
infusion of fewer than 120 scans reads 1.0000 on both figures and is refused
anyway. None of the nine to hand is that short. The single row where the new
rule is still wrong is 200 scans, and it is S001 inside its flat stretch —
the case the floor cannot reach. At ten scans the settling window cannot be
taken at all (fewer than `MIN_SCANS` would be left) and the three spiked
infusions read chromatographic; below the floor nothing is called an infusion
anyway, so nothing turns on it.

Measured
--------

Forty-eight acquisitions, everything to hand, read through `milq.raw`,
whole runs, with the reference at the 99th percentile of the scans left after
the settling window:

| acquisition set | n | `above_half` | `channel_above_half` |
|---|---|---|---|
| `/Volumes/NOBRE/Cyborg/Bileomics/*` — ZenoTOF 7600, 0.6 – 2.0 min, 146 – 473 scans, product-ion infusions of bile-acid standards, negative | 9 | 0.9936 – 1.0000 | 0.9936 – 1.0000 |
| `260904_EICs_Isabela_*` — TripleTOF 5600, 21.4 min, 577 scans, 81 channels, MRM-HR | 5 | 0.019 – 0.057 | 0.030 – 0.097 |
| `20.02.21_Esfing_Zeca_Unicamp_*` — TripleTOF 5600, 14.6 min, 61 scans, 144 channels | 26 | 0.033 – 0.433 | 0.017 – 0.383 |
| `260406-Teste-*` — ZenoTOF 7600, 24.0 min, 482 – 490 scans, 25 channels, DIA | 8 | 0.031 – 0.364 | 0.015 – 0.060 |

**Nothing is miscalled: 9 infusions and 39 chromatographic runs, 48 of 48.**
The runs with the least chromatography in them are still caught by the second
figure rather than the first. `260406-Teste-Eq01` is a column equilibration
with no injection at all — solvent spraying for 24 minutes, the nearest thing
in the set to an infusion — and measures 0.364 on the sample total against
0.060 on its strongest channel. `20.02.21_Esfing_Zeca_Unicamp_08`, at 0.383 on
its strongest channel, measures 0.050 on the sample total. Across the
thirty-nine the smaller of the two figures never exceeds **0.1167**, and across
the nine infusions it never falls below **0.9936**. `FLAT_FRACTION = 0.75`
therefore sits 0.633 above the worst chromatographic run and 0.244 below the
worst infusion, inside a gap of 0.877. The maximum-margin cut would be 0.555;
0.75 is kept because it is already inside the gap, it is the figure the manual
states, and moving it would change verdicts on nothing measured.

The same forty-eight without the settling window — that is, the rule as it
stood before short runs were measured — give 0.9937 – 1.0000 and a
chromatographic worst of 0.1148, a gap of 0.879. Dropping a second off the
front of every trace therefore costs 0.002 of margin on whole runs and buys
everything in the section above.

Three other candidate rules were measured and are not used:

*Scan-to-scan spectral correlation.* The cosine between the average spectrum
of the first fifth of a run and that of the last fifth, binned at 0.1 Da, was
expected to be low for chromatography and near one for an infusion. On the
survey channel it behaves: 0.004 – 0.79 over the same thirty-nine files. On
the **product-ion** channel — the channel an infusion is actually shown from —
it does not: the five `260904_EICs_Isabela_*` runs measure 0.847, 0.933,
0.987, 0.990 and 0.992, because a single MRM-HR transition sees the same near
empty background at both ends of a gradient. A rule that would have to be told
which channel to look at, and that answers 0.99 for a chromatographic run on
the channel that matters, is worse than not having it.

*Coefficient of variation of the total ion chromatogram.* 0.398 – 1.493 over
the same files, the low end being a blank. An infusion whose spray falls by a
third over the run — ordinary — lands close enough to 0.4 that there is no
margin to place a threshold in, and the measure punishes drift, which is not
what is being asked.

*Absence of any peak-shaped feature.* `processing.detect_peaks` on a
synthetic flat trace of 1,000 counts with 3% noise returns three peaks, of
106, 93 and 87 counts. That is the documented behaviour rather than a
surprise — a flat trace gives `estimate_noise` nothing to measure, so
detection falls back to `NOISE_FLOOR` and gates on absolute height — but it
makes "no peak was detected" the wrong question to ask of an infusion.

Getting the verdict wrong stays cheap by design: it only decides what the
Explorer shows first, every channel and every range stays reachable by hand,
`Average whole run` gives the same view on any sample, and the default
whenever anything cannot be measured is "not an infusion", which is what the
application did before this module existed.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass

import numpy as np

from .processing import (NOISE_PEAK_RELATIVE, SpectrumNoise, quiet_window,
                         spectrum_noise)

#: how much of a run has to sit at or above half its maximum total ion current
#: before it is called flat. Measured on both populations: the worst
#: chromatographic acquisition reaches 0.1167 on the smaller of the two
#: figures and the worst infusion 0.9936, so this sits inside a gap of 0.877.
FLAT_FRACTION = 0.75

#: the reference height every figure is taken against, as a percentile of the
#: run's scans. **Not the largest scan**: one spray transient at 2.8–4.4 times
#: the median put three of nine real infusions at 0.002–0.006 and turned the
#: two populations the wrong way round. See the module docstring for the
#: measurement behind this particular percentile.
REFERENCE_PERCENTILE = 99.0

#: how much of the front of a trace is left out of both the reference and the
#: count. The spray transient that inverted the two populations is at scan 1,
#: 0.0084 min into the run; a percentile only sets it aside while there are
#: enough scans for one per cent to be more than one of them, which below
#: about a hundred scans it is not. Measured, dropping the first second takes
#: the worst infusion from 0.0200 to 1.0000 at fifty scans and costs 0.002 of
#: margin on whole runs. Not applied when it would leave fewer than
#: `MIN_SCANS`.
SETTLING_SECONDS = 1.0

#: below this there is not enough of a run to say anything about its shape
MIN_SCANS = 8

#: how long a run has to be before *flatness* is evidence of a spray. A
#: gradient cut off before anything elutes is flat too, and no statistic on a
#: chromatogram tells the two apart: `260904_EICs_Isabela_S001` truncated to
#: its first 100 scans reads 1.0000 on the sample total and 0.9388 on its
#: strongest channel. Apart from that one file no chromatographic run of the
#: thirty-nine reads flat past 35 scans, and the shortest infusion measured
#: has 146 — so this sits between them. It gates the flat answer only: a run
#: showing structure is chromatographic at any length.
MIN_JUDGED_SCANS = 120


@dataclass(frozen=True)
class InfusionVerdict:
    """What a sample looks like, and the figures that say so."""

    infusion: bool
    reason: str
    #: scans in the sample's total ion chromatogram
    n_scans: int = 0
    #: the run from its first scan to its last, in minutes
    length_min: float = 0.0
    #: fraction of the sample's total ion chromatogram at or above half its
    #: own maximum — the `REFERENCE_PERCENTILE`-th scan, not the largest one
    above_half: float = 0.0
    #: the same on the channel the average would be shown from
    channel_above_half: float = 0.0
    #: index of that channel, -1 when there is none
    channel_index: int = -1
    #: the run was flat on both figures but too short for that to be
    #: evidence — see `MIN_JUDGED_SCANS`. Still `infusion = False`: the
    #: default whenever anything cannot be decided is "not an infusion".
    too_short: bool = False

    def __bool__(self) -> bool:
        return self.infusion


def above_half_fraction(y, percentile: float = REFERENCE_PERCENTILE) -> float:
    """
    The fraction of a trace sitting at or above half its own maximum.

    The maximum is the `percentile`-th of the scans rather than the largest
    of them, because the largest is one scan and a spray transient is one
    scan. Three of nine real infusions carry one, and read 0.002 – 0.006 when
    the largest scan is the reference against 0.994 – 1.000 when the 99th
    percentile is. Every scan is still counted; only the height they are
    counted against changes.

    This is the measure on a trace as given. `flat_fraction` is the one the
    verdict reads, and it drops the settling window first — a percentile is
    a share of the scans, and on a short run that share is one scan.
    """
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return 0.0
    top = float(np.percentile(y, percentile)) if percentile < 100 else float(
        np.max(y))
    if top <= 0:
        return 0.0
    return float(np.mean(y >= 0.5 * top))


def after_settling(x, y, seconds: float = SETTLING_SECONDS):
    """
    The trace with the first `seconds` of acquisition left out.

    A percentile sets aside a *share* of the scans, so on a short run the
    99th of them is the largest again and one spray transient decides the
    answer. The transient is not just anywhere in the run, though: on all
    three files that carry one it is at scan 1, 0.0084 min in. Leaving out a fixed piece of the front rather than a
    share of the whole is what makes the measure stop moving with the run's
    length — measured, 1.0000 on every infusion from twenty scans upwards.

    Refuses to cut when fewer than `MIN_SCANS` would be left, which is the
    only case where the window could be most of the run.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if seconds <= 0 or x.size == 0:
        return x, y
    keep = x >= x[0] + seconds / 60.0
    return (x[keep], y[keep]) if int(keep.sum()) >= MIN_SCANS else (x, y)


def flat_fraction(x, y, percentile: float = REFERENCE_PERCENTILE) -> float:
    """`above_half_fraction` of what is left after the settling window."""
    return above_half_fraction(after_settling(x, y)[1], percentile)


def strongest_channel(sample):
    """
    The channel an infusion should be shown from: the product-ion channel
    carrying the most signal, or the survey when the method has no product
    scan.

    An infusion is nearly always run to look at one compound's fragments, and
    the survey — where the Explorer would otherwise land, it being the first
    channel of the method — is the one channel that does not show them. Total
    signal rather than height picks the channel actually carrying the compound
    among the several a method may declare, without caring where in the run it
    arrived.
    """
    channels = list(getattr(sample, "channels", None) or [])
    if not channels:
        return None

    def total(channel) -> float:
        try:
            y = np.asarray(channel.tic()[1], dtype=float)
        except Exception:
            return -1.0
        return float(np.sum(y)) if y.size else -1.0

    products = [c for c in channels if not c.info.is_ms1]
    return max(products or channels, key=total)


def run_range(channel) -> tuple[float, float] | None:
    """The channel's whole time axis, as a range to average over."""
    try:
        times = np.asarray(channel.rt, dtype=float)
    except Exception:
        return None
    if times.size == 0:
        return None
    return float(times[0]), float(times[-1])


# --------------------------------------------------------------------------- #
# Scans a spray lost
# --------------------------------------------------------------------------- #
#: how many scans the robust baseline is taken over. A running median survives
#: a disturbance up to half its width, and the longest one measured is eight
#: scans — `DCA-d4_TOFMSMS_Mix1` at 1.07 – 1.10 min — so the window has to be
#: at least seventeen or the burst decides its own baseline. Measured, the
#: excluded count on that file is 6 at eleven scans, 8 at fifteen and 9 from
#: twenty-one upwards, where it stops moving; a spray drifts over minutes and
#: twenty-one scans is 5.3 s at the quarter-second cycle these were acquired
#: at, so the window still follows the drift (the kept scans' median departure
#: is 0.014 – 0.065 either way).
STABILITY_WINDOW = 21

#: how far a scan's total ion current may depart from that baseline before the
#: spray is called unstable, as a fraction. **Measured on the nine bile-acid
#: infusions**: the widest departure of an undisturbed spray is 0.316
#: (`TDCA-d4_TOFMSMS_Mix1`, whose spray wanders), and the smallest departure
#: inside a real burst is 0.870 — a gap of 2.75×, and the count of excluded
#: scans is identical anywhere from 0.35 to 0.85. This is the middle of it.
SPRAY_JUMP = 0.5

#: how close to the baseline the current has to come back before the spray
#: counts as recovered. A burst is not one scan: `DCA-d4_TOFMSMS_Mix1` goes
#: 0.01, 0.03, 0.64, 2.57, 0.63, 0.13, 0.74, 4.68 of its baseline over eight
#: scans, and the three scans at 0.64, 0.63 and 0.74 are past this and under
#: `SPRAY_JUMP` — half-recovered, and not what the compound looks like.
#: Measured, the count is the same at 0.15, 0.20 and 0.25 and starts losing
#: those scans at 0.30. What it does *not* buy is a tail: on both real bursts
#: and all three transients the scan after the last excluded one is already
#: within 0.13 of the baseline, so a spray here recovers inside one scan.
SPRAY_RECOVERED = SPRAY_JUMP / 2


@dataclass(frozen=True, eq=False)
class ScanMask:
    """
    Which scans of an infusion are the spray behaving, and which are not.

    `keep` is one boolean per scan of the channel; everything else on this is
    that array said in words. `ranges` is what a header line and a library
    record's comment carry — "0.008 min; 1.069–1.099 min, 8 scans" — a single
    scan named by its time and a stretch by its ends.
    """

    #: one entry per scan: True where the scan goes into the average
    keep: np.ndarray
    #: the channel's own time axis, so the ranges can be read back
    rt: np.ndarray
    #: the excluded scans' times, as text; empty when nothing was excluded
    ranges: str = ""
    #: why nothing was judged, when nothing was — a run too short to have a
    #: baseline, or a channel that could not be read. Empty when it was.
    note: str = ""
    #: the kept scans' median |total / baseline − 1|: the ordinary scatter of
    #: this spray, which is what `SPRAY_JUMP` had to be set clear of
    scatter: float = 0.0

    @property
    def n_scans(self) -> int:
        return int(self.keep.size)

    @property
    def kept(self) -> int:
        return int(np.count_nonzero(self.keep))

    @property
    def excluded(self) -> int:
        return int(self.keep.size - np.count_nonzero(self.keep))

    def __bool__(self) -> bool:
        """True when the mask leaves anything out."""
        return self.excluded > 0

    def segments(self) -> list[tuple[int, int]]:
        """The kept scans as runs of consecutive indices, first and last."""
        return _runs(np.flatnonzero(self.keep))

    def summary(self) -> str:
        """
        One line: how many scans there were, how many were averaged, and
        where the rest went.
        """
        if self.note:
            return f"{self.n_scans:,} scans, all averaged ({self.note})"
        if not self.excluded:
            return f"{self.n_scans:,} scans, all averaged"
        return (f"{self.n_scans:,} scans, {self.kept:,} averaged; "
                f"{self.excluded:,} left out: {self.ranges}")


def _runs(indices: np.ndarray) -> list[tuple[int, int]]:
    """Consecutive indices grouped into (first, last) pairs."""
    out: list[tuple[int, int]] = []
    for i in (int(v) for v in indices):
        if out and i == out[-1][1] + 1:
            out[-1] = (out[-1][0], i)
        else:
            out.append((i, i))
    return out


def running_median(y, window: int = STABILITY_WINDOW) -> np.ndarray:
    """
    A median through the trace, `window` scans wide, clamped at the ends.

    The baseline a scan is judged against has to be local: a spray falls by a
    third over a run and the run's own median would call the whole second half
    unstable. It also has to be robust, because the thing being looked for is
    in the window while the window is being measured.
    """
    y = np.asarray(y, dtype=float)
    window = max(3, int(window) | 1)          # odd, so there is a centre
    if y.size == 0:
        return y
    half = window // 2
    padded = np.pad(y, half, mode="edge")
    return np.array([np.median(padded[i:i + window]) for i in range(y.size)])


def stable_scans(channel, jump: float = SPRAY_JUMP,
                 window: int = STABILITY_WINDOW,
                 recovered: float = SPRAY_RECOVERED) -> ScanMask:
    """
    Which scans of an infusion the spray was steady for.

    An electrospray is not steady for the whole of a run. It arcs, a droplet
    reaches the cone, the needle wets: the total ion current leaves the level
    it was holding for a few scans and comes back. Averaged in with everything
    else, those scans are a few tenths of a per cent of a two-minute run and
    move nothing — but they are not what the compound looks like, and one of
    them is a fifth of the whole run's ion current.

    A scan is unstable when its total departs from the running median of
    `window` scans by more than `jump`; the scans after it stay unstable until
    the total is back inside `recovered`. Both figures were measured on nine
    real infusions and both sit in a plateau — see the constants.

    **Why the total and not the base peak.** The reader offers `bpc()` for the
    same price as `tic()` and it was measured beside it. It is four to eight
    times the noisier: on the six infusions with no burst at all the base peak
    departs from its own running median by up to 0.585 where the total never
    passes 0.164, so any threshold that catches a burst on the base peak also
    catches ordinary scans on a spray that never faltered. And it finds
    nothing new — every scan it flags on the two files that do burst, the
    total flags too. So the mask reads the total, and says so here rather than
    reading both and hoping.

    **The first second.** `SETTLING_SECONDS` is not applied. It exists because
    a *percentile* sets aside a share of the scans and on a short run that
    share is one scan; this measures each scan against its neighbours instead,
    and the transient at scan 1 comes out at 4.5, 5.1 and 5.0 times its
    baseline on the three files that carry one — thirteen times the widest
    ordinary departure measured. Dropping four scans of every run to catch
    what is already caught would be throwing away data no measurement objects
    to, which on the shortest infusion to hand is 2.7% of it.

    A run with no baseline to speak of — fewer than `MIN_SCANS` — keeps every
    scan and says why in `note`. So does a channel that cannot be read.
    """
    try:
        x, y = channel.tic()
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
    except Exception as exc:
        first = str(exc).strip().splitlines()
        return ScanMask(np.zeros(0, dtype=bool), np.zeros(0),
                        note=f"the run could not be read: "
                             f"{first[0] if first else type(exc).__name__}")
    if y.size < MIN_SCANS:
        return ScanMask(np.ones(y.size, dtype=bool), x,
                        note=f"{y.size} scan(s): too short to measure a "
                             f"baseline against")

    baseline = running_median(y, window)
    measurable = baseline > 0
    departure = np.zeros(y.size, dtype=float)
    departure[measurable] = np.abs(y[measurable] / baseline[measurable] - 1.0)
    if not measurable.any():
        return ScanMask(np.ones(y.size, dtype=bool), x, note="the run is empty")

    unstable = measurable & (departure > jump)
    for start in np.flatnonzero(unstable).tolist():
        after = start + 1
        while after < y.size and measurable[after] \
                and departure[after] > recovered:
            unstable[after] = True
            after += 1
    keep = ~unstable
    if int(np.count_nonzero(keep)) < MIN_SCANS:
        # a run that is mostly burst is not a spray that settled, and an
        # average of the handful left is a worse answer than the whole of it
        return ScanMask(
            np.ones(y.size, dtype=bool), x,
            note=f"{int(unstable.sum())} of {y.size} scans are unstable — "
                 f"too much of the run to leave out")
    return ScanMask(keep, x, ranges=_range_text(x, unstable),
                    scatter=float(np.median(departure[keep])))


def mask_for(sample, channel) -> ScanMask:
    """
    `stable_scans`, but only where the sample reads as a direct infusion.

    A chromatographic run answers the same question with the same arithmetic
    and the answer is nonsense: a peak departs from its neighbours by far more
    than `SPRAY_JUMP` — that is what a peak *is* — so on a twenty-minute
    gradient with three peaks in it the rule leaves out twenty-nine scans and
    they are the only twenty-nine worth keeping. *Average whole run* is
    offered on any channel, so the gate is here, where the sample is known,
    and it is the same verdict the tree and the pane already show.
    """
    try:
        infusion = bool(verdict_for(sample))
    except Exception:
        infusion = False
    if infusion:
        return stable_scans(channel)
    try:
        times = np.asarray(channel.rt, dtype=float)
    except Exception:
        times = np.zeros(0)
    return ScanMask(np.ones(times.size, dtype=bool), times,
                    note="not read as a direct infusion: every scan averaged")


def _range_text(x: np.ndarray, unstable: np.ndarray) -> str:
    """The excluded scans as times: one is named, a stretch is bounded."""
    parts = []
    for first, last in _runs(np.flatnonzero(unstable)):
        if first == last:
            parts.append(f"{x[first]:.3f} min")
        else:
            parts.append(f"{x[first]:.3f}–{x[last]:.3f} min, "
                         f"{last - first + 1} scans")
    return "; ".join(parts)


def average_stable(channel, mask: ScanMask | None = None,
                   add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """
    The kept scans of an infusion, averaged into one spectrum.

    On the same scale as `channel.spectrum_rt_range`, which is the **mean** of
    the scans in its range and not their sum — measured on a real `.wiff`, a
    two-scan range comes back as the average of the two scans' totals to the
    unit.

    The kept scans are consecutive apart from the few that were left out, so
    this asks the reader for the average of each surviving stretch and
    combines those, weighted by how many scans each holds. That keeps the
    vendor's own arithmetic wherever it can reach — a mask that excludes
    nothing is one stretch and therefore one call, byte for byte the reader's
    own answer — and leaves ours doing nothing but the weighted mean of two or
    three arrays.

    Zeros are restored the way the reader restores them for a range: once, on
    the average, not scan by scan. SCIEX's `AddZeros` is applied to the
    averaged `MassSpectrum` that `GetMassSpectrum(lo, hi)` returns, so each
    stretch comes back already carrying its zeros and the combined axis is the
    union of stretches that each already have them — which is also what keeps
    the interpolation honest, since a profile with its zeros in has no gap for
    a straight line to be drawn across.
    """
    if mask is None:
        mask = stable_scans(channel)
    window = run_range(channel)
    if window is None:
        return np.zeros(0), np.zeros(0)
    segments = mask.segments() if mask.keep.size else []
    if not segments:
        return channel.spectrum_rt_range(*window, add_zeros=add_zeros)
    times = np.asarray(mask.rt, dtype=float)
    if len(segments) == 1 and segments[0] == (0, times.size - 1):
        # nothing was left out: the reader's own average of the whole run,
        # untouched, which is what it was before any of this existed
        return channel.spectrum_rt_range(*window, add_zeros=add_zeros)

    parts, weights = [], []
    for first, last in segments:
        mz, intensity = channel.spectrum_rt_range(
            float(times[first]), float(times[last]), add_zeros=add_zeros)
        mz = np.asarray(mz, dtype=float)
        if mz.size == 0:
            continue
        parts.append((mz, np.asarray(intensity, dtype=float)))
        weights.append(float(last - first + 1))
    if not parts:
        return np.zeros(0), np.zeros(0)
    if len(parts) == 1:
        return parts[0]
    axis = np.unique(np.concatenate([mz for mz, _ in parts]))
    total = np.zeros(axis.size, dtype=float)
    for (mz, intensity), weight in zip(parts, weights):
        total += weight * np.interp(axis, mz, intensity, left=0.0, right=0.0)
    return axis, total / float(sum(weights))


def is_infusion(sample) -> InfusionVerdict:
    """
    Whether this sample is a direct infusion, with the figures behind it.

    Reads chromatograms only; never a spectrum. A sample that cannot be read
    at all is not an infusion, and says why.
    """
    try:
        x, y = sample.tic()
    except Exception as exc:
        first = str(exc).strip().splitlines()
        return InfusionVerdict(
            False, f"the run could not be read: "
                   f"{first[0] if first else type(exc).__name__}")
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.size < MIN_SCANS:
        return InfusionVerdict(
            False, f"only {x.size} scan(s) — too short a run to tell",
            n_scans=int(x.size), too_short=True)

    length = float(x[-1] - x[0])
    flat = flat_fraction(x, y)
    channel = strongest_channel(sample)
    if channel is None:
        return InfusionVerdict(False, "the sample has no channels",
                               n_scans=int(x.size), length_min=length,
                               above_half=flat)
    try:
        channel_flat = flat_fraction(*channel.tic())
    except Exception:
        channel_flat = 0.0
    figures = dict(n_scans=int(x.size), length_min=length, above_half=flat,
                   channel_above_half=channel_flat,
                   channel_index=int(channel.index))

    limit = f"{FLAT_FRACTION * 100:.0f}%"
    if flat >= FLAT_FRACTION and channel_flat >= FLAT_FRACTION:
        if x.size < MIN_JUDGED_SCANS:
            # flat, but a run cut off before anything eluted is flat too, and
            # nothing on a chromatogram tells those apart. The default when
            # anything cannot be decided is "not an infusion".
            return InfusionVerdict(
                False,
                f"flat throughout — {flat * 100:.0f}% of the run and "
                f"{channel_flat * 100:.0f}% of its strongest channel sit at "
                f"or above half the maximum — but {x.size} scans is under "
                f"the {MIN_JUDGED_SCANS} a flat run needs before flatness "
                f"means anything, since a run that stopped before anything "
                f"eluted looks the same: too short to tell, so not an "
                f"infusion",
                too_short=True, **figures)
        return InfusionVerdict(
            True,
            f"the signal never falls away: {flat * 100:.0f}% of the run and "
            f"{channel_flat * 100:.0f}% of its strongest channel sit at or "
            f"above half the maximum (the {REFERENCE_PERCENTILE:g}th-percentile "
            f"scan), over {length:.2f} min — an infusion",
            **figures)
    if flat < FLAT_FRACTION:
        return InfusionVerdict(
            False,
            f"only {flat * 100:.0f}% of the run is at or above half the "
            f"maximum total ion current (the {REFERENCE_PERCENTILE:g}th-"
            f"percentile scan), where {limit} would make it an infusion "
            f"— chromatographic",
            **figures)
    return InfusionVerdict(
        False,
        f"the run as a whole is flat ({flat * 100:.0f}% above half maximum) "
        f"but its strongest channel is not ({channel_flat * 100:.0f}%, {limit} "
        f"needed) — peaks at different times, not an infusion",
        **figures)


# --------------------------------------------------------------------------- #
# the noise floor of the average
# --------------------------------------------------------------------------- #
#: how wide the quiet mass window of the second estimate is. The same stretch
#: `precursor.SEARCH_WINDOW` reaches either side of a target, because that is
#: the window the floor is applied in: `precursor.in_spectrum` takes the
#: tallest point within +-0.25 Da, and what the second estimate answers is how
#: much such a window scatters between scans where there is nothing in it.
QUIET_WINDOW_DA = 0.5


def format_counts(value: float) -> str:
    """
    An intensity for a sentence, at three figures and never in exponent form.

    A measured floor spans four orders of magnitude across the acquisitions
    to hand — 0.06 counts on one infusion and 10 on a chromatographic average
    — and `%g` writes the big end as `1e+03`, which nobody reads as a number
    of counts.
    """
    value = float(value)
    if value >= 100:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.3g}"


def _fixed_floor() -> float:
    """
    The floor used when nothing can be measured: `precursor.MIN_INTENSITY`,
    imported where it is needed rather than at the top of the module, since
    `precursor` imports this one.
    """
    from .precursor import MIN_INTENSITY
    return float(MIN_INTENSITY)


@dataclass(frozen=True)
class NoiseFloor:
    """
    The intensity below which a centroid of an averaged spectrum is noise,
    measured from the acquisition, with both estimates on the record.
    """

    #: the floor itself, in the intensity units of the averaged spectrum
    value: float
    #: (a) the empty mass regions of the averaged spectrum
    empty: SpectrumNoise | None = None
    #: (b) the scan-to-scan scatter of a quiet window, scaled to the average
    scatter: float | None = None
    #: (b) before it was scaled: the standard deviation between single scans
    per_scan: float | None = None
    #: the quiet window (b) was measured over
    window: tuple[float, float] | None = None
    #: how many scans went into the average
    scans: int = 0
    #: how many scans the scan-to-scan standard deviation was taken over —
    #: the whole run, which on an infusion is the same number
    run_scans: int = 0
    #: the base peak of the averaged spectrum, for a floor as a fraction
    base_peak: float = 0.0
    #: the fixed floor this is measured against
    fixed: float = 100.0
    #: False when nothing could be measured and `fixed` was taken instead
    measured: bool = False
    note: str = ""

    @property
    def gain(self) -> float:
        """What averaging bought: noise falls as the root of the count."""
        return float(np.sqrt(self.scans)) if self.scans > 0 else 1.0

    @property
    def from_empty(self) -> float | None:
        """
        (a), the figure the floor may be taken from: the height a noise
        *peak* of the empty regions reaches, not the height one of their
        points reaches. `SpectrumNoise.p99` is on the record beside it.
        """
        return None if self.empty is None else self.empty.peak_p99

    @property
    def basis(self) -> str:
        """Which of the two estimates the floor was taken from."""
        if not self.measured:
            return "not measured"
        empty = self.from_empty
        if empty is not None and self.scatter is not None:
            return ("the empty regions of the average"
                    if empty >= self.scatter else
                    "the scan-to-scan scatter of a quiet window")
        if empty is not None:
            return "the empty regions of the average"
        return "the scan-to-scan scatter of a quiet window"

    @property
    def relative(self) -> float | None:
        """The floor as a fraction of the base peak."""
        if self.base_peak <= 0:
            return None
        return self.value / self.base_peak

    @property
    def quieter_than_fixed(self) -> bool:
        """The instrument is quieter than the constant that stood here."""
        return self.measured and self.value < self.fixed

    def describe(self) -> str:
        """One sentence: the two estimates, the choice, and what n bought."""
        if not self.measured:
            return (f"the noise floor could not be measured"
                    f"{f' ({self.note})' if self.note else ''}, so the fixed "
                    f"{format_counts(self.fixed)} counts stands")
        bits = []
        if self.empty is not None:
            bits.append(f"the empty mass regions of the average reach "
                        f"{format_counts(self.empty.peak_p99)} counts at the "
                        f"99th percentile of their {self.empty.maxima:,} "
                        f"peaks (their {self.empty.points:,} points sit at a "
                        f"median {format_counts(self.empty.median)}, MAD "
                        f"{format_counts(self.empty.mad)}, 99th percentile "
                        f"{format_counts(self.empty.p99)})")
        if self.scatter is not None and self.window is not None:
            bits.append(f"m/z {self.window[0]:,.1f}–{self.window[1]:,.1f} "
                        f"scatters by {format_counts(self.per_scan)} counts "
                        f"between single scans over {self.run_scans:,} of "
                        f"them, which {self.scans:,} scans averaged divides "
                        f"by {self.gain:,.1f} to "
                        f"{format_counts(self.scatter)}")
        said = (f"Measured noise floor {format_counts(self.value)} counts, "
                f"from {self.basis}: " + "; ".join(bits) + ".")
        if self.quieter_than_fixed:
            said += (f" That is under the fixed "
                     f"{format_counts(self.fixed)} counts this used to be "
                     f"held to — the acquisition is quieter than the "
                     f"constant, so the measurement stands.")
        return said


def noise_floor(channel, rt0: float | None = None, rt1: float | None = None,
                min_relative: float = NOISE_PEAK_RELATIVE,
                width: float = QUIET_WINDOW_DA,
                spectrum: tuple | None = None,
                scans: int | None = None) -> NoiseFloor:
    """
    The noise floor of an infusion's averaged spectrum, measured two ways.

    A fixed floor is a guess about an instrument. `precursor.MIN_INTENSITY`
    is 100 counts and it was written for a survey scan of a chromatographic
    run — one scan, on a TripleTOF. An infusion's spectrum is the
    average of every scan of the run, and an average has neither the units
    nor the noise of one scan.

    So it is measured, from the acquisition itself, two ways that fail
    differently. Both are reported and the larger is taken.

    **(a) The empty mass regions of the averaged profile spectrum.** Every
    centroid at or above `min_relative` of the base peak is found and half a
    dalton either side of it set aside (`processing.NOISE_EXCLUDE_DA`); what
    is left is between the isotope clusters and away from every peak. The
    median, the median absolute deviation and the 99th percentile of the
    measured points there describe the background, and the 99th percentile
    of the *local maxima* among them is the height a noise peak reaches —
    which is the one the floor is taken from, since what it gates is the
    tallest point of a window and not a point drawn at random. Both are on
    the record. Points of exactly zero are left out, so a reader that
    restores a vendor's stripped zeros and one that does not give the same
    answer.

    **(b) The scan-to-scan scatter of a quiet mass window.** The quietest
    window `width` wide that holds no peak at all is extracted over the whole
    run — the same window in every scan — and the standard
    deviation of its summed intensity taken between scans. Averaging n scans
    divides noise by the root of n, so that standard deviation is divided by
    it in turn; the record keeps both numbers, because what n bought is the
    interesting half. (a) can only see what is left after averaging; (b)
    reads the averaging itself.

    The floor is never invented: where neither estimate can be made the
    record says so and carries `precursor.MIN_INTENSITY`, which is what
    stood here before. Where the measurement comes out under that constant
    the measurement is used and `quieter_than_fixed` says so.

    Measured
    --------

    The nine ZenoTOF 7600 bile-acid infusions (positive, one product-ion
    channel each, no survey scan), each averaged over its whole run. `n` is
    the scans averaged, and every intensity is in the units of that average:

    | acquisition | n | base peak | (a) | (b) | floor |
    |---|---|---|---|---|---|
    | `CA-d4_…12CE…TESTEARTIGO` | 294 | 109 | 0.068 | 0.026 | **0.068** |
    | `CA-d4_…12CE…mix1` | 244 | 12,271 | 3.53 | 0.130 | **3.53** |
    | `CA-d4_…22CE…TESTEARTIGO` | 311 | 234 | 0.129 | 0.040 | **0.129** |
    | `CA-d4_…22CE…mix1` | 146 | 9,618 | 3.12 | 0.357 | **3.12** |
    | `CA-d4_Mix1` CID 45 eV | 473 | 5,673 | 0.962 | 0.232 | **0.962** |
    | `DCA-d4_…22CE…mix1` | 473 | 9,151 | 2.67 | 0.179 | **2.67** |
    | `DCA-d4_Mix1` CID 40 eV | 473 | 3,109 | 0.583 | 0.172 | **0.583** |
    | `TDCA-d4_…22CE…mix1` | 468 | 5,235 | 1.47 | 0.111 | **1.47** |
    | `TDCA-d4_Mix1` CID 30 eV | 257 | 9,044 | 2.45 | 0.253 | **2.45** |

    **(a) is the larger on nine of nine**, by 2.6 to 27 times, so
    the choice never fell to (b) on these files — but (b) is what says the
    averaging worked: one scan's window scatters by 0.45 to 5.05 counts and
    the average of 146 to 473 of them by 0.026 to 0.36, a factor of 12 to 22,
    which is the root of n to within the width of the estimate. The two
    percentiles of (a) agree on six of the nine and differ on three, most
    where the background is nearly all of the spectrum: peaks 0.068 against
    points 0.058, 0.129 against 0.119, and 0.583 against 0.570.

    Against the fixed 100 counts, every one of the nine is quieter — by a
    factor of 28 on the loudest and 1,500 on the quietest. The floor decides
    the precursor read off the average, and there it moves **four** of the
    nine from *too little to measure* to a measurement: 84 counts on
    `CA-d4_Mix1` is 88 times its floor, and 33 on `DCA-d4_Mix1` is 57 times
    its own. What those four then measure is a different matter and not this
    function's:
    they come out at −30 to −70 ppm from the written precursor and none of
    them joins the four already inside 25 ppm. The height says a peak is
    there; the mass says whether it is the compound.

    Twelve chromatographic acquisitions for contrast, on a different
    instrument and a real gradient: a TripleTOF 5600, 81 channels each, the
    strongest product-ion channel of every one averaged over the boundaries
    of its own largest peak — 3 to 67 scans, peaks of 352 to 590,000 counts.
    Eleven of the twelve are measured, at (a) 0.69 to 20.1 counts against (b)
    0.23 to 3.25, **(a) the larger on eleven of eleven** as it was on the
    infusions, so the floor is 0.69 to 20.1. The loudest of them,
    `260904_…5E_003` on `TOF PI 325.20 -> 50-330, CE -45`, averages the 13
    scans of a peak 567,000 counts tall and comes out at **20.1 counts** —
    three hundred times the quietest infusion's, because thirteen scans
    averaged is not four hundred, and the fixed 100 was still five times too
    strict.

    The twelfth is the fallback firing on real data rather than in a test.
    `260903_…Cal001`'s strongest product channel holds a peak of 352 counts
    over three scans; the average of those three has 167 measured points in
    412 and no empty region wide enough to measure in, so neither estimate
    can be made, `measured` is False, and the fixed 100 counts stands with
    the reason on the record. A quiet acquisition and an acquisition with
    nothing in it are not the same thing, and only one of them gets a
    measurement.

    The limit, stated rather than fixed: this is one number for a whole
    spectrum and a background is not the same at every mass. On the two
    acquisitions of the nine that hold nothing at all, the empty regions are
    the high-mass end where the detector saw nothing, so the floor lands at
    0.068 and 0.129 counts while the chemical background peaks at a hundred
    — and a peak above this floor is a peak above the background, which is
    not the same claim as a peak that is the compound.

    It costs one averaged spectrum and one extracted chromatogram: 0.5 to
    1.7 s a file on those nine, opening included, and `noise_floor_for` remembers it per
    channel so the pane, the report and a record written from the spectrum
    pay for it once.

    `spectrum` is `(mz, intensity)` when the caller already holds the
    average — the report and the Explorer both do, and reading a quarter of
    a million profile points again costs seconds. The chromatogram of the
    quiet window is still read from the channel: it is the run scan by scan,
    which no averaged spectrum carries.

    `scans` is how many scans that handed-in average was taken over, where
    it is not simply every scan of the range. The report averages the stable
    stretch of the spray and leaves the rest out, so counting the range would
    divide (b) by the root of a number of scans the spectrum does not
    contain. It changes only what (b) says and what `describe` prints, since
    (a) has been the larger on every acquisition measured — but a sentence
    reading "473 scans averaged" under a spectrum averaged from 400 of them
    would be false, and the estimate would be optimistic by the ratio of the
    roots.
    """
    fixed = _fixed_floor()
    window = None
    if rt0 is None or rt1 is None:
        window = run_range(channel)
        if window is None:
            return NoiseFloor(value=fixed, fixed=fixed,
                              note="the channel has no scans")
        rt0, rt1 = window
    if spectrum is not None:
        mz, intensity = spectrum[0], spectrum[1]
    else:
        try:
            mz, intensity = channel.spectrum_rt_range(float(rt0), float(rt1))
        except Exception as exc:
            first = str(exc).strip().splitlines()
            name = first[0] if first else type(exc).__name__
            return NoiseFloor(
                value=fixed, fixed=fixed,
                note=f"the spectrum could not be read: {name}")
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    base = float(intensity.max()) if intensity.size else 0.0
    scans = (int(scans) if scans is not None
             else _scans_between(channel, float(rt0), float(rt1)))

    empty = spectrum_noise(mz, intensity, min_relative=min_relative)
    quiet = quiet_window(mz, intensity, width, min_relative=min_relative)
    scatter = per_scan = None
    run_scans = 0
    if quiet is not None:
        scatter, per_scan, run_scans = _window_scatter(channel, quiet, scans)

    candidates = [v for v in (None if empty is None else empty.peak_p99,
                              scatter)
                  if v is not None and v > 0]
    if not candidates:
        return NoiseFloor(
            value=fixed, empty=empty, scatter=scatter, per_scan=per_scan,
            window=quiet, scans=scans, run_scans=run_scans, base_peak=base,
            fixed=fixed,
            note="neither estimate could be made: the spectrum has no empty "
                 "region wide enough to measure in")
    return NoiseFloor(
        value=max(candidates), empty=empty, scatter=scatter,
        per_scan=per_scan, window=quiet, scans=scans, run_scans=run_scans,
        base_peak=base, fixed=fixed, measured=True)


def _scans_between(channel, rt0: float, rt1: float) -> int:
    """How many scans the average was taken over."""
    try:
        times = np.asarray(channel.rt, dtype=float)
    except Exception:
        return 0
    if times.size == 0:
        return 0
    lo, hi = sorted((rt0, rt1))
    return int(((times >= lo) & (times <= hi)).sum())


def _window_scatter(channel, window: tuple[float, float], scans: int):
    """
    How much a quiet window's summed intensity moves between scans, and what
    that becomes in an average of `scans` of them.

    The standard deviation is taken over **every scan of the run**, not over
    the scans that went into the average, and the division is by the root of
    the number averaged. The two are the same thing on an infusion, where the
    average is the whole run. They are not on a chromatographic average over
    a peak, and there the whole run is the better sample: a window chosen for
    holding no peak holds none all run, and six scans measure a standard
    deviation badly. The count the standard deviation was taken over comes
    back, so the record can say which was which.
    """
    try:
        _x, y = channel.xic_range(window[0], window[1])
    except Exception:
        return None, None, 0
    y = np.asarray(y, dtype=float)
    if y.size < 3:
        return None, None, int(y.size)
    per_scan = float(np.std(y, ddof=1))
    averaged = max(int(scans), 1)
    if per_scan <= 0:
        return None, per_scan, int(y.size)
    return per_scan / float(np.sqrt(averaged)), per_scan, int(y.size)


#: floors already measured, by channel, so that the report, the pane and the
#: record written from it pay for the average once. Weak, like the verdicts.
_FLOORS: "weakref.WeakKeyDictionary[object, NoiseFloor]" = (
    weakref.WeakKeyDictionary())


def noise_floor_for(channel, spectrum: tuple | None = None,
                    scans: int | None = None) -> NoiseFloor:
    """
    `noise_floor` over the whole run, measured once per channel.

    A spectrum handed in is measured and **not** remembered: what the caller
    holds may be background-subtracted or recalibrated, and a floor measured
    off one pane's conditioning is not the channel's own.
    """
    if channel is None:
        return NoiseFloor(value=_fixed_floor(), fixed=_fixed_floor(),
                          note="no channel")
    if spectrum is not None:
        return noise_floor(channel, spectrum=spectrum, scans=scans)
    try:
        floor = _FLOORS.get(channel)
    except TypeError:
        return noise_floor(channel)
    if floor is None:
        floor = noise_floor(channel)
        try:
            _FLOORS[channel] = floor
        except TypeError:
            pass
    return floor


#: verdicts already reached, by sample, so that the tree — rebuilt on every
#: file opened — and the precursor measurement — run once per component —
#: each pay for the chromatograms once. Weak, so it holds nothing open.
_REACHED: "weakref.WeakKeyDictionary[object, InfusionVerdict]" = (
    weakref.WeakKeyDictionary())


def verdict_for(sample) -> InfusionVerdict:
    """`is_infusion`, measured once per sample and remembered."""
    if sample is None:
        return InfusionVerdict(False, "no sample")
    try:
        verdict = _REACHED.get(sample)
    except TypeError:  # a sample that cannot be weakly referenced or hashed
        return is_infusion(sample)
    if verdict is None:
        verdict = is_infusion(sample)
        try:
            _REACHED[sample] = verdict
        except TypeError:
            pass
    return verdict
