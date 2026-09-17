"""
Data layer: SCIEX WIFF files as numpy arrays.

Hierarchy: WiffFile -> Sample -> Channel (one "experiment" of the method).
Each Channel yields TIC, BPC, XIC and spectra (single scan or range average).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

from . import bootstrap

_API = None


def _api():
    """Import the .NET types once, after the bootstrap."""
    global _API
    if _API is None:
        bootstrap.ensure()
        from System import Array, Double
        from Clearcore2.Data.AnalystDataProvider import (
            AnalystDataProviderFactory,
            AnalystWiffDataProvider,
        )
        from Clearcore2.Data.DataAccess.SampleData import (
            BasePeakChromatogramSettings,
            ExtractedIonChromatogramSettings,
        )
        from Clearcore2.Utility import OpenFileMode

        _API = {
            "Array": Array,
            "Double": Double,
            "Factory": AnalystDataProviderFactory,
            "Provider": AnalystWiffDataProvider,
            "BPCSettings": BasePeakChromatogramSettings,
            "XICSettings": ExtractedIonChromatogramSettings,
            "OpenFileMode": OpenFileMode,
        }
    return _API


def _to_numpy(net_array) -> np.ndarray:
    """
    A Clearcore2 `double[]` as a numpy array, through the buffer protocol.

    pythonnet exports a .NET array of a primitive type as a C-contiguous
    buffer, so numpy can take the bytes in one memcpy. Walking it with
    `list()` marshals one double at a time across the managed boundary and
    cost 216× as much: 0.194 ms against 0.0009 ms for one 1,143-point TOF
    scan, which was 84% of building a contour and two thirds of averaging.
    The values are the same doubles either way — `tests/test_reader_arrays.py`
    checks the two routes byte for byte.

    **The copy is not optional.** `np.frombuffer`/`np.asarray` on the .NET
    object give an array whose memory belongs to the managed heap: it reads
    correctly today and is a use-after-free the moment the collector moves
    or frees the array behind it, which on macOS shows up as plausible
    numbers rather than a crash. `np.array(..., copy=True)` is the whole
    difference and costs nothing measurable.

    Anything the buffer protocol refuses — a `List<double>`, a jagged array,
    a future Clearcore2 returning something else — falls back to the element
    walk, so this is a speed-up and never a new failure.
    """
    if net_array is None:
        return np.zeros(0, dtype=np.float64)
    try:
        with memoryview(net_array) as view:
            return np.array(view, dtype=np.float64, copy=True)
    except (TypeError, ValueError, BufferError):
        return np.asarray(list(net_array), dtype=np.float64)


def _double_array(values) -> "object":
    api = _api()
    arr = api["Array"].CreateInstance(api["Double"], len(values))
    for i, v in enumerate(values):
        arr[i] = float(v)
    return arr


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ChannelInfo:
    """Metadata of one experiment (channel) of the acquisition method."""

    index: int
    name: str
    experiment_type: str
    polarity: str
    precursor: float | None
    start_mass: float
    end_mass: float
    n_scans: int
    collision_energy: float | None
    #: how the precursor was fragmented, in the words the file uses —
    #: "beam-type collision-induced dissociation" for a Thermo HCD scan,
    #: "electron transfer dissociation", and so on. Empty when the file does
    #: not say, which is every `.wiff`: Clearcore2 exposes the energy but not
    #: the method, and an activation invented from a collision energy would
    #: be an invention. Last in the field order, with a default, so the nine
    #: positional constructions in the tests keep working.
    activation: str = ""
    #: the precursor's charge, where the file states one. mzML records it in
    #: `selectedIon`; a `.wiff` does not carry it at all.
    charge: int | None = None

    @property
    def is_ms1(self) -> bool:
        return self.precursor is None

    @property
    def label(self) -> str:
        if self.is_ms1:
            return f"{self.name}  ({self.start_mass:.0f}-{self.end_mass:.0f})"
        ce = f", CE {self.collision_energy:g}" if self.collision_energy else ""
        return f"{self.name}  {self.precursor:.2f}  ->  {self.start_mass:.0f}-{self.end_mass:.0f}{ce}"

    @property
    def short_label(self) -> str:
        return self.name if self.is_ms1 else f"{self.name} {self.precursor:.2f}"


# --------------------------------------------------------------------------- #
class Channel:
    """One experiment of the method: TOF MS, TOF PI (MRM-HR), MRM, and so on."""

    def __init__(self, sample: "Sample", index: int):
        self._sample = sample
        self._exp = sample._ms.GetMSExperiment(index)
        self.index = index
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self.info = self._read_info()

    # -- metadata ------------------------------------------------------------ #
    def _read_info(self) -> ChannelInfo:
        d = self._exp.Details
        ranges = list(d.MassRangeInfo) if d.MassRangeInfo else []
        first = ranges[0] if ranges else None

        precursor = None
        if first is not None and hasattr(first, "FixedMasses"):
            fixed = list(first.FixedMasses or [])
            if fixed:
                precursor = float(fixed[0])

        ce = None
        try:
            info = self._exp.GetMassSpectrumInfo(0)
            value = getattr(info, "CollisionEnergy", None)
            if value is not None and float(value) != 0.0:
                ce = float(value)
        except Exception:
            ce = None

        return ChannelInfo(
            index=self.index,
            name=str(d.ExperimentName),
            experiment_type=str(d.ExperimentType),
            polarity=str(d.Polarity),
            precursor=precursor,
            start_mass=float(d.StartMass),
            end_mass=float(d.EndMass),
            n_scans=int(d.NumberOfScans),
            collision_energy=ce,
        )

    # -- chromatograms -------------------------------------------------------- #
    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        if self._tic is None:
            c = self._exp.GetTotalIonChromatogram()
            self._tic = (_to_numpy(c.GetActualXValues()),
                         _to_numpy(c.GetActualYValues()))
        return self._tic

    @property
    def rt(self) -> np.ndarray:
        return self.tic()[0]

    def bpc(self, mz_min: float | None = None, mz_max: float | None = None,
            tolerance: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
        api = _api()
        lo = self.info.start_mass if mz_min is None else mz_min
        hi = self.info.end_mass if mz_max is None else mz_max
        settings = api["BPCSettings"](tolerance, _double_array([lo]), _double_array([hi]))
        c = self._exp.GetBasePeakChromatogram(settings)
        return _to_numpy(c.GetActualXValues()), _to_numpy(c.GetActualYValues())

    def xic(self, mz: float, tolerance: float = 0.02,
            unit: str = "Da") -> tuple[np.ndarray, np.ndarray]:
        """Extracted ion chromatogram over a window around `mz`."""
        half = mz * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        return self.xic_range(mz - half, mz + half)

    def xic_range(self, mz_min: float, mz_max: float) -> tuple[np.ndarray, np.ndarray]:
        api = _api()
        c = self._exp.GetExtractedIonChromatogram(
            api["XICSettings"](float(mz_min), float(mz_max))
        )
        return _to_numpy(c.GetActualXValues()), _to_numpy(c.GetActualYValues())

    # -- spectra -------------------------------------------------------------- #
    def _read_spectrum(self, spectrum, add_zeros: bool) -> tuple[np.ndarray, np.ndarray]:
        """
        Pull the arrays out of a MassSpectrum, optionally restoring the zeros.

        SCIEX stores profile spectra with the zero-intensity points stripped
        out. Plotted as they come, a line is drawn straight from one peak to
        the next and the gaps between them look like signal. AddZeros puts a
        zero back on each side of every gap, using the instrument's own step
        size, which is what makes a profile spectrum render correctly.
        """
        if add_zeros:
            try:
                self._exp.AddZeros(spectrum, 1)
            except Exception:
                pass
        return (_to_numpy(spectrum.GetActualXValues()),
                _to_numpy(spectrum.GetActualYValues()))

    def spectrum(self, scan: int,
                 add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Spectrum of a single scan (0-based cycle index)."""
        scan = int(np.clip(scan, 0, max(self.info.n_scans - 1, 0)))
        return self._read_spectrum(self._exp.GetMassSpectrum(scan), add_zeros)

    def spectrum_rt_range(self, rt_start: float, rt_end: float,
                          add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Average spectrum of the scans inside the given time range."""
        lo, hi = sorted((float(rt_start), float(rt_end)))
        return self._read_spectrum(self._exp.GetMassSpectrum(lo, hi), add_zeros)

    def parameters(self) -> dict[str, str]:
        """Experiment parameters from the method (DP, CE, CES, ...)."""
        out: dict[str, str] = {}
        try:
            table = self._exp.Details.Parameters
        except Exception:
            return out
        for key in table.Keys:
            parameter = table[key]
            try:
                start, stop = float(parameter.Start), float(parameter.Stop)
            except Exception:
                out[str(key)] = str(parameter)
                continue
            # Start != Stop means a ramp (e.g. collision energy spread)
            out[str(key)] = f"{start:g}" if start == stop else f"{start:g} – {stop:g}"
        return out

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
        return f"<Channel {self.index}: {self.info.label}>"


# --------------------------------------------------------------------------- #
#: the sample has not yet tried to read a spectrum
_UNPROBED = object()


def scan_file_of(path: str | os.PathLike) -> str:
    """The companion a `.wiff` needs beside it: `name.wiff.scan`."""
    return str(path) + ".scan"


def stray_scan_files(path: str | os.PathLike) -> list[str]:
    """
    `.scan` files in the folder that belong to no `.wiff` there.

    A companion renamed by hand — `name.wiff_mix1.scan` where the `.wiff`
    became `name_mix1.wiff` — is the ordinary way the pair comes apart, and
    the stray is the file the reader needs, under the wrong name.
    """
    folder = os.path.dirname(os.path.abspath(str(path)))
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    wiffs = {n.lower() for n in names if n.lower().endswith(".wiff")}
    return sorted(n for n in names
                  if n.lower().endswith(".scan") and n[:-5].lower() not in wiffs)


def scan_problem(path: str | os.PathLike, error: BaseException) -> str:
    """
    What to tell someone whose spectra cannot be read, from the file that
    failed and the error Clearcore2 raised.

    The chromatograms and the method come from the `.wiff`, so the file
    opens and looks whole; the spectra, and with them every extracted ion
    chromatogram, come from the `.wiff.scan`. Without it the reader throws
    on the first spectrum, and a message deep in a .NET stack is not what
    a person at the instrument needs — the name of the file that is
    missing is, and the name of the one that may be it.
    """
    name = os.path.basename(str(path))
    companion = os.path.basename(scan_file_of(path))
    text = str(error).strip()
    first = text.splitlines()[0] if text else type(error).__name__
    if os.path.exists(scan_file_of(path)):
        return (f"the spectra of {name} cannot be read although {companion} "
                f"is beside it — Clearcore2 said: {first}")
    message = f"the spectra of {name} cannot be read: {companion} is not beside it"
    strays = stray_scan_files(path)
    if strays:
        message += (f"; the folder holds {', '.join(strays)}, which belongs to "
                    f"no .wiff there — renamed to {companion} it may be the one")
    return (message + ". The chromatograms open without it; the spectra, the "
            "extracted ion chromatograms and the quantitation do not.")


# --------------------------------------------------------------------------- #
class Sample:
    """One injection inside the wiff file."""

    def __init__(self, wiff: "WiffFile", index: int):
        self._wiff = wiff
        self.index = index
        self._sample = wiff._batch.GetSample(index)
        self._ms = self._sample.MassSpectrometerSample
        self.name = str(wiff.sample_names[index])
        self.instrument = str(self._ms.InstrumentName)
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self.channels: list[Channel] = [
            Channel(self, i) for i in range(int(self._ms.ExperimentCount))
        ]
        self._problem = _UNPROBED

    @property
    def problem(self) -> str | None:
        """
        Why the spectra cannot be read, or None when they can.

        Probed once, on the first scan of the first experiment: the `.wiff`
        alone gives the method, the totals and the chromatograms, and the
        first sign that the `.wiff.scan` is not beside it is a spectrum
        that throws. Asking here lets the file say so when it is opened,
        not when the first spectrum is clicked for.
        """
        if self._problem is _UNPROBED:
            self._problem = None
            if self.channels:
                try:
                    self.channels[0]._exp.GetMassSpectrum(0)
                except Exception as exc:
                    self._problem = scan_problem(self._wiff.path, exc)
        return self._problem

    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        """TIC of the whole sample (sum over all experiments)."""
        if self._tic is None:
            c = self._ms.GetTotalIonChromatogram()
            self._tic = (_to_numpy(c.GetActualXValues()),
                         _to_numpy(c.GetActualYValues()))
        return self._tic

    @property
    def acquisition_time(self) -> str:
        try:
            return str(self._sample.Details.AcquisitionDateTime.ToString("s"))
        except Exception:
            return ""

    def metadata(self) -> dict[str, str]:
        """Sample and acquisition information, for the details panel."""
        details = self._sample.Details
        wanted = [
            ("Sample", "SampleName"),
            ("ID", "SampleID"),
            ("Type", "SampleType"),
            ("Acquired", None),
            ("Instrument", "InstrumentName"),
            ("Serial number", "InstrumentSerialNumber"),
            ("Method", "AcquisitionMethodName"),
            ("Batch", "BatchName"),
            ("Rack", "Rack"),
            ("Plate", "Plate"),
            ("Vial", "Vial"),
            ("Injection volume", "InjectionVolume"),
            ("Dilution factor", "DilutionFactor"),
            ("Operator", "UserName"),
            ("Software", "SoftwareVersion"),
            ("Comment", "SampleComment"),
        ]
        out: dict[str, str] = {}
        for label, attr in wanted:
            if attr is None:
                out[label] = self.acquisition_time
                continue
            try:
                value = getattr(details, attr)
            except Exception:
                continue
            text = "" if value is None else str(value)
            if text:
                out[label] = text
        out["Channels"] = str(len(self.channels))
        rt = self.tic()[0]
        if rt.size:
            out["Time range"] = f"{rt[0]:.2f} – {rt[-1]:.2f} min"
        return out

    def __repr__(self) -> str:
        return f"<Sample {self.name}: {len(self.channels)} channels>"


# --------------------------------------------------------------------------- #
class WiffFile:
    """A .wiff file (with its matching .wiff.scan alongside)."""

    def __init__(self, path: str | os.PathLike):
        api = _api()
        self.path = os.path.realpath(str(path))
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        # ReadOnlyShared is essential: on the managed path (OpenMcdf) the
        # default mode takes an exclusive lock, which stops a second window —
        # or Analyst itself — from opening the same .wiff.
        self._provider = api["Provider"](api["OpenFileMode"].ReadOnlyShared)
        self._batch = api["Factory"].CreateBatch(self.path, self._provider)
        self.sample_names = [str(n) for n in self._batch.GetSampleNames()]
        self._samples: dict[int, Sample] = {}

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def sample(self, index: int = 0) -> Sample:
        if index not in self._samples:
            self._samples[index] = Sample(self, index)
        return self._samples[index]

    def close(self) -> None:
        try:
            self._provider.Close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"<WiffFile {self.filename}: {self.sample_names}>"
