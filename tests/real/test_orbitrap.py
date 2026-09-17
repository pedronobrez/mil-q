"""
Two Thermo Orbitrap mzML from MTBLS13066 — the instrument this program has
never read a raw file from.

`CLAUDE.md` calls both of them stated gaps: the mzML reader handles them, and
neither reads as an infusion although both were sprayed as one. They are the
only files in `tests/real` that are not SCIEX, which is the whole point of
keeping them: everything above `raw.py` is supposed not to know.

They were downloaded into a scratch directory to answer one question and were
never put anywhere permanent, so these tests skip themselves more often than
they run. `MILQ_REAL_ORBITRAP` points at the folder.
"""

from __future__ import annotations

import numpy as np
import pytest

from milq import infusion
from milq.raw import open_raw

from . import data

MS1 = "180A_D_H_ms1.mzML"
STEPPED = "180A_D_H_1Dawin_0-02step_35NCE.mzML"


def test_a_spray_that_ramps_for_ten_seconds_reads_chromatographic():
    """
    CLAUDE.md: "a 108-scan Orbitrap spray ramps for ten seconds where
    `SETTLING_SECONDS` is 1 (0.8812 with ten)".

    A stated gap, asserted as a gap: 108 scans, one channel, and the run reads
    0.5943 flat — below `FLAT_FRACTION`, so it is called chromatography —
    because the first ten seconds are the spray coming up and only the first
    second is dropped. Given ten seconds of settling the same trace reads
    **0.880** and would be called an infusion, which is the whole finding: one
    settling constant does not fit two instruments, and `SETTLING_SECONDS`
    is 1 because that is what the SCIEX files needed. CLAUDE.md's figure is
    0.8812, taken before the reference percentile moved behind the settling
    window.
    """
    handle = open_raw(data.orbitrap_file(MS1))
    try:
        sample = handle.sample(0)
        assert len(sample.channels) == 1
        assert len(handle.headers) == 108
        x, y = sample.tic()
        assert len(x) == 108
        verdict = infusion.is_infusion(sample)
        assert not verdict.infusion
        assert verdict.above_half == pytest.approx(0.5943, abs=0.001)
        settled = infusion.flat_fraction(*infusion.after_settling(x, y, 10.0))
        assert settled == pytest.approx(0.880, abs=0.002)
        assert settled > infusion.FLAT_FRACTION
        assert verdict.above_half < infusion.FLAT_FRACTION
    finally:
        handle.close()


def test_a_stepped_precursor_run_is_82_channels_and_164_points():
    """
    CLAUDE.md: "`MzmlSample.tic` grouped channels by scan count (a
    164-spectrum Thermo infusion came back as 8 points); the period now comes
    from `acquisition_cycles`."

    This is that file. 164 spectra over 82 channels — a precursor stepped in
    0.02 Da — and its total ion chromatogram is 164 points, one per spectrum,
    because two passes of a cycle are not a cycle (`MIN_REPEATS` is four) and
    the reader falls back to the scan properties rather than inventing a
    period. Eight would be the bug.

    It reads chromatographic, and CLAUDE.md says why: "a stepped-precursor
    DI-MS/MS run is a falling ion current by construction".
    """
    handle = open_raw(data.orbitrap_file(STEPPED))
    try:
        sample = handle.sample(0)
        assert len(handle.headers) == 164
        assert len(sample.channels) == 82
        x, y = sample.tic()
        assert len(x) == 164
        assert len(x) == len(y)
        assert float(np.sum(y)) > 0
        verdict = infusion.is_infusion(sample)
        assert not verdict.infusion
        assert verdict.above_half == pytest.approx(0.0123, abs=0.001)
    finally:
        handle.close()
