"""
A bottle becomes a standard: the whole path in one dialog.

Entering a new internal standard was four places and a notebook. The vial was
infused; the Explorer averaged it; the Infusions tab measured it; *Use in
method…* wrote the component; *Add spectrum to library…* wrote the record; and
the lot number — the one fact about a standard that no acquisition holds — was
written on the tube and nowhere else. Every one of those steps exists and
works. What did not exist was the path: nothing carried a name typed once
through all of them, and nothing said afterwards that the component in the
method, the record in the library and the day's entry in the history are the
same vial.

*File ▸ New standard…* is that path. It asks for what only a person knows —
the name, the bottle, the infusion file, and which adducts the compound is
expected to give — reads everything else off the acquisition, shows what it
would write, and on **Create** writes exactly two things:

* the **component**, through `standards.plan_for`: the formula it was
  explained with, the adduct read off the channel's own written precursor,
  the *exact* mass of that adduct as the precursor, the base peak as the
  fragment, no retention time, and the provenance in words — with the lot
  in it;
* the **record**, through `library.records_from_summary`: the averaged,
  centroided spectrum with the formula, the adduct, the provenance and the
  lot in its comment.

and nothing else. **The history is the library read back** — that is what
`standard_history.py` is — so it needs no write of its own: the record just
appended *is* this standard's newest entry, and the audit line says how many
the file now holds of it.

Nothing here re-implements anything. `infusion_report.report_for` measures the
preview, `infusion_report.explain_as` explains it, `standards` writes the
component and `library` writes the record. What this module owns is the order
of the questions and the refusals: a file that is not an infusion, a name that
resolves to no formula, and a precursor that fits no adduct of it — each of
which disables **Create** and says why, in that place, rather than writing a
component with an invented mass.
"""

from __future__ import annotations

import os

from PyQt6 import QtWidgets

from .. import audit, chemistry, standards
from ..infusion import strongest_channel, verdict_for
from ..infusion_report import (SCORE_PEAKS, SCORE_SHARE, InfusionRow,
                               average_spectrum, compound_of, explain_as,
                               report_for)
from ..library import provenance_keys, records_from_summary, write_msp
from ..session import Session
from ..standard_history import activation_in
from .help_window import describe, open_manual
from .settings import settings

HELP_PAGE = "new-standard"

#: the same setting the Explorer's library panel and the Infusions tab use.
#: There is one library of one's own and all three mean the same file.
SETTING_OWN_PATH = "library/own_path"

#: how many of the strongest peaks the preview lists under the base peak
PREVIEW_PEAKS = 5


class NewStandardDialog(QtWidgets.QDialog):
    """One infused vial into the method, the library and the history."""

    def __init__(self, session: Session, parent=None, path: str = "",
                 name: str = ""):
        super().__init__(parent)
        self.session = session
        self.settings = settings()
        describe(self, HELP_PAGE)
        self.setWindowTitle("New standard")
        self.resize(940, 720)

        #: the acquisition being read, and the channel the average is of
        self.entry = None
        self.channel = None
        #: the session this dialog opened the file into, and closes again.
        #: None when the file was already open in the batch on screen, which
        #: is the ordinary case from the Infusions tab: a reader opened twice
        #: is a reader held twice, and the entry there is the same entry.
        self.own_session: Session | None = None
        #: the averaged spectrum, kept so that editing the name or the
        #: formula re-identifies the compound without averaging the run
        #: again — 1.2 s against 0.02 s on a real ZenoTOF infusion
        self.averaged = None
        self.report = None
        self.explanation_note = ""
        self.plan: standards.Plan | None = None
        #: what was written, for the caller and for the suite
        self.component = None
        self.record = None
        self.refusal = ""
        #: the candidate set the adduct boxes were last ticked for, so that
        #: re-measuring does not overrule a box the analyst has just changed
        self._adduct_key: tuple = ()
        #: the analyst has typed a formula of their own, and resolving the
        #: name again must not write over it
        self._formula_typed = False
        self._measuring = False

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "Everything a new internal standard needs, from the bottle: the "
            "component in the method, the record in your own library, and "
            "with it the first point of this standard’s history. Only the "
            "name, the lot and the infusion file are yours to give — the "
            "formula comes from the name, the adduct from the channel’s own "
            "written precursor, and the mass from the two of them. Nothing "
            "is written until <b>Create</b>, and where the compound cannot "
            "be identified <b>Create</b> says why instead of writing a "
            "component with an invented mass.")
        blurb.setWordWrap(True)
        blurb.setProperty("role", "caption")
        layout.addWidget(blurb)

        layout.addLayout(self._build_form(name))
        layout.addWidget(self._build_adducts())
        layout.addWidget(self._build_preview(), 1)

        self.status = QtWidgets.QLabel("Choose an infusion file to start.")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.btn_create = self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.btn_create.setText("Create")
        self.btn_create.setEnabled(False)
        self.buttons.accepted.connect(self.create)
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        layout.addWidget(self.buttons)

        if name:
            self.name_edit.setText(name)
            self._name_changed()
        if path:
            self.set_file(path)

    # -- the questions -------------------------------------------------------- #
    def _build_form(self, name: str) -> QtWidgets.QFormLayout:
        form = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit(name)
        self.name_edit.setPlaceholderText("cholic acid-d4")
        self.name_edit.setToolTip(
            "What the compound is called. The name is resolved as you type — "
            "the bile-acid standards by the abbreviation on the bottle, then "
            "LIPID MAPS, then the lipid shorthand — and a trailing -d4 is "
            "read as four labels the name does not place")
        self.name_edit.textEdited.connect(self._name_changed)
        form.addRow("Name", self.name_edit)

        self.resolved = QtWidgets.QLabel("")
        self.resolved.setWordWrap(True)
        self.resolved.setProperty("role", "caption")
        form.addRow("", self.resolved)

        self.lot_edit = QtWidgets.QLineEdit()
        self.lot_edit.setPlaceholderText("the number on the tube")
        self.lot_edit.setToolTip(
            "The bottle. The one thing about a standard that is in no "
            "acquisition and nothing can recover later: it goes into the "
            "component’s provenance and into the record’s comment, so that "
            "two records months apart can be said to be the same material")
        self.lot_edit.textEdited.connect(self._describe)
        form.addRow("Bottle / lot", self.lot_edit)

        self.formula_edit = QtWidgets.QLineEdit()
        self.formula_edit.setPlaceholderText("filled in from the name")
        self.formula_edit.setToolTip(
            "The neutral, unlabelled formula. Filled in from the name and "
            "editable: the labels are the field below, because a formula "
            "that spells its own deuteriums out has said what it is and is "
            "left alone")
        self.formula_edit.textEdited.connect(self._formula_changed)
        form.addRow("Formula", self.formula_edit)

        self.labels_spin = QtWidgets.QSpinBox()
        self.labels_spin.setRange(0, 60)
        self.labels_spin.setToolTip(
            "Deuteriums the name declares but does not place. Every "
            "predicted fragment is offered carrying 0 to n of them and the "
            "spectrum says how many it kept")
        self.labels_spin.valueChanged.connect(self._labels_changed)
        form.addRow("Unplaced labels", self.labels_spin)

        file_row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(file_row)
        line.setContentsMargins(0, 0, 0, 0)
        self.file_edit = QtWidgets.QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText(
            "the infusion of this standard — it has to read as one")
        line.addWidget(self.file_edit, 1)
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self.choose_file)
        line.addWidget(browse)
        form.addRow("Infusion", file_row)

        self.acquisition = QtWidgets.QLabel("")
        self.acquisition.setWordWrap(True)
        self.acquisition.setProperty("role", "caption")
        form.addRow("", self.acquisition)

        self.internal_box = QtWidgets.QCheckBox(
            "Write the component as an internal standard")
        self.internal_box.setChecked(True)
        self.internal_box.toggled.connect(lambda _on: self.measure())
        form.addRow("", self.internal_box)
        return form

    def _build_adducts(self) -> QtWidgets.QWidget:
        box = QtWidgets.QGroupBox("Expected adducts")
        box.setToolTip(
            "Which ions this compound is expected to give. Ticked from the "
            "channel’s own written precursor once a file is chosen — an "
            "adduct whose mass reaches it is ticked and one that does not is "
            "offered anyway, with how far off it is. The best-fitting ticked "
            "adduct is the one the component is written as")
        grid = QtWidgets.QGridLayout(box)
        grid.setContentsMargins(8, 4, 8, 4)
        self.adduct_boxes: dict[str, QtWidgets.QCheckBox] = {}
        for index, adduct in enumerate(chemistry.ADDUCTS):
            if adduct.name == chemistry.NEUTRAL:
                continue
            tick = QtWidgets.QCheckBox(adduct.name)
            tick.toggled.connect(lambda _on: self.measure())
            self.adduct_boxes[adduct.name] = tick
            grid.addWidget(tick, index // 2, index % 2)
        self.adduct_note = QtWidgets.QLabel(
            "Choose an infusion file: the adducts are ticked from its "
            "written precursor.")
        self.adduct_note.setWordWrap(True)
        self.adduct_note.setProperty("role", "caption")
        grid.addWidget(self.adduct_note, len(self.adduct_boxes) // 2 + 1, 0,
                       1, 2)
        return box

    def _build_preview(self) -> QtWidgets.QWidget:
        box = QtWidgets.QGroupBox("What was measured, and what would be written")
        inner = QtWidgets.QVBoxLayout(box)
        inner.setContentsMargins(8, 4, 8, 4)
        self.preview = QtWidgets.QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setToolTip(
            "Read off the acquisition, not typed: the adduct with the "
            "sentence that identified it, the averaged spectrum’s strongest "
            "peaks, how much of it the formula accounts for, and the "
            "isotopic purity where the envelope could be solved")
        inner.addWidget(self.preview)
        return box

    # -- the name ------------------------------------------------------------- #
    @property
    def name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def lot(self) -> str:
        return self.lot_edit.text().strip()

    @property
    def formula(self) -> str:
        return self.formula_edit.text().strip()

    @property
    def labels(self) -> int:
        return int(self.labels_spin.value())

    def _name_changed(self) -> None:
        """
        The name resolved as it is typed: the formula, the labels, the record.

        `explain.resolve_name` is the same call the LIPID MAPS tab makes, so
        a name that works there works here. What it gives is written into the
        formula box only while the analyst has not typed one of their own —
        a resolution is a proposal and a typed formula is a decision.
        """
        from ..explain import resolve_name

        written = self.name
        named = resolve_name(written) if written else None
        if named is None:
            self.resolved.setText(
                "" if not written else
                f"“{written}” is not a name the standards table, LIPID MAPS "
                f"or the lipid shorthand knows — type the formula below.")
        else:
            said = [f"{named.formula} from {named.source}"]
            if named.labels:
                said.append(f"{named.labels} unplaced label(s) read off the "
                            f"name")
            record = getattr(named, "record", None)
            if record is not None and getattr(record, "lm_id", ""):
                said.append(f"LIPID MAPS {record.lm_id}")
            self.resolved.setText(" · ".join(said))
            if not self._formula_typed:
                self.formula_edit.setText(named.formula)
            with _blocked(self.labels_spin):
                self.labels_spin.setValue(int(named.labels or 0))
        self._rebuild_adducts()
        self.measure()

    def _formula_changed(self) -> None:
        self._formula_typed = bool(self.formula)
        self._rebuild_adducts()
        self.measure()

    def _labels_changed(self) -> None:
        self._rebuild_adducts()
        self.measure()

    # -- the file ------------------------------------------------------------- #
    def choose_file(self) -> str:
        start = self.settings.value("io/last_dir", os.path.expanduser("~"),
                                    type=str)
        path, _chosen = QtWidgets.QFileDialog.getOpenFileName(
            self, "The infusion of this standard", start,
            "Mass spectrometry data (*.wiff *.mzML *.mzml);;All files (*)")
        if not path:
            return ""
        self.settings.setValue("io/last_dir", os.path.dirname(path))
        self.set_file(path)
        return path

    def set_file(self, path: str) -> bool:
        """
        Take the acquisition at `path`, if any sample in it is an infusion.

        A file already open in the batch on screen is used where it is: a
        reader opened twice holds its `.wiff.scan` twice, and the entry there
        is the same entry. Anything else is opened into a session of its own,
        which this dialog closes when it closes — the way
        `infusion_batch.run` reads a folder without adding to what is open.
        """
        self._release()
        self.file_edit.setText(path)
        name = os.path.basename(path)
        for entry in getattr(self.session, "entries", []) or []:
            if os.path.abspath(str(getattr(entry, "path", ""))) == \
                    os.path.abspath(path):
                return self.use_sample(entry)
        opened = Session()
        try:
            opened.open_file(path)
        except Exception as exc:                # a reader that will not open
            opened.close_all()
            return self._refuse(f"{name} could not be opened — "
                                f"{type(exc).__name__}: {exc}")
        self.own_session = opened
        reasons = []
        for entry in opened.entries:
            verdict = verdict_for(getattr(entry, "sample", None))
            if verdict:
                return self.use_sample(entry)
            reasons.append(f"{entry.name}: {verdict.reason}")
        return self._refuse(
            f"{name} holds no sample that reads as a direct infusion. "
            + "; ".join(reasons)
            + ". A standard is entered from its infusion, because everything "
              "here is the average of a whole run — which is a lie about a "
              "chromatographic sample.")

    def use_sample(self, entry, channel=None) -> bool:
        """
        Use one open sample as the infusion, if it reads as one.

        The check is `infusion.is_infusion` and it is made here rather than
        by the caller, so that every way into this dialog — the file picker,
        the Infusions tab, the suite — refuses the same samples for the same
        stated reason.
        """
        verdict = verdict_for(getattr(entry, "sample", None))
        if not verdict:
            return self._refuse(
                f"{getattr(entry, 'name', 'that sample')} is not a direct "
                f"infusion: {verdict.reason}.")
        channel = channel if channel is not None else strongest_channel(
            getattr(entry, "sample", None))
        if channel is None:
            return self._refuse(
                f"{getattr(entry, 'name', 'that sample')} has no channel to "
                f"average.")
        self.entry, self.channel = entry, channel
        if not self.file_edit.text():
            self.file_edit.setText(str(getattr(entry, "path", "")))
        averaged = average_spectrum(channel, sample=getattr(entry, "sample",
                                                            None))
        self.averaged = None if averaged is None else (averaged[0],
                                                       averaged[1])
        info = getattr(channel, "info", None)
        energy = getattr(info, "collision_energy", None)
        said = [str(getattr(entry, "name", ""))]
        if info is not None:
            said.append(str(getattr(info, "label", "")))
        if energy is not None:
            said.append(f"CE {float(energy):g} eV")
        activation = activation_in(str(getattr(info, "label", "") or ""),
                                   str(getattr(entry, "name", "") or ""))
        if activation:
            said.append(activation)
        said.append(verdict.reason)
        self.acquisition.setText(" · ".join(p for p in said if p))
        if not self.name:
            self.name_edit.setText(compound_of(getattr(entry, "name", "")))
            self._name_changed()
            return bool(self.report is not None)
        self._rebuild_adducts()
        self.measure()
        return True

    def _release(self) -> None:
        """
        Close whatever this dialog opened, and forget the acquisition.

        The report is *not* dropped: it holds arrays and not a reader, and
        what was measured is still worth reading after the file it was
        measured from has been let go — which is what happens the moment
        **Create** is pressed.
        """
        if self.own_session is not None:
            self.own_session.close_all()
            self.own_session = None
        self.entry = self.channel = self.averaged = None
        self.refusal = ""

    def _refuse(self, why: str) -> bool:
        self.refusal = why
        self.report = self.plan = None
        self.preview.setHtml("")
        self.btn_create.setEnabled(False)
        self.status.setText(why)
        return False

    # -- the adducts ---------------------------------------------------------- #
    @property
    def written_precursor(self) -> float | None:
        info = getattr(self.channel, "info", None)
        precursor = getattr(info, "precursor", None)
        return float(precursor) if precursor else None

    @property
    def polarity(self) -> str:
        info = getattr(self.channel, "info", None)
        return str(getattr(info, "polarity", "") or "")

    @property
    def labelled_formula(self) -> str:
        """The formula with the declared labels folded into it."""
        return standards.formula_with_labels(self.formula, self.labels)[0]

    def _rebuild_adducts(self) -> None:
        """
        Offer the polarity's adducts, ticked where the mass reaches the
        channel.

        `chemistry.adducts_matching` returns the whole list and says which
        are `within` — a miss is as informative as a hit, since a precursor
        that is none of them means the formula is wrong — so every adduct of
        the polarity is shown with how far off it is, and the ones that fit
        are ticked. A tick the analyst has changed by hand is left alone:
        the boxes are re-ticked only when the candidate set itself changes.
        """
        formula, written = self.labelled_formula, self.written_precursor
        polarity = self.polarity or None
        sign = None
        if polarity:
            try:
                sign = chemistry.polarity_sign(polarity)
            except Exception:                   # a polarity nobody wrote
                sign = None
        matches = {}
        if formula and written:
            matches = {m.name: m for m in chemistry.adducts_matching(
                formula, written, polarity)}
        key = (formula, written, sign)
        fresh = key != self._adduct_key
        self._adduct_key = key
        for name, tick in self.adduct_boxes.items():
            adduct = chemistry.ADDUCTS_BY_NAME[name]
            tick.setVisible(sign is None or adduct.polarity == sign)
            match = matches.get(name)
            if match is None:
                tick.setText(name)
                tick.setToolTip("")
                continue
            tick.setText(f"{name} · {match.mz:.4f} · {match.error_da:+.4f} Da "
                         f"({match.error_ppm:+.1f} ppm)")
            tick.setToolTip(
                f"{name} of {formula} weighs {match.mz:.4f}; the channel is "
                f"written {written:g}"
                + ("" if match.within else " — outside the window an adduct "
                                           "is read within"))
            if fresh:
                with _blocked(tick):
                    tick.setChecked(bool(match.within))
        if not matches:
            self.adduct_note.setText(
                "Choose an infusion file and give a formula: the adducts are "
                "ticked from the channel’s written precursor.")
        else:
            fitted = [m.name for m in matches.values() if m.within]
            self.adduct_note.setText(
                f"{len(fitted)} of {len(matches)} adduct(s) of {formula} "
                f"reach the written {written:g}"
                + (f": {', '.join(fitted)}." if fitted else
                   " — none of them, which usually means the formula, the "
                   "labels or the file is not this compound."))

    @property
    def expected(self) -> list[str]:
        """
        The adducts ticked, in the order they are offered.

        `isHidden` rather than `isVisible`: a box on a dialog that has not
        been shown is not visible, so asking about visibility would make the
        whole dialog answer "nothing is expected" whenever it is driven
        without a screen.
        """
        return [name for name, tick in self.adduct_boxes.items()
                if not tick.isHidden() and tick.isChecked()]

    def _declared(self) -> str:
        """
        The ticked adduct the component is written as: the one that fits the
        channel best.

        Empty where nothing is ticked, and then the adduct is read off the
        written precursor alone, which is what `standards.identify` does with
        a report that declares none. A tick that fits nothing is not silently
        dropped: it goes over as declared, and where another adduct does
        reach the written precursor that one is taken instead and the basis
        line says which tick it passed over — the channel is a measurement
        and a tick is an expectation. Where none of them reaches it, nothing
        is identified and nothing is written.
        """
        expected = self.expected
        if not expected:
            return ""
        formula, written = self.labelled_formula, self.written_precursor
        if not formula or not written:
            return expected[0]
        ranked = [m for m in chemistry.adducts_matching(
            formula, written, self.polarity or None) if m.name in expected]
        return ranked[0].name if ranked else expected[0]

    # -- the measurement ------------------------------------------------------ #
    def measure(self) -> None:
        """
        Identify the compound in the chosen infusion, and say what would be
        written.

        Cheap on purpose, so that it can run on every keystroke: the run is
        averaged once when the file is chosen and handed to `report_for`
        thereafter — 1.2 s against 0.02 s on a real ZenoTOF infusion of
        266,432 points. Everything after the average is arithmetic on it.
        """
        if self._measuring:
            return
        if self.entry is None or self.channel is None or self.averaged is None:
            self._describe()
            return
        self._measuring = True
        try:
            method = getattr(self.session, "method", None)
            self.report = report_for(
                self.entry, self.channel,
                compound=self.name or compound_of(
                    getattr(self.entry, "name", "")),
                formula=self.formula, deuterium=self.labels,
                adduct=self._declared(), spectrum=self.averaged,
                components=getattr(method, "components", ()) or (),
                own_library=self._own_library())
            explanation, basis, note = explain_as(
                self.report, self.name, self.formula,
                adduct=self.report.adduct, deuterium=self.labels)
            self.report.explanation = explanation
            self.report.basis = basis
            self.explanation_note = note
            self.plan = standards.plan_for(
                self.report, method,
                as_internal_standard=self.internal_box.isChecked(),
                fragment=standards.BASE_PEAK,
                acquired=self._acquired(), lot=self.lot)
        finally:
            self._measuring = False
        self._describe()

    def _own_library(self):
        """The analyst's own library, where one is set and exists."""
        from ..library import load_library

        path = self.settings.value(SETTING_OWN_PATH, "", type=str)
        if not path or not os.path.exists(path):
            return None
        try:
            return load_library(path)
        except (OSError, ValueError):
            return None

    def _acquired(self) -> str:
        """When the instrument measured, as the file records it."""
        sample = getattr(self.entry, "sample", None)
        try:
            return str(getattr(sample, "acquisition_time", "") or "")
        except Exception:                       # a reader that cannot say
            return ""

    # -- what it says --------------------------------------------------------- #
    def _describe(self) -> None:
        if self.report is None or self.plan is None:
            if not self.refusal:
                self.status.setText(
                    "Choose an infusion file to start."
                    if self.entry is None else
                    "Give the compound a name and a formula.")
            self.btn_create.setEnabled(False)
            return
        self.preview.setHtml(self.preview_html())
        # the compound was identified — which is what **Create** needs, and
        # not that the method has an empty cell to fill. A second infusion of
        # a standard already in the table writes no component and is still a
        # record, and a record is a history entry: refusing it because the
        # method is complete would refuse the day's verification
        offered = self.plan.proposed is not None and bool(self.name)
        self.btn_create.setEnabled(offered)
        where = os.path.basename(self.library_path or "your own library")
        if offered and self.plan.offered:
            self.status.setText(
                f"Ready: {self.plan.into}, and one record in {where}.")
        elif offered:
            self.status.setText(
                f"Ready: {self.plan.into} — the record in {where}, and with "
                f"it this standard’s newest history entry, are still "
                f"written.")
        elif not self.name:
            self.status.setText("Give the compound a name.")
        else:
            self.status.setText(self.plan.refusal or self.plan.note)

    def preview_html(self) -> str:
        """What was measured, in the order a reader wants it."""
        report, plan = self.report, self.plan
        if report is None or plan is None:
            return ""
        rows: list[tuple[str, str]] = []
        identification = plan.identification
        rows.append(("Adduct", _escape(
            (f"{identification.adduct} — {identification.adduct_source}"
             if identification.adduct else "none fits the written precursor")
            + (f". {report.adduct_note}" if report.adduct_note else ""))))
        rows.append(("Precursor", _escape(
            identification.note or identification.refusal)))
        choices = standards.fragment_choices(report, most=PREVIEW_PEAKS)
        if choices:
            base = next((c for c in choices if c.base), choices[0])
            rows.append(("Base peak", _escape(base.text)))
            rest = [c.text for c in choices if c is not base]
            if rest:
                rows.append((f"Next {len(rest)}",
                             "<br>".join(_escape(t) for t in rest)))
        else:
            rows.append(("Base peak", "the averaged spectrum has no peak"))
        explanation = report.explanation
        if explanation is not None:
            rows.append(("Explained", _escape(
                f"{explanation.matched} of {explanation.predicted} predicted "
                f"ion(s), {explanation.share * 100:.1f}% of the intensity — "
                f"{report.basis}")))
        else:
            rows.append(("Explained", _escape(
                self.explanation_note or "nothing was explained")))
        if report.purity is not None:
            # `line()` names itself, so the row is labelled `Purity`: a cell
            # reading "Isotopic purity: Isotopic purity: …" is what naming it
            # twice looks like
            rows.append(("Purity", _escape(report.purity.line())))
        isolation = report.isolation
        if isolation is not None and isolation.disagrees:
            rows.append(("Isolated", _escape(isolation.sentence())))
        if plan.proposed is None:
            rows.append(("Nothing is written", _escape(
                f"{plan.refusal} — so no component, no record and no history "
                f"entry. A component with an invented mass is worse than no "
                f"component.")))
        else:
            rows.append(("Component", _escape(
                f"{plan.into} — {plan.audit_after}")))
            rows.append(("Record", _escape(self._record_line())))
            rows.append(("History", _escape(
                "the library read back: this record becomes this standard’s "
                "newest entry, so nothing else is written")))
        if plan.note and plan.note != identification.note:
            rows.append(("Note", _escape(plan.note)))
        body = "".join(
            f"<tr><td><b>{label}</b></td><td>{value}</td></tr>"
            for label, value in rows)
        return f"<table cellpadding='3' width='100%'>{body}</table>"

    def _record_line(self) -> str:
        path = self.library_path
        where = os.path.basename(path) if path else "a library of your own"
        said = f"{self.name} into {where}"
        if self.lot:
            said += f", lot {self.lot} in its comment"
        if self.report is not None and self.report.scans:
            said += f" — the average of {self.report.scans:,} scans"
        return said

    # -- writing it ----------------------------------------------------------- #
    @property
    def library_path(self) -> str:
        return self.settings.value(SETTING_OWN_PATH, "", type=str)

    def _ask_for_library(self) -> str:
        """
        The MSP the record goes into, asked for once and remembered.

        The same setting the Explorer's library panel and the Infusions tab
        write: there is one library of one's own and all three mean the same
        file. A save dialog, since it usually does not exist yet, with the
        overwrite warning off — picking the library that is already there is
        the ordinary case and the record is appended, not written over.
        """
        path = self.library_path
        if path:
            return path
        path, _chosen = QtWidgets.QFileDialog.getSaveFileName(
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

    def row(self) -> InfusionRow:
        """
        This infusion as the row the library writer already takes.

        `library.records_from_summary` writes a whole batch of these and it
        is the only writer of a record of one's own that carries a
        provenance; a dialog of one should not become a second one.
        """
        peaks = []
        if self.report is not None and self.report.spectrum is not None \
                and self.report.trace is not None:
            peaks = self.report.spectrum.peaks(
                self.report.trace, most=SCORE_PEAKS, min_relative=SCORE_SHARE)
        return InfusionRow(report=self.report, peaks=peaks)

    def create(self, path: str = "") -> bool:
        """
        Write the record and the component, and record the one entry.

        Returns whether anything was written. Two things and not one, and
        either of them may be all there is:

        * the **record** is written whenever the compound was identified,
          including for a compound the method already carries in full. A
          second infusion of a standard is a second verification of it, and a
          verification is a history entry — refusing to file it because the
          component table has no empty cell left would throw the day's
          measurement away;
        * the **component** is written where there is something to write:
          a new row, or the empty cells of one already there.

        The audit entry comes after both, so a trail never claims a record
        that was not written, and it names all three — the component, the
        record, and how many records of this standard the file now holds,
        which is its history. Nothing writes a history: it *is* the file.
        """
        if self.plan is None or self.plan.proposed is None:
            self.status.setText(
                self.refusal
                or (self.plan.refusal if self.plan is not None else "")
                or "There is nothing to write.")
            return False
        path = path or self._ask_for_library()
        if not path:
            self.status.setText(
                "Choose a file for your own library first: a standard "
                "entered without a record has no history to have.")
            return False
        made = records_from_summary(
            [self.row()], existing=provenance_keys(path),
            identify=lambda _row: (self.plan.identification.formula,
                                   self.plan.identification.adduct),
            acquired={os.path.basename(str(self.report.file or "")):
                      self._acquired()},
            lot=self.lot)
        written = 0
        if made.entries:
            try:
                written = write_msp(made.entries, path, append=True)
            except OSError as exc:
                self.status.setText(f"Could not write the record: {exc}")
                return False
            self.record = made.entries[0]
        component = self.plan.apply(self.session.method)
        self.component = component
        if component is None and not written:
            # the component was complete and the record was already in the
            # file: this acquisition has been entered before, and saying so
            # is better than an audit entry for nothing
            self.status.setText(
                f"Nothing was written: {self.plan.into}, and "
                f"{made.line(written).lower()}")
            return False
        held = self._records_of(path, self.name)
        self.session.record(
            audit.NEW_STANDARD, target=self.name,
            before=self.plan.audit_before,
            after=" · ".join((
                self.plan.audit_after or "component unchanged",
                f"{written} record(s) in {os.path.basename(path)}",
                f"history {held} record(s)")),
            note=self.plan.audit_note or made.line(written))
        if component is not None:
            self.session.notify_method_changed()
        self.status.setText(
            f"{self.name}: {self.plan.into}, {made.line(written)} The "
            f"history of this standard now holds {held} record(s).")
        self.accept()
        return True

    @staticmethod
    def _records_of(path: str, name: str) -> int:
        """
        How many records of this standard the library now holds.

        Read from the file rather than counted here: the history is the file,
        and a library of one's own is appended to from more than one window.
        """
        from ..library import load_library

        wanted = " ".join(str(name or "").split()).lower()
        try:
            entries = load_library(path).entries
        except (OSError, ValueError):
            return 0
        return sum(1 for entry in entries
                   if " ".join(str(entry.name).split()).lower() == wanted)

    # -- the reader this dialog opened --------------------------------------- #
    def done(self, code: int) -> None:
        self._release()
        super().done(code)


class _blocked:
    """A widget's signals held while something is written into it."""

    def __init__(self, widget):
        self.widget = widget

    def __enter__(self):
        self.was = self.widget.blockSignals(True)
        return self.widget

    def __exit__(self, *exc):
        self.widget.blockSignals(self.was)
        return False


def _escape(text) -> str:
    """Text into one cell of the preview, apostrophes left as apostrophes."""
    from html import escape

    return escape(str(text or ""), quote=False).replace("\n", "<br>")
