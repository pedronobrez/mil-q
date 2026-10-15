"""A project carried to another computer finds its raw files again."""

import json
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq.audit import RAW_FILES_RELOCATED
from milq.quantify import PeakResult, ResultsSet
from milq.session import (
    Session, locate_raw_files, plan_relocation, raw_name,
)
from tests.test_api import _write_run


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def _project_elsewhere(tmp_path, qapp):
    """A project saved against `first/run.mzML`, whose raw file then moves
    to `second/` — what the second computer sees."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    raw = _write_run(first / "run.mzML")
    source = Session()
    source.open_file(raw)
    key = source.entries[0].key
    source.results = ResultsSet.from_list(
        [PeakResult(sample_key=key, sample_name="run", component="Cer",
                    area=123.0).__dict__])
    source.view = {"pins": [{"sample_key": key, "channel": 0}]}
    project = str(tmp_path / "projects" / "p.oqproj")
    os.makedirs(os.path.dirname(project))
    source.save_project(project)
    source.close_all()
    shutil.move(raw, second / "run.mzML")
    return project, raw, str(second / "run.mzML")


def test_a_windows_path_is_named_on_any_system():
    assert raw_name(r"C:\Users\lab\data\run01.wiff") == "run01.wiff"
    assert raw_name("/Users/lab/data/run01.wiff") == "run01.wiff"


def test_a_wiff_counts_only_with_its_scan(tmp_path):
    (tmp_path / "a.wiff").write_bytes(b"")
    assert locate_raw_files(["/old/a.wiff"], str(tmp_path)) == {}
    (tmp_path / "a.wiff.scan").write_bytes(b"")
    assert locate_raw_files(["/old/a.wiff"], str(tmp_path)) == {
        "/old/a.wiff": str(tmp_path / "a.wiff")}


def test_a_subfolder_is_searched_but_two_copies_are_not_guessed(tmp_path):
    (tmp_path / "day1").mkdir()
    (tmp_path / "day1" / "b.mzML").write_bytes(b"")
    assert locate_raw_files([r"D:\x\b.mzML"], str(tmp_path)) == {
        r"D:\x\b.mzML": str(tmp_path / "day1" / "b.mzML")}
    (tmp_path / "day2").mkdir()
    (tmp_path / "day2" / "b.mzML").write_bytes(b"")
    assert locate_raw_files(["/x/b.mzML"], str(tmp_path)) == {}


def test_relocating_keeps_results_and_pins_attached(tmp_path, qapp):
    project, old, new = _project_elsewhere(tmp_path, qapp)
    relocate, missing = plan_relocation(project)
    assert missing == [old] and relocate == {}

    session = Session()
    assert session.load_project(project, {old: new}) == []
    entry = session.entries[0]
    assert entry.path == new and entry.sample is not None
    assert session.results.get(entry.key, "Cer").area == 123.0
    assert session.view["pins"][0]["sample_key"] == entry.key
    # the trail says what was, and the new place is waiting to be saved
    moved = session.audit.of(RAW_FILES_RELOCATED)
    assert [(e.before, e.after) for e in moved] == [(old, new)]
    assert session.dirty
    session.save_project(project)
    with open(project, encoding="utf-8") as handle:
        assert json.load(handle)["samples"][0]["path"] == new
    session.close_all()


def test_files_beside_the_project_are_found_without_asking(tmp_path, qapp):
    project, old, new = _project_elsewhere(tmp_path, qapp)
    beside = os.path.join(os.path.dirname(project), "raw", "run.mzML")
    os.makedirs(os.path.dirname(beside))
    shutil.move(new, beside)
    assert plan_relocation(project) == ({old: beside}, [])
    session = Session()
    assert session.load_project(project) == []
    assert session.entries[0].path == beside
    session.close_all()


def test_the_window_asks_for_the_folder(tmp_path, qapp, monkeypatch):
    from milq.ui.shell import MainShell

    project, old, new = _project_elsewhere(tmp_path, qapp)
    shell = MainShell()
    asked = []

    def answer(missing, note=""):
        asked.append((list(missing), note))
        return shell.LOCATE if len(asked) < 3 else shell.CONTINUE

    folders = iter([str(tmp_path / "first"), os.path.dirname(new)])
    monkeypatch.setattr(shell, "ask_about_missing_files", answer)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: next(folders)))
    assert shell.load_project_file(project)
    # the first folder held nothing and said so; the second held the file
    assert len(asked) == 2 and "None of them" in asked[1][1]
    assert shell.session.entries[0].path == new
    assert shell.session.entries[0].sample is not None
    shell.session.close_all()
    shell.session._mark_clean()
    shell.close()


def test_cancelling_opens_nothing(tmp_path, qapp, monkeypatch):
    from milq.ui.shell import MainShell

    project, _, _ = _project_elsewhere(tmp_path, qapp)
    shell = MainShell()
    monkeypatch.setattr(shell, "ask_about_missing_files",
                        lambda missing, note="": shell.CANCEL)
    assert not shell.load_project_file(project)
    assert shell.session.entries == []
    shell.close()
