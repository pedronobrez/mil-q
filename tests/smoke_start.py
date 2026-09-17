"""
Does the main window come up on this system?

Run as a script in a process of its own, not collected by pytest: building
the whole shell is not something to do in the middle of a suite, and a crash
here should take down only itself. CI runs it on every system, which is the
only thing that can answer the question for Linux and Windows.

    python -X faulthandler tests/smoke_start.py
"""

import platform
import sys

from PyQt6 import QtWidgets

import milq
from milq.ui import style
from milq.ui.theme import apply_defaults


def main() -> int:
    app = QtWidgets.QApplication([])
    style.apply(app)
    apply_defaults()
    print("style applied", flush=True)

    from milq.ui.shell import MainShell

    window = MainShell()
    print("shell built", flush=True)
    window.show()
    print("shown", flush=True)
    app.processEvents()
    print("events processed", flush=True)
    print(f"MIL-Q {milq.__version__} started on {platform.system()}",
          flush=True)

    # the same shutdown the real application does; without it PyQt's atexit
    # hook walks wrappers whose Qt objects are gone and the process dies with
    # signal 11 after a completely successful run
    from milq.app import _shut_down

    _shut_down(app, window)
    return 0


if __name__ == "__main__":
    sys.exit(main())
