"""
What the application costs on this machine, scenario by scenario.

Every performance figure in CLAUDE.md was produced by running something; this
is the something. Each scenario is a named callable that does one whole piece
of work — opening a file, drawing a tab, printing a document — and is timed
with the wall clock, the CPU clock and the process's peak resident size. A
scenario that cannot run here (its data is not on this machine) says so and is
skipped, never quietly reported as fast.

    python3 tools/bench.py                      # every scenario that can run
    python3 tools/bench.py --only open,spectra  # a few of them
    python3 tools/bench.py --profile spectra    # cProfile that one
    python3 tools/bench.py --json out.json      # for comparing two runs
    python3 tools/bench.py --compare before.json after.json

Peak resident size is the **process**'s, not the scenario's: it never falls,
so a scenario's figure is the high-water mark reached by the time it ended,
and only the first scenario to reach a level is charged for it. Run one
scenario alone to attribute memory to it.
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import gc
import glob
import json
import os
import pstats
import resource
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class Skip(Exception):
    """The data this scenario needs is not on this machine."""


def peak_rss_mb() -> float:
    """The process's high-water resident size, in megabytes."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux kilobytes
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


# --------------------------------------------------------------------------- #
# where the data is
# --------------------------------------------------------------------------- #
@functools.cache
def _checkouts() -> tuple[str, ...]:
    """
    This checkout, and the main one if this is a worktree.

    A `git worktree` holds only what git tracks and the acquisitions are
    ignored, so an agent measuring from a worktree has to reach into the main
    checkout for them — the same way `tests/real/data.py` does.

    Cached, because it forks a subprocess: uncached it charged every scenario
    that names a file 18 ms of somebody else's process, which is a quarter of
    what reading all 81 chromatograms costs.
    """
    import subprocess
    found = [ROOT]
    try:
        common = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--path-format=absolute",
             "--git-common-dir"],
            capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return tuple(found)
    main = os.path.dirname(common)
    if main and main not in found:
        found.append(main)
    return tuple(found)


@functools.cache
def eics() -> tuple[str, ...]:
    """The five `260904_EICs_Isabela_*.wiff`, in the working directory."""
    roots = [os.environ.get("MILQ_REAL_EICS"), *_checkouts()]
    for root in roots:
        if not root:
            continue
        files = sorted(glob.glob(os.path.join(root, "260904_EICs_Isabela_*.wiff")))
        if files:
            return tuple(files)
    raise Skip("no 260904_EICs_Isabela_*.wiff in "
               + ", ".join(r for r in roots if r))


def one_wiff() -> str:
    return eics()[0]


def one_mzml() -> str:
    for root in [os.environ.get("MILQ_REAL_EICS"), *_checkouts()]:
        if not root:
            continue
        files = sorted(glob.glob(os.path.join(root, "*.mzML")))
        if files:
            return files[0]
    raise Skip("no .mzML beside the acquisitions")


def infusion_folder() -> str:
    for candidate in (os.environ.get("MILQ_REAL_INFUSIONS"),
                      "/Volumes/NOBRE/Cyborg/Bileomics"):
        if candidate and os.path.isdir(candidate):
            return candidate
    raise Skip("the bile-acid infusion folder is not mounted")


# --------------------------------------------------------------------------- #
# the scenarios
# --------------------------------------------------------------------------- #
SCENARIOS: dict[str, tuple[str, callable]] = {}


def scenario(name: str, what: str):
    def register(func):
        SCENARIOS[name] = (what, func)
        return func
    return register


@scenario("import-api", "import milq.api")
def _import_api():
    import subprocess
    subprocess.run([sys.executable, "-c", "import milq.api"],
                   cwd=ROOT, check=True)


@scenario("import-ui", "import the whole user interface")
def _import_ui():
    import subprocess
    subprocess.run([sys.executable, "-c", "import milq.ui.shell"],
                   cwd=ROOT, check=True)


@scenario("bootstrap", "bring up .NET and the SCIEX assemblies")
def _bootstrap():
    from milq import bootstrap
    bootstrap.ensure()


@scenario("open", "open one .wiff and list its channels")
def _open():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        return len(acquisition.channels)


@scenario("tics", "every channel's chromatogram of one sample")
def _tics():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        return sum(len(channel.tic()) for channel in acquisition.channels)


@scenario("spectra", "25 spectra off the busiest channel")
def _spectra():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        channel = _busiest(acquisition)
        scans = len(channel.tic())
        step = max(1, scans // 25)
        return sum(len(channel.spectrum(i)) for i in range(0, scans, step))


@scenario("average", "average 100 scans of the busiest channel")
def _average():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        channel = _busiest(acquisition)
        times = channel.tic().arrays()[0]
        stop = min(len(times) - 1, 99)
        return len(channel.average(float(times[0]), float(times[stop])))


@scenario("xic", "an extracted ion chromatogram over the busiest channel")
def _xic():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        channel = _busiest(acquisition)
        info = channel.reader.info
        centre = (info.start_mass + info.end_mass) / 2
        return len(channel.xic(centre, tolerance=0.25))


@scenario("peaks", "detect peaks in every channel of one sample")
def _peaks():
    from milq import api
    from milq import processing
    found = 0
    with api.open(one_wiff()) as acquisition:
        for channel in acquisition.channels:
            x, y = channel.tic().arrays()
            found += len(processing.detect_peaks(x, y))
    return found


@scenario("centroid", "centroid 25 profile spectra")
def _centroid():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        channel = _busiest(acquisition)
        scans = len(channel.tic())
        step = max(1, scans // 25)
        return sum(len(channel.spectrum(i).centroid())
                   for i in range(0, scans, step))


@scenario("pick-peaks", "the top peaks of 25 profile spectra")
def _pick_peaks():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        channel = _busiest(acquisition)
        scans = len(channel.tic())
        step = max(1, scans // 25)
        return sum(len(channel.spectrum(i).peaks(limit=60))
                   for i in range(0, scans, step))


@scenario("contour", "the run as a retention time by m/z grid")
def _contour():
    from milq import api
    from milq.contour import build_contour
    with api.open(one_wiff()) as acquisition:
        grid = build_contour(_busiest(acquisition).reader)
        return grid.intensity.shape


@scenario("quantify", "81 components integrated over the five acquisitions")
def _quantify():
    _qt_app()
    from milq.session import Session
    from milq import quantify
    session = Session()
    for path in eics():
        session.open_file(path)
    components = session.generate_components()
    session.set_components(components)
    results = quantify.process(session.entries, session.method,
                               cache=session.cache)
    session.close_all()
    return len(results)


@scenario("bpc", "a base peak chromatogram over the busiest channel")
def _bpc():
    from milq import api
    with api.open(one_wiff()) as acquisition:
        return len(_busiest(acquisition).reader.bpc())


@scenario("mzml-xic", "six extracted ion chromatograms off one mzML channel")
def _mzml_xic():
    """
    Where an mzML is actually read twice.

    A chromatogram off an mzML channel used to re-parse every scan of that
    channel on every call and keep nothing, so a method asking for eighty
    components asked eighty times.
    """
    from milq import api
    with api.open(one_mzml()) as acquisition:
        channel = _busiest(acquisition)
        info = channel.reader.info
        low, high = info.start_mass, info.end_mass
        total = 0
        for step in range(6):
            centre = low + (high - low) * (step + 1) / 7.0
            total += len(channel.xic_range(centre - 0.25, centre + 0.25))
        return total


@scenario("mzml-bpc", "every channel's base peak chromatogram off one mzML")
def _mzml_bpc():
    from milq import api
    with api.open(one_mzml()) as acquisition:
        return sum(len(channel.reader.bpc()[0])
                   for channel in acquisition.channels)


@scenario("mzml-spectra", "decode 25 spectra out of one mzML")
def _mzml_spectra():
    from milq import api
    with api.open(one_mzml()) as acquisition:
        channel = _busiest(acquisition)
        scans = len(channel.tic())
        step = max(1, scans // 25)
        return sum(len(channel.spectrum(i)) for i in range(0, scans, step))


@scenario("sampling", "the sampling report over the batch")
def _sampling():
    from milq import sampling
    session, results = _processed()
    report = sampling.sampling_report(results, session.entries, session.method)
    session.close_all()
    return len(report.rows)


@scenario("compare", "every integration algorithm run over the batch")
def _compare():
    from milq import compare
    session, _ = _processed()
    comparison = compare.compare_algorithms(session.entries, session.method,
                                            cache=session.cache)
    session.close_all()
    return comparison is not None and len(comparison.components)


def _processed():
    """The five acquisitions opened, componented and integrated once."""
    _qt_app()
    from milq.session import Session
    from milq import quantify
    session = Session()
    for path in eics():
        session.open_file(path)
    session.set_components(session.generate_components())
    results = quantify.process(session.entries, session.method,
                               cache=session.cache)
    return session, results


@scenario("mzml-read", "read one mzML end to end")
def _mzml_read():
    from milq import api
    with api.open(one_mzml()) as acquisition:
        return sum(len(channel.tic()) for channel in acquisition.channels)


def _busiest(acquisition):
    return max(acquisition.channels, key=lambda c: len(c.tic()))


@scenario("digest", "the --digest fingerprint over the five acquisitions")
def _digest():
    import subprocess
    files = eics()
    subprocess.run([sys.executable, "-m", "milq.app", "--digest", *files],
                   cwd=ROOT, check=True, capture_output=True)


@scenario("explorer-open", "open one .wiff in the window and list its channels")
def _explorer_open():
    """
    What opening a file costs through the window rather than through the
    reader: the sample opened, the tree and the channel list rebuilt.

    The window is closed with its session marked clean. Opening a file makes
    the session dirty, and closing a dirty window puts up the modal "discard
    changes?" box — which, offscreen, nobody can answer.
    """
    app = _qt_app()
    from milq.ui.shell import MainShell
    window = MainShell()
    window.show()
    app.processEvents()
    window.session.open_file(one_wiff())
    window.explorer.rebuild_tree()
    app.processEvents()
    window.session.dirty = False
    window.close()
    app.processEvents()


@scenario("open-five", "open all five acquisitions in the window")
def _open_five():
    app = _qt_app()
    from milq.ui.shell import MainShell
    window = MainShell()
    window.show()
    app.processEvents()
    for path in eics():
        window.session.open_file(path)
    window.explorer.rebuild_tree()
    app.processEvents()
    window.session.dirty = False
    window.close()
    app.processEvents()


@scenario("shell", "build the main window")
def _shell():
    app = _qt_app()
    from milq.ui.shell import MainShell
    window = MainShell()
    window.show()
    app.processEvents()
    window.close()
    app.processEvents()


@scenario("shell-tabs", "build the window and visit every tab")
def _shell_tabs():
    app = _qt_app()
    from PyQt6 import QtWidgets
    from milq.ui.shell import MainShell
    window = MainShell()
    window.show()
    app.processEvents()
    tabs = window.findChild(QtWidgets.QTabWidget)
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        app.processEvents()
    window.close()
    app.processEvents()


@scenario("review-relayout", "the peak review grid rebuilt at 1x1 … 8x8")
def _review_relayout():
    _qt_app()
    from milq.ui.peak_review import PeakReviewGrid
    grid = PeakReviewGrid()
    grid.resize(1200, 700)
    for columns, rows in ((1, 1), (3, 2), (4, 4), (6, 6), (8, 8), (3, 2)):
        grid.col_spin.setValue(columns)
        grid.row_spin.setValue(rows)
    grid.deleteLater()


@scenario("manual-pdf", "print the manual to PDF")
def _manual_pdf():
    _qt_app()
    import tempfile
    from milq import manual
    out = os.path.join(tempfile.mkdtemp(), "manual.pdf")
    manual.load().write_pdf(out)
    return os.path.getsize(out)


@scenario("infusion-report", "one infused standard reported")
def _infusion_report():
    folder = infusion_folder()
    files = sorted(glob.glob(os.path.join(folder, "*.wiff")))
    if not files:
        raise Skip(f"no .wiff in {folder}")
    _qt_app()
    from milq import api
    return api.infusion_report(files[0]) is not None


_APP = None


def _qt_app():
    global _APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


# --------------------------------------------------------------------------- #
# running them
# --------------------------------------------------------------------------- #
def run_one(name: str, repeats: int) -> dict:
    what, func = SCENARIOS[name]
    walls, cpus = [], []
    note = ""
    for _ in range(repeats):
        gc.collect()
        before_wall, before_cpu = time.perf_counter(), time.process_time()
        try:
            func()
        except Skip as skipped:
            return {"name": name, "what": what, "skipped": str(skipped)}
        walls.append(time.perf_counter() - before_wall)
        cpus.append(time.process_time() - before_cpu)
    return {"name": name, "what": what, "note": note,
            "wall": min(walls), "wall_median": statistics.median(walls),
            "cpu": min(cpus), "peak_rss_mb": peak_rss_mb(),
            "repeats": repeats}


def profile_one(name: str, out: str | None, warm: bool = True) -> None:
    """
    cProfile one scenario, after a warm-up pass.

    Without the warm-up the profile of any scenario that touches a `.wiff` is
    two thirds importing numpy and bringing up .NET — one-time costs that say
    nothing about what the scenario does every time it runs. The first run is
    thrown away and the second is the one measured. `--cold` keeps the old
    behaviour for when the import cost is the question.
    """
    _, func = SCENARIOS[name]
    if warm:
        try:
            func()
        except Skip as skipped:
            print(f"{name} skipped — {skipped}")
            return
    profiler = cProfile.Profile()
    profiler.enable()
    func()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(35)
    stats.sort_stats("tottime")
    stats.print_stats(25)
    if out:
        stats.dump_stats(out)
        print(f"written to {out}")


def machine() -> dict:
    import platform
    return {"platform": platform.platform(), "python": platform.python_version(),
            "machine": platform.machine(), "cpus": os.cpu_count()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--only", help="comma-separated scenario names")
    parser.add_argument("--list", action="store_true", help="name every scenario")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--profile", help="cProfile one scenario instead")
    parser.add_argument("--profile-out", help="where to write the .prof")
    parser.add_argument("--cold", action="store_true",
                        help="profile without the warm-up pass")
    parser.add_argument("--json", help="write the table as JSON")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args(argv)

    if args.list:
        for name, (what, _) in SCENARIOS.items():
            print(f"{name:18s} {what}")
        return 0

    if args.compare:
        return _compare(*args.compare)

    if args.profile:
        profile_one(args.profile, args.profile_out, warm=not args.cold)
        return 0

    names = args.only.split(",") if args.only else list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        parser.error(f"no such scenario: {', '.join(unknown)}")

    rows = []
    for name in names:
        row = run_one(name, args.repeats)
        rows.append(row)
        if "skipped" in row:
            print(f"{name:18s} skipped — {row['skipped']}", flush=True)
        else:
            print(f"{name:18s} {row['wall']:8.3f} s wall  {row['cpu']:8.3f} s cpu  "
                  f"{row['peak_rss_mb']:7.1f} MB peak", flush=True)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"machine": machine(), "rows": rows}, handle, indent=2)
        print(f"written to {args.json}")
    return 0


def _compare(before: str, after: str) -> int:
    with open(before, encoding="utf-8") as handle:
        first = {r["name"]: r for r in json.load(handle)["rows"]}
    with open(after, encoding="utf-8") as handle:
        second = {r["name"]: r for r in json.load(handle)["rows"]}
    print(f"{'scenario':18s} {'before':>9s} {'after':>9s} {'change':>9s}")
    for name, row in first.items():
        other = second.get(name)
        if not other or "wall" not in row or "wall" not in other:
            continue
        change = (other["wall"] - row["wall"]) / row["wall"] * 100
        print(f"{name:18s} {row['wall']:8.3f}s {other['wall']:8.3f}s {change:+8.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
