"""
The acquisition schedule a method implies, and what a target cycle buys.

The arithmetic is short; what matters is that concurrency is counted at
the busiest moment and not summed over the run, that a target the busiest
moment cannot meet is said to be unreachable with the cycle that could be,
that components without a time are left out and named, and that the
starting cycle carries its provenance — including that it is a bound when
the batch's peaks were narrower than a cycle.
"""

import csv
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.components import Component  # noqa: E402
from milq.health import WARNING, check_method  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.sampling import ComponentSampling, SamplingReport  # noqa: E402
from milq.schedule import (CSV_HEADER, build_schedule, suggested_cycle,  # noqa: E402
                                write_csv)
from milq.samples import SampleEntry  # noqa: E402
from tests.test_matching import Channel, Sample  # noqa: E402


def _method():
    method = ProcessingMethod()
    method.replace_all([
        Component("A", 700.0, 184.0, rt=5.0, rt_halfwidth=0.5),
        Component("B", 702.0, 184.0, rt=5.3, rt_halfwidth=0.5),
        Component("C", 704.0, 184.0, rt=5.6, rt_halfwidth=0.5),
        Component("D", 706.0, 184.0, rt=9.0, rt_halfwidth=0.5),
        Component("E", 708.0, None, rt=9.2, rt_halfwidth=0.5, is_internal_standard=True),
        Component("F", 710.0, 184.0),                        # no time
    ])
    return method


def test_the_busiest_moment_is_counted_not_the_whole_run():
    schedule = build_schedule(_method(), target_cycle=1.0)
    assert [slot.component for slot in schedule.slots] == ["A", "B", "C", "D", "E"]
    assert schedule.unscheduled == ["F"]
    # A, B and C overlap between 5.1 and 5.5; D and E between 8.7 and 9.5
    assert schedule.busiest == 3
    assert schedule.busiest_at == pytest.approx(5.1)
    profile = dict(schedule.concurrency())
    assert profile[5.5] == 2 and profile[6.1] == 0


def test_the_target_cycle_gives_the_dwell_and_the_floor_gives_the_cycle():
    schedule = build_schedule(_method(), target_cycle=0.3, pause_ms=5.0,
                              min_dwell_ms=5.0)
    assert schedule.dwell_ms == pytest.approx(300.0 / 3 - 5.0)
    assert schedule.feasible
    tight = build_schedule(_method(), target_cycle=0.024, pause_ms=5.0,
                           min_dwell_ms=5.0)
    assert tight.dwell_ms == pytest.approx(3.0)
    assert not tight.feasible
    assert tight.achievable_cycle == pytest.approx(0.03)
    assert "under the 5 ms floor" in tight.summary()
    assert "shortest cycle is 0.0 s" in tight.summary() or "0.0 s" in tight.summary()


def test_a_component_without_a_fragment_is_written_with_its_precursor():
    schedule = build_schedule(_method(), target_cycle=1.0)
    e = next(slot for slot in schedule.slots if slot.component == "E")
    assert e.fragment == e.precursor and e.is_internal_standard


def test_nothing_to_schedule_says_why():
    method = ProcessingMethod()
    method.replace_all([Component("F", 710.0, 184.0)])
    schedule = build_schedule(method, target_cycle=1.0)
    assert not schedule.slots and schedule.dwell_ms is None
    assert "no component has a retention time" in schedule.summary()


def test_the_csv_carries_one_row_per_transition(tmp_path):
    schedule = build_schedule(_method(), target_cycle=0.3)
    path = write_csv(schedule, tmp_path / "s.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == CSV_HEADER
    assert len(rows) == 6
    a = rows[1]
    assert a[0] == "A" and a[2] == "700.0000" and a[3] == "184.0000"
    assert a[4] == "5.00" and a[5] == "4.50" and a[6] == "5.50"
    assert float(a[7]) == pytest.approx(95.0)
    assert rows[5][8] == "yes"


def _sampling(width, unmeasured=0):
    return SamplingReport(rows=[ComponentSampling(
        "A", False, 10, cycle=14.6, width=width, points=2.0, sparse=8,
        unmeasured=unmeasured)])


def test_the_starting_cycle_comes_from_the_measured_width_and_says_so():
    cycle, note = suggested_cycle(_sampling(20.0))
    assert cycle == pytest.approx(20.0 * 2.0 / 2.3548)
    assert "3 points on the flanks" in note and "20.0 s wide" in note
    assert "upper bound" not in note
    ten, note = suggested_cycle(_sampling(20.0), points=10)
    assert ten == pytest.approx(20.0 * (4.0 / 2.3548) / 10)
    assert "10 points across the base" in note


def test_a_bounded_width_gives_a_cycle_called_an_upper_bound():
    cycle, note = suggested_cycle(_sampling(14.6, unmeasured=2206))
    assert cycle is not None
    assert "upper bound" in note and "2,206" in note
    none, note = suggested_cycle(None)
    assert none is None and "Sampling" in note


# --------------------------------------------------------------------------- #
# the survey-range check
# --------------------------------------------------------------------------- #
def _entry_with(channels):
    entry = SampleEntry("/d/x.wiff", 0, "x")
    entry.sample = Sample(channels)
    return entry


def test_check_method_names_the_precursors_no_survey_covers():
    method = ProcessingMethod()
    method.replace_all([
        Component("in", 600.0, 184.0, rt=5.0),
        Component("out", 806.0, 184.0, rt=5.0),
    ])
    entry = _entry_with([Channel(0, None, 50.0, 700.0, 0.0, 12.0),
                         Channel(1, 600.0, 100.0, 700.0, 0.0, 12.0),
                         Channel(2, 806.0, 100.0, 900.0, 0.0, 12.0)])
    health = check_method(method, [entry])
    finding = next(f for f in health.findings
                   if f.check == "precursor outside the survey scan")
    assert finding.severity == WARNING
    assert finding.components == ["out"]
    assert "50–700" in finding.detail


def test_an_acquisition_without_a_survey_is_a_skipped_check_not_a_finding():
    method = ProcessingMethod()
    method.replace_all([Component("a", 600.0, 184.0, rt=5.0)])
    entry = _entry_with([Channel(1, 600.0, 100.0, 700.0, 0.0, 12.0)])
    health = check_method(method, [entry])
    assert not any(f.check == "precursor outside the survey scan"
                   for f in health.findings)
    assert any("no survey scan" in note for note in health.skipped)


def test_the_dialog_builds_and_rebuilds_on_the_cycle():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.session import Session
    from milq.ui.schedule_dialog import ScheduleDialog

    session = Session()
    session.method = _method()
    dialog = ScheduleDialog(session)
    assert dialog.table.rowCount() == 5
    assert "Sampling" in dialog.basis.text()          # nothing measured yet
    dialog.cycle.setValue(0.3)
    assert dialog.table.item(0, 6).text() == "95.0"
    # the cycle spin resolves a tenth of a second, so the unreachable case is
    # made by raising the floor rather than by shrinking the cycle
    dialog.cycle.setValue(0.1)
    dialog.floor.setValue(40.0)
    assert "under the 40 ms floor" in dialog.summary.text()
    dialog.close()
    app.processEvents()
