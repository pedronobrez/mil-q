"""The molecule, drawn from the coordinates the structure was laid out with."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..structure import Fragment, Structure
from . import theme

#: carbons are drawn as line ends, the way a skeletal formula does; everything
#: else is spelled out
IMPLICIT = {"C"}


class StructureView(QtWidgets.QWidget):
    """
    A skeletal drawing, with the bonds of a cleavage struck through.

    The molfile carries the layout somebody already drew, so there is nothing
    to compute here beyond fitting it to the widget: no coordinate generation,
    and the picture matches the one on the database's own page.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._structure: Structure | None = None
        self._fragment: Fragment | None = None
        self.setMinimumHeight(150)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    # -- content ------------------------------------------------------------- #
    def set_structure(self, structure: Structure | None) -> None:
        self._structure = structure
        self._fragment = None
        self.update()

    def set_fragment(self, fragment: Fragment | None) -> None:
        """Highlight one piece and strike the bonds that would free it."""
        self._fragment = fragment
        self.update()

    # -- painting ------------------------------------------------------------ #
    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(theme.background()))
        structure = self._structure
        if structure is None or not structure.atoms:
            self._say(painter, "No structure for this lipid")
            return

        points = self._layout(structure)
        kept = self._fragment.atoms if self._fragment else None
        cuts = set(self._fragment.cuts) if self._fragment else set()

        faded = QtGui.QColor(theme.ink_faint())
        strong = QtGui.QColor(theme.foreground())
        accent = QtGui.QColor(theme.accent())

        for index, bond in enumerate(structure.bonds):
            inside = kept is None or (bond.a in kept and bond.b in kept)
            colour = accent if (kept is not None and inside) else (
                strong if kept is None else faded)
            self._draw_bond(painter, points[bond.a], points[bond.b],
                            bond.order, colour)
            if index in cuts:
                self._draw_cut(painter, points[bond.a], points[bond.b])

        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        for index, atom in enumerate(structure.atoms):
            if atom.element in IMPLICIT and not atom.charge:
                continue
            inside = kept is None or index in kept
            painter.setPen(QtGui.QPen(
                accent if (kept is not None and inside) else
                (strong if kept is None else faded)))
            label = atom.element
            if atom.charge:
                label += "+" if atom.charge > 0 else "−"
            point = points[index]
            box = metrics.boundingRect(label).adjusted(-2, -1, 2, 1)
            box.moveCenter(point.toPoint())
            painter.fillRect(box, QtGui.QColor(theme.background()))
            painter.drawText(box, QtCore.Qt.AlignmentFlag.AlignCenter, label)
        painter.end()

    def _say(self, painter: QtGui.QPainter, text: str) -> None:
        painter.setPen(QtGui.QPen(QtGui.QColor(theme.muted())))
        painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

    def _layout(self, structure: Structure) -> list[QtCore.QPointF]:
        """Fit the drawing to the widget, keeping its proportions."""
        xs = [a.x for a in structure.atoms]
        ys = [a.y for a in structure.atoms]
        margin = 16.0
        width = max(max(xs) - min(xs), 1e-6)
        height = max(max(ys) - min(ys), 1e-6)
        scale = min((self.width() - 2 * margin) / width,
                    (self.height() - 2 * margin) / height)
        offset_x = (self.width() - width * scale) / 2 - min(xs) * scale
        offset_y = (self.height() - height * scale) / 2 + max(ys) * scale
        # the molfile counts y upwards and the widget counts it down
        return [QtCore.QPointF(a.x * scale + offset_x, offset_y - a.y * scale)
                for a in structure.atoms]

    def _draw_bond(self, painter, start, end, order: int,
                   colour: QtGui.QColor) -> None:
        pen = QtGui.QPen(colour)
        pen.setWidthF(1.4)
        painter.setPen(pen)
        if order < 2:
            painter.drawLine(start, end)
            return
        # a double bond as two lines, offset along the bond's own normal
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        nx, ny = -dy / length * 1.8, dx / length * 1.8
        for sign in ((1, -1) if order == 2 else (0, 1, -1))[:order]:
            painter.drawLine(
                QtCore.QPointF(start.x() + nx * sign, start.y() + ny * sign),
                QtCore.QPointF(end.x() + nx * sign, end.y() + ny * sign))

    def _draw_cut(self, painter, start, end) -> None:
        """A stroke across the bond, where it would break."""
        pen = QtGui.QPen(QtGui.QColor(theme.danger()))
        pen.setWidthF(2.0)
        painter.setPen(pen)
        mid = QtCore.QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        nx, ny = -dy / length * 6.0, dx / length * 6.0
        painter.drawLine(QtCore.QPointF(mid.x() + nx, mid.y() + ny),
                         QtCore.QPointF(mid.x() - nx, mid.y() - ny))
