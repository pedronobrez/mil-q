"""
What the command line keeps beside a file so the next call on it is cheap.

Two things cost on every call and never change while the file does not:
an mzML's spectrum headers (the XML parse that is the whole of an open),
and the number of points in each scan of a `.wiff` (one vendor call per
scan). Both are written to an index directory keyed on the file's real
path, size and modification time — plus the companion `.wiff.scan`'s — so
an edited or replaced file is never answered from a stale entry. Every
failure to read or write an entry is a miss, never an error.

The directory is `--cache DIR` on the command line, else `MILQ_INDEX_DIR`,
else `index/` under the application's cache (`~/Library/Caches/MIL-Q` on
macOS, `$XDG_CACHE_HOME/milq` on Linux). The window does not use it unless
the variable is set.
"""

from __future__ import annotations

import hashlib
import os
import pickle

import numpy as np

#: bumped whenever what is stored changes shape
VERSION = 1
ENV = "MILQ_INDEX_DIR"

#: set by the command line; None means "the variable or nothing"
INDEX_DIR: str | None = None


def default_dir() -> str:
    from .spectrum_cache import cache_dir

    return os.path.join(cache_dir(None), "index")


def configure(directory: str | None) -> str:
    """Use `directory` (or the default) from now on, and return it."""
    global INDEX_DIR
    INDEX_DIR = os.path.abspath(os.path.expanduser(directory or default_dir()))
    return INDEX_DIR


def _where() -> str | None:
    return INDEX_DIR or (os.environ.get(ENV) or None)


def identity(path: str, *extra) -> str | None:
    """A key that changes whenever the file (or its `.wiff.scan`) does."""
    try:
        real = os.path.realpath(path)
        parts = [real, str(os.path.getsize(real)), str(os.stat(real).st_mtime_ns)]
        if real.lower().endswith(".wiff") and os.path.exists(real + ".scan"):
            scan = os.stat(real + ".scan")
            parts += [str(scan.st_size), str(scan.st_mtime_ns)]
    except OSError:
        return None
    parts += [str(VERSION)] + [str(e) for e in extra]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _file(key: str, suffix: str) -> str | None:
    where = _where()
    if not where or key is None:
        return None
    return os.path.join(where, key[:2], key + suffix)


def _write(target: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = f"{target}.{os.getpid()}.tmp"
    with open(temporary, "wb") as handle:
        handle.write(payload)
    os.replace(temporary, target)


def load_headers(path: str):
    target = _file(identity(path, "headers"), ".pkl")
    if target is None or not os.path.exists(target):
        return None
    try:
        with open(target, "rb") as handle:
            return pickle.load(handle)
    except Exception:
        return None


def save_headers(path: str, headers) -> None:
    target = _file(identity(path, "headers"), ".pkl")
    if target is None:
        return
    try:
        _write(target, pickle.dumps(headers, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:
        pass


def points(channel, path: str, sample_index: int, cache: str | None = None) -> np.ndarray:
    """`channel.scan_points()`, kept in the index for the next call."""
    if cache:
        configure(cache)
    key = identity(path, "points", sample_index, getattr(channel, "index", 0))
    target = _file(key, ".npy")
    if target is not None and os.path.exists(target):
        try:
            found = np.load(target)
            if found.size == int(channel.info.n_scans) or found.size == len(channel.rt):
                return found
        except Exception:
            pass
    found = np.asarray(channel.scan_points(), dtype=np.int64)
    if target is not None:
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target + ".tmp", "wb") as handle:
                np.save(handle, found)
            os.replace(target + ".tmp", target)
        except Exception:
            pass
    return found
