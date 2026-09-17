"""
*Measure* taken off the window's thread.

Averaging nine ZenoTOF infusions, centroiding each average, explaining every
compound and scoring each against the others is half a minute of arithmetic.
Run on the GUI thread it is half a minute in which the window does not
repaint, does not move and does not answer — a wait cursor over a frozen
picture, which on macOS is a beachball and one more press away from being
force-quit.

So the whole of `infusion_report.summarise` runs in a `QRunnable` on the
global thread pool and says what it is doing through signals. What that buys
is not speed: the arithmetic is the same arithmetic and takes the same time.
It buys a window that repaints, a *Cancel* that is answered between files,
and a table that fills as the files finish instead of all at once at the end.

Rules this obeys, and they are the whole of why it is safe
---------------------------------------------------------

- **Nothing in here touches a widget.** The signals carry rows and strings;
  the panel connects them and does the drawing. A `QWidget` touched from a
  worker thread is undefined behaviour that usually looks like working.
- **One worker, files one after another.** Two threads each opening a
  `.wiff` was measured and Clearcore2 tolerates it, but the readers here are
  not two readers: the samples are already open on the session and shared,
  and `Sample` memoises its chromatogram and its probe without a lock. One
  thread walking them in order is off the GUI thread, which is the point;
  reading one file per thread would be a different design with a reader per
  thread in it.
- **Cancel is answered between files, never inside one.** A file being read
  is inside Clearcore2 and nothing here can interrupt it; the rows already
  measured are kept and the summary says how many of how many it holds.
"""

from __future__ import annotations

from PyQt6 import QtCore


class MeasureSignals(QtCore.QObject):
    """What the worker says. A plain `QObject` because `QRunnable` is not
    one and cannot carry signals of its own."""

    #: files finished, files in all, the sample now being read
    progress = QtCore.pyqtSignal(int, int, str)
    #: one `InfusionRow`, as soon as its file is done
    row = QtCore.pyqtSignal(object)
    #: the finished `InfusionSummary`, or None where it was cancelled
    finished = QtCore.pyqtSignal(object)
    #: the measurement did not run at all, with the reason
    failed = QtCore.pyqtSignal(str)


class MeasureTask(QtCore.QRunnable):
    """
    One press of *Measure*, off the GUI thread.

    `cancel()` is called from the GUI thread and read from the worker's; a
    bool assignment is atomic under the interpreter's lock and the worst a
    race can cost is one more file being measured, so there is no lock here
    on purpose — a lock held across a file read would be a lock held for
    four seconds.
    """

    def __init__(self, session, library=None, explanations=None,
                 include_unstable: bool = False, cache=None):
        super().__init__()
        self.setAutoDelete(False)
        self.session = session
        self.library = library
        self.explanations = explanations or {}
        self.include_unstable = bool(include_unstable)
        self.cache = cache
        self.signals = MeasureSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:                              # pragma: no cover - Qt
        self.measure()

    def measure(self):
        """
        The body, callable directly so a test does not need a thread pool.

        Every exception is a `failed` signal: a worker that raised would take
        the traceback to a console nobody has and leave the dialog up and the
        buttons disabled for ever, which is the one failure a background
        measurement must not have.
        """
        from ..infusion_report import summarise

        def tick(done: int, total: int, name: str) -> bool:
            if not self._cancelled:
                self.signals.progress.emit(int(done), int(total), str(name))
            return not self._cancelled

        try:
            summary = summarise(
                self.session, library=self.library,
                explanations=self.explanations,
                include_unstable=self.include_unstable,
                cache=self.cache, progress=tick,
                on_row=lambda row: self.signals.row.emit(row))
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return None
        self.signals.finished.emit(summary)
        return summary
