"""
Local LIPID MAPS lookup.

The LIPID MAPS Structure Database is redistributed under CC BY 4.0 as a single
SDF. This module keeps a compact local index of it, so annotation works with no
network and answers a whole component table in microseconds — a batch of eighty
precursors would otherwise be eighty HTTP round trips against a public service.

The index is a SQLite file — 45 MB for 49,969 records — opened rather than
read: nothing is held in memory, and a name, an LM_ID, a formula and a mass
window are index lookups. The connection tables are most of it and almost
nothing reads one, so each is kept deflated and inflated only in
`LipidRecord.molecule()`.

What a mass search returns is a *species*, never a compound: forty-six
structures in the database share the formula of a DiHOME, eleven of them named
DiHOME, and no exact mass separates isomers. Treat every result as a shortlist
for a person to confirm.

This indexes LMSD, the curated structure database — every record has a name and
an LM_ID. LIPID MAPS also publishes COMP_DB, a computationally enumerated set of
theoretical species that covers more masses but carries no compound names, and
that is what the public `moverz/LIPIDS` endpoint searches. A mass with no hit
here may still match a theoretical species there; for naming components, the
curated database is the one worth having.

Six hundred of the fifty thousand records carry no exact mass in the published
file and are skipped: without a mass they cannot be matched, which is this
module's whole purpose.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import sqlite3
import threading
import zipfile
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from .bootstrap import CACHE_DIR, urlopen as safe_urlopen
from .chemistry import ADDUCTS, ADDUCTS_BY_NAME, NEUTRAL, Adduct
from .structure import Structure, parse_molblock

#: elements a lipid from a biological sample is built from. LMSD also holds
#: organoarsenic and fluorinated structures, which are valid entries and absurd
#: candidates for a plasma oxylipin panel; without this filter a rounded
#: precursor mass happily matches one.
BIOLOGICAL_ELEMENTS = frozenset("C H N O P S Se".split())

_ELEMENT = re.compile(r"([A-Z][a-z]?)\d*")

#: the published SDF, about 21 MB compressed
DATABASE_URL = "https://www.lipidmaps.org/files/?file=LMSD&ext=sdf.zip"
INDEX_PATH = CACHE_DIR / "lipidmaps" / "lmsd-index.sqlite"
#: the name every version before 3 used: one gzipped JSON document holding
#: fifty thousand records, which had to be decoded whole to answer anything.
#: One is read once and rewritten as the database beside it.
JSON_INDEX_NAME = "lmsd-index.json.gz"
#: where it lived before the software was renamed. A 21 MB download should not
#: have to happen twice because the cache directory changed name.
LEGACY_INDEX_PATH = Path.home() / ".openpeakview" / "lipidmaps" / JSON_INDEX_NAME
INDEX_VERSION = 3

#: SDF tags kept in the index, mapped to the field they fill
_TAGS = {
    "LM_ID": "lm_id",
    "NAME": "name",
    "SYSTEMATIC_NAME": "systematic_name",
    "ABBREVIATION": "abbrev",
    "FORMULA": "formula",
    "EXACT_MASS": "exact_mass",
    "CATEGORY": "category",
    "MAIN_CLASS": "main_class",
    "SUB_CLASS": "sub_class",
}


@dataclass(frozen=True)
class LipidRecord:
    """One structure in the database, stripped to its annotation."""

    lm_id: str
    name: str
    abbrev: str
    formula: str
    exact_mass: float
    category: str = ""
    main_class: str = ""
    sub_class: str = ""
    systematic_name: str = ""
    #: the connection table, or None for a record whose structure the file did
    #: not carry. A record built in memory holds the compact dict; one read
    #: from the index holds the bytes it is stored as, and decodes them only
    #: when somebody asks for the molecule. They are 51 MB of the index
    #: written plainly against 20 MB deflated, and almost no search reads one.
    structure: dict | str | bytes | None = field(default=None, repr=False)

    def compact(self) -> dict | None:
        """The connection table as a dict, decoded if the index stored it."""
        raw = self.structure
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, (bytes, bytearray)):
            raw = zlib.decompress(raw).decode("utf-8")
        return json.loads(raw)

    def molecule(self) -> Structure | None:
        """The structure, rebuilt from the index."""
        compact = self.compact()
        if compact is None:
            return None
        return Structure.from_compact(compact)

    @property
    def species(self) -> str:
        """The shorthand species name, falling back to the formula."""
        return self.abbrev or self.formula

    @property
    def elements(self) -> frozenset[str]:
        return frozenset(_ELEMENT.findall(self.formula))


@dataclass(frozen=True)
class LipidMatch:
    """A record matched against a measured mass."""

    record: LipidRecord
    measured: float
    theoretical: float
    adduct: str = ""

    @property
    def error_mda(self) -> float:
        return (self.measured - self.theoretical) * 1000.0

    @property
    def error_ppm(self) -> float:
        if not self.theoretical:
            return 0.0
        return (self.measured - self.theoretical) / self.theoretical * 1e6


@dataclass(frozen=True)
class IonForm:
    """
    A lipid seen through one ionisation form: the reverse of a mass search.

    The website lists these on every molecule page. They are arithmetic on the
    exact mass, so they are computed here rather than fetched: no network, and
    the answer carries the full precision of the formula instead of the four
    decimals a page prints.
    """

    record: LipidRecord
    adduct: str
    mz: float
    charge: int

    @property
    def species(self) -> str:
        return self.record.species

    @property
    def formula(self) -> str:
        return self.record.formula

    @property
    def name(self) -> str:
        return self.record.name or self.record.abbrev


@dataclass
class SpeciesMatch:
    """
    Every structure that shares one species and formula.

    Matches are grouped this way because that is the honest unit of a mass
    search: `FA 18:1;O2` is a family of isomers, and showing eleven DiHOMEs as
    eleven separate answers would imply a precision the measurement does not
    have.
    """

    species: str
    formula: str
    theoretical: float
    measured: float
    adduct: str
    records: list[LipidRecord]

    @property
    def error_mda(self) -> float:
        return (self.measured - self.theoretical) * 1000.0

    @property
    def error_ppm(self) -> float:
        if not self.theoretical:
            return 0.0
        return (self.measured - self.theoretical) / self.theoretical * 1e6

    @property
    def category(self) -> str:
        return self.records[0].category if self.records else ""

    @property
    def main_class(self) -> str:
        return self.records[0].main_class if self.records else ""

    @property
    def names(self) -> list[str]:
        return [r.name for r in self.records if r.name]


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_sdf(stream) -> list[LipidRecord]:
    """
    Read the annotation tags and the connection table out of an SDF.

    Works line by line over a text stream so the 280 MB file never has to be
    held in memory or written to disk; only one record is in hand at a time.
    """
    records: list[LipidRecord] = []
    fields: dict[str, str] = {}
    tag: str | None = None
    value: list[str] = []
    block: list[str] | None = []

    def close_tag():
        nonlocal tag, value
        if tag is not None:
            text = " ".join(part.strip() for part in value).strip()
            if text:
                fields[_TAGS[tag]] = text
        tag, value = None, []

    for raw in stream:
        line = raw.rstrip("\n").rstrip("\r")
        if block is not None:
            block.append(line)
            if line.startswith("M  END"):
                fields["molblock"] = "\n".join(block)
                block = None
            continue
        if line.startswith("> <"):
            close_tag()
            name = line[3:].split(">", 1)[0]
            tag = name if name in _TAGS else None
            continue
        if line == "$$$$":
            close_tag()
            record = _record_from(fields)
            if record is not None:
                records.append(record)
            fields = {}
            block = []
            continue
        if tag is not None:
            if line == "":
                close_tag()
            else:
                value.append(line)
    close_tag()
    record = _record_from(fields)
    if record is not None:
        records.append(record)
    return records


def _record_from(fields: dict) -> LipidRecord | None:
    lm_id = fields.get("lm_id")
    if not lm_id:
        return None
    try:
        mass = float(fields.get("exact_mass", ""))
    except ValueError:
        return None
    return LipidRecord(
        lm_id=lm_id,
        name=fields.get("name", ""),
        abbrev=fields.get("abbrev", ""),
        formula=fields.get("formula", ""),
        exact_mass=mass,
        category=fields.get("category", ""),
        main_class=fields.get("main_class", ""),
        sub_class=fields.get("sub_class", ""),
        systematic_name=fields.get("systematic_name", ""),
        structure=_compact_structure(fields),
    )


def _compact_structure(fields: dict) -> dict | None:
    """The connection table, small enough to keep for every record."""
    block = fields.get("molblock")
    if not block:
        return None
    molecule = parse_molblock(block, fields.get("formula", ""))
    return molecule.to_compact() if molecule is not None else None


# --------------------------------------------------------------------------- #
# the database
# --------------------------------------------------------------------------- #
class LipidDatabase:
    """A searchable index over the records."""

    def __init__(self, records: list[LipidRecord]):
        self.records = sorted(records, key=lambda r: r.exact_mass)
        self._masses = np.array([r.exact_mass for r in self.records],
                                dtype=np.float64)
        self._by_formula: dict[str, list[LipidRecord]] = {}
        for record in self.records:
            self._by_formula.setdefault(record.formula, []).append(record)

    def __len__(self) -> int:
        return len(self.records)

    # -- searching ------------------------------------------------------------- #
    def search_mass(self, mass: float, tolerance: float = 0.01,
                    unit: str = "Da",
                    elements: frozenset[str] | None = BIOLOGICAL_ELEMENTS,
                    ) -> list[LipidMatch]:
        """
        Records whose neutral monoisotopic mass matches, nearest first.

        `elements` restricts the answer to structures built only from those
        atoms; pass None to search everything.
        """
        if not self.records or mass <= 0:
            return []
        half = mass * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        lo = int(np.searchsorted(self._masses, mass - half, side="left"))
        hi = int(np.searchsorted(self._masses, mass + half, side="right"))
        matches = []
        for i in range(lo, hi):
            record = self.records[i]
            if elements is not None and not record.elements <= elements:
                continue
            matches.append(LipidMatch(record=record, measured=mass,
                                      theoretical=record.exact_mass))
        matches.sort(key=lambda m: abs(m.error_mda))
        return matches

    def search_mz(self, mz: float, adduct: str | Adduct = "[M-H]-",
                  tolerance: float = 0.01, unit: str = "Da",
                  elements: frozenset[str] | None = BIOLOGICAL_ELEMENTS,
                  ) -> list[LipidMatch]:
        """
        Records matching a measured m/z through an ionisation form.

        The tolerance is applied on the m/z, where it was measured, not on the
        neutral mass — for a multiply charged adduct the two differ by the
        charge.
        """
        form = ADDUCTS_BY_NAME.get(adduct) if isinstance(adduct, str) else adduct
        if form is None:
            raise KeyError(f"unknown adduct: {adduct}")
        half = mz * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        charge = abs(form.charge) or 1
        neutral = form.neutral_mass(mz)
        matches = self.search_mass(neutral, half * charge, "Da", elements)
        return [
            LipidMatch(record=m.record, measured=mz,
                       theoretical=form.mz(m.record.exact_mass),
                       adduct=form.name)
            for m in matches
        ]

    def search_formula(self, formula: str) -> list[LipidRecord]:
        return list(self._by_formula.get(formula.strip(), []))

    def search_name(self, text: str, limit: int = 50) -> list[LipidRecord]:
        """Case-insensitive substring search over names and abbreviations."""
        return self.find_by_name(text, limit)

    def find_by_name(self, text: str, limit: int = 25) -> list[LipidRecord]:
        """
        Records whose name, abbreviation or LM_ID matches, best first.

        An exact name outranks one that merely contains it: searching
        `12,13-DiHOME` should not answer `12,13-DiHOME(9)` first because it
        happens to sit earlier in the file.
        """
        needle = _squash(text)
        if not needle:
            return []
        scored: list[tuple[int, int, int, LipidRecord]] = []
        for index, record in enumerate(self.records):
            best = None
            for written in (record.name, record.abbrev, record.lm_id):
                if not written:
                    continue
                squashed = _squash(written)
                if squashed == needle:
                    rank = 0
                elif squashed.startswith(needle):
                    rank = 1
                elif needle in squashed:
                    rank = 2
                else:
                    continue
                best = rank if best is None else min(best, rank)
            if best is not None:
                # shorter names are the more specific ones at the same rank
                scored.append((best, len(record.name or record.abbrev), index,
                               record))
        scored.sort()
        return [record for _rank, _length, _index, record in scored[:limit]]

    def precursor(self, name: str, adduct: str | Adduct = "[M+H]+",
                  ) -> IonForm | None:
        """
        The m/z of the named lipid through one adduct — a mass search run
        backwards, for when the compound is known and the channel is not.
        """
        found = self.find_by_name(name, limit=1)
        return ion_form(found[0], adduct) if found else None

    def by_id(self, lm_id: str) -> LipidRecord | None:
        target = lm_id.strip().upper()
        for record in self.records:
            if record.lm_id == target:
                return record
        return None

    # -- persistence ------------------------------------------------------------ #
    def close(self) -> None:
        """
        Let go of whatever this is holding.

        Nothing, for a database built in memory. The one read off a file
        holds the file open, and Windows will not remove or replace a file
        something has open — so every caller closes, and only one of them
        has anything to do.
        """

    def __enter__(self) -> "LipidDatabase":
        return self

    def __exit__(self, *_exception) -> None:
        self.close()

    def save(self, path: str | os.PathLike = INDEX_PATH) -> Path:
        return _write_index(self.records, path)

    @classmethod
    def load(cls, path: str | os.PathLike = INDEX_PATH) -> "LipidDatabase":
        """
        The index on disk, opened rather than read.

        An index in the format before version 3 — one gzipped JSON document —
        is read once, written out as the database, and then opened the same
        way, so nobody downloads fifty thousand structures twice.
        """
        path = Path(path)
        source = path if path.exists() else old_format_index(path)
        if source is None:
            raise FileNotFoundError(path)
        if not _is_index_database(source):
            _write_index(_read_json_index(source), path)
            if source != path:
                source.unlink(missing_ok=True)
        return _StoredDatabase(path)


def _squash(text: str) -> str:
    """
    Compare names without tripping over spacing.

    LIPID MAPS writes `SM 30:1;O2` where a method writes `SM(d18:1/12:0)`;
    neither should fail to match itself over a stray space.
    """
    return "".join(text.split()).casefold()


# --------------------------------------------------------------------------- #
# the index on disk
# --------------------------------------------------------------------------- #
# One SQLite file, opened and never read whole. The format before this was a
# gzipped JSON document, and answering *any* question about it — including how
# many records it holds — meant decoding all fifty thousand: 0.74 s and 591 MB
# of resident memory, most of it the connection tables nothing had asked for.
#
# The columns are the record's own fields, in the order the dataclass declares
# them, so a row is a record positionally and nothing has to be renamed. `id`
# is the position in mass order, which is the order the previous index's list
# had, so every search answers in the order it answered before.
_COLUMNS = ("lm_id, name, abbrev, formula, exact_mass, category, main_class, "
            "sub_class, systematic_name, structure")

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE records (
    id INTEGER PRIMARY KEY,
    lm_id TEXT NOT NULL, name TEXT NOT NULL, abbrev TEXT NOT NULL,
    formula TEXT NOT NULL, exact_mass REAL NOT NULL, category TEXT NOT NULL,
    main_class TEXT NOT NULL, sub_class TEXT NOT NULL,
    systematic_name TEXT NOT NULL, structure BLOB,
    sort_length INTEGER NOT NULL);
CREATE TABLE names (squashed TEXT NOT NULL, record INTEGER NOT NULL);
"""

_INDEXES = """
CREATE INDEX records_mass ON records(exact_mass);
CREATE INDEX records_lm_id ON records(lm_id);
CREATE INDEX records_formula ON records(formula);
CREATE INDEX names_squashed ON names(squashed);
"""


def _stored_structure(record: LipidRecord) -> bytes | None:
    """
    The connection table as the index keeps it: deflated JSON.

    The tables are 51 MB of the index written plainly and 20 MB deflated, and
    a search that never calls `molecule()` never pays to inflate one.
    """
    raw = record.structure
    if not raw:
        return None
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    text = raw if isinstance(raw, str) else json.dumps(raw,
                                                       separators=(",", ":"))
    return zlib.compress(text.encode("utf-8"), 6)


def _searchable(record: LipidRecord) -> list[str]:
    """The three fields `find_by_name` matches on, squashed."""
    return list(dict.fromkeys(
        _squash(written)
        for written in (record.name, record.abbrev, record.lm_id) if written))


def _write_index(records, path: str | os.PathLike = INDEX_PATH) -> Path:
    """Write the records out as the index, through a scratch file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Windows refuses to replace a file something still has open, and a
    # reinstall is exactly when the index is open
    if getattr(_CACHED, "path", None) == path:
        forget()
    scratch = path.with_name(path.name + ".building")
    scratch.unlink(missing_ok=True)
    ordered = sorted(records, key=lambda r: r.exact_mass)
    connection = sqlite3.connect(scratch)
    try:
        connection.executescript("PRAGMA journal_mode=OFF;"
                                 "PRAGMA synchronous=OFF;" + _SCHEMA)
        connection.executemany(
            "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ((index, r.lm_id, r.name, r.abbrev, r.formula, r.exact_mass,
              r.category, r.main_class, r.sub_class, r.systematic_name,
              _stored_structure(r), len(r.name or r.abbrev))
             for index, r in enumerate(ordered)))
        connection.executemany(
            "INSERT INTO names VALUES (?,?)",
            ((squashed, index) for index, r in enumerate(ordered)
             for squashed in _searchable(r)))
        connection.executescript(_INDEXES)
        connection.executemany("INSERT INTO meta VALUES (?,?)", [
            ("version", str(INDEX_VERSION)),
            ("source", DATABASE_URL),
            ("count", str(len(ordered))),
        ])
        connection.commit()
    finally:
        connection.close()
    scratch.replace(path)
    return path


def _read_json_index(path: Path) -> list[LipidRecord]:
    """Every record of an index written before version 3."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    known = LipidRecord.__dataclass_fields__
    return [LipidRecord(**{k: v for k, v in row.items() if k in known})
            for row in payload.get("records", [])]


def _is_index_database(path: Path) -> bool:
    """Whether the file is a SQLite database rather than the old document."""
    try:
        with open(path, "rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _open_read_only(path: Path) -> sqlite3.Connection:
    """
    The index, read-only, usable from any thread.

    `check_same_thread=False` because there is one connection and the
    measuring worker searches off the window's thread; `_StoredDatabase`
    takes a lock around every statement, which is what makes that safe.
    """
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)


class _StoredRecords(Sequence):
    """
    The records in mass order, read one at a time.

    `LipidDatabase.records` used to be a list and some callers index it; this
    keeps that working without the list ever existing.
    """

    def __init__(self, database: "_StoredDatabase"):
        self._database = database

    def __len__(self) -> int:
        return len(self._database)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        position = index + len(self) if index < 0 else index
        record = self._database.at(position)
        if record is None:
            raise IndexError(index)
        return record

    def __iter__(self):
        return iter(self._database.all())


class _StoredDatabase(LipidDatabase):
    """
    The database backed by the file: nothing is held but a connection.

    Every method answers what `LipidDatabase`'s answers, in the same order —
    `tests/test_lipidmaps_index.py` runs both over the installed index and
    compares record for record.
    """

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = _open_read_only(self.path)
        row = self.query("SELECT value FROM meta WHERE key='count'")
        self._count = int(row[0][0]) if row else self.query(
            "SELECT COUNT(*) FROM records")[0][0]
        self.records = _StoredRecords(self)

    # -- the connection -------------------------------------------------------- #
    # One connection, shared by every thread and taken in turn.
    #
    # It was one connection per thread, which is the usual advice, and it is
    # wrong here for a reason Windows enforces and nothing else does: a
    # connection belongs to the thread that made it, so `close` could only
    # ever close the calling thread's, and a file Windows still has open
    # cannot be deleted or replaced. The measuring worker searches the
    # library off the window's thread, so a reinstall — or a test that
    # writes an index and removes it — failed with `WinError 32` on the
    # runner and silently worked everywhere else. A read takes a millisecond
    # at most, so taking turns costs nothing worth measuring.
    def query(self, sql: str, parameters=()) -> list:
        with self._lock:
            if self._db is None:
                self._db = _open_read_only(self.path)
            return self._db.execute(sql, parameters).fetchall()

    def close(self) -> None:
        """Let go of the file, so it can be replaced or removed."""
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def __enter__(self) -> "_StoredDatabase":
        return self

    def __exit__(self, *_exception) -> None:
        self.close()

    # -- reading rows ---------------------------------------------------------- #
    def _rows(self, where: str, parameters=()) -> list[LipidRecord]:
        return [LipidRecord(*row) for row in self.query(
            f"SELECT {_COLUMNS} FROM records {where}", parameters)]

    def at(self, position: int) -> LipidRecord | None:
        if not 0 <= position < self._count:
            return None
        found = self._rows("WHERE id = ?", (position,))
        return found[0] if found else None

    def all(self) -> list[LipidRecord]:
        return self._rows("ORDER BY id")

    def __len__(self) -> int:
        return self._count

    # -- searching ------------------------------------------------------------- #
    def search_mass(self, mass: float, tolerance: float = 0.01,
                    unit: str = "Da",
                    elements: frozenset[str] | None = BIOLOGICAL_ELEMENTS,
                    ) -> list[LipidMatch]:
        if not self._count or mass <= 0:
            return []
        half = mass * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        matches = [LipidMatch(record=record, measured=mass,
                              theoretical=record.exact_mass)
                   for record in self._rows(
                       "WHERE exact_mass BETWEEN ? AND ? ORDER BY id",
                       (mass - half, mass + half))
                   if elements is None or record.elements <= elements]
        matches.sort(key=lambda m: abs(m.error_mda))
        return matches

    def search_formula(self, formula: str) -> list[LipidRecord]:
        return self._rows("WHERE formula = ? ORDER BY id", (formula.strip(),))

    def by_id(self, lm_id: str) -> LipidRecord | None:
        found = self._rows("WHERE lm_id = ? ORDER BY id LIMIT 1",
                           (lm_id.strip().upper(),))
        return found[0] if found else None

    def find_by_name(self, text: str, limit: int = 25) -> list[LipidRecord]:
        needle = _squash(text)
        if not needle:
            return []
        rows = self._ranked(needle, limit, leading_only=True)
        # a leading match always outranks a match in the middle of a name, so
        # once enough of them are in hand the scan over every name — the one
        # part of this that is not an index lookup — cannot change the answer
        if len(rows) < limit:
            rows = self._ranked(needle, limit, leading_only=False)
        return [self.at(record) for record, _rank, _length in rows]

    def _ranked(self, needle: str, limit: int, leading_only: bool):
        if leading_only:
            ceiling = _above(needle)
            if ceiling is None:
                return []
            rank = "MIN(CASE WHEN n.squashed = :needle THEN 0 ELSE 1 END)"
            where = "n.squashed >= :needle AND n.squashed < :ceiling"
            parameters = {"needle": needle, "ceiling": ceiling, "limit": limit}
        else:
            rank = ("MIN(CASE WHEN n.squashed = :needle THEN 0 "
                    "WHEN substr(n.squashed, 1, :length) = :needle THEN 1 "
                    "ELSE 2 END)")
            where = "instr(n.squashed, :needle) > 0"
            parameters = {"needle": needle, "length": len(needle),
                          "limit": limit}
        return self.query(
            f"SELECT n.record, {rank} AS rank, r.sort_length "
            f"FROM names n JOIN records r ON r.id = n.record WHERE {where} "
            "GROUP BY n.record ORDER BY rank, r.sort_length, n.record "
            "LIMIT :limit", parameters)

    # -- persistence ------------------------------------------------------------ #
    def save(self, path: str | os.PathLike = INDEX_PATH) -> Path:
        path = Path(path)
        if path == self.path:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(path)
        try:
            with self._lock:
                if self._db is None:
                    self._db = _open_read_only(self.path)
                self._db.backup(target)
        finally:
            target.close()
        return path


def _above(text: str) -> str | None:
    """
    The smallest string that sorts after everything starting with `text`.

    SQLite compares text byte by byte, so raising the last character by one
    bounds the prefix range and lets the index answer it.
    """
    if not text:
        return None
    last = ord(text[-1])
    if last >= 0x10FFFF:
        return None
    return text[:-1] + chr(last + 1)


def ion_form(record: LipidRecord, adduct: str | Adduct) -> IonForm | None:
    """The m/z a record would be seen at through one adduct."""
    form = ADDUCTS_BY_NAME.get(adduct) if isinstance(adduct, str) else adduct
    if form is None or not record.exact_mass:
        return None
    return IonForm(record=record, adduct=form.name,
                   mz=form.mz(record.exact_mass), charge=form.charge)


def ion_forms(record: LipidRecord,
              adducts: list[str] | None = None) -> list[IonForm]:
    """
    Every adduct's m/z for one record, positive first then negative.

    The neutral entry is left out: it exists so a neutral mass can be searched
    as if it were an ion, and it is not one. The neutral mass belongs to the
    lipid, and is on the record.
    """
    names = (adducts if adducts is not None
             else [a.name for a in ADDUCTS if a.name != NEUTRAL])
    forms = [ion_form(record, name) for name in names]
    found = [f for f in forms if f is not None]
    found.sort(key=lambda f: (-f.charge, f.mz))
    return found


def mass_precision(value: float, text: str | None = None) -> float:
    """
    How well a written mass is actually known, as a half-width in Da.

    A precursor recorded as `351.20` is known to ±0.005 Da — about 14 ppm at
    that mass. Searching it to 5 ppm claims a precision the number does not
    carry, and the window then fills with whatever happens to sit nearby.
    """
    text = text if text is not None else repr(float(value))
    if "." not in text:
        return 0.5
    # trailing zeros in a written mass are significant: 351.20 says two
    # decimals were measured, and stripping them would overstate the window
    decimals = len(text.split(".")[1])
    return 0.5 * 10 ** (-decimals) if decimals else 0.5


def group_by_species(matches: list[LipidMatch]) -> list[SpeciesMatch]:
    """Collapse structure matches into the species they belong to."""
    buckets: dict[tuple[str, str], SpeciesMatch] = {}
    order: list[tuple[str, str]] = []
    for match in matches:
        key = (match.record.species, match.record.formula)
        if key not in buckets:
            buckets[key] = SpeciesMatch(
                species=match.record.species, formula=match.record.formula,
                theoretical=match.theoretical, measured=match.measured,
                adduct=match.adduct, records=[],
            )
            order.append(key)
        buckets[key].records.append(match.record)
    groups = [buckets[key] for key in order]
    groups.sort(key=lambda g: (abs(g.error_mda), -len(g.records)))
    return groups


# --------------------------------------------------------------------------- #
# installation
# --------------------------------------------------------------------------- #
def adopt_legacy_index(path: str | os.PathLike = INDEX_PATH) -> bool:
    """
    Move an index left behind under the old cache directory.

    Returns True when one was adopted. Falling back to reading it in place
    would work too, but moving it means the answer stops depending on a
    directory named after software that no longer exists.
    """
    target = Path(path)
    if target.exists() or not LEGACY_INDEX_PATH.exists():
        return False
    # what is under the old directory is in the old format, so it keeps that
    # name here and `load` rewrites it as the database on first use
    destination = target.parent / LEGACY_INDEX_PATH.name
    if destination.exists():
        return False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        LEGACY_INDEX_PATH.replace(destination)
    except OSError:
        return False
    return True


def old_format_index(path: str | os.PathLike = INDEX_PATH) -> Path | None:
    """
    An index written before version 3, to be migrated rather than downloaded.

    Beside where the database belongs, and then under the cache directory the
    software used before it was renamed.
    """
    path = Path(path)
    for candidate in (path.parent / JSON_INDEX_NAME, LEGACY_INDEX_PATH):
        if candidate != path and candidate.exists():
            return candidate
    return None


def is_installed(path: str | os.PathLike = INDEX_PATH) -> bool:
    if Path(path).exists():
        return True
    if adopt_legacy_index(path):
        return True
    return old_format_index(path) is not None


def record_count(path: str | os.PathLike = INDEX_PATH) -> int | None:
    """
    How many records the installed index holds, without reading them.

    The panel's label is a question about the *file*, and answering it by
    loading fifty thousand connection tables cost the window 0.84 s and
    570 MB. None when there is no index, or when one is there and does not
    say — which is not the same as an index of nothing.
    """
    path = Path(path)
    source = path if path.exists() else old_format_index(path)
    if source is None:
        return None
    if _is_index_database(source):
        try:
            connection = _open_read_only(source)
        except (sqlite3.Error, OSError, ValueError):
            return None
        try:
            row = connection.execute(
                "SELECT value FROM meta WHERE key='count'").fetchone()
            if row is not None:
                return int(row[0])
            return int(connection.execute(
                "SELECT COUNT(*) FROM records").fetchone()[0])
        except (sqlite3.Error, ValueError):
            return None
        finally:
            connection.close()
    return _json_index_count(source)


def _json_index_count(path: Path) -> int | None:
    """The `count` an old index writes before its records, off the front."""
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            head = handle.read(4096)
    except OSError:
        return None
    found = re.search(r'"count"\s*:\s*(\d+)', head)
    return int(found.group(1)) if found else None


def build_index(zip_bytes: bytes,
                path: str | os.PathLike = INDEX_PATH) -> LipidDatabase:
    """Parse the downloaded archive and write the index."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".sdf")]
        if not names:
            raise ValueError("the archive contains no .sdf file")
        with archive.open(names[0]) as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            records = parse_sdf(stream)
    if not records:
        raise ValueError("no records found in the database")
    # written straight out and reopened, so the parsed list — 600 MB of
    # connection tables — is dropped rather than kept for the session
    _write_index(records, path)
    records.clear()
    return LipidDatabase.load(path)


def install(path: str | os.PathLike = INDEX_PATH, progress=None) -> LipidDatabase:
    """
    Download the database and build the local index.

    `progress` is called with a short status line, so a caller can report what
    is happening during a download of about twenty megabytes.
    """
    if progress:
        progress("Downloading the LIPID MAPS database…")
    try:
        payload = safe_urlopen(DATABASE_URL).read()
    except Exception:
        with urlopen(DATABASE_URL) as response:
            payload = response.read()
    if progress:
        progress("Building the local index…")
    database = build_index(payload, path)
    if progress:
        progress(f"{len(database):,} lipid structures indexed.")
    return database


_CACHED: LipidDatabase | None = None


def database(path: str | os.PathLike = INDEX_PATH) -> LipidDatabase | None:
    """The installed database, loaded once, or None when it is not installed."""
    global _CACHED
    if _CACHED is None and is_installed(path):
        _CACHED = LipidDatabase.load(path)
    return _CACHED


def forget() -> None:
    """Drop the cached database; the next call reopens it from disk."""
    global _CACHED
    if isinstance(_CACHED, _StoredDatabase):
        _CACHED.close()
    _CACHED = None
