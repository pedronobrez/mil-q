"""
Whether a concentration can be reported at all: below zero, under the
lowest standard, the curve's intercept, or a ratio to an internal standard
that was not spiked alike in the curve and the sample.

Each case is the shape a real eicosanoid batch had: prostaglandins
normalised to a PGE2-d4 present in the samples and absent from the curve,
leukotrienes to a standard absent everywhere, analytes at the blank's level.
"""

import pytest

from milq.components import Component
from milq.method import ProcessingMethod
from milq.quantify import (
    PASS,
    FAIL,
    PeakResult,
    ResultsSet,
    apply_calibrations,
    build_calibrations,
    evaluate_acceptance,
    link_internal_standards,
)
from milq.samples import SOLVENT, STANDARD, UNKNOWN, SampleEntry

LEVELS = (2.0, 10.0, 50.0, 200.0)


def _entry(name, kind, concentration=None, dilution=1.0):
    return SampleEntry(f"/d/{name}.wiff", 0, name, sample_type=kind,
                       actual_concentration=concentration,
                       dilution_factor=dilution)


def _row(entry, component, area):
    return PeakResult(sample_key=entry.key, sample_name=entry.name,
                      component=component, area=area, height=area / 2,
                      rt=5.0, expected_rt=5.0)


def _batch(analyte_areas: dict[str, float], is_curve=400.0, is_sample=400.0,
           is_solvent=0.0, slope=10.0, intercept=0.0, with_is=True,
           dilution=1.0, areas=None):
    """
    A curve of four standards and the unknowns named in `analyte_areas`,
    the analyte's area being slope·c + intercept times the standard's area
    over a hundred, so its ratio is exactly the line — or `areas`, one per
    level, for a curve the line does not pass through.
    """
    method = ProcessingMethod()
    components = [Component("PGD2", 351.2, 271.2, rt=5.0,
                            internal_standard="PGE2-d4" if with_is else "")]
    if with_is:
        components.append(Component("PGE2-d4", 355.2, 275.2, rt=5.0,
                                    is_internal_standard=True))
    method.replace_all(components)
    entries, rows = [], []
    for index, level in enumerate(LEVELS):
        entry = _entry(f"P{index}", STANDARD, level)
        entries.append(entry)
        scale = is_curve / 100 if with_is else 1.0
        area = (areas[index] if areas is not None
                else (slope * level + intercept) * scale)
        rows.append(_row(entry, "PGD2", area))
        if with_is:
            rows.append(_row(entry, "PGE2-d4", is_curve))
    for name, area in analyte_areas.items():
        entry = _entry(name, UNKNOWN, dilution=dilution)
        entries.append(entry)
        rows.append(_row(entry, "PGD2", area))
        if with_is:
            rows.append(_row(entry, "PGE2-d4", is_sample))
    solvent = _entry("S1", SOLVENT)
    entries.append(solvent)
    rows.append(_row(solvent, "PGD2", 0.5))
    if with_is:
        rows.append(_row(solvent, "PGE2-d4", is_solvent))
    results = ResultsSet(rows)
    link_internal_standards(results, method)
    curves = build_calibrations(results, entries, method)
    apply_calibrations(results, entries, method, curves)
    evaluate_acceptance(results, entries, method, curves)
    return results, entries, curves


def _flags(results, name, component="PGD2"):
    return next(r for r in results if r.sample_name == name
                and r.component == component)


def test_a_sample_inside_the_curve_with_a_steady_standard_passes():
    results, _, _ = _batch({"KO01": 2000.0})   # ratio 5: 50 ng/mL
    row = _flags(results, "KO01")
    assert row.calculated_concentration == pytest.approx(50.0)
    assert row.flags == []
    assert row.status == PASS


def test_a_standard_in_the_samples_and_not_in_the_curve_is_flagged():
    # PGE2-d4 on the real batch: ~5,000 counts in the samples, ~3 in the curve
    results, _, _ = _batch({"KO01": 2.0}, is_curve=3.0, is_sample=5000.0)
    row = _flags(results, "KO01")
    assert any("PGE2-d4 5,000 here against 3 in the curve" in f
               for f in row.flags)
    assert row.status == FAIL


def test_a_standard_in_the_curve_and_not_in_the_samples_is_flagged():
    # 5-oxo-ETE-d7: ~100 in the curve, nothing in the samples
    results, _, _ = _batch({"KO01": 2.0}, is_curve=100.0, is_sample=0.0)
    row = _flags(results, "KO01")
    assert any("absent here" in f for f in row.flags)


def test_a_standard_no_higher_than_the_solvents_was_never_spiked():
    # 12-epi-LTB4-d4: ~5 counts in the curve against ~1 in the solvents
    results, _, _ = _batch({"KO01": 2.0}, is_curve=5.0, is_sample=4.0,
                           is_solvent=1.0)
    row = _flags(results, "KO01")
    assert any("not above the solvents" in f for f in row.flags)


def test_a_standard_kept_within_its_factor_is_not_flagged():
    results, _, _ = _batch({"KO01": 400.0 * 0.5 * 3}, is_curve=400.0,
                           is_sample=400.0 * 3)
    assert not any(f.startswith("IS") for f in _flags(results, "KO01").flags)


def test_a_negative_concentration_and_the_intercept_are_named():
    # a positive intercept the sample's response never reaches
    results, _, curves = _batch({"KO01": 0.001}, with_is=False, slope=10.0,
                                intercept=30.0)
    row = _flags(results, "KO01")
    assert curves["PGD2"].response_at(0.0) == pytest.approx(30.0)
    assert row.calculated_concentration < 0
    assert "negative concentration" in row.flags
    assert "the curve's intercept, not the sample's response" in row.flags


def test_a_response_under_the_lowest_standard_is_below_the_lloq_even_when_the_curve_says_otherwise():
    # a negative intercept carries a response under the lowest standard's to
    # a concentration above the lowest level — LXA4 on the real batch
    # the line through these is 2.95c − 10.1: the lowest standard gave 3,
    # and a response of 1 reads 3.75 against a lowest level of 2
    results, _, curves = _batch({"KO01": 1.0}, with_is=False,
                                areas=[3.0, 10.0, 140.0, 580.0])
    row = _flags(results, "KO01")
    lowest_level = min(p.concentration for p in curves["PGD2"].used_points)
    assert row.calculated_concentration > lowest_level
    assert "< LLOQ (2 ng/mL)" in row.flags


def test_the_lloq_is_the_vials_and_the_dilution_is_taken_back_out():
    # 5 ng/mL in the vial, reported ×0.05: 0.25 is not under an LLOQ of 2
    results, _, _ = _batch({"KO01": 50.0}, with_is=False, dilution=0.05)
    row = _flags(results, "KO01")
    assert row.calculated_concentration == pytest.approx(0.25)
    assert not any(f.startswith("< LLOQ") for f in row.flags)


def test_above_the_highest_standard_is_named():
    results, _, _ = _batch({"KO01": 10.0 * 400}, with_is=False)
    assert any(f.startswith("> ULOQ") for f in _flags(results, "KO01").flags)


def test_blanks_and_solvents_are_expected_to_read_nothing():
    results, _, _ = _batch({"KO01": 100.0}, with_is=False, intercept=30.0)
    solvent = _flags(results, "S1")
    assert not any(f in ("negative concentration",) or f.startswith("< LLOQ")
                   for f in solvent.flags)


def test_without_curves_nothing_new_is_checked():
    """The old call, with no curves, keeps its old meaning."""
    results, entries, _ = _batch({"KO01": 0.001}, with_is=False, intercept=30.0)
    method = ProcessingMethod()
    method.replace_all([Component("PGD2", 351.2, 271.2, rt=5.0)])
    evaluate_acceptance(results, entries, method)
    assert _flags(results, "KO01").flags == []
    assert _flags(results, "KO01").status == ""

