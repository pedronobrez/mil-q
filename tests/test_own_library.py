"""
A spectral library of one's own, built from the spectra on screen.

An infused deuterated standard is in no public library, so the record has
to be made from the measurement. What is tested is that a record written
from a spectrum comes back from `parse_msp` as the same record — the same
peaks, the same fields — that appending leaves the records before it
readable, that the floor and the ceiling on the peaks are applied, and that
the panel's flow writes the file, counts it, and reloads the library when
it is the one the record went into.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.library import (OWN_MAX_PEAKS, entry_from_spectrum,  # noqa: E402
                               format_msp, load_library, parse_msp, write_msp)

#: a made-up product spectrum with a base peak, two flanks and a whisper
MZ = np.array([80.9601, 121.0653, 289.2168, 371.2591, 411.3054])
INTENSITY = np.array([120.0, 4.0, 3800.0, 900.0, 45.0])


def a_record(**kwargs):
    fields = dict(name="cholic acid-d4", precursor=411.3054,
                  precursor_type="[M-H]-", formula="C24H36D4O5",
                  collision_energy=-35.0,
                  comment="CA-d4_TOFMSMS_Mix1.wiff · scans 1-120 · 2026-09-09")
    fields.update(kwargs)
    return entry_from_spectrum(mz=MZ, intensity=INTENSITY, **fields)


def test_a_record_from_a_spectrum_holds_relative_peaks_above_the_floor():
    entry = a_record()
    # 4.0 counts is 0.1% of the base peak: under the one per cent floor
    assert entry.peaks == 4
    assert 121.0653 not in entry.mz
    assert entry.intensity.max() == pytest.approx(1.0)
    assert entry.mz[0] == pytest.approx(80.9601)          # sorted by mass
    assert entry.intensity[entry.mz == 289.2168][0] == pytest.approx(1.0)
    assert entry.fields["Collision_energy"] == "-35"
    assert entry.fields["Comment"].startswith("CA-d4")


def test_a_record_keeps_the_strongest_peaks_and_needs_a_name():
    rng = np.random.default_rng(7)
    mz = np.linspace(100.0, 900.0, 500)
    intensity = rng.uniform(0.02, 1.0, 500) * 1000.0
    intensity[123] = 5000.0
    entry = entry_from_spectrum("crowded", mz, intensity)
    assert entry.peaks == OWN_MAX_PEAKS
    assert entry.mz[np.argmax(entry.intensity)] == pytest.approx(mz[123])
    # the ceiling keeps the strongest, so the weakest kept is above the
    # weakest dropped
    assert entry.intensity.min() * 5000.0 >= np.sort(intensity)[-OWN_MAX_PEAKS]
    with pytest.raises(ValueError):
        entry_from_spectrum("  ", mz, intensity)
    with pytest.raises(ValueError):
        entry_from_spectrum("empty", np.zeros(0), np.zeros(0))


def test_a_written_record_is_read_back_as_the_same_record(tmp_path):
    entry = a_record()
    path = tmp_path / "own.msp"
    assert write_msp([entry], path) == 1
    back = load_library(path)
    assert len(back) == 1
    read = back.entries[0]
    assert read.name == entry.name
    assert read.precursor == pytest.approx(411.3054)
    assert read.precursor_type == "[M-H]-" and read.formula == "C24H36D4O5"
    assert read.fields["Collision_energy"] == "-35"
    assert read.fields["Comment"] == entry.fields["Comment"]
    assert read.peaks == entry.peaks
    assert read.mz == pytest.approx(entry.mz, abs=1e-5)
    assert read.intensity == pytest.approx(entry.intensity, rel=1e-5)
    # and it scores one against the spectrum it was made from
    hit = back.search(MZ, INTENSITY, precursor=411.3054)[0]
    assert hit.score == pytest.approx(1.0)
    assert hit.matched == entry.peaks


def test_a_record_with_no_precursor_or_energy_writes_no_such_field():
    text = format_msp([entry_from_spectrum("bare", MZ, INTENSITY)])
    assert "PrecursorMZ" not in text and "Collision_energy" not in text
    assert "Num Peaks: 4" in text
    read = parse_msp(text)[0]
    assert read.precursor is None and read.name == "bare"


def test_appending_leaves_the_record_before_it_readable(tmp_path):
    path = tmp_path / "own.msp"
    write_msp([a_record(name="first")], path)
    write_msp([a_record(name="second", precursor=395.3105)], path, append=True)
    write_msp([a_record(name="third")], path, append=True)
    names = [e.name for e in load_library(path).entries]
    assert names == ["first", "second", "third"]
    # a file that somebody left without its trailing blank line still appends
    truncated = tmp_path / "truncated.msp"
    truncated.write_text(format_msp([a_record(name="first")]).rstrip("\n"),
                         encoding="utf-8")
    write_msp([a_record(name="second")], truncated, append=True)
    assert [e.name for e in load_library(truncated).entries] == ["first", "second"]


def test_a_newline_in_a_field_cannot_end_the_record(tmp_path):
    entry = a_record(name="one\ntwo", comment="a\nb")
    assert entry.name == "one two"
    path = tmp_path / "own.msp"
    write_msp([entry], path)
    read = load_library(path).entries
    assert len(read) == 1 and read[0].fields["Comment"] == "a b"


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #
@pytest.fixture
def panel(qapp_module):
    from milq.ui.library_panel import LibraryPanel
    widget = LibraryPanel()
    yield widget
    widget.deleteLater()


@pytest.fixture(scope="module")
def qapp_module():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_panel_writes_a_record_and_counts_its_own_library(panel, tmp_path):
    path = str(tmp_path / "mine.msp")
    panel.set_own_path(path)
    assert "not written yet" in panel.own_label.text()
    panel.set_spectrum(MZ, INTENSITY, 411.3054,
                       {"title": "Mix1 · TOF PI 411.30 · average of 120 scans",
                        "file": "CA-d4_TOFMSMS_Mix1.wiff", "sample": "Mix1",
                        "polarity": "Negative", "collision_energy": -35.0})
    prefill = panel.own_prefill()
    assert prefill["precursor"] == pytest.approx(411.3054)
    assert prefill["precursor_type"] == "[M-H]-"
    assert prefill["collision_energy"] == pytest.approx(-35.0)
    assert "CA-d4_TOFMSMS_Mix1.wiff" in prefill["comment"]
    assert "average of 120 scans" in prefill["comment"]

    entry = panel.add_to_own_library("cholic acid-d4", **{
        k: prefill[k] for k in ("precursor", "precursor_type",
                                "collision_energy", "comment")})
    assert entry is not None and entry.peaks == 4
    assert "1 record(s) in mine.msp" in panel.own_label.text()
    assert "cholic acid-d4" in panel.status.text()
    written = load_library(path).entries[0]
    assert written.precursor == pytest.approx(411.3054)

    # a second one appends rather than replacing
    panel.add_to_own_library("deoxycholic acid-d4", precursor=395.3105)
    assert "2 record(s)" in panel.own_label.text()


def test_the_record_is_searchable_at_once_when_it_is_the_loaded_library(panel,
                                                                       tmp_path):
    path = str(tmp_path / "mine.msp")
    write_msp([a_record(name="deoxycholic acid-d4", precursor=395.3105,
                       formula="C24H36D4O4")], path)
    panel.load(path)
    panel.set_own_path(path)
    assert len(panel.library) == 1
    panel.set_spectrum(MZ, INTENSITY, 411.3054)
    panel.add_to_own_library("cholic acid-d4", precursor=411.3054)
    assert len(panel.library) == 2                  # reloaded, not stale
    panel.search()
    assert panel.hits.topLevelItemCount() == 1
    assert panel.hits.topLevelItem(0).text(0) == "cholic acid-d4"
    assert panel.hits.topLevelItem(0).text(1) == "100"


def test_a_record_keeps_the_precision_its_precursor_was_given(tmp_path):
    """
    A method value of `430.35` written back as `430.3500` would claim four
    decimals it does not have, and `precursor_disagrees` would then measure
    it to ±0.00005 and call the compound's own formula wrong.
    """
    path = tmp_path / "own.msp"
    write_msp([a_record(name="cholic acid-d4", precursor=430.35,
                        precursor_type="[M+NH4]+", formula="C24H36D4O5")], path)
    assert "PrecursorMZ: 430.35\n" in path.read_text(encoding="utf-8")
    read = load_library(path).entries[0]
    assert read.precursor_text == "430.35"
    assert read.exact_precursor == pytest.approx(430.3465, abs=1e-4)
    assert not read.precursor_disagrees
    # and a precursor genuinely known to four decimals still writes them
    write_msp([a_record(precursor=411.3054)], path)
    assert "PrecursorMZ: 411.3054\n" in path.read_text(encoding="utf-8")


def test_the_panel_gates_on_the_channel_polarity_until_the_box_is_ticked(panel,
                                                                        tmp_path):
    path = tmp_path / "mixed.msp"
    path.write_text(
        "Name: a positive record\nPrecursorMZ: 411.3054\n"
        "Precursor_type: [M+H]+\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n\n"
        "Name: a negative record\nPrecursorMZ: 411.3054\n"
        "Precursor_type: [M-H]-\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n", encoding="utf-8")
    panel.load(str(path))
    assert not panel.other_polarity.isChecked()          # off by default
    panel.set_spectrum(MZ, INTENSITY, 411.3054,
                       {"title": "t", "polarity": "Negative"})
    assert panel.query_polarity() == "Negative"
    panel.search()
    listed = [panel.hits.topLevelItem(i).text(0)
              for i in range(panel.hits.topLevelItemCount())]
    assert listed == ["a negative record"]
    assert "negative records only" in panel.status.text()
    panel.other_polarity.setChecked(True)
    panel.search()
    assert panel.hits.topLevelItemCount() == 2
    # with no context there is nothing to gate on and everything is scored
    panel.other_polarity.setChecked(False)
    panel.set_spectrum(MZ, INTENSITY, 411.3054, {"title": "t"})
    panel.search()
    assert panel.hits.topLevelItemCount() == 2


def test_the_panel_says_which_precursor_the_delta_was_measured_against(panel,
                                                                      tmp_path):
    path = tmp_path / "mixed.msp"
    path.write_text(
        "Name: with a formula\nPrecursorMZ: 430.35\n"
        "Precursor_type: [M+NH4]+\nFormula: C24H36D4O5\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n\n"
        "Name: typed wrong\nPrecursorMZ: 430.35\n"
        "Precursor_type: [M+NH4]+\nFormula: C24H36D4O4\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n", encoding="utf-8")
    panel.load(str(path))
    panel.set_spectrum(MZ, INTENSITY, 430.34, {"title": "t"})
    panel.precursor_tol.setValue(0.05)
    panel.search()
    rows = {panel.hits.topLevelItem(i).text(0): panel.hits.topLevelItem(i)
            for i in range(panel.hits.topLevelItemCount())}
    assert set(rows) == {"with a formula", "typed wrong"}
    assert rows["with a formula"].text(5) == "-15.1"
    assert rows["with a formula"].text(6) == "formula"
    assert rows["with a formula"].text(4) == "430.3500"      # no disagreement
    # the record whose formula is a different compound says both numbers
    assert "≠" in rows["typed wrong"].text(4)


def test_the_panel_refuses_without_a_file_or_a_spectrum(panel, tmp_path):
    panel.set_own_path("")
    panel.set_spectrum(MZ, INTENSITY, 411.3054)
    assert panel.add_to_own_library("nowhere") is None
    assert "Choose a file" in panel.status.text()
    panel._spectrum = None
    assert panel.add_to_own_library("x", path=str(tmp_path / "a.msp")) is None
    assert "Show a spectrum first" in panel.status.text()


def test_the_hook_may_carry_the_context_and_need_not(panel, tmp_path):
    panel.spectrum_source = lambda: (MZ, INTENSITY, 411.3054,
                                     {"polarity": "Negative", "file": "a.wiff"})
    panel._pull_spectrum()
    assert panel.own_prefill()["precursor_type"] == "[M-H]-"
    # the three-value form of the hook, which is what it was before
    panel.spectrum_source = lambda: (MZ, INTENSITY, 411.3054)
    panel._pull_spectrum()
    assert panel._spectrum is not None


def test_the_dialog_prefills_and_gives_back_what_was_typed(qapp_module):
    from milq.ui.library_add_dialog import AddToLibraryDialog
    from PyQt6.QtWidgets import QDialogButtonBox

    dialog = AddToLibraryDialog(
        {"precursor": 411.3054, "precursor_type": "[M-H]-",
         "collision_energy": -35.0, "comment": "from a file"}, peaks=4,
        target="mine.msp")
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()                   # nothing is written unnamed
    dialog.name_edit.setText("cholic acid-d4")
    assert ok.isEnabled()
    dialog.formula_edit.setText("C24H36D4O5")
    values = dialog.values()
    assert values["name"] == "cholic acid-d4"
    assert values["precursor"] == pytest.approx(411.3054)
    assert values["precursor_type"] == "[M-H]-"
    assert values["formula"] == "C24H36D4O5"
    assert values["collision_energy"] == pytest.approx(-35.0)
    assert values["comment"] == "from a file"
    dialog.deleteLater()


def test_the_explorer_hands_over_where_the_spectrum_came_from(qapp_module):
    """
    A record has to say which file, sample, channel and scans it was made
    from, and the Explorer is the only place that knows.
    """
    from milq.samples import SampleEntry
    from milq.session import Session
    from milq.ui.explorer import ChannelRef, ExplorerWorkspace
    from milq.ui.plots import Trace
    from milq.wiff import ChannelInfo

    explorer = ExplorerWorkspace(Session())
    mz = np.linspace(100.0, 200.0, 201)
    intensity = np.exp(-((mz - 150.0) ** 2) / 0.02) * 1000.0
    explorer.spectrum.set_traces([Trace("spec", "spectrum", mz, intensity, "#000")])
    explorer.spectrum.set_title("Mix1 · TOF PI 411.30 · average of 120 scans (1–120)")

    class _Channel:
        info = ChannelInfo(index=3, name="TOF PI", experiment_type="Product",
                           polarity="Negative", precursor=411.3, start_mass=50.0,
                           end_mass=500.0, n_scans=120, collision_energy=-35.0)

    entry = SampleEntry(path="/data/CA-d4_TOFMSMS_Mix1.wiff", sample_index=0,
                        name="Mix1")
    explorer.active_ref = ChannelRef(entry, _Channel())
    result = explorer._library_spectrum()
    assert result is not None and len(result) == 4
    _mz, _intensity, precursor, context = result
    assert precursor == pytest.approx(411.3)
    assert context["file"] == "CA-d4_TOFMSMS_Mix1.wiff"
    assert context["sample"] == "Mix1"
    assert context["polarity"] == "Negative"
    assert context["collision_energy"] == pytest.approx(-35.0)
    assert "average of 120 scans" in context["title"]
    # and the panel turns that into a comment naming all of it
    explorer.library_panel._pull_spectrum()
    comment = explorer.library_panel.own_prefill()["comment"]
    assert "CA-d4_TOFMSMS_Mix1.wiff" in comment and "average of 120 scans" in comment
    assert explorer.library_panel.own_prefill()["precursor_type"] == "[M-H]-"
    explorer.deleteLater()


def test_the_dialog_names_a_page_the_manual_has():
    from milq.manual import manual
    from milq.ui.library_add_dialog import HELP_PAGE
    assert HELP_PAGE in manual().pages


def test_the_comment_says_whether_the_adduct_was_measured_or_deduced(qapp_module):
    """
    A record states an adduct and nothing in it says how that was arrived
    at. Which of the two it was is the difference between a fact and a
    reading, so it goes in the comment beside the provenance.
    """
    from milq import chemistry as ch
    from milq.samples import SampleEntry
    from milq.session import Session
    from milq.ui.explorer import ChannelRef, ExplorerWorkspace
    from milq.ui.plots import Trace
    from milq.wiff import ChannelInfo

    explorer = ExplorerWorkspace(Session())
    mz = np.arange(425.0, 436.0, 0.002)
    intensity = np.exp(-((mz - 430.3465) ** 2) / 0.0002) * 1000.0
    explorer.spectrum.set_traces([Trace("spec", "spectrum", mz, intensity,
                                        "#000")])
    explorer.spectrum.set_title("Mix1 · TOF PI 430.35 · average of 120 scans")

    class _Channel:
        info = ChannelInfo(index=3, name="TOF PI", experiment_type="Product",
                           polarity="Positive", precursor=430.35,
                           start_mass=50.0, end_mass=500.0, n_scans=120,
                           collision_energy=45.0)

    entry = SampleEntry(path="/data/CA-d4_TOFMSMS_Mix1.wiff", sample_index=0,
                        name="Mix1")
    explorer.active_ref = ChannelRef(entry, _Channel())
    panel = explorer.lipid_panel

    # nothing has been handed over yet: nothing is claimed
    assert panel.adduct_provenance == ""

    # a spectrum with no survey beside it — the nine bile-acid infusions
    panel.set_spectrum(mz, intensity, 430.35, "Positive", survey=None)
    assert "no survey scan" in panel.adduct_provenance
    explorer.library_panel._pull_spectrum()
    assert "no survey scan" in explorer.library_panel.own_prefill()["comment"]

    # and the same spectrum with the survey the adduct was read from
    pattern = ch.ion_pattern(
        "C24H36D4O5", ch.ADDUCTS_BY_NAME["[M+NH4]+"], max_peaks=3)
    survey = np.zeros_like(mz)
    for centre, abundance in pattern:
        survey += 50_000.0 * abundance * np.exp(
            -((mz - centre) ** 2) / 0.0002)
    panel.set_spectrum(mz, intensity, 430.35, "Positive", survey=(mz, survey))
    panel.own_formula.setText("C24H40O5")
    panel.own_deuterium.setValue(4)
    adduct, reason = panel._own_adduct("C24H40O5", 4)

    assert adduct is ch.ADDUCTS_BY_NAME["[M+NH4]+"]
    assert "confirmed by the survey" in reason
    assert panel.adduct_provenance.startswith(
        "adduct [M+NH4]+ confirmed by the survey")
    explorer.library_panel._pull_spectrum()
    comment = explorer.library_panel.own_prefill()["comment"]
    assert "adduct [M+NH4]+ confirmed by the survey" in comment
    explorer.deleteLater()


# --------------------------------------------------------------------------- #
# a whole batch of infusions in one go
# --------------------------------------------------------------------------- #
# The Explorer writes one record at a time; a folder of infusions is nine of
# them, and the tab that measured them already holds every number a record
# needs. What is tested here is what a batch adds that one spectrum does not:
# the provenance a record carries, the duplicate that provenance prevents, the
# reason a row that produced nothing gives — and then reading the files again
# and finding the same peaks.
from milq import infusion_report as ir  # noqa: E402
from milq.library import (Provenance, identity_of,  # noqa: E402
                               own_peaks, provenance_comment, provenance_keys,
                               provenance_of, records_from_summary,
                               rewrite_records)
from milq.session import Session  # noqa: E402


def _batch(qapp_module, *names):
    """A session of infused standards the method knows the formula of."""
    from milq.components import Component
    from tests.test_infusion_report import ADDUCT, FORMULA, _entry, _ions

    session = Session()
    channels = []
    for name in names:
        entry, channel = _entry(name=name)
        session.entries.append(entry)
        channels.append(channel)
    session.method.replace_all([
        Component(name="TESTOL", precursor=_ions()[0], formula=FORMULA,
                  adduct=ADDUCT)])
    return session, channels


class _FakeFile:
    """Enough of a reader for `rewrite_records`: one sample, its channels."""

    def __init__(self, sample):
        self._sample = sample
        self.sample_names = [sample.name]
        self.closed = False

    def sample(self, index: int = 0):
        return self._sample

    def close(self) -> None:
        self.closed = True


def _reader_for(session):
    """A reader that hands back the fixtures' samples by file name."""
    samples = {os.path.basename(e.path): e.sample for e in session.entries}

    def reader(path):
        return _FakeFile(samples[os.path.basename(path)])

    return reader


def _on_disk(folder, session):
    """The acquisitions as empty files, so `rewrite_records` finds them.

    The reader is a fake; what has to be real is only that a file of that
    name exists, which is the question the rewrite actually asks of a disk.
    """
    for entry in session.entries:
        (folder / os.path.basename(entry.path)).write_bytes(b"")
    return str(folder)


class _Correction:
    """A mass correction of a fixed number of ppm, as `recalibrate` gives."""

    usable = True

    def __init__(self, ppm: float):
        self.ppm = float(ppm)

    def ppm_at(self, mz):
        return np.full(np.asarray(mz, dtype=float).shape, self.ppm)

    def apply(self, mz):
        return np.asarray(mz, dtype=float) * (1.0 + self.ppm * 1e-6)


def test_a_record_is_made_of_every_measured_row(qapp_module):
    session, _channels = _batch(qapp_module, "TESTOL_infusion_A",
                                "TESTOL_infusion_B")
    summary = ir.summarise(session)
    made = records_from_summary(
        summary, added="2026-09-10",
        acquired={"TESTOL_infusion_A.wiff": "2026-09-02T15:06:00Z"})

    assert len(made) == 2 and not made.skipped
    first = made.entries[0]
    assert first.name == "TESTOL"                    # the compound, not the file
    # the peaks the table was measured from, not a second opinion about them
    assert first.peaks == len(summary.rows[0].peaks)
    assert first.mz == pytest.approx(
        sorted(m for m, _i in summary.rows[0].peaks))
    # the formula and the adduct the report identified, and a precursor that
    # is what they weigh rather than what the method typed
    assert first.formula and first.precursor_type
    assert not first.precursor_disagrees
    assert first.precursor == pytest.approx(first.exact_precursor)
    assert first.fields["Acquired"] == "2026-09-02T15:06:00Z"
    assert float(first.fields["Base_peak_intensity"]) > 0
    # and the provenance: the file and the channel it came from
    provenance = provenance_of(first)
    assert provenance.file == "TESTOL_infusion_A.wiff"
    assert provenance.channel.startswith("TOF PI")
    assert provenance.scans == 160 and provenance.added == "2026-09-10"
    assert provenance.rt_range == pytest.approx((0.0, 1.5))
    assert made.line() == "2 record(s) written."


def test_the_provenance_key_is_the_file_and_the_channel(qapp_module, tmp_path):
    session, _channels = _batch(qapp_module, "TESTOL_infusion_A",
                                "TESTOL_infusion_B")
    summary = ir.summarise(session)
    path = tmp_path / "mine.msp"
    made = records_from_summary(summary)
    write_msp(made.entries, path, append=True)
    assert len(load_library(path)) == 2

    # the same batch offered again: both rows are already in the file, by the
    # acquisition and the channel their comments name
    keys = provenance_keys(path)
    assert keys == {provenance_of(entry).key for entry in made.entries}
    assert len(keys) == 2
    assert sorted(file for file, _channel in keys) == [
        "testol_infusion_a.wiff", "testol_infusion_b.wiff"]
    assert all(channel.startswith("tof pi") for _file, channel in keys)
    again = records_from_summary(summary, existing=keys)
    assert not again.entries and len(again.skipped) == 2
    assert "already in the file" in again.skipped[0].reason
    assert "2 skipped" in again.line(0)

    # and a row repeated inside one batch is written once, not twice
    twice = records_from_summary(list(summary.rows) + list(summary.rows))
    assert len(twice.entries) == 2 and len(twice.skipped) == 2


def test_a_row_that_gives_no_record_says_why():
    """
    A row with nothing to write is a row somebody has to decide about, and a
    count of what was written hides which one it was.
    """
    class _Report:
        compound = ""
        sample = "nameless.wiff"
        file = "nameless.wiff"
        scans = 0

    class _Row:
        report = _Report()
        compound = ""
        peaks: list = []

    empty = _Row()
    quiet = _Row()
    quiet.compound = "CA-d4"
    quiet.report = _Report()
    quiet.report.compound = "CA-d4"
    made = records_from_summary([empty, quiet])

    assert not made.entries and len(made.skipped) == 2
    assert "no compound could be proposed" in made.skipped[0].reason
    assert "base peak" in made.skipped[1].reason
    assert str(made.skipped[0]).startswith("nameless.wiff (")
    assert made.line(0).startswith("0 record(s) written, 2 skipped:")


def test_an_empty_provenance_is_never_a_duplicate():
    entry = a_record(comment="written from something, somewhere")
    provenance = provenance_of(entry)
    assert not provenance.keyed and provenance.file == ""
    assert provenance_of(entry_from_spectrum("bare", MZ, INTENSITY)) \
        == Provenance()
    # and the comment a batch writes reads back as what was written
    comment = provenance_comment(file="/a/b/CA.wiff", sample="Mix1",
                                 channel="TOF PI 430.35", scans=339,
                                 rt_range=(0.0031, 8.2455), added="2026-09-10")
    assert comment.startswith("Mix1 · TOF PI 430.35 · average of 339 scans")
    assert "CA.wiff" in comment and "/a/b/" not in comment



def test_a_comment_is_read_by_whole_words_and_not_by_position():
    """
    A sample is named by whoever ran it, and the parser has to survive that.
    `^CE` alone takes `CEramide` for a collision energy, and a date at the
    front of a name is not a scan count.
    """
    def read(comment):
        return provenance_of(a_record(comment=comment))

    one = read("CEramide-d7_run · TOF PI 520.50 · average of 100 scans · "
               "RT 0.0–1.0 min · 20260902_CEramide.wiff · added 2026-09-10")
    assert one.sample == "CEramide-d7_run" and one.channel == "TOF PI 520.50"
    assert one.file == "20260902_CEramide.wiff" and one.scans == 100

    two = read("20260902_mix1 · TOF MS (50-700) · a.mzML · added 2026-01-01")
    assert two.sample == "20260902_mix1" and two.channel == "TOF MS (50-700)"
    assert two.file == "a.mzML" and two.rt_range is None
    # a background-subtracted average says so, and that is not the channel
    three = read("Mix1 · TOF PI 430.35 · average of 12 scans (1–12) · "
                 "background subtracted · a.wiff")
    assert three.channel == "TOF PI 430.35" and three.scans == 12

# --------------------------------------------------------------------------- #
# rewritten from the files
# --------------------------------------------------------------------------- #
def test_rewriting_finds_the_same_peaks_and_adds_what_was_missing(
        qapp_module, tmp_path):
    session, _channels = _batch(qapp_module, "TESTOL_infusion_A")
    summary = ir.summarise(session)
    path = tmp_path / "mine.msp"
    made = records_from_summary(summary, added="2026-09-10")
    write_msp(made.entries, path, append=True)
    before = load_library(path).entries[0]

    # an old record of the same acquisition: no Acquired, no base peak
    # height, and a precursor typed to two decimals
    old = ("Name: TESTOL (older)\n"
           f"PrecursorMZ: {before.precursor:.2f}\n"
           f"Precursor_type: {before.precursor_type}\n"
           f"Formula: {before.formula}\n"
           f"Comment: {before.fields['Comment']}\n"
           "Num Peaks: 1\n"
           "100.00000 100\n\n")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(old)
    assert len(load_library(path)) == 2

    result = rewrite_records(path, folders=[_on_disk(tmp_path, session)],
                             reader=_reader_for(session))

    assert len(result.rewritten) == 2 and not result.kept
    assert result.recalibrated == 0
    assert os.path.exists(result.backup) and result.backup.endswith(".msp.bak")
    assert "Name: TESTOL (older)" in open(result.backup, encoding="utf-8").read()

    after = {e.name: e for e in load_library(path).entries}
    fresh = after["TESTOL"]
    # byte for byte the same measurement: the file was read again and the
    # same peaks came back out of it
    assert np.array_equal(fresh.mz, before.mz)
    assert np.array_equal(fresh.intensity, before.intensity)
    # and it gains what the row could not supply: the session held the
    # sample, and the file holds the day the instrument measured on
    assert "Acquired" not in before.fields
    assert fresh.fields["Acquired"] == "2026-09-09T09:00:00Z"

    older = after["TESTOL (older)"]
    assert older.peaks == fresh.peaks          # read from the file, not kept
    assert older.fields["Acquired"] == "2026-09-09T09:00:00Z"
    assert float(older.fields["Base_peak_intensity"]) > 0
    # the precursor it was written with was rounded; its formula's is not
    assert older.precursor == pytest.approx(older.exact_precursor)
    assert not older.precursor_disagrees
    assert provenance_of(older).added == provenance_of(before).added


def test_a_record_whose_file_is_gone_is_kept_exactly_as_it_was(
        qapp_module, tmp_path):
    session, _channels = _batch(qapp_module, "TESTOL_infusion_A")
    summary = ir.summarise(session)
    path = tmp_path / "mine.msp"
    write_msp(records_from_summary(summary).entries, path, append=True)
    write_msp([a_record(name="cholic acid-d4",
                        comment="Mix1 · TOF PI 411.31 · gone.wiff · "
                                "added 2026-01-01")], path, append=True)
    write_msp([a_record(name="from somebody else", comment="no file named")],
              path, append=True)
    kept_before = {e.name: (e.mz.copy(), e.intensity.copy(), dict(e.fields))
                   for e in load_library(path).entries}

    result = rewrite_records(path, folders=[_on_disk(tmp_path, session)],
                             reader=_reader_for(session))

    assert result.rewritten == ["TESTOL"]
    reasons = dict(result.kept)
    assert "gone.wiff is not on disk" in reasons["cholic acid-d4"]
    assert "names no acquisition" in reasons["from somebody else"]
    assert "1 record(s) rewritten" in result.summary()
    assert "2 kept as they were" in result.summary()
    after = {e.name: e for e in load_library(path).entries}
    for name in ("cholic acid-d4", "from somebody else"):
        mz, intensity, fields = kept_before[name]
        assert np.array_equal(after[name].mz, mz)
        assert np.array_equal(after[name].intensity, intensity)
        assert after[name].fields == fields


def test_a_correction_in_force_moves_the_axis_and_the_comment_says_so(
        qapp_module, tmp_path):
    session, _channels = _batch(qapp_module, "TESTOL_infusion_A")
    summary = ir.summarise(session)
    path = tmp_path / "mine.msp"
    write_msp(records_from_summary(summary).entries, path, append=True)
    before = load_library(path).entries[0]

    result = rewrite_records(
        path, folders=[_on_disk(tmp_path, session)],
        reader=_reader_for(session),
        corrections={"TESTOL_infusion_A.wiff": _Correction(-5.2)})

    assert result.recalibrated == 1
    after = load_library(path).entries[0]
    assert after.mz == pytest.approx(before.mz * (1 - 5.2e-6), abs=1e-5)
    assert "recalibrated -5.2 ppm" in after.fields["Comment"]
    # and the provenance still reads: a note is not a piece of it
    assert provenance_of(after).file == "TESTOL_infusion_A.wiff"
    assert provenance_of(after).channel.startswith("TOF PI")


def test_the_peaks_a_record_is_made_of_are_the_ones_the_table_measured(
        qapp_module):
    session, channels = _batch(qapp_module, "TESTOL_infusion_A")
    summary = ir.summarise(session)
    mz, intensity = channels[0].spectrum_rt_range(0.0, 1.5)
    assert own_peaks(mz, intensity) == summary.rows[0].peaks


def test_the_identity_is_read_off_the_report_and_not_guessed(qapp_module):
    session, _channels = _batch(qapp_module, "TESTOL_infusion_A")
    from tests.test_infusion_report import ADDUCT, FORMULA

    row = ir.summarise(session).rows[0]
    assert identity_of(row.report) == (FORMULA, ADDUCT)

    class _Silent:
        basis = ""
        explanation = None
    assert identity_of(_Silent()) == ("", "")


# --------------------------------------------------------------------------- #
# the two buttons
# --------------------------------------------------------------------------- #
def test_the_infusions_tab_writes_a_record_for_every_row(qapp_module, tmp_path):
    from milq import audit
    from milq.ui.infusions_panel import InfusionsPanel

    session, _channels = _batch(qapp_module, "TESTOL_infusion_A",
                                "TESTOL_infusion_B")
    panel = InfusionsPanel(session)
    path = str(tmp_path / "mine.msp")
    panel.settings.setValue("library/own_path", path)
    try:
        assert not panel.btn_library.isEnabled()      # nothing measured yet
        panel.measure(threaded=False)
        assert panel.btn_library.isEnabled()

        made = panel.add_all_to_library()
        assert len(made.entries) == 2
        assert "2 record(s) written" in panel.status.text()
        assert os.path.basename(path) in panel.status.text()
        assert len(load_library(path)) == 2
        assert len(session.audit.of(audit.OWN_LIBRARY)) == 1

        # pressed twice, the file does not grow
        again = panel.add_all_to_library()
        assert not again.entries and len(again.skipped) == 2
        assert len(load_library(path)) == 2
        assert len(session.audit.of(audit.OWN_LIBRARY)) == 1
    finally:
        panel.settings.remove("library/own_path")
        panel.deleteLater()


def test_the_library_panel_rewrites_and_leaves_what_it_cannot_find(panel,
                                                                   tmp_path):
    path = str(tmp_path / "mine.msp")
    write_msp([a_record(name="cholic acid-d4",
                        comment="Mix1 · TOF PI 411.31 · CA-d4_Mix1.wiff · "
                                "added 2026-01-01")], path)
    panel.set_own_path(path)
    assert panel.btn_rewrite.isEnabled()

    result = panel.rewrite_own_library(confirm=False)

    # nothing is on disk here, so nothing is rewritten and nothing is lost
    assert result is not None and not result.rewritten
    assert result.backup == "" and len(result.kept) == 1
    assert "CA-d4_Mix1.wiff is not on disk" in result.kept[0][1]
    assert "kept as they were" in panel.status.text()
    assert len(load_library(path)) == 1
    assert not os.path.exists(path + ".bak")


def test_the_library_panel_asks_the_session_where_the_files_are(panel):
    class _Entry:
        path = "/data/infusions/CA-d4_Mix1.wiff"
        key = "/data/infusions/CA-d4_Mix1.wiff|0"

    class _Session:
        entries = [_Entry()]
        def correction_for(self, key):
            return _Correction(-3.0) if key == _Entry.key else None

    panel.session = _Session()
    assert "/data/infusions" in panel._acquisition_folders()
    assert set(panel._corrections()) == {"ca-d4_mix1.wiff"}
    # no session at all is the ordinary case for a panel with nothing open
    panel.session = None
    assert panel._corrections() == {}


def test_the_rewrite_button_asks_before_it_writes(panel):
    """
    `clicked` carries the button's checked state. Connected straight to
    `rewrite_own_library` it would arrive as `confirm=False`, and the button
    would write over a library of months' work without asking.
    """
    called = []
    panel.rewrite_own_library = lambda *args, **kwargs: called.append(
        (args, kwargs))
    panel.btn_rewrite.setEnabled(True)
    panel.btn_rewrite.click()
    assert called == [((), {})]          # no `False` for confirm
