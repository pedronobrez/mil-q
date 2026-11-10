"""
SCIEX IDA: the precursor of a dependent slot is per scan.

A synthetic IDA run — a survey and two dependent slots, each slot isolating
a different precursor most cycles and nothing in some — is written through
the mzML writer and read back through the real reader, so every test below
exercises the reader protocol as the application uses it. The `.wiff` half
of the same rule is `tests/real/test_ida_wiff.py`, which needs a real file.
"""

import inspect

import numpy as np
import pytest

from milq import gating, mzml, wiff
from milq.components import Component
from milq.matching import components_from_sample, match_channel
from milq.wiff import ChannelInfo, ScanDetails

#: what each slot isolated, cycle by cycle (NaN: not triggered)
SLOT_1 = [500.2500, 627.8457, np.nan, 627.8460, 712.4000, 627.8455]
SLOT_2 = [np.nan, 410.1000, 627.8459, np.nan, 627.8458, 500.2501]
TIMES = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
FRAGMENT = 136.0757           # a fragment only 627.85 gives
OTHER = 214.1180              # a fragment only the other precursors give


class FakeChannel:
    def __init__(self, index, info, parents=None, survey=False):
        self.index, self.info = index, info
        self._times = np.asarray(TIMES, dtype=float)
        n = len(TIMES)
        if parents is None:
            self._details = ScanDetails.constant(n, None, None, None)
        else:
            parents = np.asarray(parents, dtype=float)
            self._details = ScanDetails(
                parents, np.where(np.isfinite(parents), 1.0, np.nan),
                np.where(np.isfinite(parents), 35.0, np.nan),
                np.where(np.isfinite(parents), 2, 0).astype(np.int64))
        self._spectra = []
        for scan in range(n):
            if survey:
                self._spectra.append((np.array([500.25, 627.8457, 712.40]),
                                      np.array([3000.0, 9000.0, 1500.0])))
                continue
            parent = self._details.parent_mz[scan]
            if not np.isfinite(parent):
                self._spectra.append((np.zeros(0), np.zeros(0)))
            elif abs(parent - 627.8457) < 0.01:
                # the fragment, and the surviving precursor as a small
                # profile peak with zeros either side, as a TOF records it
                self._spectra.append((
                    np.array([FRAGMENT, 627.8357, 627.8407, 627.8457,
                              627.8507, 627.8557]),
                    np.array([1000.0 + 100 * scan, 0.0, 20.0, 50.0, 20.0, 0.0])))
            else:
                self._spectra.append((np.array([OTHER]), np.array([777.0])))

    def tic(self):
        return self._times, np.array([float(np.sum(s[1])) for s in self._spectra])

    @property
    def rt(self):
        return self._times

    def spectrum(self, scan, add_zeros=True):
        return self._spectra[int(scan)]

    def scan_details(self):
        return self._details


class FakeSample:
    name = "ida"
    instrument = "TripleTOF 5600"
    acquisition_time = ""

    def __init__(self, channels):
        self.channels = channels


def _slot(index, parents):
    # FixedMasses on a real slot is the slot's number: the placeholder
    info = ChannelInfo(index, "TOF PI", "Product", "Positive", None,
                       50.0, 1000.0, len(TIMES), 35.0, kind=wiff.KIND_IDA_SLOT)
    return FakeChannel(index, info, parents)


@pytest.fixture
def ida(tmp_path):
    survey = FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                        100.0, 1500.0, len(TIMES), None,
                                        kind=wiff.KIND_MS1), survey=True)
    path = tmp_path / "ida.mzML"
    mzml.write_mzml(FakeSample([survey, _slot(1, SLOT_1), _slot(2, SLOT_2)]), path)
    reader = mzml.MzmlFile(path)
    yield reader.sample(0)
    reader.close()


# --------------------------------------------------------------------------- #
def test_a_slot_is_an_ida_slot_with_no_channel_precursor(ida):
    survey, one, two = ida.channels
    assert survey.info.kind == wiff.KIND_MS1 and survey.info.is_ms1
    for slot in (one, two):
        assert slot.info.kind == wiff.KIND_IDA_SLOT
        assert slot.info.precursor is None
        assert not slot.info.is_ms1
        assert slot.info.per_scan
        assert "IDA slot" in slot.info.short_label


def test_untriggered_cycles_are_not_written(ida):
    _survey, one, two = ida.channels
    assert one.info.n_scans == 5 and two.info.n_scans == 4


def test_the_precursor_is_each_scans_own(ida):
    _survey, one, two = ida.channels
    want_1 = [p for p in SLOT_1 if np.isfinite(p)]
    want_2 = [p for p in SLOT_2 if np.isfinite(p)]
    assert one.scan_precursors() == pytest.approx(want_1, abs=1e-6)
    assert two.scan_precursors() == pytest.approx(want_2, abs=1e-6)
    assert np.all(np.isnan(ida.channels[0].scan_precursors()))
    assert one.scan_details().isolation == pytest.approx([1.0] * 5)
    assert set(one.scan_details().charge) == {2}


def test_a_gate_takes_only_the_scans_that_isolated_the_target(ida):
    refs = gating.selected_scans(ida, gating.Source.gated(627.8457))
    # three in slot 1, two in slot 2, none of 500.25 / 712.40 / 410.10
    assert [(r.channel, round(r.rt, 2)) for r in refs] == [
        (1, 0.2), (2, 0.3), (1, 0.4), (2, 0.5), (1, 0.6)]
    assert all(abs(r.parent_mz - 627.8457) <= 0.05 for r in refs)


def test_a_gated_xic_has_none_of_the_other_precursors(ida):
    gated = gating.xic(ida, FRAGMENT - 0.01, FRAGMENT + 0.01,
                       gating.Source.gated(627.8457))
    assert gated.rt == pytest.approx([0.2, 0.3, 0.4, 0.5, 0.6])
    assert gated.intensity.min() > 0
    other = gating.xic(ida, OTHER - 0.01, OTHER + 0.01,
                       gating.Source.gated(627.8457))
    assert other.intensity.sum() == 0
    every = gating.xic(ida, OTHER - 0.01, OTHER + 0.01,
                       gating.Source.parse("ms2-all"))
    assert every.intensity.sum() == pytest.approx(4 * 777.0)


def test_a_gated_spectrum_averages_its_scans_and_lists_them(ida):
    gated = gating.spectrum(ida, gating.Source.gated(627.8457, 0.01), (0.0, 1.0))
    assert len(gated.scans) == 5
    assert OTHER not in np.round(gated.mz, 4)
    frag = gated.intensity[np.argmin(abs(gated.mz - FRAGMENT))]
    # slot scans 1,2(slot2),2,3,4(slot2),5 → heights by write order; the mean
    assert frag == pytest.approx(np.mean([g.intensity.max() for g in
                                          [gating.spectrum(ida, gating.Source(
                                              "channel", channel=r.channel),
                                              scan=r.scan) for r in gated.scans]]))
    # an average over a slot that mixes precursors has no precursor
    one = ida.channels[1]
    assert gating.precursor_shown(one, rt0=0.0, rt1=1.0) is None
    assert "mixes" in gating.describe_precursors(
        gating.precursors_shown(one, rt0=0.0, rt1=1.0))
    assert gating.precursor_shown(one, scan=1) == pytest.approx(627.8457)


def test_no_component_is_served_from_a_slot(ida):
    component = Component(name="pE-QPLAPVHNPISV", precursor=627.8457,
                          fragment=FRAGMENT, rt=0.4)
    assert match_channel(ida, component) is ida.channels[0]   # the survey
    assert components_from_sample(ida) == []


def test_the_surviving_precursor_reads_the_gated_scans(ida):
    from milq.precursor import _surviving_precursor
    from milq.samples import SampleEntry

    entry = SampleEntry(path="ida.mzML", sample_index=0, name="ida")
    entry.sample = ida
    component = Component(name="pep", precursor=627.85, fragment=FRAGMENT)
    found = _surviving_precursor(entry, component, 0.15, 0.65, 0.4, 0.25)
    assert found == pytest.approx(627.8457, abs=1e-3)


def test_exporting_again_keeps_every_precursor(ida, tmp_path):
    again = tmp_path / "again.mzML"
    mzml.write_mzml(ida, again)
    reader = mzml.MzmlFile(again)
    try:
        back = reader.sample(0)
        for a, b in zip(ida.channels, back.channels):
            assert a.info.kind == b.info.kind
            pa, pb = a.scan_precursors(), b.scan_precursors()
            assert np.array_equal(np.isnan(pa), np.isnan(pb))
            assert pa[np.isfinite(pa)] == pytest.approx(pb[np.isfinite(pb)],
                                                        abs=1e-6)
    finally:
        reader.close()


def test_sources_parse_and_print():
    assert str(gating.Source.parse("gated:627.8457")) == "gated:627.8457:0.05"
    assert gating.Source.parse("channel:3").channel == 3
    assert gating.Source.parse("MS2-ALL").kind == "ms2-all"
    with pytest.raises(gating.SourceError):
        gating.Source.parse("gated:")


# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("wiff_class, mzml_class", [
    (wiff.Channel, mzml.MzmlChannel),
    (wiff.Sample, mzml.MzmlSample),
    (wiff.WiffFile, mzml.MzmlFile),
])
def test_the_readers_share_one_surface(wiff_class, mzml_class):
    """The reader protocol, by reflection: names and parameters alike."""
    def surface(cls):
        out = {}
        for name in dir(cls):
            if name.startswith("_"):
                continue
            member = getattr(cls, name)
            if callable(member):
                out[name] = [(p.name, p.kind, p.default)
                             for p in inspect.signature(member).parameters.values()]
            else:
                out[name] = "attribute"
        return out
    assert surface(wiff_class) == surface(mzml_class)


# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_explorer_extracts_a_gated_xic_and_names_the_parent(ida, qapp):
    from milq.samples import SampleEntry
    from milq.session import Session
    from milq.ui.explorer import ChannelRef, ExplorerWorkspace

    entry = SampleEntry(path="ida.mzML", sample_index=0, name="ida")
    entry.sample = ida
    explorer = ExplorerWorkspace(Session())
    try:
        slot = ida.channels[1]
        explorer.active_ref = ChannelRef(entry, slot)
        explorer.set_xic_source("gated:627.8457:0.05")
        assert str(explorer._xic_source()) == "gated:627.8457:0.05"
        explorer.xic_tol.setValue(0.01)
        explorer.xic_unit.setCurrentText("Da")
        explorer.xic_mz.setText(f"{FRAGMENT:.4f}")
        explorer._extract_from_form()
        assert len(explorer.xic_defs) == 1
        made = explorer.xic_defs[0]
        assert "gated:627.8457" in made["label"]
        assert list(np.round(made["x"], 2)) == [0.2, 0.3, 0.4, 0.5, 0.6]

        explorer._show_scan(1)
        assert "parent 627.8457" in explorer.spectrum.title
        assert explorer._shown_precursor(slot) == pytest.approx(627.8457)
        explorer._show_average(0.0, 1.0)
        assert "mixes" in explorer.spectrum.title
        assert explorer._shown_precursor(slot) is None
    finally:
        explorer.deleteLater()
        qapp.processEvents()
