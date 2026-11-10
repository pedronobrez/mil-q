"""The window as a script sees it: MILQ_UI_PROBE and its command file."""

import json
import os

import pytest
from PyQt6 import QtWidgets

from milq import mzml
from tests.test_ida import FakeSample as IdaSample
from tests.test_ida import FRAGMENT, _slot, FakeChannel, TIMES, SLOT_1, SLOT_2
from milq.wiff import ChannelInfo, KIND_MS1


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def ida_file(tmp_path):
    survey = FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                        100.0, 1500.0, len(TIMES), None,
                                        kind=KIND_MS1), survey=True)
    path = tmp_path / "ida.mzML"
    mzml.write_mzml(IdaSample([survey, _slot(1, SLOT_1), _slot(2, SLOT_2)]), path)
    return str(path)


@pytest.fixture
def shell(qapp, tmp_path):
    from milq.ui.shell import MainShell

    window = MainShell()
    yield window
    window.session.dirty = False
    window.close()
    window.deleteLater()
    qapp.processEvents()


def _send(probe, *commands):
    with open(probe.command_path, "w", encoding="utf-8") as handle:
        json.dump(list(commands), handle)
    probe.tick()
    with open(probe.path, encoding="utf-8") as handle:
        return json.load(handle)


def test_a_script_opens_selects_extracts_exports_and_saves(shell, ida_file, tmp_path):
    from milq.ui.probe import UiProbe

    probe = UiProbe(shell, str(tmp_path / "probe.json"))
    state = _send(probe, {"id": "1", "action": "open-file", "path": ida_file})
    assert state["last_command"]["ok"], state["last_command"]
    assert len(state["samples"]) == 1
    key = state["samples"][0]["key"]

    state = _send(probe, {"id": "2", "action": "select-channel", "sample": 0,
                          "channel": 1})
    assert state["last_command"]["ok"], state["last_command"]
    assert state["active"]["key"] == f"{key}|1"
    assert state["active"]["kind"] == "ida-slot"

    state = _send(probe, {"id": "3", "action": "add-xic", "mz": [FRAGMENT],
                          "tol": 0.01, "unit": "Da",
                          "source": "gated:627.8457:0.05"})
    assert state["last_command"]["ok"], state["last_command"]
    assert any("gated:627.8457" in x for x in state["xics"])

    state = _send(probe, {"id": "4", "action": "set-rt-range", "start": 0.2,
                          "end": 0.5})
    assert state["rt_range"][0] == pytest.approx(0.2, abs=0.05)

    picture = tmp_path / "chrom.png"
    state = _send(probe, {"id": "5", "action": "export-chart", "path": str(picture),
                          "chart": "chromatogram", "scale": 2, "theme": "dark"})
    assert state["last_command"]["ok"], state["last_command"]
    assert os.path.getsize(picture) > 1000

    project = tmp_path / "p.oqproj"
    state = _send(probe, {"id": "6", "action": "save-project", "path": str(project)})
    assert state["last_command"]["ok"] and project.exists()
    assert state["project"]["path"] == str(project)


def test_a_bad_command_is_answered_not_raised(shell, tmp_path):
    from milq.ui.probe import UiProbe

    probe = UiProbe(shell, str(tmp_path / "probe.json"))
    state = _send(probe, {"id": "x", "action": "launch-rockets"})
    assert state["last_command"] == {**state["last_command"], "id": "x",
                                     "ok": False}
    assert "unknown action" in state["last_command"]["message"]
    state = _send(probe, {"id": "y", "action": "select-workspace", "name": "method"})
    assert state["workspace"] == "method"
    assert not os.path.exists(probe.command_path)


def test_the_environment_opens_and_snapshots(shell, ida_file, tmp_path, monkeypatch, qapp):
    from milq.ui import probe as probe_module

    monkeypatch.setenv("MILQ_OPEN_RAW", ida_file)
    monkeypatch.setenv("MILQ_SNAPSHOT", str(tmp_path / "shot.png"))
    monkeypatch.setenv("MILQ_SNAPSHOT_DELAY", "0")
    monkeypatch.setenv("MILQ_UI_PROBE", str(tmp_path / "probe.json"))
    made = probe_module.start_from_environment(shell, qapp)
    assert made is not None and shell._scripted_start
    for _ in range(20):
        qapp.processEvents()
    assert len(shell.session.entries) == 1
    assert (tmp_path / "shot.png").exists()
