"""
Adding one injection to a batch of twenty-six reads one injection.

What is tested is the rule that makes that safe rather than the saving: a row
records the settings it was integrated under, and it is kept only while those
settings stand. So every test here ends the same way — the incremental set is
compared field by field against what a full run gives on the same data — and
the interesting cases are the ones where it is deliberately *not* identical: a
row the operator integrated by hand.

The channel counts its reads, which is how "one injection was read" is
measured here rather than asserted.
"""

from dataclasses import fields

import numpy as np
import pytest

from milq.components import Component, IntegrationParams
from milq.method import ProcessingMethod
from milq.quantify import (CHANGED, CHANGED_MANUAL, COMPONENT_GONE,
                                NEW_COMPONENT, NEW_SAMPLE, NOT_RECORDED,
                                SAMPLE_GONE, PeakResult, ResultsSet,
                                fingerprint, incremental_plan,
                                integrate_manually, process,
                                process_incremental)
from milq.samples import SampleEntry
from tests.test_matching import Channel, Sample

STEP = 14.6 / 60.0


def _gaussian(x, centre, sigma, height):
    return height * np.exp(-0.5 * ((x - centre) / sigma) ** 2)


class _Channel(Channel):
    """A channel that remembers how often it was asked for a chromatogram."""

    def __init__(self, *args, centre=6.4, height=20000.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.centre = centre
        self.height = height
        self.reads = 0

    def xic_range(self, mz_lo, mz_hi):
        self.reads += 1
        y = _gaussian(self.rt, self.centre, 0.2, self.height)
        y[y < 1] = 0
        return self.rt, y


def _entries(n=4):
    scans = int(round(12.0 / STEP))
    out = []
    for index in range(n):
        entry = SampleEntry(f"/d/S{index}.wiff", 0, f"S{index}")
        entry.sample = Sample([
            _Channel(1, 703.6, 100.0, 800.0, 0.0, 12.0, n=scans,
                     height=20000.0 + 1000.0 * index),
            _Channel(2, 811.7, 100.0, 900.0, 0.0, 12.0, n=scans,
                     centre=7.1, height=5000.0),
        ])
        out.append(entry)
    return out


def _method():
    method = ProcessingMethod()
    method.replace_all([
        Component("A", 703.6, 184.0, rt=6.4, rt_halfwidth=0.5),
        Component("B", 811.7, 184.0, rt=7.1, rt_halfwidth=0.5),
    ])
    return method


def _reads(entries):
    return sum(channel.reads for e in entries for channel in e.sample.channels)


#: what a row is compared on. The fingerprint is part of it — two rows that
#: hold the same numbers under different settings are not the same row.
_FIELDS = [f.name for f in fields(PeakResult)]


def _same(left: ResultsSet, right: ResultsSet, what: str = "") -> None:
    """Every row, in order, on every field."""
    assert len(left) == len(right), what
    for one, other in zip(left, right):
        for name in _FIELDS:
            a, b = getattr(one, name), getattr(other, name)
            assert a == b or (a != a and b != b), (
                f"{what}: {one.sample_name}/{one.component}.{name}: {a} != {b}")


# --------------------------------------------------------------------------- #
# the fingerprint
# --------------------------------------------------------------------------- #
def test_the_fingerprint_moves_with_what_changes_the_numbers():
    method = _method()
    component = method.components[0]
    before = fingerprint(component, method)
    assert before == fingerprint(component, method), "not stable"

    for field_name, value in (("rt_halfwidth", 0.8), ("tolerance", 0.05),
                              ("unit", "ppm"), ("fragment", 264.3),
                              ("rt", 6.6), ("precursor", 704.6)):
        was = getattr(component, field_name)
        setattr(component, field_name, value)
        assert fingerprint(component, method) != before, field_name
        setattr(component, field_name, was)
    assert fingerprint(component, method) == before


def test_a_label_is_not_part_of_the_fingerprint():
    """Renaming a group does not make the file worth reading again."""
    method = _method()
    component = method.components[0]
    before = fingerprint(component, method)
    component.group = "sphingomyelins"
    component.internal_standard = "B"
    component.min_response = 5000.0
    assert fingerprint(component, method) == before


def test_a_method_default_reaches_the_components_that_inherit_it():
    method = _method()
    inherits, overrides = method.components
    overrides.integration = IntegrationParams(smoothing=1.0)
    was = [fingerprint(c, method) for c in method.components]
    method.defaults.min_relative_height = 0.2
    now = [fingerprint(c, method) for c in method.components]
    assert now[0] != was[0], "the inheriting component did not move"
    assert now[1] == was[1], "the overriding component moved with the default"


# --------------------------------------------------------------------------- #
# keeping, integrating, dropping
# --------------------------------------------------------------------------- #
def test_adding_one_injection_integrates_only_that_one():
    entries, method = _entries(4), _method()
    first = process(entries[:3], method)
    added = _reads(entries)

    results, report = process_incremental(entries, method, first)
    assert report.kept == 6 and report.integrated == 2 and report.dropped == 0
    assert report.reasons == {NEW_SAMPLE: 2}
    assert _reads(entries) - added == 2, "more than the new injection was read"
    _same(results, process(entries, method), "one added")


def test_a_new_component_integrates_its_column_only():
    entries, method = _entries(3), _method()
    only_a = ProcessingMethod()
    only_a.replace_all([method.components[0]])
    first = process(entries, only_a)

    results, report = process_incremental(entries, method, first)
    assert report.kept == 3 and report.integrated == 3
    assert report.reasons == {NEW_COMPONENT: 3}
    _same(results, process(entries, method), "one component added")


def test_removing_an_injection_drops_its_rows_and_reads_nothing():
    entries, method = _entries(4), _method()
    first = process(entries, method)
    before = _reads(entries)

    results, report = process_incremental(entries[:3], method, first)
    assert report.kept == 6 and report.integrated == 0
    assert report.dropped == 2 and report.dropped_reasons == {SAMPLE_GONE: 2}
    assert _reads(entries) == before, "a file was read to drop a row"
    _same(results, process(entries[:3], method), "one removed")


def test_removing_a_component_drops_its_column():
    entries, method = _entries(3), _method()
    first = process(entries, method)
    method.replace_all(method.components[:1])

    results, report = process_incremental(entries, method, first)
    assert report.kept == 3 and report.integrated == 0
    assert report.dropped_reasons == {COMPONENT_GONE: 3}
    _same(results, process(entries, method), "one component removed")


def test_changing_one_window_re_integrates_that_component_only():
    entries, method = _entries(4), _method()
    first = process(entries, method)
    before = _reads(entries)

    method.components[0].rt_halfwidth = 0.9
    results, report = process_incremental(entries, method, first)
    assert report.kept == 4 and report.integrated == 4
    assert report.reasons == {CHANGED: 4}
    assert _reads(entries) - before == 4, "a component that did not change was read"
    assert {r.component for r in results if r.component == "A"} == {"A"}
    _same(results, process(entries, method), "one window widened")


def test_a_method_default_change_keeps_nothing():
    entries, method = _entries(4), _method()
    first = process(entries, method)

    method.defaults.min_relative_height = 0.3
    plan = incremental_plan(entries, method, first)
    assert plan.kept == 0 and plan.is_full and plan.kept_fraction == 0.0
    results, report = process_incremental(entries, method, first)
    assert report.is_full and report.integrated == 8
    _same(results, process(entries, method), "a default changed")


def test_a_row_that_does_not_say_what_it_was_integrated_under_is_redone():
    """A project saved before fingerprints existed reprocesses in full, once."""
    entries, method = _entries(3), _method()
    first = process(entries, method)
    for row in first:
        row.fingerprint = ""

    results, report = process_incremental(entries, method, first)
    assert report.is_full and report.reasons == {NOT_RECORDED: 6}
    _same(results, process(entries, method), "no fingerprints")
    # and the run it just did records them, so the next one keeps everything
    assert incremental_plan(entries, method, results).kept == 6


# --------------------------------------------------------------------------- #
# rows integrated by hand
# --------------------------------------------------------------------------- #
def test_a_hand_integrated_row_is_kept_as_it_is():
    entries, method = _entries(3), _method()
    first = process(entries, method)
    component = method.components[0]
    by_hand = integrate_manually(entries[1], component, method, 6.0, 6.8,
                                 first.get(entries[1].key, "A"))
    assert by_hand.manual and by_hand.area > 0
    area, boundaries = by_hand.area, (by_hand.start_rt, by_hand.end_rt)

    # something else changed, so the batch is reprocessed
    method.components[1].rt_halfwidth = 0.9
    results, report = process_incremental(entries, method, first)
    assert report.reintegrated_manual == 0
    kept = results.get(entries[1].key, "A")
    assert kept.manual and kept.area == area
    assert (kept.start_rt, kept.end_rt) == boundaries


def test_a_hand_integrated_row_on_a_changed_component_is_redone():
    entries, method = _entries(3), _method()
    first = process(entries, method)
    component = method.components[0]
    by_hand = integrate_manually(entries[1], component, method, 6.0, 6.8,
                                 first.get(entries[1].key, "A"))
    assert by_hand.manual

    component.rt_halfwidth = 0.9
    results, report = process_incremental(entries, method, first)
    assert report.reintegrated_manual == 1
    assert report.reasons == {CHANGED: 2, CHANGED_MANUAL: 1}
    assert CHANGED_MANUAL in report.why()
    redone = results.get(entries[1].key, "A")
    assert not redone.manual, "the boundary nobody chose was kept"
    _same(results, process(entries, method), "a manual row on a changed component")


def test_a_manual_row_is_why_the_set_may_differ_from_a_full_run():
    """The one exception, stated: a full run overwrites it, this does not."""
    entries, method = _entries(3), _method()
    first = process(entries, method)
    integrate_manually(entries[1], method.components[0], method, 6.0, 6.8,
                       first.get(entries[1].key, "A"))
    method.components[1].rt_halfwidth = 0.9

    results, _report = process_incremental(entries, method, first)
    full = process(entries, method)
    with pytest.raises(AssertionError):
        _same(results, full, "manual kept")
    # every other row still agrees
    for one, other in zip(results, full):
        if one.manual:
            continue
        assert one.area == other.area and one.fingerprint == other.fingerprint


# --------------------------------------------------------------------------- #
# identity, and what the report says
# --------------------------------------------------------------------------- #
def test_nothing_changed_keeps_everything_and_reads_nothing():
    entries, method = _entries(4), _method()
    first = process(entries, method)
    before = _reads(entries)

    results, report = process_incremental(entries, method, first)
    assert report.kept == 8 and report.integrated == 0 and report.dropped == 0
    assert _reads(entries) == before
    assert report.kept_fraction == 1.0
    _same(results, first, "nothing changed")
    _same(results, process(entries, method), "nothing changed, against a full run")


def test_the_plan_costs_nothing_and_agrees_with_the_run():
    entries, method = _entries(4), _method()
    first = process(entries[:3], method)
    method.components[0].rt_halfwidth = 0.9
    before = _reads(entries)

    plan = incremental_plan(entries, method, first)
    assert _reads(entries) == before, "planning opened a file"
    results, report = process_incremental(entries, method, first)
    assert (plan.kept, plan.integrated, plan.dropped) == (
        report.kept, report.integrated, report.dropped)
    assert plan.reasons == report.reasons
    _same(results, process(entries, method), "planned")


def test_the_report_reads_as_one_line():
    entries, method = _entries(4), _method()
    first = process(entries[:3], method)
    _results, report = process_incremental(entries, method, first)
    assert report.summary().startswith("6 kept, 2 integrated")
    assert report.why() == f"2 — {NEW_SAMPLE}"


def test_a_rename_is_written_on_the_kept_row_rather_than_read_again():
    entries, method = _entries(3), _method()
    first = process(entries, method)
    before = _reads(entries)
    entries[0].name = "blank 01"
    method.components[0].group = "sphingomyelins"

    results, report = process_incremental(entries, method, first)
    assert report.kept == 6 and _reads(entries) == before
    assert results.get(entries[0].key, "A").sample_name == "blank 01"
    assert results.get(entries[0].key, "A").group == "sphingomyelins"
    _same(results, process(entries, method), "renamed")


def test_a_cancelled_run_leaves_the_old_rows_and_is_finished_by_the_next():
    entries, method = _entries(4), _method()
    first = process(entries, method)
    method.components[0].rt_halfwidth = 0.9

    stop_after = 2

    def progress(done, _total):
        return done < stop_after

    partial, report = process_incremental(entries, method, first,
                                          progress=progress)
    assert report.cancelled and report.integrated == stop_after
    assert report.pending == 4 - stop_after
    assert len(partial) == len(first)

    results, again = process_incremental(entries, method, partial)
    assert not again.cancelled and again.integrated == 4 - stop_after
    _same(results, process(entries, method), "resumed")


# --------------------------------------------------------------------------- #
# the Process button
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets

    from milq.ui import style

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.apply(app)
    yield app


@pytest.fixture
def workspace(qapp):
    from milq.session import Session
    from milq.ui.analytics import AnalyticsWorkspace

    session = Session()
    method = _method()
    session.set_components(method.components)
    session.entries = _entries(4)
    widget = AnalyticsWorkspace(session)
    yield widget
    widget.close()


def _select(workspace, name: str) -> bool:
    """Pick a component in the tree, as clicking it does."""
    from PyQt6 import QtWidgets

    from milq.ui.analytics import ROLE_NAME

    it = QtWidgets.QTreeWidgetItemIterator(workspace.component_tree)
    while it.value():
        if it.value().data(0, ROLE_NAME) == name:
            workspace.component_tree.setCurrentItem(it.value())
            return True
        it += 1
    return False


def test_the_first_press_is_a_full_run_and_the_second_keeps_everything(workspace):
    from milq import audit

    session = workspace.session
    workspace.process_batch()
    assert len(session.audit.of(audit.PROCESSED)) == 1
    assert len(session.audit.of(audit.REPROCESSED)) == 0
    first = [(r.sample_key, r.component, r.area) for r in session.results]

    workspace.process_batch()
    entries = session.audit.of(audit.REPROCESSED)
    assert len(entries) == 1
    assert entries[0].target == "the batch, incrementally"
    assert entries[0].after.startswith("8 kept, 0 integrated")
    assert entries[0].note == "nothing had changed"
    assert [(r.sample_key, r.component, r.area) for r in session.results] == first
    assert workspace.status.text().startswith("8 kept, 0 integrated")


def test_the_status_line_names_what_was_kept_and_what_was_read(workspace):
    session = workspace.session
    every = session.entries
    session.entries = every[:3]
    workspace.process_batch()
    session.entries = every
    workspace.process_batch()
    assert workspace.status.text().startswith("6 kept, 2 integrated")


def test_a_method_default_sends_the_button_back_to_a_full_run(workspace):
    from milq import audit

    session = workspace.session
    workspace.process_batch()
    session.method.defaults.min_relative_height = 0.3
    session.notify_method_changed()
    workspace.process_batch()
    assert len(session.audit.of(audit.PROCESSED)) == 2, "not a full run"
    assert len(session.audit.of(audit.REPROCESSED)) == 0
    assert "every row from the files" in session.audit.of(audit.PROCESSED)[1].note


def test_reprocess_all_redoes_a_hand_integrated_row(workspace, monkeypatch):
    from PyQt6 import QtWidgets

    session = workspace.session
    workspace.process_batch()
    assert _select(workspace, "A")
    workspace._on_manual_range(session.entries[1].key, 6.0, 6.8)
    assert session.results.get(session.entries[1].key, "A").manual

    asked = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        lambda *args, **kwargs: asked.append(args[1])
        or QtWidgets.QMessageBox.StandardButton.Yes)
    workspace.reprocess_all()
    assert asked == ["Reprocess all"], "the manual rows were not asked about"
    assert not session.results.get(session.entries[1].key, "A").manual


def test_reprocess_all_can_be_cancelled_and_changes_nothing(workspace, monkeypatch):
    from PyQt6 import QtWidgets

    session = workspace.session
    workspace.process_batch()
    assert _select(workspace, "A")
    workspace._on_manual_range(session.entries[1].key, 6.0, 6.8)
    area = session.results.get(session.entries[1].key, "A").area
    assert session.results.get(session.entries[1].key, "A").manual

    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.Cancel)
    workspace.reprocess_all()
    row = session.results.get(session.entries[1].key, "A")
    assert row.manual and row.area == area
