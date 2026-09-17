"""
Settings go where the suite says, never into the person's preferences.

`QSettings("MIL-Q", "MIL-Q")` is the native store, which on macOS
ignores `setPath`; a test of the library panel once left a pytest
temporary path as the remembered spectral library. `ui.settings.settings`
is the one constructor, and `MILQ_SETTINGS` — set by conftest before
any widget exists — sends it to an INI file instead.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore  # noqa: E402

from milq.ui.settings import ENV_FILE, settings  # noqa: E402


def test_the_suite_writes_to_its_own_ini_file():
    target = os.environ[ENV_FILE]
    assert target.endswith("MIL-Q.ini")
    store = settings()
    assert store.format() == QtCore.QSettings.Format.IniFormat
    # Qt writes the path with forward slashes whatever the platform
    assert os.path.normpath(store.fileName()) == os.path.normpath(target)
    store.setValue("test/marker", 1)
    store.sync()
    assert os.path.exists(target)


def test_without_the_variable_it_is_the_native_store(monkeypatch):
    monkeypatch.delenv(ENV_FILE)
    store = settings()
    assert store.format() == QtCore.QSettings.Format.NativeFormat
    assert store.organizationName() == "MIL-Q"
    assert store.applicationName() == "MIL-Q"
