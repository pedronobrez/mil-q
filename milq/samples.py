"""
Sample entries — the batch table.

Sample type, expected concentration, dilution and the internal-standard link
are not recorded in the .wiff file (every injection comes back as `kUnknown`),
so they are held here and saved with the project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

UNKNOWN = "Unknown"
STANDARD = "Standard"
QC = "Quality Control"
BLANK = "Blank"
DOUBLE_BLANK = "Double Blank"
SOLVENT = "Solvent"

SAMPLE_TYPES = (UNKNOWN, STANDARD, QC, BLANK, DOUBLE_BLANK, SOLVENT)

#: sample types whose points define a calibration curve
CALIBRATION_TYPES = (STANDARD,)


@dataclass
class SampleEntry:
    """One injection, plus the batch information the raw file does not carry."""

    path: str
    sample_index: int
    name: str
    sample_type: str = UNKNOWN
    actual_concentration: float | None = None
    dilution_factor: float = 1.0
    comment: str = ""
    #: the study group this injection belongs to — control, treated, day 7.
    #: Free text, because no vocabulary fits every study. Last in the field
    #: order so positional construction keeps working.
    sample_group: str = ""
    #: live wiff Sample; set when the file is open, never serialised
    sample: object | None = field(default=None, repr=False, compare=False)
    #: why the sample's spectra cannot be read — a `.wiff.scan` not beside
    #: its `.wiff` — set when the file is opened; empty when they can
    problem: str = field(default="", compare=False)
    #: the injection's place in the run — 1 for the first vial the
    #: instrument took. Typed, not read: a .wiff carries an acquisition time
    #: but no sequence position, and an mzML converted elsewhere may carry
    #: neither. None until somebody numbers it; where it is set it decides
    #: the order of every chart through the run (`validation.acquisition_order`).
    #: Last in the field order so positional construction keeps working.
    batch_order: int | None = None

    @property
    def key(self) -> str:
        return f"{self.path}|{self.sample_index}"

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def is_loaded(self) -> bool:
        return self.sample is not None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "sample_index": self.sample_index,
            "name": self.name,
            "sample_type": self.sample_type,
            "sample_group": self.sample_group,
            "batch_order": self.batch_order,
            "actual_concentration": self.actual_concentration,
            "dilution_factor": self.dilution_factor,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SampleEntry":
        sample_type = str(data.get("sample_type", UNKNOWN))
        return cls(
            path=str(data.get("path", "")),
            sample_index=int(data.get("sample_index", 0)),
            name=str(data.get("name", "")),
            sample_type=sample_type if sample_type in SAMPLE_TYPES else UNKNOWN,
            sample_group=str(data.get("sample_group", "") or ""),
            actual_concentration=(
                None if data.get("actual_concentration") in (None, "")
                else float(data["actual_concentration"])
            ),
            dilution_factor=float(data.get("dilution_factor", 1.0) or 1.0),
            comment=str(data.get("comment", "")),
            batch_order=parse_batch_order(data.get("batch_order")),
        )


def parse_batch_order(value) -> int | None:
    """
    A batch order as typed or as saved: a whole number from 1, or None.

    `"3"`, `3` and `3.0` are the same position; anything else — empty, zero,
    negative, a fraction, a word — is no position, because a vial cannot be
    injected 2.5th and a guessed number would reorder every chart in the run.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not number.is_integer() or number < 1:
        return None
    return int(number)


def acquisition_stamp(entry: SampleEntry) -> str:
    """The acquisition time the file carries, or "" where it carries none."""
    if not entry.is_loaded:
        return ""
    return str(getattr(entry.sample, "acquisition_time", "") or "")


def numbering_start(entries: list[SampleEntry], targets: list[SampleEntry]) -> int:
    """
    The first number to give `targets` when they are numbered as a block.

    Every row numbered starts at 1. Part of the batch numbered keeps the
    lowest number already among those rows — renumbering a stretch keeps it
    where it was — and a stretch with no number yet follows the highest
    number anywhere else in the batch, so it never collides with rows the
    selection did not touch.
    """
    chosen = {id(entry) for entry in targets}
    if len(chosen) == len(entries):
        return 1
    own = [e.batch_order for e in targets if e.batch_order is not None]
    if own:
        return min(own)
    others = [e.batch_order for e in entries
              if id(e) not in chosen and e.batch_order is not None]
    return max(others) + 1 if others else 1


def by_acquisition_time(entries: list[SampleEntry]) -> list[SampleEntry]:
    """
    `entries` by the time the files carry; those without one after them, in
    the order they came.
    """
    def when(entry: SampleEntry):
        stamp = acquisition_stamp(entry)
        return (stamp == "", stamp)

    return sorted(entries, key=when)


def shorten_names(entries: list[SampleEntry]) -> None:
    """
    Give each entry a short display name by dropping the prefix shared by every
    file: `demo_QC01` and `demo_STD_L1` become
    `QC001` and `S001`.
    """
    stems = [os.path.splitext(e.filename)[0] for e in entries]
    prefix = os.path.commonprefix(stems) if len(stems) > 1 else ""
    prefix = prefix[: prefix.rfind("_") + 1] if "_" in prefix else ""
    for entry, stem in zip(entries, stems, strict=True):
        entry.name = stem[len(prefix):] or stem
    _make_names_distinct(entries)


def _make_names_distinct(entries: list[SampleEntry]) -> None:
    """
    Two entries must never read the same.

    Shortening can collapse two different files onto one name — the same
    acquisition also present as mzML is the obvious case, and two batches
    holding a file of the same name in different folders is the other. One
    .wiff can also carry several injections, which all take the file's name.
    Two identical rows in the tree, or two identically labelled traces in a
    legend, are worse than a long name: there is no way to tell which is
    which, and no way to know that anything is wrong.
    """
    by_name: dict[str, list[SampleEntry]] = {}
    for entry in entries:
        by_name.setdefault(entry.name, []).append(entry)

    for name, clashing in by_name.items():
        if len(clashing) < 2:
            continue
        for candidate in (
            # the same acquisition in two formats: say which
            [os.path.splitext(e.filename)[1].lstrip(".") for e in clashing],
            # several injections in one file: the sample's own name
            [str(getattr(e.sample, "name", "") or "") for e in clashing],
            # the same file name under different folders
            [os.path.basename(os.path.dirname(e.path)) for e in clashing],
        ):
            if all(candidate) and len(set(candidate)) == len(clashing):
                for entry, suffix in zip(clashing, candidate, strict=True):
                    entry.name = f"{name} ({suffix})"
                break
        else:
            # nothing distinguishes them but their order
            for number, entry in enumerate(clashing, start=1):
                entry.name = f"{name} #{number}"
