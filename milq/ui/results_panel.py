"""Integration results table (chromatographic peaks)."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from PyQt6 import QtCore, QtWidgets
from .flow_layout import FlowLayout

COLUMNS = ["Component", "Sample", "Channel", "m/z", "RT", "Area", "Height",
           "Width", "S/N", "Note"]


@dataclass
class Result:
    """One table row: an integrated peak of one trace."""

    component: str
    sample: str
    channel: str
    mz: str
    rt: float
    area: float
    height: float
    width: float
    snr: float
    note: str = ""
    trace_key: str = ""
    start_rt: float = 0.0
    end_rt: float = 0.0

    def as_row(self) -> list[str]:
        return [
            self.component,
            self.sample,
            self.channel,
            self.mz,
            f"{self.rt:.3f}",
            f"{self.area:,.0f}",
            f"{self.height:,.0f}",
            f"{self.width:.3f}",
            "—" if self.snr is None else
            ("∞" if self.snr == float("inf") else f"{self.snr:.0f}"),
            self.note,
        ]


class ResultsPanel(QtWidgets.QWidget):
    """Integration results, exportable to CSV."""

    sigResultActivated = QtCore.pyqtSignal(object)  # Result

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[Result] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setToolTip("Double-click to bring the chromatogram to the peak")
        layout.addWidget(self.table, 1)

        buttons = FlowLayout()
        self.btn_export = QtWidgets.QPushButton("Export CSV…")
        self.btn_clear = QtWidgets.QPushButton("Clear")
        buttons.addWidget(self.btn_export)
        buttons.addWidget(self.btn_clear)
        layout.addLayout(buttons)

        self.btn_export.clicked.connect(self._export)
        self.btn_clear.clicked.connect(self.clear)
        self.table.cellDoubleClicked.connect(self._activated)

    def set_results(self, results: list[Result]) -> None:
        self._results = list(results)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            for column, text in enumerate(result.as_row()):
                item = QtWidgets.QTableWidgetItem(text)
                if column >= 4:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, row)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def add_results(self, results: list[Result]) -> None:
        self.set_results(self._results + list(results))

    def clear(self) -> None:
        self.set_results([])

    @property
    def results(self) -> list[Result]:
        return list(self._results)

    def _activated(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        index = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if index is not None and 0 <= index < len(self._results):
            self.sigResultActivated.emit(self._results[index])

    def _export(self) -> None:
        if not self._results:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export results", "results.csv", "CSV (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            for result in self._results:
                writer.writerow([
                    result.component, result.sample, result.channel, result.mz,
                    f"{result.rt:.4f}", f"{result.area:.4f}",
                    f"{result.height:.4f}", f"{result.width:.4f}",
                    "" if result.snr is None or result.snr == float("inf")
                    else f"{result.snr:.2f}",
                    result.note,
                ])
