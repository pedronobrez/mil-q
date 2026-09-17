"""
The acquisition schedule the method implies, to take to the instrument.

A target cycle time — from what the batch measured, or typed — a pause and
a dwell floor, and the dialog says what the busiest moment of the run
leaves each transition, before the table is saved.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from ..schedule import (MIN_DWELL_MS, PAUSE_MS, Schedule, build_schedule,
                        suggested_cycle, write_csv)
from ..session import Session
from .help_window import describe, open_manual

HELP_PAGE = "acquisition-schedule"


class ScheduleDialog(QtWidgets.QDialog):
    COLUMNS = ["Component", "Q1", "Q3", "RT", "From", "To", "Dwell (ms)"]

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.schedule: Schedule | None = None
        self.setWindowTitle("Export acquisition schedule")
        self.resize(880, 600)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Every component with a retention time, acquired over its window. "
            "At any moment the instrument cycles through the transitions whose "
            "windows hold that moment, so the busiest moment decides what dwell "
            "a target cycle leaves each one. The file is a plain CSV whose "
            "columns map onto the vendor's table; Analyst takes one detection "
            "window for the whole method, in which case the widest here is the "
            "one to type.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        form = QtWidgets.QFormLayout()
        self.cycle = QtWidgets.QDoubleSpinBox()
        self.cycle.setRange(0.1, 120.0)
        self.cycle.setDecimals(1)
        self.cycle.setSuffix(" s")
        self.pause = QtWidgets.QDoubleSpinBox()
        self.pause.setRange(0.0, 100.0)
        self.pause.setDecimals(1)
        self.pause.setSuffix(" ms")
        self.pause.setValue(PAUSE_MS)
        self.pause.setToolTip("Spent moving from one transition to the next")
        self.floor = QtWidgets.QDoubleSpinBox()
        self.floor.setRange(0.1, 1000.0)
        self.floor.setDecimals(1)
        self.floor.setSuffix(" ms")
        self.floor.setValue(MIN_DWELL_MS)
        self.floor.setToolTip("The shortest dwell worth acquiring")
        form.addRow("Target cycle", self.cycle)
        form.addRow("Pause", self.pause)
        form.addRow("Dwell floor", self.floor)
        layout.addLayout(form)

        self.basis = QtWidgets.QLabel("")
        self.basis.setWordWrap(True)
        self.basis.setProperty("role", "hint")
        layout.addWidget(self.basis)

        self.summary = QtWidgets.QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QtWidgets.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save).setText(
            "Save CSV…")
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save
                            ).clicked.connect(self.save)
        layout.addWidget(self.buttons)

        cycle, note = self._starting_cycle()
        self.cycle.setValue(cycle if cycle is not None else 10.0)
        self.basis.setText(note)
        for widget in (self.cycle, self.pause, self.floor):
            widget.valueChanged.connect(self.rebuild)
        self.rebuild()
        self.saved_path = ""

    def _starting_cycle(self) -> tuple[float | None, str]:
        from ..sampling import sampling_report

        session = self.session
        if not len(session.results):
            return suggested_cycle(None)
        report = sampling_report(session.results, session.entries, session.method)
        cycle, note = suggested_cycle(report)
        return cycle, ("Starting from " + note) if cycle is not None else note

    def rebuild(self, *_args) -> None:
        self.schedule = build_schedule(self.session.method, self.cycle.value(),
                                       self.pause.value(), self.floor.value())
        schedule = self.schedule
        self.summary.setText(schedule.summary())
        self.summary.setStyleSheet(
            "" if schedule.feasible or schedule.note else "color: #a4262c;")
        dwell = schedule.dwell_ms
        self.table.setRowCount(len(schedule.slots))
        for row, slot in enumerate(schedule.slots):
            cells = [slot.component + (" (IS)" if slot.is_internal_standard else ""),
                     f"{slot.precursor:.4f}", f"{slot.fragment:.4f}",
                     f"{slot.rt:.2f}", f"{slot.start:.2f}", f"{slot.end:.2f}",
                     "—" if dwell is None else f"{dwell:.1f}"]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save
                            ).setEnabled(bool(schedule.slots))

    def save(self) -> None:
        if self.schedule is None or not self.schedule.slots:
            return
        stem = (os.path.splitext(os.path.basename(self.session.project_path))[0]
                if self.session.project_path else "method")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save the acquisition schedule", f"{stem}-schedule.csv",
            "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        self.saved_path = write_csv(self.schedule, path)
        self.accept()
