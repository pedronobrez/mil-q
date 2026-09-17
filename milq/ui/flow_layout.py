"""
A row of controls that wraps instead of demanding the width it wants.

A `QHBoxLayout` of thirteen buttons has a minimum width of all thirteen laid
side by side, and a widget's minimum reaches the window: the Method workspace's
toolbar alone asked for 1,994 pixels, so the main window could not be made
narrower than that on any screen. A `FlowLayout` asks for its *widest single
item* and puts the rest on the next line, which is what a toolbar means anyway.

It is the layout from Qt's own Flow Layout example, with two differences: it
answers `heightForWidth`, so a window that narrows grows the bar rather than
clipping it, and it takes `addSpacing`, so the bars written against
`QHBoxLayout` need only the one word changed.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class FlowLayout(QtWidgets.QLayout):
    """A left-to-right layout that moves to the next line when it runs out."""

    def __init__(self, parent=None, margin: int = 0, spacing: int = 6):
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    # -- the QLayout contract ------------------------------------------------- #
    def addItem(self, item) -> None:            # noqa: N802 (Qt's name)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):               # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):               # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):              # noqa: N802
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:        # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:    # noqa: N802
        return self._lay_out(QtCore.QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect) -> None:        # noqa: N802
        super().setGeometry(rect)
        self._lay_out(rect, apply=True)

    def sizeHint(self):                         # noqa: N802
        return self.minimumSize()

    def minimumSize(self):                      # noqa: N802
        """
        The widest single item, not the sum.

        This is the whole point: a bar that can wrap does not need room for
        every control at once, so it stops being what decides how narrow the
        window may be.
        """
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QtCore.QSize(margins.left() + margins.right(),
                                   margins.top() + margins.bottom())

    # -- conveniences the box layouts have ------------------------------------ #
    def addWidget(self, widget, stretch: int = 0, alignment=None) -> None:  # noqa: N802, ARG002
        """
        `QBoxLayout.addWidget` takes a stretch factor and an alignment.

        Neither means anything in a bar that wraps — every item is given the
        size it asks for and the line ends where the width runs out — so both
        are accepted and dropped, and a bar written for one line needs only
        the word `QHBoxLayout` changed. The names are Qt's, because the call
        sites write them as keywords.
        """
        del stretch, alignment
        super().addWidget(widget)

    def addPair(self, text: str, widget) -> None:   # noqa: N802
        """
        A label and the control it names, wrapped as one item.

        A wrapping bar breaks between any two items, and breaking between
        "Zoom" and the box that says what the zoom is leaves a word stranded
        at the end of a line above the control it belongs to. They go in one
        widget, so the line either takes both or takes neither.
        """
        holder = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(QtWidgets.QLabel(text))
        row.addWidget(widget)
        self.addWidget(holder)

    def addSpacing(self, width: int) -> None:   # noqa: N802
        """A gap between two groups of controls, which may end a line."""
        self.addItem(QtWidgets.QSpacerItem(
            width, 0, QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Minimum))

    def addStretch(self, stretch: int = 0) -> None:    # noqa: N802, ARG002
        """
        Nothing: a wrapping bar is already packed to the left.

        `QHBoxLayout.addStretch` is how a bar written for one line pushes the
        rest of itself to the right. There is no right-hand end here, and a
        stretch that silently consumed a whole line would be worse than none,
        so the call is accepted and ignored — the bars read the same either
        way.
        """
        del stretch

    # -- the arithmetic ------------------------------------------------------- #
    def _lay_out(self, rect, apply: bool) -> int:
        """Place every item; return the height used. With `apply`, move them."""
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(),
                             -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        spacing = self.spacing()

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > area.right() and line_height > 0:
                x = area.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if apply:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()
