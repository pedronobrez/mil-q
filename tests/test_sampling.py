"""
Points per peak: the one thing three other findings kept running into.

The count is made at integration and carried on the row, so the report is
arithmetic over results rather than a second pass over the files; the cycle
comes from the channel's own time axis. What is tested is that the count is
what it says, that rows from before it existed are left out and said so,
and that the recommended cycle times follow from the width.
"""

import numpy as np
import pytest

from milq import processing as pr
from milq.components import Component
from milq.method import ProcessingMethod
from milq.quantify import integrate_component, process
from milq.samples import SampleEntry
from milq.sampling import (BASE_IN_FWHM, BASE_POINTS, FIT_IN_FWHM,
                                sampling_report)
from tests.test_matching import Channel, Sample

STEP = 14.6 / 60.0


def _gaussian(x, centre, sigma, height):
    return height * np.exp(-0.5 * ((x - centre) / sigma) ** 2)


class _Channel(Channel):
    def __init__(self, *args, sigma=0.2, **kwargs):
        super().__init__(*args, **kwargs)
        self.sigma = sigma

    def xic_range(self, mz_lo, mz_hi):
        y = _gaussian(self.rt, 6.4, self.sigma, 20000.0)
        y[y < 1] = 0
        return self.rt, y


def _entries(n=4, sigma=0.2):
    scans = int(round(12.0 / STEP))
    out = []
    for i in range(n):
        entry = SampleEntry(f"/d/S{i}.wiff", 0, f"S{i}")
        entry.sample = Sample([_Channel(1, 703.6, 100.0, 800.0, 0.0, 12.0,
                                        n=scans, sigma=sigma)])
        out.append(entry)
    return out


def _method():
    method = ProcessingMethod()
    method.replace_all([Component("A", 703.6, 184.0, rt=6.4, rt_halfwidth=0.5)])
    return method


def test_the_count_is_the_points_on_the_peak_not_its_feet():
    y = np.array([0.0, 0.0, 44.0, 52112.0, 98.0, 0.0, 0.0])
    assert pr.points_on_peak(y) == 1
    y = np.array([0.0, 500.0, 9000.0, 3000.0, 0.0])
    assert pr.points_on_peak(y) == 3
    assert pr.points_on_peak(np.zeros(5)) == 0


def test_every_algorithm_carries_the_count_onto_the_row():
    entries, method = _entries(1), _method()
    for algorithm in pr.ALGORITHMS:
        method.defaults.algorithm = algorithm
        row = integrate_component(entries[0], method.components[0], method)
        assert row.found and row.points is not None
        # summation's boundaries are the window's own ends, which become the
        # baseline and so count for nothing: a four-scan window leaves two
        wanted = 2 if algorithm == pr.ALGORITHM_SUMMATION else 3
        assert row.points >= wanted, algorithm


def test_the_report_measures_cycle_width_and_points():
    entries, method = _entries(), _method()
    results = process(entries, method)
    report = sampling_report(results, entries, method)
    assert report.note == ""
    row = report.rows[0]
    assert row.found == 4
    assert row.cycle == pytest.approx(15.0, abs=0.2)   # 49 scans over 12 min
    # a Gaussian of sigma 0.2 min is 28 s wide at half height, and a width
    # read off points 15 s apart is a multiple of 15: one or two steps
    assert 15.0 - 0.2 <= row.width <= 30.0 + 0.2
    assert row.points >= 3 and row.sparse == 0 and not row.too_sparse
    assert row.cycle_for_fit == pytest.approx(row.width * FIT_IN_FWHM)
    assert row.cycle_for_base == pytest.approx(row.width * BASE_IN_FWHM / BASE_POINTS)
    assert "point(s) on the peak" in report.summary()


def test_a_peak_narrower_than_the_sampling_is_called_sparse():
    entries, method = _entries(sigma=0.04), _method()
    results = process(entries, method)
    report = sampling_report(results, entries, method)
    row = report.rows[0]
    assert row.found == 4 and row.points < 3 and row.too_sparse
    assert row.sparse == 4 and row.sparse_share == 1.0
    assert report.sparse == [row]
    assert "under the 3 a fit needs" in report.summary()
    # one point above half height: the width is a bound, and said to be
    assert row.unmeasured == 4 and report.unmeasured == 4
    assert row.width is None and row.cycle_for_fit is None
    assert "narrower than one cycle" in report.summary()


def test_rows_from_before_the_count_are_left_out_and_said():
    entries, method = _entries(), _method()
    results = process(entries, method)
    for row in results:
        row.points = None
    report = sampling_report(results, entries, method)
    assert report.measured == [] and "process it again" in report.note
    assert report.summary() == report.note
    results.results[0].points = 4
    report = sampling_report(results, entries, method)
    assert report.rows[0].found == 4 and report.rows[0].points == 4


def test_no_results_is_said_rather_than_reported_as_zero():
    from milq.quantify import ResultsSet
    report = sampling_report(ResultsSet(), _entries(), _method())
    assert "process the batch" in report.note
    assert report.median_cycle is None and report.median_points is None


def test_the_report_section_and_the_qc_tab_show_it(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq import report
    from milq.session import Session
    from milq.ui.qc_panel import QualityPanel

    entries, method = _entries(sigma=0.04), _method()
    session = Session()
    session.entries = entries
    session.method = method
    session.results = process(entries, method)
    document = report.build_html(session, sections=("sampling",))
    assert "Sampling" in document and "Cycle for a fit" in document
    panel = QualityPanel(session)
    panel.reload()
    assert panel.sampling.rowCount() == 1
    assert panel.sampling.item(0, 4).text() in ("1", "2")
    assert "fewer than three points" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


def test_the_cycle_memo_answers_what_the_plain_measurement_answered():
    """
    The cycle belongs to the channel, so it is measured once per channel and
    not once per component. The memo must not change the answer, and a second
    component on the same channel must get the same number.
    """
    from milq.sampling import _cycle

    entries, method = _entries(3), _method()
    component = method.components[0]
    plain = _cycle(entries, component)
    memo: dict = {}
    first = _cycle(entries, component, memo)
    second = _cycle(entries, component, memo)
    assert plain == first == second
    assert len(memo) == 1                      # measured once, not three times


def test_a_component_no_channel_serves_still_reports_no_cycle():
    from milq.components import Component
    from milq.sampling import _cycle

    stranger = Component("Z", 1234.5, 99.0, rt=6.4, rt_halfwidth=0.5)
    memo: dict = {}
    assert _cycle(_entries(2), stranger, memo) is None
    assert memo == {}


def test_the_report_reads_the_same_with_the_index_as_without():
    """`by_component` replaced a filter of the whole list per component."""
    entries, method = _entries(3), _method()
    results = process(entries, method)
    report = sampling_report(results, entries, method)
    for row in report.rows:
        rows = [r for r in results.for_component(row.component) if r.found]
        assert row.found == len(rows)
    assert results.by_component()["A"] == results.for_component("A")
