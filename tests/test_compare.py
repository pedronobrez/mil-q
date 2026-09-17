"""
The batch integrated every way, and what the comparison says about it.

What matters here is not that three runs happen but that the differences
are reported where they are and only there: a component every algorithm
agrees on is not marked, one that moves is, a row one algorithm found and
another did not is counted rather than averaged over, and adopting an
algorithm changes every component's settings and not just the defaults.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import processing as pr  # noqa: E402
from milq.compare import (SENSITIVE_PERCENT, adopt_algorithm,  # noqa: E402
                               compare_algorithms, with_algorithm)
from milq.components import Component, IntegrationParams  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.samples import QC, UNKNOWN, SampleEntry  # noqa: E402
from tests.test_matching import Channel, Sample  # noqa: E402

STEP = 14.6 / 60.0
_app = None


def _gaussian(x, centre, sigma, height):
    return height * np.exp(-0.5 * ((x - centre) / sigma) ** 2)


class _Channel(Channel):
    """Two transitions: a wide, well-behaved peak and a narrow one whose
    trapezoid moves with the scan phase."""

    def __init__(self, *args, phase=0.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.phase = phase

    def xic_range(self, mz_lo, mz_hi):
        x = self.rt + self.phase
        if mz_lo < 200:
            y = _gaussian(x, 6.4, 0.13, 20000.0)
        else:
            y = _gaussian(x, 6.4, 0.16, 5000.0) + 30.0
        y[y < 1] = 0
        return x, y


def _entries(n=6, kind=UNKNOWN):
    entries = []
    scans = int(round(12.0 / STEP))
    for i in range(n):
        channels = [_Channel(1, 703.6, 100.0, 300.0, 0.0, 12.0, n=scans,
                             phase=STEP * i / n),
                    _Channel(2, 703.6, 300.0, 800.0, 0.0, 12.0, n=scans,
                             phase=STEP * i / n)]
        entry = SampleEntry(f"/d/S{i:02d}.wiff", 0, f"S{i:02d}", kind)
        entry.sample = Sample(channels)
        entries.append(entry)
    return entries


def _method():
    method = ProcessingMethod()
    method.replace_all([
        Component("IS_narrow", 703.6, 184.0, rt=6.4, rt_halfwidth=0.5,
                  is_internal_standard=True),
        Component("A_wide", 703.6, 500.0, rt=6.4, rt_halfwidth=0.5,
                  internal_standard="IS_narrow",
                  integration=IntegrationParams(smoothing=0.0)),
    ])
    return method


def test_every_algorithm_is_run_and_the_reference_is_the_methods():
    comparison = compare_algorithms(_entries(), _method())
    assert comparison is not None
    assert comparison.reference == pr.ALGORITHM_VALLEY
    assert set(comparison.algorithms) == set(pr.ALGORITHMS)
    assert comparison.rows == 12
    for algorithm in pr.ALGORITHMS:
        assert len(comparison.results[algorithm]) == 12
        assert all(r.algorithm for r in comparison.results[algorithm])


def test_the_fit_repeats_better_than_the_trapezoid_on_the_standard():
    """
    Six injections of the same standard, each with the scans landing at a
    different phase: the trapezoid's %CV is the phase, the fit's is not.
    """
    comparison = compare_algorithms(_entries(), _method())
    standard = next(c for c in comparison.components if c.component == "IS_narrow")
    valley = standard.figures[pr.ALGORITHM_VALLEY]
    fitted = standard.figures[pr.ALGORITHM_GAUSSIAN]
    assert valley.precision is not None and fitted.precision is not None
    assert valley.replicates == 6
    assert fitted.precision < valley.precision / 5


def test_an_analyte_has_no_replicates_without_quality_controls():
    comparison = compare_algorithms(_entries(kind=UNKNOWN), _method())
    analyte = next(c for c in comparison.components if c.component == "A_wide")
    assert analyte.figures[pr.ALGORITHM_VALLEY].precision is None
    with_qcs = compare_algorithms(_entries(kind=QC), _method())
    analyte = next(c for c in with_qcs.components if c.component == "A_wide")
    assert analyte.figures[pr.ALGORITHM_VALLEY].precision is not None


def test_a_component_that_agrees_is_not_marked_and_one_that_moves_is():
    comparison = compare_algorithms(_entries(), _method())
    wide = next(c for c in comparison.components if c.component == "A_wide")
    narrow = next(c for c in comparison.components if c.component == "IS_narrow")
    # the wide peak is sampled well enough that the fit and the trapezoid
    # agree; summation over a ±0.5 min window on a 30-count baseline does not
    assert not wide.deltas[pr.ALGORITHM_GAUSSIAN].sensitive
    assert wide.deltas[pr.ALGORITHM_GAUSSIAN].median_percent < 5.0
    assert wide.deltas[pr.ALGORITHM_SUMMATION].both == 6
    for delta in narrow.deltas.values():
        assert delta.both == 6 and delta.only_reference == 0


def test_rows_found_by_one_algorithm_only_are_counted_not_averaged():
    method = _method()
    # no window: summation cannot run, the others can
    method.components[0].rt = None
    comparison = compare_algorithms(_entries(), method)
    narrow = next(c for c in comparison.components if c.component == "IS_narrow")
    delta = narrow.deltas[pr.ALGORITHM_SUMMATION]
    assert delta.both == 0 and delta.median_percent is None
    assert delta.only_reference == 6
    assert narrow.figures[pr.ALGORITHM_SUMMATION].found == 0


def test_the_totals_and_the_summary_add_up():
    comparison = compare_algorithms(_entries(), _method())
    totals = comparison.totals(pr.ALGORITHM_VALLEY)
    assert totals.rows == 12 and totals.found == 12
    assert totals.components_found == 2
    assert totals.sensitive == 0                      # the reference itself
    text = comparison.summary()
    assert "12 rows integrated 3 ways" in text
    assert "Valley to valley" in text and "Gaussian fit" in text


def test_a_fallback_is_counted_as_one():
    entries = _entries()
    method = _method()
    for entry in entries:
        for channel in entry.sample.channels:
            channel.phase += STEP / 2          # the narrow peak lands between scans
    # narrower still, so that only two points clear the baseline
    class _Narrow(_Channel):
        def xic_range(self, mz_lo, mz_hi):
            x = self.rt + self.phase
            y = _gaussian(x, 6.4 + STEP / 2, 0.05, 20000.0)
            y[y < 1] = 0
            return x, y
    for entry in entries:
        entry.sample = Sample([_Narrow(1, 703.6, 100.0, 300.0, 0.0, 12.0,
                                       n=int(round(12.0 / STEP)))])
    method.replace_all([method.components[0]])
    comparison = compare_algorithms(entries, method)
    narrow = comparison.components[0]
    assert narrow.figures[pr.ALGORITHM_GAUSSIAN].fallbacks == 6
    assert narrow.figures[pr.ALGORITHM_GAUSSIAN].too_sparse == 6
    assert narrow.figures[pr.ALGORITHM_VALLEY].fallbacks == 0
    assert "fewer than three points wide" in comparison.summary()


def test_cancelling_returns_nothing_rather_than_a_partial_comparison():
    calls = []

    def progress(done, total):
        calls.append((done, total))
        return done < 5

    assert compare_algorithms(_entries(), _method(), progress=progress) is None
    assert calls and calls[0][1] == 36


def test_with_algorithm_copies_and_reaches_the_overrides():
    method = _method()
    copy = with_algorithm(method, pr.ALGORITHM_GAUSSIAN)
    assert copy.defaults.algorithm == pr.ALGORITHM_GAUSSIAN
    assert copy.components[1].integration.algorithm == pr.ALGORITHM_GAUSSIAN
    # and the original is untouched
    assert method.defaults.algorithm == pr.ALGORITHM_VALLEY
    assert method.components[1].integration.algorithm == pr.ALGORITHM_VALLEY


def test_adopting_changes_the_defaults_and_every_override_in_place():
    method = _method()
    touched = adopt_algorithm(method, pr.ALGORITHM_SUMMATION)
    assert touched == 1
    assert method.defaults.algorithm == pr.ALGORITHM_SUMMATION
    assert method.components[1].integration.algorithm == pr.ALGORITHM_SUMMATION
    assert adopt_algorithm(method, pr.ALGORITHM_SUMMATION) == 0


def test_sensitivity_is_judged_on_the_median_not_on_one_row():
    from milq.compare import Delta
    assert Delta("x", both=3, median_percent=SENSITIVE_PERCENT + 1).sensitive
    assert not Delta("x", both=3, median_percent=SENSITIVE_PERCENT - 1,
                     max_percent=300.0).sensitive
    assert not Delta("x", both=0).sensitive


# --------------------------------------------------------------------------- #
# the dialog and the report
# --------------------------------------------------------------------------- #
@pytest.fixture
def session_with_comparison():
    from PyQt6 import QtWidgets
    from milq.session import Session
    global _app   # held, or it is collected before the dialog is built
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    session = Session()
    session.entries = _entries()
    session.method = _method()
    session.comparison = compare_algorithms(session.entries, session.method,
                                            session.cache)
    return session


def test_the_dialog_lists_every_component_and_draws_every_algorithm(session_with_comparison):
    from milq.ui.compare_dialog import ComparisonDialog
    session = session_with_comparison
    dialog = ComparisonDialog(session, session.comparison)
    assert dialog.components.rowCount() == 2
    assert dialog.samples.rowCount() == 6            # the first component's rows
    # a legend entry per algorithm that found the peak, plus the trace
    legend = dialog.plot.plotItem.legend
    assert len(legend.items) == 4
    adopted = []
    dialog.sigAdopt.connect(adopted.append)
    dialog.choice.setCurrentIndex(2)
    dialog.btn_adopt.click()
    assert adopted == [session.comparison.algorithms[2]]
    dialog.close()


def test_the_report_carries_the_section_only_when_a_comparison_was_run(session_with_comparison):
    from milq import report
    session = session_with_comparison
    document = report.build_html(session, sections=("summary", "algorithms"))
    assert "Integration algorithms" in document
    assert "Gaussian fit" in document
    session.comparison = None
    document = report.build_html(session, sections=("summary", "algorithms"))
    assert "Integration algorithms" not in document


def test_the_indexed_lookups_report_what_the_walks_reported():
    """
    `_figures`, `_delta` and `_precision` are handed prebuilt indexes now:
    the counterpart of a row used to be found by walking the whole result
    set, once per row, once per component, once per algorithm. What the
    comparison says has to be exactly what it said.
    """
    from milq import compare as cm

    entries, method = _entries(), _method()
    comparison = compare_algorithms(entries, method)
    assert comparison is not None
    reference = comparison.reference

    for item in comparison.components:
        component = next(c for c in method.components if c.name == item.component)
        for algorithm in comparison.algorithms:
            results = comparison.results[algorithm]
            # the same figures, computed the slow way from the set itself
            rows = results.for_component(component.name)
            found = [r for r in rows if r.found]
            assert item.figures[algorithm].total == len(rows)
            assert item.figures[algorithm].found == len(found)

            walked = []
            for entry in cm._replicate_set(component, entries):
                row = results.get(entry.key, component.name)
                if row is not None and row.found:
                    walked.append(row.area)
            assert item.figures[algorithm].replicates == len(walked)

            if algorithm == reference:
                continue
            both = 0
            for row in comparison.results[reference].for_component(component.name):
                counterpart = results.get(row.sample_key, row.component)
                if row.found and counterpart is not None and counterpart.found:
                    both += 1
            assert item.deltas[algorithm].both == both


def test_a_component_missing_from_one_run_is_still_compared():
    """`.get(name, [])`: an absent key must read as no rows, not as a crash."""
    from milq import compare as cm

    delta = cm._delta("summation", [], {}, _method().components[0])
    assert delta.both == 0 and delta.median_percent is None
    assert delta.only_reference == 0 and delta.only_other == 0
