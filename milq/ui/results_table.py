"""The Results Table: one row per sample and component."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from PyQt6 import QtCore, QtGui, QtWidgets

from ..audit import ROW_USED
from ..quantify import FAIL, MARGINAL, PASS, PeakResult, ResultsSet
from ..session import Session
from . import theme
from .flow_layout import FlowLayout

#: colours of the confidence traffic light
CONFIDENCE_COLOURS = {PASS: "#2ca02c", MARGINAL: "#e8a33d", FAIL: "#d62728"}
_ICONS: dict[str, QtGui.QIcon] = {}


def confidence_icon(status: str) -> QtGui.QIcon | None:
    """A small coloured dot for the confidence column, built once per status."""
    colour = CONFIDENCE_COLOURS.get(status)
    if colour is None:
        return None
    if status not in _ICONS:
        pixmap = QtGui.QPixmap(12, 12)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(colour)))
        painter.setPen(QtGui.QPen(QtGui.QColor(colour).darker(140)))
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()
        _ICONS[status] = QtGui.QIcon(pixmap)
    return _ICONS[status]


@dataclass(frozen=True)
class Column:
    title: str
    field: str
    decimals: int | None = None   # None means text
    width: int = 0


COLUMNS: list[Column] = [
    Column("Sample", "sample_name", None, 110),
    Column("Type", "sample_type", None, 110),
    Column("Sample group", "sample_group", None, 110),
    Column("Component", "component", None, 150),
    Column("Group", "group", None, 90),
    Column("Channel", "channel", None, 120),
    Column("m/z", "mz", 4),
    Column("RT", "rt", 3),
    Column("Exp. RT", "expected_rt", 2),
    Column("ΔRT", "rt_delta", 3),
    Column("Area", "area", 0, 90),
    Column("Height", "height", 0, 90),
    Column("Width", "width", 3),
    Column("S/N", "snr", 0),
    Column("Algorithm", "algorithm", None, 80),
    Column("IS", "internal_standard", None, 110),
    Column("IS area", "is_area", 0, 90),
    Column("Area ratio", "area_ratio", 4, 90),
    Column("Height ratio", "height_ratio", 4, 90),
    Column("Response", "response_value", 4, 90),
    Column("Ion ratio %", "ion_ratio", 1, 80),
    Column("Exp. ratio %", "expected_ion_ratio", 1, 80),
    Column("Conf.", "confidence", None, 56),
    Column("Actual conc.", "actual_concentration", 4, 95),
    Column("Calc. conc.", "calculated_concentration", 4, 95),
    Column("Accuracy %", "accuracy", 1, 85),
    Column("Status", "status", None, 56),
    Column("Flags", "flags_text", None, 190),
    Column("Used", "used", None, 46),
    Column("Note", "note", None, 200),
]
FIELD_INDEX = {c.field: i for i, c in enumerate(COLUMNS)}
USED_COLUMN = FIELD_INDEX["used"]
IS_COLUMN = FIELD_INDEX["internal_standard"]

#: widest a column is made when fitted to its contents
MAX_AUTO_WIDTH = 320


class ResultsModel(QtCore.QAbstractTableModel):
    """
    A table model rather than a widget full of items: a 50-component batch of
    20 samples is a thousand rows, and rebuilding that many widgets on every
    sort or filter is what makes a results table feel slow.
    """

    sigUsedChanged = QtCore.pyqtSignal()
    #: (component, internal standard) chosen in the table
    sigInternalStandardChanged = QtCore.pyqtSignal(str, str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._rows: list[PeakResult] = []
        self._decimals = {c.field: c.decimals for c in COLUMNS}

    # -- data ------------------------------------------------------------------- #
    def set_results(self, results: ResultsSet) -> None:
        self.beginResetModel()
        self._rows = list(results)
        self.endResetModel()

    def shape(self) -> tuple[int, int, int]:
        """What the table holds, ignoring the values — see _fit_columns."""
        return (len(self._rows),
                len({r.component for r in self._rows}),
                len({r.sample_key for r in self._rows}))

    def result_at(self, row: int) -> PeakResult | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def row_of(self, sample_key: str, component: str) -> int | None:
        for index, result in enumerate(self._rows):
            if result.sample_key == sample_key and result.component == component:
                return index
        return None

    def set_decimals(self, field: str, decimals: int | None) -> None:
        self._decimals[field] = decimals
        if self._rows:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self._rows) - 1, len(COLUMNS) - 1))

    def decimals(self, field: str) -> int | None:
        return self._decimals.get(field)

    def _value(self, result: PeakResult, column: Column):
        if column.field in ("sample_type", "sample_group"):
            entry = self.session.entry_by_key(result.sample_key)
            return getattr(entry, column.field) if entry else ""
        if column.field == "rt_delta":
            return result.rt_delta
        if column.field == "flags_text":
            return ", ".join(result.flags)
        if column.field == "internal_standard":
            # link_internal_standards leaves this empty when the name does not
            # resolve; showing the method's own text is what makes a mistyped
            # standard visible instead of looking like "no standard set"
            return result.internal_standard or self._named_standard(result)
        if column.field == "response_value":
            component = self.session.method.by_name(result.component)
            return result.response(component.response if component else "area")
        return getattr(result, column.field, "")

    def _named_standard(self, result: PeakResult) -> str:
        """What the method says, even when no row of that name exists."""
        component = self.session.method.by_name(result.component)
        return component.internal_standard if component else ""

    def _standard_problem(self, result: PeakResult) -> str:
        """
        Why the named standard is not one, or "" when it is.

        internal_standard_for only asks that a component of that name exists,
        so an analyte can end up normalised against a row nobody ever ticked
        IS — which is what an imported spreadsheet usually produces.
        """
        named = self._named_standard(result)
        if not named:
            return ""
        component = self.session.method.by_name(named)
        if component is None:
            return f"no component is named \u201c{named}\u201d"
        if not component.is_internal_standard:
            return f"\u201c{named}\u201d is not ticked IS in the method"
        return ""

    # -- Qt interface -------------------------------------------------------------- #
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            return COLUMNS[section].title
        return section + 1

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        result = self._rows[index.row()]
        column = COLUMNS[index.column()]
        value = self._value(result, column)

        if role == QtCore.Qt.ItemDataRole.CheckStateRole and index.column() == USED_COLUMN:
            return (QtCore.Qt.CheckState.Checked if result.used
                    else QtCore.Qt.CheckState.Unchecked)
        if role == QtCore.Qt.ItemDataRole.DecorationRole:
            if column.field == "confidence":
                return confidence_icon(result.confidence)
            if column.field == "status":
                return confidence_icon(result.status)
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if index.column() == USED_COLUMN:
                return ""
            if column.field in ("confidence", "status"):
                return ""
            if value is None:
                return "—"
            decimals = self._decimals.get(column.field)
            if decimals is None:
                return str(value)
            if not isinstance(value, (int, float)):
                return str(value)
            return f"{value:,.{decimals}f}"
        if role == QtCore.Qt.ItemDataRole.EditRole:
            # raw value so sorting is numeric, not lexicographic
            return value if value is not None else float("-inf")
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if column.decimals is not None:
                return int(QtCore.Qt.AlignmentFlag.AlignRight
                           | QtCore.Qt.AlignmentFlag.AlignVCenter)
            return int(QtCore.Qt.AlignmentFlag.AlignLeft
                       | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if role == QtCore.Qt.ItemDataRole.ForegroundRole:
            if index.column() == IS_COLUMN and self._standard_problem(result):
                return QtGui.QBrush(QtGui.QColor(theme.warning()))
            if not result.found:
                return QtGui.QBrush(QtGui.QColor(theme.danger()))
            if not result.used:
                return QtGui.QBrush(QtGui.QColor(theme.ink_faint()))
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            if index.column() == IS_COLUMN:
                problem = self._standard_problem(result)
                if problem:
                    return problem
            if column.decimals is None and value:
                return str(value)
            if result.note:
                return result.note
        return None

    def flags(self, index):
        base = (QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable)
        if index.column() == USED_COLUMN:
            return base | QtCore.Qt.ItemFlag.ItemIsUserCheckable
        if index.column() == IS_COLUMN and self._is_editable(index.row()):
            return base | QtCore.Qt.ItemFlag.ItemIsEditable
        return base

    def _is_editable(self, row: int) -> bool:
        """A standard is not quantified against another one."""
        component = self.session.method.by_name(self._rows[row].component)
        return component is not None and not component.is_internal_standard

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if (role == QtCore.Qt.ItemDataRole.CheckStateRole
                and index.column() == USED_COLUMN):
            result = self._rows[index.row()]
            was = result.used
            result.used = QtCore.Qt.CheckState(value) == QtCore.Qt.CheckState.Checked
            if result.used != was:
                self.session.record(
                    ROW_USED, f"{result.component} · {result.sample_name}",
                    before="used" if was else "excluded",
                    after="used" if result.used else "excluded",
                    note=f"area {result.area:,.0f}" if result.found
                         else result.note or "not integrated")
            self.dataChanged.emit(index, index)
            self.sigUsedChanged.emit()
            return True
        if role == QtCore.Qt.ItemDataRole.EditRole and index.column() == IS_COLUMN:
            result = self._rows[index.row()]
            if str(value) == self._value(result, COLUMNS[IS_COLUMN]):
                return False
            self.sigInternalStandardChanged.emit(result.component, str(value))
            return True
        return False


class InternalStandardDelegate(QtWidgets.QStyledItemDelegate):
    """Picks the internal standard from the components ticked IS."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session

    def createEditor(self, parent, _option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.addItem("")
        combo.addItems(sorted((c.name for c in self.session.method.internal_standards),
                              key=str.lower))
        current = index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""
        # a name the method carries but no component answers to stays on offer,
        # so opening the editor cannot quietly discard it
        if current and combo.findText(current) < 0:
            combo.insertItem(1, current)
        return combo

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(),
                      QtCore.Qt.ItemDataRole.EditRole)


class StatusFilterProxy(QtCore.QSortFilterProxyModel):
    """Text filter plus an acceptance-status filter, applied together."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "All"
        self._component = ""

    def set_status(self, status: str) -> None:
        self._status = status
        self.invalidateFilter()

    def set_component(self, component: str) -> None:
        """Narrow to one component; "" is every one of them."""
        self._component = component
        self.invalidateFilter()

    @property
    def component(self) -> str:
        return self._component

    def filterAcceptsRow(self, row, parent):
        if not super().filterAcceptsRow(row, parent):
            return False
        if self._component:
            result = self.sourceModel().result_at(row)
            if result is not None and result.component != self._component:
                return False
        if self._status == "All":
            return True
        model = self.sourceModel()
        result = model.result_at(row)
        if result is None:
            return True
        if self._status == "Not integrated":
            return not result.found
        return result.status == self._status


class ColumnDialog(QtWidgets.QDialog):
    """Which columns are shown, and to how many decimals."""

    def __init__(self, view: QtWidgets.QTableView, model: ResultsModel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Results table columns")
        self.view = view
        self.model = model
        self.resize(360, 460)

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(len(COLUMNS), 3)
        self.table.setHorizontalHeaderLabels(["Column", "Visible", "Decimals"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        for row, column in enumerate(COLUMNS):
            name = QtWidgets.QTableWidgetItem(column.title)
            name.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, name)

            visible = QtWidgets.QTableWidgetItem()
            visible.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                             | QtCore.Qt.ItemFlag.ItemIsEnabled)
            visible.setCheckState(
                QtCore.Qt.CheckState.Unchecked if view.isColumnHidden(row)
                else QtCore.Qt.CheckState.Checked)
            self.table.setItem(row, 1, visible)

            if column.decimals is None:
                blank = QtWidgets.QTableWidgetItem("—")
                blank.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, 2, blank)
            else:
                spin = QtWidgets.QSpinBox()
                spin.setRange(0, 6)
                spin.setValue(model.decimals(column.field) or 0)
                self.table.setCellWidget(row, 2, spin)
        layout.addWidget(self.table)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        for row, column in enumerate(COLUMNS):
            hidden = (self.table.item(row, 1).checkState()
                      != QtCore.Qt.CheckState.Checked)
            self.view.setColumnHidden(row, hidden)
            widget = self.table.cellWidget(row, 2)
            if widget is not None:
                self.model.set_decimals(column.field, widget.value())


class ResultsTable(QtWidgets.QWidget):
    """The table plus its filter, view modes and export."""

    sigSelected = QtCore.pyqtSignal(str, str)   # sample key, component
    #: (component, internal standard) picked in the IS column
    sigInternalStandardChanged = QtCore.pyqtSignal(str, str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        bar = FlowLayout()
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter rows…")
        self.filter_edit.setClearButtonEnabled(True)
        bar.addWidget(self.filter_edit, 1)
        bar.addWidget(QtWidgets.QLabel("Show"))
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItems(["All", "Pass", "Marginal", "Fail",
                                    "Not integrated"])
        self.status_combo.setToolTip("Filter by the acceptance status")
        bar.addWidget(self.status_combo)
        bar.addWidget(QtWidgets.QLabel("View"))
        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.addItems(["By sample", "By component"])
        bar.addWidget(self.view_combo)
        self.btn_columns = QtWidgets.QPushButton("Columns…")
        self.btn_export = QtWidgets.QPushButton("Export CSV…")
        bar.addWidget(self.btn_columns)
        bar.addWidget(self.btn_export)
        layout.addLayout(bar)

        self.model = ResultsModel(session, self)
        self.proxy = StatusFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(QtCore.Qt.ItemDataRole.EditRole)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

        self.view = QtWidgets.QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.view.verticalHeader().setDefaultSectionSize(24)
        self.view.setAlternatingRowColors(True)
        self.view.setItemDelegateForColumn(
            IS_COLUMN, InternalStandardDelegate(session, self))
        self.view.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
            | QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(46)
        header.sectionResized.connect(self._section_resized)
        #: columns the analyst has dragged; those keep the width they were given
        self._manual_widths: set[int] = set()
        self._fitted_shape: tuple[int, int, int] | None = None
        self._sizing = True
        for index, column in enumerate(COLUMNS):
            if column.width:
                self.view.setColumnWidth(index, column.width)
        self._sizing = False
        layout.addWidget(self.view, 1)

        self.summary = QtWidgets.QLabel("")
        self.summary.setProperty("role", "caption")
        layout.addWidget(self.summary)

        self.filter_edit.textChanged.connect(self.proxy.setFilterFixedString)
        self.status_combo.currentTextChanged.connect(self.proxy.set_status)
        self.view_combo.currentIndexChanged.connect(self._apply_view_mode)
        self.btn_columns.clicked.connect(self._choose_columns)
        self.btn_export.clicked.connect(self._export)
        self.view.selectionModel().selectionChanged.connect(self._on_selection)
        self.model.sigUsedChanged.connect(self._update_summary)
        self.model.sigInternalStandardChanged.connect(self.sigInternalStandardChanged)
        session.sigResultsChanged.connect(self.reload)
        self.reload()

    # -- content -------------------------------------------------------------------- #
    def reload(self) -> None:
        self.model.set_results(self.session.results)
        self._apply_view_mode()
        self._fit_columns()
        self._update_summary()

    def _section_resized(self, index: int, _old: int, _new: int) -> None:
        """A column the analyst sized by hand keeps that width from then on."""
        if not self._sizing:
            self._manual_widths.add(index)

    def _fit_columns(self) -> None:
        """
        Widen the columns to what they actually hold.

        The fixed widths were guesses; a component called
        LacCER(d18:1/24:1(15Z)) does not fit any of them.

        Measuring every cell of a twenty-sample batch costs a third of a
        second, and results reload after each manual integration, so this only
        runs when the batch itself changed — not when its numbers did.
        """
        shape = self.model.shape()
        if shape == self._fitted_shape:
            return
        self._fitted_shape = shape
        self._sizing = True
        for index, column in enumerate(COLUMNS):
            if index in self._manual_widths or self.view.isColumnHidden(index):
                continue
            self.view.resizeColumnToContents(index)
            self.view.setColumnWidth(
                index, min(max(self.view.columnWidth(index), column.width),
                           MAX_AUTO_WIDTH))
        self._sizing = False

    def _apply_view_mode(self, *_args) -> None:
        primary = (FIELD_INDEX["sample_name"] if self.view_combo.currentIndex() == 0
                   else FIELD_INDEX["component"])
        self.proxy.sort(primary, QtCore.Qt.SortOrder.AscendingOrder)

    def _update_summary(self) -> None:
        component = self.proxy.component
        rows = [r for r in self.session.results
                if not component or r.component == component]
        found = sum(1 for r in rows if r.found)
        unused = sum(1 for r in rows if not r.used)
        failed = sum(1 for r in rows if r.status == FAIL)
        marginal = sum(1 for r in rows if r.status == MARGINAL)
        passed = sum(1 for r in rows if r.status == PASS)
        text = f"{len(rows)} row(s), {found} integrated"
        if component:
            text = f"{component} · " + text
        if unused:
            text += f", {unused} excluded"
        if passed or failed or marginal:
            text += f" · {passed} pass, {marginal} marginal, {failed} fail"
        self.summary.setText(text)

    def set_component_filter(self, component: str) -> None:
        """Show only one component's rows; "" shows the whole batch."""
        self.proxy.set_component(component)
        self._update_summary()

    # -- selection ------------------------------------------------------------------ #
    def _on_selection(self, *_args) -> None:
        result = self.current_result()
        if result is not None:
            self.sigSelected.emit(result.sample_key, result.component)

    def current_result(self) -> PeakResult | None:
        indexes = self.view.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.model.result_at(self.proxy.mapToSource(indexes[0]).row())

    def select(self, sample_key: str, component: str) -> None:
        row = self.model.row_of(sample_key, component)
        if row is None:
            return
        proxy_index = self.proxy.mapFromSource(self.model.index(row, 0))
        if not proxy_index.isValid():
            return
        self.view.selectionModel().blockSignals(True)
        self.view.selectRow(proxy_index.row())
        self.view.selectionModel().blockSignals(False)
        self.view.scrollTo(proxy_index)

    # -- actions -------------------------------------------------------------------- #
    def _choose_columns(self) -> None:
        dialog = ColumnDialog(self.view, self.model, self)
        if dialog.exec():
            dialog.apply()

    def _export(self) -> None:
        if not len(self.session.results):
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export results", "results.csv", "CSV (*.csv)")
        if not path:
            return
        visible = [i for i in range(len(COLUMNS)) if not self.view.isColumnHidden(i)]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([COLUMNS[i].title for i in visible])
            for proxy_row in range(self.proxy.rowCount()):
                source = self.proxy.mapToSource(self.proxy.index(proxy_row, 0))
                result = self.model.result_at(source.row())
                row = []
                for i in visible:
                    column = COLUMNS[i]
                    if column.field == "used":
                        row.append("yes" if result.used else "no")
                        continue
                    if column.field in ("confidence", "status"):
                        row.append(getattr(result, column.field))
                        continue
                    value = self.model._value(result, column)
                    row.append("" if value is None else value)
                writer.writerow(row)
        self.summary.setText(f"Exported to {path}")
