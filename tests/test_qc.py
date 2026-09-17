"""
Whether the batch held up.

A control chart is read for a decision — reinject, requantify, or accept —
so most of what is tested here is the machinery declining to draw one: too
few injections, no spread, no internal standard, scatter that fits a line
because everything does.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import qc  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.quantify import PeakResult, ResultsSet  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402


class _Sample:
    def __init__(self, when):
        self.acquisition_time = when


def _entry(name, kind="Unknown", minute=0, timed=True):
    entry = SampleEntry(f"/d/{name}.wiff", 0, name, kind, None, 1.0, "")
    if timed:
        entry.sample = _Sample(f"2026-01-15T09:{minute:02d}:00")
    return entry


def _batch(count=12, kind="Unknown"):
    return [_entry(f"S{n:02d}", kind, minute=n) for n in range(count)]


def _method(internal=("IS",), analytes=("A",)):
    method = ProcessingMethod()
    components = [Component(name=name, precursor=1.0, fragment=1.0, rt=1.0)
                  for name in analytes]
    components += [Component(name=name, precursor=2.0, fragment=1.0, rt=1.0,
                             is_internal_standard=True) for name in internal]
    method.replace_all(components)
    return method


def _results(entries, component, areas):
    results = ResultsSet.from_list([])
    for entry, area in zip(entries, areas):
        row = PeakResult(sample_key=entry.key, sample_name=entry.name,
                         component=component)
        row.area = float(area)
        results.replace(row)
    return results


# --------------------------------------------------------------------------- #
# the statistics, which have no dependency to lean on
# --------------------------------------------------------------------------- #
def test_spearman_sees_a_monotonic_climb_a_straight_line_does_not():
    """Ranks, not values: a curve that only ever rises correlates perfectly."""
    order = np.arange(1.0, 11.0)
    assert qc.spearman(order, order ** 3) == pytest.approx(1.0)
    assert qc.spearman(order, -(order ** 3)) == pytest.approx(-1.0)


def test_tied_values_share_a_rank():
    """Otherwise a flat run correlates with whatever order it was sorted in."""
    order = np.arange(1.0, 7.0)
    assert qc.spearman(order, np.ones(6)) is None      # no spread at all
    ranked = qc._ranks(np.array([5.0, 5.0, 5.0, 9.0]))
    assert list(ranked) == [2.0, 2.0, 2.0, 4.0]


def test_the_centre_is_not_moved_by_one_wild_injection():
    """
    The whole reason for a median: the outlier being hunted is in the sample
    that sets the limits meant to catch it.
    """
    clean = np.array([100.0, 101.0, 99.0, 100.0, 102.0, 98.0])
    spiked = np.append(clean, 1000.0)
    assert qc.robust_centre(spiked)[0] == pytest.approx(100.0)
    # the mean would have moved by more than a hundred
    assert abs(float(spiked.mean()) - 100.0) > 100


# --------------------------------------------------------------------------- #
# control charts
# --------------------------------------------------------------------------- #
def test_a_steady_internal_standard_is_flagged_for_nothing():
    entries = _batch(12)
    areas = [10000 + (n % 3 - 1) * 40 for n in range(12)]
    report = qc.batch_qc(_results(entries, "IS", areas), entries, _method())
    chart = report.charts[0]
    assert chart.measurable and chart.is_internal_standard
    assert chart.out == [] and not chart.drifted
    assert report.ordered


def test_one_injection_that_failed_is_caught():
    entries = _batch(12)
    areas = [10000 + (n % 3 - 1) * 40 for n in range(12)]
    areas[7] = 2000.0                       # a missed spike, or a blocked tip
    report = qc.batch_qc(_results(entries, "IS", areas), entries, _method())
    chart = report.charts[0]
    assert [point.sample for point in chart.out] == ["S07"]
    assert chart.out[0].percent < -70
    assert report.out == [chart]


def test_a_run_that_falls_away_is_called_drift():
    """
    The failure per-sample review cannot see: every point inside its limits,
    and the last injection two thirds of the first.
    """
    entries = _batch(20)
    areas = [10000 - 300 * n for n in range(20)]
    report = qc.batch_qc(_results(entries, "IS", areas), entries, _method())
    chart = report.charts[0]
    assert chart.drifted
    assert chart.drift < -50
    assert chart.correlation == pytest.approx(-1.0)
    assert report.drifted == [chart]


def test_scatter_that_happens_to_fit_a_line_is_not_drift():
    """
    A slope can always be fitted. Without a monotonic trend behind it, it is
    an artefact of fitting, and calling it drift sends somebody to change a
    column that is fine.
    """
    entries = _batch(12)
    rng = np.random.default_rng(20260907)
    areas = 10000 + rng.normal(0, 1500, 12)
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    assert abs(chart.correlation) < qc.DRIFT_CORRELATION
    assert not chart.drifted


def test_a_short_run_gets_no_chart_and_a_reason():
    entries = _batch(4)
    chart = qc.batch_qc(_results(entries, "IS", [10000] * 4), entries,
                        _method()).charts[0]
    assert not chart.measurable
    assert "6 are needed" in chart.note
    assert len(chart.injections) == 4      # the points are still there to plot


def test_a_response_with_no_spread_flags_nothing():
    """
    Identical responses to the last digit are a reason to distrust the
    measurement, not to put every other point outside three sigma.
    """
    entries = _batch(10)
    chart = qc.batch_qc(_results(entries, "IS", [500.0] * 10), entries,
                        _method()).charts[0]
    assert chart.sigma == 0
    assert chart.out == [] and chart.warned == []
    assert "over half the injections share one response" in chart.note


def test_a_batch_with_no_internal_standard_says_so():
    entries = _batch(10)
    report = qc.batch_qc(_results(entries, "A", [1.0] * 10), entries,
                         _method(internal=()))
    assert report.charts == []
    assert "no internal standard is marked" in report.note


def test_a_double_blank_is_not_on_the_internal_standard_chart():
    """
    It is extracted without the standard. Plotted, it is a zero in the middle
    of the run that makes a sound batch look as though it lost the spike.
    """
    entries = _batch(10)
    entries.insert(5, _entry("DB01", "Double Blank", minute=55))
    areas = [10000.0] * 5 + [0.0] + [10000.0] * 5
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    assert "DB01" not in [point.sample for point in chart.injections]
    assert len(chart.injections) == 10


def test_the_order_is_the_order_the_instrument_ran():
    entries = list(reversed(_batch(8)))          # opened back to front
    areas = {f"S{n:02d}": 1000.0 + n for n in range(8)}
    results = _results(entries, "IS", [areas[e.name] for e in entries])
    chart = qc.batch_qc(results, entries, _method()).charts[0]
    assert [point.sample for point in chart.injections][:3] == ["S00", "S01", "S02"]


def test_an_untimed_batch_says_the_order_is_only_the_order_opened():
    entries = [_entry(f"S{n:02d}", timed=False) for n in range(8)]
    report = qc.batch_qc(_results(entries, "IS", [1000.0] * 8), entries,
                         _method())
    assert not report.ordered
    assert report.timed == 0


# --------------------------------------------------------------------------- #
# precision of the controls
# --------------------------------------------------------------------------- #
def test_precision_is_measured_over_quality_controls_only():
    """
    Unknowns differ by design and standards by construction; a %CV over
    either measures the study rather than the method.
    """
    entries = [_entry(f"QC{n}", "Quality Control", minute=n) for n in range(4)]
    entries += [_entry(f"U{n}", "Unknown", minute=10 + n) for n in range(4)]
    areas = [1000.0, 1010.0, 990.0, 1000.0, 1.0, 500.0, 9000.0, 20.0]
    rows = qc.precision(_results(entries, "A", areas), entries,
                        _method(internal=()))
    row = next(r for r in rows if r.component == "A")
    assert row.replicates == 4
    assert row.percent_cv < 2.0            # the unknowns did not get in
    assert not row.fails


def test_scattered_controls_fail_their_limit():
    entries = [_entry(f"QC{n}", "Quality Control", minute=n) for n in range(4)]
    rows = qc.precision(_results(entries, "A", [500.0, 1500.0, 800.0, 1200.0]),
                        entries, _method(internal=()))
    row = next(r for r in rows if r.component == "A")
    assert row.fails and row.percent_cv > qc.CV_PERCENT


def test_two_controls_get_no_coefficient_of_variation():
    entries = [_entry(f"QC{n}", "Quality Control", minute=n) for n in range(2)]
    rows = qc.precision(_results(entries, "A", [1000.0, 1010.0]), entries,
                        _method(internal=()))
    row = next(r for r in rows if r.component == "A")
    assert not row.measurable
    assert "fewer than 3" in row.note


def test_points_beyond_two_sigma_are_only_news_above_what_chance_gives():
    """
    One injection in twenty falls outside two standard deviations with
    nothing wrong. A verdict column that reports each of them is reporting
    the arithmetic of a normal distribution, and one that always has
    something in it stops being read.
    """
    def chart_of(sigmas):
        # a spread wide enough that the per-cent floors are not what decides:
        # one sigma is fifteen per cent of the centre here
        return qc.ControlChart(
            component="IS", centre=100.0, sigma=15.0,
            injections=[qc.Injection(order=n, sample=f"S{n:02d}",
                                     sample_type="Unknown", when="",
                                     value=100.0 + 15.0 * s, sigmas=s,
                                     percent=15.0 * s)
                        for n, s in enumerate(sigmas, start=1)])

    # twenty injections, one of them beyond two sigma: exactly what chance
    # gives, and nothing to report
    quiet = chart_of([0.5] * 19 + [2.4])
    assert len(quiet.warned) == 1 and quiet.excess_warnings == 0

    # four of twenty is four times that
    noisy = chart_of([0.5] * 16 + [2.4, 2.5, -2.6, 2.9])
    assert len(noisy.warned) == 4 and noisy.excess_warnings == 3

    # and beyond three sigma is never merely chance: it is counted apart
    assert chart_of([0.5] * 19 + [4.0]).warned == []
    assert len(chart_of([0.5] * 19 + [4.0]).out) == 1


def test_a_tight_batch_does_not_turn_ordinary_scatter_into_outliers():
    """
    The defect this floor exists for, measured on a real run: a batch that
    repeats itself to within half a per cent has a median absolute deviation
    of about that, and three sigmas of it is an internal standard three per
    cent low — an ordinary injection, flagged on almost every batch.
    """
    entries = _batch(11)
    areas = [7736, 7778, 7815, 7308, 7787, 7849, 7793, 7508, 7758, 7929, 7515]
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    worst = min(chart.injections, key=lambda p: p.percent)
    assert worst.sigmas < -4.0          # unusual for this batch, and
    assert worst.percent > -10.0        # nobody would reinject on it, so
    assert chart.out == [] and chart.warned == []


def test_a_failed_injection_is_still_caught_in_a_tight_batch():
    """The floor must not cost the flag that matters."""
    entries = _batch(11)
    areas = [7736, 7778, 7815, 7308, 7787, 1200, 7793, 7508, 7758, 7929, 7515]
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    assert [point.sample for point in chart.out] == ["S05"]


# --------------------------------------------------------------------------- #
# a response too small to quantify
# --------------------------------------------------------------------------- #
#: a steady response with two injections far out of line, so that what is
#: being tested is the signal-to-noise gate and not the spread
NOISY = [100, 104, 96, 300, 102, 98, 101, 99, 280, 103, 97, 100]


def _results_with_snr(entries, component, areas, snr):
    results = ResultsSet.from_list([])
    for entry, area in zip(entries, areas):
        row = PeakResult(sample_key=entry.key, sample_name=entry.name,
                         component=component)
        row.area, row.snr = float(area), float(snr)
        results.replace(row)
    return results


def test_a_standard_below_the_limit_of_quantitation_flags_nothing():
    """
    Measured on a real batch: eight of eleven internal standards had a median
    response between 4 and 52 counts and produced almost every flag in the
    run. A standard whose median is five counts reads three hundred per cent
    high the moment it gives twenty, and the per-cent floors cannot help —
    a small absolute change is a huge relative one.
    """
    entries = _batch(12)
    areas = NOISY
    chart = qc.batch_qc(_results_with_snr(entries, "IS", areas, snr=2.0),
                        entries, _method()).charts[0]
    assert chart.measurable                 # the centre is still computed
    assert not chart.quantifiable
    assert chart.out == [] and chart.warned == [] and not chart.drifted
    assert "below 10" in chart.note
    assert len(chart.injections) == 12      # and the points are still there


def test_the_same_numbers_above_the_limit_are_flagged():
    """The suppression has to be about the signal, not about the arithmetic."""
    entries = _batch(12)
    chart = qc.batch_qc(_results_with_snr(entries, "IS", NOISY, snr=250.0),
                        entries, _method()).charts[0]
    assert chart.quantifiable
    assert [p.sample for p in chart.out] == ["S03", "S08"]


def test_a_drift_in_a_response_too_small_to_quantify_is_not_reported():
    entries = _batch(20)
    areas = [40 - n for n in range(20)]
    chart = qc.batch_qc(_results_with_snr(entries, "IS", areas, snr=3.0),
                        entries, _method()).charts[0]
    assert abs(chart.drift) > qc.DRIFT_PERCENT      # the arithmetic still runs
    assert not chart.drifted                        # and is not acted on


def test_an_unmeasured_signal_to_noise_suppresses_nothing():
    """None means not measured, which is not the same as measured and small."""
    entries = _batch(12)
    areas = [10000 + (n % 3 - 1) * 40 for n in range(12)]
    areas[7] = 2000.0
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    assert chart.snr is None and chart.quantifiable
    assert [p.sample for p in chart.out] == ["S07"]


def test_the_median_decides_not_the_worst_injection():
    """A standard strong through the run is not written off by two failures."""
    entries = _batch(12)
    results = ResultsSet.from_list([])
    for n, entry in enumerate(entries):
        row = PeakResult(sample_key=entry.key, sample_name=entry.name,
                         component="IS")
        row.area = 10000.0 if n != 7 else 2000.0
        row.snr = 2.0 if n in (3, 9) else 400.0
        results.replace(row)
    chart = qc.batch_qc(results, entries, _method()).charts[0]
    assert chart.snr == pytest.approx(400.0)
    assert chart.quantifiable


# --------------------------------------------------------------------------- #
# the injections taken together
# --------------------------------------------------------------------------- #
def _many_standards(entries, plan):
    """`plan` maps a standard's name to its response in each injection."""
    results = ResultsSet.from_list([])
    for component, areas in plan.items():
        for entry, area in zip(entries, areas):
            row = PeakResult(sample_key=entry.key, sample_name=entry.name,
                             component=component)
            row.area = float(area)
            results.replace(row)
    return results


def test_an_injection_where_every_standard_went_together_is_named():
    """
    What a single standard's chart cannot say. Injection 7 has all three
    standards at a fifth of normal — the injection failed — and each standard
    separately only sees one point a long way from its own centre.
    """
    entries = _batch(12)
    plan = {}
    for name, level in (("IS_A", 10000.0), ("IS_B", 800.0), ("IS_C", 40.0)):
        areas = [level * (1.0 + (n % 3 - 1) * 0.05) for n in range(12)]
        areas[7] = level * 0.2
        plan[name] = areas
    report = qc.batch_qc(_many_standards(entries, plan), entries,
                         _method(internal=("IS_A", "IS_B", "IS_C")))
    index = report.index
    assert index is not None and index.measurable
    assert [p.sample for p in index.out] == ["S07"]
    assert index.injections[7].value == pytest.approx(0.2, abs=0.02)
    assert "median of 3 internal standards" in index.note


def test_one_standard_misbehaving_does_not_move_the_index():
    """
    The other half of the distinction: a compound's own problem must not read
    as an injection failure, which is what a median across standards buys.
    """
    entries = _batch(12)
    plan = {}
    for name, level in (("IS_A", 10000.0), ("IS_B", 800.0), ("IS_C", 40.0)):
        plan[name] = [level] * 12
    plan["IS_B"] = [800.0 * (6.0 if n % 2 else 0.1) for n in range(12)]
    report = qc.batch_qc(_many_standards(entries, plan), entries,
                         _method(internal=("IS_A", "IS_B", "IS_C")))
    assert report.index.out == []
    assert any(c.component == "IS_B" and c.unusable for c in report.charts)


def test_too_few_standards_get_no_index():
    entries = _batch(12)
    report = qc.batch_qc(_results(entries, "IS", [10000.0] * 12), entries,
                         _method())
    assert report.index is not None
    assert not report.index.measurable
    assert "fewer than 3 internal standards" in report.index.note


# --------------------------------------------------------------------------- #
# a batch too loose to flag its own failures
# --------------------------------------------------------------------------- #
def test_a_wide_batch_still_calls_out_an_injection_that_plainly_failed():
    """
    The mirror of the per-cent floors. Measured on a real run: an injection
    where every standard came back at a fifth of normal sat at 2.6 robust
    standard deviations, because the batch it was compared against varied by a
    third from one injection to the next.
    """
    entries = _batch(20)
    # a batch that swings 20% either way from injection to injection, which
    # gives a robust sigma of about 3,000 on a centre of 10,000
    areas = [8000.0 if n % 2 else 12000.0 for n in range(20)]
    areas[9] = 2000.0
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    point = chart.injections[9]
    assert abs(point.sigmas) < qc.OUTLIER_SIGMA      # the spread hides it
    assert abs(point.percent) >= qc.ALWAYS_OUT_PERCENT
    assert point.out


def test_a_standard_mostly_out_is_reported_once_rather_than_injection_by_injection():
    entries = _batch(24)
    areas = [10000.0 if n % 2 else 500.0 for n in range(24)]
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    assert chart.unusable
    assert len(chart.out) / len(chart.injections) > qc.UNUSABLE_FRACTION


def test_a_batch_with_a_few_bad_injections_is_not_called_unusable():
    entries = _batch(24)
    areas = [10000.0] * 24
    areas[5] = 3000.0
    areas[17] = 20000.0
    chart = qc.batch_qc(_results(entries, "IS", areas), entries,
                        _method()).charts[0]
    assert not chart.unusable
    assert [p.sample for p in chart.out] == ["S05", "S17"]


def test_the_results_of_a_failed_injection_can_be_taken_out():
    """
    Detecting an injection that failed and then letting its numbers into the
    means is most of the way to not having detected it.
    """
    entries = _batch(12)
    plan = {}
    for name, level in (("IS_A", 10000.0), ("IS_B", 800.0), ("IS_C", 40.0)):
        areas = [level] * 12
        areas[7] = level * 0.2
        plan[name] = areas
    results = _many_standards(entries, plan)
    report = qc.batch_qc(results, entries, _method(internal=("IS_A", "IS_B", "IS_C")))
    assert qc.failed_injections(report) == ["S07"]

    changed = qc.exclude_failed(results, entries, report)
    assert changed == 3
    excluded = [r for r in results if not r.used]
    assert {r.sample_name for r in excluded} == {"S07"}
    assert all("every internal standard low" in " ".join(r.flags)
               for r in excluded)


def test_excluding_twice_changes_nothing_more():
    entries = _batch(12)
    plan = {n: [1000.0] * 12 for n in ("IS_A", "IS_B", "IS_C")}
    for name in plan:
        plan[name][7] = 200.0
    results = _many_standards(entries, plan)
    report = qc.batch_qc(results, entries, _method(internal=tuple(plan)))
    assert qc.exclude_failed(results, entries, report) == 3
    assert qc.exclude_failed(results, entries, report) == 0


def test_a_row_integrated_by_hand_is_left_alone():
    """Somebody looked at that one."""
    entries = _batch(12)
    plan = {n: [1000.0] * 12 for n in ("IS_A", "IS_B", "IS_C")}
    for name in plan:
        plan[name][7] = 200.0
    results = _many_standards(entries, plan)
    row = results.get(entries[7].key, "IS_A")
    row.manual = True
    report = qc.batch_qc(results, entries, _method(internal=tuple(plan)))
    qc.exclude_failed(results, entries, report)
    assert results.get(entries[7].key, "IS_A").used


def test_nothing_to_exclude_when_no_injection_failed():
    entries = _batch(12)
    plan = {n: [1000.0] * 12 for n in ("IS_A", "IS_B", "IS_C")}
    results = _many_standards(entries, plan)
    report = qc.batch_qc(results, entries, _method(internal=tuple(plan)))
    assert qc.failed_injections(report) == []
    assert qc.exclude_failed(results, entries, report) == 0
