"""
The Python surface: the ten-line script, without the window.

Everything the application does is in modules that can be imported — that is
how the tests reach them — but a module surface is not an API. `session.py`
is a `QObject`, `quantify.process` wants a list of `SampleEntry` and a
`ProcessingMethod` built by hand, and the report renders through Qt. A
colleague who wants "open this project, reprocess it, give me the numbers"
should not have to know any of that.

This module is that promise, and it is the only one made:

**What is stable.** The names in `__all__`, the functions and methods on
them, and their **keyword names**. A keyword that exists here will keep
existing and keep meaning what it means; new ones are added with defaults
that preserve today's answers. The dataclasses returned keep their field
names, and gain fields rather than losing them. `VERSION` is bumped when
that promise is broken, which is the only time it will be.

**What is not.** Everything underneath. `milq.quantify`,
`milq.session`, `milq.report` and the readers are internals: they
are free to move, and code that calls them is code that will break. Field
*values* are not promised either — a better peak detector gives different
areas, and that is the point of it. The escape hatch is deliberate and
documented: `Batch.session`, `Acquisition.sample` and `Acquisition.file`
hand back the objects underneath for anyone who needs more than this. Using
them is opting out of the promise above.

Nothing here takes or returns a Qt object except `headless`, and nothing
here needs a window. What is returned is plain dataclasses, numpy arrays,
and lists of them.

    from milq import api

    with api.open("run.wiff") as run:
        spectrum = run.infusion_average()
        print(api.explain(spectrum, name=run.compound).share)

The report and the infusion document are drawn by Qt, so a script that
writes one needs a `QApplication`. `headless()` makes the offscreen one,
once; the calls that render use it themselves, so a plain script works and a
script that also wants Qt for something of its own can hold it open.
"""

from __future__ import annotations

import io
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np

#: the version of *this surface*, not of the application. Bumped only when
#: something documented above stops being true — a function removed, a
#: keyword renamed, a field dropped from a returned dataclass.
VERSION = 1

__all__ = [
    "VERSION",
    "Acquisition", "Annotation", "Batch", "Channel", "Chromatogram", "Curve",
    "Fragment", "InfusionDocument", "InfusionLine", "Library", "Match",
    "Result", "Results", "Spectrum", "Table",
    "explain", "headless", "infusion_report", "open",
]


# --------------------------------------------------------------------------- #
# a Qt application, for the calls that render
# --------------------------------------------------------------------------- #
#: the offscreen application, once made. Held here because Qt allows exactly
#: one per process and destroying it is not something to do between two
#: exports in the same script.
_APPLICATION = None


def offscreen_fonts() -> None:
    """
    Give Qt's offscreen platform the system's fonts on Windows.

    On macOS and Linux the offscreen platform reads the same font
    directories the desktop does. On Windows it reads none — `QFontDatabase`
    comes up with zero families — and every glyph is drawn as a box:
    measured on Windows 11, a batch report written through `Batch.report`
    was 47 pages of black rectangles with no text to extract, and the test
    that reads greyscale off a printed comparison failed for the same
    reason. `QT_QPA_FONTDIR` is how the platform is told where to look;
    this points it at the system's directory when nothing else has, and
    only where the offscreen platform is the one in force. Called by
    everything that makes an offscreen application, before it is made.
    """
    import sys

    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        return
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if os.path.isdir(fonts):
        os.environ.setdefault("QT_QPA_FONTDIR", fonts)


@contextmanager
def headless():
    """
    An offscreen `QApplication`, made once and shared.

    The report and the infusion document are laid out by Qt, which needs an
    application object even with nothing on screen. This makes one on the
    offscreen platform — no display required, so it works over ssh and in
    CI — and yields it. Entering it again yields the same one, so it is safe
    to nest and to call in a loop; it never tears the application down,
    because a second `QApplication` in one process is not allowed.

    The calls that render enter it themselves, so an ordinary script does
    not have to. Use it directly to hold one application open across many
    exports, or when the script wants Qt for something of its own:

        with api.headless():
            batch.report("report.pdf")
            api.infusion_report(folder, "infusions.pdf")
    """
    global _APPLICATION
    from PyQt6 import QtWidgets

    existing = QtWidgets.QApplication.instance()
    if existing is None:
        # only when we are the ones making it: a caller who set up their own
        # display has said what they want
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        offscreen_fonts()
        _APPLICATION = QtWidgets.QApplication(["milq"])
    else:
        _APPLICATION = existing
    yield _APPLICATION


# --------------------------------------------------------------------------- #
# what comes back
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, eq=False)
class Chromatogram:
    """A trace against time: two numpy arrays of the same length."""

    rt: np.ndarray
    intensity: np.ndarray
    label: str = ""

    def __len__(self) -> int:
        return int(self.rt.size)

    @property
    def apex(self) -> tuple[float, float] | None:
        """The tallest point, as `(rt, intensity)`; None for an empty trace."""
        if not self.intensity.size:
            return None
        index = int(np.argmax(self.intensity))
        return float(self.rt[index]), float(self.intensity[index])

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        return self.rt, self.intensity


@dataclass(frozen=True, eq=False)
class Spectrum:
    """
    A spectrum: two numpy arrays, and what the file says about them.

    `precursor`, `polarity` and `collision_energy` are the channel's, as the
    method wrote them — carried along because every other call here wants
    them and asking the caller to fetch them twice is how they come to
    disagree.
    """

    mz: np.ndarray
    intensity: np.ndarray
    label: str = ""
    #: the time range averaged over, when it is an average
    rt_range: tuple[float, float] | None = None
    precursor: float | None = None
    polarity: str = ""
    collision_energy: float | None = None
    scans: int = 0
    #: whether these are already one stick per ion. A spectrum straight off
    #: a reader is a profile — tens of points across every ion — and
    #: everything here that wants ions rather than points centroids it
    #: first, which is why the flag travels with the arrays
    centroided: bool = False

    def __len__(self) -> int:
        return int(self.mz.size)

    @property
    def base_peak(self) -> tuple[float, float] | None:
        if not self.intensity.size:
            return None
        index = int(np.argmax(self.intensity))
        return float(self.mz[index]), float(self.intensity[index])

    def centroid(self) -> "Spectrum":
        """
        The same spectrum as one stick per ion, at the intensity-weighted
        centre of each profile peak.

        Already centroided, it is returned unchanged: centroiding sticks
        averages a stick with its neighbours and moves the mass.
        """
        if self.centroided:
            return self
        from dataclasses import replace
        from .processing import centroid_spectrum

        mz, intensity = centroid_spectrum(self.mz, self.intensity)
        return replace(self, mz=mz, intensity=intensity, centroided=True)

    def peaks(self, min_relative: float = 0.01, limit: int = 60,
              centroid=None) -> list[tuple[float, float]]:
        """
        The peaks worth looking at, as `(mz, intensity)`, strongest first.

        `min_relative` is a share of the base peak: the baseline of a
        product scan is thousands of points and none of them mean anything.
        The mass of each is the centre of mass of its profile peak unless
        the spectrum is already centroided — `centroid` overrides that
        judgement either way.
        """
        from .processing import pick_peaks

        return pick_peaks(self.mz, self.intensity, max_peaks=int(limit),
                          min_relative=float(min_relative),
                          centroid=(not self.centroided if centroid is None
                                    else bool(centroid)),
                          min_distance=0.005)

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        return self.mz, self.intensity


@dataclass(frozen=True, eq=False)
class Channel:
    """
    One experiment of the acquisition method, and the traces it holds.

    `reader` is the reader's own channel object — the escape hatch, not part
    of the promise.
    """

    index: int
    name: str
    label: str
    polarity: str
    precursor: float | None
    collision_energy: float | None
    start_mass: float
    end_mass: float
    n_scans: int
    is_ms1: bool
    reader: object = field(default=None, repr=False, compare=False)

    def tic(self) -> Chromatogram:
        """This channel's total ion chromatogram."""
        rt, y = self.reader.tic()
        return Chromatogram(np.asarray(rt, dtype=float),
                            np.asarray(y, dtype=float), self.label)

    def xic(self, mz: float, tolerance: float = 0.02,
            unit: str = "Da") -> Chromatogram:
        """
        An extracted ion chromatogram over a window around `mz`.

        The vendor does the summing — see the manual on why the same window
        gives a slightly different area from a `.wiff` and from its mzML.
        """
        rt, y = self.reader.xic(float(mz), tolerance, unit)
        return Chromatogram(np.asarray(rt, dtype=float),
                            np.asarray(y, dtype=float), f"{mz:g} ± {tolerance:g}")

    def xic_range(self, mz_low: float, mz_high: float) -> Chromatogram:
        """An extracted ion chromatogram over an explicit mass window."""
        rt, y = self.reader.xic_range(float(mz_low), float(mz_high))
        return Chromatogram(np.asarray(rt, dtype=float),
                            np.asarray(y, dtype=float),
                            f"{mz_low:g}–{mz_high:g}")

    def spectrum(self, scan: int, add_zeros: bool = True) -> Spectrum:
        """One scan, by its index. `add_zeros` restores a profile's zeros."""
        mz, y = self.reader.spectrum(int(scan), add_zeros)
        return self._spectrum(mz, y, f"{self.label} · scan {int(scan)}", None)

    def average(self, rt0: float, rt1: float,
                add_zeros: bool = True) -> Spectrum:
        """The scans between two retention times, averaged into one spectrum."""
        window = (float(min(rt0, rt1)), float(max(rt0, rt1)))
        mz, y = self.reader.spectrum_rt_range(window[0], window[1], add_zeros)
        return self._spectrum(mz, y,
                              f"{self.label} · {window[0]:.2f}–{window[1]:.2f} min",
                              window)

    def scan_at(self, rt: float) -> int:
        """The scan nearest a retention time."""
        return int(self.reader.scan_at_rt(float(rt)))

    def rt_at(self, scan: int) -> float:
        """The retention time of a scan."""
        return float(self.reader.rt_at_scan(int(scan)))

    def _spectrum(self, mz, intensity, label: str,
                  window: tuple[float, float] | None) -> Spectrum:
        return Spectrum(np.asarray(mz, dtype=float),
                        np.asarray(intensity, dtype=float),
                        label=label, rt_range=window,
                        precursor=self.precursor, polarity=self.polarity,
                        collision_energy=self.collision_energy,
                        scans=self.n_scans)


def _channel(reader) -> Channel:
    """One of the reader's channels, as the plain thing above."""
    info = reader.info
    return Channel(
        index=int(getattr(info, "index", getattr(reader, "index", 0))),
        name=str(getattr(info, "name", "") or ""),
        label=str(getattr(info, "label", "") or ""),
        polarity=str(getattr(info, "polarity", "") or ""),
        precursor=(None if getattr(info, "precursor", None) is None
                   else float(info.precursor)),
        collision_energy=(None if getattr(info, "collision_energy", None) is None
                          else float(info.collision_energy)),
        start_mass=float(getattr(info, "start_mass", 0.0) or 0.0),
        end_mass=float(getattr(info, "end_mass", 0.0) or 0.0),
        n_scans=int(getattr(info, "n_scans", 0) or 0),
        is_ms1=bool(getattr(info, "is_ms1", False)),
        reader=reader,
    )


# --------------------------------------------------------------------------- #
# one acquisition
# --------------------------------------------------------------------------- #
@dataclass(eq=False)
class Acquisition:
    """
    One sample of one raw file, whichever format it is.

    Made by `api.open`. `file` and `sample` are the reader's own objects —
    the escape hatch, not part of the promise. Usable as a context manager,
    which closes the file on the way out.
    """

    path: str
    #: how the application names this injection: the file's own stem, since
    #: that is where the compound is written and a SCIEX sample is usually
    #: called `sample`. A file of several appends the instrument's own name
    name: str
    instrument: str = ""
    #: the name the instrument wrote, whatever it was
    sample_name: str = ""
    sample_index: int = 0
    file: object = field(default=None, repr=False, compare=False)
    sample: object = field(default=None, repr=False, compare=False)
    #: why the spectra cannot be read, when they cannot — a `.wiff` whose
    #: `.wiff.scan` is not beside it opens and lists its channels anyway
    problem: str = ""
    _channels: object = field(default=None, repr=False, compare=False)
    _entry: object = field(default=None, repr=False, compare=False)
    _verdict: object = field(default=None, repr=False, compare=False)

    # -- what is in the file -------------------------------------------- #
    @property
    def samples(self) -> list["Acquisition"]:
        """Every sample of the file this one came from, this one included."""
        names = list(getattr(self.file, "sample_names", []) or [])
        if not names:
            return [self]
        return [self if index == self.sample_index
                else _acquisition(self.file, index)
                for index in range(len(names))]

    @property
    def compound(self) -> str:
        """
        What was infused, by the name of the file: the part before the first
        underscore or space, which is how these acquisitions are named.

        The same rule the infusion document groups by, so a script and a
        document call the same run the same thing.
        """
        from .infusion_report import compound_of

        return compound_of(self.name)

    @property
    def channels(self) -> list[Channel]:
        """The experiments of the acquisition method, in the method's order."""
        if self._channels is None:
            self._channels = [_channel(c)
                              for c in getattr(self.sample, "channels", [])]
        return list(self._channels)

    def channel(self, index: int = 0) -> Channel:
        """One channel by its index."""
        return self.channels[int(index)]

    # -- traces ---------------------------------------------------------- #
    def tic(self) -> Chromatogram:
        """
        The sample's total ion chromatogram, as the instrument reports it.

        Summed by the vendor over the whole method rather than by adding the
        channels here — see the manual: the union of the channels' times is
        one point per spectrum, which on a scheduled method is forty times
        as many points as the instrument's own total.
        """
        rt, y = self.sample.tic()
        return Chromatogram(np.asarray(rt, dtype=float),
                            np.asarray(y, dtype=float), self.name)

    def spectrum(self, scan: int, channel: int = 0,
                 add_zeros: bool = True) -> Spectrum:
        """One scan of one channel."""
        return self.channel(channel).spectrum(scan, add_zeros)

    def average(self, rt0: float, rt1: float, channel: int = 0,
                add_zeros: bool = True) -> Spectrum:
        """The scans between two retention times of one channel, averaged."""
        return self.channel(channel).average(rt0, rt1, add_zeros)

    def xic(self, mz: float, tolerance: float = 0.02, channel: int = 0,
            unit: str = "Da") -> Chromatogram:
        """An extracted ion chromatogram from one channel."""
        return self.channel(channel).xic(mz, tolerance, unit)

    # -- infusions -------------------------------------------------------- #
    @property
    def is_infusion(self) -> bool:
        """
        Whether this reads as a direct infusion rather than a run down a
        column — measured from the shape of the total ion chromatogram, and
        `False` whenever it cannot be decided.
        """
        return bool(self._infusion_verdict())

    @property
    def infusion_reason(self) -> str:
        """The sentence behind `is_infusion`, either way."""
        verdict = self._infusion_verdict()
        return str(getattr(verdict, "reason", "") or "")

    def infusion_channel(self) -> Channel | None:
        """
        The channel an infusion should be read from: the product-ion channel
        carrying the most signal, or the survey where there is no product
        scan. None when the sample has no channels at all.
        """
        from .infusion import strongest_channel

        found = strongest_channel(self.sample)
        return None if found is None else _channel(found)

    def infusion_average(self) -> Spectrum | None:
        """
        The infusion channel averaged into one spectrum — the view the
        Explorer opens an infusion on. None when there is nothing to average.

        The scans the spray faltered on are left out, which is what makes
        this the Explorer's view rather than merely the whole run: this used
        to average `run_range` end to end, so on the three of the nine real
        bile-acid infusions whose spray bursts it disagreed with the
        Explorer, with the [[infusion-report]] and with `infusion_report`
        below — by 2.9% of the base peak on the worst of them. Worse, it
        disagreed with itself: `infusion_report` explained and searched
        *this* spectrum and then printed the masked one beside the figures.
        `Spectrum.scans` is how many went into it, so a script can say what
        it read.

        A run that is not an infusion has no mask worth applying — a
        chromatographic peak departs from its neighbours further than any
        spray does — so `average` over the whole range is what to call
        there, and `is_infusion` is the gate.
        """
        channel = self.infusion_channel()
        if channel is None:
            return None
        from .infusion import average_stable, mask_for, run_range

        window = run_range(channel.reader)
        if window is None:
            return None
        mask = mask_for(self.sample, channel.reader)
        mz, intensity = average_stable(channel.reader, mask)
        if not len(mz):
            return None
        label = (f"{channel.label} · {window[0]:.2f}–{window[1]:.2f} min"
                 + (f" · {mask.kept:,} of {mask.n_scans:,} scans"
                    if mask.excluded else ""))
        return Spectrum(
            np.asarray(mz, dtype=float), np.asarray(intensity, dtype=float),
            label=label, rt_range=window, precursor=channel.precursor,
            polarity=channel.polarity,
            collision_energy=channel.collision_energy,
            scans=(mask.kept if mask.n_scans else channel.n_scans))

    def _infusion_verdict(self):
        if self._verdict is None:
            from .infusion import verdict_for

            try:
                self._verdict = verdict_for(self.sample)
            except Exception:                     # a reader that cannot say
                self._verdict = False
        return self._verdict

    # -- the rest --------------------------------------------------------- #
    def metadata(self) -> dict[str, str]:
        """What the file records about the injection, as strings."""
        try:
            return dict(self.sample.metadata())
        except Exception:
            return {}

    def entry(self):
        """
        This sample as the `SampleEntry` the internals pass around.

        Here because the escape hatch needs it — `quantify.integrate_component`
        and `precursor.measure` both take one. Not part of the promise.
        """
        if self._entry is None:
            from .samples import SampleEntry

            self._entry = SampleEntry(
                path=self.path, sample_index=self.sample_index,
                name=self.name, sample=self.sample, problem=self.problem)
        return self._entry

    def close(self) -> None:
        """Close the file. Every sample of it goes with it."""
        try:
            self.file.close()
        except Exception:
            pass

    def __enter__(self) -> "Acquisition":
        return self

    def __exit__(self, *_exception) -> None:
        self.close()


def _acquisition(handle, index: int) -> Acquisition:
    sample = handle.sample(index)
    path = str(getattr(handle, "path", ""))
    written = str(getattr(sample, "name", "") or "")
    # the file's own stem, as the application names an injection: a SCIEX
    # sample is called `sample` more often than it is called anything, and
    # the compound is in the file name. A file holding several keeps them
    # apart by the name the instrument did write.
    stem = os.path.splitext(os.path.basename(path))[0]
    several = len(getattr(handle, "sample_names", []) or []) > 1
    name = f"{stem} · {written or index + 1}" if several else (stem or written)
    return Acquisition(
        path=path, name=name, sample_name=written,
        instrument=str(getattr(sample, "instrument", "") or ""),
        sample_index=int(index), file=handle, sample=sample,
        problem=str(getattr(sample, "problem", "") or ""),
    )


def open(path, sample: int = 0) -> Acquisition:      # noqa: A001
    """
    Open a raw file — `.wiff` or `.mzML` — and return one of its samples.

    A `.wiff` may hold several injections; `sample` picks one and
    `Acquisition.samples` lists them all. The format is chosen by the
    extension and nothing above this call knows which reader answered.

        with api.open("batch.wiff", sample=3) as run:
            rt, y = run.tic().arrays()
    """
    from .raw import open_raw

    return _acquisition(open_raw(os.fspath(path)), int(sample))


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Result:
    """One integrated peak: one component measured in one sample."""

    sample: str
    component: str
    group: str = ""
    channel: str = ""
    mz: float = 0.0
    rt: float = 0.0
    expected_rt: float | None = None
    area: float = 0.0
    height: float = 0.0
    width: float = 0.0
    #: None when the baseline could not be measured, which is the ordinary
    #: case on a scheduled MRM channel — see the manual on signal to noise
    snr: float | None = None
    start_rt: float = 0.0
    end_rt: float = 0.0
    #: points on the peak. One is what a scheduled method usually gives
    points: int | None = None
    algorithm: str = ""
    internal_standard: str = ""
    #: the standard's own area in this injection, and this row's ratio to it
    is_area: float | None = None
    area_ratio: float | None = None
    concentration: float | None = None
    actual_concentration: float | None = None
    accuracy: float | None = None
    ion_ratio: float | None = None
    status: str = ""
    flags: tuple[str, ...] = ()
    note: str = ""
    manual: bool = False
    used: bool = True

    @property
    def found(self) -> bool:
        return self.area > 0.0


#: the columns of `Results.table`, and the fields they are read from
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Sample", "sample"), ("Component", "component"), ("Group", "group"),
    ("Channel", "channel"), ("m/z", "mz"), ("RT", "rt"),
    ("Expected RT", "expected_rt"), ("Area", "area"), ("Height", "height"),
    ("Width", "width"), ("S/N", "snr"), ("Points", "points"),
    ("Algorithm", "algorithm"), ("Internal standard", "internal_standard"),
    ("IS area", "is_area"), ("Area ratio", "area_ratio"), ("Concentration", "concentration"),
    ("Accuracy %", "accuracy"), ("Ion ratio %", "ion_ratio"),
    ("Status", "status"), ("Flags", "flags"), ("Note", "note"),
)


@dataclass(frozen=True)
class Table:
    """
    A table with no dependencies: column names, and rows of plain values.

    What a spreadsheet, a CSV writer or a DataFrame constructor all take —
    `pandas.DataFrame(table.rows, columns=table.columns)` — without this
    module depending on any of them.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple, ...]

    def __len__(self) -> int:
        return len(self.rows)

    def to_csv(self, path) -> str:
        """Write the table as a CSV and return the path written."""
        import csv

        path = os.fspath(path)
        with io.open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.columns)
            writer.writerows(self.rows)
        return path


@dataclass(frozen=True)
class Results:
    """Every row of one processing run."""

    rows: tuple[Result, ...] = ()

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, index):
        return self.rows[index]

    @property
    def found(self) -> "Results":
        """Only the rows that got a peak."""
        return Results(tuple(r for r in self.rows if r.found))

    def for_component(self, name: str) -> "Results":
        return Results(tuple(r for r in self.rows if r.component == name))

    def for_sample(self, name: str) -> "Results":
        return Results(tuple(r for r in self.rows if r.sample == name))

    def dicts(self) -> list[dict]:
        """The rows as dictionaries, one key per field."""
        from dataclasses import asdict

        out = []
        for row in self.rows:
            data = asdict(row)
            data["flags"] = list(row.flags)
            data["found"] = row.found
            out.append(data)
        return out

    def table(self) -> Table:
        """The rows as a table of plain values — see `Table`."""
        columns = tuple(name for name, _field in _COLUMNS)
        rows = []
        for row in self.rows:
            values = []
            for _name, attribute in _COLUMNS:
                value = getattr(row, attribute, None)
                values.append("; ".join(value) if attribute == "flags"
                              else value)
            rows.append(tuple(values))
        return Table(columns, tuple(rows))


def _result(row) -> Result:
    """One of `quantify`'s rows, read defensively."""
    def value(name, default=None):
        return getattr(row, name, default)

    return Result(
        sample=str(value("sample_name", "") or ""),
        component=str(value("component", "") or ""),
        group=str(value("group", "") or ""),
        channel=str(value("channel", "") or ""),
        mz=float(value("mz", 0.0) or 0.0),
        rt=float(value("rt", 0.0) or 0.0),
        expected_rt=value("expected_rt"),
        area=float(value("area", 0.0) or 0.0),
        height=float(value("height", 0.0) or 0.0),
        width=float(value("width", 0.0) or 0.0),
        snr=value("snr"),
        start_rt=float(value("start_rt", 0.0) or 0.0),
        end_rt=float(value("end_rt", 0.0) or 0.0),
        points=value("points"),
        algorithm=str(value("algorithm", "") or ""),
        internal_standard=str(value("internal_standard", "") or ""),
        is_area=value("is_area"),
        area_ratio=value("area_ratio"),
        concentration=value("calculated_concentration"),
        actual_concentration=value("actual_concentration"),
        accuracy=value("accuracy"),
        ion_ratio=value("ion_ratio"),
        status=str(value("status", "") or ""),
        flags=tuple(str(f) for f in (value("flags", ()) or ())),
        note=str(value("note", "") or ""),
        manual=bool(value("manual", False)),
        used=bool(value("used", True)),
    )


@dataclass(frozen=True)
class Curve:
    """One component's calibration curve."""

    component: str
    regression: str = ""
    weighting: str = ""
    #: highest order first, as `numpy.polyval` takes them
    coefficients: tuple[float, ...] = ()
    r2: float = 0.0
    equation: str = ""
    points: int = 0
    used: int = 0
    fitted: bool = False
    note: str = ""

    def concentration_at(self, response: float) -> float | None:
        """Read a concentration off the curve; None outside it."""
        if not self.fitted:
            return None
        coefficients = list(self.coefficients)
        if len(coefficients) == 1:
            return None if not coefficients[0] else float(response / coefficients[0])
        if len(coefficients) == 2:
            slope, intercept = coefficients
            return None if not slope else float((response - intercept) / slope)
        roots = np.roots([coefficients[0], coefficients[1],
                          coefficients[2] - response])
        real = [float(r.real) for r in roots if abs(r.imag) < 1e-9]
        return min(real, key=abs) if real else None


def _curve(name: str, fitted) -> Curve:
    return Curve(
        component=str(getattr(fitted, "component", name) or name),
        regression=str(getattr(fitted, "regression", "") or ""),
        weighting=str(getattr(fitted, "weighting", "") or ""),
        coefficients=tuple(float(c) for c in
                           (getattr(fitted, "coefficients", ()) or ())),
        r2=float(getattr(fitted, "r2", 0.0) or 0.0),
        equation=str(getattr(fitted, "equation", "") or ""),
        points=len(getattr(fitted, "points", ()) or ()),
        used=len(getattr(fitted, "used_points", ()) or ()),
        fitted=bool(getattr(fitted, "is_fitted", False)),
        note=str(getattr(fitted, "note", "") or ""),
    )


# --------------------------------------------------------------------------- #
# a batch
# --------------------------------------------------------------------------- #
class Batch:
    """
    A batch of samples and the method that measures them.

    Either loaded from a project — everything the application saved, the
    method, the sample types, the concentrations and the rows already
    integrated —

        batch = api.Batch.from_project("study.oqproj")

    or built from raw files and a component table:

        batch = api.Batch(["a.wiff", "b.wiff"], components_csv="method.csv")

    `session` is the object underneath: the escape hatch, not part of the
    promise.
    """

    def __init__(self, files=(), components_csv=None):
        from .session import Session

        self.session = Session()
        #: the raw files a project named that could not be reopened
        self.missing: tuple[str, ...] = ()
        #: the project this came from, when it came from one
        self.project: str = ""
        for path in files or ():
            self.session.open_file(os.fspath(path))
        if components_csv is not None:
            self.load_components(components_csv)

    # -- making one -------------------------------------------------------- #
    @classmethod
    def from_project(cls, path) -> "Batch":
        """
        Open a saved project — `.oqproj` — with its raw files.

        Raw files that have moved are not an error: they are listed in
        `missing`, and everything the project itself holds is still there.
        """
        batch = cls()
        missing = batch.session.load_project(os.fspath(path))
        batch.missing = tuple(missing or ())
        batch.project = os.fspath(path)
        return batch

    def load_components(self, path) -> int:
        """Read a component table from CSV and return how many were read."""
        from .components import load_components

        components = load_components(os.fspath(path))
        self.session.set_components(components)
        return len(components)

    def open_file(self, path) -> "Batch":
        """Add a raw file's samples to the batch."""
        self.session.open_file(os.fspath(path))
        return self

    # -- what is in it ----------------------------------------------------- #
    @property
    def samples(self) -> list[str]:
        """The names of the injections, in the order they were opened."""
        return [str(e.name) for e in self.session.entries]

    @property
    def components(self) -> list[str]:
        """The names of the components in the method."""
        return [str(c.name) for c in self.session.method.components]

    def acquisitions(self) -> list[Acquisition]:
        """The batch's samples as `Acquisition`s, for reading traces."""
        out = []
        for entry in self.session.entries:
            if not getattr(entry, "is_loaded", False):
                continue
            found = Acquisition(
                path=str(entry.path), name=str(entry.name),
                sample_name=str(getattr(entry.sample, "name", "") or ""),
                instrument=str(getattr(entry.sample, "instrument", "") or ""),
                sample_index=int(entry.sample_index),
                sample=entry.sample, problem=str(entry.problem or ""))
            found._entry = entry
            out.append(found)
        return out

    # -- running it -------------------------------------------------------- #
    def process(self, only=None, keep_manual: bool = True,
                progress=None) -> Results:
        """
        Run the method over every loaded sample and return the rows.

        `only` names the components to run, leaving the rest of an earlier
        run alone; `keep_manual` carries across any peak integrated by hand,
        so reprocessing does not silently undo it. `progress(done, total)` is
        called as it goes and stops the run by returning False.

        Ratios to the internal standards, ion ratios and the acceptance
        status are filled in afterwards, as the application fills them.
        """
        from .quantify import evaluate_acceptance, process as run

        session = self.session
        results = run(session.entries, session.method, session.cache,
                      progress=progress, previous=session.results,
                      keep_manual=keep_manual,
                      only=None if only is None else list(only),
                      corrections=session.corrections_in_force())
        evaluate_acceptance(results, session.entries, session.method)
        session.set_results(results)
        return self.results

    @property
    def results(self) -> Results:
        """The rows as they stand: from `process`, or from the project."""
        return Results(tuple(_result(row) for row in self.session.results))

    def calibrate(self, auto_outliers: bool = False,
                  tolerance: float = 15.0) -> dict[str, Curve]:
        """
        Fit a curve per component from the samples marked as standards, read
        the concentrations back onto every row, and return the curves.

        `auto_outliers` drops standards further than `tolerance` per cent
        from their own curve — off by default, because a point removed
        without being seen is a point nobody knows about.
        """
        from .quantify import apply_calibrations, build_calibrations

        session = self.session
        curves = build_calibrations(session.results, session.entries,
                                    session.method,
                                    auto_outliers=auto_outliers,
                                    tolerance=tolerance,
                                    previous=session.calibrations)
        apply_calibrations(session.results, session.entries, session.method,
                           curves)
        session.set_calibrations(curves)
        return {name: _curve(name, curve) for name, curve in curves.items()}

    @property
    def curves(self) -> dict[str, Curve]:
        """The curves as they stand, without refitting."""
        return {name: _curve(name, curve)
                for name, curve in self.session.calibrations.items()}

    def statistics(self, grouping: str = "sample type",
                   quantity: str = "response") -> Table:
        """
        Mean, standard deviation and %CV per component and group.

        `grouping` is `"concentration"`, `"sample type"`, `"sample group"` or
        `"sample"`; rows unticked in the application are counted in `n of`
        and left out of the arithmetic.
        """
        from .statistics import summarise

        rows = summarise(self.session.results, self.session.entries,
                         self.session.method, grouping=grouping,
                         quantity=quantity)
        columns = ("Component", "Group", "n", "n of", "Mean", "SD", "%CV")
        out = []
        for row in rows:
            out.append((str(getattr(row, "component", "")),
                        str(getattr(row, "group", "")),
                        int(getattr(row, "used", 0) or 0),
                        int(getattr(row, "total", 0) or 0),
                        getattr(row, "mean", None),
                        getattr(row, "standard_deviation", None),
                        getattr(row, "percent_cv", None)))
        return Table(columns, tuple(out))

    # -- writing it out ---------------------------------------------------- #
    def export_xlsx(self, path) -> str:
        """Write the batch as a spreadsheet and return the path written."""
        from .report import export_workbook

        return export_workbook(self.session, os.fspath(path))

    def report(self, path, title: str = "Batch report", **kwargs) -> str:
        """
        Write the batch report and return the path written.

        A `.pdf` is laid out on A4 pages, which is done by Qt: an offscreen
        application is made if the script has none. Any other suffix writes
        the HTML the PDF is printed from.
        """
        from . import report as _report

        path = os.fspath(path)
        if not path.lower().endswith(".pdf"):
            return _report.write_html(self.session, path, title=title, **kwargs)
        with headless():
            return _report.write_pdf(self.session, path, title=title, **kwargs)

    def save_project(self, path) -> str:
        """Save everything as a project the application can reopen."""
        path = os.fspath(path)
        self.session.save_project(path)
        return self.session.project_path or path

    def close(self) -> None:
        """Close every raw file the batch holds open."""
        self.session.close_all()

    def __enter__(self) -> "Batch":
        return self

    def __exit__(self, *_exception) -> None:
        self.close()

    def __repr__(self) -> str:
        return (f"<Batch {len(self.samples)} sample(s), "
                f"{len(self.components)} component(s), "
                f"{len(self.session.results)} row(s)>")


# --------------------------------------------------------------------------- #
# explaining a spectrum
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fragment:
    """One measured peak and the ion that lands on it."""

    mz: float
    intensity: float
    #: the predicted mass, and how far the measured one sits from it
    predicted: float
    error_ppm: float
    description: str


@dataclass(frozen=True)
class Annotation:
    """What a formula, a name or a drawing accounts for in a spectrum."""

    name: str = ""
    #: the formula the prediction was made from, with any labels the name
    #: declares written into it: `CA-d4` is `C24H36D4O5`, not `C24H40O5`
    formula: str = ""
    adduct: str = ""
    #: deuterium the name declares but does not place
    labels: int = 0
    #: the fraction of the spectrum's intensity accounted for, 0 to 1
    share: float = 0.0
    #: peaks explained, ions offered, and peaks there were to explain
    matched: int = 0
    predicted: int = 0
    considered: int = 0
    fragments: tuple[Fragment, ...] = ()
    unexplained: tuple[tuple[float, float], ...] = ()
    #: what the prediction was made from, in words — the sentence that says
    #: what the denominator of "n of m" counts
    basis: str = ""
    #: why there is nothing here, when there is nothing
    note: str = ""

    def __bool__(self) -> bool:
        return self.matched > 0


def _peaks_of(spectrum, limit: int, min_relative: float
              ) -> list[tuple[float, float]]:
    """
    A spectrum, a pair of arrays, or a list of peaks — as a list of peaks.

    A `Spectrum` is peak-picked, which centroids it unless it has already
    been centroided: a profile spectrum has tens of points across every ion
    and explaining those points as ions would count one fragment thirty
    times. A bare pair of arrays is thresholded and taken as given, since
    whoever built it knows what it holds.
    """
    from .explain import significant_peaks

    if isinstance(spectrum, Spectrum):
        return spectrum.peaks(min_relative=min_relative, limit=limit)
    mz = getattr(spectrum, "mz", None)
    intensity = getattr(spectrum, "intensity", None)
    if mz is not None and intensity is not None:
        return significant_peaks(mz, intensity, noise_share=min_relative,
                                 limit=limit)
    pair = list(spectrum)
    if len(pair) == 2 and np.ndim(pair[0]) == 1 and np.ndim(pair[1]) == 1:
        return significant_peaks(pair[0], pair[1], noise_share=min_relative,
                                 limit=limit)
    return [(float(a), float(b)) for a, b in pair]


def _labelled_formula(formula: str, labels: int) -> str:
    """
    The formula with the labels its name declares written into it.

    A d4 standard is bought and filed as `CA-d4` and the formula beside it
    is the unlabelled one; nothing in a component table has a column for
    four deuteriums. Without this the arithmetic is out by 4.025 Da and no
    adduct fits the precursor at all.
    """
    from .chemistry import FormulaError, format_formula, parse_formula

    if not labels:
        return formula
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return formula
    if counts.get("D") or counts.get("H", 0) < labels:
        return formula
    counts["D"] = labels
    counts["H"] -= labels
    return format_formula(counts)


def _adduct_for(formula: str, adduct, precursor, polarity) -> tuple[str, str]:
    """The adduct to predict with, and where it came from."""
    from .chemistry import identify_adduct

    if adduct:
        return str(adduct), "as given"
    if precursor:
        choice = identify_adduct(formula, float(precursor), polarity or None)
        if getattr(choice, "adduct", None) is not None:
            return choice.adduct.name, f"read off the precursor — {choice.reason}"
        return "", str(getattr(choice, "reason", "no adduct fits the precursor"))
    return ("[M-H]-" if str(polarity).lower().startswith("neg") else "[M+H]+",
            "assumed, since nothing said otherwise")


def _explanation(spectrum, formula=None, name=None, molfile=None, adduct=None,
                 deuterium=0, tolerance_ppm=None, limit=60,
                 min_relative=0.01):
    """
    The work behind `explain`, returning what the internals hold.

    Kept apart so that `infusion_report` can put the same `Explanation` into
    a document — the document draws it, and the API hands back the plain
    dataclass built from it.
    """
    from . import explain as _explain

    peaks = _peaks_of(spectrum, limit, min_relative)
    precursor = getattr(spectrum, "precursor", None)
    polarity = str(getattr(spectrum, "polarity", "") or "")
    tolerance = (_explain.TOLERANCE_PPM if tolerance_ppm is None
                 else float(tolerance_ppm))
    written = str(name or "")
    molecule, source, labels = None, "", int(deuterium)

    if molfile is not None:
        text = str(molfile)
        if "\n" not in text:
            with io.open(os.fspath(molfile), encoding="utf-8",
                         errors="replace") as handle:
                text = handle.read()
        molecule, drawn = _explain.read_molfile(text)
        if molecule is None:
            return None, Annotation(name=written, note="that molfile could "
                                                       "not be read")
        written = written or drawn
        formula = formula or molecule.formula
        source = "a drawing of your own"
    elif not formula and written:
        found = _explain.resolve_name(written)
        if found is None:
            return None, Annotation(name=written,
                                    note=f"nothing knows the name {written!r}")
        formula = found.formula
        molecule = found.molecule()
        if not deuterium:
            labels = int(found.labels)
        source = found.source
    if not formula:
        raise ValueError("explain needs a formula, a name or a molfile")

    # the formula the arithmetic is done with: a d4 standard is bought,
    # named and filed as `CA-d4` and the formula beside it is the unlabelled
    # one, so this is the one an adduct is fitted against and the one a
    # record of the spectrum should carry
    weighed = _labelled_formula(formula, labels)
    chosen, why = _adduct_for(weighed, adduct, precursor, polarity)
    if not chosen:
        return None, Annotation(name=written, formula=weighed, labels=labels,
                                note=why)
    if not peaks:
        return None, Annotation(name=written, formula=weighed, labels=labels,
                                adduct=chosen,
                                note="no peak above the noise share to explain")

    if molecule is not None:
        from .chemistry import adduct_from_name

        explanation = _explain.explain_structure(
            molecule, peaks, name=written,
            adduct=adduct_from_name(chosen), deuterium=labels,
            tolerance_ppm=tolerance)
        how = "its structure"
    else:
        if not _explain.formula_ions(formula, chosen):
            return None, Annotation(name=written, formula=weighed,
                                    labels=labels, adduct=chosen,
                                    note=f"{chosen} is not an adduct this "
                                         f"program knows")
        explanation = _explain.explain_formula(
            formula, chosen, peaks, name=written, deuterium=labels,
            tolerance_ppm=tolerance)
        how = "the formula alone"
    basis = (f"{weighed} as {chosen} ({why}), predicted from {how}"
             + (f", named from {source}" if source else ""))
    return explanation, _annotation(explanation, written, weighed, chosen,
                                    labels, basis, peaks)


def _annotation(explanation, name, formula, adduct, labels, basis,
                peaks) -> Annotation:
    fragments = tuple(
        Fragment(mz=float(match.mz), intensity=float(match.intensity),
                 predicted=float(getattr(match.ion, "mz", 0.0) or 0.0),
                 error_ppm=float(match.error_ppm),
                 description=str(match.best_route))
        for match in getattr(explanation, "matches", ()))
    unexplained = tuple((float(a), float(b))
                        for a, b in explanation.unexplained(peaks))
    return Annotation(
        name=name or str(getattr(explanation, "name", "") or ""),
        formula=formula, adduct=adduct, labels=int(labels),
        share=float(getattr(explanation, "share", 0.0) or 0.0),
        matched=int(getattr(explanation, "matched", 0) or 0),
        predicted=int(getattr(explanation, "predicted", 0) or 0),
        considered=int(getattr(explanation, "considered", 0) or 0),
        fragments=fragments, unexplained=unexplained, basis=basis)


def explain(spectrum, formula=None, name=None, molfile=None, adduct=None,
            deuterium: int = 0, tolerance_ppm=None, limit: int = 60,
            min_relative: float = 0.01) -> Annotation:
    """
    What a compound accounts for in a measured spectrum.

    `spectrum` is a `Spectrum`, a `(mz, intensity)` pair of arrays, or a
    list of `(mz, intensity)` peaks. What is being looked for is given one
    of three ways, in this order of precedence:

    * `molfile` — a path to a `.mol`/`.sdf`, or its text. Bonds are cut and
      the pieces are matched, which is the richest answer available.
    * `formula` — a formula alone has no bonds to cut, so what is predicted
      is the precursor as it was ionised and the neutral losses that form
      could shed.
    * `name` — resolved through the standards table, LIPID MAPS and the
      lipid shorthand, in that order. Where the name resolves to a drawing
      the fragments come with it; where it resolves to a formula only, the
      formula route is taken. A trailing `-d4` is read as four labels the
      name declares but does not place.

    `adduct` is written as `[M+H]+`, `[M-H]-`, `[M+NH4]+`. Left out, it is
    read off the spectrum's own precursor where it has one — an ammoniated
    channel explained as `[M+H]+` predicts every fragment 17 Da from
    anything measured — and otherwise assumed from the polarity.
    `deuterium` is labels the drawing or formula does not place; a name that
    declares them supplies it.

    An `Annotation` always comes back. When nothing could be predicted it
    says why in `note` rather than raising: a name nothing knows, an adduct
    that fits no precursor, a spectrum with no peak above the noise.

        said = api.explain(spectrum, name="TDCA-d4")
        print(f"{said.share:.0%} of the spectrum, {said.matched} "
              f"of {said.predicted} ions — {said.basis}")
    """
    _raw, annotation = _explanation(
        spectrum, formula=formula, name=name, molfile=molfile, adduct=adduct,
        deuterium=deuterium, tolerance_ppm=tolerance_ppm, limit=limit,
        min_relative=min_relative)
    return annotation


# --------------------------------------------------------------------------- #
# a spectral library
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Match:
    """One library record scored against a measured spectrum."""

    name: str
    #: cosine over everything both spectra hold, 0 to 1
    score: float
    #: cosine asking only whether the record's peaks are in the measurement,
    #: so an impurity beside the compound does not count against it
    reverse: float
    matched: int
    of_library: int
    of_query: int
    precursor: float | None = None
    adduct: str = ""
    formula: str = ""
    #: the queried precursor against the record's; None when neither the
    #: record nor the query gave one, so the filter could not apply
    delta_ppm: float | None = None
    #: which of the record's precursors that was measured against:
    #: "formula", "written", or "" when there was nothing to measure
    delta_basis: str = ""
    collision_energy: float | None = None
    source: str = ""


def _match(hit) -> Match:
    entry = hit.entry
    return Match(
        name=str(getattr(entry, "name", "") or ""),
        score=float(getattr(hit, "score", 0.0) or 0.0),
        reverse=float(getattr(hit, "reverse", 0.0) or 0.0),
        matched=int(getattr(hit, "matched", 0) or 0),
        of_library=int(getattr(hit, "of_library", 0) or 0),
        of_query=int(getattr(hit, "of_query", 0) or 0),
        precursor=getattr(entry, "precursor", None),
        adduct=str(getattr(entry, "precursor_type", "") or ""),
        formula=str(getattr(entry, "formula", "") or ""),
        delta_ppm=getattr(hit, "delta_ppm", None),
        delta_basis=str(getattr(hit, "delta_basis", "") or ""),
        collision_energy=_energy_of(entry),
        source=str(getattr(entry, "source", "") or ""),
    )


def _energy_of(entry) -> float | None:
    from .infusion_report import energy_of

    try:
        return energy_of(entry)
    except Exception:
        return None


class Library:
    """
    A spectral library: records read from an MSP or MGF, searched and added to.

        lib = api.Library.open("MassBank.msp")
        for hit in lib.search(spectrum, precursor=430.35)[:5]:
            print(f"{hit.score:.2f}  {hit.name}")

    `entries` is the list underneath — the escape hatch, not part of the
    promise.
    """

    def __init__(self, library=None, path: str = ""):
        from .library import SpectralLibrary

        self._library = library if library is not None else SpectralLibrary()
        self.path = str(path or getattr(self._library, "path", "") or "")

    # -- opening ---------------------------------------------------------- #
    @classmethod
    def open(cls, msp, create: bool = False) -> "Library":       # noqa: A003
        """
        Read a library from an `.msp` or `.mgf`.

        `create` allows a file that is not there yet, giving an empty
        library bound to that path — which is what a library of one's own
        starts as, one `add` at a time. Without it a missing file raises,
        so a mistyped path does not read as an empty library.
        """
        from .library import load_library

        path = os.fspath(msp)
        if create and not os.path.exists(path):
            return cls(None, path)
        return cls(load_library(path), path)

    @property
    def entries(self):
        """The records underneath. Not part of the promise."""
        return self._library.entries

    def __len__(self) -> int:
        return len(self._library)

    def __repr__(self) -> str:
        return f"<Library {os.path.basename(self.path) or 'unsaved'}: {len(self)} records>"

    # -- searching --------------------------------------------------------- #
    def search(self, spectrum, precursor=None, polarity=None, top: int = 20,
               tolerance_ppm=None, precursor_tolerance=None,
               min_matched=None, include_unknown_precursor: bool = False,
               include_other_polarity: bool = False,
               min_relative: float = 0.01) -> list[Match]:
        """
        The records that best match a measured spectrum, best first.

        `spectrum` is a `Spectrum`, a `(mz, intensity)` pair or a list of
        peaks. `precursor` and `polarity` come off a `Spectrum` by
        themselves; pass them to override, or to search a bare pair of
        arrays.

        With a precursor, only records within `precursor_tolerance` are
        scored. Records stating no precursor are left out unless
        `include_unknown_precursor` — on MassBank they are 24,000 of
        139,000 and they dominate every search — and when included their
        `delta_ppm` is None, so a reader can see the filter did not apply
        rather than believing it passed. The tolerance defaults to the
        precision the query's own precursor was written to: a channel that
        says `647.5` is not known to three decimals.
        """
        return [_match(hit) for hit in self._search(
            spectrum, precursor=precursor, polarity=polarity, top=top,
            tolerance_ppm=tolerance_ppm,
            precursor_tolerance=precursor_tolerance, min_matched=min_matched,
            include_unknown_precursor=include_unknown_precursor,
            include_other_polarity=include_other_polarity,
            min_relative=min_relative)]

    def _search(self, spectrum, precursor=None, polarity=None, top: int = 20,
                tolerance_ppm=None, precursor_tolerance=None,
                min_matched=None, include_unknown_precursor: bool = False,
                include_other_polarity: bool = False,
                min_relative: float = 0.01):
        """The hits as the library holds them — for `infusion_report`."""
        from .library import (MIN_MATCHED, PEAK_TOLERANCE_PPM,
                              PRECURSOR_TOLERANCE_DA)

        mz, intensity = _arrays_of(spectrum, min_relative)
        if precursor is None:
            precursor = getattr(spectrum, "precursor", None)
        if polarity is None:
            polarity = getattr(spectrum, "polarity", None) or None
        if precursor_tolerance is None:
            precursor_tolerance = PRECURSOR_TOLERANCE_DA
            if precursor:
                # the channel's precursor is good to the decimals it was
                # typed with: `430.35` is known to ±0.005, and a filter
                # tighter than that asks for digits nothing ever carried
                from .lipidmaps import mass_precision

                precursor_tolerance = max(precursor_tolerance,
                                          mass_precision(float(precursor)))
        return self._library.search(
            mz, intensity,
            None if precursor is None else float(precursor),
            tolerance_ppm=(PEAK_TOLERANCE_PPM if tolerance_ppm is None
                           else float(tolerance_ppm)),
            precursor_tolerance=float(precursor_tolerance),
            top=int(top),
            min_matched=(MIN_MATCHED if min_matched is None
                         else int(min_matched)),
            include_unknown_precursor=bool(include_unknown_precursor),
            polarity=polarity,
            include_other_polarity=bool(include_other_polarity))

    # -- adding ------------------------------------------------------------ #
    def add(self, spectrum, name: str, precursor=None, adduct: str = "",
            formula: str = "", collision_energy=None, comment: str = "",
            acquired: str = "", path=None, write: bool = True) -> int:
        """
        Add one measured spectrum as a record, and write it out.

        The peaks must already be centroids: a profile spectrum has tens of
        points across every ion, and a record made of them describes the
        instrument's peak shape rather than the compound. Peaks under one
        per cent of the base peak are dropped and at most two hundred kept.

        `precursor`, `adduct` and `collision_energy` come off a `Spectrum`
        where it has them. The record is appended to `path`, or to the file
        the library was opened from; `write=False` adds it in memory only.
        Returns the number of records the library now holds.
        """
        from .library import entry_from_spectrum, write_msp

        mz, intensity = _arrays_of(spectrum, 0.0)
        if precursor is None:
            precursor = getattr(spectrum, "precursor", None)
        if collision_energy is None:
            collision_energy = getattr(spectrum, "collision_energy", None)
        entry = entry_from_spectrum(
            name, mz, intensity,
            precursor=None if precursor is None else float(precursor),
            precursor_type=str(adduct or ""), formula=str(formula or ""),
            collision_energy=(None if collision_energy is None
                              else float(collision_energy)),
            comment=str(comment or ""), acquired=str(acquired or ""))
        self._library.entries.append(entry)
        self._rebuild()
        if write:
            target = os.fspath(path) if path is not None else self.path
            if not target:
                raise ValueError("no file to write to: open the library with "
                                 "a path, or pass one to add()")
            write_msp([entry], target, append=True)
            self.path = self.path or target
        return len(self)

    def _rebuild(self) -> None:
        """Drop whatever the library memoised, so a search sees the new record."""
        from .library import SpectralLibrary

        self._library = SpectralLibrary(list(self._library.entries), self.path)


def _arrays_of(spectrum, min_relative: float) -> tuple[np.ndarray, np.ndarray]:
    """
    A spectrum, a pair of arrays or a list of peaks — as two arrays of
    centroids.

    A `Spectrum` that has not been centroided is, because both the things
    that read this — a library search and a record written from a spectrum —
    are about ions and not about the instrument's peak shape. A bare pair of
    arrays is taken as given: whoever built it knows what it holds.
    """
    if isinstance(spectrum, Spectrum):
        spectrum = spectrum.centroid()
    mz = getattr(spectrum, "mz", None)
    intensity = getattr(spectrum, "intensity", None)
    if mz is None or intensity is None:
        pair = list(spectrum)
        if len(pair) == 2 and np.ndim(pair[0]) == 1 and np.ndim(pair[1]) == 1:
            mz, intensity = pair
        else:
            mz = [float(a) for a, _b in pair]
            intensity = [float(b) for _a, b in pair]
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if min_relative and intensity.size:
        top = float(intensity.max())
        if top > 0:
            keep = intensity >= min_relative * top
            mz, intensity = mz[keep], intensity[keep]
    return mz, intensity


# --------------------------------------------------------------------------- #
# the infusion document
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class InfusionLine:
    """One infusion, as the document's table reports it."""

    compound: str
    sample: str
    file: str = ""
    polarity: str = ""
    collision_energy: float | None = None
    scans: int = 0
    base_peak: float | None = None
    precursor_written: float | None = None
    #: the accurate precursor, measured in the survey scan where there is
    #: one and in the averaged product spectrum where there is not
    precursor_found: float | None = None
    delta_ppm: float | None = None
    #: how the precursor was measured: "survey", "survivor", or "" when it
    #: was not measured at all
    precursor_from: str = ""
    #: the annotation, when a formula or a name was resolved for it
    annotation: Annotation | None = None
    #: the best record of the library, when one was given
    match: Match | None = None
    note: str = ""


@dataclass(frozen=True)
class InfusionDocument:
    """What `infusion_report` wrote, and what it found on the way."""

    path: str
    lines: tuple[InfusionLine, ...] = ()
    seconds: float = 0.0

    def __len__(self) -> int:
        return len(self.lines)

    def __iter__(self):
        return iter(self.lines)


def _infusions_of(source) -> list[Acquisition]:
    """Every sample of a file, a folder or an acquisition that reads as one."""
    from .raw import is_supported

    if isinstance(source, Acquisition):
        candidates = [source]
    else:
        path = os.fspath(source)
        if os.path.isdir(path):
            files = sorted(os.path.join(path, name)
                           for name in os.listdir(path)
                           if is_supported(name) and not name.startswith("."))
        else:
            files = [path]
        candidates = []
        for one in files:
            candidates += open(one).samples
    return [run for run in candidates if run.is_infusion]


def infusion_report(source, out, library=None, formula=None, adduct=None,
                    name=None, title: str = "",
                    measure_precursor: bool = True) -> InfusionDocument:
    """
    Write the direct-infusion document for a file, a folder or one sample.

    `source` is a path to a raw file, a path to a folder of them, or an
    `Acquisition`. Every sample that reads as a direct infusion gets a
    section: the averaged spectrum, the accurate precursor, what a formula
    or a name accounts for in it, and the best record of `library`. Samples
    that read as chromatography are left out — an infusion document of a
    gradient would be a page about the wrong thing — and if nothing reads as
    an infusion this raises rather than writing an empty document.

    `formula` and `name` say what is being infused. Left out, the compound
    is taken from the sample's own name — the part before the first
    underscore, which is how these files are named — and resolved through
    the standards table and LIPID MAPS. `library` is a `Library`, or a path
    to an MSP.

    `out` ending in `.pdf` is laid out on A4 pages by Qt, which is done in
    an offscreen application made here; any other suffix writes HTML.

        doc = api.infusion_report("/data/infusions", "infusions.pdf")
        for line in doc:
            print(line.compound, line.annotation.share)
    """
    from .infusion_report import compound_of, write_html, write_pdf

    started = time.perf_counter()
    runs = _infusions_of(source)
    if not runs:
        raise ValueError(f"nothing in {source!r} reads as a direct infusion — "
                         f"see the manual on what makes one")
    if library is not None and not isinstance(library, Library):
        library = Library.open(library)

    reports, lines = [], []
    for run in runs:
        report, line = _infusion_section(run, library, formula, adduct, name,
                                         measure_precursor)
        reports.append(report)
        lines.append(line)

    out = os.fspath(out)
    title = title or f"{compound_of(runs[0].name)} — infusion report"
    if out.lower().endswith(".pdf"):
        with headless():
            write_pdf(reports, out, title=title)
    else:
        write_html(reports, out, title=title)
    return InfusionDocument(path=out, lines=tuple(lines),
                            seconds=time.perf_counter() - started)


def _infusion_section(run: Acquisition, library, formula, adduct, name,
                      measure_precursor: bool):
    """One infusion: the report the document prints, and the plain line."""
    from .infusion_report import compound_of, report_for

    channel = run.infusion_channel()
    compound = compound_of(run.name)
    spectrum = run.infusion_average()

    explanation, annotation = None, None
    if spectrum is not None:
        try:
            explanation, annotation = _explanation(
                spectrum, formula=formula, name=name or compound,
                adduct=adduct)
        except Exception as exc:                 # a formula nothing parses
            annotation = Annotation(name=compound, note=str(exc))

    hit, match = None, None
    if library is not None and spectrum is not None and len(library):
        found = library._library.search(
            *_arrays_of(spectrum, 0.01),
            precursor=spectrum.precursor)
        if found:
            hit, match = found[0], _match(found[0])

    report = report_for(
        run.entry(), channel.reader if channel is not None else None,
        compound=compound,
        explanation=explanation,
        basis=(annotation.basis if annotation is not None else ""),
        deuterium=(annotation.labels if annotation is not None else 0),
        hit=hit, library=(os.path.basename(library.path) if library else ""),
        adduct=(annotation.adduct if annotation is not None else ""),
        measure_precursor=measure_precursor)
    return report, _infusion_line(run, report, annotation, match)


def _infusion_line(run: Acquisition, report, annotation, match) -> InfusionLine:
    measurement = getattr(report, "measurement", None)
    found, source = None, ""
    if measurement is not None and getattr(measurement, "found", False):
        found, source = float(measurement.measured), "survey"
    elif getattr(report, "survivor", None):
        found, source = float(report.survivor[0]), "survivor"
    written = getattr(report, "written_precursor", None)
    delta = (None if not (found and written)
             else (found - written) / written * 1e6)
    try:
        peak = report.base_peak()
    except Exception:
        peak = None
    return InfusionLine(
        compound=str(getattr(report, "compound", "") or ""),
        sample=str(getattr(report, "sample", "") or run.name),
        file=str(getattr(report, "file", "") or ""),
        polarity=str(getattr(report, "polarity", "") or ""),
        collision_energy=getattr(report, "collision_energy", None),
        scans=int(getattr(report, "scans", 0) or 0),
        base_peak=(None if not peak else float(peak[0])),
        precursor_written=(None if written is None else float(written)),
        precursor_found=found, delta_ppm=delta, precursor_from=source,
        annotation=annotation, match=match,
        note=str(getattr(report, "survivor_note", "") or ""),
    )
