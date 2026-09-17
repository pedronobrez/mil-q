"""
The spectrum pane saved with the project, and put back when it is opened.

An infusion project's whole result is a comparison of averaged spectra: the
pins, the label floor that decides which masses are named, and the two
switches that make the comparison readable. Saving the batch and losing all
of that means the project reopens as a list of files.

What is saved is the *recipe* of each pinned spectrum — which sample, which
channel, which scan or stretch of time — and never its points, so the
project stays a small JSON document that points at the raw files rather than
a copy of them. Which means the spectra are read again on load, and the test
that matters is that they come back point for point.

The fakes below are a reader whose spectra depend on the scan, so a recipe
that reads the wrong scan cannot pass by accident.
"""

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import labels as label_rule  # noqa: E402
from milq import session as session_module  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.spectra_compare import SpectrumRecipe  # noqa: E402
from milq.ui.explorer import ExplorerWorkspace  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

N_SCANS = 24


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Channel:
    """A channel whose every scan is a different spectrum."""

    def __init__(self, index: int, offset: float):
        self.index = index
        self._offset = offset
        self.mz = np.linspace(100.0, 200.0, 401)
        self._rt = np.linspace(0.0, 2.0, N_SCANS)
        self.info = ChannelInfo(
            index=index, name=f"TOF PI {index}", experiment_type="Product",
            polarity="Positive", precursor=430.0 + index,
            start_mass=100.0, end_mass=200.0, n_scans=N_SCANS,
            collision_energy=20.0)

    @property
    def rt(self):
        return self._rt

    def _scan(self, scan: int) -> np.ndarray:
        centre = 120.0 + self._offset + 0.01 * scan
        return (1_000.0 * (scan + 1) + self._offset) * np.exp(
            -0.5 * ((self.mz - centre) / 0.05) ** 2)

    def spectrum(self, scan, add_zeros=True):
        return self.mz, self._scan(int(scan))

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        first, last = self.scans_in_range(rt_start, rt_end)
        return self.mz, np.mean(
            [self._scan(s) for s in range(first, last + 1)], axis=0)

    def tic(self):
        return self._rt, np.array([self._scan(s).sum() for s in range(N_SCANS)])

    def bpc(self, *args, **kwargs):
        return self.tic()

    def xic(self, mz, tolerance=0.02, unit="Da"):
        return self.tic()

    def xic_range(self, mz_lo, mz_hi):
        return self.tic()

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self._rt - rt)))

    def rt_at_scan(self, scan):
        return float(self._rt[int(np.clip(scan, 0, N_SCANS - 1))])

    def scans_in_range(self, rt_start, rt_end):
        lo, hi = sorted((float(rt_start), float(rt_end)))
        inside = np.nonzero((self._rt >= lo) & (self._rt <= hi))[0]
        if inside.size == 0:
            return 0, 0
        return int(inside[0]), int(inside[-1])

    def parameters(self):
        return {}


class _Sample:
    instrument = "ZenoTOF 7600"
    acquisition_time = "2026-09-10T09:00:00Z"
    problem = None

    def __init__(self, name: str, offset: float):
        self.name = name
        self.channels = [_Channel(0, offset), _Channel(1, offset + 7.0)]

    def tic(self):
        rt = self.channels[0].rt
        return rt, np.sum([c.tic()[1] for c in self.channels], axis=0)

    def metadata(self):
        return {"Sample": self.name}


class _File:
    """Enough of a reader for a session to open and reopen."""

    def __init__(self, path: str):
        self.path = path
        self.sample_names = ["mix1"]
        self.closed = False

    def sample(self, index: int):
        name = os.path.splitext(os.path.basename(self.path))[0]
        return _Sample(name, offset=float(len(name)))

    def close(self):
        self.closed = True


@pytest.fixture
def fake_files(tmp_path, monkeypatch):
    """Two openable acquisitions, and `open_raw` giving the fake reader."""
    paths = []
    for name in ("CA-d4_Mix1.wiff", "CA-d4_EAD_22CE_mix1.wiff"):
        path = tmp_path / name
        path.write_bytes(b"not a real acquisition")
        paths.append(str(path))
    monkeypatch.setattr(session_module, "open_raw", _File)
    return paths


def _explorer(session):
    return ExplorerWorkspace(session)


def _pin_whole_run(explorer, ref_key: str) -> None:
    """Land on a channel, average the whole run, and pin it — what the
    Infusions flow does for a sample with no chromatography."""
    explorer._make_active(ref_key)
    explorer.average_whole_run()
    explorer.pin_spectrum()


def _saved(session, tmp_path, name="view") -> str:
    session.save_project(str(tmp_path / name))
    return session.project_path


# --------------------------------------------------------------------------- #
def test_the_pins_the_floor_and_the_switches_come_back(qapp, tmp_path,
                                                       fake_files):
    """
    The round trip: two whole-run averages pinned, the floor at 0.5%, and
    the project reopened into a second window.

    The arrays are compared point for point, because a recipe that came back
    with a spectrum of the right shape and the wrong scan would pass any
    softer test.
    """
    session = Session()
    explorer = _explorer(session)
    for path in fake_files:
        session.open_file(path)

    first, second = (f"{path}|0|0" for path in fake_files)
    _pin_whole_run(explorer, first)
    _pin_whole_run(explorer, second)
    explorer.floor_spin.setValue(0.5)
    explorer.act_norm.setChecked(True)
    explorer.act_mirror.setChecked(True)
    explorer._show_scan(5)          # the live spectrum is somewhere else

    before = [(t.label, t.x.copy(), t.y.copy()) for t in explorer.pinned_spectra]
    assert session.spectra_comparison.stands
    path = _saved(session, tmp_path)

    reopened = Session()
    other = _explorer(reopened)
    assert reopened.load_project(path) == []

    after = other.pinned_spectra
    assert [t.label for t in after] == [label for label, _x, _y in before]
    for (label, x, y), trace in zip(before, after):
        assert np.array_equal(trace.x, x), label
        assert np.array_equal(trace.y, y), label
    # the floor, the switches and the live spectrum's own recipe
    assert other.spectrum.label_floor == pytest.approx(0.005)
    assert other.act_norm.isChecked() and other.act_mirror.isChecked()
    assert other._live_recipe.scan == 5
    assert "scan 6" in other.spectrum.title
    # and the comparison the report prints stands at once, at that floor
    comparison = reopened.spectra_comparison
    assert comparison is not None and comparison.stands
    assert comparison.label_floor == pytest.approx(0.005)
    assert len(comparison.traces) == 3       # the live one first, then the pins
    assert comparison.normalise and comparison.mirror

    explorer.deleteLater()
    other.deleteLater()
    qapp.processEvents()


def test_what_is_saved_is_the_recipe_and_not_the_points(qapp, tmp_path,
                                                        fake_files):
    """A pin is 401 points here and a hundred thousand on a real infusion.
    What goes into the project is how it was made."""
    session = Session()
    explorer = _explorer(session)
    session.open_file(fake_files[0])
    _pin_whole_run(explorer, f"{fake_files[0]}|0|1")
    path = _saved(session, tmp_path)

    data = json.loads(open(path, encoding="utf-8").read())
    assert data["version"] == 5
    view = data["view"]
    assert view["pins"] == [{
        "sample_key": f"{fake_files[0]}|0",
        "channel": 1, "scan": None,
        "rt0": 0.0, "rt1": 2.0, "whole_run": True,
        "background": None,
        "label": view["pins"][0]["label"],
        "colour": explorer.PIN_COLOURS[0],
    }]
    assert view["live"]["whole_run"] is True
    # the whole project, two spectra pinned, is a few kilobytes
    assert os.path.getsize(path) < 8_000

    explorer.deleteLater()
    qapp.processEvents()


def test_a_pin_whose_file_is_gone_says_so_and_stays_listed(qapp, tmp_path,
                                                           fake_files):
    """
    A comparison that quietly came back one spectrum short would be read as
    the comparison that was saved. The pin stays in the list, with nothing
    in it and the reason in its name.
    """
    session = Session()
    explorer = _explorer(session)
    for path in fake_files:
        session.open_file(path)
    _pin_whole_run(explorer, f"{fake_files[0]}|0|0")
    _pin_whole_run(explorer, f"{fake_files[1]}|0|0")
    project = _saved(session, tmp_path)

    os.remove(fake_files[1])
    reopened = Session()
    other = _explorer(reopened)
    assert reopened.load_project(project) == [fake_files[1]]

    pins = other.pinned_spectra
    assert len(pins) == 2
    assert pins[0].x.size and other.PIN_MISSING not in pins[0].label
    assert pins[1].x.size == 0 and other.PIN_MISSING in pins[1].label
    # the recipe survives even where the spectrum could not be made
    assert pins[1].recipe.sample_key == f"{fake_files[1]}|0"
    # two traces with points in them is what a comparison needs; there is one
    assert not reopened.spectra_comparison.stands

    explorer.deleteLater()
    other.deleteLater()
    qapp.processEvents()


def test_a_project_written_before_the_view_existed_opens_with_defaults(
        qapp, tmp_path, fake_files):
    """Version 4 has no `view` key, and that is the right answer for it."""
    session = Session()
    explorer = _explorer(session)
    session.open_file(fake_files[0])
    path = _saved(session, tmp_path, "older")
    data = json.loads(open(path, encoding="utf-8").read())
    data["version"] = 4
    data.pop("view")
    open(path, "w", encoding="utf-8").write(json.dumps(data))

    reopened = Session()
    other = _explorer(reopened)
    assert reopened.load_project(path) == []
    assert other.pinned_spectra == []
    assert other.spectrum.label_floor == pytest.approx(
        label_rule.LABEL_MIN_RELATIVE)
    assert reopened.spectra_comparison is None

    explorer.deleteLater()
    other.deleteLater()
    qapp.processEvents()


def test_a_pinned_scan_carries_its_background_window(qapp, tmp_path,
                                                     fake_files):
    """A spectrum with a blank subtracted is not the raw one, so the window
    that made it is part of the recipe — and is subtracted again on load."""
    session = Session()
    explorer = _explorer(session)
    session.open_file(fake_files[0])
    explorer._make_active(f"{fake_files[0]}|0|0")
    explorer.chrom.set_background_range(0.0, 0.3)
    explorer._show_scan(9)
    explorer.pin_spectrum()
    assert explorer._live_recipe.background == (0.0, 0.3)
    subtracted = explorer.pinned_spectra[0].y.copy()
    path = _saved(session, tmp_path, "background")

    reopened = Session()
    other = _explorer(reopened)
    reopened.load_project(path)
    assert np.array_equal(other.pinned_spectra[0].y, subtracted)
    # and it is not simply the unsubtracted spectrum
    channel = reopened.entries[0].sample.channels[0]
    assert not np.array_equal(subtracted, channel.spectrum(9)[1])

    explorer.deleteLater()
    other.deleteLater()
    qapp.processEvents()


def test_the_recipe_is_readable_where_the_pin_is(qapp, tmp_path, fake_files):
    """Whoever reads the legend can see which scan of which sample it was."""
    session = Session()
    explorer = _explorer(session)
    session.open_file(fake_files[0])
    explorer._make_active(f"{fake_files[0]}|0|1")
    explorer._show_scan(3)
    explorer.pin_spectrum()

    recipe = explorer.pinned_spectra[0].recipe
    assert recipe.describe().startswith("CA-d4_Mix1.wiff sample 1 · channel 1")
    assert "scan 4" in recipe.describe()
    assert recipe.describe() in explorer.spectrum.toolTip()

    explorer.unpin_spectra()
    assert explorer.spectrum.toolTip() == ""

    explorer.deleteLater()
    qapp.processEvents()


def test_a_recipe_round_trips_through_its_dictionary():
    """The one part with no window in it."""
    recipe = SpectrumRecipe(sample_key="/d/a.wiff|0", channel=2, rt0=0.1,
                            rt1=1.4, background=(0.0, 0.2), label="A",
                            colour="#e08a1e")
    assert SpectrumRecipe.from_dict(recipe.to_dict()) == recipe
    assert SpectrumRecipe.from_dict(None) is None
    assert SpectrumRecipe.from_dict({}) is None
    assert recipe.kind == "range"
    assert SpectrumRecipe(scan=0).kind == "scan"
    assert SpectrumRecipe(whole_run=True).kind == "whole run"
    # a project written by hand, or by a future version, is read for what it has
    loose = SpectrumRecipe.from_dict({"sample_key": "/d/a.wiff|0",
                                      "background": "nonsense"})
    assert loose.background is None and loose.channel is None
