"""
What the MIL-Q × MIL-X cross-check of 2026-11-09 found on the MIL-Q side
(issues pedronobrez/mil-q #1–#6), held fixed.
"""

import json

import numpy as np
import pytest

from milq import contract, gating, mzml
from tests.test_cli import FRAGMENT, call, ida  # noqa: F401
from tests.test_mzml import _dda_spectrum, _hand_written


def test_the_summary_apex_is_the_traces_maximum_on_a_jagged_trace():
    """An IDA survey trace alternates; the valley walk chose a later tooth."""
    rt = np.round(np.arange(1.20, 1.40, 0.0195), 4)
    y = np.array([4.36, 4.14, 8.52, 5.53, 7.10, 4.86, 8.31, 5.36, 4.87, 1.0, 0.1]) * 1e6
    found = contract.summarise(rt[:y.size], y)
    assert found.apex_rt == pytest.approx(rt[2])
    assert found.apex_height == pytest.approx(8.52e6)


def test_bounds_area_and_points_follow_the_published_definitions():
    rt = np.arange(0, 21) * 0.1
    y = np.array([0, 0, 1, 2, 10, 40, 80, 100, 70, 30, 12, 9, 25, 40, 20, 4, 1, 0, 0, 0, 0],
                 dtype=float)
    found = contract.summarise(rt, y)
    # left: first point at or below 5 % (index 3, 2 ≤ 5); right: the valley
    # at index 11 (9) before the rise to 25 (≥ 9 + 10)
    assert (found.start_rt, found.end_rt) == (pytest.approx(0.3), pytest.approx(1.1))
    assert found.points == 9
    assert found.area == pytest.approx(np.trapezoid(y[3:12], rt[3:12]))
    assert found.apex_height == 100.0


def test_sticks_from_several_scans_merge_into_one_ion():
    parts = [(np.array([138.0657, 200.0]), np.array([1000.0, 10.0])),
             (np.array([138.0661]), np.array([3000.0])),
             (np.array([138.0666, 300.0]), np.array([2000.0, 5.0]))]
    mz, height = gating.merge_sticks(parts)
    assert mz.size == 3
    assert mz[0] == pytest.approx((138.0657 * 1000 + 138.0661 * 3000 + 138.0666 * 2000) / 6000)
    assert height[0] == pytest.approx(6000.0 / 3)


def test_scan_n_of_a_gated_source_is_one_scan(ida):  # noqa: F811
    code, out, err = call("spectrum", ida, "--source", "gated:627.8457", "--scan", "1",
                          "--centroid", "none")
    assert code == 0, err
    doc = json.loads(out)
    assert len(doc["scans_used"]) == 1 and doc["scans_used"][0]["rt"] == pytest.approx(0.3)
    code, _out, err = call("spectrum", ida, "--source", "gated:627.8457", "--scan", "99")
    assert code == 2 and json.loads(err)["error"] == "bad_arguments"


def test_an_ida_run_without_exclusion_is_one_channel_of_events(tmp_path):
    """Twelve precursors, each picked in every cycle while it elutes."""
    body, index = [], 0
    for cycle in range(60):
        rt = cycle * 0.01
        body.append(_dda_spectrum(index, 1, rt))
        index += 1
        for k in range(12):
            if 5 * k <= cycle < 5 * k + 25:
                body.append(_dda_spectrum(index, 2, rt + 0.0001 * (k + 1), 300.0 + 11.7 * k))
                index += 1
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body="".join(body),
                                         name="noex.mzML")).sample(0)
    assert [(c.info.kind, c.info.n_scans) for c in sample.channels] == [
        ("ms1", 60), ("dda-events", index - 60)]


def test_convert_keeps_every_precursor_to_the_last_bit(ida, tmp_path):  # noqa: F811
    out = tmp_path / "sub" / "dir" / "again.mzML"           # a folder not there yet
    code, _out, err = call("convert", ida, "--out", out)
    assert code == 0, err
    before = mzml.MzmlFile(ida)
    after = mzml.MzmlFile(str(out))
    try:
        for a, b in zip(before.sample(0).channels, after.sample(0).channels):
            pa, pb = a.scan_precursors(), b.scan_precursors()
            assert np.array_equal(pa[np.isfinite(pa)], pb[np.isfinite(pb)])
    finally:
        before.close()
        after.close()


def test_a_request_with_an_unknown_argument_is_refused_not_emptied(ida):  # noqa: F811
    from milq.cli import run
    from milq.contract import ContractError

    folder = str(__import__("os").path.dirname(ida))
    doc = run("batch-xic", {"files": folder, "mz": [FRAGMENT], "source": "ms2-all"})
    assert doc["files"] == 1 and doc["rows"]
    with pytest.raises(ContractError) as refused:
        run("batch-xic", {"folder": folder, "mz": [FRAGMENT]})
    assert refused.value.code == "bad_arguments"
    with pytest.raises(ContractError):
        run("xic", {"file": ida, "mz": [FRAGMENT], "tolerance": 0.01})
    assert run("info", {"path": ida})["command"] == "info"
