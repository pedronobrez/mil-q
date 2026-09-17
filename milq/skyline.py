"""
The method as a transition list Skyline can import.

Skyline is where a great deal of small-molecule work is reviewed, and its
*Import Transition List* takes a plain CSV whose columns it recognises by
name. A method built here — precursor, fragment, retention time and window,
which standards are internal — is exactly the table that file wants, so
handing it over should not mean retyping it.

The headers below are Skyline's own. They were read off the reader that
consumes them, `SmallMoleculeTransitionListColumnHeaders` in
`pwiz_tools/Skyline/Model/SmallMoleculeTransitionListReader.cs`, together
with the display strings in Skyline's resources and the negative-mode lists
in its own functional tests; the matching there is case- and
space-insensitive, and `Molecule Name` and `Precursor Name` are synonyms for
the same column. **No file written here has been imported into Skyline**:
there is no copy of it on the machine this was developed on. What is
claimed is that the headers are the documented ones and the values are the
method's; whether Skyline accepts the file is untested, and the manual says
so.

Three things the method does not carry, and what is done about each:

* **Charge.** It comes from the adduct, signed, so `[M-H]-` is −1 and
  `[M+2H]2+` is +2. A component with no adduct has no charge to write and
  the cell is left empty rather than filled with a guess; `TransitionList`
  counts those so the caller can say which components need an adduct. The
  neutral entry is not an ion and counts as no adduct.
* **Product charge.** A fragment's charge is nowhere in an MRM method. The
  polarity is the precursor's, since a fragment of a negative ion is
  negative, and the magnitude is one, which is what a triple quadrupole
  reports; that is an assumption and it is stated here rather than hidden.
* **The window.** Skyline's *Explicit Retention Time Window* is the whole
  width, and a component's `rt_halfwidth` is half of it, so the value
  written is twice the half width — the same window the integration uses.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field

from .chemistry import ADDUCTS_BY_NAME, NEUTRAL
from .components import Component
from .method import ProcessingMethod

#: Skyline's column names, in the order they are written. Spelled as
#: Skyline spells them; it matches without regard to case or spaces, but a
#: file a person also reads should be spelled the documented way.
HEADER = ["Molecule List Name", "Molecule Name", "Precursor m/z",
          "Precursor Charge", "Product m/z", "Product Charge",
          "Explicit Retention Time", "Explicit Retention Time Window", "Note"]

#: what a component with no group is filed under. Skyline puts every
#: molecule in a list, and a blank name makes one called nothing.
DEFAULT_LIST = "Molecules"

#: what the Note says of an internal standard. Skyline has a `Label Type`
#: column for heavy labelling, but an internal standard is a role in this
#: method rather than a label — some are structural analogues — so it is
#: said in words instead of asserted as a label the compound may not carry.
IS_NOTE = "internal standard"


def charge_of(component: Component) -> int | None:
    """
    The component's charge, signed, or None when the method does not say.

    Read from the adduct, which is the only place a method here records
    polarity. `M (neutral)` is not an ion and answers None.
    """
    adduct = ADDUCTS_BY_NAME.get(component.adduct or "")
    if adduct is None or adduct.name == NEUTRAL:
        return None
    return adduct.charge


def product_charge(precursor_charge: int | None) -> int | None:
    """Singly charged, with the precursor's polarity. See the module note."""
    if precursor_charge is None:
        return None
    return -1 if precursor_charge < 0 else 1


@dataclass(frozen=True)
class Row:
    """One transition, as the columns of `HEADER`."""

    molecule_list: str
    molecule: str
    precursor_mz: float
    precursor_charge: int | None
    product_mz: float
    product_charge: int | None
    retention_time: float | None
    retention_window: float | None
    note: str

    def as_cells(self) -> list[str]:
        return [
            self.molecule_list, self.molecule,
            f"{self.precursor_mz:.4f}",
            "" if self.precursor_charge is None else str(self.precursor_charge),
            f"{self.product_mz:.4f}",
            "" if self.product_charge is None else str(self.product_charge),
            "" if self.retention_time is None else f"{self.retention_time:.3f}",
            "" if self.retention_window is None
            else f"{self.retention_window:.3f}",
            self.note,
        ]


@dataclass
class TransitionList:
    """The rows, and what the method could not supply for them."""

    rows: list[Row] = field(default_factory=list)
    #: components left out entirely, with why
    skipped: list[str] = field(default_factory=list)
    #: rows written without a charge, because no adduct is declared
    without_charge: list[str] = field(default_factory=list)
    #: rows whose product m/z is the precursor's, there being no fragment
    without_fragment: list[str] = field(default_factory=list)
    #: rows written without a retention time
    without_time: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """What went in and what the method could not say, in one line."""
        if not self.rows:
            return ("nothing to write: the method has no component with a "
                    "precursor mass")
        parts = [f"{len(self.rows)} transition(s)"]
        if self.without_charge:
            parts.append(f"{len(self.without_charge)} without a charge — give "
                         f"those components an adduct, or Skyline will ask "
                         f"for one")
        if self.without_fragment:
            parts.append(f"{len(self.without_fragment)} with no fragment, "
                         f"written precursor to precursor")
        if self.without_time:
            parts.append(f"{len(self.without_time)} with no retention time")
        if self.skipped:
            parts.append(f"{len(self.skipped)} left out")
        return "; ".join(parts) + "."


def build_transition_list(method: ProcessingMethod) -> TransitionList:
    """Every valid component of the method as a Skyline row."""
    listing = TransitionList()
    for component in method.components:
        if not component.is_valid:
            listing.skipped.append(component.name or "(unnamed)")
            continue
        charge = charge_of(component)
        if charge is None:
            listing.without_charge.append(component.name)
        fragment = component.fragment
        if fragment is None:
            listing.without_fragment.append(component.name)
            fragment = component.precursor
        window = None
        if component.rt is None:
            listing.without_time.append(component.name)
        elif component.rt_halfwidth:
            window = component.rt_halfwidth * 2.0
        notes = []
        if component.is_internal_standard:
            notes.append(IS_NOTE)
        if component.qualifier_of:
            notes.append(f"qualifier of {component.qualifier_of}")
        if component.internal_standard:
            notes.append(f"reported against {component.internal_standard}")
        listing.rows.append(Row(
            molecule_list=component.group or DEFAULT_LIST,
            molecule=component.name,
            precursor_mz=component.precursor,
            precursor_charge=charge,
            product_mz=fragment,
            product_charge=product_charge(charge),
            retention_time=component.rt,
            retention_window=window,
            note="; ".join(notes),
        ))
    return listing


def write_transition_list(method: ProcessingMethod,
                          path: str | os.PathLike) -> TransitionList:
    """
    Write the method as a Skyline small-molecule transition list.

    Returns what was written and what the method could not supply, so the
    caller can say so rather than leave the analyst to find the blank
    columns in Skyline's error dialog.
    """
    listing = build_transition_list(method)
    path = str(path)
    if not path.lower().endswith(".csv"):
        path += ".csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for row in listing.rows:
            writer.writerow(row.as_cells())
    return listing
