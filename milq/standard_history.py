"""
One infused standard across the days it was verified: the Batch QC idea
applied to a library of one's own.

A record written by *Add spectrum to library…* is a verification that has
already happened. Every time somebody sprays the standard to check the vial,
one more record of the same compound goes into the same MSP, and after a
few months the file holds the only longitudinal measurement of that standard
anybody has. Nothing was reading it back.

This does. It asks of one compound the three questions a control chart asks
of a batch, with the records in the order they were **acquired** rather than
the order they were typed in:

*Does it still look like itself?* The cosine of each record against the
first — `library.match`, the same arithmetic a library search uses, so
"how alike are two spectra" has one answer in this program and not two.
Both scores are kept: the plain cosine, and the reverse, which asks only
whether the reference's peaks are still there and so forgives an impurity
that has arrived since.

*Is the base peak still where it was?* Its distance from the reference's
base peak, in ppm. This is the one metric that cannot be a percentage of
its own centre — a median of zero ppm has no percentage — which is what
`qc.Limits.absolute` exists for.

*Is it still giving what it gave?* The base peak's absolute height. A
library format holds every peak as a share of the base peak, so this is
lost the moment a record is written unless it is written too; it is, in
`library.BASE_INTENSITY_FIELD`, from the version that added this module
onwards. Records made before that have none and the chart says so rather
than charting the survivors as though they were the whole file.

Three things are deliberate
---------------------------

**The arithmetic is `qc`'s, not a second copy of it.** `qc.chart_from_values`
draws the centre, the spread, the two conditions a point has to meet before
it is out, and the trend that needs both a size and a correlation. A history
differs from a batch in two parameters — how many points are enough, and
whether the scale is a percentage — and in nothing else. Two views that
disagreed about what "out" means would be worse than one view.

**Three records, not six.** A batch is acquired in an afternoon and
`qc.MIN_INJECTIONS` is six because it can be. A history accumulates one
record per verification, and six of them is a year; the floor here is the
fewest points a median and a spread can be taken from at all. Below it
nothing is drawn and the verdict is *too few to chart* — a limit through
two points is a line through two points, which is not a limit.

**A record at 22 eV EAD is not compared with one at 45 eV CID.** A spectrum
measured at another collision energy has other fragments and a different
base peak; scoring across energies measures the method, not the standard.
So the records of one compound are cut into series by energy and
activation, each with its own reference — the first record *of that series*
— and the absolute height, which is only comparable within one method
anyway, is charted inside a series and never across.

**And a record written from a corrected mass axis is not compared with one
written from the instrument's.** The mass recalibration moves every peak of
a record by a few parts per million before it is written down, so a
verification made with it on and one made with it off differ by the
correction whatever the standard did. The axis is therefore a series
attribute like the energy — cut by how far apart the two corrections are
rather than by whether there was one, since under `SAME_AXIS_PPM` they put
every peak in the same window and are one axis. Where a compound does come
out as two series for that reason the chart says so and names the repair:
*Rewrite from files…* writes them all from the same axis again.

What it cannot do
-----------------

The activation is read from the record's own field where an exporter wrote
one and from the record's name otherwise, because no vendor field this
program reads carries it: the nine ZenoTOF infusions this was measured on
say `TOF PI`, `Product`, and the electron energy appears only in the file
name. A record whose name does not say is grouped as unstated, which is
right for a laboratory that runs CID and never says so and wrong for one
that renames its files — and the grouping is shown, so it can be seen.
"""

from __future__ import annotations

import os
import re

import numpy as np

from .infusion_report import ENERGY_TOLERANCE_EV, compound_of, energy_of
from .library import (CORRECTED_AXIS, INSTRUMENT_AXIS, PEAK_TOLERANCE_PPM,
                      LibraryEntry, SpectralLibrary, acquired_of,
                      base_intensity_of, field_value, load_library, match)
from .qc import (DRIFT_CORRELATION, OUTLIER_SIGMA, WARN_SIGMA, ControlChart,
                 Limits, PERCENT, chart_from_values)

#: the fewest records before a centre and a spread mean anything. Three is
#: the fewest a median absolute deviation can be taken from; below it the
#: history is a list, and says so.
MIN_RECORDS = 3

#: how far the base peak may sit from the reference's before the difference
#: is worth acting on, in ppm — and past which it is out whatever the
#: spread. `library.PEAK_TOLERANCE_PPM` is the figure the library itself
#: pairs peaks within: beyond it a search would not call these the same ion
#: at all, so they are not one ion measured twice.
WARN_PPM = PEAK_TOLERANCE_PPM / 2
OUT_PPM = PEAK_TOLERANCE_PPM
ALWAYS_OUT_PPM = 2 * PEAK_TOLERANCE_PPM

#: the floors the mass chart flags on. Absolute, because the deviation is
#: already a ratio: ppm of ppm is not a quantity.
MASS_LIMITS = Limits(warn=WARN_PPM, out=OUT_PPM, always=ALWAYS_OUT_PPM,
                     drift=OUT_PPM, unit=" ppm", absolute=True)

#: past this the two base peaks are not one ion measured twice, and the
#: difference between them is not a mass error to be charted.
#:
#: This is `mass_drift`'s lesson in another place: a −351 ppm "drift" was a
#: window catching a different neighbour each time, and a measurement that
#: cannot be shown to be of the same ion is not judged. The figure is
#: `recalibrate.MAX_LOCK_ERROR_PPM`, which that module measured as the far
#: edge of the trough between "the ion the formula names" and something
#: else. Measured here it is not a close call: two of the nine bile-acid
#: infusions came back 950,000 and 1,224,000 ppm from their reference,
#: which is 377.30 against 839.23 — a different precursor, not a drift.
SAME_PEAK_PPM = 50.0

#: how close two records' mass axes have to be before they are one axis.
#:
#: A record written while the mass recalibration was on carries peaks the
#: instrument never reported, and one written without it carries the numbers
#: the instrument wrote; scoring the two against each other measures the
#: correction and calls it the standard changing. So the axis is a series
#: attribute, exactly as the collision energy is.
#:
#: The cut is between **corrected and not**, and never between two different
#: corrections: two records each corrected against their own acquisition's
#: lock masses stand on the axis those lock masses define, which is one axis
#: however far apart the two corrections were — `library.axis_gap` carries
#: the measurement that says so. What splits a series is a correction one
#: record carries and another does not.
#:
#: And only where that correction is large enough to matter. The figure is
#: `library.PEAK_TOLERANCE_PPM`, the ppm a search pairs peaks within: under
#: it the two put every peak in the same window as each other, so a record
#: corrected by +0.3 ppm and an uncorrected one are one series and splitting
#: them would break a history over a fiftieth of a peak width. Measured on
#: the three bile-acid standards, no correction fitted from an infusion's own
#: precursor ladder reaches it — the largest was 8.6 ppm — so on that data
#: nothing splits, which is the intended outcome and not a missing feature.
SAME_AXIS_PPM = PEAK_TOLERANCE_PPM

#: what to do about a history split across two axes, named in the words the
#: button carries. The repair is not to rescore anything: it is to write
#: every record whose acquisition is still on disk from the same axis again.
REWRITE_REPAIR = ("Rewrite from files… on the Library tab reads every record "
                  "whose acquisition is still on disk again and writes them "
                  "all onto the axis in force now")

#: what the three charts are called, in the order they are offered
SCORE = "score against the first record"
MASS = "base peak, ppm from the first record"
INTENSITY = "base peak intensity"
METRICS = (SCORE, MASS, INTENSITY)

#: the fields an exporter may name the activation in
_ACTIVATION_KEYS = frozenset({"activation", "activationtype",
                              "fragmentation", "fragmentationmode",
                              "fragmentationtype", "dissociation"})

#: activations worth telling apart, matched as whole words in a record's
#: name. Electron-activated dissociation and a collision cell do not produce
#: the same spectrum of the same compound, and a history that mixed them
#: would report the method changing as the standard changing.
ACTIVATIONS = ("EAD", "ECD", "ETD", "EIEIO", "UVPD", "HCD", "CID")

#: how an activation is written in a name: on its own, between separators
_WORD = re.compile(r"(?:^|[^A-Za-z])(%s)(?![A-Za-z])"
                   % "|".join(ACTIVATIONS), re.IGNORECASE)

#: a file name inside a record's comment. The comment is written as the
#: pane's title, the file and the date; this is the piece that names the
#: acquisition, and it is taken by its extension rather than by position
#: because the title itself holds separators.
_FILE = re.compile(r"[^\s·|,;]+\.(?:wiff2?|mzml|mzxml|raw|d)\b", re.IGNORECASE)

#: what a record's kind is called on the chart. `qc.Injection` carries a
#: sample type; a library record has none, and this is what stands there.
RECORD = "record"


# --------------------------------------------------------------------------- #
# reading a record
# --------------------------------------------------------------------------- #
def activation_in(*texts) -> str:
    """
    The activation one of these pieces of text names, upper case, or `""`.

    Taken as a whole word: a name is `CA-d4_TOFMSMS_EAD_22CE`, and matching
    on what a name *contains* finds `EAD` inside a compound called
    `head group`. Shared with `library.py`, which writes the activation into
    a record it makes from a channel rather than leaving the file name to
    say it.
    """
    for text in texts:
        found = _WORD.search(str(text or ""))
        if found:
            return found.group(1).upper()
    return ""


def activation_of(entry: LibraryEntry) -> str:
    """
    How the compound was fragmented: a field where one was written, and the
    record's name otherwise.

    Returned upper case, or `""` when nothing says. Empty is *unstated*, not
    *collision-induced*: guessing the ordinary case would put a record that
    says nothing into the same series as one that says CID, which is the
    comparison this exists to prevent.
    """
    return activation_in(field_value(entry, _ACTIVATION_KEYS),
                         getattr(entry, "name", "") or "",
                         field_value(entry, {"comment"}))


def file_of(entry: LibraryEntry) -> str:
    """The acquisition a record was made from, where its comment names one."""
    found = _FILE.search(field_value(entry, {"comment"}) or "")
    return os.path.basename(found.group()) if found else ""


class Record:
    """One record of one compound, with what it is compared against."""

    def __init__(self, entry: LibraryEntry, index: int = 0):
        self.entry = entry
        self.index = index
        self.name = entry.name
        self.compound = compound_of(entry.name)
        self.when = acquired_of(entry)
        self.file = file_of(entry)
        self.energy = energy_of(entry)
        self.activation = activation_of(entry)
        #: the correction in force when the record was written, in ppm, or
        #: None where it was written from the instrument's own axis
        self.recalibrated_ppm = entry.recalibrated_ppm
        self.precursor = entry.precursor
        self.base_intensity = base_intensity_of(entry)
        top = int(np.argmax(entry.intensity)) if entry.peaks else 0
        self.base_mz = float(entry.mz[top]) if entry.peaks else 0.0
        #: filled in by the series it lands in
        self.order = 0
        self.score: float | None = None
        self.reverse: float | None = None
        self.previous_score: float | None = None
        self.previous_reverse: float | None = None
        #: the base peak's distance from the reference's, always
        self.base_gap_ppm: float | None = None
        #: and the same figure where it can be read as a mass error at all:
        #: None when the two base peaks are not the same ion
        self.ppm: float | None = None

    @property
    def axis(self) -> str:
        """`CORRECTED_AXIS` or `INSTRUMENT_AXIS`, in one word."""
        return (CORRECTED_AXIS if self.recalibrated_ppm is not None
                else INSTRUMENT_AXIS)

    @property
    def axis_ppm(self) -> float:
        """
        Where this record's axis sits, in ppm from the instrument's.

        Zero for a record nobody corrected — which is not a claim that its
        axis is right, only that nothing was added to it. `axis` is what says
        whether the zero was applied or merely never moved.
        """
        return 0.0 if self.recalibrated_ppm is None else self.recalibrated_ppm

    @property
    def axis_label(self) -> str:
        """The record's axis in words, for a table cell."""
        return ("the instrument's" if self.recalibrated_ppm is None
                else f"corrected {self.recalibrated_ppm:+.1f} ppm")

    @property
    def same_base_peak(self) -> bool:
        """
        Whether this record's base peak is the reference's ion at all.

        False is not a large mass error; it is a different ion. Saying which
        is the difference between a standard whose axis has moved and a
        record of something else under the same compound's name.
        """
        return (self.base_gap_ppm is not None
                and abs(self.base_gap_ppm) <= SAME_PEAK_PPM)

    @property
    def day(self) -> str:
        """The date alone, where the record carries a date and a time."""
        return self.when[:10] if len(self.when) >= 10 else self.when

    @property
    def label(self) -> str:
        """What the record is called on a chart: the file, or its name."""
        return self.file or self.name

    def __repr__(self) -> str:                            # pragma: no cover
        return f"<Record {self.name} {self.when or 'undated'}>"


def _sort_key(record: Record) -> tuple:
    """
    Acquisition date first, and the order the file holds them in after.

    A record with no date sorts last rather than first: the first record of a
    series is its reference, and an undated record cannot be shown to be the
    earliest one. Where nothing is dated the file's own order stands, which
    is the order the records were appended in.
    """
    return (0, record.when, record.index) if record.when \
        else (1, "", record.index)


# --------------------------------------------------------------------------- #
# one compound at one energy
# --------------------------------------------------------------------------- #
class Series:
    """
    One compound at one collision energy, activation and mass axis, in date
    order.

    The reference is the first record of the *series*, not of the compound.
    The two are the same thing wherever a standard is only ever verified one
    way, and where they differ the series is right: a cosine against a
    spectrum measured at another energy is a measurement of the energy, and
    a cosine across two mass axes is a measurement of the correction.
    """

    def __init__(self, compound: str, energy: float | None, activation: str,
                 records: list[Record]):
        self.compound = compound
        self.energy = energy
        self.activation = activation
        self.records = sorted(records, key=_sort_key)
        #: how many of its records were written from a corrected axis
        self.corrected = sum(1 for r in self.records
                             if r.recalibrated_ppm is not None)
        #: what those corrections came to, in ppm: their median, and zero
        #: where the series is the instrument's own axis. Not an average over
        #: every record — a series may hold a corrected record beside an
        #: uncorrected one, when the correction was too small to separate
        #: them, and the figure worth printing is the correction
        self.axis_ppm = float(np.median(
            [r.recalibrated_ppm for r in self.records
             if r.recalibrated_ppm is not None])) if self.corrected else 0.0
        for order, record in enumerate(self.records, start=1):
            record.order = order
        self._score()
        self.charts: dict[str, ControlChart] = {
            SCORE: self._chart(SCORE, [(r, None if r.score is None
                                        else r.score * 100.0)
                                       for r in self.records]),
            MASS: self._chart(
                MASS, [(r, r.ppm) for r in self.records], limits=MASS_LIMITS,
                missing=(f"left out: the base peak is more than "
                         f"{SAME_PEAK_PPM:g} ppm from the first record's, "
                         f"which is a different ion and not a mass error")),
            INTENSITY: self._chart(
                INTENSITY, [(r, r.base_intensity) for r in self.records],
                missing="left out: written before the base peak's height was"),
        }

    # -- what it is called ---------------------------------------------------- #
    @property
    def method_conditions(self) -> str:
        """The energy and activation, as a person would write them."""
        bits = []
        if self.activation:
            bits.append(self.activation)
        bits.append("CE unstated" if self.energy is None
                    else f"{self.energy:g} eV")
        return " ".join(bits)

    @property
    def axis_label(self) -> str:
        """
        How this series' mass axis is named, or "" for the instrument's.

        Named only when something was applied, because a name on every series
        would put five words on the ninety-nine histories where nothing was
        corrected in order to serve the hundredth.
        """
        if not self.corrected:
            return ""
        said = f"axis corrected {self.axis_ppm:+.1f} ppm"
        if self.corrected < len(self.records):
            said += (f" for {self.corrected} of {len(self.records)}, the rest "
                     f"on the instrument's own and within {SAME_AXIS_PPM:g} "
                     f"ppm of it")
        return said

    @property
    def conditions(self) -> str:
        """The energy, the activation and the axis, where the axis was moved."""
        axis = self.axis_label
        return f"{self.method_conditions} · {axis}" if axis \
            else self.method_conditions

    @property
    def label(self) -> str:
        return f"{self.compound} · {self.conditions}"

    @property
    def method_key(self) -> tuple:
        """What makes two series the same measurement but for the axis."""
        return (self.compound, self.activation,
                float("inf") if self.energy is None else self.energy)

    @property
    def key(self) -> tuple:
        return self.method_key + (self.axis_ppm,)

    # -- what it holds --------------------------------------------------------- #
    @property
    def reference(self) -> Record | None:
        return self.records[0] if self.records else None

    @property
    def dated(self) -> int:
        return sum(1 for record in self.records if record.when)

    @property
    def ordered(self) -> bool:
        """Whether every record said when it was acquired."""
        return bool(self.records) and self.dated == len(self.records)

    @property
    def days(self) -> list[str]:
        return sorted({record.day for record in self.records if record.day})

    @property
    def with_intensity(self) -> int:
        return sum(1 for record in self.records
                   if record.base_intensity is not None)

    def summary_line(self) -> str:
        """How many records, over how many days, in a phrase."""
        said = [f"{len(self.records)} record(s)"]
        days = self.days
        if len(days) > 1:
            said.append(f"{len(days)} days, {days[0]} to {days[-1]}")
        elif days:
            said.append(f"one day, {days[0]}")
        else:
            said.append("no acquisition dates")
        return ", ".join(said)

    @property
    def flagged(self) -> dict[str, list[str]]:
        """Which records are out, per record label, and on what."""
        out: dict[str, list[str]] = {}
        for metric, chart in self.charts.items():
            for point in chart.out:
                out.setdefault(point.sample, []).append(metric)
        return out

    # -- the arithmetic, all of it borrowed ------------------------------------ #
    def _score(self) -> None:
        reference = self.reference
        if reference is None:
            return
        for index, record in enumerate(self.records):
            record.score, record.reverse = _cosine(record, reference)
            if reference.base_mz and record.base_mz:
                record.base_gap_ppm = ((record.base_mz - reference.base_mz)
                                       / reference.base_mz * 1e6)
                record.ppm = (record.base_gap_ppm if record.same_base_peak
                              else None)
            if index:
                record.previous_score, record.previous_reverse = _cosine(
                    record, self.records[index - 1])

    def _chart(self, metric: str,
               points: list[tuple[Record, float | None]],
               limits: Limits = PERCENT, missing: str = "") -> ControlChart:
        """
        One metric charted, saying which records could not supply it.

        A record left out is said so on the chart rather than dropped
        quietly: three points out of eight is a different statement from
        three points out of three, and the note is the only place that
        difference appears.
        """
        usable = [(record.label, RECORD, record.when, float(value))
                  for record, value in points if value is not None]
        chart = chart_from_values(metric, usable, limits=limits,
                                  minimum=MIN_RECORDS, unit_word=RECORD,
                                  value_word="value")
        left_out = len(points) - len(usable)
        if left_out:
            said = f"{left_out} of {len(points)} record(s) {missing}".strip()
            chart.note = f"{chart.note}; {said}" if chart.note else said
        return chart


def _cosine(record: Record, other: Record) -> tuple[float, float]:
    """
    One record scored against another: the plain cosine and the reverse.

    `library.match` with the other record as the library, so `reverse` asks
    whether *its* peaks are still in this one — which is the question a
    verification asks, since a standard that has picked up an impurity has
    kept everything it had and gained something.
    """
    score, reverse, _pairs = match(record.entry.mz, record.entry.intensity,
                                   other.entry.mz, other.entry.intensity,
                                   PEAK_TOLERANCE_PPM)
    return float(score), float(reverse)


# --------------------------------------------------------------------------- #
# the whole file
# --------------------------------------------------------------------------- #
class StandardHistory:
    """Every record of a library of one's own, grouped into series."""

    def __init__(self, entries: list[LibraryEntry], path: str = ""):
        self.path = path
        self.records = [Record(entry, index)
                        for index, entry in enumerate(entries)]
        grouped: dict[tuple, list[Record]] = {}
        for record in self.records:
            grouped.setdefault(_group(record), []).append(record)
        self.series = sorted(
            (Series(compound, energy, activation, members)
             for (compound, activation, energy), together in grouped.items()
             for members in _by_axis(together)),
            key=lambda series: series.key)

    @property
    def compounds(self) -> list[str]:
        return sorted({series.compound for series in self.series})

    def for_compound(self, compound: str) -> list[Series]:
        return [series for series in self.series if series.compound == compound]

    def axis_splits(self, compound: str = "") -> list[list[Series]]:
        """
        Every set of series that would be one but for the mass axis.

        A list per compound, activation and energy that came out as more than
        one series because its records sit on axes further apart than
        `SAME_AXIS_PPM`. This is the finding the chart has to say out loud:
        the standard was not verified twice, it was written down twice on two
        axes, and `REWRITE_REPAIR` is what puts them back together.
        """
        grouped: dict[tuple, list[Series]] = {}
        for series in (self.for_compound(compound) if compound
                       else self.series):
            grouped.setdefault(series.method_key, []).append(series)
        return [group for group in grouped.values() if len(group) > 1]

    def split_with(self, series: Series) -> list[Series]:
        """The series this one was cut from by the axis, itself included."""
        for group in self.axis_splits():
            if any(other is series for other in group):
                return group
        return [series]

    def summary(self, compound: str = "") -> str:
        """What the file holds, in a sentence."""
        series = self.for_compound(compound) if compound else self.series
        records = sum(len(one.records) for one in series)
        if not records:
            return "no records"
        days = sorted({record.day for one in series for record in one.records
                       if record.day})
        undated = sum(1 for one in series for record in one.records
                      if not record.when)
        said = [f"{records:,} record(s)", f"{len(series)} series"]
        if days:
            said.append(f"{len(days)} day(s), {days[0]} to {days[-1]}"
                        if len(days) > 1 else f"one day, {days[0]}")
        if undated:
            said.append(f"{undated} with no acquisition date — read in the "
                        f"order the file holds them")
        return " · ".join(said)


def _group(record: Record) -> tuple:
    """
    Which series a record belongs to: compound, activation, energy.

    The energy is rounded onto a grid of `ENERGY_TOLERANCE_EV`, the figure
    the infusion report already uses to decide two energies differ: a vendor
    writes a nominal energy and a spread, and a fraction of an electronvolt
    is one setting written twice.
    """
    energy = record.energy
    if energy is not None:
        energy = round(energy / ENERGY_TOLERANCE_EV) * ENERGY_TOLERANCE_EV
    return (record.compound, record.activation, energy)


def _by_axis(records: list[Record]) -> list[list[Record]]:
    """
    One compound at one energy cut again by the mass axis it was written on.

    Two groups at most, and only ever between corrected and not: records that
    were each corrected against their own acquisition's lock masses are on
    one axis whatever the corrections were, and records nobody corrected are
    on the instrument's. What can separate them is the correction the one
    side carries and the other does not — and only when it is larger than
    `SAME_AXIS_PPM`, since under that the two put every peak in the same
    window as each other and two series would be a history broken in half
    over a fiftieth of a peak width.
    """
    corrected = [r for r in records if r.recalibrated_ppm is not None]
    plain = [r for r in records if r.recalibrated_ppm is None]
    if not corrected or not plain:
        return [list(records)]
    if max(abs(r.recalibrated_ppm) for r in corrected) <= SAME_AXIS_PPM:
        return [list(records)]
    return [plain, corrected]


def axis_split_note(group: list[Series]) -> str:
    """
    What to say about a compound whose records sit on more than one axis.

    Everything the reader needs to act: which series there are, how far apart
    their axes are, that the gap is wider than the tolerance a search pairs
    peaks within, and the repair. An empty string where there is nothing to
    say, which is the ordinary case.
    """
    if len(group) < 2:
        return ""
    ordered = sorted(group, key=lambda series: series.corrected)
    named = ", ".join(
        f"{len(series.records)} on "
        + ("the instrument's axis" if not series.corrected
           else f"an axis corrected {series.axis_ppm:+.1f} ppm")
        for series in ordered)
    gap = max(abs(record.axis_ppm) for series in group
              for record in series.records)
    return (f"{ordered[0].compound} · {ordered[0].method_conditions} is "
            f"{len(group)} series, not one: {named} — up to {gap:.1f} ppm of "
            f"correction carried by one and not the other, further than the "
            f"{PEAK_TOLERANCE_PPM:g} ppm a search pairs peaks within. Scoring "
            f"them against each other would measure the correction and "
            f"report it as the standard changing. {REWRITE_REPAIR}.")


def read_history(path: str | os.PathLike) -> StandardHistory:
    """A history from an MSP or MGF file of one's own."""
    library = load_library(path)
    return history_of(library)


def history_of(library: SpectralLibrary) -> StandardHistory:
    """A history from a library already read."""
    return StandardHistory(library.entries, getattr(library, "path", ""))


# --------------------------------------------------------------------------- #
# what the charts say, in words
# --------------------------------------------------------------------------- #
def verdict(chart: ControlChart) -> str:
    """
    One chart in a sentence, on the same rules the Batch QC tab prints.

    The wording differs in one place and deliberately: below `MIN_RECORDS`
    the answer is *too few to chart*, because a reader who is shown a median
    and two limits drawn through two points will read them.
    """
    if not chart.injections:
        return "nothing measured"
    if not chart.measurable:
        return f"too few to chart — {chart.note}"
    unit = chart.limits.unit
    if chart.unusable:
        return (f"{len(chart.out)} of {len(chart.injections)} records more "
                f"than {chart.limits.always:g}{unit} from the centre: these "
                f"are not one standard measured repeatedly")
    said = []
    if chart.drifted:
        said.append(f"drift {chart.drift:+,.1f}{unit} across the records")
    if chart.out:
        said.append(f"{len(chart.out)} outside {OUTLIER_SIGMA:g}σ")
    if chart.excess_warnings:
        said.append(f"{len(chart.warned)} beyond {WARN_SIGMA:g}σ")
    if said:
        return "; ".join(said)
    if chart.note:
        return chart.note
    if chart.correlation is not None and abs(chart.correlation) >= DRIFT_CORRELATION:
        return (f"steady: {chart.drift:+,.1f}{unit} across the records, under "
                f"the {chart.limits.drift:g}{unit} a trend needs")
    return "steady"


def verdicts(series: Series) -> list[tuple[str, str]]:
    """Each metric of a series and what it says."""
    return [(metric, verdict(series.charts[metric])) for metric in METRICS]


def caveat(series: Series) -> str:
    """
    What has to be said beside this series' figures, or "".

    Two of the three go on every chart because they are properties of the
    data rather than findings in it: an absolute height compares only inside
    one method and energy, and records that did not say when they were
    acquired are in the order the file holds them and not in the order they
    were measured.
    """
    said = [f"{series.conditions}: an absolute intensity is comparable only "
            f"within one method and energy"]
    if series.corrected:
        said.append(f"every record here was written from a mass axis "
                    f"corrected {series.axis_ppm:+.1f} ppm; a record written "
                    f"from the instrument's own axis is a different series")
    if not series.ordered:
        said.append(f"{len(series.records) - series.dated} of "
                    f"{len(series.records)} record(s) carry no acquisition "
                    f"date; those are left in the order the file holds them")
    if len(series.days) == 1 and len(series.records) > 1:
        said.append(f"every record was acquired on {series.days[0]} — this is "
                    f"a history of one day, not of a standard over months")
    if series.with_intensity < len(series.records):
        said.append(f"{len(series.records) - series.with_intensity} record(s) "
                    f"were written before the base peak's height was, so the "
                    f"intensity chart is not the whole series")
    return " · ".join(said)


# --------------------------------------------------------------------------- #
# out of the program
# --------------------------------------------------------------------------- #
CSV_HEADER = ("Compound", "Activation", "Collision energy", "Record",
              "Acquired", "File", "Precursor", "Base peak m/z",
              "ppm from first", "Base peak intensity", "Score vs first",
              "Reverse vs first", "Score vs previous", "Reverse vs previous",
              "Out on", "Mass axis")


def ppm_text(record: Record) -> str:
    """
    The base peak against the reference's, for a table.

    A record whose base peak is a different ion is written as that rather
    than as a mass error of a million parts per million, which is a number
    that invites the reader to divide it by anything.
    """
    if record.ppm is not None:
        return f"{record.ppm:+.1f}"
    if record.base_gap_ppm is None:
        return ""
    return "not the same ion"


def _cell(value, decimals: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def csv_rows(history: StandardHistory, compound: str = "") -> list[list[str]]:
    """The table under the charts, one row per record."""
    rows = [list(CSV_HEADER)]
    series_list = history.for_compound(compound) if compound else history.series
    for series in series_list:
        flagged = series.flagged
        for record in series.records:
            rows.append([
                series.compound, series.activation,
                _cell(series.energy, 1), record.name, record.when, record.file,
                _cell(record.precursor, 4), _cell(record.base_mz, 4),
                ppm_text(record), _cell(record.base_intensity, 0),
                _cell(None if record.score is None else record.score * 100, 1),
                _cell(None if record.reverse is None else record.reverse * 100, 1),
                _cell(None if record.previous_score is None
                      else record.previous_score * 100, 1),
                _cell(None if record.previous_reverse is None
                      else record.previous_reverse * 100, 1),
                "; ".join(flagged.get(record.label, [])),
                record.axis_label,
            ])
    return rows


def csv_text(history: StandardHistory, compound: str = "") -> str:
    """
    The rows as CSV, with the verdicts above them as commented lines.

    The verdicts are what the charts say and the rows are what they say it
    about; a file that carried only the rows would be a table somebody has
    to draw the charts from again.
    """
    lines = [f"# standard history from {os.path.basename(history.path)}"
             if history.path else "# standard history"]
    for group in history.axis_splits(compound):
        lines.append(f"# {axis_split_note(group)}")
    for series in (history.for_compound(compound) if compound
                   else history.series):
        lines.append(f"# {series.label}: {series.summary_line()}")
        for metric, said in verdicts(series):
            lines.append(f"#   {metric}: {said}")
        note = caveat(series)
        if note:
            lines.append(f"#   {note}")
    for row in csv_rows(history, compound):
        lines.append(",".join(_escape(cell) for cell in row))
    return "\n".join(lines) + "\n"


def _escape(cell: str) -> str:
    text = str(cell)
    if any(character in text for character in ',"\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def write_csv(history: StandardHistory, path: str | os.PathLike,
              compound: str = "") -> str:
    """Write the table and return the path written."""
    path = str(path)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(csv_text(history, compound))
    return path
