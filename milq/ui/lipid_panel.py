"""Candidate lipids for a measured mass, from the local LIPID MAPS index."""

from __future__ import annotations

import os

import numpy as np
from PyQt6 import QtCore, QtWidgets

from .. import lipidmaps
from ..chemistry import ADDUCTS, NEUTRAL
from ..explain import (isotope_column, rank_candidates,
                       significant_peaks)
from ..matching import PRECURSOR_MATCH_DA
from ..structure import predict
from .structure_view import StructureView

ROLE_RECORD = QtCore.Qt.ItemDataRole.UserRole
ROLE_MZ = QtCore.Qt.ItemDataRole.UserRole + 1
ROLE_ADDUCT = QtCore.Qt.ItemDataRole.UserRole + 2
ROLE_ION = QtCore.Qt.ItemDataRole.UserRole + 3
ROLE_EXPLANATION = QtCore.Qt.ItemDataRole.UserRole + 4

#: the adduct combo's first entry: work it out from the written precursor
AUTO_ADDUCT = "from the precursor"

#: the mass search's first entry: every adduct the channel's polarity allows,
#: each candidate saying which one found it
EVERY_ADDUCT = "every adduct"


class LipidPanel(QtWidgets.QWidget):
    """
    Looks a mass up in LMSD and lists what it could be.

    Species first, structures underneath: a mass search cannot separate isomers,
    and eleven DiHOMEs listed as eleven answers would imply a precision the
    measurement does not have.
    """

    sigAnnotate = QtCore.pyqtSignal(str, str, str)   # name, formula, lm_id
    #: name, formula, lm_id, adduct, m/z — a lipid resolved to a channel
    sigPrecursor = QtCore.pyqtSignal(str, str, str, str, float)
    #: name, lm_id, description, m/z — a predicted fragment sent onward
    sigFragment = QtCore.pyqtSignal(str, str, str, float)
    #: (m/z, label) pairs the spectrum should mark as accounted for
    sigMatches = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        #: what the last explanation was predicted from, in words. A report
        #: prints it under the fragment table, because "12 of 34 ions found"
        #: says nothing until the reader knows what offered the 34.
        self.explanation_basis = ""
        #: the adduct that explanation was actually run as, which is not
        #: always the one in the box above it: the own-structure path reads
        #: it off the written precursor, and a report that printed the box
        #: instead would name an ion nothing was scored against
        self.explanation_adduct = ""
        #: what the selected explanation is worth against its nearest
        #: impostors — `margin.cross_validate`, or None where nothing has
        #: been explained or nothing could be contrasted with it. Measured
        #: on the peaks the explanation was scored on, so the report and the
        #: basis line under the table cannot disagree about it.
        self.explanation_margin = None
        #: True while the ranked table is being filled. Filling it selects
        #: the first row, which is a selection change like any other and
        #: would measure the margin a second time for the same candidate —
        #: half a second, twice, for one answer.
        self._filling = False
        #: the survey scan of the same acquisition over the same range, as
        #: `(mz, intensity)`, or None where the sample has no full-scan
        #: channel. What turns the adduct from arithmetic on a typed number
        #: into a measurement — see `chemistry.adduct_evidence`.
        self._survey = None
        #: `chemistry.AdductEvidence` per candidate from the last automatic
        #: adduct, for a report to print
        self.adduct_evidence: list = []
        #: what was done to the mass axis of the peaks on screen, in the
        #: Explorer's words, or empty for the instrument's own numbers. Part
        #: of the basis, since a 5 ppm tolerance against an axis moved by
        #: five is not the same test as one against the axis as measured.
        self._recalibration = ""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.modes = QtWidgets.QTabWidget()
        self.modes.setDocumentMode(True)
        layout.addWidget(self.modes)

        by_mass = QtWidgets.QWidget()
        mass_layout = QtWidgets.QVBoxLayout(by_mass)
        mass_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(by_mass, "Mass → lipid")

        form = QtWidgets.QFormLayout()
        self.mz_edit = QtWidgets.QLineEdit()
        self.mz_edit.setPlaceholderText("313.2384")
        form.addRow("Measured m/z:", self.mz_edit)

        self.adduct_combo = QtWidgets.QComboBox()
        self.adduct_combo.addItem(EVERY_ADDUCT)
        self.adduct_combo.addItems([a.name for a in ADDUCTS])
        self.adduct_combo.setCurrentText(EVERY_ADDUCT)
        self.adduct_combo.setToolTip(
            "Which ion the measured mass is — which is the question, so the "
            "box starts on “every adduct”: the search is then run at each of "
            "them the channel's polarity allows and every row says which "
            "found it and what that adduct does when the ion breaks up. A "
            "triacylglycerol is not a lipid at all as [M+H]+, and a search "
            "fixed to one adduct can only come back empty")
        form.addRow("Adduct:", self.adduct_combo)

        tolerance = QtWidgets.QHBoxLayout()
        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setDecimals(3)
        self.tol_spin.setRange(0.001, 1000.0)
        self.tol_spin.setValue(10.0)
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["ppm", "Da"])
        tolerance.addWidget(self.tol_spin)
        tolerance.addWidget(self.unit_combo)
        form.addRow("Tolerance (±):", tolerance)
        mass_layout.addLayout(form)

        self.btn_search = QtWidgets.QPushButton("Search LIPID MAPS")
        self.btn_search.setProperty("primary", True)
        mass_layout.addWidget(self.btn_search)

        by_name = QtWidgets.QWidget()
        name_layout = QtWidgets.QVBoxLayout(by_name)
        name_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(by_name, "Lipid → mass")

        name_form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("SM(d18:1/16:0), Cer(d18:1/16:0), LMSP03010003")
        self.name_edit.setToolTip(
            "The LIPID MAPS name, its shorthand or its LM_ID. A method's own "
            "label — C16:0-Ceramide — is not one of these; search the shorthand.")
        name_form.addRow("Lipid:", self.name_edit)
        name_layout.addLayout(name_form)

        self.btn_lookup = QtWidgets.QPushButton("Find the precursor")
        self.btn_lookup.setProperty("primary", True)
        name_layout.addWidget(self.btn_lookup)

        self.name_tree = QtWidgets.QTreeWidget()
        self.name_tree.setHeaderLabels(["Lipid", "Formula", "Neutral", "LM_ID"])
        self.name_tree.setColumnWidth(0, 200)
        self.name_tree.setColumnWidth(1, 110)
        self.name_tree.setAlternatingRowColors(True)
        self.name_tree.setToolTip("Pick the lipid; its ions are listed below")
        name_layout.addWidget(self.name_tree, 1)

        self.ion_tree = QtWidgets.QTreeWidget()
        self.ion_tree.setHeaderLabels(["Adduct", "m/z", "z"])
        self.ion_tree.setColumnWidth(0, 130)
        self.ion_tree.setAlternatingRowColors(True)
        self.ion_tree.setToolTip(
            "Double-click an ion to use its m/z as the precursor")
        name_layout.addWidget(self.ion_tree, 1)

        by_fragment = QtWidgets.QWidget()
        frag_layout = QtWidgets.QVBoxLayout(by_fragment)
        frag_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(by_fragment, "Fragments")

        frag_form = QtWidgets.QFormLayout()
        self.frag_name = QtWidgets.QLineEdit()
        self.frag_name.setPlaceholderText("Cer(d18:1/16:0), Cholic acid…")
        frag_form.addRow("Lipid:", self.frag_name)

        limits = QtWidgets.QHBoxLayout()
        self.frag_polarity = QtWidgets.QComboBox()
        self.frag_polarity.addItems(["positive", "negative"])
        limits.addWidget(self.frag_polarity)
        self.frag_cuts = QtWidgets.QSpinBox()
        self.frag_cuts.setRange(1, 2)
        self.frag_cuts.setValue(1)
        self.frag_cuts.setPrefix("cuts ≤ ")
        self.frag_cuts.setToolTip(
            "Two are needed to open a ring, or to free a piece held at both "
            "ends — and produce a great many more candidates")
        limits.addWidget(self.frag_cuts)
        self.frag_losses = QtWidgets.QSpinBox()
        self.frag_losses.setRange(0, 2)
        self.frag_losses.setValue(1)
        self.frag_losses.setPrefix("losses ≤ ")
        self.frag_losses.setToolTip(
            "Small neutrals shed after the bond breaks — water, ammonia, CO, "
            "CO2, formic acid")
        limits.addWidget(self.frag_losses)
        frag_form.addRow("Limits:", limits)

        window = QtWidgets.QHBoxLayout()
        self.frag_target = QtWidgets.QLineEdit()
        self.frag_target.setPlaceholderText("264.2686")
        self.frag_target.setToolTip(
            "Show only ions near this mass — for checking whether a fragment "
            "you already use can be accounted for")
        window.addWidget(self.frag_target, 1)
        self.frag_tolerance = QtWidgets.QDoubleSpinBox()
        self.frag_tolerance.setRange(0.001, 5.0)
        self.frag_tolerance.setDecimals(3)
        self.frag_tolerance.setValue(0.01)
        self.frag_tolerance.setPrefix("± ")
        self.frag_tolerance.setSuffix(" Da")
        window.addWidget(self.frag_tolerance)
        frag_form.addRow("Near m/z:", window)
        frag_layout.addLayout(frag_form)

        self.btn_fragments = QtWidgets.QPushButton("Predict fragments")
        self.btn_fragments.setProperty("primary", True)
        frag_layout.addWidget(self.btn_fragments)

        self.frag_tree = QtWidgets.QTreeWidget()
        self.frag_tree.setHeaderLabels(["m/z", "Piece", "Route", "Cuts", "Rivals"])
        self.frag_tree.setColumnWidth(0, 90)
        self.frag_tree.setColumnWidth(1, 120)
        self.frag_tree.setAlternatingRowColors(True)
        self.frag_tree.setToolTip(
            "Double-click to send the m/z on; the drawing below shows where "
            "the molecule would break")
        frag_layout.addWidget(self.frag_tree, 3)

        self.structure_view = StructureView()
        frag_layout.addWidget(self.structure_view, 2)

        self.frag_note = QtWidgets.QLabel(
            "A loss is only offered where the piece carries the group it needs "
            "— water from an alcohol, CO2 from a carboxyl. The mass is exact; "
            "the route is still the simplest one that reaches it, and where "
            "another route reaches the same mass the Rivals column says so. "
            "Confirm against a measured product spectrum.")
        self.frag_note.setWordWrap(True)
        self.frag_note.setProperty("role", "warning")
        frag_layout.addWidget(self.frag_note)

        explain_tab = QtWidgets.QWidget()
        explain_layout = QtWidgets.QVBoxLayout(explain_tab)
        explain_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(explain_tab, "Explain")

        self.explain_header = QtWidgets.QLabel(
            "Take the spectrum on screen, look its precursor up in LIPID MAPS, "
            "and score each candidate by how much of the spectrum its "
            "structure accounts for.")
        self.explain_header.setWordWrap(True)
        self.explain_header.setProperty("role", "hint")
        explain_layout.addWidget(self.explain_header)

        self.btn_explain_any = QtWidgets.QPushButton("Explain")
        self.btn_explain_any.setProperty("primary", True)
        self.btn_explain_any.setToolTip(
            "Try every route at once — the compound's name, LIPID MAPS at "
            "this precursor, the formula, and a drawing if one is loaded — "
            "and show the one that explains the most, with the others listed "
            "under it. The precursor, the polarity and the survey come from "
            "the channel; the name and the formula from the component whose "
            "precursor this channel isolates, unless something is typed below")
        explain_layout.addWidget(self.btn_explain_any)

        explain_form = QtWidgets.QFormLayout()
        self.explain_precursor = QtWidgets.QLineEdit()
        self.explain_precursor.setPlaceholderText("703.5749")
        explain_form.addRow("Precursor:", self.explain_precursor)
        self.explain_adduct = QtWidgets.QComboBox()
        self.explain_adduct.addItem(AUTO_ADDUCT)
        self.explain_adduct.addItems([a.name for a in ADDUCTS if a.name != NEUTRAL])
        self.explain_adduct.setCurrentText(AUTO_ADDUCT)
        self.explain_adduct.setToolTip(
            "How the precursor was ionised. Left on automatic every adduct "
            "the channel's polarity allows is searched, and each candidate "
            "says which one found it and how far the written precursor sits "
            "from it — a triacylglycerol acquired at 876.80 is the ammonium "
            "adduct, and asking the database for [M+H]+ there answers nothing "
            "at all")
        explain_form.addRow("Adduct:", self.explain_adduct)
        explain_layout.addLayout(explain_form)

        self.btn_explain = QtWidgets.QPushButton("Explain this spectrum")
        self.btn_explain.setProperty("primary", True)
        explain_layout.addWidget(self.btn_explain)

        own = QtWidgets.QGroupBox("Or a structure or formula of your own")
        own.setToolTip(
            "For a compound the database does not hold — a labelled internal "
            "standard, a bile acid, anything drawn or written down. A "
            "structure gives cleavages and losses; a formula gives the "
            "precursor and its losses only")
        own_layout = QtWidgets.QFormLayout(own)
        own_layout.setContentsMargins(8, 4, 8, 6)
        structure_row = QtWidgets.QHBoxLayout()
        self.btn_own_structure = QtWidgets.QPushButton("Load .mol / .sdf…")
        self.own_structure_label = QtWidgets.QLabel("none")
        self.own_structure_label.setProperty("role", "caption")
        structure_row.addWidget(self.btn_own_structure)
        structure_row.addWidget(self.own_structure_label, 1)
        own_layout.addRow("Structure:", structure_row)
        self.own_formula = QtWidgets.QLineEdit()
        self.own_formula.setPlaceholderText("C24H40O5 — used when no structure is loaded")
        own_layout.addRow("Formula:", self.own_formula)
        self.own_name = QtWidgets.QLineEdit()
        self.own_name.setPlaceholderText("Cholic acid-d4")
        self.own_name.setToolTip(
            "A name is looked up in the table of standards (bile acids and "
            "their conjugates, by name or by the abbreviation on the bottle, "
            "with a -d4 read as four unplaced labels), then in LIPID MAPS, "
            "then in the lipid shorthand. It is used only when no structure "
            "is loaded and no formula is typed")
        own_layout.addRow("Name:", self.own_name)
        self.own_adduct = QtWidgets.QComboBox()
        self.own_adduct.addItem(AUTO_ADDUCT)
        # the neutral entry is in the list above because a neutral mass can be
        # searched for; it cannot be fragmented, so it is not offered here
        self.own_adduct.addItems([a.name for a in ADDUCTS if a.name != NEUTRAL])
        self.own_adduct.setToolTip(
            "How the precursor was ionised. Left on automatic, the written "
            "precursor and the formula decide it and the line under the "
            "button says which and how far off — a channel written 430.35 "
            "is the ammonium adduct, and scoring it as [M+H]+ predicts "
            "every fragment 17 Da too high")
        own_layout.addRow("Adduct:", self.own_adduct)
        self.own_deuterium = QtWidgets.QSpinBox()
        self.own_deuterium.setRange(0, 30)
        self.own_deuterium.setToolTip(
            "Labels the drawing does not place. A fragment is then offered "
            "carrying none to all of them, and the spectrum says how many it "
            "kept. A drawing that places them (an M ISO block, or D atoms) "
            "needs 0 here")
        own_layout.addRow("Deuterium, unplaced:", self.own_deuterium)
        own_limits = QtWidgets.QHBoxLayout()
        self.own_cuts = QtWidgets.QSpinBox()
        self.own_cuts.setRange(1, 2)
        self.own_cuts.setValue(2)
        self.own_cuts.setPrefix("cuts ≤ ")
        self.own_cuts.setToolTip(
            "Two are needed to open a ring: a steroid cut once is still in "
            "one piece, so a bile acid gives nothing at one")
        own_limits.addWidget(self.own_cuts)
        self.own_losses = QtWidgets.QSpinBox()
        self.own_losses.setRange(0, 3)
        self.own_losses.setValue(3)
        self.own_losses.setPrefix("losses ≤ ")
        self.own_losses.setToolTip(
            "Three, because a trihydroxy bile acid sheds three waters and "
            "the three-water ion is its base peak")
        own_limits.addWidget(self.own_losses)
        self.own_tolerance = QtWidgets.QDoubleSpinBox()
        self.own_tolerance.setRange(0.5, 50.0)
        self.own_tolerance.setDecimals(1)
        self.own_tolerance.setValue(5.0)
        self.own_tolerance.setPrefix("± ")
        self.own_tolerance.setSuffix(" ppm")
        self.own_tolerance.setToolTip(
            "Tighter than the 20 ppm a database candidate is scored at, "
            "because a label is only 1.55 mDa from the hydrogen it replaced: "
            "a window wider than that holds both and the number of labels a "
            "piece kept cannot be read off it")
        own_limits.addWidget(self.own_tolerance)
        own_limits.addStretch(1)
        own_layout.addRow("Limits:", own_limits)
        self.btn_explain_own = QtWidgets.QPushButton("Explain with this")
        own_layout.addRow(self.btn_explain_own)
        explain_layout.addWidget(own)
        self._own_molecule = None
        self._label_inputs = None
        self._inference = None
        self._polarity = ""
        #: the precursor the ranked database candidates were found at, or
        #: None when the table is holding a structure of one's own — which
        #: writes its own basis line and must not have it written over
        self._record_context = None
        #: how the candidates in the ranked table were enumerated, so the
        #: basis line says what was actually run rather than the default
        self._record_limits = (1, 2)
        #: the route the ranked table is showing, prefixed onto the basis
        #: line so that selecting another candidate does not lose it
        self._route_basis = ""
        #: the last `explain_any.AnyExplanation`, and the component table the
        #: unified button fills itself from
        self._any = None
        self._components = []
        self._spectrum = None
        #: the last `purity.Purity`, for a report or a library record to read
        self.purity = None

        self.explain_tree = QtWidgets.QTreeWidget()
        self.explain_tree.setHeaderLabels(["Candidate", "Explains", "Peaks",
                                           "Formula", "Adduct", "ppm",
                                           "Isotopes"])
        self.explain_tree.setColumnWidth(0, 190)
        self.explain_tree.setAlternatingRowColors(True)
        self.explain_tree.setToolTip(
            "Select a candidate to mark the peaks it accounts for on the "
            "spectrum. Adduct is the ion the precursor was taken to be — the "
            "row says what that adduct does when it breaks up, and ppm is how "
            "far the written precursor sits from that candidate through it. "
            "Isotopes is what each matched fragment's own M+1 said — hover "
            "the cell for the sentence")
        explain_layout.addWidget(self.explain_tree, 2)

        self.route_tree = QtWidgets.QTreeWidget()
        self.route_tree.setHeaderLabels(["Route", "Adduct", "Explains",
                                         "Ions", "ppm"])
        self.route_tree.setColumnWidth(0, 110)
        self.route_tree.setAlternatingRowColors(True)
        self.route_tree.setMaximumHeight(120)
        self.route_tree.setToolTip(
            "What each route made of this spectrum. Click one to put its "
            "answer in the table above. Ions is how many of the ions that "
            "route predicted were found, of how many it offered — read it "
            "beside the share: a route that offers four thousand masses "
            "covers a spectrum by accident, and one that offers fifty and "
            "explains most of it has said something.")
        self.route_tree.setVisible(False)
        explain_layout.addWidget(self.route_tree)

        self.match_tree = QtWidgets.QTreeWidget()
        self.match_tree.setHeaderLabels(["Measured", "ppm", "Route", "Ladder"])
        self.match_tree.setColumnWidth(0, 95)
        self.match_tree.setToolTip(
            "Ladder: how much of a route's own intermediate ions this spectrum "
            "shows. Where two routes reach the same mass, that is what tells "
            "them apart.")
        self.match_tree.setAlternatingRowColors(True)
        explain_layout.addWidget(self.match_tree, 2)

        self.labels_box = QtWidgets.QGroupBox("Where the labels are")
        labels_layout = QtWidgets.QVBoxLayout(self.labels_box)
        labels_layout.setContentsMargins(8, 4, 8, 6)
        self.labels_text = QtWidgets.QLabel("")
        self.labels_text.setWordWrap(True)
        self.labels_text.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        labels_layout.addWidget(self.labels_text)
        self.labels_hetero = QtWidgets.QCheckBox(
            "Include O- and N-bound positions")
        self.labels_hetero.setToolTip(
            "Off by default: an O–D or an N–D exchanges with the solvent long "
            "before the spectrum is recorded, so a label drawn there is not "
            "one that survives to be measured. Tick it to see what the "
            "spectrum would say if it did.")
        labels_layout.addWidget(self.labels_hetero)
        self.labels_note = QtWidgets.QLabel(
            "A fragment says how many labels it kept, which is a statement "
            "about which ones only when the pieces are certain. Labels also "
            "move: a hydrogen that migrates as the bond breaks can be a "
            "label, and an exchangeable one is gone before the spectrum "
            "exists. Read a tie as the spectrum bounding the labels, not "
            "placing them — on a real infusion of a standard whose vendor "
            "places them, this did not recover the placement.")
        self.labels_note.setWordWrap(True)
        self.labels_note.setProperty("role", "warning")
        labels_layout.addWidget(self.labels_note)
        self.labels_box.setVisible(False)
        explain_layout.addWidget(self.labels_box)

        self.purity_text = QtWidgets.QLabel("")
        self.purity_text.setWordWrap(True)
        self.purity_text.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.purity_text.setToolTip(
            "The isotopic purity of the labelled standard, solved from the "
            "envelope at the identified ion — the number on the certificate "
            "that nobody measures. It needs the natural-abundance satellites "
            "of the fully-labelled ion to be in the spectrum, so a "
            "product-ion scan whose precursor the quadrupole isolated cannot "
            "be asked and says so")
        self.purity_text.setVisible(False)
        explain_layout.addWidget(self.purity_text)

        self.explain_note = QtWidgets.QLabel(
            "A share is evidence, not proof. Isomers fragment alike, and a long "
            "enough list of possible masses covers a spectrum by accident — so "
            "read the peaks a candidate leaves unexplained as carefully as the "
            "ones it claims.")
        self.explain_note.setWordWrap(True)
        self.explain_note.setProperty("role", "warning")
        explain_layout.addWidget(self.explain_note)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Species / structure", "Formula", "mDa",
                                   "ppm", "n", "Adduct"])
        self.tree.setColumnWidth(0, 210)
        self.tree.setColumnWidth(1, 120)
        self.tree.setAlternatingRowColors(True)
        self.tree.setToolTip(
            "Double-click a structure to name the component after it. Adduct "
            "is the ion this species would have to be to weigh what was "
            "measured; hover it for what that adduct does when the ion breaks "
            "up, which is what decides the masses a product spectrum can hold")
        mass_layout.addWidget(self.tree, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "hint")
        layout.addWidget(self.status)

        self.install_box = QtWidgets.QWidget()
        install_layout = QtWidgets.QVBoxLayout(self.install_box)
        install_layout.setContentsMargins(0, 0, 0, 0)
        message = QtWidgets.QLabel(
            "The LIPID MAPS database is not installed yet. It is a one-off "
            "21 MB download that becomes a 1.3 MB local index — after that, "
            "lookups need no network.")
        message.setWordWrap(True)
        install_layout.addWidget(message)
        self.btn_install = QtWidgets.QPushButton("Download the database")
        install_layout.addWidget(self.btn_install)
        layout.addWidget(self.install_box)

        self.btn_search.clicked.connect(self.search)
        self.mz_edit.returnPressed.connect(self.search)
        self.btn_install.clicked.connect(self.install)
        self.tree.itemDoubleClicked.connect(self._activated)
        self.btn_lookup.clicked.connect(self.look_up_name)
        self.name_edit.returnPressed.connect(self.look_up_name)
        self.name_tree.currentItemChanged.connect(self._show_ions)
        self.ion_tree.itemDoubleClicked.connect(self._ion_activated)
        self.btn_fragments.clicked.connect(self.predict_fragments)
        self.frag_name.returnPressed.connect(self.predict_fragments)
        self.frag_target.returnPressed.connect(self.predict_fragments)
        self.frag_tree.currentItemChanged.connect(self._show_cleavage)
        self.frag_tree.itemDoubleClicked.connect(self._fragment_activated)
        self.btn_explain_any.clicked.connect(self.explain_anything)
        self.route_tree.currentItemChanged.connect(self._route_chosen)
        self.btn_explain.clicked.connect(self.explain_spectrum)
        self.explain_precursor.returnPressed.connect(self.explain_spectrum)
        self.btn_own_structure.clicked.connect(self._load_own_structure)
        self.btn_explain_own.clicked.connect(self.explain_own)
        self.labels_hetero.toggled.connect(self._replace_labels)
        self.explain_tree.currentItemChanged.connect(self._show_explanation)
        self.refresh_availability()

    # -- availability -------------------------------------------------------- #
    def refresh_availability(self) -> None:
        installed = lipidmaps.is_installed()
        self.install_box.setVisible(not installed)
        for widget in (self.btn_search, self.mz_edit, self.adduct_combo,
                       self.tol_spin, self.unit_combo,
                       self.btn_lookup, self.name_edit,
                       self.btn_fragments, self.frag_name,
                       self.btn_explain, self.explain_precursor):
            widget.setEnabled(installed)
        if installed:
            # the count is a question about the file, and it is read off the
            # file: opening the database here loaded fifty thousand records
            # into the window before anybody had searched for anything
            count = lipidmaps.record_count()
            self.status.setText(
                f"{count:,} curated structures indexed locally." if count
                else "Curated structures indexed locally.")

    def install(self) -> None:
        self.btn_install.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            lipidmaps.install(progress=self._report)
            lipidmaps.forget()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Could not install the database",
                f"{exc}\n\nThe download is about 21 MB from lipidmaps.org.")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.btn_install.setEnabled(True)
            self.refresh_availability()

    # -- searching ------------------------------------------------------------ #
    def set_target(self, mz: float, adduct: str | None = None) -> None:
        self.mz_edit.setText(f"{mz:.4f}")
        if adduct:
            self.adduct_combo.setCurrentText(adduct)

    def search(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        text = self.mz_edit.text().strip().replace(",", ".")
        try:
            mz = float(text)
        except ValueError:
            self._report("Type a measured m/z first.")
            return

        chosen = self.adduct_combo.currentText()
        matches = []
        for name in self._search_adducts(chosen):
            matches.extend(database.search_mz(mz, name, self.tol_spin.value(),
                                              self.unit_combo.currentText()))
        groups = lipidmaps.group_by_species(matches)
        groups.sort(key=lambda g: (abs(g.error_mda), -len(g.records)))
        self._fill(groups)
        unit = self.unit_combo.currentText()
        if groups:
            forms = list(dict.fromkeys(g.adduct for g in groups if g.adduct))
            over = (f" as {', '.join(forms)}" if len(forms) > 1 else "")
            self._report(f"{len(groups)} species, {len(matches)} structure(s) "
                         f"within ±{self.tol_spin.value():g} {unit}{over}. "
                         "A mass cannot separate isomers — confirm before "
                         "using; a product spectrum ranks them, in Explain.")
        else:
            self._report(
                f"Nothing within ±{self.tol_spin.value():g} {unit}. The curated "
                "database has no structure at that mass; a theoretical species "
                "may still exist in LIPID MAPS' computed set.")

    def _search_adducts(self, chosen: str) -> list[str]:
        """
        The adducts a mass search is run at.

        One when the analyst named it. Otherwise every adduct the channel's
        polarity allows, because which ion a measured mass is *is* the
        question — a triacylglycerol searched as [M+H]+ answers nothing, and
        nothing is not the same as "no such lipid".
        """
        from ..chemistry import adducts_of_polarity

        if chosen != EVERY_ADDUCT:
            return [chosen]
        return [a.name for a in adducts_of_polarity(self._polarity or None)]

    def _fill(self, groups) -> None:
        from ..chemistry import adduct_from_name, behaviour_text

        self.tree.clear()
        for group in groups:
            parent = QtWidgets.QTreeWidgetItem(self.tree, [
                group.species, group.formula, f"{group.error_mda:+.2f}",
                f"{group.error_ppm:+.1f}", str(len(group.records)),
                group.adduct,
            ])
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            parent.setToolTip(0, group.main_class)
            form = adduct_from_name(group.adduct)
            if form is not None:
                parent.setToolTip(5, behaviour_text(form))
            for record in group.records:
                child = QtWidgets.QTreeWidgetItem(
                    parent, [record.name or record.systematic_name,
                             record.lm_id, "", "", "", ""])
                child.setToolTip(1, record.lm_id)
                child.setData(0, ROLE_RECORD, record.lm_id)
                child.setToolTip(0, record.systematic_name or record.name)
            parent.setExpanded(len(groups) <= 3)

    def _activated(self, item, _column: int) -> None:
        lm_id = item.data(0, ROLE_RECORD)
        if not lm_id:
            item.setExpanded(not item.isExpanded())
            return
        database = lipidmaps.database()
        record = database.by_id(lm_id) if database else None
        if record is None:
            return
        self.sigAnnotate.emit(record.name or record.abbrev, record.formula,
                              record.lm_id)
        self._report(f"{record.name} ({record.lm_id}) sent to the component.")

    # -- the other direction: a lipid, and where it would be seen ------------- #
    def set_name(self, name: str) -> None:
        """Put a name in the box and look it up, from elsewhere in the app."""
        self.name_edit.setText(name)
        self.modes.setCurrentIndex(1)
        self.look_up_name()

    def look_up_name(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        text = self.name_edit.text().strip()
        if not text:
            self._report("Type a lipid name, its shorthand or its LM_ID.")
            return

        records = database.find_by_name(text, limit=40)
        self.name_tree.clear()
        self.ion_tree.clear()
        for record in records:
            item = QtWidgets.QTreeWidgetItem(
                self.name_tree,
                [record.name or record.abbrev, record.formula,
                 f"{record.exact_mass:.4f}", record.lm_id])
            item.setData(0, ROLE_RECORD, record.lm_id)
            item.setToolTip(0, record.systematic_name or record.name)
            item.setToolTip(2, f"{record.exact_mass:.6f} Da, monoisotopic")
            item.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight
                                  | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if records:
            self.name_tree.setCurrentItem(self.name_tree.topLevelItem(0))
            self._report(f"{len(records)} match(es). The ions below are exact "
                         "arithmetic on the formula, not rounded values.")
        else:
            self._report(
                f"Nothing named like {text!r}. LIPID MAPS uses its own "
                "shorthand — Cer(d18:1/16:0) rather than C16:0-Ceramide.")

    def _show_ions(self, item, _previous=None) -> None:
        self.ion_tree.clear()
        lm_id = item.data(0, ROLE_RECORD) if item is not None else None
        database = lipidmaps.database()
        record = database.by_id(lm_id) if (database and lm_id) else None
        if record is None:
            return
        for form in lipidmaps.ion_forms(record):
            row = QtWidgets.QTreeWidgetItem(
                self.ion_tree,
                [form.adduct, f"{form.mz:.4f}", f"{form.charge:+d}"])
            row.setData(0, ROLE_MZ, form.mz)
            row.setData(0, ROLE_ADDUCT, form.adduct)
            row.setData(0, ROLE_RECORD, record.lm_id)
            row.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            row.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            if form.adduct == "[M+H]+":
                font = row.font(0)
                font.setBold(True)
                for column in range(3):
                    row.setFont(column, font)

    def _ion_activated(self, item, _column: int) -> None:
        mz = item.data(0, ROLE_MZ)
        database = lipidmaps.database()
        record = database.by_id(item.data(0, ROLE_RECORD)) if database else None
        if mz is None or record is None:
            return
        adduct = item.data(0, ROLE_ADDUCT)
        self.sigPrecursor.emit(record.name or record.abbrev, record.formula,
                               record.lm_id, adduct, float(mz))
        self._report(f"{record.name} {adduct} — {mz:.4f} sent to the component.")

    # -- fragments ------------------------------------------------------------ #
    def set_fragment_target(self, name: str, mz: float | None = None) -> None:
        """Ask about a lipid from elsewhere in the app."""
        self.frag_name.setText(name)
        if mz is not None:
            self.frag_target.setText(f"{mz:.4f}")
        self.modes.setCurrentIndex(2)
        self.predict_fragments()

    def predict_fragments(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        text = self.frag_name.text().strip()
        if not text:
            self._report("Type a lipid name, its shorthand or its LM_ID.")
            return
        found = database.find_by_name(text, limit=1)
        if not found:
            self._report(f"Nothing named like {text!r}.")
            return

        record = found[0]
        molecule = record.molecule()
        self.frag_tree.clear()
        self.structure_view.set_structure(molecule)
        if molecule is None:
            self._report(
                f"{record.name} has no structure in the index. Reinstall the "
                "database to add the connection tables.")
            return

        charge = 1 if self.frag_polarity.currentIndex() == 0 else -1
        cuts, losses = self.frag_cuts.value(), self.frag_losses.value()
        ions = self._near_target(predict(molecule, charge=charge,
                                         max_cuts=cuts, max_losses=losses))
        wider = ""
        if not ions and self.frag_target.text().strip():
            # a mass the analyst already uses turning up empty is worth more
            # than silence: say what it would take to reach it
            needed = self._reachable_at(molecule, charge, cuts, losses)
            wider = (f" It is reachable with {needed}." if needed else
                     " No combination of one or two cuts and two losses "
                     "reaches it.")

        for ion in ions:
            row = QtWidgets.QTreeWidgetItem(self.frag_tree, [
                f"{ion.mz:.4f}", ion.formula,
                ion.description.split(" ", 1)[1] if " " in ion.description
                else "as drawn",
                str(ion.fragment.cut_count),
                str(len(ion.alternatives)) if ion.alternatives else "",
            ])
            row.setData(0, ROLE_ION, ion)
            if ion.alternatives:
                # two routes to one mass is a question for the spectrum, and
                # showing only the winner hides that there was a question
                row.setToolTip(2, "Also reachable as:\n  "
                               + "\n  ".join(ion.alternatives))
                row.setToolTip(4, f"{len(ion.alternatives)} other route(s) "
                                  "reach this mass")
            row.setTextAlignment(0, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            for column in (3, 4):
                row.setTextAlignment(column,
                                     QtCore.Qt.AlignmentFlag.AlignRight
                                     | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if ions:
            self.frag_tree.setCurrentItem(self.frag_tree.topLevelItem(0))

        if wider:
            self._report(f"{record.name}: nothing within the current limits."
                         + wider)
            return
        warning = "" if molecule.reliable else (
            " Its hydrogen count does not match the published formula, so "
            "these masses are not to be trusted.")
        self._report(f"{record.name}: {len(ions)} ion(s) from "
                     f"{len(molecule.atoms)} atoms." + warning)

    def _reachable_at(self, molecule, charge: int, cuts: int,
                      losses: int) -> str:
        """The smallest limits that would reach the mass being asked about."""
        for more_cuts in range(cuts, 3):
            for more_losses in range(losses, 3):
                if (more_cuts, more_losses) == (cuts, losses):
                    continue
                if self._near_target(predict(molecule, charge=charge,
                                             max_cuts=more_cuts,
                                             max_losses=more_losses)):
                    return f"cuts ≤ {more_cuts} and losses ≤ {more_losses}"
        return ""

    def _near_target(self, ions: list) -> list:
        """Narrow to a mass being checked, when one was given."""
        text = self.frag_target.text().strip().replace(",", ".")
        if not text:
            return ions
        try:
            target = float(text)
        except ValueError:
            return ions
        half = self.frag_tolerance.value()
        return [i for i in ions if abs(i.mz - target) <= half]

    def _show_cleavage(self, item, _previous=None) -> None:
        ion = item.data(0, ROLE_ION) if item is not None else None
        self.structure_view.set_fragment(ion.fragment if ion else None)

    def _fragment_activated(self, item, _column: int) -> None:
        ion = item.data(0, ROLE_ION)
        if ion is None:
            return
        name = self.frag_name.text().strip()
        database = lipidmaps.database()
        found = database.find_by_name(name, limit=1) if database else []
        lm_id = found[0].lm_id if found else ""
        self.sigFragment.emit(found[0].name if found else name, lm_id,
                              ion.description, float(ion.mz))
        self._report(f"{ion.mz:.4f} ({ion.description}) sent on. The route is "
                     "the simplest arithmetic, not a mechanism.")

    # -- explaining a measured spectrum --------------------------------------- #
    def set_spectrum(self, mz, intensity, precursor: float | None = None,
                     polarity: str = "", survey=None,
                     recalibration: str = "") -> None:
        """
        Hand the panel the spectrum on screen, ready to be explained.

        The precursor is written with the digits the method carried and no
        more: `430.35` says the number is known to ±0.005, and printing it
        as `430.3500` invents two decimals the instrument was never given —
        which then decides how tight an adduct has to fit. The polarity is
        a fact about the acquisition, not a choice, and is what stops a
        negative adduct being offered for a positive channel.

        `survey` is the same acquisition's full-scan channel averaged over
        the same range, as `(mz, intensity)`, or None where the method has no
        survey. With it the adduct stops being a deduction from the written
        precursor and becomes a measurement: the exact mass of the ion and
        its isotope pattern, both of which the product-ion scan cannot show,
        since Q1 threw away everything but the one mass.
        `recalibration` is what was done to the mass axis of these peaks, in
        the caller's own words, or empty for the instrument's own numbers.
        """
        self._peaks = significant_peaks(mz, intensity)
        # the profile arrays as well as the peaks above 1%: an isotopic
        # envelope's rungs are tenths of a per cent of the base peak and
        # `significant_peaks` has already thrown every one of them away
        self._spectrum = (np.asarray(mz, dtype=float),
                          np.asarray(intensity, dtype=float))
        self._polarity = str(polarity or "")
        self._survey = survey
        self.adduct_evidence = []
        self._recalibration = str(recalibration or "")
        # a purity belongs to the spectrum it was solved from: leaving the
        # last one standing would write another sample's material into this
        # one's library record
        self.purity = None
        self.purity_text.setVisible(False)
        self.purity_text.setText("")
        if precursor:
            self.explain_precursor.setText(f"{precursor:g}")
        self.modes.setCurrentIndex(3)
        self.explain_header.setText(
            f"{len(self._peaks)} peak(s) above 1% of the base peak are on "
            "screen. Give the precursor and score the candidates against them.")

    @property
    def adduct_provenance(self) -> str:
        """
        Where the adduct came from, in one clause, for a record's comment.

        A record of one's own states an adduct, and a reader a year later
        cannot tell whether it was measured or assumed. This is the
        difference, written into the comment: the survey confirmed it, the
        survey did not, or the acquisition had no survey and the adduct is
        the written precursor read as one. Empty before a spectrum has been
        handed over, since then nothing has been claimed at all.
        """
        if getattr(self, "_peaks", None) is None:
            return ""
        # present at the right mass is not the same as confirmed: an ion
        # whose satellites are not its own is something else on the mass
        best = next((e for e in self.adduct_evidence
                     if e.present and (e.pattern is None or e.agrees)), None)
        if best is not None:
            if self.explanation_adduct in ("", best.name):
                return (f"adduct {best.name} confirmed by the survey "
                        f"({best.confirmation})")
            return (f"adduct {self.explanation_adduct} chosen, though the "
                    f"survey supports {best.name}")
        if self.adduct_evidence:
            return "adduct not confirmed by the survey"
        if self._survey is None:
            return ("no survey scan: the adduct is read from the written "
                    "precursor alone")
        return ""

    def set_components(self, components) -> None:
        """
        The method's component table, for the unified **Explain** button.

        A panel that has been handed a spectrum knows the precursor, the
        polarity and the survey; what it does not know is what the compound
        is called or what it is made of, and the component table is where a
        method writes both. Kept as a list rather than reached for through
        the session, because this panel has never held one and a widget that
        can be built alone stays testable alone.
        """
        self._components = list(components or [])

    def component_for_channel(self):
        """
        The component this channel isolates, or None.

        Nearest written precursor inside `matching.PRECURSOR_MATCH_DA`, which
        is the window the quadrupole passed: a method writing `430.35` and a
        component written `430.3465` are the same channel. Nothing is guessed
        beyond that — a component half a dalton away is a different compound
        and naming the spectrum after it would be inventing the answer.
        """
        text = self.explain_precursor.text().strip().replace(",", ".")
        try:
            precursor = float(text)
        except ValueError:
            return None
        near = [(abs(float(getattr(c, "precursor", 0.0) or 0.0) - precursor), c)
                for c in self._components
                if getattr(c, "precursor", 0.0)]
        near = [(gap, c) for gap, c in near if gap <= PRECURSOR_MATCH_DA]
        near.sort(key=lambda pair: pair[0])
        return near[0][1] if near else None

    def explain_anything(self) -> None:
        """
        Every route at once, and the best of them in the ranked table.

        The inputs are taken from wherever they exist: the precursor, the
        polarity and the survey from the channel the spectrum came off, the
        name and the formula from the component whose precursor this channel
        isolates — unless the boxes below hold something, since an analyst
        who typed a name meant it — and the drawing from whatever was loaded.
        A route with nothing to work from is listed as skipped with the
        reason, not silently left out.
        """
        from ..explain_any import explain_any

        peaks = getattr(self, "_spectrum", None)
        if peaks is None or not getattr(self, "_peaks", None):
            self._report("Show a spectrum first — Process ▸ Explain spectrum "
                         "takes the one on screen.")
            return
        text = self.explain_precursor.text().strip().replace(",", ".")
        try:
            precursor = float(text)
        except ValueError:
            precursor = None
        component = self.component_for_channel()
        name = (self.own_name.text().strip()
                or str(getattr(component, "name", "") or ""))
        formula = (self.own_formula.text().strip()
                   or str(getattr(component, "formula", "") or ""))
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        try:
            # at `explain_any`'s own tolerance, not the box below it. The
            # box defaults to 5 ppm because a deuterium is 1.55 mDa from the
            # hydrogen it replaced and a wider window cannot say how many
            # labels a piece kept — a question about *placing* labels, not
            # about which route explains the spectrum. Measured on the four
            # real bile-acid infusions, whose axes sit 4–7 ppm high: at
            # 20 ppm the route naming the right compound wins 3 of 4, at
            # 5 ppm 1 of 4, because tightening drops the true compound's
            # ions while a four-thousand-ion candidate still covers by
            # accident. The label inference below still gets the box.
            answer = explain_any(
                peaks[0], peaks[1], precursor, self._polarity,
                name=name, formula=formula, molecule=self._own_molecule,
                deuterium=self.own_deuterium.value(), survey=self._survey)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._any = answer
        # what the survey said, so `adduct_provenance` can tell a record
        # whose adduct was confirmed from one that was read off two decimals
        self.adduct_evidence = list(answer.evidence)
        self._fill_routes(answer)
        if answer.best is None:
            self._explain_nothing("; ".join(f"{s.route} — {s.why}"
                                            for s in answer.skipped))
            self.route_tree.setVisible(bool(answer.results))
            return
        from_table = (f" Name and formula from {component.name}."
                      if component is not None and (
                          not self.own_name.text().strip()
                          and not self.own_formula.text().strip()) else "")
        self._report(answer.summary + from_table)

    def _fill_routes(self, answer) -> None:
        """
        The route table: what every route made of the spectrum, best first.

        A skipped route is a row too, greyed and unselectable, because "the
        database is not installed" and "the database had nothing at this
        mass" are different answers and a route that is simply missing from
        the table says neither.
        """
        self.route_tree.blockSignals(True)
        self.route_tree.clear()
        for result in answer.results:
            row = QtWidgets.QTreeWidgetItem(self.route_tree, [
                result.route, result.adduct,
                f"{result.share * 100:.1f}%", result.ions,
                "" if result.precursor_ppm is None
                else f"{result.precursor_ppm:+.1f}",
            ])
            row.setData(0, ROLE_EXPLANATION, result)
            row.setToolTip(0, result.source or result.basis)
            row.setToolTip(1, result.reason or result.explanation.behaviour)
            for column in (2, 3, 4):
                row.setTextAlignment(column,
                                     QtCore.Qt.AlignmentFlag.AlignRight
                                     | QtCore.Qt.AlignmentFlag.AlignVCenter)
        for skip in answer.skipped:
            row = QtWidgets.QTreeWidgetItem(self.route_tree,
                                            [skip.route, "—", "—", "—", ""])
            row.setToolTip(0, skip.why)
            row.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.route_tree.blockSignals(False)
        self.route_tree.setVisible(True)
        if answer.results:
            self.route_tree.setCurrentItem(self.route_tree.topLevelItem(0))

    def _route_chosen(self, item, _previous=None) -> None:
        result = item.data(0, ROLE_EXPLANATION) if item is not None else None
        if result is None:
            return
        self._show_route(result)
        self._report(f"{result.name}: {result.share * 100:.1f}% of the "
                     f"spectrum {result.basis}; {result.ions} predicted "
                     f"ion(s) matched, "
                     f"{len(result.explanation.unexplained(self._peaks))} "
                     f"peak(s) not.")

    def _show_route(self, result) -> None:
        """
        One route's answer in the ranked table, with the line that names it.

        The database route hands over its whole ranked list, so selecting
        another candidate still works and still rewrites the adduct sentence
        — with the route kept in front of it, since what is on screen is
        still an answer that route produced.
        """
        from ..explain_any import MAX_CUTS, MAX_LOSSES, ROUTE_DATABASE

        self._route_basis = result.basis
        self._record_limits = (MAX_CUTS, MAX_LOSSES)
        self._record_context = (self._any.precursor
                                if result.route == ROUTE_DATABASE
                                and self._any is not None else None)
        self.explanation_basis = self._with_axis(
            f"{result.basis}; {result.reason}" if result.reason
            else result.basis)
        self.explanation_adduct = result.adduct
        self._show_ranked(list(result.ranked), None, result.adduct)
        # a label inference needs the drawing the labels would sit on, which
        # only the analyst's own molfile is; a database record's drawing is
        # not the labelled compound
        peaks = getattr(self, "_peaks", None) or []
        self._place_labels(result.explanation, peaks,
                           self.own_deuterium.value())

    def explain_spectrum(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        peaks = getattr(self, "_peaks", None)
        if not peaks:
            self._report("Show a spectrum first — Process ▸ Explain spectrum "
                         "takes the one on screen.")
            return
        text = self.explain_precursor.text().strip().replace(",", ".")
        try:
            precursor = float(text)
        except ValueError:
            self._report("Type the precursor m/z of this spectrum.")
            return

        chosen = self.explain_adduct.currentText()
        auto = chosen == AUTO_ADDUCT
        # the quadrupole passed a window, not a mass, and the method's own
        # figure is rounded besides — 538.6 for a ceramide whose precursor is
        # 538.52. Anything the isolation let through is a candidate.
        ranked = rank_candidates(database, precursor, peaks,
                                 adduct=None if auto else chosen,
                                 tolerance=PRECURSOR_MATCH_DA, unit="Da",
                                 polarity=self._polarity or None)
        # the basis follows the selection, because on this path each candidate
        # may have been found at a different adduct and a report that printed
        # the box would name an ion nothing was scored against
        self._record_context = precursor
        self._record_limits = (1, 2)
        self._route_basis = ""
        self.explanation_basis = ""
        self.explanation_adduct = ""
        self.route_tree.setVisible(False)
        self.explanation_margin = None
        self._show_ranked(ranked, precursor, EVERY_ADDUCT if auto else chosen)

    def _load_own_structure(self) -> None:
        from ..explain import read_molfile

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load a structure", "", "Structures (*.mol *.sdf *.mdl);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                molecule, name = read_molfile(handle.read())
        except OSError as exc:
            self._report(f"Could not read the file: {exc}")
            return
        if molecule is None:
            self._report("That file is not a V2000 molblock this can read; "
                         "save it as MDL molfile V2000 (PubChem's download is).")
            self.own_structure_label.setText("none")
            self._own_molecule = None
            return
        self._own_molecule = molecule
        self.own_structure_label.setText(f"{molecule.formula} from {os.path.basename(path)}")
        if name and not self.own_name.text():
            self.own_name.setText(name)
        if not self.own_formula.text():
            self.own_formula.setText(molecule.formula)

    def _own_subject(self):
        """
        What the analyst gave to explain with: a drawing, a formula, a name.

        In that order, because that is the order of how much each says. A
        name is resolved through `explain.resolve_name` — the standards
        table, then LIPID MAPS, then the lipid shorthand — and brings its
        own structure when the database holds one and its own label count
        when it is written `-d4`. Anything typed in the boxes above it wins,
        since the analyst who typed it meant it.
        """
        from ..explain import resolve_name

        molecule = self._own_molecule
        formula = self.own_formula.text().strip()
        name = self.own_name.text().strip()
        deuterium = self.own_deuterium.value()
        note = ""
        if molecule is None and not formula and name:
            resolved = resolve_name(name)
            if resolved is None:
                return None, "", name, 0, (
                    f"\u201c{name}\u201d is not in the standards table, in LIPID MAPS "
                    f"or in the lipid shorthand — load a structure or type a "
                    f"formula")
            molecule = resolved.molecule()
            formula = resolved.formula
            if not deuterium:
                deuterium = resolved.labels
            where = resolved.source
            if molecule is not None and resolved.record is not None:
                where += f", drawn as {resolved.record.lm_id}"
            labels = f" with {resolved.labels} unplaced label(s)" if resolved.labels else ""
            note = f"{name} read as {formula}{labels} from {where}"
        if molecule is None and not formula:
            return None, "", name, 0, "Load a structure, or type a formula or a name"
        if not formula and molecule is not None:
            formula = molecule.formula
        return molecule, formula, name, deuterium, note

    def _own_adduct(self, formula: str, deuterium: int):
        """
        The adduct to explain with, and the sentence that says why.

        Left on automatic it is read off the written precursor: the channel
        says 430.35, the molecule weighs 412.31, and the only adduct that
        joins the two is the ammonium. Where nothing fits, no adduct comes
        back and the sentence names the closest misses — a spectrum
        explained as the wrong ion is worse than one not explained at all.
        """
        from ..chemistry import (adduct_from_name, format_formula,
                                 identify_adduct, parse_formula)

        chosen = self.own_adduct.currentText()
        counts = dict(parse_formula(formula))
        if deuterium:
            counts["D"] = counts.get("D", 0) + deuterium
            counts["H"] = counts.get("H", 0) - deuterium
        labelled = format_formula(counts)
        if chosen != AUTO_ADDUCT:
            adduct = adduct_from_name(chosen)
            return adduct, (f"{chosen}, chosen by hand" if adduct is not None
                            else f"{chosen} is not an adduct this program knows")
        text = self.explain_precursor.text().strip().replace(",", ".")
        try:
            precursor = float(text)
        except ValueError:
            # nothing to read the adduct off. The Adduct box above is the one
            # the analyst already chose for this spectrum, so it stands in —
            # said out loud, since it was not derived from anything
            fallback = self.explain_adduct.currentText()
            if fallback == AUTO_ADDUCT:
                return None, ("no precursor is written and the Adduct box "
                              "above is on automatic, so there is nothing to "
                              "read the adduct off — type the precursor, or "
                              "choose an adduct")
            return adduct_from_name(fallback), (
                f"no precursor is written, so {fallback} was taken from the "
                f"Adduct box above")
        choice = identify_adduct(labelled, precursor, self._polarity or None,
                                 survey=self._survey)
        self.adduct_evidence = list(choice.evidence)
        return choice.adduct, choice.reason

    def explain_own(self) -> None:
        """Score a structure, formula or name the database does not hold."""
        from ..chemistry import FormulaError
        from ..explain import explain_formula, explain_structure

        peaks = getattr(self, "_peaks", None)
        if not peaks:
            self._report("Show a spectrum first — Process ▸ Explain spectrum "
                         "takes the one on screen.")
            return
        molecule, formula, name, deuterium, note = self._own_subject()
        if molecule is None and not formula:
            self._report(f"{note}.")
            return
        try:
            adduct, reason = self._own_adduct(formula, deuterium)
        except (FormulaError, ValueError):
            self._report(f"\u201c{formula}\u201d is not a formula this can read.")
            return
        if adduct is None:
            self._explain_nothing(reason)
            return
        self.own_adduct.setToolTip(reason)
        if molecule is not None:
            explanation = explain_structure(
                molecule, peaks, name=name or formula, adduct=adduct,
                deuterium=deuterium, max_cuts=self.own_cuts.value(),
                max_losses=self.own_losses.value(),
                tolerance_ppm=self.own_tolerance.value())
            basis = (f"cleavages and losses of the drawing "
                     f"({molecule.formula}) as {adduct.name}")
        else:
            explanation = explain_formula(
                formula, adduct.name, peaks, name=name, deuterium=deuterium,
                tolerance_ppm=self.own_tolerance.value())
            if not explanation.record.exact_mass:
                self._report(f"\u201c{formula}\u201d is not a formula this can read.")
                return
            basis = (f"the precursor {formula} as {adduct.name} and its neutral "
                     f"losses — a formula has no bonds to cut")
        self._record_context = None
        self._route_basis = ""
        self.route_tree.setVisible(False)
        self.explanation_basis = self._with_axis(f"{basis}; {reason}")
        self.explanation_adduct = adduct.name
        self._show_ranked([explanation], None, adduct.name)
        self._place_labels(explanation, peaks, deuterium)
        self._show_purity(molecule, formula, adduct, deuterium)
        labelled = f", {deuterium} unplaced label(s)" if deuterium else ""
        lead = f"{note}. " if note else ""
        contrast = self._measure_margin(explanation)
        margin_said = f" Margin: {contrast}." if contrast else ""
        self._report(f"{lead}{explanation.name}: {explanation.share * 100:.1f}% of "
                     f"the spectrum from {basis}{labelled}; "
                     f"{explanation.matched} of {explanation.predicted} "
                     f"predicted ion(s) matched, "
                     f"{len(explanation.unexplained(peaks))} peak(s) not."
                     f"{margin_said}")

    def _with_axis(self, basis: str) -> str:
        """
        The basis line with what was done to the mass axis on the end.

        Only where something was done. The sentence carries the raw and the
        corrected error of the rung the offset mostly rests on, because
        either alone is misleading: the corrected figure is a residual the
        fit was made to produce, and the raw one does not say the axis
        moved.
        """
        return (f"{basis} \u00b7 {self._recalibration}"
                if self._recalibration else basis)

    def _show_purity(self, molecule, formula: str, adduct,
                     deuterium: int) -> None:
        """
        The isotopic purity line, under the label inference, when there are
        labels and an ion to read them at.

        Off the profile spectrum rather than off `self._peaks`: the rungs of
        an isotopic envelope are tenths of a per cent of the base peak and
        the peak list starts at one per cent. Where the envelope cannot be
        solved the reason goes in the same place — a line that appears only
        on success is a line nobody can tell from a feature that did not run.
        """
        from ..explain import placed_labels
        from ..purity import purity_from_spectrum

        self.purity = None
        spectrum = getattr(self, "_spectrum", None)
        labels = deuterium or (len(placed_labels(molecule))
                               if molecule is not None else 0)
        if spectrum is None or labels <= 0 or adduct is None:
            self.purity_text.setVisible(False)
            self.purity_text.setText("")
            return
        # a drawing that places its labels has them in its own formula
        # already, so `deuterium` is the count to fold in and nothing else
        source = (molecule.formula if molecule is not None and not deuterium
                  else formula)
        attempt = purity_from_spectrum(spectrum[0], spectrum[1], source,
                                       adduct, deuterium)
        result = attempt.best
        if result is None:
            self.purity_text.setVisible(False)
            self.purity_text.setText("")
            return
        self.purity = result
        self.purity_text.setText(result.line())
        self.purity_text.setProperty("role",
                                     "hint" if result.usable else "warning")
        self.purity_text.style().unpolish(self.purity_text)
        self.purity_text.style().polish(self.purity_text)
        self.purity_text.setVisible(True)

    def _explain_nothing(self, reason: str) -> None:
        """
        Clear the tables and say why, rather than explain the wrong ion.

        An adduct that does not fit the written precursor is the one case
        where the right answer is nothing at all: every fragment would be
        predicted from a molecule the quadrupole did not isolate, and a
        table of confident wrong routes is harder to disbelieve than an
        empty one.
        """
        self._record_context = None
        self._route_basis = ""
        self.explain_tree.clear()
        self.match_tree.clear()
        self.sigMatches.emit([])
        self.labels_box.setVisible(False)
        self.purity_text.setVisible(False)
        self.purity = None
        self.explanation_basis = ""
        self.explanation_adduct = ""
        self.explanation_margin = None
        self._report(f"Nothing explained: {reason}.")

    def _measure_margin(self, explanation, precursor=None) -> str:
        """
        What the selected explanation is worth against its neighbours.

        Off `self._spectrum` — the arrays the peaks were taken from — rather
        than off `self._peaks`, so the rivals are scored on exactly the peak
        list the explanation was scored on and the two shares share a
        denominator. Silent about its own failures: a database that is not
        installed, or a reader that throws, leaves the margin unmeasured and
        the basis line says only what it did measure.
        """
        from .. import margin as margin_module

        self.explanation_margin = None
        spectrum = getattr(self, "_spectrum", None)
        if explanation is None or spectrum is None:
            return ""
        if precursor is None:
            precursor = getattr(self, "_record_context", None)
        if precursor is None:
            text = self.explain_precursor.text().strip().replace(",", ".")
            try:
                precursor = float(text)
            except ValueError:
                precursor = None
        try:
            result = margin_module.cross_validate(
                spectrum[0], spectrum[1], explanation, precursor,
                self._polarity or "")
        except Exception:                       # a database that will not read
            return ""
        self.explanation_margin = result
        return result.sentence()

    def current_explanation(self):
        """
        The explanation the analyst has selected, for a report to print.

        The tree is the panel's memory of what was run: the row carries its
        `Explanation`, so nothing has to be scored a second time to put it on
        paper, and a report shows the candidate that was being looked at
        rather than whichever scored best.
        """
        item = self.explain_tree.currentItem()
        return item.data(0, ROLE_EXPLANATION) if item is not None else None

    def _place_labels(self, explanation, peaks, deuterium: int) -> None:
        """
        Where the labels are, under the ranked table, when there are any.

        Only a drawing can be asked: a formula has no atoms to put them on.
        """
        from ..explain import infer_labels, placed_labels

        molecule = self._own_molecule
        self._label_inputs = (explanation, peaks, deuterium)
        if molecule is None or not (deuterium or placed_labels(molecule)):
            self.labels_box.setVisible(False)
            self.labels_text.setText("")
            return
        inference = infer_labels(explanation, molecule, deuterium=deuterium,
                                 peaks=peaks,
                                 tolerance_ppm=self.own_tolerance.value(),
                                 heteroatoms=self.labels_hetero.isChecked())
        self._inference = inference
        lines = [inference.summary()]
        for placement in inference.placements[:3]:
            lines.append("• " + placement.text())
        self.labels_text.setText("\n".join(lines))
        self.labels_box.setVisible(True)

    def _replace_labels(self) -> None:
        """Ask again with the heteroatom positions in or out."""
        if getattr(self, "_label_inputs", None) is None:
            return
        self._place_labels(*self._label_inputs)

    def _show_ranked(self, ranked, precursor, adduct) -> None:
        self.explain_tree.clear()
        self.match_tree.clear()
        self._filling = True
        try:
            self._fill_ranked(ranked, precursor, adduct)
        finally:
            self._filling = False

    def _fill_ranked(self, ranked, precursor, adduct) -> None:
        for explanation in ranked:
            found = self._isotopes_for(explanation)
            row = QtWidgets.QTreeWidgetItem(self.explain_tree, [
                explanation.name,
                f"{explanation.share * 100:.1f}%",
                str(explanation.matched),
                explanation.record.formula,
                explanation.adduct,
                "" if explanation.precursor_ppm is None
                else f"{explanation.precursor_ppm:+.1f}",
                isotope_column(found, explanation.isolation),
            ])
            row.setData(0, ROLE_EXPLANATION, explanation)
            # the count is a summary of a finding per ion, so the sentence
            # that says what the counts mean goes where it is read
            row.setToolTip(6, explanation.isotope_summary)
            # what the adduct does when the ion breaks up decides which masses
            # the spectrum can hold, so it belongs on the row rather than in
            # the reader's memory
            row.setToolTip(4, explanation.behaviour)
            row.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            row.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            row.setTextAlignment(5, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if ranked:
            self.explain_tree.setCurrentItem(self.explain_tree.topLevelItem(0))
            if precursor is None:
                return
            top = ranked[0]
            close = [e for e in ranked[1:] if top.share - e.share < 0.05]
            tie = (f" {len(close)} other(s) explain it about as well."
                   if close else "")
            forms = list(dict.fromkeys(e.adduct for e in ranked if e.adduct))
            over = (f" Found as {', '.join(forms)}." if len(forms) > 1
                    else f" Found as {forms[0]}." if forms else "")
            # the contrast for the row that is selected, which is the first:
            # `setCurrentItem` above has already run `_show_explanation` and
            # its status line is about to be written over by this one
            contrast = self._measure_margin(top, precursor)
            said = f" {top.name} {contrast}." if contrast else ""
            self._report(f"{len(ranked)} candidate(s) at that precursor."
                         + over + tie + said)
        else:
            self.sigMatches.emit([])
            where = ("as any adduct of this channel's polarity"
                     if adduct == EVERY_ADDUCT else f"as {adduct}")
            self._report(
                f"No structure in the curated database sits within "
                f"±{PRECURSOR_MATCH_DA:g} Da of {precursor:.4f} {where}. "
                "A theoretical species may still exist in the computed set.")

    def _isotopes_for(self, explanation):
        """
        What each matched ion's own satellites say, where there is a spectrum.

        Off the whole spectrum rather than off `self._peaks`, for the reason
        the purity solve is: a satellite is tenths of a per cent of the base
        peak and `significant_peaks` has already dropped it.
        """
        from ..explain import isotope_evidence

        spectrum = getattr(self, "_spectrum", None)
        if spectrum is None:
            return {}
        return isotope_evidence(explanation, spectrum[0], spectrum[1])

    def _record_basis(self, explanation) -> None:
        """
        What the selected database candidate was predicted from, in words.

        The same sentence the own-structure path prints, from the same code in
        `chemistry`: the row was found at one adduct and the reader needs to
        see how far the written precursor sits from *that* one, with the form
        its fragments carry beside it.
        """
        from ..chemistry import adduct_reason

        precursor = getattr(self, "_record_context", None)
        if precursor is None or explanation is None:
            return
        reason = adduct_reason(explanation.record.formula, precursor,
                               explanation.adduct, self._polarity or None)
        cuts, losses = self._record_limits
        basis = (f"the curated structure, {'one bond' if cuts == 1 else f'up to {cuts} bonds'} "
                 f"cut and up to {losses} neutral losses, as "
                 f"{explanation.adduct}")
        # the route stays in front of the sentence: on the unified path the
        # reader has to know which of four ways produced what is on screen,
        # and selecting another candidate must not lose it
        if self._route_basis:
            basis = f"{self._route_basis} — {basis}"
        self.explanation_basis = f"{basis}; {reason}" if reason else basis
        self.explanation_adduct = explanation.adduct

    def _show_explanation(self, item, _previous=None) -> None:
        explanation = item.data(0, ROLE_EXPLANATION) if item is not None else None
        self.match_tree.clear()
        self._record_basis(explanation)
        if explanation is None:
            self.explanation_margin = None
            self.sigMatches.emit([])
            return
        # the margin belongs to the candidate that is selected, not to the
        # one that ranked first: an analyst who picks the fourth row is
        # asking what *that* one is worth against the other three. Not while
        # the table is being filled: the row it selects is the one the
        # caller is about to measure itself.
        if not self._filling:
            contrast = self._measure_margin(explanation)
            if contrast:
                self._report(f"{explanation.name} {contrast}.")
        for match in sorted(explanation.matches, key=lambda m: -m.intensity):
            route = match.route
            support = (f"{len(route.seen)}/{len(route.companions)}"
                       if route and route.companions else "—")
            row = QtWidgets.QTreeWidgetItem(self.match_tree, [
                f"{match.mz:.4f}", f"{match.error_ppm:+.1f}",
                match.best_route, support,
            ])
            if route and route.companions:
                row.setToolTip(3, "Implies " + ", ".join(
                    f"{m:.4f}" for m in route.companions)
                    + ("\nPresent: " + ", ".join(f"{m:.4f}" for m in route.seen)
                       if route.seen else "\nNone of them are in this spectrum"))
            for column in (0, 1):
                row.setTextAlignment(column,
                                     QtCore.Qt.AlignmentFlag.AlignRight
                                     | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.sigMatches.emit(
            [(m.mz, m.ion.formula) for m in explanation.matches])

    def _report(self, text: str) -> None:
        self.status.setText(text)
