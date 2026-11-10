"""
Where an extracted ion chromatogram or a spectrum is read from, and
precursor-gated extraction.

In data-dependent acquisition (SCIEX IDA, any DDA mzML) a product-ion
channel is not one precursor's: an IDA dependent slot isolates whatever the
survey offered that cycle — 298 different precursors in 405 triggered
cycles of one TripleTOF 5600 slot. An XIC or an average over such a channel
mixes every one of them. The answer is to choose scans by what they
isolated rather than by which slot they landed in: **gated** extraction keeps
only the MS2 scans whose own precursor (`Channel.scan_details().parent_mz`)
lies within a tolerance of a target, from every channel, merged by
retention time.

A source is written the way the command-line contract writes it
(`docs/CLI-CONTRACT.md`):

    ms1               the survey channel(s)
    channel:N         one channel by index
    ms2-all           every MS2 scan of every channel
    gated:MZ[:TOL]    the MS2 scans that isolated MZ ± TOL (default 0.05 Da)

The arithmetic is the reader's wherever it can be. A gated XIC is each
channel's own extraction (`xic_range`, the vendor's on a `.wiff`) with the
scans that isolated something else taken out, never a re-summing of points.
A gated spectrum has to be averaged here, because the vendor's average over
a time range takes every scan of the slot; it adds each scan up at the
masses it measured and divides by the number of scans, the rule that
reproduces SCIEX's own average of 146 scans exactly (see
`MzmlChannel.spectrum_rt_range`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: how close two sticks from different scans must be to be one ion in an
#: average across scans, in Da — MIL-X's figure, so the two tools agree
MERGE_DA = 0.01

#: the tolerance a gate uses when none is given, in Da. An IDA precursor is
#: the survey's centroid, to a few millidaltons; 0.05 Da keeps every
#: re-isolation of one ion and none of its 13C neighbour.
DEFAULT_PARENT_TOL = 0.05

SOURCE_CHANNEL = "channel"
SOURCE_MS1 = "ms1"
SOURCE_MS2_ALL = "ms2-all"
SOURCE_GATED = "gated"


class SourceError(ValueError):
    """A source that cannot be parsed or does not exist in the sample."""


@dataclass(frozen=True)
class Source:
    """One of the four places a trace can be read from."""

    kind: str
    channel: int | None = None
    mz: float | None = None
    tol: float = DEFAULT_PARENT_TOL

    @classmethod
    def parse(cls, text: str | None) -> "Source":
        text = (text or SOURCE_MS1).strip()
        head, _, rest = text.partition(":")
        head = head.lower()
        if head == SOURCE_MS1 and not rest:
            return cls(SOURCE_MS1)
        if head == SOURCE_MS2_ALL and not rest:
            return cls(SOURCE_MS2_ALL)
        try:
            if head == SOURCE_CHANNEL and rest:
                return cls(SOURCE_CHANNEL, channel=int(rest))
            if head == SOURCE_GATED and rest:
                mz, _, tol = rest.partition(":")
                return cls(SOURCE_GATED, mz=float(mz),
                           tol=float(tol) if tol else DEFAULT_PARENT_TOL)
        except ValueError:
            pass
        raise SourceError(f"not a source: {text!r} (ms1, channel:N, ms2-all, "
                          f"gated:MZ[:TOL])")

    @classmethod
    def gated(cls, mz: float, tol: float = DEFAULT_PARENT_TOL) -> "Source":
        return cls(SOURCE_GATED, mz=float(mz), tol=float(tol))

    def __str__(self) -> str:
        if self.kind == SOURCE_CHANNEL:
            return f"channel:{self.channel}"
        if self.kind == SOURCE_GATED:
            return f"gated:{self.mz:.4f}:{self.tol:g}"
        return self.kind

    @property
    def merges(self) -> bool:
        """Whether the source spans channels (and is merged by time)."""
        return self.kind in (SOURCE_MS2_ALL, SOURCE_GATED)


@dataclass(frozen=True)
class ScanRef:
    """One scan a trace was made from."""

    channel: int
    scan: int
    rt: float
    parent_mz: float | None


@dataclass
class Trace:
    """A chromatogram from a source, and the scans it stands on."""

    rt: np.ndarray
    intensity: np.ndarray
    source: Source
    scans: list[ScanRef] = field(default_factory=list)


@dataclass
class GatedSpectrum:
    """A spectrum from a source, with every scan it averaged."""

    mz: np.ndarray
    intensity: np.ndarray
    source: Source
    scans: list[ScanRef] = field(default_factory=list)

    @property
    def parents(self) -> np.ndarray:
        values = [s.parent_mz for s in self.scans if s.parent_mz is not None]
        return np.asarray(values, dtype=float)


# --------------------------------------------------------------------------- #
def _details(channel):
    """`scan_details()` where the reader has it, a constant otherwise."""
    reader = getattr(channel, "scan_details", None)
    if reader is not None:
        return reader()
    from .wiff import ScanDetails

    info = channel.info
    return ScanDetails.constant(len(channel.rt), info.precursor, None,
                                info.collision_energy)


def ms2_channels(sample) -> list:
    """Every channel of the sample that is not a survey."""
    return [c for c in sample.channels if not c.info.is_ms1]


def survey_channels(sample) -> list:
    return [c for c in sample.channels if c.info.is_ms1]


def _selected(channel, source: Source) -> np.ndarray:
    """Which scans of one MS2 channel a merging source takes."""
    parents = np.asarray(_details(channel).parent_mz, dtype=float)
    keep = np.isfinite(parents)
    if source.kind == SOURCE_GATED:
        keep &= np.abs(parents - float(source.mz)) <= float(source.tol) + 1e-9
    return keep


def channels_of(sample, source: Source) -> list:
    """The channels a source reads, in index order."""
    if source.kind == SOURCE_CHANNEL:
        for channel in sample.channels:
            if channel.index == source.channel:
                return [channel]
        raise SourceError(f"the sample has no channel {source.channel}")
    if source.kind == SOURCE_MS1:
        found = survey_channels(sample)
        if not found:
            raise SourceError("the sample has no survey (MS1) channel")
        return found
    return ms2_channels(sample)


def selected_scans(sample, source: Source, rt_range=None) -> list[ScanRef]:
    """Every scan a source reads, in time order (channel order at a tie)."""
    refs: list[ScanRef] = []
    lo, hi = (sorted(map(float, rt_range)) if rt_range is not None
              else (-np.inf, np.inf))
    for channel in channels_of(sample, source):
        times = np.asarray(channel.rt, dtype=float)
        parents = np.asarray(_details(channel).parent_mz, dtype=float)
        if source.merges:
            keep = _selected(channel, source)
        else:
            keep = np.ones(times.size, dtype=bool)
        keep = keep[:times.size] & (times >= lo) & (times <= hi)
        for scan in np.nonzero(keep)[0]:
            parent = parents[scan] if scan < parents.size else np.nan
            refs.append(ScanRef(int(channel.index), int(scan), float(times[scan]),
                                float(parent) if np.isfinite(parent) else None))
    refs.sort(key=lambda r: (r.rt, r.channel, r.scan))
    return refs


def xic(sample, mz_lo: float, mz_hi: float, source: Source) -> Trace:
    """
    An extracted ion chromatogram over [mz_lo, mz_hi] from a source.

    One channel is that channel's extraction as it stands. Several — every
    survey of a scheduled method, every MS2 channel, the gated scans — are
    each channel's own extraction restricted to the scans the source takes,
    laid on one time axis; scans at the same retention time (the slots of
    one IDA cycle share their cycle's) are added, so the trace has one
    point per time.
    """
    channels = channels_of(sample, source)
    if source.kind == SOURCE_CHANNEL:
        rt, y = channels[0].xic_range(mz_lo, mz_hi)
        rt = np.asarray(rt, dtype=float)
        parents = np.asarray(_details(channels[0]).parent_mz, dtype=float)
        return Trace(rt, np.asarray(y, dtype=float), source, [
            ScanRef(int(channels[0].index), i, float(t),
                    float(parents[i]) if i < parents.size
                    and np.isfinite(parents[i]) else None)
            for i, t in enumerate(rt)])
    times, values, refs = [], [], []
    for channel in channels:
        rt, y = channel.xic_range(mz_lo, mz_hi)
        rt = np.asarray(rt, dtype=float)
        y = np.asarray(y, dtype=float)
        if source.merges:
            keep = _selected(channel, source)[:rt.size]
        else:
            keep = np.ones(rt.size, dtype=bool)
        parents = np.asarray(_details(channel).parent_mz, dtype=float)
        for scan in np.nonzero(keep)[0]:
            refs.append(ScanRef(int(channel.index), int(scan), float(rt[scan]),
                                float(parents[scan])
                                if scan < parents.size and np.isfinite(parents[scan])
                                else None))
        times.append(rt[keep])
        values.append(y[keep])
    if not times or not sum(t.size for t in times):
        return Trace(np.zeros(0), np.zeros(0), source, [])
    rt = np.concatenate(times)
    y = np.concatenate(values)
    axis, where = np.unique(rt, return_inverse=True)
    summed = np.bincount(where, weights=y, minlength=axis.size)
    refs.sort(key=lambda r: (r.rt, r.channel, r.scan))
    return Trace(axis, summed, source, refs)


def _accumulate(parts: list[tuple[np.ndarray, np.ndarray]]):
    """Each scan added up at the masses it measured, divided by the count."""
    masses = [np.asarray(m, dtype=float) for m, _ in parts]
    if not parts or not sum(m.size for m in masses):
        return np.zeros(0), np.zeros(0)
    every = np.concatenate(masses)
    heights = np.concatenate([np.asarray(i, dtype=float) for _, i in parts])
    axis, where = np.unique(every, return_inverse=True)
    total = np.bincount(where, weights=heights, minlength=axis.size)
    return axis, total / len(parts)


def merge_sticks(parts: list[tuple[np.ndarray, np.ndarray]],
                 tolerance: float = MERGE_DA):
    """
    Sticks from several scans as one spectrum: every run of sticks closer
    than `tolerance` to its neighbour is one ion, at the intensity-weighted
    m/z, with the summed intensity divided by the number of scans (a mean).

    Why not `_accumulate`: adding each scan up at the masses it measured is
    right for profile scans of one experiment, which share the digitizer's
    axis — it reproduced SCIEX's own average exactly. Centroids, and scans
    from different IDA slots, do not share an axis, and there it split one
    ion into a stick per scan: a fragment read 5,825 where the mean of the
    same 20 scans is 64,368 (the cross-check of 2026-11-09).
    """
    if not parts:
        return np.zeros(0), np.zeros(0)
    mz = np.concatenate([np.asarray(m, dtype=float) for m, _ in parts])
    height = np.concatenate([np.asarray(h, dtype=float) for _, h in parts])
    keep = height > 0
    mz, height = mz[keep], height[keep]
    if mz.size == 0:
        return np.zeros(0), np.zeros(0)
    order = np.argsort(mz, kind="stable")
    mz, height = mz[order], height[order]
    starts = np.concatenate(([0], np.nonzero(np.diff(mz) > tolerance)[0] + 1))
    total = np.add.reduceat(height, starts)
    weighted = np.add.reduceat(mz * height, starts)
    return weighted / total, total / len(parts)


def spectrum(sample, source: Source, rt_range=None,
             scan: int | None = None, centroid_each: bool = False) -> GatedSpectrum:
    """
    The spectrum a source gives over a time range (or one scan of a channel).

    `channel:N` with no range and a `scan` is that scan; with a range it is
    the reader's own average. MS1 with several survey channels takes the one
    covering the middle of the range. A merging source averages the scans it
    selects, at their measured masses, and lists them.
    """
    channels = channels_of(sample, source)
    if not source.merges:
        if source.kind == SOURCE_MS1 and rt_range is not None:
            middle = sum(map(float, rt_range)) / 2.0
            channel = next((c for c in channels if c.rt.size
                            and c.rt[0] <= middle <= c.rt[-1]), channels[0])
        else:
            channel = channels[0]
        parents = np.asarray(_details(channel).parent_mz, dtype=float)
        if scan is not None or rt_range is None:
            index = int(scan or 0)
            mz, intensity = channel.spectrum(index, add_zeros=False)
            rt = float(channel.rt_at_scan(index))
            used = [ScanRef(int(channel.index), index, rt,
                            float(parents[index]) if index < parents.size
                            and np.isfinite(parents[index]) else None)]
        else:
            lo, hi = sorted(map(float, rt_range))
            first, last = channel.scans_in_range(lo, hi)
            mz, intensity = channel.spectrum_rt_range(lo, hi, add_zeros=False)
            times = channel.rt
            used = [ScanRef(int(channel.index), i, float(times[i]),
                            float(parents[i]) if i < parents.size
                            and np.isfinite(parents[i]) else None)
                    for i in range(first, last + 1)]
        return GatedSpectrum(np.asarray(mz, dtype=float),
                             np.asarray(intensity, dtype=float), source, used)
    refs = selected_scans(sample, source, rt_range if scan is None else None)
    if scan is not None:
        # `--scan N` on a merged source is the source's N-th scan, as on a
        # channel: one scan, never the average of all of them
        if not 0 <= int(scan) < len(refs):
            raise SourceError(f"{source} has {len(refs)} scans; no scan {scan}")
        refs = [refs[int(scan)]]
    by_index = {c.index: c for c in channels}
    parts, sticks = [], True
    for r in refs:
        channel = by_index[r.channel]
        mz, height = channel.spectrum(r.scan, add_zeros=False)
        if getattr(channel.info, "centroided", False):
            pass
        elif centroid_each:
            from .processing import centroid_spectrum

            mz, height = centroid_spectrum(np.asarray(mz, dtype=float),
                                           np.asarray(height, dtype=float))
        else:
            sticks = False
        parts.append((mz, height))
    if sticks:
        mz, intensity = merge_sticks(parts)
    else:
        # profile kept as profile: valid within one experiment's axis
        mz, intensity = _accumulate(parts)
    return GatedSpectrum(mz, intensity, source, refs)


# --------------------------------------------------------------------------- #
def precursors_shown(channel, scan: int | None = None, rt0: float | None = None,
                     rt1: float | None = None) -> np.ndarray:
    """
    The precursors behind a spectrum of one channel: the scan's, or every
    distinct one of the triggered scans in the range. Empty for a survey.
    """
    parents = np.asarray(_details(channel).parent_mz, dtype=float)
    if scan is not None:
        value = parents[int(scan)] if 0 <= int(scan) < parents.size else np.nan
        return np.array([value]) if np.isfinite(value) else np.zeros(0)
    times = np.asarray(channel.rt, dtype=float)
    if rt0 is None or rt1 is None:
        inside = np.ones(times.size, dtype=bool)
    else:
        lo, hi = sorted((float(rt0), float(rt1)))
        inside = (times >= lo) & (times <= hi)
    values = parents[:times.size][inside[:parents.size]]
    return values[np.isfinite(values)]


def precursor_shown(channel, scan: int | None = None, rt0: float | None = None,
                    rt1: float | None = None,
                    tol: float = DEFAULT_PARENT_TOL) -> float | None:
    """
    The one precursor a spectrum of this channel stands for, or None.

    A fixed channel's own precursor; for a per-scan channel the scan's, or —
    over a range — the median of the triggered scans' when they all lie
    within `tol` of one another. A range that mixes precursors has none,
    and nothing downstream (a library search, an explanation) is handed a
    precursor that only some of the averaged scans isolated.
    """
    info = channel.info
    if not getattr(info, "per_scan", False):
        return info.precursor
    values = precursors_shown(channel, scan, rt0, rt1)
    if values.size == 0:
        return None
    if float(values.max() - values.min()) > tol:
        return None
    return float(np.median(values))


def describe_precursors(values: np.ndarray, tol: float = DEFAULT_PARENT_TOL) -> str:
    """'parent 627.8457', or 'mixes 37 precursors (412.1–890.3)', or ''."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return ""
    if float(values.max() - values.min()) <= tol:
        return f"parent {float(np.median(values)):.4f}"
    distinct = np.unique(np.round(values / tol)).size
    return (f"mixes {distinct} precursors "
            f"({values.min():.2f}–{values.max():.2f})")
