"""
What was changed by hand: when, to what, from what to what.

Everything a batch is processed with is saved with the project — the method,
the integration parameters, the calibration. What is not saved anywhere is
the sequence of decisions a person made on top of that: this peak integrated
by hand, that standard dropped from the curve, this injection retyped as a
blank. Reopening a project six months later shows the answer and not how it
was arrived at.

The trail is that record. It is append-only: nothing here edits or deletes an
entry, and no interface is offered for doing so. It is saved in the project
under `audit` and read back; a project written before this existed has no key
and loads with an empty trail, which is the truthful answer for it rather
than a fabricated one.

It is **not** a regulated audit trail. There are no user accounts, no
electronic signatures and no tamper evidence: the project is a JSON file that
anyone can edit in a text editor. What it gives is the provenance of the
numbers for the person reviewing them, which is a different and smaller
claim — see the manual's *Audit trail* page.

Values are recorded as they were shown to the user and kept short: the point
is a line that reads at a glance, not a serialisation of the object.
"""

from __future__ import annotations

import csv
import datetime as _dt
from dataclasses import dataclass

#: the kinds of change recorded. A `what` is one of these — free text would
#: make the filter box useless within a week.
MANUAL_INTEGRATION = "Manual integration"
AUTOMATIC_INTEGRATION = "Automatic integration"
ROW_USED = "Row used"
CALIBRATION_POINT = "Calibration point"
CALIBRATION_OUTLIERS = "Calibration outliers"
COMPONENT_ADDED = "Component added"
COMPONENT_EDITED = "Component edited"
COMPONENT_REMOVED = "Component removed"
#: a component written from an infused standard, with the infusion it came
#: from in the note — see standards.py
COMPONENT_FROM_INFUSION = "Component from infusion"
PRECURSOR_REPAIRED = "Precursor repaired"
#: the other half of a precursor that disagrees with its name: where the
#: mass is what the instrument acquired, the name is the thing corrected
NAME_RENAMED = "Name renamed"
METHOD_DEFAULT = "Method default"
SAMPLE_EDITED = "Sample edited"
PROCESSED = "Batch processed"
REPROCESSED = "Batch reprocessed"
RECALIBRATION = "Mass recalibration"
INFUSION_REPORT = "Infusion report"
#: the method read every way it can be read before it is run, written out
METHOD_REPORT = "Method report"
#: the ratio of an analyte to its internal standard in a spray, written into
#: the Results table. A separate event from `PROCESSED` because it is a
#: separate kind of number: a height in one averaged spectrum, not an
#: integrated peak, and the trail has to say which the rows are.
INFUSION_QUANTITATION = "Infusion quantitation"
#: records written into the analyst's own spectral library. The library is a
#: file of its own and not part of the project, so the trail is the only
#: place the project says a batch of its spectra was written into one
OWN_LIBRARY = "Own library"
#: a standard entered from its bottle: one component, one record of one's
#: own, and with it the newest entry of that standard's history — one entry
#: naming all three, because they are one act. See ui/new_standard_dialog.py
NEW_STANDARD = "New standard"
PROJECT_SAVED = "Project saved"

EVENTS: tuple[str, ...] = (
    MANUAL_INTEGRATION, AUTOMATIC_INTEGRATION, ROW_USED, CALIBRATION_POINT,
    CALIBRATION_OUTLIERS, COMPONENT_ADDED, COMPONENT_EDITED,
    COMPONENT_REMOVED, COMPONENT_FROM_INFUSION, PRECURSOR_REPAIRED,
    NAME_RENAMED, METHOD_DEFAULT,
    SAMPLE_EDITED,
    PROCESSED, REPROCESSED,
    RECALIBRATION, INFUSION_REPORT, METHOD_REPORT, INFUSION_QUANTITATION,
    OWN_LIBRARY, NEW_STANDARD, PROJECT_SAVED,
)

#: the columns of the trail, in the order the panel, the report and the CSV
#: all show them
COLUMNS: tuple[str, ...] = ("When", "What", "Target", "Before", "After", "Note")

#: longest a recorded value is kept. A value is what was on screen, and a
#: table column that has to hold a paragraph holds nothing readable.
MAX_LENGTH = 160

#: the component fields worth recording a change to, under the names the
#: method table gives them, so an entry reads as the column that was typed in
COMPONENT_FIELDS: dict[str, str] = {
    "name": "name",
    "group": "group",
    "precursor": "precursor",
    "fragment": "fragment",
    "rt": "RT",
    "rt_halfwidth": "± RT",
    "tolerance": "tolerance",
    "unit": "unit",
    "formula": "formula",
    "adduct": "adduct",
    "is_internal_standard": "IS",
    "internal_standard": "internal standard",
    "response": "response",
    "concentration_unit": "conc. unit",
    "qualifier_of": "qualifier of",
    "ion_ratio": "ion ratio %",
    "ion_ratio_tolerance": "± ratio %",
    "regression": "regression",
    "weighting": "weighting",
    "min_response": "min. response",
    "lm_id": "LIPID MAPS id",
    "provenance": "provenance",
}


def now() -> str:
    """
    The timestamp an entry carries: ISO, to the second, local time.

    To the second because two entries a millisecond apart are one user action
    recorded twice, and local because the person reading the trail is the
    person who made it. ISO so that sorting the column as text sorts it as
    time, which is what the panel's sort does.
    """
    return _dt.datetime.now().isoformat(timespec="seconds")


def short(value) -> str:
    """
    One value, as it was shown: a string, kept short.

    `None` is the empty string rather than the word "None" — a field that was
    not set reads as blank on screen and reads as blank here.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        # ten significant figures: enough to keep a precursor mass to
        # its fourth decimal without printing binary noise
        text = f"{value:,.10g}"
    elif isinstance(value, int):
        text = f"{value:,}"
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= MAX_LENGTH else text[:MAX_LENGTH - 1] + "…"


@dataclass(frozen=True)
class AuditEntry:
    """One change, made by hand, at a time."""

    when: str
    what: str
    target: str = ""
    before: str = ""
    after: str = ""
    note: str = ""

    def __post_init__(self):
        # frozen so that nothing downstream can quietly rewrite history; the
        # coercion is the one write, and it happens on the way in
        for name in ("when", "what", "target", "before", "after", "note"):
            object.__setattr__(self, name, short(getattr(self, name)))

    @property
    def row(self) -> list[str]:
        return [self.when, self.what, self.target, self.before, self.after,
                self.note]

    @property
    def change(self) -> str:
        """`before → after`, or whichever of the two there is."""
        if self.before and self.after:
            return f"{self.before} → {self.after}"
        return self.after or self.before

    def to_dict(self) -> dict:
        return {"when": self.when, "what": self.what, "target": self.target,
                "before": self.before, "after": self.after, "note": self.note}

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        return cls(
            when=data.get("when", ""), what=data.get("what", ""),
            target=data.get("target", ""), before=data.get("before", ""),
            after=data.get("after", ""), note=data.get("note", ""),
        )


class AuditTrail:
    """
    The changes, in the order they were made.

    Append-only by construction: `entries` hands out a tuple, so a caller
    holding one cannot reach the list behind it, and the only way in is
    `record`. There is deliberately no remove, no edit and no clear — a
    project that starts again starts with a new trail rather than an emptied
    one.
    """

    def __init__(self, entries=()):
        self._entries: list[AuditEntry] = [
            entry if isinstance(entry, AuditEntry) else AuditEntry.from_dict(entry)
            for entry in entries
        ]

    def __repr__(self) -> str:  # pragma: no cover - debugging comfort
        return f"AuditTrail({len(self._entries)} entries)"

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __getitem__(self, index):
        return self._entries[index]

    def record(self, what: str, target="", before="", after="", note="",
               when: str | None = None) -> AuditEntry:
        """Add one change and return it."""
        entry = AuditEntry(when=when or now(), what=what, target=target,
                           before=before, after=after, note=note)
        self._entries.append(entry)
        return entry

    def rows(self) -> list[list[str]]:
        return [entry.row for entry in self._entries]

    def of(self, what: str) -> list[AuditEntry]:
        """Every entry of one kind, which is what the tests and filters want."""
        return [entry for entry in self._entries if entry.what == what]

    # -- the project ----------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"entries": [entry.to_dict() for entry in self._entries]}

    @classmethod
    def from_dict(cls, data) -> "AuditTrail":
        """
        A trail from what a project holds.

        Anything absent or unreadable gives an empty trail rather than an
        exception: a batch is not worth losing over its history, and an empty
        trail is honest about a project that recorded nothing.
        """
        if not data:
            return cls()
        rows = data.get("entries", ()) if isinstance(data, dict) else data
        try:
            return cls(rows)
        except (TypeError, AttributeError):
            return cls()


def write_csv(trail: AuditTrail, path) -> str:
    """The trail as a CSV, in the order it was made."""
    path = str(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(trail.rows())
    return path


# --------------------------------------------------------------------------- #
# what changed between two component tables
# --------------------------------------------------------------------------- #
def _pairs(before: list, after: list):
    """
    Which component of the old table is which of the new one.

    The method table is committed whole on every edit, so what a change was
    has to be worked out by comparing the two. When the two are the same
    length nothing was added or removed and the rows line up by position —
    which is what makes renaming a component read as a name changed rather
    than as one component removed and another added. Otherwise the name is
    the only identity there is.
    """
    if len(before) == len(after):
        return list(zip(before, after)), [], []
    old = {c.name: c for c in before}
    new = {c.name: c for c in after}
    common = [(old[name], new[name]) for name in old if name in new]
    removed = [c for name, c in old.items() if name not in new]
    added = [c for name, c in new.items() if name not in old]
    return common, added, removed


def describe_component(component) -> str:
    """A component in one line: enough to tell which one it was."""
    parts = [f"{component.precursor:,.4f}"]
    if component.fragment:
        parts.append(f"→ {component.fragment:,.4f}")
    if component.rt is not None:
        parts.append(f"RT {component.rt:,.2f}")
    return " ".join(parts)


def describe_integration(params) -> str:
    """
    The integration settings that were applied, in one line.

    The trail records a reprocessing by what it was reprocessed with, because
    the parameters themselves are overwritten by the next change and the
    project only ever holds the last set.
    """
    from .processing import ALGORITHM_LABELS

    parts = [ALGORITHM_LABELS.get(params.algorithm, params.algorithm).lower()]
    if params.smoothing:
        parts.append(f"smoothing {params.smoothing:g}")
    if params.baseline_window:
        parts.append(f"baseline {params.baseline_window:g}")
    parts.append(f"min height {params.min_relative_height:g}")
    parts.append(f"min S/N {params.min_snr:g}")
    region = params.noise_region
    if region is not None:
        parts.append(f"noise {region[0]:.2f}\u2013{region[1]:.2f} min")
    parts.append(params.peak_choice)
    return ", ".join(parts)


def component_changes(before: list, after: list) -> list[tuple[str, str, str, str]]:
    """
    `(what, target, before, after)` for every hand edit between two tables.

    One tuple per field changed, so an entry names the column that was typed
    in and what was in it. A component added or removed is one tuple.
    """
    changes: list[tuple[str, str, str, str]] = []
    pairs, added, removed = _pairs(before, after)
    for old, new in pairs:
        for attribute, label in COMPONENT_FIELDS.items():
            was, is_ = getattr(old, attribute, None), getattr(new, attribute, None)
            if was == is_:
                continue
            changes.append((COMPONENT_EDITED, f"{new.name} · {label}",
                            short(was), short(is_)))
    for component in added:
        changes.append((COMPONENT_ADDED, component.name, "",
                        describe_component(component)))
    for component in removed:
        changes.append((COMPONENT_REMOVED, component.name,
                        describe_component(component), ""))
    return changes
