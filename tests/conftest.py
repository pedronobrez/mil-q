"""
A clean slate between tests, because Qt and Python disagree about lifetimes.

Qt allows one QApplication per process, so every test module shares the same
one however many fixtures ask for it. A widget built inside a test is then
left to Python's garbage collector, which runs at moments Qt knows nothing
about — including in the middle of building an unrelated widget.

On Linux that was fatal. The collector freed a C++ widget the application
still had a pointer to, and the next thing to walk a QObject's children
dereferenced it: a segfault inside PyQt's own attribute lookup, landing in a
different test on every run and never in the test that caused it. macOS and
Windows read the same freed memory and survived, which is luck, not
correctness.

Proved by exhaustion before being fixed: every test file passes alone, and
the whole suite passes with each test in its own process. Nothing here is
about what a test does — only about what it leaves behind.
"""

import gc
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# the offscreen platform finds no fonts on Windows and draws every glyph as
# a box, which a test measuring ink off a rendered page reads as ink
from milq.api import offscreen_fonts

offscreen_fonts()

from PyQt6 import QtCore, QtWidgets  # noqa: E402

# Every settings object the suite constructs would otherwise write to the
# person's real preferences: a test of the library panel left a pytest
# temporary path as the remembered library, and a test that closes the
# shell saves its window layout over the real one. The native store on
# macOS ignores setPath and setDefaultFormat applies only to the
# no-argument constructor, so ui.settings reads this variable instead —
# set before any widget exists, and inherited by a subprocess.
os.environ["MILQ_SETTINGS"] = os.path.join(
    tempfile.mkdtemp(prefix="milq-test-settings-"), "MIL-Q.ini")

# And for the same reason, the on-disk cache of averaged spectra: without
# this the folder route and anything that opens a session would write .npz
# entries into ~/Library/Caches/MIL-Q, where the next run of the suite
# would read them back and a test of a cold measurement would be measuring a
# warm one. See spectrum_cache.ENV_DIR.
os.environ["MILQ_CACHE_DIR"] = tempfile.mkdtemp(
    prefix="milq-test-cache-")


# A widget left to the collector on Windows is torn down by Qt after its
# Python side is gone, and the layout of a plot being destroyed asks its
# title for a size hint, a bounding rectangle and a resize on the way out.
# pyqtgraph answers those from attributes its __init__ set, and the wrapper
# sip makes for a C++ object whose Python wrapper was collected has never
# run __init__ — so the suite's teardown printed AttributeErrors from
# inside Qt's event loop and pytest-qt called seven tests errors for it,
# on Windows only. Nothing in the application reaches this: measured by
# rebuilding stacked panes in a real window, which prints nothing. A ghost
# is given what the originals give an unknown hint: nothing.
import pyqtgraph as _pyqtgraph  # noqa: E402
from pyqtgraph.graphicsItems.GraphicsWidget import GraphicsWidget as _GraphicsWidget  # noqa: E402


def _unless_a_ghost(cls, name, attribute, nothing):
    original = getattr(cls, name)

    def method(self, *args, **kwargs):
        if not hasattr(self, attribute):
            return nothing() if callable(nothing) else nothing
        return original(self, *args, **kwargs)

    setattr(cls, name, method)


_unless_a_ghost(_pyqtgraph.LabelItem, "sizeHint", "_sizeHint",
                lambda: QtCore.QSizeF(0, 0))
_unless_a_ghost(_pyqtgraph.LabelItem, "resizeEvent", "item", None)
_unless_a_ghost(_GraphicsWidget, "boundingRect", "_previousGeometry",
                lambda: QtCore.QRectF())


@pytest.fixture(autouse=True)
def _settle_qt():
    """Collect and let Qt finish its deletions, between tests rather than during."""
    yield
    application = QtWidgets.QApplication.instance()
    if application is None:
        return
    gc.collect()
    application.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    application.processEvents()


# --------------------------------------------------------------------------- #
# tests/real: asserted against acquisitions that are not in the repository
# --------------------------------------------------------------------------- #
#: Everything under `tests/real` is a regression over data that lives outside
#: the repository — five sets of real acquisitions, none of which can ever be
#: committed. Those tests are marked here rather than in each file, so that a
#: new one cannot forget and start failing CI, where there is no data at all.
#: They run when asked for, by either route:
#:
#:     MILQ_REAL_DATA=1 pytest -q tests/real
#:     pytest -q -m real
#:
#: and are skipped otherwise. Each one also skips itself, naming the path it
#: looked for, when its own files are absent — see tests/real/data.py.
REAL_DATA = "MILQ_REAL_DATA"
REAL_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real")


def _real_data_wanted(config) -> bool:
    if os.environ.get(REAL_DATA, "").strip() not in ("", "0", "no", "false"):
        return True
    # `-m real`, `-m "real and infusions"`, and equally `-m "not real"`, which
    # is a caller saying they know the marker exists
    return "real" in (getattr(config.option, "markexpr", "") or "")


def pytest_collection_modifyitems(config, items):
    """Mark everything under `tests/real`, and skip it unless it was asked for."""
    wanted = _real_data_wanted(config)
    skip = pytest.mark.skip(
        reason=f"real data: run with {REAL_DATA}=1 or -m real "
               "(the files are not in the repository; see tests/real/README.md)")
    for item in items:
        if not str(item.path).startswith(REAL_DIRECTORY):
            continue
        item.add_marker(pytest.mark.real)
        if not wanted:
            item.add_marker(skip)
