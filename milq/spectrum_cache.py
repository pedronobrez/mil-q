"""
Averaged spectra kept on disk, so a file that has not changed is read once.

Averaging every scan of an infusion is the expensive half of the Infusions
tab: nine ZenoTOF acquisitions spend about twelve seconds inside
`Channel.spectrum_rt_range` alone, and pressing *Measure* twice on the same
nine files spent it twice. Nothing about that average depends on the session
— it is a function of the file, the channel, which scans the spray mask kept
and whether the unstable ones were asked for — so it is a function that can
be written down.

What is cached and what is not
------------------------------

The **raw** average, as the reader gives it: profile masses and intensities,
before any mass correction. A correction is an offset applied to an array
(`MassCorrection.apply`, one multiplication per point) and it changes with
the session's switch, so caching a corrected axis would key the file's own
measurement to a preference. Corrections are applied on read, by the caller
that already applies them.

The spray mask is stored beside the arrays as the sentence it writes
(`ScanMask.ranges`) — provenance for someone looking in the directory, not
something read back: the mask is measured again from the channel's own
chromatogram on every call, because it is what the key is made of.

Where the directory is
----------------------

Beside the project, `<project>.oqcache/`, when a project has been saved.
The averages belong to that batch of files: they are found where the batch
is found, they can be deleted with it, and a project copied to another
machine leaves its cache behind rather than carrying stale arrays. With no
project open there is nowhere that belongs to, so the operating system's own
cache directory is used — `~/Library/Caches/MIL-Q` on macOS,
`%LOCALAPPDATA%/MIL-Q/Cache` on Windows, `$XDG_CACHE_HOME/milq`
elsewhere — which is the directory the system is entitled to empty.
`MILQ_CACHE_DIR` overrides both (the test suite sets it, for the same
reason `MILQ_SETTINGS` exists), and so does the `cache/dir` setting,
which the window passes in.

What bounds it
--------------

`CACHE_MAX_MB`. Each entry is one `.npz` of two float64 arrays. Measured on
the nine real ZenoTOF bile-acid infusions: 39.1 MB between them, 4.3 MB
each, largest 5.1 MB — a quarter of a million profile points twice over,
which is what the averages of those runs are. The default of 512 MB
therefore holds about 120 infusions, four folders of thirty, and is small
beside the 47 MB of `.wiff.scan` those nine already occupy. Over the bound,
the least recently *used* entries go first: `get` stamps the file's
modification time, so the stamp is the last read and not the write. Pruning
happens after a write, since that is when the directory grows.

What invalidates an entry
-------------------------

The key. It digests the acquisition's path, its size and its modification
time — and the same two for the `.wiff.scan` beside a `.wiff`, which is
where the scans actually are — with the channel index, the range asked for,
the spray mask's own bytes and the `include_unstable` switch. A file
rewritten in place has a new mtime and therefore a new key, so a stale entry
is never read; it is only pruned, later, for being old. Measured on those
nine with one `.wiff.scan` touched: eight hits, one miss, one entry more on
disk and the run 0.7 s longer than a wholly warm one.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time

import numpy as np

#: how large the directory may grow before the least recently used entries
#: are dropped. Measured: the nine real ZenoTOF bile-acid infusions store as
#: 39.1 MB of `.npz`, so this is about a hundred and twenty of them.
CACHE_MAX_MB = 512.0

#: a directory to use instead of either default; set by the test suite, and
#: read before the setting so a suite cannot write into a real one
ENV_DIR = "MILQ_CACHE_DIR"

#: what a project's cache directory is called, beside the project file
PROJECT_SUFFIX = ".oqcache"

#: the extension every entry carries
ENTRY_SUFFIX = ".npz"

#: how the key is built, digested into the file name. Bumped when the shape
#: of what is stored changes, which retires every entry at once without
#: anything having to delete them.
FORMAT = 1


# --------------------------------------------------------------------------- #
# where
# --------------------------------------------------------------------------- #
def user_dir() -> str:
    """The operating system's cache directory for this application."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches/MIL-Q")
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MIL-Q", "Cache")
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "milq")


def cache_dir(project_path: str | None = None, override: str = "") -> str:
    """
    Where averaged spectra for this project go, and why there.

    `MILQ_CACHE_DIR` first, then `override` (the `cache/dir` setting),
    then `<project>.oqcache/` beside a saved project, then the user's cache
    directory. Nothing is created here: a directory is made when something
    is written into it.
    """
    forced = os.environ.get(ENV_DIR)
    if forced:
        return forced
    if override:
        return str(override)
    if project_path:
        stem = os.path.splitext(str(project_path))[0]
        return stem + PROJECT_SUFFIX
    return user_dir()


def describe_dir(directory: str, project_path: str | None = None) -> str:
    """One line saying where the cache is and why it is there."""
    if os.environ.get(ENV_DIR):
        return f"{directory} ({ENV_DIR})"
    if project_path and directory.endswith(PROJECT_SUFFIX):
        return f"{directory} (beside the project)"
    return f"{directory} (no project is open, so the system's cache)"


# --------------------------------------------------------------------------- #
# the key
# --------------------------------------------------------------------------- #
def _stat_of(path: str) -> tuple[int, int]:
    """A file's size and modification time, or zeros where it is not there."""
    try:
        info = os.stat(path)
    except OSError:
        return (0, 0)
    return (int(info.st_size), int(info.st_mtime_ns))


def file_stamp(path: str) -> tuple:
    """
    What says a file has not changed: its size and mtime, and its `.wiff.scan`
    companion's, where one sits beside it.

    The companion matters because it is where the scans are — a `.wiff` alone
    opens, gives its method and its chromatograms, and has no spectrum to
    average. A cache keyed on the `.wiff` alone would answer from a stale
    average after the scans had been replaced.
    """
    path = str(path or "")
    stamp = [os.path.abspath(path), *_stat_of(path)]
    companion = path + ".scan"
    if os.path.exists(companion):
        stamp += list(_stat_of(companion))
    return tuple(stamp)


def average_key(path: str, channel: int | None, *,
                whole_run: bool = True,
                rt_range: tuple[float, float] | None = None,
                mask=None, include_unstable: bool = False) -> str:
    """
    The digest one averaged spectrum is stored under.

    Everything that changes the arrays is in it and nothing else is: the
    file's identity and stamp, which channel, which stretch of the run, the
    spray mask's own bytes (so a mask that keeps other scans is another
    entry) and whether the unstable scans were asked for. No mass correction
    — see the module docstring.
    """
    parts: list = [FORMAT, file_stamp(path), channel,
                   bool(whole_run), bool(include_unstable)]
    if rt_range is not None:
        parts.append((round(float(rt_range[0]), 6),
                      round(float(rt_range[1]), 6)))
    else:
        parts.append(None)
    digest = hashlib.sha256(repr(tuple(parts)).encode("utf-8"))
    keep = getattr(mask, "keep", None)
    if keep is not None and getattr(keep, "size", 0):
        digest.update(np.asarray(keep, dtype=bool).tobytes())
    else:
        digest.update(b"no-mask")
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# the cache
# --------------------------------------------------------------------------- #
class AverageCache:
    """
    Averaged spectra on disk, one `.npz` per entry, bounded and least
    recently used first out.

    Every failure is a miss. A cache that raised because a disk was full, a
    directory was read-only or an entry had been truncated would turn a
    performance measure into a way of losing a measurement, so `get` returns
    None and `put` returns False and the caller reads the file as it always
    did. `errors` counts them, for a status line that wants to say the cache
    is not working.
    """

    def __init__(self, directory: str, max_mb: float = CACHE_MAX_MB):
        self.directory = str(directory)
        self.max_mb = float(max_mb)
        self.hits = 0
        self.misses = 0
        self.errors = 0
        #: the last error, in words, for a status line
        self.note = ""

    # -- reading ------------------------------------------------------------ #
    def path_for(self, key: str) -> str:
        return os.path.join(self.directory, f"{key}{ENTRY_SUFFIX}")

    def get(self, key: str):
        """
        The stored `(mz, intensity, ranges)`, or None.

        Reading stamps the entry's modification time, which is what the
        bound orders by: an entry read every day is the newest in the
        directory however long ago it was written.
        """
        path = self.path_for(key)
        try:
            with np.load(path, allow_pickle=False) as data:
                mz = np.asarray(data["mz"], dtype=float)
                intensity = np.asarray(data["intensity"], dtype=float)
                ranges = str(data["ranges"]) if "ranges" in data else ""
        except (OSError, ValueError, KeyError, EOFError):
            self.misses += 1
            return None
        try:
            now = time.time()
            os.utime(path, (now, now))
        except OSError:                     # a read-only cache still reads
            pass
        self.hits += 1
        return mz, intensity, ranges

    # -- writing ------------------------------------------------------------ #
    def put(self, key: str, mz, intensity, ranges: str = "") -> bool:
        """Store one average. False where it could not be written."""
        path = self.path_for(key)
        temporary = f"{path}.{os.getpid()}.part"
        try:
            os.makedirs(self.directory, exist_ok=True)
            with open(temporary, "wb") as handle:
                np.savez(handle,
                         mz=np.asarray(mz, dtype=float),
                         intensity=np.asarray(intensity, dtype=float),
                         ranges=np.array(str(ranges or "")))
            os.replace(temporary, path)
        except (OSError, ValueError) as exc:
            self.errors += 1
            self.note = f"{type(exc).__name__}: {exc}"
            try:
                os.unlink(temporary)
            except OSError:
                pass
            return False
        self.prune()
        return True

    # -- the bound ---------------------------------------------------------- #
    def entries(self) -> list[tuple[str, int, float]]:
        """Every entry as (path, bytes, last used), newest last."""
        found: list[tuple[str, int, float]] = []
        try:
            names = os.listdir(self.directory)
        except OSError:
            return found
        for name in names:
            if not name.endswith(ENTRY_SUFFIX):
                continue
            path = os.path.join(self.directory, name)
            try:
                info = os.stat(path)
            except OSError:
                continue
            found.append((path, int(info.st_size), float(info.st_mtime)))
        found.sort(key=lambda row: row[2])
        return found

    def size_bytes(self) -> int:
        return sum(size for _p, size, _t in self.entries())

    def prune(self) -> int:
        """
        Drop the least recently used entries until the directory fits.

        Returns how many were dropped. An entry that cannot be removed is
        counted as staying, so a directory nothing may delete from stops
        growing on the next write rather than looping.
        """
        limit = self.max_mb * 1024 * 1024
        found = self.entries()
        total = sum(size for _p, size, _t in found)
        dropped = 0
        for path, size, _when in found:
            if total <= limit:
                break
            try:
                os.unlink(path)
            except OSError:
                continue
            total -= size
            dropped += 1
        return dropped

    def clear(self) -> tuple[int, int]:
        """Empty the directory. Returns (entries removed, bytes freed)."""
        removed, freed = 0, 0
        for path, size, _when in self.entries():
            try:
                os.unlink(path)
            except OSError:
                continue
            removed += 1
            freed += size
        self.hits = self.misses = 0
        return removed, freed

    # -- what it did -------------------------------------------------------- #
    def summary(self) -> str:
        """Hits, misses and how much is on disk, for a status line."""
        megabytes = self.size_bytes() / (1024 * 1024)
        said = (f"{self.hits} from the cache, {self.misses} read from file; "
                f"{megabytes:.1f} MB in {self.directory}")
        if self.errors:
            said += f" · {self.errors} could not be written ({self.note})"
        return said


def for_project(project_path: str | None = None, override: str = "",
                max_mb: float = CACHE_MAX_MB) -> AverageCache:
    """The cache one project's averages belong in."""
    return AverageCache(cache_dir(project_path, override), max_mb=max_mb)
