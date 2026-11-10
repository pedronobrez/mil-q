"""
Who turns a profile spectrum into centroids: the instrument's software, or
this program.

For a SCIEX `.wiff` the instrument's software can centroid: Clearcore2's
spectral peak finder (`MSExperiment.GetPeakArray`), the one Analyst and
MIL-X use, fits each profile peak and reports its apex. MIL-Q's ground rule
would make that the default, and 1.1 was first written that way; then it
was measured, and on a sphingolipid batch the vendor's masses reproduced
worse between injections (median 10.5 ppm against 7.0) and an own record
was found first 9 times in 20 against 16. A rule that loses on the data it
is meant to serve is not kept on principle, so **this program's
centroider is the default** and the vendor's is a choice:

    local   this program's `processing.centroid_spectrum` (the default,
            as before 1.1)
    sciex   the vendor's peak finder, for labels, Explain, the library and
            a record wherever the spectrum on screen is the reader's own
    0       the vendor off, exactly as `local` — the value MIL-X uses for
            the same switch, accepted so it means one thing in both

The command line's `--centroid vendor` asks the vendor for that call
whatever the variable says.

An mzML has no vendor peak finder and is centroided locally whatever the
variable says. Quantitation reads extracted ion chromatograms and is not
touched by any of this.

What the change measured (see `CLAUDE.md`): on a TripleTOF 5600 survey scan
the vendor kept 4,561 peaks where the local finder kept 13,764, at the same
height (median ratio 1.00 over the 200 tallest — MIL-X measured 1.27 on a
ZenoTOF 7600, so the instrument decides).
"""

from __future__ import annotations

import os

import numpy as np

ENV = "MILQ_WIFF_CENTROID"
SCIEX = "sciex"
LOCAL = "local"
PROFILE = "0"

#: how far a locally found peak may be from the vendor's apex and still be
#: called the same peak when a label is moved onto it
SNAP_DA = 0.02


def mode() -> str:
    """The mode in force: `sciex`, `local` or `0`."""
    value = (os.environ.get(ENV) or LOCAL).strip().lower()
    if value in ("0", "off", "false", "profile", "none"):
        return PROFILE
    if value in ("sciex", "vendor"):
        return SCIEX
    return LOCAL


def describe(how: str) -> str:
    return {SCIEX: "SCIEX peak finder", LOCAL: "local maxima",
            PROFILE: "profile"}.get(how, how)


def vendor(channel, scan: int | None = None, rt_range=None, force: bool = False):
    """
    The vendor's centroids where the mode asks for them (or `force`, an
    explicit request) and the reader has them.
    """
    if channel is None or (not force and mode() != SCIEX):
        return None
    reader = getattr(channel, "vendor_centroids", None)
    if reader is None:
        return None
    try:
        if scan is not None:
            return reader(scan=int(scan))
        if rt_range is not None:
            lo, hi = rt_range
            return reader(rt_start=float(lo), rt_end=float(hi))
    except Exception:
        return None
    return None


def centroids(channel, mz, intensity, scan: int | None = None, rt_range=None):
    """
    (mz, intensity, how) for one spectrum of a channel: the vendor's where
    the mode and the reader allow, the local centroider otherwise.
    """
    found = vendor(channel, scan, rt_range)
    if found is not None and len(found[0]):
        return found[0], found[1], SCIEX
    from .processing import centroid_spectrum

    cm, ci = centroid_spectrum(np.asarray(mz, dtype=float),
                               np.asarray(intensity, dtype=float))
    return cm, ci, LOCAL


def snap(masses, sticks, tolerance: float = SNAP_DA):
    """
    Each mass moved onto the nearest stick within `tolerance`, or kept.

    A label is placed where the local peak finder found a peak and named
    with the vendor's apex for it, so which peaks carry a label is decided
    as before and only the number written changes.
    """
    masses = np.asarray(masses, dtype=float)
    if sticks is None or masses.size == 0:
        return masses
    axis = np.asarray(sticks[0], dtype=float)
    if axis.size == 0:
        return masses
    where = np.clip(np.searchsorted(axis, masses), 1, axis.size - 1)
    left, right = axis[where - 1], axis[where]
    nearest = np.where(np.abs(masses - left) <= np.abs(right - masses), left, right)
    return np.where(np.abs(nearest - masses) <= tolerance, nearest, masses)
