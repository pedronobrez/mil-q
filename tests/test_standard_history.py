"""
A standard's own-library records read back as a control chart.

What is tested is the reading and the refusing: that the records come out in
acquisition order with the first as the reference, that a record at another
collision energy or activation is a different series, that no limit is drawn
through fewer than three records, that a record that is out is out on the
Batch QC rule and not on a sigma alone, that a base peak which is a
different ion is not charted as a mass error, and that the CSV and the
dialog say the same things the module does.

Everything here is synthetic. The nine real infusions have no series of
three records at one energy — measured, and written up in the manual page —
so the limits could not have been exercised on them.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import standard_history as sh          # noqa: E402
from milq.library import (entry_from_spectrum, load_library,  # noqa: E402
                               parse_msp, write_msp)
from milq.qc import ALWAYS_OUT_PERCENT, OUT_PERCENT  # noqa: E402

#: three peaks, the last of them the base peak
MZ = np.array([100.0500, 200.1000, 300.1500])
INTENSITY = np.array([200.0, 500.0, 1000.0])

#: a spectrum with nothing in common with the one above
OTHER_MZ = np.array([150.0500, 250.1000, 350.1500])


def a_record(day: str, index: int = 1, energy: float | None = 22.0,
             activation: str = "EAD", scale: float = 1.0,
             shift_ppm: float = 0.0, mz=None, compound: str = "CA-d4"):
    """One record of one compound, as the panel would have written it."""
    mz = MZ if mz is None else mz
    name = f"{compound}_TOFMSMS_{activation}_{energy:g}CE_{index}"
    return entry_from_spectrum(
        name, np.asarray(mz) * (1.0 + shift_ppm * 1e-6), INTENSITY * scale,
        precursor=430.3465, collision_energy=energy,
        acquired=f"{day}T10:00:00" if day else "",
        comment=f"Mix1 · TOF PI · average of 100 scans · {name}.wiff")


def a_history(records) -> sh.StandardHistory:
    """A history from records, through the text so the parser is in the way."""
    from milq.library import format_msp

    return sh.StandardHistory(parse_msp(format_msp(list(records))))


def days(n: int) -> list[str]:
    return [f"2026-{month:02d}-05" for month in range(1, n + 1)]


# --------------------------------------------------------------------------- #
# what a record carries
# --------------------------------------------------------------------------- #
def test_a_record_carries_the_day_it_was_acquired_and_its_base_peak(tmp_path):
    path = tmp_path / "own.msp"
    write_msp([a_record("2026-03-04")], path)
    entry = load_library(path).entries[0]
    record = sh.Record(entry)
    assert record.when == "2026-03-04T10:00:00" and record.day == "2026-03-04"
    assert record.compound == "CA-d4"
    assert record.energy == pytest.approx(22.0)
    assert record.activation == "EAD"
    assert record.base_mz == pytest.approx(300.1500, abs=1e-4)
    assert record.base_intensity == pytest.approx(1000.0)
    assert record.file.endswith(".wiff")
    assert record.precursor == pytest.approx(430.3465)


def test_the_activation_is_read_from_a_field_before_a_name():
    entry = a_record("2026-01-05", activation="EAD")
    entry.fields["Activation"] = "CID"
    assert sh.activation_of(entry) == "CID"
    bare = entry_from_spectrum("CA-d4 plain", MZ, INTENSITY)
    assert sh.activation_of(bare) == ""          # unstated, not assumed CID


# --------------------------------------------------------------------------- #
# the order, and the reference
# --------------------------------------------------------------------------- #
def test_records_are_ordered_by_date_and_the_first_is_the_reference():
    written = [a_record("2026-03-05", 3), a_record("2026-01-05", 1),
               a_record("2026-02-05", 2)]
    series = a_history(written).series[0]
    assert [r.day for r in series.records] == days(3)
    assert series.reference is series.records[0]
    assert series.records[0].name.endswith("_1")
    assert series.records[0].score == pytest.approx(1.0)
    assert series.records[0].previous_score is None
    assert series.ordered and series.dated == 3


def test_an_undated_record_keeps_the_order_of_the_file_and_says_so():
    series = a_history([a_record("2026-02-05", 1), a_record("", 2),
                        a_record("2026-01-05", 3)]).series[0]
    assert [r.name[-1] for r in series.records] == ["3", "1", "2"]
    assert not series.ordered and series.dated == 2
    assert "no acquisition date" in sh.caveat(series)


# --------------------------------------------------------------------------- #
# the grouping
# --------------------------------------------------------------------------- #
def test_a_record_at_another_energy_or_activation_is_another_series():
    history = a_history([
        a_record("2026-01-05", 1, energy=22.0, activation="EAD"),
        a_record("2026-01-06", 2, energy=22.0, activation="EAD"),
        a_record("2026-01-07", 3, energy=45.0, activation=""),
        a_record("2026-01-08", 4, energy=22.0, activation="CID"),
    ])
    assert history.compounds == ["CA-d4"]
    labels = [s.conditions for s in history.for_compound("CA-d4")]
    assert labels == ["45 eV", "CID 22 eV", "EAD 22 eV"]
    counts = {s.conditions: len(s.records) for s in history.series}
    assert counts == {"EAD 22 eV": 2, "45 eV": 1, "CID 22 eV": 1}
    # each series has its own reference, so nothing is scored across energies
    for series in history.series:
        assert series.reference is series.records[0]
        assert series.records[0].score == pytest.approx(1.0)


def test_energies_within_the_tolerance_are_one_setting_written_twice():
    history = a_history([a_record("2026-01-05", 1, energy=22.0),
                         a_record("2026-01-06", 2, energy=22.2)])
    assert len(history.series) == 1


def test_the_caveat_names_the_conditions_the_intensity_belongs_to():
    series = a_history([a_record(d, i) for i, d in enumerate(days(3), 1)]).series[0]
    said = sh.caveat(series)
    assert "EAD 22 eV" in said
    assert "comparable only within one method and energy" in said


# --------------------------------------------------------------------------- #
# limits are drawn from three records, never two
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("count", [1, 2])
def test_fewer_than_three_records_are_listed_and_not_charted(count):
    series = a_history([a_record(d, i)
                        for i, d in enumerate(days(count), 1)]).series[0]
    for metric in sh.METRICS:
        chart = series.charts[metric]
        assert not chart.measurable
        assert chart.centre is None and chart.sigma is None
        assert len(chart.injections) == count
        assert sh.verdict(chart).startswith("too few to chart")
        assert f"{sh.MIN_RECORDS} are needed" in sh.verdict(chart)


def test_three_records_are_enough_for_a_centre_and_limits():
    series = a_history([a_record(d, i, scale=s)
                        for i, (d, s) in enumerate(zip(days(3),
                                                       (1.0, 1.05, 0.95)), 1)]
                       ).series[0]
    chart = series.charts[sh.INTENSITY]
    assert chart.measurable and chart.centre == pytest.approx(1000.0)
    assert chart.sigma > 0
    assert not chart.out and "too few" not in sh.verdict(chart)


# --------------------------------------------------------------------------- #
# out, on the Batch QC rule
# --------------------------------------------------------------------------- #
def test_a_record_at_a_third_of_the_response_is_out():
    scales = [1.0, 1.0, 1.0, 1.0, 1.0, 0.3]
    series = a_history([a_record(d, i, scale=s)
                        for i, (d, s) in enumerate(zip(days(6), scales), 1)]
                       ).series[0]
    chart = series.charts[sh.INTENSITY]
    assert chart.centre == pytest.approx(1000.0)
    assert [point.order for point in chart.out] == [6]
    assert chart.out[0].percent <= -ALWAYS_OUT_PERCENT
    assert "1 outside" in sh.verdict(chart)


def test_a_sigma_alone_does_not_flag_a_record():
    """
    The Batch QC floor: a series that repeats itself well has a spread too
    small to flag on, and a record fifteen per cent high is not a finding.
    """
    scales = [1.0, 1.01, 0.99, 1.005, 0.995, 1.15]
    series = a_history([a_record(d, i, scale=s)
                        for i, (d, s) in enumerate(zip(days(6), scales), 1)]
                       ).series[0]
    chart = series.charts[sh.INTENSITY]
    point = chart.injections[-1]
    assert abs(point.sigmas) > 3.0                 # unusual for this series
    assert abs(point.percent) < OUT_PERCENT        # and not far enough to act on
    assert chart.out == [] and point.warned


def test_a_spectrum_with_nothing_in_common_is_out_on_the_score():
    entries = [a_record(d, i) for i, d in enumerate(days(4), 1)]
    entries[-1] = a_record(days(4)[-1], 4, mz=OTHER_MZ)
    series = a_history(entries).series[0]
    chart = series.charts[sh.SCORE]
    assert series.records[-1].score == pytest.approx(0.0)
    assert [point.order for point in chart.out] == [4]
    assert series.flagged[series.records[-1].label] == [sh.SCORE]


# --------------------------------------------------------------------------- #
# drift
# --------------------------------------------------------------------------- #
def test_a_response_falling_through_the_records_is_a_drift():
    scales = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    series = a_history([a_record(d, i, scale=s)
                        for i, (d, s) in enumerate(zip(days(6), scales), 1)]
                       ).series[0]
    chart = series.charts[sh.INTENSITY]
    assert chart.correlation == pytest.approx(-1.0)
    assert chart.drift < -20.0 and chart.drifted
    assert "drift" in sh.verdict(chart)


def test_a_mass_trend_is_measured_in_ppm_and_not_in_per_cent():
    shifts = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0]
    series = a_history([a_record(d, i, shift_ppm=p)
                        for i, (d, p) in enumerate(zip(days(6), shifts), 1)]
                       ).series[0]
    chart = series.charts[sh.MASS]
    assert chart.limits.absolute and chart.limits.unit == " ppm"
    assert chart.drift == pytest.approx(40.0, abs=1.0)
    assert chart.drifted and "ppm" in sh.verdict(chart)
    # the reference is at zero, and a percentage of zero is why this is
    # charted absolutely
    assert series.records[0].ppm == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# a base peak that is a different ion
# --------------------------------------------------------------------------- #
def test_a_different_base_peak_is_not_charted_as_a_mass_error():
    entries = [a_record(d, i) for i, d in enumerate(days(4), 1)]
    entries[-1] = a_record(days(4)[-1], 4, mz=OTHER_MZ)
    series = a_history(entries).series[0]
    odd = series.records[-1]
    assert not odd.same_base_peak
    assert odd.ppm is None and abs(odd.base_gap_ppm) > sh.SAME_PEAK_PPM
    assert sh.ppm_text(odd) == "not the same ion"
    chart = series.charts[sh.MASS]
    assert len(chart.injections) == 3            # the odd one is left out
    assert "not a mass error" in chart.note


# --------------------------------------------------------------------------- #
# out of the program
# --------------------------------------------------------------------------- #
def test_the_csv_holds_a_row_per_record_under_the_verdicts(tmp_path):
    history = a_history([a_record(d, i, scale=s)
                         for i, (d, s) in enumerate(zip(days(3),
                                                        (1.0, 1.1, 0.9)), 1)])
    path = sh.write_csv(history, tmp_path / "history.csv", "CA-d4")
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    said = [line for line in lines if line.startswith("#")]
    rows = [line for line in lines if not line.startswith("#")]
    assert any(sh.SCORE in line for line in said)
    assert any("EAD 22 eV" in line for line in said)
    assert rows[0].split(",")[:4] == ["Compound", "Activation",
                                      "Collision energy", "Record"]
    assert len(rows) == 4                        # the header and three records
    assert all(row.startswith("CA-d4,EAD,22.0,") for row in rows[1:])
    assert "1,000" not in text                   # no thousands separator in a CSV


def test_the_csv_of_one_compound_leaves_the_others_out(tmp_path):
    history = a_history([a_record("2026-01-05", 1),
                         a_record("2026-01-06", 2, compound="DCA-d4")])
    assert history.compounds == ["CA-d4", "DCA-d4"]
    text = open(sh.write_csv(history, tmp_path / "one.csv", "CA-d4"),
                encoding="utf-8").read()
    assert "CA-d4" in text and "DCA-d4" not in text


# --------------------------------------------------------------------------- #
# the dialog
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def written(tmp_path):
    path = str(tmp_path / "own.msp")
    write_msp([a_record(d, i, scale=s)
               for i, (d, s) in enumerate(zip(days(4), (1.0, 1.1, 0.9, 0.3)), 1)]
              + [a_record("2026-05-05", 9, energy=45.0, activation="")], path)
    return path


def test_the_dialog_lists_the_series_and_fills_its_tables(qapp, written):
    from milq.ui.standard_history_dialog import StandardHistoryDialog

    dialog = StandardHistoryDialog(written)
    try:
        assert dialog.compound.count() == 1
        assert dialog.compound.currentText() == "CA-d4"
        assert dialog.series.count() == 2
        # the series are offered in one order everywhere — activation, then
        # energy — so the single 45 eV record comes first
        assert dialog.current_series().conditions == "45 eV"
        assert dialog.records.rowCount() == 1
        assert "too few to chart" in dialog.charts.item(0, 6).text()

        dialog.series.setCurrentIndex(1)
        series = dialog.current_series()
        assert series.conditions == "EAD 22 eV" and len(series.records) == 4
        assert dialog.records.rowCount() == 4
        assert dialog.charts.rowCount() == len(sh.METRICS)
        # the record at three tenths of the response is out on the intensity
        assert dialog.records.item(3, 10).text() == sh.INTENSITY
        assert dialog.btn_save.isEnabled()

        dialog.metric.setCurrentText(sh.MASS)
        assert dialog.plot.getPlotItem().getAxis("left").labelText == sh.MASS
    finally:
        dialog.close()
        dialog.deleteLater()


def test_the_dialog_says_so_when_there_is_nothing_to_read(qapp, tmp_path):
    from milq.ui.standard_history_dialog import StandardHistoryDialog

    dialog = StandardHistoryDialog(str(tmp_path / "missing.msp"))
    try:
        assert "No library of your own" in dialog.status.text()
        assert not dialog.btn_save.isEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_the_dialog_names_a_manual_page_that_exists(qapp):
    from milq.manual import manual
    from milq.ui.help_window import HELP_PROPERTY
    from milq.ui.standard_history_dialog import HELP_PAGE, StandardHistoryDialog

    dialog = StandardHistoryDialog("")
    try:
        assert dialog.property(HELP_PROPERTY) == HELP_PAGE
        assert HELP_PAGE in manual().pages
    finally:
        dialog.close()
        dialog.deleteLater()


def test_the_library_panel_opens_the_history_of_what_it_has_written(qapp,
                                                                    tmp_path):
    from milq.ui.library_panel import LibraryPanel

    panel = LibraryPanel()
    try:
        panel.set_own_path(str(tmp_path / "mine.msp"))
        assert not panel.btn_history.isEnabled()
        assert panel.show_history() is None
        assert "Write a record" in panel.status.text()

        panel.set_spectrum(MZ, INTENSITY, 430.3465,
                           {"title": "Mix1 · TOF PI · average of 100 scans",
                            "file": "CA-d4_TOFMSMS_Mix1.wiff",
                            "polarity": "Positive",
                            "collision_energy": 22.0,
                            "acquired": "2026-03-04T10:00:00"})
        prefill = panel.own_prefill()
        assert prefill["acquired"] == "2026-03-04T10:00:00"
        panel.add_to_own_library("CA-d4_TOFMSMS_Mix1", **{
            k: prefill[k] for k in ("precursor", "precursor_type",
                                    "collision_energy", "comment", "acquired")})
        assert panel.btn_history.isEnabled()
        history = sh.read_history(panel.own_path)
        assert history.records[0].when == "2026-03-04T10:00:00"
        assert history.records[0].base_intensity == pytest.approx(1000.0)
    finally:
        panel.deleteLater()
