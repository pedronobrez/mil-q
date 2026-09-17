"""Analytics workspace: process a batch, review the peaks, read the results."""

from __future__ import annotations

import time

from PyQt6 import QtCore, QtWidgets

from ..audit import (AUTOMATIC_INTEGRATION, CALIBRATION_OUTLIERS,
                     CALIBRATION_POINT, COMPONENT_EDITED,
                     MANUAL_INTEGRATION, PROCESSED, REPROCESSED,
                     describe_integration)
from ..calibration import fit as fit_curve
from ..calibration import remove_outliers
from ..components import Component, IntegrationParams
from .settings import settings
from ..quantify import (
    FULL_RUN_BELOW,
    PeakResult,
    apply_calibrations,
    build_calibrations,
    evaluate_acceptance,
    extract_xic,
    incremental_plan,
    integrate_manually,
    process,
    process_incremental,
)
from ..session import Session
from .acceptance_panel import AcceptancePanel
from .audit_panel import AuditPanel
from .calibration_panel import CalibrationPanel
from .integration_panel import IntegrationPanel
from .infusions_panel import InfusionsPanel
from .metric_plot import MetricPlotPanel
from .mass_drift_panel import MassDriftPanel
from .qc_panel import QualityPanel
from .statistics_panel import StatisticsPanel
from .peak_review import PeakReviewGrid
from .results_table import ResultsTable
from .flow_layout import FlowLayout

ROLE_NAME = QtCore.Qt.ItemDataRole.UserRole

#: the tree entry that means "do not narrow anything down". Not a component
#: name, and picked so no real one can collide with it.
ALL_COMPONENTS = "\u0000all-components"


def _integration(result) -> str:
    """One peak as the review grid states it, for the audit trail."""
    if result is None or not result.found:
        return "not integrated"
    return (f"{result.start_rt:.3f}–{result.end_rt:.3f} min, "
            f"area {result.area:,.0f}")


class ComponentTree(QtWidgets.QTreeWidget):
    """
    The component list, whose rows are as wide as the panel holding them.

    The column is sized to its contents so a long name can be scrolled to
    instead of elided. On its own that leaves the column narrower than the
    viewport whenever the names are short, and a row is painted across its
    columns rather than across the widget — so the selection and the
    alternating stripes stop in mid-air. The column is therefore the wider of
    what it holds and what there is room for.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.header().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.header().setStretchLastSection(False)
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def fit_column(self) -> None:
        self.setColumnWidth(
            0, max(self.sizeHintForColumn(0), self.viewport().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_column()


class AnalyticsWorkspace(QtWidgets.QWidget):
    """
    The component list drives the review grid, and the grid and the results
    table follow each other's selection.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._component: Component | None = None
        self._all_components = False
        self._magnified = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = FlowLayout()
        # a tool button rather than a push button so the full reprocess can
        # hang off the same control: it is the same command with the saving
        # switched off, and a separate button would read as a different one
        self.btn_process = QtWidgets.QToolButton()
        self.btn_process.setText("Process batch")
        self.btn_process.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_process.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        font = self.btn_process.font()
        font.setBold(True)
        self.btn_process.setFont(font)
        self.btn_process.setToolTip(
            "Extract and integrate every component in every open sample. "
            "With results already in hand it reads only what changed — a new "
            "injection, a new component, a component whose window or "
            "parameters moved — and says how many rows it kept")
        process_menu = QtWidgets.QMenu(self.btn_process)
        self.act_reprocess_all = process_menu.addAction("Reprocess all…")
        self.act_reprocess_all.setToolTip(
            "Integrate every row again from the files, keeping nothing — "
            "including the rows integrated by hand")
        self.btn_process.setMenu(process_menu)
        bar.addWidget(self.btn_process)
        self.btn_calibrate = QtWidgets.QPushButton("Recalibrate")
        self.btn_calibrate.setToolTip(
            "Refit every curve from the samples marked as standards and read "
            "the unknowns back off them")
        bar.addWidget(self.btn_calibrate)
        self.btn_compare = QtWidgets.QPushButton("Compare algorithms…")
        self.btn_compare.setToolTip(
            "Integrate the batch with every algorithm and put the answers "
            "side by side: how far the areas move, and how well each one "
            "repeats itself on the internal standards and quality controls")
        bar.addWidget(self.btn_compare)
        self.btn_batches = QtWidgets.QPushButton("Compare batches…")
        self.btn_batches.setToolTip(
            "A reference project against this batch, component by component: "
            "rows found, points on the peak, the replicates' %CV, the area and "
            "the retention time. The question a new schedule poses")
        bar.addWidget(self.btn_batches)
        self.btn_magnify = QtWidgets.QPushButton("Magnify peak")
        self.btn_magnify.setCheckable(True)
        self.btn_magnify.setToolTip(
            "Expand the selected panel to fill the pane (double-click a panel "
            "does the same)")
        bar.addWidget(self.btn_magnify)
        bar.addStretch(1)
        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        bar.addWidget(self.status)
        layout.addLayout(bar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.component_filter = QtWidgets.QLineEdit()
        self.component_filter.setPlaceholderText("Filter components…")
        self.component_filter.setClearButtonEnabled(True)
        left_layout.addWidget(self.component_filter)
        self.component_tree = ComponentTree()
        left_layout.addWidget(self.component_tree, 1)
        self.integration = IntegrationPanel()
        left_layout.addWidget(self.integration)
        self.acceptance = AcceptancePanel()
        left_layout.addWidget(self.acceptance)
        # folded to start with: expanded they leave the component list a few
        # rows tall, and they are only wanted while a setting is being changed
        self.settings = settings()
        self.integration.restore(self.settings, "analytics/integration_open")
        self.acceptance.restore(self.settings, "analytics/acceptance_open")
        self.integration.toggled.connect(self._save_sections)
        self.acceptance.toggled.connect(self._save_sections)
        splitter.addWidget(left)

        right = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.grid = PeakReviewGrid()
        self.results = ResultsTable(session)
        self.calibration = CalibrationPanel()
        self.statistics = StatisticsPanel(session)
        self.metrics = MetricPlotPanel(session)
        self.quality = QualityPanel(session)
        self.mass = MassDriftPanel(session)
        self.infusions = InfusionsPanel(session)
        self.audit = AuditPanel(session)
        self.bottom = QtWidgets.QTabWidget()
        self.bottom.setDocumentMode(True)
        self.bottom.addTab(self.results, "Results")
        self.bottom.addTab(self.calibration, "Calibration")
        self.bottom.addTab(self.statistics, "Statistics")
        self.bottom.addTab(self.metrics, "Metric plot")
        self.bottom.addTab(self.quality, "Batch QC")
        self.bottom.addTab(self.mass, "Mass drift")
        self.infusions_tab = self.bottom.addTab(self.infusions, "Infusions")
        self.bottom.addTab(self.audit, "Audit trail")
        right.addWidget(self.grid)
        right.addWidget(self.bottom)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1200])
        layout.addWidget(splitter, 1)

        from .help_window import describe
        for widget, page in ((self.integration, "integration-parameters"),
                             (self.acceptance, "acceptance-criteria"),
                             (self.grid, "peak-review"),
                             (self.results, "results-table"),
                             (self.calibration, "calibration"),
                             (self.statistics, "statistics"),
                             (self.metrics, "metric-plot"),
                             (self.quality, "batch-qc"),
                             (self.mass, "mass-drift"),
                             (self.infusions, "infusion-report"),
                             (self.audit, "audit-trail")):
            describe(widget, page)

        self.btn_process.clicked.connect(lambda: self.process_batch())
        self.act_reprocess_all.triggered.connect(self.reprocess_all)
        self.btn_magnify.toggled.connect(self._set_magnified)
        self.btn_calibrate.clicked.connect(lambda: self._recalibrate())
        self.btn_compare.clicked.connect(self.compare_algorithms)
        self.btn_batches.clicked.connect(self.compare_batches)
        self.component_filter.textChanged.connect(self._filter_components)
        self.component_tree.currentItemChanged.connect(self._on_component_changed)
        # queued: the recalculation resets the results model, which must not
        # happen while the table's editor is still closing over the cell
        self.results.sigInternalStandardChanged.connect(
            self._set_internal_standard, QtCore.Qt.ConnectionType.QueuedConnection)
        self.grid.sigSelected.connect(self._on_panel_selected)
        self.grid.sigMagnified.connect(self._on_panel_magnified)
        self.grid.sigManualRange.connect(self._on_manual_range)
        self.grid.sigContextMenu.connect(self._panel_menu)
        self.results.sigSelected.connect(self._on_row_selected)
        self.integration.sigApplyComponent.connect(self._apply_to_component)
        self.integration.sigApplyGroup.connect(self._apply_to_group)
        self.integration.sigResetComponent.connect(self._reset_component)
        self.calibration.sigSettingsChanged.connect(self._set_curve_settings)
        self.calibration.sigPointToggled.connect(self._toggle_point)
        self.calibration.sigAutoOutliers.connect(self._auto_outliers)
        self.acceptance.sigApplyComponent.connect(self._apply_acceptance_component)
        self.acceptance.sigApplyAll.connect(self._apply_acceptance_all)
        self.metrics.sigPointActivated.connect(self._on_row_selected)
        self.quality.sigSampleActivated.connect(self.grid.select)
        self.mass.sigSampleActivated.connect(self.grid.select)
        self.infusions.sigRowsChanged.connect(self._show_infusion_count)
        self.infusions.sigStatus.connect(self.sigStatus)
        self.audit.sigStatus.connect(self.sigStatus)

        session.sigMethodChanged.connect(self.reload_components)
        session.sigSamplesChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_calibration)
        self.reload_components()

    def _show_infusion_count(self, rows: int) -> None:
        """The tab carries its own count: a table measured on request is
        otherwise a tab nobody knows has anything in it."""
        self.bottom.setTabText(self.infusions_tab,
                               f"Infusions ({rows})" if rows else "Infusions")

    def _save_sections(self, *_args) -> None:
        self.integration.save(self.settings, "analytics/integration_open")
        self.acceptance.save(self.settings, "analytics/acceptance_open")

    # -- components ---------------------------------------------------------------- #
    def reload_components(self) -> None:
        current = (ALL_COMPONENTS if self._all_components
                   else self._component.name if self._component else None)
        self.component_tree.blockSignals(True)
        self.component_tree.clear()

        groups: dict[str, QtWidgets.QTreeWidgetItem] = {}
        all_item = QtWidgets.QTreeWidgetItem(self.component_tree,
                                             ["All components"])
        all_item.setData(0, ROLE_NAME, ALL_COMPONENTS)
        all_item.setToolTip(0, "Every peak of every component, and the whole "
                               "results table")
        font = all_item.font(0)
        font.setBold(True)
        all_item.setFont(0, font)
        selected_item = all_item if current == ALL_COMPONENTS else None
        for component in self.session.method.components:
            parent = self.component_tree
            if component.group:
                if component.group not in groups:
                    node = QtWidgets.QTreeWidgetItem(self.component_tree,
                                                     [component.group])
                    node.setExpanded(True)
                    font = node.font(0)
                    font.setBold(True)
                    node.setFont(0, font)
                    groups[component.group] = node
                parent = groups[component.group]
            label = component.name + (" (IS)" if component.is_internal_standard else "")
            item = QtWidgets.QTreeWidgetItem(parent, [label])
            item.setData(0, ROLE_NAME, component.name)
            item.setToolTip(0, label)
            if component.name == current:
                selected_item = item
        self.component_tree.blockSignals(False)

        self.component_tree.fit_column()
        if selected_item is None:
            selected_item = self._first_component_item()
        if selected_item is not None:
            self.component_tree.setCurrentItem(selected_item)
        else:
            self._component = None
            self.grid.clear()

    def _first_component_item(self):
        it = QtWidgets.QTreeWidgetItemIterator(self.component_tree)
        while it.value():
            if it.value().data(0, ROLE_NAME):
                return it.value()
            it += 1
        return None

    def _filter_components(self, text: str) -> None:
        needle = text.strip().lower()
        it = QtWidgets.QTreeWidgetItemIterator(self.component_tree)
        while it.value():
            item = it.value()
            if item.data(0, ROLE_NAME):
                item.setHidden(bool(needle) and needle not in item.text(0).lower())
            it += 1
        self.component_tree.fit_column()

    def _on_component_changed(self, current, _previous) -> None:
        name = current.data(0, ROLE_NAME) if current is not None else None
        self._all_components = name == ALL_COMPONENTS
        self._component = (None if self._all_components
                           else self.session.method.by_name(name) if name else None)
        # the results table follows the tree: reviewing one component against a
        # table of every other one is what made the table hard to read
        self.results.set_component_filter(
            "" if self._all_components or self._component is None
            else self._component.name)
        self._show_integration_params()
        self.refresh_grid()
        self.refresh_calibration()

    def _show_integration_params(self) -> None:
        component = self._component
        if component is None:
            return
        params = self.session.method.integration_for(component)
        self.integration.set_params(params, component.integration is not None)
        self.grid.set_noise_region(params.noise_region)
        self.acceptance.set_limits(self.session.method.acceptance_for(component),
                                   component.acceptance is not None)

    # -- grid ------------------------------------------------------------------------ #
    def refresh_grid(self) -> None:
        if self._all_components:
            self._refresh_grid_all()
            return
        component = self._component
        if component is None:
            self.grid.clear()
            return
        method = self.session.method
        expected = component.rt_window()
        standard = method.internal_standard_for(component)
        items = []
        for entry in self.session.entries:
            if not entry.is_loaded:
                continue
            result = self.session.results.get(entry.key, component.name)
            if result is None:
                # not processed yet: still show the trace, unintegrated
                result = PeakResult(
                    sample_key=entry.key, sample_name=entry.name,
                    component=component.name, group=component.group,
                    expected_rt=component.rt, note="not processed",
                )
            correction = self.session.correction_for(entry.key)
            x, y, _channel = extract_xic(entry, component, method,
                                         self.session.cache, correction)
            is_trace = None
            if standard is not None:
                sx, sy, _ = extract_xic(entry, standard, method,
                                        self.session.cache, correction)
                if sx.size:
                    is_trace = (sx, sy)
            items.append((result, x, y, expected, is_trace))
        self.grid.set_items(component.label, items)

        found = sum(1 for i in items if i[0].found)
        message = f"{component.name}: {found} of {len(items)} sample(s) integrated"
        if standard is not None:
            message += f" · internal standard {standard.name}"
        quantifier = method.quantifier_for(component)
        if quantifier is not None:
            message += f" · qualifier of {quantifier.name}"
        self._report(message)

    def _refresh_grid_all(self) -> None:
        """
        Every peak of every component, built a page at a time.

        Extracting all of them on a real batch — 141 components across 26
        samples — is around a hundred seconds of work to put nine on screen.
        """
        loaded = [e for e in self.session.entries if e.is_loaded]
        components = [c for c in self.session.method.components if c.is_valid]
        pairs = [(c, e) for c in components for e in loaded]

        def fetch(start: int, stop: int) -> list[tuple]:
            return [self._grid_item(c, e) for c, e in pairs[start:stop]]

        self.grid.set_lazy("All components", len(pairs), fetch)
        self._report(f"{len(components)} component(s) across {len(loaded)} "
                     f"sample(s) — {len(pairs)} peak(s)")

    def _grid_item(self, component: Component, entry) -> tuple:
        """One panel's worth: the result, its trace, and the standard's."""
        method = self.session.method
        result = self.session.results.get(entry.key, component.name)
        if result is None:
            result = PeakResult(
                sample_key=entry.key, sample_name=entry.name,
                component=component.name, group=component.group,
                expected_rt=component.rt, note="not processed",
            )
        correction = self.session.correction_for(entry.key)
        x, y, _channel = extract_xic(entry, component, method,
                                     self.session.cache, correction)
        standard = method.internal_standard_for(component)
        is_trace = None
        if standard is not None:
            sx, sy, _ = extract_xic(entry, standard, method,
                                    self.session.cache, correction)
            if sx.size:
                is_trace = (sx, sy)
        return (result, x, y, component.rt_window(), is_trace)

    # -- acceptance ------------------------------------------------------------------ #
    def _apply_acceptance_component(self, limits) -> None:
        component = self._component
        if component is None:
            return
        component.acceptance = limits.copy()
        self.session.notify_method_changed()
        self._revalidate()
        self._report(f"Acceptance criteria applied to {component.name}.")

    def _apply_acceptance_all(self, limits) -> None:
        method = self.session.method
        method.acceptance = limits.copy()
        for component in method.components:
            component.acceptance = None
        self.session.notify_method_changed()
        self._show_integration_params()
        self._revalidate()
        self._report("Acceptance criteria applied to every component.")

    def _revalidate(self) -> None:
        evaluate_acceptance(self.session.results, self.session.entries,
                            self.session.method)
        self.session.notify_results_changed()

    # -- calibration ---------------------------------------------------------------- #
    def refresh_calibration(self) -> None:
        component = self._component
        if component is None:
            self.calibration.show_curve(None)
            return
        curve = (self.session.calibrations.get(component.name)
                 if component is not None else None)
        self.calibration.show_curve(
            curve, self.session.method.concentration_unit)

    def _recalibrate(self, auto_outliers: bool = False,
                     tolerance: float = 15.0) -> None:
        """Refit every curve and read the unknowns back off them."""
        session = self.session
        curves = build_calibrations(session.results, session.entries,
                                    session.method, auto_outliers, tolerance,
                                    previous=session.calibrations)
        apply_calibrations(session.results, session.entries, session.method,
                           curves)
        session.calibrations = curves
        evaluate_acceptance(session.results, session.entries, session.method)
        session.notify_results_changed()
        fitted = sum(1 for c in curves.values() if c.is_fitted)
        if not curves:
            self._report("No standards found — mark samples as Standard and "
                         "give them a concentration in the Samples workspace.")
        else:
            self._report(f"{fitted} of {len(curves)} curve(s) fitted.")

    def _set_curve_settings(self, regression: str, weighting: str) -> None:
        component = self._component
        if component is None:
            return
        component.regression = regression
        component.weighting = weighting
        self.session.notify_method_changed()
        self._recalibrate()

    def _toggle_point(self, sample_key: str) -> None:
        """Include or exclude one standard, then refit."""
        component = self._component
        curve = (self.session.calibrations.get(component.name)
                 if component is not None else None)
        if curve is None:
            return
        for point in curve.points:
            if point.sample_key == sample_key:
                point.used = not point.used
                self.session.record(
                    CALIBRATION_POINT, f"{curve.component} · {point.sample_name}",
                    before="excluded" if point.used else "used",
                    after="used" if point.used else "excluded",
                    note=f"{point.concentration:g} "
                         f"{self.session.method.concentration_unit}".strip())
                break
        refitted = fit_curve(curve.points, curve.regression, curve.weighting,
                             curve.component)
        self.session.calibrations[curve.component] = refitted
        apply_calibrations(self.session.results, self.session.entries,
                           self.session.method, self.session.calibrations)
        evaluate_acceptance(self.session.results, self.session.entries,
                            self.session.method)
        self.session.notify_results_changed()

    def _auto_outliers(self, tolerance: float) -> None:
        component = self._component
        curve = (self.session.calibrations.get(component.name)
                 if component is not None else None)
        if curve is None or not curve.is_fitted:
            return
        was = sum(1 for p in curve.points if not p.used)
        cleaned = remove_outliers(curve, tolerance)
        self.session.calibrations[curve.component] = cleaned
        self.session.record(
            CALIBRATION_OUTLIERS, curve.component,
            before=f"{was} excluded",
            after=f"{sum(1 for p in cleaned.points if not p.used)} excluded",
            note=f"automatic, over {tolerance:g}% from the curve")
        apply_calibrations(self.session.results, self.session.entries,
                           self.session.method, self.session.calibrations)
        evaluate_acceptance(self.session.results, self.session.entries,
                            self.session.method)
        self.session.notify_results_changed()
        dropped = sum(1 for p in cleaned.points if not p.used)
        self._report(f"{curve.component}: {dropped} standard(s) excluded, "
                     f"r² = {cleaned.r2:.5f}")

    # -- integration parameters -------------------------------------------------- #
    def _apply_to_component(self, params: IntegrationParams) -> None:
        component = self._component
        if component is None:
            return
        self.session.method.set_integration(component, params)
        self.session.notify_method_changed()
        self._reprocess([component.name], describe_integration(params))
        self.integration.report(f"Applied to {component.name}.")

    def _apply_to_group(self, params: IntegrationParams) -> None:
        component = self._component
        if component is None:
            return
        if not component.group:
            self.integration.report(
                "This component has no group; use “update for component”.")
            return
        method = self.session.method
        touched = method.apply_integration_to_group(component.group, params)
        self.session.notify_method_changed()
        names = [c.name for c in method.components if c.group == component.group]
        self._reprocess(names, describe_integration(params))
        self.integration.report(
            f"Applied to {touched} component(s) of {component.group}.")

    def _reset_component(self) -> None:
        component = self._component
        if component is None:
            return
        self.session.method.set_integration(component, None)
        self.session.notify_method_changed()
        self._show_integration_params()
        self._reprocess([component.name],
                        "back to the method defaults: "
                        + describe_integration(
                            self.session.method.integration_for(component)))
        self.integration.report(f"{component.name} back to the method defaults.")

    def _reprocess(self, names: list[str], note: str = "") -> None:
        """
        Re-integrate the rows a method change reaches, and only those.

        `names` says which components the caller touched; what is actually
        read is decided by `quantify.fingerprint`, which is the same rule the
        Process button follows. So a change applied to a group re-integrates
        that group and nothing else, and a hand-integrated row inside it goes
        with it — a boundary drawn under the old settings is not a decision
        about the new ones. The audit says how many.

        The audit entry is written here rather than by the caller, so that
        one user action — applying a parameter, resetting a component —
        leaves one line saying what was reprocessed and what with.
        """
        if not self.session.results.results:
            return
        results, done = process_incremental(
            self.session.loaded_entries, self.session.method,
            self.session.results, self.session.cache,
            corrections=self.session.corrections_in_force())
        self.session.results = results
        after = f"{done.integrated} row(s)"
        if done.reintegrated_manual:
            after += (f", {done.reintegrated_manual} of them integrated "
                      f"by hand before")
        self.session.record(
            REPROCESSED,
            names[0] if len(names) == 1 else f"{len(names)} component(s)",
            after=after, note=note)
        self._recalibrate()

    # -- manual integration -------------------------------------------------------- #
    def _on_manual_range(self, sample_key: str, start: float, end: float) -> None:
        component = self._component
        entry = self.session.entry_by_key(sample_key)
        if component is None or entry is None:
            return
        previous = self.session.results.get(sample_key, component.name)
        # read before integrating: integrate_manually writes into the row it
        # is given, so the previous numbers are gone the moment it runs
        was = _integration(previous)
        result = integrate_manually(entry, component, self.session.method,
                                    start, end, previous, self.session.cache,
                                    self.session.correction_for(sample_key))
        self.session.results.replace(result)
        self.session.record(
            MANUAL_INTEGRATION, f"{component.name} · {entry.name}",
            before=was, after=_integration(result),
            note=f"dragged {min(start, end):.3f}–{max(start, end):.3f} min")
        self._relink()
        self._recalibrate()
        self.results.select(sample_key, component.name)
        self._report(
            f"{entry.name}: integrated {min(start, end):.3f}–{max(start, end):.3f} min "
            f"by hand — area {result.area:,.0f}")

    def _set_internal_standard(self, component_name: str, standard: str) -> None:
        """
        Point a component at another internal standard from the results table.

        Every ratio, response and calculated concentration that came off the old
        standard is wrong the moment this changes, so they are recomputed here
        rather than left for the analyst to remember to refresh.
        """
        component = self.session.method.by_name(component_name)
        if component is None:
            return
        self.session.record(
            COMPONENT_EDITED, f"{component_name} · internal standard",
            before=component.internal_standard, after=standard,
            note="chosen in the results table")
        component.internal_standard = standard
        self.session.notify_method_changed()
        self._relink()
        self._recalibrate()
        self._report(f"{component_name} is now quantified against "
                     + (f"{standard}." if standard else "its own area."))

    def _relink(self) -> None:
        from ..quantify import compute_ion_ratios, link_internal_standards
        link_internal_standards(self.session.results, self.session.method)
        compute_ion_ratios(self.session.results, self.session.method)

    def _panel_menu(self, sample_key: str, position) -> None:
        component = self._component
        if component is None:
            return
        result = self.session.results.get(sample_key, component.name)
        menu = QtWidgets.QMenu(self)
        noise = menu.addAction("Set noise region from the shaded range")
        revert = menu.addAction("Back to automatic integration")
        revert.setEnabled(result is not None and result.manual)
        chosen = menu.exec(position)
        if chosen is noise:
            self._noise_from_panel(sample_key)
        elif chosen is revert:
            self._revert_manual(sample_key)

    def _noise_from_panel(self, sample_key: str) -> None:
        panel = next((p for p in self.grid.views if p.sample_key == sample_key), None)
        if panel is None:
            return
        region = panel.integration_range()
        if region is None:
            self.integration.report("Drag across a stretch of baseline first.")
            return
        self.integration.set_noise_region(region)
        self.grid.set_noise_region(region)
        self.integration.report(
            f"Noise region {region[0]:.2f}–{region[1]:.2f} min — apply to keep it.")

    def _revert_manual(self, sample_key: str) -> None:
        component = self._component
        entry = self.session.entry_by_key(sample_key)
        if component is None or entry is None:
            return
        from ..quantify import integrate_component
        was = _integration(self.session.results.get(sample_key, component.name))
        result = integrate_component(entry, component, self.session.method,
                                     self.session.cache,
                                     self.session.correction_for(sample_key))
        self.session.results.replace(result)
        self.session.record(
            AUTOMATIC_INTEGRATION, f"{component.name} · {entry.name}",
            before=was, after=_integration(result),
            note="the detector has it again")
        self._relink()
        self._recalibrate()
        self._report(f"{entry.name}: back to automatic integration.")

    def _set_magnified(self, enabled: bool) -> None:
        """One panel filling the pane, or back to the grid."""
        self._magnified = enabled
        if enabled:
            self._saved_layout = (self.grid.col_spin.value(),
                                  self.grid.row_spin.value())
            self.grid.col_spin.setValue(1)
            self.grid.row_spin.setValue(1)
            selected = self.results.current_result()
            if selected is not None:
                self.grid.select(selected.sample_key)
        elif hasattr(self, "_saved_layout"):
            self.grid.col_spin.setValue(self._saved_layout[0])
            self.grid.row_spin.setValue(self._saved_layout[1])

    def _on_panel_magnified(self, sample_key: str) -> None:
        self.btn_magnify.setChecked(not self._magnified)
        self.grid.select(sample_key)

    # -- linking ---------------------------------------------------------------------- #
    def _on_panel_selected(self, sample_key: str) -> None:
        if self._component is not None:
            self.results.select(sample_key, self._component.name)

    def _on_row_selected(self, sample_key: str, component: str) -> None:
        if self._component is None or component != self._component.name:
            item = self._item_for(component)
            if item is not None:
                self.component_tree.setCurrentItem(item)
        self.grid.select(sample_key)

    def _item_for(self, component: str):
        it = QtWidgets.QTreeWidgetItemIterator(self.component_tree)
        while it.value():
            if it.value().data(0, ROLE_NAME) == component:
                return it.value()
            it += 1
        return None

    # -- processing --------------------------------------------------------------- #
    def process_batch(self, full: bool = False) -> None:
        """
        Run the method over the batch — reading only what changed, where it
        can.

        With results already in hand, most presses of this button follow a
        small change: one injection added, one component's window widened.
        `quantify.incremental_plan` says what a run would have to read before
        it reads anything, and where enough of the previous rows still answer
        to the method the run keeps them. Where they do not — a change to a
        method default reaches every component that inherits it — the plan
        keeps too little to be worth the bookkeeping and the batch is
        processed in full, which is also what `full=True` asks for outright.
        """
        method = self.session.method
        components = [c for c in method.components if c.is_valid]
        loaded = self.session.loaded_entries
        if not components:
            self._report("Build the component list in the Method workspace first.")
            return
        if not loaded:
            self._report("Open at least one sample first.")
            return

        previous = self.session.results
        plan = None
        if not full and previous.results:
            plan = incremental_plan(loaded, method, previous,
                                    self.session.corrections_in_force())
            if plan.kept_fraction < FULL_RUN_BELOW:
                plan = None
        if plan is None:
            self._process_fully(components, loaded)
        else:
            self._process_incrementally(plan, loaded)

    def reprocess_all(self) -> None:
        """
        Integrate every row again, keeping nothing.

        Offered because a fingerprint can only say the method has not
        changed. It cannot say the acquisition under a path has not been
        replaced, and it cannot answer for a row this version integrated
        differently from the last. Hand-integrated rows go with it, which is
        why the question is asked before it runs.
        """
        manual = sum(1 for r in self.session.results if r.manual)
        if manual:
            answer = QtWidgets.QMessageBox.question(
                self, "Reprocess all",
                f"Every row will be integrated again from the files, "
                f"including {manual:,} integrated by hand. Their boundaries "
                f"will be replaced by the detector's.\n\nReprocess all?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.process_batch(full=True)

    def _process_fully(self, components, loaded) -> None:
        """Every row from the files, as the first run of a batch always is."""
        method = self.session.method
        total = len(components) * len(loaded)
        dialog = QtWidgets.QProgressDialog("Processing…", "Cancel", 0, total, self)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)

        def report(done: int, _total: int) -> bool:
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        started = time.perf_counter()
        results = process(loaded, method, self.session.cache, report,
                          corrections=self.session.corrections_in_force())
        seconds = time.perf_counter() - started
        dialog.setValue(total)
        self.session.results = results
        self._recalibrate()
        found = sum(1 for r in results if r.found)
        self.session.record(
            PROCESSED, f"{len(components)} component(s) × "
                       f"{len(loaded)} sample(s)",
            after=f"{len(results)} row(s), {found} integrated",
            note=f"every row from the files; "
                 f"{describe_integration(method.defaults)}")
        self._report(f"{len(results):,} row(s) across {len(loaded)} sample(s); "
                     f"{found:,} integrated — {seconds:.1f} s.")

    def _process_incrementally(self, plan, loaded) -> None:
        """Only the rows the previous run cannot answer for."""
        method = self.session.method
        dialog = None
        if plan.integrated:
            dialog = QtWidgets.QProgressDialog(
                f"Integrating {plan.integrated:,} row(s)…", "Cancel", 0,
                plan.integrated, self)
            dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            dialog.setMinimumDuration(300)

        def report(done: int, _total: int) -> bool:
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        results, done = process_incremental(
            loaded, method, self.session.results, self.session.cache,
            report if dialog is not None else None,
            corrections=self.session.corrections_in_force())
        if dialog is not None:
            dialog.setValue(plan.integrated)
        self.session.results = results
        self._recalibrate()
        self.session.record(
            REPROCESSED, "the batch, incrementally",
            after=f"{done.kept:,} kept, {done.integrated:,} integrated, "
                  f"{done.dropped:,} dropped",
            note=done.why() or "nothing had changed")
        message = done.summary()
        if done.reintegrated_manual:
            message += (" — a hand-integrated row is redone when its "
                        "component changes")
        if done.cancelled:
            message += " — cancelled; press Process again to finish it"
        self._report(message)

    # -- algorithms ------------------------------------------------------------- #
    def compare_algorithms(self) -> None:
        """Integrate the batch every way and show the differences."""
        from ..compare import compare_algorithms
        from .compare_dialog import ComparisonDialog
        from .help_window import describe

        method = self.session.method
        components = [c for c in method.components if c.is_valid]
        loaded = self.session.loaded_entries
        if not components:
            self._report("Build the component list in the Method workspace first.")
            return
        if not loaded:
            self._report("Open at least one sample first.")
            return

        dialog = QtWidgets.QProgressDialog("Comparing…", "Cancel", 0, 100, self)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)

        def report(done: int, total: int) -> bool:
            dialog.setMaximum(total)
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        comparison = compare_algorithms(
            loaded, method, self.session.cache, progress=report,
            corrections=self.session.corrections_in_force())
        dialog.reset()
        if comparison is None:
            self._report("Comparison cancelled.")
            return
        self.session.comparison = comparison
        self._comparison_dialog = ComparisonDialog(self.session, comparison, self)
        describe(self._comparison_dialog, "compare-algorithms")
        self._comparison_dialog.sigAdopt.connect(self._adopt_algorithm)
        self._comparison_dialog.show()
        self._report(comparison.summary())

    def compare_batches(self) -> None:
        """A reference project against the open batch."""
        import os

        from ..batches import compare_batches, read_project, snapshot
        from .batches_dialog import BatchesDialog

        if not len(self.session.results):
            self._report("Process the batch first; the comparison is of results.")
            return
        start = settings().value("io/last_dir", "", type=str)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Reference project", start, "MIL-Q project (*.oqproj *.opvproj)")
        if not path:
            return
        try:
            reference = read_project(path)
        except Exception as exc:
            self._report(f"Could not read {os.path.basename(path)}: {exc}")
            return
        comparison = compare_batches(snapshot(self.session), reference)
        if not comparison.rows:
            self._report("The two methods share no component by name.")
            return
        self.session.batch_comparison = comparison
        self._batches_dialog = BatchesDialog(comparison, self)
        self._batches_dialog.show()
        self._report(comparison.summary())

    def _adopt_algorithm(self, algorithm: str) -> None:
        """
        Put the batch on one algorithm and integrate it again.

        The whole batch, not the comparison's own rows, which were run
        against a method this one is no longer. An algorithm is how every
        area is arrived at, so it moves every component's fingerprint and
        every row is read again — hand-integrated rows included, since a
        boundary drawn to be integrated one way is not a decision about
        another. The audit line says how many there were.
        """
        from ..compare import adopt_algorithm
        from ..processing import ALGORITHM_LABELS

        method = self.session.method
        label = ALGORITHM_LABELS.get(algorithm, algorithm)
        touched = adopt_algorithm(method, algorithm)
        self.session.notify_method_changed()
        self._show_integration_params()
        loaded = self.session.loaded_entries
        if loaded and self.session.results.results:
            results, done = process_incremental(
                loaded, method, self.session.results, self.session.cache,
                corrections=self.session.corrections_in_force())
            self.session.results = results
            after = f"{done.integrated} row(s)"
            if done.reintegrated_manual:
                after += (f", {done.reintegrated_manual} of them integrated "
                          f"by hand before")
            self.session.record(
                REPROCESSED, "the whole batch",
                after=after,
                note=f"{label.lower()} adopted from the comparison")
            self._recalibrate()
        else:
            self.process_batch()
        message = f"Batch integrated with {label.lower()}."
        if touched:
            message += f" {touched} component override(s) moved with it."
        self._report(message)

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
