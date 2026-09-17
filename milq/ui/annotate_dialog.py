"""Reviewing LIPID MAPS proposals for a whole component table."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6 import QtCore, QtWidgets

from .. import lipidmaps
from ..components import Component
from ..precursor import PrecursorConsensus

#: mass accuracy expected of the instrument once a precursor has actually been
#: measured, rather than read off the method
MEASURED_TOLERANCE_PPM = 10.0

WRITTEN = "written"
SURVEY = "survey"


@dataclass
class Proposal:
    """One component and the species a mass search suggests for it."""

    component: Component
    species: str = ""
    formula: str = ""
    lm_id: str = ""
    error_ppm: float = 0.0
    structures: int = 0
    species_count: int = 0
    window_mda: float = 0.0
    #: the mass the search used, and whether it was measured or transcribed
    mass: float = 0.0
    source: str = WRITTEN
    note: str = ""

    @property
    def has_match(self) -> bool:
        """Only an unambiguous species is offered for automatic use."""
        return bool(self.species) and self.species_count == 1

    @property
    def from_survey(self) -> bool:
        return self.source == SURVEY


def propose(components: list[Component], adduct: str = "[M-H]-",
            tolerance: float = 10.0, unit: str = "ppm",
            only_unnamed: bool = True,
            measured: dict[str, PrecursorConsensus] | None = None,
            ) -> list[Proposal]:
    """
    Suggest a species for each component from its precursor mass.

    Where the survey scan has given a precursor a measured mass, that mass is
    searched at the instrument's accuracy. Otherwise the value written in the
    method is used, and the window is never narrower than the decimals it was
    typed with — a mass written as 351.20 is known to ±0.005 Da, so asking for
    10 ppm of it would be inventing digits.

    A component is only offered for automatic naming when exactly one species
    fits. Anything else is reported with its count and left for a person,
    because at nominal precision several species usually do.
    """
    database = lipidmaps.database()
    if database is None:
        return []
    measured = measured or {}
    out: list[Proposal] = []

    for component in components:
        if only_unnamed and not _looks_unnamed(component):
            continue

        consensus = measured.get(component.name)
        if consensus is not None and consensus.is_reliable:
            mass = consensus.measured
            window = mass * MEASURED_TOLERANCE_PPM * 1e-6
            source = SURVEY
        else:
            mass = component.precursor
            requested = (mass * tolerance * 1e-6
                         if unit.lower() == "ppm" else tolerance)
            window = max(requested, lipidmaps.mass_precision(mass))
            source = WRITTEN

        groups = lipidmaps.group_by_species(
            database.search_mz(mass, adduct, window, "Da"))

        proposal = Proposal(component=component, mass=mass, source=source,
                            window_mda=window * 1000.0, species_count=len(groups))
        if not groups:
            proposal.note = (
                "no lipid at this mass" if source == SURVEY
                else "no lipid at the written mass")
            out.append(proposal)
            continue

        best = groups[0]
        proposal.species = best.species
        proposal.formula = best.formula
        proposal.error_ppm = best.error_ppm
        proposal.structures = len(best.records)
        proposal.lm_id = best.records[0].lm_id if len(best.records) == 1 else ""
        if len(groups) > 1:
            proposal.note = (f"{len(groups)} species fit"
                             + ("" if source == SURVEY else " — needs an accurate mass"))
        elif len(best.records) > 1:
            proposal.note = f"{len(best.records)} isomers share it"
        out.append(proposal)
    return out


def _looks_unnamed(component: Component) -> bool:
    """A component still carrying its generated name is just a number."""
    name = component.name.strip()
    if not name:
        return True
    try:
        float(name)
    except ValueError:
        return False
    return True


class AnnotateDialog(QtWidgets.QDialog):
    """Accept or reject each proposal; nothing is written until OK."""

    COLUMNS = ["Use", "Component", "Mass used", "From", "± window",
               "Best species", "Formula", "ppm", "Isomers", "Note"]

    def __init__(self, proposals: list[Proposal], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Annotate from LIPID MAPS")
        self.resize(880, 480)
        self._proposals = proposals

        layout = QtWidgets.QVBoxLayout(self)
        from_survey = sum(1 for p in proposals if p.from_survey)
        blurb = QtWidgets.QLabel(
            f"{from_survey} of {len(proposals)} precursors were measured in the "
            "survey scan and searched at ±10 ppm. The rest fall back to the mass "
            "written in the method, which is only good to its decimals, so their "
            "window is widened to match — a value typed to two decimals is "
            "searched at ±5 mDa, not at a few ppm.\n"
            "Only rows where exactly one species fits are ticked. A species is "
            "still a family of isomers, never a compound.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.table = QtWidgets.QTableWidget(len(proposals), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            len(self.COLUMNS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        numeric = {2, 4, 7, 8}
        for row, proposal in enumerate(proposals):
            use = QtWidgets.QTableWidgetItem()
            use.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                         | (QtCore.Qt.ItemFlag.ItemIsEnabled
                            if proposal.has_match else QtCore.Qt.ItemFlag.NoItemFlags))
            use.setCheckState(QtCore.Qt.CheckState.Checked if proposal.has_match
                              else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, use)

            values = [
                proposal.component.name,
                f"{proposal.mass:.4f}" if proposal.mass else "—",
                proposal.source,
                f"{proposal.window_mda:.1f} mDa",
                proposal.species or "—",
                proposal.formula or "—",
                f"{proposal.error_ppm:+.1f}" if proposal.species else "—",
                str(proposal.structures) if proposal.species else "—",
                proposal.note or proposal.lm_id,
            ]
            for column, text in enumerate(values, start=1):
                item = QtWidgets.QTableWidgetItem(text)
                if column in numeric:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 3 and proposal.from_survey:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        from .help_window import describe, open_manual
        describe(self, "annotate-from-lipid-maps")
        buttons.helpRequested.connect(
            lambda: open_manual(self, "annotate-from-lipid-maps"))
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
            "Apply the checked rows")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accepted_proposals(self) -> list[Proposal]:
        out = []
        for row, proposal in enumerate(self._proposals):
            item = self.table.item(row, 0)
            if item and item.checkState() == QtCore.Qt.CheckState.Checked:
                out.append(proposal)
        return out
