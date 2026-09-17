"""
The index as a file: what it costs to ask it a question, and what it answers.

The previous format was one gzipped JSON document, so every question about it
— including how many records it holds, which is all the panel's label wants —
meant decoding fifty thousand records and their connection tables. The file is
now a SQLite database: the count is read off a header, and `by_id`,
`search_formula` and `find_by_name` are index lookups instead of walks.

These tests are about the two things that could go wrong in moving it: an
answer that changed, and an index somebody already has that stops working.
"""

import gzip
import json
import sqlite3
import threading

import pytest

from milq import lipidmaps as lm
from milq.lipidmaps import LipidDatabase, LipidRecord
from milq.structure import Structure, parse_molblock


def _ethanol() -> str:
    """A minimal V2000 block, the way `tests/test_structure.py` writes one."""
    lines = ["ethanol", "  test", "",
             f"{3:3}{2:3}  0     0  0            999 V2000"]
    for element, x in (("C", 0.0), ("C", 1.0), ("O", 2.0)):
        lines.append(f"{x:10.4f}{0.0:10.4f}{0.0:10.4f} {element:<3} 0  0  0  0")
    for a, b in ((1, 2), (2, 3)):
        lines.append(f"{a:3}{b:3}{1:3}  0  0  0  0")
    lines.append("M  END")
    return "\n".join(lines)


def records() -> list[LipidRecord]:
    molecule = parse_molblock(_ethanol(), "C2H6O")
    return [
        LipidRecord(lm_id="LMSP03010002", name="SM(d18:1/12:0)",
                    abbrev="SM 30:1;O2", formula="C35H71N2O6P",
                    exact_mass=646.504974, main_class="Sphingomyelins",
                    structure=molecule.to_compact()),
        LipidRecord(lm_id="LMFA02000230", name="12,13-DiHOME",
                    abbrev="FA 18:1;O2", formula="C18H34O4",
                    exact_mass=314.245710),
        LipidRecord(lm_id="LMFA02000164", name="12,13-DiHOME(9)",
                    abbrev="FA 18:1;O2", formula="C18H34O4",
                    exact_mass=314.245710, structure=molecule.to_compact()),
        LipidRecord(lm_id="LMSP02010004", name="Cer(d18:1/16:0)",
                    abbrev="Cer 34:1;O2", formula="C34H67NO3",
                    exact_mass=537.512095),
    ]


@pytest.fixture(autouse=True)
def no_real_legacy_index(tmp_path, monkeypatch):
    """
    Keep the suite away from an index this machine really has.

    `is_installed` adopts one from the directory the software used before it
    was renamed, and adopting means *moving*: a test given a `tmp_path` would
    otherwise carry a real 8 MB index into it and lose it when the path went.
    """
    monkeypatch.setattr(lm, "LEGACY_INDEX_PATH",
                        tmp_path / "nowhere" / lm.JSON_INDEX_NAME)


@pytest.fixture
def held() -> LipidDatabase:
    """The database as it is built in memory, before anything is written."""
    return LipidDatabase(records())


@pytest.fixture
def stored(tmp_path) -> LipidDatabase:
    """The same records, asked through the file."""
    return LipidDatabase.load(LipidDatabase(records()).save(
        tmp_path / "index.sqlite"))


# -- the same answers -------------------------------------------------------- #
def _key(record):
    return (record.lm_id, record.name, record.abbrev, record.formula,
            record.exact_mass, record.category, record.main_class,
            record.sub_class, record.systematic_name)


@pytest.mark.parametrize("text", [
    "12,13-DiHOME", "dihome", "SM 30:1;O2", "LMSP03010002", "sm (d18:1/12:0)",
    "Cer", "e", "", "nothing like this",
])
def test_a_name_search_answers_what_the_walk_answered(held, stored, text):
    """Rank, then the shorter name, then the position: in that order."""
    assert ([_key(r) for r in stored.find_by_name(text)]
            == [_key(r) for r in held.find_by_name(text)])
    assert ([_key(r) for r in stored.find_by_name(text, limit=1)]
            == [_key(r) for r in held.find_by_name(text, limit=1)])


@pytest.mark.parametrize("mass,tolerance,unit", [
    (314.245710, 0.01, "Da"), (314.2457, 10.0, "ppm"), (646.5050, 0.5, "Da"),
    (537.512095, 0.001, "Da"), (100.0, 0.01, "Da"),
])
def test_a_mass_search_answers_in_the_same_order(held, stored, mass,
                                                 tolerance, unit):
    assert ([(_key(m.record), m.error_mda)
             for m in stored.search_mass(mass, tolerance, unit)]
            == [(_key(m.record), m.error_mda)
                for m in held.search_mass(mass, tolerance, unit)])


def test_the_element_filter_still_decides(held, stored):
    arsenic = LipidRecord(lm_id="LMFA99999999", name="Arsenolipid", abbrev="",
                          formula="C17H37OAs", exact_mass=332.209)
    held = LipidDatabase(records() + [arsenic])
    assert held.search_mass(332.209, 0.01) == []
    assert len(held.search_mass(332.209, 0.01, elements=None)) == 1


def test_by_id_and_search_formula_agree(held, stored):
    for lm_id in ("LMFA02000164", "lmfa02000164", " LMSP03010002 ", "NOPE"):
        found, expected = stored.by_id(lm_id), held.by_id(lm_id)
        assert (found and _key(found)) == (expected and _key(expected))
    for formula in ("C18H34O4", " C18H34O4 ", "C1"):
        assert ([_key(r) for r in stored.search_formula(formula)]
                == [_key(r) for r in held.search_formula(formula)])


def test_the_precursor_of_a_named_lipid_survives_the_move(stored):
    form = stored.precursor("SM(d18:1/12:0)", "[M+H]+")
    assert form.mz == pytest.approx(647.5122, abs=5e-4)
    assert form.record.lm_id == "LMSP03010002"


# -- the structures ---------------------------------------------------------- #
def test_a_molfile_comes_back_out_of_the_index(held, stored):
    for index in range(len(held)):
        expected, found = held.records[index], stored.records[index]
        assert (expected.molecule() is None) == (found.molecule() is None)
        if expected.molecule() is not None:
            assert found.molecule().to_compact() == expected.compact()
            assert isinstance(found.molecule(), Structure)


def test_the_connection_table_is_kept_deflated_and_decoded_on_demand(stored):
    """It is 51 MB of the real index and almost nothing ever reads one."""
    record = next(r for r in stored.records if r.structure)
    assert isinstance(record.structure, bytes)
    assert record.compact()["e"] == "C C O"
    assert record.molecule().formula == "C2H6O"


def test_a_record_with_no_structure_says_so(stored):
    record = stored.by_id("LMFA02000230")
    assert record.structure is None
    assert record.molecule() is None and record.compact() is None


# -- `records` still behaves like a list ------------------------------------- #
def test_the_records_are_indexable_without_being_read(stored):
    assert stored.records[0].exact_mass == pytest.approx(314.245710)
    assert stored.records[-1].lm_id == "LMSP03010002"
    assert [r.lm_id for r in stored.records[:2]] == \
        [r.lm_id for r in list(stored.records)[:2]]
    assert len(list(stored.records)) == len(stored) == 4
    with pytest.raises(IndexError):
        stored.records[99]


# -- what the file says about itself ----------------------------------------- #
def test_the_count_is_read_without_opening_the_records(tmp_path):
    path = LipidDatabase(records()).save(tmp_path / "index.sqlite")
    assert lm.record_count(path) == 4
    # and it is the header that answers, not a walk
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE records")
    assert lm.record_count(path) == 4


def test_no_index_is_not_an_index_of_nothing(tmp_path):
    assert lm.record_count(tmp_path / "absent.sqlite") is None


def test_a_file_that_is_not_an_index_answers_nothing(tmp_path):
    path = tmp_path / "index.sqlite"
    path.write_bytes(b"SQLite format 3\x00 and then nonsense")
    assert lm.record_count(path) is None


# -- an index somebody already has ------------------------------------------- #
def _write_old_index(path, rows):
    """The version-2 format: one gzipped JSON document."""
    from dataclasses import asdict

    payload = {"version": 2, "source": lm.DATABASE_URL, "count": len(rows),
               "records": [asdict(r) for r in rows]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    return path


def test_an_old_index_is_found_rather_than_downloaded_again(tmp_path):
    _write_old_index(tmp_path / lm.JSON_INDEX_NAME, records())
    assert lm.is_installed(tmp_path / "lmsd-index.sqlite")
    assert lm.record_count(tmp_path / "lmsd-index.sqlite") == 4


def test_an_old_index_is_rewritten_once_and_then_read_as_a_database(tmp_path):
    old = _write_old_index(tmp_path / lm.JSON_INDEX_NAME, records())
    new = tmp_path / "lmsd-index.sqlite"
    database = LipidDatabase.load(new)

    assert new.exists() and not old.exists()
    assert lm._is_index_database(new)
    assert len(database) == 4
    assert database.by_id("LMFA02000164").molecule().formula == "C2H6O"
    # and the second open is the database, not the document again
    assert len(LipidDatabase.load(new)) == 4


def test_an_old_index_under_the_old_cache_directory_keeps_its_name(
        tmp_path, monkeypatch):
    legacy = _write_old_index(tmp_path / "old" / lm.JSON_INDEX_NAME, records())
    monkeypatch.setattr(lm, "LEGACY_INDEX_PATH", legacy)
    target = tmp_path / "new" / "lmsd-index.sqlite"

    assert lm.is_installed(target)
    assert not legacy.exists()
    assert (target.parent / lm.JSON_INDEX_NAME).exists()
    assert len(LipidDatabase.load(target)) == 4
    assert target.exists()


def test_loading_an_index_that_is_not_there_says_so(tmp_path):
    with pytest.raises(FileNotFoundError):
        LipidDatabase.load(tmp_path / "absent.sqlite")


# -- the connection belongs to its thread ------------------------------------ #
def test_a_worker_thread_can_search(stored):
    """
    The measuring worker explains spectra off the window's thread.

    There is one connection, shared and taken in turn, rather than one per
    thread: a connection belongs to the thread that made it, so per-thread
    connections could never all be closed, and a file Windows still has open
    cannot be replaced or removed.
    """
    found = []

    def search():
        found.append(stored.find_by_name("12,13-DiHOME", limit=1)[0].lm_id)
        found.append(stored.by_id("LMSP03010002").lm_id)

    worker = threading.Thread(target=search)
    worker.start()
    worker.join()
    assert found == ["LMFA02000230", "LMSP03010002"]


# -- letting go of the file -------------------------------------------------- #
def test_closing_lets_go_of_the_file(tmp_path):
    """
    An open database is an open file, and Windows will not replace one.

    This is what `WinError 32` on the runner was: the index is rewritten in
    place on a reinstall, and a test writes one and removes it. On macOS and
    Linux removing an open file is allowed and nothing was ever noticed, so
    what is asserted here is the state rather than the removal — the removal
    would pass on this machine either way.
    """
    path = LipidDatabase(records()).save(tmp_path / "index.sqlite")
    database = LipidDatabase.load(path)
    assert database.by_id("LMFA02000230") is not None
    assert database._db is not None

    database.close()
    assert database._db is None, "the file is still open after close"
    path.unlink()                       # the point, where Windows is watching
    assert not path.exists()


def test_a_closed_database_opens_again_when_asked(stored):
    """Closing is letting go of the file, not breaking the object."""
    first = stored.by_id("LMFA02000230").name
    stored.close()
    assert stored.by_id("LMFA02000230").name == first


def test_a_database_in_memory_can_be_closed_too(stored):
    """
    Every caller closes and only one of them has anything to do.

    `LipidDatabase.load` gives back the stored kind and `LipidDatabase(...)`
    the in-memory kind, and nothing that holds one knows which it has.
    """
    plain = LipidDatabase(records())
    plain.close()
    assert len(plain) == len(stored)
    with LipidDatabase(records()) as held:
        assert len(held) == len(stored)


def test_a_worker_leaves_no_connection_behind(stored):
    """
    One connection, not one per thread.

    A `sqlite3.Connection` belongs to the thread that made it, so per-thread
    connections could never all be closed from anywhere — which is why there
    is one, taken in turn.
    """
    def search():
        stored.find_by_name("12,13-DiHOME", limit=1)

    worker = threading.Thread(target=search)
    worker.start()
    worker.join()
    stored.close()
    assert stored._db is None
