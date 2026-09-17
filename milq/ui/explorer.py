"""Explorer workspace: the qualitative review of raw samples."""

from __future__ import annotations

import csv
import os
from dataclasses import replace

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from ..chemistry import (
    ADDUCTS_BY_NAME,
    find_formulas,
    has_isotope_satellites,
    isotope_pattern,
    rank_by_isotope_pattern,
)
from ..components import Component
from .. import infusion as infusion_rules
from ..infusion import (InfusionVerdict, NoiseFloor, after_settling,
                        format_counts, noise_floor_for, run_range,
                        verdict_for)
from ..infusion_report import average_spectrum
from ..matching import match_channel
from ..precursor import survey_channel
from .settings import settings
from ..processing import (centroid_spectrum, detect_peaks, integrate,
                          signal_to_noise)
from ..samples import SampleEntry
from ..session import Session
from ..spectra_compare import SpectrumRecipe
from ..wiff import Channel
from .chrom_area import ChromatogramArea
from .component_list import ComponentListPanel
from .formula_panel import FormulaPanel
from .lipid_panel import LipidPanel
from .mass_calc_panel import MassCalcPanel
from ..contour import Contour, build_contour
from .contour_view import ContourView
from . import plots
from .plots import SpectrumView, Trace, colour
from .. import labels as label_rule
from .results_panel import Result, ResultsPanel
from .sample_info import SampleInfoPanel
from .flow_layout import FlowLayout

ROLE_REF = QtCore.Qt.ItemDataRole.UserRole

#: bumped whenever the toolbars are rearranged, so Qt throws away a layout
#: saved by a version that had them somewhere else
LAYOUT_VERSION = 2


def _first_line(error: BaseException) -> str:
    """A .NET exception is a page; the first line is the message."""
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


def _as_scan_mask(chosen, times: np.ndarray) -> np.ndarray | None:
    """
    Whatever `infusion.stable_scans` hands back, as a boolean per scan.

    The shape of that answer is not this module's to decide, and it is being
    written elsewhere while this is: a mask, a list of scan indices, or the
    kept part of the trace are all reasonable and all readable. Anything else
    is None, and the caller falls back to what it can measure itself. This
    reads a value rather than trusting one — a wrong guess about the shape
    would mark the wrong scans, which is worse than marking none.
    """
    if chosen is None:
        return None
    chosen = getattr(chosen, "mask", chosen)
    if isinstance(chosen, tuple) and len(chosen) == 2:
        # the kept times, the way `after_settling` returns them
        kept = np.asarray(chosen[0], dtype=float)
        return np.isin(times, kept) if kept.ndim == 1 else None
    values = np.asarray(chosen)
    if values.ndim != 1:
        return None
    if values.dtype == bool and values.size == times.size:
        return values
    if np.issubdtype(values.dtype, np.integer) and values.size <= times.size:
        mask = np.zeros(times.size, dtype=bool)
        inside = values[(values >= 0) & (values < times.size)]
        mask[inside] = True
        return mask
    return None


def excluded_scans(times, y) -> np.ndarray:
    """
    Which scans of an infusion are **not** in the average it is read from.

    `infusion.stable_scans` is the authority when the module has it; it is
    what actually decides the average, so a marker that read anything else
    would be drawing a different answer from the one in force. Without it the
    settling window is all there is to go on — the first second of
    acquisition, which is where the spray transient was measured to be — and
    that is what `infusion.after_settling` already leaves out of the verdict.
    """
    times = np.asarray(times, dtype=float)
    y = np.asarray(y, dtype=float)
    if times.size == 0 or times.size != y.size:
        return np.zeros(times.size, dtype=bool)
    picker = getattr(infusion_rules, "stable_scans", None)
    if picker is not None:
        try:
            mask = _as_scan_mask(picker(times, y), times)
        except Exception:
            mask = None
        if mask is not None:
            return ~mask
    kept, _ = after_settling(times, y)
    if kept.size == times.size or kept.size == 0:
        return np.zeros(times.size, dtype=bool)
    return times < float(kept[0])


class ChannelRef:
    """A tree node: either the sample TIC or one specific channel."""

    def __init__(self, entry: SampleEntry, channel: Channel | None):
        self.entry = entry
        self.channel = channel

    @property
    def sample(self):
        return self.entry.sample

    @property
    def alias(self) -> str:
        return self.entry.name

    @property
    def filename(self) -> str:
        return self.entry.filename

    @property
    def key(self) -> str:
        idx = "TIC" if self.channel is None else str(self.channel.index)
        return f"{self.entry.key}|{idx}"

    @property
    def label(self) -> str:
        if self.channel is None:
            return f"{self.alias} · TIC"
        return f"{self.alias} · {self.channel.info.short_label}"

    @property
    def full_label(self) -> str:
        base = os.path.splitext(self.filename)[0]
        if self.channel is None:
            return f"{base} · sample TIC"
        return f"{base} · {self.channel.info.label}"


VIEW_CHROMATOGRAM = "Chromatogram"
VIEW_CONTOUR = "Contour"

#: how many built surfaces to keep. Each is a grid of some ten megabytes, and
#: a file of eighty-one channels would otherwise fill memory with pictures
#: nobody is looking at any more.
CONTOUR_CACHE = 6


class _Cancelled(Exception):
    """The reader asked to stop, from inside the writer's progress callback."""


class ExplorerWorkspace(QtWidgets.QMainWindow):
    """
    Qualitative review of the raw data.

    A QMainWindow so it keeps dock widgets and toolbars while living inside a
    tab of the shell; the shell owns the real window and its menu bar.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Widget)

        self.session = session
        self.settings = settings()
        self.refs: dict[str, ChannelRef] = {}
        self.xic_defs: list[dict] = []
        self.active_ref: ChannelRef | None = None
        self.current_scan: int = 0
        self._background_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
        #: whole-run averages, by channel, for the Δ mode — reading 473 scans
        #: once a scan is what a film would cost without this
        self._average_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
        #: Mirror as it was before Δ turned it on, to put back afterwards
        self._mirror_before_delta: bool | None = None
        #: how the spectrum on screen was made — set by `_show_scan` and
        #: `_show_average`, which are the only two things that draw one, and
        #: copied onto a pin so the project can say where it came from
        self._live_recipe: SpectrumRecipe | None = None

        self.chrom = ChromatogramArea()
        self.contour_view = ContourView()
        self.spectrum = SpectrumView()
        #: built contours, by channel and by the ranges they were built over
        self._contour_cache: dict[tuple, object] = {}
        #: each dock panel and the scroller it was put in, so a panel can
        #: still be brought to the front by name
        self._tab_hosts: dict = {}

        self._build_ui()
        self._connect()
        self._restore_settings()
        self.session.sigSamplesChanged.connect(self.rebuild_tree)
        self.session.sigMethodChanged.connect(self._refresh_components)
        # the project saves what this pane is showing, and puts it back when
        # it is opened. The hook is set here rather than by the window, so
        # that every path that saves a project saves the view with it
        self.session.sigViewRestored.connect(self.restore_view)
        self.session.view_source = self.view_state
        self._update_status("Open a .wiff or .mzML file to start.")

    # ------------------------------------------------------------------ UI -- #
    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self._wrap_chromatogram())
        splitter.addWidget(self._wrap_spectrum())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self._build_tree_dock()
        self._build_side_dock()
        self._build_toolbars()

    def _wrap_chromatogram(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        bar = FlowLayout()
        bar.addWidget(QtWidgets.QLabel("View:"))
        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.addItems([VIEW_CHROMATOGRAM, VIEW_CONTOUR])
        self.view_combo.setToolTip(
            "The contour is the same data with neither axis summed away: "
            "time across, m/z up, intensity as colour")
        bar.addWidget(self.view_combo)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["TIC", "BPC"])
        self.mode_combo.setToolTip("Chromatogram type for the checked channels")
        bar.addWidget(self.mode_combo)
        bar.addSpacing(16)
        bar.addWidget(QtWidgets.QLabel("Active channel (spectra / XIC):"))
        self.active_combo = QtWidgets.QComboBox()
        # a channel is named in full — "TOF MSMS 647.5 [+], 40 eV" and longer
        # — and a minimum width is what the window has to give this box before
        # anything else gets any. It wants to be wide; it does not need to be,
        # and the difference decided how narrow the window could be made.
        self.active_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.active_combo.setMinimumContentsLength(18)
        self.active_combo.setMinimumWidth(180)
        bar.addWidget(self.active_combo, 1)
        layout.addLayout(bar)

        self.top_stack = QtWidgets.QStackedWidget()
        self.top_stack.addWidget(self.chrom)
        self.top_stack.addWidget(self.contour_view)
        layout.addWidget(self.top_stack)
        return box

    def _wrap_spectrum(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 0, 4, 4)
        layout.setSpacing(4)

        bar = FlowLayout()
        self.btn_prev = QtWidgets.QToolButton()
        self.btn_prev.setText("◀")
        self.btn_prev.setToolTip("Previous scan (left arrow)")
        self.btn_next = QtWidgets.QToolButton()
        self.btn_next.setText("▶")
        self.btn_next.setToolTip("Next scan (right arrow)")
        self.scan_spin = QtWidgets.QSpinBox()
        self.scan_spin.setMinimum(1)
        self.scan_spin.setMaximum(1)
        self.scan_spin.setToolTip("Scan number (1 is the channel's first cycle)")
        self.rt_label = QtWidgets.QLabel("—")
        self.rt_label.setMinimumWidth(170)
        #: says so when the active sample was read as a direct infusion, and
        #: carries the figures that decided it on hover
        self.infusion_label = QtWidgets.QLabel("")
        self.infusion_label.setProperty("role", "warning")

        bar.addWidget(QtWidgets.QLabel("Scan:"))
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.scan_spin)
        bar.addWidget(self.btn_next)
        bar.addWidget(self.rt_label)
        bar.addWidget(self.infusion_label)
        bar.addStretch(1)
        self.bg_label = QtWidgets.QLabel("")
        self.bg_label.setProperty("role", "warning")
        bar.addWidget(self.bg_label)
        self.btn_avg = QtWidgets.QPushButton("Average selected range")
        self.btn_avg.setToolTip(
            "Average spectrum of the scans inside the range marked on the chromatogram"
        )
        bar.addWidget(self.btn_avg)
        layout.addLayout(bar)
        layout.addWidget(self.spectrum)
        return box

    def _build_tree_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Samples and channels", self)
        dock.setObjectName("dock_tree")
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter channels (e.g. 313.2)")
        self.filter_edit.setClearButtonEnabled(True)
        layout.addWidget(self.filter_edit)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(self.tree, 1)

        buttons = FlowLayout()
        self.btn_none = QtWidgets.QPushButton("Uncheck all")
        self.btn_ms1 = QtWidgets.QPushButton("TOF MS only")
        self.btn_collapse = QtWidgets.QPushButton("Collapse all")
        self.btn_collapse.setToolTip(
            "Fold every sample shut. A TripleTOF method is eighty channels per "
            "injection, and a dozen injections buries the list.")
        buttons.addWidget(self.btn_none)
        buttons.addWidget(self.btn_ms1)
        buttons.addWidget(self.btn_collapse)
        layout.addLayout(buttons)

        dock.setWidget(panel)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
                             | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(330)
        self.dock_tree = dock
        self.act_dock_tree = self._reopen_action(
            dock, "Samples and channels", "Ctrl+Shift+S",
            "The tree of open files and their channels, on the left")

    #: the least width a dock panel is given before it starts to scroll. A
    #: panel narrower than this is unreadable rather than merely cramped.
    PANEL_WIDTH = 300

    def _scrolled(self, panel: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """
        A dock panel in a scroller, so its own height is not the window's.

        The LIPID MAPS panel asks for 712 pixels of height and the Library
        panel for 520; a dock is as tall as its tallest tab, a window is as
        tall as its dock, and the result was a window 864 pixels high on a
        screen with 913 to give. In a scroller the panel keeps the size it
        wants and the dock keeps the size the screen has.
        """
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        area.setWidget(panel)
        area.setMinimumWidth(self.PANEL_WIDTH)
        self._tab_hosts[panel] = area
        return area

    def _tab_of(self, panel: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """The scroller a panel was put in, so the tab can still be selected."""
        return self._tab_hosts.get(panel, panel)

    def showing_panel(self) -> QtWidgets.QWidget | None:
        """
        The dock panel on show, not the scroller holding it.

        Every panel sits in a `QScrollArea`, so the tab widget's current
        widget is the scroller; what anything asking this question means is
        the panel.
        """
        current = self.tabs.currentWidget()
        for panel, host in self._tab_hosts.items():
            if host is current:
                return panel
        return current

    def _build_side_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Panels", self)
        dock.setObjectName("dock_side")
        self.tabs = QtWidgets.QTabWidget()

        self.component_list = ComponentListPanel()
        self.results_panel = ResultsPanel()
        self.mass_calc = MassCalcPanel()
        self.formula_panel = FormulaPanel()
        self.lipid_panel = LipidPanel()
        self.sample_info = SampleInfoPanel()

        from .help_window import describe
        xic_tab, peaks_tab = self._build_xic_tab(), self._build_peaks_tab()
        self.tabs.addTab(self._scrolled(self.component_list), "Components")
        self.tabs.addTab(self._scrolled(self.results_panel), "Results")
        self.tabs.addTab(self._scrolled(xic_tab), "Manual XIC")
        self.tabs.addTab(self._scrolled(peaks_tab), "Spectrum peaks")
        self.tabs.addTab(self._scrolled(self.mass_calc), "Mass calc")
        self.tabs.addTab(self._scrolled(self.formula_panel), "Formula finder")
        self.tabs.addTab(self._scrolled(self.lipid_panel), "LIPID MAPS")
        from .library_panel import LibraryPanel
        self.library_panel = LibraryPanel()
        self.library_panel.spectrum_source = self._library_spectrum
        # for *Rewrite from files…*: which folders the open acquisitions came
        # from, and whether their masses are being corrected
        self.library_panel.session = self.session
        self.tabs.addTab(self._scrolled(self.library_panel), "Library")
        for widget, page in ((self.component_list, "explorer-components-and-results"),
                             (self.results_panel, "explorer-components-and-results"),
                             (xic_tab, "manual-xic"),
                             (peaks_tab, "chromatograms-and-spectra"),
                             (self.mass_calc, "mass-calculator"),
                             (self.formula_panel, "formula-finder"),
                             (self.lipid_panel, "lipid-maps"),
                             (self.sample_info, "sample-information"),
                             (self.contour_view, "contour-view"),
                             (self.chrom, "chromatograms-and-spectra"),
                             (self.infusion_label, "direct-infusion"),
                             (self.spectrum, "chromatograms-and-spectra")):
            describe(widget, page)
        # eight tabs in a narrow dock elide into unreadable stubs; scroll
        # buttons keep the full names and let the reader page through them
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.tabs.addTab(self._scrolled(self.sample_info), "Sample")

        # the eight tabs need twice the width the dock has, so five of them sit
        # behind two small arrows and are found by accident or not at all. This
        # lists every panel by name, at the tabs, where you look for them.
        self.panel_menu = QtWidgets.QMenu(self)
        self.btn_panels = QtWidgets.QToolButton()
        self.btn_panels.setText("Panels")
        self.btn_panels.setToolTip("Go to a panel by name")
        self.btn_panels.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_panels.setMenu(self.panel_menu)
        self.tabs.setCornerWidget(self.btn_panels,
                                  QtCore.Qt.Corner.TopRightCorner)
        self._build_panel_actions()

        dock.setWidget(self.tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setMinimumWidth(360)
        self.dock_side = dock
        self.act_dock_side = self._reopen_action(
            dock, "Side panels", "Ctrl+Shift+P",
            "Components, results, XIC and the rest, on the right")

    def _build_xic_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        form = QtWidgets.QFormLayout()
        self.xic_mz = QtWidgets.QLineEdit()
        self.xic_mz.setPlaceholderText("183.1391, 313.2384")
        form.addRow("m/z (comma separated):", self.xic_mz)

        tol_row = QtWidgets.QHBoxLayout()
        self.xic_tol = QtWidgets.QDoubleSpinBox()
        self.xic_tol.setDecimals(4)
        self.xic_tol.setRange(0.0001, 500.0)
        self.xic_tol.setValue(0.02)
        self.xic_unit = QtWidgets.QComboBox()
        self.xic_unit.addItems(["Da", "ppm"])
        tol_row.addWidget(self.xic_tol)
        tol_row.addWidget(self.xic_unit)
        form.addRow("Tolerance (±):", tol_row)
        layout.addLayout(form)

        self.xic_all_channels = QtWidgets.QCheckBox("Extract from every checked channel")
        layout.addWidget(self.xic_all_channels)

        buttons = FlowLayout()
        self.btn_xic = QtWidgets.QPushButton("Extract XIC")
        self.btn_xic_clear = QtWidgets.QPushButton("Clear XICs")
        buttons.addWidget(self.btn_xic)
        buttons.addWidget(self.btn_xic_clear)
        layout.addLayout(buttons)

        layout.addWidget(QtWidgets.QLabel("Active XICs:"))
        self.xic_list = QtWidgets.QListWidget()
        self.xic_list.setToolTip("Delete removes the selected XIC")
        layout.addWidget(self.xic_list, 1)

        hint = QtWidgets.QLabel(
            "Tip: select a range on the spectrum (Shift + drag) and right-click "
            "to extract its XIC."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)
        return page

    def _build_peaks_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.peak_table = QtWidgets.QTableWidget(0, 3)
        self.peak_table.setHorizontalHeaderLabels(["m/z", "Intensity", "% base"])
        self.peak_table.horizontalHeader().setStretchLastSection(True)
        self.peak_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.peak_table.setToolTip("Double-click to extract that mass as an XIC")
        layout.addWidget(self.peak_table)
        return page

    def _build_toolbars(self) -> None:
        bar = self.addToolBar("Main")
        bar.setObjectName("toolbar_main")
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.act_select = QtGui.QAction("Select range", self, checkable=True)
        self.act_select.setToolTip(
            "Dragging selects a range instead of zooming "
            "(Shift + drag always does the same)"
        )
        bar.addAction(self.act_select)
        self.act_autoscale = bar.addAction("Fit")
        self.act_marker = bar.addAction("Add marker")
        self.act_marker.setToolTip(
            "Reference marker on the spectrum; other peaks are then labelled "
            "with their distance to it — neutral losses and isotope spacings"
        )
        self.act_marker_clear = bar.addAction("Clear markers")

        view = self.addToolBar("View")
        view.setObjectName("toolbar_view")
        view.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.act_norm = QtGui.QAction("Normalise", self, checkable=True)
        self.act_mirror = QtGui.QAction("Mirror", self, checkable=True)
        self.act_mirror.setToolTip("Flip every other trace — sample against blank")
        self.act_stack = QtGui.QAction("Stack", self, checkable=True)
        self.act_stack.setToolTip(
            "One pane per trace, with the time axes locked together"
        )
        self.act_overview = QtGui.QAction("Overview", self, checkable=True)
        self.act_overview.setToolTip(
            "Navigator showing the full range and the region currently in view"
        )
        self.act_labels = QtGui.QAction("m/z labels", self, checkable=True)
        self.act_labels.setChecked(True)
        self.act_apex = QtGui.QAction("RT labels", self, checkable=True)
        self.act_apex.setChecked(True)
        self.act_relative = QtGui.QAction("Relative labels", self, checkable=True)
        self.act_relative.setChecked(True)
        self.act_relative.setToolTip(
            "With markers present, label peaks by their distance to the marker"
        )
        self.act_legend = QtGui.QAction("Legend", self, checkable=True)
        self.act_legend.setChecked(True)
        for action in (self.act_norm, self.act_mirror, self.act_stack,
                       self.act_overview, self.act_labels, self.act_apex,
                       self.act_relative, self.act_legend):
            view.addAction(action)
        view.addSeparator()
        # beside the label switches, because that is what it belongs to, and
        # ahead of the cascade so it is the cascade that goes into the
        # toolbar's overflow on a narrow window
        view.addWidget(QtWidgets.QLabel(" Label floor (%): "))
        self.floor_spin = QtWidgets.QDoubleSpinBox()
        self.floor_spin.setRange(plots.FLOOR_MIN * 100.0, plots.FLOOR_MAX * 100.0)
        self.floor_spin.setDecimals(2)
        self.floor_spin.setSingleStep(0.25)
        self.floor_spin.setValue(label_rule.LABEL_MIN_RELATIVE * 100.0)
        self.floor_spin.setToolTip(
            "How tall a peak must be, against the tallest one in view, to be "
            "labelled with its m/z.\nThe same as the triangle beside the "
            "spectrum's Y axis; either moves the other."
        )
        view.addWidget(self.floor_spin)
        view.addSeparator()
        view.addWidget(QtWidgets.QLabel(" Cascade x (min): "))
        self.offset_x_spin = QtWidgets.QDoubleSpinBox()
        self.offset_x_spin.setRange(-10.0, 10.0)
        self.offset_x_spin.setSingleStep(0.05)
        self.offset_x_spin.setDecimals(2)
        self.offset_x_spin.setToolTip("Shift each overlaid trace along time")
        view.addWidget(self.offset_x_spin)
        view.addWidget(QtWidgets.QLabel("  y (%): "))
        self.offset_y_spin = QtWidgets.QDoubleSpinBox()
        self.offset_y_spin.setRange(-500.0, 500.0)
        self.offset_y_spin.setSingleStep(5.0)
        self.offset_y_spin.setDecimals(0)
        self.offset_y_spin.setToolTip("Stagger each overlaid trace vertically")
        view.addWidget(self.offset_y_spin)

        # Main and View fill a row on their own; without a break the whole
        # Processing toolbar collapses behind an overflow button
        self.addToolBarBreak()
        proc = self.addToolBar("Processing")
        proc.setObjectName("toolbar_proc")
        proc.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        proc.addWidget(QtWidgets.QLabel(" Smooth (σ, scans): "))
        self.smooth_spin = QtWidgets.QDoubleSpinBox()
        self.smooth_spin.setRange(0.0, 25.0)
        self.smooth_spin.setSingleStep(0.5)
        self.smooth_spin.setDecimals(1)
        self.smooth_spin.setToolTip("Gaussian smoothing; 0 turns it off")
        proc.addWidget(self.smooth_spin)
        proc.addWidget(QtWidgets.QLabel("  Baseline (min): "))
        self.baseline_spin = QtWidgets.QDoubleSpinBox()
        self.baseline_spin.setRange(0.0, 60.0)
        self.baseline_spin.setSingleStep(0.5)
        self.baseline_spin.setDecimals(1)
        self.baseline_spin.setToolTip(
            "Window width used to estimate the baseline; 0 turns it off.\n"
            "It must be wider than the broadest peak you want to keep."
        )
        proc.addWidget(self.baseline_spin)
        proc.addSeparator()
        self.act_centroid = QtGui.QAction("Centroid", self, checkable=True)
        self.act_centroid.setToolTip("Show the spectrum as centroid sticks")
        proc.addAction(self.act_centroid)
        # off by default: a whole-run average leaves out the scans where the
        # spray faltered, and this puts them back for anyone who wants the
        # run exactly as it came off the instrument
        self.act_unstable = QtGui.QAction("Include unstable scans", self,
                                          checkable=True)
        self.act_unstable.setToolTip(
            "Average every scan of the run, including the ones where the "
            "spray faltered.\n"
            "Off, a whole-run average leaves out any scan whose total ion "
            "current departs\nfrom its neighbours by more than half, and the "
            "ones after it until it comes back —\nthe pane's title, the "
            "report's header and a library record made from it all say how "
            "many\nand where")
        proc.addSeparator()
        self.act_set_bg = proc.addAction("Set background")
        self.act_set_bg.setToolTip(
            "Use the selected chromatogram range as the blank: every spectrum "
            "generated from then on comes out with that background subtracted"
        )
        self.act_clear_bg = proc.addAction("Clear background")
        proc.addSeparator()
        self.act_explain = proc.addAction("Explain spectrum")
        self.act_explain.setToolTip(
            "Score every LIPID MAPS candidate for this precursor by how much "
            "of the spectrum on screen its structure accounts for")
        self.act_detect = proc.addAction("Detect peaks")
        self.act_avg_run = proc.addAction("Average whole run")
        self.act_avg_run.setToolTip(
            "Average every scan of the active channel into one spectrum — "
            "what a direct infusion, which has no chromatography to select "
            "over, is meant to be looked at as")
        self.act_delta = QtGui.QAction("Δ from average", self, checkable=True)
        self.act_delta.setEnabled(False)
        self.act_delta.setToolTip(
            "On an infusion: draw the scan minus the average of the whole "
            "run, with the average mirrored underneath it. Every scan of a "
            "spray is the same spectrum, so what is left is what changed — "
            "and while this is on, the live spectrum is that difference")
        proc.addAction(self.act_delta)
        self.act_inf_report = proc.addAction("Report this infusion…")
        self.act_inf_report.setEnabled(False)
        self.act_inf_report.setToolTip(
            "One compound on paper: the averaged spectrum at the label floor "
            "on screen, its peaks, the accurate precursor, whatever structure "
            "or formula was scored in the LIPID MAPS tab and whatever the "
            "library search found — and a verdict that sums what was checked "
            "rather than passing or failing it")
        self.act_inf_reports = QtGui.QAction("Report every infusion…", self)
        self.act_inf_reports.setEnabled(False)
        self.act_inf_reports.setToolTip(
            "The same report for every open infusion, one section per "
            "compound in one document")
        self.act_exp_chrom = QtGui.QAction("Export chromatograms (CSV)…", self)
        self.act_exp_spec = QtGui.QAction("Export spectrum (CSV)…", self)
        self.act_exp_cmp = QtGui.QAction("Export comparison (PNG/SVG)…", self)
        self.act_exp_cmp.setEnabled(False)
        self.act_exp_cmp.setToolTip(
            "Write the pinned spectra and the live one as one picture — PNG "
            "at twice the size for print, or SVG to resize. The same drawing "
            "goes in the report")
        self.act_exp_mzml = QtGui.QAction("Export sample as mzML…", self)
        self.act_pin = proc.addAction("Pin spectrum")
        self.act_pin.setToolTip(
            "Keep the spectrum on screen so the next one draws over it — "
            "another sample, scan or channel. Normalise puts them on one scale; "
            "Mirror draws every other one downwards, head to tail")
        self.act_unpin = proc.addAction("Unpin spectra")
        self.act_unpin.setEnabled(False)
        self.act_exp_mzml.setToolTip(
            "Write the selected sample as open-format mzML, spectrum for "
            "spectrum, so it can be read elsewhere"
        )
        self.act_detect.setToolTip(
            "Integrate the peaks of every chromatogram trace and fill the Results tab"
        )

    def _build_panel_actions(self) -> None:
        """One action per panel, for the corner menu and the menu bar."""
        self.panel_actions = []
        for index in range(self.tabs.count()):
            action = QtGui.QAction(self.tabs.tabText(index), self)
            action.setShortcut(QtGui.QKeySequence(f"Ctrl+Shift+{index + 1}"))
            action.triggered.connect(
                lambda _checked, i=index: self.show_panel(i))
            self.panel_menu.addAction(action)
            self.panel_actions.append(action)
            self.addAction(action)

    def show_panel(self, index: int) -> None:
        """Bring a panel to the front, opening the dock if it was closed."""
        self.dock_side.show()
        self.dock_side.raise_()
        self.tabs.setCurrentIndex(index)
        self.tabs.tabBar().setCurrentIndex(index)

    def show_panel_named(self, title: str) -> bool:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.show_panel(index)
                return True
        return False

    def _reopen_action(self, dock, text: str, shortcut: str,
                       tip: str) -> QtGui.QAction:
        """
        The way back after a side panel has been closed.

        A dock has a close button and nothing that undoes it. Qt lists them in
        a context menu on the toolbar, which nobody finds — close the tree of
        samples and channels and the workspace looks broken with no way back.

        The action is made here, where the dock is, rather than when the menu
        asks for it: the shortcut has to work whether or not anything built a
        menu, and it only fires at all if the window itself owns the action.
        """
        action = dock.toggleViewAction()
        action.setText(text)
        action.setShortcut(QtGui.QKeySequence(shortcut))
        action.setShortcutContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        action.setToolTip(tip)
        self.addAction(action)
        return action

    def _dock_actions(self) -> list:
        separator = QtGui.QAction(self)
        separator.setSeparator(True)
        return [separator, self.act_dock_tree, self.act_dock_side]

    def build_actions(self) -> dict:
        """Actions the shell adds to its own menus for this workspace."""
        return {
            "File": [self.act_exp_chrom, self.act_exp_spec, self.act_exp_cmp,
                     self.act_exp_mzml],
            "View": [self.act_autoscale, self.act_norm, self.act_mirror,
                     self.act_stack, self.act_overview, self.act_labels,
                     self.act_apex, self.act_relative, self.act_legend,
                     *self._dock_actions()],
            "Panels": list(self.panel_actions),
            "Process": [self.act_centroid, self.act_unstable,
                        self.act_marker, self.act_marker_clear,
                        self.act_set_bg, self.act_clear_bg, self.act_explain,
                        self.act_detect, self.act_avg_run, self.act_delta,
                        self.act_inf_report, self.act_inf_reports,
                        self.act_pin, self.act_unpin],
        }

    # -------------------------------------------------------------- signals -- #
    def _connect(self) -> None:
        self.act_autoscale.triggered.connect(self._autoscale_both)
        self.act_select.toggled.connect(self._set_select_mode)
        self.act_norm.toggled.connect(self._set_normalised)
        self.act_mirror.toggled.connect(self._set_mirror)
        self.act_stack.toggled.connect(self.chrom.set_stacked)
        self.act_overview.toggled.connect(self._set_overview)
        self.act_labels.toggled.connect(self.spectrum.set_labels_enabled)
        self.act_apex.toggled.connect(self.chrom.set_apex_labels)
        self.act_relative.toggled.connect(self._set_relative_labels)
        self.act_legend.toggled.connect(self.chrom.set_legend_visible)
        self.act_centroid.toggled.connect(self._set_centroid)
        self.act_unstable.toggled.connect(self._unstable_toggled)
        self.act_marker.triggered.connect(self._add_marker)
        self.act_marker_clear.triggered.connect(self._clear_markers)
        self.act_pin.triggered.connect(self.pin_spectrum)
        self.act_unpin.triggered.connect(self.unpin_spectra)
        self.spectrum.sigPinRequested.connect(self.pin_spectrum)
        self.spectrum.sigUnpinRequested.connect(self.unpin_spectra)
        self.act_exp_chrom.triggered.connect(
            lambda: self._export(self.chrom, "chromatograms"))
        self.act_exp_spec.triggered.connect(
            lambda: self._export(self.spectrum, "spectrum"))
        self.act_exp_cmp.triggered.connect(self._export_comparison)
        self.act_exp_mzml.triggered.connect(self._export_mzml)
        self.act_set_bg.triggered.connect(self._set_background)
        self.act_clear_bg.triggered.connect(self._clear_background)
        self.act_explain.triggered.connect(self.explain_spectrum)
        self.act_detect.triggered.connect(self._detect_peaks)
        self.act_avg_run.triggered.connect(self.average_whole_run)
        self.act_delta.toggled.connect(self._set_delta_mode)
        self.act_inf_report.triggered.connect(self.report_infusion)
        self.act_inf_reports.triggered.connect(
            lambda: self.report_infusion(batch=True))

        self.smooth_spin.valueChanged.connect(self._set_smoothing)
        self.baseline_spin.valueChanged.connect(self.chrom.set_baseline)
        self.offset_x_spin.valueChanged.connect(self._set_offsets)
        self.offset_y_spin.valueChanged.connect(self._set_offsets)
        self.floor_spin.valueChanged.connect(self._set_label_floor)
        self.spectrum.sigLabelFloorChanged.connect(self._label_floor_moved)

        self.tree.itemChanged.connect(self._on_tree_changed)
        self.tree.currentItemChanged.connect(self._on_tree_selection)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.btn_collapse.clicked.connect(self.collapse_samples)
        self.btn_none.clicked.connect(lambda: self._bulk_check(lambda ref: False))
        self.btn_ms1.clicked.connect(
            lambda: self._bulk_check(
                lambda ref: ref.channel is not None and ref.channel.info.is_ms1
            )
        )

        self.mode_combo.currentTextChanged.connect(lambda _: self.refresh_chromatogram())
        self.active_combo.currentIndexChanged.connect(self._on_active_changed)
        self.view_combo.currentTextChanged.connect(self._on_view_changed)
        self.contour_view.sigPointPicked.connect(self._on_contour_point)
        self.contour_view.sigRegionPicked.connect(self._on_contour_region)
        self.contour_view.sigRebuildRequested.connect(self._rebuild_contour)
        self.contour_view.sigScanRequested.connect(self._play_to_scan)

        self.chrom.sigClicked.connect(self._on_chrom_click)
        self.chrom.sigRangeSelected.connect(self._on_chrom_range)
        self.chrom.sigRangeDragging.connect(self._on_chrom_dragging)
        self.chrom.sigBackgroundChanged.connect(self._on_background_changed)
        self.spectrum.sigExtractRequested.connect(self._extract_from_range)

        self.btn_prev.clicked.connect(lambda: self._step_scan(-1))
        self.btn_next.clicked.connect(lambda: self._step_scan(+1))
        self.scan_spin.valueChanged.connect(self._on_scan_spin)
        self.btn_avg.clicked.connect(self._average_selection)

        self.btn_xic.clicked.connect(self._extract_from_form)
        self.btn_xic_clear.clicked.connect(self._clear_xics)
        self.peak_table.cellDoubleClicked.connect(self._peak_double_clicked)

        self.component_list.sigExtractAll.connect(self._extract_components)
        self.component_list.sigShowComponent.connect(self._show_component)
        self.results_panel.sigResultActivated.connect(self._go_to_result)

        self.spectrum.sigIdentifyRequested.connect(self._identify_peak)
        self.mass_calc.sigOverlay.connect(self._overlay_pattern)
        self.library_panel.sigOverlay.connect(self._overlay_pattern)
        self.library_panel.sigClearOverlay.connect(self.spectrum.clear_overlay)
        self.mass_calc.sigClearOverlay.connect(self.spectrum.clear_overlay)
        self.mass_calc.sigSendToFinder.connect(self._send_to_finder)
        self.formula_panel.sigSearch.connect(self._run_formula_search)
        self.formula_panel.sigOverlay.connect(self._overlay_hit)
        self.formula_panel.sigSendToCalculator.connect(
            self.mass_calc.formula_edit.setText)
        self.lipid_panel.sigAnnotate.connect(self._lipid_annotation)
        self.lipid_panel.sigPrecursor.connect(self._lipid_precursor)
        self.lipid_panel.sigFragment.connect(self._lipid_fragment)
        self.lipid_panel.sigMatches.connect(self.spectrum.set_matches)

        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Left), self,
                        activated=lambda: self._step_scan(-1))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Right), self,
                        activated=lambda: self._step_scan(+1))
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.xic_list,
                        activated=self._remove_selected_xic)

    # ---------------------------------------------------------- preferences -- #
    def _restore_settings(self) -> None:
        s = self.settings
        state = s.value("explorer/state")
        if state is not None:
            # a saved arrangement from a version with a different toolbar
            # layout is discarded rather than pinning the old one back
            self.restoreState(state, LAYOUT_VERSION)

        def flag(key: str, default: bool) -> bool:
            return s.value(key, default, type=bool)

        self.act_norm.setChecked(flag("view/normalise", False))
        self.act_mirror.setChecked(flag("view/mirror", False))
        self.act_stack.setChecked(flag("view/stacked", False))
        self.act_overview.setChecked(flag("view/overview", False))
        self.act_labels.setChecked(flag("view/labels", True))
        self.act_apex.setChecked(flag("view/apex", True))
        self.act_relative.setChecked(flag("view/relative_labels", True))
        self.act_legend.setChecked(flag("view/legend", True))
        self.act_select.setChecked(flag("view/select_mode", False))
        self.act_centroid.setChecked(flag("view/centroid", False))
        self.act_unstable.setChecked(flag("proc/include_unstable", False))
        self.offset_x_spin.setValue(s.value("view/offset_x", 0.0, type=float))
        self.offset_y_spin.setValue(s.value("view/offset_y", 0.0, type=float))
        # kept as the per cent the spin box shows, which is what the reader
        # typed; the pane stores it as a fraction
        self.floor_spin.setValue(s.value(
            "view/label_floor", label_rule.LABEL_MIN_RELATIVE * 100.0,
            type=float))
        self.smooth_spin.setValue(s.value("proc/smooth", 0.0, type=float))
        self.baseline_spin.setValue(s.value("proc/baseline", 0.0, type=float))
        self.xic_tol.setValue(s.value("xic/tolerance", 0.02, type=float))
        self.xic_unit.setCurrentText(s.value("xic/unit", "Da", type=str))
        self.xic_all_channels.setChecked(flag("xic/all_channels", False))
        self.mode_combo.setCurrentText(s.value("chrom/mode", "TIC", type=str))
        self.formula_panel.tol_spin.setValue(s.value("formula/tolerance", 10.0, type=float))
        self.formula_panel.unit_combo.setCurrentText(
            s.value("formula/unit", "ppm", type=str))
        self.formula_panel.adduct_combo.setCurrentText(
            s.value("formula/adduct", "[M-H]-", type=str))
        self.mass_calc.adduct_combo.setCurrentText(
            s.value("formula/adduct", "[M-H]-", type=str))
        self.formula_panel.even_electron.setChecked(flag("formula/even_electron", True))
        self.formula_panel.golden_rules.setChecked(flag("formula/golden_rules", True))
        self.formula_panel.use_isotopes.setChecked(flag("formula/use_isotopes", True))
        stored_ranges = s.value("formula/ranges", "", type=str)
        if stored_ranges:
            try:
                import json as _json
                self._apply_element_ranges(_json.loads(stored_ranges))
            except (ValueError, TypeError):
                pass

        # push the restored state through (signals are already connected)
        self._set_select_mode(self.act_select.isChecked())
        self._set_normalised(self.act_norm.isChecked())
        self._set_mirror(self.act_mirror.isChecked())
        self.chrom.set_stacked(self.act_stack.isChecked())
        self._set_overview(self.act_overview.isChecked())
        self.spectrum.set_labels_enabled(self.act_labels.isChecked())
        self.chrom.set_apex_labels(self.act_apex.isChecked())
        self._set_relative_labels(self.act_relative.isChecked())
        self.chrom.set_legend_visible(self.act_legend.isChecked())
        self._set_centroid(self.act_centroid.isChecked())
        self._set_offsets()
        self._set_label_floor(self.floor_spin.value())
        self._set_smoothing(self.smooth_spin.value())
        self.chrom.set_baseline(self.baseline_spin.value())

    def save_settings(self) -> None:
        s = self.settings
        s.setValue("explorer/state", self.saveState(LAYOUT_VERSION))
        s.setValue("view/normalise", self.act_norm.isChecked())
        s.setValue("view/mirror", self.act_mirror.isChecked())
        s.setValue("view/stacked", self.act_stack.isChecked())
        s.setValue("view/overview", self.act_overview.isChecked())
        s.setValue("view/labels", self.act_labels.isChecked())
        s.setValue("view/apex", self.act_apex.isChecked())
        s.setValue("view/relative_labels", self.act_relative.isChecked())
        s.setValue("view/legend", self.act_legend.isChecked())
        s.setValue("view/select_mode", self.act_select.isChecked())
        s.setValue("view/centroid", self.act_centroid.isChecked())
        s.setValue("proc/include_unstable", self.act_unstable.isChecked())
        s.setValue("view/offset_x", self.offset_x_spin.value())
        s.setValue("view/offset_y", self.offset_y_spin.value())
        s.setValue("view/label_floor", self.floor_spin.value())
        s.setValue("proc/smooth", self.smooth_spin.value())
        s.setValue("proc/baseline", self.baseline_spin.value())
        s.setValue("xic/tolerance", self.xic_tol.value())
        s.setValue("xic/unit", self.xic_unit.currentText())
        s.setValue("xic/all_channels", self.xic_all_channels.isChecked())
        s.setValue("chrom/mode", self.mode_combo.currentText())
        s.setValue("formula/tolerance", self.formula_panel.tol_spin.value())
        s.setValue("formula/unit", self.formula_panel.unit_combo.currentText())
        s.setValue("formula/adduct", self.formula_panel.adduct_combo.currentText())
        s.setValue("formula/even_electron", self.formula_panel.even_electron.isChecked())
        s.setValue("formula/golden_rules", self.formula_panel.golden_rules.isChecked())
        s.setValue("formula/use_isotopes", self.formula_panel.use_isotopes.isChecked())
        import json as _json
        s.setValue("formula/ranges", _json.dumps(self.formula_panel.ranges()))

    def _apply_element_ranges(self, ranges: dict) -> None:
        """Write stored element ranges back into the finder's table."""
        table = self.formula_panel.elements
        for row in range(table.rowCount()):
            element = table.item(row, 0).text()
            low, high = ranges.get(element, (0, 0))
            table.item(row, 1).setText(str(int(low)))
            table.item(row, 2).setText(str(int(high)))

    def _last_dir(self) -> str:
        return self.settings.value("io/last_dir", "", type=str)

    def _remember_dir(self, path: str) -> None:
        self.settings.setValue("io/last_dir", os.path.dirname(path))

    # -------------------------------------------------------- samples/tree --- #
    def rebuild_tree(self) -> None:
        """Rebuild the sample and channel tree from the session."""
        # A node keeps whatever the user had set; a node that was never in the
        # tree is new, and a new sample comes in with its TIC shown.
        previous = self._tree_items()
        checked = {k for k, item in previous.items()
                   if item.checkState(0) == QtCore.Qt.CheckState.Checked}
        self.tree.blockSignals(True)
        self.tree.clear()
        self.refs.clear()

        #: the newest infusion opened this time round, to land on afterwards
        arrived: ChannelRef | None = None
        by_file: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for entry in self.session.entries:
            if not entry.is_loaded:
                continue
            file_item = by_file.get(entry.path)
            if file_item is None:
                file_item = QtWidgets.QTreeWidgetItem(self.tree, [entry.filename])
                font = file_item.font(0)
                font.setBold(True)
                file_item.setFont(0, font)
                by_file[entry.path] = file_item

            sample = entry.sample
            verdict = self.verdict(entry)
            instrument = sample.instrument + (", infusion" if verdict else "")
            sample_item = QtWidgets.QTreeWidgetItem(
                file_item, [f"{entry.name}  ({instrument})"]
            )
            if verdict:
                sample_item.setToolTip(0, verdict.reason)
            if entry.problem:
                # in front, where a narrow dock cannot cut it off
                sample_item.setText(0, "⚠ " + sample_item.text(0))
                sample_item.setToolTip(0, entry.problem)
            tic = ChannelRef(entry, None)
            self._add_leaf(sample_item, "Sample TIC (all channels)", tic,
                           checked=tic.key in checked or tic.key not in previous)
            # an infusion's own channel comes in checked and becomes the
            # active one; nothing else about a new sample changes
            wanted = verdict.channel_index if verdict else None
            for channel in sample.channels:
                ref = ChannelRef(entry, channel)
                new = ref.key not in previous
                on_arrival = new and channel.index == wanted
                self._add_leaf(sample_item, channel.info.label, ref,
                               checked=ref.key in checked or on_arrival)
                if on_arrival:
                    arrived = ref
            sample_item.setExpanded(True)
            file_item.setExpanded(True)
        self.tree.blockSignals(False)
        self._rebuild_active_combo()
        self.refresh_chromatogram()
        if arrived is not None:
            self.open_as_infusion(arrived)

    # -------------------------------------------------------------- infusion #
    def verdict(self, entry: SampleEntry) -> InfusionVerdict:
        """
        Whether this sample is a direct infusion.

        The tree asks for every sample it draws and it is rebuilt on every
        file opened, so the measurement is the module's cached one: it reads
        chromatograms only, but on an eighty-one channel sample that is still
        eighty-one of them.
        """
        try:
            return verdict_for(entry.sample)
        except Exception as exc:  # a reader that cannot say is not one
            return InfusionVerdict(
                False, f"the run could not be read: {_first_line(exc)}")

    def noise_floor(self, ref: ChannelRef) -> NoiseFloor | None:
        """
        What this channel's averaged spectrum calls noise, measured once.

        Asked of an infusion and of nothing else: the floor is a statement
        about the average of a whole run, and `infusion.noise_floor_for`
        remembers it per channel, so the pane, the report and a record
        written from the spectrum all read one measurement.
        """
        channel = getattr(ref, "channel", None)
        if channel is None or not self.verdict(ref.entry):
            return None
        try:
            return noise_floor_for(channel)
        except Exception:                   # a reader that cannot say
            return None

    def _floor_from_noise(self, ref: ChannelRef) -> None:
        """
        Start an infusion's labels at the higher of 2% and the noise floor.

        Two per cent of the tallest peak in view is a drawing rule and it
        knows nothing about the acquisition; the noise floor is measured off
        this one. Whichever is higher is the one that means something, and
        the status line says which it was and what it was measured from —
        a floor that moved on its own and did not say why would be worse
        than the constant it replaced.
        """
        floor = self.noise_floor(ref)
        if floor is None or not floor.measured:
            return
        share = floor.relative or 0.0
        wanted = max(label_rule.LABEL_MIN_RELATIVE, share)
        self.floor_spin.setValue(wanted * 100.0)
        which = ("the noise floor" if share >= label_rule.LABEL_MIN_RELATIVE
                 else f"the drawing's {label_rule.LABEL_MIN_RELATIVE:.0%}")
        self._update_status(
            f"Label floor {wanted:.2%}, {which}: {floor.describe()} "
            f"That is {share:.3%} of the base peak "
            f"({format_counts(floor.value)} counts).")

    def open_as_infusion(self, ref: ChannelRef) -> None:
        """
        Land on an infusion's own channel, showing the whole run at once.

        An infusion has no chromatography to pick a range over, so the
        chromatogram — which is still drawn, and is still the TIC over time —
        has nothing to point at. The average of every scan is the spectrum,
        and it is what Explain, the library search and a pin all then work on.
        """
        index = self.active_combo.findData(ref.key)
        if index < 0:
            return
        self.active_combo.blockSignals(True)
        self.active_combo.setCurrentIndex(index)
        self.active_combo.blockSignals(False)
        self._sync_active_ref()
        self.average_whole_run()

    def average_whole_run(self) -> None:
        """Every scan of the active channel, averaged into one spectrum."""
        ref = self.active_ref
        channel = ref.channel if ref else None
        if channel is None:
            self._update_status("Pick an active channel first.")
            return
        window = run_range(channel)
        if window is None:
            self._update_status(f"{ref.label} has no scans to average.")
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            infused = bool(self.verdict(ref.entry))
            self._show_average(*window, whole_run=True,
                               tag=" (infusion)" if infused else "")
            if infused:
                self._floor_from_noise(ref)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    # -- Δ from the average ------------------------------------------------ #
    def run_average(self, channel) -> tuple[np.ndarray, np.ndarray] | None:
        """
        The average of every scan of a channel, read once and kept.

        The Δ mode needs it on every scan the film steps through, and on the
        real infusions that is 473 scans of a 242,308-point average: reading
        it each time would make Play a slideshow.
        """
        if channel is None:
            return None
        window = run_range(channel)
        if window is None:
            return None
        key = (id(channel), int(getattr(channel.info, "n_scans", 0)), window)
        if key not in self._average_cache:
            try:
                self._average_cache[key] = channel.spectrum_rt_range(*window)
            except Exception:
                return None
        return self._average_cache[key]

    def _delta_from_average(self, channel, mz: np.ndarray,
                            intensity: np.ndarray):
        """
        The scan minus the whole-run average, and the average beside it.

        The average is interpolated onto the scan's own m/z axis first, the
        same way a background is: the two grids do not line up in profile
        data, and on a real infusion they are not even the same length — a
        scan of 8,815 points against an average of 242,308, which is every
        scan's grid unioned. Nothing is clipped at zero, unlike the
        background subtraction: a scan that is *short* of the average is
        precisely what this is for.
        """
        average = self.run_average(channel)
        if average is None or mz.size == 0:
            return None
        avg_mz, avg_intensity = average
        if np.asarray(avg_mz).size < 2:
            return None
        base = np.interp(mz, avg_mz, avg_intensity, left=0.0, right=0.0)
        return intensity - base, base

    def _set_delta_mode(self, enabled: bool) -> None:
        """
        Turn the difference on, and Mirror with it.

        Mirror is what draws the pair head to tail, and a difference drawn on
        top of the average it was taken from is unreadable — so this turns it
        on rather than asking, and puts it back as it was on the way out. It
        is the existing switch being set, not a second copy of it: turning
        Mirror off by hand while Δ is on leaves the two overlaid, which is a
        thing somebody might want.
        """
        if enabled:
            self._mirror_before_delta = bool(self.act_mirror.isChecked())
            self.act_mirror.setChecked(True)
        else:
            if self._mirror_before_delta is not None:
                self.act_mirror.setChecked(self._mirror_before_delta)
            self._mirror_before_delta = None
        if self.active_ref is not None and self.active_ref.channel is not None:
            self._show_scan(self.current_scan)
        self._update_status(
            "Δ from the average: the scan minus the average of the whole "
            "run, over the average mirrored. The live spectrum is that "
            "difference — turn it off before Explain or a library search."
            if enabled else "Δ from the average off.")

    def report_infusion(self, batch: bool = False) -> None:
        """
        One compound on paper — the dialog picks the format, the file and
        what it is compared against.

        Offered only on an infusion: everything the report holds is the
        average of a whole run, which is a lie about a chromatographic
        sample. The dialog does the writing, so the flow can be exercised
        without a modal loop.
        """
        if self.active_ref is None or self.active_ref.channel is None:
            self._update_status("Pick an active channel first.")
            return
        from .infusion_report_dialog import InfusionReportDialog

        dialog = InfusionReportDialog(self, batch=batch, parent=self)
        dialog.exec()
        if dialog.written:
            self._remember_dir(dialog.written[-1])
            self._update_status(f"Infusion report written to "
                                f"{dialog.written[-1]}")
        dialog.deleteLater()

    def _tree_items(self) -> dict:
        out = {}
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            key = it.value().data(0, ROLE_REF)
            if key:
                out[key] = it.value()
            it += 1
        return out

    def _add_leaf(self, parent, text: str, ref: ChannelRef, checked: bool) -> None:
        item = QtWidgets.QTreeWidgetItem(parent, [text])
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked,
        )
        item.setData(0, ROLE_REF, ref.key)
        if ref.entry.problem:
            item.setToolTip(0, ref.entry.problem)
        self.refs[ref.key] = ref

    def clear_views(self) -> None:
        """Drop everything that referred to samples that are no longer open."""
        self.refs.clear()
        self.xic_defs.clear()
        self.active_ref = None
        self._background_cache.clear()
        self._contour_cache.clear()
        self._average_cache.clear()
        self.contour_view.clear_film()
        # a pin points at a channel of a file that is about to be closed,
        # and its recipe at a sample that is about to be gone
        self._pinned = []
        self._live_recipe = None
        self.act_unpin.setEnabled(False)
        self.act_exp_cmp.setEnabled(False)
        self.tree.clear()
        self.xic_list.clear()
        self.active_combo.clear()
        self.chrom.clear_traces()
        self.chrom.clear_peak_markers()
        self.chrom.clear_background_range()
        self.spectrum.clear_traces()
        self.peak_table.setRowCount(0)
        self.results_panel.clear()
        self.sample_info.clear()
        self._update_status("No files open.")

    def _refresh_components(self) -> None:
        self.component_list.set_components(self.session.method.components)

    # ----------------------------------------------------------------- tree -- #
    def _checked_refs(self) -> list[ChannelRef]:
        out = []
        it = QtWidgets.QTreeWidgetItemIterator(
            self.tree, QtWidgets.QTreeWidgetItemIterator.IteratorFlag.Checked
        )
        while it.value():
            key = it.value().data(0, ROLE_REF)
            if key in self.refs:
                out.append(self.refs[key])
            it += 1
        return out

    def _checked_samples(self) -> list[ChannelRef]:
        """One reference per checked sample, in tree order."""
        seen, out = set(), []
        for ref in self._checked_refs():
            if ref.entry.key not in seen:
                seen.add(ref.entry.key)
                out.append(ref)
        if out:
            return out
        # nothing checked: fall back to every loaded sample
        return [ChannelRef(e, None) for e in self.session.loaded_entries]

    def collapse_samples(self) -> None:
        """Fold every sample shut, leaving the file names visible."""
        self.tree.collapseAll()
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setExpanded(True)
        self._update_status("Samples collapsed.")

    def _bulk_check(self, predicate) -> None:
        self.tree.blockSignals(True)
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, ROLE_REF)
            if key in self.refs:
                item.setCheckState(
                    0,
                    QtCore.Qt.CheckState.Checked if predicate(self.refs[key])
                    else QtCore.Qt.CheckState.Unchecked,
                )
            it += 1
        self.tree.blockSignals(False)
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, ROLE_REF) is not None:
                item.setHidden(bool(needle) and needle not in item.text(0).lower())
            it += 1

    def _on_tree_changed(self, item, column) -> None:
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _on_tree_selection(self, current, previous) -> None:
        if current is None:
            return
        key = current.data(0, ROLE_REF)
        if key in self.refs:
            index = self.active_combo.findData(key)
            if index >= 0:
                self.active_combo.setCurrentIndex(index)

    # -------------------------------------------------------- active channel - #
    def _rebuild_active_combo(self) -> None:
        previous = self.active_combo.currentData()
        self.active_combo.blockSignals(True)
        self.active_combo.clear()
        candidates = [r for r in self._checked_refs() if r.channel is not None]
        if not candidates:
            candidates = [r for r in self.refs.values() if r.channel is not None]
        for ref in candidates:
            self.active_combo.addItem(ref.full_label, ref.key)
        index = self.active_combo.findData(previous)
        self.active_combo.setCurrentIndex(index if index >= 0 else 0)
        self.active_combo.blockSignals(False)
        self._sync_active_ref()

    def _sync_active_ref(self) -> None:
        key = self.active_combo.currentData()
        self.active_ref = self.refs.get(key) if key else None
        channel = self.active_ref.channel if self.active_ref else None
        self.scan_spin.blockSignals(True)
        self.scan_spin.setMaximum(max(channel.info.n_scans if channel else 1, 1))
        self.scan_spin.blockSignals(False)
        verdict = self.verdict(self.active_ref.entry) if self.active_ref else None
        self.infusion_label.setText("infusion" if verdict else "")
        self.infusion_label.setToolTip(verdict.reason if verdict else "")
        # the report is of an infusion, so it is offered on one and nowhere
        # else; the batch one needs at least one open, which is the same test
        self.act_inf_report.setEnabled(bool(verdict))
        self.act_inf_reports.setEnabled(bool(verdict))
        # the difference is against the average of the whole run, which is
        # only the spectrum on a run with no chromatography in it
        self.act_delta.setEnabled(bool(verdict))
        if not verdict and self.act_delta.isChecked():
            self.act_delta.setChecked(False)
        if self.active_ref is not None:
            self.sample_info.show_sample(self.active_ref.sample, channel)

    def _on_active_changed(self, _index: int) -> None:
        # a film is of one channel; the next channel's is a different run of
        # scans, and a timer left running would be stepping the new one
        self.contour_view.stop_play()
        self._sync_active_ref()
        if self.active_ref and self.active_ref.channel:
            self._show_scan(min(self.current_scan,
                                self.active_ref.channel.info.n_scans - 1))
        if self._contour_showing:
            self._show_contour()
        else:
            self.contour_view.clear_film()

    # ----------------------------------------------------------- contour -- #
    @property
    def _contour_showing(self) -> bool:
        return self.top_stack.currentIndex() == 1

    def _on_view_changed(self, name: str) -> None:
        self.top_stack.setCurrentIndex(1 if name == VIEW_CONTOUR else 0)
        # TIC against BPC is a choice about a chromatogram; on a surface with
        # neither axis summed away it means nothing, so it goes away
        self.mode_combo.setVisible(not self._contour_showing)
        if self._contour_showing and self.contour_view.contour().is_empty:
            self._show_contour()
        elif not self._contour_showing:
            # Pause lives on the surface, so a film left running behind the
            # chromatogram would be stepping scans with nothing on screen to
            # stop it
            self.contour_view.stop_play()

    def _show_contour(self, rt_range=None, mz_range=None) -> None:
        """
        Build the surface for the active channel, or show the one already
        built for it.

        Reading every scan is the cost, so it is cached against the channel
        and the ranges it was built over, and a second look at the same
        channel is instant. It is also cancellable: a partial surface of the
        first half of a run still shows what is in the first half.
        """
        ref = self.active_ref
        channel = ref.channel if ref else None
        if channel is None:
            self.contour_view.set_contour(Contour(
                note="Pick an active channel to build a contour."))
            self.contour_view.clear_film()
            return

        key = (ref.key, rt_range, mz_range)
        cached = self._contour_cache.get(key)
        if cached is not None:
            self.contour_view.set_contour(cached, ref.label)
            return

        progress = QtWidgets.QProgressDialog(
            f"Reading {channel.info.n_scans:,} scans…", "Cancel", 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)

        def tick(done: int, total: int):
            progress.setValue(int(done / max(total, 1) * 100))
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            contour = build_contour(channel, rt_range=rt_range,
                                    mz_range=mz_range, progress=tick)
        except Exception as exc:
            progress.close()
            self._update_status(ref.entry.problem or f"Contour failed: {_first_line(exc)}")
            return
        progress.close()
        self._contour_cache[key] = contour
        while len(self._contour_cache) > CONTOUR_CACHE:
            self._contour_cache.pop(next(iter(self._contour_cache)))
        self.contour_view.set_contour(contour, ref.label)
        self._update_film()
        self._update_status(f"Contour of {ref.label}: {contour.scans:,} scans")

    def _update_film(self) -> None:
        """
        On an infusion, the surface is a film and gets the strip and Play.

        The strip is the channel's own chromatogram rather than anything
        taken off the grid: the grid's rows may be several scans averaged
        into one and its m/z bins are wider than the instrument's steps, so
        a burst read off it would be the picture's arithmetic and not the
        instrument's. On a chromatographic run there is nothing here to add
        — the chromatogram pane already draws the same trace, over peaks
        that mean something — so the film goes away entirely.
        """
        ref = self.active_ref
        channel = ref.channel if ref else None
        if channel is None or not self.verdict(ref.entry):
            self.contour_view.clear_film()
            return
        try:
            times, values = channel.tic()
        except Exception:
            self.contour_view.clear_film()
            return
        self.contour_view.set_film(times, values,
                                   excluded_scans(times, values), ref.label)
        self.contour_view.set_current_scan(self.current_scan)

    def _play_to_scan(self, scan: int) -> None:
        """
        Play asks for a scan; the spin box is what moves.

        Through the spin box rather than straight to `_show_scan` so that
        one frame of the film is exactly what pressing ▶ once is: the same
        signal, the same title, the same recipe on the spectrum, and the
        number under the reader's eye keeps up with the picture.
        """
        self.scan_spin.setValue(int(scan) + 1)

    def _rebuild_contour(self) -> None:
        """Read the scans again over what is on screen, at the full grid."""
        rt_lo, rt_hi, mz_lo, mz_hi = self.contour_view.view_ranges()
        self._show_contour(rt_range=(rt_lo, rt_hi), mz_range=(mz_lo, mz_hi))

    def _on_contour_point(self, rt: float, _mz: float) -> None:
        """A click on the surface shows the spectrum underneath it."""
        channel = self.active_ref.channel if self.active_ref else None
        if channel is not None:
            self._show_scan(channel.scan_at_rt(rt))

    def _on_contour_region(self, rt_lo: float, rt_hi: float,
                           mz_lo: float, mz_hi: float) -> None:
        """
        The rectangle on screen, as a chromatogram and a spectrum.

        Both come from the reader rather than from the grid. The grid is a
        picture: its m/z bins are wider than the instrument's steps and its
        rows may be several scans averaged together, so a number taken off it
        would be neither the instrument's nor reproducible from the file.
        """
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        self._add_xic(mz_lo, mz_hi, f"m/z {mz_lo:.3f}–{mz_hi:.3f}")
        self._show_average(rt_lo, rt_hi)
        self.view_combo.setCurrentText(VIEW_CHROMATOGRAM)

    def _activate_trace_key(self, key: str) -> None:
        """When a stacked pane is clicked, make its channel the active one."""
        if not key:
            return
        index = self.active_combo.findData(key)
        if index >= 0 and index != self.active_combo.currentIndex():
            self.active_combo.setCurrentIndex(index)

    # ---------------------------------------------------------- chromatogram - #
    def refresh_chromatogram(self) -> None:
        refs = self._checked_refs()
        mode = self.mode_combo.currentText()
        traces: list[Trace] = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for i, ref in enumerate(refs):
                if ref.channel is None:
                    x, y = ref.sample.tic()
                    label = f"{ref.label} (TIC)"
                elif mode == "BPC":
                    x, y = ref.channel.bpc()
                    label = f"{ref.label} (BPC)"
                else:
                    x, y = ref.channel.tic()
                    label = f"{ref.label} (TIC)"
                traces.append(Trace(ref.key, label, x, y, colour(i), ref.channel))

            for j, xic in enumerate(self.xic_defs):
                traces.append(
                    Trace(xic["key"], xic["label"], xic["x"], xic["y"],
                          colour(len(refs) + j), xic["channel"])
                )
            self.chrom.set_traces(traces)
            self.chrom.autoscale()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._update_status(
            f"{len(traces)} trace(s) on the chromatogram · {mode} mode"
            + (f" · active channel: {self.active_ref.label}" if self.active_ref else "")
        )

    def _on_chrom_click(self, key: str, rt: float) -> None:
        self._activate_trace_key(key)
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            self._update_status("Pick an active channel to see the spectrum.")
            return
        self._show_scan(channel.scan_at_rt(rt))

    def _on_chrom_range(self, key: str, rt0: float, rt1: float) -> None:
        self._activate_trace_key(key)
        if self.active_ref is None or self.active_ref.channel is None:
            return
        self._show_average(rt0, rt1)
        self._report_integration(rt0, rt1)

    def _on_chrom_dragging(self, key: str, rt0: float, rt1: float) -> None:
        """
        Live preview while the selection is being dragged or resized: the
        spectrum follows the highlight instead of waiting for the mouse to be
        released.
        """
        if self.active_ref is None or self.active_ref.channel is None:
            return
        self._show_average(rt0, rt1, live=True)

    def _report_integration(self, rt0: float, rt1: float) -> None:
        traces = [t for t in self.chrom.traces if t.source is not None]
        if not traces:
            return
        target = next(
            (t for t in traces
             if self.active_ref and t.source is self.active_ref.channel),
            traces[0],
        )
        conditioned = self.chrom.conditioned(target.key)
        x, y = conditioned if conditioned else (target.x, target.y)
        stats = integrate(x, y, rt0, rt1)
        snr = signal_to_noise(x, y, rt0, rt1)
        self._update_status(
            f"{target.label} · {rt0:.3f}–{rt1:.3f} min · "
            f"area {stats['area']:,.0f} · height {stats['height']:,.0f} · "
            f"apex {stats['apex_rt']:.3f} min · S/N ≈ {snr:.0f} · "
            f"{stats['n_points']} scans"
        )

    # -------------------------------------------------------------- background #
    def _set_background(self) -> None:
        selection = self.chrom.selected_range()
        if selection is None:
            self._update_status(
                "Select the blank range on the chromatogram (Shift + drag) "
                "before setting the background."
            )
            return
        self.chrom.set_background_range(*selection)

    def _clear_background(self) -> None:
        self.chrom.clear_background_range()

    def _on_background_changed(self) -> None:
        self._background_cache.clear()
        window = self.chrom.background_range()
        if window is None:
            self.bg_label.setText("")
            self._update_status("Background subtraction off.")
        else:
            self.bg_label.setText(f"background {window[0]:.2f}–{window[1]:.2f} min")
            self._update_status(
                f"Background set at {window[0]:.3f}–{window[1]:.3f} min; "
                "new spectra come out with it subtracted."
            )

    def _background_spectrum(self, channel: Channel, window=None):
        """The blank to subtract: the pane's window, or one asked for.

        A pin carries the window it was made with, so restoring one has to
        be able to say which blank rather than take whatever the
        chromatogram is set to now.
        """
        window = window if window is not None else self.chrom.background_range()
        if window is None:
            return None
        key = (id(channel), round(window[0], 5), round(window[1], 5))
        if key not in self._background_cache:
            self._background_cache[key] = channel.spectrum_rt_range(*window)
        return self._background_cache[key]

    def _apply_background(self, channel: Channel, mz: np.ndarray,
                          intensity: np.ndarray,
                          window=None) -> tuple[np.ndarray, bool]:
        """
        Subtract the average blank spectrum. In profile data the m/z grids of
        the spectrum and of the blank do not line up, so the blank is
        interpolated onto the spectrum's grid before subtraction.
        """
        background = self._background_spectrum(channel, window)
        if background is None:
            return intensity, False
        bmz, bi = background
        if bmz.size < 2 or mz.size == 0:
            return intensity, False
        interpolated = np.interp(mz, bmz, bi, left=0.0, right=0.0)
        return np.clip(intensity - interpolated, 0.0, None), True

    # ---------------------------------------------------------------- spectrum #
    def _recalibrate_mz(self, mz, entry: SampleEntry | None = None):
        """
        The spectrum's m/z axis with this injection's correction applied.

        Returns the axis and the words for the title. The title has to say so:
        a mass axis that has been moved and does not admit it is the one thing
        worse than a mass axis that is wrong — and it says what the correction
        stood on, since "recalibrated −5.2 ppm" from one measurement and from
        four are not the same claim.
        """
        if entry is None:
            entry = self.active_ref.entry if self.active_ref else None
        correction = (self.session.correction_for(entry.key)
                      if entry is not None else None)
        if correction is None or mz.size == 0:
            return mz, ""
        middle = float(np.median(mz))
        said = f" · recalibrated {float(correction.ppm_at(middle)):+.1f} ppm"
        count = len(correction.lock_masses)
        if count:
            said += f" from {count} {correction.plural}"
        return correction.apply(mz), said

    def _fit_infusion_axis(self, mz, intensity,
                           entry: SampleEntry | None = None) -> None:
        """
        Fit this infusion's axis from its own precursor ladder, once.

        Called with the average **as the instrument read it**, before
        `_recalibrate_mz` moves it: a correction cannot be fitted from an
        axis that has already been corrected. The result — the refusals
        included — goes on `session.mass_corrections`, which is where every
        correction in this program lives, so the extraction, the report and
        the mass-drift panel's table need nothing new to see it. Fitting is
        skipped when the key already has one; the drift panel clears them
        when the batch changes.
        """
        if entry is None:
            entry = self.active_ref.entry if self.active_ref else None
        channel = self.active_ref.channel if self.active_ref else None
        if entry is None or channel is None:
            return
        from ..infusion_report import fit_axis

        try:
            fit_axis(self.session, entry, channel, spectrum=(mz, intensity))
        except Exception:
            # a reader that cannot say, a formula that cannot be parsed: the
            # spectrum is still worth drawing, uncorrected
            pass

    def _recipe(self, channel, scan: int | None = None,
                rt0: float | None = None, rt1: float | None = None,
                whole_run: bool = False, subtracted: bool = False,
                label: str = "", colour: str = "") -> SpectrumRecipe:
        """
        How the spectrum being drawn was made.

        Kept beside the trace rather than derived afterwards: by the time a
        spectrum is pinned the pane has only its points and its title, and
        neither says which scan of which channel of which sample they came
        from. The background window goes in only when it actually changed
        the spectrum — a window set on the chromatogram after the fact would
        otherwise be recorded as though it had been subtracted.
        """
        entry = self.active_ref.entry if self.active_ref else None
        window = self.chrom.background_range() if subtracted else None
        return SpectrumRecipe(
            sample_key=entry.key if entry is not None else "",
            channel=getattr(channel, "index", None),
            scan=None if scan is None else int(scan),
            rt0=None if rt0 is None else float(rt0),
            rt1=None if rt1 is None else float(rt1),
            whole_run=bool(whole_run),
            background=(float(window[0]), float(window[1])) if window else None,
            label=label, colour=colour)

    def _show_scan(self, scan: int) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        self.current_scan = int(np.clip(scan, 0, max(channel.info.n_scans - 1, 0)))
        try:
            mz, intensity = channel.spectrum(self.current_scan)
        except Exception as exc:
            self._spectrum_unreadable(exc)
            return
        intensity, subtracted = self._apply_background(channel, mz, intensity)
        rt = channel.rt_at_scan(self.current_scan)
        # the difference is taken before the mass axis is corrected, so that
        # one correction moves the pair together rather than sliding the
        # scan against the average it is being compared with
        pair = (self._delta_from_average(channel, mz, intensity)
                if self.act_delta.isChecked() else None)
        mz, recalibrated = self._recalibrate_mz(mz)
        title = (
            f"{self.active_ref.label} · scan {self.current_scan + 1}"
            f"/{channel.info.n_scans} · RT {rt:.3f} min"
            + (" · Δ from the run average" if pair is not None else "")
            + (" · background subtracted" if subtracted else "")
            + recalibrated
        )
        # the title is the recipe's label, so a pin made from this spectrum
        # carries the same words in the legend as the pane had over it
        self._live_recipe = self._recipe(channel, scan=self.current_scan,
                                         subtracted=subtracted, label=title)
        if pair is None:
            drawn = [Trace("spec", "spectrum", mz, intensity, "#1f77b4",
                           channel, self._live_recipe)]
        else:
            difference, average = pair
            # the difference keeps the "spec" key: it is what this pane is
            # showing, and every panel that reads the first trace should read
            # what is on screen rather than a spectrum that is not
            drawn = [
                Trace("spec", f"scan {self.current_scan + 1} − run average",
                      mz, difference, "#1f77b4", channel, self._live_recipe),
                Trace("avg", "run average", mz, average, "#d62728", channel),
            ]
        self.spectrum.set_traces(self._with_pins(drawn))
        # a film whose axes jump every frame is a flicker rather than a film:
        # while Play is running the scale is left where it was, so what moves
        # on screen is the data. Every other way of reaching a scan rescales.
        if not self.contour_view.playing:
            self.spectrum.autoscale()
        self.spectrum.set_title(title)
        self.scan_spin.blockSignals(True)
        self.scan_spin.setValue(self.current_scan + 1)
        self.scan_spin.blockSignals(False)
        self.rt_label.setText(f"RT {rt:.3f} min")
        self.chrom.mark(rt)
        # the film's cursor follows whatever put a scan on screen — Play, the
        # arrow keys, the spin box or a click on the surface
        self.contour_view.set_current_scan(self.current_scan)
        self.refresh_comparison()
        self._fill_peak_table()

    def include_unstable_scans(self) -> bool:
        """Whether a whole-run average keeps the scans the spray lost."""
        return bool(self.act_unstable.isChecked())

    def _unstable_toggled(self, _checked: bool) -> None:
        """Redraw a whole-run average under the new rule; leave the rest."""
        recipe = self._live_recipe
        if recipe is not None and getattr(recipe, "whole_run", False):
            self.average_whole_run()

    def _show_average(self, rt0: float, rt1: float, live: bool = False,
                      tag: str = "", whole_run: bool = False) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        # a whole-run average is an infusion's spectrum, and an infusion's
        # spray is not steady for the whole of it. `stable_scans` says which
        # scans it was and the average is taken over those alone, unless the
        # Process menu asks otherwise. A range average is a range: the reader
        # picked it, and nothing here second-guesses what it holds.
        mask = None
        try:
            if whole_run:
                # through the cache, since this is the same average the
                # Infusions tab measures and the same file it is measured
                # from: whichever is asked for first pays for it
                averaged = average_spectrum(
                    channel,
                    include_unstable=self.include_unstable_scans(),
                    sample=self.active_ref.entry.sample,
                    cache=self.session.averages,
                    path=str(self.active_ref.entry.path or ""))
                if averaged is None:
                    raise ValueError("the channel has no scans to average")
                mz, intensity, _window, mask = averaged
                if self.include_unstable_scans():
                    mask = None
            else:
                mz, intensity = channel.spectrum_rt_range(rt0, rt1)
        except Exception as exc:
            self._spectrum_unreadable(exc)
            return
        intensity, subtracted = self._apply_background(channel, mz, intensity)
        first, last = channel.scans_in_range(rt0, rt1)
        if whole_run:
            # the whole run averaged is what an infusion's ladder is read
            # from, and this is the one place that has it uncorrected
            self._fit_infusion_axis(mz, intensity)
        mz, recalibrated = self._recalibrate_mz(mz)
        # the scan numbers are what says which part of the run was taken;
        # a whole-run average has no other part to be told from, so the tag
        # replaces them rather than sitting beside them
        scans = f" ({first + 1}–{last + 1})" if not tag else ""
        # a whole-run average says how many scans it kept and where the rest
        # went, because that sentence is the provenance a pinned spectrum, a
        # library record's comment and the report's header all copy from it
        count = (mask.summary() if mask is not None and mask.excluded
                 else f"average of {last - first + 1} scans")
        title = (
            f"{self.active_ref.label} · {count}{tag}{scans} "
            f"· RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min"
            + (" · background subtracted" if subtracted else "")
            + recalibrated
        )
        self._live_recipe = self._recipe(
            channel, rt0=rt0, rt1=rt1, whole_run=whole_run,
            subtracted=subtracted, label=title)
        self.spectrum.set_traces(self._with_pins(
            Trace("spec", "average spectrum", mz, intensity, "#d62728", channel,
                  self._live_recipe)))
        if not live:
            self.spectrum.autoscale()
        self.spectrum.set_title(title)
        self.rt_label.setText(f"RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min")
        self.chrom.mark(None)
        if not live:  # too slow to rebuild on every mouse move of a drag
            self.refresh_comparison()
            self._fill_peak_table()

    def _spectrum_unreadable(self, error: Exception) -> None:
        """
        Say, where the spectrum would be, why there is none.

        A .wiff whose .wiff.scan is not beside it opens, draws its
        chromatograms and throws on the first spectrum. Left to Qt the
        exception went to a console nobody has and the pane stayed as it
        was: nothing scan by scan, nothing for a selected range, and no
        word why — found on a folder where one companion had been renamed
        by hand. The title of the pane is where the eye already is, and
        the entry's own diagnosis names the file that is missing.
        """
        problem = self.active_ref.entry.problem if self.active_ref else ""
        if not problem:
            text = str(error).strip()
            problem = ("the spectrum could not be read: "
                       + (text.splitlines()[0] if text else type(error).__name__))
        # nothing is on screen, so there is no recipe for what is: a stale
        # one would be saved as the live spectrum of a pane showing an error
        self._live_recipe = None
        self.spectrum.set_traces(list(self.pinned_spectra))
        # the pane's title is one line: the diagnosis, not the advice
        self.spectrum.set_title(problem.split(";")[0].split(". ")[0])
        self.spectrum.setToolTip(problem)
        self.rt_label.setText("—")
        self.chrom.mark(None)
        self.refresh_comparison()
        self._fill_peak_table()
        self._update_status(problem)

    def _average_selection(self) -> None:
        selection = self.chrom.selected_range()
        if selection is None:
            self._update_status(
                "Select a range on the chromatogram first (Shift + drag)."
            )
            return
        self._show_average(*selection)
        self._report_integration(*selection)

    def _step_scan(self, delta: int) -> None:
        if self.active_ref and self.active_ref.channel:
            self._show_scan(self.current_scan + delta)

    def _on_scan_spin(self, value: int) -> None:
        self._show_scan(value - 1)

    def _fill_peak_table(self) -> None:
        peaks = self.spectrum.peaks_of_current(max_peaks=60)
        base = peaks[0][1] if peaks else 1.0
        self.peak_table.setRowCount(len(peaks))
        for row, (mz, intensity) in enumerate(peaks):
            for col, text in enumerate(
                (f"{mz:.4f}", f"{intensity:,.0f}", f"{intensity / base * 100:.1f}")
            ):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.peak_table.setItem(row, col, item)

    def _peak_double_clicked(self, row: int, _column: int) -> None:
        item = self.peak_table.item(row, 0)
        if item:
            self.mass_calc.set_measured(float(item.text()))
            self.xic_mz.setText(item.text())
            self._extract_from_form()

    # ------------------------------------------------------------------ XIC -- #
    def _xic_targets(self) -> list[ChannelRef]:
        if self.xic_all_channels.isChecked():
            targets = [r for r in self._checked_refs() if r.channel is not None]
            if targets:
                return targets
        return [self.active_ref] if self.active_ref and self.active_ref.channel else []

    def _extract_from_form(self) -> None:
        text = self.xic_mz.text().replace(";", ",")
        values = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid m/z", f"Not a number: {part}")
                return
        if not values:
            return
        tol = self.xic_tol.value()
        unit = self.xic_unit.currentText()
        for mz in values:
            half = mz * tol * 1e-6 if unit == "ppm" else tol
            self._add_xic(mz - half, mz + half, f"XIC {mz:.4f} ±{tol:g} {unit}")

    def _extract_from_range(self, mz0: float, mz1: float) -> None:
        lo, hi = sorted((mz0, mz1))
        self._add_xic(lo, hi, f"XIC {lo:.4f}–{hi:.4f}")

    def _add_xic(self, mz_lo: float, mz_hi: float, label: str,
                 targets: list[ChannelRef] | None = None) -> None:
        targets = targets if targets is not None else self._xic_targets()
        if not targets:
            self._update_status("Pick an active channel before extracting an XIC.")
            return
        unreadable: list[str] = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for ref in targets:
                try:
                    x, y = ref.channel.xic_range(mz_lo, mz_hi)
                except Exception as exc:
                    unreadable.append(ref.entry.problem
                                      or f"{ref.label}: {_first_line(exc)}")
                    continue
                if x.size == 0:
                    continue
                key = f"xic|{ref.key}|{mz_lo:.5f}|{mz_hi:.5f}"
                if any(d["key"] == key for d in self.xic_defs):
                    continue
                full = f"{ref.label} · {label}"
                self.xic_defs.append(
                    {"key": key, "label": full, "x": x, "y": y, "channel": ref.channel}
                )
                self.xic_list.addItem(full)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.refresh_chromatogram()
        if unreadable:
            self._update_status(unreadable[0])

    def _remove_selected_xic(self) -> None:
        row = self.xic_list.currentRow()
        if 0 <= row < len(self.xic_defs):
            self.xic_defs.pop(row)
            self.xic_list.takeItem(row)
            self.refresh_chromatogram()

    def _clear_xics(self) -> None:
        self.xic_defs.clear()
        self.xic_list.clear()
        self.refresh_chromatogram()

    # ------------------------------------------------------------ components -- #
    def _integrate_component(self, ref: ChannelRef, channel: Channel,
                            component: Component) -> Result:
        mz_lo, mz_hi = component.mass_window()
        mz_text = f"{(mz_lo + mz_hi) / 2:.4f}"
        # the window moves, the reader's arithmetic does not — see
        # quantify.extract_xic
        correction = self.session.correction_for(ref.entry.key)
        if correction is not None:
            mz_lo, mz_hi = (float(correction.undo(mz_lo)),
                            float(correction.undo(mz_hi)))

        def empty(note: str) -> Result:
            return Result(
                component=component.name, sample=ref.alias,
                channel=channel.info.short_label, mz=mz_text,
                rt=component.rt or 0.0, area=0.0, height=0.0, width=0.0,
                snr=0.0, note=note,
            )

        try:
            x, y = channel.xic_range(mz_lo, mz_hi)
        except Exception as exc:
            return empty(ref.entry.problem or _first_line(exc))
        if x.size == 0:
            return empty("no data")

        window = component.rt_window()
        if window is None:
            mask = np.ones(x.size, dtype=bool)
        else:
            mask = (x >= window[0]) & (x <= window[1])
            # Do not fall back to scanning the whole run when the window is not
            # covered: returning a peak from another time would be a wrong
            # result, not an approximate one.
            if mask.sum() < 3:
                return empty(f"channel does not cover {window[0]:.2f}–{window[1]:.2f} min")

        peaks = detect_peaks(x[mask], y[mask], min_relative=0.05, min_snr=3.0)
        if not peaks:
            return empty("no peak above noise")

        peak = peaks[0]
        return Result(
            component=component.name, sample=ref.alias,
            channel=channel.info.short_label, mz=mz_text,
            rt=peak.apex_rt, area=peak.area, height=peak.height,
            width=peak.width, snr=peak.snr,
            start_rt=peak.start_rt, end_rt=peak.end_rt,
        )

    def _extract_components(self, components: list[Component]) -> None:
        if not components:
            self._update_status("No valid component in the list.")
            return
        samples = self._checked_samples()
        if not samples:
            self._update_status("Open at least one file before extracting.")
            return

        total = len(components) * len(samples)
        progress = QtWidgets.QProgressDialog(
            "Extracting and integrating…", "Cancel", 0, total, self
        )
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        results: list[Result] = []
        done = 0
        for ref in samples:
            for component in components:
                if progress.wasCanceled():
                    break
                channel = match_channel(ref.sample, component)
                if channel is None:
                    results.append(Result(
                        component=component.name, sample=ref.alias, channel="—",
                        mz=f"{component.target_mz:.4f}", rt=component.rt or 0.0,
                        area=0.0, height=0.0, width=0.0, snr=0.0,
                        note="no matching channel",
                    ))
                else:
                    results.append(self._integrate_component(ref, channel, component))
                done += 1
                progress.setValue(done)
                QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                break
        progress.setValue(total)

        self.results_panel.set_results(results)
        self.tabs.setCurrentWidget(self._tab_of(self.results_panel))
        found = sum(1 for r in results if r.area > 0)
        self._update_status(
            f"{len(results)} extractions across {len(samples)} sample(s); "
            f"{found} with a detected peak."
        )

    def _show_component(self, component: Component) -> None:
        """Plot one component's XIC across every checked sample."""
        samples = self._checked_samples()
        targets = []
        for ref in samples:
            channel = match_channel(ref.sample, component)
            if channel is not None:
                targets.append(ChannelRef(ref.entry, channel))
        if not targets:
            self._update_status(f"No channel matches {component.name}.")
            return
        mz_lo, mz_hi = component.mass_window()
        self._add_xic(mz_lo, mz_hi,
                      f"{component.name} {component.target_mz:.4f}", targets)
        window = component.rt_window()
        if window:
            self.chrom.set_x_range(*window)

    def _go_to_result(self, result: Result) -> None:
        """Bring the chromatogram to the peak of a results row."""
        if result.end_rt > result.start_rt:
            span = max(result.end_rt - result.start_rt, 0.05)
            self.chrom.set_x_range(result.start_rt - span, result.end_rt + span)
            self.chrom.mark(result.rt)
        self._update_status(
            f"{result.component} · {result.sample} · {result.channel} · "
            f"RT {result.rt:.3f} min · area {result.area:,.0f}"
        )

    # ------------------------------------------------------ chromatogram peaks #
    def _detect_peaks(self) -> None:
        traces = self.chrom.traces
        if not traces:
            self._update_status("Nothing on the chromatogram to integrate.")
            return
        results: list[Result] = []
        markers = []
        for trace in traces:
            conditioned = self.chrom.conditioned(trace.key)
            x, y = conditioned if conditioned else (trace.x, trace.y)
            peaks = detect_peaks(x, y, min_relative=0.05, min_snr=3.0)
            markers.extend(peaks)
            ref = self.refs.get(trace.key)
            sample_name = ref.alias if ref else "—"
            channel_name = (
                trace.source.info.short_label if trace.source is not None else "TIC"
            )
            for peak in peaks:
                results.append(
                    Result(
                        component="(detected)", sample=sample_name,
                        channel=channel_name, mz="—", rt=peak.apex_rt,
                        area=peak.area, height=peak.height, width=peak.width,
                        snr=peak.snr, trace_key=trace.key,
                        start_rt=peak.start_rt, end_rt=peak.end_rt,
                    )
                )
        self.chrom.set_peak_markers(markers)
        self.results_panel.set_results(results)
        self.tabs.setCurrentWidget(self._tab_of(self.results_panel))
        self._update_status(
            f"{len(results)} peak(s) integrated across {len(traces)} trace(s)."
        )

    # ------------------------------------------------------------- chemistry -- #
    def _identify_peak(self, mz: float) -> None:
        """Right-click on a spectrum peak: send it to every chemistry panel."""
        self.mass_calc.set_measured(mz)
        self.formula_panel.set_target(mz)
        self.lipid_panel.set_target(mz)
        self.tabs.setCurrentWidget(self.formula_panel)
        self._update_status(f"m/z {mz:.4f} sent to the formula finder.")

    def _lipid_annotation(self, name: str, formula: str, lm_id: str) -> None:
        """A structure picked in the LIPID MAPS tab feeds the chemistry panels."""
        self.mass_calc.formula_edit.setText(formula)
        self._update_status(f"{name} · {formula} · {lm_id}")

    def _lipid_precursor(self, name: str, formula: str, lm_id: str,
                         adduct: str, mz: float) -> None:
        """
        An ion picked in the LIPID MAPS tab becomes a component.

        This is the reverse of annotation: the compound is known and what is
        wanted is the channel to extract it on. The component carries the
        formula and the LM_ID, so where the mass came from stays on the record.
        """
        method = self.session.method
        if method.by_name(name) is not None:
            self.xic_mz.setText(f"{mz:.4f}")
            self._update_status(
                f"{name} is already in the method — {mz:.4f} put in the "
                "manual XIC box instead.")
            return
        method.components.append(Component(
            name=name, precursor=mz, formula=formula, adduct=adduct,
            lm_id=lm_id, tolerance=method.tolerance, unit=method.unit,
        ))
        self.session.notify_method_changed()
        self.mass_calc.formula_edit.setText(formula)
        self.xic_mz.setText(f"{mz:.4f}")
        self._update_status(
            f"{name} {adduct} — m/z {mz:.4f} added to the method "
            f"({len(method.components)} component(s)).")

    def explain_spectrum(self) -> None:
        """Send the spectrum on screen to be scored against LIPID MAPS."""
        current = self._current_spectrum()
        if current is None:
            self._update_status("Show a spectrum first.")
            return
        mz, intensity = current
        if not self.act_centroid.isChecked():
            # centroiding what is already sticks merges neighbours and moves
            # the masses, which is worse than not centroiding at all
            mz, intensity = centroid_spectrum(mz, intensity)
        precursor, polarity = None, ""
        if self.active_ref is not None and self.active_ref.channel is not None:
            info = self.active_ref.channel.info
            precursor = info.precursor
            # the polarity goes with the precursor: which adduct that number
            # is depends on the sign the channel was acquired at, and the
            # sign is a fact about the acquisition rather than a choice
            polarity = str(getattr(info, "polarity", "") or "")
        self.lipid_panel.set_spectrum(mz, intensity, precursor, polarity,
                                      self._survey_spectrum(precursor),
                                      recalibration=self._axis_sentence())
        # what the method says this channel is: the unified Explain button
        # fills its name and formula from the component whose precursor the
        # channel isolates, so a spectrum of a declared standard needs
        # nothing typed at all
        self.lipid_panel.set_components(self.session.method.components)
        self.show_panel_named("LIPID MAPS")
        self.lipid_panel.explain_spectrum()

    def _survey_spectrum(self, precursor: float | None):
        """
        The same acquisition's survey over the same range as the spectrum.

        The product-ion scan cannot say which adduct its precursor is: Q1
        passed one mass and threw the isotopes away with everything else. The
        survey has both — the exact mass and the pattern — and reading it
        over the same scans is what makes it the same moment of the same run
        rather than a different compound eluting.

        None where the method has no full-scan channel covering that mass,
        which is the ordinary case on a product-ion-only acquisition and is
        what the panel prints instead of a confirmation.
        """
        ref = self.active_ref
        sample = getattr(ref, "entry", None)
        sample = getattr(sample, "sample", None)
        if sample is None or not precursor:
            return None
        channel = getattr(ref, "channel", None)
        if channel is None or channel.info.is_ms1:
            return None            # the spectrum on screen is the survey
        rt0, rt1 = self._shown_range(channel)
        survey = survey_channel(sample, float(precursor), (rt0 + rt1) / 2.0)
        if survey is None:
            return None
        try:
            return survey.spectrum_rt_range(rt0, rt1)
        except Exception:          # a .wiff whose .wiff.scan is missing
            return None

    def _shown_range(self, channel) -> tuple[float, float]:
        """The retention times the spectrum on screen was made from."""
        recipe = getattr(self, "_live_recipe", None)
        if recipe is not None and recipe.rt0 is not None \
                and recipe.rt1 is not None:
            return float(recipe.rt0), float(recipe.rt1)
        if recipe is not None and recipe.scan is not None:
            rt = float(channel.rt_at_scan(int(recipe.scan)))
            return rt, rt
        times = channel.rt
        if times.size == 0:
            return 0.0, 0.0
        return float(times[0]), float(times[-1])

    def _axis_sentence(self) -> str:
        """
        What the mass axis of the spectrum on screen has had done to it.

        Empty when nothing was applied, which is the ordinary case; a
        sentence naming the offset, what it stood on and the strongest
        rung's error raw and corrected when something was. It goes into the
        basis line of the explanation, because a prediction scored at 5 ppm
        against an axis that was moved by five is a different claim from one
        scored against the instrument's own numbers.
        """
        entry = self.active_ref.entry if self.active_ref else None
        correction = (self.session.correction_for(entry.key)
                      if entry is not None else None)
        return "" if correction is None else correction.basis_sentence()

    def _library_spectrum(self):
        """
        The spectrum on screen as the library panel wants it.

        Centroided sticks, the active channel's precursor, and a mapping of
        where they came from. The last is for the panel's *Add spectrum to
        library…*: a record has to say which file, sample, channel and scans
        it was made from, and the Explorer is the only place that knows. The
        pane's own title already reads "sample · channel · average of n scans
        (a–b) · RT x–y", which is exactly the provenance a record wants, so
        it is passed as written rather than assembled a second time here.
        """
        current = self._current_spectrum()
        if current is None:
            self._update_status("Show a spectrum first.")
            return None
        mz, intensity = current
        if not self.act_centroid.isChecked():
            mz, intensity = centroid_spectrum(mz, intensity)
        precursor = None
        context = {"title": self.spectrum.title,
                   # whether the adduct on the record was measured or assumed
                   "adduct": self.lipid_panel.adduct_provenance,
                   # a record written from a corrected axis and one written
                   # from the instrument's are different measurements
                   "recalibration": self._axis_sentence()}
        if self.active_ref is not None:
            context["file"] = self.active_ref.filename
            context["sample"] = self.active_ref.alias
            # the acquisition's own date, for the record's Acquired field:
            # the day this was measured, not the day it is being written
            context["acquired"] = str(
                getattr(self.active_ref.sample, "acquisition_time", "") or "")
            channel = self.active_ref.channel
            if channel is not None:
                info = channel.info
                precursor = info.precursor
                context["channel"] = info.label
                context["polarity"] = info.polarity
                context["collision_energy"] = info.collision_energy
            # a record made off an infusion gets the acquisition's own floor
            # as well as the relative one: 1% of a base peak of a hundred
            # counts is one count, which on that average is the background
            floor = self.noise_floor(self.active_ref)
            if floor is not None and floor.measured:
                context["noise_floor"] = float(floor.value)
        # the isotopic purity the Explain tab last measured, if any. It has
        # to travel with the record because it cannot be recovered from one:
        # the envelope it was solved from is under the floor the record's
        # peaks are kept at
        measured = getattr(self.lipid_panel, "purity", None)
        if measured is not None:
            context["isotopic_purity"] = measured.field()
        return mz, intensity, precursor, context

    def _lipid_fragment(self, name: str, lm_id: str, route: str,
                        mz: float) -> None:
        """
        A predicted fragment goes to the manual XIC, not into the method.

        A precursor from the database is arithmetic on a known formula; a
        fragment is a candidate. Extracting it against a real sample is how it
        earns a place in a method, so that is what this offers.
        """
        self.xic_mz.setText(f"{mz:.4f}")
        self.show_panel_named("Manual XIC")
        self._update_status(
            f"{name}: candidate fragment {mz:.4f} ({route}) — extract it to "
            "see whether the sample agrees.")

    def _send_to_finder(self, mz: float, adduct: str) -> None:
        self.formula_panel.set_target(mz, adduct)
        self.tabs.setCurrentWidget(self.formula_panel)

    # -- pinned spectra --------------------------------------------------------- #
    #: colours for the spectra held for comparison; the live one stays blue
    PIN_COLOURS = ("#e08a1e", "#2ca02c", "#9467bd", "#8c564b", "#17becf", "#7f7f7f")

    def _with_pins(self, current: "Trace | list[Trace]") -> list[Trace]:
        """The live spectrum first, then whatever was pinned: the first trace
        is what every panel reads, and Mirror flips the odd ones.

        More than one live trace when the Δ mode is on: the difference and,
        second, the average it was taken from, which is the one Mirror draws
        downwards. The pins then start at the third, so Δ and pins together
        flip the pins the other way up — the price of drawing the pair
        through the switch that already exists rather than a second one.
        """
        live = [current] if isinstance(current, Trace) else list(current)
        return live + list(getattr(self, "_pinned", []))

    def pin_spectrum(self) -> None:
        """
        Hold the spectrum on screen so the next one draws over it.

        The comparison a chromatogram overlay gives for free — sample against
        blank, injection against injection — needs the spectrum pane to keep
        one while another is shown. The pinned copy carries the pane's title
        as its legend entry, so the sample, channel and scan it came from
        stay readable after the live spectrum has moved on.
        """
        traces = self.spectrum.traces
        live = next((t for t in traces if t.key == "spec"), None)
        if live is None:
            self._update_status("Show a spectrum first.")
            return
        pinned = getattr(self, "_pinned", [])
        colour = self.PIN_COLOURS[len(pinned) % len(self.PIN_COLOURS)]
        label = self.spectrum.title or live.label
        # the recipe travels with the copy, so the project can save how this
        # spectrum was made instead of its hundred thousand points
        recipe = getattr(live, "recipe", None) or self._live_recipe
        if recipe is not None:
            recipe = replace(recipe, label=label, colour=colour)
        pinned.append(Trace(f"pin{len(pinned) + 1}", label, live.x.copy(),
                            live.y.copy(), colour, live.source, recipe))
        self._pinned = pinned
        self.spectrum.set_traces(self._with_pins(live))
        self.spectrum.set_legend_visible(True)
        self.spectrum.autoscale()
        self.act_unpin.setEnabled(True)
        self.act_exp_cmp.setEnabled(True)
        self._show_pin_recipes()
        self.refresh_comparison()
        self._update_status(
            f"{len(pinned)} spectrum(s) pinned. The next spectrum draws over "
            f"them; Normalise puts them on one scale, Mirror draws every other "
            f"one downwards.")

    def unpin_spectra(self) -> None:
        self._pinned = []
        self._show_pin_recipes()
        traces = self.spectrum.traces
        live = next((t for t in traces if t.key == "spec"), None)
        self.spectrum.set_traces([live] if live is not None else [])
        self.spectrum.autoscale()
        self.act_unpin.setEnabled(False)
        self.act_exp_cmp.setEnabled(False)
        self.refresh_comparison()
        self._update_status("Pinned spectra cleared.")

    @property
    def pinned_spectra(self) -> list[Trace]:
        return list(getattr(self, "_pinned", []))

    #: what a restored pin says for itself when its file is not there
    PIN_MISSING = "not available: file missing"

    def _show_pin_recipes(self) -> None:
        """The pins and how each was made, under the pointer."""
        lines = []
        for trace in self.pinned_spectra:
            recipe = getattr(trace, "recipe", None)
            lines.append(f"{trace.label}\n    {recipe.describe()}"
                         if recipe is not None else trace.label)
        self.spectrum.setToolTip(
            "Pinned spectra:\n" + "\n".join(lines) if lines else "")

    # -- the pane as the project saves it --------------------------------- #
    def view_state(self) -> dict:
        """
        What this pane is showing, small enough to go into a project.

        Recipes, not points: which sample, channel and scan or range each
        pinned spectrum was made from, plus the label floor and the three
        switches that decide how the comparison reads. `Session.to_dict`
        asks for it — see `Session.view_source` — so every path that saves a
        project saves this with it.
        """
        pins = []
        for trace in self.pinned_spectra:
            recipe = getattr(trace, "recipe", None)
            if recipe is not None:
                pins.append(recipe.to_dict())
        return {
            "label_floor": float(self.spectrum.label_floor),
            "normalise": bool(self.act_norm.isChecked()),
            "mirror": bool(self.act_mirror.isChecked()),
            "centroid": bool(self.act_centroid.isChecked()),
            # which scans a whole-run average is of: a project reopened
            # under the other setting would show a different spectrum from
            # the one it was saved with, and its pins are recipes rather
            # than points, so this has to travel with them
            "include_unstable": bool(self.act_unstable.isChecked()),
            "live": (self._live_recipe.to_dict()
                     if self._live_recipe is not None else None),
            "pins": pins,
        }

    def restore_view(self, view: dict | None = None) -> None:
        """
        Put a saved view back: the pins, the floor, the switches, the
        spectrum that was on screen, and the comparison the report prints.

        The order is the whole of it. The pins are rebuilt first, because
        the live spectrum is drawn over them and `_with_pins` reads the list
        as it stands; the live recipe is shown last, which is also what
        refreshes the comparison. Every spectrum is read from its file
        again, which is why this waits for `sigViewRestored` — emitted after
        `load_project` has opened the samples — rather than listening for
        the samples themselves.
        """
        view = self.session.view if view is None else view
        if not view:
            return
        floor = view.get("label_floor")
        if floor:
            self.floor_spin.blockSignals(True)
            self.floor_spin.setValue(float(floor) * 100.0)
            self.floor_spin.blockSignals(False)
            # the pane exactly, the spin box to the two decimals it shows: a
            # floor dragged to 0.437% is not the same as one typed
            self.spectrum.set_label_floor(float(floor))
        for action, key in ((self.act_norm, "normalise"),
                            (self.act_mirror, "mirror"),
                            (self.act_centroid, "centroid")):
            if key in view:
                action.setChecked(bool(view[key]))
        if "include_unstable" in view:
            # set with its signal blocked: the pins and the live spectrum are
            # read from the file further down and a toggle that redrew now
            # would read the run twice. An older project has no key at all
            # and keeps whatever the preference is.
            self.act_unstable.blockSignals(True)
            self.act_unstable.setChecked(bool(view["include_unstable"]))
            self.act_unstable.blockSignals(False)

        pins: list[Trace] = []
        for index, row in enumerate(view.get("pins") or []):
            recipe = SpectrumRecipe.from_dict(row)
            if recipe is None:
                continue
            colour = recipe.colour or self.PIN_COLOURS[index % len(self.PIN_COLOURS)]
            key = f"pin{index + 1}"
            read = self._read_recipe(recipe)
            if read is None:
                # a pin nobody can read stays in the list saying so: a
                # comparison that quietly came back with one spectrum fewer
                # than it was saved with is worse than one that is short and
                # says which spectrum is missing
                label = f"{recipe.label or recipe.describe()} — {self.PIN_MISSING}"
                empty = np.zeros(0, dtype=np.float64)
                pins.append(Trace(key, label, empty, empty.copy(), colour,
                                  None, recipe))
                self._update_status(f"{recipe.label or recipe.describe()}: "
                                    f"{self.PIN_MISSING}")
            else:
                mz, intensity, channel = read
                pins.append(Trace(key, recipe.label or recipe.describe(),
                                  mz, intensity, colour, channel, recipe))
        self._pinned = pins
        self.act_unpin.setEnabled(bool(pins))
        self.act_exp_cmp.setEnabled(bool(pins))
        if pins:
            self.spectrum.set_legend_visible(True)
        self._show_pin_recipes()

        live = SpectrumRecipe.from_dict(view.get("live"))
        if live is None or not self._show_recipe(live):
            self.spectrum.set_traces(list(self.pinned_spectra))
            self.spectrum.autoscale()
            self.refresh_comparison()

    def _ref_for(self, recipe: SpectrumRecipe) -> ChannelRef | None:
        """The tree node a recipe names, if its sample is open."""
        if not recipe.sample_key or recipe.channel is None:
            return None
        return self.refs.get(f"{recipe.sample_key}|{recipe.channel}")

    def _read_recipe(self, recipe: SpectrumRecipe):
        """
        Make the spectrum a recipe describes again, off the file.

        Returns the points and the channel they came from, or None when the
        sample is not open, the channel is not there any more, or the reader
        cannot give the scans — a `.wiff` without its `.wiff.scan` among
        them. The conditioning is the same as the pane's: the recipe's own
        background window, and this injection's mass correction, which is
        the injection the recipe names and not whichever is active now.
        """
        ref = self._ref_for(recipe)
        channel = ref.channel if ref is not None else None
        if channel is None:
            return None
        try:
            if recipe.scan is not None:
                mz, intensity = channel.spectrum(recipe.scan)
            else:
                window = self._range_of(recipe, channel)
                if window is None:
                    return None
                # a pin of a whole run is rebuilt under the rule in force
                # now, the same as the live spectrum: the recipe says every
                # scan, and which of those the spray was steady for is a
                # measurement on the file rather than something to store
                if recipe.whole_run and not self.include_unstable_scans():
                    averaged = average_spectrum(
                        channel, sample=ref.entry.sample,
                        cache=self.session.averages,
                        path=str(ref.entry.path or ""))
                    if averaged is None:
                        return None
                    mz, intensity = averaged[0], averaged[1]
                else:
                    mz, intensity = channel.spectrum_rt_range(*window)
        except Exception:
            return None
        intensity, _ = self._apply_background(channel, mz, intensity,
                                              window=recipe.background)
        mz, _ = self._recalibrate_mz(mz, ref.entry)
        return mz, intensity, channel

    @staticmethod
    def _range_of(recipe: SpectrumRecipe, channel):
        """The stretch of time a recipe covers, in this channel's own axis.

        A whole-run average is re-measured rather than restored from the
        bounds it was made with: it means every scan, and that is what it
        has to mean again."""
        if recipe.whole_run:
            window = run_range(channel)
            if window is not None:
                return window
        if recipe.rt0 is None or recipe.rt1 is None:
            return None
        return recipe.rt0, recipe.rt1

    def _show_recipe(self, recipe: SpectrumRecipe) -> bool:
        """Draw the spectrum a recipe names as the live one; did it work?"""
        ref = self._ref_for(recipe)
        if ref is None or not self._make_active(ref.key):
            return False
        if recipe.background:
            self.chrom.set_background_range(*recipe.background)
        if recipe.scan is not None:
            self._show_scan(recipe.scan)
        else:
            window = self._range_of(recipe, ref.channel)
            if window is None:
                return False
            self._show_average(*window, whole_run=recipe.whole_run,
                               tag=" (infusion)" if recipe.whole_run else "")
        return True

    def _make_active(self, key: str) -> bool:
        """
        Make one channel the active one, ticking it in the tree if it is not.

        The active list holds the checked channels, so a project that was
        saved looking at a channel nobody had ticked — which is what
        happens when a pin is made and the tree is tidied afterwards —
        would have nowhere to put it.
        """
        if key not in self.refs:
            return False
        if self.active_combo.findData(key) < 0:
            item = self._tree_items().get(key)
            if item is None:
                return False
            self.tree.blockSignals(True)
            item.setCheckState(0, QtCore.Qt.CheckState.Checked)
            self.tree.blockSignals(False)
            self._rebuild_active_combo()
            self.refresh_chromatogram()
        index = self.active_combo.findData(key)
        if index < 0:
            return False
        self.active_combo.blockSignals(True)
        self.active_combo.setCurrentIndex(index)
        self.active_combo.blockSignals(False)
        self._sync_active_ref()
        return True

    def refresh_comparison(self) -> None:
        """
        Keep the session's comparison of spectra in step with this pane.

        The rule is that the report prints what the pane shows: pinning a
        spectrum starts the comparison, changing the live spectrum or either
        of the two switches refreshes it, and unpinning drops it. The
        alternative — a snapshot taken by a button — means a report that
        disagrees with the window and no way of telling from either which
        one is stale, and the argument for it (that browsing away from the
        pinned spectrum spoils the comparison) is answered by the pane
        showing exactly the same thing.

        A comparison is a copy of the conditioned traces, so it survives the
        live spectrum moving on, and it costs nothing at all while nothing
        is pinned.
        """
        session = getattr(self, "session", None)
        if session is None:
            return
        if not self.pinned_spectra:
            session.spectra_comparison = None
            return
        from ..spectra_compare import from_traces

        traces = self.spectrum.traces
        if not traces:
            session.spectra_comparison = None
            return
        # the live trace is named by the pane's title, the way a pin is
        labelled = []
        for index, trace in enumerate(traces):
            label = (self.spectrum.title or trace.label) if index == 0 else trace.label
            labelled.append(Trace(trace.key, label, trace.x, trace.y,
                                  trace.colour, trace.source))
        session.spectra_comparison = from_traces(
            labelled, title=self._comparison_title(),
            normalise=self.act_norm.isChecked(),
            mirror=self.act_mirror.isChecked(),
            centroid=self.spectrum.centroided,
            condition=self.spectrum.condition,
            label_floor=self.spectrum.label_floor)

    def _comparison_title(self) -> str:
        """What the picture is called: the samples it holds, once each."""
        names = []
        for trace in self.spectrum.traces:
            name = (trace.label or "").split(" · ")[0].strip()
            if name and name not in names:
                names.append(name)
        if len(names) > 1:
            return " against ".join(names[:2]) + (
                f" and {len(names) - 2} more" if len(names) > 2 else "")
        return "Compared spectra"

    def _export_comparison(self) -> None:
        """
        The comparison as an image, at print size rather than screen size.

        PNG is written at twice the drawing's own size, which is what makes
        the type and the sticks come out sharp on paper; SVG is the same
        drawing as vectors for a figure that will be resized. The theme is
        asked for here, beside the file name, because it is a property of
        where the figure is going and not of the window it came from — and
        it is remembered for the next one.
        """
        self.refresh_comparison()
        comparison = getattr(self.session, "spectra_comparison", None)
        if comparison is None or not comparison.stands:
            self._update_status("Pin a spectrum first: a comparison needs two.")
            return
        from .export_theme import add_theme_box, chosen_theme, remember
        from .help_window import describe

        dialog = QtWidgets.QFileDialog(
            self, "Export comparison",
            os.path.join(self._last_dir(), "compared-spectra.png"),
            "PNG image, 2× for print (*.png);;SVG image (*.svg)")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        theme_box = add_theme_box(dialog, self.settings)
        describe(dialog, "chromatograms-and-spectra")
        wanted = dialog.exec() and dialog.selectedFiles()
        path = dialog.selectedFiles()[0] if wanted else ""
        svg = "svg" in dialog.selectedNameFilter().lower()
        theme = chosen_theme(theme_box)
        dialog.deleteLater()
        if not wanted:
            return
        remember(theme, self.settings)
        self._write_comparison(path, svg=svg, theme=theme)

    def _write_comparison(self, path: str, svg: bool = False,
                          theme: str = "paper") -> str | None:
        """Write the current comparison to `path`, as SVG or as a 2× PNG."""
        comparison = getattr(self.session, "spectra_comparison", None)
        if comparison is None:
            return None
        from ..spectra_compare import (PALETTE_NAMES, PRINT_SCALE,
                                       palette_named, render_png, render_svg)

        palette = palette_named(theme)
        svg = svg or path.lower().endswith(".svg")
        wanted = ".svg" if svg else ".png"
        if not path.lower().endswith(wanted):
            path += wanted
        self._remember_dir(path)
        try:
            if svg:
                render_svg(comparison, path, palette=palette)
            else:
                render_png(comparison, path, scale=PRINT_SCALE,
                           palette=palette)
        except Exception as exc:                       # a full disk, a bad path
            self._update_status(f"Could not write {path}: {exc}")
            return None
        self._update_status(
            f"{len(comparison.traces)} spectra written to {path}"
            f", {PALETTE_NAMES[palette.name].lower()}"
            + ("" if svg else f", at {PRINT_SCALE:g}× for print"))
        return path

    def _current_spectrum(self) -> tuple[np.ndarray, np.ndarray] | None:
        traces = self.spectrum.traces
        if not traces:
            return None
        return self.spectrum.condition(traces[0])

    def _run_formula_search(self, params: dict) -> None:
        adduct = ADDUCTS_BY_NAME[params["adduct"]]
        neutral = adduct.neutral_mass(params["mz"])
        if neutral <= 0:
            self.formula_panel.set_results([], "That m/z is below the adduct mass.")
            return

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            hits = find_formulas(
                neutral, params["tolerance"], params["unit"],
                ranges=params["ranges"], rdbe_range=params["rdbe_range"],
                even_electron=params["even_electron"],
                golden_rules=params["golden_rules"],
            )
            for hit in hits:
                hit.mz = adduct.mz(hit.neutral_mass)

            note = f"{len(hits)} candidate(s) within ±{params['tolerance']:g} {params['unit']}"
            spectrum = self._current_spectrum()
            if params["use_isotopes"] and hits and spectrum is not None:
                mz, intensity = spectrum
                if has_isotope_satellites(mz, intensity, params["mz"], adduct.charge):
                    hits = rank_by_isotope_pattern(hits, mz, intensity, adduct)
                    note += ", ranked by isotope pattern"
                else:
                    # Nothing to score against: say so rather than showing a
                    # column of meaningless numbers, and point at the scan that
                    # does carry the pattern.
                    note += ("; this spectrum has no isotope satellites for that "
                             "ion, so candidates are ranked by mass error — a "
                             "product-ion scan isolates the monoisotopic "
                             "precursor, so use the TOF MS survey channel to "
                             "bring the pattern into play")
            elif params["use_isotopes"] and spectrum is None:
                note += "; no spectrum on screen, so ranked by mass error only"
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.formula_panel.set_results(hits, note)
        if hits:
            self._overlay_hit(hits[0])
        self._update_status(note)

    def _overlay_hit(self, hit) -> None:
        adduct = ADDUCTS_BY_NAME[self.formula_panel.adduct_combo.currentText()]
        pattern = isotope_pattern(hit.counts, adduct, min_abundance=0.005,
                                  max_peaks=6)
        self.spectrum.set_overlay(pattern, f"{hit.formula} {adduct.name}")
        self._update_status(
            f"{hit.formula} · m/z {hit.mz:.5f} · {hit.error_ppm:+.2f} ppm · "
            f"RDBE {hit.rdbe:g}"
            + (f" · isotope match {hit.isotope_score * 100:.0f}%"
               if hit.isotope_score else "")
        )

    def _overlay_pattern(self, pattern: list, label: str) -> None:
        self.spectrum.set_overlay(pattern, label)
        self._update_status(f"Theoretical pattern of {label} overlaid.")

    # ------------------------------------------------------------------ misc -- #
    def _set_select_mode(self, enabled: bool) -> None:
        self.chrom.set_select_mode(enabled)
        self.spectrum.set_select_mode(enabled)

    def _set_normalised(self, enabled: bool) -> None:
        self.chrom.set_normalised(enabled)
        self.spectrum.set_normalised(enabled)
        self.refresh_comparison()

    def _set_mirror(self, enabled: bool) -> None:
        self.chrom.set_mirror(enabled)
        self.spectrum.set_mirror(enabled)
        self.refresh_comparison()

    def _set_smoothing(self, sigma: float) -> None:
        self.chrom.set_smoothing(sigma)
        self.spectrum.set_smoothing(sigma)

    def _set_offsets(self, *_args) -> None:
        dx, dy = self.offset_x_spin.value(), self.offset_y_spin.value()
        self.chrom.set_offsets(dx, dy)
        self.spectrum.set_offsets(0.0, dy)  # shifting a spectrum in m/z is misleading

    def _set_overview(self, enabled: bool) -> None:
        self.chrom.set_overview_visible(enabled)
        self.spectrum.set_overview_visible(enabled)

    def _set_label_floor(self, percent: float) -> None:
        """The spin box moved: take the handle with it, and the print."""
        self.spectrum.set_label_floor(float(percent) / 100.0)
        self._floor_into_comparison()

    def _label_floor_moved(self, fraction: float) -> None:
        """The handle moved: take the spin box with it, and the print.

        Blocked while it is set, or the spin box's own signal comes back
        here as a second `set_label_floor` and a drag lands on the rounded
        value rather than where the mouse is.
        """
        self.floor_spin.blockSignals(True)
        try:
            self.floor_spin.setValue(float(fraction) * 100.0)
        finally:
            self.floor_spin.blockSignals(False)
        self._floor_into_comparison()

    def _floor_into_comparison(self) -> None:
        """
        Keep the print's floor in step with the pane's.

        The field is set rather than the comparison rebuilt: `from_traces`
        copies every point of every trace, and this runs on every mouse move
        of a drag. A comparison that does not exist yet is left alone —
        pinning builds one, and it reads the floor as it stands.
        """
        comparison = getattr(getattr(self, "session", None),
                             "spectra_comparison", None)
        if comparison is not None:
            comparison.label_floor = self.spectrum.label_floor

    def _set_relative_labels(self, enabled: bool) -> None:
        self.chrom.set_relative_labels(enabled)
        self.spectrum.set_relative_labels(enabled)

    def _set_centroid(self, enabled: bool) -> None:
        self.spectrum.set_centroid(enabled)
        self.refresh_comparison()
        self._fill_peak_table()

    def _add_marker(self) -> None:
        """Drop a marker at the tallest peak of the current spectrum selection."""
        selection = self.spectrum.selected_range()
        traces = self.spectrum.traces
        if not traces:
            self._update_status("Show a spectrum before adding a marker.")
            return
        if selection is None:
            x, y = self.spectrum.condition(traces[0])
            position = float(x[int(np.argmax(y))]) if x.size else 0.0
        else:
            position = sum(selection) / 2.0
        self.spectrum.add_marker(position)
        self._update_status(
            "Marker added; other peaks are now labelled by their distance to it."
        )

    def _clear_markers(self) -> None:
        self.spectrum.clear_markers()
        self.chrom.clear_markers()

    def _autoscale_both(self) -> None:
        self.chrom.autoscale()
        self.spectrum.autoscale()

    def _export(self, view, what: str) -> None:
        traces = view.traces
        if not traces:
            self._update_status(f"Nothing to export in {what}.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Export {what}", os.path.join(self._last_dir(), f"{what}.csv"),
            "CSV (*.csv)"
        )
        if not path:
            return
        self._remember_dir(path)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for trace in traces:
                conditioned = view.conditioned(trace.key)
                x, y = conditioned if conditioned else (trace.x, trace.y)
                writer.writerow([trace.label])
                writer.writerow(["x", "y"])
                writer.writerows(zip(x.tolist(), y.tolist()))
                writer.writerow([])
        self._update_status(f"Exported to {path}")

    def _export_mzml(self) -> None:
        """
        Write the selected sample out as mzML.

        Every spectrum goes through, as the instrument stored it, along with
        the total ion current the instrument reported rather than a sum taken
        here. A run of this size is tens of thousands of spectra, so the
        window says how far it has got instead of appearing to hang.
        """
        # whichever sample the tree is pointing at, falling back to the first
        # one open — exporting is about a sample, not about a channel
        entry = self.active_ref.entry if self.active_ref else None
        if entry is None or not entry.is_loaded:
            entry = next((e for e in self.session.entries if e.is_loaded), None)
        if entry is None:
            self._update_status("Open a file before exporting it.")
            return

        suggestion = os.path.join(self._last_dir(), f"{entry.name}.mzML")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export as mzML", suggestion, "mzML (*.mzML)")
        if not path:
            return
        self._remember_dir(path)

        progress = QtWidgets.QProgressDialog(
            f"Writing {os.path.basename(path)}…", "Cancel", 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        cancelled = False

        def tick(done: int, total: int) -> None:
            nonlocal cancelled
            progress.setValue(int(done / max(total, 1) * 100))
            QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                cancelled = True
                raise _Cancelled()

        from ..mzml import write_mzml

        try:
            write_mzml(entry.sample, path, progress=tick)
        except _Cancelled:
            pass
        except Exception as exc:
            progress.close()
            QtWidgets.QMessageBox.warning(self, "Export failed", str(exc))
            return
        progress.close()
        if cancelled:
            try:
                os.remove(path)
            except OSError:
                pass
            self._update_status("Export cancelled.")
            return
        size = os.path.getsize(path) / 1048576
        self._update_status(f"Exported {entry.name} to {path} ({size:.0f} MB)")

    def _show_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "How to use",
            "<b>Chromatogram</b><br>"
            "• drag = rubber-band zoom; double-click = fit<br>"
            "• single click = spectrum of that scan<br>"
            "• Shift + drag = select a range → average spectrum + integration<br>"
            "• the spectrum follows the highlight while you drag or resize it<br>"
            "• ← → step through the scans<br><br>"
            "<b>Spectrum</b><br>"
            "• Shift + drag selects an m/z range<br>"
            "• right-click → extract an XIC, or drop a marker<br>"
            "• with a marker present, other peaks are labelled by their distance "
            "to it — that is how neutral losses and isotope spacings are read<br>"
            "• double-click a row of the Spectrum peaks tab to extract its XIC<br><br>"
            "<b>Components</b><br>"
            "• the list comes from the Method workspace and is shared<br>"
            "• “Extract and integrate all” runs it over every checked sample<br>"
            "• double-click a row to show that component's XIC<br><br>"
            "<b>View</b><br>"
            "• Stack gives each trace its own pane with the time axes locked<br>"
            "• Overview adds a navigator showing where the current zoom sits<br>"
            "• Mirror flips every other trace; Cascade offsets them in x and y<br><br>"
            "<b>Chemistry</b><br>"
            "• Mass calc: type a formula for its exact masses, RDBE and isotope "
            "pattern, and overlay that pattern on the spectrum<br>"
            "• right-click a spectrum peak → “Find formula for this peak”<br>"
            "• the finder ranks candidates by how well their isotope pattern "
            "matches the spectrum on screen<br><br>"
            "<b>Processing</b><br>"
            "• smoothing and baseline apply to the display, the integration and "
            "the export alike<br>"
            "• select a blank range and click “Set background” to subtract it "
            "from the spectra<br>"
            "• Centroid turns the profile spectrum into sticks",
        )

    def _update_status(self, text: str) -> None:
        """
        Say it once.

        This workspace is a QMainWindow nested in the shell's tab widget, so
        calling statusBar() here creates a second status bar inside the tab,
        directly above the shell's own — and every message was printed in
        both. The shell owns the status bar; this only reports.
        """
        self.sigStatus.emit(text)
