"""
The suite's command-line contract (`docs/CLI-CONTRACT.md`, `mil-cli/1`),
implemented without a window.

Every subcommand of `milq <subcommand>` is a function here returning a
plain document (a dict in the order the contract prints it). `cli.py` adds
the envelope and writes JSON or TSV; `serve.py` runs the same functions for
requests from a pipe or a watched folder; `api.py` exposes them to scripts.
One implementation, so the three give the same numbers.

Nothing here imports Qt. Numbers follow the contract: m/z to 4 decimals (6
for theoretical values), retention times in minutes to 4, intensities as the
reader reports them; a period for the decimal mark whatever the locale,
because `json` and `repr` never use another.
"""

from __future__ import annotations

import collections
import os
import platform
import time
from dataclasses import dataclass, field

import numpy as np


SCHEMA = "mil-cli/1"
TOOL = "milq"

#: exit codes and error names of the contract
EXIT_ARGUMENTS, EXIT_FILE, EXIT_NOTHING, EXIT_INTERNAL = 2, 3, 4, 5


class ContractError(Exception):
    """An error the contract names, with its exit code."""

    def __init__(self, code: str, message: str, exit_code: int = EXIT_ARGUMENTS):
        super().__init__(message)
        self.code, self.message, self.exit_code = code, message, exit_code


#: the noise convention every S/N in a summary uses, named in the output
NOISE_CONVENTION = ("milq.processing.estimate_noise: the median absolute "
                    "deviation of point-to-point differences of the extracted "
                    "trace, scaled to a standard deviation; null where the "
                    "trace has no measurable baseline (most of a scheduled "
                    "acquisition), and then S/N is null")


def mz4(value) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), 4)


def mz6(value) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), 6)


def rt4(value) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), 4)


def num(value) -> float | None:
    """An intensity as the reader reported it (a float, never NaN)."""
    if value is None:
        return None
    value = float(value)
    return value if np.isfinite(value) else None


# --------------------------------------------------------------------------- #
# readers kept open: the point of `serve`
# --------------------------------------------------------------------------- #
MAX_OPEN = 4
_OPEN: "collections.OrderedDict[str, object]" = collections.OrderedDict()


def open_file(path: str):
    """A reader for `path`, from the open ones when it is there (LRU)."""
    from .raw import open_raw

    real = os.path.realpath(os.path.expanduser(str(path)))
    if not os.path.exists(real):
        raise ContractError("file_unreadable", f"no such file: {real}", EXIT_FILE)
    if real.lower().endswith(".wiff") and not os.path.exists(real + ".scan"):
        raise ContractError("missing_companion",
                            f"{os.path.basename(real)}.scan is not beside it",
                            EXIT_FILE)
    stamp = (os.path.getsize(real), os.stat(real).st_mtime_ns)
    held = _OPEN.get(real)
    if held is not None and held[1] == stamp:
        _OPEN.move_to_end(real)
        return held[0]
    if held is not None:
        _close(held[0])
    try:
        reader = open_raw(real)
    except Exception as exc:
        raise ContractError("file_unreadable", f"{os.path.basename(real)}: "
                            f"{type(exc).__name__}: {exc}", EXIT_FILE) from exc
    _OPEN[real] = (reader, stamp)
    while len(_OPEN) > MAX_OPEN:
        _close(_OPEN.popitem(last=False)[1][0])
    return reader


def _close(reader) -> None:
    try:
        reader.close()
    except Exception:
        pass


def close_all() -> None:
    while _OPEN:
        _close(_OPEN.popitem()[1][0])


def _sample(path: str, sample):
    reader = open_file(path)
    names = list(reader.sample_names)
    if sample is None or sample == "":
        index = 0
    elif isinstance(sample, int) or str(sample).isdigit():
        index = int(sample)
    elif str(sample) in names:
        index = names.index(str(sample))
    else:
        raise ContractError("bad_sample", f"no sample {sample!r} in {path}; "
                            f"there are {len(names)}")
    if not 0 <= index < len(names):
        raise ContractError("bad_sample", f"sample {index} out of range "
                            f"(0–{len(names) - 1})")
    return reader, reader.sample(index), index


def input_block(path: str, sample_index: int | None) -> dict:
    out = {"path": os.path.realpath(os.path.expanduser(str(path)))}
    if sample_index is not None:
        out["sample"] = sample_index
    return out


# --------------------------------------------------------------------------- #
# parsing the contract's small grammars
# --------------------------------------------------------------------------- #
def parse_range(text) -> tuple[float, float] | None:
    if text in (None, ""):
        return None
    if isinstance(text, (list, tuple)) and len(text) == 2:
        lo, hi = map(float, text)
    else:
        parts = str(text).replace("–", ":").split(":")
        if len(parts) != 2:
            raise ContractError("bad_arguments", f"not a range A:B: {text!r}")
        lo, hi = float(parts[0]), float(parts[1])
    return (min(lo, hi), max(lo, hi))


def parse_masses(value) -> list[float]:
    if value in (None, ""):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            items.extend(parse_masses(item))
        return items
    text = str(value).replace(",", " ").replace(";", " ")
    try:
        return [float(p) for p in text.split()]
    except ValueError as exc:
        raise ContractError("bad_arguments", f"not a list of m/z: {value!r}") from exc


def parse_parent(text) -> tuple[float, float] | None:
    """`MZ[:TOL]` → (mz, tol)."""
    from .gating import DEFAULT_PARENT_TOL

    if text in (None, ""):
        return None
    mz, _, tol = str(text).partition(":")
    return float(mz), float(tol) if tol else DEFAULT_PARENT_TOL


def parse_source(text):
    from .gating import Source, SourceError

    try:
        return Source.parse(text or "ms1")
    except SourceError as exc:
        raise ContractError("bad_source", str(exc)) from exc


def _window(mz: float, tol: float, unit: str) -> tuple[float, float]:
    half = mz * tol * 1e-6 if str(unit).lower() == "ppm" else tol
    return mz - half, mz + half


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #
def selftest(files=()) -> dict:
    """What works on this machine: the runtime, the vendor SDK, each file."""
    from . import bootstrap

    doc = {"platform": {"system": platform.system(), "machine": platform.machine(),
                        "python": platform.python_version()}}
    sdk: dict = {}
    started = time.perf_counter()
    try:
        bootstrap.ensure()
        sdk = {"ok": True, "dotnet": str(bootstrap.find_dotnet_root() or ""),
               "seconds": round(time.perf_counter() - started, 2)}
    except Exception as exc:
        sdk = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
               "note": ("the SCIEX .wiff path is unavailable here; mzML is read "
                        "without it, and `convert` on a machine where .wiff "
                        "reads gives an mzML this one can use")}
    doc["vendor_sdk"] = sdk
    doc["wiff_readable"] = bool(sdk.get("ok"))
    checks = []
    for path in files:
        entry = {"path": os.path.realpath(path)}
        try:
            reader, sample, _ = _sample(path, 0)
            channel = sample.channels[0]
            rt, _y = channel.tic()
            channel.spectrum(int(len(rt) // 2))
            entry.update(ok=True, samples=len(reader.sample_names),
                         channels=len(sample.channels), scans=int(len(rt)))
        except ContractError as exc:
            entry.update(ok=False, error=exc.code, message=exc.message)
        except Exception as exc:
            entry.update(ok=False, error="file_unreadable",
                         message=f"{type(exc).__name__}: {exc}")
        checks.append(entry)
    doc["files"] = checks
    return doc


# --------------------------------------------------------------------------- #
# info
# --------------------------------------------------------------------------- #
def _channel_row(channel) -> dict:
    info = channel.info
    details = channel.scan_details()
    widths = details.isolation[np.isfinite(details.isolation)]
    return {
        "index": int(channel.index),
        "kind": info.kind or ("ms1" if info.is_ms1 else "other"),
        "label": info.label,
        "name": info.name,
        "scans": int(info.n_scans),
        "mass_range": [mz4(info.start_mass), mz4(info.end_mass)],
        "precursor": mz4(info.precursor),
        "isolation": mz4(float(widths[0])) if widths.size else None,
        "ce": num(info.collision_energy),
        "polarity": str(info.polarity).lower(),
    }


def info(path: str, sample=None) -> dict:
    reader, smp, index = _sample(path, sample)
    rt = smp.tic()[0]
    return {
        "samples": [{"index": i, "name": str(n)}
                    for i, n in enumerate(reader.sample_names)],
        "sample": {"index": index, "name": str(smp.name),
                   "instrument": str(getattr(smp, "instrument", "") or ""),
                   "acquired": str(getattr(smp, "acquisition_time", "") or ""),
                   "rt_range": [rt4(rt[0]), rt4(rt[-1])] if len(rt) else None,
                   "problem": getattr(smp, "problem", None) or None},
        "channels": [_channel_row(c) for c in smp.channels],
    }, index


# --------------------------------------------------------------------------- #
# scans
# --------------------------------------------------------------------------- #
def _points(channel, path, sample_index, cache) -> np.ndarray:
    """Data points per scan, from the sidecar when it has them."""
    from . import sidecar

    return sidecar.points(channel, path, sample_index, cache)


def scans(path: str, sample=None, source: str | None = None, rt=None,
          parent=None, ms_level=None, count: bool = False,
          cache: str | None = None) -> tuple[dict, int]:
    from .gating import Source

    _reader, smp, index = _sample(path, sample)
    chosen = (smp.channels if source in (None, "", "all")
              else _channels_for(smp, parse_source(source)))
    window = parse_range(rt)
    gate = parse_parent(parent)
    level = None if ms_level in (None, "") else int(ms_level)
    rows = []
    for channel in chosen:
        times, totals = channel.tic()
        details = channel.scan_details()
        level_of = 1 if channel.info.is_ms1 else 2
        if level is not None and level_of != level:
            continue
        parents = details.parent_mz
        keep = np.ones(len(times), dtype=bool)
        if channel.info.per_scan:
            keep &= np.isfinite(parents[:len(times)])
        if window is not None:
            keep &= (times >= window[0]) & (times <= window[1])
        if gate is not None:
            keep &= np.abs(parents[:len(times)] - gate[0]) <= gate[1] + 1e-9
        if isinstance(_source_of(source), Source) and _source_of(source).kind == "gated":
            src = _source_of(source)
            keep &= np.abs(parents[:len(times)] - src.mz) <= src.tol + 1e-9
        if count:
            rows.append({"channel": int(channel.index), "scans": int(keep.sum())})
            continue
        points = _points(channel, path, index, cache) if keep.any() else None
        cycles = getattr(channel, "scan_cycles", None)
        cycle_of = cycles() if cycles is not None else np.arange(len(times))
        for scan in np.nonzero(keep)[0]:
            width = details.isolation[scan]
            p = parents[scan]
            rows.append({
                "channel": int(channel.index), "scan": int(scan),
                "cycle": int(cycle_of[scan]), "rt": rt4(times[scan]),
                "ms_level": level_of, "parent_mz": mz4(p),
                "isolation": ([mz4(p - width / 2), mz4(p + width / 2)]
                              if np.isfinite(width) and np.isfinite(p) else None),
                "ce": num(details.collision_energy[scan])
                if np.isfinite(details.collision_energy[scan]) else None,
                "tic": num(totals[scan]) if scan < len(totals) else None,
                "points": int(points[scan]) if points is not None else None,
            })
    if not count:
        rows.sort(key=lambda r: (r["rt"], r["channel"], r["scan"]))
    return ({"count": int(sum(r["scans"] for r in rows)), "channels": rows}
            if count else {"count": len(rows), "scans": rows}), index


def _source_of(text):
    if text in (None, "", "all"):
        return None
    return parse_source(text)


def _channels_for(smp, source) -> list:
    from .gating import SourceError, channels_of

    try:
        return channels_of(smp, source)
    except SourceError as exc:
        raise ContractError("bad_source", str(exc)) from exc


# --------------------------------------------------------------------------- #
# xic
# --------------------------------------------------------------------------- #
@dataclass
class PeakSummary:
    found: bool
    apex_rt: float | None = None
    apex_height: float | None = None
    area: float | None = None
    start_rt: float | None = None
    end_rt: float | None = None
    fwhm: float | None = None
    points: int = 0
    sn: float | None = None
    noise: float | None = None
    trace: tuple = field(default=(), repr=False)


def _fwhm(rt: np.ndarray, y: np.ndarray, apex: int) -> float | None:
    half = y[apex] / 2.0
    if half <= 0:
        return None
    left = apex
    while left > 0 and y[left] > half:
        left -= 1
    right = apex
    while right < y.size - 1 and y[right] > half:
        right += 1
    if y[left] > half or y[right] > half:
        return None                    # the trace ends above half height

    def cross(a, b):
        if y[a] == y[b]:
            return rt[a]
        return rt[a] + (half - y[a]) * (rt[b] - rt[a]) / (y[b] - y[a])

    return float(cross(right - 1, right) - cross(left, left + 1))


#: the summary's definitions, the same words MIL-X prints in its
#: `definitions` block, so the two tools give one number for one trace
BOUND_FRACTION = 0.05          # a bound is the first point at or below 5% of the apex
VALLEY_RISE = 0.10             # … or the valley before a rise of a tenth of the apex
DEFINITIONS = {
    "apex": "the tallest point of the (smoothed) trace",
    "bounds": ("from the apex outward to the first point at or below 5 % of "
               "the apex, or to the valley before a rise of a tenth of the apex"),
    "area": "trapezoid between the bounds, intensity × minutes, no baseline",
    "fwhm": "interpolated at half the apex height; null when the trace ends above it",
    "snr": ("apex height / noise; noise = milq.processing.estimate_noise over the "
            "trace in the window; null when the baseline cannot be measured"),
}


def _bound(y: np.ndarray, apex: int, step: int) -> int:
    """Walk from the apex one way until 5% of the apex, or a rise after a valley."""
    height = float(y[apex])
    valley, low = apex, height
    i = apex
    while 0 <= i + step < y.size:
        i += step
        value = float(y[i])
        if value <= BOUND_FRACTION * height:
            return i
        if value < low:
            low, valley = value, i
        elif value - low >= VALLEY_RISE * height:
            return valley
    return i


def summarise(rt: np.ndarray, y: np.ndarray, smooth: float = 0.0) -> PeakSummary:
    """
    One trace's peak, by the definitions in `DEFINITIONS` — the same ones
    MIL-X uses, so the two tools agree on an identical trace.

    It used to be `processing.detect_peaks`' valley integration: a height
    and an area above a baseline line, and the peak with the largest such
    height. On a jagged IDA survey trace that picked a tooth 0.08 min after
    the trace's maximum, and on a synthetic trace it gave 740,118 where the
    trace's own maximum is 778,604 (the cross-check of 2026-11-09). The
    application's quantitation still integrates with `detect_peaks`; this is
    the command line's summary of a trace, and it reports the trace.
    """
    from .processing import estimate_noise, gaussian_smooth

    rt = np.asarray(rt, dtype=float)
    y = np.asarray(y, dtype=float)
    if smooth and smooth > 0 and y.size:
        y = gaussian_smooth(y, float(smooth))
    if y.size == 0 or float(np.max(y)) <= 0:
        return PeakSummary(False, trace=(rt, y))
    noise = estimate_noise(y)
    apex = int(np.argmax(y))
    height = float(y[apex])
    lo = _bound(y, apex, -1)
    hi = _bound(y, apex, +1)
    area = float(np.trapezoid(y[lo:hi + 1], rt[lo:hi + 1])) if hi > lo else 0.0
    return PeakSummary(
        True, float(rt[apex]), height, area, float(rt[lo]), float(rt[hi]),
        _fwhm(rt, y, apex), int(hi - lo + 1),
        (height / noise) if noise else None, noise, (rt, y))


def _restricted(rt, y, window):
    if window is None:
        return rt, y
    keep = (rt >= window[0]) & (rt <= window[1])
    return rt[keep], y[keep]


def _trace(smp, mz, tol, unit, source, window):
    from .gating import xic as gated_xic

    lo, hi = _window(mz, tol, unit)
    trace = gated_xic(smp, lo, hi, source)
    return _restricted(trace.rt, trace.intensity, window)


def _versus(target: PeakSummary, reference: PeakSummary) -> dict:
    if not (target.found and reference.found):
        return {"pearson_r": None, "apex_delta_rt": None, "height_ratio": None}
    rt_r, y_r = reference.trace
    rt_t, y_t = target.trace
    span = (rt_r >= reference.start_rt) & (rt_r <= reference.end_rt)
    r = None
    if span.sum() >= 3 and rt_t.size >= 2:
        on_reference = np.interp(rt_r[span], rt_t, y_t, left=0.0, right=0.0)
        a, b = on_reference, y_r[span]
        if np.std(a) > 0 and np.std(b) > 0:
            r = float(np.corrcoef(a, b)[0, 1])
    return {"pearson_r": None if r is None else round(r, 4),
            "apex_delta_rt": rt4(target.apex_rt - reference.apex_rt),
            "height_ratio": (round(target.apex_height / reference.apex_height, 6)
                             if reference.apex_height else None)}


def _summary_row(mz, tol, unit, summary: PeakSummary) -> dict:
    return {
        "mz": mz4(mz), "tol": tol, "unit": unit, "found": summary.found,
        "apex_rt": rt4(summary.apex_rt) if summary.found else None,
        "apex_height": num(summary.apex_height),
        "area": num(summary.area),
        "start_rt": rt4(summary.start_rt) if summary.found else None,
        "end_rt": rt4(summary.end_rt) if summary.found else None,
        "fwhm": rt4(summary.fwhm) if summary.fwhm is not None else None,
        "points_across_peak": summary.points,
        "sn": None if summary.sn is None else round(summary.sn, 2),
    }


def xic(path: str, mz, tol: float = 0.01, unit: str = "Da", source=None,
        rt=None, smooth: float = 0.0, trace: bool = False, reference=None,
        sample=None, require: bool = False) -> tuple[dict, int]:
    masses = parse_masses(mz)
    if not masses:
        raise ContractError("bad_arguments", "give at least one m/z (--mz)")
    if str(unit).lower() not in ("da", "ppm"):
        raise ContractError("bad_arguments", f"unit is Da or ppm, not {unit!r}")
    unit = "ppm" if str(unit).lower() == "ppm" else "Da"
    src = parse_source(source)
    window = parse_range(rt)
    _reader, smp, index = _sample(path, sample)
    ref_summary = None
    ref_doc = None
    if reference:
        text = str(reference)
        ref_mz, _, ref_source = text.partition("@")
        ref_src = parse_source(ref_source or str(src))
        rrt, ry = _trace(smp, float(ref_mz), tol, unit, ref_src, window)
        ref_summary = summarise(rrt, ry, smooth)
        ref_doc = {"mz": mz4(float(ref_mz)), "source": str(ref_src),
                   **{k: v for k, v in _summary_row(float(ref_mz), tol, unit,
                                                    ref_summary).items()
                      if k not in ("mz", "tol", "unit")}}
    rows, traces = [], []
    for value in masses:
        trt, ty = _trace(smp, value, tol, unit, src, window)
        summary = summarise(trt, ty, smooth)
        row = _summary_row(value, tol, unit, summary)
        if ref_summary is not None:
            row["vs_reference"] = _versus(summary, ref_summary)
        rows.append(row)
        if trace:
            traces.append({"mz": mz4(value), "rt": [rt4(t) for t in trt],
                           "intensity": [num(v) for v in ty]})
    if require and not any(r["found"] for r in rows):
        raise ContractError("nothing_found", "no signal for any m/z", EXIT_NOTHING)
    doc = {"source": str(src), "rt_window": list(window) if window else None,
           "smooth": smooth, "noise_convention": NOISE_CONVENTION,
           "definitions": DEFINITIONS, "summary": rows}
    if ref_doc is not None:
        doc["reference"] = ref_doc
    if trace:
        doc["traces"] = traces
    return doc, index


# --------------------------------------------------------------------------- #
# spectrum
# --------------------------------------------------------------------------- #
def _accumulate(parts):
    from .gating import _accumulate as accumulate

    return accumulate(parts)


def _difference_sticks(mz, intensity, bg_mz, bg_y):
    """Sticks less background sticks: each background stick is taken off the
    nearest signal stick within gating.MERGE_DA; never below zero."""
    from .gating import MERGE_DA

    mz = np.asarray(mz, dtype=float)
    out = np.asarray(intensity, dtype=float).copy()
    if mz.size:
        for m, h in zip(np.asarray(bg_mz, dtype=float), np.asarray(bg_y, dtype=float)):
            j = int(np.argmin(np.abs(mz - m)))
            if abs(mz[j] - m) <= MERGE_DA:
                out[j] -= h
    keep = out > 0
    return mz[keep], out[keep]


def _difference(mz, intensity, bg_mz, bg_y):
    """Signal less background on the union of their axes, never below zero."""
    union = np.union1d(np.asarray(mz, dtype=float), np.asarray(bg_mz, dtype=float))
    signal = np.zeros(union.size)
    np.add.at(signal, np.searchsorted(union, mz), intensity)
    back = np.zeros(union.size)
    np.add.at(back, np.searchsorted(union, bg_mz), bg_y)
    return union, np.clip(signal - back, 0.0, None)


def spectrum(path: str, source=None, scan=None, rt=None, subtract=(),
             centroid: str = "local", top=None, min_rel: float = 0.01,
             msp: str | None = None, sample=None, name: str = "",
             require: bool = False) -> tuple[dict, int]:
    from .centroiding import vendor
    from .gating import SourceError
    from .gating import spectrum as gated
    from .processing import centroid_spectrum

    src = parse_source(source)
    window = parse_range(rt)
    if scan is None and window is None and src.kind != "channel":
        raise ContractError("bad_arguments", "give --scan N or --rt A:B")
    _reader, smp, index = _sample(path, sample)
    how_asked = str(centroid or "local").lower()
    try:
        got = gated(smp, src, window, None if scan is None else int(scan),
                    centroid_each=src.merges and how_asked in ("local", "vendor", "sciex"))
    except SourceError as exc:
        raise ContractError("bad_arguments", str(exc)) from exc
    mz, intensity = got.mz, got.intensity
    merged_sticks = src.merges and (how_asked != "none" or all(
        getattr(c.info, "centroided", False) for c in smp.channels if not c.info.is_ms1))
    notes = []
    windows = [parse_range(w) for w in (subtract or [])]
    if windows:
        # the background is the mean of its windows' averages, taken off on
        # the union of the two mass axes, at the masses each was measured
        background = [gated(smp, src, w, centroid_each=merged_sticks)
                      for w in windows]
        if merged_sticks:
            from .gating import merge_sticks

            bg_mz, bg_y = merge_sticks([(b.mz, b.intensity) for b in background])
            mz, intensity = _difference_sticks(mz, intensity, bg_mz, bg_y)
        else:
            bg_mz, bg_y = _accumulate([(b.mz, b.intensity) for b in background])
            mz, intensity = _difference(mz, intensity, bg_mz, bg_y)
        notes.append(f"background subtracted: mean of {len(windows)} window(s)")
    how = how_asked
    if merged_sticks:
        # already one stick per ion: each scan centroided (or stored as
        # centroids) and merged across scans within gating.MERGE_DA
        how = "merged" if how == "none" else "local"
        notes.append("scans merged across channels: sticks within 0.01 Da "
                     "are one ion, at the intensity-weighted m/z, mean intensity")
    elif how in ("vendor", "sciex"):
        sticks = None
        if not windows and src.kind in ("channel", "ms1") and got.scans:
            channel = next(c for c in smp.channels if c.index == got.scans[0].channel)
            if scan is not None:
                sticks = vendor(channel, scan=int(scan), force=True)
            elif window is not None:
                sticks = vendor(channel, rt_range=window, force=True)
        if sticks is not None and len(sticks[0]):
            mz, intensity, how = sticks[0], sticks[1], "vendor"
        else:
            notes.append("centroided locally: the vendor's peak finder cannot "
                         "see this spectrum (an mzML, a subtraction, scans "
                         "merged across channels)")
            mz, intensity = centroid_spectrum(mz, intensity)
            how = "local"
    elif how == "local":
        mz, intensity = centroid_spectrum(mz, intensity)
    elif how in ("none", "profile"):
        how = "none"
    else:
        raise ContractError("bad_arguments",
                            f"--centroid vendor|local|none, not {centroid!r}")
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    base = float(intensity.max()) if intensity.size else 0.0
    order = np.argsort(intensity)[::-1]
    keep = [i for i in order if base > 0 and intensity[i] >= float(min_rel) * base]
    if top:
        keep = keep[:int(top)]
    keep.sort(key=lambda i: mz[i])
    peaks = [{"mz": mz4(mz[i]), "intensity": num(intensity[i]),
              "relative": round(100.0 * float(intensity[i]) / base, 4)}
             for i in keep]
    if require and not peaks:
        raise ContractError("nothing_found", "the spectrum is empty", EXIT_NOTHING)
    parents = got.parents
    doc = {
        "source": str(src), "centroid": how,
        "scan": None if scan is None else int(scan),
        "rt_window": list(window) if window else None,
        "subtract": [list(w) for w in windows],
        "scans_used": [{"channel": s.channel, "scan": s.scan, "rt": rt4(s.rt),
                        "parent_mz": mz4(s.parent_mz)} for s in got.scans],
        "parent_mz": (mz4(float(np.median(parents)))
                      if parents.size and float(np.ptp(parents)) <= 0.05 else None),
        "base_peak": num(base),
        "notes": notes,
        "peaks": peaks,
    }
    if msp:
        doc["msp"] = _write_msp(msp, name or os.path.basename(path), peaks, doc)
    return doc, index


def _write_msp(path: str, name: str, peaks, doc) -> str:
    from .library import entry_from_spectrum, write_msp

    mz = np.array([p["mz"] for p in peaks], dtype=float)
    height = np.array([p["intensity"] for p in peaks], dtype=float)
    entry = entry_from_spectrum(name, mz, height, precursor=doc.get("parent_mz"),
                                comment=f"milq spectrum {doc['source']} "
                                        f"{doc['rt_window'] or doc['scan']}")
    path = os.path.abspath(os.path.expanduser(path))
    write_msp([entry], path)
    return path


# --------------------------------------------------------------------------- #
# isotopes
# --------------------------------------------------------------------------- #
NEUTRON = 1.0033548378


def isotopes(path: str, mz: float, charge: int = 1, rt=None, formula: str = "",
             tol: float = 0.01, n: int = 4, source=None, sample=None,
             adduct: str = "") -> tuple[dict, int]:
    from .gating import spectrum as gated
    from .precursor import in_spectrum

    window = parse_range(rt)
    if window is None:
        raise ContractError("bad_arguments", "give --rt A:B")
    z = abs(int(charge or 1))
    src = parse_source(source or "ms1")
    _reader, smp, index = _sample(path, sample)
    got = gated(smp, src, window)
    rows = []
    for k in range(int(n) + 1):
        expect_mz = float(mz) + k * NEUTRON / z
        # MIL-Q's one rule for a mass read off a spectrum: the tallest point
        # within the tolerance, refined across its profile peak
        # on a slice around it, so the refinement cannot walk to a neighbour
        # that is another ion altogether
        reach = max(3.0 * tol, 0.1)
        near = np.abs(got.mz - expect_mz) <= reach
        found = (in_spectrum(got.mz[near], got.intensity[near], expect_mz, tol)
                 if near.any() else None)
        if found is not None:
            measured, height = found
            rows.append({"peak": f"M+{k}" if k else "M", "expected_mz": mz6(expect_mz),
                         "mz": mz4(measured), "intensity": num(height),
                         "delta_mda": round((measured - expect_mz) * 1000, 2)})
        else:
            rows.append({"peak": f"M+{k}" if k else "M", "expected_mz": mz6(expect_mz),
                         "mz": None, "intensity": None, "delta_mda": None})
    mono = rows[0]["intensity"] or 0.0
    for row in rows:
        row["relative"] = (round(100.0 * row["intensity"] / mono, 3)
                           if mono and row["intensity"] is not None else None)
    spacing = [round((rows[k]["mz"] - rows[k - 1]["mz"]) * z * 1000 - NEUTRON * 1000, 2)
               for k in range(1, len(rows))
               if rows[k]["mz"] is not None and rows[k - 1]["mz"] is not None]
    doc = {"mz": mz4(mz), "charge": z, "rt_window": list(window),
           "source": str(src), "tolerance_da": tol, "envelope": rows,
           "spacing_error_mda": spacing}
    if formula:
        from .chemistry import adduct_from_name, isotope_pattern, parse_formula

        try:
            counts = parse_formula(formula)
            ion = adduct_from_name(adduct) if adduct else None
            pattern = isotope_pattern(counts, ion)
        except Exception as exc:
            raise ContractError("bad_arguments", f"formula {formula!r}: {exc}") from exc
        top = max(a for _m, a in pattern) if pattern else 1.0
        mono_theory = pattern[0][1] if pattern else 1.0
        for row in rows:
            k = 0 if row["peak"] == "M" else int(row["peak"][2:])
            near = [a for m, a in pattern
                    if abs(m - (pattern[0][0] + k * NEUTRON / z)) < 0.05]
            row["expected_relative"] = (round(100.0 * near[0] / mono_theory, 3)
                                        if near else 0.0)
        doc["formula"] = formula
        doc["theory_base"] = round(top, 6)
    return doc, index


# --------------------------------------------------------------------------- #
# batch-xic
# --------------------------------------------------------------------------- #
def batch_xic(paths, mz, tol: float = 0.01, unit: str = "Da", source=None,
              rt=None, rt_window: str | None = None, smooth: float = 0.0) -> dict:
    from .folder import check_files

    masses = parse_masses(mz)
    if not masses:
        raise ContractError("bad_arguments", "give at least one m/z (--mz)")
    window = parse_range(rt)
    centre = None
    if rt_window:
        text = str(rt_window).replace("+-", "±").replace("+/-", "±")
        c, _, w = text.partition("±")
        centre, width = float(c), float(w or 0.5)
        window = (centre - width, centre + width)
    src = parse_source(source)
    files = []
    for p in (paths or []):
        p = os.path.expanduser(str(p))
        if os.path.isdir(p):
            files.extend(os.path.join(p, n) for n in sorted(os.listdir(p))
                         if n.lower().endswith((".wiff", ".mzml")))
        else:
            files.append(p)
    report = check_files(files)
    openable = [os.path.realpath(p) for p in report.paths]
    skipped = [{"path": f.path, "kind": f.kind, "reason": f.finding}
               for f in report.findings if f.action in ("skip", "ignore")
               or os.path.realpath(f.path) not in openable]
    rows = []
    for path in openable:
        try:
            reader = open_file(path)
        except ContractError as exc:
            skipped.append({"path": path, "kind": exc.code, "reason": exc.message})
            continue
        for s_index in range(len(reader.sample_names)):
            smp = reader.sample(s_index)
            for value in masses:
                try:
                    trt, ty = _trace(smp, value, tol, unit, src, window)
                    summary = summarise(trt, ty, smooth)
                except Exception as exc:
                    skipped.append({"path": path, "sample": s_index,
                                    "kind": "unreadable", "reason": str(exc)})
                    break
                rows.append({"path": path, "sample": s_index,
                             "sample_name": str(smp.name),
                             "mz": mz4(value), "found": summary.found,
                             "apex_rt": rt4(summary.apex_rt) if summary.found else None,
                             "apex_height": num(summary.apex_height),
                             "area": num(summary.area),
                             "fwhm": rt4(summary.fwhm) if summary.fwhm else None})
    return {"source": str(src), "rt_window": list(window) if window else None,
            "rt_centre": centre, "files": len(openable), "rows": rows,
            "skipped": skipped}


# --------------------------------------------------------------------------- #
# convert
# --------------------------------------------------------------------------- #
def convert(path: str, out: str | None = None, centroid: str | None = None,
            sample=None) -> tuple[dict, int]:
    from .mzml import write_mzml

    _reader, smp, index = _sample(path, sample)
    target = out or os.path.splitext(os.path.realpath(path))[0] + (
        f".s{index}" if index else "") + ".mzML"
    target = os.path.abspath(os.path.expanduser(target))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    started = time.perf_counter()
    write_mzml(smp, target, centroid=centroid or None)
    return {"out": target, "centroid": centroid or "none",
            "seconds": round(time.perf_counter() - started, 1),
            "bytes": os.path.getsize(target)}, index
