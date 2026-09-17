"""
The five `260904_EICs_Isabela_*.wiff` — TripleTOF 5600, 81 channels, 577 cycles.

These are the acquisitions every reader figure in `CLAUDE.md` was measured on:
the digest that says two builds agree, the channel count mzML has to infer,
and the one place where the two formats do not.

Nothing here is a unit test. Each one runs the shipped code over the real
files and checks that a number written down somewhere — `CLAUDE.md`'s
*Verified facts* and *Things that are subtle*, or the manual's
`measured-facts.md` — is still the number that comes out.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import subprocess
import sys

import numpy as np
import pytest

from milq import infusion, mzml, processing
from milq.raw import open_raw

from . import data

#: The digest of the five files as this build reads them, sha256 over every
#: line but the `# milq <version> digest` header — which carries the
#: version and would change on every release without anything having been
#: read differently.
#:
#: `CLAUDE.md` records `ebdeebc2…` for the same five files: that hash was
#: taken over the whole output, header included, at v0.6.x. The digest's
#: *content* is what this pins, and it has not moved.
DIGEST = "a3819c46fd6e329b340bd942e3884c5ff7a3b7b2ce96fd57b2aada768f3032ce"


@pytest.fixture(scope="module")
def files():
    return data.eics()


@pytest.fixture(scope="module")
def digest(files):
    """`--digest` over all five, run the way a release is checked."""
    result = subprocess.run([sys.executable, "-m", "milq.app", "--digest",
                             *files], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


# --------------------------------------------------------------------------- #
# the digest: what a build reads
# --------------------------------------------------------------------------- #
def test_the_digest_is_405_channels_25_spectra_and_125_peaks(digest):
    """
    CLAUDE.md, *Verified facts*: "405 channel chromatograms, 25 spectra, 125
    integrated peaks with areas to nine decimals".

    Five files of 81 channels, five channels each read in full, five peaks
    each. Exact counts: a file that read one channel short would still hash
    to something.
    """
    kinds: dict[str, int] = {}
    for line in digest:
        if not line.startswith("#"):
            kinds[line.split("\t")[0]] = kinds.get(line.split("\t")[0], 0) + 1
    assert kinds == {"file": 5, "sample.tic": 5, "channel": 405,
                     "spectrum": 25, "xic": 25, "peak": 125}


def test_all_405_channel_hashes_differ(digest):
    """
    CLAUDE.md: "All 405 channel hashes differ from one another, so those were
    five different acquisitions rather than one read five times."
    """
    hashes = {tuple(line.split("\t")[6:8])
              for line in digest if line.startswith("channel\t")}
    assert len(hashes) == 405


def test_the_digest_has_not_moved(digest):
    """
    CLAUDE.md, *Verified facts*: the digest is byte-identical from source, from
    the disk image and from the Windows installer. This is the one of those
    three that can be run here — and it is what would catch the reader, the
    conditioning or the peak detector moving a number without anyone saying so.

    A failure here is not necessarily a bug: it means something about what the
    program reads or integrates changed. Find out what, then move the constant
    and say why in the commit.
    """
    body = [line for line in digest if not line.startswith("#")]
    assert hashlib.sha256("\n".join(body).encode()).hexdigest() == DIGEST


# --------------------------------------------------------------------------- #
# mzML: the same numbers, except in one place
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def pair(files, tmp_path_factory):
    """One acquisition, and the mzML written from it, both open."""
    wiff = open_raw(files[0])
    sample = wiff.sample(0)
    path = tmp_path_factory.mktemp("mzml") / "eic.mzML"
    mzml.write_mzml(sample, path)
    back = open_raw(path)
    yield sample, back.sample(0), back
    back.close()
    wiff.close()


def test_the_run_is_23722_spectra_in_cycles_of_44_and_37(pair):
    """
    CLAUDE.md: "a cycle of 44 run 339 times then one of 37 run 238 times —
    44 + 37 = 81 channels, 44·339 + 37·238 = 23,722 spectra."
    """
    _, _, back = pair
    keys = [header.key for header in back.headers]
    assert len(keys) == 23_722
    cycles = mzml.acquisition_cycles(keys)
    assert all(cycle is not None for cycle in cycles)
    lengths = {period: 0 for period, _ in cycles}
    counts = dict(lengths)
    for period, position in cycles:
        lengths[period] = max(lengths[period], position + 1)
        counts[period] += 1
    assert lengths == {0: 44, 1: 37}
    assert counts == {0: 44 * 339, 1: 37 * 238}


def test_scan_properties_alone_give_69_channels_and_the_cycle_gives_81(pair):
    """
    CLAUDE.md: "Scan properties alone gave 69 channels where the acquisition
    has 81." The written file names the experiment, which is why the reader
    gets 81 from it directly; asking the same key function to forget the
    experiment is what any other program's mzML looks like.
    """
    sample, from_mzml, back = pair
    assert len(sample.channels) == len(from_mzml.channels) == 81
    plain = [dataclasses.replace(header, experiment=None).key
             for header in back.headers]
    assert len(set(plain)) == 69
    recovered = mzml.acquisition_cycles(plain)
    assert len({cycle for cycle in recovered if cycle is not None}) == 81


def test_the_tic_is_577_points_and_not_23722(pair):
    """
    CLAUDE.md: "the union of their times is one point per spectrum — 23,722
    where the instrument reports 577." The mzML reader has to sum by cycle to
    reproduce it, and reproduce it exactly.
    """
    sample, from_mzml, _ = pair
    x1, y1 = sample.tic()
    x2, y2 = from_mzml.tic()
    assert len(x1) == len(x2) == 577
    assert np.max(np.abs(x1 - x2)) == 0.0
    assert np.max(np.abs(y1 - y2)) == 0.0


def test_every_channel_chromatogram_and_spectrum_is_identical(pair):
    """
    CLAUDE.md, *Formats agree, except in one place*: spectra and channel
    chromatograms identical, every channel. The spectra are compared with the
    zeros left out on both sides — SCIEX strips them when storing and this
    writes what was stored.
    """
    sample, from_mzml, _ = pair
    worst_time = worst_total = worst_mz = worst_intensity = 0.0
    points = 0
    for original, copy in zip(sample.channels, from_mzml.channels, strict=True):
        ax, ay = original.tic()
        bx, by = copy.tic()
        assert len(ax) == len(bx)
        worst_time = max(worst_time, float(np.max(np.abs(ax - bx))))
        worst_total = max(worst_total, float(np.max(np.abs(ay - by))))
        scan = int(np.argmax(ay))
        m1, i1 = original.spectrum(scan, add_zeros=False)
        m2, i2 = copy.spectrum(scan)
        assert len(m1) == len(m2)
        points += len(m1)
        if len(m1):
            worst_mz = max(worst_mz, float(np.max(np.abs(m1 - m2))))
            worst_intensity = max(worst_intensity, float(np.max(np.abs(i1 - i2))))
    assert (worst_time, worst_total, worst_mz, worst_intensity) == (0, 0, 0, 0)
    assert points == 28_907


def test_every_integrated_peak_is_identical(pair):
    """
    CLAUDE.md: "chromatographic peak areas | identical". 915 peaks over the
    81 channels of this acquisition, area and apex to the bit.
    """
    sample, from_mzml, _ = pair
    compared = 0
    for original, copy in zip(sample.channels, from_mzml.channels, strict=True):
        ax, ay = original.tic()
        bx, by = copy.tic()
        first = processing.detect_peaks(ax, ay)
        second = processing.detect_peaks(bx, by)
        assert len(first) == len(second)
        for a, b in zip(first, second, strict=True):
            compared += 1
            assert a.area == b.area
            assert a.apex_rt == b.apex_rt
    assert compared == 915


def test_the_extracted_ion_chromatograms_differ_and_always_downwards(pair):
    """
    CLAUDE.md: the extraction is the exception — "Median 0.58% of peak height,
    at most 12%, always lower." Measured here on all 81 channels, extracting
    the base peak of each channel's own apex scan at ±0.02 Da.

    This is the figure that says quantify a series in one format. It is
    asserted loosely on purpose in the median (a hundredth of a per cent) and
    tightly where it matters: never higher, never zero everywhere.
    """
    sample, from_mzml, _ = pair
    differences, lower = [], True
    for original, copy in zip(sample.channels, from_mzml.channels, strict=True):
        ax, ay = original.tic()
        scan = int(np.argmax(ay))
        mz, intensity = original.spectrum(scan, add_zeros=False)
        if not len(mz):
            continue
        target = float(mz[int(np.argmax(intensity))])
        _, first = original.xic(target, 0.02)
        _, second = copy.xic(target, 0.02)
        height = float(np.max(first)) if len(first) else 0.0
        if height <= 0:
            continue
        first = np.asarray(first, float)
        second = np.asarray(second, float)
        differences.append(float(np.max(np.abs(first - second))) / height * 100)
        lower = lower and bool(np.all(second <= first + 1e-9))
    assert len(differences) == 81
    assert float(np.median(differences)) == pytest.approx(0.583, abs=0.01)
    assert float(np.max(differences)) == pytest.approx(12.1, abs=0.1)
    assert lower, "SCIEX counts part of a peak just outside the window; this sums inside"


def test_one_component_quantified_from_both_formats(pair):
    """
    CLAUDE.md: "quantifying one component from `.wiff` and from its mzML gives
    the same retention time and the same peak width with the area differing by
    0.54%."

    That 0.54% was one component of the sphingolipid method. The component
    here is built from this acquisition — channel 20's precursor and the base
    peak of its own apex scan — so the figure it gives is its own: **6.46%**,
    on a peak of 236 counts. What carries across is the shape of the answer:
    the retention time and the width are identical, the area from mzML is the
    lower of the two, and the difference sits inside the 12% envelope above.
    """
    from milq.components import Component
    from milq.method import ProcessingMethod
    from milq.quantify import integrate_component
    from milq.samples import SampleEntry

    sample, from_mzml, _ = pair
    channel = sample.channels[20]
    x, y = channel.tic()
    mz, intensity = channel.spectrum(int(np.argmax(y)), add_zeros=False)
    component = Component(name="probe", precursor=channel.info.precursor,
                          fragment=float(mz[int(np.argmax(intensity))]),
                          tolerance=0.02)
    method = ProcessingMethod(components=[component])
    rows = [integrate_component(SampleEntry(path="", sample_index=0, name="x",
                                            sample=held), component, method)
            for held in (sample, from_mzml)]
    first, second = rows
    assert first.found and second.found
    assert first.rt == second.rt
    assert first.width == second.width
    assert second.area < first.area
    difference = abs(first.area - second.area) / first.area * 100
    assert difference == pytest.approx(6.46, abs=0.05)


# --------------------------------------------------------------------------- #
# the stripped zeros
# --------------------------------------------------------------------------- #
def test_restoring_the_zeros_puts_the_labels_back(files):
    """
    CLAUDE.md: "A profile spectrum from mzML has fewer points than the same one
    from `.wiff`… peak labels were centroids taken across the gaps: one read
    184.8466 for a peak at 185.0077."

    That scan is not named anywhere, so this asserts the mechanism on a scan
    that is: the survey's apex, scan 335 of `_1`. SCIEX stores 436 points and
    hands back 1,091 with the zeros put back; `restore_profile_zeros` makes
    1,064 of the same 436 and recovers 323 of the vendor's 326 centroids with
    the ten strongest labels identical. Centroiding the stripped spectrum
    instead finds 77 peaks — three quarters of the spectrum gone, and the
    labels that remain taken across the gaps.
    """
    wiff = open_raw(files[0])
    try:
        channel = wiff.sample(0).channels[0]
        x, y = channel.tic()
        scan = int(np.argmax(y))
        assert scan == 335
        vendor = channel.spectrum(scan, add_zeros=True)
        stripped = channel.spectrum(scan, add_zeros=False)
        restored = processing.restore_profile_zeros(*stripped)
        assert (len(vendor[0]), len(stripped[0]), len(restored[0])) == (1091, 436, 1064)

        counts = [len(processing.centroid_spectrum(*spectrum)[0])
                  for spectrum in (vendor, stripped, restored)]
        assert counts == [326, 77, 323]

        def strongest(spectrum, n=10):
            mz, intensity = processing.centroid_spectrum(*spectrum)
            order = np.argsort(intensity)[::-1][:n]
            return np.round(np.asarray(mz)[order], 4)

        assert list(strongest(vendor)) == list(strongest(restored))
    finally:
        wiff.close()


def test_a_centroid_across_the_gaps_moves_the_label(files):
    """
    The same mechanism where it does damage: on channel 2's apex scan the
    fifth-strongest label reads 310.1827 with the zeros and 310.2477 without
    — 0.065 Da, a label pointing at a compound that is not there.
    """
    wiff = open_raw(files[0])
    try:
        channel = wiff.sample(0).channels[2]
        x, y = channel.tic()
        scan = int(np.argmax(y))
        stripped = channel.spectrum(scan, add_zeros=False)
        vendor = channel.spectrum(scan, add_zeros=True)

        def fifth(spectrum):
            mz, intensity = processing.centroid_spectrum(*spectrum)
            return float(mz[np.argsort(intensity)[::-1][4]])

        assert fifth(vendor) == pytest.approx(310.1827, abs=5e-4)
        assert fifth(stripped) == pytest.approx(310.2477, abs=5e-4)
    finally:
        wiff.close()


# --------------------------------------------------------------------------- #
# these five are the chromatographic half of the infusion measurement
# --------------------------------------------------------------------------- #
def test_none_of_the_five_reads_as_an_infusion(files):
    """
    `milq/infusion.py`'s measured table: the five `260904_EICs_Isabela_*`
    runs measure 0.019 – 0.057 on the sample total and 0.030 – 0.097 on their
    strongest channel, against `FLAT_FRACTION` of 0.75. 39 chromatographic
    runs and 9 infusions, 48 of 48, and these are five of the 39.
    """
    totals, channels = [], []
    for path in files:
        wiff = open_raw(path)
        try:
            verdict = infusion.is_infusion(wiff.sample(0))
            assert not verdict.infusion and not verdict.too_short
            totals.append(verdict.above_half)
            channels.append(verdict.channel_above_half)
        finally:
            wiff.close()
    assert min(totals) == pytest.approx(0.019, abs=0.001)
    assert max(totals) == pytest.approx(0.057, abs=0.001)
    assert min(channels) == pytest.approx(0.030, abs=0.001)
    assert max(channels) == pytest.approx(0.097, abs=0.001)


def test_a_gradient_truncated_before_anything_elutes_reads_flat(files):
    """
    CLAUDE.md: "a gradient cut off before anything elutes is flat too
    (`260904_EICs_Isabela_S001` is empty until 8.9 min and its first 100 scans
    read 1.0000 / 0.9388)" — which is why `MIN_JUDGED_SCANS` refuses to call a
    short flat run an infusion.

    The sample total reproduces exactly. The companion figure does not:
    0.9388 was measured on a channel this test cannot identify, since
    `strongest_channel` on the whole run picks a channel of the run's *second*
    period, whose own first hundred scans are minutes 12.6 onwards and read
    0.5859. Both numbers say the same thing — a truncated gradient is flat —
    so the current one is asserted and the old one recorded here.
    """
    path = [p for p in files if "S001" in p][0]
    wiff = open_raw(path)
    try:
        sample = wiff.sample(0)
        x, y = sample.tic()
        assert len(x) == 577
        assert infusion.flat_fraction(x[:100], y[:100]) == pytest.approx(1.0)
        channel = infusion.strongest_channel(sample)
        cx, cy = channel.tic()
        assert infusion.flat_fraction(cx[:100], cy[:100]) == pytest.approx(0.5859,
                                                                          abs=1e-3)
        # and the whole run is nothing of the sort
        assert infusion.flat_fraction(x, y) < infusion.FLAT_FRACTION
    finally:
        wiff.close()


def test_the_files_are_where_the_repository_says_they_are(files):
    """A guard on the fixture itself: five files, and the names in CLAUDE.md."""
    assert len(files) == 5
    assert all(os.path.basename(path).startswith("260904_EICs_Isabela_")
               for path in files)
