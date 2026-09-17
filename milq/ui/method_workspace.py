"""Method workspace: the component table of the processing method."""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import lipidmaps, precursor
from ..audit import METHOD_DEFAULT, component_changes
from ..chemistry import ADDUCTS
from ..components import (RESPONSES, Component, fill_formulas, load_components,
                          precursor_repairs, save_components)
from ..session import Session
from . import style, theme
from .annotate_dialog import AnnotateDialog, _looks_unnamed, propose
from .flow_layout import FlowLayout
from .help_window import describe

COLUMNS = ["Name", "Group", "Precursor", "Fragment", "RT", "± RT", "Tol.",
           "Unit", "Formula", "Adduct", "IS", "Internal standard", "Response",
           "Conc. unit", "Qualifier of", "Ion ratio %", "± ratio %",
           "Min. response"]
COL = {name: i for i, name in enumerate(COLUMNS)}

#: where a row's provenance is kept while it is in the table. It has no
#: column of its own — it is a sentence, and a column of sentences is a
#: table nobody can read — so it rides on the Name cell and is shown in that
#: cell's tooltip. It has to be kept *somewhere* in the widget: the table is
#: committed whole on every keystroke (`_commit`), so a component field the
#: table does not carry is a field the next edit erases.
PROVENANCE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1

#: widest a column is made when fitted to its contents; past this the
#: analyst widens it themselves rather than losing the rest of the table
MAX_AUTO_WIDTH = 320

#: columns parsed as numbers, mapped to the dataclass field they fill
_NUMERIC = {
    COL["Precursor"]: "precursor",
    COL["Fragment"]: "fragment",
    COL["RT"]: "rt",
    COL["± RT"]: "rt_halfwidth",
    COL["Tol."]: "tolerance",
    COL["Ion ratio %"]: "ion_ratio",
    COL["± ratio %"]: "ion_ratio_tolerance",
    COL["Min. response"]: "min_response",
}


class MethodWorkspace(QtWidgets.QWidget):
    """
    Edits the shared component table.

    Writes straight into the session's method, so the Explorer and, later, the
    Analytics workspace always see the same list.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._loading = False
        #: columns the analyst has dragged; those keep the width they were given
        self._manual_widths: set[int] = set()

        layout = QtWidgets.QVBoxLayout(self)

        bar = FlowLayout()
        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_remove = QtWidgets.QPushButton("Remove")
        self.btn_generate = QtWidgets.QPushButton("Generate from acquisition method")
        self.btn_generate.setToolTip(
            "Create one component per product-ion channel of the open sample, "
            "so an 80-transition method does not have to be typed in"
        )
        self.btn_import = QtWidgets.QPushButton("Import CSV…")
        self.btn_export = QtWidgets.QPushButton("Export CSV…")
        self.btn_suggest = QtWidgets.QPushButton("Suggest from data…")
        self.btn_suggest.setToolTip(
            "Retention times from agreement between the open injections, and "
            "window widths from their sampling. Every proposal says what it "
            "rests on and nothing is applied without being ticked")
        self.btn_check = QtWidgets.QPushButton("Check method")
        self.btn_check.setToolTip(
            "Read the method against itself, and against the files that are "
            "open: components that share a transition, internal standards "
            "with no retention time, windows the sampling cannot resolve")
        self.btn_schedule = QtWidgets.QPushButton("Export schedule…")
        self.btn_schedule.setToolTip(
            "The scheduled acquisition the method implies — every component "
            "with a retention time, over its window — with the dwell a target "
            "cycle leaves each transition at the busiest moment of the run")
        self.btn_skyline = QtWidgets.QPushButton("Export for Skyline…")
        self.btn_skyline.setToolTip(
            "The method as a small-molecule transition list, in the columns "
            "Skyline's Import Transition List reads")
        self.btn_annotate = QtWidgets.QPushButton("Annotate from LIPID MAPS…")
        self.btn_annotate.setToolTip(
            "Propose a lipid species for every component still named after its "
            "precursor mass")
        self.btn_formulas = QtWidgets.QPushButton("Fill formulas from names")
        self.btn_formulas.setToolTip(
            "Read the lipid shorthand in each name — SM(d18:1/12:0), "
            "C16:0-Ceramide, PC 34:1 — and fill the empty Formula cells with "
            "what it implies. A formula is only kept where it agrees with the "
            "precursor already written down; a cell that has a formula is "
            "never touched, and no precursor is changed")
        self.btn_method_report = QtWidgets.QPushButton("Method report…")
        self.btn_method_report.setToolTip(
            "Everything this can say about the method before it is run, on "
            "one document: the component table with the flagged rows marked, "
            "the findings of Check method, the formulas it carries and could "
            "carry, the standards that could be lock masses, and — with a "
            "file open — which channel serves what and the schedule the "
            "method implies")
        self.btn_repair = QtWidgets.QPushButton("Repair precursors…")
        self.btn_repair.setToolTip(
            "Where a formula and the precursor written beside it disagree, "
            "take the precursor from the formula — row by row, ticked by "
            "hand, each one recorded. The only thing in the workspace that "
            "moves a precursor for you")
        for widget in (self.btn_add, self.btn_remove, self.btn_generate,
                       self.btn_import, self.btn_export, self.btn_check,
                       self.btn_schedule, self.btn_skyline,
                       self.btn_suggest, self.btn_annotate, self.btn_formulas,
                       self.btn_repair, self.btn_method_report):
            bar.addWidget(widget)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(60)
        header.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        header.sectionResized.connect(self._section_resized)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.table, 1)

        defaults = FlowLayout()
        defaults.addWidget(QtWidgets.QLabel("Default tolerance ±"))
        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setDecimals(4)
        self.tol_spin.setRange(0.0001, 500.0)
        self.tol_spin.setValue(session.method.tolerance)
        defaults.addWidget(self.tol_spin)
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["Da", "ppm"])
        self.unit_combo.setCurrentText(session.method.unit)
        defaults.addWidget(self.unit_combo)
        defaults.addSpacing(20)
        defaults.addWidget(QtWidgets.QLabel("Concentration unit"))
        self.conc_edit = QtWidgets.QLineEdit(session.method.concentration_unit)
        self.conc_edit.setMaximumWidth(120)
        defaults.addWidget(self.conc_edit)
        defaults.addSpacing(20)
        defaults.addWidget(QtWidgets.QLabel("Ion ratio ±"))
        self.ratio_spin = QtWidgets.QDoubleSpinBox()
        self.ratio_spin.setRange(0.0, 100.0)
        self.ratio_spin.setValue(session.method.ion_ratio_tolerance)
        self.ratio_spin.setSuffix(" %")
        self.ratio_spin.setToolTip("Deviation from the expected ion ratio that passes")
        defaults.addWidget(self.ratio_spin)
        defaults.addWidget(QtWidgets.QLabel("marginal to"))
        self.marginal_spin = QtWidgets.QDoubleSpinBox()
        self.marginal_spin.setRange(0.0, 200.0)
        self.marginal_spin.setValue(session.method.ion_ratio_marginal)
        self.marginal_spin.setSuffix(" %")
        defaults.addWidget(self.marginal_spin)
        defaults.addStretch(1)
        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        defaults.addWidget(self.status)
        layout.addLayout(defaults)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_remove.clicked.connect(self._remove_rows)
        self.btn_generate.clicked.connect(self._generate)
        self.btn_import.clicked.connect(self._import)
        self.btn_export.clicked.connect(self._export)
        self.btn_check.clicked.connect(self.check_method)
        self.btn_schedule.clicked.connect(self.export_schedule)
        self.btn_skyline.clicked.connect(self.export_skyline)
        self.btn_suggest.clicked.connect(self.suggest_from_data)
        self.btn_annotate.clicked.connect(self._annotate)
        self.btn_formulas.clicked.connect(self.fill_formulas)
        self.btn_repair.clicked.connect(self.repair_precursors)
        self.btn_method_report.clicked.connect(self.export_method_report)
        self.table.itemChanged.connect(self._on_edit)
        self.tol_spin.valueChanged.connect(self._defaults_changed)
        self.unit_combo.currentTextChanged.connect(self._defaults_changed)
        self.conc_edit.textChanged.connect(self._defaults_changed)
        self.ratio_spin.valueChanged.connect(self._defaults_changed)
        self.marginal_spin.valueChanged.connect(self._defaults_changed)
        # the value is written on every keystroke, because the method has to
        # follow the box; the trail is written when the typing stops
        self._recorded_defaults = self._default_values()
        for name, _field, _label in self._DEFAULTS:
            widget = getattr(self, name)
            if isinstance(widget, QtWidgets.QComboBox):
                widget.currentTextChanged.connect(
                    lambda _t: self._record_defaults())
            else:
                widget.editingFinished.connect(self._record_defaults)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.table,
                        activated=self._remove_rows)
        # F1 on the Skyline button opens the page about exporting rather
        # than the one about the component table it happens to sit above
        describe(self.btn_skyline, "export")
        # and F1 on the report button opens the page about the document
        # rather than the one about the table it is built from
        describe(self.btn_method_report, "method-report")

        session.sigMethodChanged.connect(self.reload)
        self.reload()

    # -- table <-> method -------------------------------------------------------- #
    def reload(self) -> None:
        self._loading = True
        components = self.session.method.components
        self.table.setRowCount(len(components))
        for row, component in enumerate(components):
            self._write_row(row, component)
        self._refresh_is_choices()
        self._fit_columns()
        self._loading = False
        self._update_status()

    def _write_row(self, row: int, c: Component) -> None:
        values = {
            COL["Name"]: c.name,
            COL["Group"]: c.group,
            COL["Precursor"]: f"{c.precursor:.4f}" if c.precursor else "",
            COL["Fragment"]: "" if c.fragment is None else f"{c.fragment:.4f}",
            COL["RT"]: "" if c.rt is None else f"{c.rt:.2f}",
            COL["± RT"]: f"{c.rt_halfwidth:g}",
            COL["Tol."]: f"{c.tolerance:g}",
            COL["Formula"]: c.formula,
            COL["Conc. unit"]: c.concentration_unit,
            COL["Qualifier of"]: c.qualifier_of,
            COL["Ion ratio %"]: "" if c.ion_ratio is None else f"{c.ion_ratio:g}",
            COL["± ratio %"]: ("" if not c.ion_ratio_tolerance
                               else f"{c.ion_ratio_tolerance:g}"),
            COL["Min. response"]: ("" if c.min_response is None
                                   else f"{c.min_response:g}"),
        }
        for column, text in values.items():
            item = QtWidgets.QTableWidgetItem(text)
            if column not in (COL["Name"], COL["Group"], COL["Formula"],
                              COL["Conc. unit"], COL["Qualifier of"]):
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
            elif text:
                # names outrun any sensible column width; keep the full one
                # readable without making the analyst widen the column
                item.setToolTip(text)
            self.table.setItem(row, column, item)

        name_item = self.table.item(row, COL["Name"])
        if name_item is not None:
            name_item.setData(PROVENANCE_ROLE, c.provenance)
            if c.provenance:
                name_item.setToolTip(
                    f"{c.name}\n\n{c.provenance}" if c.name else c.provenance)

        check = QtWidgets.QTableWidgetItem()
        check.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                       | QtCore.Qt.ItemFlag.ItemIsEnabled)
        check.setCheckState(QtCore.Qt.CheckState.Checked if c.is_internal_standard
                            else QtCore.Qt.CheckState.Unchecked)
        self.table.setItem(row, COL["IS"], check)

        self._set_is_combo(row, c.internal_standard)
        self._set_combo(row, COL["Unit"], ["Da", "ppm"], c.unit)
        self._set_combo(row, COL["Adduct"], [""] + [a.name for a in ADDUCTS], c.adduct)
        self._set_combo(row, COL["Response"], list(RESPONSES), c.response)

    def _set_is_combo(self, row: int, value: str) -> None:
        """The internal standard is picked from a list, never typed."""
        combo = QtWidgets.QComboBox()
        combo.addItem("")
        if value:
            combo.addItem(value)
            combo.setCurrentText(value)
        combo.currentTextChanged.connect(lambda _t: self._commit())
        self.table.setCellWidget(row, COL["Internal standard"], combo)

    def _refresh_is_choices(self) -> None:
        """
        Offer every row ticked IS as a choice, and nothing else.

        A method can still arrive naming a standard that has no row of its own —
        converting someone's spreadsheet usually produces a few. That name stays
        in the list and is marked, because dropping it silently would lose the
        one clue that the reference is broken.
        """
        pool = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, COL["IS"])
            name = self.table.item(row, COL["Name"])
            if (check is not None and name is not None
                    and check.checkState() == QtCore.Qt.CheckState.Checked
                    and name.text().strip()):
                pool.append(name.text().strip())
        pool.sort(key=str.lower)

        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, COL["Internal standard"])
            if not isinstance(combo, QtWidgets.QComboBox):
                continue
            own = self.table.item(row, COL["Name"])
            own_name = own.text().strip() if own else ""
            options = [""] + [n for n in pool if n != own_name]
            current = combo.currentText()
            unknown = bool(current) and current not in options
            if unknown:
                options.insert(1, current)
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItems(options)
            combo.setCurrentIndex(options.index(current) if current in options else 0)
            combo.blockSignals(blocked)
            combo.setStyleSheet(f"color:{theme.warning()};" if unknown else "")
            combo.setToolTip(
                f"nothing is ticked IS under the name \u201c{current}\u201d"
                if unknown else current or "Rows ticked IS appear here")

    def _section_resized(self, index: int, _old: int, _new: int) -> None:
        """A column the analyst sized by hand keeps that width from then on."""
        if not self._loading:
            self._manual_widths.add(index)

    def _fit_columns(self) -> None:
        """Size the columns to what they hold, leaving dragged ones alone."""
        kept = {c: self.table.columnWidth(c) for c in self._manual_widths}
        self.table.resizeColumnsToContents()
        for column in range(self.table.columnCount()):
            if column in kept:
                self.table.setColumnWidth(column, kept[column])
            else:
                self.table.setColumnWidth(
                    column, min(self.table.columnWidth(column), MAX_AUTO_WIDTH))
        style.fit_cell_widgets(self.table)
        for column in kept:
            self.table.setColumnWidth(column, kept[column])

    def _set_combo(self, row: int, column: int, options: list[str], value: str) -> None:
        combo = QtWidgets.QComboBox()
        combo.addItems(options)
        combo.setCurrentText(value if value in options else options[0])
        combo.currentTextChanged.connect(lambda _t: self._commit())
        self.table.setCellWidget(row, column, combo)

    def _read_row(self, row: int) -> Component | None:
        def text(column: int) -> str:
            widget = self.table.cellWidget(row, column)
            if isinstance(widget, QtWidgets.QComboBox):
                return widget.currentText()
            item = self.table.item(row, column)
            return item.text().strip() if item else ""

        name = text(COL["Name"])
        if not name:
            return None
        numbers: dict[str, float | None] = {}
        for column, field in _NUMERIC.items():
            raw = text(column).replace(",", ".")
            try:
                numbers[field] = float(raw) if raw else None
            except ValueError:
                numbers[field] = None

        is_item = self.table.item(row, COL["IS"])
        name_item = self.table.item(row, COL["Name"])
        provenance = ("" if name_item is None
                      else str(name_item.data(PROVENANCE_ROLE) or ""))
        component = Component(
            name=name,
            precursor=numbers.get("precursor") or 0.0,
            fragment=numbers.get("fragment"),
            rt=numbers.get("rt"),
            rt_halfwidth=numbers.get("rt_halfwidth") or 0.5,
            tolerance=numbers.get("tolerance") or self.session.method.tolerance,
            unit=text(COL["Unit"]) or "Da",
            group=text(COL["Group"]),
            formula=text(COL["Formula"]),
            adduct=text(COL["Adduct"]),
            is_internal_standard=bool(
                is_item and is_item.checkState() == QtCore.Qt.CheckState.Checked
            ),
            internal_standard=text(COL["Internal standard"]),
            response=text(COL["Response"]) or "area",
            concentration_unit=text(COL["Conc. unit"]),
            qualifier_of=text(COL["Qualifier of"]),
            ion_ratio=numbers.get("ion_ratio"),
            ion_ratio_tolerance=numbers.get("ion_ratio_tolerance") or 0.0,
            min_response=numbers.get("min_response"),
            provenance=provenance,
        )
        return component if component.is_valid else None

    def components(self) -> list[Component]:
        rows = (self._read_row(row) for row in range(self.table.rowCount()))
        return [c for c in rows if c is not None]

    def _commit(self) -> None:
        """
        Write the table back into the method, and note what changed.

        The table is committed whole on every edit, so what a change *was*
        has to be worked out by comparing the two tables — which is what
        `audit.component_changes` does. One edited cell is one entry naming
        the column and what was in it; a row added or removed is one entry.
        """
        if self._loading:
            return
        components = self.components()
        for what, target, before, after in component_changes(
                self.session.method.components, components):
            self.session.record(what, target, before, after,
                                note="method table")
        self.session.method.replace_all(components)
        self.session.notify_method_changed()
        self._update_status()

    def _on_edit(self, item) -> None:
        if self._loading:
            return
        row = item.row()
        # A formula plus an adduct can stand in for the precursor mass, which is
        # how a labelled internal standard is entered: C18H30D4O4 instead of a
        # hand-computed 317.26.
        if item.column() in (COL["Formula"], COL["Adduct"]):
            component = self._read_row(row)
            if component is not None:
                computed = component.precursor_from_formula()
                if computed:
                    self._loading = True
                    self.table.item(row, COL["Precursor"]).setText(f"{computed:.4f}")
                    self._loading = False
        # renaming a row, or ticking it IS, changes what the other rows may point at
        if item.column() in (COL["Name"], COL["IS"]):
            self._refresh_is_choices()
        self._commit()

    # -- actions ------------------------------------------------------------------ #
    def _add_row(self) -> None:
        row = self.table.rowCount()
        self._loading = True
        self.table.insertRow(row)
        self._write_row(row, Component(name="new", precursor=0.0))
        self._refresh_is_choices()
        self._loading = False
        self.table.editItem(self.table.item(row, COL["Name"]))

    def _remove_rows(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self._refresh_is_choices()
        self._commit()

    def _generate(self) -> None:
        components = self.session.generate_components()
        if not components:
            self._report("Open a sample first — the list is built from its "
                         "acquisition method.")
            return
        if self.session.method.components:
            answer = QtWidgets.QMessageBox.question(
                self, "Replace the component list?",
                f"This replaces the current {len(self.session.method.components)} "
                f"component(s) with {len(components)} taken from the acquisition "
                "method. Continue?",
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.session.set_components(components)
        self._report(f"{len(components)} component(s) from the acquisition method. "
                     "Set names, fragments and retention times before processing.")

    def _import(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import components", "", "CSV (*.csv *.txt);;All files (*)")
        if not path:
            return
        try:
            components = load_components(path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not read the CSV", str(exc))
            return
        if not components:
            self._report("The file had no valid rows.")
            return
        self.session.set_components(components)
        self._report(f"{len(components)} component(s) imported.")

    def suggest_from_data(self) -> None:
        """Offer what the open files can say about times and windows."""
        from .suggest_dialog import SuggestDialog

        if not self.session.method.components:
            QtWidgets.QMessageBox.information(
                self, "Suggest from data",
                "Build the component list first — there is nothing to look "
                "for.")
            return
        dialog = SuggestDialog(self.session, self)
        if dialog.load():
            dialog.exec()
        dialog.deleteLater()

    def check_method(self) -> None:
        """
        Say what the method will fail at, before a batch is processed.

        Everything here would otherwise be learned from the results, which is
        both later and harder: a component that shares a transition with
        another reports a number that is not wrong so much as not its own.
        """
        from ..health import SERIOUS, check_method

        health = check_method(self.session.method, self.session.entries)
        if health.sound and not health.skipped:
            QtWidgets.QMessageBox.information(
                self, "Check method",
                f"Nothing in the {health.components} components contradicts "
                f"itself.")
            return

        lines = []
        for finding in health.findings:
            names = ", ".join(finding.components[:8])
            if finding.count > 8:
                names += f", and {finding.count - 8} more"
            mark = "SERIOUS" if finding.severity == SERIOUS else "warning"
            lines.append(f"{mark} — {finding.summary}\n    {finding.detail}"
                         f"\n    {names}")
        for note in health.skipped:
            lines.append(f"not checked — {note}")

        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Check method")
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning if health.serious
                    else QtWidgets.QMessageBox.Icon.Information)
        box.setText(f"{len(health.serious)} serious, {len(health.warnings)} "
                    f"warning(s) over {health.components} components.")
        box.setDetailedText("\n\n".join(lines))
        box.exec()

    def _export(self) -> None:
        components = self.components()
        if not components:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export components", "components.csv", "CSV (*.csv)")
        if path:
            save_components(path, components)
            self._report(f"Exported to {path}")

    def export_schedule(self) -> None:
        from .schedule_dialog import ScheduleDialog

        dialog = ScheduleDialog(self.session, self)
        if dialog.exec() and dialog.saved_path:
            self._report(f"Schedule written to {dialog.saved_path}")

    def export_method_report(self) -> None:
        """
        Write the method report: the checks that exist, on one document.

        The acquisition is the first open sample, because that is what the
        checks needing one already use — `health.check_method` reads the
        sampling and the survey off `entries[0]` — and the batch is whatever
        the session has processed, which is only used to start the schedule's
        target cycle from a measured peak width rather than a round number.
        Neither is required: with nothing open the document says what a
        method alone can say, and says which sections are missing for want of
        a file.
        """
        from ..audit import METHOD_REPORT
        from ..method_report import build, write_html, write_pdf

        if not self.components():
            self._report("Build the component list first.")
            return
        path, chosen = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export method report", "method-report.pdf",
            "PDF (*.pdf);;HTML (*.html)")
        if not path:
            return
        session = self.session
        loaded = session.loaded_entries
        batch = session if len(session.results) else None
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        try:
            report = build(session.method,
                           acquisition_sample=loaded[0] if loaded else None,
                           batch=batch, database=lipidmaps.database)
            if path.lower().endswith(".html") or "HTML" in chosen:
                if not path.lower().endswith(".html"):
                    path += ".html"
                write_html(report, path)
            else:
                if not path.lower().endswith(".pdf"):
                    path += ".pdf"
                write_pdf(report, path)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        health = report.health
        session.record(
            METHOD_REPORT, target=f"{len(report.components)} component(s)",
            after=os.path.basename(path),
            note=(f"{len(health.serious)} serious, {len(health.warnings)} "
                  f"warning(s); "
                  + (f"against {report.acquisition.name or report.acquisition.file}"
                     if report.acquisition is not None
                     else "no acquisition open")))
        self._report(f"Method report written to {path}")

    def export_skyline(self) -> None:
        """
        The method as a transition list for Skyline.

        Whatever the method cannot supply — a charge with no adduct behind
        it, a component with no retention time — is said in the status line
        rather than left for Skyline's import to complain about.
        """
        from ..skyline import write_transition_list

        if not self.components():
            self._report("Build the component list first.")
            return
        path, _chosen = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export for Skyline", "transitions.csv", "CSV (*.csv)")
        if not path:
            return
        listing = write_transition_list(self.session.method, path)
        self._report(f"{listing.summary()} Written to {path}")

    def fill_formulas(self) -> None:
        """
        Fill the empty Formula cells from what the names say.

        Only the empty ones: a formula somebody typed is the method's own and
        a reading of a name is a guess about it. Nothing else on the row
        moves — in particular not the precursor, which is both what the
        guess was checked against and what the extraction window is built
        from.
        """
        components = self.components()
        if not components:
            self._report("Build the component list first.")
            return

        # the database is passed unloaded: it is only consulted for a name
        # that is not shorthand at all, and a table that is all shorthand
        # should not wait for fifty thousand records to be read
        fill = fill_formulas(components, database=lipidmaps.database)
        if fill.filled:
            self.session.set_components(components)

        lines = []
        if fill.refused:
            lines.append(f"{len(fill.refused)} refused — the formula the name "
                         f"implies is not the precursor the method carries, "
                         f"and one of the two is wrong:")
            lines += [f"    {p.component.name}: {p.reason}" for p in fill.refused]
        if fill.underived:
            lines.append(f"\n{len(fill.underived)} whose name is not lipid "
                         f"shorthand, so nothing could be read from it:")
            lines.append("    " + ", ".join(c.name for c in fill.underived))
        standards = [c for c in components
                     if c.is_internal_standard and not c.formula]
        if standards:
            lines.append(f"\n{len(standards)} internal standard(s) still "
                         f"without a formula, so without a lock mass for the "
                         f"mass recalibration:")
            lines.append("    " + ", ".join(c.name for c in standards))

        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Fill formulas from names")
        box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        box.setText(fill.summary())
        box.setInformativeText(
            "A formula is kept only where its mass agrees with the precursor "
            "already written down, to that precursor's own last decimal. "
            "Typed formulas and every precursor were left as they were.")
        if lines:
            box.setDetailedText("\n".join(lines))
        # the way out of the stand-off the refusals leave behind: the formula
        # may be the right one and the written mass the mistake. Offered here
        # because this is where the disagreement is found, and never done
        # here, because moving a precursor is a decision per row
        repair = None
        if fill.refused:
            repair = box.addButton("Repair precursors…",
                                   QtWidgets.QMessageBox.ButtonRole.ActionRole)
        box.exec()
        self._report(fill.summary())
        if repair is not None and box.clickedButton() is repair:
            self.repair_precursors()

    def repair_precursors(self) -> None:
        """
        Take the precursor from the formula, where the two disagree.

        The mirror of *Fill formulas from names*, which refuses a formula the
        written precursor contradicts and leaves the row as it found it. Every
        one of those refusals is one of two mistakes and only one of them can
        be fixed by arithmetic; the dialog says which is which, ticks the
        ones that are arithmetic, and applies nothing that is not ticked.

        The database is handed over for the third answer the dialog offers on
        a whole-dalton row: the mass there is the one the instrument acquired,
        so the name is what is in question, and the names that do match that
        mass come from the component's own class and from LIPID MAPS.
        """
        from .repair_dialog import RepairPrecursorsDialog

        components = self.components()
        if not components:
            self._report("Build the component list first.")
            return
        repairs = precursor_repairs(components, database=lipidmaps.database)
        if not repairs:
            QtWidgets.QMessageBox.information(
                self, "Repair precursors from formulas",
                "Every component whose formula can be read agrees with the "
                "precursor written beside it. There is nothing to repair.")
            self._report("No precursor contradicts its formula.")
            return

        dialog = RepairPrecursorsDialog(self.session, repairs, components, self,
                                        database=lipidmaps.database)
        dialog.exec()
        self._report(dialog.summary())
        dialog.deleteLater()

    def _annotate(self) -> None:
        """Name the unnamed components from their precursor masses."""
        if lipidmaps.database() is None:
            QtWidgets.QMessageBox.information(
                self, "LIPID MAPS not installed",
                "Open the Explorer's LIPID MAPS tab and download the database "
                "first. It is a one-off 21 MB download.")
            return
        components = self.components()
        if not components:
            self._report("Build the component list first.")
            return

        wanted = [c for c in components if _looks_unnamed(c)]
        if not wanted:
            self._report("Every component already has a name.")
            return

        measured = self._measure_precursors(wanted)
        proposals = propose(components, adduct="[M-H]-", tolerance=10.0,
                            unit="ppm", only_unnamed=True, measured=measured)
        if not proposals:
            self._report("Every component already has a name.")
            return

        dialog = AnnotateDialog(proposals, self)
        if not dialog.exec():
            return
        accepted = dialog.accepted_proposals()
        for proposal in accepted:
            proposal.component.name = proposal.species
            proposal.component.formula = proposal.formula
            proposal.component.lm_id = proposal.lm_id
            if not proposal.component.adduct:
                proposal.component.adduct = "[M-H]-"
        self.session.set_components(components)
        self._report(f"{len(accepted)} component(s) annotated.")

    def _measure_precursors(self, components: list) -> dict:
        """
        Read each precursor's real mass off the survey scan before searching.

        The method's own list is only good to the decimals it was typed with,
        which at these masses is around fifteen parts per million — enough for
        a database search to return a confident, wrong answer.
        """
        loaded = self.session.loaded_entries
        if not loaded:
            self._report("Open the samples first — the accurate mass is "
                         "measured from their survey scans.")
            return {}

        dialog = QtWidgets.QProgressDialog(
            "Measuring precursor masses from the survey scan…", "Cancel",
            0, len(components), self)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)

        def report(done: int, _total: int) -> bool:
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        measured = precursor.measure_all(loaded, components,
                                         self.session.method, progress=report)
        dialog.setValue(len(components))
        reliable = sum(1 for c in measured.values() if c.is_reliable)
        self._report(f"{reliable} of {len(measured)} precursor(s) measured "
                     "from the survey scan.")
        return measured

    #: the defaults under the table, as (widget attribute, method field, label)
    _DEFAULTS = (
        ("tol_spin", "tolerance", "default tolerance"),
        ("unit_combo", "unit", "tolerance unit"),
        ("conc_edit", "concentration_unit", "concentration unit"),
        ("ratio_spin", "ion_ratio_tolerance", "ion ratio ±"),
        ("marginal_spin", "ion_ratio_marginal", "ion ratio marginal to"),
    )

    def _default_values(self) -> dict:
        """What the boxes under the table say, in the method's own terms."""
        return {
            "tolerance": self.tol_spin.value(),
            "unit": self.unit_combo.currentText(),
            "concentration_unit": self.conc_edit.text().strip(),
            "ion_ratio_tolerance": self.ratio_spin.value(),
            "ion_ratio_marginal": self.marginal_spin.value(),
        }

    def _defaults_changed(self, *_args) -> None:
        method = self.session.method
        for field, value in self._default_values().items():
            setattr(method, field, value)
        self.session.notify_method_changed()

    def _record_defaults(self) -> None:
        """
        Note a default that was changed, once the typing has finished.

        Bound to `editingFinished` rather than to the value: a spin box
        typed into emits on every digit, and a trail of *2*, *25*, *250* is
        three entries for one decision.
        """
        if self._loading:
            return
        values = self._default_values()
        for _widget, field, label in self._DEFAULTS:
            after = values[field]
            before = self._recorded_defaults.get(field)
            if before == after:
                continue
            self._recorded_defaults[field] = after
            self.session.record(METHOD_DEFAULT, label, before, after,
                                note="under the component table")

    def _update_status(self) -> None:
        method = self.session.method
        internal = len(method.internal_standards)
        self.status.setText(
            f"{len(method.components)} component(s)"
            + (f", {internal} internal standard(s)" if internal else "")
        )

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
