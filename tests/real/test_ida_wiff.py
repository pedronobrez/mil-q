"""
A real SCIEX IDA `.wiff`: the precursor of a dependent slot is per scan.

Measured on a TripleTOF 5600 HILIC ESI+ acquisition (one TOF MS survey, eight
dependent TOF PI slots, 1,986 cycles): the slots declare `FixedMasses` of
1.0, 2.0 … 8.0 — the slot's number — while `ParentMZ` changed almost every
cycle (slot 1: 405 triggered cycles, 298 distinct precursors at 0.001 Da;
the eight slots 405, 361, 330, 301, 271, 248, 232, 216 triggered). Cycle 0
of every slot was untriggered with a collision energy of 0, which is where
the channel's energy used to be read; the triggered scans say 35.

What follows asserts what is true of any IDA file, so `MILQ_TEST_WIFF` can
name whichever one is at hand.
"""

from __future__ import annotations

import numpy as np
import pytest

from milq import gating, mzml, wiff
from milq.matching import components_from_sample

from . import data


@pytest.fixture(scope="module")
def sample():
    reader = wiff.WiffFile(data.ida_wiff())
    yield reader.sample(0)
    reader.close()


@pytest.fixture(scope="module")
def slots(sample):
    found = [c for c in sample.channels if c.info.kind == wiff.KIND_IDA_SLOT]
    if not found:
        pytest.skip(f"{data.ida_wiff()} has no IDA dependent experiment")
    return found


def test_no_slot_carries_the_placeholder(sample, slots):
    for slot in slots:
        fixed = list(slot._exp.Details.MassRangeInfo[0].FixedMasses or [])
        assert slot.info.precursor is None, fixed
        assert not slot.info.is_ms1
    assert [c for c in sample.channels if c.info.is_ms1]


def test_each_scan_has_its_own_precursor(slots):
    first = slots[0]
    parents = first.scan_precursors()
    assert parents.size == first.info.n_scans
    triggered = parents[np.isfinite(parents)]
    assert triggered.size > 0
    assert np.all(triggered > 0)
    # far more than one: the placeholder was one number for the whole slot
    assert np.unique(np.round(triggered, 3)).size > triggered.size // 4


def test_an_untriggered_cycle_has_no_points(slots):
    slot = slots[0]
    parents = slot.scan_precursors()
    for cycle in np.nonzero(~np.isfinite(parents))[0][:20]:
        assert slot._exp.GetMassSpectrum(int(cycle)).NumDataPoints == 0


def test_the_channel_energy_is_a_triggered_scans(slots):
    for slot in slots:
        energies = slot.scan_details().collision_energy
        energies = energies[np.isfinite(energies) & (energies != 0)]
        if energies.size:
            assert slot.info.collision_energy == pytest.approx(energies[0])


def test_a_gate_reads_only_its_precursor(sample, slots):
    parents = np.concatenate([s.scan_precursors() for s in slots])
    parents = parents[np.isfinite(parents)]
    values, counts = np.unique(np.round(parents, 2), return_counts=True)
    target = float(values[np.argmax(counts)])
    gated = gating.spectrum(sample, gating.Source.gated(target))
    assert gated.scans
    assert np.all(np.abs(gated.parents - target) <= gating.DEFAULT_PARENT_TOL + 0.005)
    peak = float(gated.mz[np.argmax(gated.intensity)])
    trace = gating.xic(sample, peak - 0.02, peak + 0.02, gating.Source.gated(target))
    every = gating.xic(sample, peak - 0.02, peak + 0.02, gating.Source.parse("ms2-all"))
    assert 0 < trace.rt.size < every.rt.size


def test_no_component_comes_from_a_placeholder(sample, slots):
    names = {c.name for c in components_from_sample(sample)}
    assert not names & {f"{float(i):.2f}" for i in range(1, len(slots) + 1)}


def test_the_export_keeps_every_precursor(sample, slots, tmp_path_factory):
    path = tmp_path_factory.mktemp("ida") / "ida.mzML"
    mzml.write_mzml(sample, path)
    reader = mzml.MzmlFile(path)
    try:
        back = reader.sample(0)
        assert len(back.channels) == len(sample.channels)
        for a, b in zip(sample.channels, back.channels):
            assert b.info.kind == a.info.kind
            pa = a.scan_precursors()
            pa = pa[np.isfinite(pa)]
            pb = b.scan_precursors()
            pb = pb[np.isfinite(pb)]
            assert pb == pytest.approx(pa, abs=5e-7)
    finally:
        reader.close()


def test_another_programs_mzml_of_it_is_a_survey_and_ms2_events(
        sample, slots, tmp_path_factory):
    """
    The same run written to mzML without our experiment parameters — which
    is what any other converter's file of it is — read as 1,177 channels,
    one per precursor, before A2. It is the survey and one channel of
    events, each scan with its own precursor.
    """
    import re

    folder = tmp_path_factory.mktemp("dda")
    ours = folder / "ours.mzML"
    mzml.write_mzml(sample, ours)
    theirs = folder / "theirs.mzML"
    theirs.write_bytes(re.sub(rb'<userParam name="milq experiment[^"]*"[^>]*/>',
                              b"", ours.read_bytes()))
    reader = mzml.MzmlFile(theirs)
    try:
        back = reader.sample(0)
        assert [c.info.kind for c in back.channels] == ["ms1", "dda-events"]
        events = back.channels[1]
        triggered = sum(int(np.isfinite(s.scan_precursors()).sum()) for s in slots)
        assert events.info.n_scans == triggered
        assert back.channels[0].info.n_scans == sample.channels[0].info.n_scans
    finally:
        reader.close()


def test_the_vendor_centroids_a_scan_and_a_range(sample):
    """
    `GetPeakArray(cycle)` and `(rt0, rt1)`. Measured on a TripleTOF 5600
    survey scan: 4,561 vendor peaks against 13,764 local maxima, the same
    heights over the 200 tallest (median ratio 1.00).
    """
    from milq.processing import centroid_spectrum

    survey = next(c for c in sample.channels if c.info.is_ms1)
    scan = survey.info.n_scans // 2
    mz, height = survey.vendor_centroids(scan=scan)
    assert mz.size > 0 and np.all(np.diff(mz) >= 0) and np.all(height > 0)
    local, _ = centroid_spectrum(*survey.spectrum(scan))
    assert mz.size < local.size
    rt = survey.rt_at_scan(scan)
    ranged = survey.vendor_centroids(rt_start=rt, rt_end=survey.rt_at_scan(scan + 5))
    assert ranged is not None and ranged[0].size > 0
