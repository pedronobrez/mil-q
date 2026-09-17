"""
The spectrum on screen written into a library of one's own.

A deuterated internal standard infused on purpose is in nobody's public
library, and the only spectrum of it that will ever exist is the one on
screen. This asks for the few things a record needs that the file cannot
supply — what the compound is called, which adduct was isolated, its
formula — and prefills everything the acquisition already knows: the
precursor from the active channel, the collision energy from the channel
information where the instrument recorded one, and a comment naming the
sample, the channel and the scans the average was taken over.

Nothing is written until Add is pressed, and the values are read back
through `values()` so the flow can be exercised without a modal loop.
"""

from __future__ import annotations

from PyQt6 import QtWidgets

from ..chemistry import ADDUCTS, NEUTRAL
from .help_window import describe

HELP_PAGE = "spectral-library"

#: offered in the combo, most likely first for the polarity that was run
ADDUCT_NAMES = [a.name for a in ADDUCTS if a.name != NEUTRAL]


class AddToLibraryDialog(QtWidgets.QDialog):
    """Name a spectrum and write it into the library of one's own."""

    def __init__(self, prefill: dict | None = None, peaks: int = 0,
                 target: str = "", parent=None):
        super().__init__(parent)
        prefill = dict(prefill or {})
        self.setWindowTitle("Add spectrum to library")
        describe(self, HELP_PAGE)
        self.resize(560, 260)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            f"The centroided spectrum on screen — {peaks:,} peak(s) above one "
            f"per cent of the base peak — is appended to "
            f"{target or 'a file you choose'} as one MSP record. Everything "
            f"below is written into it; the name is what the search will show.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit(str(prefill.get("name", "")))
        self.name_edit.setPlaceholderText("cholic acid-d4")
        form.addRow("Name", self.name_edit)

        self.precursor_edit = QtWidgets.QLineEdit(
            "" if prefill.get("precursor") is None else f"{prefill['precursor']:g}")
        self.precursor_edit.setPlaceholderText("from the active channel")
        self.precursor_edit.setToolTip(
            "The isolated precursor. Written as the record's PrecursorMZ, "
            "which is what a later search filters on")
        form.addRow("Precursor m/z", self.precursor_edit)

        self.adduct = QtWidgets.QComboBox()
        self.adduct.setEditable(True)          # any adduct may be typed
        self.adduct.addItems([""] + ADDUCT_NAMES)
        wanted = str(prefill.get("precursor_type", ""))
        if wanted and wanted not in ADDUCT_NAMES:
            self.adduct.addItem(wanted)
        self.adduct.setCurrentText(wanted)
        form.addRow("Adduct", self.adduct)

        self.formula_edit = QtWidgets.QLineEdit(str(prefill.get("formula", "")))
        self.formula_edit.setPlaceholderText("C24H36D4O5, if it is known")
        form.addRow("Formula", self.formula_edit)

        energy = prefill.get("collision_energy")
        self.energy_edit = QtWidgets.QLineEdit("" if energy is None else f"{energy:g}")
        self.energy_edit.setPlaceholderText("from the channel, where it records one")
        form.addRow("Collision energy", self.energy_edit)

        self.acquired_edit = QtWidgets.QLineEdit(str(prefill.get("acquired", "")))
        self.acquired_edit.setReadOnly(True)
        self.acquired_edit.setPlaceholderText("the file records no acquisition time")
        self.acquired_edit.setToolTip(
            "When the instrument measured this, as the file records it — not "
            "when the record was made. Written as the record's Acquired "
            "field, which is what orders a standard's history. Read from the "
            "file, so it is not typed here")
        form.addRow("Acquired", self.acquired_edit)

        self.purity_edit = QtWidgets.QLineEdit(
            str(prefill.get("isotopic_purity", "")))
        self.purity_edit.setReadOnly(True)
        self.purity_edit.setPlaceholderText(
            "not measured — explain the spectrum with a labelled formula first")
        self.purity_edit.setToolTip(
            "The isotopic purity measured from this very spectrum, as the "
            "Explain tab last read it. Written as the record's "
            "Isotopic_purity field, so a record of a labelled standard says "
            "what the material was rather than only what it fragments to. "
            "Measured, so it is not typed here")
        form.addRow("Isotopic purity", self.purity_edit)

        self.comment_edit = QtWidgets.QLineEdit(str(prefill.get("comment", "")))
        self.comment_edit.setToolTip(
            "Where the record came from: the file, the sample, the scans "
            "averaged and the date. Kept as the record's Comment field")
        form.addRow("Comment", self.comment_edit)
        layout.addLayout(form)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Add")
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.name_edit.textChanged.connect(self._check)
        self._check()

    def _check(self) -> None:
        # a record with no name cannot be found again, and `parse_msp` opens
        # a record on `Name:` — one without it is not read back at all
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(
                bool(self.name_edit.text().strip()))

    @staticmethod
    def _number(text: str) -> float | None:
        text = text.strip().replace(",", ".")
        try:
            return float(text) if text else None
        except ValueError:
            return None

    def values(self) -> dict:
        """What was typed, as `LibraryPanel.add_to_own_library` takes it."""
        return {
            "name": self.name_edit.text().strip(),
            "precursor": self._number(self.precursor_edit.text()),
            "precursor_type": self.adduct.currentText().strip(),
            "formula": self.formula_edit.text().strip(),
            "collision_energy": self._number(self.energy_edit.text()),
            "comment": self.comment_edit.text().strip(),
            "acquired": self.acquired_edit.text().strip(),
            "isotopic_purity": self.purity_edit.text().strip(),
        }


def default_adduct(polarity: str) -> str:
    """The adduct a run of that polarity most likely isolated."""
    return "[M-H]-" if str(polarity).lower().startswith("neg") else "[M+H]+"
