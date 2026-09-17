"""
The Infusions tab: every infused compound on one row.

A summary of many is a different claim from a report of one, and the thing
worth testing is what it does with what is *not* there. A precursor
fragmented away, a compound the method has no formula for, no library of
one's own, an infusion with nothing to compare against — every one of those
is a cell, and the rule is that a cell says why rather than being blank. So
most of what follows builds a batch with one thing missing and reads the cell
back.

The rest is the shape: the rows and their grouping, the summary line's
counts, the CSV, the report section standing only while a summary does, and
the panel itself offscreen.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import audit, infusion_report as ir  # noqa: E402
from milq import report as batch_report  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.library import (SpectralLibrary,  # noqa: E402
                               entry_from_spectrum)
from milq.precursor import MIN_INTENSITY  # noqa: E402
from milq.session import Session  # noqa: E402
from tests.test_infusion_report import (ADDUCT, FORMULA, _entry,  # noqa: E402
                                        _ions)


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _session(*entries) -> Session:
    session = Session()
    session.entries.extend(entries)
    return session


def _with_component(session, name="TESTOL", formula=FORMULA, adduct=ADDUCT):
    """The method saying what the compound is made of, which is what lets a
    summary explain a spectrum with nobody at the LIPID MAPS tab."""
    session.method.replace_all([
        Component(name=name, precursor=_ions()[0], formula=formula,
                  adduct=adduct)])
    return session


def _own_library(entry, channel, name="Testol reference", energy=45.0):
    """A record of one's own, made from the infusion it will be searched by
    — which is what an analyst's library of infused standards actually is."""
    from milq.processing import centroid_spectrum

    mz, intensity = channel.spectrum_rt_range(0.0, 1.5)
    cmz, cit = centroid_spectrum(mz, intensity)
    record = entry_from_spectrum(name, cmz, cit,
                                 precursor=channel.info.precursor,
                                 precursor_type=ADDUCT, formula=FORMULA,
                                 collision_energy=energy)
    return SpectralLibrary([record], path="/d/own.msp")


# --------------------------------------------------------------------------- #
# the rows
# --------------------------------------------------------------------------- #
def test_one_row_per_infusion_grouped_by_compound(qapp):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="TESTOL_infusion_B")
    third, _c3 = _entry(name="OTHEROL_infusion", stray_only=True)
    summary = ir.summarise(_session(first, second, third))

    assert len(summary) == 3
    assert summary.compounds == ["TESTOL", "OTHEROL"]
    # grouped: the two TESTOL rows are together and before OTHEROL
    assert [row.compound for row in summary.rows] == [
        "TESTOL", "TESTOL", "OTHEROL"]
    row = summary.rows[0]
    assert row.sample == "TESTOL_infusion_A"
    assert row.report.scans == 160
    assert row.report.base_peak()[0] == pytest.approx(_ions()[0], abs=0.01)
    assert "Positive" in row.mode


def test_a_sample_that_is_not_an_infusion_is_not_a_row(qapp):
    """The tab is of infusions; a chromatographic run has no average of a
    whole run worth putting on a row."""
    from milq.samples import SampleEntry
    from tests.test_infusion import gradient_sample

    entry, _channel = _entry(name="TESTOL_infusion_A")
    other = SampleEntry("/d/gradient.wiff", 0, "GRADIENT_run")
    other.sample = gradient_sample()
    summary = ir.summarise(_session(entry, other))

    assert [row.sample for row in summary.rows] == ["TESTOL_infusion_A"]


def test_nothing_open_says_so_rather_than_showing_an_empty_table(qapp):
    summary = ir.summarise(_session())

    assert not len(summary)
    assert "No open sample reads as a direct infusion" in summary.summary()


# --------------------------------------------------------------------------- #
# the precursor
# --------------------------------------------------------------------------- #
def test_a_precursor_that_survives_is_measured_with_its_error(qapp):
    entry, _channel = _entry(survives=True)
    row = ir.summarise(_session(entry)).rows[0]
    cells = dict(zip(ir.SUMMARY_COLUMNS, row.cells()))

    assert row.confirmed
    assert row.found is not None
    assert float(cells["Found m/z"].replace(",", "")) == pytest.approx(
        _ions()[0], abs=0.01)
    assert cells["Δ ppm"].startswith(("+", "-"))
    assert float(cells["Height"].replace(",", "")) > MIN_INTENSITY


def test_a_precursor_fragmented_away_says_why_in_the_cell(qapp):
    entry, _channel = _entry(survives=False)
    row = ir.summarise(_session(entry)).rows[0]
    cells = dict(zip(ir.SUMMARY_COLUMNS, row.cells()))

    assert not row.confirmed
    assert row.found is None
    assert "counts survive" in cells["Found m/z"]
    assert cells["Δ ppm"] == "—"
    # the whole sentence is still on the report, for the tooltip and the page
    assert "too little of the precursor survives" in row.report.survivor_note


# --------------------------------------------------------------------------- #
# the fragments
# --------------------------------------------------------------------------- #
def test_the_method_s_formula_explains_the_spectrum_with_nobody_at_the_tab(qapp):
    entry, _channel = _entry()
    session = _with_component(_session(entry))
    row = ir.summarise(session).rows[0]
    cells = dict(zip(ir.SUMMARY_COLUMNS, row.cells()))

    assert row.report.explanation is not None
    assert " of " in cells["Ions found"]
    found, _of, predicted = cells["Ions found"].split()
    assert 0 < int(found) <= int(predicted)
    assert "from the component table" in row.report.basis


def test_an_explanation_already_run_is_used_rather_than_made_again(qapp):
    from tests.test_infusion_report import _explanation

    entry, channel = _entry()
    given = _explanation(entry, channel)
    summary = ir.summarise(_session(entry), explanations={"TESTOL": given})

    assert summary.rows[0].report.explanation is given
    assert summary.rows[0].report.basis == "what was run in the LIPID MAPS tab"


def test_a_compound_the_method_does_not_hold_says_so(qapp):
    entry, _channel = _entry()
    row = ir.summarise(_session(entry)).rows[0]
    cells = dict(zip(ir.SUMMARY_COLUMNS, row.cells()))

    assert row.report.explanation is None
    assert cells["Ions found"] == "TESTOL is not a component of the method"


def test_a_component_without_a_formula_says_that_instead(qapp):
    entry, _channel = _entry()
    session = _with_component(_session(entry), formula="")
    row = ir.summarise(session).rows[0]

    assert row.explanation_note == "TESTOL carries no formula"


def test_a_component_without_an_adduct_has_it_read_off_the_precursor(qapp):
    """The channel's written precursor and the formula name the adduct
    between them, so a component that declares none is still explained —
    and the basis says the number was read rather than declared."""
    entry, _channel = _entry()
    session = _with_component(_session(entry), adduct="")
    row = ir.summarise(session).rows[0]

    assert row.explanation_note == ""
    assert row.report.explanation is not None
    assert "read off the written precursor" in row.report.basis
    assert "[M+H]+" in row.report.basis


def test_a_precursor_no_adduct_of_the_formula_reaches_is_not_explained(qapp):
    """A formula that cannot make the written precursor under any adduct is
    the one case where nothing is the right answer: explaining it would
    predict every fragment from a molecule the quadrupole never isolated."""
    entry, _channel = _entry()
    session = _with_component(_session(entry), formula="C6H12O6", adduct="")
    row = ir.summarise(session).rows[0]

    assert row.report.explanation is None
    assert "none of the adducts of C6H12O6" in row.explanation_note


def test_an_adduct_the_precursor_contradicts_is_overruled_and_said_so(qapp):
    """The component table says [M+Na]+ and the channel's own number is the
    protonated molecule. The precursor wins, because it is what the
    instrument was given, and the basis carries both."""
    entry, _channel = _entry()
    session = _with_component(_session(entry), adduct="[M+Na]+")
    row = ir.summarise(session).rows[0]

    assert row.report.explanation is not None
    assert "not the [M+Na]+ the component table carries" in row.report.basis


# --------------------------------------------------------------------------- #
# the library of one's own
# --------------------------------------------------------------------------- #
def test_the_best_own_record_is_reported_with_both_scores(qapp):
    entry, channel = _entry(energy=12.0)
    library = _own_library(entry, channel, energy=45.0)
    row = ir.summarise(_session(entry), library=library).rows[0]
    cells = dict(zip(ir.SUMMARY_COLUMNS, row.cells()))

    assert cells["Library record"] == "Testol reference"
    # the record was made from this very spectrum, so it matches itself
    assert cells["Score"] == "100" and cells["Reverse"] == "100"
    assert " of " in cells["Matched"]
    # and the energies differ, which is the column that says a low score
    # elsewhere would be the energy rather than the compound
    assert cells["Record CE"] == "45 vs 12"


def test_no_library_set_says_so_in_every_row_and_in_the_line(qapp):
    entry, _channel = _entry()
    summary = ir.summarise(_session(entry))
    cells = dict(zip(ir.SUMMARY_COLUMNS, summary.rows[0].cells()))

    assert cells["Library record"] == "no library of your own is set"
    assert "no library of your own is set" in summary.summary()


def test_a_library_that_holds_nothing_matching_says_what_was_looked_for(qapp):
    entry, _channel = _entry()
    elsewhere = entry_from_spectrum("Otherol reference", [100.0, 200.0],
                                    [1.0, 0.5], precursor=999.9)
    library = SpectralLibrary([elsewhere], path="/d/own.msp")
    row = ir.summarise(_session(entry), library=library).rows[0]

    assert row.report.hit is None
    assert row.library_note.startswith("no record matched within ±")
    assert f"{_ions()[0]:g}" in row.library_note


# --------------------------------------------------------------------------- #
# the other infusions of the same compound
# --------------------------------------------------------------------------- #
def test_two_infusions_of_one_compound_are_scored_against_each_other(qapp):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="TESTOL_infusion_B")
    summary = ir.summarise(_session(first, second))

    for row, other in zip(summary.rows, reversed(summary.rows)):
        assert len(row.others) == 1
        label, score, reverse, matched, of_other = row.others[0]
        assert label == other.sample
        # the same spectrum twice: it matches itself exactly
        assert score == pytest.approx(1.0, abs=1e-6)
        assert reverse == pytest.approx(1.0, abs=1e-6)
        assert 0 < matched <= of_other
    cells = dict(zip(ir.SUMMARY_COLUMNS, summary.rows[0].cells()))
    assert cells["Other infusions"] == "TESTOL_infusion_B 100/100"


def test_the_only_infusion_of_a_compound_says_that_it_is(qapp):
    entry, _channel = _entry()
    row = ir.summarise(_session(entry)).rows[0]
    cells = dict(zip(ir.SUMMARY_COLUMNS, row.cells()))

    assert row.others == []
    assert cells["Other infusions"] == "the only infusion of this compound"


def test_infusions_of_different_compounds_are_not_compared(qapp):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="OTHEROL_infusion", stray_only=True)
    summary = ir.summarise(_session(first, second))

    assert all(not row.others for row in summary.rows)


# --------------------------------------------------------------------------- #
# the summary line
# --------------------------------------------------------------------------- #
def test_the_summary_line_counts_what_it_says_it_counts(qapp):
    first, channel = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="TESTOL_infusion_B", survives=False)
    library = _own_library(first, channel)
    session = _with_component(_session(first, second))
    summary = ir.summarise(session, library=library)

    line = summary.summary()
    assert "2 compound(s)" not in line          # one compound, two infusions
    assert line.startswith("1 compound(s) in 2 infusion(s)")
    assert f"1 of 2 precursor(s) confirmed within {ir.CONFIRMED_PPM:g} ppm" \
        in line
    assert "predicted ion(s) found across 2" in line
    assert (f"{len(summary.counted)} with an own record above "
            f"{ir.COUNTED_SCORE * 100:.0f} in own.msp") in line
    assert len(summary.confirmed) == 1


# --------------------------------------------------------------------------- #
# the CSV
# --------------------------------------------------------------------------- #
def test_the_csv_is_every_column_of_every_row(qapp, tmp_path):
    import csv

    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="OTHEROL_infusion", stray_only=True)
    summary = ir.summarise(_session(first, second))
    path = ir.write_summary_csv(summary, tmp_path / "infusions.csv")

    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == list(ir.SUMMARY_COLUMNS)
    assert len(rows) == 3
    assert rows[1][0] == "TESTOL" and rows[2][0] == "OTHEROL"
    assert all(len(row) == len(ir.SUMMARY_COLUMNS) for row in rows)
    # a reason, not a blank, wherever there is no number
    assert all(cell.strip() for row in rows[1:] for cell in row)


# --------------------------------------------------------------------------- #
# the report section
# --------------------------------------------------------------------------- #
def test_the_section_stands_only_while_a_summary_does(qapp):
    entry, _channel = _entry()
    session = _session(entry)

    assert "Infusions" not in batch_report.build_html(session)

    session.infusion_summary = ir.summarise(session)
    document = batch_report.build_html(session)
    assert "Infusions</h2>" in document
    assert "TESTOL" in document
    for heading in ir.REPORT_COLUMNS:
        assert heading in document, heading

    # and an empty summary is no summary: a table of nothing says less than
    # no table at all
    session.infusion_summary = ir.InfusionSummary(note="nothing open")
    assert "Infusions</h2>" not in batch_report.build_html(session)


def test_the_section_prints_the_reasons_too(qapp):
    entry, _channel = _entry(survives=False)
    session = _session(entry)
    session.infusion_summary = ir.summarise(session)
    document = batch_report.build_html(session)

    assert "counts survive" in document
    assert "no library of your own is set" in document
    assert "not a component of the method" in document


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #
def _panel(session):
    from milq.ui.infusions_panel import InfusionsPanel

    return InfusionsPanel(session)


def test_the_panel_measures_on_request_and_not_before(qapp):
    entry, _channel = _entry()
    session = _session(entry)
    panel = _panel(session)

    assert panel.table.rowCount() == 0
    assert session.infusion_summary is None
    assert "Not measured yet" in panel.status.text()
    assert not panel.btn_report.isEnabled()

    panel.measure(threaded=False)
    assert session.infusion_summary is not None
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 0).text() == "TESTOL"
    assert panel.btn_report.isEnabled() and panel.btn_csv.isEnabled()
    assert "1 compound(s) in 1 infusion(s)" in panel.status.text()

    panel.deleteLater()
    qapp.processEvents()


def test_the_tab_carries_the_row_count(qapp):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="OTHEROL_infusion", stray_only=True)
    session = _session(first, second)
    panel = _panel(session)
    seen: list[int] = []
    panel.sigRowsChanged.connect(seen.append)

    panel.measure(threaded=False)
    assert seen == [2]

    panel.deleteLater()
    qapp.processEvents()


def test_the_table_sorts_on_numbers_where_it_has_them(qapp):
    from PyQt6 import QtCore

    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="OTHEROL_infusion", stray_only=True)
    session = _session(first, second)
    panel = _panel(session)
    panel.measure(threaded=False)

    column = list(ir.SUMMARY_COLUMNS).index("Base peak m/z")
    panel.table.sortItems(column, QtCore.Qt.SortOrder.AscendingOrder)
    read = [float(panel.table.item(row, column).text().replace(",", ""))
            for row in range(panel.table.rowCount())]
    assert read == sorted(read)

    panel.deleteLater()
    qapp.processEvents()


def test_a_file_opened_or_closed_drops_the_measurement(qapp):
    entry, _channel = _entry()
    session = _session(entry)
    panel = _panel(session)
    panel.measure(threaded=False)
    assert panel.table.rowCount() == 1

    session.sigSamplesChanged.emit()
    assert session.infusion_summary is None
    assert panel.table.rowCount() == 0

    panel.deleteLater()
    qapp.processEvents()


def test_the_panel_writes_the_document_for_the_rows_chosen(qapp, tmp_path):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="TESTOL_infusion_B")
    session = _session(first, second)
    panel = _panel(session)
    panel.measure(threaded=False)

    path = panel.write_report(str(tmp_path / "infusions.pdf"))
    assert path and os.path.exists(path)
    with open(path, "rb") as handle:
        assert handle.read(5) == b"%PDF-"
    # nothing selected means every row, and the two are of one compound, so
    # each is drawn against the other
    assert all(len(row.report.compared) == 1
               for row in session.infusion_summary.rows)

    written = session.audit.of(audit.INFUSION_REPORT)
    assert len(written) == 1 and written[0].target == "TESTOL"
    assert "2 infusion(s)" in written[0].note

    panel.deleteLater()
    qapp.processEvents()


def test_one_row_selected_is_one_section_and_nothing_to_compare(qapp, tmp_path):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="TESTOL_infusion_B")
    session = _session(first, second)
    panel = _panel(session)
    panel.measure(threaded=False)
    panel.table.selectRow(0)

    chosen = panel.chosen()
    assert len(chosen) == 1
    reports = ir.prepare_documents(chosen)
    assert reports[0].compared == []
    document = ir.build_html(reports)
    assert "Other infusions of the same compound" not in document

    panel.deleteLater()
    qapp.processEvents()


def test_the_panel_exports_the_whole_table_not_the_selection(qapp, tmp_path):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="OTHEROL_infusion", stray_only=True)
    session = _session(first, second)
    panel = _panel(session)
    panel.measure(threaded=False)
    panel.table.selectRow(0)

    path = panel.export_csv(str(tmp_path / "infusions.csv"))
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert "TESTOL" in text and "OTHEROL" in text
    assert "2 row(s) written" in panel.status.text()

    panel.deleteLater()
    qapp.processEvents()


def test_the_panel_names_the_page_that_explains_it(qapp):
    from milq.manual import manual
    from milq.ui.help_window import help_page_for
    from milq.ui.infusions_panel import HELP_PAGE

    entry, _channel = _entry()
    panel = _panel(_session(entry))

    assert help_page_for(panel) == HELP_PAGE
    assert HELP_PAGE in manual().pages

    panel.deleteLater()
    qapp.processEvents()


def test_the_analytics_workspace_carries_the_tab(qapp):
    from milq.ui.analytics import AnalyticsWorkspace

    entry, _channel = _entry()
    session = _session(entry)
    workspace = AnalyticsWorkspace(session)
    titles = [workspace.bottom.tabText(i)
              for i in range(workspace.bottom.count())]

    assert "Infusions" in titles
    workspace.infusions.measure(threaded=False)
    assert workspace.bottom.tabText(workspace.infusions_tab) == "Infusions (1)"

    workspace.deleteLater()
    qapp.processEvents()


def test_nothing_is_measured_twice_for_one_spectrum(qapp):
    """
    Every infusion is averaged once.

    `report_for(others=…)` reads the other infusion's whole run again for
    every report that mentions it, which for three infusions of one compound
    is nine reads of three acquisitions. The summary scores them from the
    averages it already holds instead.
    """
    made = [_entry(name=f"TESTOL_infusion_{letter}") for letter in "ABC"]
    counted: dict[str, int] = {}
    for entry, channel in made:
        original = channel.spectrum_rt_range

        def read(*args, _name=entry.name, _call=original, **kwargs):
            counted[_name] = counted.get(_name, 0) + 1
            return _call(*args, **kwargs)

        channel.spectrum_rt_range = read
    summary = ir.summarise(_session(*(entry for entry, _c in made)))

    assert counted == {"TESTOL_infusion_A": 1, "TESTOL_infusion_B": 1,
                       "TESTOL_infusion_C": 1}
    assert all(len(row.others) == 2 for row in summary.rows)
    assert all(row.peaks for row in summary.rows)
    assert np.isclose(summary.rows[0].others[0][1], 1.0)

    # and the pictures, when a document is asked for, read nothing either
    ir.prepare_documents(summary.rows)
    assert set(counted.values()) == {1}
    assert all(len(row.report.compared) == 2 for row in summary.rows)
