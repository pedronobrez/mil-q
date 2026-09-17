"""
The infusions that were measured, offered to the method.

One row per chosen infusion, saying what pressing Apply would write: a new
component, or the empty cells of one the method already carries. Nothing is
written until a row is ticked, and no typed value is ever overwritten — where
one disagrees with the infusion, the Note column says so and the typed value
stays.

The two things the analyst chooses per row are here rather than in
`standards.py`: which peak is the fragment (the base peak, or one of the
strongest few, labelled with the ion the explanation matched to it), and
whether the row is an internal standard. Changing either rebuilds that row's
plan, so the Precursor, Fragment and Note cells always describe what would
actually be written.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from .. import audit, standards
from ..session import Session
from .help_window import describe, open_manual

HELP_PAGE = "infusion-report"

COLUMNS = ["Use", "Compound", "Into", "Precursor", "Fragment", "Formula",
           "Adduct", "IS", "Note"]
COL = {name: index for index, name in enumerate(COLUMNS)}


class StandardsDialog(QtWidgets.QDialog):
    """Tick the infusions to write into the method, then apply."""

    def __init__(self, session: Session, rows, parent=None):
        super().__init__(parent)
        self.session = session
        self.rows = list(rows)
        #: the acquisition day per sample, so the provenance carries when the
        #: instrument measured and not when this button was pressed
        self.dates = {
            str(getattr(standards.report_of(row), "sample", "")):
                standards.acquisition_time(
                    session, getattr(standards.report_of(row), "sample", ""))
            for row in self.rows}
        self.fragments = [standards.BASE_PEAK] * len(self.rows)
        self.internal = [True] * len(self.rows)
        self.plans: list[standards.Plan] = [self._plan(index)
                                            for index in range(len(self.rows))]
        self.applied = 0
        #: rows that were ticked and had nothing left to write — a second
        #: infusion of a compound the first one already completed
        self.skipped: list[str] = []

        self.setWindowTitle("Use the infusions in the method")
        self.resize(1100, 460)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Each infusion becomes a component: the formula it was explained "
            "with, the adduct read off the channel’s written precursor, and "
            "the <b>exact</b> mass of that adduct as the precursor — the "
            "written value is what the instrument was given and is good only "
            "to the decimals it was typed with, so both are shown. An "
            "infusion has no retention time and none is invented; "
            "<i>Check method</i> will say so. A compound the method already "
            "carries has its empty cells filled and nothing else: where a "
            "typed value disagrees, the Note says so and the typed value "
            "stays.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.table = QtWidgets.QTableWidget(len(self.rows), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setSectionResizeMode(
            COL["Note"], QtWidgets.QHeaderView.ResizeMode.Stretch)
        for index in range(len(self.rows)):
            self._build_row(index)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        ).setText("Write the ticked rows into the method")
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply
                            ).clicked.connect(self.apply_selected)
        layout.addWidget(self.buttons)
        self._describe()

    # -- the plans ------------------------------------------------------------ #
    def _plan(self, index: int) -> standards.Plan:
        row = self.rows[index]
        sample = str(getattr(standards.report_of(row), "sample", ""))
        return standards.plan_for(
            row, self.session.method,
            as_internal_standard=self.internal[index],
            fragment=self.fragments[index],
            acquired=self.dates.get(sample, ""))

    def _build_row(self, index: int) -> None:
        plan = self.plans[index]
        report = standards.report_of(self.rows[index])

        tick = QtWidgets.QTableWidgetItem()
        tick.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                      | QtCore.Qt.ItemFlag.ItemIsEnabled)
        tick.setCheckState(QtCore.Qt.CheckState.Checked if plan.offered
                           else QtCore.Qt.CheckState.Unchecked)
        if not plan.offered:
            tick.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.table.setItem(index, COL["Use"], tick)

        name = QtWidgets.QTableWidgetItem(
            plan.name or str(getattr(report, "sample", "")))
        name.setToolTip(str(getattr(report, "sample", "")))
        self.table.setItem(index, COL["Compound"], name)

        combo = QtWidgets.QComboBox()
        for text, value in self._fragment_options(report):
            combo.addItem(text, value)
        combo.currentIndexChanged.connect(
            lambda _i, row=index: self._fragment_chosen(row))
        combo.setEnabled(combo.count() > 0)
        self.table.setCellWidget(index, COL["Fragment"], combo)

        box = QtWidgets.QCheckBox()
        box.setChecked(self.internal[index])
        box.setToolTip("Write the component as an internal standard")
        box.toggled.connect(lambda on, row=index: self._is_chosen(row, on))
        holder = QtWidgets.QWidget()
        inner = QtWidgets.QHBoxLayout(holder)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(box)
        inner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(index, COL["IS"], holder)

        for column in (COL["Into"], COL["Precursor"], COL["Formula"],
                       COL["Adduct"], COL["Note"]):
            self.table.setItem(index, column, QtWidgets.QTableWidgetItem(""))
        self._write_row(index)

    @staticmethod
    def _fragment_options(report) -> list[tuple[str, object]]:
        """The base peak first, then the other strong peaks it is chosen from."""
        choices = standards.fragment_choices(report)
        if not choices:
            return [("no peak to take", None)]
        options = []
        base = next((c for c in choices if c.base), choices[0])
        options.append((f"base peak · {base.text}", standards.BASE_PEAK))
        for choice in choices:
            if choice is base:
                continue
            options.append((choice.text, choice.mz))
        return options

    def _fragment_chosen(self, index: int) -> None:
        combo = self.table.cellWidget(index, COL["Fragment"])
        if not isinstance(combo, QtWidgets.QComboBox):
            return
        self.fragments[index] = combo.currentData()
        self.plans[index] = self._plan(index)
        self._write_row(index)
        self._describe()

    def _is_chosen(self, index: int, on: bool) -> None:
        self.internal[index] = bool(on)
        self.plans[index] = self._plan(index)
        self._write_row(index)
        self._describe()

    def _write_row(self, index: int) -> None:
        plan = self.plans[index]
        component = plan.proposed
        cells = {
            COL["Into"]: plan.into,
            COL["Precursor"]: ("—" if component is None
                               else f"{component.precursor:.4f}"),
            COL["Formula"]: plan.identification.formula or "—",
            COL["Adduct"]: plan.identification.adduct or "—",
            COL["Note"]: plan.note,
        }
        for column, text in cells.items():
            item = self.table.item(index, column)
            if item is None:
                item = QtWidgets.QTableWidgetItem()
                self.table.setItem(index, column, item)
            item.setText(text)
            item.setToolTip(plan.audit_note if column == COL["Note"] else text)
        tick = self.table.item(index, COL["Use"])
        if tick is not None and not plan.offered:
            tick.setCheckState(QtCore.Qt.CheckState.Unchecked)
            tick.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        elif tick is not None and not (tick.flags()
                                       & QtCore.Qt.ItemFlag.ItemIsEnabled):
            tick.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                          | QtCore.Qt.ItemFlag.ItemIsEnabled)
            tick.setCheckState(QtCore.Qt.CheckState.Checked)

    def _describe(self) -> None:
        offered = [p for p in self.plans if p.offered]
        new = [p for p in offered if p.is_new]
        refused = [p for p in self.plans if p.refusal]
        said = (f"{len(new)} new component(s), "
                f"{len(offered) - len(new)} completed")
        if refused:
            said += f", {len(refused)} refused — see the Note"
        self.status.setText(said + ".")

    # -- writing it ----------------------------------------------------------- #
    def selected(self) -> list[standards.Plan]:
        chosen = []
        for index, plan in enumerate(self.plans):
            item = self.table.item(index, COL["Use"])
            if (item is not None
                    and item.checkState() == QtCore.Qt.CheckState.Checked
                    and plan.offered):
                chosen.append(plan)
        return chosen

    def apply_selected(self) -> int:
        """
        Write the ticked rows; one audit entry per component.

        Each row is planned again against the method **as it stands at that
        moment**, because writing one row changes what the next one is
        writing into: two infusions of the same compound — the same vial at
        two collision energies — are one component, and the first of them
        fills the cells the second would have. The second then has nothing
        left to write and is reported as such rather than appended as a
        duplicate row with the same name and another fragment.
        """
        written, nothing = 0, []
        for index, plan in enumerate(self.plans):
            item = self.table.item(index, COL["Use"])
            if item is None or item.checkState() != QtCore.Qt.CheckState.Checked:
                continue
            plan = self.plans[index] = self._plan(index)
            if not plan.offered:
                nothing.append(plan.name)
                continue
            before, after = plan.audit_before, plan.audit_after
            note = plan.audit_note
            component = plan.apply(self.session.method)
            if component is None:
                nothing.append(plan.name)
                continue
            self.session.record(audit.COMPONENT_FROM_INFUSION, component.name,
                                before=before, after=after, note=note)
            written += 1
        self.applied = written
        self.skipped = list(nothing)
        if written:
            self.session.notify_method_changed()
        self.accept()
        return written
