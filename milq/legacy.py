"""
What the old name left behind, read once and never written.

OpenQuant became MIL-Q in 1.0.0. The rule is the one the OpenPeakView
rename set in 0.6.1 and it has not changed: **the old name goes on being
understood and is never written again**. A person who set
`OPENQUANT_REAL_BATCH` in a shell profile, or whose preferences remember
which spectral library was open, or whose `~/.openquant` holds a .NET
runtime and a 45 MB LIPID MAPS index, should not have to do anything.

Everything that knows the old name is here rather than spread through the
modules, so that retiring it later is deleting one file and three calls.
Nothing in here imports Qt or anything else the application does not
already need at its very first line: `bootstrap` calls it before .NET is
up and `app` before there is a window.
"""

from __future__ import annotations

import os
from pathlib import Path

#: the old prefix, and the new one. Every `OPENQUANT_X` is read as `MILQ_X`.
OLD_PREFIX = "OPENQUANT_"
NEW_PREFIX = "MILQ_"

#: one name that was not simply prefixed: the cache directory's override has
#: carried the name before last since 0.6.1, and this is where it stops
OLD_NAMES = {"OPENPEAKVIEW_HOME": "MILQ_HOME"}

#: where the .NET runtime, the shims and the LIPID MAPS index live
HOME_ENV = "MILQ_HOME"
NEW_HOME = ".milq"
OLD_HOME = ".openquant"

#: the organisation and application the preferences were stored under
PREVIOUS_NAME = "OpenQuant"


def adopt_environment(environ=None) -> list[str]:
    """
    Read every `OPENQUANT_*` as its `MILQ_*` twin, where that is not set.

    Returns the names it filled in, so that a caller can say so. An
    environment variable is something a person typed into a shell profile
    or a launch configuration months ago; changing what the program is
    called is not a reason to make them find it again. The new name always
    wins where both are set, because that is the one they chose today.
    """
    environ = os.environ if environ is None else environ
    adopted = []
    for old, new in _pairs(environ):
        if new in environ or not environ.get(old):
            continue
        environ[new] = environ[old]
        adopted.append(new)
    return adopted


def _pairs(environ):
    """Every (old name, new name) this version still answers to."""
    for old, new in OLD_NAMES.items():
        yield old, new
    for name in list(environ):
        if name.startswith(OLD_PREFIX):
            yield name, NEW_PREFIX + name[len(OLD_PREFIX):]


def home() -> Path:
    """
    The directory the runtime and the index live in.

    `MILQ_HOME` if it is set. Otherwise `~/.milq` — unless this machine
    already has a `~/.openquant`, in which case that one is used as it
    stands. It holds a .NET runtime and a 45 MB index, and moving or
    copying either to satisfy a change of name would be minutes of work
    and a download to redo if it went wrong, for nothing anybody can see.
    A machine that has never run the old program gets the new name.
    """
    told = os.environ.get(HOME_ENV) or os.environ.get("OPENPEAKVIEW_HOME")
    if told:
        return Path(told)
    new, old = Path.home() / NEW_HOME, Path.home() / OLD_HOME
    if not new.exists() and old.is_dir():
        return old
    return new


def inherit_settings(current, previous=None) -> int:
    """
    Copy the old preferences into the new store, once, if it is empty.

    Window geometry, the last folder a file was opened from, whether the
    start prompt was dismissed: small things, and all of them annoying to
    lose. Returns how many keys were copied — zero on every start after the
    first, because the new store is no longer empty.

    `previous` is the old store, and is opened from the old name when it is
    not given. It is a parameter because the native store on macOS is a
    daemon with a cache of its own: two `QSettings` on the same key can
    disagree for a moment, so a test that wrote through one and read through
    another would be measuring `cfprefsd` rather than this. **Which store
    inherits is the caller's decision** — `ui.settings` only offers this to
    the native one, since the suite's INI file is meant to start empty.
    """
    from PyQt6 import QtCore

    if current.allKeys():
        return 0
    old = previous if previous is not None else QtCore.QSettings(
        PREVIOUS_NAME, PREVIOUS_NAME)
    keys = old.allKeys()
    for key in keys:
        current.setValue(key, old.value(key))
    if keys:
        current.sync()
    return len(keys)
