"""Scoring a candidate structure against a measured product spectrum."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from milq.explain import (
    explain,
    match_peaks,
    rank_candidates,
    significant_peaks,
)
from milq.lipidmaps import LipidDatabase, LipidRecord
from milq.structure import parse_molblock, predict

FIXTURES = Path(__file__).parent / "fixtures"


def record(lm_id, name, formula, fixture, mass):
    molecule = parse_molblock((FIXTURES / f"{fixture}.mol").read_text(), formula)
    return LipidRecord(lm_id=lm_id, name=name, abbrev="", formula=formula,
                       exact_mass=mass, structure=molecule.to_compact())


@pytest.fixture
def cholic():
    return record("LMST04010001", "Cholic acid", "C24H40O5", "LMST04010001",
                  408.287574)


@pytest.fixture
def database(cholic):
    return LipidDatabase([
        cholic,
        record("LMSP03010002", "SM(d18:1/12:0)", "C35H71N2O6P",
               "LMSP03010002", 646.504974),
    ])


# -- picking the peaks worth explaining -------------------------------------- #
def test_only_peaks_above_the_noise_share_are_considered():
    mz = np.array([100.0, 200.0, 300.0])
    intensity = np.array([1000.0, 5.0, 400.0])
    kept = significant_peaks(mz, intensity, noise_share=0.01)
    assert [round(m) for m, _ in kept] == [100, 300]


def test_the_strongest_come_first_and_the_list_is_capped():
    mz = np.arange(100.0, 200.0)
    intensity = np.arange(100.0, 200.0)
    kept = significant_peaks(mz, intensity, limit=5)
    assert len(kept) == 5
    assert kept[0][1] > kept[-1][1]


def test_an_empty_spectrum_explains_nothing():
    assert significant_peaks(np.array([]), np.array([])) == []
    assert significant_peaks(np.array([1.0]), np.array([0.0])) == []


# -- pairing ------------------------------------------------------------------ #
def test_a_peak_takes_the_nearest_prediction(cholic):
    ions = predict(cholic.molecule())
    peaks = [(391.2843, 100.0)]
    matches = match_peaks(peaks, ions, tolerance_ppm=20.0)
    assert len(matches) == 1
    assert abs(matches[0].error_ppm) < 5


def test_one_prediction_cannot_claim_two_peaks(cholic):
    """Otherwise a dense prediction scores twice for the same ion."""
    ions = predict(cholic.molecule())
    peaks = [(391.2843, 100.0), (391.2845, 90.0)]
    matches = match_peaks(peaks, ions, tolerance_ppm=20.0)
    assert len({id(m.ion) for m in matches}) == len(matches)


def test_a_peak_nothing_predicts_is_left_unmatched(cholic):
    ions = predict(cholic.molecule())
    matches = match_peaks([(123.4567, 100.0)], ions, tolerance_ppm=1.0)
    assert matches == []


def test_nothing_to_match_against():
    assert match_peaks([], []) == []
    assert match_peaks([(100.0, 1.0)], []) == []


# -- scoring ------------------------------------------------------------------ #
def test_the_share_is_intensity_accounted_for_not_peaks_counted(cholic):
    # a candidate that explains the base peak beats one explaining forty specks
    peaks = [(391.2843, 1000.0), (123.4567, 10.0)]
    result = explain(cholic, peaks)
    assert result.matched == 1
    assert result.share > 0.98


def test_the_peaks_it_cannot_account_for_are_reported(cholic):
    peaks = [(391.2843, 1000.0), (123.4567, 10.0)]
    result = explain(cholic, peaks)
    left = result.unexplained(peaks)
    assert [round(m, 4) for m, _ in left] == [123.4567]


def test_a_record_with_no_structure_cannot_be_scored():
    bare = LipidRecord(lm_id="LMX", name="x", abbrev="", formula="C2H6O",
                       exact_mass=46.0)
    assert explain(bare, [(46.0, 1.0)]) is None


# -- ranking ------------------------------------------------------------------ #
def test_candidates_are_ordered_by_what_they_account_for(database, cholic):
    peaks = [(391.2843, 1000.0), (373.2737, 500.0), (355.2632, 200.0)]
    ranked = rank_candidates(database, 409.2948, peaks, adduct="[M+H]+",
                             tolerance=0.7, unit="Da")
    assert ranked
    assert ranked[0].record.lm_id == "LMST04010001"
    assert ranked == sorted(ranked, key=lambda e: (-e.share, -e.matched))


def test_a_precursor_nothing_sits_at_returns_nothing(database):
    assert rank_candidates(database, 999.9999, [(100.0, 1.0)],
                           tolerance=0.7, unit="Da") == []


def test_one_structure_per_species_is_scored(database):
    """A mass search answers with a family; scoring each is the same answer
    twelve times."""
    peaks = [(391.2843, 1000.0)]
    ranked = rank_candidates(database, 409.2948, peaks, tolerance=0.7,
                             unit="Da")
    species = [e.record.species for e in ranked]
    assert len(species) == len(set(species))


# -- letting the spectrum choose between routes ------------------------------- #
def test_a_route_implies_its_own_intermediates(cholic):
    from milq.explain import companion_masses
    from milq.structure import predict

    ions = predict(cholic.molecule(), max_cuts=1, max_losses=2)
    two_waters = next(i for i in ions if i.losses == ("H2O", "H2O"))
    companions = companion_masses(cholic.molecule(), two_waters)
    # losing two waters means the one-water ion existed on the way
    assert len(companions) == 2
    assert companions[0] == pytest.approx(two_waters.mz + 18.0106, abs=1e-3)
    assert companions[1] == pytest.approx(two_waters.mz + 36.0211, abs=1e-3)


def test_a_route_with_no_losses_implies_nothing(cholic):
    from milq.explain import companion_masses
    from milq.structure import predict

    ions = predict(cholic.molecule(), max_cuts=1, max_losses=0)
    assert companion_masses(cholic.molecule(), ions[0]) == []


def test_the_route_whose_ladder_is_present_wins(cholic):
    """Two routes reach one mass; only the companions separate them."""
    from milq.explain import routes_for
    from milq.structure import predict

    molecule = cholic.molecule()
    ions = predict(molecule, max_cuts=1, max_losses=2)
    target = next(i for i in ions if i.losses == ("H2O", "H2O"))
    from milq.explain import companion_masses

    with_ladder = [(target.mz, 100.0)] + [
        (m, 50.0) for m in companion_masses(molecule, target)]
    routes = routes_for(molecule, target, with_ladder)
    assert routes[0].support == pytest.approx(1.0)

    alone = routes_for(molecule, target, [(target.mz, 100.0)])
    assert alone[0].support == 0.0


def test_the_match_carries_the_route_the_spectrum_supports(cholic):
    peaks = [(391.2843, 1000.0), (373.2737, 500.0), (409.2948, 200.0)]
    result = explain(cholic, peaks)
    assert result.matches
    assert all(m.route is not None for m in result.matches)
    assert all(m.best_route for m in result.matches)


def test_a_spectrum_that_cannot_tell_them_apart_says_so(cholic):
    """No ladder present is an honest answer, not a reason to pick one."""
    from milq.explain import routes_for
    from milq.structure import predict

    molecule = cholic.molecule()
    target = next(i for i in predict(molecule, max_cuts=1, max_losses=2)
                  if i.losses == ("H2O", "H2O"))
    routes = routes_for(molecule, target, [(target.mz, 100.0)])
    assert all(r.support == 0.0 for r in routes)


# --------------------------------------------------------------------------- #
# a structure or formula the database does not hold
# --------------------------------------------------------------------------- #
def test_a_formula_alone_gives_the_precursor_and_its_losses():
    from milq.explain import explain_formula, formula_ions

    ions = formula_ions("C24H40O5", "[M-H]-")
    descriptions = {ion.description for ion in ions}
    # an ion of the precursor is written as the form it is, losses inside
    # the bracket, and carries the residual formula beside it
    assert "[M-H]-" in descriptions and "[M-H-H2O]-" in descriptions
    assert "[M-H-2H2O-CO2]-" in descriptions              # O5 - 2 - 2
    assert not any("NH3" in d for d in descriptions)           # no nitrogen
    assert len(ions) == len(descriptions)                       # no duplicates
    water = next(ion for ion in ions if ion.losses == ("H2O",))
    assert water.formula == "C24H38O4"
    intact = next(ion for ion in ions if not ion.losses)
    assert intact.mz == pytest.approx(407.2803, abs=0.001)
    peaks = [(407.2803, 1000.0), (389.2697, 300.0), (200.0, 100.0)]
    explanation = explain_formula("C24H40O5", "[M-H]-", peaks, name="Cholic acid")
    assert explanation.name == "Cholic acid"
    assert explanation.matched == 2 and explanation.share == pytest.approx(1300 / 1400)
    routes = {m.best_route for m in explanation.matches}
    assert "[M-H-H2O]-" in routes


def test_unplaced_deuterium_offers_every_count_and_the_spectrum_picks_one():
    from milq.explain import D_MINUS_H, explain_formula

    # a d4 cholic acid: the intact ion carries all four; a water loss may
    # have taken one with it
    d4 = 407.2803 + 4 * D_MINUS_H
    peaks = [(d4, 1000.0), (d4 - 18.0106 - D_MINUS_H, 200.0)]
    explanation = explain_formula("C24H40O5", "[M-H]-", peaks, deuterium=4)
    assert explanation.matched == 2
    routes = {m.best_route for m in explanation.matches}
    assert any(r.endswith("+4D") and "-H2O" not in r for r in routes)
    assert any("-H2O" in r and r.endswith("+3D") for r in routes)


def test_a_drawing_of_ones_own_is_scored_like_a_record(tmp_path):
    from milq.explain import explain_structure, read_molfile, with_labels
    from milq.structure import predict

    hexanol = """1-hexanol
  test

  7  6  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 C   0  0  0  0  0  0
    7.5000    0.0000    0.0000 C   0  0  0  0  0  0
    9.0000    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
  5  6  1  0
  6  7  1  0
M  END
"""
    molecule, name = read_molfile(hexanol)
    assert molecule is not None and name == "1-hexanol"
    assert molecule.formula == "C6H14O"
    ions = predict(molecule, charge=1, max_cuts=1, max_losses=1)
    labelled = with_labels(ions, deuterium=2)
    assert len(labelled) > len(ions)
    assert any(ion.labels == 2 and ion.description.endswith("+2D") for ion in labelled)
    assert all(ion.labels <= 2 for ion in labelled)
    explanation = explain_structure(molecule, [(103.1117, 100.0)], name="1-hexanol",
                                    charge=1)
    assert explanation.name == "1-hexanol" and explanation.record.category == "your own"


def test_the_panel_explains_with_a_formula():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.ui.lipid_panel import LipidPanel

    panel = LipidPanel()
    import numpy as np
    panel.set_spectrum(np.array([407.2803, 389.2697]), np.array([1000.0, 300.0]))
    panel.explain_adduct.setCurrentText("[M-H]-")
    panel.own_formula.setText("C24H40O5")
    panel.own_name.setText("Cholic acid")
    panel.explain_own()
    assert panel.explain_tree.topLevelItemCount() == 1
    assert panel.explain_tree.topLevelItem(0).text(0) == "Cholic acid"
    assert panel.match_tree.topLevelItemCount() == 2
    assert "no bonds to cut" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


# --------------------------------------------------------------------------- #
# where the labels are
# --------------------------------------------------------------------------- #
HEXANOIC = """hexanoic acid
  test

  8  7  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 C   0  0  0  0  0  0
    7.5000    0.0000    0.0000 C   0  0  0  0  0  0
    8.2500    1.2990    0.0000 O   0  0  0  0  0  0
    9.0000    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
  5  6  1  0
  6  7  2  0
  6  8  1  0
M  END
"""

#: the same acid drawn with its three methyl hydrogens written out and
#: marked heavy — how a vendor draws a d3 standard
HEXANOIC_D3 = """hexanoic acid-d3
  test

 11 10  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 C   0  0  0  0  0  0
    7.5000    0.0000    0.0000 C   0  0  0  0  0  0
    8.2500    1.2990    0.0000 O   0  0  0  0  0  0
    9.0000    0.0000    0.0000 O   0  0  0  0  0  0
   -0.5000    0.8660    0.0000 H   0  0  0  0  0  0
   -0.5000   -0.8660    0.0000 H   0  0  0  0  0  0
   -1.0000    0.0000    0.0000 H   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
  5  6  1  0
  6  7  2  0
  6  8  1  0
  1  9  1  0
  1 10  1  0
  1 11  1  0
M  ISO  3   9   2  10   2  11   2
M  END
"""


def labelled_ions(molecule, deuterium=3):
    from milq.explain import with_labels

    return with_labels(predict(molecule, charge=-1, max_cuts=1, max_losses=0),
                       deuterium)


def one_ion(ions, atoms, labels):
    """The predicted ion for one piece carrying one number of labels."""
    wanted = frozenset(atoms)
    found = [i for i in ions if i.fragment.atoms == wanted and i.labels == labels]
    assert found, f"no ion for {sorted(atoms)} carrying {labels}"
    return sorted(found, key=lambda i: abs(i.hydrogens))[0]


def observed(molecule, ions, seen, rivals=None):
    """An explanation made by hand: these ions, matched exactly."""
    from milq.explain import Explanation, PeakMatch, custom_record

    matches = [PeakMatch(mz=ion.mz, intensity=height, ion=ion)
               for ion, height in seen]
    total = sum(height for _ion, height in seen)
    return Explanation(record=custom_record("test", molecule.formula, molecule),
                       matches=matches, explained=total, total=total,
                       considered=len(matches),
                       ions=list(rivals if rivals is not None
                                 else [ion for ion, _h in seen]))


def test_a_piece_that_kept_none_of_the_labels_rules_its_atoms_out():
    from milq.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    # the acid end comes off carrying none of the three labels
    explanation = observed(molecule, ions,
                           [(one_ion(ions, {4, 5, 6, 7}, 0), 1000.0)])
    inference = infer_labels(explanation, molecule, deuterium=3)
    assert inference.placements
    placed = {atom for placement in inference.placements
              for site in placement.sites for atom in site.atoms}
    assert 4 not in placed and placed <= {0, 1, 2, 3}
    assert inference.agreement == pytest.approx(1.0)


def test_a_piece_that_kept_all_of_them_rules_its_atoms_in_and_ties():
    from milq.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    explanation = observed(molecule, ions,
                           [(one_ion(ions, {0, 1, 2, 3}, 3), 1000.0)])
    inference = infer_labels(explanation, molecule, deuterium=3)
    placed = {atom for placement in inference.placements
              for site in placement.sites for atom in site.atoms}
    assert placed <= {0, 1, 2, 3}
    # three labels over a methyl and three methylenes: seventeen ways
    assert inference.tied == 17
    assert inference.total > inference.tied
    assert not inference.agreed          # no single position is in all of them


def test_two_pieces_together_place_the_labels():
    from milq.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    explanation = observed(molecule, ions, [
        (one_ion(ions, {0, 1, 2, 3}, 3), 1000.0),   # the four keep all three
        (one_ion(ions, {4, 5, 6, 7}, 0), 500.0),
    ])
    inference = infer_labels(explanation, molecule, deuterium=3)
    # the second piece says nothing the first did not, so the tie stands
    assert inference.tied == 17
    explanation = observed(molecule, ions, [
        (one_ion(ions, {0, 1, 2, 3}, 3), 1000.0),
        (one_ion(ions, {1, 2, 3, 4, 5, 6, 7}, 0), 500.0),
    ])
    inference = infer_labels(explanation, molecule, deuterium=3)
    assert inference.tied == 1
    assert [(a.atom, a.labels) for a in inference.agreed] == [(0, 3)]
    assert "C1" in inference.agreed[0].description


def test_heteroatom_bound_positions_are_left_out_unless_asked_for():
    from milq.explain import label_positions, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    carbon = label_positions(molecule)
    everything = label_positions(molecule, heteroatoms=True)
    assert [atom for atom, _capacity in carbon] == [0, 1, 2, 3, 4]
    assert [atom for atom, _capacity in everything] == [0, 1, 2, 3, 4, 7]
    assert dict(carbon)[0] == 3                 # a methyl holds three


def test_a_drawing_that_places_its_labels_is_checked_not_inferred():
    from milq.explain import infer_labels, placed_labels, read_molfile

    molecule, name = read_molfile(HEXANOIC_D3)
    assert name == "hexanoic acid-d3"
    assert molecule.formula == "C6H9D3O2"       # the explicit ones folded in
    assert placed_labels(molecule) == (0, 0, 0)
    ions = predict(molecule, charge=-1, max_cuts=1, max_losses=0)
    explanation = observed(molecule, ions,
                           [(one_ion(ions, {0, 1, 2, 3}, 0), 1000.0)])
    inference = infer_labels(explanation, molecule)
    assert inference.placed
    assert inference.checked == (0, 0, 0)
    assert inference.checked_top and inference.checked_agreement == pytest.approx(1.0)
    assert "The drawing places its labels itself" in inference.summary()


def test_a_peak_two_label_counts_reach_is_not_used():
    from milq.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    ion = one_ion(ions, {0, 1, 2, 3}, 3)
    # every prediction is offered as a rival, and a deuterium is 1.55 mDa
    # from the hydrogen it replaced: at m/z 60 that is 26 ppm
    explanation = observed(molecule, ions, [(ion, 1000.0)], rivals=ions)
    wide = infer_labels(explanation, molecule, deuterium=3, tolerance_ppm=40.0)
    assert wide.undecided == 1 and not wide.placements
    assert "with a different number" in wide.note
    assert "1.55 mDa" in wide.note
    narrow = infer_labels(explanation, molecule, deuterium=3, tolerance_ppm=5.0)
    assert narrow.undecided == 0 and narrow.placements


def test_the_panel_places_the_labels_under_the_table():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import numpy as np
    from PyQt6 import QtWidgets

    from milq.explain import read_molfile
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.ui.lipid_panel import LipidPanel

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    ion = one_ion(ions, {0, 1, 2, 3}, 3)
    panel = LipidPanel()
    panel.set_spectrum(np.array([ion.mz]), np.array([1000.0]))
    panel.explain_adduct.setCurrentText("[M-H]-")
    panel._own_molecule = molecule
    panel.own_name.setText("hexanoic acid-d3")
    panel.own_deuterium.setValue(3)
    panel.own_cuts.setValue(1)
    panel.own_losses.setValue(0)
    panel.explain_own()
    assert panel.labels_box.isVisibleTo(panel)
    assert "position" in panel.labels_text.text()
    before = len(panel._inference.positions)
    panel.labels_hetero.setChecked(True)
    assert len(panel._inference.positions) > before
    panel.own_deuterium.setValue(0)
    panel.explain_own()
    assert not panel.labels_box.isVisibleTo(panel)
    panel.deleteLater()
    app.processEvents()


# --------------------------------------------------------------------------- #
# the adduct the precursor was ionised as
# --------------------------------------------------------------------------- #
#: cholic acid-d4 as the ZenoTOF infusion holds it: the ammonium adduct the
#: channel is written 430.35 for, and the water ladder the spectrum shows
CA_D4 = "C24H36D4O5"
CA_LADDER = {"[M+NH4]+": 430.3465, "[M+H]+": 413.3200, "-H2O": 395.3094,
             "-2H2O": 377.2988, "-3H2O": 359.2882}


def test_a_labile_adduct_leaves_and_the_ladder_hangs_off_the_proton():
    """The finding this was written for. An ammoniated precursor is seen
    intact at 430.35 and then as [M+H]+ at 413.32, and every dehydration
    hangs off the 413 — `[M+NH4-H2O]+` is not a species, because the
    ammonia is gone before a hydroxyl leaves."""
    from milq.explain import formula_ions

    ions = formula_ions(CA_D4, "[M+NH4]+")

    def at(mass):
        found = [ion for ion in ions if abs(ion.mz - mass) < 0.002]
        assert found, mass
        return found[0]

    for label, mass in CA_LADDER.items():
        assert at(mass), label
    assert at(430.3465).description == "[M+NH4]+ +4D"
    assert at(413.3200).description == "[M+H]+ (-NH3) +4D"
    assert at(359.2882).description == "[M+H-3H2O]+ +4D"
    # nothing keeps the ammonium while shedding a water
    assert not any(ion.losses and "NH4" in ion.description for ion in ions)


def test_a_dehydration_may_take_a_label_with_it_and_the_rung_says_so():
    """Measured on the real CID spectrum: 359.2870 is the three-water loss
    keeping all four labels and 358.2808 beside it is the same ion keeping
    three, 1.0062 apart, which is D-H and not H."""
    from milq.explain import D_MINUS_H, formula_ions

    ions = formula_ions(CA_D4, "[M+NH4]+")
    kept_three = [ion for ion in ions
                  if abs(ion.mz - (359.2882 - D_MINUS_H)) < 0.002]

    assert kept_three and kept_three[0].description == "[M+H-3H2O]+ +3D"
    # the residual formula is corrected for the label that left
    assert kept_three[0].formula == "C24H31D3O2"
    # a decarboxylation takes no carbon-bound hydrogen, so it says exactly
    dropped_co2 = [ion for ion in ions if ion.losses == ("CO2",)]
    assert {ion.labels for ion in dropped_co2} == {4}


def test_labels_spelt_into_the_formula_are_the_same_labels():
    from milq.explain import formula_ions

    spelt = {ion.description for ion in formula_ions(CA_D4, "[M+NH4]+")}
    unplaced = {ion.description
                for ion in formula_ions("C24H40O5", "[M+NH4]+", deuterium=4)}
    assert spelt == unplaced


def test_a_formate_adduct_fragments_as_the_deprotonated_molecule():
    """The negative-mode case: formic acid leaves and the pieces are
    [M-H]-, so a lipid infused in formate buffer shows its own ladder
    17 Da below what the channel is written for."""
    from milq.explain import formula_ions

    ions = formula_ions("C24H40O5", "[M+HCOO]-")
    descriptions = {ion.description for ion in ions}

    assert "[M+HCOO]-" in descriptions
    assert "[M-H]- (-HCOOH)" in descriptions
    assert "[M-H-2H2O]-" in descriptions
    # nothing keeps the formate while shedding a water. (`-HCOOH` on a rung
    # is formic acid leaving the deprotonated molecule, which is a different
    # thing and a real one.)
    assert not any(ion.losses and ion.form.startswith("[M+HCOO")
                   for ion in ions)
    intact = next(ion for ion in ions if ion.description == "[M+HCOO]-")
    core = next(ion for ion in ions if ion.description == "[M-H]- (-HCOOH)")
    assert intact.mz - core.mz == pytest.approx(46.0055, abs=1e-3)  # HCOOH


def test_a_metal_adduct_offers_the_metal_and_the_proton_and_says_which():
    """Sodium is a coordinate bond and stays on whichever piece keeps the
    coordinating site, which arithmetic cannot know. Both are offered."""
    from milq.explain import formula_ions

    ions = formula_ions("C24H40O5", "[M+Na]+")
    descriptions = {ion.description for ion in ions}

    assert "[M+Na]+" in descriptions and "[M+Na-H2O]+" in descriptions
    assert "[M+H-H2O]+" in descriptions
    # ... but not the intact protonated molecule, which is a different
    # precursor rather than a product of this one
    assert "[M+H]+" not in descriptions


def test_a_drawing_is_scored_as_the_adduct_it_was_ionised_as(cholic):
    """One ion is the whole difference on a structure: the enumerator
    already builds protonated pieces, so a labile adduct adds its own
    intact precursor and nothing else — and that ion is the base peak of
    the EAD infusions."""
    from milq.explain import structure_ions

    molecule = cholic.molecule()
    plain = structure_ions(molecule, adduct="[M+H]+", max_cuts=1, max_losses=1)
    ammonium = structure_ions(molecule, adduct="[M+NH4]+", max_cuts=1,
                              max_losses=1)

    assert len(ammonium) == len(plain) + 1
    added = ({round(i.mz, 4) for i in ammonium}
             - {round(i.mz, 4) for i in plain})
    assert added == {round(408.2876 + 18.0338, 4)}
    forms = {i.description for i in ammonium}
    assert "[M+NH4]+" in forms and "[M+H]+ (-NH3)" in forms
    assert "[M+H-H2O]+" in forms


def test_a_piece_keeps_the_formula_it_is_and_the_precursor_keeps_its_form(cholic):
    from milq.explain import structure_ions

    ions = structure_ions(cholic.molecule(), adduct="[M+NH4]+", max_cuts=1,
                          max_losses=1)
    pieces = [i for i in ions if i.fragment.cuts]

    assert pieces and all(not i.form for i in pieces)
    assert all(i.formula in i.description for i in pieces)


# --------------------------------------------------------------------------- #
# a name of one's own
# --------------------------------------------------------------------------- #
def test_a_standard_is_resolved_by_the_name_on_the_bottle():
    from milq.explain import resolve_name
    from milq.lipidmaps import LipidDatabase

    database = LipidDatabase([
        record("LMST04010001", "Cholic acid", "C24H40O5", "LMST04010001",
               408.287574)])
    resolved = resolve_name("cholic acid-d4", database=database)

    assert resolved is not None
    assert resolved.formula == "C24H40O5" and resolved.labels == 4
    assert resolved.source == "the standards table"
    assert resolved.molecule() is not None       # the drawing came from LMSD


def test_a_standard_resolves_without_a_database_too():
    """The table carries the formula for a machine with no LMSD installed;
    what is lost is the drawing, not the answer."""
    from milq.explain import resolve_name

    resolved = resolve_name("TDCA-d4", database=None, use_installed=False)

    assert resolved.formula == "C26H45NO6S" and resolved.labels == 4
    assert resolved.molecule() is None


def test_a_name_nothing_knows_is_not_guessed_at():
    from milq.explain import resolve_name

    assert resolve_name("frobnicic acid", use_installed=False) is None
    assert resolve_name("", use_installed=False) is None


def test_a_lipid_shorthand_name_still_gives_its_formula():
    from milq.explain import resolve_name

    resolved = resolve_name("SM(d18:1/16:0)", database=None,
                            use_installed=False)
    assert resolved.formula == "C39H79N2O6P"
    assert resolved.source == "the lipid shorthand"


# --------------------------------------------------------------------------- #
# the panel: the adduct read off the precursor, and the refusal
# --------------------------------------------------------------------------- #
def _panel(precursor=None, polarity="Positive", peaks=((430.3465, 1000.0),)):
    from PyQt6 import QtWidgets

    from milq.ui.lipid_panel import LipidPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = LipidPanel()
    mz = np.array([m for m, _h in peaks])
    intensity = np.array([h for _m, h in peaks])
    panel.set_spectrum(mz, intensity, precursor, polarity)
    return app, panel


def test_the_panel_reads_the_adduct_off_the_written_precursor():
    """The user's own case: a channel written 430.35, a formula typed by
    hand, and no idea that the difference is an ammonium."""
    app, panel = _panel(precursor=430.35, peaks=[(430.3465, 1000.0),
                                                 (359.2882, 800.0)])
    panel.own_formula.setText(CA_D4)
    panel.own_name.setText("Cholic acid-d4")
    panel.explain_own()

    assert panel.explain_tree.topLevelItemCount() == 1
    assert "[M+NH4]+" in panel.explanation_basis
    assert "430.3465" in panel.explanation_basis
    assert "[M+H]+ would be 413.3200" in panel.explanation_basis
    routes = {panel.match_tree.topLevelItem(i).text(2)
              for i in range(panel.match_tree.topLevelItemCount())}
    assert routes == {"[M+NH4]+ +4D", "[M+H-3H2O]+ +4D"}
    panel.deleteLater()
    app.processEvents()


def test_the_panel_takes_a_name_and_finds_its_labels_and_its_drawing():
    app, panel = _panel(precursor=430.35, peaks=[(430.3465, 1000.0)])
    panel.own_name.setText("cholic acid-d4")
    panel.explain_own()

    assert "read as C24H40O5" in panel.status.text()
    assert "4 unplaced label(s)" in panel.status.text()
    assert "the standards table" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


def test_the_panel_explains_nothing_when_no_adduct_fits():
    """The refusal. Cholic acid unlabelled cannot reach 430.35 under any
    adduct, and explaining it anyway would predict every fragment from a
    molecule the quadrupole never isolated."""
    app, panel = _panel(precursor=430.35, peaks=[(430.3465, 1000.0)])
    panel.own_formula.setText("C24H40O5")
    panel.explain_own()

    assert panel.explain_tree.topLevelItemCount() == 0
    assert panel.explanation_basis == ""
    assert "Nothing explained" in panel.status.text()
    assert "none of the adducts of C24H40O5" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


def test_the_panel_lets_the_adduct_be_overridden_by_hand():
    app, panel = _panel(precursor=430.35, peaks=[(413.3200, 1000.0)])
    panel.own_formula.setText(CA_D4)
    panel.own_adduct.setCurrentText("[M+H]+")
    panel.explain_own()

    assert "chosen by hand" in panel.explanation_basis
    assert panel.explain_tree.topLevelItemCount() == 1
    panel.deleteLater()
    app.processEvents()


def test_the_panel_never_offers_a_negative_adduct_to_a_positive_channel():
    from milq.chemistry import adducts_matching

    app, panel = _panel(precursor=407.28, polarity="Positive")
    signs = {m.name[-1] for m in adducts_matching("C24H40O5", 407.28,
                                                  panel._polarity)}
    assert signs == {"+"}
    panel.deleteLater()
    app.processEvents()


def test_the_explorer_hands_the_lipid_panel_its_own_survey_scan():
    """
    A product-ion scan cannot say which adduct its precursor is: Q1 passed
    one mass and the satellites never reached the detector. The survey of
    the same acquisition, over the same scans, can — so the Explorer looks
    for one and hands it over, and where the method has none it hands over
    nothing rather than something else's spectrum.
    """
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import numpy as np
    from PyQt6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.samples import SampleEntry
    from milq.session import Session
    from milq.ui.explorer import ChannelRef, ExplorerWorkspace
    from milq.wiff import ChannelInfo

    mz = np.arange(400.0, 440.0, 0.01)

    class _Channel:
        def __init__(self, index, ms1, tag):
            self.index = index
            self.tag = tag
            self.info = ChannelInfo(
                index=index, name="TOF MS" if ms1 else "TOF PI",
                experiment_type="TOF MS" if ms1 else "Product",
                polarity="Positive", precursor=None if ms1 else 430.35,
                start_mass=400.0, end_mass=440.0, n_scans=60,
                collision_energy=None if ms1 else 45.0)
            self.asked = []

        @property
        def rt(self):
            return np.linspace(0.0, 15.0, 60)

        def rt_at_scan(self, scan):
            return float(self.rt[int(scan)])

        def spectrum_rt_range(self, rt0, rt1, add_zeros=True):
            self.asked.append((rt0, rt1))
            return mz, np.full(mz.size, float(self.tag))

        def scans_in_range(self, rt0, rt1):
            return 20, 24

        def tic(self):
            return self.rt, np.full(60, 1000.0)

    class _Sample:
        instrument = "ZenoTOF"
        problem = None

        def __init__(self, channels):
            self.channels = channels

    survey, product = _Channel(0, True, 7.0), _Channel(1, False, 3.0)
    explorer = ExplorerWorkspace(Session())
    entry = SampleEntry("/d/CA-d4.wiff", 0, "CA-d4")
    entry.sample = _Sample([survey, product])
    explorer.active_ref = ChannelRef(entry, product)
    explorer._show_average(5.0, 6.0)

    found = explorer._survey_spectrum(430.35)
    assert found is not None
    assert float(found[1][0]) == 7.0                  # the survey, not the pane
    assert survey.asked[-1] == (5.0, 6.0)             # the same scans

    # a sample whose only channel is the product-ion one has nothing to give
    entry.sample = _Sample([product])
    assert explorer._survey_spectrum(430.35) is None
    # and the survey is never handed back for itself
    explorer.active_ref = ChannelRef(entry, survey)
    assert explorer._survey_spectrum(430.35) is None
    explorer.deleteLater()
    app.processEvents()

# --------------------------------------------------------------------------- #
# a LIPID MAPS record through the same adduct model
# --------------------------------------------------------------------------- #
#: triacetin, TG 2:0/2:0/2:0 — a real triacylglycerol small enough to draw by
#: hand, and the smallest thing that can be asked what a TG asks: three ester
#: bonds, no free hydroxyl, and it is seen as [M+NH4]+
TRIACETIN = """triacetin
  test

 15 14  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
   -0.7500    1.2990    0.0000 O   0  0  0  0  0  0
   -2.2500    1.2990    0.0000 C   0  0  0  0  0  0
   -3.0000    0.0000    0.0000 O   0  0  0  0  0  0
   -3.0000    2.5980    0.0000 C   0  0  0  0  0  0
    2.2500   -1.2990    0.0000 O   0  0  0  0  0  0
    3.7500   -1.2990    0.0000 C   0  0  0  0  0  0
    4.5000   -0.0000    0.0000 O   0  0  0  0  0  0
    4.5000   -2.5980    0.0000 C   0  0  0  0  0  0
    3.7500    1.2990    0.0000 O   0  0  0  0  0  0
    5.2500    1.2990    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 O   0  0  0  0  0  0
    6.0000    2.5980    0.0000 C   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  1  4  1  0
  4  5  1  0
  5  6  2  0
  5  7  1  0
  2  8  1  0
  8  9  1  0
  9 10  2  0
  9 11  1  0
  3 12  1  0
 12 13  1  0
 13 14  2  0
 13 15  1  0
M  END
"""

#: what the drawing weighs, and where each adduct of it is seen
TRIACETIN_MASS = 218.079038
TG_AMMONIUM = 236.112864          # [M+NH4]+
TG_PROTON = 219.086315            # [M+H]+, the core the ammonium hands over
#: the diacylglycerol-analogue ion: [M+H - acetic acid]+, reached by a cut
TG_DIACYL = 159.065185
#: what a metal adduct adds over the proton it replaces
NA_MINUS_H = 21.981948


def triacetin_record():
    molecule = parse_molblock(TRIACETIN, "C9H14O6")
    return LipidRecord(lm_id="LMGL03010000", name="TG 2:0/2:0/2:0", abbrev="",
                       formula="C9H14O6", exact_mass=TRIACETIN_MASS,
                       structure=molecule.to_compact())


def test_a_record_at_an_ammonium_precursor_gets_its_core_and_its_ladder():
    """
    The record path is the own-structure path with the drawing taken out of
    the database, so a triacylglycerol annotated [M+NH4]+ is scored with the
    intact ammonium, the [M+H]+ it hands over, and the ladder off *that*.
    """
    from milq.explain import structure_ions

    molecule = triacetin_record().molecule()
    ions = structure_ions(molecule, adduct="[M+NH4]+", max_cuts=1, max_losses=2)
    forms = {ion.form for ion in ions if ion.form}
    assert "[M+NH4]+" in forms                      # the intact adduct
    assert "[M+H]+ (-NH3)" in forms                 # the core it hands over
    assert {"[M+H-CO]+", "[M+H-CO2]+", "[M+H-2CO2]+"} <= forms   # the ladder
    # nothing hangs off the ammonium: it is gone before anything breaks
    assert not any(form.startswith("[M+NH4-") for form in forms)
    # and every piece carries a proton rather than the adduct
    assert {ion.carrier for ion in ions} == {""}
    assert any(abs(ion.mz - TG_DIACYL) < 1e-3 for ion in ions)
    plain = structure_ions(molecule, adduct="[M+H]+", max_cuts=1, max_losses=2)
    # exactly one ion more than the protonated molecule gives: the ammonium
    assert len(ions) == len(plain) + 1


def test_a_record_at_a_sodium_precursor_offers_both_carriers():
    from milq.explain import structure_ions

    molecule = triacetin_record().molecule()
    ions = structure_ions(molecule, adduct="[M+Na]+", max_cuts=1, max_losses=2)
    assert {ion.carrier for ion in ions} == {"", "Na"}
    forms = {ion.form for ion in ions if ion.form}
    assert {"[M+Na]+", "[M+H]+", "[M+Na-CO]+", "[M+H-CO]+"} <= forms
    # the same piece, once with the metal and once with a proton
    sodiated = [i for i in ions if abs(i.mz - TG_DIACYL - NA_MINUS_H) < 1e-3]
    protonated = [i for i in ions if abs(i.mz - TG_DIACYL) < 1e-3]
    assert sodiated and protonated
    assert sodiated[0].carrier == "Na" and protonated[0].carrier == ""


def test_a_record_says_which_adduct_it_was_scored_as():
    peaks = [(TG_AMMONIUM, 1000.0), (TG_DIACYL, 400.0)]
    result = explain(triacetin_record(), peaks, adduct="[M+NH4]+")
    assert result.adduct == "[M+NH4]+"
    assert "labile" in result.behaviour and "NH3" in result.behaviour
    assert result.matched == 2 and result.share == 1.0


def test_the_record_search_finds_what_the_proton_adduct_cannot():
    """
    A triacylglycerol is not a lipid at all as [M+H]+: asked for the proton
    adduct of an ammonium precursor the database answers nothing, which is
    not the same as there being nothing there.
    """
    database = LipidDatabase([triacetin_record()])
    peaks = [(TG_AMMONIUM, 1000.0), (TG_DIACYL, 400.0)]
    assert rank_candidates(database, TG_AMMONIUM, peaks, adduct="[M+H]+",
                           tolerance=0.5, unit="Da") == []
    ranked = rank_candidates(database, TG_AMMONIUM, peaks, adduct=None,
                             tolerance=0.5, unit="Da", polarity="Positive")
    assert [e.adduct for e in ranked] == ["[M+NH4]+"]
    assert ranked[0].matched == 2
    assert abs(ranked[0].precursor_ppm) < 0.1


def test_a_non_proton_adduct_has_to_name_the_precursor():
    """
    The gate. The isolation window is half a dalton because a method writes
    its precursor rounded; letting every adduct through it multiplies the
    candidates that explain a spectrum by accident, so an adduct that is not
    the written reading has to fit the mass — see `explain.adduct_gate`.
    """
    from milq.explain import adduct_gate

    database = LipidDatabase([triacetin_record()])
    peaks = [(TG_DIACYL, 1000.0)]
    assert adduct_gate(TG_AMMONIUM) == 0.05
    # 0.3 Da out: inside the isolation window, outside the gate
    assert rank_candidates(database, TG_AMMONIUM + 0.3, peaks, adduct=None,
                           tolerance=0.5, unit="Da", polarity="Positive") == []
    # the proton adduct is not gated: it is the reading the method wrote down
    ranked = rank_candidates(database, TG_PROTON + 0.3, peaks, adduct=None,
                             tolerance=0.5, unit="Da", polarity="Positive")
    assert [e.adduct for e in ranked] == ["[M+H]+"]


def test_the_panel_reads_a_records_adduct_off_the_written_precursor(monkeypatch):
    """
    The record path's basis line is the own path's, written by the same code
    in `chemistry`: which adduct found this candidate, and how far the
    written precursor sits from it.
    """
    from PyQt6 import QtWidgets

    from milq import lipidmaps
    from milq.ui.lipid_panel import AUTO_ADDUCT, LipidPanel

    database = LipidDatabase([triacetin_record()])
    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: database)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = LipidPanel()
    panel.refresh_availability()
    panel.set_spectrum(np.array([TG_AMMONIUM, TG_DIACYL]),
                       np.array([1000.0, 400.0]), 236.11, "Positive")
    assert panel.explain_adduct.currentText() == AUTO_ADDUCT
    panel.explain_spectrum()

    assert panel.explain_tree.topLevelItemCount() == 1
    row = panel.explain_tree.topLevelItem(0)
    assert row.text(4) == "[M+NH4]+"
    assert "labile" in row.toolTip(4)
    assert "236.11 is [M+NH4]+ of C9H14O6 (236.1129, -12.1 ppm)" in panel.explanation_basis
    assert panel.explanation_adduct == "[M+NH4]+"
    # and the combo overrides it: asked for the proton adduct there is nothing
    panel.explain_adduct.setCurrentText("[M+H]+")
    panel.explain_spectrum()
    assert panel.explain_tree.topLevelItemCount() == 0
    assert "as [M+H]+" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


def test_the_mass_search_lists_the_adduct_and_what_it_does(monkeypatch):
    from PyQt6 import QtWidgets

    from milq import lipidmaps
    from milq.ui.lipid_panel import EVERY_ADDUCT, LipidPanel

    database = LipidDatabase([triacetin_record()])
    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: database)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = LipidPanel()
    panel.refresh_availability()
    panel._polarity = "Positive"
    panel.mz_edit.setText(f"{TG_AMMONIUM:.4f}")
    panel.adduct_combo.setCurrentText(EVERY_ADDUCT)
    panel.search()

    assert panel.tree.topLevelItemCount() == 1
    row = panel.tree.topLevelItem(0)
    assert row.text(5) == "[M+NH4]+"
    assert "leaves as NH3" in row.toolTip(5)
    panel.deleteLater()
    app.processEvents()
