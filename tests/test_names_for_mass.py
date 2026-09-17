"""
The name for a mass, when the mass is right and the name is wrong.

`chemistry.names_for_mass` is the other half of `precursor_repairs`: where a
written precursor and its name's formula disagree by a whole dalton, the
instrument acquired the mass that was written — that number is the channel the
data is on — so the name is what is in question, and this is what offers the
names whose formula does match.

The three cases here are the three whole-dalton rows of the real method, and
two of them offer nothing. That is the finding rather than a gap: a chain
moves a lipid's mass by 14 Da, a double bond by 2 and a hydroxyl by 16, so a
name that is out by one odd dalton is not out by a chain at all.
"""

import time

import pytest

from milq.chemistry import (ADDUCTS_BY_NAME, NAME_SEARCH_CARBONS,
                                 NAME_SEARCH_CHAINS, formulas_from_name,
                                 monoisotopic_mass, names_for_mass,
                                 parse_formula, parse_shorthand)
from milq.lipidmaps import LipidDatabase, LipidRecord

PROTON = ADDUCTS_BY_NAME["[M+H]+"]


def names(*args, **kwargs):
    return [s.name for s in names_for_mass(*args, **kwargs)]


# -- the three real rows -------------------------------------------------------- #
def test_the_isomer_one_double_bond_along_is_offered_first():
    """
    `LacCER(d18:1/18:1(9Z))` is written 886.6407 and its own name reads as
    888.6407 — exactly 2.0000 Da, which is a nominal shift and not a real
    double bond (2.0157). The name that weighs 886.6 is the same species with
    one more double bond, and both ways of writing it come first because both
    are one edit from what was written.
    """
    offered = names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))")
    assert [s.name for s in offered[:2]] == ["LacCER(d18:1/18:2)",
                                             "LacCER(d18:2/18:1)"]
    first = offered[0]
    assert first.formula == "C48H87NO13"
    assert first.in_class and first.source == "the class"
    assert first.changes == 1 and first.distance == 1
    # a nominal match, and the row says how nominal: 15.7 mDa
    assert first.mz == pytest.approx(886.6250, abs=5e-5)
    assert first.error_ppm == pytest.approx(-17.7, abs=0.1)


def test_a_whole_odd_dalton_is_not_a_chain_and_the_class_offers_nothing():
    """
    `LacCER(d18:0/18:1)` is written 889.6563 against a formula of 890.6563.
    Nothing this class can be is 1 Da from that: 14 Da a chain, 2 a double
    bond, 16 a hydroxyl, and no combination of them within the search lands on
    an odd dalton. The number is off by a digit, not the name by a chain.
    """
    assert names_for_mass(889.6563, "[M+H]+", like="LacCER(d18:0/18:1)") == []


def test_a_mass_out_of_the_search_s_reach_offers_nothing():
    """
    `C18:1 Cer` is written 464.4 and reads as 564.5350 — a dropped digit. A
    ceramide of 464.4 would need about eleven carbons fewer than the name
    says, which is past what a wrong name is, so the class says nothing.
    """
    assert names_for_mass(464.4, "[M+H]+", like="C18:1 Cer") == []


# -- what may be offered -------------------------------------------------------- #
def test_every_name_offered_is_the_written_name_s_own_class():
    written = parse_shorthand("LacCER(d18:1/18:1(9Z))")
    for suggestion in names_for_mass(886.6407, "[M+H]+",
                                     like="LacCER(d18:1/18:1(9Z))"):
        parsed = parse_shorthand(suggestion.name)
        assert parsed.lipid is written.lipid
        assert len(parsed.chains) == len(written.chains)
        assert parsed.labels == written.labels


def test_no_chain_moves_further_than_the_search_allows():
    written = parse_shorthand("LacCER(d18:1/18:1(9Z))")
    for suggestion in names_for_mass(886.6407, "[M+H]+",
                                     like="LacCER(d18:1/18:1(9Z))"):
        for offered, before in zip(parse_shorthand(suggestion.name).chains,
                                   written.chains):
            assert abs(offered.carbons - before.carbons) <= NAME_SEARCH_CARBONS


def test_the_written_name_is_never_offered_back():
    offered = names(647.5123, "[M+H]+", like="SM(d18:1/12:0)")
    assert offered            # its own neighbourhood does hold names
    assert "SM(d18:1/12:0)" not in offered


def test_a_name_that_is_not_shorthand_offers_nothing_from_a_class():
    assert names_for_mass(411.3054, "[M+H]+", like="cholic acid-d4") == []


def test_nothing_is_offered_without_an_adduct_to_put_a_formula_through():
    assert names_for_mass(886.6407, "", like="LacCER(d18:1/18:1(9Z))") == []
    assert names_for_mass(0.0, "[M+H]+", like="LacCER(d18:1/18:1(9Z))") == []


def test_a_mass_nothing_in_the_class_fits_offers_nothing():
    """
    One dalton above a real ceramide. Every move the search can make is an
    even number of nominal daltons — 14 for a chain, 2 for a double bond, 16
    for a hydroxyl — so half the integers are not reachable at all, which is
    the same arithmetic that leaves `LacCER(d18:0/18:1)` with nothing.
    """
    assert names_for_mass(538.5194, "[M+H]+", like="Cer(d18:1/16:0)")
    assert names_for_mass(539.5194, "[M+H]+", like="Cer(d18:1/16:0)") == []


def test_the_tolerance_is_the_caller_s_to_tighten():
    """
    The default is the nominal mass — see `NAME_MASS_TOLERANCE`. Asked for the
    precision the number was written to, the same search answers nothing,
    which is exactly why the default is not that.
    """
    assert names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))",
                          tolerance=0.0001) == []


# -- the ranking ---------------------------------------------------------------- #
def test_the_fewest_changes_come_first():
    offered = names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))")
    assert len(offered) > 4
    distances = [s.distance for s in offered]
    assert distances == sorted(distances)
    assert distances[0] == 1


def test_an_exact_match_outranks_a_nominal_one_at_the_same_distance():
    """
    `Cer(d18:1/16:0)` is 538.5194 through [M+H]+. Asked for that mass with
    `Cer(d18:1/17:0)` written down, the search offers both ways of moving one
    carbon — they are isomers and weigh the same to the ninth decimal, so the
    tie is broken on the name — and puts the hydroxyl swap that only matches
    the integer, 67 ppm out, after them.
    """
    offered = names_for_mass(538.5194, "[M+H]+", like="Cer(d18:1/17:0)")
    assert [s.name for s in offered[:2]] == ["Cer(d17:1/17:0)",
                                             "Cer(d18:1/16:0)"]
    assert all(abs(s.error_ppm) < 1.0 for s in offered[:2])
    nominal = [s for s in offered if abs(s.error_ppm) > 10]
    assert nominal and nominal[0].distance >= offered[0].distance
    for group in {(s.distance, s.changes) for s in offered}:
        errors = [abs(s.error_ppm) for s in offered
                  if (s.distance, s.changes) == group]
        assert errors == sorted(errors)


# -- what an offered name says about itself ------------------------------------- #
def test_an_offered_name_reads_back_as_the_formula_it_was_offered_with():
    """
    The proposal is a name, and a name is only worth offering if the software
    reads it the same way afterwards — it is about to be written into the
    method, where `fill_formulas` and the recalibration will read it again.
    """
    for suggestion in names_for_mass(886.6407, "[M+H]+",
                                     like="LacCER(d18:1/18:1(9Z))"):
        assert suggestion.formula in formulas_from_name(suggestion.name)
        mass = monoisotopic_mass(parse_formula(suggestion.formula))
        assert PROTON.mz(mass) == pytest.approx(suggestion.mz, abs=1e-9)


def test_a_hydroxylated_and_a_trihydroxy_base_are_written_so_they_read_back():
    """
    The two things the search varies besides the chains are the base's
    hydroxyls and an acyl hydroxyl, and both have to appear in the name or the
    formula that comes back would not be the one offered.
    """
    offered = names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))")
    written = [s.name for s in offered]
    assert any(name.startswith("LacCER(m") for name in written)
    assert any("/h" in name for name in written)
    for name in written:
        parsed = parse_shorthand(name)
        assert parsed is not None and parsed.formulas()


# -- the second list ------------------------------------------------------------ #
def fake_database():
    """Two records, one of them at the mass in question."""
    return LipidDatabase([
        LipidRecord(lm_id="LMGP02000001", name="PE 44:5", abbrev="PE 44:5",
                    formula="C49H88NO8P", exact_mass=885.6334),
        LipidRecord(lm_id="LMGP02000002", name="somewhere else",
                    abbrev="PC 30:0", formula="C38H76NO8P",
                    exact_mass=705.5309),
    ])


def test_the_database_answers_after_the_class_and_says_it_is_another_one():
    offered = names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))",
                             database=fake_database())
    assert [s.in_class for s in offered] == sorted(
        [s.in_class for s in offered], reverse=True)
    outside = [s for s in offered if not s.in_class]
    assert [s.name for s in outside] == ["PE 44:5"]
    assert outside[0].formula == "C49H88NO8P"
    assert outside[0].source == "LIPID MAPS LMGP02000001"


def test_the_database_is_asked_at_the_precision_the_mass_was_written_to():
    """
    A database name is judged on its mass and nothing else — there is no
    written name for it to be a correction of — so it does not get the nominal
    search the class gets. The other record is 180 Da away and never appears.
    """
    offered = names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))",
                             database=fake_database())
    assert "PC 30:0" not in [s.name for s in offered]
    outside = [s for s in offered if not s.in_class][0]
    assert abs(outside.error_ppm) < 1.0


def test_the_database_is_the_only_list_where_the_class_has_nothing():
    offered = names_for_mass(886.6407, "[M+H]+", like="not a lipid at all",
                             database=fake_database())
    assert [s.name for s in offered] == ["PE 44:5"]
    assert not offered[0].in_class


def test_a_callable_database_is_resolved_only_when_it_is_needed():
    asked = []

    def database():
        asked.append(True)
        return fake_database()

    assert names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))",
                          database=None)
    assert not asked
    assert names_for_mass(886.6407, "[M+H]+", like="LacCER(d18:1/18:1(9Z))",
                          database=database)
    assert asked == [True]


# -- the shape of a proposal ---------------------------------------------------- #
def test_a_name_written_without_brackets_is_not_offered_its_own_name_back():
    """
    `TG 52:2` and `TG(52:2)` are one name: the brackets are this module's way
    of writing a name back, not something it is proposing to change.
    """
    assert "TG(52:2)" not in names(859.7, "[M+H]+", like="TG 52:2")


def test_at_most_two_of_a_name_s_chains_are_ever_changed():
    """
    A name is wrong by a chain, not by all of them — and three chains each
    free over their own range is a product that took 13 seconds to walk.
    """
    written = parse_shorthand("TG(16:0/18:1/18:1)")
    offered = names_for_mass(859.7, "[M+H]+", like="TG(16:0/18:1/18:1)")
    assert offered
    for suggestion in offered:
        chains = parse_shorthand(suggestion.name).chains
        changed = sum(1 for a, b in zip(chains, written.chains)
                      if (a.carbons, a.double_bonds, a.prefix)
                      != (b.carbons, b.double_bonds, b.prefix))
        assert changed <= NAME_SEARCH_CHAINS


def test_a_three_chain_class_answers_as_fast_as_a_two_chain_one():
    """
    The mass is asked about the totals before the chains are split, which is
    what keeps this from being a product of three ranges. A second is a
    dialog that has stopped responding; this is measured in milliseconds.
    """
    start = time.perf_counter()
    names_for_mass(859.7, "[M+H]+", like="TG(16:0/18:1/18:1)")
    assert time.perf_counter() - start < 1.0
