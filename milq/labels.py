"""
Which peaks of a spectrum get their mass written next to them.

Picking the tallest peaks and dropping whatever will not fit is the obvious
rule and it reads badly on a survey scan. Measured on the TOF MS survey of
`260904_EICs_Isabela_1`, apex scan of the run, over m/z 100-1960: 268
maxima stand at or above 2% of the base peak, and they are not spread
evenly — 105 of them fall in the first eighth of the axis, 72 in the
second, 62 in the third, one in the last. The twelve tallest are *all* in
the first eighth, inside a stretch 118 Da wide. Everything above m/z 330 is
drawn and never named.

So the axis on screen is cut into `LABEL_REGIONS` equal windows and each
window may claim `LABEL_BUDGET` labels, tallest first. The order in which
they claim is a round of the tallest of every window, then a round of each
window's second, and so on — a dense window cannot spend three labels
before a quiet window's only peak has had its turn, which is what stops a
cluster starving a lone tall peak elsewhere. The collision rule that
already runs afterwards is unchanged: a label that would print on top of
one already placed is still dropped rather than overlapped. The budget
decides who asks; the collision rule decides who fits.

This is a drawing rule and nothing is quantified from it.

What it is worth, measured by rendering a 980 by 420 pane offscreen and
counting the labels actually drawn — the survey above at full range and
zoomed to 150-350, and the product-ion scan of `CA-d4_TOFMSMS_Mix1` (a
ZenoTOF infusion, precursor 430.35, 25,116 points):

| | offered, drawn, dropped: before | after |
|---|---|---|
| survey, 100-1960 | 12, **1**, 11 | 18, **6**, 12 |
| survey, 150-350 | 12, **4**, 8 | 23, **7**, 16 |
| product ions, 51-449 | 12, **6**, 6 | 20, **7**, 13 |

The full-range survey is the whole complaint in one number: twelve labels
offered, one drawn. The other eleven were the eleven next-tallest peaks,
all within 118 Da of the first, and at that zoom their masses are 50 pixels
apart while the text is 55 pixels wide. Nothing was overlapped and nothing
was gained.

Both constants were chosen from that rendering, and from looking at the
pictures — see `LABEL_REGIONS` and `LABEL_BUDGET`.
"""

from __future__ import annotations

from collections.abc import Sequence

#: how many equal windows the visible mass axis is cut into.
#:
#: Labels drawn at a budget of three, over the three renderings above,
#: for 4 / 8 / 12 / 16 regions: survey full 4 / 6 / 7 / 7, survey zoomed
#: 5 / 7 / 8 / 8, product ions 7 / 7 / 8 / 8. Four is too coarse — the
#: dense low-mass stretch is still a quarter of the axis and still spends
#: every label it is given on one cluster. Past eight the count buys one
#: more label and it is the wrong one: at 12 and at 16 regions the survey
#: is drawn with m/z 100.4884 named — the first point of the scan, a
#: region's tallest only because its region is empty — and 171.1374, a
#: peak one can see, unnamed, which is the reverse of the trade at eight.
#: A region has to be wide enough that its tallest peak means something;
#: on a 100-2000 axis, eight makes it 240 Da.
LABEL_REGIONS = 8

#: how many labels one region may claim.
#:
#: Same renderings, at 8 regions, for budgets 1 / 2 / 3 / 4 / 6: survey
#: full 5 / 6 / 6 / 6 / 6, survey zoomed 6 / 6 / 7 / 7 / 8, product ions
#: 6 / 7 / 7 / 7 / 8. The gain stops at three because the fourth peak of a
#: region sits close enough to the first three that the collision rule
#: drops it — at a budget of six the survey offers 33 candidates and draws
#: the same six. Three also covers the case a peak worth naming usually
#: is: a monoisotope with its M+1 and M+2, which separate as soon as one
#: zooms in, and that is where the budget past one earns anything at all.
LABEL_BUDGET = 3

#: a candidate has to reach this fraction of the tallest peak *in view* to
#: be worth a label. Relative to the view rather than to the whole spectrum
#: on purpose: zoomed into a quiet stretch, 2% of a base peak that is off
#: screen excludes everything that is on it.
LABEL_MIN_RELATIVE = 0.02


def region_of(x: float, low: float, high: float,
              regions: int = LABEL_REGIONS) -> int:
    """Which window of `[low, high]` the value falls in, 0-based."""
    span = high - low
    if span <= 0 or regions <= 1:
        return 0
    index = int((x - low) / span * regions)
    return max(0, min(regions - 1, index))


def choose(peaks: Sequence[tuple[float, float]], low: float, high: float,
           regions: int = LABEL_REGIONS, budget: int = LABEL_BUDGET,
           most: int | None = None,
           min_relative: float | None = None) -> list[tuple[float, float]]:
    """
    The peaks worth labelling between `low` and `high`, in claim order.

    `peaks` is `(position, height)` in any order; the ones returned are the
    same objects, ordered so that the caller's collision rule offers room to
    the tallest peak of every region before it offers a second label to any
    region. A region's tallest is therefore only ever passed over by another
    region's tallest, or by `most`.

    `min_relative` is a fraction of the tallest peak *in view*, applied
    before the regions are counted, so an empty window claims nothing.
    """
    kept = [p for p in peaks if low <= float(p[0]) <= high]
    if not kept:
        return []
    if min_relative is not None:
        ceiling = max(float(p[1]) for p in kept)
        floor = ceiling * min_relative
        kept = [p for p in kept if float(p[1]) >= floor]
        if not kept:
            return []

    by_region: dict[int, list[tuple[float, float]]] = {}
    for peak in kept:
        by_region.setdefault(region_of(float(peak[0]), low, high, regions),
                             []).append(peak)

    ordered: list[tuple[float, float]] = []
    for group in by_region.values():
        group.sort(key=lambda p: -float(p[1]))
    for rank in range(max(1, int(budget))):
        round_ = [group[rank] for group in by_region.values()
                  if len(group) > rank]
        round_.sort(key=lambda p: -float(p[1]))
        ordered.extend(round_)
    if most is not None:
        ordered = ordered[:int(most)]
    return ordered
