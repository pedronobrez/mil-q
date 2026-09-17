"""Tests for the component list (CSV round-trip)."""

import pytest

from milq.components import Component, load_components, save_components


def test_roundtrip_csv(tmp_path):
    components = [
        Component("12,13-DiHOME", 313.2384, 183.1391, 14.7, 0.5, 0.02, "Da"),
        Component("9,10-DiHOME", 313.2384, 201.1496, 14.2, 0.5, 20.0, "ppm"),
    ]
    path = tmp_path / "compounds.csv"
    save_components(path, components)
    back = load_components(path)
    assert back == components


def test_load_accepts_minimal_columns(tmp_path):
    path = tmp_path / "min.csv"
    path.write_text("name,precursor\nDiHOME,313.2384\n", encoding="utf-8")
    [component] = load_components(path)
    assert component.name == "DiHOME"
    assert component.precursor == pytest.approx(313.2384)
    assert component.fragment is None


def test_load_reads_a_formula_under_any_of_its_headers(tmp_path):
    """
    A formula is what makes a component a lock mass for the recalibration, so
    a spreadsheet that calls the column something else should still arrive
    with one.
    """
    for header in ("formula", "elemental_formula", "composition",
                   "molecular_formula", "Chemical Formula"):
        path = tmp_path / "f.csv"
        path.write_text(f"name,precursor,adduct,{header}\n"
                        f"SM(d18:1/12:0),647.5,[M+H]+,C35H71N2O6P\n",
                        encoding="utf-8")
        [component] = load_components(path)
        assert component.formula == "C35H71N2O6P", header
        assert component.precursor_from_formula() == pytest.approx(647.5123,
                                                                   abs=5e-4)


def test_load_rejects_missing_name(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("precursor\n313.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="name column"):
        load_components(path)


def test_mass_window_da():
    component = Component("x", 313.2, 183.1391, tolerance=0.02, unit="Da")
    lo, hi = component.mass_window()
    assert (lo, hi) == pytest.approx((183.1191, 183.1591))


def test_mass_window_ppm():
    component = Component("x", 313.2, 200.0, tolerance=25.0, unit="ppm")
    lo, hi = component.mass_window()
    assert (hi - lo) == pytest.approx(0.01, rel=1e-6)


def test_mass_window_falls_back_to_precursor():
    component = Component("x", 313.2, None, tolerance=0.02)
    lo, hi = component.mass_window()
    assert (lo + hi) / 2 == pytest.approx(313.2)


def test_rt_window_none_when_unset():
    assert Component("x", 313.2).rt_window() is None
    assert Component("x", 313.2, rt=10.0, rt_halfwidth=0.5).rt_window() == (9.5, 10.5)
