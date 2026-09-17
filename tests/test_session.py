"""Tests for the shared session, method and batch models (no GUI, no .wiff)."""

import json

import pytest

from milq.components import Component
from milq.method import ProcessingMethod
from milq.samples import SampleEntry, shorten_names


# --- components -------------------------------------------------------------- #
def test_precursor_is_computed_from_formula_and_adduct():
    c = Component("DiHOME-d4", formula="C18H30D4O4", adduct="[M-H]-")
    assert c.precursor == pytest.approx(317.2635, abs=1e-3)


def test_formula_without_adduct_leaves_the_precursor_alone():
    assert Component("x", formula="C18H34O4").precursor == 0.0


def test_explicit_precursor_wins_over_the_formula():
    c = Component("x", precursor=300.0, formula="C18H34O4", adduct="[M-H]-")
    assert c.precursor == 300.0


def test_unknown_response_falls_back_to_area():
    assert Component("x", 100.0, response="nonsense").response == "area"


def test_component_validity():
    assert Component("x", 100.0).is_valid
    assert not Component("", 100.0).is_valid
    assert not Component("x", 0.0).is_valid


# --- method ------------------------------------------------------------------- #
@pytest.fixture
def method():
    m = ProcessingMethod()
    m.replace_all([
        Component("DiHOME", 313.2384, 183.1391, 14.7, group="oxylipins",
                  internal_standard="DiHOME-d4"),
        Component("DiHOME-d4", 317.2635, 185.0, 14.7, group="oxylipins",
                  is_internal_standard=True),
        Component("HODE", 295.2279, 195.1391, group="oxylipins"),
    ])
    return m


def test_method_splits_analytes_and_internal_standards(method):
    assert [c.name for c in method.analytes] == ["DiHOME", "HODE"]
    assert [c.name for c in method.internal_standards] == ["DiHOME-d4"]


def test_internal_standard_lookup(method):
    analyte = method.by_name("DiHOME")
    assert method.internal_standard_for(analyte).name == "DiHOME-d4"
    assert method.internal_standard_for(method.by_name("HODE")) is None


def test_component_cannot_be_its_own_internal_standard():
    m = ProcessingMethod()
    m.replace_all([Component("A", 100.0, internal_standard="A")])
    assert m.internal_standard_for(m.by_name("A")) is None


def test_groups_are_listed_once_in_order(method):
    method.add(Component("Other", 200.0, group="sterols"))
    assert method.groups() == ["oxylipins", "sterols"]


def test_method_round_trips_through_json(method, tmp_path):
    method.concentration_unit = "pg/mL"
    path = tmp_path / "m.json"
    method.save(path)
    back = ProcessingMethod.load(path)
    assert back.concentration_unit == "pg/mL"
    assert [c.name for c in back.components] == [c.name for c in method.components]
    assert back.by_name("DiHOME-d4").is_internal_standard


def test_method_from_dict_ignores_unknown_keys():
    data = {"tolerance": 0.05, "future_option": True,
            "components": [{"name": "A", "precursor": 100.0, "future_field": 1}]}
    method = ProcessingMethod.from_dict(data)
    assert method.tolerance == 0.05
    assert method.components[0].name == "A"


# --- samples ------------------------------------------------------------------ #
def test_shorten_names_strips_the_common_prefix():
    entries = [
        SampleEntry("/d/demo_QC01.wiff", 0, ""),
        SampleEntry("/d/demo_STD_L1.wiff", 0, ""),
    ]
    shorten_names(entries)
    assert [e.name for e in entries] == ["QC01", "STD_L1"]


def test_shorten_names_keeps_a_single_file_intact():
    entries = [SampleEntry("/d/demo_QC01.wiff", 0, "")]
    shorten_names(entries)
    assert entries[0].name == "demo_QC01"


def test_sample_entry_round_trip():
    entry = SampleEntry("/d/a.wiff", 1, "QC", "Quality Control", 25.0, 2.0, "note")
    back = SampleEntry.from_dict(json.loads(json.dumps(entry.to_dict())))
    assert back == entry
    assert back.sample is None  # the live handle is never serialised


def test_unknown_sample_type_falls_back():
    back = SampleEntry.from_dict({"path": "a", "sample_index": 0, "name": "n",
                                  "sample_type": "Bogus"})
    assert back.sample_type == "Unknown"


def test_blank_concentration_stays_none():
    back = SampleEntry.from_dict({"path": "a", "sample_index": 0, "name": "n",
                                  "actual_concentration": ""})
    assert back.actual_concentration is None
