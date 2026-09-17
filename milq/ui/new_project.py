"""
The New Project wizard.

Setting a batch up piece by piece — open some files, build a method, remember
to save — leaves too much to memory. The wizard asks for the same things in
the order the work actually needs them, and writes the project file at the end,
so a run is reproducible from the file rather than from what the analyst did
that afternoon.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from .. import raw
from ..components import load_components
from ..method import ProcessingMethod
from ..samples import SAMPLE_TYPES
from ..session import PROJECT_SUFFIX, Session
from . import style

#: how the method is filled in
METHOD_IMPORT = "import"
METHOD_ACQUISITION = "acquisition"
METHOD_EMPTY = "empty"

PROJECT, SAMPLES, METHOD, SUMMARY = range(4)


class NewProjectWizard(QtWidgets.QWizard):
    """
    Builds a project on the session it is given.

    Files are opened as they are added, because the acquisition method — and
    so the option to generate a component list from it — is only readable once
    the file is open. Cancelling therefore closes what was opened; the caller
    is expected to have dealt with the previous project first.
    """

    def __init__(self, session: Session, start_dir: str = "", parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("New project")
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ModernStyle)
        self.setOption(QtWidgets.QWizard.WizardOption.NoBackButtonOnStartPage)
        self.setOption(QtWidgets.QWizard.WizardOption.HaveHelpButton)
        self.resize(820, 560)
        from .help_window import describe, open_manual
        describe(self, "starting-a-project")
        self.helpRequested.connect(lambda: open_manual(self, "starting-a-project"))

        self.setPage(PROJECT, ProjectPage(start_dir))
        self.setPage(SAMPLES, SamplesPage(session, start_dir))
        self.setPage(METHOD, MethodPage(session))
        self.setPage(SUMMARY, SummaryPage(session))

        self.rejected.connect(self._discard)

    # -- results ----------------------------------------------------------------- #
    @property
    def project_path(self) -> str:
        return self.page(PROJECT).project_path()

    @property
    def process_now(self) -> bool:
        return self.page(SUMMARY).check_process.isChecked()

    def _discard(self) -> None:
        """A cancelled wizard leaves nothing behind."""
        self.session.close_all()


class ProjectPage(QtWidgets.QWizardPage):
    """Where the project file goes — chosen first, so saving is not a chore."""

    def __init__(self, start_dir: str, parent=None):
        super().__init__(parent)
        self.setTitle("Project")
        self.setSubTitle(
            "The project file is written when the wizard finishes, and every "
            "later change is saved back into it.")

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Sphingolipids — cohort A")
        self.folder_edit = QtWidgets.QLineEdit(start_dir or os.path.expanduser("~"))
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)

        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)

        self.preview = QtWidgets.QLabel("")
        self.preview.setProperty("role", "caption")
        self.preview.setWordWrap(True)

        form = QtWidgets.QFormLayout(self)
        form.addRow("Name", self.name_edit)
        form.addRow("Folder", folder_row)
        form.addRow("", self.preview)

        self.name_edit.textChanged.connect(self._changed)
        self.folder_edit.textChanged.connect(self._changed)
        self.registerField("project_name*", self.name_edit)

    def _browse(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Project folder", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def _changed(self, *_args) -> None:
        path = self.project_path()
        if not path:
            self.preview.setText("")
        elif os.path.exists(path):
            self.preview.setText(f"{path}\nA file of that name is already there "
                                 "and will be overwritten.")
        else:
            self.preview.setText(path)
        self.completeChanged.emit()

    def project_path(self) -> str:
        name = self.name_edit.text().strip()
        folder = self.folder_edit.text().strip()
        if not name or not folder:
            return ""
        if not name.endswith(PROJECT_SUFFIX):
            name += PROJECT_SUFFIX
        return os.path.join(folder, name)

    def isComplete(self) -> bool:
        path = self.project_path()
        return bool(path) and os.path.isdir(os.path.dirname(path))


class SamplesPage(QtWidgets.QWizardPage):
    """The batch, with the type and study group set while they are still fresh."""

    COLUMNS = ["File", "Sample", "Type", "Group"]

    def __init__(self, session: Session, start_dir: str, parent=None):
        super().__init__(parent)
        self.session = session
        self._start_dir = start_dir
        self.setTitle("Samples")
        self.setSubTitle(
            "Add the raw files, then say what each injection is. Type drives "
            "the calibration; group is the study arm the statistics compare.")

        layout = QtWidgets.QVBoxLayout(self)

        bar = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add .wiff files…")
        self.btn_remove = QtWidgets.QPushButton("Remove selected")
        bar.addWidget(self.btn_add)
        bar.addWidget(self.btn_remove)
        bar.addSpacing(16)
        bar.addWidget(QtWidgets.QLabel("Set for selection:"))
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(SAMPLE_TYPES)
        bar.addWidget(self.type_combo)
        self.group_combo = QtWidgets.QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setMinimumWidth(130)
        self.group_combo.lineEdit().setPlaceholderText("group")
        bar.addWidget(self.group_combo)
        self.btn_apply = QtWidgets.QPushButton("Apply")
        bar.addWidget(self.btn_apply)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("No files yet.")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.btn_add.clicked.connect(self.add_files)
        self.btn_remove.clicked.connect(self._remove)
        self.btn_apply.clicked.connect(self._apply)

    def initializePage(self) -> None:
        self._rebuild()

    # -- batch ------------------------------------------------------------------- #
    def add_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Add SCIEX files", self._start_dir,
            raw.FILE_FILTER)
        self.add_paths(paths)

    def add_paths(self, paths: list[str]) -> list[str]:
        """Open each file; returns the ones that could not be read."""
        failed = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                try:
                    self.session.open_file(path)
                except Exception as exc:  # pragma: no cover - depends on the file
                    failed.append(f"{os.path.basename(path)}: {exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._rebuild()
        if failed:
            QtWidgets.QMessageBox.warning(
                self, "Some files could not be opened", "\n".join(failed))
        return failed

    def _remove(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()},
                          reverse=True):
            if row < len(self.session.entries):
                del self.session.entries[row]
        self.session.sigSamplesChanged.emit()
        self._rebuild()

    def _apply(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            self.status.setText("Select the rows to change first.")
            return
        sample_type = self.type_combo.currentText()
        group = self.group_combo.currentText().strip()
        for row in rows:
            entry = self.session.entries[row]
            entry.sample_type = sample_type
            entry.sample_group = group
        self._refresh()

    def _groups(self) -> list[str]:
        """Groups already in the batch, in the order it introduces them."""
        seen: list[str] = []
        for entry in self.session.entries:
            if entry.sample_group and entry.sample_group not in seen:
                seen.append(entry.sample_group)
        return seen

    def _rebuild(self) -> None:
        """Recreate the rows. Only for a batch that gained or lost a sample."""
        entries = self.session.entries
        self.table.setRowCount(0)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for column, text in ((0, entry.filename), (1, entry.name)):
                item = QtWidgets.QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(row, column, item)

            type_combo = QtWidgets.QComboBox()
            type_combo.addItems(SAMPLE_TYPES)
            type_combo.currentTextChanged.connect(
                lambda text, e=entry: setattr(e, "sample_type", text))
            self.table.setCellWidget(row, 2, type_combo)

            group_combo = QtWidgets.QComboBox()
            group_combo.setEditable(True)
            group_combo.setMinimumWidth(120)
            group_combo.activated.connect(
                lambda _i, e=entry, c=group_combo: self._set_group(e, c))
            group_combo.lineEdit().editingFinished.connect(
                lambda e=entry, c=group_combo: self._set_group(e, c))
            self.table.setCellWidget(row, 3, group_combo)
        self._refresh()

    def _refresh(self) -> None:
        """
        Update what the widgets show, without replacing them.

        Replacing a cell widget only queues the old one for deletion, so a
        rebuild on every edit leaves the previous combo painting over the new
        one until the event loop catches up.
        """
        entries = self.session.entries
        groups = self._groups()
        options = [""] + groups
        for row, entry in enumerate(entries):
            type_combo = self.table.cellWidget(row, 2)
            group_combo = self.table.cellWidget(row, 3)
            if type_combo is None or group_combo is None:
                continue
            blocked = type_combo.blockSignals(True)
            type_combo.setCurrentText(entry.sample_type)
            type_combo.blockSignals(blocked)
            if group_combo.lineEdit() is not None and group_combo.lineEdit().hasFocus():
                continue
            blocked = group_combo.blockSignals(True)
            group_combo.clear()
            group_combo.addItems(options)
            group_combo.setCurrentText(entry.sample_group)
            group_combo.blockSignals(blocked)

        current = self.group_combo.currentText()
        blocked = self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItems(groups)
        self.group_combo.setCurrentText(current)
        self.group_combo.blockSignals(blocked)

        by_type: dict[str, int] = {}
        for entry in entries:
            by_type[entry.sample_type] = by_type.get(entry.sample_type, 0) + 1
        summary = ", ".join(f"{n} {name}" for name, n in by_type.items())
        self.status.setText(
            f"{len(entries)} injection(s)" + (f" — {summary}" if summary else "")
            + (f" · groups: {', '.join(groups)}" if groups else "")
            if entries else "No files yet.")
        # the first group is typed after the columns were first sized, so the
        # Group column has to be given room again once it holds something
        self.table.resizeColumnsToContents()
        style.fit_cell_widgets(self.table)
        self.completeChanged.emit()

    def _set_group(self, entry, combo) -> None:
        group = combo.currentText().strip()
        if group != entry.sample_group:
            entry.sample_group = group
            self._refresh()

    def isComplete(self) -> bool:
        # a project with no samples is allowed: a method is often built first
        return True


class MethodPage(QtWidgets.QWizardPage):
    """Where the component table comes from, and the defaults it inherits."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._imported: list = []
        self._csv_path = ""
        self.setTitle("Method")
        self.setSubTitle(
            "A processing method says what to extract. It can be imported, "
            "read off the acquisition method of the samples, or left empty "
            "and built in the Method workspace.")

        layout = QtWidgets.QVBoxLayout(self)

        self.radio_import = QtWidgets.QRadioButton("Import a component list (CSV)")
        self.btn_browse = QtWidgets.QPushButton("Choose file…")
        self.import_label = QtWidgets.QLabel("")
        self.import_label.setProperty("role", "caption")
        self.import_label.setWordWrap(True)

        import_row = QtWidgets.QHBoxLayout()
        import_row.addSpacing(24)
        import_row.addWidget(self.btn_browse)
        import_row.addWidget(self.import_label, 1)

        self.radio_acquisition = QtWidgets.QRadioButton(
            "Generate one component per product-ion channel of the samples")
        self.acquisition_label = QtWidgets.QLabel("")
        self.acquisition_label.setProperty("role", "caption")
        acquisition_row = QtWidgets.QHBoxLayout()
        acquisition_row.addSpacing(24)
        acquisition_row.addWidget(self.acquisition_label, 1)

        self.radio_empty = QtWidgets.QRadioButton("Start with an empty method")
        self.radio_empty.setChecked(True)

        layout.addWidget(self.radio_import)
        layout.addLayout(import_row)
        layout.addWidget(self.radio_acquisition)
        layout.addLayout(acquisition_row)
        layout.addWidget(self.radio_empty)
        layout.addSpacing(12)

        box = QtWidgets.QGroupBox("Defaults every component inherits")
        form = QtWidgets.QFormLayout(box)
        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setDecimals(4)
        self.tol_spin.setRange(0.0001, 500.0)
        self.tol_spin.setValue(session.method.tolerance)
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["Da", "ppm"])
        self.unit_combo.setCurrentText(session.method.unit)
        tolerance_row = QtWidgets.QHBoxLayout()
        tolerance_row.addWidget(self.tol_spin)
        tolerance_row.addWidget(self.unit_combo)
        tolerance_row.addStretch(1)
        form.addRow("Extraction window ±", tolerance_row)
        self.conc_edit = QtWidgets.QLineEdit(session.method.concentration_unit)
        form.addRow("Concentration unit", self.conc_edit)
        layout.addWidget(box)
        layout.addStretch(1)

        self.btn_browse.clicked.connect(self._browse)
        for radio in (self.radio_import, self.radio_acquisition, self.radio_empty):
            radio.toggled.connect(lambda _c: self.completeChanged.emit())

    def initializePage(self) -> None:
        channels = len(self.session.generate_components())
        self.radio_acquisition.setEnabled(channels > 0)
        self.acquisition_label.setText(
            f"{channels} channel(s) found in the first sample — names, "
            "fragments and retention times are edited afterwards"
            if channels else "No sample is open, so there is no acquisition "
                             "method to read.")

    def _browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import components", "", "CSV (*.csv *.txt);;All files (*)")
        if not path:
            return
        try:
            components = load_components(path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not read the CSV", str(exc))
            return
        self._imported = components
        self._csv_path = path
        standards = sum(1 for c in components if c.is_internal_standard)
        self.import_label.setText(
            f"{os.path.basename(path)} — {len(components)} component(s), "
            f"{standards} internal standard(s)")
        self.radio_import.setChecked(True)
        self.completeChanged.emit()

    def choice(self) -> str:
        if self.radio_import.isChecked():
            return METHOD_IMPORT
        if self.radio_acquisition.isChecked():
            return METHOD_ACQUISITION
        return METHOD_EMPTY

    def components(self) -> list:
        if self.choice() == METHOD_IMPORT:
            return list(self._imported)
        if self.choice() == METHOD_ACQUISITION:
            return self.session.generate_components()
        return []

    def describe(self) -> str:
        choice = self.choice()
        if choice == METHOD_IMPORT:
            return f"{len(self._imported)} component(s) from " \
                   f"{os.path.basename(self._csv_path)}"
        if choice == METHOD_ACQUISITION:
            return f"{len(self.session.generate_components())} component(s) " \
                   "from the acquisition method"
        return "empty — built in the Method workspace"

    def apply_to(self, method: ProcessingMethod) -> None:
        method.tolerance = self.tol_spin.value()
        method.unit = self.unit_combo.currentText()
        method.concentration_unit = self.conc_edit.text().strip()

    def isComplete(self) -> bool:
        return not (self.radio_import.isChecked() and not self._imported)


class SummaryPage(QtWidgets.QWizardPage):
    """What is about to be written, in one place, before it is."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setTitle("Ready")
        self.setSubTitle("Check the batch, then create the project.")

        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(QtCore.Qt.TextFormat.RichText)
        layout.addWidget(self.summary)
        layout.addSpacing(8)
        self.warnings = QtWidgets.QLabel("")
        self.warnings.setWordWrap(True)
        self.warnings.setProperty("role", "warning")
        layout.addWidget(self.warnings)
        layout.addStretch(1)
        self.check_process = QtWidgets.QCheckBox(
            "Process the batch as soon as the project is created")
        layout.addWidget(self.check_process)

    def initializePage(self) -> None:
        wizard = self.wizard()
        entries = self.session.entries
        groups = sorted({e.sample_group for e in entries if e.sample_group})
        by_type: dict[str, int] = {}
        for entry in entries:
            by_type[entry.sample_type] = by_type.get(entry.sample_type, 0) + 1

        method_page = wizard.page(METHOD)
        rows = [
            ("Project file", wizard.page(PROJECT).project_path()),
            ("Samples", f"{len(entries)} injection(s)"
                        + (" — " + ", ".join(f"{n} {t}" for t, n in by_type.items())
                           if by_type else "")),
            ("Study groups", ", ".join(groups) if groups else "none set"),
            ("Method", method_page.describe()),
            ("Default window", f"± {method_page.tol_spin.value():g} "
                               f"{method_page.unit_combo.currentText()}"),
        ]
        self.summary.setText(
            "<table cellpadding='4'>"
            + "".join(f"<tr><td><b>{name}</b></td><td>{value}</td></tr>"
                      for name, value in rows)
            + "</table>")

        notes = []
        if not entries:
            notes.append("No samples yet — add them in the Samples workspace.")
        if method_page.choice() == METHOD_EMPTY:
            notes.append("The method is empty, so there is nothing to process "
                         "until components are added.")
        components = method_page.components()
        if components and not any(c.is_internal_standard for c in components):
            notes.append("No component is marked as an internal standard.")
        self.warnings.setText("\n".join(notes))
        self.check_process.setEnabled(bool(entries and components))
        self.check_process.setChecked(bool(entries and components))


class StartDialog(QtWidgets.QDialog):
    """
    What the window offers before anything is open.

    A batch built by hand and never saved is not reproducible, so the project
    route is the one presented first — but the Explorer is a real tool on its
    own, and looking at one file should not require a project.
    """

    NEW, OPEN, EXPLORE = range(3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MIL-Q")
        self.choice = self.EXPLORE

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 22)
        layout.setSpacing(9)
        title = QtWidgets.QLabel("MIL-Q")
        title.setFont(style.wordmark_font(29))
        layout.addWidget(title)
        rule = QtWidgets.QFrame()
        rule.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background:{style.token('accent')}; border:none;")
        rule.setMaximumWidth(46)
        layout.addWidget(rule)
        layout.addSpacing(4)
        blurb = QtWidgets.QLabel(
            "A project keeps the batch, the method and the results together in "
            "one file, so a run can be reopened and repeated.")
        blurb.setWordWrap(True)
        blurb.setProperty("role", "caption")
        layout.addWidget(blurb)
        layout.addSpacing(10)

        for label, hint, choice in (
            ("New project…", "Set up the samples and the method step by step",
             self.NEW),
            ("Open project…", "Reopen a saved batch", self.OPEN),
            ("Explore without a project",
             "Open a .wiff and look at it; nothing is saved", self.EXPLORE),
        ):
            button = QtWidgets.QPushButton(label)
            button.setMinimumHeight(36)
            button.setToolTip(hint)
            button.clicked.connect(
                lambda _c, value=choice: self._chose(value))
            if choice == self.NEW:
                button.setProperty("primary", True)
            layout.addWidget(button)

        layout.addSpacing(10)
        self.check_skip = QtWidgets.QCheckBox("Do not show this again")
        layout.addWidget(self.check_skip)

    def _chose(self, choice: int) -> None:
        self.choice = choice
        self.accept()
