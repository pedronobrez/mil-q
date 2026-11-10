"""
The shared command-line contract (`docs/CLI-CONTRACT.md`, `mil-cli/1`) on a
synthetic IDA run: a survey and two dependent slots that isolate several
precursors each (`tests/test_ida.py`).
"""

import json
import os
import subprocess
import sys

import pytest

from milq import cli, contract, mzml
from milq.wiff import KIND_MS1, ChannelInfo
from tests.test_ida import (FRAGMENT, OTHER, SLOT_1, SLOT_2, TIMES, FakeChannel,
                            FakeSample, _slot)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def ida(tmp_path):
    survey = FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                        100.0, 1500.0, len(TIMES), None,
                                        kind=KIND_MS1), survey=True)
    path = tmp_path / "ida.mzML"
    mzml.write_mzml(FakeSample([survey, _slot(1, SLOT_1), _slot(2, SLOT_2)]), path)
    yield str(path)
    contract.close_all()


def call(*argv):
    """In process, as `milq` would print it."""
    from io import StringIO

    out, err = StringIO(), StringIO()
    stdout, stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        code = cli.main([str(a) for a in argv])
    finally:
        sys.stdout, sys.stderr = stdout, stderr
    return code, out.getvalue(), err.getvalue()


def doc(*argv):
    code, out, err = call(*argv)
    assert code == 0, err
    return json.loads(out)


def test_every_document_carries_the_envelope(ida):
    found = doc("info", ida)
    assert list(found)[:5] == ["schema", "tool", "version", "command", "input"]
    assert found["schema"] == "mil-cli/1" and found["tool"] == "milq"
    assert found["input"] == {"path": os.path.realpath(ida), "sample": 0}
    kinds = [c["kind"] for c in found["channels"]]
    assert kinds == ["ms1", "ida-slot", "ida-slot"]
    assert found["channels"][1]["precursor"] is None


def test_scans_list_each_scans_own_precursor(ida):
    found = doc("scans", ida, "--source", "gated:627.8457")
    assert found["count"] == 5
    assert [s["rt"] for s in found["scans"]] == [0.2, 0.3, 0.4, 0.5, 0.6]
    assert all(abs(s["parent_mz"] - 627.8457) < 0.05 for s in found["scans"])
    assert found["scans"][0]["isolation"] == [pytest.approx(627.3457, abs=1e-3),
                                              pytest.approx(628.3457, abs=1e-3)]
    counted = doc("scans", ida, "--count", "--ms-level", "2")
    assert counted["count"] == 9


def test_a_gated_xic_summary_and_a_reference(ida):
    found = doc("xic", ida, "--mz", FRAGMENT, OTHER, "--tol", "0.01",
                "--source", "gated:627.8457", "--reference", "627.8457@ms1")
    first, second = found["summary"]
    assert first["found"] and first["apex_rt"] == 0.6
    assert first["apex_height"] == pytest.approx(1500.0)
    assert not second["found"]                     # 214.118 is not 627.85's
    assert found["noise_convention"].startswith("milq.processing.estimate_noise")
    assert set(first["vs_reference"]) == {"pearson_r", "apex_delta_rt", "height_ratio"}


def test_a_trace_is_given_only_when_asked(ida):
    assert "traces" not in doc("xic", ida, "--mz", FRAGMENT, "--source", "ms2-all")
    traced = doc("xic", ida, "--mz", FRAGMENT, "--source", "ms2-all", "--trace")
    assert len(traced["traces"][0]["rt"]) == len(traced["traces"][0]["intensity"])


def test_a_gated_spectrum_lists_its_scans_and_writes_an_msp(ida, tmp_path):
    msp = tmp_path / "out.msp"
    found = doc("spectrum", ida, "--source", "gated:627.8457", "--rt", "0:1",
                "--centroid", "none", "--msp", msp)
    assert found["parent_mz"] == pytest.approx(627.8457, abs=1e-3)
    assert len(found["scans_used"]) == 5
    assert any(abs(p["mz"] - FRAGMENT) < 1e-3 for p in found["peaks"])
    assert all(abs(p["mz"] - OTHER) > 0.01 for p in found["peaks"])
    assert msp.exists() and "Name:" in msp.read_text()


def test_a_background_is_subtracted(ida):
    whole = doc("spectrum", ida, "--source", "channel:0", "--rt", "0.1:0.6",
                "--centroid", "none", "--min-rel", "0")
    bare = doc("spectrum", ida, "--source", "channel:0", "--rt", "0.1:0.6",
               "--subtract", "0.1:0.6", "--centroid", "none", "--min-rel", "0")
    assert whole["peaks"] and not bare["peaks"]    # itself, subtracted
    assert bare["subtract"] == [[0.1, 0.6]]


def test_tsv_is_the_main_table(ida):
    code, out, _ = call("xic", ida, "--mz", FRAGMENT, "--source", "ms2-all",
                        "--format", "tsv")
    header, row = out.strip().split("\n")
    assert header.split("\t")[:4] == ["mz", "tol", "unit", "found"]
    assert row.split("\t")[3] == "true"


def test_the_isotope_envelope(ida):
    found = doc("isotopes", ida, "--mz", "627.8457", "--rt", "0:1",
                "--formula", "C30H50N8O9")
    assert found["envelope"][0]["peak"] == "M"
    assert found["envelope"][0]["mz"] == pytest.approx(627.8457, abs=1e-3)
    assert "expected_relative" in found["envelope"][1]


def test_batch_xic_over_a_folder_reports_what_it_skipped(ida, tmp_path):
    (tmp_path / "stray.wiff").write_bytes(b"")            # no .wiff.scan
    found = doc("batch-xic", tmp_path, "--mz", FRAGMENT,
                "--source", "gated:627.8457", "--rt-window", "0.4±0.3")
    assert found["rows"][0]["found"] and found["rows"][0]["sample"] == 0
    assert any("stray.wiff" in s["path"] for s in found["skipped"])
    assert found["rt_window"] == [pytest.approx(0.1), pytest.approx(0.7)]


def test_convert_round_trips_every_parent(ida, tmp_path):
    out = tmp_path / "again.mzML"
    found = doc("convert", ida, "--out", out)
    assert found["out"] == str(out)
    before = doc("scans", ida, "--ms-level", "2")["scans"]
    after = doc("scans", out, "--ms-level", "2")["scans"]
    assert [s["parent_mz"] for s in before] == [s["parent_mz"] for s in after]


def test_errors_are_json_on_stderr_with_the_contracts_codes(ida, tmp_path):
    code, out, err = call("info", tmp_path / "missing.mzML")
    assert code == 3 and out == "" and json.loads(err)["error"] == "file_unreadable"
    lonely = tmp_path / "lonely.wiff"
    lonely.write_bytes(b"x")
    code, _out, err = call("info", lonely)
    assert code == 3 and json.loads(err)["error"] == "missing_companion"
    code, _out, err = call("xic", ida)
    assert code == 2 and json.loads(err)["error"] == "bad_arguments"
    code, _out, err = call("xic", ida, "--mz", "1", "--source", "gated:")
    assert code == 2 and json.loads(err)["error"] == "bad_source"
    code, out, _err = call("xic", ida, "--mz", "999.9", "--source", "ms1")
    assert code == 0 and not json.loads(out)["summary"][0]["found"]
    code, _out, err = call("xic", ida, "--mz", "999.9", "--require")
    assert code == 4 and json.loads(err)["error"] == "nothing_found"


def test_the_same_call_gives_the_same_bytes(ida):
    assert call("xic", ida, "--mz", FRAGMENT, "--source", "ms2-all")[1] == \
        call("xic", ida, "--mz", FRAGMENT, "--source", "ms2-all")[1]


def test_no_qt_on_the_command_line(ida):
    """A subprocess, so nothing the suite already imported counts."""
    script = ("import sys; from milq.cli import main; "
              f"code = main(['info', {ida!r}, '--quiet']); "
              "bad = [m for m in sys.modules if m.startswith(('PyQt', 'pyqtgraph'))]; "
              "sys.stderr.write(repr(bad)); sys.exit(code or (1 if bad else 0))")
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["command"] == "info"


def test_run_py_takes_a_subcommand(ida):
    done = subprocess.run([sys.executable, "run.py", "info", ida, "--format", "tsv"],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("index\tkind\t")


def test_the_sidecar_index_serves_the_second_open(ida, tmp_path):
    from milq import sidecar

    sidecar.configure(str(tmp_path / "index"))
    try:
        first = mzml.MzmlFile(ida)
        first.close()
        assert sidecar.load_headers(ida) is not None
        again = mzml.MzmlFile(ida)
        assert [h.rt for h in again.headers] == [h.rt for h in first.headers]
        again.close()
        os.utime(ida, None)                       # the file changed: a miss
        assert sidecar.load_headers(ida) is None or os.stat(ida).st_mtime_ns
    finally:
        sidecar.INDEX_DIR = None


def test_the_contract_document_is_the_attached_one():
    with open(os.path.join(ROOT, "docs", "CLI-CONTRACT.md"), "rb") as handle:
        text = handle.read()
    assert text.startswith(b"# MIL suite \xe2\x80\x94 shared command-line contract")
    assert b"`mil-cli/1`" in text


def test_the_api_gives_the_command_lines_bytes(ida):
    from milq import api

    made = api.xic(ida, [FRAGMENT], source="gated:627.8457")
    assert made.json() == call("xic", ida, "--mz", FRAGMENT,
                               "--source", "gated:627.8457")[1]
    assert api.info(ida)["channels"][1]["kind"] == "ida-slot"
    assert api.scans(ida, count=True)["count"] == 1 + 9 + 5
