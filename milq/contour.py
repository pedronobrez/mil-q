"""
The run as a surface: retention time across, m/z up, intensity as colour.

A chromatogram is the surface summed along one axis and a spectrum is it
summed along the other, so everything here is already visible somewhere else
in the program — one slice at a time. What the contour adds is adjacency: an
interference half a dalton from a target, a second species eluting under the
same peak, a contaminant ridge running the whole length of the run. Those are
facts about the neighbourhood of a signal, and a view that shows one slice
cannot show a neighbourhood.

Building it means reading every scan in the range, which is the expensive part
and why this takes a progress callback and can be stopped. Nothing here
touches Qt: the grid is arithmetic and is tested as arithmetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

#: how finely m/z is divided. About a bin per screen pixel across a wide
#: range: finer than that and the picture is the same, only slower.
DEFAULT_BINS = 1400

#: the most rows drawn. A long run has more scans than a screen has pixels,
#: and the ones over the limit are averaged into their neighbours rather than
#: dropped — skipping scans is how a one-scan peak disappears from a picture
#: that is supposed to show what is there.
DEFAULT_ROWS = 900

MIN_BINS = 32


@dataclass
class Contour:
    """A retention time by m/z grid of intensities."""

    intensity: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    #: the centre time of each row, in minutes
    rt: np.ndarray = field(default_factory=lambda: np.zeros(0))
    #: bins + 1 edges, so a value can be placed without guessing the width
    mz_edges: np.ndarray = field(default_factory=lambda: np.zeros(0))
    scans: int = 0
    #: how many scans were averaged into one row; 1 when none had to be
    grouped: int = 1
    note: str = ""

    @property
    def is_empty(self) -> bool:
        return self.intensity.size == 0

    @property
    def mz_centres(self) -> np.ndarray:
        if self.mz_edges.size < 2:
            return np.zeros(0)
        return (self.mz_edges[:-1] + self.mz_edges[1:]) / 2.0

    @property
    def mz_range(self) -> tuple[float, float]:
        if self.mz_edges.size < 2:
            return (0.0, 0.0)
        return (float(self.mz_edges[0]), float(self.mz_edges[-1]))

    @property
    def rt_range(self) -> tuple[float, float]:
        if self.rt.size == 0:
            return (0.0, 0.0)
        return (float(self.rt[0]), float(self.rt[-1]))

    @property
    def rect(self) -> tuple[float, float, float, float]:
        """Left, bottom, width, height — where the image sits in the plot."""
        rt_lo, rt_hi = self.rt_range
        mz_lo, mz_hi = self.mz_range
        return (rt_lo, mz_lo, max(rt_hi - rt_lo, 1e-9), max(mz_hi - mz_lo, 1e-9))

    def at(self, rt: float, mz: float) -> float | None:
        """The intensity of the cell a point falls in, or None if outside."""
        if self.is_empty:
            return None
        mz_lo, mz_hi = self.mz_range
        if not (mz_lo <= mz <= mz_hi) or self.rt.size == 0:
            return None
        # `side="right"` because that is where numpy's histogram puts a value
        # sitting exactly on an edge; searching left reads the cell next door
        column = int(np.clip(np.searchsorted(self.mz_edges, mz, side="right") - 1,
                             0, self.intensity.shape[1] - 1))
        row = int(np.argmin(np.abs(self.rt - rt)))
        return float(self.intensity[row, column])

    def slice_rt(self, mz_lo: float, mz_hi: float) -> tuple[np.ndarray, np.ndarray]:
        """
        The chromatogram of an m/z band: the surface summed upwards.

        This is a picture of the grid, not a substitute for `xic_range` — the
        band is quantised to whole bins, and quantitation should come from the
        reader.
        """
        if self.is_empty:
            return np.zeros(0), np.zeros(0)
        lo, hi = sorted((float(mz_lo), float(mz_hi)))
        columns = np.nonzero((self.mz_centres >= lo) & (self.mz_centres <= hi))[0]
        if columns.size == 0:
            return self.rt, np.zeros(self.rt.size)
        return self.rt, self.intensity[:, columns].sum(axis=1)

    def slice_mz(self, rt_lo: float, rt_hi: float) -> tuple[np.ndarray, np.ndarray]:
        """The averaged spectrum of a time band: the surface summed across."""
        if self.is_empty:
            return np.zeros(0), np.zeros(0)
        lo, hi = sorted((float(rt_lo), float(rt_hi)))
        rows = np.nonzero((self.rt >= lo) & (self.rt <= hi))[0]
        if rows.size == 0:
            return self.mz_centres, np.zeros(self.mz_centres.size)
        return self.mz_centres, self.intensity[rows, :].mean(axis=0)


def build_contour(channel, rt_range: tuple[float, float] | None = None,
                  mz_range: tuple[float, float] | None = None,
                  bins: int = DEFAULT_BINS, max_rows: int = DEFAULT_ROWS,
                  progress=None) -> Contour:
    """
    Read a channel's scans into a retention time by m/z grid.

    `progress(done, total)` is called as the scans are read and stops the
    build by returning False; what has been read so far comes back, marked in
    the note, because a partial surface of the first half of a run is still
    worth looking at.

    Zeros are deliberately not restored. `Channel.spectrum` can put back the
    zero-intensity points SCIEX strips out, which is what makes a profile
    spectrum draw correctly — but a histogram of intensities is unchanged by
    adding points of intensity zero, so here it would triple the work to
    produce the same grid.
    """
    times = np.asarray(getattr(channel, "rt", np.zeros(0)), dtype=float)
    if times.size == 0:
        return Contour(note="the channel has no scans")

    first, last = 0, times.size - 1
    if rt_range is not None:
        lo, hi = sorted((float(rt_range[0]), float(rt_range[1])))
        inside = np.nonzero((times >= lo) & (times <= hi))[0]
        if inside.size == 0:
            return Contour(note=f"no scans between {lo:.2f} and {hi:.2f} min")
        first, last = int(inside[0]), int(inside[-1])

    if mz_range is not None:
        mz_lo, mz_hi = sorted((float(mz_range[0]), float(mz_range[1])))
    else:
        mz_lo = float(getattr(channel.info, "start_mass", 0.0) or 0.0)
        mz_hi = float(getattr(channel.info, "end_mass", 0.0) or 0.0)
    if not (math.isfinite(mz_lo) and math.isfinite(mz_hi)) or mz_hi <= mz_lo:
        return Contour(note="the channel does not declare a mass range")

    bins = max(int(bins), MIN_BINS)
    edges = np.linspace(mz_lo, mz_hi, bins + 1)

    scans = list(range(first, last + 1))
    group = max(1, math.ceil(len(scans) / max(int(max_rows), 1)))
    rows = math.ceil(len(scans) / group)
    grid = np.zeros((rows, bins), dtype=float)
    counts = np.zeros(rows, dtype=float)
    row_time = np.zeros(rows, dtype=float)

    stopped = False
    for number, scan in enumerate(scans):
        row = number // group
        try:
            mz, intensity = channel.spectrum(scan, add_zeros=False)
        except Exception:                 # one unreadable scan is not a failure
            mz = intensity = np.zeros(0)
        if mz.size and intensity.size:
            counted, _ = np.histogram(np.asarray(mz, dtype=float), bins=edges,
                                      weights=np.asarray(intensity, dtype=float))
            grid[row] += counted
        counts[row] += 1.0
        row_time[row] += float(times[scan])
        if progress is not None and progress(number + 1, len(scans)) is False:
            stopped = True
            break

    read = int(counts.sum())
    keep = int(np.count_nonzero(counts))
    grid, counts, row_time = grid[:keep], counts[:keep], row_time[:keep]
    # the mean, not the sum: the last group is usually short, and a row that
    # is dimmer only because fewer scans landed in it is a lie about the data
    safe = np.where(counts > 0, counts, 1.0)
    grid /= safe[:, None]
    row_time /= safe

    note = ""
    if stopped:
        note = f"stopped after {read} of {len(scans)} scans"
    elif group > 1:
        note = f"{group} scans averaged into each row"
    return Contour(intensity=grid, rt=row_time, mz_edges=edges, scans=read,
                   grouped=group, note=note)
