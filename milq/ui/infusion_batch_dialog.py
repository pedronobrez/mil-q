"""
A folder of infusions reported without opening one of them.

*File ▸ Report infusions in a folder…* is the window on `infusion_batch.run`,
and it asks for exactly what that call needs and nothing else: where the
files are, where the document goes, the library and the component table if
there are any, and how it is written. Nothing is opened into the batch on
screen — the run makes a session of its own per file and closes it again —
so this can be used with a project open, or with nothing open at all, and
neither is disturbed.

The dialog runs the work itself, in `write`, rather than handing values back
to the window. That is what lets the whole flow be exercised with no modal
loop: the suite constructs it, sets the paths, and calls `write`. The one
thing it deliberately does not do is put up a message box at the end — the
window does that, so a headless test can read the result off the dialog.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from ..infusion_batch import BatchResult, run
from .help_window import describe, open_manual
from .settings import settings

HELP_PAGE = "infusion-report"

PDF = "PDF, laid out on A4 pages"
HTML = "HTML, one file that opens in a browser"


class InfusionBatchDialog(QtWidgets.QDialog):
    """Point at a folder; get the per-compound document for what is in it."""

    def __init__(self, parent=None, start_dir: str = ""):
        super().__init__(parent)
        self.settings = settings()
        self.result: BatchResult | None = None
        describe(self, HELP_PAGE)
        self.setWindowTitle("Report infusions in a folder")
        self.resize(760, 360)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Every acquisition in the folder that reads as a direct infusion, "
            "one section per compound, in one document — read one file at a "
            "time and closed again, so nothing is added to what is open here. "
            "A .wiff without its .wiff.scan is skipped and said so, and a run "
            "that is not an infusion is left out with the figures that say "
            "why.")
        blurb.setWordWrap(True)
        blurb.setProperty("role", "caption")
        layout.addWidget(blurb)

        form = QtWidgets.QFormLayout()
        self.folder_edit = QtWidgets.QLineEdit(start_dir or self._directory())
        form.addRow("Folder", self._with_browse(self.folder_edit,
                                                self._browse_folder))
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setToolTip(
            "The document. With one per compound, the compound's name is put "
            "in before the extension")
        form.addRow("Report", self._with_browse(self.path_edit,
                                                self._browse_report))
        self.library_edit = QtWidgets.QLineEdit(
            self.settings.value("library/own_path", "", type=str))
        self.library_edit.setPlaceholderText(
            "optional — an MSP or MGF of your own to search each spectrum "
            "against")
        form.addRow("Library", self._with_browse(self.library_edit,
                                                 self._browse_library))
        self.components_edit = QtWidgets.QLineEdit()
        self.components_edit.setPlaceholderText(
            "optional — a project or a components CSV, for the formulas the "
            "compounds are explained from")
        form.addRow("Components",
                    self._with_browse(self.components_edit,
                                      self._browse_components))
        self.format_box = QtWidgets.QComboBox()
        self.format_box.addItems([PDF, HTML])
        form.addRow("Format", self.format_box)
        layout.addLayout(form)

        self.check_per_compound = QtWidgets.QCheckBox(
            "One document per compound")
        self.check_per_compound.setToolTip(
            "A file each, named after the compound, rather than one document "
            "with a section per compound")
        layout.addWidget(self.check_per_compound)
        self.check_csv = QtWidgets.QCheckBox(
            "Also write the summary table as a CSV beside it")
        self.check_csv.setToolTip(
            "One row per infusion, every column — the same table the "
            "Infusions tab exports")
        layout.addWidget(self.check_csv)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save).setText(
                "Write the report")
        self.buttons.accepted.connect(self.write)
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        layout.addWidget(self.buttons)

        self.folder_edit.textChanged.connect(self._folder_changed)
        self.format_box.currentIndexChanged.connect(self._retype_path)
        self._folder_changed()

    # -- the choices ------------------------------------------------------- #
    @staticmethod
    def _with_browse(edit, slot) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(edit, 1)
        button = QtWidgets.QPushButton("Browse…")
        button.clicked.connect(slot)
        line.addWidget(button)
        return row

    def _directory(self) -> str:
        return self.settings.value("io/last_dir", os.path.expanduser("~"),
                                   type=str)

    @property
    def is_pdf(self) -> bool:
        return self.format_box.currentText() == PDF

    @property
    def suffix(self) -> str:
        return ".pdf" if self.is_pdf else ".html"

    def _folder_changed(self, *_args) -> None:
        """The report lands in the folder it is made from, until it is moved."""
        folder = self.folder_edit.text().strip()
        if folder and not self.path_edit.text().strip():
            self.path_edit.setText(
                os.path.join(folder, "infusion-report" + self.suffix))

    def _retype_path(self) -> None:
        path = self.path_edit.text().strip()
        if path:
            self.path_edit.setText(os.path.splitext(path)[0] + self.suffix)

    def _browse_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "The folder of infusions", self.folder_edit.text()
            or self._directory())
        if folder:
            self.folder_edit.setText(folder)
            self.path_edit.setText(
                os.path.join(folder, "infusion-report" + self.suffix))

    def _browse_report(self) -> None:
        dialog = QtWidgets.QFileDialog(
            self, "Write the infusion report", self.path_edit.text(),
            "PDF (*.pdf);;HTML (*.html)")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        describe(dialog, HELP_PAGE)
        if dialog.exec() and dialog.selectedFiles():
            self.path_edit.setText(dialog.selectedFiles()[0])
        dialog.deleteLater()

    def _browse_library(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Your own library", self.library_edit.text()
            or self._directory(), "Spectral library (*.msp *.mgf)")
        if path:
            self.library_edit.setText(path)

    def _browse_components(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "The component table", self.components_edit.text()
            or self._directory(),
            "Project or components (*.oqproj *.opvproj *.csv)")
        if path:
            self.components_edit.setText(path)

    def csv_path(self) -> str:
        """Where the CSV goes: beside the document, under its own name."""
        if not self.check_csv.isChecked():
            return ""
        path = self.path_edit.text().strip()
        return os.path.splitext(path)[0] + ".csv" if path else ""

    # -- the run ------------------------------------------------------------ #
    def write(self) -> BatchResult | None:
        """
        Run it, with a progress dialog over it, and keep what it did.

        A file is a second or two, so a folder is a wait with no sign of life
        unless something says which file is being read; and a wait that
        cannot be stopped is worse still, which is what the Cancel button on
        the progress dialog is for — `run` puts nothing on paper when it is
        pressed.
        """
        folder = self.folder_edit.text().strip()
        out = self.path_edit.text().strip()
        if not folder or not out:
            self.status.setText("Choose the folder and where the report goes.")
            return None
        if not os.path.isdir(folder) and not os.path.isfile(folder):
            self.status.setText(f"{folder} is not there.")
            return None

        progress = QtWidgets.QProgressDialog(
            "Reading the folder…", "Stop", 0, 1, self)
        progress.setWindowTitle("Report infusions in a folder")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        describe(progress, HELP_PAGE)

        def note(done: int, total: int, name: str) -> bool:
            progress.setMaximum(max(total, 1))
            progress.setValue(min(done, total))
            progress.setLabelText(f"{name} ({min(done + 1, total)} of {total})")
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        try:
            self.result = run(
                [folder], out,
                library=self.library_edit.text().strip() or None,
                components=self.components_edit.text().strip() or None,
                fmt="pdf" if self.is_pdf else "html",
                csv=self.csv_path() or None, progress=note,
                per_compound=self.check_per_compound.isChecked())
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not write the report: {exc}")
            return None
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            progress.close()
            progress.deleteLater()

        self.status.setText(self.describe_result())
        if self.result.documents:
            self.accept()
        return self.result

    def describe_result(self) -> str:
        """What was done, and everything that was left out, in full."""
        result = self.result
        if result is None:
            return ""
        said = [result.line()]
        if result.summary is not None and result.summary.rows:
            said.append(result.summary.summary())
        said += [f"skipped {skip}" for skip in result.skipped]
        return "\n".join(said)

    @property
    def output_folder(self) -> str:
        if self.result is not None and self.result.documents:
            return os.path.dirname(os.path.abspath(self.result.documents[0]))
        return os.path.dirname(os.path.abspath(self.path_edit.text().strip()))
