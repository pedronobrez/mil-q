"""Name plus adduct to precursor: the mass search run backwards."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore

from milq import lipidmaps
from milq.chemistry import ADDUCTS_BY_NAME
from milq.lipidmaps import LipidDatabase, LipidRecord


@pytest.fixture
def database():
    return LipidDatabase([
        LipidRecord(lm_id="LMSP03010002", name="SM(d18:1/12:0)",
                    abbrev="SM 30:1;O2", formula="C35H71N2O6P",
                    exact_mass=646.504974, main_class="Sphingomyelins"),
        LipidRecord(lm_id="LMFA02000230", name="12,13-DiHOME",
                    abbrev="FA 18:1;O2", formula="C18H34O4",
                    exact_mass=314.245710),
        LipidRecord(lm_id="LMFA02000164", name="12,13-DiHOME(9)",
                    abbrev="FA 18:1;O2", formula="C18H34O4",
                    exact_mass=314.245710),
        LipidRecord(lm_id="LMSP02010004", name="Cer(d18:1/16:0)",
                    abbrev="Cer 34:1;O2", formula="C34H67NO3",
                    exact_mass=537.512095),
    ])


# -- finding the lipid ------------------------------------------------------------ #
def test_an_exact_name_outranks_one_that_merely_contains_it(database):
    # 12,13-DiHOME(9) sits earlier in the file, and used to answer first
    found = database.find_by_name("12,13-DiHOME")
    assert [r.lm_id for r in found] == ["LMFA02000230", "LMFA02000164"]


def test_the_shorthand_and_the_lm_id_both_find_it(database):
    assert database.find_by_name("SM 30:1;O2")[0].lm_id == "LMSP03010002"
    assert database.find_by_name("LMSP03010002")[0].lm_id == "LMSP03010002"


def test_spacing_does_not_decide_the_answer(database):
    for typed in ("SM(d18:1/12:0)", "sm (d18:1/12:0)", " SM(d18:1/12:0) "):
        assert database.find_by_name(typed)[0].lm_id == "LMSP03010002"


def test_a_name_nothing_answers_to_returns_nothing(database):
    assert database.find_by_name("C16:0-Ceramide") == []


# -- the ions --------------------------------------------------------------------- #
def test_the_precursor_of_a_named_lipid(database):
    form = database.precursor("SM(d18:1/12:0)", "[M+H]+")
    assert form.adduct == "[M+H]+"
    assert form.mz == pytest.approx(647.5122, abs=5e-4)
    assert form.formula == "C35H71N2O6P"
    assert form.record.lm_id == "LMSP03010002"


def test_each_adduct_lands_where_the_arithmetic_says(database):
    record = database.find_by_name("SM(d18:1/12:0)")[0]
    forms = {f.adduct: f.mz for f in lipidmaps.ion_forms(record)}
    for adduct, expected in (("[M+H]+", 647.5122), ("[M+Na]+", 669.4942),
                             ("[M-H]-", 645.4977), ("[M+2H]2+", 324.2598)):
        assert forms[adduct] == pytest.approx(expected, abs=1e-3), adduct


def test_a_doubly_charged_ion_is_halved_not_doubled(database):
    record = database.find_by_name("SM(d18:1/12:0)")[0]
    forms = {f.adduct: f for f in lipidmaps.ion_forms(record)}
    assert forms["[M+2H]2+"].charge == 2
    assert forms["[M+2H]2+"].mz < forms["[M+H]+"].mz / 1.9


def test_the_forms_run_from_the_most_positive_down(database):
    record = database.find_by_name("Cer(d18:1/16:0)")[0]
    charges = [f.charge for f in lipidmaps.ion_forms(record)]
    assert charges == sorted(charges, reverse=True)


def test_it_is_the_exact_inverse_of_a_mass_search(database):
    """What the forward search matches is what the reverse search hands back."""
    record = database.find_by_name("Cer(d18:1/16:0)")[0]
    for name in ADDUCTS_BY_NAME:
        form = lipidmaps.ion_form(record, name)
        if form is None:
            continue
        back = database.search_mz(form.mz, name, 1.0, "ppm")
        assert record.lm_id in [m.record.lm_id for m in back], name


def test_an_unknown_adduct_gives_nothing_rather_than_a_wrong_mass(database):
    record = database.find_by_name("Cer(d18:1/16:0)")[0]
    assert lipidmaps.ion_form(record, "[M+Xe]+") is None


def test_a_record_with_no_mass_yields_no_ion():
    record = LipidRecord(lm_id="LMX", name="x", abbrev="", formula="C1",
                         exact_mass=0.0)
    assert lipidmaps.ion_form(record, "[M+H]+") is None


def test_looking_up_a_name_that_is_not_there(database):
    assert database.precursor("nothing like this", "[M+H]+") is None


# -- the panel -------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def panel(qapp, database, monkeypatch):
    from milq.ui.lipid_panel import LipidPanel

    monkeypatch.setattr(lipidmaps, "database", lambda *a, **k: database)
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    widget = LipidPanel()
    widget.refresh_availability()
    yield widget
    widget.close()


def test_looking_a_name_up_lists_the_candidates(qapp, panel):
    panel.name_edit.setText("DiHOME")
    panel.look_up_name()
    names = [panel.name_tree.topLevelItem(i).text(0)
             for i in range(panel.name_tree.topLevelItemCount())]
    assert names == ["12,13-DiHOME", "12,13-DiHOME(9)"]


def test_the_first_candidate_s_ions_are_shown_at_once(qapp, panel):
    panel.name_edit.setText("SM(d18:1/12:0)")
    panel.look_up_name()
    adducts = [panel.ion_tree.topLevelItem(i).text(0)
               for i in range(panel.ion_tree.topLevelItemCount())]
    assert "[M+H]+" in adducts and "[M-H]-" in adducts


def test_double_clicking_an_ion_hands_over_the_precursor(qapp, panel):
    seen = []
    panel.sigPrecursor.connect(lambda *args: seen.append(args))
    panel.name_edit.setText("SM(d18:1/12:0)")
    panel.look_up_name()
    row = next(panel.ion_tree.topLevelItem(i)
               for i in range(panel.ion_tree.topLevelItemCount())
               if panel.ion_tree.topLevelItem(i).text(0) == "[M+H]+")
    panel._ion_activated(row, 0)
    name, formula, lm_id, adduct, mz = seen[0]
    assert (name, formula, lm_id, adduct) == (
        "SM(d18:1/12:0)", "C35H71N2O6P", "LMSP03010002", "[M+H]+")
    assert mz == pytest.approx(647.5122, abs=5e-4)


def test_a_name_with_no_match_says_why(qapp, panel):
    panel.name_edit.setText("C16:0-Ceramide")
    panel.look_up_name()
    assert panel.ion_tree.topLevelItemCount() == 0
    # the method's own label is not a LIPID MAPS name, and saying so is the
    # difference between a dead end and a next step
    assert "shorthand" in panel.status.text()


# -- the index left behind by the rename ------------------------------------------ #
def test_an_index_under_the_old_cache_directory_is_adopted(tmp_path,
                                                           monkeypatch):
    legacy = tmp_path / "old" / "lmsd-index.json.gz"
    legacy.parent.mkdir(parents=True)
    LipidDatabase([]).save(legacy)
    target = tmp_path / "new" / "lmsd-index.json.gz"
    monkeypatch.setattr(lipidmaps, "LEGACY_INDEX_PATH", legacy)

    # a 21 MB download should not happen twice because the cache changed name
    assert lipidmaps.is_installed(target)
    assert target.exists()
    assert not legacy.exists()


def test_nothing_is_adopted_when_the_index_is_already_there(tmp_path,
                                                           monkeypatch):
    legacy = tmp_path / "old" / "lmsd-index.json.gz"
    legacy.parent.mkdir(parents=True)
    LipidDatabase([]).save(legacy)
    target = tmp_path / "new" / "lmsd-index.json.gz"
    LipidDatabase([]).save(target)
    monkeypatch.setattr(lipidmaps, "LEGACY_INDEX_PATH", legacy)

    assert not lipidmaps.adopt_legacy_index(target)
    assert legacy.exists()


def test_the_neutral_entry_is_not_offered_as_an_ion(database):
    """It exists so a neutral mass can be searched, and it is not an ion."""
    from milq.chemistry import NEUTRAL

    record = database.find_by_name("Cer(d18:1/16:0)")[0]
    assert NEUTRAL not in [f.adduct for f in lipidmaps.ion_forms(record)]
    # and it is still searchable as before
    assert lipidmaps.ion_form(record, NEUTRAL).mz == pytest.approx(537.5121,
                                                                   abs=1e-3)


# -- reaching the panel ----------------------------------------------------------- #
def test_every_panel_can_be_reached_by_name(qapp):
    """
    Eight tabs need twice the width the dock has.

    Five of them sit behind two small arrows, which is how a panel ends up
    findable by accident or not at all.
    """

    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace

    workspace = ExplorerWorkspace(Session())
    workspace.resize(1500, 800)
    workspace.show()
    qapp.processEvents()

    titles = [workspace.tabs.tabText(i) for i in range(workspace.tabs.count())]
    assert [a.text() for a in workspace.panel_actions] == titles
    assert "LIPID MAPS" in titles

    bar = workspace.tabs.tabBar()
    hidden = [t for i, t in enumerate(titles)
              if bar.tabRect(i).right() > bar.width()]
    assert hidden, "the tab bar used to fit everything; the menu may be moot"

    assert workspace.show_panel_named("LIPID MAPS")
    qapp.processEvents()
    # every panel sits in a scroller, so the tab's widget is the scroller and
    # the panel is what `showing_panel` unwraps
    assert workspace.showing_panel() is workspace.lipid_panel
    assert workspace.tabs.cornerWidget(QtCore.Qt.Corner.TopRightCorner) is not None
    workspace.close()


def test_an_unknown_panel_name_reports_rather_than_switching(qapp):
    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace

    workspace = ExplorerWorkspace(Session())
    assert not workspace.show_panel_named("Nothing")
    workspace.close()


# -- the label is a question about the file ---------------------------------- #
def test_the_panel_counts_the_index_without_opening_it(qapp, monkeypatch):
    """
    Printing "49,969 curated structures indexed locally." used to load all
    49,969 of them: 0.84 s and 570 MB of the window's startup.
    """
    from milq.ui.lipid_panel import LipidPanel

    opened = []
    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    monkeypatch.setattr(lipidmaps, "record_count", lambda *a, **k: 49969)
    monkeypatch.setattr(lipidmaps, "database",
                        lambda *a, **k: opened.append(1))

    widget = LipidPanel()
    try:
        widget.refresh_availability()
        assert widget.status.text() == \
            "49,969 curated structures indexed locally."
        assert opened == []
    finally:
        widget.close()


def test_an_index_that_will_not_say_how_many_still_says_it_is_there(qapp,
                                                                    monkeypatch):
    from milq.ui.lipid_panel import LipidPanel

    monkeypatch.setattr(lipidmaps, "is_installed", lambda *a, **k: True)
    monkeypatch.setattr(lipidmaps, "record_count", lambda *a, **k: None)
    widget = LipidPanel()
    try:
        widget.refresh_availability()
        assert widget.status.text() == "Curated structures indexed locally."
        assert widget.btn_search.isEnabled()
    finally:
        widget.close()
