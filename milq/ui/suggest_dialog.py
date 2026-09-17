"""
What the data proposes, put in front of somebody who can accept or decline it.

Nothing here decides anything. Every row carries what it rests on — how many
injections agree, how tall the peak is, and how accurate the estimator proved
to be at that height on the components of this same method whose time is
already known — because a retention time written into a method on the
program's say-so is a retention time nobody can defend later.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..session import Session
from ..suggest import Suggestions, suggest_times, suggest_windows

CHECKED = QtCore.Qt.CheckState.Checked
UNCHECKED = QtCore.Qt.CheckState.Unchecked


class SuggestDialog(QtWidgets.QDialog):
    """Retention times and window widths the open files can supply."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Suggest from data")
        self.resize(920, 620)

        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel("Reading the batch…")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.tabs = QtWidgets.QTabWidget()
        self.times = self._table(
            ["", "Component", "RT", "Support", "Height",
             "How well this did, at this height", "Note"])
        self.windows = self._table(
            ["", "Component", "Now", "Points", "Suggested", "Points"])
        self.tabs.addTab(self.times, "Retention times")
        self.tabs.addTab(self.windows, "Windows")
        layout.addWidget(self.tabs, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        from .help_window import describe, open_manual
        describe(self, "suggest-from-data")
        self.buttons.helpRequested.connect(
            lambda: open_manual(self, "suggest-from-data"))
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply).setText(
                "Apply the ticked rows")
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply).clicked.connect(
                self.apply_selected)
        layout.addWidget(self.buttons)

        self._suggestions: Suggestions | None = None
        self._windows: list = []

    @staticmethod
    def _table(headers: list[str]) -> QtWidgets.QTableWidget:
        table = QtWidgets.QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(20)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 28)          # the tick, and nothing else
        return table

    # -- content ------------------------------------------------------------- #
    def load(self) -> bool:
        """Read the batch. False when there was nothing to read."""
        progress = QtWidgets.QProgressDialog(
            "Looking for every peak in every injection…", "Cancel", 0, 100,
            self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        def tick(done: int, total: int):
            progress.setValue(int(done / max(total, 1) * 100))
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        found = suggest_times(self.session.method, self.session.entries, tick)
        progress.close()
        if found.note:
            QtWidgets.QMessageBox.information(self, "Suggest from data",
                                              found.note)
            return False
        self._suggestions = found
        self._windows = suggest_windows(self.session.method,
                                        self.session.entries)
        self._describe()
        self._fill_times()
        self._fill_windows()
        return True

    def _describe(self) -> None:
        found = self._suggestions
        known = [b for b in found.bands if b.components]
        said = [f"{found.injections} injections, sampled every "
                f"{found.step * 60:.1f} s — no measured time is better than "
                f"that."]
        if known:
            parts = ", ".join(
                f"{b.within:.0%} at {b.low:,.0f}–"
                f"{'∞' if b.high == float('inf') else format(b.high, ',.0f')} "
                f"(n={b.components})" for b in known)
            said.append(f"Checked against the {sum(b.components for b in known)} "
                        f"components that already declare a time, the estimate "
                        f"landed within one sampling interval: {parts}.")
        else:
            said.append("No component of this method declares a time, so "
                        "there was nothing to check the estimator against. "
                        "Treat every row below as unverified.")
        self.summary.setText(" ".join(said))

    def _fill_times(self) -> None:
        rows = sorted(self._suggestions.offered, key=lambda e: -e.height)
        self.times.setRowCount(len(rows))
        for index, estimate in enumerate(rows):
            band = self._suggestions.confidence(estimate)
            confidence = (f"{band.within:.0%} of {band.components} landed "
                          f"within {self._suggestions.step * 60:.0f} s"
                          if band and band.components
                          else "nothing to compare against at this height")
            cells = [estimate.component, f"{estimate.rt:.2f}",
                     f"{estimate.support}/{estimate.injections}",
                     f"{estimate.height:,.0f}", confidence, estimate.note]
            self._put(self.times, index, cells, estimate,
                      # ticked only where the estimator proved itself
                      band is not None and band.components > 0
                      and band.within >= 0.6 and not estimate.note)
        self.times.setColumnWidth(0, 28)
        self.times.setColumnWidth(1, 200)
        for column, width in ((2, 60), (3, 70), (4, 80), (5, 230)):
            self.times.setColumnWidth(column, width)

    def _fill_windows(self) -> None:
        self.windows.setRowCount(len(self._windows))
        for index, w in enumerate(self._windows):
            cells = [w.component, f"±{w.current:.2f}", f"{w.points_now}",
                     f"±{w.suggested:.2f}", f"{w.points_then}"]
            self._put(self.windows, index, cells, w, True)
        self.windows.setColumnWidth(0, 28)
        self.windows.setColumnWidth(1, 240)

    @staticmethod
    def _put(table, row: int, cells: list[str], payload, ticked: bool) -> None:
        box = QtWidgets.QTableWidgetItem()
        box.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                     | QtCore.Qt.ItemFlag.ItemIsEnabled)
        box.setCheckState(CHECKED if ticked else UNCHECKED)
        box.setData(QtCore.Qt.ItemDataRole.UserRole, payload)
        table.setItem(row, 0, box)
        for column, text in enumerate(cells, start=1):
            table.setItem(row, column, QtWidgets.QTableWidgetItem(text))

    # -- applying ------------------------------------------------------------- #
    def _ticked(self, table) -> list:
        out = []
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.checkState() == CHECKED:
                out.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
        return out

    def apply_selected(self) -> None:
        times = self._ticked(self.times)
        windows = self._ticked(self.windows)
        if not times and not windows:
            self.reject()
            return
        by_name = {c.name: c for c in self.session.method.components}
        for estimate in times:
            component = by_name.get(estimate.component)
            if component is not None:
                component.rt = round(float(estimate.rt), 2)
        for suggestion in windows:
            component = by_name.get(suggestion.component)
            if component is not None:
                component.rt_halfwidth = float(suggestion.suggested)
        self.session.notify_method_changed()
        QtWidgets.QMessageBox.information(
            self, "Suggest from data",
            f"{len(times)} retention time(s) and {len(windows)} window(s) "
            f"written into the method. Nothing is processed until the batch "
            f"is run again.")
        self.accept()
