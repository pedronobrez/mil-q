"""
Where the real data is, and how a test says it is not there.

None of these files is in the repository and none of them ever will be: they
are acquisitions belonging to other people, some of them unpublished. Two of
the five sets are named here because the repository already names them —
`milq/infusion.py` tabulates the bile-acid infusions by path and the
`260904_EICs_Isabela_*` runs sit in the working directory, ignored by git.
The rest are found by environment variable or by an untracked
`tests/real/data.local.json`, so that neither a folder name nor a sample name
belonging to somebody's unpublished method is written down here.

Every accessor either returns a path that exists or raises
`pytest.skip` **naming the path it looked for**, because a regression test
that quietly passes on missing data is worse than no test.
"""

from __future__ import annotations

import functools
import glob
import json
import os
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, "data.local.json")


@functools.lru_cache(maxsize=1)
def _local() -> dict:
    """The untracked map of dataset name to path, if the person wrote one."""
    try:
        with open(LOCAL, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


@functools.lru_cache(maxsize=1)
def _checkouts() -> tuple[str, ...]:
    """
    This checkout, and the main one if this is a worktree.

    A `git worktree` holds only what git tracks, and the `260904_EICs_*` files
    are ignored — so they are in the main checkout and not here. The common
    git directory is the main checkout's `.git`, which is how that is found
    without writing anyone's home directory into a test.
    """
    root = os.path.dirname(os.path.dirname(HERE))
    found = [root]
    try:
        common = subprocess.run(
            ["git", "-C", root, "rev-parse", "--path-format=absolute",
             "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return tuple(found)
    main = os.path.dirname(common)
    if main and main not in found:
        found.append(main)
    return tuple(found)


def _resolve(name: str, variable: str, defaults=()) -> str | None:
    """The first of the environment variable, the local map and the defaults."""
    candidates = [os.environ.get(variable), _local().get(name), *defaults]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _require(name: str, variable: str, what: str, defaults=()) -> str:
    path = _resolve(name, variable, defaults)
    if path is None:
        looked = [c for c in (os.environ.get(variable), _local().get(name),
                              *defaults) if c] or ["nothing configured"]
        pytest.skip(f"{what} is not here: set {variable} (or {LOCAL}); "
                    f"looked at {', '.join(looked)}")
    return path


# --------------------------------------------------------------------------- #
# the five sets
# --------------------------------------------------------------------------- #
def eics() -> list[str]:
    """
    The five `260904_EICs_Isabela_*.wiff` — TripleTOF 5600, 81 channels each.

    In the working directory, ignored by git; a worktree looks at the main
    checkout as well.
    """
    for root in (os.environ.get("MILQ_REAL_EICS"),
                 _local().get("eics"), *_checkouts()):
        if not root:
            continue
        files = sorted(glob.glob(os.path.join(root, "260904_EICs_Isabela_*.wiff")))
        if len(files) == 5:
            return files
    pytest.skip("the five 260904_EICs_Isabela_*.wiff are not here: put them in "
                f"the working directory ({', '.join(_checkouts())}) or set "
                "MILQ_REAL_EICS to the folder holding them")


def infusions() -> str:
    """The folder of nine ZenoTOF 7600 bile-acid infusions."""
    return _require("infusions", "MILQ_REAL_INFUSIONS",
                    "the bile-acid infusion folder",
                    ("/Volumes/NOBRE/Cyborg/Bileomics",))


def infusion_files() -> list[str]:
    """Those nine `.wiff`, in the order the folder gives them."""
    files = sorted(glob.glob(os.path.join(infusions(), "*.wiff")))
    if not files:
        pytest.skip(f"no .wiff in {infusions()}")
    return files


def batch() -> str:
    """The folder of the 26-injection sphingolipid batch (somebody's method)."""
    return _require("batch", "MILQ_REAL_BATCH",
                    "the 26-injection sphingolipid folder")


def batch_files() -> list[str]:
    files = sorted(glob.glob(os.path.join(batch(), "*.wiff")))
    if len(files) < 26:
        pytest.skip(f"{batch()} holds {len(files)} .wiff, not 26")
    return files


def project() -> str:
    """The `.oqproj` of that batch, reprocessed under the corrected method."""
    return _require("project", "MILQ_REAL_PROJECT",
                    "the sphingolipid project file")


def dia() -> str:
    """The folder of eight DIA lipidomics runs."""
    return _require("dia", "MILQ_REAL_DIA", "the DIA lipidomics folder")


def orbitrap() -> str:
    """
    The folder holding the Thermo Orbitrap mzML of MTBLS13066, if it is still
    anywhere.

    These were never anywhere permanent — downloaded into a scratch directory
    to answer one question — so the tests that want them skip themselves far
    more often than not. Point `MILQ_REAL_ORBITRAP` at whatever folder
    holds `180A_D_H_ms1.mzML` and `180A_D_H_1Dawin_0-02step_35NCE.mzML`.
    """
    return _require("orbitrap", "MILQ_REAL_ORBITRAP",
                    "the MTBLS13066 Orbitrap mzML folder")


def orbitrap_file(name: str) -> str:
    """One of those mzML by name, or a skip that says which was wanted."""
    path = os.path.join(orbitrap(), name)
    if not os.path.exists(path):
        pytest.skip(f"{path} is not there")
    return path
