"""The fragments tab: the list, the drawing, and what it refuses to claim."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PyQt6 import QtGui, QtWidgets

from milq import lipidmaps
from milq.lipidmaps import LipidDatabase, LipidRecord
from milq.structure import parse_molblock
from milq.ui import style
from milq.ui.lipid_panel import ROLE_ION, LipidPanel
from milq.ui.structure_view import StructureView

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.apply(app)
    yield app


@pytest.fixture
def database():
    def record(lm_id, name, formula, fixture, mass):
        molecule = parse_molblock((FIXTURES / f"{fixture}.mol").read_text(),
                                  formula)
        return LipidRecord(lm_id=lm_id, name=name, abbrev="", formula=formula,
                           exact_mass=mass, structure=molecule.to_compact())

    return LipidDatabase([
        record("LMST04010001", "Cholic acid", "C24H40O5", "LMST04010001",
               408.287574),
        record("LMSP03010002", "SM(d18:1/12:0)", "C35H71N2O6P", "LMSP03010002",
               646.504974),
        LipidRecord(lm_id="LMX", name="No structure", abbrev="",
                    formula="C2H6O", exact_mass=46.0),
    ])


@pytest.fixture
def panel(qapp, database, monkeypatch):
    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: database)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    widget = LipidPanel()
    widget.refresh_availability()
    widget.resize(460, 900)
    yield widget
    widget.close()


def rows(panel):
    return [panel.frag_tree.topLevelItem(i)
            for i in range(panel.frag_tree.topLevelItemCount())]


# -- the list --------------------------------------------------------------- #
def test_predicting_fills_the_list_and_draws_the_molecule(qapp, panel):
    panel.set_fragment_target("Cholic acid")
    assert rows(panel)
    assert panel.structure_view._structure is not None
    assert "ion(s)" in panel.status.text()


def test_a_mass_being_checked_narrows_it_to_that_mass(qapp, panel):
    panel.frag_target.setText("391.2843")
    panel.set_fragment_target("Cholic acid")
    assert len(rows(panel)) == 1
    assert rows(panel)[0].text(0) == "391.2843"


def test_the_limits_needed_are_reported_rather_than_an_empty_list(qapp, panel):
    panel.frag_cuts.setValue(1)
    panel.frag_losses.setValue(0)
    panel.frag_target.setText("355.2632")          # cholic acid, three waters
    panel.set_fragment_target("Cholic acid")
    assert not rows(panel)
    assert "reachable with" in panel.status.text()
    assert "losses ≤ 2" in panel.status.text()


def test_a_mass_nothing_reaches_says_so(qapp, panel):
    panel.frag_target.setText("999.9999")
    panel.set_fragment_target("Cholic acid")
    assert not rows(panel)
    assert "No combination" in panel.status.text()


def test_widening_the_limits_produces_more(qapp, panel):
    panel.frag_losses.setValue(0)
    panel.set_fragment_target("Cholic acid")
    narrow = len(rows(panel))
    panel.frag_losses.setValue(2)
    panel.predict_fragments()
    assert len(rows(panel)) > narrow


def test_a_negative_scan_gives_different_masses(qapp, panel):
    panel.set_fragment_target("Cholic acid")
    positive = [r.text(0) for r in rows(panel)]
    panel.frag_polarity.setCurrentText("negative")
    panel.predict_fragments()
    assert [r.text(0) for r in rows(panel)] != positive


def test_a_lipid_with_no_structure_says_so_rather_than_showing_nothing(qapp,
                                                                       panel):
    panel.set_fragment_target("No structure")
    assert not rows(panel)
    assert "no structure" in panel.status.text().lower()


# -- what it refuses to claim ------------------------------------------------ #
def test_the_route_is_labelled_as_arithmetic_not_mechanism(qapp, panel):
    note = panel.frag_note.text()
    assert "the simplest one that reaches it" in note
    assert "Rivals" in note
    assert "measured product spectrum" in note


def test_sending_a_fragment_on_repeats_the_caveat(qapp, panel):
    seen = []
    panel.sigFragment.connect(lambda *args: seen.append(args))
    panel.set_fragment_target("Cholic acid")
    panel._fragment_activated(rows(panel)[0], 0)
    name, lm_id, route, mz = seen[0]
    assert name == "Cholic acid" and lm_id == "LMST04010001"
    assert mz > 0
    assert "not a mechanism" in panel.status.text()


# -- the drawing ------------------------------------------------------------- #
def test_the_drawing_survives_having_nothing_to_draw(qapp):
    view = StructureView()
    view.resize(200, 150)
    view.set_structure(None)
    view.grab()          # would raise if paintEvent could not cope
    view.close()


def test_selecting_a_row_marks_the_bond_it_would_break(qapp, panel):
    panel.set_fragment_target("Cholic acid")
    panel.frag_tree.setCurrentItem(rows(panel)[0])
    fragment = panel.structure_view._fragment
    assert fragment is not None
    assert fragment.atoms
    assert rows(panel)[0].data(0, ROLE_ION).fragment is fragment


def test_the_drawing_puts_something_on_the_canvas(qapp, panel):
    panel.set_fragment_target("Cholic acid")
    view = panel.structure_view
    view.resize(300, 220)
    qapp.processEvents()
    image = view.grab().toImage()
    background = QtGui.QColor(style.token("surface")).rgb()
    painted = sum(1 for x in range(0, image.width(), 3)
                  for y in range(0, image.height(), 3)
                  if image.pixel(x, y) != background)
    assert painted > 50, "the molecule did not reach the canvas"


# -- explaining a spectrum ---------------------------------------------------- #
def test_the_precursor_window_is_the_isolation_width_not_a_few_ppm(qapp, panel):
    """
    A method's own precursor is rounded — 538.6 for a ceramide whose precursor
    is 538.52 — and the quadrupole passed a window rather than a mass.
    """
    import numpy as np

    from milq.matching import PRECURSOR_MATCH_DA

    mz = np.array([391.2843, 373.2737, 355.2632])
    intensity = np.array([1000.0, 500.0, 200.0])
    panel.set_spectrum(mz, intensity, 409.6)      # rounded, 0.3 Da out
    panel.explain_spectrum()
    assert PRECURSOR_MATCH_DA >= 0.5
    assert panel.explain_tree.topLevelItemCount() >= 1


def test_the_candidates_are_listed_with_what_they_explain(qapp, panel):
    import numpy as np

    panel.set_spectrum(np.array([391.2843, 373.2737]),
                       np.array([1000.0, 500.0]), 409.2948)
    panel.explain_spectrum()
    top = panel.explain_tree.topLevelItem(0)
    assert top.text(0) == "Cholic acid"
    assert top.text(1).endswith("%")
    assert int(top.text(2)) >= 1


def test_selecting_a_candidate_marks_its_peaks_on_the_spectrum(qapp, panel):
    import numpy as np

    marked = []
    panel.sigMatches.connect(lambda pairs: marked.append(pairs))
    panel.set_spectrum(np.array([391.2843, 373.2737]),
                       np.array([1000.0, 500.0]), 409.2948)
    panel.explain_spectrum()
    assert marked and marked[-1]
    assert all(len(pair) == 2 for pair in marked[-1])


def test_a_near_tie_between_candidates_is_said_out_loud(qapp, panel):
    """Isomers fragment alike; presenting the top one alone would overclaim."""
    import numpy as np

    panel.set_spectrum(np.array([391.2843]), np.array([1000.0]), 409.2948)
    panel.explain_spectrum()
    if panel.explain_tree.topLevelItemCount() > 1:
        assert "about as well" in panel.status.text()


def test_a_precursor_nothing_matches_says_what_window_it_looked_in(qapp, panel):
    import numpy as np

    panel.set_spectrum(np.array([100.0]), np.array([1.0]), 12345.0)
    panel.explain_spectrum()
    assert not panel.explain_tree.topLevelItemCount()
    assert "±" in panel.status.text()


def test_the_share_is_called_evidence_and_not_proof(qapp, panel):
    note = panel.explain_note.text()
    assert "not proof" in note
    assert "unexplained" in note
