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
#: what a channel is, in the words of the suite's command-line contract
#: (`docs/CLI-CONTRACT.md`). "" on a `ChannelInfo` built by hand means "not
#: said", and the channel is then judged by its precursor as it always was.
KIND_MS1 = "ms1"
KIND_IDA_SLOT = "ida-slot"          # one SCIEX IDA dependent experiment
KIND_DDA_EVENTS = "dda-events"      # every data-dependent MS2 of an mzML
KIND_SWATH = "swath"                # one isolation window
KIND_MRM = "mrm"
KIND_PRODUCT = "product"            # a fixed precursor's product-ion scan
KIND_OTHER = "other"
#: the kinds whose precursor is a property of each scan, not of the channel
PER_SCAN_KINDS = (KIND_IDA_SLOT, KIND_DDA_EVENTS)


@dataclass(frozen=True)
class ScanDetails:
    """
    What each scan of a channel isolated, one entry per scan, aligned with
    the channel's `rt`.

    `parent_mz` is the precursor **actually isolated for that scan**. For a
    SCIEX IDA dependent experiment it is `MassSpectrumInfo.ParentMZ`, which
    changes almost every cycle; the experiment's `FixedMasses` is a
    placeholder the method was written with and is never used for one. A
    scan that isolated nothing — the survey, or a dependent slot the cycle
    did not trigger — has NaN, never zero. `isolation` is the full width of
    the isolation window in Da, NaN where the file does not say;
    `collision_energy` NaN likewise; `charge` 0 where not stated.
    """

    parent_mz: np.ndarray
    isolation: np.ndarray
    collision_energy: np.ndarray
    charge: np.ndarray

    @property
    def triggered(self) -> np.ndarray:
        """Which scans isolated a precursor."""
        return np.isfinite(self.parent_mz)

    @classmethod
    def constant(cls, n: int, parent: float | None, isolation: float | None,
                 collision_energy: float | None) -> "ScanDetails":
        """A channel whose every scan isolated the same thing."""
        def filled(value):
            return np.full(n, np.nan if value is None else float(value))
        return cls(filled(parent), filled(isolation), filled(collision_energy),
                   np.zeros(n, dtype=np.int64))


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
    #: one of the `KIND_*` names above; "" when whoever built this did not
    #: say. An IDA dependent slot and an mzML's data-dependent events carry
    #: **no** channel precursor (`precursor` is None) — theirs is per scan,
    #: in `Channel.scan_details()` — and are still not MS1.
    kind: str = ""
    #: whether the scans are stored as centroids already (an mzML's
    #: `centroid spectrum`, a `.wiff` scan's `CentroidMode`)
    centroided: bool = False

    @property
    def per_scan(self) -> bool:
        """Whether the precursor changes from scan to scan."""
        return self.kind in PER_SCAN_KINDS

    @property
    def is_ms1(self) -> bool:
        if self.kind == KIND_MS1:
            return True
        if self.per_scan:
            return False
        return self.precursor is None

    @property
    def label(self) -> str:
        if self.is_ms1:
            return f"{self.name}  ({self.start_mass:.0f}-{self.end_mass:.0f})"
        ce = f", CE {self.collision_energy:g}" if self.collision_energy else ""
        if self.precursor is None:
            what = self._per_scan_word()
            return f"{self.name}  {what}  ->  {self.start_mass:.0f}-{self.end_mass:.0f}{ce}"
        return f"{self.name}  {self.precursor:.2f}  ->  {self.start_mass:.0f}-{self.end_mass:.0f}{ce}"

    @property
    def short_label(self) -> str:
        if self.is_ms1:
            return self.name
        if self.precursor is None:
            return f"{self.name} {self._per_scan_word()}"
        return f"{self.name} {self.precursor:.2f}"

    def _per_scan_word(self) -> str:
        if self.kind == KIND_IDA_SLOT:
            return f"IDA slot {self.index}"
        if self.kind == KIND_DDA_EVENTS:
            return f"events ({self.n_scans})"
        return "no precursor"


# --------------------------------------------------------------------------- #
class Channel:
    """One experiment of the method: TOF MS, TOF PI (MRM-HR), MRM, and so on."""

    def __init__(self, sample: "Sample", index: int):
        self._sample = sample
        self._exp = sample._ms.GetMSExperiment(index)
        self.index = index
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self._scan_details: ScanDetails | None = None
        self._isolation: float | None = None
        self.info = self._read_info()

    # -- metadata ------------------------------------------------------------ #
    @staticmethod
    def _kind_of(details, precursor: float | None) -> str:
        """
        What the experiment is. `IDAType` first: a dependent experiment
        declares `FixedMasses` like any product-ion scan, and on the
        TripleTOF 5600 IDA acquisition they read 1.0, 2.0 … 8.0 — the
        slot's number, not a mass — and on MIL-X's ZenoTOF data 829.5 in all
        24 slots. Neither is anything that was isolated.
        """
        ida = str(getattr(details, "IDAType", "") or "")
        if ida in ("Dependent", "Confirmation"):
            return KIND_IDA_SLOT
        if bool(getattr(details, "IsSwath", False)):
            return KIND_SWATH
        experiment = str(getattr(details, "ExperimentType", "") or "")
        if experiment in ("MRM", "SIM"):
            return KIND_MRM
        if precursor is not None:
            return KIND_PRODUCT
        return KIND_MS1 if experiment == "MS" else KIND_OTHER

    def _read_info(self) -> ChannelInfo:
        d = self._exp.Details
        ranges = list(d.MassRangeInfo) if d.MassRangeInfo else []
        first = ranges[0] if ranges else None

        precursor = None
        if first is not None and hasattr(first, "FixedMasses"):
            fixed = list(first.FixedMasses or [])
            if fixed:
                precursor = float(fixed[0])
        if first is not None:
            try:
                width = float(getattr(first, "IsolationWindow", 0.0) or 0.0)
            except (TypeError, ValueError):
                width = 0.0
            self._isolation = width if width > 0 else None
        kind = self._kind_of(d, precursor)

        ce = None
        centroided = False
        try:
            centroided = bool(self._exp.GetMassSpectrumInfo(0).CentroidMode)
        except Exception:
            pass
        if kind == KIND_IDA_SLOT:
            # the placeholder is not a precursor, and cycle 0 is usually a
            # slot nothing triggered, whose collision energy reads 0: the
            # energy is the first triggered scan's
            precursor = None
            energies = self.scan_details().collision_energy
            energies = energies[np.isfinite(energies) & (energies != 0.0)]
            ce = float(energies[0]) if energies.size else None
        else:
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
            kind=kind,
            centroided=centroided,
        )

    def scan_details(self) -> ScanDetails:
        """
        What every scan isolated (see `ScanDetails`), read once and kept.

        For an IDA dependent slot this asks Clearcore2 for each cycle's
        `MassSpectrumInfo` — 13 ms for the 1,986 cycles of a TripleTOF 5600
        slot — and a cycle whose `ParentMZ` is not positive is a slot that
        was not triggered (no data points either: the two agreed on all
        1,986 cycles of the slot measured). Every other channel isolated one
        thing for the whole run and is not read scan by scan.
        """
        if self._scan_details is None:
            d = self._exp.Details
            n = int(d.NumberOfScans)
            info = getattr(self, "info", None)
            kind = info.kind if info is not None else self._kind_of(d, None)
            if kind != KIND_IDA_SLOT:
                self._scan_details = ScanDetails.constant(
                    n, info.precursor if info is not None else None,
                    None if info is None or info.is_ms1 else self._isolation,
                    info.collision_energy if info is not None else None)
            else:
                parent = np.full(n, np.nan)
                energy = np.full(n, np.nan)
                charge = np.zeros(n, dtype=np.int64)
                for cycle in range(n):
                    try:
                        spectrum_info = self._exp.GetMassSpectrumInfo(cycle)
                        if int(spectrum_info.MSLevel) < 2:
                            continue
                        value = float(spectrum_info.ParentMZ)
                    except Exception:
                        continue
                    if value <= 0:
                        continue            # a slot this cycle did not trigger
                    parent[cycle] = value
                    try:
                        energy[cycle] = float(spectrum_info.CollisionEnergy)
                        charge[cycle] = int(spectrum_info.ParentChargeState)
                    except Exception:
                        pass
                width = np.full(n, np.nan if self._isolation is None
                                else self._isolation)
                width[~np.isfinite(parent)] = np.nan
                self._scan_details = ScanDetails(parent, width, energy, charge)
        return self._scan_details

    def scan_precursors(self) -> np.ndarray:
        """`scan_details().parent_mz`: the precursor of every scan, NaN for none."""
        return self.scan_details().parent_mz

    def scan_points(self) -> np.ndarray:
        """
        How many data points each scan stored. One `GetMassSpectrum` per
        cycle (about 0.1 ms each, 1.8 s for an 18,000-scan IDA run), so the
        command line keeps the answer in its sidecar (`sidecar.points`).
        """
        out = np.zeros(int(self.info.n_scans), dtype=np.int64)
        for cycle in range(out.size):
            try:
                out[cycle] = int(self._exp.GetMassSpectrum(cycle).NumDataPoints)
            except Exception:
                out[cycle] = 0
        return out

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

    def vendor_centroids(self, scan: int | None = None,
                         rt_start: float | None = None,
                         rt_end: float | None = None
                         ) -> tuple[np.ndarray, np.ndarray] | None:
        """
        SCIEX's own centroids of one scan, or of the average over a time
        range: `MSExperiment.GetPeakArray(cycle)` or `(rt_start, rt_end)`,
        each peak's fitted apex (`apexX`, `apexY`), sorted by mass.

        The spectral peak finder Analyst and the closed MS-DIAL reader use,
        and what MIL-X centroids `.wiff` with. None where it cannot run or
        finds nothing — an MRM or SIM experiment is not a spectrum to centroid
        — and the caller then centroids locally (`centroiding`).
        """
        if self.info.kind == KIND_MRM:
            return None
        try:
            if scan is not None:
                index = int(np.clip(scan, 0, max(self.info.n_scans - 1, 0)))
                peaks = self._exp.GetPeakArray(index)
            elif rt_start is not None and rt_end is not None:
                lo, hi = sorted((float(rt_start), float(rt_end)))
                peaks = self._exp.GetPeakArray(lo, hi)
            else:
                return None
        except Exception:
            return None
        if peaks is None or len(peaks) == 0:
            return None
        n = len(peaks)
        mz = np.fromiter((float(p.apexX) for p in peaks), dtype=float, count=n)
        height = np.fromiter((float(p.apexY) for p in peaks), dtype=float, count=n)
        keep = (mz > 0) & (height > 0)
        order = np.argsort(mz[keep], kind="stable")
        return mz[keep][order], height[keep][order]

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
