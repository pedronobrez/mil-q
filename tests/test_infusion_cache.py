"""
The averaged spectra kept on disk, and *Measure* taken off the window's
thread.

Two things are being tested and they have almost nothing to do with each
other. The cache is arithmetic about keys — what makes two averages the same
average and what makes them different — and the only way to be sure is to
change one input at a time and watch the key move. The worker is a promise
about order and about failure: rows in the order the files finished, a cancel
that stops after the file it interrupted rather than in the middle of it, a
file that raises being one row with the reason on it, and the buttons coming
back whatever happened.

What is *not* tested here is that either makes anything faster. That is a
measurement on real files and it belongs in CLAUDE.md with the figures, not
in an assertion that would fail on a slow runner.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import infusion_report as ir  # noqa: E402
from milq import spectrum_cache  # noqa: E402
from milq.session import Session  # noqa: E402
from tests.test_infusion_report import _entry  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def cache(tmp_path):
    return spectrum_cache.AverageCache(str(tmp_path / "oqcache"))


def _file(tmp_path, name="CA-d4_mix1.wiff", size=64, scan_size=4096):
    """A `.wiff` and its `.wiff.scan`, as far as a stamp can tell."""
    path = tmp_path / name
    path.write_bytes(b"w" * size)
    (tmp_path / (name + ".scan")).write_bytes(b"s" * scan_size)
    return str(path)


def _session(*entries) -> Session:
    session = Session()
    session.entries.extend(entries)
    return session


# --------------------------------------------------------------------------- #
# where the directory is
# --------------------------------------------------------------------------- #
def test_a_saved_project_keeps_its_averages_beside_it(monkeypatch, tmp_path):
    """`<project>.oqcache/`: the averages belong to the batch, so they are
    found where the batch is found and go when it goes."""
    monkeypatch.delenv(spectrum_cache.ENV_DIR, raising=False)
    where = spectrum_cache.cache_dir(str(tmp_path / "bileomics.oqproj"))

    assert where == str(tmp_path / "bileomics.oqcache")
    assert "beside the project" in spectrum_cache.describe_dir(
        where, str(tmp_path / "bileomics.oqproj"))


def test_with_no_project_open_the_system_cache_is_used(monkeypatch):
    """There is nowhere that belongs to the files, so the directory the
    operating system is entitled to empty is the honest place."""
    monkeypatch.delenv(spectrum_cache.ENV_DIR, raising=False)
    where = spectrum_cache.cache_dir(None)

    assert where == spectrum_cache.user_dir()
    assert "no project is open" in spectrum_cache.describe_dir(where, None)


def test_the_setting_and_the_variable_both_overrule_the_defaults(monkeypatch,
                                                                 tmp_path):
    monkeypatch.delenv(spectrum_cache.ENV_DIR, raising=False)
    assert spectrum_cache.cache_dir(str(tmp_path / "p.oqproj"),
                                    override="/somewhere") == "/somewhere"
    monkeypatch.setenv(spectrum_cache.ENV_DIR, "/forced")
    assert spectrum_cache.cache_dir(str(tmp_path / "p.oqproj"),
                                    override="/somewhere") == "/forced"


def test_the_session_follows_its_project(tmp_path, monkeypatch):
    """Saving a project under a name moves where its averages are kept, and
    the cache is rebuilt rather than left pointing at the old directory."""
    monkeypatch.delenv(spectrum_cache.ENV_DIR, raising=False)
    session = Session()
    first = session.averages.directory

    session.project_path = str(tmp_path / "day1.oqproj")
    second = session.averages.directory

    assert first == spectrum_cache.user_dir()
    assert second == str(tmp_path / "day1.oqcache")


# --------------------------------------------------------------------------- #
# the key
# --------------------------------------------------------------------------- #
def _key(path, **kwargs):
    kwargs.setdefault("whole_run", True)
    return spectrum_cache.average_key(path, kwargs.pop("channel", 1), **kwargs)


def test_the_key_moves_with_the_modification_time(tmp_path):
    path = _file(tmp_path)
    before = _key(path)
    os.utime(path, (1_000_000, 1_000_000))

    assert _key(path) != before


def test_the_key_moves_with_the_size(tmp_path):
    path = _file(tmp_path)
    before = _key(path)
    stamp = os.stat(path)
    with open(path, "ab") as handle:
        handle.write(b"more")
    os.utime(path, (stamp.st_atime, stamp.st_mtime))    # size alone

    assert _key(path) != before


def test_the_key_moves_with_the_companion_that_holds_the_scans(tmp_path):
    """A `.wiff` alone gives the method and the chromatograms; the spectra
    are in the `.wiff.scan`, so replacing that must retire the average."""
    path = _file(tmp_path)
    before = _key(path)
    with open(path + ".scan", "ab") as handle:
        handle.write(b"rewritten")

    assert _key(path) != before


def test_the_key_moves_with_the_channel_the_range_and_the_switch(tmp_path):
    path = _file(tmp_path)
    base = _key(path, channel=1, rt_range=(0.0, 1.5))

    assert _key(path, channel=2, rt_range=(0.0, 1.5)) != base
    assert _key(path, channel=1, rt_range=(0.0, 1.4)) != base
    assert _key(path, channel=1, rt_range=(0.0, 1.5),
                include_unstable=True) != base
    assert _key(path, channel=1, rt_range=(0.0, 1.5), whole_run=False) != base
    assert _key(path, channel=1, rt_range=(0.0, 1.5)) == base


def test_the_key_moves_with_the_spray_mask(tmp_path):
    """Two masks keeping different scans are two averages, and a mask is
    what `include_unstable` is switching off."""
    from milq.infusion import ScanMask

    path = _file(tmp_path)
    rt = np.linspace(0.0, 1.5, 8)
    whole = ScanMask(np.ones(8, dtype=bool), rt)
    trimmed = ScanMask(np.array([1, 1, 1, 0, 1, 1, 1, 1], dtype=bool), rt)

    assert _key(path, mask=whole) != _key(path, mask=trimmed)
    assert _key(path, mask=whole) != _key(path, mask=None)
    assert _key(path, mask=trimmed) == _key(path, mask=trimmed)


# --------------------------------------------------------------------------- #
# hit, miss and the bound
# --------------------------------------------------------------------------- #
def test_a_miss_then_a_hit(cache):
    assert cache.get("nothing-here") is None
    assert cache.misses == 1

    mz = np.array([100.0, 200.5, 300.25])
    intensity = np.array([1.0, 2.0, 3.5])
    assert cache.put("k", mz, intensity, ranges="0.008 min")

    got = cache.get("k")
    assert got is not None
    assert np.array_equal(got[0], mz)
    assert np.array_equal(got[1], intensity)
    assert got[2] == "0.008 min"
    assert (cache.hits, cache.misses) == (1, 1)


def test_a_truncated_entry_is_a_miss_and_not_a_failure(cache):
    """Every failure is a miss: a cache that raised would turn a way of
    going faster into a way of losing a measurement."""
    cache.put("k", np.zeros(4), np.zeros(4))
    with open(cache.path_for("k"), "wb") as handle:
        handle.write(b"not an npz")

    assert cache.get("k") is None
    assert cache.misses == 1


def test_a_directory_that_cannot_be_written_is_reported_and_not_raised(
        tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where a directory would go")
    cache = spectrum_cache.AverageCache(str(blocked / "oqcache"))

    assert cache.put("k", np.zeros(3), np.zeros(3)) is False
    assert cache.errors == 1
    assert "could not be written" in cache.summary()


def test_the_bound_drops_the_least_recently_used(cache):
    """LRU by access and not by write: `get` stamps the entry, so the one
    read most recently survives however long ago it was written."""
    import time

    payload = np.zeros(2_000)
    cache.max_mb = 1e6                       # unbounded, to learn the size
    cache.put("a", payload, payload)
    one = cache.size_bytes()
    time.sleep(0.02)
    cache.put("b", payload, payload)
    time.sleep(0.02)
    cache.get("a")                           # a is now the most recently used
    time.sleep(0.02)

    cache.max_mb = (one * 2.5) / (1024 * 1024)   # room for two of the three
    cache.put("c", payload, payload)             # prunes on the way out

    assert cache.get("b") is None            # written second, never read
    assert cache.get("a") is not None        # written first, read last
    assert cache.get("c") is not None


def test_clear_empties_it_and_says_what_went(cache):
    cache.put("a", np.zeros(100), np.zeros(100))
    cache.put("b", np.zeros(100), np.zeros(100))

    removed, freed = cache.clear()

    assert removed == 2
    assert freed > 0
    assert cache.entries() == []
    assert cache.size_bytes() == 0


# --------------------------------------------------------------------------- #
# reading through it
# --------------------------------------------------------------------------- #
def test_average_spectrum_reads_through_the_cache(cache, tmp_path):
    """The second call gives the same arrays and does not touch the reader,
    which is asserted by taking the reader away."""
    entry, channel = _entry()
    path = _file(tmp_path)
    first = ir.average_spectrum(channel, sample=entry.sample, cache=cache,
                                path=path)
    assert cache.misses == 1 and cache.hits == 0

    def refuse(*args, **kwargs):
        raise AssertionError("the file was read again")

    channel.spectrum_rt_range = refuse
    second = ir.average_spectrum(channel, sample=entry.sample, cache=cache,
                                 path=path)

    assert cache.hits == 1
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])
    assert first[2] == second[2]
    # the mask is measured again either way: it is what the key is made of
    assert second[3] is not None


def test_without_a_path_nothing_is_cached(cache):
    """A caller with no file to name has nothing to key on, and gets the
    reader's answer rather than a wrong one."""
    entry, channel = _entry()
    ir.average_spectrum(channel, sample=entry.sample, cache=cache, path="")

    assert cache.entries() == []
    assert (cache.hits, cache.misses) == (0, 0)


def test_what_is_stored_is_the_raw_average_and_the_correction_is_applied_on_read(
        cache, tmp_path):
    """
    The cache holds the file's own measurement; the axis correction belongs
    to the session and is applied afterwards, so turning the switch on does
    not have to re-read anything and cannot poison what was stored.
    """
    from milq.recalibrate import LockMass, MassCorrection

    entry, channel = _entry()
    path = _file(tmp_path)
    mz, _intensity, _window, _mask = ir.average_spectrum(
        channel, sample=entry.sample, cache=cache, path=path)
    stored = cache.get(spectrum_cache.average_key(
        path, channel.index, rt_range=ir.run_range(channel),
        mask=_mask, include_unstable=False))

    correction = MassCorrection(sample_key=entry.key, offset_ppm=5.0,
                                lock_masses=[LockMass("x", 400.0, 400.002)])
    corrected = correction.apply(mz)

    assert np.array_equal(stored[0], mz)            # raw, not corrected
    assert not np.array_equal(stored[0], corrected)
    # and applying it costs nothing that had to be stored
    assert np.allclose(corrected, mz * (1.0 + 5.0e-6))


def test_a_summary_measured_twice_reads_the_files_once(cache, tmp_path):
    entry, _channel = _entry(name="TESTOL_infusion_A")
    entry.path = _file(tmp_path)
    session = _session(entry)

    ir.summarise(session, cache=cache)
    assert cache.misses == 1 and cache.hits == 0

    session.mass_corrections = {}
    ir.summarise(session, cache=cache)

    assert cache.hits == 1


# --------------------------------------------------------------------------- #
# summarise, one row at a time
# --------------------------------------------------------------------------- #
def test_rows_arrive_one_at_a_time_in_the_order_the_files_finished():
    seen = []
    first, _a = _entry(name="TESTOL_infusion_A")
    second, _b = _entry(name="TESTOL_infusion_B")
    summary = ir.summarise(_session(first, second),
                           on_row=lambda row: seen.append(row.sample))

    assert seen == ["TESTOL_infusion_A", "TESTOL_infusion_B"]
    assert [row.sample for row in summary.rows] == seen


def test_progress_names_the_file_it_is_about_to_read():
    """Before, not after: what a progress dialog has to say is which file is
    being waited for."""
    calls = []
    entry, _c = _entry(name="TESTOL_infusion_A")
    ir.summarise(_session(entry),
                 progress=lambda done, total, name:
                     calls.append((done, total, name)) or True)

    assert calls[0] == (0, 1, "TESTOL_infusion_A")
    assert calls[-1] == (1, 1, "")


def test_progress_returning_false_stops_the_measurement():
    first, _a = _entry(name="TESTOL_infusion_A")
    second, _b = _entry(name="TESTOL_infusion_B")
    summary = ir.summarise(
        _session(first, second),
        progress=lambda done, total, name: done < 1)

    assert summary is None


def test_a_file_that_raises_is_one_row_with_the_reason_on_it():
    """Nine infusions where the fourth has lost its `.wiff.scan` are eight
    measurements and a reason, not a dead run."""
    good, _a = _entry(name="TESTOL_infusion_A")
    bad, bad_channel = _entry(name="TESTOL_infusion_B")

    def refuse(*args, **kwargs):
        raise OSError("the .wiff.scan is not beside the .wiff")

    bad_channel.spectrum_rt_range = refuse
    summary = ir.summarise(_session(good, bad))

    assert len(summary.rows) == 2
    failed = next(r for r in summary.rows if r.sample == "TESTOL_infusion_B")
    assert "the .wiff.scan is not beside" in failed.precursor_note
    assert "OSError" in failed.report.survivor_note
    # and it still says which infusion it is about
    assert failed.compound == "TESTOL"
    assert failed.report.channel == bad_channel.info.label
    # the one that worked is untouched
    good_row = next(r for r in summary.rows if r.sample == "TESTOL_infusion_A")
    assert good_row.report.spectrum is not None


# --------------------------------------------------------------------------- #
# the panel, off the window's thread
# --------------------------------------------------------------------------- #
def _panel(qapp, *entries):
    from milq.ui.infusions_panel import InfusionsPanel

    return InfusionsPanel(_session(*entries))


def test_the_table_fills_row_by_row_and_the_buttons_come_back(qapp):
    first, _a = _entry(name="TESTOL_infusion_A")
    second, _b = _entry(name="TESTOL_infusion_B")
    panel = _panel(qapp, first, second)
    counts = []
    panel.table.model().rowsInserted.connect(
        lambda *_: counts.append(panel.table.rowCount()))

    panel.measure(threaded=False)

    # one at a time as the files finished; the pair after them is `reload`
    # rewriting the finished summary, which is where the mutual scores come in
    assert counts[:2] == [1, 2]
    assert panel.table.rowCount() == 2
    assert panel.btn_measure.isEnabled()
    assert panel.btn_report.isEnabled()
    assert panel.btn_csv.isEnabled()
    assert panel._task is None
    assert panel._progress is None


def test_the_buttons_are_off_while_it_runs(qapp):
    entry, _c = _entry(name="TESTOL_infusion_A")
    panel = _panel(qapp, entry)
    off = []
    panel.session.sigSamplesChanged.connect(lambda: None)

    def watch(row):
        off.append((panel.btn_measure.isEnabled(),
                    panel.btn_report.isEnabled()))

    from milq.ui.infusion_worker import MeasureTask

    task = MeasureTask(panel.session, cache=panel.session.averages)
    panel._task = task
    panel._measured = []
    panel._start_table()
    task.signals.row.connect(panel._on_row)
    task.signals.row.connect(watch)
    task.signals.finished.connect(panel._on_finished)
    panel._enable(False)
    task.measure()

    assert off == [(False, False)]           # while it ran
    assert panel.btn_measure.isEnabled()     # and after


def test_cancel_stops_after_the_file_it_interrupted_and_keeps_the_rows(qapp):
    """
    A file being read is inside the reader and nothing here can interrupt
    it. What cancel promises is that the next one is not started and that
    what was measured stands.
    """
    first, _a = _entry(name="TESTOL_infusion_A")
    second, _b = _entry(name="TESTOL_infusion_B")
    third, _c = _entry(name="TESTOL_infusion_C")
    panel = _panel(qapp, first, second, third)
    task = None

    def stop(row):
        if panel.table.rowCount() == 1:
            task.cancel()

    from milq.ui.infusion_worker import MeasureTask

    task = MeasureTask(panel.session, cache=panel.session.averages)
    panel._task = task
    panel._measured = []
    panel._start_table()
    task.signals.row.connect(panel._on_row)
    task.signals.row.connect(stop)
    task.signals.finished.connect(panel._on_finished)
    panel._enable(False)
    task.measure()

    assert panel.table.rowCount() == 1
    assert len(panel.summary.rows) == 1
    assert "Cancelled" in panel.status.text()
    assert panel.btn_measure.isEnabled()
    assert panel._task is None


def test_a_worker_that_raises_is_a_sentence_and_not_a_dead_panel(qapp):
    """The one failure a background measurement must not have is leaving
    the dialog up and the buttons off for ever."""
    entry, _c = _entry(name="TESTOL_infusion_A")
    panel = _panel(qapp, entry)
    from milq.ui.infusion_worker import MeasureTask

    class Broken:
        """A session that raises before anything can be grouped — a reader
        gone, a project half loaded, whatever it turns out to be."""

        @property
        def entries(self):
            raise RuntimeError("the batch went away")

    task = MeasureTask(Broken())
    panel._task = task
    panel._measured = []
    panel._start_table()
    task.signals.finished.connect(panel._on_finished)
    task.signals.failed.connect(panel._on_failed)
    panel._enable(False)
    task.measure()

    assert "could not be run" in panel.status.text()
    assert panel.btn_measure.isEnabled()
    assert panel._task is None


def test_nothing_in_the_worker_touches_a_widget():
    """
    Read rather than run: a worker that touched a widget would usually work
    and occasionally crash, so the check is that the module holds no widget
    at all — no import of QtWidgets and nothing named for one.
    """
    import inspect

    from milq.ui import infusion_worker

    source = inspect.getsource(infusion_worker)
    assert "QtWidgets" not in source
    assert "self.panel" not in source
    for name in vars(infusion_worker):
        thing = getattr(infusion_worker, name)
        assert not (isinstance(thing, type)
                    and issubclass(thing, QtWidgets.QWidget))


def test_clearing_the_cache_says_what_went(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv(spectrum_cache.ENV_DIR, str(tmp_path / "oqcache"))
    entry, _c = _entry(name="TESTOL_infusion_A")
    entry.path = _file(tmp_path)
    panel = _panel(qapp, entry)
    panel.measure(threaded=False)
    assert panel.session.averages.entries()

    said = panel.clear_cache()

    assert "1 cached average(s) removed" in said
    assert panel.session.averages.entries() == []
    assert panel.clear_cache().startswith("Nothing was cached")
