"""Acceptance criteria for the component under review."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..components import AcceptanceLimits
from .collapsible import CollapsibleGroup


class AcceptancePanel(CollapsibleGroup):
    """
    The limits a row has to satisfy to pass.

    Every field of zero is off, so nothing is flagged until the criteria have
    actually been stated.
    """

    sigApplyComponent = QtCore.pyqtSignal(object)   # AcceptanceLimits
    sigApplyAll = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__("Acceptance", parent)
        form = QtWidgets.QFormLayout(self.body)
        form.setContentsMargins(8, 6, 8, 6)
        form.setVerticalSpacing(4)

        self.rt = QtWidgets.QDoubleSpinBox()
        self.rt.setRange(0.0, 60.0)
        self.rt.setDecimals(3)
        self.rt.setSingleStep(0.05)
        self.rt.setSuffix(" min")
        self.rt.setToolTip("Largest allowed shift from the expected retention time")
        form.addRow("Max ΔRT", self.rt)

        self.accuracy = QtWidgets.QDoubleSpinBox()
        self.accuracy.setRange(0.0, 200.0)
        self.accuracy.setSuffix(" %")
        self.accuracy.setToolTip(
            "Largest allowed departure from 100% accuracy, for samples with a "
            "known concentration")
        form.addRow("Max accuracy dev.", self.accuracy)

        self.snr = QtWidgets.QDoubleSpinBox()
        self.snr.setRange(0.0, 10000.0)
        self.snr.setDecimals(1)
        self.snr.setToolTip("Smallest acceptable signal-to-noise")
        form.addRow("Min S/N", self.snr)

        buttons = QtWidgets.QVBoxLayout()
        self.btn_component = QtWidgets.QPushButton("Apply to component")
        self.btn_all = QtWidgets.QPushButton("Apply to every component")
        buttons.addWidget(self.btn_component)
        buttons.addWidget(self.btn_all)
        form.addRow(buttons)

        self.btn_component.clicked.connect(
            lambda: self.sigApplyComponent.emit(self.limits()))
        self.btn_all.clicked.connect(lambda: self.sigApplyAll.emit(self.limits()))

    def set_limits(self, limits: AcceptanceLimits, overridden: bool) -> None:
        self.rt.setValue(limits.rt_tolerance)
        self.accuracy.setValue(limits.accuracy_tolerance)
        self.snr.setValue(limits.min_snr)
        self.setTitle("Acceptance — component override" if overridden
                      else "Acceptance — method defaults")

    def limits(self) -> AcceptanceLimits:
        return AcceptanceLimits(rt_tolerance=self.rt.value(),
                                accuracy_tolerance=self.accuracy.value(),
                                min_snr=self.snr.value())
