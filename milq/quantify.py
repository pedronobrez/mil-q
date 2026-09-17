"""
Turning samples and a method into results.

Kept apart from the interface so the extraction and integration can be tested,
scripted and reused by more than one workspace.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from .calibration import Calibration, CalibrationPoint
from .calibration import fit as fit_curve
from .calibration import remove_outliers
from .components import Component, IntegrationParams
from .matching import match_channel
from .method import ProcessingMethod
from .processing import (
    ALGORITHM_GAUSSIAN,
    ALGORITHM_SUMMATION,
    ChromPeak,
    choose_peak,
    detect_peaks,
    estimate_noise,
    gaussian_smooth,
    integrate_window,
    noise_in_region,
    refine_gaussian,
    subtract_baseline,
    summation_peak,
)
from .samples import CALIBRATION_TYPES, SampleEntry

#: scans given to the detector either side of the window, so that it can
#: see a peak's edges rather than a slice of its middle
MARGIN_SCANS = 3

#: below this `detect_peaks` refuses, and the reason is reported as such
MIN_DETECTION_POINTS = 5

#: what `PeakResult.algorithm` says of a row the operator integrated by hand
MANUAL = "manual"

#: confidence of a qualifier's ion ratio
PASS = "Pass"
MARGINAL = "Marginal"
FAIL = "Fail"
NOT_APPLICABLE = ""


@dataclass
class PeakResult:
    """One integrated peak: a component measured in a sample."""

    sample_key: str
    sample_name: str
    component: str
    group: str = ""
    channel: str = "—"
    mz: float = 0.0
    rt: float = 0.0
    expected_rt: float | None = None
    area: float = 0.0
    height: float = 0.0
    width: float = 0.0
    #: None when the baseline could not be measured — see estimate_noise
    snr: float | None = None
    start_rt: float = 0.0
    end_rt: float = 0.0
    note: str = ""
    used: bool = True
    manual: bool = False
    #: the algorithm that produced the area — the one that actually ran, so
    #: a fit that fell back to the valley area is labelled valley. Empty on
    #: rows integrated before this was recorded.
    algorithm: str = ""
    #: the fitted curve when the area came from one, as GaussianModel.to_dict
    model: dict | None = None
    #: points inside the boundaries at or above one per cent of the peak —
    #: the peak rather than its feet. None on rows integrated before this
    #: was counted.
    points: int | None = None
    #: what this row was integrated under: `fingerprint`, below. Empty on a
    #: row written before this existed, which is why such a row cannot be
    #: kept by an incremental run — not knowing is not the same as agreeing.
    fingerprint: str = ""
    #: the mass recalibration applied to the extraction window, in ppm at
    #: this component's mass. None when the switch was off or the injection
    #: had no lock mass — which is not the same as a correction of zero.
    recalibrated_ppm: float | None = None
    #: internal standard this component is reported against, and its response
    internal_standard: str = ""
    is_area: float | None = None
    is_height: float | None = None
    area_ratio: float | None = None
    height_ratio: float | None = None
    #: qualifier confirmation
    quantifier: str = ""
    ion_ratio: float | None = None
    expected_ion_ratio: float | None = None
    confidence: str = NOT_APPLICABLE
    #: quantitation
    actual_concentration: float | None = None
    calculated_concentration: float | None = None
    accuracy: float | None = None
    #: acceptance review
    flags: list[str] = field(default_factory=list)
    status: str = NOT_APPLICABLE

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample_key, self.component)

    @property
    def found(self) -> bool:
        return self.area > 0.0

    @property
    def rt_delta(self) -> float | None:
        """Signed difference from the expected retention time, in minutes."""
        if self.expected_rt is None or not self.found:
            return None
        return self.rt - self.expected_rt

    def response(self, mode: str) -> float | None:
        """
        The number this component is reported by: the raw area, its ratio to
        the internal standard, or the concentration read off the curve.
        """
        if mode == "ratio":
            return self.area_ratio
        if mode == "concentration":
            return self.calculated_concentration
        return self.area

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PeakResult":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class ResultsSet:
    """Every result of one processing run, addressable by sample and component."""

    results: list[PeakResult] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def clear(self) -> None:
        self.results = []

    def get(self, sample_key: str, component: str) -> PeakResult | None:
        for result in self.results:
            if result.sample_key == sample_key and result.component == component:
                return result
        return None

    def by_key(self) -> dict[tuple[str, str], PeakResult]:
        """
        Every row indexed by sample and component, first one wins.

        `get` walks the list, which is right for one lookup and quadratic for
        one per row: linking a batch of 3,666 rows to their internal
        standards did 13 million comparisons and took over a second on a set
        where nothing had been integrated at all. Anything that looks a row
        up for every row builds this once instead.
        """
        index: dict[tuple[str, str], PeakResult] = {}
        for result in self.results:
            index.setdefault(result.key, result)
        return index

    def by_component(self) -> dict[str, list[PeakResult]]:
        """
        Every row grouped by component, in the order the rows are held.

        `for_component` filters the whole list, which is right for one
        component and quadratic for one per component: the sampling report,
        the calibration pass and the algorithm comparison each ask for every
        component in turn, so on a 141-component batch of 3,666 rows they
        walked half a million rows to read 3,666. Anything looping over the
        method's components builds this once instead — the same shape, and
        the same reason, as `by_key`.
        """
        index: dict[str, list[PeakResult]] = {}
        for result in self.results:
            index.setdefault(result.component, []).append(result)
        return index

    def for_component(self, component: str) -> list[PeakResult]:
        return [r for r in self.results if r.component == component]

    def for_sample(self, sample_key: str) -> list[PeakResult]:
        return [r for r in self.results if r.sample_key == sample_key]

    def replace(self, result: PeakResult) -> None:
        for index, existing in enumerate(self.results):
            if existing.key == result.key:
                self.results[index] = result
                return
        self.results.append(result)

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self.results]

    @classmethod
    def from_list(cls, rows: list[dict]) -> "ResultsSet":
        return cls([PeakResult.from_dict(row) for row in rows or []])


# --------------------------------------------------------------------------- #
# what a row was integrated under
# --------------------------------------------------------------------------- #
#: the `Component` fields that decide what is extracted and how it is
#: integrated. Everything else about a component — its group, the standard it
#: is reported against, its calibration, its acceptance limits — is either a
#: label or is recomputed over the whole set afterwards, so changing it does
#: not need the file read again.
FINGERPRINTED_FIELDS = ("name", "precursor", "fragment", "rt", "rt_halfwidth",
                        "tolerance", "unit")


def _correction_key(correction) -> tuple | None:
    """A mass correction as the numbers that move a window, or None."""
    if correction is None or not correction.usable:
        return None
    return (round(float(correction.offset_ppm), 9),
            round(float(correction.slope_ppm_per_da), 9),
            round(float(correction.pivot), 9))


def fingerprint(component: Component, method: ProcessingMethod,
                correction=None) -> str:
    """
    A short digest of everything that decides this component's numbers.

    Two rows carrying the same fingerprint were integrated from the same mass
    window over the same time window with the same parameters, so one can
    stand for the other and `process_incremental` may keep it. It covers the
    component's own extraction fields, the integration parameters actually in
    force — the component's override where it has one and the method defaults
    where it does not, which is what makes a change to the defaults reach
    exactly the components that inherit them — and the injection's mass
    correction, since that moves the window.

    It deliberately does **not** cover the file's contents. A fingerprint says
    the method has not changed; it cannot say the acquisition has not been
    replaced under the same name, and nothing else in this application can
    either.
    """
    params = method.integration_for(component)
    parts = (
        tuple(getattr(component, name) for name in FINGERPRINTED_FIELDS),
        tuple(sorted(asdict(params).items())),
        _correction_key(correction),
    )
    digest = hashlib.blake2b(repr(parts).encode("utf-8"), digest_size=8)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #
class XicCache:
    """
    Memoises extracted chromatograms.

    Switching between components in the review grid re-reads the same traces
    over and over; a small cache keeps that instant without holding a whole
    batch in memory.
    """

    def __init__(self, max_entries: int = 512):
        self._data: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
        self._order: list[tuple] = []
        self.max_entries = max_entries

    def clear(self) -> None:
        self._data.clear()
        self._order.clear()

    def get(self, key: tuple):
        return self._data.get(key)

    def put(self, key: tuple, value) -> None:
        if key not in self._data and len(self._order) >= self.max_entries:
            self._data.pop(self._order.pop(0), None)
        if key not in self._data:
            self._order.append(key)
        self._data[key] = value


def condition(x: np.ndarray, y: np.ndarray,
              params: IntegrationParams) -> np.ndarray:
    """Apply a component's baseline and smoothing, as the display does."""
    if params.baseline_window > 0:
        y = subtract_baseline(x, y, params.baseline_window)
    if params.smoothing > 0:
        y = gaussian_smooth(y, params.smoothing)
    return y


def extract_xic(entry: SampleEntry, component: Component,
                method: ProcessingMethod,
                cache: XicCache | None = None,
                correction=None) -> tuple[np.ndarray, np.ndarray, object]:
    """
    The chromatogram of one component in one sample, already conditioned.

    Returns the trace and the channel it came from, so callers can label the
    panel with the experiment that was actually used.

    `correction` is a `recalibrate.MassCorrection` for this injection, or
    None. It moves the **window**, never the data: the component's mass
    window is written where the ion belongs, the file holds the ion where the
    instrument read it, so the reader is asked for `correction.undo` of the
    window and then sums exactly the points it would have summed anyway. The
    vendor's extraction arithmetic is untouched — a corrected axis is a
    different question from a different sum, and conflating them would repeat
    the mistake CLAUDE.md records about substituting our arithmetic for the
    instrument's.
    """
    empty = (np.zeros(0), np.zeros(0), None)
    if not entry.is_loaded:
        return empty
    channel = match_channel(entry.sample, component)
    if channel is None:
        return empty
    params = method.integration_for(component)
    mz_lo, mz_hi = component.mass_window()
    if correction is not None and correction.usable:
        mz_lo, mz_hi = (float(correction.undo(mz_lo)),
                        float(correction.undo(mz_hi)))
    key = (entry.key, channel.index, round(mz_lo, 6), round(mz_hi, 6),
           params.cache_key())
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit[0], hit[1], channel
    x, y = channel.xic_range(mz_lo, mz_hi)
    y = condition(x, y, params)
    if cache is not None:
        cache.put(key, (x, y))
    return x, y, channel


def _first_line(error: BaseException) -> str:
    text = str(error).strip()
    return f"could not be read: {text.splitlines()[0] if text else type(error).__name__}"


def integrate_component(entry: SampleEntry, component: Component,
                        method: ProcessingMethod,
                        cache: XicCache | None = None,
                        correction=None) -> PeakResult:
    """
    Integrate one component in one sample.

    When the component declares a retention time whose window the matched
    channel does not cover, the result comes back empty and annotated instead
    of reporting a peak found somewhere else in the run.
    """
    mz_lo, mz_hi = component.mass_window()
    result = PeakResult(
        sample_key=entry.key, sample_name=entry.name, component=component.name,
        group=component.group, mz=(mz_lo + mz_hi) / 2,
        expected_rt=component.rt, rt=component.rt or 0.0,
        fingerprint=fingerprint(component, method, correction),
    )

    if correction is not None and correction.usable:
        result.recalibrated_ppm = float(correction.ppm_at(component.target_mz))
    try:
        x, y, channel = extract_xic(entry, component, method, cache, correction)
    except Exception as exc:
        # a .wiff whose .wiff.scan is not beside it opens, lists its
        # channels and throws on the first extraction; the row says so
        # rather than the batch stopping on it
        result.note = entry.problem or _first_line(exc)
        return result
    if channel is None:
        result.note = "no matching channel"
        return result
    result.channel = channel.info.short_label
    if x.size == 0:
        result.note = "no data"
        return result

    window = component.rt_window()
    if window is None:
        mask = np.ones(x.size, dtype=bool)
    else:
        mask = (x >= window[0]) & (x <= window[1])
        if mask.sum() < 3:
            result.note = (f"channel does not cover "
                           f"{window[0]:.2f}–{window[1]:.2f} min")
            return result

    params = method.integration_for(component)
    noise = measured_noise(x, y, params)
    if params.algorithm == ALGORITHM_SUMMATION:
        # no detection at all: the window is the boundary, or there is none
        if window is None:
            result.note = "summation needs a retention-time window"
            return result
        peak, note = summation_peak(x, y, window[0], window[1], noise,
                                    params.min_snr)
        if peak is None:
            result.note = note
            return result
        return apply_peak(result, peak)

    peaks = detect_peaks(x[detection_range(x, mask)], y[detection_range(x, mask)],
                         min_relative=params.min_relative_height,
                         min_snr=params.min_snr, noise=noise)
    if window is not None:
        # the window says where the apex may be, not where the peak has to
        # end. Peaks found in the margin belong to something else.
        peaks = [p for p in peaks if window[0] <= p.apex_rt <= window[1]]
    if not peaks:
        result.note = _nothing_found(x, mask)
        return result
    peak, note = choose_peak(peaks, component.rt, params.peak_choice)
    if params.algorithm == ALGORITHM_GAUSSIAN:
        peak, fit_note = refine_gaussian(x, y, peak, noise)
        note = "; ".join(part for part in (note, fit_note) if part)
    result = apply_peak(result, peak)
    if note:
        result.note = note
    return result


def detection_range(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    The stretch the detector is given: the window, plus room to see the edges.

    A retention-time window says where the apex may be. It is not a statement
    about where the peak ends, and handing the detector exactly that window
    has two consequences, both measured on real data.

    A peak is truncated at the boundary, which biases its area. And below five
    points `detect_peaks` declines outright — so with the 14.6 s sampling of a
    scheduled method, a ±0.5 min window holding four scans returned nothing at
    all, whatever was in it: a peak of 44,875 counts came back as "no peak
    above noise". Whether a component was integrated then depended on whether
    its window happened to catch four scans or five, which is set by the
    channel's start offset — an accident of the acquisition rather than
    anything about the chemistry.

    So the detector sees a few scans either side and the apex is required to
    land inside the declared window afterwards. The margin is deliberately
    small: everything in it competes on relative height with the real peak,
    and a wide margin would let a tall neighbour suppress it.
    """
    inside = np.flatnonzero(mask)
    if inside.size == 0:
        return mask
    first = max(int(inside[0]) - MARGIN_SCANS, 0)
    last = min(int(inside[-1]) + MARGIN_SCANS, x.size - 1)
    widened = np.zeros(x.size, dtype=bool)
    widened[first:last + 1] = True
    return widened


def _nothing_found(x: np.ndarray, mask: np.ndarray) -> str:
    """Why there is no peak — which is not always that there is no signal."""
    points = int(detection_range(x, mask).sum())
    if points < MIN_DETECTION_POINTS:
        return (f"only {points} points to detect in; the window is narrower "
                f"than the sampling can resolve")
    return "no peak above noise"


def measured_noise(x: np.ndarray, y: np.ndarray,
                   params: IntegrationParams) -> float | None:
    """
    The noise a signal-to-noise ratio is measured against.

    Taken over the component's noise region when one is set, and otherwise
    over the whole chromatogram. It deliberately is not measured inside the
    retention-time window: that stretch is mostly peak, so its point-to-point
    spread reports the peak's own slope — on real data that read 16,944 where
    the trace's actual noise was 505, and the same peak came out at S/N 19
    automatically against 531 by hand.
    """
    region = params.noise_region
    if region is not None:
        return noise_in_region(x, y, region[0], region[1], params.snr_mode)
    return estimate_noise(y)


def integrate_manually(entry: SampleEntry, component: Component,
                       method: ProcessingMethod, start: float, end: float,
                       previous: PeakResult | None = None,
                       cache: XicCache | None = None,
                       correction=None) -> PeakResult:
    """
    Integrate exactly the stretch the operator marked on a chromatogram.

    No peak finding runs: the boundaries are the answer. The row is flagged
    manual so a later reprocessing can be told to leave it alone.
    """
    mz_lo, mz_hi = component.mass_window()
    result = previous or PeakResult(
        sample_key=entry.key, sample_name=entry.name, component=component.name,
        group=component.group, mz=(mz_lo + mz_hi) / 2, expected_rt=component.rt,
    )
    # a hand-drawn boundary is drawn on the trace the current settings give,
    # so the row records those settings: it is kept while they stand and
    # re-integrated when they do not
    result.fingerprint = fingerprint(component, method, correction)
    if correction is not None and correction.usable:
        result.recalibrated_ppm = float(correction.ppm_at(component.target_mz))
    x, y, channel = extract_xic(entry, component, method, cache, correction)
    if channel is None or x.size == 0:
        result.note = "no data"
        return result
    result.channel = channel.info.short_label
    params = method.integration_for(component)
    peak = integrate_window(x, y, start, end, measured_noise(x, y, params))
    if peak is None:
        result.note = "selection too narrow to integrate"
        return result
    return apply_peak(result, peak, manual=True)


def apply_peak(result: PeakResult, peak: ChromPeak, manual: bool = False) -> PeakResult:
    """Copy an integrated peak onto a result row."""
    result.rt = peak.apex_rt
    result.area = peak.area
    result.height = peak.height
    result.width = peak.width
    result.snr = peak.snr
    result.start_rt = peak.start_rt
    result.end_rt = peak.end_rt
    result.note = ""
    result.manual = manual
    result.algorithm = MANUAL if manual else peak.algorithm
    result.model = peak.model.to_dict() if peak.model is not None else None
    result.points = peak.points
    return result


def link_internal_standards(results: ResultsSet, method: ProcessingMethod) -> None:
    """
    Fill in each result's ratio to its internal standard.

    Done after the whole batch, because the standard's own peak has to be
    integrated before anything can be divided by it.
    """
    index = results.by_key()
    for result in results:
        component = method.by_name(result.component)
        if component is None:
            continue
        standard = method.internal_standard_for(component)
        if standard is None:
            # the component was pointed at another standard, at none, or at a
            # name nothing answers to: the old ratios describe a link that is
            # gone, so they go with it rather than quietly standing
            result.internal_standard = ""
            result.is_area = None
            result.is_height = None
            result.area_ratio = None
            result.height_ratio = None
            continue
        result.internal_standard = standard.name
        reference = index.get((result.sample_key, standard.name))
        if reference is None or not reference.found:
            result.is_area = None
            result.is_height = None
            result.area_ratio = None
            result.height_ratio = None
            continue
        result.is_area = reference.area
        result.is_height = reference.height
        result.area_ratio = result.area / reference.area
        result.height_ratio = (result.height / reference.height
                               if reference.height else None)


def ion_ratio_confidence(measured: float | None, expected: float | None,
                         tolerance: float, marginal: float) -> str:
    """
    Grade a measured ion ratio against the expected one.

    The deviation is relative to the expected ratio, which is how a qualifier
    tolerance is normally written: "within 20% of the expected ratio".
    """
    if measured is None or expected in (None, 0):
        return NOT_APPLICABLE
    deviation = abs(measured - expected) / abs(expected) * 100.0
    if deviation <= tolerance:
        return PASS
    if deviation <= marginal:
        return MARGINAL
    return FAIL


def compute_ion_ratios(results: ResultsSet, method: ProcessingMethod) -> None:
    """Score every qualifier against its quantifier, in each sample."""
    index = results.by_key()
    for result in results:
        component = method.by_name(result.component)
        if component is None:
            continue
        quantifier = method.quantifier_for(component)
        if quantifier is None:
            continue
        result.quantifier = quantifier.name
        result.expected_ion_ratio = component.ion_ratio
        reference = index.get((result.sample_key, quantifier.name))
        if reference is None or not reference.found or not result.found:
            result.ion_ratio = None
            result.confidence = NOT_APPLICABLE
            continue
        result.ion_ratio = result.area / reference.area * 100.0
        tolerance, marginal = method.ion_ratio_limits(component)
        result.confidence = ion_ratio_confidence(
            result.ion_ratio, component.ion_ratio, tolerance, marginal)


def evaluate_acceptance(results: ResultsSet, entries: list[SampleEntry],
                        method: ProcessingMethod) -> None:
    """
    Score every row against its component's acceptance criteria.

    A row with no criteria set gets no status at all rather than a green light:
    a method that has not been told what to check has not checked anything, and
    saying otherwise would be worse than saying nothing.
    """
    by_key = {e.key: e for e in entries}
    for result in results:
        result.flags = []
        result.status = NOT_APPLICABLE
        component = method.by_name(result.component)
        if component is None:
            continue
        limits = method.acceptance_for(component)
        checked = False

        if not result.found:
            result.flags.append("not integrated")
            result.status = FAIL
            continue

        if limits.rt_tolerance:
            checked = True
            delta = result.rt_delta
            if delta is not None and abs(delta) > limits.rt_tolerance:
                result.flags.append(f"RT {delta:+.3f} min")

        if limits.min_snr:
            if result.snr is None:
                # a criterion that cannot be evaluated is not a criterion that
                # passed, and saying nothing would let it read as one
                if result.found:
                    result.flags.append("S/N not measured")
            else:
                checked = True
                if result.snr < limits.min_snr:
                    result.flags.append(f"S/N {result.snr:.0f}")

        standard = method.internal_standard_for(component)
        if standard is not None and standard.min_response is not None \
                and result.is_area is not None:
            # the method declared what the standard has to give before a
            # ratio to it means anything; below that the row is not
            # normalised, whatever its own peak looks like
            checked = True
            if result.is_area < standard.min_response:
                result.flags.append(
                    f"IS {result.is_area:,.0f} below its floor of "
                    f"{standard.min_response:,.0f}")

        if limits.accuracy_tolerance:
            entry = by_key.get(result.sample_key)
            wanted = entry is not None and entry.actual_concentration is not None
            if wanted:
                checked = True
                if result.accuracy is None:
                    result.flags.append("no concentration")
                elif abs(result.accuracy - 100.0) > limits.accuracy_tolerance:
                    result.flags.append(f"accuracy {result.accuracy:.0f}%")

        if result.confidence == FAIL:
            checked = True
            result.flags.append(f"ion ratio {result.ion_ratio:.1f}%")
        elif result.confidence == MARGINAL:
            checked = True

        if not checked:
            continue
        if result.flags:
            result.status = FAIL
        elif result.confidence == MARGINAL:
            result.status = MARGINAL
        else:
            result.status = PASS


def build_calibrations(results: ResultsSet, entries: list[SampleEntry],
                       method: ProcessingMethod,
                       auto_outliers: bool = False,
                       tolerance: float = 15.0,
                       previous: dict[str, Calibration] | None = None,
                       ) -> dict[str, Calibration]:
    """
    Fit one curve per component from the samples marked as standards.

    Points the operator excluded by hand are carried over from `previous`, so
    refitting after a parameter change does not quietly put them back.
    """
    by_key = {e.key: e for e in entries}
    excluded: dict[tuple[str, str], bool] = {}
    for name, curve in (previous or {}).items():
        for point in curve.points:
            excluded[(name, point.sample_key)] = point.used

    curves: dict[str, Calibration] = {}
    rows_of = results.by_component()
    for component in method.components:
        mode = component.calibration_response
        points: list[CalibrationPoint] = []
        for result in rows_of.get(component.name, ()):
            entry = by_key.get(result.sample_key)
            if entry is None or entry.sample_type not in CALIBRATION_TYPES:
                continue
            if entry.actual_concentration is None:
                continue
            response = result.response(mode)
            if response is None:
                continue
            points.append(CalibrationPoint(
                sample_key=result.sample_key, sample_name=result.sample_name,
                concentration=entry.actual_concentration, response=response,
                used=excluded.get((component.name, result.sample_key), True),
            ))
        if not points:
            continue
        points.sort(key=lambda p: p.concentration)
        curve = fit_curve(points, component.regression, component.weighting,
                          component.name)
        if auto_outliers and curve.is_fitted:
            curve = remove_outliers(curve, tolerance)
        curves[component.name] = curve
    return curves


def apply_calibrations(results: ResultsSet, entries: list[SampleEntry],
                       method: ProcessingMethod,
                       curves: dict[str, Calibration]) -> None:
    """
    Read a concentration off each component's curve and score its accuracy.

    The dilution factor multiplies the result, because the curve describes the
    vial that was injected and the answer wanted is the original sample.
    """
    by_key = {e.key: e for e in entries}
    for result in results:
        component = method.by_name(result.component)
        entry = by_key.get(result.sample_key)
        if entry is not None:
            result.actual_concentration = entry.actual_concentration
        result.calculated_concentration = None
        result.accuracy = None
        if component is None:
            continue
        curve = curves.get(component.name)
        if curve is None or not curve.is_fitted or not result.found:
            continue
        response = result.response(component.calibration_response)
        if response is None:
            continue
        value = curve.concentration_at(response)
        if value is None:
            continue
        dilution = entry.dilution_factor if entry else 1.0
        result.calculated_concentration = value * (dilution or 1.0)
        if result.actual_concentration:
            result.accuracy = (result.calculated_concentration
                               / result.actual_concentration * 100.0)


def process(entries: list[SampleEntry], method: ProcessingMethod,
            cache: XicCache | None = None, progress=None,
            previous: ResultsSet | None = None,
            keep_manual: bool = True,
            only: list[str] | None = None,
            corrections: dict | None = None) -> ResultsSet:
    """
    Run the method over the batch.

    `previous` carries the rows of an earlier run. With `keep_manual`, any row
    the operator integrated by hand is carried across untouched, so adjusting a
    parameter does not silently undo their work. `only` limits the run to named
    components, which is what makes re-tuning one analyte cheap.

    `corrections` maps a sample key to a `recalibrate.MassCorrection`. Absent
    — which is the default and what a project saved before this existed asks
    for — every window is exactly the one the method wrote, and the numbers
    are the ones that project has always given.

    This is the full run: every row read from the file. The workspace reaches
    for `process_incremental` instead wherever an earlier run's rows can
    answer for themselves; `previous`, `keep_manual` and `only` here predate
    it and remain for a script that wants to say outright what to redo.
    """
    components = [c for c in method.components if c.is_valid]
    if only is not None:
        wanted = set(only)
        components = [c for c in components if c.name in wanted]
    loaded = [e for e in entries if e.is_loaded]
    total = len(components) * len(loaded)
    out = ResultsSet()
    if previous is not None and only is not None:
        keep = set(only)
        out.results = [r for r in previous if r.component not in keep]
    done = 0
    for entry in loaded:
        for component in components:
            kept = previous.get(entry.key, component.name) if previous else None
            if keep_manual and kept is not None and kept.manual:
                out.results.append(kept)
            else:
                out.results.append(integrate_component(
                    entry, component, method, cache,
                    (corrections or {}).get(entry.key)))
            done += 1
            if progress is not None and progress(done, total) is False:
                break
        else:
            continue
        break
    link_internal_standards(out, method)
    compute_ion_ratios(out, method)
    return out


# --------------------------------------------------------------------------- #
# incremental reprocessing
# --------------------------------------------------------------------------- #
#: why a row was integrated rather than kept
NEW_SAMPLE = "a sample the previous run did not have"
NEW_COMPONENT = "a component the previous run did not have"
NO_PREVIOUS_ROW = "the previous run has no row for it"
CHANGED = "the extraction or integration changed"
CHANGED_MANUAL = "a hand-integrated row whose component changed"
NOT_RECORDED = "the row does not say what it was integrated under"

#: why a previous row is not in the new set
SAMPLE_GONE = "the sample is no longer in the batch"
COMPONENT_GONE = "the component is no longer in the method"

#: below this share of the previous rows kept, the Process button does a full
#: run instead. Declared, not derived: an incremental run that keeps almost
#: nothing does the same reading as a full one and adds bookkeeping to it, and
#: a change reaching most of the method is one the operator should see
#: reported as a reprocess of the batch rather than as an incremental run that
#: happened to redo all of it.
FULL_RUN_BELOW = 0.5


@dataclass
class IncrementalReport:
    """What an incremental run kept, integrated and dropped, and why."""

    kept: int = 0
    integrated: int = 0
    dropped: int = 0
    #: rows left standing by a cancelled run: the previous numbers, which no
    #: longer answer to the method. Their fingerprints say so, so pressing
    #: Process again finishes what was cancelled.
    pending: int = 0
    #: how many rows were integrated for each reason, and dropped for each
    reasons: dict[str, int] = field(default_factory=dict)
    dropped_reasons: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0
    cancelled: bool = False

    @property
    def total(self) -> int:
        return self.kept + self.integrated + self.pending

    @property
    def reintegrated_manual(self) -> int:
        """Rows the operator had integrated by hand and that were redone."""
        return self.reasons.get(CHANGED_MANUAL, 0)

    @property
    def kept_fraction(self) -> float:
        considered = self.kept + self.integrated + self.pending
        return self.kept / considered if considered else 0.0

    @property
    def is_full(self) -> bool:
        """True when nothing could be kept: the run read every row."""
        return self.kept == 0

    def summary(self) -> str:
        """The one line the status bar shows."""
        parts = [f"{self.kept:,} kept", f"{self.integrated:,} integrated"]
        if self.dropped:
            parts.append(f"{self.dropped:,} dropped")
        if self.reintegrated_manual:
            parts.append(f"{self.reintegrated_manual:,} re-integrated "
                         f"after a manual")
        if self.pending:
            parts.append(f"{self.pending:,} left for the next run")
        # two decimals under a second: the whole point of the thing is runs
        # that take a twentieth of one, and "0.1 s" for all of them says
        # nothing about which
        parts.append(f"{self.seconds:.2f} s" if self.seconds < 1.0
                     else f"{self.seconds:.1f} s")
        return ", ".join(parts)

    def why(self) -> str:
        """The reasons behind those counts, commonest first, as one line."""
        items = list(self.reasons.items()) + list(self.dropped_reasons.items())
        items.sort(key=lambda pair: (-pair[1], pair[0]))
        return "; ".join(f"{count:,} — {reason}" for reason, count in items)


@dataclass(frozen=True)
class _Row:
    """One cell of the batch grid, and what is to be done with it."""

    entry: SampleEntry
    component: Component
    correction: object
    previous: PeakResult | None
    keep: bool
    reason: str


def _plan(entries: list[SampleEntry], method: ProcessingMethod,
          previous: ResultsSet | None,
          corrections: dict | None) -> tuple[list[_Row], dict[str, int]]:
    """
    Which rows can be kept and which have to be read again — reading nothing.

    Everything here is arithmetic over the rows already held, so the Process
    button can ask what a run would cost before it starts one.
    """
    components = [c for c in method.components if c.is_valid]
    loaded = [e for e in entries if e.is_loaded]
    rows = {(r.sample_key, r.component): r for r in (previous or ())}
    known_samples = {key for key, _ in rows}
    known_components = {name for _, name in rows}

    stamps: dict[tuple, str] = {}
    work: list[_Row] = []
    seen: set[tuple[str, str]] = set()
    for entry in loaded:
        correction = (corrections or {}).get(entry.key)
        stamp_key = _correction_key(correction)
        for component in components:
            seen.add((entry.key, component.name))
            wanted = stamps.get((component.name, stamp_key))
            if wanted is None:
                wanted = fingerprint(component, method, correction)
                stamps[(component.name, stamp_key)] = wanted
            row = rows.get((entry.key, component.name))
            if row is None:
                if entry.key not in known_samples:
                    reason = NEW_SAMPLE
                elif component.name not in known_components:
                    reason = NEW_COMPONENT
                else:
                    reason = NO_PREVIOUS_ROW
            elif not row.fingerprint:
                reason = NOT_RECORDED
            elif row.fingerprint == wanted:
                reason = ""
            elif row.manual:
                reason = CHANGED_MANUAL
            else:
                reason = CHANGED
            work.append(_Row(entry, component, correction, row,
                             keep=not reason, reason=reason))

    dropped: dict[str, int] = {}
    open_keys = {e.key for e in loaded}
    for sample_key, name in rows:
        if (sample_key, name) in seen:
            continue
        reason = SAMPLE_GONE if sample_key not in open_keys else COMPONENT_GONE
        dropped[reason] = dropped.get(reason, 0) + 1
    return work, dropped


def incremental_plan(entries: list[SampleEntry], method: ProcessingMethod,
                     previous: ResultsSet | None,
                     corrections: dict | None = None) -> IncrementalReport:
    """
    What `process_incremental` would keep, integrate and drop — before it runs.

    No file is opened and no peak is integrated, so this costs milliseconds on
    a batch that takes minutes to process. It is what decides whether the
    Process button reprocesses incrementally at all.
    """
    started = time.perf_counter()
    work, dropped = _plan(entries, method, previous, corrections)
    report = IncrementalReport(
        kept=sum(1 for row in work if row.keep),
        integrated=sum(1 for row in work if not row.keep),
        dropped=sum(dropped.values()),
        dropped_reasons=dropped,
    )
    for row in work:
        if row.reason:
            report.reasons[row.reason] = report.reasons.get(row.reason, 0) + 1
    report.seconds = time.perf_counter() - started
    return report


def process_incremental(entries: list[SampleEntry], method: ProcessingMethod,
                        previous: ResultsSet, cache: XicCache | None = None,
                        progress=None,
                        corrections: dict | None = None,
                        ) -> tuple[ResultsSet, IncrementalReport]:
    """
    Run the method over only the rows an earlier run cannot answer for.

    Adding one injection to a batch of twenty-six should read one injection.
    What makes that safe is `fingerprint`: a row records the component fields,
    the integration parameters and the mass correction it was integrated
    under, so a row whose fingerprint still matches the method was produced by
    exactly the arithmetic a full run would produce now, and keeping it is not
    an assumption. A row that records nothing — written before fingerprints
    existed — is integrated again, because not knowing is not the same as
    agreeing.

    **A hand-integrated row is kept as it stands** while its component's
    fingerprint holds, which is the whole point of integrating by hand. When
    the fingerprint changes it is integrated again and the report says how
    many: a boundary drawn on one trace is not a decision about a different
    mass window or a different smoothing, and leaving it standing would report
    a peak nobody chose.

    Everything derived — the ratios to the internal standards, the ion ratios,
    and, in the caller, the calibrations and the quality charts — is recomputed
    over the whole set, because those are arithmetic over rows and not reads of
    a file.

    The result is row for row what `process` would give, in the same order,
    with two deliberate exceptions the report names: a row the operator
    integrated by hand, and a row a cancelled run left standing.
    """
    started = time.perf_counter()
    work, dropped = _plan(entries, method, previous, corrections)
    report = IncrementalReport(dropped=sum(dropped.values()),
                               dropped_reasons=dropped)
    to_do = sum(1 for row in work if not row.keep)

    out = ResultsSet()
    done = 0
    for row in work:
        if row.keep:
            # a label is not a measurement: a renamed injection or a regrouped
            # component is written onto the kept row rather than bought with a
            # second read of the file
            row.previous.sample_name = row.entry.name
            row.previous.group = row.component.group
            out.results.append(row.previous)
            report.kept += 1
            continue
        if report.cancelled:
            # what a cancelled run leaves behind is the old numbers, and they
            # say so themselves: the fingerprint on them does not match, so
            # the next run picks them up
            if row.previous is not None:
                out.results.append(row.previous)
                report.pending += 1
            continue
        out.results.append(integrate_component(
            row.entry, row.component, method, cache, row.correction))
        report.integrated += 1
        report.reasons[row.reason] = report.reasons.get(row.reason, 0) + 1
        done += 1
        if progress is not None and progress(done, to_do) is False:
            report.cancelled = True

    link_internal_standards(out, method)
    compute_ion_ratios(out, method)
    report.seconds = time.perf_counter() - started
    return out, report
