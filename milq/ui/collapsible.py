"""A group box whose contents fold away."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class CollapsibleGroup(QtWidgets.QGroupBox):
    """
    A titled section that can be folded to its heading.

    The panels below the component list are only wanted while their settings
    are being changed; the rest of the time they crowd out the list itself.
    Folding is per section and remembered, so the layout an analyst arrives at
    is the one they get back.

    Content goes into `body`, not into the group box: a checkable QGroupBox
    disables its children rather than hiding them, which would leave the space
    taken by a panel nobody can use.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                           QtWidgets.QSizePolicy.Policy.Maximum)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 0)
        outer.setSpacing(0)
        self.body = QtWidgets.QWidget()
        outer.addWidget(self.body)

        self.toggled.connect(self._show_body)

    def _show_body(self, expanded: bool) -> None:
        self.body.setVisible(expanded)

    # -- state ------------------------------------------------------------------ #
    @property
    def expanded(self) -> bool:
        return self.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.setChecked(expanded)
        self._show_body(expanded)

    def restore(self, settings: QtCore.QSettings, key: str,
                default: bool = False) -> None:
        self.set_expanded(settings.value(key, default, type=bool))

    def save(self, settings: QtCore.QSettings, key: str) -> None:
        settings.setValue(key, self.expanded)
