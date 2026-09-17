"""
Measuring a precursor's accurate mass from the TOF MS survey scan.

A method's precursor list is written by hand — `351.20`, `313.24` — and is only
good to the decimals it was typed with. Looking a lipid up from that is asking
a database for digits the number does not carry: at ±0.005 Da a mass near 350
is uncertain by 14 ppm, and the search window fills with whatever happens to
sit nearby.

The survey scan holds the real number. This module finds the precursor ion in
the full-scan channel, at the time the product-ion channel actually sees the
peak, and reports the mass the instrument measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .components import Component
from .infusion import verdict_for
from .matching import match_channel
from .method import ProcessingMethod
from .processing import centroid_mz, detect_peaks
from .samples import SampleEntry

#: how far either side of the written precursor to look for the real ion.
#: Wide enough to absorb a hand-rounded value, and well inside the roughly 1 Da
#: that Q1 isolates, so a neighbouring nominal mass can never be picked up.
SEARCH_WINDOW = 0.25

#: a survey peak weaker than this is not worth trusting as a mass measurement
MIN_INTENSITY = 100.0

#: samples disagreeing by more than this are not measuring the same ion
CONSENSUS_SPREAD_PPM = 25.0

#: how far the survey and the surviving precursor may differ and still be
#: taken as the same ion
AGREEMENT_PPM = 25.0


@dataclass
class PrecursorMeasurement:
    """What one sample's survey scan says the precursor mass is."""

    component: str
    sample_key: str
    sample_name: str
    nominal: float
    measured: float | None = None
    intensity: float = 0.0
    rt: float = 0.0
    #: the same precursor read off its own product-ion spectrum, where Q1 has
    #: already removed every co-eluting ion
    product_mz: float | None = None
    #: the recalibration applied at this mass, in ppm, when a correction was
    #: handed in. `measured` always stays what the instrument read: the
    #: correction is fitted from these measurements, so writing it back over
    #: them would be circular, and a corrected number that could not be
    #: compared with its raw one could not be reviewed.
    correction_ppm: float | None = None
    note: str = ""

    @property
    def found(self) -> bool:
        return self.measured is not None

    @property
    def agreement_ppm(self) -> float | None:
        """
        How far the two independent measurements sit apart.

        The survey scan sees everything eluting at that moment, so a strong
        interference within the search window can win. The product-ion scan
        cannot have that problem — whatever survived fragmentation passed
        through Q1's isolation window first. When the two agree, the survey
        really did find the precursor.
        """
        if self.measured is None or self.product_mz is None:
            return None
        return (self.measured - self.product_mz) / self.product_mz * 1e6

    @property
    def corroborated(self) -> bool:
        agreement = self.agreement_ppm
        return agreement is not None and abs(agreement) <= AGREEMENT_PPM

    @property
    def corrected(self) -> float | None:
        """The measurement with the injection's recalibration applied."""
        if self.measured is None or self.correction_ppm is None:
            return None
        return self.measured * (1.0 + self.correction_ppm * 1e-6)

    @property
    def reported(self) -> float | None:
        """Corrected where a correction stands, and raw where none does."""
        return self.corrected if self.corrected is not None else self.measured

    @property
    def error_mda(self) -> float | None:
        if self.measured is None:
            return None
        return (self.measured - self.nominal) * 1000.0

    @property
    def error_ppm(self) -> float | None:
        if self.measured is None or not self.nominal:
            return None
        return (self.measured - self.nominal) / self.nominal * 1e6


@dataclass
class PrecursorConsensus:
    """The measurements of one component pooled across the batch."""

    component: str
    nominal: float
    measured: float | None = None
    samples: list[PrecursorMeasurement] = field(default_factory=list)
    note: str = ""

    @property
    def found(self) -> bool:
        return self.measured is not None

    @property
    def used(self) -> list[PrecursorMeasurement]:
        return [m for m in self.samples if m.found]

    @property
    def spread_ppm(self) -> float | None:
        """
        How far apart the samples are, in ppm.

        A wide spread means the samples are not measuring the same ion — most
        often a co-eluting interference winning in one of them — and the
        consensus should not be trusted.
        """
        values = [m.measured for m in self.used]
        if len(values) < 2:
            return None
        centre = float(np.mean(values))
        if not centre:
            return None
        return (max(values) - min(values)) / centre * 1e6

    @property
    def shift_ppm(self) -> float | None:
        if self.measured is None or not self.nominal:
            return None
        return (self.measured - self.nominal) / self.nominal * 1e6

    @property
    def corroborated(self) -> int:
        """How many samples had the survey confirmed by the product-ion scan."""
        return sum(1 for m in self.used if m.corroborated)

    @property
    def is_reliable(self) -> bool:
        """
        Consistent across the batch, and confirmed by the product-ion scan
        wherever that check could be made.
        """
        if not self.found:
            return False
        spread = self.spread_ppm
        if spread is not None and spread > CONSENSUS_SPREAD_PPM:
            return False
        checkable = [m for m in self.used if m.product_mz is not None]
        if checkable:
            return self.corroborated >= (len(checkable) + 1) // 2
        return True


def survey_channel(sample, mz: float, rt: float | None = None):
    """
    The full-scan channel that covers a mass, and the time if one is given.

    Scheduled methods split the survey across periods, so the channel that
    holds a mass at 5 minutes need not be the one that holds it at 15.
    """
    candidates = [
        c for c in sample.channels
        if c.info.is_ms1 and c.info.start_mass <= mz <= c.info.end_mass
    ]
    if rt is not None:
        for channel in candidates:
            times = channel.rt
            if times.size and times[0] <= rt <= times[-1]:
                return channel
    return candidates[0] if candidates else None


def _anchor_rt(entry: SampleEntry, component: Component) -> float | None:
    """
    When to look. The component's own retention time if it has one, otherwise
    the apex of a peak actually detected in its product-ion channel.

    A detected peak, not just the tallest point: a transition carrying only
    noise still has a maximum somewhere, and anchoring on it would send the
    survey search to an arbitrary time, where it would dutifully measure
    whatever ion happened to be co-eluting. If the transition shows nothing,
    there is nothing to annotate.

    A direct infusion is the case where all of that is the wrong question.
    There is no peak, and a retention time copied into the method from a
    chromatographic one points outside a run that lasts a minute — which used
    to leave the measurement either refused for want of an anchor or taken
    over three scans of a run whose every scan is the same. The middle of the
    run stands for all of it, and `measure` then averages the whole run.
    """
    channel = match_channel(entry.sample, component)
    if verdict_for(entry.sample):
        # an infusion has no peak to anchor on and no retention time worth
        # believing — the compound is there from the first scan to the last —
        # so the middle of the run stands for all of it
        times = channel.rt if channel is not None else np.zeros(0)
        if times.size == 0:
            return None
        return float(times[times.size // 2])
    if component.rt is not None:
        return component.rt
    if channel is None:
        return None
    x, y = channel.tic()
    if x.size == 0:
        return None
    peaks = detect_peaks(x, y, min_relative=0.2, min_snr=10.0)
    return peaks[0].apex_rt if peaks else None


def measure(entry: SampleEntry, component: Component,
            method: ProcessingMethod | None = None,
            window: float = SEARCH_WINDOW,
            min_intensity: float = MIN_INTENSITY,
            correction=None) -> PrecursorMeasurement:
    """
    Find the precursor in one sample's survey scan and read its mass.

    `correction` is a `recalibrate.MassCorrection` for this injection, or
    None. It never moves the search — the window is a quarter of a dalton
    and the correction is parts per million, so shifting it would change
    nothing but the story — and it never touches `measured`. It fills in
    `correction_ppm`, from which `corrected` follows, so the raw and the
    recalibrated number sit side by side.
    """
    result = PrecursorMeasurement(
        component=component.name, sample_key=entry.key,
        sample_name=entry.name, nominal=component.precursor,
    )
    if not entry.is_loaded:
        result.note = "sample not open"
        return result
    if component.precursor <= 0:
        result.note = "no precursor mass"
        return result

    anchor = _anchor_rt(entry, component)
    if anchor is None:
        result.note = "no peak in the product-ion channel to anchor on"
        return result
    survey = survey_channel(entry.sample, component.precursor, anchor)
    if survey is None:
        result.note = "no survey scan covers this mass"
        return result

    lo, hi = component.precursor - window, component.precursor + window
    x, y = survey.xic_range(lo, hi)
    if x.size == 0:
        result.note = "no survey data"
        return result

    # Narrow to the component's expected window when it has one, so a bigger
    # peak elsewhere in the run cannot claim the measurement. An infusion has
    # no such window: every scan is the same spectrum, and all of them count.
    infused = bool(verdict_for(entry.sample))
    mask = np.ones(x.size, dtype=bool)
    rt_window = None if infused else component.rt_window()
    if rt_window is not None:
        inside = (x >= rt_window[0]) & (x <= rt_window[1])
        if inside.sum() >= 3:
            mask = inside
    elif anchor is not None and not infused:
        inside = np.abs(x - anchor) <= 0.3
        if inside.sum() >= 3:
            mask = inside

    times, response = x[mask], y[mask]
    if float(np.max(response)) <= 0:
        result.note = "precursor not seen in the survey scan"
        return result

    peaks = [] if infused else detect_peaks(times, response, min_relative=0.2,
                                            min_snr=3.0)
    if infused:
        # the whole run is the measurement, which is what makes an infusion
        # worth measuring at all: every scan of it averages into one spectrum
        apex_rt = anchor
        start, end = float(times[0]), float(times[-1])
    elif peaks:
        apex_rt, start, end = peaks[0].apex_rt, peaks[0].start_rt, peaks[0].end_rt
    else:
        apex_rt = float(times[int(np.argmax(response))])
        start = end = apex_rt
    result.rt = apex_rt

    mz, intensity = survey.spectrum_rt_range(min(start, apex_rt),
                                             max(end, apex_rt))
    inside = (mz >= lo) & (mz <= hi)
    if not inside.any():
        result.note = "precursor not seen in the survey scan"
        return result

    local_i = intensity[inside]
    apex = int(np.argmax(local_i))
    height = float(local_i[apex])
    if height < min_intensity:
        result.intensity = height
        result.note = f"survey signal too weak ({height:,.0f})"
        return result

    # centre of gravity across the profile peak, the same refinement the
    # spectrum's own peak labels use
    absolute = int(np.nonzero(inside)[0][apex])
    result.measured = centroid_mz(mz, intensity, absolute)
    result.intensity = height
    result.product_mz = _surviving_precursor(entry, component, start, end,
                                             apex_rt, window)
    if correction is not None and correction.usable:
        result.correction_ppm = float(correction.ppm_at(result.measured))
    if result.product_mz is not None and not result.corroborated:
        result.note = (f"survey and product-ion scans differ by "
                       f"{result.agreement_ppm:+.0f} ppm")
    return result


def in_spectrum(mz, intensity, target: float,
                window: float = SEARCH_WINDOW,
                floor: float | None = None) -> tuple[float, float] | None:
    """
    The strongest thing within `window` of `target` in a spectrum already
    read: its accurate mass and its height.

    The one rule for turning a spectrum into a mass — the tallest point inside
    the window, refined to the centre of gravity across the profile peak, the
    same refinement the spectrum's own peak labels use. `measure` applies it
    to the survey scan and `_surviving_precursor` to the product-ion scan; an
    infusion report applies it to the averaged spectrum it already holds,
    which is why this is public rather than written out three times.

    The height comes back with the mass because a centroid says nothing about
    whether there was anything there to centroid: at 45 eV a bile-acid
    precursor leaves 84 counts of nothing in particular inside its own window,
    and a caller that cannot see the height reports that as a mass 70 ppm out.

    `floor` is the height below which what is in the window is noise rather
    than a measurement, and the window is then reported as holding nothing.
    A caller that has measured its own — `infusion.noise_floor`, which reads
    it off the acquisition — should hand it in; `MIN_INTENSITY` is the fixed
    one `measure` holds the survey scan to, and it is a statement about one
    scan of a TripleTOF rather than about every instrument. None applies no
    gate at all, which is what a caller wanting the height whatever it is
    needs.

    Returns None when the window holds nothing at all, or nothing above the
    floor where one is given.
    """
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if mz.size == 0 or mz.size != intensity.size:
        return None
    inside = (mz >= target - window) & (mz <= target + window)
    if not inside.any() or float(intensity[inside].max()) <= 0:
        return None
    local = int(np.argmax(intensity[inside]))
    absolute = int(np.nonzero(inside)[0][local])
    height = float(intensity[absolute])
    if floor is not None and height < float(floor):
        return None
    return centroid_mz(mz, intensity, absolute), height


def _surviving_precursor(entry: SampleEntry, component: Component,
                         start: float, end: float, apex: float,
                         window: float) -> float | None:
    """
    The unfragmented precursor in its own product-ion spectrum.

    Independent of the survey scan and immune to co-elution, because Q1
    isolated roughly one dalton before anything reached the collision cell.
    """
    channel = match_channel(entry.sample, component)
    if channel is None or channel.info.is_ms1:
        return None
    if component.precursor > channel.info.end_mass:
        return None            # the scan range stops below the precursor
    mz, intensity = channel.spectrum_rt_range(min(start, apex), max(end, apex))
    found = in_spectrum(mz, intensity, component.precursor, window)
    return None if found is None else found[0]


def measure_across(entries: list[SampleEntry], component: Component,
                   method: ProcessingMethod | None = None,
                   window: float = SEARCH_WINDOW,
                   min_intensity: float = MIN_INTENSITY) -> PrecursorConsensus:
    """
    Pool one component's measurements over the batch.

    The consensus is weighted by survey intensity: a strong peak locates a
    centroid far better than a weak one, and averaging them evenly would let
    the noisiest sample drag the answer.
    """
    consensus = PrecursorConsensus(component=component.name,
                                   nominal=component.precursor)
    consensus.samples = [
        measure(entry, component, method, window, min_intensity)
        for entry in entries
    ]
    used = consensus.used
    if not used:
        notes = {m.note for m in consensus.samples if m.note}
        consensus.note = sorted(notes)[0] if notes else "not measured"
        return consensus

    masses = np.array([m.measured for m in used], dtype=float)
    weights = np.array([max(m.intensity, 1.0) for m in used], dtype=float)
    consensus.measured = float(np.average(masses, weights=weights))

    spread = consensus.spread_ppm
    checkable = [m for m in used if m.product_mz is not None]
    if spread is not None and spread > CONSENSUS_SPREAD_PPM:
        consensus.note = (f"samples disagree by {spread:.0f} ppm — probably a "
                          "co-eluting ion in at least one of them")
    elif checkable and consensus.corroborated < (len(checkable) + 1) // 2:
        consensus.note = ("the product-ion scan does not confirm this ion — "
                          "the survey window may have caught an interference")
    elif checkable:
        consensus.note = (f"confirmed by the product-ion scan in "
                          f"{consensus.corroborated} of {len(checkable)} sample(s)")
    return consensus


def measure_all(entries: list[SampleEntry], components: list[Component],
                method: ProcessingMethod | None = None,
                window: float = SEARCH_WINDOW,
                min_intensity: float = MIN_INTENSITY,
                progress=None) -> dict[str, PrecursorConsensus]:
    """
    Measure every component. `progress(done, total)` may return False to stop.
    """
    loaded = [e for e in entries if e.is_loaded]
    out: dict[str, PrecursorConsensus] = {}
    total = len(components)
    for done, component in enumerate(components, start=1):
        out[component.name] = measure_across(loaded, component, method,
                                             window, min_intensity)
        if progress is not None and progress(done, total) is False:
            break
    return out
