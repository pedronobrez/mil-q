"""
The peaks nothing explained, given a formula to try and a name where there
is one.

Every mass below is arithmetic on a formula, computed in the test rather
than typed, so a test that passes says the module agrees with `chemistry`
and not that two constants were copied from the same place. The one
exception is the phthalate, which is a tabulated background mass and is
meant to be compared against the table.

What is checked is the shape of the answer: a satellite of an ion that was
matched beats a composition, a composition is offered only from atoms the
precursor has, and a mass needing an atom the precursor has not got comes
back refused rather than approximated.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import unexplained as U  # noqa: E402
from milq.chemistry import (ADDUCTS_BY_NAME, ELECTRON_MASS,  # noqa: E402
                                 monoisotopic_mass, parse_formula)
from milq.explain import explain_formula  # noqa: E402

FORMULA = "C20H34O2"
ADDUCT = "[M+H]+"
NEUTRAL = monoisotopic_mass(parse_formula(FORMULA))
PRECURSOR = ADDUCTS_BY_NAME[ADDUCT].mz(NEUTRAL)
#: the water loss, an ion the prediction offers and the spectrum will show
WATER_LOSS = PRECURSOR - U.WATER
#: a piece of the precursor: nothing but its own carbons, hydrogens and one
#: of its oxygens
PIECE = monoisotopic_mass(parse_formula("C10H17O")) - ELECTRON_MASS
#: protonated taurine — a real fragment of a real compound, and one this
#: precursor cannot make: it has neither the nitrogen nor the sulfur
OUTSIDE = monoisotopic_mass(parse_formula("C2H8NO3S")) - ELECTRON_MASS
PHTHALATE = 149.0233


def _explained(peaks):
    """An explanation of `peaks` from the formula, as the tab would make it."""
    return explain_formula(FORMULA, ADDUCT, peaks, name="Testol")


def _annotate(peaks, **kwargs):
    mz = [m for m, _h in peaks]
    intensity = [h for _m, h in peaks]
    return U.annotate(mz, intensity, _explained(peaks), FORMULA, ADDUCT,
                      "Positive", **kwargs)


def _row(rows, mz):
    found = [row for row in rows if abs(row.mz - mz) < 0.01]
    assert found, f"{mz:.4f} is not in {[f'{r.mz:.4f}' for r in rows]}"
    return found[0]


# --------------------------------------------------------------------------- #
# what a named mass looks like
# --------------------------------------------------------------------------- #
def test_a_sodium_satellite_of_a_matched_ion_is_named_as_one():
    """
    The sodiated form of a fragment sits 21.982 above it, not 22.989: an ion
    already carries its charge, so the sodium replaces the proton.
    """
    sodiated = WATER_LOSS + U.NA_FOR_H
    peaks = [(PRECURSOR, 10_000.0), (WATER_LOSS, 6_000.0), (sodiated, 900.0)]
    rows = _annotate(peaks)

    row = _row(rows, sodiated)
    assert row.kind == U.SATELLITE
    assert "sodiated" in row.label
    assert abs(row.error_ppm) < 1.0
    assert row.accounted and row.named


def test_a_carbon_13_satellite_is_named_before_any_composition():
    from milq.chemistry import NEUTRON_SPACING

    satellite = WATER_LOSS + NEUTRON_SPACING
    peaks = [(PRECURSOR, 10_000.0), (WATER_LOSS, 6_000.0), (satellite, 1_200.0)]

    row = _row(_annotate(peaks), satellite)
    assert row.kind == U.SATELLITE
    assert "13C" in row.label


def test_a_phthalate_is_named_from_the_table():
    peaks = [(PRECURSOR, 10_000.0), (PHTHALATE, 2_000.0)]

    row = _row(_annotate(peaks), PHTHALATE)
    assert row.kind == U.CONTAMINANT
    assert "phthalate" in row.label
    assert abs(row.error_ppm) < 5.0
    # and the table's mass is the arithmetic it claims to be
    computed = monoisotopic_mass(parse_formula("C8H5O3")) - ELECTRON_MASS
    assert abs(PHTHALATE - computed) < 0.0005


def test_a_contaminant_of_the_other_polarity_is_not_offered():
    """Trifluoroacetate is an anion; a positive spectrum never sees it."""
    positive = {label for _mz, label in U.CONTAMINANTS[1]}
    negative = {label for _mz, label in U.CONTAMINANTS[-1]}

    assert not positive & negative
    assert all(c.mz > 0 for c in U.contaminant_masses(1))
    assert "trifluoroacetate [C2F3O2]-" not in {
        c.label for c in U.contaminant_masses(1)}


# --------------------------------------------------------------------------- #
# the constrained search
# --------------------------------------------------------------------------- #
def test_a_sub_formula_of_the_precursor_is_offered_with_its_error():
    peaks = [(PRECURSOR, 10_000.0), (PIECE, 3_000.0)]

    row = _row(_annotate(peaks), PIECE)
    assert row.kind == U.FORMULA
    assert row.formula == "C10H17O"
    assert abs(row.error_ppm) < 1.0
    assert row.accounted and not row.named
    assert not row.radical


def test_a_mass_needing_atoms_the_precursor_has_not_got_is_refused():
    """
    The whole point of the constraint. Protonated taurine is a real ion and
    a fine answer for a taurine-conjugated bile acid; for a C20H34O2 it is
    not an answer at all, and saying so is more use than the nearest
    composition made of something else.
    """
    peaks = [(PRECURSOR, 10_000.0), (OUTSIDE, 2_500.0)]

    row = _row(_annotate(peaks), OUTSIDE)
    assert row.kind == U.NOTHING
    assert not row.accounted
    assert row.label == U.NO_FORMULA
    assert row.error_ppm is None
    assert row.formula == ""


def test_the_ranges_are_the_precursor_ion_and_its_slack():
    ranges = U.sub_formula_ranges("C24H36D4O5", ADDUCTS_BY_NAME["[M+NH4]+"])

    assert ranges["C"] == (0, 24)
    assert ranges["O"] == (0, 5)
    assert ranges["D"] == (0, 4)            # never more labels than were put on
    assert ranges["N"] == (0, 1)            # the ammonium's own nitrogen
    # the molecule's 36 + the adduct's 4, and EXTRA_H for a rearrangement
    assert ranges["H"] == (0, 36 + 4 + U.EXTRA_H)


def test_a_formula_that_cannot_be_read_leaves_the_search_unrun():
    assert U.sub_formula_ranges("", ADDUCTS_BY_NAME[ADDUCT]) is None
    assert U.sub_formula_ranges("not a formula", ADDUCTS_BY_NAME[ADDUCT]) is None

    peaks = [(PRECURSOR, 10_000.0), (PIECE, 3_000.0)]
    mz = [m for m, _h in peaks]
    intensity = [h for _m, h in peaks]
    rows = U.annotate(mz, intensity, _explained(peaks), "", ADDUCT, "Positive")

    assert _row(rows, PIECE).kind == U.NOTHING


def test_the_golden_rules_do_not_refuse_a_small_real_fragment():
    """
    Protonated taurine has H/C = 4.0 and the Seven Golden Rules cap it at
    3.1. It is the fragment every taurine-conjugated bile acid gives, and it
    is the strongest unexplained peak of the real TDCA-d4 infusion, so the
    rules are not applied under `GOLDEN_RULE_MASS`.
    """
    ranges = U.sub_formula_ranges("C26H45NO6S", ADDUCTS_BY_NAME["[M+H]+"])
    hits = U.sub_formulas(OUTSIDE, ranges, 1)

    assert OUTSIDE < U.GOLDEN_RULE_MASS
    assert "C2H8NO3S" in [hit.formula for hit in hits]


def test_an_odd_electron_composition_is_offered_and_ranked_last():
    """
    Electron activated dissociation makes radicals — the benzene cation at
    78.0465 is 22% of the base peak of the real CA-d4 EAD spectrum — so an
    odd-electron composition is offered, marked, and never preferred to an
    even-electron rival at the same mass.
    """
    benzene = monoisotopic_mass(parse_formula("C6H6")) - ELECTRON_MASS
    ranges = U.sub_formula_ranges(FORMULA, ADDUCTS_BY_NAME[ADDUCT])
    hits = U.sub_formulas(benzene, ranges, 1)

    assert hits and hits[0].formula == "C6H6"
    assert U.is_radical(hits[0])
    # an even-electron rival, wherever there is one, comes first
    ordered = [U.is_radical(hit) for hit in hits]
    assert ordered == sorted(ordered)

    peaks = [(PRECURSOR, 10_000.0), (benzene, 2_200.0)]
    row = _row(_annotate(peaks), benzene)
    assert row.radical and "odd-electron" in row.label


# --------------------------------------------------------------------------- #
# how the answers are chosen and counted
# --------------------------------------------------------------------------- #
def test_a_named_mass_beats_a_composition_at_the_same_peak():
    """
    A composition can always be assembled; a name is a specific claim. So a
    satellite of something already matched is written even where the
    constrained search would also have answered — here the carbon-13
    satellite of the water loss, which `C20H34O` reaches at 15 ppm.
    """
    from milq.chemistry import NEUTRON_SPACING

    satellite = WATER_LOSS + NEUTRON_SPACING
    peaks = [(PRECURSOR, 10_000.0), (WATER_LOSS, 6_000.0), (satellite, 900.0)]
    ranges = U.sub_formula_ranges(FORMULA, ADDUCTS_BY_NAME[ADDUCT])

    assert U.sub_formulas(satellite, ranges, 1)     # the search does answer
    row = _row(_annotate(peaks), satellite)
    assert row.kind == U.SATELLITE and "13C" in row.label


def test_a_sodium_the_precursor_has_not_got_is_only_ever_a_named_mass():
    """
    The constraint cuts both ways: a sodiated fragment carries an atom the
    precursor ion has not got, so the composition search refuses it and the
    satellite is the only thing that can answer at all.
    """
    sodiated = WATER_LOSS + U.NA_FOR_H
    ranges = U.sub_formula_ranges(FORMULA, ADDUCTS_BY_NAME[ADDUCT])

    assert "Na" not in ranges
    assert U.sub_formulas(sodiated, ranges, 1) == []


def test_only_the_peaks_above_the_floor_are_annotated():
    peaks = [(PRECURSOR, 10_000.0), (PIECE, 3_000.0), (PHTHALATE, 50.0)]
    rows = _annotate(peaks, floor=0.1)

    assert [round(row.mz, 3) for row in rows] == [round(PIECE, 3)]
    # the small one is still evidence, it is only not annotated
    assert len(_annotate(peaks, floor=0.001)) == 2


def test_the_strongest_come_first_and_most_caps_the_list():
    peaks = [(PRECURSOR, 10_000.0), (PIECE, 3_000.0), (PHTHALATE, 5_000.0)]
    rows = _annotate(peaks)

    assert [round(row.mz, 3) for row in rows] == [round(PHTHALATE, 3),
                                                 round(PIECE, 3)]
    assert len(_annotate(peaks, most=1)) == 1


def test_the_tally_counts_each_kind_and_says_so_in_one_sentence():
    sodiated = WATER_LOSS + U.NA_FOR_H
    peaks = [(PRECURSOR, 10_000.0), (WATER_LOSS, 6_000.0),
             (sodiated, 3_000.0), (PHTHALATE, 2_500.0), (PIECE, 2_000.0),
             (OUTSIDE, 1_500.0)]
    counted = U.tally(_annotate(peaks))

    assert counted.peaks == 4
    assert (counted.satellites, counted.contaminants) == (1, 1)
    assert (counted.formulas, counted.nothing) == (1, 1)
    assert counted.accounted == 2
    said = counted.sentence()
    assert "satellite" in said and "contaminant" in said
    assert "nothing reaches at all" in said


def test_nothing_annotated_is_an_empty_answer_not_a_crash():
    assert U.annotate([], [], None, FORMULA, ADDUCT, "Positive") == []
    assert U.annotate([100.0], [0.0], None, FORMULA, ADDUCT, "Positive") == []
    # no explanation at all: every peak above the floor is unexplained
    rows = U.annotate([PIECE], [1_000.0], None, FORMULA, ADDUCT, "Positive")
    assert len(rows) == 1 and rows[0].kind == U.FORMULA


def test_a_negative_spectrum_searches_the_other_polarity():
    formula = "C24H40O5"
    neutral = monoisotopic_mass(parse_formula(formula))
    deprotonated = ADDUCTS_BY_NAME["[M-H]-"].mz(neutral)
    piece = monoisotopic_mass(parse_formula("C12H17O2")) + ELECTRON_MASS
    rows = U.annotate([deprotonated, piece], [10_000.0, 3_000.0], None,
                      formula, "[M-H]-", "Negative")

    row = _row(rows, piece)
    assert row.kind == U.FORMULA and row.formula == "C12H17O2"
    assert row.label.endswith("-")
    assert abs(row.error_ppm) < 1.0


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
def test_the_report_table_names_what_each_unexplained_peak_might_be(qapp):
    """
    The block in `infusion_report`: the same list, with a column saying what
    each peak might be and how far the guess sits from the measured mass.
    """
    from tests.test_infusion_report import STRAY, _entry, _explanation
    from milq import infusion_report as ir

    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    report = ir.report_for(entry, channel, explanation=explanation,
                           formula="C20H34O2", adduct="[M+H]+",
                           basis="the precursor and its losses",
                           measure_precursor=False)
    document = ir.build_html(report)

    assert "What it might be" in document
    assert "Δ ppm" in document
    rows = report.annotations()
    assert rows, "the stray mass should have been annotated"
    assert any(abs(row.mz - STRAY) < 0.01 for row in rows)
    # the sentence says how the unexplained peaks came out
    said = [s for s in report.sentences() if "not accounted for" in s]
    assert len(said) == 1
    assert "Of those," in said[0] or "None of the" in said[0]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_report_survives_a_module_that_answers_nothing(qapp):
    """
    The block is read defensively: a report whose spectrum is not held has
    nothing to annotate, and the table is then the masses alone — which is
    what it printed before there was anything to say about them.
    """
    from tests.test_infusion_report import _entry, _explanation
    from milq import infusion_report as ir

    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    report = ir.report_for(entry, channel, explanation=explanation,
                           measure_precursor=False)
    report.spectrum = None

    assert report.annotations() == []
    document = ir.build_html(report)
    # nothing to annotate and nothing to list: the block says so and the
    # document is still written
    assert "Every peak above the label floor is accounted for." in document
    assert "Peaks it does not account for" in document


def test_the_pool_reaches_below_the_printed_floor(qapp):
    """
    A carbon-13 satellite is about a hundredth of the peak it belongs to and
    the printed table starts at two per cent, so the evidence has to reach
    further down than the list does.
    """
    from milq import infusion_report as ir

    assert ir.ANNOTATION_POOL > 1
    assert ir.ANNOTATION_POOL_PEAKS > ir.PEAKS_LISTED


def test_every_tabulated_mass_is_a_positive_number_with_a_name():
    for polarity, rows in U.CONTAMINANTS.items():
        assert polarity in (1, -1)
        for mz, label in rows:
            assert mz > 0 and label
    for candidate in U.contaminant_masses(1) + U.contaminant_masses(-1):
        assert candidate.mz > 0
        assert candidate.label and candidate.basis
        assert candidate.kind == U.CONTAMINANT


def test_the_solvent_clusters_are_computed_from_their_own_formulas():
    acetonitrile = monoisotopic_mass(parse_formula(U.SOLVENTS["acetonitrile"]))
    protonated = ADDUCTS_BY_NAME["[M+H]+"].mz(acetonitrile * 2)
    labels = {round(c.mz, 4): c.label for c in U.contaminant_masses(1)}

    assert round(protonated, 4) in labels
    assert "acetonitrile" in labels[round(protonated, 4)]
    assert abs(protonated - 83.0604) < 0.001     # the tabulated value


def test_an_isotope_pattern_ranks_the_candidates_where_there_is_one():
    """
    Where the spectrum carries satellites the composition is ranked by them,
    which is the only evidence that separates two formulas at the same mass.
    """
    from milq.chemistry import NEUTRON_SPACING

    ranges = U.sub_formula_ranges(FORMULA, ADDUCTS_BY_NAME[ADDUCT])
    mz = np.array([PIECE, PIECE + NEUTRON_SPACING])
    intensity = np.array([1_000.0, 110.0])
    hits = U.sub_formulas(PIECE, ranges, 1, spectrum=(mz, intensity))

    assert hits
    assert hits[0].isotope_score > 0.0
