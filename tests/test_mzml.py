"""
Reading and writing mzML.

The writer exists to test the reader, so most of what is here is a round
trip. That is not enough on its own — a reader checked only against its own
writer shares every assumption with it — so the cases that come from other
people's files are built by hand: seconds instead of minutes, 32-bit arrays,
uncompressed binaries, a centroided run, numpress.
"""

import base64
import zlib

import numpy as np
import pytest

from milq import mzml, raw
from milq.wiff import ChannelInfo


# --------------------------------------------------------------------------- #
# a stand-in for a sample, so a round trip needs no instrument
# --------------------------------------------------------------------------- #
class FakeChannel:
    def __init__(self, index, info, times, spectra, totals=None):
        self.index, self.info = index, info
        self._times = np.asarray(times, dtype=float)
        self._spectra = spectra
        self._totals = (np.asarray(totals, dtype=float) if totals is not None
                        else np.array([float(np.sum(s[1])) for s in spectra]))

    def tic(self):
        return self._times, self._totals

    @property
    def rt(self):
        return self._times

    def spectrum(self, scan, add_zeros=True):
        return self._spectra[int(scan)]


class FakeSample:
    name = "run"
    instrument = "TripleTOF 6600"
    acquisition_time = "2026-09-06T10:00:00Z"

    def __init__(self, channels):
        self.channels = channels


def _ms1(times=(0.1, 0.2, 0.3), totals=None):
    spectra = [
        (np.array([100.1234, 264.2686, 500.5001]), np.array([10.0, 5000.0, 3.0])),
        (np.array([100.1235, 264.2687]), np.array([12.0, 6000.0])),
        (np.array([264.2686]), np.array([7000.0])),
    ]
    return FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                      100.0, 2000.0, 3, None),
                       times, spectra, totals)


def _ms2(times=(0.1, 0.2, 0.3)):
    spectra = [
        (np.array([264.2686, 282.2791]), np.array([900.0, 300.0])),
        (np.array([264.2686]), np.array([950.0])),
        (np.array([264.2686, 282.2791]), np.array([880.0, 290.0])),
    ]
    return FakeChannel(1, ChannelInfo(1, "TOF PI", "Product Ion", "Positive",
                                      538.5188, 50.0, 550.0, 3, -35.0),
                       times, spectra)


@pytest.fixture
def written(tmp_path):
    path = tmp_path / "round-trip.mzML"
    mzml.write_mzml(FakeSample([_ms1(), _ms2()]), path)
    return path


# --------------------------------------------------------------------------- #
def test_the_channels_come_back(written):
    sample = mzml.MzmlFile(written).sample(0)
    assert len(sample.channels) == 2
    ms1, ms2 = sample.channels
    assert ms1.info.is_ms1
    assert ms2.info.precursor == pytest.approx(538.5188)
    assert ms2.info.collision_energy == pytest.approx(-35.0)
    assert ms2.info.start_mass == pytest.approx(50.0)
    assert ms2.info.end_mass == pytest.approx(550.0)


def test_an_mzml_has_nothing_beside_it_to_go_missing(written):
    """A .wiff without its .wiff.scan has a problem; one file cannot."""
    assert mzml.MzmlFile(written).sample(0).problem is None


def test_the_spectra_come_back_unchanged(written):
    sample = mzml.MzmlFile(written).sample(0)
    for index, source in enumerate((_ms1(), _ms2())):
        for scan in range(3):
            want_mz, want_intensity = source.spectrum(scan)
            got_mz, got_intensity = sample.channels[index].spectrum(scan)
            assert np.array_equal(got_mz, want_mz)
            assert np.array_equal(got_intensity, want_intensity)


def test_the_instruments_own_totals_are_kept_not_recomputed(tmp_path):
    """
    The total ion current is the detector's number, not a sum of the points.

    A profile spectrum is stored with its zeros stripped out, so adding up
    what is left is not what the instrument reported — on a real acquisition
    the difference moved every integrated area by about two per cent.
    """
    reported = [12345.5, 999.25, 0.0]
    path = tmp_path / "totals.mzML"
    mzml.write_mzml(FakeSample([_ms1(totals=reported)]), path)
    _, values = mzml.MzmlFile(path).sample(0).channels[0].tic()
    assert np.array_equal(values, np.array(reported))


def test_a_scan_with_nothing_in_it_is_not_mistaken_for_a_missing_total(tmp_path):
    """
    A total of zero is a measurement. Reading it as absence made the whole
    channel fall back to summing the stored points, which is a different
    number — and it happened on three of five real acquisitions.
    """
    path = tmp_path / "zero.mzML"
    mzml.write_mzml(FakeSample([_ms1(totals=[0.0, 0.0, 4242.0])]), path)
    file = mzml.MzmlFile(path)
    assert all(h.total_ion_current is not None for h in file.headers)
    _, values = file.sample(0).channels[0].tic()
    assert np.array_equal(values, np.array([0.0, 0.0, 4242.0]))


def test_retention_times_survive_to_the_last_digit(tmp_path):
    times = [0.123456789012, 1.9999999999, 21.431166666667]
    path = tmp_path / "times.mzML"
    mzml.write_mzml(FakeSample([_ms1(times=times)]), path)
    got, _ = mzml.MzmlFile(path).sample(0).channels[0].tic()
    assert np.array_equal(got, np.array(times))


def test_the_whole_run_can_be_summed(written):
    """
    Two experiments of three cycles each: six spectra, six points.

    Three is under `mzml.MIN_REPEATS`, so there is no cycle here to believe —
    "two consecutive stretches that happen to match are a coincidence". The
    channels are grouped by their properties and the run's chromatogram is
    one point per spectrum, which is what an acquisition with no repeating
    order gets. `test_the_run_total_is_summed_by_cycle_not_by_time` is the
    same question asked of a method that does repeat.
    """
    sample = mzml.MzmlFile(written).sample(0)
    times, total = sample.tic()
    assert times.size == 6
    assert [c.period for c in sample.channels] == [None, None]
    assert total.sum() > 0


def test_an_extracted_chromatogram_sums_the_window(written):
    sample = mzml.MzmlFile(written).sample(0)
    _, values = sample.channels[1].xic(264.2686, 0.02)
    assert np.array_equal(values, np.array([900.0, 950.0, 880.0]))


def test_the_file_says_where_it_came_from(written):
    sample = mzml.MzmlFile(written).sample(0)
    meta = sample.metadata()
    assert meta["Format"] == "mzML"
    assert meta["Instrument"] == "TripleTOF 6600"
    assert sample.acquisition_time == "2026-09-06T10:00:00Z"


# --------------------------------------------------------------------------- #
# files written by somebody else
# --------------------------------------------------------------------------- #
def _hand_written(tmp_path, *, spectrum_body: str, name="other.mzML") -> str:
    path = tmp_path / name
    path.write_text(
        '<?xml version="1.0"?>\n'
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0" id="x">'
        '<run id="x"><spectrumList count="1">'
        + spectrum_body +
        "</spectrumList></run></mzML>"
    )
    return str(path)


def _binary(values, *, bits=64, compress=False):
    fmt = "<f8" if bits == 64 else "<f4"
    raw_bytes = np.asarray(values, dtype=fmt).tobytes()
    if compress:
        raw_bytes = zlib.compress(raw_bytes)
    return base64.b64encode(raw_bytes).decode()


def _array_xml(values, accession, name, *, bits=64, compress=False):
    encoding = ('<cvParam accession="MS:1000523" name="64-bit float" value=""/>'
                if bits == 64 else
                '<cvParam accession="MS:1000521" name="32-bit float" value=""/>')
    compression = ('<cvParam accession="MS:1000574" name="zlib compression" value=""/>'
                   if compress else
                   '<cvParam accession="MS:1000576" name="no compression" value=""/>')
    return (
        "<binaryDataArray>" + encoding + compression
        + f'<cvParam accession="{accession}" name="{name}" value=""/>'
        + f"<binary>{_binary(values, bits=bits, compress=compress)}</binary>"
        + "</binaryDataArray>"
    )


def test_seconds_are_converted_to_minutes(tmp_path):
    """
    ProteoWizard writes minutes from one vendor and seconds from another, and
    the unit is in the file. Reading the number without it turns a twenty
    minute run into a twenty hour one.
    """
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="1">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<scanList count="1"><scan>'
        '<cvParam accession="MS:1000016" name="scan start time" value="90.0"'
        ' unitAccession="UO:0000010" unitName="second"/>'
        "</scan></scanList><binaryDataArrayList count=\"2\">"
        + _array_xml([100.0], "MS:1000514", "m/z array")
        + _array_xml([5.0], "MS:1000515", "intensity array")
        + "</binaryDataArrayList></spectrum>"
    )
    file = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body))
    assert file.headers[0].rt == pytest.approx(1.5)


@pytest.mark.parametrize("bits,compress", [(64, False), (32, False),
                                           (64, True), (32, True)])
def test_every_combination_of_width_and_compression(tmp_path, bits, compress):
    masses = [100.5, 200.25, 300.125]
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="3">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="2">'
        + _array_xml(masses, "MS:1000514", "m/z array", bits=bits, compress=compress)
        + _array_xml([1.0, 2.0, 3.0], "MS:1000515", "intensity array",
                     bits=bits, compress=compress)
        + "</binaryDataArrayList></spectrum>"
    )
    name = f"w{bits}{'z' if compress else ''}.mzML"
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name=name)).sample(0)
    mz, intensity = sample.channels[0].spectrum(0)
    assert mz == pytest.approx(masses, rel=1e-6)
    assert intensity == pytest.approx([1.0, 2.0, 3.0], rel=1e-6)


def test_numpress_is_refused_by_name(tmp_path):
    """
    It is lossy at its usual settings. Reading it wrongly would be worse than
    not reading it, so the refusal says what to do instead.
    """
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="1">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="1"><binaryDataArray>'
        '<cvParam accession="MS:1002312" name="MS-Numpress linear" value=""/>'
        '<cvParam accession="MS:1000514" name="m/z array" value=""/>'
        "<binary>AAAA</binary></binaryDataArray>"
        "</binaryDataArrayList></spectrum>"
    )
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="np.mzML")).sample(0)
    with pytest.raises(mzml.MzmlError, match="numpress"):
        sample.channels[0].spectrum(0)


def test_a_truncated_array_is_an_error_not_a_short_spectrum(tmp_path):
    """The file says how many points there are; silently returning fewer
    would put a spectrum with holes into an identification."""
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="5">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="2">'
        + _array_xml([100.0, 200.0], "MS:1000514", "m/z array")
        + _array_xml([1.0, 2.0], "MS:1000515", "intensity array")
        + "</binaryDataArrayList></spectrum>"
    )
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="short.mzML")).sample(0)
    with pytest.raises(mzml.MzmlError, match="declares 5 points"):
        sample.channels[0].spectrum(0)


def test_channels_are_inferred_when_nothing_records_them(tmp_path):
    """
    Another vendor's file has no idea of an experiment. Scans that share an
    MS level, a precursor and a mass range came from the same entry in the
    method, and that is all there is to go on.
    """
    def spectrum(index, level, precursor=None):
        precursor_xml = ""
        if precursor is not None:
            precursor_xml = (
                "<precursorList count=\"1\"><precursor><selectedIonList "
                "count=\"1\"><selectedIon>"
                f'<cvParam accession="MS:1000744" name="selected ion m/z" '
                f'value="{precursor}"/>'
                "</selectedIon></selectedIonList></precursor></precursorList>"
            )
        return (
            f'<spectrum index="{index}" id="scan={index}" defaultArrayLength="1">'
            f'<cvParam accession="MS:1000511" name="ms level" value="{level}"/>'
            '<scanList count="1"><scan>'
            f'<cvParam accession="MS:1000016" name="scan start time" '
            f'value="{index * 0.1}" unitName="minute"/>'
            "</scan></scanList>" + precursor_xml
            + '<binaryDataArrayList count="2">'
            + _array_xml([100.0], "MS:1000514", "m/z array")
            + _array_xml([1.0], "MS:1000515", "intensity array")
            + "</binaryDataArrayList></spectrum>"
        )

    body = "".join([spectrum(0, 1), spectrum(1, 2, 500.1), spectrum(2, 1),
                    spectrum(3, 2, 500.1), spectrum(4, 2, 600.2)])
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="infer.mzML")).sample(0)
    assert len(sample.channels) == 3
    assert [len(c._headers) for c in sample.channels] == [2, 2, 1]
    assert sample.channels[0].info.is_ms1
    assert sample.channels[1].info.precursor == pytest.approx(500.1)
    assert sample.channels[2].info.precursor == pytest.approx(600.2)


def test_a_file_that_is_not_mzml_says_so(tmp_path):
    path = tmp_path / "not.mzML"
    path.write_text("this is not a mass spectrum")
    with pytest.raises(mzml.MzmlError, match="does not look like mzML"):
        mzml.MzmlFile(path)


# --------------------------------------------------------------------------- #
# choosing a reader
# --------------------------------------------------------------------------- #
def test_the_dispatcher_knows_both_formats():
    assert raw.format_of("a.wiff") == "SCIEX"
    assert raw.format_of("a.mzML") == "mzML"
    assert raw.format_of("a.MZML") == "mzML"
    assert raw.is_supported("b.mzml")
    assert not raw.is_supported("b.raw")


def test_an_unknown_extension_says_what_is_supported():
    with pytest.raises(raw.UnsupportedFormat, match="wiff"):
        raw.format_of("acquisition.raw")


def test_wiff2_is_refused_and_is_not_mistaken_for_a_wiff():
    """
    `.wiff2` is not a reader that is missing; it is a container with no scan
    data in it. Measured: Clearcore2 raises `Invalid OLE structured storage
    file` on every one, its own CheckDataFileIntegrity calls them
    `NotWiffFile`, and the format's declared schema has no column for a
    spectrum. So the dispatcher must refuse it outright rather than fall
    through to the SCIEX reader on a prefix match — `.wiff2` starts with
    `.wiff`, and an extension test written with `startswith` would have
    handed it to a reader that cannot open it.
    """
    assert not raw.is_supported("acquisition.wiff2")
    assert ".wiff2" not in raw.FORMATS
    with pytest.raises(raw.UnsupportedFormat, match=r"\.wiff2"):
        raw.format_of("acquisition.wiff2")
    assert raw.format_of("acquisition.wiff") == "SCIEX"


def test_opening_mzml_needs_no_dotnet(written):
    """
    The SCIEX reader starts a .NET runtime on import. Someone working with
    mzML alone should not need one, so the dispatcher must not reach for it.
    """
    file = raw.open_raw(written)
    assert isinstance(file, mzml.MzmlFile)
    file.close()


def test_the_run_total_is_summed_by_cycle_not_by_time(tmp_path):
    """
    The experiments of one cycle are measured one after another, so no two
    share a time. Summing on the union of all the times gives one point per
    spectrum — a comb, not a chromatogram — and it is not what the instrument
    reports either. The experiments of one period are added cycle by cycle.

    The fixture is the shape a scheduled method actually has: two periods,
    one after the other in time, each repeating enough for
    `acquisition_cycles` to believe it. It used to be two periods overlapping
    in time with three and two cycles, told apart by counting each channel's
    scans — which no acquisition looks like, and which was how a real Thermo
    direct-infusion file with 164 spectra and 82 one- and two-scan channels
    came back with an eight-point chromatogram. The period is now whatever
    `acquisition_cycles` found, and a channel it could not place keeps its
    own times.
    """
    survey = np.array([0.10, 0.20, 0.30, 0.40])
    product = survey + 0.01
    second = np.array([0.50, 0.60, 0.70, 0.80])
    one = (np.array([100.0]), np.array([1.0]))
    channels = [
        FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                   100.0, 2000.0, 4, None),
                    survey, [one] * 4, totals=[10.0, 20.0, 30.0, 40.0]),
        FakeChannel(1, ChannelInfo(1, "TOF PI", "Product Ion", "Positive",
                                   500.0, 50.0, 550.0, 4, -30.0),
                    product, [one] * 4, totals=[1.0, 2.0, 3.0, 4.0]),
        FakeChannel(2, ChannelInfo(2, "TOF PI", "Product Ion", "Positive",
                                   600.0, 50.0, 650.0, 4, -30.0),
                    second, [one] * 4, totals=[100.0, 200.0, 300.0, 400.0]),
    ]
    path = tmp_path / "periods.mzML"
    mzml.write_mzml(FakeSample(channels), path)
    sample = mzml.MzmlFile(path).sample(0)
    assert [c.period for c in sample.channels] == [0, 0, 1]
    times, total = sample.tic()

    # four cycles of the first period and four of the second, in time order
    assert times.size == 8
    assert np.array_equal(times, np.concatenate([survey, second]))
    # the first period's two channels are added cycle by cycle at the times
    # of the first of them; the second period keeps its own
    assert np.array_equal(total, np.array([11.0, 22.0, 33.0, 44.0,
                                           100.0, 200.0, 300.0, 400.0]))


def test_a_run_with_no_cycle_keeps_one_point_per_spectrum(tmp_path):
    """
    Grouping the channels by how many scans each has is right for a scheduled
    method and fiction for anything else.

    Measured on a real ProteoWizard-converted Thermo direct infusion — an LTQ
    Orbitrap Elite stepping its isolation window across the precursor in 0.02
    Da increments, 164 spectra, 82 inferred channels of one, two and five
    scans — the three distinct scan counts became three "periods" and the
    run's total ion chromatogram came back as **eight points for 164
    spectra**, every channel piled onto whichever channel of that length came
    first. The total was right and the shape was fiction, and
    `infusion.is_infusion` reads exactly that shape.

    Here: three experiments with nothing repeating, one point each, and the
    total still adds up to every scan's own.
    """
    one = (np.array([100.0]), np.array([1.0]))
    channels = [
        FakeChannel(0, ChannelInfo(0, "MS2", "Product Ion", "Positive",
                                   180.30, 50.0, 182.0, 1, 35.0),
                    [0.10], [one], totals=[10.0]),
        FakeChannel(1, ChannelInfo(1, "MS2", "Product Ion", "Positive",
                                   180.32, 50.0, 182.0, 2, 35.0),
                    [0.20, 0.50], [one] * 2, totals=[20.0, 50.0]),
        FakeChannel(2, ChannelInfo(2, "MS2", "Product Ion", "Positive",
                                   180.34, 50.0, 182.0, 1, 35.0),
                    [0.30], [one], totals=[30.0]),
    ]
    path = tmp_path / "no-cycle.mzML"
    mzml.write_mzml(FakeSample(channels), path)
    sample = mzml.MzmlFile(path).sample(0)
    assert all(c.period is None for c in sample.channels)
    times, total = sample.tic()
    assert np.array_equal(times, np.array([0.10, 0.20, 0.30, 0.50]))
    assert np.array_equal(total, np.array([10.0, 20.0, 30.0, 50.0]))
    assert total.sum() == 110.0


# --------------------------------------------------------------------------- #
# the acquisition cycle
# --------------------------------------------------------------------------- #
def test_a_repeating_method_is_split_by_position_in_the_cycle():
    """
    Two entries of a method can agree on every property mzML records. On a
    real 81-channel acquisition, grouping by MS level, precursor, collision
    energy and mass range alone gave 69 channels: a panel ran some transitions
    twice at different points in the cycle. The order of acquisition is what
    separates them, and mzML does keep that.
    """
    cycle = ["ms1", "a", "b", "a"]          # "a" twice, at positions 1 and 3
    keys = cycle * 8
    positions = mzml.acquisition_cycles(keys)
    assert all(p is not None for p in positions)
    assert len(set(positions)) == 4, "four entries, not three"
    # the two "a" entries are told apart
    a_positions = {p for p, k in zip(positions, keys) if k == "a"}
    assert len(a_positions) == 2


def test_two_periods_are_found_one_after_the_other():
    """
    A method runs in periods and each has its own cycle. The acquisition this
    was checked against is a cycle of 44 run 339 times followed by a cycle of
    37 run 238 times — and 44 + 37 is exactly the 81 channels the vendor's own
    file declares.
    """
    keys = ["p", "q"] * 10 + ["x", "y", "z"] * 10
    positions = mzml.acquisition_cycles(keys)
    periods = {p[0] for p in positions if p is not None}
    assert periods == {0, 1}
    assert len({p for p in positions if p is not None}) == 5   # 2 + 3


def test_an_acquisition_stopped_mid_cycle_keeps_its_last_scans():
    keys = ["a", "b", "c"] * 6 + ["a", "b"]
    positions = mzml.acquisition_cycles(keys)
    assert all(p is not None for p in positions)
    assert positions[-2:] == [(0, 0), (0, 1)]


def test_data_dependent_acquisition_has_no_cycle_and_says_so():
    """
    DDA picks its precursors from the last survey scan, so nothing repeats.
    Reporting a cycle there would invent channels; the properties of the scans
    are all there is, and the caller falls back to them.
    """
    keys = ["ms1", "p1", "p2", "ms1", "p3", "p4", "ms1", "p5", "p6",
            "ms1", "p7", "p8"]
    assert all(p is None for p in mzml.acquisition_cycles(keys))


def test_a_short_run_is_not_mistaken_for_a_cycle():
    """Two stretches that happen to match are a coincidence, not a method."""
    assert all(p is None for p in mzml.acquisition_cycles(["a", "b", "a", "b"]))


# --------------------------------------------------------------------------- #
# an infusion from another vendor
# --------------------------------------------------------------------------- #
#: how many scans a flat run needs before flatness is evidence — the figure
#: `infusion.MIN_JUDGED_SCANS` gates on, plus a few, so the fixture is a run
#: the verdict is allowed to judge rather than one it refuses for length
INFUSION_SCANS = 130


#: the four fragments the fixture's compound gives, and the precursor last
INFUSION_PEAKS = ((181.0974, 300.0), (289.2162, 1200.0),
                  (377.3018, 9600.0), (430.3489, 9400.0))


def _profile(centre: float, height: float, step: float = 0.004):
    """One peak as an instrument stores it: nine points, zeros stripped."""
    offsets = np.arange(-4, 5) * step
    return centre + offsets, height * np.exp(-0.5 * (offsets / (1.5 * step)) ** 2)


def _infusion_sample(polarity="Negative", wandering=False):
    """
    A direct infusion of one compound: one product-ion experiment, every scan
    the same four fragments plus a little more of them, no chromatography,
    and nothing at all between the peaks — a profile spectrum with its zeros
    stripped out, which is how one arrives.

    `wandering=True` adds a point of noise that moves half a dalton per scan
    across the empty stretch between two fragments. It is what makes
    averaging a question rather than an elementwise mean: the union axis then
    has 130 masses in a stretch where any one scan measured exactly one, and
    a rule that interpolates each scan onto the union fills the whole stretch
    in.
    """
    spectra, totals, times = [], [], []
    for scan in range(INFUSION_SCANS):
        masses, heights = [], []
        for centre, height in INFUSION_PEAKS:
            peak_mz, peak_y = _profile(centre, height + scan)
            masses.append(peak_mz)
            heights.append(peak_y)
        if wandering:
            masses.append(np.array([210.0 + scan * 0.5]))
            heights.append(np.array([50.0]))
        mz = np.concatenate(masses)
        intensity = np.concatenate(heights)
        order = np.argsort(mz)
        spectra.append((mz[order], intensity[order]))
        totals.append(float(intensity.sum()))
        times.append(0.004 + scan * 0.0042)
    info = ChannelInfo(0, "TOF PI", "Product Ion", polarity, 430.3423,
                       50.0, 500.0, INFUSION_SCANS, 22.0,
                       activation="beam-type collision-induced dissociation",
                       charge=1)
    return FakeSample([FakeChannel(0, info, times, spectra, totals)])


def _thermo_shaped(source_path, path):
    """
    The same acquisition re-written the way ProteoWizard writes a Thermo
    `.raw`, with everything this program put in it taken back out.

    Nothing here is SCIEX and nothing here is ours: a `.raw` source file in
    the Thermo nativeID format, the instrument named in a
    `referenceableParamGroup` the configuration only points at,
    `controllerType=0 controllerNumber=1 scan=N` ids, a filter string, scan
    start times in **seconds**, an isolation window, a charge state, and
    `beam-type collision-induced dissociation`. No `milq experiment`
    parameter, so the channels have to be inferred from the scans; a plain
    `<mzML>` with no index and no offsets to read them out of.
    """
    channel = mzml.MzmlFile(source_path).sample(0).channels[0]
    info = channel.info
    times, totals = channel.tic()
    negative = info.polarity.lower().startswith("neg")
    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0" id="infusion">',
        '<fileDescription><fileContent>'
        '<cvParam accession="MS:1000580" name="MSn spectrum" value=""/>'
        '</fileContent><sourceFileList count="1">'
        '<sourceFile id="RAW1" name="infusion.raw" location="file:///C:/data">'
        '<cvParam accession="MS:1000768" name="Thermo nativeID format" value=""/>'
        '<cvParam accession="MS:1000563" name="Thermo RAW format" value=""/>'
        '</sourceFile></sourceFileList></fileDescription>',
        '<referenceableParamGroupList count="1">'
        '<referenceableParamGroup id="CommonInstrumentParams">'
        '<cvParam accession="MS:1001911" name="Q Exactive" value=""/>'
        '<cvParam accession="MS:1000529" name="instrument serial number" value="SN1"/>'
        '</referenceableParamGroup></referenceableParamGroupList>',
        '<softwareList count="2">'
        '<software id="Xcalibur" version="4.3"/>'
        '<software id="pwiz" version="3.0.24000"/></softwareList>',
        '<instrumentConfigurationList count="1">'
        '<instrumentConfiguration id="IC1">'
        '<referenceableParamGroupRef ref="CommonInstrumentParams"/>'
        '<componentList count="1"><analyzer order="1">'
        '<cvParam accession="MS:1000484" name="orbitrap" value=""/>'
        '</analyzer></componentList>'
        '</instrumentConfiguration></instrumentConfigurationList>',
        f'<run id="infusion" defaultInstrumentConfigurationRef="IC1">'
        f'<spectrumList count="{times.size}">',
    ]
    polarity_xml = (
        '<cvParam accession="MS:1000129" name="negative scan" value=""/>'
        if negative else
        '<cvParam accession="MS:1000130" name="positive scan" value=""/>')
    for scan in range(times.size):
        mz, intensity = channel.spectrum(scan)
        out.append(
            f'<spectrum index="{scan}" '
            f'id="controllerType=0 controllerNumber=1 scan={scan + 1}" '
            f'defaultArrayLength="{mz.size}">'
            '<cvParam accession="MS:1000511" name="ms level" value="2"/>'
            '<cvParam accession="MS:1000580" name="MSn spectrum" value=""/>'
            '<cvParam accession="MS:1000128" name="profile spectrum" value=""/>'
            + polarity_xml
            + f'<cvParam accession="MS:1000285" name="total ion current" '
              f'value="{float(totals[scan])!r}"/>'
            '<scanList count="1"><scan>'
            # seconds, which is what ProteoWizard writes from a Thermo file
            f'<cvParam accession="MS:1000016" name="scan start time" '
            f'value="{float(times[scan]) * 60.0!r}" unitAccession="UO:0000010" '
            f'unitName="second"/>'
            '<cvParam accession="MS:1000512" name="filter string" '
            'value="FTMS - p ESI Full ms2 430.3423@hcd22.00 [50.00-500.00]"/>'
            '<scanWindowList count="1"><scanWindow>'
            f'<cvParam accession="MS:1000501" name="scan window lower limit" '
            f'value="{info.start_mass:.6f}"/>'
            f'<cvParam accession="MS:1000500" name="scan window upper limit" '
            f'value="{info.end_mass:.6f}"/>'
            '</scanWindow></scanWindowList></scan></scanList>'
            '<precursorList count="1"><precursor><isolationWindow>'
            f'<cvParam accession="MS:1000827" name="isolation window target m/z" '
            f'value="{info.precursor:.6f}"/>'
            '</isolationWindow><selectedIonList count="1"><selectedIon>'
            f'<cvParam accession="MS:1000744" name="selected ion m/z" '
            f'value="{info.precursor:.6f}"/>'
            '<cvParam accession="MS:1000041" name="charge state" value="1"/>'
            '</selectedIon></selectedIonList><activation>'
            '<cvParam accession="MS:1000422" '
            'name="beam-type collision-induced dissociation" value=""/>'
            '<cvParam accession="MS:1000045" name="collision energy" value="22"'
            ' unitAccession="UO:0000266" unitName="electronvolt"/>'
            '</activation></precursor></precursorList>'
            '<binaryDataArrayList count="2">'
            + _array_xml(mz, "MS:1000514", "m/z array", compress=True)
            + _array_xml(intensity, "MS:1000515", "intensity array",
                         bits=32, compress=True)
            + "</binaryDataArrayList></spectrum>"
        )
    out.append("</spectrumList></run></mzML>")
    path.write_text("".join(out))
    return str(path)


def _whole_run(channel):
    times = channel.rt
    return float(times[0]), float(times[-1])


@pytest.fixture
def thermo_infusion(tmp_path):
    """A direct infusion as another vendor's converter would hand it over."""
    ours = tmp_path / "ours.mzML"
    mzml.write_mzml(_infusion_sample(), ours)
    return _thermo_shaped(ours, tmp_path / "infusion-thermo.mzML")


def test_a_thermo_infusion_is_one_product_ion_channel(thermo_infusion):
    """
    Nothing in the file says which experiment a scan belongs to, so the
    channels are inferred — and one infused compound is one channel, with
    everything the method set on it read off the scans.
    """
    file = mzml.MzmlFile(thermo_infusion)
    assert file.source_file == "infusion.raw"
    # the model is in a parameter group the configuration only points at,
    # which is how ProteoWizard writes every Thermo file; read only inside
    # the configuration, this said "unknown"
    assert file.instrument == "Q Exactive"

    sample = file.sample(0)
    assert len(sample.channels) == 1
    info = sample.channels[0].info
    assert not info.is_ms1
    assert info.experiment_type == "Product Ion"
    assert info.precursor == pytest.approx(430.3423)
    assert info.collision_energy == pytest.approx(22.0)
    assert info.polarity == "Negative"
    assert info.charge == 1
    assert info.activation == "beam-type collision-induced dissociation"

    shown = sample.channels[0].parameters()
    assert shown["Activation"] == "beam-type collision-induced dissociation"
    assert shown["Charge"] == "1"
    assert shown["Spectrum type"] == "profile"


def test_an_infusions_times_are_read_as_minutes(thermo_infusion):
    """The file says seconds; a run of half a minute is not one of 33."""
    times, _total = mzml.MzmlFile(thermo_infusion).sample(0).tic()
    assert times.size == INFUSION_SCANS
    assert times[0] == pytest.approx(0.004, abs=1e-9)
    assert times[-1] == pytest.approx(0.004 + (INFUSION_SCANS - 1) * 0.0042)


def test_an_activation_separates_two_entries_a_precursor_does_not(tmp_path):
    """
    Twenty-two electronvolts of beam-type CID and twenty-two of electron
    transfer are different experiments on the same precursor, and a file that
    runs both has two entries. Nothing else in the scan tells them apart.
    """
    def spectrum(index, activation):
        return (
            f'<spectrum index="{index}" id="scan={index}" defaultArrayLength="1">'
            '<cvParam accession="MS:1000511" name="ms level" value="2"/>'
            '<scanList count="1"><scan>'
            f'<cvParam accession="MS:1000016" name="scan start time" '
            f'value="{index * 0.1}" unitName="minute"/>'
            '</scan></scanList>'
            '<precursorList count="1"><precursor>'
            '<selectedIonList count="1"><selectedIon>'
            '<cvParam accession="MS:1000744" name="selected ion m/z" value="430.34"/>'
            '</selectedIon></selectedIonList><activation>'
            f'<cvParam accession="{activation[0]}" name="{activation[1]}" value=""/>'
            '<cvParam accession="MS:1000045" name="collision energy" value="22"/>'
            '</activation></precursor></precursorList>'
            '<binaryDataArrayList count="2">'
            + _array_xml([100.0], "MS:1000514", "m/z array")
            + _array_xml([1.0], "MS:1000515", "intensity array")
            + "</binaryDataArrayList></spectrum>"
        )

    hcd = ("MS:1000422", "beam-type collision-induced dissociation")
    etd = ("MS:1000598", "electron transfer dissociation")
    body = "".join([spectrum(0, hcd), spectrum(1, etd),
                    spectrum(2, hcd), spectrum(3, etd)])
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="two-activations.mzML")).sample(0)
    assert len(sample.channels) == 2
    assert [c.info.activation for c in sample.channels] == [hcd[1], etd[1]]
    # the energy names a number, not a method: reading the first cvParam of
    # the activation element would have called both of these "collision energy"
    assert all(c.info.collision_energy == pytest.approx(22.0)
               for c in sample.channels)


def test_a_thermo_infusion_is_called_an_infusion(thermo_infusion):
    """
    The verdict reads chromatograms and nothing else, so it says the same
    thing about another vendor's file as about a `.wiff`.
    """
    from milq import infusion

    sample = mzml.MzmlFile(thermo_infusion).sample(0)
    verdict = infusion.is_infusion(sample)
    assert verdict.infusion
    assert verdict.above_half == pytest.approx(1.0)
    assert verdict.channel_above_half == pytest.approx(1.0)
    assert verdict.n_scans == INFUSION_SCANS
    assert infusion.strongest_channel(sample) is sample.channels[0]
    assert infusion.run_range(sample.channels[0]) == pytest.approx(
        _whole_run(sample.channels[0]))


def test_the_average_of_an_infusion_is_the_mean_of_its_scans(thermo_infusion):
    """
    Averaging adds each scan up where it was measured. On one shared mass
    axis that is the elementwise mean, exactly.
    """
    channel = mzml.MzmlFile(thermo_infusion).sample(0).channels[0]
    mz, intensity = channel.spectrum_rt_range(*_whole_run(channel))
    scans = [channel.spectrum(scan) for scan in range(INFUSION_SCANS)]
    assert np.array_equal(mz, scans[0][0])
    assert intensity == pytest.approx(
        np.mean([y for _x, y in scans], axis=0), rel=1e-6)


def test_averaging_adds_the_scans_up_where_they_were_measured(tmp_path):
    """
    A time-of-flight does not put two scans on the same mass axis, and the
    average is then over the union of them. Interpolating each scan onto that
    union — the obvious thing to write, and what this used to do — draws a
    straight line across every stretch a profile spectrum has no points in,
    which is signal where the instrument reported none. Measured against
    SCIEX's own averaging of 146 real scans over the same 221,847 masses:
    220,222 of them came back higher, the spectrum totalled **3.31 times**
    the vendor's, and centroiding it gave 670 sticks against the vendor's
    424. Adding each scan up where it was measured reproduces the vendor's
    average exactly — largest difference at any point 0.0.

    Here: every count in, every count out, and nothing between the peaks.
    """
    ours = tmp_path / "wandering.mzML"
    mzml.write_mzml(_infusion_sample(wandering=True), ours)
    path = _thermo_shaped(ours, tmp_path / "wandering-thermo.mzML")
    channel = mzml.MzmlFile(path).sample(0).channels[0]
    mz, intensity = channel.spectrum_rt_range(*_whole_run(channel))

    scans = [channel.spectrum(scan) for scan in range(INFUSION_SCANS)]
    # the union is far wider than any one scan, because of the wandering point
    assert mz.size == scans[0][0].size + INFUSION_SCANS - 1
    # every count is still there, exactly once
    assert intensity.sum() == pytest.approx(
        float(np.mean([y.sum() for _x, y in scans])), rel=1e-9)

    # the stretch between two fragments, where one scan in a hundred and
    # thirty measured 50 counts and the rest measured nothing at all
    empty = (mz > 205.0) & (mz < 280.0)
    assert int(empty.sum()) == INFUSION_SCANS
    # each of those masses carries one scan's fifty counts and no more —
    # interpolating instead would have given every scan a value at every one
    assert intensity[empty] == pytest.approx(50.0 / INFUSION_SCANS)
    # and the fragments themselves are untouched
    assert intensity.max() == pytest.approx(
        float(np.mean([9600.0 + scan for scan in range(INFUSION_SCANS)])))


@pytest.fixture(scope="module")
def qapp():
    """The report draws, and drawing needs an application to measure type."""
    from PyQt6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_report_builds_for_an_infusion_from_another_vendor(thermo_infusion,
                                                               qapp):
    """The whole path: the verdict, the channel, the average, the pages."""
    from milq import infusion, infusion_report
    from milq.samples import SampleEntry

    sample = mzml.MzmlFile(thermo_infusion).sample(0)
    entry = SampleEntry(path=thermo_infusion, sample_index=0, name="CA-d4",
                        sample=sample)
    report = infusion_report.report_for(
        entry, infusion.strongest_channel(sample), compound="CA-d4")
    assert report.verdict is not None and report.verdict.infusion
    assert report.polarity == "Negative"
    assert report.collision_energy == pytest.approx(22.0)
    assert report.written_precursor == pytest.approx(430.3423)
    assert report.scans == INFUSION_SCANS
    assert report.base_peak()[0] == pytest.approx(377.3018, abs=1e-3)
    assert "430.3489" in infusion_report.build_section(report, heading="one")


# --------------------------------------------------------------------------- #
# extraction without the XML parser
# --------------------------------------------------------------------------- #
def test_the_arrays_read_from_the_bytes_agree_with_the_parser(written):
    """
    Every spectrum's arrays are located the first time they are wanted and
    decoded straight from the file's bytes; the XML path is what they are
    checked against.
    """
    from xml.etree import ElementTree as ET

    file = mzml.MzmlFile(written)
    assert file.headers
    for header in file.headers:
        binaries = file._binaries_for(header)
        assert binaries is not None
        fast = file._decode(binaries)
        slow = mzml._arrays(ET.fromstring(file._data[header.offset:header.end]))
        assert np.array_equal(fast["mz"], slow["mz"])
        assert np.array_equal(fast["intensity"], slow["intensity"])
    file.close()


def test_extraction_agrees_with_a_scan_by_scan_sum(written):
    channel = mzml.MzmlFile(written).sample(0).channels[0]
    lo, hi = 264.2, 264.3
    x, y = channel.xic_range(lo, hi)
    _, top = channel.bpc(lo, hi)
    for scan in range(3):
        mz, intensity = channel.spectrum(scan)
        inside = intensity[(mz >= lo) & (mz <= hi)]
        assert y[scan] == pytest.approx(float(inside.sum()))
        assert top[scan] == pytest.approx(float(inside.max()))
    assert x.tolist() == pytest.approx([0.1, 0.2, 0.3])
    # a window holding nothing is a chromatogram of zeros, not an error
    assert channel.xic_range(900.0, 901.0)[1].tolist() == [0.0, 0.0, 0.0]
    assert channel.bpc(900.0, 901.0)[1].tolist() == [0.0, 0.0, 0.0]


def test_a_spectrum_the_bytes_cannot_read_is_left_to_the_parser(tmp_path):
    """A numpress array is refused with its name, through the XML path."""
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="1">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="1"><binaryDataArray>'
        '<cvParam accession="MS:1000523" name="64-bit float" value=""/>'
        '<cvParam accession="MS:1002312" name="MS-Numpress linear" value=""/>'
        '<cvParam accession="MS:1000514" name="m/z array" value=""/>'
        f"<binary>{_binary([1.0])}</binary>"
        "</binaryDataArray></binaryDataArrayList></spectrum>"
    )
    file = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body, name="np.mzML"))
    assert file._binaries_for(file.headers[0]) is None
    with pytest.raises(mzml.MzmlError, match="numpress"):
        file.sample(0).channels[0].spectrum(0)


def test_a_decoded_channel_is_kept_under_a_budget_and_dropped_on_close(
        written, monkeypatch):
    """
    One budget for the process, oldest out first, and a closed file's
    channels go with it — a batch is dozens of files, and a budget per
    file would be the budget times the batch.
    """
    monkeypatch.setattr(mzml, "DECODED_BUDGET", 1)      # room for the newest only
    mzml._DECODED.clear()
    monkeypatch.setattr(mzml, "_DECODED_BYTES", 0)
    file = mzml.MzmlFile(written)
    sample = file.sample(0)
    sample.channels[0].xic(264.2686)
    assert list(mzml._DECODED) == [(file._token, 0)]
    sample.channels[1].xic(264.2686)
    assert list(mzml._DECODED) == [(file._token, 1)]
    # what is held is what the channel measured, not a stale neighbour
    assert mzml._DECODED[(file._token, 1)][0].tolist() == pytest.approx(
        [264.2686, 282.2791, 264.2686, 264.2686, 282.2791])
    file.close()
    assert not mzml._DECODED and mzml._DECODED_BYTES == 0


def test_closing_lets_go_of_the_file(written):
    """Mapped, not read: on Windows a mapped file cannot be removed."""
    import os

    file = mzml.MzmlFile(written)
    file.sample(0).channels[0].spectrum(0)
    file.close()
    os.remove(written)
    assert not os.path.exists(written)
