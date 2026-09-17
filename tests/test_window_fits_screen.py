"""
The window has to fit on the screen, and go on fitting.

The main window's least size was 2,000 by 864 pixels on a laptop screen with
1,512 by 913 to give: thirteen buttons in a row set the Method workspace's
minimum width, the LIPID MAPS panel set the dock's height, and a widget's
minimum reaches the window. So the window could not be made narrower than the
screen, and every layout change — changing Columns or Rows in the peak review
grid, which is done constantly — re-applied that minimum and pushed the window
back out over the edge.

These tests assert the two halves of the answer: a bar of controls wraps
instead of demanding its whole width, and the window clamps itself to the
screen whatever it was saved at.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq.ui.flow_layout import FlowLayout  # noqa: E402
from milq.ui.shell import MainShell  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

#: the smallest screen this is expected to be opened on — a 1280 by 800
#: laptop. The window's least size has to fit inside it with room for the
#: title bar and the menu bar.
SMALL_SCREEN = (1280, 760)


def _least_size(widget) -> tuple[int, int]:
    hint, floor = widget.minimumSizeHint(), widget.minimumSize()
    return (max(hint.width() if hint.isValid() else 0, floor.width()),
            max(hint.height() if hint.isValid() else 0, floor.height()))


def test_the_window_fits_a_small_laptop(qapp):
    shell = MainShell()
    shell.show()
    qapp.processEvents()
    width, height = _least_size(shell)
    shell.close()
    assert width <= SMALL_SCREEN[0], (
        f"the window cannot be made narrower than {width} px")
    assert height <= SMALL_SCREEN[1], (
        f"the window cannot be made shorter than {height} px")


def test_every_workspace_fits_it_too(qapp):
    """Each tab separately, so a failure names the workspace that grew."""
    shell = MainShell()
    shell.show()
    qapp.processEvents()
    sizes = {name: _least_size(getattr(shell, name))
             for name in ("explorer", "analytics", "method", "samples")}
    shell.close()
    too_wide = {n: s for n, s in sizes.items() if s[0] > SMALL_SCREEN[0]}
    assert not too_wide, f"wider than the screen: {too_wide}"


def test_changing_rows_and_columns_does_not_grow_the_window(qapp):
    """
    The complaint this came from: the grid's spin boxes resized the window.

    The size asked for is the window's own least size and a little over, not
    a round number, because Qt will not go below the minimum and what is
    being tested is that a change of shape does not move the window — not
    what the minimum happens to be. `test_the_window_fits_a_small_laptop`
    is what holds the minimum down.
    """
    shell = MainShell()
    shell.show()
    least = _least_size(shell)
    wanted = QtCore.QSize(least[0] + 40, least[1] + 40)
    shell.resize(wanted)
    qapp.processEvents()
    assert shell.size() == wanted, "the window would not take the size asked"
    grid = shell.analytics.grid
    for columns, rows in ((1, 1), (8, 8), (3, 2)):
        grid.col_spin.setValue(columns)
        grid.row_spin.setValue(rows)
        qapp.processEvents()
        assert shell.size() == wanted, (
            f"{columns}x{rows} moved the window to {shell.size()}")
    shell.close()


def test_the_opening_size_is_never_larger_than_the_screen(qapp):
    available = qapp.primaryScreen().availableGeometry()
    width, height = MainShell.size_for_screen((10_000, 10_000))
    assert width <= available.width() and height <= available.height()
    # and a wanted size that does fit is left alone
    assert MainShell.size_for_screen((640, 480)) == (640, 480)


def test_a_window_saved_too_big_is_brought_back(qapp):
    """
    Bigger than the screen goes back to the screen.

    The floor is the window's own least size, which Qt will not go under: on
    the offscreen platform the screen is 800 by 800 and the window's least
    width is larger than that, so the assertion is against whichever is
    bigger. On a real screen the screen is what wins.
    """
    shell = MainShell()
    shell.show()
    available = qapp.primaryScreen().availableGeometry()
    shell.resize(available.width() + 800, available.height() + 400)
    qapp.processEvents()
    shell.fit_on_screen()
    qapp.processEvents()
    size, least = shell.size(), _least_size(shell)
    shell.close()
    assert size.width() <= max(available.width(), least[0])
    assert size.height() <= max(available.height(), least[1])


# --------------------------------------------------------------------------- #
# the layout itself
# --------------------------------------------------------------------------- #
def test_a_flow_layout_asks_for_its_widest_item_not_the_sum(qapp):
    box = QtWidgets.QWidget()
    flow = FlowLayout(box)
    widths = (120, 200, 90, 160)
    for width in widths:
        button = QtWidgets.QPushButton()
        button.setFixedSize(width, 24)
        flow.addWidget(button)
    assert flow.minimumSize().width() == max(widths)
    assert flow.minimumSize().width() < sum(widths)


def test_a_flow_layout_grows_taller_as_it_narrows(qapp):
    box = QtWidgets.QWidget()
    flow = FlowLayout(box)
    for _ in range(6):
        button = QtWidgets.QPushButton()
        button.setFixedSize(100, 24)
        flow.addWidget(button)
    one_line = flow.heightForWidth(1000)
    narrow = flow.heightForWidth(220)
    assert narrow > one_line, "a bar that cannot wrap is not wrapping"


def test_a_label_and_its_control_wrap_together(qapp):
    """
    Breaking between "Zoom" and the box saying what the zoom is leaves a word
    stranded above the control it names.
    """
    box = QtWidgets.QWidget()
    flow = FlowLayout(box)
    combo = QtWidgets.QComboBox()
    combo.addItems(["Expected window", "Peak", "Whole run"])
    flow.addPair("Zoom", combo)
    assert flow.count() == 1, "the label and the control are two items"
    assert combo.parent() is not box, "the control moved into the pair's holder"


def test_a_flow_layout_takes_the_calls_a_box_layout_takes(qapp):
    """The bars were written against QHBoxLayout and only the word changed."""
    box = QtWidgets.QWidget()
    flow = FlowLayout(box)
    flow.addWidget(QtWidgets.QLabel("one"), 1)
    flow.addSpacing(12)
    flow.addStretch(1)
    flow.addWidget(QtWidgets.QLabel("two"),
                   alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
    # the stretch is the one that is dropped: two labels and one spacer
    assert flow.count() == 3
