"""One Explain that tries every route and shows the best with its reason."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.explain_any import (
    MAX_CUTS,
    MAX_LOSSES,
    ROUTE_DATABASE,
    ROUTE_DRAWING,
    ROUTE_FORMULA,
    ROUTE_NAME,
    ROUTES,
    RouteResult,
    _rank,
    explain_any,
)
from milq.lipidmaps import LipidDatabase, LipidRecord
from milq.structure import parse_molblock

#: triacetin, TG 2:0/2:0/2:0 — the same drawing `test_explain` uses: small
#: enough to enumerate in a test and a real triacylglycerol, so the ammonium
#: it is really seen as is the ammonium this scores
TRIACETIN = """triacetin
  test

 15 14  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
   -0.7500    1.2990    0.0000 O   0  0  0  0  0  0
   -2.2500    1.2990    0.0000 C   0  0  0  0  0  0
   -3.0000    0.0000    0.0000 O   0  0  0  0  0  0
   -3.0000    2.5980    0.0000 C   0  0  0  0  0  0
    2.2500   -1.2990    0.0000 O   0  0  0  0  0  0
    3.7500   -1.2990    0.0000 C   0  0  0  0  0  0
    4.5000   -0.0000    0.0000 O   0  0  0  0  0  0
    4.5000   -2.5980    0.0000 C   0  0  0  0  0  0
    3.7500    1.2990    0.0000 O   0  0  0  0  0  0
    5.2500    1.2990    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 O   0  0  0  0  0  0
    6.0000    2.5980    0.0000 C   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  1  4  1  0
  4  5  1  0
  5  6  2  0
  5  7  1  0
  2  8  1  0
  8  9  1  0
  9 10  2  0
  9 11  1  0
  3 12  1  0
 12 13  1  0
 13 14  2  0
 13 15  1  0
M  END
"""

TRIACETIN_MASS = 218.079038
TG_AMMONIUM = 236.112864          # [M+NH4]+, what the channel isolates
TG_DIACYL = 159.065185            # [M+H − acetic acid]+, which needs a cut

#: a different compound whose [M+H]+ also sits inside ±0.05 Da of the same
#: written precursor — 236.1281, 64 ppm from the ammonium, so the two routes
#: genuinely disagree about what the channel held
RIVAL = "C13H17NO3"
RIVAL_WATER_LOSS = 218.1176       # [M+H−H2O]+ of the rival, and nothing else


def triacetin():
    return parse_molblock(TRIACETIN, "C9H14O6")


def triacetin_record():
    return LipidRecord(lm_id="LMGL03010000", name="TG 2:0/2:0/2:0", abbrev="",
                       formula="C9H14O6", exact_mass=TRIACETIN_MASS,
                       structure=triacetin().to_compact())


@pytest.fixture(autouse=True)
def no_installed_database(monkeypatch):
    """
    Every test here says which database it is asking.

    Without this the suite reaches whatever LMSD is installed on the machine
    running it, and a test asserting that the database route was skipped
    passes on a build server and fails on the analyst's laptop.
    """
    from milq import lipidmaps

    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: None)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: False)


@pytest.fixture
def database():
    return LipidDatabase([triacetin_record()])


def arrays(peaks):
    return (np.array([m for m, _h in peaks]),
            np.array([h for _m, h in peaks]))


# --------------------------------------------------------------------------- #
# every route asked, and the two that disagree both reported
# --------------------------------------------------------------------------- #
def test_the_formula_route_and_a_record_disagree_and_both_are_listed(database):
    """
    The point of asking every route: the database says the channel is a
    triacylglycerol seen as its ammonium, a formula typed beside it says the
    channel is something else seen as its protonated molecule, and the
    spectrum has a peak for each. Neither is hidden.
    """
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0), (TG_DIACYL, 600.0),
                            (RIVAL_WATER_LOSS, 300.0)])
    out = explain_any(mz, intensity, 236.1129, "Positive",
                      formula=RIVAL, database=database)

    routes = {r.route: r for r in out.results}
    assert set(routes) == {ROUTE_DATABASE, ROUTE_FORMULA}
    record, formula = routes[ROUTE_DATABASE], routes[ROUTE_FORMULA]
    assert record.adduct == "[M+NH4]+" and formula.adduct == "[M+H]+"
    # they explain different peaks, so they are different claims about the
    # same number and the shares say which the spectrum supports
    assert record.share > formula.share
    assert 0.0 < formula.share < 0.3
    assert out.best is record
    # and the one that lost is still on the list with its own figures
    assert formula in out.others
    assert formula.matched == 1 and formula.predicted > 1


def test_the_best_names_its_route_in_the_basis_line(database):
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0), (TG_DIACYL, 600.0)])
    out = explain_any(mz, intensity, 236.1129, "Positive", database=database)

    assert out.best.route == ROUTE_DATABASE
    # the precursor is written with the digits it was given, which is what
    # `identify_adduct` prints too — 236.1129 typed into a box reading `:g`
    assert out.best.basis == ("from LIPID MAPS at 236.113 → LMGL03010000 "
                              "as [M+NH4]+")
    assert "from LIPID MAPS" in out.summary


def test_a_name_route_writes_the_record_it_resolved_to():
    """`from the name cholic acid-d4 → LMST04010001 as [M+NH4]+`."""
    mz, intensity = arrays([(430.3465, 1000.0), (359.2882, 400.0)])
    out = explain_any(mz, intensity, 430.35, "Positive", name="cholic acid-d4")

    name = out.result(ROUTE_NAME)
    assert name is not None
    assert name.basis.startswith("from the name cholic acid-d4 → ")
    assert name.basis.endswith(" as [M+NH4]+")
    # the standards table alone, with no database: the formula and the four
    # labels the name declares, which is what makes 430.35 an ammonium at all
    assert "the standards table" in name.basis or "LMST" in name.basis
    assert "[M+NH4]+ of C24H36D4O5" in name.reason


# --------------------------------------------------------------------------- #
# the tie rules, stated and tested
# --------------------------------------------------------------------------- #
def test_a_drawing_beats_a_formula_at_the_same_share():
    """
    A spectrum of the intact ion alone: the drawing and the formula both
    predict it and both explain all of it. The drawing wins because it
    offered more ways to be wrong and was not.
    """
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0)])
    out = explain_any(mz, intensity, 236.1129, "Positive",
                      formula="C9H14O6", molecule=triacetin(), database=None)

    routes = {r.route: r for r in out.results}
    assert set(routes) == {ROUTE_FORMULA, ROUTE_DRAWING}
    assert routes[ROUTE_FORMULA].share == pytest.approx(1.0)
    assert routes[ROUTE_DRAWING].share == pytest.approx(1.0)
    assert out.best.route == ROUTE_DRAWING
    assert routes[ROUTE_DRAWING].predicted > routes[ROUTE_FORMULA].predicted


def _result(route, share=0.5, drawn=True, inside=True):
    class _Fake:
        def __init__(self, share):
            self.share = share
    return RouteResult(route=route, explanation=_Fake(share), basis="",
                       drawn=drawn, inside=inside)


def test_a_record_inside_the_written_precision_beats_one_outside():
    outside = _result(ROUTE_DATABASE, inside=False)
    inside = _result(ROUTE_NAME, inside=True)
    assert sorted([outside, inside], key=_rank) == [inside, outside]


def test_the_share_comes_before_every_tie_rule():
    """A formula that explains more beats a drawing that explains less."""
    formula = _result(ROUTE_FORMULA, share=0.9, drawn=False)
    drawing = _result(ROUTE_DRAWING, share=0.4, drawn=True)
    assert sorted([drawing, formula], key=_rank) == [formula, drawing]


def test_the_route_order_is_the_last_word():
    """Equal in every stated way, the order the routes are asked in decides."""
    later = _result(ROUTE_DRAWING)
    earlier = _result(ROUTE_NAME)
    assert sorted([later, earlier], key=_rank) == [earlier, later]
    assert ROUTES.index(ROUTE_NAME) < ROUTES.index(ROUTE_DRAWING)


# --------------------------------------------------------------------------- #
# what is missing is reported, not raised
# --------------------------------------------------------------------------- #
def test_no_input_at_all_skips_every_route_and_says_why():
    mz, intensity = arrays([(236.1129, 1000.0)])
    out = explain_any(mz, intensity, 236.1129, "Positive", database=None)

    assert out.results == []
    assert out.best is None
    assert {s.route for s in out.skipped} == set(ROUTES)
    assert "no name was given" in out.why_skipped(ROUTE_NAME)
    assert "not installed" in out.why_skipped(ROUTE_DATABASE)
    assert "no formula was given" in out.why_skipped(ROUTE_FORMULA)
    assert "no structure was loaded" in out.why_skipped(ROUTE_DRAWING)
    assert out.summary.startswith("Nothing could be explained")


def test_without_a_precursor_the_routes_that_need_one_say_so(database):
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0)])
    out = explain_any(mz, intensity, None, "Positive", formula="C9H14O6",
                      database=database)

    assert out.results == []
    assert "no precursor" in out.why_skipped(ROUTE_DATABASE)
    assert "which adduct" in out.why_skipped(ROUTE_FORMULA)


def test_an_unreadable_name_is_a_skip_and_not_a_failure(database):
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0)])
    out = explain_any(mz, intensity, 236.1129, "Positive",
                      name="not a compound at all", database=database)

    assert "not in the standards table" in out.why_skipped(ROUTE_NAME)
    assert out.best.route == ROUTE_DATABASE          # the rest still ran


def test_a_spectrum_with_nothing_above_the_noise_share_explains_nothing():
    out = explain_any(np.array([]), np.array([]), 236.1129, "Positive",
                      formula="C9H14O6")
    assert out.results == [] and out.considered == 0
    assert {s.route for s in out.skipped} == set(ROUTES)


# --------------------------------------------------------------------------- #
# nothing derived twice
# --------------------------------------------------------------------------- #
def test_the_adduct_is_identified_once_for_a_formula_two_routes_share(
        monkeypatch):
    """
    The name and the formula come to the same composition, and the survey is
    read and the isotopes scored once — which is the expensive half.
    """
    from milq import chemistry

    calls = []
    real = chemistry.identify_adduct

    def counted(formula, precursor, *args, **kwargs):
        calls.append(formula)
        return real(formula, precursor, *args, **kwargs)

    monkeypatch.setattr(chemistry, "identify_adduct", counted)
    mz, intensity = arrays([(430.3465, 1000.0), (359.2882, 400.0)])
    explain_any(mz, intensity, 430.35, "Positive", name="cholic acid-d4",
                formula="C24H40O5")
    assert calls == ["C24H36D4O5"]


# --------------------------------------------------------------------------- #
# the panel's one button
# --------------------------------------------------------------------------- #
def _panel(monkeypatch, database):
    from PyQt6 import QtWidgets

    from milq import lipidmaps
    from milq.ui.lipid_panel import LipidPanel

    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: database)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = LipidPanel()
    panel.refresh_availability()
    return app, panel


def test_the_panel_button_fills_itself_from_the_component_table(monkeypatch,
                                                               database):
    from milq.components import Component

    app, panel = _panel(monkeypatch, database)
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0), (TG_DIACYL, 600.0),
                            (RIVAL_WATER_LOSS, 300.0)])
    panel.set_spectrum(mz, intensity, 236.1129, "Positive")
    panel.set_components([Component(name="triacetin", precursor=236.1129,
                                    formula=RIVAL)])
    assert panel.component_for_channel().name == "triacetin"
    panel.explain_anything()

    # the route table: one row per route that ran, plus the skipped ones
    assert panel.route_tree.isVisibleTo(panel)
    rows = [panel.route_tree.topLevelItem(i)
            for i in range(panel.route_tree.topLevelItemCount())]
    labels = [row.text(0) for row in rows]
    assert labels[:2] == [ROUTE_DATABASE, ROUTE_FORMULA]
    assert ROUTE_NAME in labels and ROUTE_DRAWING in labels
    assert rows[0].text(1) == "[M+NH4]+"
    assert rows[0].text(2).endswith("%")
    assert " of " in rows[0].text(3)
    # a skipped route is a row that cannot be picked, with the reason on it
    skipped = next(row for row in rows if row.text(0) == ROUTE_DRAWING)
    assert "no structure was loaded" in skipped.toolTip(0)

    # the best is what the ranked table shows, and the line names its route
    assert panel.explain_tree.topLevelItem(0).text(0) == "TG 2:0/2:0/2:0"
    assert panel.explanation_basis.startswith("from LIPID MAPS at 236.113")
    assert panel.explanation_adduct == "[M+NH4]+"

    panel.deleteLater()
    app.processEvents()


def test_clicking_a_route_swaps_the_ranked_table(monkeypatch, database):
    from milq.components import Component

    app, panel = _panel(monkeypatch, database)
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0), (TG_DIACYL, 600.0),
                            (RIVAL_WATER_LOSS, 300.0)])
    panel.set_spectrum(mz, intensity, 236.1129, "Positive")
    panel.set_components([Component(name="triacetin", precursor=236.1129,
                                    formula=RIVAL)])
    panel.explain_anything()
    assert panel.explain_tree.topLevelItem(0).text(0) == "TG 2:0/2:0/2:0"

    formula_row = next(
        panel.route_tree.topLevelItem(i)
        for i in range(panel.route_tree.topLevelItemCount())
        if panel.route_tree.topLevelItem(i).text(0) == ROUTE_FORMULA)
    panel.route_tree.setCurrentItem(formula_row)

    assert panel.explain_tree.topLevelItemCount() == 1
    assert panel.explain_tree.topLevelItem(0).text(3) == RIVAL
    assert panel.explanation_basis.startswith(f"from the formula {RIVAL}")
    assert panel.explanation_adduct == "[M+H]+"
    assert "no bonds to cut" in panel.explanation_basis
    assert f"from the formula {RIVAL}" in panel.status.text()

    panel.deleteLater()
    app.processEvents()


def test_the_database_row_keeps_its_route_when_another_candidate_is_picked(
        monkeypatch, database):
    """
    The database route hands over its whole ranked list, so selecting a
    second candidate still rewrites the adduct sentence — with the route
    still in front of it, since what is on screen came from that route.
    """
    app, panel = _panel(monkeypatch, database)
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0), (TG_DIACYL, 600.0)])
    panel.set_spectrum(mz, intensity, 236.1129, "Positive")
    panel.set_components([])
    panel.own_formula.setText("C9H14O6")
    panel.explain_anything()

    panel.explain_tree.setCurrentItem(panel.explain_tree.topLevelItem(0))
    assert panel.explanation_basis.startswith("from LIPID MAPS at 236.113")
    # and it says what was actually enumerated, not the record path's default
    assert f"up to {MAX_CUTS} bonds cut" in panel.explanation_basis
    assert f"up to {MAX_LOSSES} neutral losses" in panel.explanation_basis

    panel.deleteLater()
    app.processEvents()


def test_the_manual_routes_still_work_after_the_unified_one(monkeypatch,
                                                            database):
    """The three routes the analyst picks by hand are untouched."""
    app, panel = _panel(monkeypatch, database)
    mz, intensity = arrays([(TG_AMMONIUM, 1000.0), (TG_DIACYL, 600.0)])
    panel.set_spectrum(mz, intensity, 236.1129, "Positive")
    panel.explain_anything()
    assert panel.route_tree.isVisibleTo(panel)

    panel.own_formula.setText("C9H14O6")
    panel.explain_own()
    assert not panel.route_tree.isVisibleTo(panel)
    assert panel.explanation_basis.startswith("the precursor C9H14O6")

    panel.explain_spectrum()
    assert not panel.route_tree.isVisibleTo(panel)
    assert panel.explanation_basis.startswith("the curated structure, one bond")

    panel.deleteLater()
    app.processEvents()
