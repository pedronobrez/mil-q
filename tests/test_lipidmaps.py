"""Tests for the local LIPID MAPS index."""

import io
import sqlite3
import zipfile

import pytest

from milq import lipidmaps as lm

SDF = """\

  Mrv  

  1  0  0  0  0  0
M  END
> <LM_ID>
LMFA02000164

> <NAME>
12,13-DiHOME(9)

> <ABBREVIATION>
FA 18:1;O2

> <FORMULA>
C18H34O4

> <EXACT_MASS>
314.245711

> <CATEGORY>
Fatty Acyls [FA]

> <MAIN_CLASS>
Octadecanoids [FA02]

$$$$

M  END
> <LM_ID>
LMFA02000161

> <NAME>
9,10-DiHOME(12)

> <ABBREVIATION>
FA 18:1;O2

> <FORMULA>
C18H34O4

> <EXACT_MASS>
314.245711

$$$$

M  END
> <LM_ID>
LMFA02000999

> <NAME>
A nearby species

> <ABBREVIATION>
FA 17:2;O3

> <FORMULA>
C17H30O5

> <EXACT_MASS>
314.209324

$$$$

M  END
> <LM_ID>
LMFA99999999

> <NAME>
Arsenolipid

> <ABBREVIATION>
As 17:0

> <FORMULA>
C17H37OAs

> <EXACT_MASS>
332.209000

$$$$

M  END
> <LM_ID>
LMFA00000000

> <NAME>
No mass here

> <FORMULA>
C10H20

$$$$
"""


@pytest.fixture
def database():
    return lm.LipidDatabase(lm.parse_sdf(io.StringIO(SDF)))


# --- parsing ------------------------------------------------------------------- #
def test_parser_reads_the_annotation_tags(database):
    assert len(database) == 4          # the record with no mass is skipped
    record = database.by_id("LMFA02000164")
    assert record.name == "12,13-DiHOME(9)"
    assert record.abbrev == "FA 18:1;O2"
    assert record.formula == "C18H34O4"
    assert record.exact_mass == pytest.approx(314.245711)
    assert record.main_class == "Octadecanoids [FA02]"


def test_records_without_a_mass_are_skipped(database):
    assert database.by_id("LMFA00000000") is None


def test_species_falls_back_to_the_formula():
    record = lm.LipidRecord("X", "n", "", "C10H20", 140.0)
    assert record.species == "C10H20"


def test_elements_are_read_from_the_formula():
    assert lm.LipidRecord("X", "n", "", "C17H37OAs", 1.0).elements == \
        frozenset({"C", "H", "O", "As"})


# --- searching ------------------------------------------------------------------ #
def test_mass_search_finds_the_isomers(database):
    matches = database.search_mass(314.2457, 0.01)
    assert len(matches) == 2
    assert {m.record.lm_id for m in matches} == {"LMFA02000164", "LMFA02000161"}


def test_mz_search_through_an_adduct(database):
    matches = database.search_mz(313.2384, "[M-H]-", 0.01)
    assert len(matches) == 2
    assert matches[0].adduct == "[M-H]-"
    assert abs(matches[0].error_ppm) < 1.0


def test_ppm_tolerance_is_applied_on_the_mz(database):
    assert database.search_mz(313.2384, "[M-H]-", 5, "ppm")
    assert not database.search_mz(313.30, "[M-H]-", 5, "ppm")


def test_unknown_adduct_is_refused(database):
    with pytest.raises(KeyError):
        database.search_mz(313.0, "[M+Xe]+", 0.01)


def test_element_filter_drops_implausible_structures(database):
    """An organoarsenic lipid is a valid record and an absurd candidate."""
    everything = database.search_mass(332.209, 0.01, elements=None)
    biological = database.search_mass(332.209, 0.01)
    assert [m.record.lm_id for m in everything] == ["LMFA99999999"]
    assert biological == []


def test_formula_and_name_search(database):
    assert len(database.search_formula("C18H34O4")) == 2
    assert database.search_name("dihome")[0].lm_id.startswith("LMFA")
    assert database.search_name("") == []


# --- grouping --------------------------------------------------------------------- #
def test_matches_group_into_one_species(database):
    groups = lm.group_by_species(database.search_mz(313.2384, "[M-H]-", 0.01))
    assert len(groups) == 1
    group = groups[0]
    assert group.species == "FA 18:1;O2"
    assert len(group.records) == 2
    assert sorted(group.names) == ["12,13-DiHOME(9)", "9,10-DiHOME(12)"]


def test_grouping_orders_by_mass_error(database):
    matches = database.search_mass(314.2457, 0.05, elements=None)
    groups = lm.group_by_species(matches)
    errors = [abs(g.error_mda) for g in groups]
    assert errors == sorted(errors)


# --- precision -------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("351.20", 0.005),
    ("351.2", 0.05),
    ("313.2384", 0.00005),
    ("313", 0.5),
])
def test_mass_precision_follows_the_written_decimals(text, expected):
    assert lm.mass_precision(float(text), text) == pytest.approx(expected)


def test_trailing_zeros_count_as_measured():
    """351.20 says two decimals were measured; 351.2 says one."""
    assert lm.mass_precision(351.2, "351.20") < lm.mass_precision(351.2, "351.2")


# --- persistence -------------------------------------------------------------------- #
def test_index_round_trip(database, tmp_path):
    path = tmp_path / "index.sqlite"
    database.save(path)
    back = lm.LipidDatabase.load(path)
    assert len(back) == len(database)
    assert back.by_id("LMFA02000164").name == "12,13-DiHOME(9)"


def test_the_index_is_a_database(database, tmp_path):
    path = tmp_path / "index.sqlite"
    database.save(path)
    with sqlite3.connect(path) as connection:
        assert dict(connection.execute("SELECT key, value FROM meta")) == {
            "version": str(lm.INDEX_VERSION), "source": lm.DATABASE_URL,
            "count": "4"}
        # mass order, so the row number is the position the list used to have
        masses = [m for (m,) in connection.execute(
            "SELECT exact_mass FROM records ORDER BY id")]
        assert masses == sorted(masses)


def test_build_index_from_an_archive(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("structures.sdf", SDF)
    path = tmp_path / "index.sqlite"
    database = lm.build_index(buffer.getvalue(), path)
    assert len(database) == 4
    assert path.exists()


def test_archive_without_an_sdf_is_refused(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "nothing here")
    with pytest.raises(ValueError, match="no .sdf"):
        lm.build_index(buffer.getvalue(), tmp_path / "i.sqlite")


def test_is_installed_reports_a_missing_index(tmp_path, monkeypatch):
    # not the one this machine may really have under the old cache directory:
    # adopting moves it, and a tmp_path is thrown away afterwards
    monkeypatch.setattr(lm, "LEGACY_INDEX_PATH", tmp_path / "nowhere.json.gz")
    assert not lm.is_installed(tmp_path / "absent.sqlite")


# --- batch proposals ------------------------------------------------------------- #
def test_proposals_refuse_to_guess_at_nominal_precision(database, monkeypatch):
    """
    A precursor written to one decimal is known to ±50 mDa. Several species fit
    a window that wide, so nothing is offered for automatic naming.
    """
    from milq.components import Component
    from milq.ui.annotate_dialog import propose

    monkeypatch.setattr(lm, "database", lambda *a, **k: database)
    [proposal] = propose([Component("313.2", 313.2)])
    assert proposal.window_mda == pytest.approx(50.0)
    assert proposal.species_count == 2     # two species fit a window that wide
    assert not proposal.has_match          # so nothing is offered
    assert "needs an accurate mass" in proposal.note


def test_an_accurate_mass_gives_an_unambiguous_species(database, monkeypatch):
    from milq.components import Component
    from milq.ui.annotate_dialog import propose

    monkeypatch.setattr(lm, "database", lambda *a, **k: database)
    [proposal] = propose([Component("313.2384", 313.2384)])
    assert proposal.species_count == 1
    assert proposal.species == "FA 18:1;O2"
    assert proposal.structures == 2        # still two isomers behind it
    assert not proposal.lm_id              # so no single identifier is claimed


def test_named_components_are_left_alone(database, monkeypatch):
    from milq.components import Component
    from milq.ui.annotate_dialog import propose

    monkeypatch.setattr(lm, "database", lambda *a, **k: database)
    named = Component("12,13-DiHOME", 313.2384)
    assert propose([named]) == []
    assert len(propose([named], only_unnamed=False)) == 1


def test_no_database_gives_no_proposals(monkeypatch):
    from milq.components import Component
    from milq.ui.annotate_dialog import propose

    monkeypatch.setattr(lm, "database", lambda *a, **k: None)
    assert propose([Component("313.2", 313.2)]) == []
