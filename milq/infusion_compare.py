"""
Two days of infusions of the same standards, side by side.

`batches.py` puts two chromatographic batches of one method next to each
other and asks what moved. This asks the same question of a tray of
infusions: the vials sprayed this morning against the ones sprayed the day
the method was written, compound by compound and *condition by condition* —
a spectrum measured at 22 eV EAD is compared with the reference's 22 eV EAD
and with nothing else, for the reason `standard_history.py` cuts a history
into series at all. Scoring across activations measures the method.

The reference is read from its project file and no raw file is opened. That
needs the project to have saved something to read, which it did not until
this module: `summary_to_dict` writes the figures of an
`infusion_report.InfusionSummary` **and the averaged, centroided peak list
of every row**, at the floor and the ceiling a record of one's own is
written at (`library.OWN_MIN_RELATIVE`, `library.OWN_MAX_PEAKS`), so that a
reference can be scored against months later on a machine that has never
seen the acquisitions. `Session.save_project` puts it under `infusions`.

What is compared, per matched row
---------------------------------

*Does it still look like itself?* `library.match` of this morning's peaks
against the reference's stored ones — the same cosine a library search and
a standard's history take, so "how alike are two spectra" has one answer in
this program and not three. Both scores are kept: the plain one, and the
reverse, which asks only whether the reference's peaks are still there.

*Is the base peak where it was, and as big?* Its distance from the
reference's in ppm, and the ratio of the two heights.

*And the rest of the row:* the precursor's error against what the method
wrote, the ions a formula found of those it predicted, and the score of the
best record in the library of one's own — each as a change rather than as a
value, since the value itself is already in the Infusions tab.

The *moved* mark is `standard_history`'s two rules and not a third of its
own: a base peak more than `SAME_PEAK_PPM` from the reference's is not the
same ion, and a base-peak height outside `qc.OUT_PERCENT` of the
reference's is what a control chart of that standard would call out. The
cosine is reported and is deliberately **not** a rule: a history judges a
score against the spread of its own series, and two days are two points,
which is not a spread.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import re
from dataclasses import dataclass, field

import numpy as np

from .infusion_report import ENERGY_TOLERANCE_EV, compound_of
from .library import (OWN_MAX_PEAKS, OWN_MIN_RELATIVE, PEAK_TOLERANCE_PPM,
                      match)
from .qc import OUT_PERCENT
from .standard_history import SAME_PEAK_PPM
from .standard_history import _WORD as _ACTIVATION_IN_NAME

#: how far the base peak's height may sit from the reference's before the
#: row is marked. `qc.OUT_PERCENT` is what a control chart of that same
#: standard calls out, and a second figure for the same question would be
#: one too many — see `standard_history`, which charts this metric.
MOVED_PERCENT = OUT_PERCENT

#: the floor and the ceiling the stored peak list is written at: the ones a
#: record of one's own is written at. A reference is scored against the way
#: a library record is scored against, or the two cosines in this program
#: would not be the same arithmetic on the same input.
STORED_MIN_RELATIVE = OWN_MIN_RELATIVE
STORED_PEAKS = OWN_MAX_PEAKS

#: the key the summary is saved under in a project, and the shape of what is
#: written there. Bumped when the shape changes; a reader that does not know
#: a version reads what it recognises rather than refusing the project.
PROJECT_KEY = "infusions"
FORMAT = 1

#: a collision energy written into a file name — `..._EAD_22CE_44DP_...`,
#: `..._45eV_...`. Read only where the acquisition itself declares none,
#: and a proposal from a naming convention exactly as
#: `standard_history.activation_of` is: without it two rows of one compound
#: acquired at two energies are one row with no energy, which is the
#: comparison this module exists to prevent.
_ENERGY_IN_NAME = re.compile(r"(?:^|[^A-Za-z0-9])(\d+(?:\.\d+)?)\s*(?:CE|eV)"
                             r"(?![A-Za-z0-9])", re.IGNORECASE)

_NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _flat(text) -> str:
    """A compound's name with case and punctuation set aside: `CA-d4` and
    `CA d4` are one standard written by two people."""
    return _NOT_ALPHANUMERIC.sub("", str(text or "").lower())


def activation_in(*names: str) -> str:
    """
    The activation a name says, upper case, or `""` for unstated.

    `standard_history.activation_of` reads a library record's fields first
    and its name second; an infusion has no record to read, so the name is
    all there is. The expression is that module's, so the two agree on what
    counts as a word — `EAD` between separators and not the `ead` inside a
    word.
    """
    for name in names:
        found = _ACTIVATION_IN_NAME.search(str(name or ""))
        if found:
            return found.group(1).upper()
    return ""


def energy_in(*names: str) -> float | None:
    """The collision energy a name writes, or None."""
    for name in names:
        found = _ENERGY_IN_NAME.search(str(name or ""))
        if found:
            try:
                return float(found.group(1))
            except ValueError:
                continue
    return None


def _get(obj, name, default=None):
    """
    An attribute, or a method's return, whichever the object offers.

    Everything is read this way because an `InfusionRow` is another module's
    dataclass and a row saved by another version of this program is not
    obliged to carry every field this one knows about. A missing field is a
    cell that says so, not an exception.
    """
    value = getattr(obj, name, default)
    if callable(value):
        try:
            value = value()
        except Exception:
            return default
    return default if value is None else value


def _floats(text) -> np.ndarray:
    """A stored peak axis: a string of numbers, or a list of them."""
    if isinstance(text, np.ndarray):
        return np.asarray(text, dtype=float)
    if isinstance(text, (list, tuple)):
        return np.asarray(text, dtype=float)
    parts = str(text or "").split()
    return np.asarray([float(p) for p in parts], dtype=float) if parts \
        else np.zeros(0)


def stored_peaks(peaks) -> tuple[np.ndarray, np.ndarray, float]:
    """
    A row's peak list as a record of one's own would hold it.

    The peaks in ascending mass, their intensities as shares of the base
    peak, and the base peak's own height in counts — which every library
    format loses the moment a record is written, and which is the one figure
    that says whether the standard is still giving what it gave.
    """
    mz = np.asarray([float(p[0]) for p in peaks or []], dtype=float)
    intensity = np.asarray([float(p[1]) for p in peaks or []], dtype=float)
    finite = (np.isfinite(mz) & np.isfinite(intensity) & (intensity > 0)
              if mz.size else np.zeros(0, dtype=bool))
    mz, intensity = mz[finite], intensity[finite]
    top = float(intensity.max()) if intensity.size else 0.0
    if top <= 0:
        return np.zeros(0), np.zeros(0), 0.0
    keep = np.flatnonzero(intensity >= STORED_MIN_RELATIVE * top)
    if keep.size > STORED_PEAKS:
        keep = keep[np.argsort(-intensity[keep])[:STORED_PEAKS]]
    keep = keep[np.argsort(mz[keep])]
    return mz[keep], intensity[keep] / top, top


# --------------------------------------------------------------------------- #
# one infusion, as a comparison reads it
# --------------------------------------------------------------------------- #
@dataclass
class InfusionSide:
    """
    One infusion reduced to what a comparison needs and what a file can hold.

    Built from a live `infusion_report.InfusionRow`, or read back from a
    project that saved one. Everything here is a number, a short string or a
    peak list: no spectrum, no picture and no reader.
    """

    compound: str = ""
    sample: str = ""
    file: str = ""
    mode: str = ""
    energy: float | None = None
    activation: str = ""
    scans: int = 0
    base_mz: float | None = None
    base_height: float | None = None
    written_precursor: float | None = None
    found_mz: float | None = None
    found_height: float | None = None
    precursor_ppm: float | None = None
    ions_found: int | None = None
    ions_predicted: int | None = None
    record: str = ""
    record_score: float | None = None
    record_reverse: float | None = None
    #: the averaged, centroided peaks, ascending in mass, relative to the
    #: base peak — `library.OWN_MIN_RELATIVE` and `OWN_MAX_PEAKS`
    mz: np.ndarray = field(default_factory=lambda: np.zeros(0))
    intensity: np.ndarray = field(default_factory=lambda: np.zeros(0))

    # -- what it is called ---------------------------------------------------- #
    @property
    def conditions(self) -> str:
        """The energy and activation, as a person would write them —
        `standard_history.Series.conditions`, which is the same phrase."""
        bits = [self.activation] if self.activation else []
        bits.append("CE unstated" if self.energy is None
                    else f"{self.energy:g} eV")
        return " ".join(bits)

    @property
    def label(self) -> str:
        return f"{self.compound or self.sample} · {self.conditions}"

    @property
    def key(self) -> tuple:
        return (_flat(self.compound), self.activation)

    @property
    def peaks(self) -> int:
        return int(self.mz.size)

    # -- building one --------------------------------------------------------- #
    @classmethod
    def from_row(cls, row) -> "InfusionSide":
        """
        One row of a live summary, read defensively.

        The compound, the activation and — where the acquisition declares
        none — the collision energy are read from the **file name first and
        the sample's name second**, which is the opposite of what the
        Infusions tab shows and is deliberate. `samples.shorten_names` takes
        the prefix every open sample shares off the names it displays, so
        one file is called `EAD_12CE_44DP_13KE_mix1` beside two other
        cholic-acid infusions and `12CE_44DP_13KE_TESTEARTIGO` beside one:
        measured on the real folder, the compound came out as *EAD* one day
        and *12CE* the next and nothing matched anything. The name on the
        disk does not depend on what else is open, and a comparison of two
        days needs an identity that does not either.
        """
        report = getattr(row, "report", None) or row
        found = _get(row, "found")
        explanation = getattr(report, "explanation", None)
        hit = getattr(report, "hit", None)
        entry = getattr(hit, "entry", None)
        sample = _get(report, "sample", "")
        file = os.path.basename(str(_get(report, "file", "") or ""))
        names = tuple(name for name in (file, sample) if name)
        energy = _get(report, "collision_energy")
        mz, intensity, top = stored_peaks(getattr(row, "peaks", []) or [])
        # the base peak is the strongest of the *stored* peaks and not the
        # tallest point of the drawn trace, which is a profile point a few
        # thousandths away: the stored intensities are shares of this one by
        # construction, and it is the only definition a reference read back
        # out of a file could still check. `standard_history` reads a
        # record's base peak the same way, off the peaks the record holds.
        base = ((float(mz[int(np.argmax(intensity))]), top) if mz.size
                else _get(report, "base_peak"))
        return cls(
            compound=(compound_of(names[0]) if names
                      else _get(report, "compound", "")),
            sample=sample,
            file=_get(report, "file", ""),
            mode=_get(row, "mode", "") or _get(report, "channel_name", ""),
            energy=(float(energy) if energy is not None
                    else energy_in(*names)),
            activation=activation_in(*names, _get(report, "channel", "")),
            scans=int(_get(report, "scans", 0) or 0),
            base_mz=float(base[0]) if base else None,
            base_height=float(base[1]) if base else (top or None),
            written_precursor=_get(report, "written_precursor"),
            found_mz=float(found[0]) if found else None,
            found_height=float(found[1]) if found else None,
            precursor_ppm=_get(report, "error_ppm"),
            ions_found=(int(_get(explanation, "matched", 0))
                        if explanation is not None else None),
            ions_predicted=(int(_get(explanation, "predicted", 0))
                            if explanation is not None else None),
            record=_get(entry, "name", "") if entry is not None else "",
            record_score=_get(hit, "score") if hit is not None else None,
            record_reverse=_get(hit, "reverse") if hit is not None else None,
            mz=mz, intensity=intensity)

    # -- saved and read back --------------------------------------------------- #
    def to_dict(self) -> dict:
        """
        The row as a project holds it.

        The peaks go in as two space-separated strings rather than as two
        lists of numbers, because a project is written with `indent=2` and
        `json.dump` puts every element of a list on a line of its own: four
        hundred numbers become four hundred lines, for the same figures at
        the same precision. Five decimals of mass is 0.02 ppm at m/z 500,
        finer than anything here compares on.
        """
        return {
            "compound": self.compound, "sample": self.sample,
            "file": self.file, "mode": self.mode,
            "energy": self.energy, "activation": self.activation,
            "scans": self.scans,
            "base_mz": self.base_mz, "base_height": self.base_height,
            "written_precursor": self.written_precursor,
            "found_mz": self.found_mz, "found_height": self.found_height,
            "precursor_ppm": self.precursor_ppm,
            "ions_found": self.ions_found,
            "ions_predicted": self.ions_predicted,
            "record": self.record, "record_score": self.record_score,
            "record_reverse": self.record_reverse,
            "mz": " ".join(f"{value:.5f}" for value in self.mz),
            "intensity": " ".join(f"{value:.6g}" for value in self.intensity),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InfusionSide":
        data = dict(data or {})
        return cls(
            compound=str(data.get("compound", "") or ""),
            sample=str(data.get("sample", "") or ""),
            file=str(data.get("file", "") or ""),
            mode=str(data.get("mode", "") or ""),
            energy=data.get("energy"),
            activation=str(data.get("activation", "") or ""),
            scans=int(data.get("scans", 0) or 0),
            base_mz=data.get("base_mz"), base_height=data.get("base_height"),
            written_precursor=data.get("written_precursor"),
            found_mz=data.get("found_mz"),
            found_height=data.get("found_height"),
            precursor_ppm=data.get("precursor_ppm"),
            ions_found=data.get("ions_found"),
            ions_predicted=data.get("ions_predicted"),
            record=str(data.get("record", "") or ""),
            record_score=data.get("record_score"),
            record_reverse=data.get("record_reverse"),
            mz=_floats(data.get("mz")),
            intensity=_floats(data.get("intensity")))


@dataclass
class StoredSummary:
    """An infusion summary read back from a project: figures and peaks."""

    name: str = ""
    rows: list[InfusionSide] = field(default_factory=list)
    library: str = ""
    taken: str = ""
    seconds: float = 0.0
    note: str = ""

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def compounds(self) -> list[str]:
        return list(dict.fromkeys(row.compound for row in self.rows))


def summary_to_dict(summary, name: str = "") -> dict:
    """An `InfusionSummary` — or a `StoredSummary` — as a project holds it."""
    taken = getattr(summary, "taken", "")
    if isinstance(taken, _dt.datetime):
        taken = taken.isoformat(timespec="seconds")
    return {
        "format": FORMAT,
        "name": name or getattr(summary, "name", ""),
        "library": str(getattr(summary, "library", "") or ""),
        "taken": str(taken or ""),
        "seconds": float(getattr(summary, "seconds", 0.0) or 0.0),
        "rows": [side.to_dict() for side in sides_of(summary)],
    }


def summary_from_dict(data: dict, name: str = "") -> StoredSummary:
    data = dict(data or {})
    return StoredSummary(
        name=name or str(data.get("name", "") or ""),
        rows=[InfusionSide.from_dict(row) for row in data.get("rows") or []],
        library=str(data.get("library", "") or ""),
        taken=str(data.get("taken", "") or ""),
        seconds=float(data.get("seconds", 0.0) or 0.0))


def read_summary(path: str | os.PathLike) -> StoredSummary | None:
    """
    The infusion summary a project saved, or None where it saved none.

    `batches.read_project`'s rule, for the same reason: everything compared
    here is in what the project wrote, so a reference whose acquisitions
    have moved to another disk is still a reference. None is not an error —
    it is a project measured before this existed, or one whose Infusions tab
    was never asked to measure — and the caller says so in those words.
    """
    path = str(path)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    stored = data.get(PROJECT_KEY)
    if not isinstance(stored, dict) or not stored.get("rows"):
        return None
    return summary_from_dict(stored,
                             name=os.path.splitext(os.path.basename(path))[0])


def sides_of(summary) -> list[InfusionSide]:
    """
    Either kind of summary as a list of sides.

    A live `infusion_report.InfusionSummary` holds `InfusionRow`s and a
    `StoredSummary` holds these already; a comparison should not have to
    care which of the two it was handed, and this is the one place that
    knows.
    """
    rows = list(getattr(summary, "rows", []) or []) if summary is not None \
        else []
    return [row if isinstance(row, InfusionSide) else InfusionSide.from_row(row)
            for row in rows]


def name_of(summary, fallback: str = "") -> str:
    return str(getattr(summary, "name", "") or fallback)


# --------------------------------------------------------------------------- #
# one row against one row
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class InfusionDelta:
    """One infusion of one compound, this day against the reference's."""

    current: InfusionSide
    reference: InfusionSide
    #: the cosine of this morning's peaks against the reference's stored
    #: ones, and the reverse — `library.match`, the reference as the library
    score: float = 0.0
    reverse: float = 0.0
    matched: int = 0
    of_reference: int = 0

    @property
    def compound(self) -> str:
        return self.current.compound or self.reference.compound

    @property
    def conditions(self) -> str:
        return self.current.conditions

    @property
    def label(self) -> str:
        return f"{self.compound} · {self.conditions}"

    # -- the base peak --------------------------------------------------------- #
    @property
    def base_gap_ppm(self) -> float | None:
        mine, theirs = self.current.base_mz, self.reference.base_mz
        if not mine or not theirs:
            return None
        return (mine - theirs) / theirs * 1e6

    @property
    def same_base_peak(self) -> bool:
        """
        Whether the two base peaks are one ion measured twice.

        False is not a large mass error; it is a different ion, and saying
        which is `standard_history`'s distinction — a base peak that moved
        from a fragment to the surviving precursor is the spray changing,
        not the axis.
        """
        gap = self.base_gap_ppm
        return gap is not None and abs(gap) <= SAME_PEAK_PPM

    @property
    def intensity_ratio(self) -> float | None:
        mine, theirs = self.current.base_height, self.reference.base_height
        if not theirs or mine is None:
            return None
        return mine / theirs

    @property
    def intensity_change(self) -> float | None:
        """Per cent change of the base peak's height."""
        ratio = self.intensity_ratio
        return None if ratio is None else (ratio - 1.0) * 100.0

    # -- the rest of the row --------------------------------------------------- #
    @property
    def precursor_ppm_change(self) -> float | None:
        mine, theirs = self.current.precursor_ppm, self.reference.precursor_ppm
        if mine is None or theirs is None:
            return None
        return mine - theirs

    @property
    def ions_change(self) -> int | None:
        mine, theirs = self.current.ions_found, self.reference.ions_found
        if mine is None or theirs is None:
            return None
        return int(mine) - int(theirs)

    @property
    def record_score_change(self) -> float | None:
        mine, theirs = self.current.record_score, self.reference.record_score
        if mine is None or theirs is None:
            return None
        return (mine - theirs) * 100.0

    # -- the mark -------------------------------------------------------------- #
    @property
    def moved(self) -> bool:
        return bool(self.why)

    @property
    def why(self) -> str:
        """Why the row is marked, in the words of the rule that marked it."""
        said = []
        gap = self.base_gap_ppm
        if gap is None:
            said.append("there is no base peak on one of the two sides")
        elif not self.same_base_peak:
            said.append(f"the base peak is {gap:+,.0f} ppm from the "
                        f"reference's, past the {SAME_PEAK_PPM:g} ppm that "
                        f"says the same ion")
        change = self.intensity_change
        if change is not None and abs(change) > MOVED_PERCENT:
            said.append(f"the base peak is {change:+.0f}% of the reference's, "
                        f"past {MOVED_PERCENT:g}%")
        return "; ".join(said)


# --------------------------------------------------------------------------- #
# the whole comparison
# --------------------------------------------------------------------------- #
@dataclass
class InfusionComparison:
    reference: str = ""
    current: str = ""
    reference_taken: str = ""
    current_taken: str = ""
    reference_library: str = ""
    current_library: str = ""
    rows: list[InfusionDelta] = field(default_factory=list)
    #: an infusion one side has and the other does not, at those conditions
    only_reference: list[InfusionSide] = field(default_factory=list)
    only_current: list[InfusionSide] = field(default_factory=list)

    # -- what each side holds -------------------------------------------------- #
    def _totals(self, sides: list[InfusionSide]) -> dict:
        heights = [s.base_height for s in sides if s.base_height]
        scores = [s.record_score for s in sides if s.record_score is not None]
        return {
            "infusions": len(sides),
            "compounds": len({_flat(s.compound) for s in sides if s.compound}),
            "measured": sum(1 for s in sides if s.found_mz is not None),
            "median_height": float(np.median(heights)) if heights else None,
            "median_record": (float(np.median(scores)) * 100.0 if scores
                              else None),
            "median_peaks": (float(np.median([s.peaks for s in sides]))
                             if sides else None),
        }

    def totals(self) -> tuple[dict, dict]:
        return (self._totals([row.reference for row in self.rows]
                             + list(self.only_reference)),
                self._totals([row.current for row in self.rows]
                             + list(self.only_current)))

    @property
    def moved(self) -> list[InfusionDelta]:
        return [row for row in self.rows if row.moved]

    @property
    def median_score(self) -> float | None:
        if not self.rows:
            return None
        return float(np.median([row.score for row in self.rows])) * 100.0

    @property
    def median_reverse(self) -> float | None:
        if not self.rows:
            return None
        return float(np.median([row.reverse for row in self.rows])) * 100.0

    @property
    def same_ion(self) -> int:
        return sum(1 for row in self.rows if row.same_base_peak)

    def summary(self) -> str:
        ref, cur = self.totals()

        def figure(value, decimals=0):
            return "—" if value is None else f"{value:,.{decimals}f}"

        parts = [f"{self.reference} ({ref['infusions']} infusion(s), "
                 f"{ref['compounds']} compound(s)) against {self.current} "
                 f"({cur['infusions']}, {cur['compounds']})"]
        parts.append(f"{len(self.rows)} matched by compound and conditions")
        if self.only_reference or self.only_current:
            parts.append(f"{len(self.only_reference)} only in the reference, "
                         f"{len(self.only_current)} only in the current")
        if self.rows:
            parts.append(f"median score against the reference's peaks "
                         f"{figure(self.median_score)} of 100, reverse "
                         f"{figure(self.median_reverse)}")
            parts.append(f"the base peak is the same ion within "
                         f"{SAME_PEAK_PPM:g} ppm in {self.same_ion} of "
                         f"{len(self.rows)}")
            parts.append(f"median base peak {figure(ref['median_height'])} "
                         f"counts against {figure(cur['median_height'])}")
            parts.append(f"{len(self.moved)} marked as moved")
        return "; ".join(parts) + "."


def _agree(mine: float | None, theirs: float | None) -> bool:
    """Two collision energies that are the same setting written twice."""
    if mine is None or theirs is None:
        return mine is None and theirs is None
    return abs(float(mine) - float(theirs)) <= ENERGY_TOLERANCE_EV


def compare_infusions(current, reference, current_name: str = "",
                      reference_name: str = "") -> InfusionComparison:
    """
    Every infusion the two days share, matched by compound *and* conditions.

    A row is paired with the reference's row of the same compound, the same
    activation and a collision energy within `ENERGY_TOLERANCE_EV` — a
    22 eV EAD spray against the reference's 22 eV EAD spray, and never
    against its 12 eV one. Where the reference has more than one candidate
    the nearest energy takes it, and each reference row is used once: two
    sprays of one compound at one setting are two rows, not one row twice.

    Both arguments may be a live `infusion_report.InfusionSummary` or a
    `StoredSummary` read back from a project. A live summary does not know
    what it is called — it is whatever is open — so the caller may name the
    two sides; a stored one carries the name of the project it came from.
    """
    current_sides = sides_of(current)
    reference_sides = sides_of(reference)
    pool: dict[tuple, list[InfusionSide]] = {}
    for side in reference_sides:
        pool.setdefault(side.key, []).append(side)

    comparison = InfusionComparison(
        reference=reference_name or name_of(reference, "the reference"),
        current=current_name or name_of(current, "the open infusions"),
        reference_taken=str(getattr(reference, "taken", "") or ""),
        current_taken=str(getattr(current, "taken", "") or ""),
        reference_library=str(getattr(reference, "library", "") or ""),
        current_library=str(getattr(current, "library", "") or ""))
    taken: set[int] = set()
    for side in current_sides:
        candidates = [other for other in pool.get(side.key, [])
                      if id(other) not in taken
                      and _agree(side.energy, other.energy)]
        if not candidates:
            comparison.only_current.append(side)
            continue
        other = min(candidates,
                    key=lambda o: abs((o.energy or 0.0) - (side.energy or 0.0)))
        taken.add(id(other))
        score, reverse, pairs = match(side.mz, side.intensity,
                                      other.mz, other.intensity,
                                      PEAK_TOLERANCE_PPM)
        comparison.rows.append(InfusionDelta(
            current=side, reference=other, score=float(score),
            reverse=float(reverse), matched=len(pairs),
            of_reference=int(other.mz.size)))
    comparison.only_reference = [side for side in reference_sides
                                 if id(side) not in taken]
    return comparison


# --------------------------------------------------------------------------- #
# the export
# --------------------------------------------------------------------------- #
CSV_HEADER = ["Compound", "Conditions", "Sample (reference)",
              "Sample (current)", "Score", "Reverse", "Matched",
              "Of reference", "Base m/z (reference)", "Base m/z (current)",
              "Base Δ ppm", "Same ion", "Height (reference)",
              "Height (current)", "Height ratio", "Height change %",
              "Precursor ppm (reference)", "Precursor ppm (current)",
              "Precursor Δ ppm", "Ions (reference)", "Ions (current)",
              "Ions change", "Record (reference)", "Record (current)",
              "Record score change", "Moved", "Note"]


def _ions_cell(side: InfusionSide) -> str:
    if side.ions_found is None:
        return ""
    return (f"{side.ions_found} of {side.ions_predicted}"
            if side.ions_predicted else f"{side.ions_found}")


def write_csv(comparison: InfusionComparison, path: str | os.PathLike) -> str:
    """Every matched row, then the infusions only one of the two days has."""
    def cell(value, decimals=1):
        return "" if value is None else f"{value:.{decimals}f}"

    path = str(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for row in comparison.rows:
            r, c = row.reference, row.current
            writer.writerow([
                row.compound, row.conditions, r.sample, c.sample,
                f"{row.score * 100:.1f}", f"{row.reverse * 100:.1f}",
                row.matched, row.of_reference,
                cell(r.base_mz, 4), cell(c.base_mz, 4),
                cell(row.base_gap_ppm), "yes" if row.same_base_peak else "no",
                cell(r.base_height, 0), cell(c.base_height, 0),
                cell(row.intensity_ratio, 3), cell(row.intensity_change),
                cell(r.precursor_ppm), cell(c.precursor_ppm),
                cell(row.precursor_ppm_change),
                _ions_cell(r), _ions_cell(c),
                "" if row.ions_change is None else f"{row.ions_change:+d}",
                r.record, c.record, cell(row.record_score_change),
                "yes" if row.moved else "", row.why])
        for side in comparison.only_reference:
            writer.writerow([side.compound, side.conditions, side.sample, ""]
                            + [""] * (len(CSV_HEADER) - 5)
                            + ["only in the reference"])
        for side in comparison.only_current:
            writer.writerow([side.compound, side.conditions, "", side.sample]
                            + [""] * (len(CSV_HEADER) - 5)
                            + ["only in the current"])
    return path
