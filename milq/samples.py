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
        )


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
