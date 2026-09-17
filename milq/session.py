"""
The session shared by every workspace: open files, the batch, and the method.

Both the Explorer and the Analytics workspaces read from here, so that the
component table, the sample list and the loaded files exist once instead of
once per workspace.
"""

from __future__ import annotations

import json
import os

from PyQt6 import QtCore

from .audit import PROJECT_SAVED, RECALIBRATION, AuditTrail
from .components import Component
from .matching import components_from_sample, match_channel
from .calibration import Calibration
from .method import ProcessingMethod
from .quantify import ResultsSet, XicCache
from .samples import SampleEntry, shorten_names
from .raw import open_raw

PROJECT_SUFFIX = ".oqproj"
#: the suffix used before the software was renamed; still opened, never written
LEGACY_PROJECT_SUFFIX = ".opvproj"
PROJECT_SUFFIXES = (PROJECT_SUFFIX, LEGACY_PROJECT_SUFFIX)


class Session(QtCore.QObject):
    """Owns the data; the workspaces are views onto it."""

    sigSamplesChanged = QtCore.pyqtSignal()
    sigMethodChanged = QtCore.pyqtSignal()
    sigResultsChanged = QtCore.pyqtSignal()
    #: the project path or the unsaved state changed
    sigProjectChanged = QtCore.pyqtSignal()
    #: something was written into the audit trail
    sigAuditChanged = QtCore.pyqtSignal()
    #: a project's saved view is ready to be put back on screen. Emitted
    #: last of all by `load_project`, after the samples exist: a pinned
    #: spectrum is read from its file, so the file has to be open first.
    sigViewRestored = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: list = []
        self.entries: list[SampleEntry] = []
        self.method = ProcessingMethod()
        self.results = ResultsSet()
        self.calibrations: dict[str, Calibration] = {}
        self.cache = XicCache()
        #: the last run of compare_algorithms, for the dialog and the report.
        #: Derived from the batch and not saved with it: it is three
        #: integrations of the whole batch and is rebuilt on request.
        self.comparison = None
        #: the last mass-drift measurement, likewise derived and not saved
        self.mass_drift = None
        #: the mass recalibration fitted from the internal standards, keyed by
        #: sample key. Derived from the drift measurement and not saved: a few
        #: seconds to repeat, and a correction stored without the measurement
        #: behind it could not be reviewed.
        self.mass_corrections: dict = {}
        #: whether that correction is applied. Saved with the project, because
        #: it changes the numbers and a project has to reopen as it was left.
        self.recalibrate = False
        #: the last comparison against a reference batch, likewise
        self.batch_comparison = None
        #: the last run of infusion_report.summarise: every open infusion,
        #: one row each. Measured on request and never restored as a live
        #: measurement — it is a few seconds of reading per compound, and a
        #: table put back without the spectra behind it could not be checked
        #: against them. Its figures and peak lists *are* written into the
        #: project, and come back as `infusion_stored` below.
        self.infusion_summary = None
        #: the summary the project was *saved* with, read back as figures
        #: and peak lists rather than as spectra — `infusion_compare`
        #: writes it under `infusions` when one stands. It is what a later
        #: day is compared against, and it is deliberately not the live
        #: measurement above: that one is measured from the open files and
        #: this one is what the file remembers.
        self.infusion_stored = None
        #: the last comparison of the open infusions against a reference
        #: project's saved summary, likewise derived and not saved
        self.infusion_comparison = None
        #: the spectra the Explorer is holding together — a
        #: spectra_compare.SpectrumComparison, kept in step with its spectrum
        #: pane and dropped when the pins are cleared. Derived and not saved:
        #: it is a copy of two traces that came off the files, and the report
        #: prints it only while it stands.
        self.spectra_comparison = None
        #: how the Explorer was left: the pinned spectra as recipes rather
        #: than as points, the label floor, the spectrum pane's switches and
        #: the live spectrum's own recipe. Saved with the project under
        #: `view`, because an infusion project whose comparison is its whole
        #: result has to reopen with that comparison standing. It is written
        #: by whoever set `view_source` and read by whoever listens for
        #: `sigViewRestored`; nothing here knows what a pane is.
        self.view: dict = {}
        #: what to ask for the view when the project is saved — the Explorer
        #: sets it. A hook rather than a call from the window, so that every
        #: path that saves a project saves the view with it instead of three
        #: of them remembering to.
        self.view_source = None
        #: what was changed by hand in this project, in the order it was
        #: changed. Saved with the project and appended to only — see audit.py
        self.audit = AuditTrail()
        self.project_path: str | None = None
        #: where averaged spectra are kept on disk instead of either default;
        #: the window sets it from the `cache/dir` setting. A plain string
        #: rather than a settings read, so nothing here imports Qt's settings
        self.cache_dir_override = ""
        self._averages = None
        #: something changed since the last save. Tracked here rather than in
        #: the window, because every workspace can change the session and none
        #: of them should have to remember to say so.
        self.dirty = False
        for signal in (self.sigSamplesChanged, self.sigMethodChanged,
                       self.sigResultsChanged):
            signal.connect(self._mark_dirty)

    # -- the audit trail --------------------------------------------------------- #
    def record(self, what: str, target="", before="", after="", note="",
               when: str | None = None):
        """
        Note one change made by hand.

        Called from wherever the change is actually made, once per user
        action. A change worth recording is a change worth saving, so this
        marks the project unsaved as well — which is also how an edit that
        touches nothing else, retyping a sample's comment, comes to be
        remembered at all.
        """
        entry = self.audit.record(what, target, before, after, note, when)
        self.sigAuditChanged.emit()
        self._mark_dirty()
        return entry

    # -- unsaved state ------------------------------------------------------------ #
    def _mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self.sigProjectChanged.emit()

    def _mark_clean(self) -> None:
        self.dirty = False
        self.sigProjectChanged.emit()

    @property
    def has_content(self) -> bool:
        """Is there anything here that would be lost?"""
        return bool(self.entries or self.method.components or len(self.results))

    # -- files ------------------------------------------------------------------ #
    def open_file(self, path: str):
        """Open a raw file of any supported format and add its samples."""
        wiff = open_raw(path)
        self.files.append(wiff)
        for index in range(len(wiff.sample_names)):
            sample = wiff.sample(index)
            self.entries.append(
                SampleEntry(path=wiff.path, sample_index=index,
                            name=sample.name, sample=sample,
                            problem=sample.problem or "")
            )
        shorten_names(self.entries)
        self.sigSamplesChanged.emit()
        return wiff

    def close_all(self) -> None:
        for wiff in self.files:
            wiff.close()
        self.files.clear()
        self.comparison = None
        self.mass_drift = None
        self.mass_corrections = {}
        self.batch_comparison = None
        self.infusion_summary = None
        self.infusion_stored = None
        self.infusion_comparison = None
        self.spectra_comparison = None
        self.view = {}
        self.entries.clear()
        self.results.clear()
        self.calibrations.clear()
        self.cache.clear()
        # a new trail rather than an emptied one: nothing removes an entry
        self.audit = AuditTrail()
        self.project_path = None
        self.sigSamplesChanged.emit()
        self.sigResultsChanged.emit()
        self._mark_clean()

    @property
    def loaded_entries(self) -> list[SampleEntry]:
        return [e for e in self.entries if e.is_loaded]

    # -- averaged spectra on disk ------------------------------------------------ #
    @property
    def averages(self):
        """
        The on-disk cache of averaged spectra this project's files belong in.

        Built on first use and rebuilt whenever the directory it should be in
        changes — which is what saving a project under a new name does, since
        a saved project keeps its averages beside it (`spectrum_cache`
        explains why there). The entries themselves are keyed on the files
        and not on the project, so moving the directory costs one re-read
        each and never a wrong answer.
        """
        from . import spectrum_cache

        wanted = spectrum_cache.cache_dir(self.project_path,
                                          self.cache_dir_override)
        if self._averages is None or self._averages.directory != wanted:
            self._averages = spectrum_cache.AverageCache(wanted)
        return self._averages

    # -- mass recalibration ------------------------------------------------------ #
    def correction_for(self, sample_key: str):
        """
        The mass correction to apply in one injection, or None.

        None whenever the switch is off, nothing has been fitted, or that
        injection had no lock mass — three different reasons for the same
        answer, which is that the masses stand as the instrument read them.
        """
        if not self.recalibrate:
            return None
        correction = self.mass_corrections.get(sample_key)
        if correction is None or not correction.usable:
            return None
        return correction

    def corrections_in_force(self) -> dict:
        """Every correction that would be applied right now, keyed by sample."""
        if not self.recalibrate:
            return {}
        return {key: correction
                for key, correction in self.mass_corrections.items()
                if correction.usable}

    def set_recalibrate(self, on: bool) -> None:
        """Turn the correction on or off; conditioned traces are cached."""
        on = bool(on)
        if on == self.recalibrate:
            return
        self.recalibrate = on
        self.cache.clear()
        self.record(RECALIBRATION, "the batch",
                    before="off" if on else "on",
                    after="on" if on else "off",
                    note=f"{len(self.corrections_in_force())} injection(s) "
                         f"corrected" if on else "masses as the instrument "
                                                 "read them")
        self._mark_dirty()

    def entry_by_key(self, key: str) -> SampleEntry | None:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    # -- method ------------------------------------------------------------------ #
    def set_components(self, components: list[Component]) -> None:
        self.method.replace_all(components)
        self._forget_ladder_corrections()
        self.sigMethodChanged.emit()

    def notify_method_changed(self) -> None:
        # Conditioning is baked into the cached traces, so a method change
        # invalidates them.
        self.cache.clear()
        self._forget_ladder_corrections()
        self.sigMethodChanged.emit()

    def _forget_ladder_corrections(self) -> None:
        """
        Drop the corrections an infusion's own precursor ladder gave.

        The formula and the adduct the ladder is predicted from come from the
        component table, so editing it changes what the fit would find — and
        a fit is kept rather than repeated, since it costs a centroiding of
        the whole averaged spectrum. Filling in a formula that was missing
        must therefore not leave the vial reading "no lock mass" for the rest
        of the session. The batch's own corrections are not touched here:
        they come from `mass_drift`, which the Mass drift tab invalidates
        itself, and throwing them away on a method edit would silently
        change every extraction window.
        """
        from .recalibrate import LADDER_SOURCE

        stale = [key for key, correction in self.mass_corrections.items()
                 if getattr(correction, "source", "") == LADDER_SOURCE]
        for key in stale:
            del self.mass_corrections[key]
        if stale:
            self.cache.clear()

    # -- results ------------------------------------------------------------------ #
    def set_results(self, results: ResultsSet) -> None:
        self.results = results
        self.sigResultsChanged.emit()

    def set_calibrations(self, curves: dict[str, Calibration]) -> None:
        self.calibrations = curves
        self.sigResultsChanged.emit()

    def notify_results_changed(self) -> None:
        self.sigResultsChanged.emit()

    def generate_components(self) -> list[Component]:
        """
        Derive a component table from the acquisition method of the first
        loaded sample, so an 80-transition method does not have to be typed in.
        """
        for entry in self.entries:
            if entry.is_loaded:
                return components_from_sample(entry.sample)
        return []

    def channel_for(self, entry: SampleEntry, component: Component):
        """The acquisition channel that carries a component in one sample."""
        if not entry.is_loaded:
            return None
        return match_channel(entry.sample, component)

    # -- project ------------------------------------------------------------------ #
    def current_view(self) -> dict:
        """
        The view as it stands, asked of whoever is showing it.

        Kept here so that a session with no window — the command line, a
        test, a batch comparison reading a project — still round-trips
        whatever view the project came with instead of dropping it.
        """
        if self.view_source is not None:
            self.view = dict(self.view_source() or {})
        return self.view

    def saved_infusions(self) -> dict | None:
        """
        The infusion summary to write into the project, or None.

        The live measurement when the Infusions tab has made one, and
        otherwise whatever the project was opened with — so that saving a
        project again does not throw away the reference somebody measured
        last month. Written as figures and peak lists (`infusion_compare`),
        which is what a comparison needs and what a file can hold: the
        spectra themselves stay in the acquisitions.
        """
        from . import infusion_compare

        summary = self.infusion_summary
        if summary is not None and len(getattr(summary, "rows", []) or []):
            name = (os.path.splitext(os.path.basename(self.project_path))[0]
                    if self.project_path else "")
            return infusion_compare.summary_to_dict(summary, name=name)
        if self.infusion_stored is not None and len(self.infusion_stored):
            return infusion_compare.summary_to_dict(self.infusion_stored)
        return None

    def to_dict(self) -> dict:
        # the version is not bumped for the infusion summary: the key is
        # additive and every reader that does not know it opens the project
        # exactly as it did before
        from .infusion_compare import PROJECT_KEY

        infusions = self.saved_infusions()
        return {
            "version": 5,
            "method": self.method.to_dict(),
            "samples": [e.to_dict() for e in self.entries],
            "results": self.results.to_list(),
            "calibrations": {name: curve.to_dict()
                             for name, curve in self.calibrations.items()},
            "recalibrate": self.recalibrate,
            "view": self.current_view(),
            "audit": self.audit.to_dict(),
            **({PROJECT_KEY: infusions} if infusions else {}),
        }

    def save_project(self, path: str) -> None:
        if not path.endswith(PROJECT_SUFFIXES):
            path += PROJECT_SUFFIX
        # recorded before the file is written, so that the saved project
        # holds the record of its own saving rather than of the one before
        self.audit.record(PROJECT_SAVED, os.path.basename(path),
                          after=path,
                          note=f"{len(self.results)} row(s), "
                               f"{len(self.entries)} sample(s)")
        self.sigAuditChanged.emit()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
        self.project_path = path
        self._mark_clean()

    def load_project(self, path: str) -> list[str]:
        """
        Restore a project. Returns the paths of raw files that could not be
        reopened, so the caller can tell the user which ones are missing rather
        than silently dropping their batch information.
        """
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)

        self.close_all()
        self.method = ProcessingMethod.from_dict(data.get("method", {}))

        entries = [SampleEntry.from_dict(row) for row in data.get("samples", [])]
        missing: list[str] = []
        opened: dict[str, object] = {}
        for entry in entries:
            if not os.path.exists(entry.path):
                missing.append(entry.path)
                continue
            wiff = opened.get(entry.path)
            if wiff is None:
                try:
                    wiff = open_raw(entry.path)
                except Exception:
                    missing.append(entry.path)
                    continue
                opened[entry.path] = wiff
                self.files.append(wiff)
            if entry.sample_index < len(wiff.sample_names):
                entry.sample = wiff.sample(entry.sample_index)
        self.entries = entries
        self.results = ResultsSet.from_list(data.get("results", []))
        self.calibrations = {
            name: Calibration.from_dict(row)
            for name, row in (data.get("calibrations") or {}).items()
        }
        # absent in every project written before this existed, which is
        # exactly the answer those projects want
        self.recalibrate = bool(data.get("recalibrate", False))
        # a project written before version 5 has no view; an empty one is
        # the right answer for it, and whoever restores views does nothing
        self.view = dict(data.get("view") or {})
        # likewise absent from every project written before this existed,
        # which loads with an empty trail rather than an invented one
        self.audit = AuditTrail.from_dict(data.get("audit"))
        # absent from every project written before this existed, and from
        # every project whose Infusions tab was never asked to measure —
        # which is not an error, and is why nothing is invented for it
        from . import infusion_compare

        stored = data.get(infusion_compare.PROJECT_KEY)
        self.infusion_stored = (
            infusion_compare.summary_from_dict(
                stored, name=os.path.splitext(os.path.basename(path))[0])
            if isinstance(stored, dict) and stored.get("rows") else None)
        self.project_path = path
        self.sigMethodChanged.emit()
        self.sigSamplesChanged.emit()
        self.sigResultsChanged.emit()
        self.sigAuditChanged.emit()
        # last, and after the samples: a pinned spectrum is rebuilt by
        # reading it out of its file again, which needs the file open
        self.sigViewRestored.emit()
        self._mark_clean()
        return missing
