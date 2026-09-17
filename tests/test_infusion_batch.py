"""
A folder of infusions reported without opening one of them.

What matters here is what the run *refuses* to do. It must not open a `.wiff`
whose companion is missing — the fake reader below records every path it is
given, so the test can say so rather than infer it from the output — it must
not report a chromatographic run as an infusion, and it must not leave either
of those out silently: a folder of three reported as one is only honest if
the other two come back with the reason.

The rest is the shape of the run: one document or one per compound, the CSV,
the components read from a file rather than from a window, the same scores
between infusions of one compound that the tab computes within one session,
and the two ways in — `app.main` with no window at all, and the dialog.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import app  # noqa: E402
from milq import folder as folder_module  # noqa: E402
from milq import infusion_batch as batch  # noqa: E402
from milq import session as session_module  # noqa: E402
from milq.explain import formula_ions  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

FORMULA = "C20H34O2"
ADDUCT = "[M+H]+"
N_SCANS = 160


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _ions() -> list[float]:
    """The formula's ions, the intact one — the precursor — first."""
    ions = formula_ions(FORMULA, ADDUCT, max_losses=2)
    ions.sort(key=lambda ion: (len(ion.losses), -ion.mz))
    return [ion.mz for ion in ions]


def _grid(centres, width: float = 0.05, step: float = 0.005) -> np.ndarray:
    return np.unique(np.concatenate(
        [np.arange(c - width, c + width + step / 2, step) for c in centres]))


def _profile(mz: np.ndarray, peaks: dict) -> np.ndarray:
    out = np.zeros(mz.size)
    for centre, height in peaks.items():
        out += height * np.exp(-0.5 * ((mz - centre) / 0.008) ** 2)
    return out


class _Channel:
    """Enough of `wiff.Channel`: a chromatogram and an averaged spectrum."""

    def __init__(self, index, mz, peaks, precursor=None, flat=True,
                 n=N_SCANS):
        self.index = index
        self.mz = np.asarray(mz, dtype=float)
        self._peaks = dict(peaks)
        self._rt = np.linspace(0.0, 1.5, n)
        if flat:
            self._y = np.full(n, 50_000.0)
        else:                       # three peaks: a chromatogram, not a spray
            self._y = sum(
                50_000.0 * np.exp(-0.5 * ((self._rt - c) / 0.04) ** 2)
                for c in (0.3, 0.7, 1.1)) + 50.0
        self.info = ChannelInfo(
            index=index, name=f"TOF PI {index}",
            experiment_type="Product" if precursor else "TOF MS",
            polarity="Positive", precursor=precursor,
            start_mass=float(self.mz[0]), end_mass=float(self.mz[-1]),
            n_scans=n, collision_energy=20.0 if precursor else None)

    def tic(self):
        return self._rt, self._y

    @property
    def rt(self):
        return self._rt

    def spectrum(self, scan, add_zeros=True):
        return self.mz, _profile(self.mz, self._peaks)

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        return self.mz, _profile(self.mz, self._peaks)

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self._rt - rt)))

    def rt_at_scan(self, scan):
        return float(self._rt[int(np.clip(scan, 0, self._rt.size - 1))])

    def scans_in_range(self, rt_start, rt_end):
        return 0, self._rt.size - 1

    def bpc(self, *args, **kwargs):
        return self._rt, self._y

    def xic(self, mz, tolerance=0.02, unit="Da"):
        return self._rt, self._y

    def xic_range(self, mz_lo, mz_hi):
        return self._rt, self._y

    def parameters(self):
        return {}


class _Sample:
    instrument = "ZenoTOF 7600"
    acquisition_time = "2026-09-10T09:00:00Z"
    problem = None

    def __init__(self, name: str, flat: bool):
        ions = _ions()
        peaks = {ions[0]: 9_000.0, ions[1]: 4_000.0, ions[2]: 2_000.0}
        # a shoulder of its own per compound, so two compounds do not score
        # 100 against each other by construction
        peaks[150.1 + len(name) * 0.01] = 900.0
        self.name = name
        self.channels = [_Channel(0, _grid(list(peaks)), peaks,
                                  precursor=ions[0], flat=flat)]

    def tic(self):
        rt = self.channels[0].rt
        return rt, np.sum([c.tic()[1] for c in self.channels], axis=0)

    def metadata(self):
        return {"Sample": self.name}


class _File:
    """A reader that records every path it was asked to open."""

    opened: list[str] = []

    def __init__(self, path: str):
        self.path = str(path)
        _File.opened.append(self.path)
        self.sample_names = ["mix1"]
        self.closed = False

    def sample(self, index: int):
        name = os.path.splitext(os.path.basename(self.path))[0]
        return _Sample(name, flat="gradient" not in name.lower())

    def close(self):
        self.closed = True


def _write(path, text: str = "not a real acquisition") -> str:
    path.write_text(text)
    return str(path)


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """
    Three acquisitions: an infusion, a gradient, and a broken pair.

    The `.wiff2` beside the first is the one that turns up in every real
    SCIEX folder; it is a finding, not a skip, and nothing must try to read
    it.
    """
    _File.opened = []
    _write(tmp_path / "TESTOL_infusion_mix1.wiff")
    _write(tmp_path / "TESTOL_infusion_mix1.wiff.scan")
    _write(tmp_path / "TESTOL_infusion_mix1.wiff2")
    _write(tmp_path / "TESTOL_gradient_mix1.wiff")
    _write(tmp_path / "TESTOL_gradient_mix1.wiff.scan")
    _write(tmp_path / "OTHEROL_infusion_alone.wiff")     # no companion
    monkeypatch.setattr(session_module, "open_raw", _File)
    return tmp_path


@pytest.fixture
def two_compounds(tmp_path, monkeypatch):
    """Three infusions in three files: two of one compound, one of another."""
    _File.opened = []
    for name in ("TESTOL_infusion_A", "TESTOL_infusion_B",
                 "OTHEROL_infusion_A"):
        _write(tmp_path / f"{name}.wiff")
        _write(tmp_path / f"{name}.wiff.scan")
    monkeypatch.setattr(session_module, "open_raw", _File)
    return tmp_path


def _components_csv(path) -> str:
    path.write_text("name,formula,adduct,precursor\n"
                    f"TESTOL,{FORMULA},{ADDUCT},{_ions()[0]:.4f}\n"
                    f"OTHEROL,{FORMULA},{ADDUCT},{_ions()[0]:.4f}\n")
    return str(path)


# --------------------------------------------------------------------------- #
# what is read, and what is refused
# --------------------------------------------------------------------------- #
def test_a_folder_gives_one_report_and_says_what_it_left_out(qapp, folder):
    out = folder / "report.pdf"
    result = batch.run([str(folder)], str(out))

    assert result.documents == [str(out)] and os.path.exists(out)
    assert result.pages >= 1
    assert result.rows == 1 and result.compounds == ["TESTOL"]
    assert [os.path.basename(p) for p in result.read] == \
        ["TESTOL_infusion_mix1.wiff"]

    kinds = {skip.kind: skip for skip in result.skipped}
    assert set(kinds) == {batch.MISSING_SCAN, batch.NOT_INFUSION}
    assert kinds[batch.MISSING_SCAN].name == "OTHEROL_infusion_alone.wiff"
    assert "no OTHEROL_infusion_alone.wiff.scan" in \
        kinds[batch.MISSING_SCAN].reason
    # the reason a run is not an infusion is the measurement, with figures
    assert "chromatographic" in kinds[batch.NOT_INFUSION].reason
    assert "scans over" in kinds[batch.NOT_INFUSION].reason

    # the one that could not be read whole was never opened at all
    assert not any("alone" in p for p in _File.opened)
    # and the .wiff2 is reported without being read
    assert any(f.kind == folder_module.IGNORED for f in result.findings)
    assert not any(p.endswith(".wiff2") for p in _File.opened)
    assert "1 compound(s) in 1 infusion(s)" in result.line()


def test_one_reader_is_open_at_a_time(qapp, two_compounds):
    """A folder of thirty infusions must not hold thirty readers."""
    live: list[_File] = []
    opened = _File.__init__
    closed = _File.close

    def track_open(self, path):
        opened(self, path)
        live.append(self)
        assert len([f for f in live if not f.closed]) == 1

    def track_close(self):
        closed(self)

    _File.__init__, _File.close = track_open, track_close
    try:
        result = batch.run([str(two_compounds)],
                           str(two_compounds / "r.html"), fmt="html")
    finally:
        _File.__init__, _File.close = opened, closed
    assert result.rows == 3
    assert len(live) == 3 and all(f.closed for f in live)


def test_infusions_of_one_compound_are_scored_across_files(qapp,
                                                           two_compounds):
    """
    One file per session would call every row the only one of its compound.

    `summarise` scores the infusions of a compound against each other within
    the session it is given, and here each session holds one acquisition.
    The scores have to be put back over the merged rows, or the whole point
    of reporting a folder — the same vial under two activations — is lost.
    """
    result = batch.run([str(two_compounds)], str(two_compounds / "r.html"),
                       fmt="html")

    assert result.rows == 3
    by_sample = {row.sample: row for row in result.summary.rows}
    testol = by_sample["TESTOL_infusion_A"]
    assert [label for label, *_rest in testol.others] == ["TESTOL_infusion_B"]
    assert testol.others[0][1] > 0.5              # the same compound
    alone = by_sample["OTHEROL_infusion_A"]
    assert not alone.others
    assert alone.others_note == "the only infusion of this compound"


def test_one_document_per_compound_and_the_csv(qapp, two_compounds, tmp_path):
    csv_path = tmp_path / "summary.csv"
    result = batch.run([str(two_compounds)], str(two_compounds / "each.html"),
                       fmt="html", per_compound=True, csv=str(csv_path))

    names = sorted(os.path.basename(p) for p in result.documents)
    # the cover as a file of its own: the pages it introduces are in the
    # others, so it cannot be printed in front of them
    assert names == ["each-OTHEROL.html", "each-TESTOL.html",
                     "each-cover.html"]
    for path in result.documents:
        if path.endswith("-cover.html"):
            continue
        compound = os.path.basename(path).split("-")[1].split(".")[0]
        with open(path, encoding="utf-8") as handle:
            assert f"<title>{compound} — direct infusion" in handle.read()

    with open(str(two_compounds / "each-cover.html"), encoding="utf-8") as it:
        cover = it.read()
    assert "The infusions" in cover and "What they add up to" in cover
    for row in result.summary.rows:
        assert row.sample in cover
    # it lists no pages: they are in eight other files and it has no numbers
    # for them
    assert "The pages that follow" not in cover

    assert result.csv == str(csv_path)
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("Compound,Sample,Isolated,Mode")
    assert len(lines) == 4                        # a header and three rows


def test_the_component_table_is_read_from_a_file(qapp, folder, tmp_path):
    """The formulas come off disk, since there is no method workspace here."""
    without = batch.run([str(folder)], str(folder / "a.html"), fmt="html")
    assert without.summary.rows[0].report.explanation is None
    assert "not a component of the method" in \
        without.summary.rows[0].explanation_note

    with_table = batch.run(
        [str(folder)], str(folder / "b.html"), fmt="html",
        components=_components_csv(tmp_path / "components.csv"))
    row = with_table.summary.rows[0]
    assert row.report.explanation is not None
    assert row.report.explanation.matched >= 1
    assert FORMULA in row.report.basis


def test_a_project_can_stand_in_for_the_component_table(qapp, tmp_path):
    from milq.method import ProcessingMethod
    from milq.session import PROJECT_SUFFIX

    method = ProcessingMethod()
    method.import_components(_components_csv(tmp_path / "c.csv"))
    project = tmp_path / f"batch{PROJECT_SUFFIX}"
    project.write_text('{"method": %s}' % __import__("json").dumps(
        method.to_dict()))

    read = batch.load_components(project)
    assert [c.name for c in read.components] == ["TESTOL", "OTHEROL"]
    assert read.components[0].formula == FORMULA


def test_nothing_to_report_is_not_a_report(qapp, tmp_path, monkeypatch):
    _File.opened = []
    _write(tmp_path / "TESTOL_gradient_mix1.wiff")
    _write(tmp_path / "TESTOL_gradient_mix1.wiff.scan")
    monkeypatch.setattr(session_module, "open_raw", _File)

    result = batch.run([str(tmp_path)], str(tmp_path / "none.pdf"))
    assert not result.documents and result.rows == 0
    assert not os.path.exists(tmp_path / "none.pdf")
    assert len(result.skipped) == 1
    assert "no infusion among them" in result.line()


def test_a_pdf_that_could_not_be_written_is_not_reported_as_written(
        qapp, folder):
    """
    `QPdfWriter` says nothing when it cannot open its file.

    Measured on the real folder: pointed at a directory that does not exist,
    the run read all nine acquisitions, laid the document out, printed
    `wrote …` and left nothing on disk. So the write is checked.
    """
    with pytest.raises(OSError) as refused:
        batch.run([str(folder)], str(folder / "nowhere" / "x.pdf"))
    assert "was not written" in str(refused.value)


def test_a_stop_writes_nothing(qapp, two_compounds):
    def stop(done, total, name):
        return done < 1

    result = batch.run([str(two_compounds)], str(two_compounds / "x.pdf"),
                       progress=stop)
    assert result.cancelled and not result.documents
    assert result.line() == "Stopped; nothing was written."


# --------------------------------------------------------------------------- #
# the two ways in
# --------------------------------------------------------------------------- #
def test_the_command_line_writes_the_report_and_the_csv(qapp, folder,
                                                        capsys):
    out, csv_path = folder / "cli.html", folder / "cli.csv"
    code = app.main(["--infusion-report", str(folder), "--out", str(out),
                     "--html", "--csv", str(csv_path)])

    assert code == 0
    assert os.path.exists(out) and os.path.exists(csv_path)
    printed = capsys.readouterr().out
    assert "TESTOL_infusion_mix1.wiff" in printed
    assert "skipped OTHEROL_infusion_alone.wiff" in printed
    assert "chromatographic" in printed
    assert "1 compound(s) in 1 infusion(s)" in printed


def test_the_command_line_fails_when_nothing_was_written(qapp, tmp_path,
                                                         monkeypatch):
    _File.opened = []
    monkeypatch.setattr(session_module, "open_raw", _File)
    code = app.main(["--infusion-report", str(tmp_path), "--out",
                     str(tmp_path / "nothing.pdf")])
    assert code == 1


def test_the_command_line_needs_somewhere_to_write(qapp, tmp_path):
    with pytest.raises(SystemExit) as stopped:
        app.main(["--infusion-report", str(tmp_path)])
    assert stopped.value.code == 2


def test_the_dialog_runs_the_same_thing(qapp, folder):
    from milq.ui.help_window import help_page_for
    from milq.ui.infusion_batch_dialog import InfusionBatchDialog

    dialog = InfusionBatchDialog(start_dir=str(folder))
    assert help_page_for(dialog) == "infusion-report"
    assert dialog.folder_edit.text() == str(folder)
    # the report lands in the folder it is made from, under the format chosen
    assert dialog.path_edit.text().endswith("infusion-report.pdf")
    dialog.format_box.setCurrentIndex(1)                      # HTML
    assert dialog.path_edit.text().endswith("infusion-report.html")
    dialog.check_csv.setChecked(True)

    result = dialog.write()
    assert result is not None and len(result.documents) == 1
    assert os.path.exists(result.documents[0])
    assert result.csv.endswith("infusion-report.csv")
    assert os.path.exists(result.csv)
    assert dialog.output_folder == str(folder)
    said = dialog.describe_result()
    assert "1 compound(s) in 1 infusion(s)" in said
    assert "skipped OTHEROL_infusion_alone.wiff" in said

    dialog.deleteLater()
    qapp.processEvents()


def test_the_dialog_says_what_is_missing_rather_than_running(qapp, tmp_path):
    from milq.ui.infusion_batch_dialog import InfusionBatchDialog

    dialog = InfusionBatchDialog(start_dir="")
    dialog.folder_edit.setText("")
    dialog.path_edit.setText("")
    assert dialog.write() is None
    assert "Choose the folder" in dialog.status.text()

    dialog.folder_edit.setText(str(tmp_path / "nowhere"))
    dialog.path_edit.setText(str(tmp_path / "r.pdf"))
    assert dialog.write() is None
    assert "is not there" in dialog.status.text()

    dialog.deleteLater()
    qapp.processEvents()


def test_the_menu_offers_it_whether_or_not_anything_is_open(qapp):
    from milq.ui.shell import MainShell

    window = MainShell()
    assert window.act_infusion_folder.isEnabled()
    assert hasattr(window, "report_infusion_folder")

    window.close()
    window.deleteLater()
    qapp.processEvents()
