"""Samples workspace: the batch table."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..audit import SAMPLE_EDITED
from ..samples import (SAMPLE_TYPES, by_acquisition_time, numbering_start,
                       parse_batch_order)
from ..session import Session
from ..validation import acquisition_order
from . import style
from .flow_layout import FlowLayout

COLUMNS = ["Batch order", "File", "Sample", "Type", "Group", "Actual conc.",
           "Dilution", "Vial", "Acquired", "Comment"]
COL = {name: i for i, name in enumerate(COLUMNS)}
EDITABLE = (COL["Batch order"], COL["Sample"], COL["Actual conc."],
            COL["Dilution"], COL["Comment"])

#: the choices under the Number button
NUMBER_IN_TABLE_ORDER = "Number in table order"
NUMBER_BY_TIME = "Number by acquisition time"
CLEAR_ORDER = "Clear batch order"


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
        bar.addSpacing(20)
        bar.addWidget(QtWidgets.QLabel("Set dilution:"))
        self.dilution_edit = QtWidgets.QLineEdit()
        self.dilution_edit.setPlaceholderText("e.g. 10")
        self.dilution_edit.setMaximumWidth(80)
        self.dilution_edit.setToolTip(
            "One dilution factor for every selected row: a number above zero.")
        bar.addWidget(self.dilution_edit)
        self.btn_apply_dilution = QtWidgets.QPushButton("Apply")
        bar.addWidget(self.btn_apply_dilution)
        bar.addSpacing(20)
        self.btn_number = QtWidgets.QToolButton()
        self.btn_number.setText("Batch order")
        self.btn_number.setToolTip(
            "Number the selected rows — every row when none is selected — as "
            "the run's injection order. Charts through the run follow it.")
        self.btn_number.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QtWidgets.QMenu(self.btn_number)
        for label in (NUMBER_IN_TABLE_ORDER, NUMBER_BY_TIME, CLEAR_ORDER):
            menu.addAction(label).triggered.connect(
                lambda _checked=False, how=label: self._number_rows(how))
        self.btn_number.setMenu(menu)
        bar.addWidget(self.btn_number)
        self.btn_sort = QtWidgets.QPushButton("Sort by batch order")
        self.btn_sort.setToolTip(
            "Put the rows in the order of the run: batch order, then "
            "acquisition time. Results follow the next time the batch is "
            "processed.")
        bar.addWidget(self.btn_sort)
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
        self.table.horizontalHeaderItem(COL["Batch order"]).setToolTip(
            "The injection's place in the run, 1 for the first. Typed, not "
            "read from the file; where it is set it orders Batch QC and the "
            "mass drift.")
        # a column copied out of a spreadsheet goes into the rows selected —
        # the editor's own paste still applies while a cell is being edited
        paste = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Paste, self.table)
        paste.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        paste.activated.connect(self._paste)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.btn_close.clicked.connect(self._close_all)
        self.btn_apply_type.clicked.connect(self._apply_type)
        self.btn_apply_group.clicked.connect(self._apply_group)
        self.btn_apply_conc.clicked.connect(self._apply_concentration)
        self.btn_apply_dilution.clicked.connect(self._apply_dilution)
        self.dilution_edit.returnPressed.connect(self._apply_dilution)
        self.btn_sort.clicked.connect(self._sort_by_order)
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
                COL["Batch order"]: ("" if entry.batch_order is None
                                     else str(entry.batch_order)),
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
            value = self._dilution(text) if text else 1.0
            if value is None:
                self._revert(item, f"{entry.dilution_factor:g}")
                self._report(f"A dilution factor is a number above zero; "
                             f"{text!r} left {entry.name} at "
                             f"{entry.dilution_factor:g}.")
                return
            self._record(entry, "dilution", entry.dilution_factor, value)
            entry.dilution_factor = value
        elif column == COL["Batch order"]:
            value = parse_batch_order(text)
            if text and value is None:
                self._revert(item, self._order_text(entry.batch_order))
                self._report(f"A batch order is a whole number from 1; "
                             f"{text!r} left {entry.name} as it was.")
                return
            self._set_order(entry, value)
        self._update_status()

    def _revert(self, item, text: str) -> None:
        self._loading = True
        item.setText(text)
        self._loading = False

    @staticmethod
    def _order_text(order: int | None) -> str:
        return "" if order is None else str(order)

    def _set_order(self, entry, order: int | None) -> None:
        self._record(entry, "batch order", self._order_text(entry.batch_order),
                     self._order_text(order))
        entry.batch_order = order

    @classmethod
    def _dilution(cls, text: str) -> float | None:
        """A dilution factor as typed, or None when it is not one: > 0."""
        value = cls._number(text.strip())
        if value is None or not value > 0 or value == float("inf"):
            return None
        return value

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

    def _apply_dilution(self) -> None:
        """One dilution factor onto every selected row."""
        text = self.dilution_edit.text().strip()
        value = self._dilution(text)
        if value is None:
            self._report("Type a dilution factor above zero first."
                         if not text else
                         f"A dilution factor is a number above zero, not {text!r}.")
            return
        rows = self._selected_rows()
        if not rows:
            self._report("Select the rows to dilute first.")
            return
        self._loading = True
        for row in rows:
            entry = self.session.entries[row]
            self._record(entry, "dilution", entry.dilution_factor, value)
            entry.dilution_factor = value
            self.table.item(row, COL["Dilution"]).setText(f"{value:g}")
        self._loading = False
        self._update_status()
        self._report(f"Dilution {value:g} set on {len(rows)} sample(s).")

    def _number_rows(self, how: str) -> None:
        """
        Give the selected rows — every row when none is selected — a batch
        order: 1, 2, 3… in the table's order or by the acquisition time the
        files carry, or none.

        Every row numbered starts at 1; a selection starts where the rows it
        holds already were, or after the highest number elsewhere
        (`samples.numbering_start`), so numbering a stretch never collides
        with rows it did not touch.
        """
        entries = self.session.entries
        rows = self._selected_rows() or list(range(len(entries)))
        if not rows:
            self._report("There are no samples to number.")
            return
        targets = [entries[row] for row in rows]
        if how == CLEAR_ORDER:
            numbers = [None] * len(targets)
        else:
            if how == NUMBER_BY_TIME:
                targets = by_acquisition_time(targets)
            start = numbering_start(entries, targets)
            numbers = list(range(start, start + len(targets)))
        self._loading = True
        for entry, number in zip(targets, numbers, strict=True):
            self._set_order(entry, number)
            row = entries.index(entry)
            self.table.item(row, COL["Batch order"]).setText(
                self._order_text(number))
        self._loading = False
        self._update_status()
        if how == CLEAR_ORDER:
            self._report(f"Batch order cleared on {len(targets)} sample(s).")
            return
        untimed = (sum(1 for e in targets
                       if not getattr(e.sample, "acquisition_time", ""))
                   if how == NUMBER_BY_TIME else 0)
        said = (f"{len(targets)} sample(s) numbered {numbers[0]}–{numbers[-1]}"
                + (" by acquisition time" if how == NUMBER_BY_TIME else ""))
        if untimed:
            said += (f"; {untimed} carry no time and were numbered last, "
                     f"in table order")
        self._report(said + ".")

    def _sort_by_order(self) -> None:
        """Put the rows in the run's order: batch order, then the clock."""
        entries = self.session.entries
        ordered = acquisition_order(entries)
        if [id(e) for e in ordered] == [id(e) for e in entries]:
            self._report("The rows are already in batch order.")
            return
        self.session.entries[:] = ordered
        self.session.sigSamplesChanged.emit()
        self._report(f"{len(ordered)} sample(s) sorted by batch order.")

    # -- pasting a column out of a spreadsheet ------------------------------------ #
    def _paste(self) -> None:
        text = QtWidgets.QApplication.clipboard().text()
        self._paste_text(text)

    def _paste_text(self, text: str) -> None:
        """
        Cells copied out of a spreadsheet, into the table from the current
        cell down and to the right — or, a single value with several rows
        selected, into that column of every one of them.

        Each cell goes through the same path as typing it, so a value that
        would be refused typed is refused pasted, and the trail records one
        line per cell changed. Read-only columns are skipped.
        """
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        grid = [line.split("\t") for line in lines]
        if not grid:
            self._report("There is nothing on the clipboard to paste.")
            return
        rows = self._selected_rows()
        current = self.table.currentIndex()
        column = current.column() if current.isValid() else -1
        if column < 0:
            self._report("Click the cell to paste into first.")
            return
        if len(grid) == 1 and len(grid[0]) == 1 and len(rows) > 1:
            targets = [(row, column, grid[0][0]) for row in rows]
        else:
            first = rows[0] if rows else current.row()
            targets = [(first + i, column + j, value)
                       for i, cells in enumerate(grid)
                       for j, value in enumerate(cells)
                       if first + i < self.table.rowCount()
                       and column + j < self.table.columnCount()]
        pasted = skipped = 0
        for row, col, value in targets:
            if self._set_cell(row, col, value.strip()):
                pasted += 1
            else:
                skipped += 1
        self._update_status()
        said = f"Pasted {pasted} cell(s)"
        if skipped:
            said += f"; {skipped} left as they were (read-only or not valid there)"
        self._report(said + ".")

    def _set_cell(self, row: int, column: int, value: str) -> bool:
        """One pasted value into one cell, as though typed. True if taken."""
        if row >= len(self.session.entries):
            return False
        if column == COL["Type"]:
            match = next((t for t in SAMPLE_TYPES
                          if t.lower() == value.lower()), None)
            widget = self.table.cellWidget(row, column)
            if match is None or widget is None:
                return False
            widget.setCurrentText(match)
            return True
        if column == COL["Group"]:
            widget = self.table.cellWidget(row, column)
            if widget is None:
                return False
            widget.setCurrentText(value)
            self._commit_group(row)
            return True
        item = self.table.item(row, column)
        if column not in EDITABLE or item is None:
            return False
        if column == COL["Dilution"] and value and self._dilution(value) is None:
            return False
        if (column == COL["Actual conc."] and value
                and self._number(value) is None):
            return False
        if (column == COL["Batch order"] and value
                and parse_batch_order(value) is None):
            return False
        item.setText(value)
        return True

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
        numbered = sum(1 for e in entries if e.batch_order is not None)
        if numbered:
            text += (" · batch order on every sample" if numbered == len(entries)
                     else f" · batch order on {numbered} of {len(entries)}")
        self.status.setText(text)

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
