"""
Eight ZenoTOF 7600 DIA runs of a liver lipidomics method, 25 windows each.

They are here for two things. They are eight of the thirty-nine
chromatographic runs the infusion verdict was measured against — including the
one that comes closest to reading flat, a column equilibration with no
injection in it at all — and they are the hardest case for inferring channels
from an mzML, because every one of the 25 windows writes the same precursor.
"""

from __future__ import annotations

import dataclasses
import glob
import os

import numpy as np
import pytest

from milq import infusion, mzml
from milq.raw import open_raw

from . import data


@pytest.fixture(scope="module")
def files():
    found = sorted(glob.glob(os.path.join(data.dia(), "*.wiff")))
    if len(found) != 8:
        pytest.skip(f"{data.dia()} holds {len(found)} .wiff, not 8")
    return found


def test_all_eight_read_as_chromatography(files):
    """
    `milq/infusion.py`'s measured table: eight DIA runs, 24.0 min,
    482–490 scans, 25 channels, measuring 0.031 – 0.364 on the sample total
    and 0.015 – 0.060 on the strongest channel.

    "`260406-Teste-Eq01` is a column equilibration with no injection at all —
    solvent spraying for 24 minutes, the nearest thing in the set to an
    infusion — and measures 0.364 on the sample total against 0.060 on its
    strongest channel." That second figure is what keeps it out.
    """
    totals, channels = {}, {}
    for path in files:
        handle = open_raw(path)
        try:
            sample = handle.sample(0)
            assert len(sample.channels) == 25
            verdict = infusion.is_infusion(sample)
            assert not verdict.infusion and not verdict.too_short
            assert 482 <= verdict.n_scans <= 490
            totals[os.path.basename(path)] = verdict.above_half
            channels[os.path.basename(path)] = verdict.channel_above_half
        finally:
            handle.close()
    assert min(totals.values()) == pytest.approx(0.031, abs=0.001)
    assert max(totals.values()) == pytest.approx(0.364, abs=0.001)
    assert min(channels.values()) == pytest.approx(0.015, abs=0.001)
    assert max(channels.values()) == pytest.approx(0.060, abs=0.001)
    assert totals["260406-Teste-Eq01.wiff"] == pytest.approx(0.364, abs=0.001)
    assert channels["260406-Teste-Eq01.wiff"] == pytest.approx(0.060, abs=0.001)
    # every one of them is under the cut on both figures, with room to spare
    assert max(min(totals[name], channels[name]) for name in totals) < 0.15


def test_twenty_five_windows_that_scan_properties_cannot_tell_apart(files, tmp_path):
    """
    CLAUDE.md: "mzML has no idea of an experiment. Channels are inferred…
    `mzml.acquisition_cycles` recovers them from the order of acquisition."

    On the 81-channel MRM-HR file the properties get 69 of 81. Here they get
    **2 of 25**: this acquisition writes the same precursor — 829.50 — on all
    twenty-five DIA windows, so a survey and one product-ion key is everything
    the scan headers hold. The cycle recovers all 25, and the run's total ion
    chromatogram comes back as the instrument's own 484 points rather than as
    12,100.
    """
    handle = open_raw(files[0])
    try:
        sample = handle.sample(0)
        assert {channel.info.precursor for channel in sample.channels[1:]} == {829.5}
        path = tmp_path / "dia.mzML"
        mzml.write_mzml(sample, path)
        back = open_raw(path)
        try:
            assert len(back.headers) == 12_100
            assert len(back.sample(0).channels) == 25
            plain = [dataclasses.replace(header, experiment=None).key
                     for header in back.headers]
            assert len(set(plain)) == 2
            cycles = mzml.acquisition_cycles(plain)
            assert all(cycle is not None for cycle in cycles)
            assert len({cycle for cycle in cycles}) == 25

            x1, y1 = sample.tic()
            x2, y2 = back.sample(0).tic()
            assert len(x1) == len(x2) == 484
            assert float(np.max(np.abs(y1 - y2))) == 0.0
        finally:
            back.close()
    finally:
        handle.close()
