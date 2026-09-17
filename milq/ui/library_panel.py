"""
The spectrum on screen searched against a spectral library, and written
into one.

A library is loaded once and remembered; the search takes the spectrum the
Explorer is showing, the active channel's precursor, and lists the records
that match with both scores, the matched peaks of the chosen one, and an
overlay of its peaks on the spectrum pane.

The other direction is a library of one's own. A deuterated standard
infused deliberately is in no public library, so the spectrum on screen is
the only record of it there will ever be: *Add spectrum to library…* writes
it into an MSP file of the analyst's choosing, appending, and reloads that
file when it is the one loaded so the record is searchable at once.

Both directions carry the **mass axis**. A record written while the
recalibration was on says so in its comment; a search says, per hit, which
axis each side was written from and how far apart the two are, and warns
where that is further than the tolerance its own peaks were paired within.
*Re-search with the axis matched* then asks the question again with both
sides on one axis.
"""

from __future__ import annotations

import datetime
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from ..infusion import format_counts
from ..library import (MIN_MATCHED, OWN_MIN_RELATIVE, PEAK_TOLERANCE_PPM,
                       PRECURSOR_TOLERANCE_DA, LibraryEntry, LibraryHit,
                       SpectralLibrary, axis_named, count_records,
                       entry_from_spectrum, load_library, recalibration_in,
                       rewrite_records, to_axis, write_msp)
from ..lipidmaps import mass_precision
from . import theme
from .help_window import describe
from .library_add_dialog import AddToLibraryDialog, default_adduct
from .settings import settings
from .flow_layout import FlowLayout

SETTING_PATH = "library/path"
#: the MSP the analyst's own records are appended to, chosen once
SETTING_OWN_PATH = "library/own_path"


class LibraryPanel(QtWidgets.QWidget):
    sigOverlay = QtCore.pyqtSignal(list, str)     # [(m/z, share)], label
    sigClearOverlay = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        describe(self, "spectral-library")
        self.library: SpectralLibrary | None = None
        self._hits: list[LibraryHit] = []
        self._spectrum = None
        #: what the last search did to the query's mass axis, as a phrase for
        #: the status line: empty unless the axis was matched to a record's
        self._matched_axis = ""
        #: set by the Explorer: returns (mz, intensity, precursor) on screen,
        #: optionally with a fourth element — a mapping describing where the
        #: spectrum came from, which is what a record of one's own has to say
        self.spectrum_source = None
        self._context: dict = {}
        #: set by the Explorer, and optional: the open batch, for the folders
        #: its acquisitions were opened from and the mass corrections in
        #: force. Duck-typed, so this panel still builds with no session
        self.session = None
        self.settings = settings()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        top = FlowLayout()
        self.btn_load = QtWidgets.QPushButton("Load library…")
        self.btn_load.setToolTip("An MSP (NIST, MassBank, MoNA, GNPS) or MGF file")
        top.addWidget(self.btn_load)
        self.library_label = QtWidgets.QLabel("No library loaded.")
        self.library_label.setProperty("role", "caption")
        top.addWidget(self.library_label, 1)
        layout.addLayout(top)

        own = FlowLayout()
        self.btn_add = QtWidgets.QPushButton("Add spectrum to library…")
        self.btn_add.setToolTip(
            "Write the spectrum on screen into a library of your own — an "
            "MSP file chosen once and appended to. An infused standard is in "
            "no public library, and this is the only record of it there is")
        own.addWidget(self.btn_add)
        self.btn_history = QtWidgets.QPushButton("History…")
        self.btn_history.setToolTip(
            "Read your own library back as a control chart: every record of "
            "one compound, in the order it was acquired, scored against the "
            "first of them — the standard checked against itself over the "
            "days it was verified")
        own.addWidget(self.btn_history)
        self.btn_rewrite = QtWidgets.QPushButton("Rewrite from files…")
        self.btn_rewrite.setToolTip(
            "Read every record whose acquisition is still on disk again from "
            "that file and write it back in place, so records made by an "
            "older version gain the fields this one writes. A record whose "
            "file is gone is left exactly as it is; the library as it stands "
            "is copied to <name>.msp.bak first")
        own.addWidget(self.btn_rewrite)
        self.own_label = QtWidgets.QLabel("")
        self.own_label.setProperty("role", "caption")
        own.addWidget(self.own_label, 1)
        layout.addLayout(own)

        form = QtWidgets.QFormLayout()
        self.precursor_edit = QtWidgets.QLineEdit()
        self.precursor_edit.setPlaceholderText("from the active channel")
        self.precursor_edit.setToolTip(
            "Only records whose precursor sits within the tolerance are "
            "scored; records with no precursor are scored anyway and say so")
        form.addRow("Precursor", self.precursor_edit)
        self.precursor_tol = QtWidgets.QDoubleSpinBox()
        self.precursor_tol.setRange(0.001, 5.0)
        self.precursor_tol.setDecimals(3)
        self.precursor_tol.setValue(PRECURSOR_TOLERANCE_DA)
        self.precursor_tol.setSuffix(" Da")
        self.precursor_tol.setToolTip("Wider for a nominal-mass library")
        form.addRow("Precursor ±", self.precursor_tol)
        self.peak_tol = QtWidgets.QDoubleSpinBox()
        self.peak_tol.setRange(1.0, 500.0)
        self.peak_tol.setDecimals(0)
        self.peak_tol.setValue(PEAK_TOLERANCE_PPM)
        self.peak_tol.setSuffix(" ppm")
        form.addRow("Peaks ±", self.peak_tol)
        self.min_matched = QtWidgets.QSpinBox()
        self.min_matched.setRange(1, 50)
        self.min_matched.setValue(MIN_MATCHED)
        self.min_matched.setToolTip(
            "A record has to land this many of its peaks to be listed. One "
            "peak in common is a coincidence: a phosphocholine ion at 184.07 "
            "scored 83 against a laxative whose fragment sits 13 ppm away")
        form.addRow("Matched peaks ≥", self.min_matched)
        self.unknown_precursor = QtWidgets.QCheckBox("Also records with no precursor")
        self.unknown_precursor.setToolTip(
            "A filtered search leaves out records that state no precursor at "
            "all — neither a written mass nor a formula with an adduct — "
            "since a filter that admits them is not one. Tick to score them "
            "anyway; their Δ ppm is blank")
        form.addRow("", self.unknown_precursor)
        self.other_polarity = QtWidgets.QCheckBox("Also the other polarity")
        self.other_polarity.setToolTip(
            "The active channel's polarity leaves out records whose adduct "
            "declares the other sign — a negative-mode record cannot be what "
            "a positive-mode scan measured. Records that say nothing about "
            "their polarity are kept either way. Tick to score them all")
        form.addRow("", self.other_polarity)
        layout.addLayout(form)

        self.btn_search = QtWidgets.QPushButton("Search the spectrum on screen")
        self.btn_search.setEnabled(False)
        layout.addWidget(self.btn_search)

        self.hits = QtWidgets.QTreeWidget()
        self.hits.setHeaderLabels(["Record", "Score", "Reverse", "Matched",
                                   "Precursor", "Δ ppm", "Δ from", "Formula",
                                   "Axis"])
        self.hits.setRootIsDecorated(False)
        self.hits.setToolTip(
            "Score: the cosine over everything both spectra hold. Reverse: "
            "only whether the library's peaks are in the measured spectrum, "
            "so a co-eluting impurity does not count against a record. A "
            "high reverse with a low score is a compound present with company")
        layout.addWidget(self.hits, 3)

        self.energies = QtWidgets.QLabel("")
        self.energies.setWordWrap(True)
        self.energies.setProperty("role", "hint")
        self.energies.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.energies.setToolTip(
            "A record does not travel between collision energies: on the "
            "bile-acid infusions a CA-d4 record at 45 eV scored 6 against "
            "the same vial at 12 eV. Where a compound has records at two or "
            "more energies of one activation, this interpolates between them "
            "and says which energy the spectrum on screen fits best. It never "
            "goes past the energies on file and never mixes two activations, "
            "so a compound with one record of an activation says so. The "
            "score is the cosine over the profile's own ions")
        self.energies.hide()
        layout.addWidget(self.energies)

        self.pairs = QtWidgets.QTreeWidget()
        self.pairs.setHeaderLabels(["Measured", "Library", "ppm", "Measured %",
                                    "Library %"])
        self.pairs.setRootIsDecorated(False)
        layout.addWidget(self.pairs, 2)

        buttons = FlowLayout()
        self.btn_overlay = QtWidgets.QPushButton("Overlay on spectrum")
        self.btn_overlay.setEnabled(False)
        self.btn_clear = QtWidgets.QPushButton("Clear overlay")
        self.btn_axis = QtWidgets.QPushButton("Re-search with the axis matched")
        self.btn_axis.setEnabled(False)
        self.btn_axis.setToolTip(
            "This record and the spectrum on screen were written from "
            "different mass axes — one of them recalibrated, the other not, "
            "or both by different amounts. Search again with the spectrum "
            "moved onto the record's axis, so the score is about the "
            "compound and not about the correction. Nothing on screen "
            "changes: the masses are moved for the search only")
        buttons.addWidget(self.btn_overlay)
        buttons.addWidget(self.btn_clear)
        buttons.addWidget(self.btn_axis)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "hint")
        layout.addWidget(self.status)

        self.btn_load.clicked.connect(self._choose_library)
        self.btn_add.clicked.connect(self.add_spectrum)
        self.btn_history.clicked.connect(self.show_history)
        # not connected directly: `clicked` carries the button's checked
        # state, which would arrive as `confirm=False` and write over the
        # library without asking
        self.btn_rewrite.clicked.connect(lambda: self.rewrite_own_library())
        self.btn_search.clicked.connect(self.search)
        self.hits.currentItemChanged.connect(self._show_pairs)
        self.btn_overlay.clicked.connect(self._overlay)
        self.btn_clear.clicked.connect(self.sigClearOverlay)
        self.btn_axis.clicked.connect(lambda: self.search_on_record_axis())

        remembered = self.settings.value(SETTING_PATH, "", type=str)
        if remembered and os.path.exists(remembered):
            self.load(remembered)
        self._refresh_own_label()

    # -- the library ------------------------------------------------------------ #
    def _choose_library(self) -> None:
        start = os.path.dirname(self.library.path) if self.library else ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load a spectral library", start,
            "Spectral libraries (*.msp *.mgf *.txt);;All files (*)")
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        try:
            self.library = load_library(path)
        except Exception as exc:
            self.status.setText(f"Could not read {os.path.basename(path)}: {exc}")
            return
        self.settings.setValue(SETTING_PATH, path)
        self.library_label.setText(
            f"{len(self.library):,} records from {os.path.basename(path)}, "
            f"{self.library.with_precursor:,} with a precursor")
        self.btn_search.setEnabled(True)
        self.status.setText("")

    # -- the spectrum ----------------------------------------------------------- #
    def set_spectrum(self, mz, intensity, precursor: float | None = None,
                     context: dict | None = None) -> None:
        self._spectrum = (mz, intensity)
        if context is not None:
            self._context = dict(context)
        if precursor:
            # the channel's precursor is what the instrument was told, to
            # the decimals it was typed with: 647.5 is known to ±0.05, and
            # a filter of ±0.02 around it is asking for digits it lacks
            self.precursor_edit.setText(f"{precursor:g}")
            self.precursor_tol.setValue(max(self.precursor_tol.value(),
                                            mass_precision(precursor)))

    def _pull_spectrum(self) -> None:
        """
        Ask the Explorer for what is on screen now.

        The hook returns the spectrum, the active channel's precursor and —
        where the caller can supply one — a mapping saying which sample,
        channel and scans it came from. Older callers return three values
        and are read as carrying no such mapping, which is why the fourth
        element is taken by length rather than unpacked.
        """
        if self.spectrum_source is None:
            return
        current = self.spectrum_source()
        if current is None:
            return
        mz, intensity, precursor = current[0], current[1], current[2]
        context = current[3] if len(current) > 3 else None
        self.set_spectrum(mz, intensity, precursor, context)

    def query_polarity(self) -> str:
        """
        The polarity of the channel the spectrum came from, as the file
        writes it — `Positive`, `Negative` — or empty when the Explorer
        could not say. It is not typed anywhere: a scan's polarity is a
        fact about the acquisition, and the only choice the reader has is
        whether to honour it.
        """
        return str(self._context.get("polarity") or "")

    def _noise_floor(self) -> float | None:
        """
        The absolute floor the Explorer measured for this spectrum, if any.

        Only an infusion has one — the average of a whole run is the only
        spectrum the measurement is defined for — so this is None for every
        other, and `entry_from_spectrum` then holds the record to its
        relative floor alone, as it always did.
        """
        value = self._context.get("noise_floor")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _query_precursor(self) -> float | None:
        text = self.precursor_edit.text().strip().replace(",", ".")
        try:
            return float(text) if text else None
        except ValueError:
            return None

    def query_recalibration(self) -> float | None:
        """
        The mass correction in force on the spectrum on screen, in ppm.

        Read from the sentence the Explorer passes with the spectrum — the
        one that also goes into a record's comment when the spectrum is
        written into a library — so the query's axis and a record's are read
        by the same parser and cannot be read two different ways. None where
        nothing was applied, which is the ordinary case.
        """
        return recalibration_in(self._context.get("recalibration"))

    def search(self, *, onto_ppm: float | None = None,
               match_axis: bool = False) -> None:
        """
        The spectrum on screen against the library.

        `match_axis` searches with the query moved onto `onto_ppm` — the axis
        a record was written from — so that both sides sit on one axis and
        the score is about the compound. Nothing on screen changes: the
        masses are moved for the search and thrown away, because the pane is
        showing what the acquisition gave.
        """
        if self.library is None:
            self.status.setText("Load a library first.")
            return
        if not match_axis:
            self._pull_spectrum()
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return
        mz, intensity = self._spectrum
        polarity = self.query_polarity()
        query_ppm = self.query_recalibration()
        moved = ""
        if match_axis:
            mz = to_axis(mz, query_ppm, onto_ppm)
            moved = (f"Searched with the query moved from "
                     f"{axis_named(query_ppm)} onto {axis_named(onto_ppm)}. "
                     f"That takes the correction one side carried and the "
                     f"other did not out of the comparison; it does not put "
                     f"either on the right axis — Rewrite from files… does "
                     f"that, by writing every record from the axis in force. ")
            query_ppm = onto_ppm
        self._matched_axis = moved
        self._hits = self.library.search(
            mz, intensity, self._query_precursor(),
            tolerance_ppm=self.peak_tol.value(),
            precursor_tolerance=self.precursor_tol.value(),
            min_matched=self.min_matched.value(),
            include_unknown_precursor=self.unknown_precursor.isChecked(),
            polarity=polarity,
            include_other_polarity=self.other_polarity.isChecked(),
            query_correction=query_ppm)
        self._show_energies(mz, intensity, polarity)
        self.hits.clear()
        self.pairs.clear()
        for hit in self._hits:
            entry = hit.entry
            # a record that states its precursor twice and disagrees with
            # itself says so on the row, with both numbers: which of the
            # two is wrong cannot be told from here
            precursor = "—" if entry.precursor is None else f"{entry.precursor:.4f}"
            if hit.precursor_disagrees:
                precursor += f" ≠ {entry.exact_precursor:.4f}"
            # which mass axis this record was written from, and — where the
            # query was corrected too — how far the two sit apart before the
            # compound is considered at all
            axis = ("instrument" if hit.record_ppm is None
                    else f"corrected {hit.record_ppm:+.1f}")
            if hit.axis_gap_ppm:
                axis += f" · {abs(hit.axis_gap_ppm):.1f} ppm apart"
            item = QtWidgets.QTreeWidgetItem([
                entry.name, f"{hit.score * 100:.0f}", f"{hit.reverse * 100:.0f}",
                f"{hit.matched}/{hit.of_library}", precursor,
                "—" if hit.delta_ppm is None else f"{hit.delta_ppm:+.1f}",
                hit.delta_basis or "—", entry.formula, axis])
            item.setToolTip(8, hit.axis_sentence
                            + (f"\n\n{hit.axis_warning}" if hit.axes_differ
                               else ""))
            if hit.axes_differ:
                # the one thing on the row that is not a property of the
                # record: the score itself is not to be read
                item.setForeground(
                    8, QtGui.QBrush(QtGui.QColor(theme.danger())))
            for column in (1, 2, 3, 4, 5):
                item.setTextAlignment(column, QtCore.Qt.AlignmentFlag.AlignRight)
            item.setToolTip(0, "\n".join(f"{k}: {v}" for k, v in entry.fields.items())
                            or entry.precursor_type)
            if hit.precursor_disagrees:
                item.setToolTip(4, (
                    f"{entry.precursor:g} as written, {entry.exact_precursor:.4f} "
                    f"from {entry.formula} {entry.precursor_type} — further "
                    f"apart than the ±{entry.written_precision:g} Da the "
                    f"written value is good to"))
            if hit.delta_basis == "formula":
                basis = (f"Δ measured against {entry.exact_precursor:.4f}, what "
                         f"{entry.formula} {entry.precursor_type} weighs — not "
                         f"against the written precursor")
            elif hit.delta_basis == "written":
                basis = ("The record gives no formula and adduct to compute its "
                         "mass from, so Δ is against its written precursor, "
                         "whatever that was typed to")
            else:
                basis = "No precursor to measure against"
            item.setToolTip(6, basis)
            self.hits.addTopLevelItem(item)
        for column in range(self.hits.columnCount()):
            self.hits.resizeColumnToContents(column)
        if self._hits:
            self.hits.setCurrentItem(self.hits.topLevelItem(0))
            precursor = self._query_precursor()
            scoped = (f" within ±{self.precursor_tol.value():g} Da of {precursor:.4f}"
                      if precursor is not None else "")
            if polarity and not self.other_polarity.isChecked():
                scoped += f", {str(polarity).lower()} records only"
            said = (f"{self._matched_axis}{len(self._hits)} record(s) "
                    f"matched{scoped}; best "
                    f"{self._hits[0].score * 100:.0f}.")
            # the axis warning goes on the line rather than only in a
            # tooltip: a score measured across two mass axes is not a score,
            # and a reader who has to hover to find that out will not
            crossed = [hit for hit in self._hits if hit.axes_differ]
            if crossed:
                said += (f" {len(crossed)} of them on a different mass axis "
                         f"from the spectrum: {crossed[0].axis_warning}. "
                         f"Re-search with the axis matched.")
            self.status.setText(said)
        else:
            self.status.setText(f"{self._matched_axis}No record matched. "
                                f"Widen the tolerances, or the compound is "
                                f"not in this library.")
        self.btn_overlay.setEnabled(bool(self._hits))

    def _show_energies(self, mz, intensity, polarity) -> None:
        """
        The energy-profile lines under the hit list, one per compound and
        activation the library can say anything about.

        Additional to the hit list and never a replacement for it: the hits
        answer *which record is this like*, these answer *what conditions
        would produce this*. Hidden entirely where no compound has more than
        one record, which is every public library — a line saying nothing on
        every search is a line nobody reads.
        """
        self._energies = []
        if self.library is None:
            self.energies.hide()
            return
        try:
            self._energies = self.library.search_energy(
                mz, intensity, self._query_precursor(),
                tolerance_ppm=self.peak_tol.value(),
                precursor_tolerance=self.precursor_tol.value(),
                min_matched=self.min_matched.value(),
                include_unknown_precursor=self.unknown_precursor.isChecked(),
                polarity=polarity,
                include_other_polarity=self.other_polarity.isChecked())
        except Exception as exc:            # a library that cannot profile
            # said rather than swallowed: a line that quietly disappears on
            # some files and not others is worse than one that says why
            self._energies = []
            self.energies.setText(f"No energy profile could be built: {exc}")
            self.energies.show()
            return
        said = [one.line() for one in self._energies]
        self.energies.setText("\n".join(said))
        self.energies.setVisible(bool(said))

    def _current_hit(self) -> LibraryHit | None:
        item = self.hits.currentItem()
        if item is None:
            return None
        index = self.hits.indexOfTopLevelItem(item)
        return self._hits[index] if 0 <= index < len(self._hits) else None

    def search_on_record_axis(self):
        """
        The button: search again with both sides on the record's mass axis.

        The record's axis rather than the query's, in both directions — a
        corrected query is put back where the instrument read it to meet an
        uncorrected record, and an uncorrected query is moved to meet a
        corrected one. Which axis was used is said on the status line, since
        the scores that come back are not the scores the ordinary search
        would give and the reader has to know which question was asked.

        It is a diagnosis and not a repair: it says how much of the agreement
        was the correction, and it can make a match worse, because moving a
        query onto a record written from an uncorrected axis moves it off its
        own lock masses. Measured on a real infusion, a hit of 61.0 at a 5
        ppm tolerance came back as no hit at all that way. What puts every
        record on one right axis is *Rewrite from files…*.
        """
        hit = self._current_hit()
        if hit is None:
            self.status.setText("Search first, then choose a record.")
            return None
        self.search(onto_ppm=hit.record_ppm, match_axis=True)
        return self._hits

    def _show_pairs(self, *_args) -> None:
        self.pairs.clear()
        hit = self._current_hit()
        self.btn_axis.setEnabled(hit is not None and bool(hit.axis_gap_ppm))
        if hit is None:
            return
        for pair in sorted(hit.pairs, key=lambda p: -p.library_share):
            item = QtWidgets.QTreeWidgetItem([
                f"{pair.measured:.4f}", f"{pair.library:.4f}", f"{pair.ppm:+.1f}",
                f"{pair.measured_share * 100:.1f}", f"{pair.library_share * 100:.1f}"])
            for column in range(5):
                item.setTextAlignment(column, QtCore.Qt.AlignmentFlag.AlignRight)
            self.pairs.addTopLevelItem(item)
        for column in range(5):
            self.pairs.resizeColumnToContents(column)

    def _overlay(self) -> None:
        hit = self._current_hit()
        if hit is None:
            return
        pattern = [(float(m), float(i)) for m, i in zip(hit.entry.mz, hit.entry.intensity)]
        self.sigOverlay.emit(pattern, hit.entry.name)

    # -- a library of one's own ------------------------------------------------- #
    @property
    def own_path(self) -> str:
        return self.settings.value(SETTING_OWN_PATH, "", type=str)

    def set_own_path(self, path: str) -> None:
        self.settings.setValue(SETTING_OWN_PATH, path)
        self._refresh_own_label()

    def refresh_own(self) -> None:
        """
        Read the library of one's own again: its count, and its records.

        Called by anything that appends to the file from outside this panel —
        *File ▸ New standard…* does — so the count under the button and, when
        the file written to is the one loaded, the searchable records are
        what is on disk rather than what was on disk when the tab was built.
        """
        path = self.own_path
        if (path and self.library is not None and self.library.path
                and os.path.abspath(self.library.path) == os.path.abspath(path)
                and os.path.exists(path)):
            self.load(path)
        self._refresh_own_label()

    def _refresh_own_label(self) -> None:
        path = self.own_path
        if not path:
            self.own_label.setText("No library of your own yet.")
            self.btn_history.setEnabled(False)
            self.btn_rewrite.setEnabled(False)
            return
        name = os.path.basename(path)
        if not os.path.exists(path):
            self.own_label.setText(f"Your library: {name}, not written yet")
            self.btn_history.setEnabled(False)
            self.btn_rewrite.setEnabled(False)
            return
        records = count_records(path)
        self.own_label.setText(f"Your library: {records:,} record(s) in {name}")
        self.btn_history.setEnabled(records > 0)
        self.btn_rewrite.setEnabled(records > 0)

    def show_history(self):
        """
        The records already written, read back as one standard over time.

        Read from the file rather than from anything held here: the library
        of one's own is appended to over months and by more than one window,
        and what is on disk is the history.
        """
        from .standard_history_dialog import StandardHistoryDialog

        path = self.own_path
        if not path or not os.path.exists(path):
            self.status.setText("Write a record of your own first.")
            return None
        dialog = StandardHistoryDialog(path, parent=self)
        dialog.exec()
        # the dialog offers the repair for a history split across two mass
        # axes and does not perform it: this panel owns the file, the folders
        # and the corrections in force, and there is one place that writes
        if dialog.rewrite_requested:
            self.rewrite_own_library()
        dialog.deleteLater()
        return dialog

    # -- rewriting it from the acquisitions --------------------------------- #
    def _acquisition_folders(self) -> list[str]:
        """
        Where to look for the files the records name.

        A record's comment carries a file name and never a path, because a
        path stops being true the moment the acquisition is copied anywhere.
        So the folders are the ones the open batch was opened from, with the
        last folder anything was read from after them; the library's own
        folder is added by `rewrite_records` itself.
        """
        folders: list[str] = []
        for entry in getattr(self.session, "entries", []) or []:
            folder = os.path.dirname(str(getattr(entry, "path", "") or ""))
            if folder:
                folders.append(folder)
        last = self.settings.value("io/last_dir", "", type=str)
        if last:
            folders.append(last)
        return list(dict.fromkeys(folders))

    def _corrections(self) -> dict:
        """
        The mass correction in force for each open acquisition, by file name.

        `Session.correction_for` answers None whenever the switch is off, so
        a batch that is not being recalibrated hands over nothing and the
        records come back on the axis the instrument wrote.
        """
        session = self.session
        if session is None or not hasattr(session, "correction_for"):
            return {}
        found = {}
        for entry in getattr(session, "entries", []) or []:
            try:
                correction = session.correction_for(entry.key)
            except Exception:
                correction = None
            name = os.path.basename(str(getattr(entry, "path", "") or ""))
            if correction is not None and name:
                found[name.lower()] = correction
        return found

    def rewrite_own_library(self, confirm: bool = True):
        """
        Every record of one's own read again from the file it names.

        The button. `confirm` is what the dialog is for and what a test turns
        off: the question names the file and how many records are in it,
        because this writes over a file the analyst has been adding to for
        months — and the answer is that the file as it was is kept beside it.
        """
        path = self.own_path
        if not path or not os.path.exists(path):
            self.status.setText("Write a record of your own first.")
            return None
        name = os.path.basename(path)
        total = count_records(path)
        if confirm:
            answer = QtWidgets.QMessageBox.question(
                self, "Rewrite from files",
                f"Read every one of the {total:,} record(s) in {name} again "
                f"from the acquisition its comment names, and write it back "
                f"in place?\n\nA record whose file is not on disk is left "
                f"exactly as it is. {name} as it stands is copied to "
                f"{name}.bak first.")
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return None
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        try:
            result = rewrite_records(path, folders=self._acquisition_folders(),
                                     corrections=self._corrections())
        except OSError as exc:
            self.status.setText(f"Could not rewrite {name}: {exc}")
            return None
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if self.library is not None and self.library.path and \
                os.path.abspath(self.library.path) == os.path.abspath(path):
            self.load(path)              # what is searched is what is on disk
        self._refresh_own_label()
        self.status.setText(result.summary())
        return result

    def _choose_own_path(self) -> str:
        """
        Where the analyst's own records go, asked for once and remembered.

        A save dialog, since the file usually does not exist yet, but with
        the overwrite warning off: picking the library that is already there
        is the ordinary case and the record is appended, not written over.
        """
        start = self.own_path or os.path.expanduser("~/my-library.msp")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Your own spectral library", start, "MSP (*.msp);;All files (*)",
            options=QtWidgets.QFileDialog.Option.DontConfirmOverwrite)
        if path:
            if not os.path.splitext(path)[1]:
                path += ".msp"
            self.set_own_path(path)
        return path

    def own_prefill(self) -> dict:
        """
        What the acquisition already knows about the spectrum on screen.

        Everything here comes from the file or from what is typed in the
        panel; only the name, the formula and the adduct are the analyst's
        to give. The comment is the pane's own title — sample, channel and
        the scans the average was taken over — with the file and the date,
        because a record whose provenance is not written down cannot be
        checked against the acquisition later. Where the mass axis was
        recalibrated the comment says so and says what the correction stood
        on: the peaks written into the record are not the ones the
        instrument reported, and a record that did not admit that could not
        be compared with one written from the raw axis.
        """
        context = self._context
        parts = [str(p) for p in (context.get("title"), context.get("file")) if p]
        # how the adduct on this record was arrived at. A record states an
        # adduct and nothing in it says whether that was measured from a
        # survey scan or deduced from a number somebody typed, which is the
        # difference between a fact and a reading
        if context.get("adduct"):
            parts.append(str(context["adduct"]))
        axis = str(context.get("recalibration") or "")
        if axis and axis not in " \u00b7 ".join(parts):
            parts.append(axis)
        parts.append(f"added {datetime.date.today().isoformat()}")
        return {
            "name": str(context.get("name", "")),
            "precursor": self._query_precursor(),
            "precursor_type": default_adduct(context.get("polarity", "")),
            "formula": str(context.get("formula", "")),
            "collision_energy": context.get("collision_energy"),
            "comment": " · ".join(parts),
            # the day the instrument measured on, which is not the day the
            # record was made: a folder acquired over three months, written
            # into a library in one afternoon, is three months of history
            # and "added" says nothing about it. `standard_history` orders
            # by this
            "acquired": str(context.get("acquired", "") or ""),
            # measured from the profile spectrum by the Explain tab, and not
            # recoverable from the record afterwards: the envelope it was
            # read from is under the floor the record's peaks are kept at
            "isotopic_purity": str(context.get("isotopic_purity", "") or ""),
        }

    def add_spectrum(self) -> None:
        """The button: the spectrum on screen, named, into the analyst's file."""
        self._pull_spectrum()
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return
        path = self.own_path or self._choose_own_path()
        if not path:
            return
        mz, intensity = self._spectrum
        try:
            preview = entry_from_spectrum("preview", mz, intensity,
                                          min_absolute=self._noise_floor())
        except ValueError as exc:
            self.status.setText(f"Nothing to write: {exc}.")
            return
        dialog = AddToLibraryDialog(self.own_prefill(), preview.peaks,
                                    os.path.basename(path), self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.add_to_own_library(**dialog.values())
        dialog.deleteLater()

    def add_to_own_library(self, name: str, precursor: float | None = None,
                           precursor_type: str = "", formula: str = "",
                           collision_energy: float | None = None,
                           comment: str = "", acquired: str = "",
                           isotopic_purity: str = "",
                           path: str = "") -> LibraryEntry | None:
        """
        Append the spectrum on screen to the analyst's own MSP, and say so.

        Separate from the dialog on purpose: the dialog collects values and
        this writes them, so the flow can be exercised without a modal loop.
        Where the library that is loaded *is* the file written to, it is read
        again, so the record can be searched for the moment it exists — which
        is the check that it was written in a form the parser reads.
        """
        path = path or self.own_path
        if not path:
            self.status.setText("Choose a file for your own library first.")
            return None
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return None
        mz, intensity = self._spectrum
        try:
            entry = entry_from_spectrum(
                name, mz, intensity, precursor=precursor,
                precursor_type=precursor_type, formula=formula,
                collision_energy=collision_energy, comment=comment,
                acquired=acquired, isotopic_purity=isotopic_purity,
                min_absolute=self._noise_floor())
            write_msp([entry], path, append=True)
        except (ValueError, OSError) as exc:
            self.status.setText(f"Could not write the record: {exc}")
            return None
        if self.library is not None and self.library.path and \
                os.path.abspath(self.library.path) == os.path.abspath(path):
            self.load(path)                  # searchable at once
        self._refresh_own_label()
        floor = self._noise_floor()
        measured = (f" and above the measured noise floor of "
                    f"{format_counts(floor)} counts"
                    if floor is not None else "")
        self.status.setText(
            f"{entry.name} written to {os.path.basename(path)}: {entry.peaks} "
            f"peak(s) at or above {OWN_MIN_RELATIVE:.0%} of the base peak"
            f"{measured}.")
        return entry
