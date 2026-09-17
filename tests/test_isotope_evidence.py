"""
The isotope pattern as evidence for a matched fragment.

Built rather than read: each spectrum here is a set of predicted ions with
their own theoretical satellites put beside them at a stated proportion, so
that "agrees" means the satellite was in proportion and "disagrees" means it
was not, and neither depends on a real file being to hand.
"""

import numpy as np
import pytest

from milq import explain
from milq.chemistry import PATTERN_AGREES, parse_formula

FORMULA = "C24H40O5"        # cholic acid
ADDUCT = "[M+H]+"


def sticks(ion, height: float, satellites: float = 1.0):
    """One ion as M, M+1, M+2, its satellites scaled by `satellites`."""
    counts = explain.ion_counts(ion, ADDUCT)
    assert counts, ion.description
    pattern = explain._pattern_of(counts, ion.charge)
    return [(mass, height * share * (1.0 if index == 0 else satellites))
            for index, (mass, share) in enumerate(pattern)]


def spectrum(placed):
    """`placed` as one spectrum, with a floor of specks under it."""
    points = list(placed)
    # something for the noise to be measured from: without it the median of
    # the positive heights is one of the ions and every satellite the
    # prediction offers is called unmeasurable
    points += [(50.0 + index * 0.7, 2.0) for index in range(300)]
    points.sort()
    mz = np.array([m for m, _h in points], dtype=float)
    intensity = np.array([h for _m, h in points], dtype=float)
    return mz, intensity


def ions_of(formula: str = FORMULA, deuterium: int = 0):
    return explain.formula_ions(formula, ADDUCT, deuterium=deuterium)


def find(ions, description: str):
    for ion in ions:
        if ion.description == description:
            return ion
    raise AssertionError(f"{description} not offered: "
                         f"{[i.description for i in ions][:12]}")


def explained(mz, intensity, formula: str = FORMULA, deuterium: int = 0):
    peaks = explain.significant_peaks(mz, intensity)
    return explain.explain_formula(formula, ADDUCT, peaks, name="test",
                                   deuterium=deuterium)


# --------------------------------------------------------------------------- #
def test_ion_counts_is_the_ion_and_not_the_molecule():
    """The proton is in the composition; the losses are taken off it."""
    ions = ions_of()
    intact = find(ions, "[M+H]+")
    assert explain.ion_counts(intact, ADDUCT) == {"C": 24, "H": 41, "O": 5}
    dehydrated = find(ions, "[M+H-H2O]+")
    assert explain.ion_counts(dehydrated, ADDUCT) == {"C": 24, "H": 39, "O": 4}


def test_ion_counts_reproduces_every_offered_mass():
    """A composition that does not weigh what the ion weighs is refused."""
    from milq.chemistry import ELECTRON_MASS, monoisotopic_mass

    for ion in ions_of(deuterium=4):
        counts = explain.ion_counts(ion, ADDUCT)
        if counts is None:
            continue
        mass = monoisotopic_mass(counts) - ion.charge * ELECTRON_MASS
        assert mass / abs(ion.charge) == pytest.approx(ion.mz, abs=1e-3)


# --------------------------------------------------------------------------- #
def test_satellites_in_proportion_agree():
    ions = ions_of()
    placed = (sticks(find(ions, "[M+H]+"), 10_000)
              + sticks(find(ions, "[M+H-H2O]+"), 5_000)
              + sticks(find(ions, "[M+H-2H2O]+"), 2_000))
    mz, intensity = spectrum(placed)
    result = explained(mz, intensity)
    found = explain.isotope_evidence(result, mz, intensity)

    assert result.matched >= 3
    verdicts = {e.verdict for e in found.values()}
    assert verdicts == {explain.ISOTOPES_AGREE}
    assert result.isolation is not None and not result.isolation.monoisotopic
    assert result.isolation.transmission == pytest.approx(1.0, abs=0.05)
    for evidence in found.values():
        assert evidence.agreement > PATTERN_AGREES
        assert evidence.text.startswith("agrees: M+1")


def test_a_wrong_satellite_disagrees_and_the_match_is_kept():
    """A satellite that is not the ion's own is printed, never subtracted."""
    ions = ions_of()
    dehydrated = find(ions, "[M+H-H2O]+")
    placed = (sticks(find(ions, "[M+H]+"), 10_000)
              + sticks(dehydrated, 5_000, satellites=0.05)
              + sticks(find(ions, "[M+H-2H2O]+"), 2_000))
    mz, intensity = spectrum(placed)
    result = explained(mz, intensity)
    before = (result.matched, result.share)
    found = explain.isotope_evidence(result, mz, intensity)

    odd = [e for e in found.values() if e.ion.mz == pytest.approx(dehydrated.mz)]
    assert len(odd) == 1
    assert odd[0].verdict == explain.ISOTOPES_DISAGREE
    assert odd[0].text.startswith("disagrees: M+1")
    # the ranking does not move: a disagreement is evidence beside the match,
    # not a reason to drop it
    assert (result.matched, result.share) == before
    assert dehydrated.mz in [m.ion.mz for m in result.matches]
    assert sum(1 for e in found.values() if e.agrees) >= 2


def test_a_monoisotopic_isolation_expects_no_satellite_anywhere():
    """Q1 kept the monoisotopic precursor; no fragment can carry a 13C."""
    ions = ions_of()
    placed = (sticks(find(ions, "[M+H]+"), 10_000, satellites=0.0)
              + sticks(find(ions, "[M+H-H2O]+"), 5_000, satellites=0.0)
              + sticks(find(ions, "[M+H-2H2O]+"), 2_000, satellites=0.0))
    mz, intensity = spectrum(placed)
    result = explained(mz, intensity)
    found = explain.isotope_evidence(result, mz, intensity)

    assert result.isolation.monoisotopic
    assert result.isolation.transmission == pytest.approx(0.0, abs=1e-6)
    assert {e.verdict for e in found.values()} == {explain.ISOTOPES_NONE_EXPECTED}
    assert not any(e.verdict == explain.ISOTOPES_DISAGREE
                   for e in found.values())
    assert explain.isotope_column(found, result.isolation) == "none expected"


def test_the_isolation_is_read_off_the_strongest_fragment_when_the_precursor_is_gone():
    """A collision energy that consumed the precursor still answers."""
    ions = ions_of()
    placed = (sticks(find(ions, "[M+H-H2O]+"), 5_000, satellites=0.0)
              + sticks(find(ions, "[M+H-2H2O]+"), 2_000, satellites=0.0))
    mz, intensity = spectrum(placed)
    result = explained(mz, intensity)
    explain.isotope_evidence(result, mz, intensity)

    assert result.isolation.basis == "the strongest matched fragment"
    assert result.isolation.monoisotopic


def test_a_satellite_under_the_noise_is_unmeasurable_not_a_disagreement():
    ions = ions_of()
    intact = find(ions, "[M+H]+")
    placed = sticks(intact, 10_000) + [(find(ions, "[M+H-H2O]+").mz, 150.0)]
    mz, intensity = spectrum(placed)
    # a noise floor tall enough to swallow the small ion's own M+1
    intensity = np.where(intensity <= 2.0, 60.0, intensity)
    result = explained(mz, intensity)
    found = explain.isotope_evidence(result, mz, intensity)

    weak = [e for e in found.values() if e.height == pytest.approx(150.0)]
    assert len(weak) == 1
    assert weak[0].verdict == explain.ISOTOPES_UNMEASURABLE
    assert "under the" in weak[0].note


def test_a_label_rung_inside_the_m_plus_one_window_is_unmeasurable():
    """
    A deuterium is 1.00628 Da from the hydrogen it replaced and a neutron
    1.00336: the same piece carrying one more label sits where this one's M+1
    belongs, 2.9 mDa away, and reading it as a satellite reads the wrong ion.
    """
    ions = ions_of("C24H36D4O5", deuterium=0)
    top = find(ions, "[M+H-H2O]+ +4D")
    below = find(ions, "[M+H-H2O]+ +3D")
    assert top.mz - below.mz == pytest.approx(1.00628, abs=1e-4)
    placed = (sticks(find(ions, "[M+H]+ +4D"), 10_000)
              + sticks(top, 6_000) + sticks(below, 1_000))
    mz, intensity = spectrum(placed)
    result = explained(mz, intensity, "C24H36D4O5")
    found = explain.isotope_evidence(result, mz, intensity)

    caught = [e for e in found.values()
              if e.ion.mz == pytest.approx(below.mz)]
    assert len(caught) == 1
    assert caught[0].verdict == explain.ISOTOPES_UNMEASURABLE
    assert "another predicted ion" in caught[0].note


# --------------------------------------------------------------------------- #
def test_the_summary_counts_what_was_found():
    ions = ions_of()
    placed = (sticks(find(ions, "[M+H]+"), 10_000)
              + sticks(find(ions, "[M+H-H2O]+"), 5_000, satellites=0.05)
              + sticks(find(ions, "[M+H-2H2O]+"), 2_000))
    mz, intensity = spectrum(placed)
    result = explained(mz, intensity)
    found = explain.isotope_evidence(result, mz, intensity)

    said = result.isotope_summary
    assert said == explain.isotope_sentence(found, result.isolation)
    total = len(found)
    agree = sum(1 for e in found.values() if e.agrees)
    assert f"{agree} of {total} matched ion(s) have a satellite that agrees" in said
    assert "1 disagree" in said
    assert "printed, not removed" in said
    assert explain.isotope_column(found, result.isolation) == \
        f"{agree} of {total} agree, 1 disagree"


def test_nothing_asked_says_nothing():
    """An explanation the spectrum was never put to has no sentence."""
    ions = ions_of()
    mz, intensity = spectrum(sticks(find(ions, "[M+H]+"), 10_000))
    result = explained(mz, intensity)
    assert result.isotopes == {}
    assert result.isotope_summary == ""
    assert explain.isotope_column({}) == ""


def test_the_composition_of_an_ion_that_has_none_is_not_invented():
    from milq.structure import Fragment, PredictedIon

    piece = Fragment(atoms=frozenset(), formula="C6H6", mass=78.0, cuts=())
    nonsense = PredictedIon(fragment=piece, mz=1234.5678, charge=1, hydrogens=0)
    assert explain.ion_counts(nonsense) is None


def test_parse_formula_agrees_with_the_composition_read_back():
    ions = ions_of()
    counts = explain.ion_counts(find(ions, "[M+H-CO2]+"), ADDUCT)
    assert counts == {k: v for k, v in parse_formula("C23H41O3").items()}


# --------------------------------------------------------------------------- #
# the column
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    """Held for the module: a `QApplication` nothing holds is collected."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets

    from milq.ui import style

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.apply(app)
    yield app


@pytest.fixture
def panel(qapp, monkeypatch):
    from pathlib import Path

    from milq import lipidmaps
    from milq.lipidmaps import LipidDatabase, LipidRecord
    from milq.structure import parse_molblock
    from milq.ui.lipid_panel import LipidPanel

    fixture = Path(__file__).parent / "fixtures" / "LMST04010001.mol"
    molecule = parse_molblock(fixture.read_text(), FORMULA)
    database = LipidDatabase([
        LipidRecord(lm_id="LMST04010001", name="Cholic acid", abbrev="",
                    formula=FORMULA, exact_mass=408.287574,
                    structure=molecule.to_compact())])
    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: database)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    widget = LipidPanel()
    widget.refresh_availability()
    yield widget
    widget.close()


def test_the_ranked_table_carries_the_column(qapp, panel):
    """The panel's own spectrum, not its peak list: a satellite is under 1%."""
    ions = ions_of()
    mz, intensity = spectrum(
        sticks(find(ions, "[M+H]+"), 10_000, satellites=0.0)
        + sticks(find(ions, "[M+H-H2O]+"), 5_000, satellites=0.0))
    panel.set_spectrum(mz, intensity, 409.2948)
    panel.explain_spectrum()

    top = panel.explain_tree.topLevelItem(0)
    assert top is not None
    assert panel.explain_tree.headerItem().text(6) == "Isotopes"
    assert top.text(6) == "none expected"
    assert "can carry a satellite" in top.toolTip(6)

