"""
A .wiff whose .wiff.scan is not beside it.

The file opens — the method, the totals and the chromatograms are in the
.wiff — and the first spectrum throws. Found on a folder where one
companion had been renamed by hand: the Explorer showed the chromatogram,
and clicking on it, stepping scan by scan or selecting a range left the
spectrum pane as it was, with the exception on a console nobody has.

What has to hold: the reader names the file that is missing, and the stray
that may be it; the Explorer says so in the pane instead of staying blank;
an XIC and an integration report it instead of stopping; an mzML, which
is one file, has no such problem.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.components import Component  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.quantify import integrate_component  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from milq.wiff import ChannelInfo, scan_problem, stray_scan_files  # noqa: E402

MISSING = "Could not open data stream. Is a required 'scan' file missing?"
NO_ASSEMBLY = "Could not load file or assembly 'OFX.Core.Contracts, Version=1.0.0.0'"
PROBLEM = "the spectra of mix1.wiff cannot be read: mix1.wiff.scan is not beside it"


class _Unreadable:
    """A channel as Clearcore2 leaves it without the .scan: totals only."""

    def __init__(self):
        self.index = 1
        self.info = ChannelInfo(index=1, name="TOF PI", experiment_type="TOF PI",
                                polarity="Negative", precursor=430.34,
                                start_mass=50.0, end_mass=500.0, n_scans=50,
                                collision_energy=12.0)
        self.rt = np.linspace(0.0, 10.0, 50)

    def tic(self):
        return self.rt, np.full(50, 1000.0)

    def bpc(self, *args, **kwargs):
        raise RuntimeError(NO_ASSEMBLY)

    def xic(self, *args, **kwargs):
        raise RuntimeError(NO_ASSEMBLY)

    def xic_range(self, mz_lo, mz_hi):
        raise RuntimeError(NO_ASSEMBLY)

    def spectrum(self, scan, add_zeros=True):
        raise RuntimeError(MISSING + "\n   at Clearcore2.Data.WiffReader.ScanCacheWiff")

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        raise RuntimeError(MISSING)

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self.rt - rt)))

    def rt_at_scan(self, scan):
        return float(self.rt[scan])

    def scans_in_range(self, rt_start, rt_end):
        return 0, 4

    def parameters(self):
        return {}


class _Sample:
    instrument = "ZenoTOF 7600"
    problem = PROBLEM

    def __init__(self):
        self.channels = [_Unreadable()]

    def tic(self):
        return self.channels[0].tic()

    def metadata(self):
        return {"Sample": "mix1"}


def _entry():
    return SampleEntry("/d/mix1.wiff", 0, "mix1", sample=_Sample(), problem=PROBLEM)


# -- the diagnosis --------------------------------------------------------- #
def test_the_stray_scan_file_is_the_one_that_belongs_to_no_wiff(tmp_path):
    for name in ("a.wiff", "a.wiff.scan", "b_mix1.wiff", "b.wiff_mix1.scan", "notes.txt"):
        (tmp_path / name).write_text("")
    assert stray_scan_files(tmp_path / "b_mix1.wiff") == ["b.wiff_mix1.scan"]
    assert stray_scan_files(tmp_path / "a.wiff") == ["b.wiff_mix1.scan"]
    assert stray_scan_files(tmp_path / "nowhere" / "c.wiff") == []


def test_the_problem_names_the_companion_and_the_stray(tmp_path):
    (tmp_path / "b_mix1.wiff").write_text("")
    (tmp_path / "b.wiff_mix1.scan").write_text("")
    text = scan_problem(tmp_path / "b_mix1.wiff", RuntimeError(MISSING))
    assert text.startswith("the spectra of b_mix1.wiff cannot be read: "
                           "b_mix1.wiff.scan is not beside it")
    assert "b.wiff_mix1.scan" in text and "renamed to b_mix1.wiff.scan" in text
    assert "chromatograms open" in text


def test_a_companion_that_is_there_but_unreadable_quotes_the_reader(tmp_path):
    (tmp_path / "a.wiff").write_text("")
    (tmp_path / "a.wiff.scan").write_text("")
    text = scan_problem(tmp_path / "a.wiff", RuntimeError(MISSING + "\n   at deep"))
    assert "a.wiff.scan is beside it" in text
    assert text.endswith("Clearcore2 said: " + MISSING)
    assert "at deep" not in text


# -- the Explorer ------------------------------------------------------------ #
def test_the_spectrum_pane_says_why_it_is_empty():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace

    session = Session()
    entry = _entry()
    session.entries.append(entry)
    explorer = ExplorerWorkspace(session)
    explorer.rebuild_tree()
    messages = []
    explorer.sigStatus.connect(messages.append)
    assert explorer.active_ref is not None and explorer.active_ref.channel is not None

    explorer._show_scan(3)                       # scan by scan
    assert explorer.spectrum.traces == []
    assert explorer.spectrum.title == PROBLEM
    assert messages[-1] == PROBLEM

    explorer._show_average(0.5, 2.0)             # a selected range
    assert explorer.spectrum.title == PROBLEM

    # the tree marks the sample, and every leaf explains on hover
    file_item = explorer.tree.topLevelItem(0)
    sample_item = file_item.child(0)
    assert sample_item.text(0).startswith("⚠ mix1")
    assert sample_item.toolTip(0) == PROBLEM
    assert sample_item.child(1).toolTip(0) == PROBLEM

    # an XIC reports instead of stopping
    explorer._add_xic(430.2, 430.4, "430.3")
    assert explorer.xic_defs == [] and messages[-1] == PROBLEM

    # and a manual integration carries it as the row's note
    ref = explorer.active_ref
    result = explorer._integrate_component(
        ref, ref.channel, Component("CA-d4", 430.34, 100.0, rt=5.0, rt_halfwidth=1.0))
    assert result.note == PROBLEM and result.area == 0.0
    explorer.deleteLater()
    app.processEvents()


def test_a_pinned_spectrum_survives_a_live_one_that_cannot_be_read():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace
    from milq.ui.plots import Trace

    session = Session()
    session.entries.append(_entry())
    explorer = ExplorerWorkspace(session)
    explorer.rebuild_tree()
    mz = np.linspace(100, 200, 20)
    explorer.spectrum.set_traces([Trace("spec", "spectrum", mz, np.ones(20), "#1f77b4")])
    explorer.pin_spectrum()
    explorer._show_scan(3)
    assert [t.key for t in explorer.spectrum.traces] == ["pin1"]
    explorer.deleteLater()
    app.processEvents()


# -- the batch --------------------------------------------------------------- #
def test_a_batch_integration_notes_the_problem_instead_of_stopping():
    entry = _entry()
    method = ProcessingMethod()
    method.replace_all([Component("CA-d4", 430.34, 100.0, rt=5.0, rt_halfwidth=1.0)])
    row = integrate_component(entry, method.components[0], method)
    assert not row.found
    assert row.note == PROBLEM


def test_without_a_diagnosis_the_readers_first_line_is_the_note():
    entry = _entry()
    entry.problem = ""
    method = ProcessingMethod()
    method.replace_all([Component("CA-d4", 430.34, 100.0, rt=5.0, rt_halfwidth=1.0)])
    row = integrate_component(entry, method.components[0], method)
    assert row.note == "could not be read: " + NO_ASSEMBLY


# -- the entry ------------------------------------------------------------- #
def test_the_problem_is_not_saved_with_the_project():
    entry = _entry()
    assert "problem" not in entry.to_dict()
    assert entry == SampleEntry("/d/mix1.wiff", 0, "mix1")


@pytest.mark.parametrize("name", ["a.wiff", "A.WIFF"])
def test_the_companion_is_the_name_plus_scan(name, tmp_path):
    from milq.wiff import scan_file_of
    assert scan_file_of(tmp_path / name) == str(tmp_path / name) + ".scan"
