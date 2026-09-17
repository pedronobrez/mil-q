"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from PyQt6 import QtCore, QtGui, QtWidgets


def _bundled_on_macos() -> bool:
    """Inside MIL-Q.app, where the bundle owns the Dock icon."""
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="milq",
        description="Open source quantitation for LC-MS data (.wiff, .mzML).",
    )
    parser.add_argument("files", nargs="*",
                        help="raw data files to open (.wiff, .mzML)")
    parser.add_argument(
        "--selftest", action="store_true",
        help="open the files, report what was read, and exit without a window")
    parser.add_argument(
        "--digest", action="store_true",
        help="print a numeric fingerprint of each file, for comparing one "
             "build against another; implies --selftest's silence")
    parser.add_argument(
        "--infusion-report", nargs="+", metavar="PATH", default=None,
        help="report every direct infusion in the given files and folders, "
             "one section per compound, and exit without a window")
    parser.add_argument(
        "--out", metavar="FILE",
        help="where the infusion report is written (.pdf, or .html with "
             "--html)")
    parser.add_argument(
        "--library", metavar="FILE",
        help="a spectral library of your own (.msp, .mgf) to search each "
             "averaged spectrum against")
    parser.add_argument(
        "--components", metavar="FILE",
        help="a project (.oqproj) or a components CSV, for the formulas and "
             "adducts the compounds are explained from")
    parser.add_argument(
        "--html", action="store_true",
        help="write the infusion report as HTML rather than PDF")
    parser.add_argument(
        "--per-compound", action="store_true",
        help="one document per compound rather than one for all of them")
    parser.add_argument(
        "--csv", metavar="FILE",
        help="also write the infusion summary table as a CSV")
    args = parser.parse_args(argv)

    if args.infusion_report is not None:
        if not args.out:
            parser.error("--infusion-report needs --out to write to")
        return _infusion_report(args)
    if args.digest:
        return _digest(args.files)
    if args.selftest:
        return _selftest(args.files)

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("MIL-Q")
    # the suite's mark, drawn beside OpenDIAL's (packaging/make_icon.py), for
    # the window and the taskbar. Not inside the macOS bundle: there Qt hands
    # the window icon to the Dock as the application icon, and a flat PNG
    # then covers the layered Liquid Glass icon the bundle carries — measured
    # on macOS 26, where the icon services drew the glass and the Dock the
    # blue square, for exactly as long as the application was running.
    from pathlib import Path
    icon = Path(__file__).with_name("icon.png")
    if icon.is_file() and not _bundled_on_macos():
        app.setWindowIcon(QtGui.QIcon(str(icon)))

    from .ui import style
    from .ui.theme import apply_defaults

    style.apply(app)
    apply_defaults()

    from .ui.shell import MainShell

    window = MainShell()
    window.show()
    for path in args.files:
        window.load_file(path)
    if not args.files:
        window.offer_start()
    status = app.exec()
    _shut_down(app, window)
    return status


def _shut_down(app, window) -> None:
    """
    Take the window down before the interpreter does.

    PyQt registers an atexit hook that walks every Python wrapper it still
    holds and cleans up the Qt object behind it. If Qt has already destroyed
    that object — which it does for every child of a window as the window
    goes — the hook dereferences freed memory. On Linux that segfaults on
    quit: the application has done its work and printed its output, and the
    process still dies with signal 11, which is what a user sees and what a
    script reads.

    Deleting the window here, and letting Qt finish, leaves the hook nothing
    to trip over.
    """
    import gc

    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    del window
    gc.collect()


def _infusion_report(args) -> int:
    """
    A folder of infusions reported from the command line, with no window.

    The document is drawn and printed through Qt, so an application object is
    made whether or not anything is shown — `QT_QPA_PLATFORM=offscreen` is
    what makes that work on a machine with no display, and is what the
    installers' own runs set.

    Everything the run left out is printed with the reason it was left out. A
    silent skip is the failure mode that matters here: a folder of nine
    reported as eight, with nothing on screen to say which one went and why,
    is worse than an error.
    """
    from .infusion_batch import run

    def note(done: int, total: int, name: str) -> bool:
        if name:
            print(f"[{done + 1}/{total}] {name}", flush=True)
        return True

    try:
        result = run(args.infusion_report, args.out, library=args.library,
                     components=args.components,
                     fmt="html" if args.html else "pdf", csv=args.csv,
                     progress=note, per_compound=args.per_compound)
    except (OSError, ValueError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    for finding in result.findings:
        print(f"  {finding.kind}: {finding.finding}")
    for skip in result.skipped:
        print(f"  skipped {skip}")
    if result.summary is not None and result.summary.rows:
        print(result.summary.summary())
    for path in result.documents:
        print(f"wrote {path}")
    if result.csv:
        print(f"wrote {result.csv}")
    print(result.line())
    return 0 if result.documents else 1


def _digest(files: list[str]) -> int:
    """
    A numeric fingerprint of what this build reads, line by line.

    --selftest answers whether a build can open a file at all. This answers
    the harder question: whether two builds, on two systems, get the same
    numbers out of it. The output is plain text, one fact per line, meant to
    be diffed — so it carries every channel's totals at full precision and a
    hash of each array, rather than a summary that could hide a difference in
    the middle of a trace.

    The integrated areas are here too. Those are the numbers a result is made
    of, and a build that reads the same raw points but integrates them
    differently is not the same build.
    """
    import hashlib
    import os

    import numpy as np

    from . import __version__
    from .bootstrap import ensure
    from .processing import detect_peaks
    from .raw import open_raw

    def line(*parts) -> None:
        print("\t".join(str(p) for p in parts), flush=True)

    def fingerprint(values) -> str:
        """A hash of the array, to six decimals — the precision anyone reads."""
        rounded = np.round(np.asarray(values, dtype=float), 6)
        return hashlib.sha256(rounded.tobytes()).hexdigest()[:16]

    print(f"# milq {__version__} digest")
    try:
        ensure()
    except Exception as exc:
        print(f"# cannot read: {exc}")
        return 1

    for path in files:
        name = os.path.basename(str(path).replace("\\", "/"))
        wiff = open_raw(path)
        try:
            sample = wiff.sample(0)
            channels = sample.channels
            line("file", name, "channels", len(channels))

            time, total = sample.tic()
            line("sample.tic", name, len(time),
                 f"{float(np.sum(total)):.6f}", f"{float(np.max(total)):.6f}",
                 fingerprint(time), fingerprint(total))

            for index, channel in enumerate(channels):
                x, y = channel.tic()
                line("channel", index, channel.info.label, len(x),
                     f"{float(np.sum(y)):.6f}", f"{float(np.max(y)):.6f}",
                     fingerprint(x), fingerprint(y))

            # a few channels in full: spectra, extracted traces, and the
            # integration that a quantitative result is actually made of
            for index in [i for i in (0, 1, 20, 40, 80) if i < len(channels)]:
                channel = channels[index]
                x, y = channel.tic()
                if not len(x):
                    continue
                apex = int(np.argmax(y))
                scan = channel.scan_at_rt(float(x[apex]))
                mz, intensity = channel.spectrum(scan)
                line("spectrum", index, scan, len(mz),
                     f"{float(np.sum(mz)):.6f}", f"{float(np.sum(intensity)):.6f}",
                     fingerprint(mz), fingerprint(intensity))

                xic_x, xic_y = channel.xic(264.2686, 0.02)
                line("xic", index, len(xic_x), f"{float(np.sum(xic_y)):.6f}",
                     fingerprint(xic_y))

                for peak in detect_peaks(x, y)[:5]:
                    line("peak", index, f"{peak.apex_rt:.9f}",
                         f"{peak.start_rt:.9f}", f"{peak.end_rt:.9f}",
                         f"{peak.area:.9f}", f"{peak.height:.9f}")
        finally:
            wiff.close()
    return 0


def _lipidmaps_line() -> str:
    """
    What this build can do about a LIPID MAPS index, not just whether one is
    there.

    The index is an SQLite database, and a packaged application either
    carries the `sqlite3` extension module or it does not — which is
    invisible until somebody searches, on a machine nobody is watching. So
    the count is read here, which opens the database, and where no index is
    installed the reader is exercised on an empty one in memory. A build
    that cannot do that says so on the line where it matters.
    """
    from .lipidmaps import is_installed, record_count

    try:
        import sqlite3
        sqlite3.connect(":memory:").close()
    except Exception as exc:                         # pragma: no cover - a broken build
        return f"unreadable by this build — {type(exc).__name__}: {exc}"
    if not is_installed():
        return "not installed; this build can read one"
    count = record_count()
    return f"{count:,} structures" if count else "installed"


def _selftest(files: list[str]) -> int:
    """
    Report what this build can actually do, and exit.

    A packaged application either reads a .wiff or it does not, and the only
    honest way to know is to make it read one. Nothing here opens a window, so
    it runs the same on a build machine as on a desk.
    """
    import platform

    from . import __version__

    print(f"MIL-Q {__version__} on {platform.system()} "
          f"{platform.machine()}, Python {platform.python_version()}")

    print(f"LIPID MAPS index: {_lipidmaps_line()}")

    from . import bootstrap
    try:
        bootstrap.ensure()
        print(f"SCIEX libraries: ready (.NET at {bootstrap.find_dotnet_root()})")
    except Exception as exc:
        print(f"SCIEX libraries: unavailable — {exc}")
        return 1 if files else 0

    from .raw import open_raw
    for path in files:
        wiff = None
        try:
            wiff = open_raw(path)
            sample = wiff.sample(0)
            x, y = sample.channels[0].tic()
            print(f"{path}: {len(wiff.sample_names)} sample(s), "
                  f"{len(sample.channels)} channel(s), "
                  f"first TIC {x.size} points, max {y.max():,.0f}")
        except Exception as exc:
            print(f"{path}: FAILED — {type(exc).__name__}: {exc}")
            return 1
        finally:
            if wiff is not None:
                wiff.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
