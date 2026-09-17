"""
Every infused compound on one row: the summary that comes before the pages.

The per-compound report answers *is this vial what the label says it is?* one
vial at a time. A folder of infusions is nine of those, and the question asked
of nine is a different one — which of them measured its precursor, which found
its fragments, which matched the record made of the same compound last month,
and which did not. That is a table, and this is it.

Nothing is measured until asked. Averaging a whole run, centroiding a quarter
of a million points, searching a library and scoring every infusion of a
compound against the others is a few seconds per compound, so *Measure* waits
to be pressed and the table stays as it was until it is pressed again. The
summary is held on the session and is never *re-measured* from a project: it
is derived from the files.

What the project does save, once a summary stands, is the figures of the
table and the averaged, centroided peak list behind every row — see
`infusion_compare`, which is what *Compare infusions…* reads back to put a
reference day beside this one without opening a raw file.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from .. import audit
from ..infusion_report import (SUMMARY_COLUMNS, InfusionRow, InfusionSummary,
                               component_for, prepare_documents, write_pdf,
                               write_summary_csv)
from ..library import (identity_of, provenance_keys, records_from_summary,
                       write_msp)
from ..session import Session
from .settings import settings
from .flow_layout import FlowLayout

HELP_PAGE = "infusion-report"

#: the columns whose cell is an abbreviation of a sentence, by name rather
#: than by position: a column added in the middle would otherwise move the
#: tooltip onto the wrong cell without anything failing
FOUND_COLUMN = SUMMARY_COLUMNS.index("Found m/z")
SCANS_COLUMN = SUMMARY_COLUMNS.index("Scans")
OTHERS_COLUMN = SUMMARY_COLUMNS.index("Other infusions")
ADDUCT_COLUMN = SUMMARY_COLUMNS.index("Adduct")
ISOLATED_COLUMN = SUMMARY_COLUMNS.index("Isolated")
COMPOUND_COLUMN = SUMMARY_COLUMNS.index("Compound")
MARGIN_COLUMN = SUMMARY_COLUMNS.index("Margin")

#: the setting the analyst's own library is remembered under, written by the
#: Explorer's library panel. Read rather than owned: there is one library of
#: one's own and both places mean the same file.
SETTING_OWN_PATH = "library/own_path"


class _Cell(QtWidgets.QTableWidgetItem):
    """A cell that sorts on its number where it has one."""

    def __init__(self, text: str, key):
        super().__init__(text)
        self.key = key

    def __lt__(self, other) -> bool:
        mine, theirs = self.key, getattr(other, "key", other.text())
        if isinstance(mine, float) and isinstance(theirs, float):
            return mine < theirs
        return str(mine).lower() < str(theirs).lower()


class InfusionsPanel(QtWidgets.QWidget):
    """One row per infused compound, measured on request."""

    #: how many rows the table holds, for the tab that shows it
    sigRowsChanged = QtCore.pyqtSignal(int)
    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.settings = settings()
        #: set by the shell: the Explorer, whose LIPID MAPS tab may already
        #: have explained the compound on screen. Duck-typed and optional, so
        #: this panel can be built and exercised with no Explorer at all.
        self.explorer = None
        #: the measurement now running, or None. One at a time: *Measure* is
        #: disabled while it runs and a second press would be a second walk
        #: over the same readers from a second thread
        self._task = None
        self._progress = None
        #: the rows this run has produced, in the order the files finished —
        #: what a cancelled measurement keeps
        self._measured: list = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        self.btn_measure = QtWidgets.QPushButton("Measure")
        self.btn_measure.setToolTip(
            "Average every open infusion over its whole run, read the "
            "precursor, explain what the method's formula can, search your "
            "own library and score each infusion against the others of the "
            "same compound. A few seconds per compound, which is why it "
            "waits to be asked")
        bar.addWidget(self.btn_measure)
        self.btn_report = QtWidgets.QPushButton("Report…")
        self.btn_report.setToolTip(
            "Write the per-compound document for the selected rows — every "
            "row when none is selected — one section per compound")
        self.btn_report.setEnabled(False)
        bar.addWidget(self.btn_report)
        self.btn_method = QtWidgets.QPushButton("Use in method…")
        self.btn_method.setToolTip(
            "Write the selected infusions into the component table — every "
            "row when none is selected. One component each: the formula, the "
            "adduct read off the channel, the exact mass of that adduct as "
            "the precursor and a peak of the averaged spectrum as the "
            "fragment, with where it all came from. Nothing typed is "
            "overwritten and nothing is written until it is ticked")
        self.btn_method.setEnabled(False)
        bar.addWidget(self.btn_method)
        self.btn_new_standard = QtWidgets.QPushButton("New standard…")
        self.btn_new_standard.setToolTip(
            "The whole path from a bottle to a standard, in one place: the "
            "component in the method, the record in your own library and "
            "with it the newest entry of that standard’s history. Takes the "
            "selected row’s acquisition where one is selected, and asks for "
            "a file where none is — it does not need a Measure")
        bar.addWidget(self.btn_new_standard)
        self.btn_csv = QtWidgets.QPushButton("Export CSV…")
        self.btn_csv.setToolTip("The table as it stands, every column")
        self.btn_csv.setEnabled(False)
        bar.addWidget(self.btn_csv)
        self.btn_compare = QtWidgets.QPushButton("Compare infusions…")
        self.btn_compare.setToolTip(
            "These infusions against a reference project's — compound by "
            "compound and at the same collision energy and activation. The "
            "reference is read from its project file, which has to have "
            "been saved with a measured summary in it; no raw file is opened")
        self.btn_compare.setEnabled(False)
        bar.addWidget(self.btn_compare)
        self.btn_energy = QtWidgets.QPushButton("Recommend energies…")
        self.btn_energy.setToolTip(
            "Every infusion of a compound grouped by activation and "
            "collision energy, and which of them to use for identification, "
            "for quantitation and for a library record — three different "
            "questions, each with the figures it was decided on. Nothing is "
            "measured again and no energy between two that were acquired is "
            "offered")
        self.btn_energy.setEnabled(False)
        bar.addWidget(self.btn_energy)
        self.btn_quantify = QtWidgets.QPushButton("Quantify…")
        self.btn_quantify.setToolTip(
            "Measure each analyte against the internal standard the method "
            "gives it, in the averaged spectrum of every open infusion: the "
            "two responses, the isotope cross-talk between them and the "
            "ratio. Independent of the table above — it needs a component "
            "table with an internal standard set, not a Measure")
        bar.addWidget(self.btn_quantify)
        self.btn_library = QtWidgets.QPushButton("Add all to library")
        self.btn_library.setToolTip(
            "Write one record per row into your own library — the averaged "
            "spectrum the table was measured from, named for the compound, "
            "with the file and channel it came from in its comment. A row "
            "whose compound could not be proposed is skipped and named, and "
            "a row already in the file from the same file and channel is not "
            "written twice")
        self.btn_library.setEnabled(False)
        bar.addWidget(self.btn_library)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(SUMMARY_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(SUMMARY_COLUMNS))
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.setToolTip(
            "One row per infused sample. A cell that could not be filled "
            "says why instead of being blank — which check was not run, or "
            "what was not there to measure")
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("Not measured yet — press Measure.")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.btn_measure.clicked.connect(self.measure)
        self.btn_new_standard.clicked.connect(self.new_standard)
        self.btn_report.clicked.connect(self.write_report)
        self.btn_csv.clicked.connect(self.export_csv)
        self.btn_compare.clicked.connect(self.compare_infusions)
        self.btn_energy.clicked.connect(self.recommend_energies)
        self.btn_method.clicked.connect(self.use_in_method)
        self.btn_quantify.clicked.connect(self.quantify)
        self.btn_library.clicked.connect(self.add_all_to_library)
        session.sigSamplesChanged.connect(self._invalidate)

        from .help_window import describe
        describe(self, HELP_PAGE)
        self.reload()

    # -- measuring ------------------------------------------------------------ #
    @property
    def summary(self) -> InfusionSummary | None:
        return getattr(self.session, "infusion_summary", None)

    def own_library(self):
        """The analyst's own library, or None with the reason left to the
        summary — a library that is not set is not an error."""
        from ..library import load_library

        path = self.settings.value(SETTING_OWN_PATH, "", type=str)
        if not path or not os.path.exists(path):
            return None
        try:
            return load_library(path)
        except (OSError, ValueError):
            return None

    def explanations(self) -> dict:
        """
        What the Explorer's LIPID MAPS tab has already produced, by compound.

        One at most: the panel holds the last explanation it made, and it
        belongs to whatever was on screen when it was made. Anything else is
        explained here from the component table.
        """
        from ..infusion_report import compound_of

        explorer = self.explorer
        if explorer is None:
            return {}
        panel = getattr(explorer, "lipid_panel", None)
        explanation = getattr(panel, "current_explanation", None)
        if callable(explanation):
            try:
                explanation = explanation()
            except Exception:
                explanation = None
        ref = getattr(explorer, "active_ref", None)
        name = getattr(getattr(ref, "entry", None), "name", "")
        compound = compound_of(name)
        if explanation is None or not compound:
            return {}
        return {compound: explanation}

    def measure(self, threaded: bool = True):
        """
        Measure every open infusion, off this thread.

        Half a minute of averaging and centroiding used to run here under a
        wait cursor, which is half a minute of a window that does not
        repaint. It now runs in `infusion_worker.MeasureTask` on the global
        thread pool and reports back by signal: a cancellable dialog naming
        the file being read, a row in the table as each file finishes, and
        the buttons disabled until it is over.

        `threaded=False` runs the same task inline, on this thread, through
        the same signals. It is what a test uses — a thread pool and a modal
        dialog make an assertion about rows arriving in order a race — and
        it is the only difference between the two paths.

        Returns the task, so a caller can cancel it.
        """
        from .infusion_worker import MeasureTask

        if self._task is not None:
            return self._task
        library = self.own_library()
        task = MeasureTask(
            self.session, library=library, explanations=self.explanations(),
            # the same rule the Explorer's pane is drawing under, so the
            # table and the spectrum on screen are of the same scans
            include_unstable=bool(getattr(
                self.explorer, "include_unstable_scans", lambda: False)()),
            cache=self.session.averages)
        self._task = task
        self._measured = []
        self._start_table()
        task.signals.progress.connect(self._on_progress)
        task.signals.row.connect(self._on_row)
        task.signals.finished.connect(self._on_finished)
        task.signals.failed.connect(self._on_failed)

        self._progress = QtWidgets.QProgressDialog(
            "Measuring the open infusions…", "Cancel", 0,
            max(len(self.session.entries), 1), self)
        self._progress.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(400)
        self._progress.canceled.connect(self.cancel_measure)
        self._enable(False)
        if threaded:
            QtCore.QThreadPool.globalInstance().start(task)
        else:
            task.measure()
        return task

    def cancel_measure(self) -> None:
        """Stop after the file being read. What is measured is kept."""
        if self._task is not None:
            self._task.cancel()

    # -- what the worker says ------------------------------------------------- #
    def _start_table(self) -> None:
        """Empty the table for a measurement about to fill it row by row."""
        self.session.infusion_summary = None
        self.session.infusion_comparison = None
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.status.setText("Measuring…")

    def _on_progress(self, done: int, total: int, name: str) -> None:
        """
        The dialog, told which file is being waited for.

        Through a local reference, and with `setValue` last, because a modal
        `QProgressDialog.setValue` pumps the event loop: it delivers the next
        queued signal from the worker — the next progress, or the finished —
        and that one closes the dialog and sets this attribute to None. Read
        again after the call it therefore raises, which is how this was
        found: an `AttributeError` on `None` at the end of a measurement that
        had otherwise worked.
        """
        dialog = self._progress
        if dialog is None:
            return
        dialog.setLabelText(
            f"Reading {name} — {done} of {total} done" if name
            else f"{done} of {total} done")
        dialog.setMaximum(max(total, 1))
        dialog.setValue(min(done, total))

    def _on_row(self, row) -> None:
        """
        One finished infusion, appended as it arrives.

        Sorting is off while the table is filling: a table that reorders
        itself under the reader between one file and the next is harder to
        read than one that fills in the order the files were measured. It
        comes back with the finished summary, along with the mutual scores,
        which are not known until a compound's last infusion is done.
        """
        self._measured.append(row)
        index = self.table.rowCount()
        self.table.insertRow(index)
        self._fill_row(index, row)
        self.table.resizeColumnsToContents()

    def _on_finished(self, summary) -> None:
        self._close_progress()
        cancelled = self._task is not None and self._task.cancelled
        self._task = None
        if summary is None:
            # cancelled between files: the rows already measured stand, and
            # the line says they are part of a batch and not all of it
            kept = list(self._measured)
            self.session.infusion_summary = InfusionSummary(
                rows=kept, library=self.summary.library if self.summary else "",
                note="Cancelled." if kept else "Cancelled before anything "
                                               "was measured.")
            self.reload()
            self._report(f"Cancelled: {len(kept)} infusion(s) measured before "
                         f"you stopped, kept as they stand."
                         if kept else "Cancelled; nothing was measured.")
            self._enable(True)
            return
        self.session.infusion_summary = summary
        self.reload()
        if cancelled:
            self._report(self.status.text() + " · cancelled")
        self._enable(True)

    def _on_failed(self, reason: str) -> None:
        self._close_progress()
        self._task = None
        self.session.infusion_summary = None
        self.reload()
        self._report(f"The measurement could not be run: {reason}")
        self._enable(True)

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None

    def _enable(self, on: bool) -> None:
        """
        The buttons while a measurement runs.

        *Measure* and everything that reads the same files go; the ones that
        only need the table are left to `reload`, which knows whether there
        is a table to act on. Nothing here is enabled by this method — a
        button turned on because a measurement finished, without asking
        whether it produced any rows, is a button that acts on nothing.
        """
        for button in (self.btn_measure, self.btn_new_standard,
                       self.btn_quantify):
            button.setEnabled(on)
        if not on:
            for button in (self.btn_report, self.btn_csv, self.btn_compare,
                           self.btn_energy, self.btn_method, self.btn_library):
                button.setEnabled(False)

    # -- the cache ------------------------------------------------------------ #
    def clear_cache(self) -> str:
        """
        Empty the on-disk cache of averaged spectra, and say what went.

        Nothing is lost that cannot be measured again: every entry is an
        average of a file that is still where it was. What it costs is the
        next *Measure* being a cold one.
        """
        from .. import spectrum_cache

        cache = self.session.averages
        removed, freed = cache.clear()
        where = spectrum_cache.describe_dir(cache.directory,
                                            self.session.project_path)
        said = (f"{removed} cached average(s) removed, "
                f"{freed / (1024 * 1024):.1f} MB freed from {where}."
                if removed else f"Nothing was cached in {where}.")
        self._report(said)
        return said

    def _invalidate(self) -> None:
        """A file opened or closed makes the table a description of a batch
        that is no longer the open one — and stops a measurement of it: the
        readers a worker is walking are the ones being closed."""
        self.cancel_measure()
        self.session.infusion_summary = None
        self.session.infusion_comparison = None
        self.reload()

    # -- content -------------------------------------------------------------- #
    def reload(self) -> None:
        summary = self.summary
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        rows = summary.rows if summary is not None else []
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._fill_row(index, row)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.btn_report.setEnabled(bool(rows))
        self.btn_csv.setEnabled(bool(rows))
        self.btn_compare.setEnabled(bool(rows))
        self.btn_energy.setEnabled(bool(rows))
        self.btn_method.setEnabled(bool(rows))
        self.btn_library.setEnabled(bool(rows))
        self._describe()
        self.sigRowsChanged.emit(len(rows))

    def _fill_row(self, index: int, row: InfusionRow) -> None:
        """One row's cells, wherever the row came from — the finished summary
        or a worker that has just measured it."""
        cells, keys = row.cells(), row.keys()
        for column, text in enumerate(cells):
            item = _Cell(text, keys[column])
            if isinstance(keys[column], float):
                item.setTextAlignment(
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(self._tooltip(row, column, text))
            self.table.setItem(index, column, item)

    @staticmethod
    def _tooltip(row: InfusionRow, column: int, text: str) -> str:
        """
        The whole sentence where the cell holds an abbreviation of it.

        A cell is a few characters wide and the reason a measurement could
        not be made is a sentence; the short form goes in the table and the
        long one here, rather than the reason being lost to the width.
        """
        if column == FOUND_COLUMN and row.found is None:
            return (row.report.survivor_note
                    or getattr(row.report.measurement, "note", "")
                    or text)
        if column == ADDUCT_COLUMN:
            # the cell is `[M+NH4]+ confirmed`; the tooltip is what the
            # survey actually measured, candidate by candidate
            lines = [row.report.adduct_note] if row.report.adduct_note else []
            lines += [e.sentence for e in row.report.evidence]
            return "\n".join(lines) or text
        if column in (ISOLATED_COLUMN, COMPOUND_COLUMN):
            # the whole sentence, on both cells the verdict writes: a reader
            # who notices the flagged name should not have to guess which
            # other column explains it
            verdict = row.report.isolation
            return verdict.sentence() if verdict is not None else text
        if column == MARGIN_COLUMN:
            # the cell is `+16.2 pts vs PG 13:0/18:3 as [M+H]+`; the tooltip
            # is the whole contrast, rival by rival, since a margin means
            # nothing without the list it was taken over
            result = row.report.margin
            if result is None:
                return text
            lines = [result.sentence()]
            lines += [f"{i.share * 100:.1f}%  {i.label}  {i.formula}  "
                      f"{i.matched} of {i.predicted} ion(s)"
                      for i in result.others[:10]]
            return "\n".join(lines)
        if column == SCANS_COLUMN:
            # the cell is "464 of 473"; where the rest went is a sentence
            return row.report.scans_line()
        if column == OTHERS_COLUMN and row.others:
            return "\n".join(
                f"{label}: score {score * 100:.0f}, reverse "
                f"{reverse * 100:.0f}, {matched} of {of_other} peak(s)"
                for label, score, reverse, matched, of_other in row.others)
        return text

    def _describe(self) -> None:
        summary = self.summary
        if summary is None:
            self.status.setText("Not measured yet — press Measure.")
            return
        said = summary.summary()
        if summary.rows:
            said += f" · measured in {summary.seconds:.1f} s"
        self.status.setText(said)
        self.sigStatus.emit(said)

    # -- what comes off it ---------------------------------------------------- #
    def chosen(self) -> list[InfusionRow]:
        """
        The selected rows, or every row when nothing is selected.

        In the table's own order, which is the order it is sorted in: a
        document whose sections are in a different order from the table they
        were chosen in reads as a different set of rows.
        """
        summary = self.summary
        if summary is None or not summary.rows:
            return []
        selected = {index.row() for index in
                    self.table.selectionModel().selectedRows()}
        # the table is sorted, so its rows are not the summary's: the sample
        # name is what identifies one, and it is unique per acquisition
        by_name = {row.sample: row for row in summary.rows}
        picked = []
        for visual in range(self.table.rowCount()):
            if selected and visual not in selected:
                continue
            item = self.table.item(visual, 1)
            row = by_name.get(item.text()) if item is not None else None
            if row is not None:
                picked.append(row)
        return picked

    def batch_result(self, rows):
        """
        This table as the run `infusion_cover` describes, for the cover.

        The cover is written from a `BatchResult` because that is what the
        headless run makes, and the tab is the same measurement taken through
        a window: the files are the ones the rows came from, and what was
        left out is every open sample that did not read as an infusion, with
        `infusion.verdict_for`'s own figures — the reason the command line
        prints for the same sample. A cover that said "nothing was left out"
        while three open acquisitions had been passed over would be the one
        thing this document must not do.
        """
        from ..infusion import verdict_for
        from ..infusion_batch import NOT_INFUSION, BatchResult, Skipped

        entries = list(getattr(self.session, "entries", []))
        wanted = {row.report.file for row in rows}
        reported = {row.sample for row in rows}
        paths, skipped = [], []
        for entry in entries:
            path = str(getattr(entry, "path", "") or "")
            if entry.filename in wanted and path not in paths:
                paths.append(path)
            if entry.name in reported:
                continue
            try:
                verdict = verdict_for(entry.sample)
                reason = (f"{verdict.reason} ({verdict.n_scans:,} scans over "
                          f"{verdict.length_min:.2f} min)")
            except Exception as exc:                 # a reader that cannot say
                reason = f"{type(exc).__name__}: {exc}"
            skipped.append(Skipped(path, NOT_INFUSION,
                                   f"{entry.name}: {reason}"))
        return BatchResult(requested=paths, read=paths, skipped=skipped,
                           summary=self.summary)

    def write_report(self, path: str = "") -> str:
        """
        Write the per-compound document for the chosen rows.

        The whole table gets `infusion_cover`'s cover in front of the pages:
        what was read, the rows summed sentence by sentence, what was left
        out, and where each compound is. A selection does not, because every
        count on that cover is a count of the folder and a cover that
        counted four of nine rows would be a summary of something nobody
        chose.
        """
        rows = self.chosen()
        if not rows:
            self.status.setText("Measure first; there is nothing to report.")
            return ""
        if not path:
            start = os.path.join(
                self.settings.value("io/last_dir", "", type=str),
                "infusion-report.pdf")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Write the infusion report", start, "PDF (*.pdf)")
            if not path:
                return ""
            self.settings.setValue("io/last_dir", os.path.dirname(path))
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        whole = len(rows) == len(self.summary.rows)
        try:
            reports = prepare_documents(rows)
            if whole:
                from ..infusion_cover import write_pdf as write_with_cover

                write_with_cover(self.batch_result(rows), self.summary,
                                 reports, path)
            else:
                write_pdf(reports, path)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return ""
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        names = ", ".join(dict.fromkeys(row.compound for row in rows))
        self.session.record(
            audit.INFUSION_REPORT, names, after=os.path.basename(path),
            note=f"{len(rows)} infusion(s) from the Infusions tab"
                 f"{'' if whole else ', a selection, with no cover'}")
        self._report(f"{len(rows)} infusion(s) written to "
                     f"{os.path.basename(path)}.")
        return path

    def recommend_energies(self):
        """
        Which collision energy and activation explains each standard best.

        Arithmetic on the summary that already stands: no file is read and
        nothing is measured again, so this opens at once. A tab that has not
        been measured has no conditions to group and says so rather than
        opening an empty table.
        """
        from .energy_dialog import EnergyDialog

        summary = self.summary
        if summary is None or not summary.rows:
            self.status.setText("Measure first; there is nothing to "
                                "recommend from.")
            return None
        self._dialog = EnergyDialog(summary, self)
        self._dialog.show()
        self._report(self._dialog.status.text())
        return self._dialog

    def compare_infusions(self, path: str = ""):
        """
        These infusions against a reference project's saved summary.

        The reference is read from the project file alone — the figures and
        the peak lists its Infusions tab measured — so a reference whose
        acquisitions have moved to another disk is still a reference. A
        project that never measured one holds nothing to compare against,
        which is said in those words rather than shown as an empty table.
        """
        from ..infusion_compare import compare_infusions, read_summary
        from .infusion_compare_dialog import InfusionCompareDialog

        summary = self.summary
        if summary is None or not summary.rows:
            self.status.setText("Measure first; there is nothing to compare.")
            return None
        if not path:
            start = self.settings.value("io/last_dir", "", type=str)
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Reference project", start,
                "MIL-Q project (*.oqproj *.opvproj)")
            if not path:
                return None
            self.settings.setValue("io/last_dir", os.path.dirname(path))
        try:
            reference = read_summary(path)
        except (OSError, ValueError) as exc:
            self._report(f"Could not read {os.path.basename(path)}: {exc}")
            return None
        if reference is None:
            self._report(f"{os.path.basename(path)} holds no infusion "
                         f"summary: open it, press Measure on the Infusions "
                         f"tab and save it again.")
            return None
        comparison = compare_infusions(
            summary, reference,
            current_name=(os.path.splitext(os.path.basename(
                self.session.project_path))[0]
                if self.session.project_path else "the open infusions"))
        self.session.infusion_comparison = comparison
        self._dialog = InfusionCompareDialog(comparison, self)
        self._dialog.show()
        self._report(comparison.summary())
        return comparison

    def use_in_method(self) -> int:
        """
        Offer the chosen infusions to the component table.

        The dialog does the writing and the recording; this only says which
        rows, and reports what came of it. Returns how many components were
        written, so a test does not have to look at the label.
        """
        from .standards_dialog import StandardsDialog

        rows = self.chosen()
        if not rows:
            self.status.setText("Measure first; there is nothing to offer the "
                                "method.")
            return 0
        dialog = StandardsDialog(self.session, rows, self)
        dialog.exec()
        if dialog.applied or dialog.skipped:
            said = (f"{dialog.applied} component(s) written into the method "
                    f"from {len(rows)} infusion(s).")
            if dialog.skipped:
                said += (f" {len(dialog.skipped)} left nothing to write — the "
                         f"method already carries "
                         f"{', '.join(dict.fromkeys(dialog.skipped))}, and a "
                         f"second infusion of a compound can only fill what "
                         f"the first left empty.")
            self._report(said)
        return dialog.applied

    def new_standard(self):
        """
        The New standard dialog, on the selected row's acquisition.

        Not gated on a Measure: entering a standard reads one file and this
        table is a summary of many, so the dialog asks for a file of its own
        where nothing is selected. Where one row is selected its acquisition
        is handed over, since that is the infusion the analyst is looking at.
        """
        from .new_standard_dialog import NewStandardDialog

        rows = self.chosen()
        row = rows[0] if len(rows) == 1 else None
        path, name = "", ""
        if row is not None:
            name = row.compound
            for entry in getattr(self.session, "entries", []) or []:
                if str(getattr(entry, "name", "")) == row.sample:
                    path = str(getattr(entry, "path", "") or "")
                    break
        dialog = NewStandardDialog(self.session, self, path=path, name=name)
        dialog.exec()
        if dialog.component is not None or dialog.record is not None:
            self._report(dialog.status.text())
        dialog.deleteLater()
        return dialog

    def export_csv(self, path: str = "") -> str:
        """The whole table, not the selection: a summary with rows left out
        is not the thing it claims to be."""
        summary = self.summary
        if summary is None or not summary.rows:
            self.status.setText("Measure first; there is nothing to export.")
            return ""
        if not path:
            start = os.path.join(
                self.settings.value("io/last_dir", "", type=str),
                "infusions.csv")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export the infusion summary", start, "CSV (*.csv)")
            if not path:
                return ""
            self.settings.setValue("io/last_dir", os.path.dirname(path))
        try:
            written = write_summary_csv(summary, path)
        except OSError as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return ""
        self._report(f"{len(summary.rows)} row(s) written to "
                     f"{os.path.basename(written)}.")
        return written

    # -- quantitation ---------------------------------------------------------- #
    def quantify(self):
        """
        Open the ratio dialog: analyte over internal standard, in the spray.

        Not gated on the summary above having been measured. The two answer
        different questions — that one asks whether a vial is what its label
        says, this one asks how much of one compound there is against
        another — and they read the files independently.
        """
        from .infusion_quant_dialog import InfusionQuantDialog

        dialog = InfusionQuantDialog(self.session, self)
        dialog.measure()
        dialog.exec()
        return dialog

    # -- a record of every row ------------------------------------------------ #
    def _own_path(self) -> str:
        """
        The MSP the analyst's own records go into, asked for once.

        The same setting the Explorer's library panel writes: there is one
        library of one's own and both places mean the same file. A save
        dialog, since it usually does not exist yet, with the overwrite
        warning off — picking the library that is already there is the
        ordinary case and the records are appended, not written over.
        """
        path = self.settings.value(SETTING_OWN_PATH, "", type=str)
        if path:
            return path
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Your own spectral library",
            os.path.expanduser("~/my-library.msp"),
            "MSP (*.msp);;All files (*)",
            options=QtWidgets.QFileDialog.Option.DontConfirmOverwrite)
        if not path:
            return ""
        if not os.path.splitext(path)[1]:
            path += ".msp"
        self.settings.setValue(SETTING_OWN_PATH, path)
        return path

    def _acquired_times(self) -> dict:
        """
        When each open acquisition was measured, by file name.

        The report holds the file it came from and the session holds the
        sample, and only the sample knows the day the instrument measured
        on — which is the day a record's history is ordered by, and is not
        the day the record is being written.
        """
        found = {}
        for entry in getattr(self.session, "entries", []) or []:
            when = str(getattr(getattr(entry, "sample", None),
                               "acquisition_time", "") or "")
            name = os.path.basename(str(getattr(entry, "path", "") or ""))
            if when and name:
                found[name] = when
        return found

    def _identify(self, row):
        """
        The formula and the adduct to write into one row's record.

        What the report already worked out first — it identified the adduct
        against the channel's written precursor and put the compound's
        labels back into the formula — and the method's component table for
        whatever that leaves empty, which is the case where an infusion was
        measured without anything being explained.

        The component table's two are taken **together or not at all**. A
        formula on its own gives the record no mass to check itself against,
        and where the report identified no adduct the reason is usually that
        no adduct of that formula reaches the precursor the channel
        isolated — so writing the formula anyway would put the compound the
        file is named after on a record of a different ion.
        """
        formula, adduct = identity_of(row.report)
        if formula and adduct:
            return formula, adduct
        component = component_for(getattr(self.session, "method", None),
                                  getattr(row, "compound", ""))
        declared = (str(getattr(component, "formula", "") or ""),
                    str(getattr(component, "adduct", "") or ""))
        return declared if all(declared) else (formula, adduct)

    def add_all_to_library(self, path: str = ""):
        """
        One record per measured row, appended to the library of one's own.

        A folder of infusions is written in one go rather than a spectrum at
        a time from the Explorer: the table has already averaged, centroided
        and identified every one of them, and a record is those numbers with
        a name and a provenance on them.

        A row that proposed no compound is skipped and named, and so is one
        whose acquisition and channel are already in the file — the
        provenance in a record's comment is the key, so pressing this twice
        adds nothing the second time.
        """
        summary = self.summary
        if summary is None or not summary.rows:
            self.status.setText("Measure first; there is nothing to write.")
            return None
        path = path or self._own_path()
        if not path:
            return None
        made = records_from_summary(
            summary.rows, existing=provenance_keys(path),
            identify=self._identify, acquired=self._acquired_times())
        written = 0
        if made.entries:
            try:
                written = write_msp(made.entries, path, append=True)
            except OSError as exc:
                self.status.setText(f"Could not write {path}: {exc}")
                return None
            names = ", ".join(dict.fromkeys(e.name for e in made.entries))
            self.session.record(
                audit.OWN_LIBRARY, target=names,
                after=os.path.basename(path),
                note=f"{written} record(s) from the Infusions tab")
        self._report(f"{made.line(written)} → {os.path.basename(path)}")
        return made

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
