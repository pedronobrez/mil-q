"""
Response floors the batch can propose, for somebody to accept.

The floor is the method's to declare — see `Component.min_response` — and
the batch cannot derive it. What the batch can do is say what each standard
gave in the injections that were not failures, and offer half of that as a
starting point, marked as a proposal with its basis beside it. Nothing is
written until a row is ticked and Apply pressed.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..qc import FLOOR_FRACTION, MIN_INJECTIONS, FloorProposal
from ..session import Session
from .help_window import describe, open_manual

HELP_PAGE = "internal-standards-and-qualifiers"


class FloorDialog(QtWidgets.QDialog):
    """Tick the standards to give a floor to, then apply."""

    COLUMNS = ["Use", "Standard", "Current", "Median", "Used", "Proposed",
               "Left out", "Note"]

    def __init__(self, session: Session, proposals: list[FloorProposal],
                 parent=None):
        super().__init__(parent)
        self.session = session
        self.proposals = proposals
        self.setWindowTitle("Suggest response floors")
        self.resize(900, 460)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            f"For each internal standard: its median area over the spiked "
            f"injections, the injections where every standard went at once "
            f"left out, and {FLOOR_FRACTION:.0%} of that median as the floor. "
            f"A proposal, not a measurement — the floor is what the standard "
            f"gives when the run is right, and this batch is the only evidence "
            f"to hand. Rows measured in fewer than {MIN_INJECTIONS} injections "
            f"are offered unticked.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.table = QtWidgets.QTableWidget(len(proposals), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            len(self.COLUMNS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, proposal in enumerate(proposals):
            tick = QtWidgets.QTableWidgetItem()
            tick.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                          | QtCore.Qt.ItemFlag.ItemIsEnabled)
            tick.setCheckState(
                QtCore.Qt.CheckState.Checked
                if proposal.offered and proposal.confident
                else QtCore.Qt.CheckState.Unchecked)
            if not proposal.offered:
                tick.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self.table.setItem(row, 0, tick)
            cells = [proposal.component,
                     "—" if proposal.current is None else f"{proposal.current:,.0f}",
                     "—" if proposal.median is None else f"{proposal.median:,.0f}",
                     f"{proposal.used} of {proposal.injections}",
                     "—" if proposal.proposed is None else f"{proposal.proposed:,.0f}",
                     f"{len(proposal.excluded)}" if proposal.excluded else "—",
                     proposal.note]
            for column, text in enumerate(cells, start=1):
                item = QtWidgets.QTableWidgetItem(text)
                if column in (2, 3, 4, 5, 6):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 6 and proposal.excluded:
                    # the names, on hover: the failed injections the index
                    # called out, left out of the median
                    item.setToolTip("Left out of the median:\n"
                                    + "\n".join(proposal.excluded))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setText(
            "Apply the ticked floors")
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply
                            ).clicked.connect(self.apply_selected)
        layout.addWidget(self.buttons)
        self.applied = 0

    def selected(self) -> list[FloorProposal]:
        chosen = []
        for row, proposal in enumerate(self.proposals):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == QtCore.Qt.CheckState.Checked:
                chosen.append(proposal)
        return chosen

    def apply_selected(self) -> int:
        """Write the ticked floors into the method; returns how many."""
        written = 0
        for proposal in self.selected():
            component = self.session.method.by_name(proposal.component)
            if component is None or proposal.proposed is None:
                continue
            component.min_response = proposal.proposed
            written += 1
        self.applied = written
        if written:
            self.session.notify_method_changed()
        self.accept()
        return written
