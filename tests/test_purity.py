"""
The isotopic purity of a labelled standard, measured from its own envelope.

Everything here is built from known fractions and read back, because that is
the only way to say a deconvolution is right: a real spectrum has no answer
key. A synthetic envelope is assembled the way the instrument assembles one —
every species' natural-abundance satellites folded in on top of the species
above it, on a profile grid at the resolving power the ZenoTOF measured — and
the fractions have to come back out.

What is checked: that the fractions are recovered within half a per cent, that
the overlap is what makes the recovery different from reading the peaks, that
the floor and the uncertainty do what they claim, that an envelope a
quadrupole has cut is refused rather than solved, that a ladder reading comes
back marked a lower bound, and that the report line and the record field say
so in words.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import purity as P  # noqa: E402
from milq.chemistry import (adduct_from_name, isotope_pattern,  # noqa: E402
                                 monoisotopic_mass, parse_formula)

#: cholic acid-d4 as its ammonium adduct: the standard this was written for
FORMULA = "C24H36D4O5"
ADDUCT = "[M+NH4]+"
#: the peak width the real infusions were measured at, 0.0102 Da at half
#: height for m/z 430 — R = 42,000
WIDTH = 0.0102


def envelope(fractions, formula: str = FORMULA, adduct_name: str = ADDUCT,
             width: float = WIDTH, noise: float = 0.0, scale: float = 1e5,
             satellites: bool = True, seed: int = 7):
    """
    A profile spectrum the instrument would record for these species.

    `satellites` False strips everything above the fully-labelled ion, which
    is what a narrow quadrupole isolation window does to a product-ion scan.
    """
    counts = parse_formula(formula)
    adduct = adduct_from_name(adduct_name)
    labels = counts.get("D", 0)
    top = adduct.mz(monoisotopic_mass(counts))
    natural = P._normalised(
        isotope_pattern(counts, adduct, min_abundance=1e-5, max_peaks=5), 4)
    sticks: dict[float, float] = {}
    for index, fraction in enumerate(fractions):
        base = top - (labels - index) * P.D_MINUS_H
        for k, abundance in enumerate(natural):
            mass = round(base + k * P.NEUTRON_SPACING, 6)
            sticks[mass] = sticks.get(mass, 0.0) + fraction * abundance
    grid = np.arange(top - (labels + 1) * 1.01, top + 4.0, 0.0018)
    intensity = np.zeros_like(grid)
    sigma = width / 2.3548
    for mass, abundance in sticks.items():
        if not satellites and mass > top + 0.5:
            continue
        intensity += abundance * np.exp(-0.5 * ((grid - mass) / sigma) ** 2)
    intensity *= scale
    if noise:
        rng = np.random.default_rng(seed)
        intensity = np.clip(intensity + rng.normal(0.0, noise * scale,
                                                   grid.size), 0.0, None)
    return grid, intensity


# --------------------------------------------------------------------------- #
def test_known_fractions_come_back_within_half_a_per_cent():
    """d4 95%, d3 4%, d2 1% — folded in, then solved back out."""
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)

    assert result.usable, result.reason
    assert result.labels == 4
    assert result.purity == pytest.approx(0.95, abs=0.005)
    assert result.at_least == pytest.approx(0.99, abs=0.005)
    assert result.fractions[2] == pytest.approx(0.01, abs=0.005)
    assert result.fractions[1] == pytest.approx(0.0, abs=0.005)
    # the atom fraction is the certificate's number and is not the purity
    assert result.atom_percent == pytest.approx(98.5, abs=0.1)


def test_unplaced_labels_are_the_same_as_labels_spelt_into_the_formula():
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    spelt = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)
    declared = P.isotopic_purity(mz, intensity, "C24H40O5", ADDUCT, 4)

    assert declared.formula == spelt.formula == "C24H36D4O5"
    assert declared.purity == pytest.approx(spelt.purity, abs=1e-9)


def test_the_overlap_is_what_the_solve_removes():
    """
    Each species' carbon-13 satellite lands on the next species' own peak,
    and that is the whole reason this is a deconvolution.

    Read straight off the rungs, the d3 impurity of a 95% material measures
    4.44% of the d4 peak where it is 4.21% of it — five per cent high, because
    d2's satellite has been added to d3 and d3's to d4. The solve gets it
    right; the ratio does not.
    """
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)
    rungs = result.measured

    naive = rungs[3] / rungs[4]
    assert naive == pytest.approx(0.0444, abs=0.0006)
    solved = result.fractions[3] / result.fractions[4]
    assert solved == pytest.approx(0.0421, abs=0.0006)
    assert naive > solved

    # and the satellite that makes the difference is genuinely there: the
    # position 2.9 mDa above the d4 peak holds a quarter of it
    assert result.natural[1] == pytest.approx(0.266, abs=0.005)


def test_a_quadrupole_isolated_envelope_is_refused_not_solved():
    """
    A product-ion scan has already lost the satellites the solve needs.

    This is what every one of the nine real bile-acid infusions looks like:
    an ion at the precursor and nothing above it.
    """
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95], satellites=False)
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)

    assert not result.usable
    assert result.purity is None
    assert "satellite" in result.reason
    assert result.satellite_ratio < P.SATELLITE_SHARE
    # the envelope is still on the object: the refusal is a statement about
    # those numbers and has to be checkable
    assert len(result.measured) == 7
    assert result.measured[4] > 0
    assert result.line().startswith("Isotopic purity: not measured")
    assert result.field() == ""


def test_a_peak_too_weak_for_its_own_satellite_is_refused_by_the_same_rule():
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95], scale=6.0,
                             noise=0.4)
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)

    assert not result.usable


def test_the_floor_is_read_from_the_gaps_and_sets_the_uncertainty():
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95], noise=0.0005)
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)

    assert result.usable
    assert result.floor > 0            # half way between rungs is not empty
    assert result.uncertainty > 0
    assert result.purity == pytest.approx(0.95, abs=0.005)
    # the answer is inside its own error bar
    assert abs(result.purity - 0.95) <= result.uncertainty + 0.005

    # a floor handed in is honoured, and a larger one widens the bar
    wider = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT,
                              floor=result.floor * 5)
    assert wider.floor == pytest.approx(result.floor * 5)
    assert wider.uncertainty > result.uncertainty


def test_an_envelope_with_nothing_in_it_says_so():
    mz = np.linspace(400.0, 440.0, 2000)
    result = P.isotopic_purity(mz, np.zeros_like(mz), FORMULA, ADDUCT)

    assert not result.usable
    assert "no envelope" in result.reason


def test_a_compound_with_no_labels_is_not_asked():
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    result = P.isotopic_purity(mz, intensity, "C24H40O5", ADDUCT)

    assert not result.usable
    assert "no labels" in result.reason


# --------------------------------------------------------------------------- #
def test_the_ladder_is_read_as_a_lower_bound_and_says_so():
    """
    Where the precursor did not survive, the water-loss ladder is tried and
    the result is flagged.

    Built here as the instrument would give it: no precursor at all, and the
    ladder rung carrying its own envelope — including, as a dehydration can,
    fully-labelled molecules that left a label behind with the water.
    """
    from milq.explain import precursor_ions

    rung = next(ion for ion in precursor_ions(FORMULA, ADDUCT)
                if ion.losses == ("H2O",) and ion.labels == 4)
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.09, 0.90],
                             formula=rung.fragment.formula,
                             adduct_name="[M+H]+")

    attempt = P.purity_from_spectrum(mz, intensity, FORMULA, ADDUCT)
    assert attempt.precursor is not None and not attempt.precursor.usable
    assert attempt.ladder is not None
    result = attempt.best
    assert result is attempt.ladder
    assert result.usable, result.reason
    assert result.lower_bound
    assert result.where == P.LADDER
    assert result.purity == pytest.approx(0.90, abs=0.005)
    assert "lower bound" in result.line()
    assert "lower bound" in " ".join(result.sentences())
    assert "lower bound" in result.field()


def test_the_precursor_wins_when_it_can_be_read():
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    attempt = P.purity_from_spectrum(mz, intensity, FORMULA, ADDUCT)

    assert attempt.best is attempt.precursor
    assert attempt.ladder is None
    assert attempt.best.where == P.PRECURSOR
    assert not attempt.best.lower_bound


# --------------------------------------------------------------------------- #
def test_the_report_line_carries_both_figures_and_the_error():
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95], noise=0.0005)
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)
    line = result.line()

    assert line.startswith("Isotopic purity: d4 ")
    assert "≥d3 " in line
    assert "the precursor at 430.35" in line
    assert "±" in line
    assert result.label().startswith("d4 ")
    assert "atom % D" in result.field()


def test_the_report_paragraph_carries_the_envelope_and_the_refusal():
    from milq.infusion_report import InfusionReport, _purity_block

    report = InfusionReport(compound="cholic acid-d4")
    assert _purity_block(report) == ""

    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    report.purity = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)
    html = _purity_block(report)
    assert "Isotopic purity" in html
    assert "atom % D" in html
    assert "430.34" in html                     # the rung the envelope sits at
    assert "d0" in html and "M+1" in html
    assert " ".join(report.sentences())         # it reaches the verdict too
    assert "atom % D" in " ".join(report.sentences())

    cut, cut_intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95],
                                  satellites=False)
    report.purity = P.isotopic_purity(cut, cut_intensity, FORMULA, ADDUCT)
    refused = _purity_block(report)
    assert "No purity was read" in refused
    assert "d0" in refused                      # the rungs are still printed


def test_a_record_carries_the_purity_because_nothing_can_recover_it():
    from milq.library import PURITY_FIELD, entry_from_spectrum, parse_msp

    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)
    entry = entry_from_spectrum(
        "cholic acid-d4", np.array([359.287, 377.298, 430.347]),
        np.array([5672.0, 9618.0, 12270.0]), precursor=430.3465,
        precursor_type=ADDUCT, formula=FORMULA,
        isotopic_purity=result.field())

    assert entry.fields[PURITY_FIELD] == result.field()
    from milq.library import format_msp
    back = parse_msp(format_msp([entry]))
    assert back[0].fields[PURITY_FIELD] == result.field()

    # nothing is written when nothing was measured
    bare = entry_from_spectrum(
        "cholic acid-d4", np.array([359.287]), np.array([5672.0]))
    assert PURITY_FIELD not in bare.fields


# --------------------------------------------------------------------------- #
def test_the_solver_refuses_to_return_a_negative_composition():
    """A fraction below zero is not a composition, whatever it fits better."""
    A = P._design(np.array([1.0, 0.266, 0.044]), 2, 5)
    b = np.array([0.0, 0.0, 1.0, 0.266, 0.044])
    x = P._nnls(A, b)

    assert (x >= 0).all()
    assert x[2] == pytest.approx(1.0, abs=1e-6)


def test_an_unrelated_ion_in_a_window_is_what_makes_the_constraint_bind():
    """
    Noise alone never drives a fraction negative; a neighbour does.

    A co-infused ion sitting on the d0 rung at half a per cent of the base
    peak takes the *unconstrained* d1 to −0.125%, which is what a report
    would otherwise print as a composition.
    """
    from milq.chemistry import (adduct_from_name, monoisotopic_mass,
                                     parse_formula)

    top = adduct_from_name(ADDUCT).mz(monoisotopic_mass(parse_formula(FORMULA)))
    mz, intensity = envelope([0.0, 0.0, 0.01, 0.04, 0.95])
    sigma = WIDTH / 2.3548
    centre = top - 4 * P.D_MINUS_H
    intensity = intensity + intensity.max() * 0.005 * np.exp(
        -0.5 * ((mz - centre) / sigma) ** 2)

    result = P.isotopic_purity(mz, intensity, FORMULA, ADDUCT)
    assert result.usable
    assert min(result.fractions) >= 0.0

    design = P._design(np.asarray(result.natural), result.labels,
                       len(result.measured))
    free = np.linalg.lstsq(design, np.asarray(result.measured), rcond=None)[0]
    free = free / free.sum()
    assert free.min() < -0.001            # the constraint had something to do
