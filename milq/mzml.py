"""
mzML: the open format, so data from other instruments can be read too.

mzML is what everything converts to. A Thermo .raw, an Agilent .d, a Bruker
.tdf all become mzML through ProteoWizard's msconvert, and a laboratory that
runs more than one instrument has mzML whether it wanted it or not. Reading it
is what turns this from a SCIEX viewer into something that can look at the
rest of the bench.

Two halves:

  * a reader that presents an mzML file through the same Channel and Sample
    interface as `wiff.py`, so nothing above this layer has to know which
    format it came from;
  * a writer, because a converted file that cannot be checked against its
    source is a file nobody should trust. Exporting from the .wiff reader —
    which is verified — and reading the result back is how the reader gets
    tested against something other than itself.

What mzML does not have is the notion of an experiment. A .wiff knows it holds
81 channels because the acquisition method said so; an mzML holds a flat list
of spectra and the channels have to be inferred from what distinguishes them:
MS level, precursor, collision energy, mass range. That inference is the only
guesswork in here, and it is written to be visible rather than clever.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import mmap
import os
import re
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import numpy as np

from .wiff import ChannelInfo

#: PSI-MS controlled vocabulary accessions this reader acts on. Anything not
#: listed is carried past without comment: an mzML written by a vendor tool
#: is full of terms that describe the instrument rather than the data.
MS_LEVEL = "MS:1000511"
SCAN_START_TIME = "MS:1000016"
SELECTED_ION_MZ = "MS:1000744"
CHARGE_STATE = "MS:1000041"
ISOLATION_TARGET = "MS:1000827"
COLLISION_ENERGY = "MS:1000045"
SCAN_WINDOW_LOWER = "MS:1000501"
SCAN_WINDOW_UPPER = "MS:1000500"
TOTAL_ION_CURRENT = "MS:1000285"
BASE_PEAK_MZ = "MS:1000504"
BASE_PEAK_INTENSITY = "MS:1000505"
POSITIVE_SCAN = "MS:1000130"
NEGATIVE_SCAN = "MS:1000129"
CENTROID_SPECTRUM = "MS:1000127"
PROFILE_SPECTRUM = "MS:1000128"

BIT_64 = "MS:1000523"
BIT_32 = "MS:1000521"
ZLIB = "MS:1000574"
NO_COMPRESSION = "MS:1000576"
MZ_ARRAY = "MS:1000514"
INTENSITY_ARRAY = "MS:1000515"
TIME_ARRAY = "MS:1000595"

#: numpress is lossy at its usual settings and is not decoded here. A file
#: that uses it is rejected by name rather than read wrongly.
NUMPRESS = {
    "MS:1002312": "linear",
    "MS:1002313": "positive integer",
    "MS:1002314": "short logged float",
}

#: what sits inside `<activation>` besides the dissociation method itself.
#: The element holds one term naming how the precursor was broken and any
#: number of terms describing how hard — reading the first cvParam would give
#: "collision energy" for a Thermo HCD scan, which names a number rather than
#: a method. Everything not on this list is taken as the method, so a
#: dissociation this program has never heard of still comes through by name
#: instead of being dropped for not being recognised.
NOT_A_DISSOCIATION = {
    COLLISION_ENERGY,                   # collision energy
    "MS:1000138",                       # normalized collision energy
    "MS:1000509",                       # activation energy
    "MS:1002679",                       # supplemental collision energy
    # a supplemental activation is a second one applied on top of the first,
    # and the first is the one that names the experiment
    "MS:1000892",                       # supplemental collision-induced …
    "MS:1002680",                       # supplemental beam-type CID
}

#: how close two precursor masses must be to be counted as the same channel.
#: Vendors write the same transition with slightly different rounding from
#: scan to scan, and a channel per rounding error would be useless.
PRECURSOR_TOLERANCE = 0.01

#: our own writer records the experiment a spectrum came from, so a file this
#: application wrote reconstructs exactly rather than by inference
EXPERIMENT_PARAM = "milq experiment"
#: and what the acquisition method called it. mzML has nowhere to put a
#: vendor's experiment name, so a converted file loses "TOF PI" and becomes
#: "MS2". Ours keeps it; anyone else's is described by its MS level, which is
#: all their file says.
EXPERIMENT_NAME_PARAM = "milq experiment name"


class MzmlError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #
#: `{namespace}name` → `name`. mzML's element vocabulary is a few dozen names
#: and every one of them recurs once per scan, so the split is worth doing
#: once each: reading a 23,722-spectrum run asked for one 1,485,831 times.
_LOCAL_NAMES: dict[str, str] = {}

#: a file whose tags really are unbounded (a converter stamping an id into
#: the element name) must not grow the table without limit. Past this the
#: split simply runs every time, which is what it always did.
_LOCAL_NAMES_MAX = 4096


def _local(tag: str) -> str:
    """The tag without its namespace — mzML declares one and never varies it."""
    name = _LOCAL_NAMES.get(tag)
    if name is None:
        name = tag.rsplit("}", 1)[-1]
        if len(_LOCAL_NAMES) < _LOCAL_NAMES_MAX:
            _LOCAL_NAMES[tag] = name
    return name


def _params(element) -> dict[str, str]:
    """
    Every cvParam and userParam under an element, by accession and by name.

    Indexing both ways is deliberate: accessions are what the standard
    guarantees, names are what a hand-written file is likely to have right.
    """
    found: dict[str, str] = {}
    for child in element.iter():
        tag = _local(child.tag)
        if tag not in ("cvParam", "userParam"):
            continue
        value = child.get("value", "")
        accession = child.get("accession")
        if accession:
            found[accession] = value
        name = child.get("name")
        if name:
            found[name] = value
    return found


def _decode_array(element) -> np.ndarray:
    """One binaryDataArray, from base64 through compression to numbers."""
    params = _params(element)
    for accession, kind in NUMPRESS.items():
        if accession in params:
            raise MzmlError(
                f"this file uses numpress {kind} compression, which is lossy "
                "and is not decoded here; reconvert with "
                "--filter 'peakPicking' left off and no numpress"
            )
    binary = element.find("binary")
    if binary is None:
        binary = next((c for c in element if _local(c.tag) == "binary"), None)
    if binary is None or not (binary.text or "").strip():
        return np.zeros(0, dtype=np.float64)

    raw = base64.b64decode(binary.text)
    if ZLIB in params:
        raw = zlib.decompress(raw)
    if BIT_64 in params:
        return np.frombuffer(raw, dtype="<f8").astype(np.float64)
    if BIT_32 in params:
        return np.frombuffer(raw, dtype="<f4").astype(np.float64)
    raise MzmlError("a binary array declares neither 32- nor 64-bit floats")


def _arrays(element) -> dict[str, np.ndarray]:
    """The m/z, intensity and time arrays of one spectrum or chromatogram."""
    out: dict[str, np.ndarray] = {}
    for array in element.iter():
        if _local(array.tag) != "binaryDataArray":
            continue
        params = _params(array)
        values = _decode_array(array)
        if MZ_ARRAY in params:
            out["mz"] = values
        elif INTENSITY_ARRAY in params:
            out["intensity"] = values
        elif TIME_ARRAY in params:
            out["time"] = values
    return out


#: how much decoded data one file keeps for extraction, in bytes. A
#: chromatogram is made by decoding every scan of its channel, and a batch
#: asks the same channel for one component after another — 141 components
#: over 81 channels on the real method — so a channel once decoded is kept
#: until the budget pushes it out, oldest first. A TOF channel of a real
#: run is some 14 MB decoded, so this holds a dozen or so of them; the
#: whole run would be a gigabyte, which is why it is a budget and not a
#: switch.
DECODED_BUDGET = 256 * 2 ** 20

#: the decoded channels of every open file, keyed by (file, channel), oldest
#: first. One budget for the process: a batch has dozens of files open, and a
#: budget per file would be the budget times the batch
_DECODED: OrderedDict[tuple[int, int], tuple] = OrderedDict()
_DECODED_BYTES = 0
_TOKENS = itertools.count()


def _hold_decoded(key: tuple[int, int], held: tuple) -> None:
    """Keep a decoded channel, letting the oldest go past the budget."""
    global _DECODED_BYTES
    size = sum(int(a.nbytes) for a in held)
    while _DECODED and _DECODED_BYTES + size > DECODED_BUDGET:
        _, gone = _DECODED.popitem(last=False)
        _DECODED_BYTES -= sum(int(a.nbytes) for a in gone)
    _DECODED[key] = held
    _DECODED_BYTES += size


def _drop_decoded(file_id: int) -> None:
    """Forget every decoded channel of one file."""
    global _DECODED_BYTES
    for key in [k for k in _DECODED if k[0] == file_id]:
        _DECODED_BYTES -= sum(int(a.nbytes) for a in _DECODED.pop(key))


@dataclass(frozen=True)
class _Binary:
    """Where one binary array's base64 text sits in the file, and how to decode it."""

    kind: str | None            # "mz", "intensity", "time", or None: not read
    start: int                  # byte range of the base64 text; empty when start == end
    end: int
    zlib: bool
    bits: int                   # 64 or 32


_ACCESSION = re.compile(rb'accession="([^"]*)"')
_NUMPRESS_BYTES = tuple(a.encode() for a in NUMPRESS)
_BIT_64_BYTES, _BIT_32_BYTES, _ZLIB_BYTES = (
    BIT_64.encode(), BIT_32.encode(), ZLIB.encode())
_KIND_BYTES = ((MZ_ARRAY.encode(), "mz"), (INTENSITY_ARRAY.encode(), "intensity"),
               (TIME_ARRAY.encode(), "time"))


def _binaries_of(fragment: bytes, base: int) -> tuple[_Binary, ...] | None:
    """
    The binary arrays of one spectrum, located by scanning its bytes.

    An extracted chromatogram needs every scan of a channel, and reading a
    scan through the XML parser — the element built, every cvParam walked
    twice — cost more than decoding its numbers did: measured on a synthetic
    81-channel run, 20 s of extraction were 11 s of XML and 4 s of base64
    and zlib. The description of each array is fixed at open time, so it is
    found once here, and `_spectrum_arrays` then goes straight from the
    file's bytes to the numbers.

    Returns None for a spectrum this does not read that way — a numpress
    array, an array declaring neither precision — and the XML path stands in,
    with its own errors.
    """
    # `find` rather than a regular expression: the body of an array is
    # kilobytes of base64, and a pattern that has to walk it cost more than
    # the XML parse it was replacing. Measured: 2.2 s of a 5 s open, against
    # 0.3 s this way.
    found: list[_Binary] = []
    position = 0
    while True:
        start = fragment.find(b"<binaryDataArray", position)
        if start < 0:
            break
        after = fragment[start + 16:start + 17]
        if after not in (b" ", b">", b"\t", b"\n", b"\r"):     # …List, or a longer name
            position = start + 16
            continue
        stop = fragment.find(b"</binaryDataArray>", start)
        if stop < 0:
            break
        position = stop + 18
        opening = fragment.find(b"<binary", start, stop)
        # `<binaryDataArray`'s own name begins with `<binary`, so the search
        # starts past it
        while 0 <= opening < stop and fragment[opening + 7:opening + 8] not in (b">", b"/", b" "):
            opening = fragment.find(b"<binary", opening + 7, stop)
        head = fragment[start:opening if opening >= 0 else stop]
        accessions = set(_ACCESSION.findall(head))
        if any(a in accessions for a in _NUMPRESS_BYTES):
            return None
        if _BIT_64_BYTES in accessions:
            bits = 64
        elif _BIT_32_BYTES in accessions:
            bits = 32
        else:
            return None
        kind = next((name for accession, name in _KIND_BYTES
                     if accession in accessions), None)
        text_start = text_end = 0
        if opening >= 0:
            close = fragment.find(b">", opening, stop)
            if close > 0 and fragment[close - 1:close] != b"/":
                closing = fragment.find(b"</binary>", close, stop)
                if closing >= 0:
                    text_start, text_end = base + close + 1, base + closing
        found.append(_Binary(kind, text_start, text_end,
                             _ZLIB_BYTES in accessions, bits))
    return tuple(found)


@dataclass(frozen=True)
class _ScanHeader:
    """What is known about a spectrum without decoding its arrays."""

    index: int
    offset: int
    end: int
    ms_level: int
    rt: float                       # minutes
    precursor: float | None
    collision_energy: float | None
    #: the dissociation named in `<activation>`, "" when the file names none
    activation: str
    #: the precursor's charge from `selectedIon`, None when not stated
    charge: int | None
    low: float
    high: float
    polarity: str
    centroided: bool
    total_ion_current: float | None      # None when the file does not say
    n_points: int
    experiment: int | None          # only in files this application wrote
    experiment_name: str

    @property
    def key(self) -> tuple:
        """What makes two scans belong to the same channel."""
        if self.experiment is not None:
            return ("experiment", self.experiment)
        precursor = (round(self.precursor / PRECURSOR_TOLERANCE)
                     if self.precursor is not None else None)
        return (self.ms_level, precursor,
                round(self.collision_energy, 2) if self.collision_energy else None,
                round(self.low, 1), round(self.high, 1), self.polarity,
                # a method that runs the same precursor twice, once by CID and
                # once by HCD, has two entries and not one. The charge is not
                # here: data-dependent acquisition assigns it per precursor,
                # so it separates scans that came from the same entry.
                self.activation)


class MzmlChannel:
    """
    One inferred experiment: the scans that share a precursor and a range.

    The same interface as `wiff.Channel`, because the workspaces above use it
    without asking where the data came from.
    """

    def __init__(self, sample: "MzmlSample", index: int,
                 headers: list[_ScanHeader], period: int | None = None):
        self._sample = sample
        self._headers = headers
        self.index = index
        #: which period of the acquisition's cycle this channel belongs to,
        #: or None when the scans were grouped by their properties because
        #: no cycle was found. `MzmlSample.tic` needs it: only channels of
        #: one period are measured cycle by cycle and may be added up that
        #: way. See `acquisition_cycles`.
        self.period = period
        # cached here rather than with lru_cache on the method: that keeps one
        # instance alive for the life of the process, and with maxsize=1 it
        # caches nothing at all when the caller walks 81 channels in turn
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self.info = self._read_info()

    def _read_info(self) -> ChannelInfo:
        first = self._headers[0]
        if first.experiment_name:
            name = first.experiment_name
        elif first.ms_level <= 1:
            name = "MS"
        else:
            name = f"MS{first.ms_level}"
        return ChannelInfo(
            index=self.index,
            name=name,
            experiment_type="MS" if first.ms_level <= 1 else "Product Ion",
            polarity=first.polarity,
            precursor=first.precursor,
            start_mass=first.low,
            end_mass=first.high,
            n_scans=len(self._headers),
            collision_energy=first.collision_energy,
            activation=first.activation,
            charge=first.charge,
        )

    # -- chromatograms -------------------------------------------------------- #
    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        """
        The total ion current per scan.

        Taken from the cvParam the converter wrote where it exists. That is
        the number the instrument reported, and recomputing it from the arrays
        would substitute our arithmetic for the instrument's — a difference
        that shows up as a chromatogram that does not match the vendor's.
        """
        if self._tic is None:
            times = np.array([h.rt for h in self._headers], dtype=float)
            if all(h.total_ion_current is not None for h in self._headers):
                values = np.array([h.total_ion_current for h in self._headers],
                                  dtype=float)
            else:
                values = np.array([float(self._read(h)["intensity"].sum())
                                   for h in self._headers], dtype=float)
            self._tic = (times, values)
        return self._tic

    @property
    def rt(self) -> np.ndarray:
        return self.tic()[0]

    def bpc(self, mz_min: float | None = None, mz_max: float | None = None,
            tolerance: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
        lo = self.info.start_mass if mz_min is None else mz_min
        hi = self.info.end_mass if mz_max is None else mz_max
        mz, intensity, scan = self._decoded()
        inside = (mz >= lo) & (mz <= hi)
        values = np.zeros(len(self._headers), dtype=float)
        np.maximum.at(values, scan[inside], intensity[inside])
        return self._times(), values

    def _times(self) -> np.ndarray:
        return np.array([h.rt for h in self._headers], dtype=float)

    def _decoded(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Every scan of the channel decoded and laid end to end: the masses,
        the intensities, and for each point the scan it belongs to.

        Held by the file under `DECODED_BUDGET`, so the second component
        extracted from a channel does not decode it again. Extraction is
        then two vectorised passes over the channel rather than a Python
        loop over its scans.
        """
        key = (self._sample._file._token, self.index)
        held = _DECODED.get(key)
        if held is not None:
            _DECODED.move_to_end(key)
            return held
        masses, intensities = [], []
        for header in self._headers:
            arrays = self._read(header)
            masses.append(arrays["mz"])
            intensities.append(arrays["intensity"])
        counts = np.fromiter((m.size for m in masses), dtype=np.int64,
                             count=len(masses))
        mz = np.concatenate(masses) if masses else np.zeros(0)
        intensity = np.concatenate(intensities) if intensities else np.zeros(0)
        scan = np.repeat(np.arange(len(masses), dtype=np.int32), counts)
        held = (mz, intensity, scan)
        _hold_decoded(key, held)
        return held

    def xic(self, mz: float, tolerance: float = 0.02,
            unit: str = "Da") -> tuple[np.ndarray, np.ndarray]:
        half = mz * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        return self.xic_range(mz - half, mz + half)

    def xic_range(self, mz_min: float, mz_max: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Sum the intensity inside a mass window, scan by scan.

        Every point whose mass falls inside the window, and nothing else.

        SCIEX's own extraction gives a slightly larger number, and always
        larger: a window narrow enough to be useful cuts through the sides of
        the peak it is extracting, and Clearcore2 counts some of what falls
        outside. Measured over the 81 channels of one acquisition, extracting
        each channel at its own strongest mass, the two differ by a median of
        0.58% and at most 12% of the peak height.

        What is here is a plain sum, because two attempts at reproducing the
        vendor's edge rule were tried and neither survived being tested on
        windows other than the ones it was derived from — the second was a
        coin toss, better on 41 channels and worse on 38. An invented rule
        that is wrong half the time is worse than a stated one that is
        different every time, because only the second can be corrected for.

        The rest of the file does not have this problem: spectra, the total
        ion current and chromatographic integration all round-trip exactly.
        """
        lo, hi = sorted((float(mz_min), float(mz_max)))
        mz, intensity, scan = self._decoded()
        inside = (mz >= lo) & (mz <= hi)
        values = np.bincount(scan[inside], weights=intensity[inside],
                             minlength=len(self._headers)).astype(float)
        return self._times(), values

    # -- spectra -------------------------------------------------------------- #
    def _read(self, header: _ScanHeader) -> dict[str, np.ndarray]:
        return self._sample._file._spectrum_arrays(header)

    def spectrum(self, scan: int,
                 add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """
        One scan.

        `add_zeros` is accepted and ignored. It exists because SCIEX strips
        zero-intensity points out of a profile spectrum and its library can
        put them back using the instrument's own step size. An mzML holds
        whatever the converter wrote and nothing that says what the step was,
        so inventing the zeros here would be inventing data.
        """
        if not self._headers:
            return np.zeros(0), np.zeros(0)
        index = int(np.clip(scan, 0, len(self._headers) - 1))
        arrays = self._read(self._headers[index])
        return arrays["mz"], arrays["intensity"]

    def spectrum_rt_range(self, rt_start: float, rt_end: float,
                          add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """
        The average spectrum over a time range.

        The axis is the union of the masses actually measured, which keeps
        every peak the instrument saw; a fixed bin width would move them. On
        that axis every scan contributes **only at the masses it measured**,
        and nothing anywhere else.

        That last sentence is the whole of this method and it was got wrong
        first. The original put each scan on the common axis with
        `np.interp`, which is the natural thing to write and is an invention:
        a profile spectrum arrives with its zero points stripped out, so
        between two peaks a scan has no points at all, and interpolating it
        draws a straight line from the end of one peak to the start of the
        next — signal at every mass in between, in a stretch where the
        instrument reported nothing. Measured against SCIEX's own averaging
        of the same 146 scans, over the same 221,847-point axis: the apex
        heights agreed, but 220,222 of the 221,847 points came back higher
        and the spectrum totalled **3.31 times** what the vendor's did, an
        extra 834,025 counts. Centroiding it gave 670 sticks where the
        vendor's average gives 424.

        Adding each scan up where it was measured instead reproduces SCIEX's
        averaged spectrum **exactly** — same 221,847 masses, same total to
        ten figures, largest difference at any point 0.0, cosine 1.00000000.
        That is the rule the vendor uses, arrived at by measuring rather than
        by reasoning about it, and it is right for a centroided file too,
        where interpolating between two sticks is worse still.
        """
        lo, hi = sorted((float(rt_start), float(rt_end)))
        chosen = [h for h in self._headers if lo <= h.rt <= hi]
        if not chosen:
            return self.spectrum(self.scan_at_rt((lo + hi) / 2))
        if len(chosen) == 1:
            arrays = self._read(chosen[0])
            return arrays["mz"], arrays["intensity"]

        parts = [self._read(h) for h in chosen]
        masses = np.concatenate([p["mz"] for p in parts])
        if masses.size == 0:
            return np.zeros(0), np.zeros(0)
        heights = np.concatenate([p["intensity"] for p in parts])
        # one pass: the distinct masses, and where each point went
        axis, where = np.unique(masses, return_inverse=True)
        total = np.bincount(where, weights=heights, minlength=axis.size)
        return axis, total / len(parts)

    def parameters(self) -> dict[str, str]:
        first = self._headers[0]
        out = {
            "MS level": str(first.ms_level),
            "Scans": str(len(self._headers)),
            "Mass range": f"{first.low:g} – {first.high:g}",
        }
        if first.precursor is not None:
            out["Precursor"] = f"{first.precursor:.4f}"
        if first.charge is not None:
            out["Charge"] = str(first.charge)
        if first.collision_energy is not None:
            out["Collision energy"] = f"{first.collision_energy:g}"
        if first.activation:
            out["Activation"] = first.activation
        out["Spectrum type"] = "centroid" if first.centroided else "profile"
        return out

    # -- positions ------------------------------------------------------------ #
    def scan_at_rt(self, rt: float) -> int:
        times = self.rt
        if times.size == 0:
            return 0
        return int(np.argmin(np.abs(times - rt)))

    def rt_at_scan(self, scan: int) -> float:
        times = self.rt
        if times.size == 0:
            return 0.0
        return float(times[int(np.clip(scan, 0, times.size - 1))])

    def scans_in_range(self, rt_start: float, rt_end: float) -> tuple[int, int]:
        lo, hi = sorted((rt_start, rt_end))
        times = self.rt
        idx = np.nonzero((times >= lo) & (times <= hi))[0]
        if idx.size == 0:
            centre = self.scan_at_rt((lo + hi) / 2)
            return centre, centre
        return int(idx[0]), int(idx[-1])

    def __repr__(self) -> str:
        return f"<MzmlChannel {self.index}: {self.info.label}>"


class MzmlSample:
    """
    One run.

    An mzML holds a single run, so a file is one sample. Where a .wiff can
    carry a whole batch in one file, a converted batch is a directory of them.
    """

    def __init__(self, file: "MzmlFile"):
        self._file = file
        self.index = 0
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self.name = file.run_id or os.path.splitext(file.filename)[0]
        self.instrument = file.instrument
        self.channels: list[MzmlChannel] = file._build_channels(self)

    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        """
        The TIC of the whole run: every channel's total, at the times it was
        actually measured.

        Summed by cycle, which is how the instrument reports it.

        The experiments of one cycle are measured one after another, so no two
        of them share a time: the union of all the channels' times is one
        point per spectrum — 23,722 of them for an acquisition whose own total
        ion chromatogram has 577. That is not a chromatogram, it is a comb.

        A method runs its experiments in periods, and every experiment of a
        period has the same number of cycles. Summing a period cycle by cycle
        at the times of its first experiment gives back exactly what SCIEX
        reports: for the acquisition this was checked against, two periods of
        339 and 238 cycles, and 577 points.

        **Only where there is a cycle.** This used to recover the periods by
        grouping the channels on how many scans each had, which is the same
        thing for a scheduled method and nonsense for anything else. On a
        real Thermo direct-infusion acquisition that steps its isolation
        window across the precursor — 164 spectra, no repeating order, 82
        inferred channels of one, two and five scans each — the three
        distinct scan counts became three "periods", and the run's total ion
        chromatogram came back as **8 points for 164 spectra**, every
        channel's signal piled onto whichever channel of that length happened
        to be first. The total was right and the shape was fiction, and
        `infusion.is_infusion` reads exactly that shape.

        So the period comes from `acquisition_cycles`, which is the only
        thing that knows whether there is a cycle at all. A channel it could
        not place is a channel of an acquisition with no repeating order, and
        there the run's chromatogram is one point per spectrum — which is
        what a data-dependent run's own software draws.
        """
        if self._tic is not None:
            return self._tic
        if not self.channels:
            return np.zeros(0), np.zeros(0)
        periods: dict[int, list] = {}
        axes, totals = [], []
        for channel in self.channels:
            times, values = channel.tic()
            if channel.period is None:
                # no cycle: every scan of it stands on its own time
                axes.append(times)
                totals.append(values)
            else:
                periods.setdefault(channel.period, []).append((times, values))

        for members in periods.values():
            # an acquisition stopped part way through a cycle leaves the
            # experiments of its last one a scan longer than the rest, so the
            # axis is the longest member's and a short one adds nothing to
            # the points it does not reach
            axis = max((times for times, _values in members), key=len)
            total = np.zeros(axis.size, dtype=float)
            for _times, values in members:
                total[:values.size] += values
            axes.append(axis)
            totals.append(total)
        if not axes:
            return np.zeros(0), np.zeros(0)
        axis = np.concatenate(axes)
        total = np.concatenate(totals)
        order = np.argsort(axis, kind="stable")
        self._tic = (axis[order], total[order])
        return self._tic

    @property
    def problem(self) -> str | None:
        """An mzML is one file: nothing is beside it to go missing."""
        return None

    @property
    def acquisition_time(self) -> str:
        return self._file.start_time or ""

    def metadata(self) -> dict[str, str]:
        out = {
            "Format": "mzML",
            "Source": self._file.source_file or self._file.filename,
            "Instrument": self.instrument,
            "Channels": str(len(self.channels)),
            "Spectra": str(len(self._file.headers)),
        }
        if self._file.start_time:
            out["Acquired"] = self._file.start_time
        if self._file.software:
            out["Written by"] = self._file.software
        return out

    def __repr__(self) -> str:
        return f"<MzmlSample {self.name}: {len(self.channels)} channels>"


class MzmlFile:
    """An mzML file, presented the way `WiffFile` is."""

    def __init__(self, path: str | os.PathLike):
        self.path = os.path.realpath(str(path))
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        # mapped rather than read: a batch is dozens of these files open at
        # once, and a gigabyte read into the process is a gigabyte the
        # machine has to find, where a mapping is the system's own file
        # cache and is given back under pressure. Everything below takes
        # byte slices, which copy, so nothing ever points into the map.
        self._data: bytes | mmap.mmap = b""
        # names this file in the decoded cache; not `id()`, which a later
        # file could be given again once this one is collected
        self._token = next(_TOKENS)
        #: where each spectrum's arrays sit, by index, once looked for
        self._binaries: dict[int, tuple[_Binary, ...] | None] = {}
        with open(self.path, "rb") as handle:
            if os.fstat(handle.fileno()).st_size:
                self._data = mmap.mmap(handle.fileno(), 0,
                                       access=mmap.ACCESS_READ)
        head = bytes(self._data[:4096])
        if b"<mzML" not in head and b"<indexedmzML" not in head:
            self.close()
            raise MzmlError(f"{self.filename} does not look like mzML")

        self.run_id = ""
        self.start_time = ""
        self.instrument = "unknown"
        self.source_file = ""
        self.software = ""
        self._read_header()
        self.headers = self._read_scan_headers()
        self.sample_names = [self.run_id or os.path.splitext(self.filename)[0]]
        self._samples: dict[int, MzmlSample] = {}

    # -- file-level metadata --------------------------------------------------- #
    def _read_header(self) -> None:
        """Everything before the spectra: who wrote it, from what, and when."""
        cut = self._data.find(b"<spectrumList")
        head = bytes(self._data[:cut if cut >= 0 else len(self._data)])
        for match in re.finditer(rb'<run[^>]*>', head):
            attributes = match.group(0).decode("utf-8", "replace")
            self.run_id = _attribute(attributes, "id") or self.run_id
            self.start_time = _attribute(attributes, "startTimeStamp") or self.start_time
        for match in re.finditer(rb'<sourceFile[^>]*>', head):
            attributes = match.group(0).decode("utf-8", "replace")
            self.source_file = _attribute(attributes, "name") or self.source_file
        for match in re.finditer(rb'<software[^>]*>', head):
            attributes = match.group(0).decode("utf-8", "replace")
            identifier = _attribute(attributes, "id")
            if identifier:
                self.software = identifier
        self.instrument = self._read_instrument(head) or self.instrument

    @staticmethod
    def _read_instrument(head: bytes) -> str:
        """
        The instrument model, written three different ways in the wild.

        A vendor converter names the exact model as its own CV term and leaves
        the value empty — "TripleTOF 6600", accession MS:1000932. A generic
        writer uses the parent term "instrument model" and puts the model in
        the value. Reading only one convention leaves half the files saying
        "unknown".

        The third is the one ProteoWizard writes from a Thermo `.raw`, and it
        is not a variant of the term at all: the model goes in a
        `referenceableParamGroup` named `CommonInstrumentParams`, and each
        `instrumentConfiguration` carries only a `referenceableParamGroupRef`
        pointing at it. An mzML built that way has no cvParam inside the
        configuration to read, and both real Thermo files measured here —
        an LTQ Orbitrap Elite infusion and ProteoWizard's own LTQ FT example
        — came back "unknown" until the reference was followed. So the groups
        are read first and a `ref` resolves through them.
        """
        groups = _param_groups(head)
        block = _between(head, b"<instrumentConfiguration",
                         b"</instrumentConfigurationList>")
        if not block:
            return ""
        for match in re.finditer(rb"<referenceableParamGroupRef[^>]*/?>", block):
            name = _attribute(match.group(0).decode("utf-8", "replace"), "ref")
            if name in groups and groups[name]:
                return groups[name]
        # stop at the component list: its cvParams describe the source and the
        # detector, not the instrument
        cut = block.find(b"<componentList")
        if cut > 0:
            block = block[:cut]
        return _model_in(block)

    # -- the scan index --------------------------------------------------------- #
    def _read_scan_headers(self) -> list[_ScanHeader]:
        """
        One pass over the file, reading each spectrum's description but not
        its arrays.

        A run of this size is tens of thousands of spectra and gigabytes of
        decoded numbers; holding them would be pointless when a chromatogram
        needs only the time and the total. The byte range of each spectrum is
        kept so the arrays can be fetched when something actually asks.
        """
        headers: list[_ScanHeader] = []
        for index, (start, stop) in enumerate(_element_ranges(self._data, b"spectrum")):
            fragment = self._data[start:stop]
            cut = fragment.find(b"<binaryDataArrayList")
            head = fragment if cut < 0 else fragment[:cut] + b"</spectrum>"
            try:
                element = ET.fromstring(head)
            except ET.ParseError:
                continue
            headers.append(self._header_of(element, index, start, stop))
        return headers

    def _header_of(self, element, index: int, start: int, stop: int) -> _ScanHeader:
        params, rt, activation = _scan_facts(element)
        # `selected ion m/z` is what the instrument decided to fragment and is
        # the number to prefer. Some converters write only the isolation
        # window, and a channel with no precursor at all would be read as a
        # survey scan — so the window's centre stands in where there is one,
        # rather than the scan becoming MS1 by omission.
        precursor = _float_or_none(params.get(SELECTED_ION_MZ))
        if precursor is None:
            precursor = _float_or_none(params.get(ISOLATION_TARGET))
        ce = _float_or_none(params.get(COLLISION_ENERGY))
        charge = _float_or_none(params.get(CHARGE_STATE))
        low = _float_or_none(params.get(SCAN_WINDOW_LOWER))
        high = _float_or_none(params.get(SCAN_WINDOW_UPPER))
        experiment = params.get(EXPERIMENT_PARAM)
        return _ScanHeader(
            index=index,
            offset=start,
            end=stop,
            ms_level=int(float(params.get(MS_LEVEL, 1) or 1)),
            rt=rt,
            precursor=precursor,
            collision_energy=ce,
            activation=activation,
            charge=int(charge) if charge is not None else None,
            low=low if low is not None else 0.0,
            high=high if high is not None else 0.0,
            polarity="Negative" if NEGATIVE_SCAN in params else "Positive",
            centroided=CENTROID_SPECTRUM in params,
            # not `or -1.0`: a scan with nothing in it has a total of zero,
            # which is falsy, and reading that as "missing" made a whole
            # channel fall back to summing the points instead of using the
            # totals the instrument recorded
            total_ion_current=_float_or_none(params.get(TOTAL_ION_CURRENT)),
            n_points=int(element.get("defaultArrayLength", 0) or 0),
            experiment=int(experiment) if experiment not in (None, "") else None,
            experiment_name=params.get(EXPERIMENT_NAME_PARAM, ""),
        )

    def _binaries_for(self, header: _ScanHeader) -> tuple[_Binary, ...] | None:
        """
        Where a spectrum's arrays sit, found the first time it is decoded.

        Not at open time: locating them for every spectrum cost 0.26 s of a
        1.5 s open on a 19,440-spectrum file, paid on every project load
        for scans most of which are never decoded. Found once here, it is
        a few microseconds on a channel's first extraction.
        """
        try:
            return self._binaries[header.index]
        except KeyError:
            pass
        fragment = self._data[header.offset:header.end]
        cut = fragment.find(b"<binaryDataArrayList")
        found = (None if cut < 0
                 else _binaries_of(fragment[cut:], header.offset + cut))
        self._binaries[header.index] = found
        return found

    def _spectrum_arrays(self, header: _ScanHeader) -> dict[str, np.ndarray]:
        binaries = self._binaries_for(header)
        if binaries is not None:
            arrays = self._decode(binaries)
        else:
            element = ET.fromstring(self._data[header.offset:header.end])
            arrays = _arrays(element)
        length = header.n_points
        mz = arrays.get("mz", np.zeros(0))
        intensity = arrays.get("intensity", np.zeros(0))
        if length and (mz.size != length or intensity.size != length):
            raise MzmlError(
                f"spectrum {header.index} declares {length} points but decoded "
                f"{mz.size} m/z and {intensity.size} intensities"
            )
        return {"mz": mz, "intensity": intensity}

    # -- channels ---------------------------------------------------------------- #
    def _build_channels(self, sample: MzmlSample) -> list[MzmlChannel]:
        """
        Group the scans into experiments.

        mzML has no idea of an experiment; it has a list of spectra. Scans
        that share an MS level, a precursor, a collision energy and a mass
        range came from the same entry in the acquisition method — except
        when a method has two entries that agree on all of those, which is
        common enough: a panel may run the same transition twice at different
        points in the cycle. On a real 81-channel acquisition, grouping by
        those properties alone gave 69 channels.

        What separates them is the order of acquisition, which mzML does keep.
        A scheduled method runs its experiments in a fixed cycle, so the
        position of a spectrum within that cycle says which entry produced it,
        and identical entries sit at different positions. See `acquisition
        cycles` below for how the cycle is found, and for what happens when
        there is not one — data-dependent acquisition has no repeating order,
        and there the properties are all there is.
        """
        cycles = acquisition_cycles([h.key for h in self.headers])
        grouped: dict[tuple, list[_ScanHeader]] = {}
        periods: dict[tuple, int | None] = {}
        # strict: one position per spectrum, and a mismatch would silently
        # drop the scans past the end of the shorter list
        for position, header in zip(cycles, self.headers, strict=True):
            key = header.key if position is None else position
            grouped.setdefault(key, []).append(header)
            periods.setdefault(key, position[0] if position is not None else None)
        return [MzmlChannel(sample, index, group, periods[key])
                for index, (key, group) in enumerate(grouped.items())]

    # -- the same surface as WiffFile -------------------------------------------- #
    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def sample(self, index: int = 0) -> MzmlSample:
        if index not in self._samples:
            self._samples[index] = MzmlSample(self)
        return self._samples[index]

    def _decode(self, binaries: tuple[_Binary, ...]) -> dict[str, np.ndarray]:
        """Straight from the file's bytes to the numbers; see `_binaries_of`."""
        out: dict[str, np.ndarray] = {}
        for binary in binaries:
            if binary.kind is None:
                continue
            if binary.end <= binary.start:
                out[binary.kind] = np.zeros(0, dtype=np.float64)
                continue
            raw = base64.b64decode(self._data[binary.start:binary.end])
            if binary.zlib:
                raw = zlib.decompress(raw)
            out[binary.kind] = np.frombuffer(
                raw, dtype="<f8" if binary.bits == 64 else "<f4"
            ).astype(np.float64)
        return out

    def close(self) -> None:
        _drop_decoded(self._token)
        if isinstance(self._data, mmap.mmap):
            try:
                self._data.close()
            except (OSError, ValueError):
                pass
        self._data = b""

    def __repr__(self) -> str:
        return f"<MzmlFile {self.filename}: {len(self.headers)} spectra>"


# --------------------------------------------------------------------------- #
# acquisition cycles
# --------------------------------------------------------------------------- #
#: the longest cycle worth looking for. A scheduled method with more entries
#: than this in one cycle is not something this has been seen to encounter,
#: and an unbounded search over tens of thousands of spectra is slow for
#: nothing.
MAX_CYCLE = 4096

#: a cycle has to repeat at least this many times to be believed. Two
#: consecutive stretches that happen to match are a coincidence; twenty are a
#: method.
MIN_REPEATS = 4


def acquisition_cycles(keys: list) -> list:
    """
    Where each spectrum sits in the method's cycle, or None if there is no cycle.

    A scheduled acquisition runs its experiments in a fixed order and repeats
    it: this file's 23,722 spectra are a cycle of 44 experiments run 339
    times, followed by a cycle of 37 run 238 times — 44 + 37 being exactly the
    81 channels the vendor's own file declares. Position in the cycle is
    therefore the experiment, and it separates two entries that a method
    happens to have given identical settings.

    Returns a list the same length as `keys`, each item either
    (period, position) or None where no cycle was found. Data-dependent
    acquisition chooses its precursors from the last survey scan, so nothing
    repeats and everything comes back None, which leaves the caller to group
    by the properties of the scans as before.
    """
    total = len(keys)
    positions: list = [None] * total
    start, period = 0, 0
    while start < total:
        length, end = _cycle_at(keys, start, total)
        if length is None:
            # no cycle from here on: leave the rest ungrouped by position
            break
        for index in range(start, end):
            positions[index] = (period, (index - start) % length)
        start, period = end, period + 1
    return positions


def _cycle_at(keys: list, start: int, total: int):
    """The shortest cycle beginning at `start`, and how far it runs."""
    limit = min(MAX_CYCLE, (total - start) // MIN_REPEATS)
    for length in range(1, limit + 1):
        if keys[start:start + length] != keys[start + length:start + 2 * length]:
            continue
        end = start + length
        while (end + length <= total
               and keys[end:end + length] == keys[start:start + length]):
            end += length
        if (end - start) // length >= MIN_REPEATS:
            # whatever is left of a final, incomplete cycle belongs to this
            # period too — an acquisition can be stopped part way through one
            remainder = total - end
            if 0 < remainder < length and keys[end:total] == keys[start:start + remainder]:
                end = total
            return length, end
    return None, total


# --------------------------------------------------------------------------- #
# small parsing helpers
# --------------------------------------------------------------------------- #
def _attribute(text: str, name: str) -> str:
    match = re.search(rf'{name}="([^"]*)"', text)
    return match.group(1) if match else ""


#: cvParams that turn up beside the model in an instrument's parameter group
#: and are not the model. The serial number is the one that matters: it is
#: written with a value, like the generic "instrument model" term, and
#: reading it would name every LTQ Orbitrap Elite "SN05311B".
NOT_A_MODEL = {
    "MS:1000529",                       # instrument serial number
    "MS:1000032",                       # customization
    "MS:1000031",                       # instrument model, handled by name
}


def _model_in(block: bytes) -> str:
    """
    The instrument model named in a stretch of mzML, by either convention.

    A vendor converter names the exact model as its own CV term with an empty
    value; a generic writer uses the parent term MS:1000031 and puts the
    model in the value.
    """
    first_named = ""
    for match in re.finditer(rb"<cvParam[^>]*/?>", block):
        text = match.group(0).decode("utf-8", "replace")
        accession = _attribute(text, "accession")
        name = _attribute(text, "name")
        value = _attribute(text, "value")
        if accession == "MS:1000031" and value:
            return value
        if (name and not value and not first_named
                and accession not in NOT_A_MODEL):
            first_named = name
    return first_named


def _param_groups(head: bytes) -> dict[str, str]:
    """
    The instrument model each `referenceableParamGroup` names, by its id.

    ProteoWizard writes a Thermo file this way as a rule: one group called
    `CommonInstrumentParams` holding the model and the serial number, and
    every `instrumentConfiguration` pointing at it and holding nothing of its
    own.
    """
    groups: dict[str, str] = {}
    block = _between(head, b"<referenceableParamGroupList",
                     b"</referenceableParamGroupList>")
    if not block:
        return groups
    for match in re.finditer(
            rb"<referenceableParamGroup\s[^>]*>(.*?)</referenceableParamGroup>",
            block, re.DOTALL):
        identifier = _attribute(match.group(0)[:match.group(0).find(b">")]
                                .decode("utf-8", "replace"), "id")
        if identifier:
            groups[identifier] = _model_in(match.group(1))
    return groups


def _between(data: bytes, opening: bytes, closing: bytes) -> bytes:
    start = data.find(opening)
    if start < 0:
        return b""
    stop = data.find(closing, start)
    return data[start:stop] if stop > 0 else data[start:]


def _activation(element) -> str:
    """
    How the precursor was broken, in the file's own words.

    mzML says so in `<activation>`, and it is the one thing about a product
    ion scan that a collision energy cannot stand in for: 22 eV of beam-type
    CID and 22 eV of electron-transfer dissociation are different experiments
    that give different spectra of the same compound. A `.wiff` does not
    carry it — Clearcore2 exposes `CollisionEnergy` and nothing that names
    the method — so this is a place where the open format says more than the
    vendor's, and the field is empty rather than guessed on that side.

    The element holds the method and any number of energies; the energies are
    named in `NOT_A_DISSOCIATION` and everything else is taken as the method,
    so a term this program has never seen comes through by name instead of
    being dropped for not being recognised.
    """
    for child in element.iter():
        if _local(child.tag) == "activation":
            return _activation_name(child)
    return ""


def _activation_name(activation) -> str:
    """The method named inside one `<activation>`, or "" — see `_activation`."""
    if activation is None:
        return ""
    for param in activation:
        if _local(param.tag) != "cvParam":
            continue
        if param.get("accession") in NOT_A_DISSOCIATION:
            continue
        name = (param.get("name") or "").strip()
        if name:
            return name
    return ""


def _float_or_none(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes(element) -> float:
    """
    The scan start time, in minutes.

    mzML records the unit, and converters disagree: ProteoWizard writes
    minutes from a SCIEX file and seconds from a Thermo one. Reading the
    number without the unit is how a twenty-minute run becomes a twenty-hour
    one.
    """
    for child in element.iter():
        if _local(child.tag) != "cvParam":
            continue
        if child.get("accession") != SCAN_START_TIME:
            continue
        return _minutes_of(child)
    return 0.0


def _minutes_of(param) -> float:
    """One `scan start time` cvParam in minutes — see `_minutes` for the units."""
    value = _float_or_none(param.get("value"))
    if value is None:
        return 0.0
    unit = (param.get("unitAccession") or "").strip()
    unit_name = (param.get("unitName") or "").lower()
    if unit == "UO:0000010" or unit_name.startswith("second"):
        return value / 60.0
    if unit == "UO:0000032" or unit_name.startswith("hour"):
        return value * 60.0
    return value


def _scan_facts(element) -> tuple[dict[str, str], float, str]:
    """
    One spectrum's parameters, its retention time and its activation, in a
    single walk of the element.

    `_params`, `_minutes` and `_activation` each walk every descendant, and
    `_header_of` wanted all three: reading a 23,722-spectrum run therefore
    visited about 4.5 million nodes to look at 1.5 million. The three answers
    come off one pass here. Each is computed exactly as its own function
    computes it — first `scan start time` in document order, first
    `<activation>` in document order, `cvParam` and `userParam` indexed by
    both accession and name — and `tests/test_mzml.py` asserts the two routes
    agree element for element on a file holding both.

    `<activation>`'s own cvParams stay in the parameter dictionary, because
    `_params` collects them: only the element that holds them is singled out.
    """
    params: dict[str, str] = {}
    rt = 0.0
    have_rt = False
    activation = None
    for child in element.iter():
        tag = _local(child.tag)
        if tag == "activation":
            if activation is None:
                activation = child
            continue
        if tag not in ("cvParam", "userParam"):
            continue
        value = child.get("value", "")
        accession = child.get("accession")
        if accession:
            params[accession] = value
            if not have_rt and accession == SCAN_START_TIME:
                rt = _minutes_of(child)
                have_rt = True
        name = child.get("name")
        if name:
            params[name] = value
    return params, rt, _activation_name(activation)


def _element_ranges(data: bytes, name: bytes):
    """
    The byte range of every `<name ...>...</name>` at any depth.

    Finding these by scanning rather than by the file's own index list is
    deliberate: an index is optional, is written by the converter, and is
    wrong often enough that trusting it means reading the wrong bytes with no
    error to say so.
    """
    opening = re.compile(rb"<" + name + rb"[\s>]")
    closing = b"</" + name + b">"
    position = 0
    while True:
        match = opening.search(data, position)
        if match is None:
            return
        start = match.start()
        # an empty element closes itself and has no arrays worth reading
        head_end = data.find(b">", start)
        if head_end > 0 and data[head_end - 1:head_end] == b"/":
            position = head_end + 1
            continue
        stop = data.find(closing, start)
        if stop < 0:
            return
        stop += len(closing)
        yield start, stop
        position = stop


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #
#: 64-bit for both arrays and zlib on top: lossless, and about the same size
#: as 32-bit uncompressed. Fidelity is the whole point of exporting from a
#: reader that has been checked; giving it back with 32-bit intensities would
#: throw away digits this application can prove it read correctly.
def _encode(values: np.ndarray, compress: bool = True) -> tuple[str, int]:
    raw = np.asarray(values, dtype="<f8").tobytes()
    if compress:
        raw = zlib.compress(raw, 6)
    encoded = base64.b64encode(raw).decode("ascii")
    return encoded, len(encoded)


def _cv(accession: str, name: str, value=None, unit: str = "",
        unit_name: str = "") -> str:
    parts = [f'accession="{accession}"', 'cvRef="MS"', f'name="{name}"']
    parts.append(f'value="{"" if value is None else value}"')
    if unit:
        parts.append(f'unitCvRef="{unit.split(":")[0]}"')
        parts.append(f'unitAccession="{unit}"')
        parts.append(f'unitName="{unit_name}"')
    return "<cvParam " + " ".join(parts) + "/>"


def _binary_array(values: np.ndarray, accession: str, name: str,
                  unit: str = "", unit_name: str = "",
                  compress: bool = True) -> str:
    encoded, length = _encode(values, compress)
    compression = (_cv(ZLIB, "zlib compression") if compress
                   else _cv(NO_COMPRESSION, "no compression"))
    return (
        f'<binaryDataArray encodedLength="{length}">'
        + _cv(BIT_64, "64-bit float")
        + compression
        + _cv(accession, name, unit=unit, unit_name=unit_name)
        + f"<binary>{encoded}</binary>"
        + "</binaryDataArray>"
    )


#: the accession to write back for a dissociation read in by name. The reader
#: keeps whatever term the file used, including one not on this list; writing
#: that back needs an accession, and MS:1000044 is the parent term every
#: dissociation is a kind of — a truthful "some dissociation, named here"
#: rather than a specific method this program made up.
_ACTIVATION_ACCESSIONS = {
    "collision-induced dissociation": "MS:1000133",
    "beam-type collision-induced dissociation": "MS:1000422",
    "trap-type collision-induced dissociation": "MS:1002472",
    "higher energy beam-type collision-induced dissociation": "MS:1002481",
    "electron transfer dissociation": "MS:1000598",
    "electron capture dissociation": "MS:1000250",
    "electron activated dissociation": "MS:1003294",
    "photodissociation": "MS:1000435",
    "in-source collision-induced dissociation": "MS:1001880",
    "pulsed q dissociation": "MS:1000599",
    "surface-induced dissociation": "MS:1000435",
}


def _activation_accession(name: str) -> str:
    return _ACTIVATION_ACCESSIONS.get(name, "MS:1000044")


def write_mzml(sample, path: str | os.PathLike, compress: bool = True,
               progress=None) -> str:
    """
    Write one sample out as indexed mzML.

    Everything the reader above needs to rebuild the channels is recorded:
    the precursor, the collision energy, the scan window, the polarity, and —
    beyond the standard — the experiment each scan came from, so a file this
    application wrote reconstructs its channels exactly rather than by
    inference. Another program ignores that user parameter and infers, which
    is what it would have to do for any vendor's file.

    Spectra are written as the instrument stored them. SCIEX strips the zeros
    out of a profile spectrum and its own library can put them back; that is a
    rendering step, and baking it into an exported file would be exporting a
    picture rather than a measurement.
    """
    path = str(path)
    scans = []
    for channel in sample.channels:
        # the instrument's own total ion current, not a sum of the points it
        # chose to store. A profile spectrum arrives with its zeros stripped
        # out, so adding up what is left is not what the detector reported —
        # measured on one acquisition, recomputing it moved every integrated
        # area by about two per cent.
        times, totals = channel.tic()
        for scan in range(len(times)):
            total = float(totals[scan]) if scan < len(totals) else None
            scans.append((channel, scan, float(times[scan]), total))
    # spectra go in time order, as an acquisition produces them
    scans.sort(key=lambda item: (item[2], item[0].index))

    run_id = _xml_escape(getattr(sample, "name", "run"))
    source = _xml_escape(os.path.basename(getattr(sample, "_wiff", None).path
                                          if getattr(sample, "_wiff", None) else path))

    offsets: list[tuple[str, int]] = []
    with open(path, "wb") as handle:
        def emit(text: str) -> None:
            handle.write(text.encode("utf-8"))

        emit(_HEADER.format(run_id=run_id, source=source,
                            instrument=_xml_escape(getattr(sample, "instrument", "")),
                            started=_xml_escape(getattr(sample, "acquisition_time", "") or ""),
                            count=len(scans)))
        for index, (channel, scan, rt, total) in enumerate(scans):
            if progress is not None and index % 500 == 0:
                progress(index, len(scans))
            mz, intensity = channel.spectrum(scan, add_zeros=False)
            identifier = (f"index={index} experiment={channel.index} "
                          f"scan={scan}")
            offsets.append((identifier, handle.tell()))
            emit(_spectrum_xml(index, identifier, channel, rt, mz, intensity,
                               compress, total))
        emit("</spectrumList></run></mzML>")

        index_offset = handle.tell()
        emit('<indexList count="1"><index name="spectrum">')
        for identifier, offset in offsets:
            emit(f'<offset idRef="{_xml_escape(identifier)}">{offset}</offset>')
        emit("</index></indexList>")
        emit(f"<indexListOffset>{index_offset}</indexListOffset>")
        emit("<fileChecksum>")
        handle.flush()

    # the checksum covers everything up to and including the opening tag of
    # the element it sits in, which is how the standard defines it
    with open(path, "rb") as handle:
        digest = hashlib.sha1(handle.read()).hexdigest()
    with open(path, "ab") as handle:
        handle.write(f"{digest}</fileChecksum></indexedmzML>".encode("utf-8"))
    if progress is not None:
        progress(len(scans), len(scans))
    return path


def _spectrum_xml(index: int, identifier: str, channel, rt: float,
                  mz: np.ndarray, intensity: np.ndarray,
                  compress: bool, total: float | None = None) -> str:
    info = channel.info
    level = 1 if info.is_ms1 else 2
    if total is None:
        total = float(np.sum(intensity)) if intensity.size else 0.0
    parts = [
        f'<spectrum index="{index}" id="{_xml_escape(identifier)}" '
        f'defaultArrayLength="{mz.size}">',
        _cv(MS_LEVEL, "ms level", level),
        _cv("MS:1000579" if level == 1 else "MS:1000580",
            "MS1 spectrum" if level == 1 else "MSn spectrum"),
        _cv(PROFILE_SPECTRUM, "profile spectrum"),
        _cv(NEGATIVE_SCAN if info.polarity.lower().startswith("neg")
            else POSITIVE_SCAN,
            "negative scan" if info.polarity.lower().startswith("neg")
            else "positive scan"),
        # repr, not a fixed number of decimals: a float written to six
        # places and read back is not the same float, and the difference
        # reaches the integrated areas
        _cv(TOTAL_ION_CURRENT, "total ion current", repr(float(total))),
    ]
    if intensity.size:
        peak = int(np.argmax(intensity))
        parts.append(_cv(BASE_PEAK_MZ, "base peak m/z", repr(float(mz[peak])),
                         unit="MS:1000040", unit_name="m/z"))
        parts.append(_cv(BASE_PEAK_INTENSITY, "base peak intensity",
                         repr(float(intensity[peak]))))

    parts.append('<scanList count="1">')
    parts.append(_cv("MS:1000795", "no combination"))
    parts.append("<scan>")
    parts.append(_cv(SCAN_START_TIME, "scan start time", repr(float(rt)),
                     unit="UO:0000031", unit_name="minute"))
    # the experiment this scan belongs to: not part of the standard, and the
    # only thing that lets a reader rebuild the channels without guessing
    parts.append(f'<userParam name="{EXPERIMENT_PARAM}" '
                 f'value="{channel.index}" type="xsd:int"/>')
    if info.name:
        parts.append(f'<userParam name="{EXPERIMENT_NAME_PARAM}" '
                     f'value="{_xml_escape(info.name)}"/>')
    parts.append('<scanWindowList count="1"><scanWindow>')
    parts.append(_cv(SCAN_WINDOW_LOWER, "scan window lower limit",
                     f"{info.start_mass:.6f}", unit="MS:1000040", unit_name="m/z"))
    parts.append(_cv(SCAN_WINDOW_UPPER, "scan window upper limit",
                     f"{info.end_mass:.6f}", unit="MS:1000040", unit_name="m/z"))
    parts.append("</scanWindow></scanWindowList></scan></scanList>")

    if not info.is_ms1 and info.precursor is not None:
        parts.append('<precursorList count="1"><precursor>')
        parts.append("<selectedIonList count=\"1\"><selectedIon>")
        parts.append(_cv(SELECTED_ION_MZ, "selected ion m/z",
                         f"{info.precursor:.6f}", unit="MS:1000040",
                         unit_name="m/z"))
        if info.charge is not None:
            parts.append(_cv(CHARGE_STATE, "charge state", int(info.charge)))
        parts.append("</selectedIon></selectedIonList>")
        parts.append("<activation>")
        # what the source said, where it said anything. A `.wiff` says
        # nothing — Clearcore2 exposes the energy and not the method — and
        # collision-induced dissociation is what a SCIEX product-ion
        # experiment is, so that stands where the source is silent. An mzML
        # read in and written back out keeps the term it arrived with.
        parts.append(_cv(_activation_accession(info.activation) if info.activation
                         else "MS:1000133",
                         info.activation or "collision-induced dissociation"))
        if info.collision_energy is not None:
            parts.append(_cv(COLLISION_ENERGY, "collision energy",
                             f"{info.collision_energy:g}", unit="UO:0000266",
                             unit_name="electronvolt"))
        parts.append("</activation></precursor></precursorList>")

    parts.append('<binaryDataArrayList count="2">')
    parts.append(_binary_array(mz, MZ_ARRAY, "m/z array",
                               unit="MS:1000040", unit_name="m/z",
                               compress=compress))
    parts.append(_binary_array(intensity, INTENSITY_ARRAY, "intensity array",
                               unit="MS:1000131", unit_name="number of detector counts",
                               compress=compress))
    parts.append("</binaryDataArrayList></spectrum>")
    return "".join(parts)


def _xml_escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<indexedmzML xmlns="http://psi.hupo.org/ms/mzml" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="http://psi.hupo.org/ms/mzml \
http://psidev.info/files/ms/mzML/xsd/mzML1.1.2_idx.xsd">
<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0" id="{run_id}">
<cvList count="2">
<cv id="MS" fullName="Proteomics Standards Initiative Mass Spectrometry Ontology" \
URI="https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/master/psi-ms.obo"/>
<cv id="UO" fullName="Unit Ontology" \
URI="https://raw.githubusercontent.com/bio-ontology-research-group/unit-ontology/master/unit.obo"/>
</cvList>
<fileDescription>
<fileContent>
<cvParam cvRef="MS" accession="MS:1000579" name="MS1 spectrum" value=""/>
<cvParam cvRef="MS" accession="MS:1000580" name="MSn spectrum" value=""/>
</fileContent>
<sourceFileList count="1">
<sourceFile id="source" name="{source}" location="file://">
<cvParam cvRef="MS" accession="MS:1000770" name="WIFF nativeID format" value=""/>
</sourceFile>
</sourceFileList>
</fileDescription>
<softwareList count="1">
<software id="MIL-Q" version="1">
<cvParam cvRef="MS" accession="MS:1000799" name="custom unreleased software tool" value="MIL-Q"/>
</software>
</softwareList>
<instrumentConfigurationList count="1">
<instrumentConfiguration id="instrument">
<cvParam cvRef="MS" accession="MS:1000031" name="instrument model" value="{instrument}"/>
</instrumentConfiguration>
</instrumentConfigurationList>
<dataProcessingList count="1">
<dataProcessing id="export">
<processingMethod order="0" softwareRef="MIL-Q">
<cvParam cvRef="MS" accession="MS:1000544" name="Conversion to mzML" value=""/>
</processingMethod>
</dataProcessing>
</dataProcessingList>
<run id="{run_id}" defaultInstrumentConfigurationRef="instrument" \
startTimeStamp="{started}">
<spectrumList count="{count}" defaultDataProcessingRef="export">
"""
