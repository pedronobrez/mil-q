"""Tests for formula parsing, exact masses, isotope patterns and the finder."""

import numpy as np
import pytest

from milq import chemistry as ch


# --- parsing --------------------------------------------------------------- #
def test_parse_simple_formula():
    assert ch.parse_formula("C18H32O3") == {"C": 18, "H": 32, "O": 3}


def test_parse_single_atoms_and_two_letter_elements():
    assert ch.parse_formula("CHNOPSCl") == {
        "C": 1, "H": 1, "N": 1, "O": 1, "P": 1, "S": 1, "Cl": 1
    }


def test_parse_nested_groups():
    assert ch.parse_formula("C6H4(NO2)2") == {"C": 6, "H": 4, "N": 2, "O": 4}
    assert ch.parse_formula("((CH2)2O)3") == {"C": 6, "H": 12, "O": 3}


def test_parse_repeated_element_accumulates():
    assert ch.parse_formula("CH3CH2OH") == {"C": 2, "H": 6, "O": 1}


def test_parse_deuterium_and_bracketed_isotopes():
    assert ch.parse_formula("C18H28D4O3") == {"C": 18, "H": 28, "D": 4, "O": 3}
    counts = ch.parse_formula("[13C]2C16H32O3")
    assert counts["[13C]"] == 2 and counts["C"] == 16


def test_parse_rejects_unknown_element():
    with pytest.raises(ch.FormulaError, match="unknown element"):
        ch.parse_formula("C6Xx2")


def test_parse_rejects_unbalanced_parentheses():
    with pytest.raises(ch.FormulaError, match="parentheses"):
        ch.parse_formula("C6H4(NO2")


def test_parse_empty_is_empty():
    assert ch.parse_formula("   ") == {}


def test_format_formula_uses_hill_order():
    assert ch.format_formula({"O": 3, "H": 32, "C": 18}) == "C18H32O3"
    assert ch.format_formula({"H": 1, "Cl": 1}) == "HCl"


# --- masses ----------------------------------------------------------------- #
def test_monoisotopic_mass_of_dihome():
    # 12,13-DiHOME, C18H34O4
    mass = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    assert mass == pytest.approx(314.245709, abs=5e-5)


def test_deprotonated_dihome_matches_the_measured_precursor():
    neutral = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    mz = ch.ADDUCTS_BY_NAME["[M-H]-"].mz(neutral)
    assert mz == pytest.approx(313.2384, abs=1e-3)


def test_average_mass_is_above_monoisotopic():
    counts = ch.parse_formula("C18H34O4")
    assert ch.average_mass(counts) > ch.monoisotopic_mass(counts)
    assert ch.average_mass(counts) == pytest.approx(314.46, abs=0.05)


def test_adduct_round_trip():
    adduct = ch.ADDUCTS_BY_NAME["[M+Na]+"]
    assert adduct.neutral_mass(adduct.mz(500.0)) == pytest.approx(500.0)


def test_doubly_charged_adduct_halves_the_mz():
    single = ch.ADDUCTS_BY_NAME["[M+H]+"].mz(500.0)
    double = ch.ADDUCTS_BY_NAME["[M+2H]2+"].mz(500.0)
    assert double < single / 2 + 1.0


def test_rdbe_of_benzene_is_four():
    assert ch.rdbe(ch.parse_formula("C6H6")) == pytest.approx(4.0)


def test_rdbe_of_a_saturated_fatty_acid_is_one():
    assert ch.rdbe(ch.parse_formula("C18H36O2")) == pytest.approx(1.0)


def test_mass_errors():
    assert ch.mass_error_ppm(313.2394, 313.2384) == pytest.approx(3.19, abs=0.05)
    assert ch.mass_error_mda(313.2394, 313.2384) == pytest.approx(1.0, abs=1e-6)


# --- isotope patterns -------------------------------------------------------- #
def test_isotope_pattern_base_peak_is_first_and_normalised():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"))
    assert pattern[0][1] == pytest.approx(1.0)
    assert all(abundance <= 1.0 for _mz, abundance in pattern)
    assert np.all(np.diff([mz for mz, _a in pattern]) > 0)


def test_carbon_13_satellite_scales_with_carbon_count():
    small = ch.isotope_pattern(ch.parse_formula("C10H22"))
    large = ch.isotope_pattern(ch.parse_formula("C40H82"))
    assert large[1][1] > small[1][1]
    # roughly 1.1% per carbon
    assert small[1][1] == pytest.approx(0.11, abs=0.02)


def test_chlorine_gives_the_expected_m2_ratio():
    pattern = ch.isotope_pattern(ch.parse_formula("C6H5Cl"), min_abundance=0.01)
    m2 = [a for mz, a in pattern if mz > pattern[0][0] + 1.5]
    assert m2 and m2[0] == pytest.approx(0.32, abs=0.03)


def test_isotope_pattern_applies_the_adduct():
    counts = ch.parse_formula("C18H34O4")
    neutral = ch.isotope_pattern(counts)
    ionised = ch.isotope_pattern(counts, ch.ADDUCTS_BY_NAME["[M-H]-"])
    assert ionised[0][0] == pytest.approx(neutral[0][0] - ch.PROTON_MASS)


def test_isotope_pattern_of_empty_formula():
    assert ch.isotope_pattern({}) == []


def test_match_isotope_pattern_perfect_and_absent():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"),
                                 ch.ADDUCTS_BY_NAME["[M-H]-"], max_peaks=3)
    mz = np.array([p[0] for p in pattern])
    intensity = np.array([p[1] for p in pattern]) * 1000.0
    assert ch.match_isotope_pattern(mz, intensity, pattern) == pytest.approx(1.0, abs=0.02)
    empty = np.zeros(0)
    assert ch.match_isotope_pattern(empty, empty, pattern) == 0.0


# --- formula finder ----------------------------------------------------------- #
def test_finder_recovers_dihome():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=5, unit="ppm")
    assert "C18H34O4" in [hit.formula for hit in hits]
    assert abs(hits[0].error_ppm) < 5


def test_finder_respects_the_tolerance():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    tight = ch.find_formulas(target, tolerance=1, unit="ppm")
    loose = ch.find_formulas(target, tolerance=50, unit="ppm")
    assert len(loose) > len(tight)
    assert all(abs(hit.error_ppm) <= 1.001 for hit in tight)


def test_finder_accepts_millidalton_tolerance():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=0.003, unit="Da")
    assert all(abs(hit.error_mda) <= 3.001 for hit in hits)


def test_finder_honours_element_ranges():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=20, unit="ppm",
                            ranges={"C": (0, 60), "H": (0, 120), "O": (0, 12)})
    assert all(set(hit.counts) <= {"C", "H", "O"} for hit in hits)


def test_finder_drops_odd_electron_formulas_by_default():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=30, unit="ppm")
    assert all(abs(hit.rdbe - round(hit.rdbe)) < 1e-9 for hit in hits)


def test_golden_rules_shrink_the_candidate_list():
    target = 400.0
    with_rules = ch.find_formulas(target, 20, "ppm", golden_rules=True)
    without = ch.find_formulas(target, 20, "ppm", golden_rules=False)
    assert len(with_rules) < len(without)


def test_finder_returns_nothing_for_impossible_mass():
    assert ch.find_formulas(0.5, 5, "ppm") == []


def test_isotope_ranking_prefers_the_right_carbon_count():
    truth = ch.parse_formula("C18H34O4")
    adduct = ch.ADDUCTS_BY_NAME["[M-H]-"]
    pattern = ch.isotope_pattern(truth, adduct, min_abundance=0.005, max_peaks=4)
    mz = np.array([p[0] for p in pattern])
    intensity = np.array([p[1] for p in pattern]) * 5000.0

    hits = ch.find_formulas(adduct.neutral_mass(float(mz[0])), 30, "ppm")
    ranked = ch.rank_by_isotope_pattern(hits, mz, intensity, adduct)
    assert ranked[0].formula == "C18H34O4"
    assert ranked[0].isotope_score > 0.9


# --- isotope scoring is built from the satellites ---------------------------- #
def _measured(pattern, scale=1000.0, factors=None):
    """Turn a theoretical pattern into a fake measured spectrum."""
    factors = factors or [1.0] * len(pattern)
    mz = np.array([p[0] for p in pattern])
    intensity = np.array([p[1] * f for p, f in zip(pattern, factors)]) * scale
    return mz, intensity


def test_score_is_zero_when_the_satellites_are_missing():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"),
                                 ch.ADDUCTS_BY_NAME["[M-H]-"], max_peaks=3)
    mz, intensity = _measured(pattern, factors=[1.0, 0.0, 0.0])
    assert ch.match_isotope_pattern(mz, intensity, pattern) == pytest.approx(0.0)


def test_score_falls_as_the_satellite_drifts():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"),
                                 ch.ADDUCTS_BY_NAME["[M-H]-"], max_peaks=2)
    exact = ch.match_isotope_pattern(*_measured(pattern), pattern)
    off_10 = ch.match_isotope_pattern(*_measured(pattern, factors=[1.0, 1.1]), pattern)
    off_50 = ch.match_isotope_pattern(*_measured(pattern, factors=[1.0, 1.5]), pattern)
    assert exact > off_10 > off_50
    assert exact == pytest.approx(1.0, abs=0.01)


def test_score_separates_carbon_counts():
    """A C40 pattern must not score well against C10 data, and vice versa."""
    adduct = ch.ADDUCTS_BY_NAME["[M+H]+"]
    small = ch.isotope_pattern(ch.parse_formula("C10H22"), adduct, max_peaks=3)
    large = ch.isotope_pattern(ch.parse_formula("C40H82"), adduct, max_peaks=3)
    mz, intensity = _measured(small)
    # compare the large-molecule pattern against small-molecule data, at the
    # same masses, so only the satellite ratios differ
    shifted = [(m, a) for (m, _), (_, a) in zip(small, large)]
    assert ch.match_isotope_pattern(mz, intensity, small) > 0.95
    assert ch.match_isotope_pattern(mz, intensity, shifted) < 0.6


def test_single_peak_pattern_cannot_be_scored():
    assert ch.match_isotope_pattern(np.array([100.0]), np.array([10.0]),
                                    [(100.0, 1.0)]) == 0.0


def test_satellites_detected_when_present():
    mz = np.array([325.1853, 326.1886, 327.1920])
    intensity = np.array([39400.0, 9486.0, 5138.0])
    assert ch.has_isotope_satellites(mz, intensity, 325.1853)


def test_satellites_absent_in_an_isolated_precursor():
    # what a product-ion scan looks like: Q1 kept only the monoisotopic peak
    mz = np.array([325.1860, 326.1890])
    intensity = np.array([17694.0, 9.0])
    assert not ch.has_isotope_satellites(mz, intensity, 325.1860)


def test_satellites_use_the_charge_spacing():
    mz = np.array([325.0, 325.5017])
    intensity = np.array([1000.0, 200.0])
    assert ch.has_isotope_satellites(mz, intensity, 325.0, charge=2)
    assert not ch.has_isotope_satellites(mz, intensity, 325.0, charge=1)


def test_satellites_on_empty_spectrum():
    empty = np.zeros(0)
    assert not ch.has_isotope_satellites(empty, empty, 300.0)


# --- adducts as other people write them ------------------------------------ #
def test_an_adduct_is_read_however_its_author_spelt_it():
    for written in ("[M+H]+", "[M+H]1+", " m+h ", "M+H"):
        assert ch.adduct_from_name(written) is ch.ADDUCTS_BY_NAME["[M+H]+"]
    assert ch.adduct_from_name("[M+FA-H]-") is ch.ADDUCTS_BY_NAME["[M+HCOO]-"]
    assert ch.adduct_from_name("[M+OAc]-") is ch.ADDUCTS_BY_NAME["[M+CH3COO]-"]
    assert ch.adduct_from_name("[M-2H]2-") is ch.ADDUCTS_BY_NAME["[M-2H]2-"]
    # not an adduct we model, not the neutral entry, and not a contradiction
    assert ch.adduct_from_name("[M]+") is None
    assert ch.adduct_from_name(ch.NEUTRAL) is None
    assert ch.adduct_from_name("[M+H]-") is None
    assert ch.adduct_from_name("") is None


def test_the_polarity_is_read_from_the_name_even_when_the_adduct_is_not():
    assert ch.polarity_sign("[M+2Na-H]+") == 1
    assert ch.polarity_sign("[M+HCOOH-H]-") == -1
    assert ch.polarity_sign("[M-2H]2-") == -1
    assert ch.polarity_sign("Positive") == 1 and ch.polarity_sign("NEG") == -1
    assert ch.polarity_sign(1) == 1 and ch.polarity_sign(-2) == -1
    for nothing in (None, "", "M+H", "unknown", 0):
        assert ch.polarity_sign(nothing) is None


def test_a_formula_and_an_adduct_give_the_mass_the_ion_has():
    assert ch.mass_from_formula("C24H36D4O5", "[M+NH4]+") == pytest.approx(
        430.34651, abs=1e-4)
    assert ch.mass_from_formula("C39H79N2O6P", "[M+H]+") == pytest.approx(
        703.57485, abs=1e-4)
    assert ch.mass_from_formula("", "[M+H]+") is None
    assert ch.mass_from_formula("C24H36D4O5", "") is None
    assert ch.mass_from_formula("not a formula", "[M+H]+") is None


# --- what an adduct does when the ion breaks up ---------------------------- #
def test_an_adduct_says_what_its_fragments_carry():
    """The rule the module docstring states, as four cases. A proton stays
    on the piece; ammonia leaves and hands over a proton; sodium is a
    coordinate bond and may go either way, so both are offered."""
    proton = ch.ADDUCTS_BY_NAME["[M+H]+"]
    ammonium = ch.ADDUCTS_BY_NAME["[M+NH4]+"]
    sodium = ch.ADDUCTS_BY_NAME["[M+Na]+"]
    formate = ch.ADDUCTS_BY_NAME["[M+HCOO]-"]

    assert proton.behaviour == ch.PROTON
    assert ammonium.behaviour == ch.LABILE and ammonium.leaves == "NH3"
    assert sodium.behaviour == ch.METAL and sodium.carrier == "Na"
    assert formate.behaviour == ch.LABILE and formate.leaves == "HCOOH"

    assert ch.fragment_adducts(proton) == (proton,)
    assert ch.fragment_adducts(ammonium) == (proton,)
    assert ch.fragment_adducts(sodium) == (sodium, proton)
    # a formate adduct is negative, so its pieces are deprotonated
    assert ch.fragment_adducts(formate) == (ch.ADDUCTS_BY_NAME["[M-H]-"],)
    assert ch.core_adduct(ammonium) is proton
    assert ch.core_adduct(sodium) is sodium


def test_a_doubly_charged_precursor_gives_singly_charged_pieces():
    assert ch.fragment_adducts(ch.ADDUCTS_BY_NAME["[M+2H]2+"]) == (
        ch.ADDUCTS_BY_NAME["[M+H]+"],)
    assert ch.fragment_adducts(ch.ADDUCTS_BY_NAME["[M-2H]2-"]) == (
        ch.ADDUCTS_BY_NAME["[M-H]-"],)


# --- which adduct a written precursor is ----------------------------------- #
def test_a_written_precursor_names_its_adduct_and_says_how_far_off():
    """The real case: a ZenoTOF channel written 430.35 for cholic acid-d4.
    It is the ammonium adduct and nothing else, and the sentence has to
    carry the number the analyst expected instead."""
    choice = ch.identify_adduct("C24H36D4O5", 430.35, "Positive")

    assert choice.adduct is ch.ADDUCTS_BY_NAME["[M+NH4]+"]
    assert "430.35 is [M+NH4]+ of C24H36D4O5" in choice.reason
    assert "430.3465" in choice.reason and "+8.1 ppm" in choice.reason
    assert "[M+H]+ would be 413.3200" in choice.reason
    assert bool(choice)


def test_a_precursor_the_method_rounded_its_own_way_still_matches():
    """The same compound is written 430.35 in one file and 430.34 in
    another, and DCA-d4's 414.34 is 0.0117 from its true 414.3516 - the
    worst of the nine infusions and what ADDUCT_MATCH_DA was set from."""
    assert ch.identify_adduct("C24H36D4O5", 430.34, "Positive").adduct \
        is ch.ADDUCTS_BY_NAME["[M+NH4]+"]
    choice = ch.identify_adduct("C24H36D4O4", 414.34, "Positive")
    assert choice.adduct is ch.ADDUCTS_BY_NAME["[M+NH4]+"]
    assert "-28.0 ppm" in choice.reason
    assert abs(choice.matches[0].error_da) < ch.ADDUCT_MATCH_DA


def test_a_precursor_no_adduct_reaches_is_refused_with_the_closest_named():
    choice = ch.identify_adduct("C24H40O5", 430.35, "Positive")

    assert choice.adduct is None and not choice
    assert "none of the adducts of C24H40O5" in choice.reason
    assert "[M+Na]+ at 431.2768" in choice.reason


def test_a_positive_channel_is_never_offered_a_negative_adduct():
    names = {m.name for m in ch.adducts_matching("C24H40O5", 409.29, "Positive")}
    assert names and all("+" in name for name in names)
    negative = {m.name for m in ch.adducts_matching("C24H40O5", 407.28, "N")}
    assert negative and all(name.endswith("-") for name in negative)
    # with no polarity given, both signs are candidates
    both = {m.name for m in ch.adducts_matching("C24H40O5", 407.28)}
    assert "[M-H]-" in both and "[M+H]+" in both
    assert ch.NEUTRAL not in both


def test_a_precursor_written_to_one_decimal_widens_its_own_window():
    """`703.6` is known to +/-0.05, and an adduct cannot be asked to fit
    closer than the number was written."""
    inside = ch.adducts_matching("C39H79N2O6P", 703.6, None)
    assert [m for m in inside if m.name == "[M+H]+"][0].within


# --- standards bought by their trivial names ------------------------------- #
def test_a_label_suffix_is_read_off_the_end_of_a_name_and_nowhere_else():
    assert ch.split_labels("cholic acid-d4") == ("cholic acid", 4)
    assert ch.split_labels("TDCA-d4") == ("TDCA", 4)
    assert ch.split_labels("Cholic acid (d4)") == ("Cholic acid", 4)
    assert ch.split_labels("cholic acid_d5") == ("cholic acid", 5)
    # the d of a sphingoid base, and the d of DCA, are not label counts
    assert ch.split_labels("SM(d18:1/16:0)") == ("SM(d18:1/16:0)", 0)
    assert ch.split_labels("DCA") == ("DCA", 0)


def test_the_standards_table_answers_to_the_bottle_and_to_the_name():
    assert ch.standard_named("TDCA") == ("C26H45NO6S", "Taurodeoxycholic acid")
    assert ch.standard_named("taurodeoxycholic acid")[0] == "C26H45NO6S"
    assert ch.standard_named("Cholic Acid")[0] == "C24H40O5"
    assert ch.standard_named("cholic")[0] == "C24H40O5"
    assert ch.standard_named("cortisol") is None
    assert ch.standard_named("") is None


def test_every_standard_in_the_table_weighs_what_the_bottle_says():
    """The formulas are the fallback for a machine with no LMSD, so they
    have to be right on their own. Glycine conjugation adds C2H3NO to the
    acid and taurine C2H5NO2S, which is the arithmetic to check."""
    acid = ch.monoisotopic_mass(ch.parse_formula(ch.STANDARDS["cholic acid"][0]))
    glyco = ch.monoisotopic_mass(
        ch.parse_formula(ch.STANDARDS["glycocholic acid"][0]))
    tauro = ch.monoisotopic_mass(
        ch.parse_formula(ch.STANDARDS["taurocholic acid"][0]))
    assert acid == pytest.approx(408.2876, abs=1e-3)
    assert glyco - acid == pytest.approx(
        ch.monoisotopic_mass(ch.parse_formula("C2H3NO")), abs=1e-6)
    assert tauro - acid == pytest.approx(
        ch.monoisotopic_mass(ch.parse_formula("C2H5NO2S")), abs=1e-6)
    for name, (formula, lm_name) in ch.STANDARDS.items():
        assert ch.parse_formula(formula) and lm_name
        assert name == name.lower()
    for alias, name in ch.STANDARD_ALIASES.items():
        assert name in ch.STANDARDS, alias


# --- what the survey says about the adduct --------------------------------- #
def _survey(peaks, width: float = 0.012, step: float = 0.002,
            pad: float = 1.5):
    """A profile spectrum from (m/z, height) sticks."""
    lo = min(m for m, _h in peaks) - pad
    hi = max(m for m, _h in peaks) + pad
    mz = np.arange(lo, hi, step)
    intensity = np.zeros_like(mz)
    for centre, height in peaks:
        intensity += height * np.exp(-0.5 * ((mz - centre) / width) ** 2)
    return mz, intensity


def _ladder(formula: str, adduct: str, height: float, peaks: int = 4):
    """One ion's isotope ladder as sticks, at the given base height."""
    return [(mz, height * abundance) for mz, abundance
            in ch.ion_pattern(formula, ch.ADDUCTS_BY_NAME[adduct],
                              max_peaks=peaks)]


def test_an_ions_pattern_carries_the_adducts_own_atoms():
    """An adduct is not an offset here either. The ammonium's nitrogen and
    four hydrogens are in the M+1, and a chloride's M+2 is a third of its M
    where the molecule alone has none of that."""
    ammonium = ch.ion_pattern("C24H40O5", ch.ADDUCTS_BY_NAME["[M+NH4]+"])
    plain = ch.ion_pattern("C24H40O5", ch.ADDUCTS_BY_NAME["[M+H]+"])
    assert ammonium[0][0] == pytest.approx(426.3214, abs=1e-3)
    assert ammonium[0][1] == 1.0 and plain[0][1] == 1.0
    # one nitrogen is 0.37% of an M+1, and four hydrogens another 0.05%
    assert ammonium[1][1] > plain[1][1]
    assert ammonium[1][1] - plain[1][1] == pytest.approx(0.0042, abs=0.001)

    chloride = ch.ion_pattern("C24H40O5", ch.ADDUCTS_BY_NAME["[M+Cl]-"])
    # 37Cl is 32% of 35Cl, and the molecule adds its own 3% on top
    assert chloride[2][1] == pytest.approx(0.363, abs=0.01)
    assert ch.ion_composition(ch.parse_formula("C24H40O5"),
                              ch.ADDUCTS_BY_NAME["[M+Cl]-"])["Cl"] == 1
    # a deprotonated molecule loses the hydrogen from the composition too
    assert ch.ion_composition(ch.parse_formula("C24H40O5"),
                              ch.ADDUCTS_BY_NAME["[M-H]-"])["H"] == 39
    assert ch.ion_composition({"C": 1}, ch.ADDUCTS_BY_NAME["[M-H]-"]) is None


def test_a_doubly_charged_ion_has_its_satellites_half_a_dalton_apart():
    pattern = ch.ion_pattern("C39H79N2O6P", ch.ADDUCTS_BY_NAME["[M+2H]2+"])
    assert pattern[1][0] - pattern[0][0] == pytest.approx(
        ch.NEUTRON_SPACING / 2, abs=1e-4)


def test_the_survey_reports_every_candidate_and_maps_the_ones_it_shows():
    """A survey holding [M+H]+ and [M+Na]+ of the same molecule, which is
    the ordinary case in positive infusion. Both are reported with their
    relative heights; the adducts that are not there say what was looked
    for and that nothing was."""
    formula = "C24H40O5"
    mz, intensity = _survey(_ladder(formula, "[M+H]+", 100_000)
                            + _ladder(formula, "[M+Na]+", 40_000))
    evidence = ch.adduct_evidence(mz, intensity, formula, polarity="Positive")
    by_name = {e.name: e for e in evidence}

    assert [e.name for e in evidence][:2] == ["[M+H]+", "[M+Na]+"]
    assert by_name["[M+H]+"].present and by_name["[M+Na]+"].present
    assert by_name["[M+H]+"].relative == pytest.approx(1.0, abs=0.01)
    assert by_name["[M+Na]+"].relative == pytest.approx(0.40, abs=0.01)
    assert abs(by_name["[M+H]+"].error_ppm) < 1.0
    assert by_name["[M+H]+"].pattern > 0.95 and by_name["[M+H]+"].agrees
    assert ch.adduct_map(evidence) == "[M+H]+ 100%, [M+Na]+ 40%"

    absent = by_name["[M+K]+"]
    assert not absent.present and absent.score == 0.0
    assert "nothing within" in absent.note
    assert absent.name in absent.sentence and "not found" not in absent.sentence
    # a negative adduct is never a candidate for a positive channel
    assert "[M-H]-" not in by_name


def test_only_the_isotope_pattern_separates_two_masses_one_dalton_apart():
    """A d4 standard and its d3 impurity are 1.0063 Da apart, and the
    impurity's M+1 lands on the standard's M. Both fit the mass to within
    a ppm; only the pattern says which of them the peak belongs to."""
    d4, d3 = "C24H36D4O5", "C24H37D3O5"
    assert ch.mass_from_formula(d4, "[M+NH4]+") \
        - ch.mass_from_formula(d3, "[M+NH4]+") == pytest.approx(1.0063, abs=1e-3)
    mz, intensity = _survey(_ladder(d4, "[M+NH4]+", 100_000)
                            + _ladder(d3, "[M+NH4]+", 25_000))

    right = ch.adduct_evidence(mz, intensity, d4, candidates=["[M+NH4]+"])[0]
    wrong = ch.adduct_evidence(mz, intensity, d3, candidates=["[M+NH4]+"])[0]

    # the mass cannot choose: both are on their ion to within a ppm
    assert abs(right.error_ppm) < 1.0 and abs(wrong.error_ppm) < 1.0
    # the pattern can: the d3 ion would need an M+1 of 0.27 and has 4.3,
    # because what sits there is the d4 standard itself
    assert right.pattern > 0.9 and right.agrees
    assert wrong.pattern < 0.2 and not wrong.agrees
    assert wrong.measured[1] > 4.0
    assert right.score > wrong.score
    assert "the isotopes disagree" in wrong.sentence


def test_a_satellite_sitting_on_a_neighbour_does_not_sink_the_whole_pattern():
    """Measured on the sphingolipid batch: the C16 ceramide's own [M+H]+
    has an M+2 four times too big, because the co-eluting dihydroceramide
    is 17 ppm from it. Summing the satellites' errors calls the compound's
    own adduct a disagreement; weighting them per satellite does not."""
    measured = (1.0, 0.333, 0.289)
    expected = (1.0, 0.380, 0.076)
    assert ch.pattern_agreement(measured, expected) == pytest.approx(0.77,
                                                                     abs=0.02)
    # and it still rejects a pattern that is not one at all
    assert ch.pattern_agreement((1.0, 1.0, 1.0), expected) < 0.4
    assert ch.pattern_agreement((1.0,), expected) is None


def test_a_survey_confirms_the_adduct_the_written_precursor_names():
    formula = "C24H36D4O5"
    survey = _survey(_ladder(formula, "[M+NH4]+", 100_000)
                     + _ladder(formula, "[M+Na]+", 20_000))
    choice = ch.identify_adduct(formula, 430.35, "Positive", survey=survey)

    assert choice.adduct is ch.ADDUCTS_BY_NAME["[M+NH4]+"]
    assert choice.confirmed and choice.read_survey
    assert "430.35 is [M+NH4]+ of C24H36D4O5" in choice.reason
    assert "confirmed by the survey: 430.346" in choice.reason
    assert "isotopes agree" in choice.reason
    # the other adduct of the same molecule is reported, not hidden
    assert "the survey also shows [M+Na]+ 20%" in choice.reason
    assert {e.name for e in choice.evidence if e.present} == {"[M+NH4]+",
                                                              "[M+Na]+"}


def test_without_a_survey_the_basis_line_is_the_one_it_always_was():
    plain = ch.identify_adduct("C24H36D4O5", 430.35, "Positive")
    passed_none = ch.identify_adduct("C24H36D4O5", 430.35, "Positive",
                                     survey=None)
    assert plain.reason == passed_none.reason
    assert not plain.confirmed and not plain.read_survey
    assert plain.evidence == ()
    assert "survey" not in plain.reason


def test_a_survey_that_does_not_show_the_ion_says_so_and_changes_nothing():
    """The real case: the 647.5 channel's larger peak is a different ion
    69.9 ppm away, and the sphingomyelin is not in that survey at all."""
    formula = "C35H71N2O6P"
    survey = _survey([(647.5575, 44_231.0), (648.5614, 17_584.0)])
    choice = ch.identify_adduct(formula, 647.5, "Positive", survey=survey)
    plain = ch.identify_adduct(formula, 647.5, "Positive")

    assert choice.adduct is ch.ADDUCTS_BY_NAME["[M+H]+"]   # unchanged
    assert not choice.confirmed and choice.read_survey
    assert choice.reason.startswith(plain.reason)
    assert "the survey does not show it" in choice.reason
    assert "chosen from the written mass alone" in choice.reason


def test_the_survey_names_an_ion_the_written_precursor_fits_none_of():
    """`538.6` for a ceramide whose [M+H]+ weighs 538.5194 is 0.08 Da out —
    eighty times what an adduct is allowed, and still the ion the
    quadrupole isolated. Without a survey it is refused; with one the
    instrument has already said what was there."""
    formula = "C34H67NO3"
    survey = _survey(_ladder(formula, "[M+H]+", 100_000))

    refused = ch.identify_adduct(formula, 538.6, "Positive")
    assert refused.adduct is None
    assert "none of the adducts" in refused.reason

    choice = ch.identify_adduct(formula, 538.6, "Positive", survey=survey)
    assert choice.adduct is ch.ADDUCTS_BY_NAME["[M+H]+"]
    assert choice.confirmed
    assert "none of the adducts" in choice.reason
    assert "but the survey shows [M+H]+ at 538.519" in choice.reason
    assert "inside the ±0.7 Da the quadrupole passes" in choice.reason

    # but only inside that window: a survey showing the ion two daltons
    # away from what was isolated does not answer for it
    far = ch.identify_adduct(formula, 540.0, "Positive", survey=survey)
    assert far.adduct is None


def test_an_ion_too_weak_to_measure_is_reported_as_such_not_as_absent():
    formula = "C24H40O5"
    mz, intensity = _survey(_ladder(formula, "[M+H]+", 40.0))
    found = ch.adduct_evidence(mz, intensity, formula,
                               candidates=["[M+H]+"])[0]
    assert not found.present and found.height == pytest.approx(40.0, abs=1.0)
    assert "only 40 counts" in found.note
    # the floor is the caller's to set, and lowering it admits the ion
    lower = ch.adduct_evidence(mz, intensity, formula, candidates=["[M+H]+"],
                               min_intensity=10.0)[0]
    assert lower.present


def test_a_product_ion_scan_has_no_satellites_and_is_not_called_a_liar():
    """Q1 kept the monoisotopic ion and threw its satellites away. Nothing
    to compare is not a disagreement: the score falls back to the mass."""
    formula = "C24H40O5"
    mz, intensity = _survey([(ch.mass_from_formula(formula, "[M+H]+"),
                              50_000.0)])
    found = ch.adduct_evidence(mz, intensity, formula,
                               candidates=["[M+H]+"])[0]
    assert found.present and found.pattern is None
    assert found.score > 0.9
    assert "no isotope satellites" in found.note
    assert "no isotope satellites to compare" in found.isotope_note
