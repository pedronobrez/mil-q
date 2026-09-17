"""
The New standard dialog: a bottle into the method, the library and the history.

The dialog writes into three places at once, so what is worth testing is that
it writes into all of them from one act — and, far more, that it writes into
none of them when it cannot identify the compound. A component with an
invented mass is worse than no component, and every refusal here is a refusal
to write one: a file that is not an infusion, a name that resolves to nothing,
and a precursor that is no adduct of the formula.

The infusion is a fake sample rather than a `.wiff`, the way the rest of the
infusion tests build one; the library is a real MSP in a temporary directory,
read back with the real parser, because a record that cannot be read back is
not a record.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import audit  # noqa: E402
from milq import standard_history as sh  # noqa: E402
from milq.library import load_library, provenance_of  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.ui.new_standard_dialog import NewStandardDialog  # noqa: E402
from tests.test_infusion_report import (ADDUCT, FORMULA,  # noqa: E402
                                        FakeChannel, FakeSample, _entry,
                                        _grid, _ions)

#: a name the standards table knows by itself, with no LIPID MAPS installed
KNOWN = "cholic acid-d4"


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _session(*entries) -> Session:
    session = Session()
    session.entries.extend(entries)
    return session


def _dialog(session, name: str = "") -> NewStandardDialog:
    dialog = NewStandardDialog(session, name=name)
    # nothing of the person's own library reaches a test
    dialog.settings.remove("library/own_path")
    return dialog


def _ready(session, entry, channel, name="Testol", lot="LOT-1"
           ) -> NewStandardDialog:
    """A dialog with everything given: the name, the formula and the file."""
    dialog = _dialog(session)
    dialog.name_edit.setText(name)
    dialog.formula_edit.setText(FORMULA)
    dialog._formula_changed()
    dialog.lot_edit.setText(lot)
    dialog.use_sample(entry, channel)
    return dialog


def _chromatographic(name="GRADIENT_S001"):
    """A sample with a peak in it, which is what an infusion is not."""
    ions = _ions()
    mz = _grid(ions[:3])
    channel = FakeChannel(0, mz, {ions[1]: 4_000.0}, precursor=ions[0])
    rt = channel.rt
    channel._y = 50_000.0 * np.exp(-0.5 * ((rt - 0.75) / 0.03) ** 2)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = FakeSample([channel], name=name)
    return entry, channel


# --------------------------------------------------------------------------- #
# the name
# --------------------------------------------------------------------------- #
def test_the_name_is_resolved_as_it_is_typed(qapp):
    dialog = _dialog(_session())
    dialog.name_edit.setText(KNOWN)
    dialog._name_changed()

    assert dialog.formula_edit.text() == "C24H40O5"
    assert dialog.labels_spin.value() == 4
    said = dialog.resolved.text()
    assert "C24H40O5" in said and "standards table" in said
    assert "4 unplaced label" in said
    # the LIPID MAPS identifier only where the database is installed: a
    # machine without it still resolves the name, from the standards table
    from milq.lipidmaps import database

    if database() is not None:
        assert "LMST04010001" in said


def test_a_name_nothing_knows_says_so_and_offers_no_formula(qapp):
    dialog = _dialog(_session())
    dialog.name_edit.setText("zqxjwv-42")
    dialog._name_changed()

    assert dialog.formula_edit.text() == ""
    assert "is not a name" in dialog.resolved.text()
    assert not dialog.btn_create.isEnabled()


def test_a_typed_formula_is_not_overwritten_by_the_name(qapp):
    """A resolution is a proposal; a typed formula is a decision."""
    dialog = _dialog(_session())
    dialog.formula_edit.setText("C20H34O2")
    dialog._formula_changed()
    dialog.name_edit.setText(KNOWN)
    dialog._name_changed()

    assert dialog.formula_edit.text() == "C20H34O2"
    assert "C24H40O5" in dialog.resolved.text()   # still says what it knows


# --------------------------------------------------------------------------- #
# the adducts
# --------------------------------------------------------------------------- #
def test_only_the_polarity_s_adducts_are_offered_and_the_fit_is_ticked(qapp):
    entry, channel = _entry()
    dialog = _ready(_session(entry), entry, channel)

    offered = {name: box for name, box in dialog.adduct_boxes.items()
               if not box.isHidden()}
    assert "[M+H]+" in offered and "[M-H]-" not in offered, \
        "a positive channel cannot have produced a negative adduct"
    assert dialog.expected == [ADDUCT]
    assert dialog._declared() == ADDUCT
    # every candidate is shown with how far off it is, fit or miss
    assert "ppm" in offered["[M+NH4]+"].text()
    assert not offered["[M+NH4]+"].isChecked()
    assert f"1 of {len(offered)} adduct(s)" in dialog.adduct_note.text()


def test_an_expected_adduct_that_fits_nothing_is_overruled_and_said_so(qapp):
    """A tick is an expectation; the written precursor is a measurement."""
    entry, channel = _entry()
    dialog = _ready(_session(entry), entry, channel)
    dialog.adduct_boxes[ADDUCT].setChecked(False)
    dialog.adduct_boxes["[M+Na]+"].setChecked(True)

    assert dialog._declared() == "[M+Na]+"
    assert dialog.plan.identification.adduct == ADDUCT, \
        "the channel decides; the tick does not"
    assert "not the [M+Na]+ you expected" in dialog.report.basis
    assert "not the [M+Na]+ you expected" in dialog.preview_html()
    assert dialog.btn_create.isEnabled()


# --------------------------------------------------------------------------- #
# the preview
# --------------------------------------------------------------------------- #
def test_the_preview_says_what_was_measured(qapp):
    entry, channel = _entry(with_survey=True)
    dialog = _ready(_session(entry), entry, channel)
    said = dialog.preview_html()

    precursor = _ions()[0]
    assert ADDUCT in said and "confirmed by the survey" in said
    assert f"{precursor:.4f}" in said                   # the exact mass
    assert "base peak" in said and "9,000 counts" in said
    assert "of the intensity" in said                   # the explained share
    assert "predicted ion(s)" in said
    assert "new component" in said and "Record" in said
    assert "the library read back" in said


def test_the_preview_is_measured_again_without_averaging_again(qapp):
    """The average is what costs; everything after it is arithmetic."""
    entry, channel = _entry()
    dialog = _ready(_session(entry), entry, channel)
    held = dialog.averaged
    calls = []
    original = channel.spectrum_rt_range
    channel.spectrum_rt_range = lambda *a, **k: (calls.append(1),
                                                 original(*a, **k))[1]

    dialog.name_edit.setText("Testol B")
    dialog.measure()

    assert calls == [], "the run was averaged a second time"
    assert dialog.averaged is held


# --------------------------------------------------------------------------- #
# what Create writes
# --------------------------------------------------------------------------- #
def test_create_writes_the_component_the_record_and_one_audit_entry(qapp,
                                                                    tmp_path):
    entry, channel = _entry()
    session = _session(entry)
    dialog = _ready(session, entry, channel, name="Testol", lot="CDN-D-2452")
    path = str(tmp_path / "mine.msp")

    assert dialog.btn_create.isEnabled()
    assert dialog.create(path=path) is True

    # (a) the component
    component = dialog.component
    assert component is not None and session.method.components == [component]
    assert component.name == "Testol"
    assert component.precursor == pytest.approx(_ions()[0], abs=1e-6)
    assert component.fragment is not None
    assert component.formula == FORMULA and component.adduct == ADDUCT
    assert component.is_internal_standard and component.rt is None
    assert "CDN-D-2452" in component.provenance
    assert "TESTOL_infusion_A" in component.provenance

    # (b) the record, read back with the real parser
    library = load_library(path)
    assert len(library) == 1
    record = library.entries[0]
    assert record.name == "Testol"
    assert record.formula == FORMULA and record.precursor_type == ADDUCT
    assert record.precursor == pytest.approx(_ions()[0], abs=1e-4)
    assert provenance_of(record).lot == "CDN-D-2452"
    assert provenance_of(record).file == "TESTOL_infusion_A.wiff"

    # (c) one entry naming all three
    entries = session.audit.of(audit.NEW_STANDARD)
    assert len(entries) == 1 and len(session.audit) == 1
    said = entries[0].after
    assert entries[0].target == "Testol"
    assert "1 record(s) in mine.msp" in said and "history 1 record(s)" in said
    assert f"{component.precursor:.4f}" in said
    assert "CDN-D-2452" in entries[0].note


def test_the_history_is_the_library_read_back_and_is_never_written(qapp,
                                                                   tmp_path):
    """Two infusions of one standard: two records, one history, no third
    file."""
    path = str(tmp_path / "mine.msp")
    session = Session()
    made = []
    for name in ("TESTOL_infusion_A", "TESTOL_infusion_B"):
        entry, channel = _entry(name=name)
        session.entries.append(entry)
        dialog = _ready(session, entry, channel, name="Testol")
        assert dialog.create(path=path) is True
        made.append(dialog)

    # the second wrote no component — the first left nothing to fill — and
    # is still a record, and a record is a history entry
    assert made[1].component is None and made[1].record is not None
    assert sorted(os.listdir(tmp_path)) == ["mine.msp"]
    history = sh.read_history(path)
    assert history.compounds == ["Testol"]
    assert sum(len(series.records) for series in history.for_compound(
        "Testol")) == 2
    assert "history 2 record(s)" in session.audit.of(
        audit.NEW_STANDARD)[-1].after


def test_a_second_component_of_the_same_name_completes_rather_than_repeats(
        qapp, tmp_path):
    path = str(tmp_path / "mine.msp")
    session = Session()
    first, first_channel = _entry(name="TESTOL_infusion_A")
    session.entries.append(first)
    _ready(session, first, first_channel, name="Testol").create(path=path)

    second, second_channel = _entry(name="TESTOL_infusion_B")
    session.entries.append(second)
    dialog = _ready(session, second, second_channel, name="Testol")

    assert not dialog.plan.is_new
    assert "Testol" in dialog.plan.into
    assert len(session.method.components) == 1
    # and Create is still offered, because the record is still worth writing
    assert dialog.btn_create.isEnabled()
    assert "still" in dialog.status.text()


# --------------------------------------------------------------------------- #
# where it refuses
# --------------------------------------------------------------------------- #
def test_a_precursor_no_adduct_fits_disables_create_and_writes_nothing(
        qapp, tmp_path):
    """The `_TESTEARTIGO` case: a file named after a compound whose method
    isolates something else."""
    ions = _ions()
    mz = _grid(ions[:3])
    channel = FakeChannel(0, mz, {ions[1]: 4_000.0}, precursor=839.56)
    entry = SampleEntry("/d/TESTOL_stray.wiff", 0, "TESTOL_stray")
    entry.sample = FakeSample([channel], name="TESTOL_stray")
    session = _session(entry)
    dialog = _ready(session, entry, channel)
    path = str(tmp_path / "mine.msp")

    assert dialog.expected == [], "nothing reaches 839.56"
    assert not dialog.btn_create.isEnabled()
    assert "none of the adducts" in dialog.plan.refusal
    assert FORMULA in dialog.plan.refusal, "refused on the typed formula"
    assert "closest" in dialog.plan.refusal
    assert "0 of 5 adduct(s)" in dialog.adduct_note.text()
    assert "Nothing is written" in dialog.preview_html()

    assert dialog.create(path=path) is False
    assert session.method.components == []
    assert not os.path.exists(path)
    assert len(session.audit) == 0


def test_a_sample_that_is_not_an_infusion_is_refused_with_its_figures(qapp):
    entry, channel = _chromatographic()
    dialog = _dialog(_session(entry))
    dialog.name_edit.setText("Testol")
    dialog.formula_edit.setText(FORMULA)

    assert dialog.use_sample(entry, channel) is False
    assert "not a direct infusion" in dialog.refusal
    assert "%" in dialog.refusal and "chromatographic" in dialog.refusal
    assert not dialog.btn_create.isEnabled()
    assert dialog.report is None


def test_a_file_that_will_not_open_is_refused_by_name(qapp, tmp_path):
    dialog = _dialog(_session())

    assert dialog.set_file(str(tmp_path / "absent.wiff")) is False
    assert "absent.wiff" in dialog.refusal
    assert not dialog.btn_create.isEnabled()


def test_an_open_acquisition_is_used_where_it_is_rather_than_opened_again(
        qapp):
    entry, channel = _entry()
    session = _session(entry)
    dialog = _dialog(session)
    dialog.name_edit.setText("Testol")
    dialog.formula_edit.setText(FORMULA)
    dialog._formula_changed()

    assert dialog.set_file(entry.path) is True
    assert dialog.entry is entry
    assert dialog.own_session is None, "the batch on screen was reopened"


def test_nothing_is_written_before_create_is_pressed(qapp, tmp_path):
    entry, channel = _entry()
    session = _session(entry)
    dialog = _ready(session, entry, channel)

    assert dialog.report is not None and dialog.plan is not None
    assert session.method.components == []
    assert len(session.audit) == 0
    assert os.listdir(tmp_path) == []


# --------------------------------------------------------------------------- #
# where it is offered from
# --------------------------------------------------------------------------- #
def test_the_dialog_names_a_manual_page_that_exists(qapp):
    from milq.manual import manual
    from milq.ui.help_window import help_page_for

    dialog = _dialog(_session())

    assert help_page_for(dialog) == "new-standard"
    assert "new-standard" in manual().pages


def test_the_infusions_tab_offers_it_without_a_measure(qapp):
    """Entering a standard reads one file; the summary is a table of many."""
    from milq.ui.infusions_panel import InfusionsPanel

    panel = InfusionsPanel(_session())

    assert panel.btn_new_standard.isEnabled()
    assert panel.summary is None


def test_the_file_menu_offers_it_and_the_shell_refreshes_what_it_wrote(qapp):
    from milq.ui.shell import MainShell

    shell = MainShell()
    try:
        assert shell.act_new_standard.text().startswith("New standard")
        # the two panels a new standard changes
        shell.refresh_standards()
    finally:
        shell.close()


def test_a_typed_formula_beats_whatever_the_name_resolves_to(
        qapp, tmp_path, monkeypatch):
    """
    The plan used to resolve the name again behind the dialog's back. On a
    machine with LIPID MAPS installed `Testol` reached testolactone
    (C19H24O3) and the refusal named that compound's adducts; on a machine
    without it the same file was refused for having no formula at all —
    the CI failure that found this. A typed formula is a decision.
    """
    from milq import explain
    from milq.explain import NamedCompound

    def elsewhere(written):
        return NamedCompound(written=written, compound="testolactone",
                             formula="C19H24O3", labels=0, source="LIPID MAPS")
    # `standards` and the dialog both import it from `explain` at call time
    monkeypatch.setattr(explain, "resolve_name", elsewhere)

    ions = _ions()
    mz = _grid(ions[:3])
    channel = FakeChannel(0, mz, {ions[1]: 4_000.0}, precursor=839.56)
    entry = SampleEntry("/d/TESTOL_stray.wiff", 0, "TESTOL_stray")
    entry.sample = FakeSample([channel], name="TESTOL_stray")
    dialog = _ready(_session(entry), entry, channel)

    assert FORMULA in dialog.plan.refusal
    assert "C19H24O3" not in dialog.plan.refusal
    assert not dialog.btn_create.isEnabled()

    # and with nothing to resolve the name to, the same refusal for the
    # same reason
    monkeypatch.setattr(explain, "resolve_name", lambda written: None)
    dialog = _ready(_session(entry), entry, channel)
    assert FORMULA in dialog.plan.refusal
    assert "none of the adducts" in dialog.plan.refusal
