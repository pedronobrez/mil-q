"""
Two days of infusions of the same standards, side by side.

The thing worth testing is the matching and the mark. A tray sprayed twice
is one row per compound *per set of conditions*, and a row that found the
reference's 12 eV spray for its 22 eV one would be a measurement of the
collision energy dressed up as a measurement of the vial — so most of what
follows builds two summaries that differ in one way and reads back which
rows were paired and which were left over.

The rest is the round trip. A reference is read out of a project file with
no raw file opened, which only works if the project saved the peaks as well
as the figures; a summary that came back with fewer peaks than it went in
with would score against itself at less than a hundred, and that is the
floor the first test measures.
"""

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import infusion_compare as ic  # noqa: E402
from milq import infusion_report as ir  # noqa: E402
from milq import report as batch_report  # noqa: E402
from milq.samples import SampleEntry, shorten_names  # noqa: E402
from milq.session import Session  # noqa: E402
from tests.test_infusion_report import (FakeChannel, FakeSample,  # noqa: E402
                                        STRAY, _grid, _ions)

IONS = _ions()
PRECURSOR = IONS[0]


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# --------------------------------------------------------------------------- #
# a tray of infusions
# --------------------------------------------------------------------------- #
def _peaks(scale: float = 1.0, other: bool = False) -> dict:
    """The compound's spectrum, optionally at another size or of something
    else entirely — a base peak somewhere the reference has nothing."""
    if other:
        return {STRAY: 20_000.0 * scale, IONS[1]: 300.0 * scale}
    return {IONS[1]: 4_000.0 * scale, IONS[2]: 2_000.0 * scale,
            STRAY: 900.0 * scale, PRECURSOR: 9_000.0 * scale}


def _infusion(name: str, energy: float = 22.0, scale: float = 1.0,
              other: bool = False, folder: str = "/d") -> SampleEntry:
    peaks = _peaks(scale, other)
    channel = FakeChannel(0, _grid(list(peaks)), peaks, precursor=PRECURSOR,
                          collision_energy=energy)
    entry = SampleEntry(os.path.join(folder, f"{name}.wiff"), 0, name)
    entry.sample = FakeSample([channel], name=name)
    return entry


def _summary(*entries) -> ir.InfusionSummary:
    session = Session()
    session.entries.extend(entries)
    return ir.summarise(session)


def _day(scale: float = 1.0, other: bool = False, which=("22", "12")):
    """One day's tray: cholic acid-d4 at 22 and 12 eV EAD."""
    made = []
    if "22" in which:
        made.append(_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1", energy=22.0,
                              scale=scale, other=other))
    if "12" in which:
        made.append(_infusion("CA-d4_TOFMSMS_EAD_12CE_mix1", energy=12.0,
                              scale=scale, other=other))
    return _summary(*made)


# --------------------------------------------------------------------------- #
# the floor of the measurement
# --------------------------------------------------------------------------- #
def test_a_tray_against_itself_scores_a_hundred_at_no_ppm(qapp):
    """The same acquisitions twice: every row paired, nothing moved."""
    comparison = ic.compare_infusions(_day(), _day())

    assert len(comparison.rows) == 2
    assert not comparison.only_reference and not comparison.only_current
    for row in comparison.rows:
        assert row.score == pytest.approx(1.0)
        assert row.reverse == pytest.approx(1.0)
        assert row.base_gap_ppm == pytest.approx(0.0, abs=1e-6)
        assert row.intensity_ratio == pytest.approx(1.0)
        assert row.same_base_peak and not row.moved
        assert row.matched == row.of_reference > 0
    assert comparison.median_score == pytest.approx(100.0)
    assert "0 marked as moved" in comparison.summary()


def test_the_rows_are_matched_by_compound_and_by_conditions(qapp):
    """A 22 eV spray finds the reference's 22 eV spray and not its 12 eV
    one — which is the whole reason the pairing is not by compound alone."""
    comparison = ic.compare_infusions(_day(which=("22",)), _day())

    assert len(comparison.rows) == 1
    row = comparison.rows[0]
    assert row.current.energy == 22.0 and row.reference.energy == 22.0
    assert row.conditions == "EAD 22 eV"
    assert [side.energy for side in comparison.only_reference] == [12.0]
    assert comparison.only_current == []


def test_a_compound_the_other_day_does_not_have_is_listed_alone(qapp):
    reference = _summary(_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1"))
    current = _summary(_infusion("TDCA-d4_TOFMSMS_EAD_22CE_mix1"))
    comparison = ic.compare_infusions(current, reference)

    assert comparison.rows == []
    assert [s.compound for s in comparison.only_reference] == ["CA-d4"]
    assert [s.compound for s in comparison.only_current] == ["TDCA-d4"]
    assert "only in the reference" in comparison.summary()


def test_an_energy_written_a_fraction_apart_is_the_same_setting(qapp):
    """Vendors write a nominal energy and a spread; a fifth of an
    electronvolt is one setting written twice."""
    reference = _summary(_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1", energy=22.0))
    current = _summary(_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1", energy=22.2))
    assert len(ic.compare_infusions(current, reference).rows) == 1

    apart = _summary(_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1", energy=24.0))
    assert ic.compare_infusions(apart, reference).rows == []


# --------------------------------------------------------------------------- #
# the mark
# --------------------------------------------------------------------------- #
def test_a_spray_at_half_the_height_still_looks_like_itself_and_is_marked(qapp):
    """The cosine is scale-free, so the score says the spectrum is the same
    and only the height says the standard is giving half of what it gave."""
    comparison = ic.compare_infusions(_day(scale=0.5), _day())

    for row in comparison.rows:
        assert row.score == pytest.approx(1.0)
        assert row.same_base_peak
        assert row.intensity_ratio == pytest.approx(0.5)
        assert row.intensity_change == pytest.approx(-50.0)
        assert row.moved and "past 20%" in row.why


def test_a_height_inside_the_limit_is_not_marked(qapp):
    comparison = ic.compare_infusions(_day(scale=0.9), _day())
    for row in comparison.rows:
        assert row.intensity_change == pytest.approx(-10.0)
        assert not row.moved and row.why == ""


def test_a_base_peak_somewhere_else_is_a_different_ion_and_not_a_drift(qapp):
    comparison = ic.compare_infusions(_day(other=True), _day())

    for row in comparison.rows:
        assert abs(row.base_gap_ppm) > ic.SAME_PEAK_PPM
        assert not row.same_base_peak
        assert row.moved and "says the same ion" in row.why
    assert comparison.same_ion == 0


def test_the_score_alone_never_marks_a_row(qapp):
    """A spectrum that has changed but kept its base peak's mass and size is
    reported and not marked: two days are two points, not a spread."""
    reference = _day(which=("22",))
    peaks = _peaks()
    peaks[IONS[2]] = 8_000.0                       # a fragment that has grown
    channel = FakeChannel(0, _grid(list(peaks)), peaks, precursor=PRECURSOR,
                          collision_energy=22.0)
    entry = SampleEntry("/d/CA-d4_TOFMSMS_EAD_22CE_mix1.wiff", 0,
                        "CA-d4_TOFMSMS_EAD_22CE_mix1")
    entry.sample = FakeSample([channel], name=entry.name)
    row = ic.compare_infusions(_summary(entry), reference).rows[0]

    assert row.score < 1.0
    assert row.same_base_peak and row.intensity_ratio == pytest.approx(1.0)
    assert not row.moved


# --------------------------------------------------------------------------- #
# what identifies an infusion
# --------------------------------------------------------------------------- #
def test_the_compound_is_read_from_the_file_and_not_from_the_short_name(qapp):
    """
    `samples.shorten_names` takes the prefix every open sample shares off
    the names it shows, so the same acquisition is called one thing beside
    two others and another thing beside one. Measured on the real folder,
    that made the compound *EAD* one day and *12CE* the next and nothing
    matched anything.
    """
    entries = [_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1"),
               _infusion("CA-d4_TOFMSMS_EAD_12CE_mix1", energy=12.0)]
    shorten_names(entries)
    # what the tab shows: these two share `CA-d4_TOFMSMS_EAD_`, so the
    # activation has gone out of the name along with the compound
    assert entries[0].name == "22CE_mix1"

    summary = _summary(*entries)
    assert summary.rows[0].compound == "22CE"      # and what it groups on
    sides = ic.sides_of(summary)
    assert [side.compound for side in sides] == ["CA-d4", "CA-d4"]
    assert [side.activation for side in sides] == ["EAD", "EAD"]

    # and so a day named one way still finds a day named the other
    other = [_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1")]
    shorten_names(other)
    comparison = ic.compare_infusions(_summary(*other), summary)
    assert len(comparison.rows) == 1
    assert comparison.rows[0].score == pytest.approx(1.0)


def test_an_activation_and_an_energy_are_read_from_a_name_when_asked():
    assert ic.activation_in("CA-d4_TOFMSMS_EAD_22CE_mix1.wiff") == "EAD"
    assert ic.activation_in("CA-d4_leader_mix1.wiff") == ""      # not "EAD"
    assert ic.energy_in("CA-d4_EAD_22CE_44DP_13KE_mix1") == 22.0
    assert ic.energy_in("CA-d4_45eV_mix1") == 45.0
    assert ic.energy_in("CA-d4_TOFMSMS_Mix1") is None


# --------------------------------------------------------------------------- #
# saved and read back
# --------------------------------------------------------------------------- #
def test_a_project_saves_the_figures_and_the_peaks_and_reads_them_back(
        qapp, tmp_path):
    entries = [_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1")]
    session = Session()
    session.entries.extend(entries)
    session.infusion_summary = ir.summarise(session)
    live = ic.sides_of(session.infusion_summary)[0]
    path = str(tmp_path / "reference.oqproj")
    session.save_project(path)

    written = json.loads(open(path, encoding="utf-8").read())
    assert written["version"] == 5                 # the key is additive
    assert written["infusions"]["format"] == ic.FORMAT

    stored = ic.read_summary(path)
    assert len(stored) == 1
    side = stored.rows[0]
    assert side.compound == "CA-d4" and side.activation == "EAD"
    assert side.energy == 22.0 and side.scans == live.scans
    assert side.peaks == live.peaks > 0
    assert side.base_mz == pytest.approx(live.base_mz)
    assert side.base_height == pytest.approx(live.base_height)
    assert np.allclose(side.mz, live.mz, atol=1e-5)
    assert np.allclose(side.intensity, live.intensity, atol=1e-6)
    # the round trip is exact enough to score a hundred against itself
    row = ic.compare_infusions(session.infusion_summary, stored).rows[0]
    assert row.score == pytest.approx(1.0, abs=1e-6)


def test_the_stored_peaks_are_relative_and_capped_as_a_record_is(qapp):
    peaks = [(100.0 + index, float(index + 1)) for index in range(400)]
    mz, intensity, top = ic.stored_peaks(peaks)
    assert mz.size == ic.STORED_PEAKS == 200
    assert top == 400.0
    assert intensity.max() == pytest.approx(1.0)
    assert intensity.min() >= ic.STORED_MIN_RELATIVE
    assert np.all(np.diff(mz) > 0)


def test_a_project_with_no_summary_holds_nothing_to_compare_against(
        qapp, tmp_path):
    path = str(tmp_path / "plain.oqproj")
    Session().save_project(path)
    assert "infusions" not in json.loads(open(path, encoding="utf-8").read())
    assert ic.read_summary(path) is None


def test_reopening_a_project_keeps_its_summary_through_the_next_save(
        qapp, tmp_path):
    session = Session()
    session.entries.extend([_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1")])
    session.infusion_summary = ir.summarise(session)
    path = str(tmp_path / "reference.oqproj")
    session.save_project(path)

    reopened = Session()
    reopened.load_project(path)       # the raw file is not there to reopen
    assert reopened.infusion_summary is None      # never restored as live
    assert len(reopened.infusion_stored) == 1

    again = str(tmp_path / "again.oqproj")
    reopened.save_project(again)
    assert len(ic.read_summary(again)) == 1


# --------------------------------------------------------------------------- #
# what comes off it
# --------------------------------------------------------------------------- #
def test_the_csv_holds_every_row_and_both_lists_of_odd_ones_out(qapp, tmp_path):
    comparison = ic.compare_infusions(_day(scale=0.5, which=("22",)), _day())
    path = ic.write_csv(comparison, tmp_path / "comparison.csv")
    lines = open(path, encoding="utf-8").read().splitlines()

    assert lines[0].startswith("Compound,Conditions")
    assert len(lines) == 1 + len(comparison.rows) + 1
    assert "yes" in lines[1] and "CA-d4" in lines[1]
    assert lines[-1].endswith("only in the reference")


def test_the_report_carries_the_comparison_while_it_stands(qapp):
    session = Session()
    session.entries.extend([_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1")])
    session.infusion_summary = ir.summarise(session)
    assert "Infusion comparison" not in batch_report.build_html(session)

    session.infusion_comparison = ic.compare_infusions(
        _day(scale=0.5, which=("22",)), _day())
    html = batch_report.build_html(session)
    assert "Infusion comparison" in html
    assert "past 20%" in html                      # why the row is marked
    assert "matched by compound and conditions" in html


def test_the_dialog_shows_the_rows_and_exports_them(qapp, tmp_path):
    from milq.ui.infusion_compare_dialog import InfusionCompareDialog

    comparison = ic.compare_infusions(_day(scale=0.5), _day())
    dialog = InfusionCompareDialog(comparison)
    try:
        assert dialog.table.rowCount() == len(comparison.rows) == 2
        assert dialog.table.item(0, 0).text() == "CA-d4"
        assert dialog.table.item(0, 1).text().endswith("eV")
        assert "marked as moved" in dialog.summary.text()
        # the height column carries the reason the row is coloured
        assert dialog.table.item(0, 10).toolTip().endswith("past 20%")
        path = dialog.export(str(tmp_path / "out.csv"))
        assert os.path.getsize(path) > 0
    finally:
        dialog.close()
        dialog.deleteLater()


def test_the_panel_says_so_when_the_reference_holds_no_summary(qapp, tmp_path):
    from milq.ui.infusions_panel import InfusionsPanel

    session = Session()
    session.entries.extend([_infusion("CA-d4_TOFMSMS_EAD_22CE_mix1")])
    panel = InfusionsPanel(session)
    try:
        panel.measure(threaded=False)
        assert panel.table.rowCount() == 1 and panel.btn_compare.isEnabled()

        plain = str(tmp_path / "plain.oqproj")
        Session().save_project(plain)
        assert panel.compare_infusions(plain) is None
        assert "holds no infusion summary" in panel.status.text()

        reference = str(tmp_path / "reference.oqproj")
        session.save_project(reference)
        comparison = panel.compare_infusions(reference)
        assert comparison is not None
        assert session.infusion_comparison is comparison
        assert len(comparison.rows) == 1
        assert comparison.rows[0].score == pytest.approx(1.0, abs=1e-6)
        panel._dialog.close()
        panel._dialog.deleteLater()
    finally:
        panel.close()
        panel.deleteLater()
