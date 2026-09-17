"""
Recalibrating the mass axis from the internal standards.

Synthetic survey ions sit a known number of ppm from their formula's mass,
so what is asked is whether that offset comes back, whether one lock mass is
honest about being one, whether a standard that was not measuring the same
ion is kept out, and — the one that guards every saved project — whether the
switch off gives exactly the numbers the switch never existing would.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.components import Component  # noqa: E402
from milq.mass_drift import mass_drift  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.quantify import extract_xic, integrate_component, process  # noqa: E402
from milq.precursor import CONSENSUS_SPREAD_PPM  # noqa: E402
from milq.recalibrate import (BATCH_SOURCE, LADDER_SOURCE,  # noqa: E402
                                   LockMass, MassCorrection,
                                   MAX_LOCK_ERROR_PPM, MIN_LADDER_RUNGS,
                                   MIN_MASS_SPAN, MIN_SLOPE_LOCK_MASSES,
                                   describe, dropped_lock_masses, fit_batch,
                                   fit_correction, fit_infusion,
                                   ladder_rungs, lock_mass_refusal,
                                   lock_masses_from_drift)
from milq.samples import SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from tests.test_matching import Sample  # noqa: E402
from tests.test_precursor import SpectrumChannel  # noqa: E402

#: three standards whose formulae span most of a survey's range
FORMULAE = (("A", "C18H30O5", "[M-H]-"),
            ("B", "C24H38O4", "[M-H]-"),
            ("C", "C35H70NO8P", "[M-H]-"))


def _exact(formula: str, adduct: str = "[M-H]-") -> float:
    return Component("x", 0.0, formula=formula, adduct=adduct).precursor


def _lock(name: str, formula: str, ppm: float) -> LockMass:
    exact = _exact(formula)
    return LockMass(component=name, theoretical=exact,
                    measured=exact * (1 + ppm * 1e-6), intensity=10_000.0)


# --------------------------------------------------------------------------- #
# the fit
# --------------------------------------------------------------------------- #
def test_an_offset_comes_back_with_its_sign_flipped():
    """Ions read 6 ppm high; the correction is 6 ppm down."""
    locks = [_lock(name, formula, 6.0) for name, formula, _ in FORMULAE]
    correction = fit_correction("s", "S", locks)
    assert correction.usable
    assert correction.offset_ppm == pytest.approx(-6.0, abs=1e-6)
    assert correction.median_before == pytest.approx(6.0, abs=1e-6)
    # not exactly zero: the correction is one multiplication, so what is left
    # is its own square — 3.6e-5 ppm at 6 ppm, and nothing to worry about
    assert correction.median_after == pytest.approx(0.0, abs=1e-3)
    for lock in locks:
        assert float(correction.apply(lock.measured)) == pytest.approx(
            lock.theoretical, rel=1e-10)


def test_one_lock_mass_is_an_offset_and_says_so():
    correction = fit_correction("s", "S", [_lock("A", "C18H30O5", -4.0)])
    assert correction.usable and not correction.linear
    assert correction.offset_ppm == pytest.approx(4.0, abs=1e-6)
    assert "1 lock mass" in correction.verdict
    assert "nothing checks it" in correction.verdict
    # its residual goes to zero by construction, which is the point of saying
    # how many there were
    assert correction.median_after == pytest.approx(0.0, abs=1e-3)


def test_no_lock_mass_leaves_the_masses_alone():
    correction = fit_correction("s", "S", [])
    assert not correction.usable
    assert "left as measured" in correction.verdict
    mz = np.array([100.0, 500.0])
    assert np.array_equal(correction.apply(mz), mz)
    assert np.array_equal(correction.undo(mz), mz)
    assert float(np.max(np.abs(correction.ppm_at(mz)))) == 0.0


def test_two_lock_masses_cannot_support_a_slope():
    locks = [_lock("A", "C18H30O5", 2.0), _lock("C", "C35H70NO8P", 10.0)]
    correction = fit_correction("s", "S", locks)
    assert not correction.linear
    assert "an offset is all that can be fitted and checked" in correction.note
    assert correction.offset_ppm == pytest.approx(-6.0, abs=1e-6)


def test_three_lock_masses_on_a_line_still_refuse_the_slope():
    """
    Hold one of three out and the line is fitted through two points, which is
    exact and predicts nothing. Four is the first count that can be checked,
    so three are refused even when they do lie on a line.
    """
    assert MIN_SLOPE_LOCK_MASSES == 4
    locks = []
    for name, formula, _ in FORMULAE:
        exact = _exact(formula)
        locks.append(_lock(name, formula, 0.05 * (exact - 400.0)))
    correction = fit_correction("s", "S", locks)
    assert not correction.linear
    assert "fewer than 4" in correction.note


def test_a_slope_is_kept_when_enough_lock_masses_prove_it():
    """
    Six lock masses on a real gradient, spread over the range: leave-one-out
    predicts a held-out one better with the line than with the offset.
    """
    masses = np.linspace(300.0, 900.0, 6)
    locks = [LockMass(component=f"L{i}", theoretical=float(m),
                      measured=float(m) * (1 + (0.02 * (m - 600.0)) * 1e-6))
             for i, m in enumerate(masses)]
    correction = fit_correction("s", "S", locks)
    assert correction.linear
    assert correction.slope_ppm_per_da == pytest.approx(-0.02, rel=1e-6)
    assert "a slope helped" in correction.note
    # again second order: a 6 ppm correction leaves 3.6e-5 ppm behind it
    assert max(abs(v) for v in correction.after_ppm) < 1e-3


def test_lock_masses_too_close_together_get_no_slope():
    masses = np.linspace(600.0, 600.0 + MIN_MASS_SPAN / 2, 5)
    locks = [LockMass(component=f"L{i}", theoretical=float(m),
                      measured=float(m) * (1 + 3e-6)) for i, m in enumerate(masses)]
    correction = fit_correction("s", "S", locks)
    assert not correction.linear
    assert "extrapolation" in correction.note


def test_the_median_resists_one_lock_mass_on_an_interference():
    locks = [_lock("A", "C18H30O5", 5.0), _lock("B", "C24H38O4", 5.2),
             _lock("C", "C35H70NO8P", 400.0)]
    correction = fit_correction("s", "S", locks)
    assert correction.offset_ppm == pytest.approx(-5.2, abs=0.1)


# --------------------------------------------------------------------------- #
# apply and undo
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("slope", [0.0, -0.02])
def test_undo_inverts_apply_exactly(slope):
    correction = MassCorrection(
        offset_ppm=-6.0, slope_ppm_per_da=slope, pivot=600.0,
        lock_masses=[_lock("A", "C18H30O5", 6.0)])
    mz = np.linspace(100.0, 1200.0, 41)
    back = correction.undo(correction.apply(mz))
    assert np.allclose(back, mz, rtol=1e-12, atol=0.0)
    forward = correction.apply(correction.undo(mz))
    assert np.allclose(forward, mz, rtol=1e-12, atol=0.0)


# --------------------------------------------------------------------------- #
# from a batch
# --------------------------------------------------------------------------- #
def _entry(name: str, ppm: float, formula: str = "C18H30O5",
           nominal: float = 325.20) -> SampleEntry:
    exact = _exact(formula)
    survey = SpectrumChannel(0, None, 100.0, 2000.0, 12.0, 14.0, n=200,
                             ions=[(exact * (1 + ppm * 1e-6), 1.0)],
                             apex=13.1, height=10_000.0)
    product = SpectrumChannel(1, nominal, 50.0, 350.0, 12.0, 14.0, n=200,
                              ions=[(183.0, 1.0),
                                    (exact * (1 + ppm * 1e-6), 0.4)], apex=13.1)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([survey, product])
    return entry


def _method(formula: str = "C18H30O5") -> ProcessingMethod:
    method = ProcessingMethod()
    method.replace_all([Component(
        "FA 18:3;O3", 325.20, 183.0, rt=13.1, rt_halfwidth=0.5,
        is_internal_standard=True, formula=formula,
        adduct="[M-H]-" if formula else "")])
    return method


class _Batch:
    """Just enough of a session for fit_batch."""

    def __init__(self, entries, method):
        self.entries = entries
        self.method = method
        self.mass_drift = None


def test_fit_batch_corrects_every_injection_it_can():
    entries = [_entry(f"S{i:02d}", 7.0) for i in range(6)]
    batch = _Batch(entries, _method())
    corrections = fit_batch(batch)
    assert set(corrections) == {e.key for e in entries}
    for correction in corrections.values():
        assert correction.usable
        assert correction.offset_ppm == pytest.approx(-7.0, abs=0.5)
        assert len(correction.lock_masses) == 1
    assert "6 of 6 injection(s) corrected" in describe(corrections)
    assert "nothing to check it" in describe(corrections)


def test_a_standard_without_a_formula_is_not_a_lock_mass():
    entries = [_entry(f"S{i:02d}", 7.0) for i in range(6)]
    corrections = fit_batch(_Batch(entries, _method(formula="")))
    assert len(corrections) == 6
    assert not any(c.usable for c in corrections.values())
    assert "no usable lock mass" in next(iter(corrections.values())).verdict
    assert "No lock mass in any of 6" in describe(corrections)


def test_a_trend_that_failed_same_ion_is_left_out():
    """
    Injections disagreeing by hundreds of ppm were not measuring one ion.
    Their median is not a lock mass, whatever formula the component carries.
    """
    entries = [_entry(f"S{i:02d}", 400.0 * (i % 2)) for i in range(6)]
    method = _method()
    drift = mass_drift(entries, method)
    trend = drift.trends[0]
    assert not trend.same_ion
    assert lock_masses_from_drift(drift) == {}
    corrections = fit_batch(_Batch(entries, method), drift)
    assert not any(c.usable for c in corrections.values())


def test_the_verdict_names_the_offset_and_the_count():
    entries = [_entry(f"S{i:02d}", -3.2) for i in range(6)]
    correction = next(iter(fit_batch(_Batch(entries, _method())).values()))
    assert correction.verdict.startswith("corrected by +3.")
    assert "from 1 lock mass" in correction.verdict


# --------------------------------------------------------------------------- #
# the formula gate
# --------------------------------------------------------------------------- #
#: an honest standard and one measuring a neighbour, in one batch. The
#: impostor's offset is the one the real batch's `C17:0_Ceramide` shows.
HONEST_PPM = -4.8
IMPOSTOR_PPM = 238.0


def _two_entry(name: str, honest_ppm: float, impostor_ppm: float) -> SampleEntry:
    """One injection measuring two standards, each in its own transition."""
    honest = _exact("C18H30O5") * (1 + honest_ppm * 1e-6)
    impostor = _exact("C24H38O4") * (1 + impostor_ppm * 1e-6)
    survey = SpectrumChannel(0, None, 100.0, 2000.0, 12.0, 14.0, n=200,
                             ions=[(honest, 1.0), (impostor, 0.8)],
                             apex=13.1, height=10_000.0)
    first = SpectrumChannel(1, 325.20, 50.0, 350.0, 12.0, 14.0, n=200,
                            ions=[(183.0, 1.0), (honest, 0.4)], apex=13.1)
    second = SpectrumChannel(2, 389.27, 50.0, 400.0, 12.0, 14.0, n=200,
                             ions=[(191.0, 1.0), (impostor, 0.4)], apex=13.1)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([survey, first, second])
    return entry


def _two_method() -> ProcessingMethod:
    method = ProcessingMethod()
    method.replace_all([
        Component("FA 18:3;O3", 325.20, 183.0, rt=13.1, rt_halfwidth=0.5,
                  is_internal_standard=True, formula="C18H30O5",
                  adduct="[M-H]-"),
        Component("DCA", 389.27, 191.0, rt=13.1, rt_halfwidth=0.5,
                  is_internal_standard=True, formula="C24H38O4",
                  adduct="[M-H]-"),
    ])
    return method


def test_the_limit_has_margin_on_both_sides_of_the_real_batch():
    """
    Fifty ppm is twice the spread `same_ion` tolerates between injections,
    and the batch it was measured on leaves a factor of about five either
    side: its one honest lock mass is 11.7 ppm from its formula in its worst
    injection, and its impostor 238.
    """
    assert MAX_LOCK_ERROR_PPM == 2 * CONSENSUS_SPREAD_PPM
    assert 11.7 * 4 < MAX_LOCK_ERROR_PPM < 238.0 / 4


def test_an_ion_measured_steadily_at_the_wrong_mass_passes_same_ion():
    """
    The gate exists because the test before it cannot ask this question.
    Six injections agreeing to a ppm about an ion 238 ppm from the formula
    are one ion, measured well — and it is not the compound.
    """
    entries = [_entry(f"S{i:02d}", IMPOSTOR_PPM) for i in range(6)]
    drift = mass_drift(entries, _method())
    trend = drift.trends[0]
    assert trend.same_ion and trend.measurable
    assert trend.error_ppm == pytest.approx(IMPOSTOR_PPM, abs=1.0)


def test_without_the_gate_the_impostor_is_a_lock_mass(monkeypatch):
    """The same batch with the limit lifted: it fits, and fits wrongly."""
    monkeypatch.setattr("milq.recalibrate.MAX_LOCK_ERROR_PPM", 1e9)
    entries = [_entry(f"S{i:02d}", IMPOSTOR_PPM) for i in range(6)]
    method = _method()
    drift = mass_drift(entries, method)
    assert lock_mass_refusal(drift.trends[0]) is None
    corrections = fit_batch(_Batch(entries, method), drift)
    assert all(c.usable for c in corrections.values())
    # every mass in the batch pulled 238 ppm by one wrong ion
    assert next(iter(corrections.values())).offset_ppm == pytest.approx(
        -IMPOSTOR_PPM, abs=1.0)


def test_with_the_gate_it_is_refused_for_the_run_and_says_why():
    entries = [_entry(f"S{i:02d}", IMPOSTOR_PPM) for i in range(6)]
    method = _method()
    drift = mass_drift(entries, method)
    refusal = lock_mass_refusal(drift.trends[0])
    assert refusal == ("measures 238 ppm from its formula: not the ion the "
                       "formula names")
    assert lock_masses_from_drift(drift) == {}
    corrections = fit_batch(_Batch(entries, method), drift)
    assert not any(c.usable for c in corrections.values())
    assert "no usable lock mass" in next(iter(corrections.values())).verdict
    assert f"{MAX_LOCK_ERROR_PPM:g} ppm" in describe(corrections)


def test_the_impostor_does_not_drag_the_honest_lock_mass():
    """
    Two standards, one of them measuring a neighbour: the fit is the honest
    one alone, and identical to the fit of a batch the impostor never
    entered.
    """
    entries = [_two_entry(f"S{i:02d}", HONEST_PPM, IMPOSTOR_PPM)
               for i in range(6)]
    method = _two_method()
    drift = mass_drift(entries, method)
    kept = {lock.component for row in lock_masses_from_drift(drift).values()
            for lock in row}
    assert kept == {"FA 18:3;O3"}
    corrections = fit_batch(_Batch(entries, method), drift)
    for correction in corrections.values():
        assert len(correction.lock_masses) == 1
        assert correction.offset_ppm == pytest.approx(-HONEST_PPM, abs=0.5)

    alone = fit_batch(_Batch([_entry(f"S{i:02d}", HONEST_PPM) for i in range(6)],
                             _method()))
    assert ([round(c.offset_ppm, 9) for c in corrections.values()]
            == [round(c.offset_ppm, 9) for c in alone.values()])


def test_one_injection_past_the_limit_is_dropped_where_it_happened():
    """
    Most injections, not any: a standard that reads its own formula in four
    injections and a neighbour in two is a lock mass in the four. The
    injections that lost it say so rather than reading as injections nobody
    measured anything in.
    """
    errors = [30.0, 32.0, 34.0, 36.0, 52.0, 54.0]
    entries = [_entry(f"S{i:02d}", ppm) for i, ppm in enumerate(errors)]
    method = _method()
    drift = mass_drift(entries, method)
    trend = drift.trends[0]
    assert trend.same_ion                     # they agree with each other
    assert lock_mass_refusal(trend) is None   # and mostly with the formula

    locks = lock_masses_from_drift(drift)
    assert len(locks) == 4
    dropped = dropped_lock_masses(drift)
    assert sorted(round(ppm) for row in dropped.values()
                  for _, ppm in row) == [52, 54]

    corrections = fit_batch(_Batch(entries, method), drift)
    kept = [c for c in corrections.values() if c.usable]
    assert len(kept) == 4
    lost = [c for c in corrections.values() if not c.usable]
    assert len(lost) == 2
    for correction in lost:
        assert "left out of this injection" in correction.verdict
        assert "FA 18:3;O3" in correction.verdict


def test_a_trend_with_no_formula_cannot_be_gated():
    """Nothing to measure against is not a refusal, it is silence."""
    entries = [_entry(f"S{i:02d}", IMPOSTOR_PPM) for i in range(6)]
    drift = mass_drift(entries, _method(formula=""))
    assert lock_mass_refusal(drift.trends[0]) is None
    assert dropped_lock_masses(drift) == {}


# --------------------------------------------------------------------------- #
# the switch
# --------------------------------------------------------------------------- #
def test_the_switch_is_off_by_default_and_survives_a_round_trip(tmp_path):
    session = Session()
    assert session.recalibrate is False
    assert "recalibrate" in session.to_dict()
    path = str(tmp_path / "p.oqproj")
    session.set_recalibrate(True)
    session.save_project(path)

    reopened = Session()
    reopened.load_project(path)
    assert reopened.recalibrate is True

    # and a project written before this existed reopens with it off
    import json
    data = json.load(open(path))
    del data["recalibrate"]
    json.dump(data, open(path, "w"))
    older = Session()
    older.load_project(path)
    assert older.recalibrate is False


def test_a_correction_is_only_handed_out_while_the_switch_is_on():
    session = Session()
    correction = fit_correction("k", "S", [_lock("A", "C18H30O5", 6.0)])
    session.mass_corrections = {"k": correction}
    assert session.correction_for("k") is None
    assert session.corrections_in_force() == {}
    session.set_recalibrate(True)
    assert session.correction_for("k") is correction
    assert session.corrections_in_force() == {"k": correction}
    # an injection with no lock mass is not corrected even so
    session.mass_corrections["empty"] = fit_correction("empty", "E", [])
    assert session.correction_for("empty") is None
    assert "empty" not in session.corrections_in_force()


def test_the_switch_off_gives_identical_numbers():
    """
    The guard on every saved project: a run with no corrections and a run
    with the argument never passed must agree to the last decimal.
    """
    entries = [_entry(f"S{i:02d}", 7.0) for i in range(4)]
    method = _method()
    before = process(entries, method)
    after = process(entries, method, corrections={})
    assert len(before) == len(after)
    for a, b in zip(before, after):
        assert a.to_dict() == b.to_dict()
        assert a.recalibrated_ppm is None


def test_the_switch_on_moves_the_window_and_marks_the_row():
    entries = [_entry("S00", 7.0)]
    method = _method()
    component = method.components[0]
    corrections = fit_batch(_Batch(entries, method))
    correction = corrections[entries[0].key]

    plain = integrate_component(entries[0], component, method)
    fixed = integrate_component(entries[0], component, method, None, correction)
    assert plain.recalibrated_ppm is None
    assert fixed.recalibrated_ppm == pytest.approx(correction.offset_ppm, abs=1e-9)

    # the window really moved: the reader was asked for a shifted range
    # the ion was measured 7 ppm high, so the raw file holds it 7 ppm above
    # where the method says it is: the window must move up, not down
    lo, hi = component.mass_window()
    assert float(correction.undo(lo)) > lo
    assert float(correction.undo(hi)) > hi
    assert (float(correction.undo(lo)) - lo) / lo * 1e6 == pytest.approx(
        7.0, abs=0.5)


def test_extraction_without_a_correction_is_untouched():
    entry = _entry("S00", 7.0)
    method = _method()
    component = method.components[0]
    x0, y0, _ = extract_xic(entry, component, method)
    x1, y1, _ = extract_xic(entry, component, method, None, None)
    x2, y2, _ = extract_xic(entry, component, method, None,
                            fit_correction("k", "S", []))
    assert np.array_equal(x0, x1) and np.array_equal(y0, y1)
    assert np.array_equal(x0, x2) and np.array_equal(y0, y2)


def test_the_precursor_measurement_reports_raw_and_corrected():
    from milq.precursor import measure

    entry = _entry("S00", 7.0)
    method = _method()
    component = method.components[0]
    correction = fit_correction("k", "S", [_lock("A", "C18H30O5", 7.0)])

    raw = measure(entry, component, method)
    assert raw.found and raw.correction_ppm is None
    assert raw.corrected is None and raw.reported == raw.measured

    fixed = measure(entry, component, method, correction=correction)
    # the measurement itself never moves — the correction was fitted from it
    assert fixed.measured == pytest.approx(raw.measured, rel=1e-12)
    assert fixed.correction_ppm == pytest.approx(-7.0, abs=1e-6)
    assert fixed.corrected == pytest.approx(_exact("C18H30O5"), rel=2e-6)
    assert fixed.reported == fixed.corrected


# --------------------------------------------------------------------------- #
# the panel and the report
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qt_app():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_panel_fits_and_shows_the_corrections(qt_app):
    from milq.ui.mass_drift_panel import MassDriftPanel

    session = Session()
    session.entries = [_entry(f"S{i:02d}", 7.0) for i in range(6)]
    session.method = _method()

    panel = MassDriftPanel(session)
    # nothing measured: the switch has nothing behind it
    assert not panel.recalibrate.isChecked()
    assert not panel.recalibrate.isEnabled()
    assert panel.corrections.rowCount() == 0

    panel.measure()
    assert panel.corrections.rowCount() == 6
    assert panel.recalibrate.isEnabled()
    assert "corrected by" in panel.corrections.item(0, 8).text()
    assert panel.corrections.item(0, 2).text() == "1"
    assert panel.corrections.item(0, 1).text() == BATCH_SOURCE
    assert "corrected" in panel.correction_status.text()

    panel.recalibrate.setChecked(True)
    assert session.recalibrate is True
    assert len(session.corrections_in_force()) == 6
    panel.recalibrate.setChecked(False)
    assert session.recalibrate is False
    panel.deleteLater()


def test_the_report_prints_the_corrections_and_says_whether_they_applied():
    from milq.report import build_html

    session = Session()
    session.entries = [_entry(f"S{i:02d}", 7.0) for i in range(6)]
    session.method = _method()
    session.mass_drift = mass_drift(session.entries, session.method)
    session.mass_corrections = fit_batch(session, session.mass_drift)

    html = build_html(session, sections=["mass"])
    assert "Mass recalibration" in html
    assert "Lock masses" in html
    assert "not</b> applied" in html

    session.recalibrate = True
    applied = build_html(session, sections=["mass"])
    assert "produced with it applied" in applied

    # and nothing at all when nothing was fitted
    session.mass_corrections = {}
    assert "Mass recalibration" not in build_html(session, sections=["mass"])


def test_the_explorer_moves_the_spectrum_axis_and_says_so(qt_app):
    """
    The one thing worse than a mass axis that is wrong is one that has been
    moved and does not admit it, so the title carries the number.
    """
    from milq.ui.explorer import ChannelRef, ExplorerWorkspace

    session = Session()
    entry = _entry("S00", 7.0)
    session.entries = [entry]
    session.method = _method()
    session.mass_corrections = fit_batch(_Batch(session.entries, session.method))

    explorer = ExplorerWorkspace(session)
    explorer.active_ref = ChannelRef(entry, entry.sample.channels[0])
    mz = np.array([300.0, 400.0, 500.0])

    axis, said = explorer._recalibrate_mz(mz)
    assert said == "" and np.array_equal(axis, mz)      # the switch is off

    session.set_recalibrate(True)
    axis, said = explorer._recalibrate_mz(mz)
    assert "recalibrated -7.0 ppm" in said
    assert np.allclose((axis - mz) / mz * 1e6, -7.0, atol=0.5)
    explorer.deleteLater()
    qt_app.processEvents()


def test_the_panel_names_the_refused_standard_in_its_verdict(qt_app):
    """A wrong ion measured steadily looks like a well-behaved standard in
    every column but this one."""
    from milq.ui.mass_drift_panel import MassDriftPanel

    session = Session()
    session.entries = [_entry(f"S{i:02d}", IMPOSTOR_PPM) for i in range(6)]
    session.method = _method()

    panel = MassDriftPanel(session)
    panel.measure()
    row = next(r for r in range(panel.table.rowCount())
               if panel.table.item(r, 0).text() == "FA 18:3;O3")
    verdict = panel.table.item(row, 8)
    assert "not the ion the formula names" in verdict.text()
    assert verdict.toolTip() == verdict.text()
    # and nothing was corrected from it
    assert not panel.recalibrate.isEnabled()
    panel.deleteLater()


def test_the_report_names_the_refused_standard_too():
    from milq.report import build_html

    session = Session()
    session.entries = [_entry(f"S{i:02d}", IMPOSTOR_PPM) for i in range(6)]
    session.method = _method()
    session.mass_drift = mass_drift(session.entries, session.method)
    session.mass_corrections = fit_batch(session, session.mass_drift)

    html = build_html(session, sections=["mass"])
    assert "not the ion the formula names" in html
    assert f"{MAX_LOCK_ERROR_PPM:g} ppm from its" in html


# --------------------------------------------------------------------------- #
# an infusion, fitted from its own precursor ladder
# --------------------------------------------------------------------------- #
#: cholic acid-d4 as the nine real infusions carry it: the ammonium adduct
#: the channel's 430.34 names, with the four labels spelt into the formula
LADDER_FORMULA = "C24H36D4O5"
LADDER_ADDUCT = "[M+NH4]+"


def _rungs_of(count: int):
    from milq.explain import precursor_ions

    return sorted(precursor_ions(LADDER_FORMULA, LADDER_ADDUCT, 0),
                  key=lambda ion: -ion.mz)[:count]


def _ladder(offset_ppm: float, heights=None, rungs: int = 4,
            skew: dict[int, float] | None = None):
    """
    A synthetic infusion average: the top `rungs` of the real ladder, as
    centroids, every one of them `offset_ppm` from where the formula puts it.

    `skew` moves one rung further, by index into the ladder, which is how an
    ion that is not the compound is written into the spectrum.
    """
    ions = _rungs_of(rungs)
    heights = heights or [10_000.0 - 1_000.0 * i for i in range(len(ions))]
    mz, intensity = [], []
    for index, ion in enumerate(ions):
        ppm = offset_ppm + (skew or {}).get(index, 0.0)
        mz.append(ion.mz * (1 + ppm * 1e-6))
        intensity.append(float(heights[index]))
    order = np.argsort(mz)
    return np.array(mz)[order], np.array(intensity)[order]


def test_a_ladder_gives_back_the_offset_it_was_built_with():
    mz, intensity = _ladder(+6.0, rungs=4)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT,
                              sample_key="k", sample_name="CA-d4")
    assert correction.usable
    assert len(correction.lock_masses) == 4
    assert correction.offset_ppm == pytest.approx(-6.0, abs=1e-6)
    assert correction.source == LADDER_SOURCE
    assert correction.unit == "rung"
    assert "4 rungs" in correction.verdict
    assert correction.short == "recalibrated -6.0 ppm from 4 rungs"
    # every rung lands on its formula's mass afterwards
    for lock in correction.lock_masses:
        assert float(correction.apply(lock.measured)) == pytest.approx(
            lock.theoretical, rel=1e-10)
    # the reason there is no slope is the span, and it names it
    assert "span" in correction.note and "extrapolation" in correction.note
    assert correction.span_da < MIN_MASS_SPAN


def test_one_rung_is_one_too_few():
    """
    A batch's one lock mass still has twenty-five other injections beside it.
    An infusion's has nothing at all, so two is the floor.
    """
    assert MIN_LADDER_RUNGS == 2
    mz, intensity = _ladder(+6.0, rungs=1)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT)
    assert correction is not None
    assert not correction.usable
    assert "1 rung" in correction.note
    assert "fewer than the 2" in correction.note
    # and it leaves every mass exactly where it was
    axis = np.array([100.0, 430.3465, 900.0])
    assert np.array_equal(correction.apply(axis), axis)
    assert "fewer than" in correction.verdict


def test_a_rung_that_disagrees_with_the_rest_is_dropped_and_named():
    """One window holding a different ion cannot decide the axis."""
    mz, intensity = _ladder(+6.0, rungs=4, skew={3: -40.0})
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT,
                              tolerance_ppm=60.0)
    assert correction.usable
    assert len(correction.lock_masses) == 3
    assert correction.offset_ppm == pytest.approx(-6.0, abs=1e-6)
    assert "dropped, disagreeing" in correction.note
    assert f"{CONSENSUS_SPREAD_PPM:g} ppm" in correction.note
    # and the one dropped is named, by the ion it claimed to be
    offered = {ion.description for ion in _rungs_of(4)}
    kept = {lock.component for lock in correction.lock_masses}
    assert len(offered - kept) == 1
    assert (offered - kept).pop() in correction.note


def test_a_ladder_far_from_its_formula_is_not_this_compound():
    """
    Past `MAX_LOCK_ERROR_PPM` it is a different ion series, not a mis-set
    axis. The default matching window is narrower than the ceiling, so this
    can only be reached by widening it — which is the case the ceiling is
    there for.
    """
    mz, intensity = _ladder(+120.0, rungs=4)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT,
                              tolerance_ppm=200.0)
    assert not correction.usable
    assert f"{MAX_LOCK_ERROR_PPM:g} ppm" in correction.note
    assert "different ion series" in correction.note


def test_a_ladder_outside_the_window_is_simply_not_found():
    mz, intensity = _ladder(+120.0, rungs=4)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT)
    assert not correction.usable
    assert "no rung" in correction.note


def test_a_rung_under_the_intensity_floor_is_not_a_measurement():
    from milq.precursor import MIN_INTENSITY

    mz, intensity = _ladder(+6.0, rungs=4,
                            heights=[10_000.0, 9_000.0, MIN_INTENSITY - 1, 1.0])
    rungs = ladder_rungs(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT)
    assert len(rungs) == 2


def test_the_weighted_median_follows_the_peaks_worth_believing():
    """
    A hundred-count rung and a twelve-thousand-count one do not locate their
    centroids equally well, and the offset is weighted accordingly.
    """
    heights = [12_000.0, 200.0, 150.0, 120.0]
    mz, intensity = _ladder(+6.0, rungs=4, heights=heights)
    strong = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT)
    assert strong.offset_ppm == pytest.approx(-6.0, abs=1e-6)
    # the same ladder with the strongest rung 8 ppm from the other three: the
    # weight puts the answer on it rather than on the three weak ones, and it
    # is inside the spread limit so nothing is dropped
    mz, intensity = _ladder(+6.0, rungs=4, heights=heights, skew={0: 8.0})
    pulled = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT,
                          tolerance_ppm=40.0)
    assert len(pulled.lock_masses) == 4
    assert pulled.offset_ppm == pytest.approx(-14.0, abs=1e-6)


def test_nothing_to_fit_from_comes_back_as_none():
    """A formula this cannot read has no ladder, and that is not a refusal."""
    mz, intensity = _ladder(+6.0, rungs=4)
    assert fit_infusion(mz, intensity, "not a formula", LADDER_ADDUCT) is None
    assert fit_infusion(mz, intensity, LADDER_FORMULA, "[M+Xx]+") is None
    assert fit_infusion(np.zeros(0), np.zeros(0), LADDER_FORMULA,
                        LADDER_ADDUCT) is None


def test_the_basis_sentence_prints_the_raw_and_the_corrected_error():
    """
    Either number alone misleads: the corrected one is a residual the fit
    was made to produce, and the raw one does not say the axis moved.
    """
    mz, intensity = _ladder(+6.0, rungs=4)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT)
    said = correction.basis_sentence()
    assert "recalibrated -6.0 ppm from 4 rungs" in said
    assert "+6.0 ppm raw" in said
    # the residual is the correction's own square: 3.6e-5 ppm at 6 ppm
    assert "0.0 ppm corrected" in said
    # the rung quoted is the strongest one, which is what the offset rests on
    strongest = max(correction.lock_masses, key=lambda lock: lock.intensity)
    assert strongest.component in said


def test_a_refusal_says_so_where_a_basis_sentence_is_asked_for():
    mz, intensity = _ladder(+6.0, rungs=1)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT)
    assert "fewer than the 2" in correction.basis_sentence()


def test_the_ladder_correction_sits_in_the_same_place_as_a_batch_one():
    """
    Everything downstream reads `session.mass_corrections`, so an infusion's
    correction has to live there and obey the same switch.
    """
    mz, intensity = _ladder(+6.0, rungs=4)
    correction = fit_infusion(mz, intensity, LADDER_FORMULA, LADDER_ADDUCT,
                              sample_key="k", sample_name="CA-d4")
    session = Session()
    session.mass_corrections = {"k": correction}
    assert session.correction_for("k") is None       # the switch is off
    session.set_recalibrate(True)
    assert session.correction_for("k") is correction
    assert correction.to_dict()["source"] == LADDER_SOURCE


def test_the_panel_shows_an_infusion_row_with_its_own_source(qt_app):
    """
    The mass-drift panel's table is where every correction is reviewed, and
    an infusion's has to appear there with no drift measured at all.
    """
    from milq.ui.mass_drift_panel import MassDriftPanel

    session = Session()
    entry = _entry("CA-d4", 0.0)
    session.entries = [entry]
    mz, intensity = _ladder(+6.0, rungs=4)
    session.mass_corrections = {entry.key: fit_infusion(
        mz, intensity, LADDER_FORMULA, LADDER_ADDUCT,
        sample_key=entry.key, sample_name="CA-d4")}

    panel = MassDriftPanel(session)
    panel.reload()
    assert session.mass_drift is None
    assert panel.corrections.rowCount() == 1
    assert panel.corrections.item(0, 1).text() == LADDER_SOURCE
    assert panel.corrections.item(0, 2).text() == "4"
    assert "4 rungs" in panel.corrections.item(0, 8).text()
    panel.deleteLater()
