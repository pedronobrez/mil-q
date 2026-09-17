"""
Which mass axis a record of one's own was written from, and what reads it.

A record written while the recalibration was on carries peaks the instrument
never reported. What is tested here is that it says so, that a search says
what the *combination* of the two axes is and warns where a correction one
side carries and the other does not is wider than the tolerance its peaks
were paired within, that a history keeps such records in a series of their
own, and that the query can be put onto the record's axis and searched again.

Everything is synthetic, on purpose: the real infusions this was measured on
never produce a correction past the 20 ppm a search pairs peaks within — the
largest is 8.6 ppm — so the split, which is the one behaviour that needs a
big correction, could not have been exercised on them. The figures those
files did give are in the manual and in `library.axis_gap`.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import standard_history as sh                    # noqa: E402
from milq.library import (CORRECTED_AXIS, INSTRUMENT_AXIS,  # noqa: E402
                               PEAK_TOLERANCE_PPM, SpectralLibrary, axis_gap,
                               correction_ppm, entry_from_spectrum, format_msp,
                               parse_msp, provenance_of, recalibration_in,
                               to_axis)

#: a spectrum with a base peak and two flanks, all of them well apart
MZ = np.array([120.0800, 260.2000, 411.3054])
INTENSITY = np.array([300.0, 700.0, 1000.0])


def a_record(name: str = "CA-d4", ppm: float | None = None,
             energy: float = 22.0, activation: str = "EAD",
             day: str = "2026-01-05", file: str = "one.wiff",
             shift_ppm: float = 0.0):
    """
    One record, written from a corrected axis when `ppm` says so.

    The peaks are moved by `shift_ppm` and the comment says `ppm`: the two
    are separate arguments because a record that claims a correction it was
    not given is exactly what the reader has to be able to tell apart from
    one that was.
    """
    note = "" if ppm is None else f"recalibrated {ppm:+.1f} ppm"
    comment = " · ".join(p for p in (
        "Mix1", f"TOF PI 430.35 · average of 100 scans · {file}", note,
        "added 2026-01-06") if p)
    return entry_from_spectrum(
        f"{name}_TOFMSMS_{activation}_{energy:g}CE",
        MZ * (1.0 + shift_ppm * 1e-6), INTENSITY,
        precursor=430.3465, collision_energy=energy,
        acquired=f"{day}T10:00:00", comment=comment)


def a_library(*entries) -> SpectralLibrary:
    """A library through the text, so the parser is in the way."""
    return SpectralLibrary(parse_msp(format_msp(list(entries))))


def a_history(*entries) -> sh.StandardHistory:
    return sh.StandardHistory(parse_msp(format_msp(list(entries))))


# --------------------------------------------------------------------------- #
# what a record says about its own axis
# --------------------------------------------------------------------------- #
def test_a_record_says_which_axis_it_was_written_from():
    corrected = a_record(ppm=-5.2)
    plain = a_record()
    assert corrected.recalibrated_ppm == pytest.approx(-5.2)
    assert corrected.written_axis == CORRECTED_AXIS
    assert plain.recalibrated_ppm is None
    assert plain.written_axis == INSTRUMENT_AXIS
    # and the provenance still reads: the note is not one of its pieces
    assert provenance_of(corrected).file == "one.wiff"
    assert provenance_of(corrected).sample == "Mix1"
    assert provenance_of(corrected).recalibrated_ppm == pytest.approx(-5.2)


def test_the_sentence_the_explorer_writes_is_read_the_same_way():
    """
    The comment the Explorer puts on a record is `MassCorrection.short` in a
    longer sentence, not the bare note a rewrite writes. Both are the same
    claim and both have to read back, or a record written from the spectrum
    pane and one rewritten from its file would disagree about their own axis.
    """
    entry = entry_from_spectrum(
        "CA-d4", MZ, INTENSITY,
        comment=("Mix1 · TOF PI · one.wiff · on an axis recalibrated -5.2 ppm "
                 "from 3 lock masses; CA-d4 measured -5.6 ppm raw, "
                 "-0.4 ppm corrected · added 2026-01-06"))
    assert entry.recalibrated_ppm == pytest.approx(-5.2)
    assert provenance_of(entry).sample == "Mix1"
    assert provenance_of(entry).channel == "TOF PI"


def test_a_record_of_somebody_elses_is_on_the_instruments_axis():
    """Silence is the instrument's axis, and a zero is not silence."""
    assert recalibration_in("") is None
    assert recalibration_in("MassBank record, nothing about an axis") is None
    assert recalibration_in("recalibrated +0.0 ppm") == pytest.approx(0.0)
    assert a_record(ppm=0.0).written_axis == CORRECTED_AXIS


def test_a_correction_object_is_read_as_its_median_over_the_masses():
    class _Correction:
        usable = True
        offset_ppm = -4.0

        def ppm_at(self, mz):
            return -4.0 + 0.01 * (np.asarray(mz, dtype=float) - 200.0)

    assert correction_ppm(-5.2) == pytest.approx(-5.2)
    assert correction_ppm(None) is None
    assert correction_ppm(_Correction(), MZ) == pytest.approx(-3.4, abs=0.01)
    # with nothing behind it the axis it leaves is the instrument's
    class _Nothing(_Correction):
        usable = False

    assert correction_ppm(_Nothing(), MZ) is None


# --------------------------------------------------------------------------- #
# what the gap between two axes is, and is not
# --------------------------------------------------------------------------- #
def test_two_corrected_spectra_are_on_one_axis_however_far_apart_they_were():
    """
    The measured finding: a record corrected +2.0 ppm and a query corrected
    −7.5 ppm gave the best agreement of the four combinations, so the 9.5 ppm
    between the two corrections is not a gap between the two axes.
    """
    assert axis_gap(2.0, -7.5) == 0.0
    assert axis_gap(None, None) == 0.0
    assert axis_gap(None, -5.6) == pytest.approx(-5.6)
    assert axis_gap(3.8, None) == pytest.approx(-3.8)


def test_matching_the_axis_undoes_what_one_side_carries_and_nothing_else():
    moved = to_axis(MZ, -5.3, None)               # a corrected query, undone
    assert moved == pytest.approx(MZ * (1 + 5.3e-6))
    applied = to_axis(MZ, None, 3.8)              # onto a corrected record
    assert applied == pytest.approx(MZ * (1 + 3.8e-6))
    # both corrected, or neither: nothing to take out of the comparison
    assert to_axis(MZ, -7.5, 2.0) == pytest.approx(MZ)
    assert to_axis(MZ, None, None) == pytest.approx(MZ)


# --------------------------------------------------------------------------- #
# what a hit says
# --------------------------------------------------------------------------- #
def _hit(record_ppm, query_ppm, tolerance=PEAK_TOLERANCE_PPM):
    library = a_library(a_record(ppm=record_ppm))
    hits = library.search(MZ, INTENSITY, 430.3465, tolerance_ppm=tolerance,
                          query_correction=query_ppm)
    assert hits, "the record is the spectrum: it has to match itself"
    return hits[0]


def test_a_hit_says_the_combined_axis_situation():
    both_plain = _hit(None, None)
    assert both_plain.record_axis == INSTRUMENT_AXIS
    assert both_plain.query_axis == INSTRUMENT_AXIS
    assert both_plain.axis_sentence == ("record and query both on the "
                                        "instrument's axis")
    assert not both_plain.axes_differ and both_plain.axis_warning == ""

    both = _hit(-5.2, -6.1)
    assert both.axis_sentence == ("record corrected -5.2 ppm, query corrected "
                                  "-6.1 ppm: each on the axis its own lock "
                                  "masses define")
    assert both.axis_gap_ppm == 0.0 and not both.axes_differ

    one = _hit(None, -5.6)
    assert one.axis_sentence == ("record on the instrument's axis, query "
                                 "corrected -5.6 ppm: 5.6 ppm apart by "
                                 "construction")
    assert one.axis_gap_ppm == pytest.approx(-5.6)


def test_a_hit_warns_only_where_the_gap_is_wider_than_the_peak_tolerance():
    inside = _hit(None, -5.6, tolerance=20.0)
    assert not inside.axes_differ and inside.axis_warning == ""
    outside = _hit(None, -5.6, tolerance=5.0)
    assert outside.axes_differ
    assert "5.6 ppm apart" in outside.axis_warning
    assert "measuring the axes and not the compound" in outside.axis_warning
    # a correction on both sides is never a warning, whatever it was
    assert not _hit(2.0, -7.5, tolerance=5.0).axes_differ


def test_the_default_search_leaves_the_query_on_the_instruments_axis():
    """A caller that says nothing is a caller that applied nothing."""
    library = a_library(a_record(ppm=-5.2))
    hit = library.search(MZ, INTENSITY, 430.3465)[0]
    assert hit.query_ppm is None and hit.query_axis == INSTRUMENT_AXIS
    assert hit.record_ppm == pytest.approx(-5.2)


# --------------------------------------------------------------------------- #
# the history
# --------------------------------------------------------------------------- #
def test_a_corrected_and_an_uncorrected_record_are_two_series():
    history = a_history(
        a_record(ppm=None, day="2026-01-05", file="a.wiff"),
        a_record(ppm=None, day="2026-02-05", file="b.wiff"),
        a_record(ppm=-40.0, day="2026-03-05", file="c.wiff", shift_ppm=-40.0),
    )
    assert len(history.series) == 2
    plain, corrected = sorted(history.series, key=lambda s: s.corrected)
    assert [len(plain.records), len(corrected.records)] == [2, 1]
    assert corrected.axis_ppm == pytest.approx(-40.0)
    assert "axis corrected -40.0 ppm" in corrected.conditions
    assert plain.axis_label == ""
    # and the chart says what happened and what puts it back together
    note = sh.axis_split_note(history.split_with(corrected))
    assert "is 2 series, not one" in note
    assert "2 on the instrument's axis" in note
    assert "1 on an axis corrected -40.0 ppm" in note
    assert "Rewrite from files…" in note


def test_a_correction_under_the_peak_tolerance_does_not_split_a_series():
    """
    Which is what the real infusions do: their corrections are 2.0 to 8.6
    ppm, all of them inside the 20 ppm a search pairs peaks within, so the
    records stay one series and the mass chart carries the difference.
    """
    history = a_history(
        a_record(ppm=None, day="2026-01-05", file="a.wiff"),
        a_record(ppm=-7.5, day="2026-02-05", file="b.wiff", shift_ppm=-7.5),
    )
    assert len(history.series) == 1
    series = history.series[0]
    assert series.corrected == 1 and len(series.records) == 2
    assert "for 1 of 2" in series.axis_label
    assert history.axis_splits() == []
    assert sh.axis_split_note(history.split_with(series)) == ""


def test_two_corrections_of_different_sizes_are_still_one_series():
    history = a_history(
        a_record(ppm=-40.0, day="2026-01-05", file="a.wiff"),
        a_record(ppm=+35.0, day="2026-02-05", file="b.wiff"),
    )
    assert len(history.series) == 1
    assert history.series[0].corrected == 2


def test_the_records_axis_reaches_the_table_and_the_csv():
    history = a_history(
        a_record(ppm=None, day="2026-01-05", file="a.wiff"),
        a_record(ppm=-40.0, day="2026-03-05", file="c.wiff", shift_ppm=-40.0),
    )
    axes = {record.file: record.axis_label
            for series in history.series for record in series.records}
    assert axes == {"a.wiff": "the instrument's", "c.wiff": "corrected -40.0 ppm"}
    text = sh.csv_text(history)
    assert sh.CSV_HEADER[-1] == "Mass axis"
    assert ",".join(sh.CSV_HEADER) in text
    assert "corrected -40.0 ppm" in text
    assert "# CA-d4 · EAD 22 eV is 2 series, not one" in text


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp_module():
    from PyQt6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(qapp_module, tmp_path):
    from milq.ui.library_panel import LibraryPanel

    widget = LibraryPanel()
    path = tmp_path / "own.msp"
    path.write_text(format_msp([a_record(ppm=None)]), encoding="utf-8")
    widget.load(str(path))
    yield widget
    widget.deleteLater()


def test_the_panel_reads_the_querys_axis_from_the_explorers_sentence(panel):
    panel.set_spectrum(MZ, INTENSITY, 430.3465, {"title": "t"})
    assert panel.query_recalibration() is None
    panel.set_spectrum(MZ, INTENSITY, 430.3465, {
        "title": "t",
        "recalibration": ("on an axis recalibrated -5.6 ppm from 8 rungs; "
                          "CA-d4 measured -5.6 ppm raw, +0.0 ppm corrected")})
    assert panel.query_recalibration() == pytest.approx(-5.6)


def test_the_panel_says_the_axis_on_the_row_and_warns_on_the_line(panel):
    panel.peak_tol.setValue(5.0)
    panel.set_spectrum(MZ, INTENSITY, 430.3465, {
        "title": "t", "recalibration": "recalibrated -5.6 ppm"})
    panel.search()
    row = panel.hits.topLevelItem(0)
    assert row.text(8).startswith("instrument")
    assert "5.6 ppm apart" in row.text(8)
    assert "measuring the axes and not the compound" in panel.status.text()
    assert "Re-search with the axis matched" in panel.status.text()
    assert panel.btn_axis.isEnabled()


def test_the_axis_matched_search_moves_the_query_and_says_which_axis(panel):
    panel.set_spectrum(MZ * (1 - 5.6e-6), INTENSITY, 430.3465, {
        "title": "t", "recalibration": "recalibrated -5.6 ppm"})
    panel.search()
    before = panel._hits[0]
    assert before.axis_gap_ppm == pytest.approx(-5.6)
    before_ppm = np.median([abs(p.ppm) for p in before.pairs])

    hits = panel.search_on_record_axis()
    assert hits and hits[0].query_ppm is None       # both on the record's now
    assert hits[0].axis_gap_ppm == 0.0
    after_ppm = np.median([abs(p.ppm) for p in hits[0].pairs])
    assert after_ppm < before_ppm and after_ppm < 0.1
    assert "moved from an axis corrected -5.6 ppm" in panel.status.text()
    assert "onto the instrument's axis" in panel.status.text()
    assert "does not put either on the right axis" in panel.status.text()
    # the spectrum on screen is untouched: it is what the acquisition gave
    assert panel._spectrum[0] == pytest.approx(MZ * (1 - 5.6e-6))


def test_the_history_dialog_offers_the_rewrite_only_where_it_is_the_repair(
        qapp_module):
    from milq.ui.standard_history_dialog import StandardHistoryDialog

    split = a_history(
        a_record(ppm=None, day="2026-01-05", file="a.wiff"),
        a_record(ppm=-40.0, day="2026-03-05", file="c.wiff", shift_ppm=-40.0))
    dialog = StandardHistoryDialog(history=split)
    assert dialog.btn_rewrite.isVisibleTo(dialog)
    assert "is 2 series, not one" in dialog.status.text()
    assert "Rewrite from files…" in dialog.status.text()
    assert not dialog.rewrite_requested
    dialog.btn_rewrite.click()
    # the dialog asks; the Library tab, which owns the file, does the writing
    assert dialog.rewrite_requested
    dialog.deleteLater()

    whole = a_history(a_record(ppm=None, day="2026-01-05", file="a.wiff"),
                      a_record(ppm=None, day="2026-02-05", file="b.wiff"))
    quiet = StandardHistoryDialog(history=whole)
    assert not quiet.btn_rewrite.isVisibleTo(quiet)
    assert "series, not one" not in quiet.status.text()
    quiet.deleteLater()


def test_the_button_is_offered_only_when_the_two_axes_differ(panel, tmp_path):
    path = tmp_path / "both.msp"
    path.write_text(format_msp([a_record(name="CA-d4", ppm=-5.2)]),
                    encoding="utf-8")
    panel.load(str(path))
    panel.set_spectrum(MZ, INTENSITY, 430.3465, {
        "title": "t", "recalibration": "recalibrated -6.1 ppm"})
    panel.search()
    assert not panel.btn_axis.isEnabled()       # both corrected: one axis
    assert panel.search_on_record_axis() is not None
