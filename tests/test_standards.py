"""
An infused standard written into the method.

The claims worth holding down are about *which number goes where*. The
precursor a component gets is the exact mass of the identified adduct and not
the value written on the channel — 430.3465, not 430.35 — and the difference
between the two is shown rather than swallowed. A compound the method already
carries is completed and never overwritten. And every row says where it came
from, in the component, in the tooltip and in the trail.

Most of what follows builds the infusion by hand: a real `InfusionReport`
whose averaged spectrum is a few profile peaks, which needs no file and no
reader, plus one deliberately foreign object to prove the module reads a row
defensively rather than by type.
"""

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq import audit, standards  # noqa: E402
from milq import infusion_report as ir  # noqa: E402
from milq.components import (Component, load_components,  # noqa: E402
                                  save_components)
from milq.method import ProcessingMethod  # noqa: E402
from milq.session import Session  # noqa: E402

#: cholic acid-d4 as its ammonium adduct: what the standards table, the four
#: labels the name declares and `[M+NH4]+` come to
EXACT = 430.34650691392
#: what the acquisition method has typed on the channel
WRITTEN = 430.35
BASE = 359.2870
SECOND = 217.1880


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


#: half width of the profile peak each fixture mass is drawn as, and the
#: step along it. Dense on purpose: a spectrum of three points per peak is
#: centroided across the gaps between them and comes back with masses that
#: are in neither the fixture nor any real file — the same trap
#: `processing.restore_profile_zeros` exists for.
PEAK_HALF_WIDTH = 0.05
PEAK_STEP = 0.005
PEAK_SIGMA = 0.012


def _spectrum(peaks) -> tuple[np.ndarray, np.ndarray]:
    """A profile axis carrying a narrow Gaussian on each of `peaks`."""
    mz = np.unique(np.concatenate([
        np.arange(centre - PEAK_HALF_WIDTH,
                  centre + PEAK_HALF_WIDTH + PEAK_STEP / 2, PEAK_STEP)
        for centre, _height in peaks]))
    intensity = np.zeros_like(mz)
    for centre, height in peaks:
        intensity += height * np.exp(
            -0.5 * ((mz - centre) / PEAK_SIGMA) ** 2)
    return mz, intensity


def _report(compound: str = "CA-d4", written: float = WRITTEN,
            peaks=((BASE, 5673.0), (SECOND, 839.0), (145.0998, 568.0)),
            **extra) -> ir.InfusionReport:
    """One infusion, built without a file: a report with an averaged spectrum."""
    mz, intensity = _spectrum(peaks)
    report = ir.InfusionReport(
        compound=compound,
        file=f"{compound}_TOFMSMS_Mix1.wiff",
        sample=f"{compound}_TOFMSMS_Mix1",
        polarity="Positive",
        channel=f"TOF PI {written} -> 50-450, CE 45",
        channel_name="TOF PI",
        written_precursor=written,
        collision_energy=45.0,
        label_floor=0.01,
    )
    report.spectrum = ir.one_spectrum("infusion", mz, intensity,
                                      label_floor=0.01)
    for key, value in extra.items():
        setattr(report, key, value)
    return report


# --------------------------------------------------------------------------- #
# the component
# --------------------------------------------------------------------------- #
def test_precursor_is_the_exact_mass_and_not_the_written_one():
    component = standards.component_from_infusion(_report())
    assert component is not None
    assert component.name == "CA-d4"
    assert component.formula == "C24H36D4O5"         # the -d4 the name declares
    assert component.adduct == "[M+NH4]+"
    assert component.precursor == pytest.approx(EXACT, abs=1e-6)
    # the written value is nowhere in the component, and is 8 ppm away
    assert component.precursor != pytest.approx(WRITTEN, abs=1e-4)
    identification = standards.identify(_report())
    assert identification.error_ppm == pytest.approx(8.1, abs=0.2)
    assert "430.3465" in identification.note and "430.35" in identification.note


def test_no_retention_time_and_the_group_says_where_it_came_from():
    component = standards.component_from_infusion(_report())
    assert component.rt is None                       # an infusion has none
    assert component.group == standards.GROUP
    assert component.is_internal_standard is True
    assert standards.component_from_infusion(
        _report(), as_internal_standard=False).is_internal_standard is False


def test_the_fragment_is_the_base_peak_or_the_peak_chosen():
    report = _report()
    choices = standards.fragment_choices(report)
    assert [round(c.mz, 4) for c in choices][:2] == [BASE, SECOND]
    assert choices[0].base and not choices[1].base
    assert "base peak" in choices[0].text

    base = standards.component_from_infusion(report)
    assert base.fragment == pytest.approx(BASE, abs=1e-3)
    chosen = standards.component_from_infusion(report, fragment=choices[1])
    assert chosen.fragment == pytest.approx(SECOND, abs=1e-3)
    by_mass = standards.component_from_infusion(report, fragment=SECOND)
    assert by_mass.fragment == pytest.approx(SECOND, abs=1e-3)


def test_the_provenance_says_which_infusion_it_was():
    report = _report()
    component = standards.component_from_infusion(
        report, acquired="2026-09-02T15:04:36")
    text = component.provenance
    assert "CA-d4_TOFMSMS_Mix1" in text
    assert "45 eV" in text
    assert "2026-09-02T15:04:36" in text
    assert ".wiff" in text
    # and the record of one's own, where the row found one
    hit = type("Hit", (), {"entry": type("Entry", (), {"name": "CA-d4 CID 45 eV"})})
    with_record = standards.component_from_infusion(_report(hit=hit))
    assert "CA-d4 CID 45 eV" in with_record.provenance


def test_a_precursor_no_adduct_fits_is_refused_rather_than_invented():
    """The `_TESTEARTIGO` case: the file is named CA-d4 and targets 839.56."""
    report = _report(written=839.56)
    assert standards.component_from_infusion(report) is None
    plan = standards.plan_for(report, ProcessingMethod())
    assert not plan.offered
    assert "839.56 is none of the adducts" in plan.refusal
    assert "C24H36D4O5" in plan.refusal


def test_a_row_is_read_by_attribute_and_not_by_type():
    """Anything carrying a `report` is a row; a report is its own row."""
    row = type("Row", (), {"report": _report()})()
    assert standards.report_of(row) is row.report
    assert standards.component_from_infusion(row).precursor == pytest.approx(
        EXACT, abs=1e-6)


# --------------------------------------------------------------------------- #
# completing what is already there
# --------------------------------------------------------------------------- #
def test_only_empty_cells_are_filled():
    method = ProcessingMethod()
    method.components.append(Component(name="CA-d4", precursor=WRITTEN,
                                       rt=4.20, rt_halfwidth=0.3))
    plan = standards.plan_for(_report(), method)
    assert not plan.is_new and plan.offered
    assert "completes CA-d4" in plan.into
    filled = dict(plan.fills)
    assert set(filled) == {"Fragment", "Formula", "Adduct", "Group",
                           "Provenance"}
    assert "Precursor" not in filled            # typed, and left alone

    plan.apply(method)
    kept = method.components[0]
    assert kept.precursor == pytest.approx(WRITTEN)   # not moved to the exact
    assert kept.rt == 4.20                             # nothing else touched
    assert kept.formula == "C24H36D4O5"
    assert kept.adduct == "[M+NH4]+"
    assert kept.fragment == pytest.approx(BASE, abs=1e-3)
    assert kept.is_internal_standard is True
    assert "CA-d4_TOFMSMS_Mix1" in kept.provenance
    assert len(method.components) == 1                 # completed, not added


def test_a_typed_value_that_disagrees_is_shown_and_kept():
    method = ProcessingMethod()
    method.components.append(Component(name="CA-d4", precursor=WRITTEN,
                                       formula="C24H40O5"))
    plan = standards.plan_for(_report(), method)
    shown = {label: (theirs, mine) for label, theirs, mine in plan.differences}
    assert shown["Precursor"] == ("430.3500", "430.3465")
    assert shown["Formula"] == ("C24H40O5", "C24H36D4O5")
    assert "430.3500 written, 430.3465 from the infusion" in plan.note
    assert "kept as written" in plan.note

    plan.apply(method)
    kept = method.components[0]
    assert kept.precursor == pytest.approx(WRITTEN)
    assert kept.formula == "C24H40O5"


def test_nothing_left_to_fill_is_not_offered():
    method = ProcessingMethod()
    written = standards.component_from_infusion(_report())
    method.components.append(written)
    plan = standards.plan_for(_report(), method)
    assert not plan.offered
    assert "nothing left to fill" in plan.into


def test_the_fragment_note_says_when_the_base_peak_is_the_precursor():
    """A soft activation leaves the precursor as the tallest peak."""
    report = _report(peaks=((430.3489, 12271.0), (78.0465, 901.0)))
    plan = standards.plan_for(report, ProcessingMethod())
    assert plan.offered
    assert "the precursor that survived" in plan.fragment_note
    assert plan.fragment_note in plan.note
    assert standards.plan_for(_report(), ProcessingMethod()).fragment_note == ""


# --------------------------------------------------------------------------- #
# the dialog and the trail
# --------------------------------------------------------------------------- #
def test_the_dialog_writes_the_ticked_rows_and_records_them(qapp):
    from milq.ui.standards_dialog import COL, StandardsDialog

    session = Session()
    session.method.components.append(
        Component(name="DCA-d4", precursor=414.34))
    rows = [_report(), _report(compound="DCA-d4", written=414.34,
                               peaks=((361.3017, 3109.0), (95.0844, 665.0)))]
    dialog = StandardsDialog(session, rows)
    assert dialog.table.rowCount() == 2
    assert dialog.plans[0].is_new and not dialog.plans[1].is_new

    # the fragment is chosen from a box holding the base peak and the rest
    combo = dialog.table.cellWidget(0, COL["Fragment"])
    assert combo.count() >= 2
    combo.setCurrentIndex(1)
    assert dialog.plans[0].proposed.fragment == pytest.approx(SECOND, abs=1e-3)

    # and the internal-standard box is per row
    holder = dialog.table.cellWidget(1, COL["IS"])
    box = holder.findChild(QtWidgets.QCheckBox)
    box.setChecked(False)
    assert dialog.plans[1].internal_standard is False

    assert dialog.apply_selected() == 2
    names = [c.name for c in session.method.components]
    assert names == ["DCA-d4", "CA-d4"]
    made = session.method.by_name("CA-d4")
    assert made.precursor == pytest.approx(EXACT, abs=1e-6)
    assert made.fragment == pytest.approx(SECOND, abs=1e-3)
    completed = session.method.by_name("DCA-d4")
    assert completed.precursor == pytest.approx(414.34)   # typed, kept
    assert completed.formula == "C24H36D4O4"
    assert completed.is_internal_standard is False

    entries = session.audit.of(audit.COMPONENT_FROM_INFUSION)
    assert len(entries) == 2
    by_target = {entry.target: entry for entry in entries}
    assert "430.3465" in by_target["CA-d4"].after
    assert "CA-d4_TOFMSMS_Mix1" in by_target["CA-d4"].note
    assert "Formula C24H36D4O4" in by_target["DCA-d4"].after
    assert by_target["DCA-d4"].before == "414.3400"
    assert session.dirty


def test_a_refused_row_cannot_be_ticked(qapp):
    from milq.ui.standards_dialog import COL, StandardsDialog

    session = Session()
    dialog = StandardsDialog(session, [_report(written=839.56)])
    tick = dialog.table.item(0, COL["Use"])
    assert tick.checkState() == QtCore.Qt.CheckState.Unchecked
    assert not (tick.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable)
    assert dialog.apply_selected() == 0
    assert not session.method.components


def test_a_second_infusion_of_one_compound_has_nothing_left_to_write(qapp):
    """Two energies of the same vial are one component, not two rows."""
    from milq.ui.standards_dialog import StandardsDialog

    session = Session()
    dialog = StandardsDialog(session, [_report(), _report()])
    assert dialog.apply_selected() == 1
    assert [c.name for c in session.method.components] == ["CA-d4"]
    assert dialog.skipped == ["CA-d4"]


# --------------------------------------------------------------------------- #
# the provenance survives everything it has to
# --------------------------------------------------------------------------- #
def test_provenance_round_trips_through_the_csv(tmp_path):
    component = standards.component_from_infusion(
        _report(), acquired="2026-09-02T15:04:36")
    path = tmp_path / "method.csv"
    save_components(path, [component])
    back = load_components(path)
    assert len(back) == 1
    assert back[0].provenance == component.provenance
    assert back[0].precursor == pytest.approx(EXACT, abs=1e-9)


def test_provenance_round_trips_through_the_project(tmp_path):
    method = ProcessingMethod()
    method.components.append(standards.component_from_infusion(_report()))
    path = tmp_path / "method.json"
    method.save(path)
    assert "provenance" in json.loads(path.read_text())["components"][0]
    back = ProcessingMethod.load(path)
    assert back.components[0].provenance == method.components[0].provenance


def test_the_method_table_shows_it_and_does_not_lose_it(qapp):
    """The table is committed whole on every edit; a field with no column of
    its own has to ride on one that has."""
    from milq.ui.method_workspace import COL, MethodWorkspace

    session = Session()
    session.method.components.append(standards.component_from_infusion(_report()))
    workspace = MethodWorkspace(session)
    workspace.reload()
    name = workspace.table.item(0, COL["Name"])
    assert "CA-d4_TOFMSMS_Mix1" in name.toolTip()

    workspace.table.item(0, COL["Group"]).setText("bile acids")
    workspace._commit()
    assert session.method.components[0].group == "bile acids"
    assert "CA-d4_TOFMSMS_Mix1" in session.method.components[0].provenance
