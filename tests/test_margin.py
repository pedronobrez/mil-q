"""An explanation's margin: the chosen compound against its nearest impostors."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from milq import margin as margin_module
from milq.explain import explain_formula, formula_ions
from milq.lipidmaps import LipidDatabase, LipidRecord
from milq.margin import (THIN_MARGIN, Impostor, Margin, cross_validate,
                              neighbours)
from milq.structure import parse_molblock

FIXTURES = Path(__file__).parent / "fixtures"

#: the true compound of these tests: cholic acid, scored from its formula
TRUE_FORMULA = "C24H40O5"
TRUE_MASS = 408.287574
#: a different composition 36 mDa away — inside a 0.7 Da isolation window,
#: and a different arithmetic, which is what makes it an impostor at all
RIVAL_FORMULA = "C25H44O4"
RIVAL_MASS = 408.323945


def drawing():
    """
    A connection table for the synthetic records.

    The same one for every record on purpose: these tests score from the
    *formula*, which never opens the drawing — `candidates_for` only asks
    that a candidate have one, because a record with no structure cannot be
    scored on the other route. `test_an_impostor_is_scored_the_same_way_as_
    the_compound` is what proves the drawing was not used.
    """
    text = (FIXTURES / "LMST04010001.mol").read_text()
    return parse_molblock(text, TRUE_FORMULA).to_compact()


def record(lm_id, name, formula, mass, abbrev=""):
    # a distinct abbreviation on purpose: `candidates_for` takes one record
    # per species, and two records with none are one species called by their
    # shared formula
    return LipidRecord(lm_id=lm_id, name=name, abbrev=abbrev or name,
                       formula=formula, exact_mass=mass, structure=drawing())


@pytest.fixture
def database():
    return LipidDatabase([
        record("LMST04010001", "Cholic acid", TRUE_FORMULA, TRUE_MASS),
        # the same formula: an isomer, and no contrast at all
        record("LMST04010002", "Allocholic acid", TRUE_FORMULA, TRUE_MASS),
        record("LMFA00000001", "The rival", RIVAL_FORMULA, RIVAL_MASS),
    ])


def intact(formula, adduct="[M+H]+"):
    """The precursor ion of a formula, as the formula route offers it."""
    ions = [i for i in formula_ions(formula, adduct) if not i.losses]
    return ions[0].mz


def dehydrated(formula, adduct="[M+H]+"):
    ions = [i for i in formula_ions(formula, adduct)
            if i.losses == ("H2O",)]
    return ions[0].mz


def spectrum(pairs):
    """`(mz, intensity)` arrays from a list of peaks."""
    mz = np.array([m for m, _h in pairs], dtype=float)
    intensity = np.array([h for _m, h in pairs], dtype=float)
    return mz, intensity


PRECURSOR = 409.29                              # written to two decimals


# -- the margin itself -------------------------------------------------------- #
def test_the_margin_is_the_chosen_share_less_the_best_impostor(database):
    """
    The whole point: a share is not evidence until something else has been
    scored on the same peaks. Here the compound accounts for two peaks of
    three and the rival for the third.
    """
    peaks = [(intact(TRUE_FORMULA), 1000.0),
             (dehydrated(TRUE_FORMULA), 200.0),
             (intact(RIVAL_FORMULA), 600.0)]
    mz, intensity = spectrum(peaks)
    chosen = explain_formula(TRUE_FORMULA, "[M+H]+",
                             list(zip(mz.tolist(), intensity.tolist())),
                             name="Cholic acid")
    result = cross_validate(mz, intensity, chosen, PRECURSOR, "Positive",
                            database)
    assert result.best is not None
    assert result.best.name == "The rival"
    assert result.best.adduct == "[M+H]+"
    assert round(result.share * 100, 1) == 66.7
    assert round(result.best.share * 100, 1) == 33.3
    assert round(result.points, 1) == 33.3
    assert result.measured and not result.thin


def test_an_isomer_of_the_same_formula_is_not_an_impostor(database):
    """
    Same formula, same arithmetic, no contrast. Allocholic acid predicts
    every mass cholic acid predicts, so scoring it would report the chosen
    compound's own number in the impostor column — a margin of zero for a
    spectrum that was never in doubt.
    """
    peaks = [(intact(TRUE_FORMULA), 1000.0),
             (intact(RIVAL_FORMULA), 600.0)]
    mz, intensity = spectrum(peaks)
    chosen = explain_formula(TRUE_FORMULA, "[M+H]+",
                             list(zip(mz.tolist(), intensity.tolist())),
                             name="Cholic acid")
    result = cross_validate(mz, intensity, chosen, PRECURSOR, "Positive",
                            database)
    names = [i.name for i in result.others]
    assert "Allocholic acid" not in names
    assert "Cholic acid" not in names
    # both were dropped for the same reason, and the count is carried so the
    # sentence can say a margin was measured over fewer than were found
    assert result.same_formula == 2
    assert "2 same-formula isomer(s) left out" in result.sentence()


def test_the_compound_itself_is_never_its_own_rival(database):
    near, same = neighbours(database, PRECURSOR, "Positive",
                            formula="something else", lm_id="LMST04010001",
                            window=0.7)
    assert "LMST04010001" not in [r.lm_id for r, _f, _e in near]
    assert same >= 1


def test_an_impostor_is_scored_the_same_way_as_the_compound(database):
    """
    The measured trap. A formula offers about fifty masses and a structure
    with one bond cut offers two thousand; a list of two thousand covers a
    spectrum by accident, and contrasting the two measures the length of the
    list rather than the compound. So a chosen explained from a formula gets
    rivals explained from *their* formulas.
    """
    peaks = [(intact(TRUE_FORMULA), 1000.0),
             (intact(RIVAL_FORMULA), 600.0)]
    mz, intensity = spectrum(peaks)
    chosen = explain_formula(TRUE_FORMULA, "[M+H]+",
                             list(zip(mz.tolist(), intensity.tolist())),
                             name="Cholic acid")
    result = cross_validate(mz, intensity, chosen, PRECURSOR, "Positive",
                            database)
    rival = next(i for i in result.others if i.name == "The rival")
    assert rival.predicted == len(formula_ions(RIVAL_FORMULA, "[M+H]+"))
    # and that is the same order of size as what the compound was offered
    assert rival.predicted < 3 * chosen.predicted


def test_nothing_to_contrast_with_says_so():
    lonely = LipidDatabase([record("LMST04010001", "Cholic acid",
                                   TRUE_FORMULA, TRUE_MASS)])
    peaks = [(intact(TRUE_FORMULA), 1000.0)]
    mz, intensity = spectrum(peaks)
    chosen = explain_formula(TRUE_FORMULA, "[M+H]+",
                             list(zip(mz.tolist(), intensity.tolist())),
                             name="Cholic acid")
    result = cross_validate(mz, intensity, chosen, PRECURSOR, "Positive",
                            lonely)
    assert result.best is None and result.points is None
    assert not result.measured and not result.thin
    assert "same formula" in result.note
    assert result.sentence().startswith("explains 100.0%;")


def test_no_precursor_no_neighbours(database):
    peaks = [(intact(TRUE_FORMULA), 1000.0)]
    mz, intensity = spectrum(peaks)
    chosen = explain_formula(TRUE_FORMULA, "[M+H]+",
                             list(zip(mz.tolist(), intensity.tolist())),
                             name="Cholic acid")
    result = cross_validate(mz, intensity, chosen, None, "Positive", database)
    assert result.best is None
    assert "no precursor" in result.note
    assert result.column() == result.note


def test_nothing_explained_is_not_a_margin_of_zero():
    result = cross_validate(np.array([100.0]), np.array([1.0]), None,
                            PRECURSOR, "Positive", None)
    assert result.best is None and result.points is None
    assert result.note == "nothing was explained"


# -- the flag ----------------------------------------------------------------- #
def wide():
    return Margin(compound="CA-d4", share=0.636,
                  best=Impostor(name="PC 34:1", formula="C42H82NO8P",
                                adduct="[M+NH4]+", share=0.201, matched=4,
                                predicted=60),
                  others=[Impostor(name="PC 34:1", formula="C42H82NO8P",
                                   adduct="[M+NH4]+", share=0.201, matched=4,
                                   predicted=60)] * 10)


def test_a_thin_margin_is_flagged():
    thin = Margin(compound="TDCA-d4", share=0.784,
                  best=Impostor(name="PC O-16:0/0:0", formula="C24H52NO6P",
                                adduct="[M+Na]+", share=0.723, matched=4,
                                predicted=87),
                  others=[])
    assert round(thin.points, 1) == 6.1
    assert thin.points < THIN_MARGIN and thin.thin
    assert "does not tell them apart" in thin.sentence()
    assert thin.column().endswith("(thin)")
    assert not wide().thin
    assert "does not tell them apart" not in wide().sentence()


def test_a_margin_can_be_negative():
    """A rival that explains more is a finding, not an error."""
    beaten = Margin(compound="Cer(d18:1/16:0)", share=0.095,
                    best=Impostor(name="PE 22:0/0:0", formula="C27H56NO7P",
                                  adduct="[M+H]+", share=0.124, matched=4,
                                  predicted=40))
    assert round(beaten.points, 1) == -2.9
    assert beaten.thin
    assert "-2.9 points" in beaten.sentence()


def test_the_sentence_names_the_impostor_and_the_margin():
    said = wide().sentence()
    assert said.startswith("explains 63.6%;")
    assert "the best of 10 neighbour(s)" in said
    assert "(PC 34:1 as [M+NH4]+) explains 20.1%" in said
    assert "a margin of 43.5 points" in said


# -- where it shows ----------------------------------------------------------- #
def test_the_report_carries_the_margin_and_says_it():
    from milq.infusion_report import InfusionReport, _explanation_block

    peaks = [(intact(TRUE_FORMULA), 1000.0)]
    chosen = explain_formula(TRUE_FORMULA, "[M+H]+", peaks, name="Cholic acid")
    report = InfusionReport(compound="Cholic acid", explanation=chosen,
                            basis="the formula C24H40O5 as [M+H]+")
    assert report.margin is None                  # nothing measured it yet
    assert "Margin —" not in _explanation_block(report)
    report.margin = wide()
    block = _explanation_block(report)
    assert "Margin — Cholic acid explains 63.6%" in block
    assert "a margin of 43.5 points" in block


def test_the_infusions_table_has_a_margin_column():
    from milq.infusion_report import (SUMMARY_COLUMNS, InfusionReport,
                                           InfusionRow)

    assert "Margin" in SUMMARY_COLUMNS
    column = SUMMARY_COLUMNS.index("Margin")
    row = InfusionRow(report=InfusionReport(compound="CA-d4"),
                      explanation_note="not a component of the method")
    assert row.cells()[column] == "not a component of the method"
    assert row.keys()[column] == float("inf")     # no number sorts to the end
    row.report.margin = wide()
    assert row.cells()[column] == "+43.5 pts vs PC 34:1 as [M+NH4]+"
    assert round(row.keys()[column], 1) == 43.5


def test_the_measurement_travels_from_the_panel_to_the_report():
    """
    `from_explorer` takes the margin the panel already measured rather than
    measuring it again: the same seconds for the same answer, and the page
    and the tab then cannot disagree about it.
    """
    from milq import infusion_report

    assert "explanation_margin" in Path(
        infusion_report.__file__).read_text(encoding="utf-8")
    assert hasattr(margin_module, "for_report")


def test_the_panel_measures_a_margin_and_says_it():
    """
    The Explain tab: the own-structure path prints the margin on the line
    under the tables and keeps the measurement for the report.

    True whether or not the LIPID MAPS index is installed on this machine.
    With it, the margin is measured; without it, the object says so in its
    own words rather than being absent — which is why the assertion is on
    the attribute and not on a number.
    """
    from PyQt6 import QtWidgets

    from milq.ui.lipid_panel import LipidPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = LipidPanel()
    panel.set_spectrum(np.array([430.3465, 359.2882]),
                       np.array([1000.0, 800.0]), 430.35, "Positive")
    panel.own_formula.setText("C24H36D4O5")
    panel.own_name.setText("Cholic acid-d4")
    panel.explain_own()

    assert panel.explanation_margin is not None
    assert isinstance(panel.explanation_margin, Margin)
    assert "Margin: explains" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


def test_the_panel_forgets_the_margin_when_it_explains_nothing():
    from PyQt6 import QtWidgets

    from milq.ui.lipid_panel import LipidPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = LipidPanel()
    panel.set_spectrum(np.array([430.3465]), np.array([1000.0]), 430.35,
                       "Positive")
    panel.own_formula.setText("C24H36D4O5")
    panel.explain_own()
    assert panel.explanation_margin is not None
    # nothing reaches 430.35 unlabelled, so the panel refuses the whole
    # explanation — and the margin of an explanation that was not made is
    # not the last one that was
    panel.own_formula.setText("C24H40O5")
    panel.explain_own()
    assert panel.explanation_margin is None
    assert "Nothing explained" in panel.status.text()
    panel.deleteLater()
    app.processEvents()
