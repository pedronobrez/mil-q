"""Grouped statistics across the batch."""

from __future__ import annotations

import csv

from PyQt6 import QtCore, QtGui, QtWidgets

from ..statistics import (GROUP_BY_SAMPLE_GROUP, GROUPINGS, QUANTITIES,
                          summarise)
from ..session import Session
from . import theme
from .flow_layout import FlowLayout

FIXED = ["Component", "Group", "n", "Mean", "SD", "%CV", "Accuracy %"]


class StatisticsPanel(QtWidgets.QWidget):
    """Mean, SD and %CV per component and group, with the values behind them."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._rows = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        bar.addWidget(QtWidgets.QLabel("Group by"))
        self.grouping = QtWidgets.QComboBox()
        self.grouping.addItems(list(GROUPINGS))
        bar.addWidget(self.grouping)
        bar.addWidget(QtWidgets.QLabel("Quantity"))
        self.quantity = QtWidgets.QComboBox()
        self.quantity.addItems(list(QUANTITIES))
        bar.addWidget(self.quantity)
        self.btn_export = QtWidgets.QPushButton("Export CSV…")
        bar.addStretch(1)
        bar.addWidget(self.btn_export)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(FIXED))
        self.table.setHorizontalHeaderLabels(FIXED)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(23)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.grouping.currentTextChanged.connect(self.reload)
        self.quantity.currentTextChanged.connect(self.reload)
        self.btn_export.clicked.connect(self._export)
        session.sigResultsChanged.connect(self.reload)

    def reload(self, *_args) -> None:
        rows = summarise(self.session.results, self.session.entries,
                         self.session.method, self.grouping.currentText(),
                         self.quantity.currentText())
        self._rows = rows
        widest = max((len(r.values) for r in rows), default=0)
        headers = FIXED + [f"Value {i + 1}" for i in range(widest)]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))

        for index, row in enumerate(rows):
            cells = [
                row.component, row.group, f"{row.used} of {row.total}",
                "—" if row.mean is None else f"{row.mean:,.4g}",
                "—" if row.standard_deviation is None else f"{row.standard_deviation:,.4g}",
                "—" if row.percent_cv is None else f"{row.percent_cv:.2f}",
                "—" if row.accuracy is None else f"{row.accuracy:.1f}",
            ]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column >= 2:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(index, column, item)

            for offset, (name, value, used) in enumerate(row.values):
                text = "—" if value is None else f"{value:,.4g}"
                item = QtWidgets.QTableWidgetItem(text)
                item.setToolTip(name)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if not used:
                    # struck through rather than hidden: an excluded injection
                    # should stay visible, so the reader can see what was left out
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                    item.setForeground(QtGui.QBrush(QtGui.QColor(theme.ink_faint())))
                self.table.setItem(index, len(FIXED) + offset, item)

        self.table.resizeColumnsToContents()
        grouping = self.grouping.currentText()
        if not rows and grouping == GROUP_BY_SAMPLE_GROUP:
            # an empty table here means the field is blank, not that the
            # batch has nothing to say
            self.status.setText(
                "No sample carries a group yet — set one in the Samples "
                "workspace, in the Group column.")
            return
        self.status.setText(
            f"{len(rows)} group(s) · {self.quantity.currentText()} by {grouping}")

    def _export(self) -> None:
        if not self._rows:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export statistics", "statistics.csv", "CSV (*.csv)")
        if not path:
            return
        widest = max((len(r.values) for r in self._rows), default=0)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(FIXED + [f"Value {i + 1}" for i in range(widest)])
            for row in self._rows:
                writer.writerow([
                    row.component, row.group, f"{row.used}/{row.total}",
                    row.mean, row.standard_deviation, row.percent_cv, row.accuracy,
                    *[value for _name, value, _used in row.values],
                ])
        self.status.setText(f"Exported to {path}")
