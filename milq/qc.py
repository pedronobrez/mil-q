"""
Whether the batch itself held up, injection by injection.

Everything else in this program asks whether a peak is right. This asks
whether the run was: whether the internal standard that went into every vial
in the same amount came back in the same amount, and whether it did so from
the first injection to the last.

It is the question that catches what per-sample review cannot. A response
that falls by a third across ninety injections is within every acceptance
criterion at every point and still means the column, the source or the
autosampler changed under the batch — and every concentration after the
change was read off a curve built before it.

Three things here are deliberate and each is a refusal to produce a number
the data does not support:

*The centre and the spread are the median and the median absolute
deviation*, not the mean and the standard deviation. The outlier being
hunted is in the sample that defines the limits meant to catch it: one
injection at ten times the rest widens two standard deviations enough to
swallow itself. The median does not move and the MAD does not widen.

*A trend is reported only when it is monotonic and large.* Scatter will
always fit a line with some slope. Spearman's correlation asks whether the
response actually goes one way through the run, and the fitted change says
whether it went far enough to matter; a trend needs both.

*A short run gets no chart at all.* Six injections cannot say what is normal
for a batch, and a control chart drawn through four points invites exactly
the reading it cannot support.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .components import RESPONSE_AREA
from .method import ProcessingMethod
from .quantify import ResultsSet
from .samples import BLANK, QC, STANDARD, UNKNOWN, SampleEntry
from .validation import acquisition_order

#: below this many injections a batch cannot say what normal looks like
MIN_INJECTIONS = 6

#: the median absolute deviation of a normal distribution is 0.6745 of its
#: standard deviation; this is the reciprocal, and turns one into the other
ROBUST = 1.4826

#: how far from the centre before an injection is worth looking at, and
#: before it is out. In robust standard deviations, so the classic two and
#: three of a control chart, taken about a centre an outlier cannot move.
WARN_SIGMA = 2.0
OUTLIER_SIGMA = 3.0

#: and how far in per cent, which is the condition that matters more.
#:
#: A batch that repeats itself well has a small spread, and three sigmas of a
#: small spread is a difference nobody would act on. Measured on a real run,
#: a median absolute deviation of 0.8% turned an internal standard 3.5% low —
#: an ordinary injection — into a four-sigma outlier, and would have done so
#: on almost every batch. So a point has to be both statistically unusual and
#: practically different before it is flagged, the same two conditions drift
#: has to meet. Twenty per cent is the loosest figure a laboratory would still
#: reinject on; below ten, nobody looks.
WARN_PERCENT = 10.0
OUT_PERCENT = 20.0

#: and the deviation past which a point is out however wide the spread.
#:
#: The floors above stop a batch that repeats itself well from flagging
#: ordinary scatter. This is the mirror of that, and it was needed for the
#: same reason in reverse: a batch whose own scatter is wide swallows a real
#: failure. Measured on a real run, an injection where every internal standard
#: came back at a fifth of normal — an injection that plainly failed — sat at
#: 2.6 robust standard deviations, because the batch it was being compared
#: against varied by a third from injection to injection.
#:
#: Half of a response, or double it, is not a matter of statistics.
ALWAYS_OUT_PERCENT = 50.0

#: the fraction of a chart that can be out before the chart itself is the
#: finding. Listing seventeen bad injections out of twenty-six misses what
#: they say together, which is that nothing can be normalised against this
#: standard — and a verdict nobody can act on is a verdict nobody reads.
UNUSABLE_FRACTION = 1 / 3

#: a fitted change across the whole run, as a percentage of the centre,
#: beyond which the run drifted rather than wandered
DRIFT_PERCENT = 20.0

#: and how monotonic that change has to be before it is called a trend
DRIFT_CORRELATION = 0.5

#: the signal-to-noise below which a response is not quantified, and so is
#: not charted either.
#:
#: Ten is the conventional limit of quantitation, the same figure `validation`
#: derives an LOQ at. Below it the per-cent floors elsewhere in this module do
#: nothing useful: they exist to stop a batch that repeats itself well from
#: flagging ordinary scatter, and a standard whose median response is five
#: counts reads three hundred per cent high the moment it gives twenty. Every
#: flag against such a standard is arithmetic performed on noise, and a
#: control chart that spends its flags there is not read anywhere else.
#:
#: Measured on a real batch: of eleven internal standards, eight had a median
#: response between 4 and 52 counts and produced almost every flag in the run.
MIN_SNR = 10.0

#: the coefficient of variation expected of replicate quality controls, and
#: the fewest replicates worth quoting one from
CV_PERCENT = 15.0
MIN_REPLICATES = 3

#: what the index is charted under
RESPONSE_INDEX = "injection response index"

#: the fewest internal standards worth taking a median across. With one, the
#: index is that standard's own chart again under another name; with two there
#: is no median, only an average of a disagreement.
MIN_INDEX_STANDARDS = 3

#: sample types that carry the internal standard. A double blank is extracted
#: without it and a solvent injection never saw it, so neither belongs on its
#: control chart: plotting them puts two zeros in the middle of the run and
#: makes a sound batch look as though it lost the standard twice.
SPIKED_TYPES = (UNKNOWN, STANDARD, QC, BLANK)


# --------------------------------------------------------------------------- #
# small statistics, without a dependency
# --------------------------------------------------------------------------- #
def _ranks(values: np.ndarray) -> np.ndarray:
    """Ranks, with ties sharing their average — the basis of Spearman's."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=float)
    ranks[order] = np.arange(1, values.size + 1, dtype=float)
    unique, inverse, counts = np.unique(values, return_inverse=True,
                                        return_counts=True)
    for index in np.flatnonzero(counts > 1):
        tied = inverse == index
        # without this a run of equal responses correlates with whatever
        # order they happened to be sorted into
        ranks[tied] = ranks[tied].mean()
    return ranks


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    a = a - a.mean()
    b = b - b.mean()
    spread = float(np.sqrt(float((a * a).sum()) * float((b * b).sum())))
    return float((a * b).sum() / spread) if spread > 0 else None


def spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    """
    Correlation of rank against rank: does this go one way through the run?

    Rank rather than value because a control chart is read for direction, not
    for shape, and because one wild injection should not decide the answer.
    """
    if x.size < 3 or x.size != y.size:
        return None
    return _pearson(_ranks(x), _ranks(y))


def robust_centre(values: np.ndarray) -> tuple[float, float]:
    """The median, and the median absolute deviation scaled to a σ."""
    centre = float(np.median(values))
    deviation = float(np.median(np.abs(values - centre)))
    return centre, deviation * ROBUST


# --------------------------------------------------------------------------- #
# one component across the run
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Limits:
    """
    The floors a chart flags on, and the scale they are written in.

    The defaults are this module's own constants, which is what a batch is
    charted against; nothing about the rule changes when they are replaced.
    What they exist for is the other kind of metric. A response is a size,
    and a deviation from it is naturally a share of the centre — but a mass
    is not: a base peak sitting a median of zero ppm from where the first
    record put it has no percentage of itself, and a chart that asks for one
    divides by zero at the first point. So `absolute` says the deviation is
    a difference from the centre rather than a share of it, and `unit` says
    what that difference is measured in, so a verdict can print it.
    """

    warn: float = WARN_PERCENT
    out: float = OUT_PERCENT
    always: float = ALWAYS_OUT_PERCENT
    drift: float = DRIFT_PERCENT
    unit: str = "%"
    absolute: bool = False


#: the ordinary case: a response, charted as a share of its own centre
PERCENT = Limits()


@dataclass(frozen=True)
class Injection:
    """One point on a control chart."""

    order: int
    sample: str
    sample_type: str
    when: str
    value: float
    sigmas: float | None = None
    #: how far from the centre, in the units `limits` is written in: a
    #: percentage of the centre for a response, and a plain difference
    #: where the chart's scale is absolute
    percent: float | None = None
    limits: Limits = PERCENT

    @property
    def out(self) -> bool:
        """
        Unusual for this batch and far enough out to act on — or so far out
        that how usual it is for the batch stops being the question.
        """
        if self.percent is not None and abs(self.percent) >= self.limits.always:
            return True
        return (self.sigmas is not None and abs(self.sigmas) > OUTLIER_SIGMA
                and self.percent is not None
                and abs(self.percent) >= self.limits.out)

    @property
    def warned(self) -> bool:
        """Worth a look: past two sigma and past the smaller of the floors."""
        if self.out:
            return False
        return (self.sigmas is not None and abs(self.sigmas) > WARN_SIGMA
                and self.percent is not None
                and abs(self.percent) >= self.limits.warn)


@dataclass
class ControlChart:
    """One component's response through the batch, in the order it was run."""

    component: str
    is_internal_standard: bool = False
    centre: float | None = None
    sigma: float | None = None
    injections: list[Injection] = field(default_factory=list)
    drift: float | None = None
    correlation: float | None = None
    #: the median signal-to-noise of the injections on the chart, where it is
    #: known. None means it was not measured, which does not suppress anything.
    snr: float | None = None
    #: the response floor the method declares for this standard, when it
    #: does; the median has to clear it for the chart to flag anything
    floor: float | None = None
    #: the floors this chart flags on, and the scale they are written in
    limits: Limits = PERCENT
    note: str = ""

    @property
    def measurable(self) -> bool:
        return self.centre is not None and self.sigma is not None

    @property
    def quantifiable(self) -> bool:
        """
        Whether the response is large enough for a deviation from it to mean
        anything. Below the limit of quantitation it is not, and the chart
        still draws — the points are worth seeing — but it flags nothing.

        A floor declared in the method decides this outright: it comes from
        somebody who knows what the standard gives when the run is right,
        which is what the signal-to-noise rule is standing in for. Without
        one, S/N — and on a scheduled acquisition, where the noise cannot be
        measured, that is an absolute height against an arbitrary constant.
        """
        if self.floor is not None:
            return self.centre is not None and self.centre >= self.floor
        return self.snr is None or self.snr >= MIN_SNR

    @property
    def below_floor(self) -> list["Injection"]:
        """The injections where the standard gave less than its floor."""
        if self.floor is None:
            return []
        return [point for point in self.injections if point.value < self.floor]

    @property
    def out(self) -> list[Injection]:
        if not self.quantifiable:
            return []
        return [point for point in self.injections if point.out]

    @property
    def warned(self) -> list[Injection]:
        if not self.quantifiable:
            return []
        return [point for point in self.injections if point.warned]

    @property
    def excess_warnings(self) -> int:
        """
        Points beyond two sigma, over and above what chance alone gives.

        About one injection in twenty falls outside two standard deviations
        with nothing whatever wrong. A chart that reports each of them is
        reporting the arithmetic of a normal distribution, and a column that
        always has something in it is a column nobody reads.
        """
        expected = int(round(0.05 * len(self.injections)))
        return max(0, len(self.warned) - expected)

    @property
    def unusable(self) -> bool:
        """
        Whether the standard itself is the finding, rather than any injection.

        A third of the run more than half away from the centre is not a set of
        outliers; it is a standard that cannot normalise anything. Saying so
        once is worth more than naming the injections one at a time.
        """
        if not self.injections or not self.quantifiable:
            return False
        return len(self.out) / len(self.injections) > UNUSABLE_FRACTION

    @property
    def drifted(self) -> bool:
        """
        Whether the run went one way, far enough to matter.

        Both conditions are needed. A large fitted change through scatter is
        an artefact of fitting a line to noise, and a strong correlation over
        a two per cent change is a trend nobody has to act on.
        """
        return (self.quantifiable
                and self.drift is not None and self.correlation is not None
                and abs(self.drift) >= self.limits.drift
                and abs(self.correlation) >= DRIFT_CORRELATION)


def chart_from_values(component: str,
                      points: list[tuple[str, str, str, float]],
                      is_internal_standard: bool = False,
                      snr: float | None = None,
                      floor: float | None = None,
                      limits: Limits = PERCENT,
                      minimum: int = MIN_INJECTIONS,
                      unit_word: str = "injection",
                      value_word: str = "response") -> ControlChart:
    """
    A control chart from bare values: `(name, kind, when, value)`, in order.

    This is the arithmetic and nothing else — the robust centre, the two
    conditions a point has to meet before it is out, the trend that needs
    both a size and a correlation — with nothing in it that knows what a
    sample is. `control_chart` below is the batch's way in;
    `standard_history` charts library records through the same body rather
    than writing the rules a second time, which is the only way two views
    can be relied on to agree about what "out" means.

    `minimum` is how many points are needed before any limit is drawn, and
    `unit_word` and `value_word` are what a point and its value are called
    in the notes — injections and responses for a batch, records and values
    for a history.
    """
    chart = ControlChart(component=component, snr=snr, floor=floor,
                         limits=limits,
                         is_internal_standard=is_internal_standard)
    if len(points) < minimum:
        chart.note = (f"only {len(points)} {unit_word}(s); "
                      f"{minimum} are needed to say what is normal")
        chart.injections = [
            Injection(order=index, sample=name, sample_type=kind, when=when,
                      value=value, limits=limits)
            for index, (name, kind, when, value) in enumerate(points, start=1)]
        return chart

    values = np.array([value for *_rest, value in points], dtype=float)
    centre, sigma = robust_centre(values)
    if centre == 0 and not limits.absolute:
        chart.note = "the response is zero through the run"
        return chart

    chart.centre, chart.sigma = centre, sigma
    if not chart.quantifiable:
        if floor is not None:
            chart.note = (f"median response {centre:,.0f}, below the floor of "
                          f"{floor:,.0f} the method declares: the standard is "
                          f"not there in a usable amount, so nothing is "
                          f"flagged against it")
        else:
            chart.note = (f"median signal-to-noise {snr:,.0f}, below "
                          f"{MIN_SNR:g}: the response is too small to "
                          f"quantify, so nothing is flagged against it")
    elif sigma == 0:
        # more than half the injections gave the same number to the last
        # digit, which is not a batch behaving well — it is a reason to
        # distrust the measurement rather than to flag every other point
        chart.note = (f"no spread to measure: over half the {unit_word}s "
                      f"share one {value_word}")

    order = np.arange(1, values.size + 1, dtype=float)
    chart.correlation = spearman(order, values)
    slope = float(np.polyfit(order, values, 1)[0])
    across = slope * (values.size - 1)
    chart.drift = across if limits.absolute else across / centre * 100.0

    for index, (name, kind, when, value) in enumerate(points, start=1):
        away = ((value - centre) if limits.absolute
                else (value - centre) / centre * 100.0)
        chart.injections.append(Injection(
            order=index, sample=name, sample_type=kind, when=when, value=value,
            sigmas=(value - centre) / sigma if sigma > 0 else None,
            percent=away, limits=limits))
    return chart


def control_chart(component: str, points: list[tuple[SampleEntry, float]],
                  is_internal_standard: bool = False,
                  snr: float | None = None,
                  floor: float | None = None) -> ControlChart:
    """
    A control chart for one component, from injections already in order.

    `points` pairs each injection with the response measured in it, in the
    order the instrument ran them; everything below is about what that
    sequence does and does not license.
    """
    return chart_from_values(
        component,
        [(entry.name, entry.sample_type, _stamp(entry), value)
         for entry, value in points],
        is_internal_standard=is_internal_standard, snr=snr, floor=floor)


def _stamp(entry: SampleEntry) -> str:
    if not entry.is_loaded:
        return ""
    return str(getattr(entry.sample, "acquisition_time", "") or "")


# --------------------------------------------------------------------------- #
# replicate precision
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Precision:
    """The scatter of one component over the quality controls of a batch."""

    component: str
    replicates: int
    mean: float | None = None
    percent_cv: float | None = None
    note: str = ""

    @property
    def measurable(self) -> bool:
        return self.percent_cv is not None

    @property
    def fails(self) -> bool:
        return self.percent_cv is not None and self.percent_cv > CV_PERCENT


def precision(results: ResultsSet, entries: list[SampleEntry],
              method: ProcessingMethod,
              limit: float = CV_PERCENT) -> list[Precision]:
    """
    How well the batch repeated itself, on the samples meant to be identical.

    Quality controls only. Unknowns differ from one another by design and
    standards differ by construction, so neither says anything about
    precision; a coefficient of variation over them measures the study, not
    the method.
    """
    controls = [entry for entry in entries if entry.sample_type == QC]
    rows: list[Precision] = []
    for component in method.components:
        mode = component.calibration_response
        values = []
        for entry in controls:
            result = results.get(entry.key, component.name)
            if result is None:
                continue
            value = result.response(mode)
            if value is not None and result.used:
                values.append(float(value))
        if len(values) < MIN_REPLICATES:
            rows.append(Precision(
                component=component.name, replicates=len(values),
                note=f"fewer than {MIN_REPLICATES} quality controls measured"))
            continue
        array = np.array(values, dtype=float)
        mean = float(array.mean())
        if mean == 0:
            rows.append(Precision(component=component.name,
                                  replicates=len(values), mean=mean,
                                  note="mean response of zero"))
            continue
        # the sample standard deviation: these are a sample of the batch's
        # controls, not the population of every control it could have had
        deviation = float(array.std(ddof=1))
        rows.append(Precision(component=component.name, replicates=len(values),
                              mean=mean,
                              percent_cv=abs(deviation / mean * 100.0)))
    return rows


# --------------------------------------------------------------------------- #
# the batch
# --------------------------------------------------------------------------- #
def response_index(charts: list[ControlChart],
                   entries: list[SampleEntry]) -> ControlChart | None:
    """
    The internal standards of each injection, taken together.

    A single standard's chart cannot tell an injection that failed from a
    compound that misbehaved: both look like a point a long way from the
    centre. Comparing the standards *within* an injection can. Each is divided
    by its own median across the run, so that standards of wildly different
    response are on one scale, and the median of those is the injection's
    index — near one when the injection did what the others did.

    That distinction is the whole point. Every standard down together is an
    injection to repeat. One standard down while its neighbours in the same
    injection are fine is that compound's problem, and no amount of looking
    at the injection will show it.

    Measured on a real batch: taken separately the standards looked hopeless,
    with scatter between 32% and 228%. Taken together the injections sat
    within ±18% — except one at 0.08, where every standard had gone at once.
    """
    usable = [chart for chart in charts
              if chart.measurable and chart.centre and chart.injections]
    if len(usable) < MIN_INDEX_STANDARDS:
        return ControlChart(
            component=RESPONSE_INDEX,
            note=f"fewer than {MIN_INDEX_STANDARDS} internal standards were "
                 f"measured; there is nothing to take a median across")

    relative = [{point.sample: point.value / chart.centre
                 for point in chart.injections} for chart in usable]
    points: list[tuple[SampleEntry, float]] = []
    for entry in acquisition_order(entries):
        ratios = [table[entry.name] for table in relative if entry.name in table]
        if len(ratios) < MIN_INDEX_STANDARDS:
            continue
        points.append((entry, float(np.median(ratios))))
    if not points:
        return ControlChart(
            component=RESPONSE_INDEX,
            note="no injection carried enough internal standards")
    chart = control_chart(RESPONSE_INDEX, points)
    chart.note = (f"the median of {len(usable)} internal standards, each "
                  f"against its own median across the run"
                  + (f"; {chart.note}" if chart.note else ""))
    return chart


@dataclass
class BatchQC:
    """What the run did, from first injection to last."""

    charts: list[ControlChart] = field(default_factory=list)
    #: the standards of each injection taken together, which separates an
    #: injection that failed from a compound that misbehaved
    index: ControlChart | None = None
    precision: list[Precision] = field(default_factory=list)
    injections: int = 0
    timed: int = 0
    note: str = ""

    @property
    def ordered(self) -> bool:
        """
        Whether the order plotted is the order the instrument ran.

        Without acquisition times the only sequence left is the order the
        files were opened in. It is usually the same and it is not the same
        thing, and a drift measured against it means correspondingly less.
        """
        return self.timed == self.injections and self.injections > 0

    @property
    def drifted(self) -> list[ControlChart]:
        return [chart for chart in self.charts if chart.drifted]

    @property
    def out(self) -> list[ControlChart]:
        return [chart for chart in self.charts if chart.out]

    @property
    def unusable(self) -> list[ControlChart]:
        return [chart for chart in self.charts if chart.unusable]

    @property
    def imprecise(self) -> list[Precision]:
        return [row for row in self.precision if row.fails]


#: the share of a standard's median response offered as its floor. Half:
#: an injection where the standard came back at less than half of normal is
#: one where the ratio to it has stopped meaning the same thing, and half is
#: also where the always-out rule of the control chart already draws its line.
FLOOR_FRACTION = 0.5


@dataclass(frozen=True)
class FloorProposal:
    """A floor the batch can offer for one internal standard, with its basis."""

    component: str
    current: float | None
    median: float | None
    #: spiked injections where the standard was found
    injections: int
    #: of those, the ones left in once the failed injections were taken out
    used: int
    excluded: tuple[str, ...] = ()
    proposed: float | None = None
    note: str = ""

    @property
    def offered(self) -> bool:
        return self.proposed is not None

    @property
    def confident(self) -> bool:
        """Enough injections behind the median to tick it by default."""
        return self.offered and self.used >= MIN_INJECTIONS


def _round_to(value: float, figures: int = 3) -> float:
    """A proposal to three significant figures: a floor is a threshold, not
    a measurement, and 4,873.2 reads as one."""
    if value <= 0:
        return value
    magnitude = int(np.floor(np.log10(value)))
    return float(round(value, figures - 1 - magnitude))


def suggest_floors(results: ResultsSet, entries: list[SampleEntry],
                   method: ProcessingMethod,
                   report: "BatchQC | None" = None) -> list[FloorProposal]:
    """
    A floor for each internal standard, from the batch's own responses.

    The median area over the spiked injections, with the injections where
    every standard went at once left out — those are what the floor exists
    to catch, and a median that includes them is lower for it — and
    FLOOR_FRACTION of that median as the proposal. It is offered as a
    proposal: the floor is what the standard gives when the run is right,
    which somebody who knows the method may put higher or lower.
    """
    if report is None:
        report = batch_qc(results, entries, method)
    failed = set(failed_injections(report))
    ordered = acquisition_order(entries)
    proposals: list[FloorProposal] = []
    for component in method.components:
        if not component.is_internal_standard or not component.is_valid:
            continue
        values: list[float] = []
        excluded: list[str] = []
        found = 0
        for entry in ordered:
            if entry.sample_type not in SPIKED_TYPES:
                continue
            row = results.get(entry.key, component.name)
            if row is None or not row.found:
                continue
            found += 1
            if entry.name in failed:
                excluded.append(entry.name)
                continue
            values.append(float(row.area))
        if not values:
            proposals.append(FloorProposal(
                component.name, component.min_response, None, found, 0,
                tuple(excluded), None,
                "not found in any spiked injection" if not found
                else "found only in injections that failed"))
            continue
        median = float(np.median(values))
        note = ""
        if len(values) < MIN_INJECTIONS:
            note = (f"only {len(values)} injection(s) behind the median; "
                    f"{MIN_INJECTIONS} are needed to trust it")
        proposals.append(FloorProposal(
            component.name, component.min_response, median, found, len(values),
            tuple(excluded), _round_to(median * FLOOR_FRACTION), note))
    return proposals


def failed_injections(report: "BatchQC") -> list[str]:
    """The samples where every internal standard went at once."""
    if report.index is None or not report.index.measurable:
        return []
    return [point.sample for point in report.index.out]


def exclude_failed(results: ResultsSet, entries: list[SampleEntry],
                   report: "BatchQC") -> int:
    """
    Take the results of the failed injections out of the statistics.

    Detecting an injection that failed and then letting its numbers into the
    means is most of the way to not having detected it. What is excluded is
    marked with the reason, because `used` is also the operator\'s own
    switch and a row that turned itself off without saying why is worse than
    one that stayed on.

    Rows integrated by hand are left alone: somebody looked at those.
    """
    failed = set(failed_injections(report))
    if not failed:
        return 0
    keys = {entry.key for entry in entries if entry.name in failed}
    changed = 0
    for row in results:
        if row.sample_key not in keys or row.manual or not row.used:
            continue
        row.used = False
        note = "excluded: every internal standard low in this injection"
        if note not in row.flags:
            row.flags.append(note)
        changed += 1
    return changed


def batch_qc(results: ResultsSet, entries: list[SampleEntry],
             method: ProcessingMethod,
             components: list[str] | None = None,
             response: str = RESPONSE_AREA) -> BatchQC:
    """
    Control charts through the run, and the precision of its controls.

    Charts are drawn for the internal standards unless asked for others: the
    same amount goes into every vial, so their response is the one number in
    the batch whose variation is the batch's own and not the study's.
    """
    ordered = acquisition_order(entries)
    report = BatchQC(injections=len(ordered),
                     timed=sum(1 for entry in ordered if _stamp(entry)))
    if not ordered:
        report.note = "no samples are open"
        return report

    internal = {c.name for c in method.components if c.is_internal_standard}
    if components is None:
        wanted = [c.name for c in method.components if c.is_internal_standard]
        if not wanted:
            report.note = ("no internal standard is marked in the method, so "
                           "there is nothing whose response should be constant")
            report.precision = precision(results, entries, method)
            return report
    else:
        wanted = list(components)

    for name in wanted:
        points: list[tuple[SampleEntry, float]] = []
        ratios: list[float] = []
        for entry in ordered:
            if name in internal and entry.sample_type not in SPIKED_TYPES:
                continue
            result = results.get(entry.key, name)
            if result is None:
                continue
            value = (result.area if response == RESPONSE_AREA
                     else result.response(response))
            if value is None or not result.found:
                continue
            points.append((entry, float(value)))
            if result.snr:
                ratios.append(float(result.snr))
        # the median, so that a standard strong through the run is not
        # written off by the few injections where it happened to fail
        snr = float(np.median(ratios)) if ratios else None
        component = method.by_name(name)
        floor = component.min_response if component is not None else None
        report.charts.append(
            control_chart(name, points, is_internal_standard=name in internal,
                          snr=snr, floor=floor))

    report.index = response_index(report.charts, entries)
    report.precision = precision(results, entries, method)
    return report
