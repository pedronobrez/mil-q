"""
Two batches side by side.

A sparse batch and a well-sampled one of the same method: the comparison
has to see more points and a tighter %CV on the second, match components
by name, list the ones only one method has, and read a reference from its
project file without opening a raw file.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.batches import (BatchSnapshot, compare_batches, read_project,  # noqa: E402
                               snapshot, write_csv)
from milq.components import Component  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.quantify import process  # noqa: E402
from milq.samples import UNKNOWN, SampleEntry  # noqa: E402
from tests.test_matching import Sample  # noqa: E402
from tests.test_sampling import _Channel  # noqa: E402

STEP = 14.6 / 60.0


def _entries(n, sigma, phase_step):
    scans = int(round(12.0 / STEP))
    out = []
    for i in range(n):
        entry = SampleEntry(f"/d/S{i}.wiff", 0, f"S{i}", UNKNOWN)
        channel = _Channel(1, 703.6, 100.0, 800.0, 0.0, 12.0, n=scans, sigma=sigma)
        channel.rt = channel.rt + phase_step * i
        entry.sample = Sample([channel])
        out.append(entry)
    return out


def _method(extra=False):
    method = ProcessingMethod()
    components = [Component("IS", 703.6, 184.0, rt=6.4, rt_halfwidth=0.5,
                            is_internal_standard=True)]
    if extra:
        components.append(Component("added", 703.6, 190.0, rt=6.4, rt_halfwidth=0.5))
    method.replace_all(components)
    return method


def _batch(name, sigma, n=6, extra=False):
    entries = _entries(n, sigma, phase_step=STEP / n)
    method = _method(extra)
    return BatchSnapshot(name, method, entries, process(entries, method))


def test_a_better_sampled_batch_shows_more_points_and_a_tighter_cv():
    reference = _batch("sparse", sigma=0.04)
    current = _batch("scheduled", sigma=0.2)
    comparison = compare_batches(current, reference)
    assert comparison.reference == "sparse" and comparison.current == "scheduled"
    row = comparison.rows[0]
    assert row.component == "IS" and row.is_internal_standard
    assert row.reference.found == 6 and row.current.found == 6
    assert row.current.median_points > row.reference.median_points
    assert row.points_change > 0
    assert row.reference.precision is not None and row.current.precision is not None
    assert row.precision_change < 0
    ref, cur = comparison.totals()
    assert cur["median_points"] > ref["median_points"]
    assert "median points on the peak" in comparison.summary()


def test_components_are_matched_by_name_and_the_rest_listed():
    reference = _batch("old", sigma=0.2)
    current = _batch("new", sigma=0.2, extra=True)
    comparison = compare_batches(current, reference)
    assert [row.component for row in comparison.rows] == ["IS"]
    assert comparison.only_current == ["added"] and comparison.only_reference == []
    assert "1 only in the current" in comparison.summary()


def test_a_moved_area_is_marked_and_a_steady_one_is_not():
    reference = _batch("a", sigma=0.2)
    current = _batch("b", sigma=0.2)
    steady = compare_batches(current, reference).rows[0]
    assert abs(steady.area_change) < 1.0 and not steady.moved
    for row in current.results:
        row.area *= 2
    doubled = compare_batches(current, reference).rows[0]
    assert doubled.area_change == pytest.approx(100.0, abs=1.0) and doubled.moved


def test_a_reference_is_read_from_its_project_without_the_raw_files(tmp_path):
    from PyQt6 import QtWidgets
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.session import Session

    batch = _batch("saved", sigma=0.2)
    session = Session()
    session.entries = batch.entries
    session.method = batch.method
    session.results = batch.results
    path = tmp_path / "saved.oqproj"
    session.save_project(str(path))
    reference = read_project(path)
    assert reference.name == "saved" and reference.injections == 6
    assert not any(entry.is_loaded for entry in reference.entries)
    assert len(reference.results) == 6
    current = snapshot(session)
    comparison = compare_batches(current, reference)
    assert comparison.rows[0].area_change == pytest.approx(0.0, abs=1e-9)


def test_the_csv_carries_every_row(tmp_path):
    comparison = compare_batches(_batch("b", 0.2), _batch("a", 0.04))
    write_csv(comparison, tmp_path / "c.csv")
    lines = (tmp_path / "c.csv").read_text().splitlines()
    assert lines[0].startswith("Component,Internal standard")
    assert len(lines) == 2 and lines[1].startswith("IS,yes,")


def test_the_dialog_shows_the_totals_and_the_rows():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.ui.batches_dialog import BatchesDialog

    comparison = compare_batches(_batch("b", 0.2), _batch("a", 0.04))
    dialog = BatchesDialog(comparison)
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "IS (IS)"
    assert "against" in dialog.windowTitle()
    dialog.close()
    app.processEvents()


def test_the_report_carries_the_comparison_only_while_it_stands():
    from PyQt6 import QtWidgets
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq import report
    from milq.session import Session

    current, reference = _batch("b", 0.2), _batch("a", 0.04)
    session = Session()
    session.entries, session.method, session.results = (
        current.entries, current.method, current.results)
    assert "Batch comparison" not in report.build_html(session, sections=("batches",))
    session.batch_comparison = compare_batches(current, reference)
    document = report.build_html(session, sections=("batches",))
    assert "Batch comparison" in document and "IS (IS)" in document
    assert "Median points on the peak" in document
