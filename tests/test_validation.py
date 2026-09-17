"""
How low the method goes, and what the last injection left behind.

Both are numbers a laboratory is asked to defend, so the tests here are less
about the arithmetic — which is three lines — than about the cases where a
number should not be produced at all: a curve with no slope, a quadratic, a
limit under the lowest calibrator, a run with no blank in the right place.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.calibration import CalibrationPoint, fit  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.quantify import PeakResult, ResultsSet  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from milq.validation import (BLANK_TYPES, acquisition_order, carryover,  # noqa: E402
                                  detection_limits)


def _curve(pairs, regression="linear", weighting="1", name="A"):
    points = [CalibrationPoint(sample_key=f"S{i}", sample_name=f"S{i}",
                               concentration=c, response=r)
              for i, (c, r) in enumerate(pairs)]
    return fit(points, regression, weighting, name)


# --------------------------------------------------------------------------- #
# detection and quantitation limits
# --------------------------------------------------------------------------- #
def test_limits_come_from_the_scatter_about_the_line():
    """
    A curve whose points sit exactly on a line has no scatter, so its limits
    are zero — which is the arithmetic being right, not the method being
    infinitely sensitive.
    """
    limits = detection_limits(_curve([(10, 1.0), (20, 2.0), (30, 3.0), (40, 4.0)]))
    assert limits.measurable
    assert limits.sigma == pytest.approx(0.0, abs=1e-9)
    assert limits.lod == pytest.approx(0.0, abs=1e-9)


def test_scatter_raises_the_limits():
    clean = detection_limits(_curve([(10, 1.0), (20, 2.0), (30, 3.0), (40, 4.0)]))
    noisy = detection_limits(_curve([(10, 1.2), (20, 1.9), (30, 3.2), (40, 3.8)]))
    assert noisy.lod > clean.lod
    assert noisy.loq > noisy.lod
    # the two multipliers of ICH Q2, one over the other
    assert noisy.loq / noisy.lod == pytest.approx(10.0 / 3.3, rel=1e-9)


def test_a_limit_below_the_lowest_standard_says_so():
    """
    A curve says nothing about concentrations nobody put on it. Reporting a
    limit under the lowest calibrator without saying it was extrapolated is
    how a method claims a sensitivity it has never shown.
    """
    limits = detection_limits(_curve([(100, 10.0), (200, 20.02), (300, 29.98),
                                      (400, 40.0)]))
    assert limits.measurable
    assert limits.loq < limits.lowest_standard
    assert limits.extrapolated


def test_a_limit_inside_the_calibrated_range_is_not_flagged():
    limits = detection_limits(_curve([(1, 1.0), (10, 9.4), (50, 51.0), (100, 99.0)]))
    assert limits.measurable
    assert not limits.extrapolated


def test_a_quadratic_gets_no_limit_and_a_reason():
    curve = _curve([(10, 1.0), (20, 2.1), (30, 3.4), (40, 5.0)], regression="quadratic")
    limits = detection_limits(curve)
    assert not limits.measurable
    assert "quadratic" in limits.note


def test_too_few_standards_get_no_limit():
    limits = detection_limits(_curve([(10, 1.0), (20, 2.0)]))
    assert not limits.measurable
    assert "three" in limits.note


def test_three_points_on_a_line_report_how_little_they_prove():
    """Two parameters and three points leave one degree of freedom: enough to
    compute a scatter and not enough to believe it."""
    limits = detection_limits(_curve([(10, 1.1), (20, 1.9), (30, 3.1)]))
    assert limits.measurable
    assert "degree(s) of freedom" in limits.note


def test_a_weighted_fit_is_declared():
    curve = _curve([(1, 1.0), (10, 9.7), (50, 50.4), (100, 100.2)], weighting="1/x")
    assert "1/x weighting" in detection_limits(curve).note


def test_an_unfitted_curve_produces_nothing():
    from milq.calibration import Calibration

    limits = detection_limits(Calibration(component="A"))
    assert not limits.measurable
    assert limits.note == "no curve"


# --------------------------------------------------------------------------- #
# carryover
# --------------------------------------------------------------------------- #
class _Sample:
    def __init__(self, when):
        self.acquisition_time = when


def _entry(name, kind, concentration=None, when=None):
    entry = SampleEntry(f"/d/{name}.wiff", 0, name, kind, concentration, 1.0, "")
    if when:
        entry.sample = _Sample(when)
    return entry


def _batch():
    """Five standards, a blank straight after the top one, then a sample."""
    return [
        _entry("STD_L1", "Standard", 5.0, "2026-01-15T09:00:00"),
        _entry("STD_L2", "Standard", 20.0, "2026-01-15T09:10:00"),
        _entry("STD_L3", "Standard", 50.0, "2026-01-15T09:20:00"),
        _entry("STD_L4", "Standard", 100.0, "2026-01-15T09:30:00"),
        _entry("STD_L5", "Standard", 200.0, "2026-01-15T09:40:00"),
        _entry("BLANK01", "Blank", None, "2026-01-15T09:50:00"),
        _entry("Sample_01", "Unknown", None, "2026-01-15T10:00:00"),
    ]


def _method():
    method = ProcessingMethod()
    method.replace_all([
        Component(name="A", precursor=1.0, fragment=1.0, rt=1.0),
        Component(name="IS", precursor=2.0, fragment=1.0, rt=1.0,
                  is_internal_standard=True),
    ])
    return method


def _results(pairs):
    results = ResultsSet.from_list([])
    for key, component, area in pairs:
        row = PeakResult(sample_key=f"/d/{key}.wiff|0", sample_name=key,
                         component=component)
        row.area = area
        results.replace(row)
    return results


def test_the_order_of_acquisition_comes_from_the_timestamps():
    entries = list(reversed(_batch()))
    assert [e.name for e in acquisition_order(entries)][:3] == \
        ["STD_L1", "STD_L2", "STD_L3"]


def test_carryover_is_measured_against_the_lowest_standard():
    """
    Not against the standard that caused it: doing that would make a method
    look worse the higher its top calibrator went, which is backwards.
    """
    entries = _batch()
    results = _results([("STD_L1", "A", 1000.0), ("STD_L5", "A", 40000.0),
                        ("BLANK01", "A", 100.0)])
    report = carryover(results, entries, _method())
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.blank == "BLANK01" and row.follows == "STD_L5"
    assert row.reference == "STD_L1"
    assert row.percent == pytest.approx(10.0)
    assert not row.fails


def test_carryover_over_the_limit_fails():
    entries = _batch()
    results = _results([("STD_L1", "A", 1000.0), ("BLANK01", "A", 250.0)])
    report = carryover(results, entries, _method())
    assert report.rows[0].percent == pytest.approx(25.0)
    assert report.rows[0].fails
    assert report.failures


def test_an_internal_standard_is_not_checked_for_carryover():
    entries = _batch()
    results = _results([("STD_L1", "A", 1000.0), ("BLANK01", "A", 10.0),
                        ("STD_L1", "IS", 5000.0), ("BLANK01", "IS", 4900.0)])
    report = carryover(results, entries, _method())
    assert [row.component for row in report.rows] == ["A"]


def test_no_blank_after_the_top_standard_is_reported_as_not_measured():
    """
    A blank somewhere else in the run does not test this, and a figure nobody
    measured is worse than none.
    """
    entries = [e for e in _batch() if e.name != "BLANK01"]
    entries.insert(0, _entry("BLANK00", "Blank", None, "2026-01-15T08:50:00"))
    results = _results([("STD_L1", "A", 1000.0), ("BLANK00", "A", 900.0)])
    report = carryover(results, entries, _method())
    assert report.rows == []
    assert "no blank was injected after" in report.note


def test_a_run_without_standards_says_so():
    entries = [_entry("Sample_01", "Unknown", None, "2026-01-15T09:00:00")]
    report = carryover(_results([]), entries, _method())
    assert report.rows == []
    assert "no standards" in report.note


@pytest.mark.parametrize("kind", BLANK_TYPES)
def test_every_kind_of_blank_counts(kind):
    entries = _batch()
    entries[5] = _entry("BLANK01", kind, None, "2026-01-15T09:50:00")
    results = _results([("STD_L1", "A", 1000.0), ("BLANK01", "A", 50.0)])
    assert carryover(results, entries, _method()).rows[0].percent == pytest.approx(5.0)
