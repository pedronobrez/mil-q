"""
Formulas read out of the names components already have.

The recalibration needs a lock mass, a lock mass needs a theoretical mass,
and a theoretical mass needs a formula — which the real method carries for
none of its 141 components while naming 125 of them in a shorthand that says
exactly what they are made of. Everything here is arithmetic on that name,
and every derivation is checked against the precursor the method already
wrote down: a formula that disagrees with it is thrown away, because a wrong
lock mass is worse than no lock mass.
"""

import pytest

from milq.chemistry import (ADDUCTS_BY_NAME, formula_from_name,
                                 formulas_from_name, monoisotopic_mass,
                                 parse_formula)
from milq.components import (Component, fill_formulas, propose_formula,
                                  written_tolerance)


def mz(formula: str, adduct: str = "[M+H]+") -> float:
    return ADDUCTS_BY_NAME[adduct].mz(monoisotopic_mass(parse_formula(formula)))


# --- the shorthand ---------------------------------------------------------- #
@pytest.mark.parametrize("name, formula, protonated", [
    ("SM(d18:1/12:0)", "C35H71N2O6P", 647.5123),
    ("Cer(d18:1/16:0)", "C34H67NO3", 538.5194),
    ("PC 34:1", "C42H82NO8P", 760.5851),
    ("LPC 18:0", "C26H54NO7P", 524.3711),
    ("TG 52:2", "C55H102O6", 859.7749),
    ("FA 18:1", "C18H34O2", 283.2632),
    ("PE 34:1", "C39H76NO8P", 718.5381),
    ("PS 34:1", "C40H76NO10P", 762.5280),
    ("PG 34:1", "C40H77O10P", 749.5327),
    ("PI 34:1", "C43H81O13P", 837.5488),
    ("DG 34:1", "C37H70O5", 595.5296),
    ("MG 18:1", "C21H40O4", 357.2999),
    ("CE 18:1", "C45H78O2", 651.6075),
    ("LPE 18:0", "C23H48NO7P", 482.3241),
])
def test_the_standard_shorthand(name, formula, protonated):
    assert formula_from_name(name) == formula
    assert mz(formula) == pytest.approx(protonated, abs=5e-4)


def test_a_hydroxyl_is_an_oxygen_however_it_is_written():
    assert formula_from_name("Cer(d18:1/24:0)") == "C42H83NO3"
    assert formula_from_name("Cer(d18:1/h24:0)") == "C42H83NO4"
    assert formula_from_name("Cer(d18:1/24:0)(2OH)") == "C42H83NO4"
    # the 2 of `2OH` is where the hydroxyl sits, not how many there are
    assert formula_from_name("Cer(d18:1/24:0)(2OH)") != "C42H83NO5"


def test_the_base_prefix_moves_the_oxygens_and_nothing_else():
    assert formula_from_name("Cer(d18:0/16:0)") == "C34H69NO3"
    assert formula_from_name("Cer(t18:0/16:0)") == "C34H69NO4"
    assert formula_from_name("Cer(m18:0/16:0)") == "C34H69NO2"
    #: LIPID MAPS writes the same thing as `;O2`
    assert formula_from_name("Cer 34:0;O3") == "C34H69NO4"


def test_a_double_bond_position_says_nothing_about_the_composition():
    assert (formula_from_name("Cer(d18:1/24:1(15Z))")
            == formula_from_name("Cer(d18:1/24:1)"))


def test_the_class_may_come_after_the_chain():
    assert formula_from_name("C16:0-Ceramide") == formula_from_name("Cer(d18:1/16:0)")
    assert formula_from_name("C14_SM") == formula_from_name("SM(d18:1/14:0)")
    # 24 carbons could be the whole species, so that reading comes first and
    # the method's — an acyl on an unwritten base — comes second
    assert (formulas_from_name("C24:1_HexCer")[1]
            == formula_from_name("HexCer(d18:1/24:1)"))


def test_the_longest_class_name_wins():
    # `LacCer` is not `Cer`, and `Sphinganine1P` is not `Sphinganine` and a 1
    assert formula_from_name("LacCER(d18:1/12:0)") == "C42H79NO13"
    assert formula_from_name("C20 Sphinganine1P") == "C20H44NO5P"
    assert formula_from_name("C12_Galactosyl_Ceramide") == "C36H69NO8"


def test_the_word_carries_the_base_double_bond():
    # sphingosine has one and sphinganine has none, whatever the `:0` says
    assert formula_from_name("Sphingosine C17:0") == "C17H35NO2"
    assert formula_from_name("Sphinganine C17:0") == "C17H37NO2"
    assert formula_from_name("C22:1 Sph") == "C22H45NO2"


def test_one_chain_for_a_two_chain_class_has_two_readings():
    # `SM 34:1` is the whole species; `C14_SM` is the acyl and an unwritten
    # d18:1 base. Both are arithmetic, only the precursor can choose.
    readings = formulas_from_name("SM 34:1")
    assert readings == ["C39H79N2O6P", "C57H113N2O6P"]
    assert mz(readings[0]) == pytest.approx(703.5749, abs=5e-4)
    # 14 carbons cannot be a whole sphingolipid, so only one reading stands
    assert formulas_from_name("SM 14:0") == ["C37H75N2O6P"]


@pytest.mark.parametrize("name", [
    "Cer(d18:1/16:0)-d7", "Cer(d18:1/16:0)d7", "Cer(d18:1/16:0)(d7)",
    "Cer(d18:1/16:0)-D7",
])
def test_deuterium_is_counted_however_it_is_suffixed(name):
    assert formula_from_name(name) == "C34H60D7NO3"


def test_deuterium_does_not_eat_the_sphingoid_base():
    assert formula_from_name("SM(d18:1/12:0)") == "C35H71N2O6P"
    assert formula_from_name("SM(d18:1/12:0)-d9") == "C35H62D9N2O6P"
    assert formula_from_name("Cer(d18:1/16:0)-d4") == "C34H63D4NO3"


def test_labels_shift_the_mass_by_the_neutron_difference():
    plain = monoisotopic_mass(parse_formula(formula_from_name("PC 34:1")))
    labelled = monoisotopic_mass(parse_formula(formula_from_name("PC 34:1-d9")))
    assert labelled - plain == pytest.approx(9 * 1.00628, abs=1e-3)


@pytest.mark.parametrize("name", [
    "", None, "Cholic acid", "unknown 4", "blank", "371.2 -> 264.3",
    "Cer", "PC", "PC 0:0", "PC 400:1",
])
def test_nothing_is_invented(name):
    assert formula_from_name(name) is None


# --- the check against the written precursor -------------------------------- #
def test_a_formula_is_kept_only_where_the_precursor_agrees():
    right = Component(name="SM(d18:1/12:0)", precursor=647.5, adduct="[M+H]+")
    wrong = Component(name="SM(d18:1/12:0)", precursor=645.5, adduct="[M+H]+")
    assert propose_formula(right).agrees
    proposal = propose_formula(wrong)
    assert not proposal.agrees
    assert "647.5123" in proposal.reason and "645.5" in proposal.reason


def test_the_tolerance_is_the_last_decimal_written():
    # a precursor typed to one decimal is good to a tenth; to four decimals,
    # to a ten-thousandth
    assert written_tolerance(647.5) == pytest.approx(0.1)
    assert written_tolerance(806.5624) == pytest.approx(1e-4)
    #: this method truncates rather than rounds — 286.2 for 286.2741 — so
    #: half a unit in the last place would refuse the compound over the way
    #: its own precursor was typed
    loose = Component(name="Sphingosine C17:0", precursor=286.2, adduct="[M+H]+")
    proposal = propose_formula(loose)
    assert proposal.agrees and abs(proposal.difference) > written_tolerance(286.2) / 2


def test_a_formula_needs_an_adduct_to_be_checked_at_all():
    naked = Component(name="SM(d18:1/12:0)", precursor=647.5)
    proposal = propose_formula(naked)
    assert proposal.theoretical is None and not proposal.agrees
    assert "no adduct" in proposal.reason
    assert fill_formulas([naked]).refused == [proposal] or not naked.formula


def test_the_nearest_reading_is_the_one_reported():
    # both readings of `C25:0-Ceramide` are refused; the one shown is the
    # near miss, not whichever came first
    component = Component(name="C25:0-Ceramide", precursor=664.4, adduct="[M+H]+")
    proposal = propose_formula(component)
    assert not proposal.agrees
    assert proposal.formula == "C43H85NO3"
    assert abs(proposal.difference) == pytest.approx(0.2602, abs=1e-3)


# --- filling a table -------------------------------------------------------- #
def _table():
    return [
        Component(name="SM(d18:1/12:0)", precursor=647.5, adduct="[M+H]+"),
        Component(name="C16:0-Ceramide", precursor=538.5, adduct="[M+H]+"),
        Component(name="Peak 3", precursor=413.2, adduct="[M+H]+"),
        Component(name="C25:0-Ceramide", precursor=664.4, adduct="[M+H]+"),
        Component(name="Mine", precursor=500.0, adduct="[M+H]+", formula="C30H61NO3"),
    ]


def test_fill_writes_only_the_empty_cells():
    components = _table()
    fill = fill_formulas(components)
    assert [c.formula for c in components] == [
        "C35H71N2O6P", "C34H67NO3", "", "", "C30H61NO3"]
    assert len(fill.filled) == 2
    assert [p.component.name for p in fill.refused] == ["C25:0-Ceramide"]
    assert [c.name for c in fill.underived] == ["Peak 3"]
    assert [c.name for c in fill.kept] == ["Mine"]
    assert fill.missing == 2


def test_a_typed_formula_is_never_overwritten_even_when_it_disagrees():
    # the disagreement is `check_method`'s finding to report, not this one's
    # to correct: only the person who typed it knows which of the two is wrong
    mine = Component(name="SM(d18:1/12:0)", precursor=647.5, adduct="[M+H]+",
                     formula="C35H70N2O6P")
    fill_formulas([mine])
    assert mine.formula == "C35H70N2O6P"


def test_filling_moves_nothing_but_the_formula():
    components = _table()
    before = [(c.name, c.precursor, c.fragment, c.rt, c.adduct, c.tolerance)
              for c in components]
    fill_formulas(components)
    after = [(c.name, c.precursor, c.fragment, c.rt, c.adduct, c.tolerance)
             for c in components]
    assert before == after


def test_filling_twice_changes_nothing_the_second_time():
    components = _table()
    fill_formulas(components)
    again = fill_formulas(components)
    assert not again.filled and len(again.kept) == 3


def test_the_summary_says_what_did_not_happen():
    summary = fill_formulas(_table()).summary()
    assert "2 formula(s) filled in" in summary
    assert "1 refused" in summary and "1 not derivable" in summary
