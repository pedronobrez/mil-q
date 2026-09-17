"""
Which collision energy and activation explains a standard best.

`schedule.py` is the chromatographic half of the same question: the method
implies an acquisition, and the program says what it would cost before
anybody types it into an instrument. This is the infusion half. A tray of
infusions of one standard is usually the same vial sprayed at several
collision energies and, on an instrument that has both, under more than one
activation — CID and EAD here. Somebody then has to pick one, and the pick
is normally made by eye off whichever spectrum looked busiest.

It is three different picks, and they disagree with each other:

*Identification.* The most predicted ions found, with the precursor still
there. A fragment list is worth what the prediction it was scored against
is worth, and a spectrum in which the precursor did not survive cannot say
that the fragments came from the ion the method isolated.

*Quantitation.* One fragment carrying as much of the spectrum as possible,
and giving the same share the next time the vial is sprayed. A transition
is one product ion, and the energy that scatters the intensity over twenty
of them is the energy that makes the transition small.

*A library record.* The middle of the energies measured, at the highest
explained share. A record made at the softest energy holds the precursor
and little else and matches nothing; one made at the hardest holds dust
that no other instrument reproduces.

Nothing here interpolates. **An energy that was not acquired is not
offered**, and neither is a "best" energy between two that were: what a
spectrum does between 22 and 45 eV is a measurement nobody made, and every
figure on the table below came off a vial. Where a compound was sprayed at
one energy only, the recommendation says there is nothing to choose between
rather than dressing the one measurement up as a choice.

What is measured, per condition
-------------------------------

A *condition* is one compound at one activation and one collision energy —
`standard_history.Series` cuts a history the same way, and for the same
reason: a spectrum at 12 eV EAD and one at 45 eV CID are two measurements
of two different things, and averaging them measures neither. Every figure
is the median over the infusions of that condition, which is the figure
itself when there is one.

The shares have two denominators and each is named where it is written.
The precursor's is **the base peak**: what survives fragmentation is read
against the biggest thing in the spectrum, which is how anyone looking at
the trace reads it. Every other share is of the **summed intensity of the
peak list the table is measured on** — the peaks at or above
`infusion_report.SCORE_SHARE` of the base peak, which is the list the
scores and the library records are already made from.

A row the isolation verdict contradicts — the file is named for one
compound and the method isolates something that is no adduct of it — is
kept in the table and marked, and is never recommended. It is not deleted
because a pair of them is a finding about somebody's tray, and it is not
recommended because it is not a measurement of the compound on the label.
"""

from __future__ import annotations

import csv
import os
import statistics
from dataclasses import dataclass, field

import numpy as np

from .infusion_compare import InfusionSide, _flat, _get
from .precursor import MIN_INTENSITY
from .qc import OUT_PERCENT
from .standard_history import SAME_PEAK_PPM

#: how tall the precursor has to be, in counts, before *identification* will
#: take a condition. `precursor.MIN_INTENSITY` is the floor `precursor.measure`
#: already holds a survey scan to, and the floor the infusion report reads a
#: surviving precursor at; a fourth figure for the same question would be one
#: too many.
MIN_PRECURSOR = MIN_INTENSITY

#: how far the top fragment's share may move between two infusions of the
#: same compound at the same condition before *quantitation* stops calling it
#: stable. `qc.OUT_PERCENT` is what a control chart of the same standard calls
#: out and what `infusion_compare` marks a base peak as moved at — the same
#: question about the same measurement, so the same number.
STABLE_PERCENT = OUT_PERCENT

#: how far a peak may sit from the precursor and still *be* the precursor,
#: for the purpose of leaving it out of the fragments. `standard_history`'s
#: figure for "the same peak in two spectra".
PRECURSOR_PPM = SAME_PEAK_PPM

#: how many fragments the table names. Three is what fits a cell and what a
#: person compares by eye; the whole list is a peak list and the report
#: already prints it.
TOP_FRAGMENTS = 3

#: the purposes a recommendation is made for, in the order they are shown
IDENTIFICATION = "identification"
QUANTITATION = "quantitation"
LIBRARY = "a library record"
PURPOSES: tuple[str, ...] = (IDENTIFICATION, QUANTITATION, LIBRARY)

#: what a compound sprayed once is told, in the words the manual uses
NOTHING_TO_CHOOSE = "one energy measured; nothing to choose between"


# --------------------------------------------------------------------------- #
# one infusion, reduced to what the choice is made on
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fragment:
    """One peak of a spectrum that is not the precursor."""

    mz: float
    intensity: float
    #: of the summed intensity of the measured peak list
    share: float

    def __str__(self) -> str:
        return f"{self.mz:.4f} ({self.share:.0%})"


@dataclass
class Point:
    """One infusion at one condition: every figure the choice reads."""

    compound: str = ""
    sample: str = ""
    file: str = ""
    mode: str = ""
    activation: str = ""
    energy: float | None = None
    scans: int = 0
    # -- what was predicted and found ---------------------------------------- #
    ions_found: int | None = None
    ions_predicted: int | None = None
    #: `explain.Explanation.share` — of the spectrum's own intensity, which is
    #: the denominator that module measures on and not this one's
    explained: float | None = None
    #: why there is no explanation, when there is none
    explained_note: str = ""
    # -- the precursor -------------------------------------------------------- #
    precursor_mz: float | None = None
    precursor_height: float | None = None
    #: the precursor's height over the base peak's
    precursor_share: float | None = None
    # -- the spectrum ---------------------------------------------------------- #
    base_mz: float | None = None
    base_height: float | None = None
    base_share: float | None = None
    fragments: list[Fragment] = field(default_factory=list)
    peaks: int = 0
    # -- what it scored against ------------------------------------------------ #
    record: str = ""
    record_score: float | None = None
    #: the median cosine of this infusion against the other **considered**
    #: infusions of the same compound, and how many there were
    against_others: float | None = None
    others: int = 0
    #: the isolation verdict's own words where it contradicts the file's name,
    #: and `""` where it does not. A marked point is never recommended.
    flagged: str = ""

    @property
    def considered(self) -> bool:
        return not self.flagged

    @property
    def top(self) -> Fragment | None:
        return self.fragments[0] if self.fragments else None

    @property
    def precursor_survived(self) -> bool:
        """Is the precursor there, and above the floor?"""
        return (self.precursor_height is not None
                and self.precursor_height >= MIN_PRECURSOR)


def _median(values) -> float | None:
    values = [float(v) for v in values if v is not None]
    return statistics.median(values) if values else None


def _fragments(side: InfusionSide, precursor: float | None) -> list[Fragment]:
    """
    The peak list as fragments: everything that is not the precursor.

    The precursor is left out because the three purposes want a *product*
    ion and the precursor is not one. It is left out by mass rather than by
    height — on a soft acquisition it is the base peak, and taking "the
    strongest peak that is not the base peak" would drop a real fragment on
    the acquisitions where it is not.
    """
    mz, intensity = np.asarray(side.mz, dtype=float), \
        np.asarray(side.intensity, dtype=float)
    if mz.size == 0 or intensity.size != mz.size:
        return []
    total = float(intensity.sum())
    if total <= 0:
        return []
    top = float(side.base_height or 0.0)
    fragments = []
    for one_mz, one_share in zip(mz, intensity):
        if (precursor and abs(one_mz - precursor) / precursor * 1e6
                <= PRECURSOR_PPM):
            continue
        fragments.append(Fragment(mz=float(one_mz),
                                  intensity=float(one_share) * top,
                                  share=float(one_share) / total))
    fragments.sort(key=lambda f: -f.share)
    return fragments


def point_from(row, considered_samples=None) -> Point:
    """
    One `infusion_report.InfusionRow` as a `Point`.

    Read through `infusion_compare.InfusionSide`, which already knows how to
    read a row defensively, where the activation and the energy are written
    when the acquisition declares neither, and what the stored peak list of
    a row is. Everything this needs beyond that — the explained share, the
    isolation verdict and the mutual scores — is read off the row itself.

    `considered_samples` is the set of sample names the mutual score may be
    taken over: a row the verdict contradicts is scored against by the
    summary, and letting it into this median would let a vial that is not
    the compound decide how alike the ones that are look.
    """
    side = InfusionSide.from_row(row)
    report = getattr(row, "report", None) or row
    explanation = getattr(report, "explanation", None)
    verdict = getattr(report, "isolation", None)
    found = _get(row, "found")
    precursor = float(found[0]) if found else None
    height = float(found[1]) if found else None
    base_height = float(side.base_height) if side.base_height else None
    fragments = _fragments(side, precursor)
    total = sum(f.intensity for f in fragments) + (height or 0.0)
    flagged = ""
    if verdict is not None and getattr(verdict, "disagrees", False):
        flagged = verdict.column()
    scores = [float(score) for label, score, *_rest in _get(row, "others", [])
              if considered_samples is None or label in considered_samples]
    return Point(
        compound=side.compound or _get(report, "compound", ""),
        sample=side.sample, file=side.file, mode=side.mode,
        activation=side.activation, energy=side.energy,
        scans=side.scans,
        ions_found=side.ions_found, ions_predicted=side.ions_predicted,
        explained=(float(explanation.share)
                   if explanation is not None else None),
        explained_note=_get(row, "explanation_note", ""),
        precursor_mz=precursor, precursor_height=height,
        precursor_share=(height / base_height
                         if height is not None and base_height else None),
        base_mz=side.base_mz, base_height=base_height,
        base_share=((base_height / total) if base_height and total else None),
        fragments=fragments[:TOP_FRAGMENTS],
        peaks=side.peaks,
        record=side.record, record_score=side.record_score,
        against_others=_median(scores), others=len(scores),
        flagged=flagged)


# --------------------------------------------------------------------------- #
# one compound at one activation and one energy
# --------------------------------------------------------------------------- #
@dataclass
class Condition:
    """
    One compound at one activation and one collision energy.

    Every figure is the median over the infusions of the condition — the
    figure itself where there is one, which is the ordinary case. The
    exception is the top fragment, which is a mass as well as a share: two
    infusions that name different masses have not repeated a measurement,
    and `stable` says so instead of taking a median of two unrelated peaks.
    """

    compound: str = ""
    activation: str = ""
    energy: float | None = None
    points: list[Point] = field(default_factory=list)

    # -- what it is called ---------------------------------------------------- #
    @property
    def label(self) -> str:
        """`standard_history.Series.conditions`, which is the same phrase."""
        bits = [self.activation] if self.activation else []
        bits.append("CE unstated" if self.energy is None
                    else f"{self.energy:g} eV")
        return " ".join(bits)

    @property
    def n(self) -> int:
        return len(self.points)

    @property
    def considered(self) -> bool:
        """A condition of marked rows is shown and never recommended."""
        return bool(self.points) and all(p.considered for p in self.points)

    @property
    def flagged(self) -> str:
        for point in self.points:
            if point.flagged:
                return point.flagged
        return ""

    # -- the figures ----------------------------------------------------------- #
    @property
    def ions_found(self) -> int | None:
        found = _median(p.ions_found for p in self.points)
        return None if found is None else int(round(found))

    @property
    def ions_predicted(self) -> int | None:
        offered = _median(p.ions_predicted for p in self.points)
        return None if offered is None else int(round(offered))

    @property
    def explained(self) -> float | None:
        return _median(p.explained for p in self.points)

    @property
    def explained_note(self) -> str:
        for point in self.points:
            if point.explained is None and point.explained_note:
                return point.explained_note
        return ""

    @property
    def precursor_mz(self) -> float | None:
        return _median(p.precursor_mz for p in self.points)

    @property
    def precursor_height(self) -> float | None:
        return _median(p.precursor_height for p in self.points)

    @property
    def precursor_share(self) -> float | None:
        return _median(p.precursor_share for p in self.points)

    @property
    def precursor_survived(self) -> bool:
        height = self.precursor_height
        return height is not None and height >= MIN_PRECURSOR

    @property
    def base_mz(self) -> float | None:
        return _median(p.base_mz for p in self.points)

    @property
    def base_share(self) -> float | None:
        return _median(p.base_share for p in self.points)

    @property
    def record_score(self) -> float | None:
        return _median(p.record_score for p in self.points)

    @property
    def against_others(self) -> float | None:
        return _median(p.against_others for p in self.points)

    @property
    def fragments(self) -> list[Fragment]:
        """The top fragments of the first infusion, by share."""
        return self.points[0].fragments if self.points else []

    @property
    def top(self) -> Fragment | None:
        return self.fragments[0] if self.fragments else None

    @property
    def top_share(self) -> float | None:
        """The median share of the strongest fragment over the repeats."""
        shares = [p.top.share for p in self.points if p.top is not None]
        return _median(shares)

    # -- what the repeats say --------------------------------------------------- #
    @property
    def repeats(self) -> int:
        return max(self.n - 1, 0)

    def stability(self) -> tuple[bool | None, float | None, str]:
        """
        Whether the top fragment repeats, by how much it moved, and in words.

        `None` for a condition sprayed once: it is not unstable, it is
        unmeasured, and a recommendation that treated the two the same would
        be reporting a figure nobody took.
        """
        tops = [p.top for p in self.points if p.top is not None]
        if len(tops) < 2:
            return None, None, ("one infusion at this condition; the share "
                                "is one measurement, not a repeat")
        first = tops[0].mz
        for other in tops[1:]:
            if abs(other.mz - first) / first * 1e6 > PRECURSOR_PPM:
                return False, None, (
                    f"the strongest fragment is {first:.4f} in one infusion "
                    f"and {other.mz:.4f} in another — not a repeat of the "
                    f"same measurement")
        shares = [top.share for top in tops]
        middle = statistics.median(shares)
        spread = ((max(shares) - min(shares)) / middle * 100.0
                  if middle else 0.0)
        stable = spread <= STABLE_PERCENT
        return stable, spread, (
            f"{first:.4f} in all {len(tops)} infusions, its share spread "
            f"{spread:.0f}% about the median"
            + ("" if stable else f", past the {STABLE_PERCENT:g}% a control "
                                 f"chart of this standard calls out"))


# --------------------------------------------------------------------------- #
# the recommendation
# --------------------------------------------------------------------------- #
@dataclass
class Choice:
    """One purpose, the condition it chose and why — or why it chose none."""

    purpose: str = ""
    condition: Condition | None = None
    reason: str = ""

    @property
    def label(self) -> str:
        return self.condition.label if self.condition is not None else "none"

    def sentence(self) -> str:
        """The pick and its reason as one sentence, with one full stop.

        The reason is written as a clause and the full stop is added here, so
        a reason that ends in a sentence of its own does not give the
        paragraph two."""
        reason = self.reason.rstrip(" .")
        if self.condition is None:
            return f"For {self.purpose}: no recommendation — {reason}."
        return f"For {self.purpose}: {self.condition.label} — {reason}."


#: the table, one row per condition, in the order it is shown and exported
COLUMNS = ("Compound", "Activation", "CE (eV)", "Infusions", "Ions found",
           "Explained", "Precursor m/z", "Precursor height",
           "Precursor % of base", "Base peak m/z", "Base peak share",
           "Fragment 1", "Fragment 2", "Fragment 3", "Record", "Record score",
           "Against other energies", "Recommended for", "Considered")

#: what the second block of the CSV holds: the three picks and their reasons
CHOICE_COLUMNS = ("Compound", "Recommended for", "Condition", "Reason")


@dataclass
class EnergyRecommendation:
    """One compound: every condition it was sprayed at, and the three picks."""

    compound: str = ""
    conditions: list[Condition] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)
    #: why there is nothing to choose between, when there is not
    note: str = ""

    @property
    def considered(self) -> list[Condition]:
        return [c for c in self.conditions if c.considered]

    @property
    def marked(self) -> list[Condition]:
        return [c for c in self.conditions if not c.considered]

    @property
    def energies(self) -> list[float]:
        return sorted({c.energy for c in self.considered
                       if c.energy is not None})

    def chosen_for(self, condition: Condition) -> list[str]:
        return [choice.purpose for choice in self.choices
                if choice.condition is condition]

    def rows(self) -> list[list[str]]:
        """The table, one row per condition, as text."""
        return [self._cells(condition) for condition in self.conditions]

    def _cells(self, condition: Condition) -> list[str]:
        fragments = list(condition.fragments)
        while len(fragments) < TOP_FRAGMENTS:
            fragments.append(None)
        found = condition.ions_found
        offered = condition.ions_predicted
        explained = condition.explained
        share = condition.precursor_share
        height = condition.precursor_height
        base_share = condition.base_share
        record = condition.record_score
        others = condition.against_others
        return [
            condition.compound,
            condition.activation or "unstated",
            "—" if condition.energy is None else f"{condition.energy:g}",
            str(condition.n),
            (f"{found} of {offered}" if found is not None and offered
             else f"{found}" if found is not None
             else condition.explained_note or "nothing run"),
            "—" if explained is None else f"{explained * 100:.1f}%",
            ("did not survive" if condition.precursor_mz is None
             else f"{condition.precursor_mz:.4f}"),
            "—" if height is None else f"{height:,.0f}",
            "—" if share is None else f"{share * 100:.0f}%",
            "—" if condition.base_mz is None else f"{condition.base_mz:.4f}",
            "—" if base_share is None else f"{base_share * 100:.0f}%",
            *[("—" if f is None else f"{f.mz:.4f} ({f.share * 100:.0f}%)")
              for f in fragments[:TOP_FRAGMENTS]],
            (condition.points[0].record if condition.points else "") or "—",
            "—" if record is None else f"{record * 100:.0f}",
            "—" if others is None else f"{others * 100:.0f}",
            ", ".join(self.chosen_for(condition)) or "—",
            "yes" if condition.considered else f"no — {condition.flagged}",
        ]

    def summary(self) -> str:
        """What the compound's table says, in one line."""
        if self.note:
            return f"{self.compound}: {self.note}"
        picks = "; ".join(f"{c.purpose}: {c.label}" for c in self.choices)
        return (f"{self.compound}: {len(self.considered)} condition(s) "
                f"measured — {picks}")

    def paragraph(self) -> str:
        """
        The compound's recommendation as sentences, for the report.

        Written here rather than in `infusion_report` so that the document,
        the dialog and the CSV cannot say three different things about the
        same arithmetic.
        """
        conditions = ", ".join(c.label for c in self.considered)
        if self.note:
            return (f"{self.compound} was infused at {conditions}: "
                    f"{self.note}.")
        said = [f"{self.compound} was infused at {len(self.considered)} "
                f"conditions — {conditions} — and they do not answer the "
                f"same question."]
        said += [choice.sentence() for choice in self.choices]
        if self.marked:
            said.append(
                f"{len(self.marked)} infusion(s) are in the table and out of "
                f"the choice: the method there isolates something the file's "
                f"name is not an adduct of.")
        return " ".join(said)


# --------------------------------------------------------------------------- #
# the three picks
# --------------------------------------------------------------------------- #
def _for_identification(conditions: list[Condition]) -> Choice:
    """
    The most predicted ions found, with the precursor still standing.

    Both halves are required and neither substitutes for the other. A
    spectrum with fifteen fragments and no precursor left cannot say the
    fragments came from the ion the method isolated — the window may have
    caught a neighbour, which is the failure `precursor.py` exists to catch —
    and a spectrum with a tall precursor and two fragments has not
    identified anything.
    """
    standing = [c for c in conditions if c.precursor_survived]
    if not standing:
        return Choice(IDENTIFICATION, None,
                      f"no condition kept its precursor above "
                      f"{MIN_PRECURSOR:,.0f} counts, so none of them can say "
                      f"the fragments came from the ion the method isolated")
    measured = [c for c in standing if c.ions_found is not None]
    if not measured:
        return Choice(IDENTIFICATION, None,
                      "nothing was predicted for this compound, so there is "
                      "no count of ions found to compare — give the component "
                      "a formula and measure again")
    best = max(measured, key=lambda c: (c.ions_found, c.explained or 0.0,
                                        -(c.energy or 0.0)))
    offered = best.ions_predicted
    counted = (f"{best.ions_found} of the {offered} ions predicted"
               if offered else f"{best.ions_found} predicted ion(s)")
    rivals = [c for c in measured if c is not best]
    survival = f"{best.precursor_height:,.0f} counts"
    if best.precursor_share is not None:
        survival += f" ({best.precursor_share * 100:.0f}% of the base peak)"
    said = f"{counted} found, the precursor surviving at {survival}"
    if rivals:
        said += (", against "
                 + "; ".join(f"{c.label} {c.ions_found}" for c in rivals))
        # a tie on the count is decided on the explained share, and a reason
        # that did not say so would look like a coin toss between two equal
        # numbers on the table above
        tied = [c for c in rivals if c.ions_found == best.ions_found]
        if tied and best.explained is not None:
            said += (f"; a tie with {len(tied)}, taken on the explained "
                     f"share, {best.explained * 100:.1f}% against "
                     + "; ".join(f"{(c.explained or 0.0) * 100:.1f}%"
                                 for c in tied))
    else:
        said += (f"; it is the only condition whose precursor stayed above "
                 f"{MIN_PRECURSOR:,.0f} counts")
    left_out = [c for c in conditions if not c.precursor_survived]
    if left_out and rivals:
        said += (f"; {len(left_out)} condition(s) left out for a precursor "
                 f"under that floor")
    return Choice(IDENTIFICATION, best, said)


def _for_quantitation(conditions: list[Condition]) -> Choice:
    """
    The largest share held by one fragment, repeating where it was repeated.

    A transition is one product ion. The energy that puts 60% of the
    spectrum on one mass gives a transition six times the one that scatters
    the same ions over twenty masses, and an energy whose strongest fragment
    is a different mass in two sprays of the same vial gives no transition
    at all.
    """
    with_fragment = [c for c in conditions if c.top is not None
                     and c.top_share is not None]
    if not with_fragment:
        return Choice(QUANTITATION, None,
                      "no condition has a fragment: nothing but the precursor "
                      "is in the peak list, so there is no transition to "
                      "quantify on")
    unstable = []
    candidates = []
    for condition in with_fragment:
        stable, _spread, _why = condition.stability()
        (candidates if stable is not False else unstable).append(condition)
    if not candidates:
        return Choice(QUANTITATION, None,
                      "every condition's strongest fragment moves between "
                      "the infusions of that condition: "
                      + "; ".join(f"{c.label}, {c.stability()[2]}"
                                  for c in unstable))
    best = max(candidates, key=lambda c: (c.top_share, -(c.energy or 0.0)))
    _stable, _spread, why = best.stability()
    rivals = [c for c in candidates if c is not best]
    against = ("; ".join(f"{c.label} {c.top_share * 100:.0f}%"
                         for c in rivals)
               if rivals else "nothing else offers a fragment")
    left_out = ("" if not unstable else
                f"; {len(unstable)} condition(s) were left out for a "
                f"strongest fragment that did not repeat")
    return Choice(QUANTITATION, best,
                  f"its strongest fragment {best.top.mz:.4f} holds "
                  f"{best.top_share * 100:.0f}% of the measured intensity, "
                  f"against {against} — {why}{left_out}")


def _for_library(conditions: list[Condition]) -> Choice:
    """
    The middle of the energies measured, at the highest explained share.

    A record made at the softest energy holds the precursor and little else
    and matches nothing; one made at the hardest holds fragments too small
    to reproduce on another instrument. The middle is a position among the
    energies **that were acquired** and never a number between them.

    The energies are ranked by their number alone, across activations. That
    is a stated simplification and not a claim: 22 eV of electron activation
    and 22 eV of collisional activation are not the same thing done twice,
    and where a tray mixes the two the middle is the middle of a list, which
    the reason says in as many words.
    """
    measured = [c for c in conditions if c.energy is not None]
    if not measured:
        return Choice(LIBRARY, None,
                      "no condition declares a collision energy, so there is "
                      "no order to take the middle of")
    ordered = sorted(measured, key=lambda c: c.energy)
    # one candidate for an odd count of energies and the two either side of
    # the middle for an even one, by *position* and never by an average of
    # the two numbers, which would be an energy nobody acquired
    middle = {(len(ordered) - 1) // 2, len(ordered) // 2}
    candidates = [c for index, c in enumerate(ordered) if index in middle]
    best = max(candidates, key=lambda c: (c.explained or 0.0,
                                          -(c.energy or 0.0)))
    listed = ", ".join(f"{c.energy:g}" for c in ordered)
    mixed = len({c.activation for c in ordered}) > 1
    said = (f"the middle of the {len(ordered)} energies measured "
            f"({listed} eV)")
    if mixed:
        said += (" — a position in a list ranked by the number alone, across "
                 "activations, and not a claim that they are the same "
                 "measurement")
    if best.explained is not None:
        said += f", explaining {best.explained * 100:.1f}% of its intensity"
        others = [c for c in candidates if c is not best]
        if others:
            said += (" against " + "; ".join(
                f"{c.label} {(c.explained or 0.0) * 100:.1f}%"
                for c in others))
    else:
        said += (", with no explained share measured — nothing was predicted "
                 "for this compound, so the middle is all this can offer")
    return Choice(LIBRARY, best, said)


# --------------------------------------------------------------------------- #
# the whole tray
# --------------------------------------------------------------------------- #
def recommend(summary) -> list[EnergyRecommendation]:
    """
    Every compound of a measured summary: its conditions, and the three picks.

    `summary` is an `infusion_report.InfusionSummary`, or anything holding
    `rows`. Reads no file and measures nothing: everything here is arithmetic
    on figures the Infusions tab has already taken, which is why it is a
    button and not a wait.
    """
    rows = list(getattr(summary, "rows", summary) or [])
    if not rows:
        return []
    considered = set()
    for row in rows:
        report = getattr(row, "report", None) or row
        verdict = getattr(report, "isolation", None)
        if not getattr(verdict, "disagrees", False):
            considered.add(getattr(report, "sample", ""))
    points = [point_from(row, considered) for row in rows]
    by_compound: dict[str, list[Point]] = {}
    for point in points:
        by_compound.setdefault(point.compound, []).append(point)

    made = []
    for compound, members in by_compound.items():
        grouped: dict[tuple, Condition] = {}
        for point in members:
            # a marked row never shares a condition with a kept one: two
            # infusions of different compounds averaged under one heading is
            # exactly the harm the verdict was written to catch
            key = (point.activation, point.energy, point.considered)
            condition = grouped.get(key)
            if condition is None:
                condition = grouped[key] = Condition(
                    compound=compound, activation=point.activation,
                    energy=point.energy)
            condition.points.append(point)
        conditions = sorted(
            grouped.values(),
            key=lambda c: (not c.considered, c.activation,
                           float("inf") if c.energy is None else c.energy))
        recommendation = EnergyRecommendation(compound=compound,
                                              conditions=conditions)
        kept = recommendation.considered
        if not kept:
            recommendation.note = (
                "every infusion of this compound is one the method "
                "contradicts; there is nothing to choose between")
        elif len(kept) == 1:
            recommendation.note = NOTHING_TO_CHOOSE
        else:
            recommendation.choices = [_for_identification(kept),
                                      _for_quantitation(kept),
                                      _for_library(kept)]
        made.append(recommendation)
    made.sort(key=lambda r: _flat(r.compound))
    return made


def summary_line(recommendations) -> str:
    """Every compound's picks in one line, for the status bar."""
    recommendations = list(recommendations or [])
    if not recommendations:
        return "Nothing measured — press Measure on the Infusions tab first."
    conditions = sum(len(r.considered) for r in recommendations)
    chosen = sum(1 for r in recommendations
                 for c in r.choices if c.condition is not None)
    single = [r.compound for r in recommendations if r.note]
    said = [f"{len(recommendations)} compound(s) over {conditions} "
            f"condition(s)", f"{chosen} recommendation(s) made"]
    if single:
        said.append(f"{len(single)} with one condition only: "
                    + ", ".join(single))
    return "; ".join(said) + "."


def write_csv(recommendations, path: str | os.PathLike) -> str:
    """
    The table and the picks as one CSV, in two blocks.

    Two blocks and not two files: the table is one row per condition and a
    pick is one row per purpose with a sentence on it, and a single header
    that had to hold both would have a column of prose beside a column of
    counts. A blank row separates them, which is what a spreadsheet reads as
    the end of a table.
    """
    path = str(path)
    recommendations = list(recommendations or [])
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for recommendation in recommendations:
            for row in recommendation.rows():
                writer.writerow(row)
        writer.writerow([])
        writer.writerow(CHOICE_COLUMNS)
        for recommendation in recommendations:
            if recommendation.note:
                writer.writerow([recommendation.compound, "—", "—",
                                 recommendation.note])
                continue
            for choice in recommendation.choices:
                writer.writerow([recommendation.compound, choice.purpose,
                                 choice.label, choice.reason])
    return path
