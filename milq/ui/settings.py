"""
The one place a settings object is made.

`QSettings("MIL-Q", "MIL-Q")` is the native store — a plist on
macOS, the registry on Windows — and the native store on macOS ignores
`setPath`, so a test suite that constructs one writes into the person's
real preferences: a pytest temporary path turned up as the remembered
spectral library, and a closed shell saved its layout over the real one.
`MILQ_SETTINGS`, set by the suite before any widget exists, points
every settings object at an INI file instead; it is inherited by a
subprocess, which `setDefaultFormat` would not have been — and that call
applies only to the no-argument constructor in any case.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore

from ..legacy import inherit_settings

#: an INI file to use instead of the native store; set by the test suite
ENV_FILE = "MILQ_SETTINGS"


def settings() -> QtCore.QSettings:
    path = os.environ.get(ENV_FILE)
    if path:
        return QtCore.QSettings(path, QtCore.QSettings.Format.IniFormat)
    store = QtCore.QSettings("MIL-Q", "MIL-Q")
    # the first MIL-Q ever started on this machine reads what OpenQuant
    # remembered and writes it here; every start after that finds a store
    # with keys in it and copies nothing. See `milq.legacy`.
    inherit_settings(store)
    return store
