"""Reading a connection table, and the fragments a cleavage would leave."""

from pathlib import Path

import pytest

from milq.chemistry import parse_formula
from milq.structure import (
    Structure,
    fragments,
    implicit_hydrogens,
    isotope_label,
    parse_molblock,
    predict,
    ring_bonds,
)

FIXTURES = Path(__file__).parent / "fixtures"


def molblock(atoms, bonds, tail=()) -> str:
    """A minimal V2000 block: (element, x, y) atoms and (a, b, order) bonds."""
    lines = ["name", "  test", "",
             f"{len(atoms):3}{len(bonds):3}  0     0  0            999 V2000"]
    for element, x, y in atoms:
        lines.append(f"{x:10.4f}{y:10.4f}{0.0:10.4f} {element:<3} 0  0  0  0")
    for a, b, order in bonds:
        lines.append(f"{a + 1:3}{b + 1:3}{order:3}  0  0  0  0")
    lines.extend(tail)
    lines.append("M  END")
    return "\n".join(lines)


ETHANOL = molblock([("C", 0, 0), ("C", 1, 0), ("O", 2, 0)],
                   [(0, 1, 1), (1, 2, 1)])
#: cyclopropane: three carbons, no way to open it with one cut
RING = molblock([("C", 0, 0), ("C", 1, 0), ("C", 0.5, 1)],
                [(0, 1, 1), (1, 2, 1), (2, 0, 1)])


# -- reading ---------------------------------------------------------------- #
def test_atoms_bonds_and_the_hydrogens_left_off():
    structure = parse_molblock(ETHANOL)
    assert [a.element for a in structure.atoms] == ["C", "C", "O"]
    assert len(structure.bonds) == 2
    # CH3-CH2-OH: the drawing shows none of the six
    assert [a.hydrogens for a in structure.atoms] == [3, 2, 1]
    assert structure.formula == "C2H6O"


def test_a_double_bond_takes_a_hydrogen_with_it():
    ethene = molblock([("C", 0, 0), ("C", 1, 0)], [(0, 1, 2)])
    assert parse_molblock(ethene).formula == "C2H4"


def test_a_charge_moves_the_valence():
    # ammonium: the cation makes room for a fourth bond, so four hydrogens
    charged = molblock([("N", 0, 0)], [], tail=["M  CHG  1   1   1"])
    structure = parse_molblock(charged)
    assert structure.atoms[0].charge == 1
    assert structure.atoms[0].hydrogens == 4


def test_a_labelled_atom_is_read_as_the_isotope():
    """A d3 standard is drawn with ordinary hydrogens and an M ISO line."""
    labelled = molblock(
        [("C", 0, 0), ("H", 1, 0), ("H", 2, 0), ("H", 3, 0), ("O", 4, 0)],
        [(0, 1, 1), (0, 2, 1), (0, 3, 1), (0, 4, 1)],
        tail=["M  ISO  3   2   2   3   2   4   2"])
    counts = parse_formula(parse_molblock(labelled).formula)
    assert counts.get("D") == 3
    assert isotope_label("H", 2) == "D"
    assert isotope_label("C", 13) == "[13C]"


def test_the_hydrogen_count_is_checked_against_the_published_formula():
    assert parse_molblock(ETHANOL, "C2H6O").reliable
    # a structure that does not add up would otherwise produce exact-looking
    # fragment masses that are wrong
    assert not parse_molblock(ETHANOL, "C2H4O").reliable


def test_a_formula_the_mass_table_cannot_read_counts_as_unverified():
    assert not parse_molblock(ETHANOL, "C2H6As").reliable


@pytest.mark.parametrize("element, bonds, charge, expected", [
    ("C", 4, 0, 0), ("C", 3, 0, 1), ("N", 3, 0, 0), ("N", 4, 1, 0),
    ("O", 1, 0, 1), ("O", 1, -1, 0), ("S", 2, 0, 0), ("S", 6, 0, 0),
    ("Xx", 1, 0, 0),
])
def test_implicit_hydrogens(element, bonds, charge, expected):
    assert implicit_hydrogens(element, bonds, charge) == expected


@pytest.mark.parametrize("text", ["", "one\ntwo\nthree", "a\nb\nc\nnot a count line",
                                  molblock([], [])])
def test_something_that_is_not_a_connection_table(text):
    assert parse_molblock(text) is None


def test_the_compact_form_survives_a_round_trip():
    original = parse_molblock(
        (FIXTURES / "LMSP03010002.mol").read_text(), "C35H71N2O6P")
    back = Structure.from_compact(original.to_compact())
    assert back.formula == original.formula
    assert len(back.bonds) == len(original.bonds)
    assert [a.charge for a in back.atoms] == [a.charge for a in original.atoms]
    assert back.reliable == original.reliable


# -- cleaving --------------------------------------------------------------- #
def test_a_chain_comes_apart_at_every_bond():
    pieces = fragments(parse_molblock(ETHANOL), min_atoms=1)
    formulas = {f.formula for f in pieces}
    # the pieces as drawn, before any hydrogen moves: cutting C-C leaves a
    # methyl and a methoxy, not methane and methanol
    assert "CH3" in formulas and "CH3O" in formulas
    assert "C2H5" in formulas and "HO" in formulas      # and the C-O bond
    assert "C2H6O" in formulas                          # and the whole thing


def test_the_molecule_itself_is_a_fragment_of_no_cuts():
    whole = next(f for f in fragments(parse_molblock(ETHANOL))
                 if f.formula == "C2H6O")
    # a precursor sheds neutrals without any bond breaking, and a bile acid is
    # mostly seen that way
    assert whole.cut_count == 0


def test_a_ring_stays_whole_until_two_of_its_bonds_go():
    structure = parse_molblock(RING)
    assert ring_bonds(structure) == frozenset({0, 1, 2})
    one_cut = [f for f in fragments(structure, max_cuts=1) if f.cut_count]
    assert one_cut == []
    two_cuts = [f for f in fragments(structure, max_cuts=2, min_atoms=1)
                if f.cut_count == 2]
    assert two_cuts


def test_the_same_piece_is_listed_once_by_its_simplest_route():
    pieces = fragments(parse_molblock(ETHANOL), min_atoms=1)
    assert len({f.atoms for f in pieces}) == len(pieces)


# -- predicting ------------------------------------------------------------- #
def real(name: str, formula: str) -> Structure:
    return parse_molblock((FIXTURES / f"{name}.mol").read_text(), formula)


def nearest(ions, target):
    close = sorted((i for i in ions if abs(i.mz - target) < 0.006),
                   key=lambda i: i.simplicity)
    return close[0] if close else None


def test_the_phosphocholine_a_sphingomyelin_is_measured_on():
    ions = predict(real("LMSP03010002", "C35H71N2O6P"))
    ion = nearest(ions, 184.0733)
    assert ion is not None and ion.mz == pytest.approx(184.0733, abs=5e-4)
    assert ion.fragment.cut_count == 1


def test_the_water_losses_a_bile_acid_is_measured_on():
    ions = predict(real("LMST04010001", "C24H40O5"))
    for target in (391.2843, 373.2737, 355.2632):
        ion = nearest(ions, target)
        assert ion is not None, target
        assert ion.mz == pytest.approx(target, abs=1e-3)


def test_a_loss_needs_the_atoms_it_takes_away():
    # nothing to lose a carbon dioxide from
    ions = predict(parse_molblock(molblock([("C", 0, 0), ("C", 1, 0)],
                                           [(0, 1, 1)])), min_mz=0.0)
    assert all("CO2" not in ion.losses for ion in ions)


def test_the_simplest_route_to_a_mass_is_the_one_kept():
    ions = predict(real("LMST04010001", "C24H40O5"))
    by_mz = {}
    for ion in ions:
        by_mz.setdefault(round(ion.mz, 4), []).append(ion)
    assert all(len(v) == 1 for v in by_mz.values())


def test_ions_below_the_floor_are_left_out():
    ions = predict(real("LMST04010001", "C24H40O5"), min_mz=200.0)
    assert ions and min(i.mz for i in ions) >= 200.0


def test_a_negative_ion_is_the_same_arithmetic_the_other_way():
    positive = predict(real("LMST04010001", "C24H40O5"), charge=1)
    negative = predict(real("LMST04010001", "C24H40O5"), charge=-1)
    assert negative and len(negative) == len(positive)
    # [M-H]- of cholic acid
    assert nearest(negative, 407.2803) is not None


# -- through the index ------------------------------------------------------- #
def test_the_connection_table_is_kept_when_the_sdf_is_read():
    import io

    from milq.lipidmaps import LipidDatabase, parse_sdf

    sdf = "\n".join([
        molblock([("C", 0, 0), ("C", 1, 0), ("O", 2, 0)],
                 [(0, 1, 1), (1, 2, 1)]),
        "> <LM_ID>", "LMTEST00001", "",
        "> <NAME>", "ethanol", "",
        "> <FORMULA>", "C2H6O", "",
        "> <EXACT_MASS>", "46.041865", "",
        "$$$$",
    ])
    records = parse_sdf(io.StringIO(sdf))
    assert len(records) == 1
    record = records[0]
    assert record.structure is not None

    molecule = record.molecule()
    assert molecule.formula == "C2H6O"
    assert molecule.reliable

    # and it survives being written to the index and read back. The index is
    # a database and a database is an open file: Windows will not remove one,
    # so it is closed before the file is, which is what `close` is for.
    saved = LipidDatabase(records)
    written = Path(__file__).parent / "fixtures" / "_tmp-index.json.gz"
    reloaded = LipidDatabase.load(saved.save(written))
    try:
        assert reloaded.records[0].molecule().formula == "C2H6O"
    finally:
        reloaded.close()
        written.unlink(missing_ok=True)


def test_a_record_with_no_structure_says_so_rather_than_failing():
    from milq.lipidmaps import LipidRecord

    record = LipidRecord(lm_id="LMX", name="x", abbrev="", formula="C2H6O",
                         exact_mass=46.0)
    assert record.molecule() is None


# -- a loss needs its functional group ---------------------------------------- #
def test_the_groups_a_piece_carries_are_read_off_the_bonds():
    structure = parse_molblock(ETHANOL)
    groups = structure.functional_groups(range(len(structure.atoms)))
    assert groups["hydroxyl"] == 1
    assert groups["carboxyl"] == 0 and groups["carbonyl"] == 0


def test_a_carboxyl_is_seen_as_both_carboxyl_and_carbonyl():
    acetic = molblock([("C", 0, 0), ("C", 1, 0), ("O", 2, 0), ("O", 1, 1)],
                      [(0, 1, 1), (1, 2, 1), (1, 3, 2)])
    groups = parse_molblock(acetic).functional_groups(range(4))
    assert groups["carboxyl"] == 1 and groups["carbonyl"] == 1
    assert groups["hydroxyl"] == 1          # the -OH of the acid


def test_a_ceramide_is_not_offered_the_carbon_dioxide_loss_it_cannot_make():
    """
    Counting elements said yes — three oxygens, plenty of carbon — and the
    sphingoid base at 264.2686 came out as a CO2 loss. There is no carboxyl
    anywhere in a ceramide.
    """
    structure = real("LMSP03010002", "C35H71N2O6P")
    ions = predict(structure, max_cuts=1, max_losses=2)
    for ion in ions:
        groups = structure.functional_groups(ion.fragment.atoms)
        if "CO2" in ion.losses:
            assert groups["carboxyl"] >= ion.losses.count("CO2")
        if "H2O" in ion.losses:
            assert groups["hydroxyl"] >= ion.losses.count("H2O")


def test_two_water_losses_need_two_hydroxyls():
    one_alcohol = parse_molblock(ETHANOL)
    ions = predict(one_alcohol, max_losses=2, min_mz=0.0)
    assert all(ion.losses.count("H2O") <= 1 for ion in ions)


def test_a_rival_route_to_the_same_mass_is_kept_not_dropped():
    """Collapsing to the simplest route is what hid the right one."""
    ions = predict(real("LMST04010001", "C24H40O5"), max_cuts=1, max_losses=2)
    assert any(ion.alternatives for ion in ions)
    for ion in ions:
        assert ion.description not in ion.alternatives
        assert len(set(ion.alternatives)) == len(ion.alternatives)


def test_explicit_hydrogens_are_folded_into_the_atoms_that_carry_them():
    """
    PubChem writes all forty of a bile acid's hydrogens out.

    Cutting a C–H bond is not a fragment anybody looks for, and forty of
    them are forty pieces that differ from the whole molecule by one
    hydrogen — which a hydrogen shift already covers.
    """
    from milq.structure import suppress_hydrogens

    ethanol = parse_molblock(ETHANOL)
    assert suppress_hydrogens(ethanol) is ethanol      # nothing to fold in

    explicit = """methanol-d3
  test

  5  4  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 O   0  0  0  0  0  0
   -0.5000    0.8660    0.0000 H   0  0  0  0  0  0
   -0.5000   -0.8660    0.0000 H   0  0  0  0  0  0
   -1.0000    0.0000    0.0000 H   0  0  0  0  0  0
  1  2  1  0
  1  3  1  0
  1  4  1  0
  1  5  1  0
M  ISO  3   3   2   4   2   5   2
M  END
"""
    drawn = parse_molblock(explicit)
    assert len(drawn.atoms) == 5 and drawn.formula == "CHD3O"
    folded = suppress_hydrogens(drawn)
    assert len(folded.atoms) == 2 and len(folded.bonds) == 1
    assert folded.formula == drawn.formula             # the mass is untouched
    assert folded.atoms[0].deuterium == 3
    assert folded.atoms[1].hydrogens == 1              # the hydroxyl's own
