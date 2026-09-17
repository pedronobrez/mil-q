"""Read-only view of the shared component list, for the Explorer workspace."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..components import Component


class ComponentListPanel(QtWidgets.QWidget):
    """
    Shows the method's components and offers the two actions the Explorer
    needs. Editing happens in the Method workspace, so the list has one editor
    rather than two that can drift apart.
    """

    sigExtractAll = QtCore.pyqtSignal(list)
    sigShowComponent = QtCore.pyqtSignal(object)
    sigEditRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._components: list[Component] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Component", "Transition", "RT"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setToolTip("Double-click a row to show that component's XIC")
        layout.addWidget(self.table, 1)

        self.btn_extract = QtWidgets.QPushButton("Extract and integrate all")
        font = self.btn_extract.font()
        font.setBold(True)
        self.btn_extract.setFont(font)
        layout.addWidget(self.btn_extract)

        self.btn_edit = QtWidgets.QPushButton("Edit in the Method workspace…")
        layout.addWidget(self.btn_edit)

        self.empty = QtWidgets.QLabel(
            "No components yet. Open the Method workspace to build the list, "
            "import a CSV, or generate it from the acquisition method."
        )
        self.empty.setWordWrap(True)
        self.empty.setProperty("role", "hint")
        layout.addWidget(self.empty)

        self.btn_extract.clicked.connect(
            lambda: self.sigExtractAll.emit(self._components))
        self.btn_edit.clicked.connect(self.sigEditRequested)
        self.table.cellDoubleClicked.connect(self._activated)

    def set_components(self, components: list[Component]) -> None:
        self._components = list(components)
        self.table.setRowCount(len(self._components))
        for row, component in enumerate(self._components):
            transition = (f"{component.precursor:.4f} → {component.fragment:.4f}"
                          if component.fragment is not None
                          else f"{component.precursor:.4f}")
            rt = "—" if component.rt is None else f"{component.rt:.2f}"
            name = component.name + (" (IS)" if component.is_internal_standard else "")
            for column, text in enumerate((name, transition, rt)):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnToContents(1)
        self.empty.setVisible(not self._components)
        self.btn_extract.setEnabled(bool(self._components))

    def _activated(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._components):
            self.sigShowComponent.emit(self._components[row])
