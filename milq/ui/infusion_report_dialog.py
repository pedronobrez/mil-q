"""
Where the infusion report goes, and what it is compared against.

Three choices and nothing else: PDF or HTML, the file, and which of the other
open infusions are the same compound. The last one is a list rather than a
rule because a naming convention is not a measurement — the prefix of the file
name is what the ticks start from, and the analyst is who says whether two
vials hold the same thing.

The dialog builds and writes the report itself, in `write`, rather than
handing values back to the Explorer. That is what lets the whole flow be
exercised with no modal loop: the suite constructs the dialog, sets the path,
and calls `write`.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from .. import audit, infusion_report
from ..infusion_report import compound_of
from .help_window import describe, open_manual
from .settings import settings

HELP_PAGE = "infusion-report"

PDF = "PDF, laid out on A4 pages"
HTML = "HTML, one file that opens in a browser"


class InfusionReportDialog(QtWidgets.QDialog):
    """Choose the format, the file, and the infusions to compare against."""

    def __init__(self, explorer, batch: bool = False, parent=None):
        super().__init__(parent or explorer)
        self.explorer = explorer
        self.session = getattr(explorer, "session", None)
        self.batch = bool(batch)
        self.written: list[str] = []
        self.settings = settings()
        describe(self, HELP_PAGE)
        self.setWindowTitle("Report every infusion" if batch
                            else "Report this infusion")
        self.resize(680, 420)

        ref = getattr(explorer, "active_ref", None)
        self.compound = compound_of(getattr(getattr(ref, "entry", None),
                                            "name", "") or "")
        open_infusions = infusion_report.infusions_open(explorer)
        active = getattr(ref, "entry", None)
        self.others = [(entry, channel) for entry, channel in open_infusions
                       if entry is not active]

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Every infusion open, one section per compound, in one document."
            if batch else
            f"The averaged spectrum of the active channel, its peaks, and "
            f"whatever was run against it — the precursor, a structure or "
            f"formula scored in the LIPID MAPS tab, a library search. The "
            f"report sums what was checked; it does not pass or fail "
            f"{self.compound or 'the compound'}.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        form = QtWidgets.QFormLayout()
        self.format_box = QtWidgets.QComboBox()
        self.format_box.addItems([PDF, HTML])
        self.format_box.setToolTip(
            "PDF is what goes in the notebook; HTML is one file, picture "
            "included, that can be mailed and opened anywhere")
        form.addRow("Format", self.format_box)

        row = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit(self._default_path())
        self.btn_browse = QtWidgets.QPushButton("Browse…")
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.btn_browse)
        holder = QtWidgets.QWidget()
        holder.setLayout(row)
        form.addRow("File", holder)
        layout.addLayout(form)

        if not batch:
            layout.addWidget(QtWidgets.QLabel(
                "Compare against — other open infusions, drawn head to tail "
                "against this one with their scores. Those whose name starts "
                "with the same compound come ticked."))
            self.list = QtWidgets.QListWidget()
            self.list.setToolTip(
                "The prefix of a file name is a proposal, not a measurement: "
                "tick whatever is actually the same compound")
            for entry, channel in self.others:
                item = QtWidgets.QListWidgetItem(
                    f"{entry.name} · {channel.info.label}")
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                same = compound_of(entry.name) == self.compound and self.compound
                item.setCheckState(QtCore.Qt.CheckState.Checked if same
                                   else QtCore.Qt.CheckState.Unchecked)
                self.list.addItem(item)
            layout.addWidget(self.list, 1)
            if not self.others:
                self.list.setEnabled(False)
                self.list.addItem("No other infusion is open.")
        else:
            self.list = None
            self.summary = QtWidgets.QListWidget()
            for entry, channel in open_infusions:
                self.summary.addItem(f"{compound_of(entry.name)} — "
                                     f"{entry.name} · {channel.info.label}")
            layout.addWidget(self.summary, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

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

        self.btn_browse.clicked.connect(self._browse)
        self.format_box.currentIndexChanged.connect(self._retype_path)

    # -- the choices ------------------------------------------------------- #
    @property
    def is_pdf(self) -> bool:
        return self.format_box.currentText() == PDF

    @property
    def suffix(self) -> str:
        return ".pdf" if self.is_pdf else ".html"

    def _directory(self) -> str:
        return self.settings.value("io/last_dir", os.path.expanduser("~"),
                                   type=str)

    def _default_path(self) -> str:
        stem = ("infusion-report" if self.batch
                else f"{self.compound or 'infusion'}-report")
        return os.path.join(self._directory(), stem + ".pdf")

    def _retype_path(self) -> None:
        path = self.path_edit.text().strip()
        if path:
            self.path_edit.setText(os.path.splitext(path)[0] + self.suffix)

    def _browse(self) -> None:
        dialog = QtWidgets.QFileDialog(
            self, "Write the infusion report", self.path_edit.text(),
            "PDF (*.pdf);;HTML (*.html)")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        describe(dialog, HELP_PAGE)
        if dialog.exec() and dialog.selectedFiles():
            self.path_edit.setText(dialog.selectedFiles()[0])
        dialog.deleteLater()

    def chosen(self) -> list:
        """The other infusions ticked, as (entry, channel) pairs."""
        if self.list is None:
            return []
        return [pair for row, pair in enumerate(self.others)
                if self.list.item(row) is not None
                and self.list.item(row).checkState()
                == QtCore.Qt.CheckState.Checked]

    def path(self) -> str:
        path = self.path_edit.text().strip()
        if path and not path.lower().endswith(self.suffix):
            path = os.path.splitext(path)[0] + self.suffix
        return path

    # -- doing it ---------------------------------------------------------- #
    def reports(self) -> list:
        """
        What is to be printed: every open infusion, or the active one.

        The active one is taken from the Explorer, so it carries what is on
        screen — the pane's spectrum at its label floor, the explanation and
        the library hit the two panels last produced. The rest of a batch is
        read from the files, because nothing is on screen for them.
        """
        if not self.batch:
            one = infusion_report.from_explorer(
                self.explorer, compound=self.compound, others=self.chosen())
            return [one] if one is not None else []
        active = getattr(getattr(self.explorer, "active_ref", None),
                         "entry", None)
        built = []
        for entry, channel in infusion_report.infusions_open(self.explorer):
            if entry is active:
                one = infusion_report.from_explorer(self.explorer,
                                                    compound=self.compound)
                if one is not None:
                    built.append(one)
                    continue
            # the session, so each of the rest is recalibrated from its own
            # precursor ladder and says so, the same as the active one
            built.append(infusion_report.report_for(
                entry, channel, session=getattr(self.explorer, "session", None)))
        return built

    def write(self) -> str | None:
        """Build the report and write it; returns the path, or None."""
        path = self.path()
        if not path:
            self.status.setText("Choose a file to write to.")
            return None
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            built = self.reports()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if not built:
            self.status.setText(
                "Nothing to report: the active sample is not an open infusion.")
            return None
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            if self.is_pdf:
                infusion_report.write_pdf(built, path)
            else:
                infusion_report.write_html(built, path)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return None
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.settings.setValue("io/last_dir", os.path.dirname(path))
        self.written.append(path)
        self._record(built, path)
        self.accept()
        return path

    def _record(self, built: list, path: str) -> None:
        """
        One audit entry per report written.

        A report is a document somebody will act on, so the project has to be
        able to say which one was produced, of what, and when — the same
        reason a manual integration is recorded.
        """
        if self.session is None or not hasattr(self.session, "record"):
            return
        names = ", ".join(dict.fromkeys(report.title for report in built))
        ran = {
            "precursor": lambda r: r.measurement is not None
            or r.survivor is not None or bool(r.survivor_note),
            "explanation": lambda r: r.explanation is not None,
            "library": lambda r: r.hit is not None,
        }
        checked = [what for what, was in ran.items()
                   if any(was(report) for report in built)]
        self.session.record(
            audit.INFUSION_REPORT, target=names,
            after=os.path.basename(path),
            note=(f"{len(built)} compound(s); "
                  f"{', '.join(checked) if checked else 'spectrum only'}"))
