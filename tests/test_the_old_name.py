"""
What OpenQuant left behind still works, and is never written again.

The rename to MIL-Q in 1.0.0 followed the rule the OpenPeakView rename set in
0.6.1: a person who set `OPENQUANT_REAL_BATCH` in a shell profile, whose
preferences remember a spectral library, or whose `~/.openquant` holds a .NET
runtime and a 45 MB index should not have to do anything about a change of
name. These assert the three places that promise it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq import legacy  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# -- the environment ---------------------------------------------------------- #
def test_an_old_variable_is_read_as_the_new_one():
    environ = {"OPENQUANT_REAL_BATCH": "/data/batch",
               "OPENQUANT_CACHE_DIR": "/tmp/cache"}
    adopted = legacy.adopt_environment(environ)
    assert environ["MILQ_REAL_BATCH"] == "/data/batch"
    assert environ["MILQ_CACHE_DIR"] == "/tmp/cache"
    assert sorted(adopted) == ["MILQ_CACHE_DIR", "MILQ_REAL_BATCH"]


def test_the_new_name_wins_where_both_are_set():
    """The one they chose today, not the one they chose last year."""
    environ = {"OPENQUANT_REAL_BATCH": "/old", "MILQ_REAL_BATCH": "/new"}
    assert legacy.adopt_environment(environ) == []
    assert environ["MILQ_REAL_BATCH"] == "/new"


def test_the_name_before_last_is_read_too():
    """`OPENPEAKVIEW_HOME` has pointed at the cache directory since 0.6.1."""
    environ = {"OPENPEAKVIEW_HOME": "/somewhere/else"}
    legacy.adopt_environment(environ)
    assert environ["MILQ_HOME"] == "/somewhere/else"


def test_an_empty_old_variable_is_not_a_value():
    environ = {"OPENQUANT_REAL_DIA": ""}
    assert legacy.adopt_environment(environ) == []
    assert "MILQ_REAL_DIA" not in environ


def test_the_package_adopts_them_when_it_is_imported():
    """Every route — window, command line, API, suite — imports the package."""
    import milq
    source = Path(milq.__file__).read_text(encoding="utf-8")
    assert "adopt_environment()" in source


# -- the cache directory ------------------------------------------------------ #
def test_the_home_directory_obeys_what_it_is_told(monkeypatch, tmp_path):
    monkeypatch.setenv("MILQ_HOME", str(tmp_path / "told"))
    assert legacy.home() == tmp_path / "told"


def test_a_machine_that_has_the_old_directory_keeps_it(monkeypatch, tmp_path):
    """
    It holds a .NET runtime and a 45 MB index. Moving either to satisfy a
    change of name is minutes of work and a download to redo if it fails.
    """
    monkeypatch.delenv("MILQ_HOME", raising=False)
    monkeypatch.delenv("OPENPEAKVIEW_HOME", raising=False)
    (tmp_path / ".openquant").mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert legacy.home() == tmp_path / ".openquant"


def test_a_machine_that_has_neither_gets_the_new_name(monkeypatch, tmp_path):
    monkeypatch.delenv("MILQ_HOME", raising=False)
    monkeypatch.delenv("OPENPEAKVIEW_HOME", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert legacy.home() == tmp_path / ".milq"


def test_the_new_directory_wins_once_it_exists(monkeypatch, tmp_path):
    monkeypatch.delenv("MILQ_HOME", raising=False)
    monkeypatch.delenv("OPENPEAKVIEW_HOME", raising=False)
    (tmp_path / ".openquant").mkdir()
    (tmp_path / ".milq").mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert legacy.home() == tmp_path / ".milq"


# -- the preferences ---------------------------------------------------------- #
def _ini(path) -> QtCore.QSettings:
    """
    An INI store, because the native one is a daemon with its own cache.

    Two `QSettings` on the same native key can disagree for a moment on
    macOS, so a test that wrote through one and read through another would
    be measuring `cfprefsd`. The copying is what is under test here.
    """
    return QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)


def test_the_old_preferences_are_copied_once(qapp, tmp_path):
    """
    Window geometry, the last folder opened, whether the prompt was
    dismissed: small things, all of them annoying to lose.
    """
    old, new = _ini(tmp_path / "old.ini"), _ini(tmp_path / "new.ini")
    old.setValue("shell/geometry", "something")
    old.setValue("cache/dir", "/tmp/somewhere")
    old.sync()

    assert legacy.inherit_settings(new, old) == 2
    assert new.value("cache/dir") == "/tmp/somewhere"

    # and never again: the store is no longer empty
    old.setValue("shell/geometry", "moved since")
    old.sync()
    assert legacy.inherit_settings(new, old) == 0
    assert new.value("shell/geometry") == "something"


def test_a_store_with_nothing_behind_it_copies_nothing(qapp, tmp_path):
    empty = _ini(tmp_path / "empty.ini")
    assert legacy.inherit_settings(_ini(tmp_path / "new.ini"), empty) == 0


def test_the_factory_is_what_inherits(qapp):
    source = Path(
        __import__("milq.ui.settings", fromlist=["settings"]).__file__
    ).read_text(encoding="utf-8")
    assert "inherit_settings(store)" in source
    # only the native store is offered it; the suite's INI file starts empty
    assert source.index("if path:") < source.index("inherit_settings(store)")
    assert 'QtCore.QSettings("MIL-Q", "MIL-Q")' in source
