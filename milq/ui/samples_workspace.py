"""Samples workspace: the batch table."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..audit import SAMPLE_EDITED
from ..samples import SAMPLE_TYPES
from ..session import Session
from . import style
from .flow_layout import FlowLayout

COLUMNS = ["File", "Sample", "Type", "Group", "Actual conc.", "Dilution",
           "Vial", "Acquired", "Comment"]
COL = {name: i for i, name in enumerate(COLUMNS)}
EDITABLE = (COL["Sample"], COL["Actual conc."], COL["Dilution"], COL["Comment"])


class SamplesWorkspace(QtWidgets.QWidget):
    """
    Sample type, expected concentration and dilution live here.

    None of it is recorded in the raw file — every injection comes back as
    `kUnknown` — so it is entered once and saved with the project.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._loading = False

        layout = QtWidgets.QVBoxLayout(self)

        bar = FlowLayout()
        self.btn_open = QtWidgets.QPushButton("Add data files…")
        self.btn_close = QtWidgets.QPushButton("Close all")
        bar.addWidget(self.btn_open)
        bar.addWidget(self.btn_close)
        bar.addSpacing(20)
        bar.addWidget(QtWidgets.QLabel("Set type of selected rows:"))
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(SAMPLE_TYPES)
        bar.addWidget(self.type_combo)
        self.btn_apply_type = QtWidgets.QPushButton("Apply")
        bar.addWidget(self.btn_apply_type)
        bar.addSpacing(20)
        bar.addWidget(QtWidgets.QLabel("Set group:"))
        self.group_edit = QtWidgets.QComboBox()
        self.group_edit.setEditable(True)
        self.group_edit.setMinimumWidth(140)
        self.group_edit.setToolTip(
            "The study group an injection belongs to — control, treated, day 7. "
            "Statistics can summarise by this instead of by sample type.")
        bar.addWidget(self.group_edit)
        self.btn_apply_group = QtWidgets.QPushButton("Apply")
        bar.addWidget(self.btn_apply_group)
        bar.addSpacing(20)
        self.btn_apply_conc = QtWidgets.QPushButton("Apply concentration to selection")
        bar.addWidget(self.btn_apply_conc)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            COL["Comment"], QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.btn_close.clicked.connect(self._close_all)
        self.btn_apply_type.clicked.connect(self._apply_type)
        self.btn_apply_group.clicked.connect(self._apply_group)
        self.btn_apply_conc.clicked.connect(self._apply_concentration)
        self.table.itemChanged.connect(self._on_edit)
        session.sigSamplesChanged.connect(self.reload)
        self.reload()

    def _record(self, entry, field: str, before, after) -> None:
        """
        Note one field of one injection changed by hand.

        Nothing here is in the raw file — every injection comes back as
        `kUnknown` — so every one of these values was typed by somebody, and
        the trail is the only record that it was.
        """
        if before == after:
            return
        self.session.record(SAMPLE_EDITED, f"{entry.name} · {field}",
                            before, after, note="samples table")

    # -- table <-> session ------------------------------------------------------- #
    def reload(self) -> None:
        self._loading = True
        entries = self.session.entries
        known_groups = self._known_groups()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            meta = entry.sample.metadata() if entry.is_loaded else {}
            values = {
                COL["File"]: entry.filename,
                COL["Sample"]: entry.name,
                COL["Actual conc."]: ("" if entry.actual_concentration is None
                                      else f"{entry.actual_concentration:g}"),
                COL["Dilution"]: f"{entry.dilution_factor:g}",
                COL["Vial"]: meta.get("Vial", ""),
                COL["Acquired"]: meta.get("Acquired", ""),
                COL["Comment"]: entry.comment,
            }
            for column, text in values.items():
                item = QtWidgets.QTableWidgetItem(text)
                if column not in EDITABLE:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    item.setForeground(QtCore.Qt.GlobalColor.darkGray)
                self.table.setItem(row, column, item)

            combo = QtWidgets.QComboBox()
            combo.addItems(SAMPLE_TYPES)
            combo.setCurrentText(entry.sample_type)
            combo.currentTextChanged.connect(
                lambda text, r=row: self._set_type(r, text))
            self.table.setCellWidget(row, COL["Type"], combo)

            # editable: the first injection of a group types it, the rest pick
            # it off the list, which is what keeps one study group from
            # becoming three through a stray capital letter
            group = QtWidgets.QComboBox()
            group.setEditable(True)
            group.addItem("")
            group.addItems(known_groups)
            group.setCurrentText(entry.sample_group)
            # committed when the analyst picks from the list or leaves the
            # field, never per keystroke — currentTextChanged would rewrite the
            # entry and rebuild the list in the middle of a word
            group.activated.connect(lambda _i, r=row: self._commit_group(r))
            group.lineEdit().editingFinished.connect(
                lambda r=row: self._commit_group(r))
            self.table.setCellWidget(row, COL["Group"], group)

            if not entry.is_loaded:
                for column in range(len(COLUMNS)):
                    item = self.table.item(row, column)
                    if item:
                        item.setBackground(QtCore.Qt.GlobalColor.lightGray)
        self.table.resizeColumnsToContents()
        style.fit_cell_widgets(self.table)
        self._refresh_group_choices()
        self._loading = False
        self._update_status()

    def _known_groups(self) -> list[str]:
        """Every group already in use, in the order the batch introduces them."""
        seen: list[str] = []
        for entry in self.session.entries:
            if entry.sample_group and entry.sample_group not in seen:
                seen.append(entry.sample_group)
        return seen

    def _refresh_group_choices(self) -> None:
        """Put a newly typed group on offer to every other row."""
        known = self._known_groups()
        options = [""] + known
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, COL["Group"])
            if not isinstance(combo, QtWidgets.QComboBox):
                continue
            if combo.lineEdit() is not None and combo.lineEdit().hasFocus():
                continue
            current = combo.currentText()
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItems(options)
            combo.setCurrentText(current)
            combo.blockSignals(blocked)
        current = self.group_edit.currentText()
        blocked = self.group_edit.blockSignals(True)
        self.group_edit.clear()
        self.group_edit.addItems(known)
        self.group_edit.setCurrentText(current)
        self.group_edit.blockSignals(blocked)

    def _commit_group(self, row: int) -> None:
        combo = self.table.cellWidget(row, COL["Group"])
        if self._loading or combo is None or row >= len(self.session.entries):
            return
        group = combo.currentText().strip()
        entry = self.session.entries[row]
        if group == entry.sample_group:
            return
        self._record(entry, "group", entry.sample_group or "none",
                     group or "none")
        entry.sample_group = group
        self._refresh_group_choices()
        self._update_status()

    def _apply_group(self) -> None:
        group = self.group_edit.currentText().strip()
        rows = self._selected_rows()
        if not rows:
            self._report("Select the rows to put in the group first.")
            return
        self._loading = True
        for row in rows:
            entry = self.session.entries[row]
            self._record(entry, "group", entry.sample_group or "none",
                         group or "none")
            entry.sample_group = group
            widget = self.table.cellWidget(row, COL["Group"])
            if widget is not None:
                widget.setCurrentText(group)
        self._loading = False
        self._refresh_group_choices()
        self._update_status()
        self._report(f"{len(rows)} sample(s) put in "
                     + (f"group {group}." if group else "no group."))

    def _on_edit(self, item) -> None:
        if self._loading:
            return
        row, column = item.row(), item.column()
        if row >= len(self.session.entries):
            return
        entry = self.session.entries[row]
        text = item.text().strip()
        # itemChanged arrives once the editor closes, which is one entry per
        # cell edited rather than one per keystroke
        if column == COL["Sample"]:
            self._record(entry, "name", entry.name, text or entry.name)
            entry.name = text or entry.name
        elif column == COL["Comment"]:
            self._record(entry, "comment", entry.comment, text)
            entry.comment = text
        elif column == COL["Actual conc."]:
            value = self._number(text)
            self._record(entry, "concentration",
                         entry.actual_concentration, value)
            entry.actual_concentration = value
        elif column == COL["Dilution"]:
            value = self._number(text) or 1.0
            self._record(entry, "dilution", entry.dilution_factor, value)
            entry.dilution_factor = value
        self._update_status()

    @staticmethod
    def _number(text: str) -> float | None:
        try:
            return float(text.replace(",", ".")) if text else None
        except ValueError:
            return None

    def _set_type(self, row: int, sample_type: str) -> None:
        if not self._loading and row < len(self.session.entries):
            entry = self.session.entries[row]
            self._record(entry, "type", entry.sample_type, sample_type)
            entry.sample_type = sample_type
            self._update_status()

    # -- actions ------------------------------------------------------------------ #
    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _apply_type(self) -> None:
        sample_type = self.type_combo.currentText()
        rows = self._selected_rows()
        for row in rows:
            widget = self.table.cellWidget(row, COL["Type"])
            if widget is not None:
                widget.setCurrentText(sample_type)
        self._report(f"{len(rows)} sample(s) set to {sample_type}.")

    def _apply_concentration(self) -> None:
        """
        Copy the concentration of the first selected row onto the rest — the
        usual case is a set of standards injected at the same level.
        """
        rows = self._selected_rows()
        if len(rows) < 2:
            self._report("Select the row to copy from, plus the rows to fill.")
            return
        source = self.session.entries[rows[0]].actual_concentration
        self._loading = True
        for row in rows[1:]:
            entry = self.session.entries[row]
            self._record(entry, "concentration",
                         entry.actual_concentration, source)
            entry.actual_concentration = source
            self.table.item(row, COL["Actual conc."]).setText(
                "" if source is None else f"{source:g}")
        self._loading = False
        self._report(f"Concentration copied to {len(rows) - 1} sample(s).")

    def _close_all(self) -> None:
        self.session.close_all()
        self._report("All files closed.")

    def _update_status(self) -> None:
        entries = self.session.entries
        by_type: dict[str, int] = {}
        for entry in entries:
            by_type[entry.sample_type] = by_type.get(entry.sample_type, 0) + 1
        summary = ", ".join(f"{n} {name}" for name, n in by_type.items())
        text = f"{len(entries)} sample(s)" + (f" — {summary}" if summary else "")
        groups = self._known_groups()
        if groups:
            ungrouped = sum(1 for e in entries if not e.sample_group)
            text += f" · {len(groups)} group(s): " + ", ".join(groups)
            if ungrouped:
                text += f" ({ungrouped} ungrouped)"
        self.status.setText(text)

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
