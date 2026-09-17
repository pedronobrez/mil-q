"""Tests for acceptance criteria and grouped statistics."""

import pytest

from milq.components import AcceptanceLimits, Component
from milq.method import ProcessingMethod
from milq.quantify import PeakResult, ResultsSet, evaluate_acceptance
from milq.samples import QC, STANDARD, UNKNOWN, SampleEntry
from milq.statistics import (
    GROUP_BY_CONCENTRATION,
    GROUP_BY_SAMPLE_TYPE,
    summarise,
)


def setup(limits: AcceptanceLimits | None = None):
    method = ProcessingMethod()
    method.replace_all([Component("Oxy", 325.20, 183.0, rt=13.1)])
    if limits is not None:
        method.acceptance = limits
    entry = SampleEntry("/d/a.wiff", 0, "QC", sample_type=QC,
                        actual_concentration=10.0)
    return method, [entry], entry


def result(entry, **kwargs):
    base = dict(sample_key=entry.key, sample_name=entry.name, component="Oxy",
                area=1000.0, height=500.0, rt=13.1, expected_rt=13.1, snr=50.0)
    base.update(kwargs)
    return PeakResult(**base)


# --- acceptance ------------------------------------------------------------------ #
def test_no_criteria_means_no_status():
    """A method that was not told what to check has not checked anything."""
    method, entries, entry = setup()
    results = ResultsSet([result(entry)])
    evaluate_acceptance(results, entries, method)
    assert results.results[0].status == ""
    assert results.results[0].flags == []


def test_a_missing_peak_always_fails():
    method, entries, entry = setup()
    results = ResultsSet([result(entry, area=0.0)])
    evaluate_acceptance(results, entries, method)
    row = results.results[0]
    assert row.status == "Fail"
    assert row.flags == ["not integrated"]


def test_retention_time_outside_tolerance_is_flagged():
    method, entries, entry = setup(AcceptanceLimits(rt_tolerance=0.05))
    results = ResultsSet([result(entry, rt=13.2)])   # +0.1 min
    evaluate_acceptance(results, entries, method)
    row = results.results[0]
    assert row.status == "Fail"
    assert row.flags == ["RT +0.100 min"]


def test_retention_time_inside_tolerance_passes():
    method, entries, entry = setup(AcceptanceLimits(rt_tolerance=0.05))
    results = ResultsSet([result(entry, rt=13.12)])
    evaluate_acceptance(results, entries, method)
    assert results.results[0].status == "Pass"


def test_low_signal_to_noise_is_flagged():
    method, entries, entry = setup(AcceptanceLimits(min_snr=100.0))
    results = ResultsSet([result(entry, snr=50.0)])
    evaluate_acceptance(results, entries, method)
    assert "S/N 50" in results.results[0].flags[0]


def test_accuracy_is_only_checked_when_a_concentration_is_known():
    method, entries, entry = setup(AcceptanceLimits(accuracy_tolerance=15.0))
    results = ResultsSet([result(entry, accuracy=130.0)])
    evaluate_acceptance(results, entries, method)
    assert results.results[0].status == "Fail"

    entries[0].actual_concentration = None
    results = ResultsSet([result(entry, accuracy=130.0)])
    evaluate_acceptance(results, entries, method)
    assert results.results[0].status == ""      # nothing to compare against


def test_failed_ion_ratio_joins_the_flags():
    method, entries, entry = setup()
    results = ResultsSet([result(entry, confidence="Fail", ion_ratio=40.0)])
    evaluate_acceptance(results, entries, method)
    row = results.results[0]
    assert row.status == "Fail"
    assert "ion ratio 40.0%" in row.flags


def test_marginal_ion_ratio_alone_gives_a_marginal_status():
    method, entries, entry = setup()
    results = ResultsSet([result(entry, confidence="Marginal", ion_ratio=40.0)])
    evaluate_acceptance(results, entries, method)
    assert results.results[0].status == "Marginal"
    assert results.results[0].flags == []


def test_several_failures_are_all_reported():
    method, entries, entry = setup(
        AcceptanceLimits(rt_tolerance=0.01, min_snr=100.0))
    results = ResultsSet([result(entry, rt=13.3, snr=10.0)])
    evaluate_acceptance(results, entries, method)
    assert len(results.results[0].flags) == 2


def test_component_override_beats_the_method_default():
    method, entries, entry = setup(AcceptanceLimits(rt_tolerance=0.01))
    method.by_name("Oxy").acceptance = AcceptanceLimits(rt_tolerance=1.0)
    results = ResultsSet([result(entry, rt=13.3)])
    evaluate_acceptance(results, entries, method)
    assert results.results[0].status == "Pass"


# --- statistics ------------------------------------------------------------------- #
def batch():
    method = ProcessingMethod()
    method.replace_all([Component("Oxy", 325.20, 183.0, rt=13.1)])
    entries, rows = [], []
    for index, (name, kind, concentration, area) in enumerate([
        ("QC1", QC, 10.0, 100.0),
        ("QC2", QC, 10.0, 110.0),
        ("QC3", QC, 10.0, 90.0),
        ("STD1", STANDARD, 50.0, 500.0),
        ("U1", UNKNOWN, None, 300.0),
    ]):
        entry = SampleEntry(f"/d/{index}.wiff", 0, name, sample_type=kind,
                            actual_concentration=concentration)
        entries.append(entry)
        rows.append(PeakResult(entry.key, name, "Oxy", area=area, height=area / 2))
    return method, entries, ResultsSet(rows)


def test_statistics_by_sample_type():
    method, entries, results = batch()
    rows = summarise(results, entries, method, GROUP_BY_SAMPLE_TYPE, "area")
    qc = next(r for r in rows if r.group == QC)
    assert qc.used == 3 and qc.total == 3
    assert qc.mean == pytest.approx(100.0)
    assert qc.standard_deviation == pytest.approx(10.0)
    assert qc.percent_cv == pytest.approx(10.0)


def test_excluded_rows_leave_the_total_alone():
    method, entries, results = batch()
    results.results[0].used = False
    qc = next(r for r in summarise(results, entries, method, GROUP_BY_SAMPLE_TYPE,
                                   "area") if r.group == QC)
    assert qc.used == 2 and qc.total == 3
    assert qc.mean == pytest.approx(100.0)      # 110 and 90
    assert qc.values[0][2] is False             # still listed, marked unused


def test_a_single_value_has_no_spread():
    method, entries, results = batch()
    row = next(r for r in summarise(results, entries, method,
                                    GROUP_BY_SAMPLE_TYPE, "area")
               if r.group == STANDARD)
    assert row.standard_deviation is None
    assert row.percent_cv is None


def test_grouping_by_concentration_skips_samples_without_one():
    method, entries, results = batch()
    rows = summarise(results, entries, method, GROUP_BY_CONCENTRATION, "area")
    groups = {r.group for r in rows}
    assert groups == {"10", "50"}               # the unknown has no level


def test_accuracy_is_reported_for_concentration_groups():
    method, entries, results = batch()
    for row in results:
        row.calculated_concentration = 11.0
    rows = summarise(results, entries, method, GROUP_BY_CONCENTRATION,
                     "calculated concentration")
    ten = next(r for r in rows if r.group == "10")
    assert ten.accuracy == pytest.approx(110.0)


def test_missing_values_do_not_break_the_mean():
    method, entries, results = batch()
    results.results[1].area = 0.0               # did not integrate
    qc = next(r for r in summarise(results, entries, method,
                                   GROUP_BY_SAMPLE_TYPE, "area")
              if r.group == QC)
    assert qc.used == 2 and qc.total == 3
