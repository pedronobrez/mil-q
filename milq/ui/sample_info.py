"""Sample and active-channel information panel."""

from __future__ import annotations

from PyQt6 import QtWidgets


class SampleInfoPanel(QtWidgets.QWidget):
    """Injection metadata plus the parameters of the selected experiment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Field", "Value"])
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

        self.copy_button = QtWidgets.QPushButton("Copy all")
        self.copy_button.clicked.connect(self._copy)
        layout.addWidget(self.copy_button)

        self.clear()

    def clear(self) -> None:
        self.tree.clear()
        placeholder = QtWidgets.QTreeWidgetItem(self.tree, ["—", "no sample loaded"])
        placeholder.setDisabled(True)

    def show_sample(self, sample, channel=None) -> None:
        """Fill the panel with the sample and, when given, the channel."""
        self.tree.clear()

        group = QtWidgets.QTreeWidgetItem(self.tree, ["Sample", ""])
        for key, value in sample.metadata().items():
            QtWidgets.QTreeWidgetItem(group, [key, value])
        group.setExpanded(True)

        if channel is not None:
            info = channel.info
            group = QtWidgets.QTreeWidgetItem(self.tree, ["Active channel", ""])
            rows = [
                ("Index", str(info.index)),
                ("Name", info.name),
                ("Type", info.experiment_type),
                ("Polarity", info.polarity),
                ("Precursor", "—" if info.precursor is None else f"{info.precursor:.4f}"),
                ("Mass range", f"{info.start_mass:.1f} – {info.end_mass:.1f}"),
                ("Scans", str(info.n_scans)),
            ]
            rt = channel.rt
            if rt.size:
                rows.append(("Time range", f"{rt[0]:.3f} – {rt[-1]:.3f} min"))
            for key, value in rows:
                QtWidgets.QTreeWidgetItem(group, [key, value])
            group.setExpanded(True)

            parameters = channel.parameters()
            if parameters:
                group = QtWidgets.QTreeWidgetItem(self.tree, ["Method parameters", ""])
                for key, value in parameters.items():
                    QtWidgets.QTreeWidgetItem(group, [key, value])
                group.setExpanded(False)

        self.tree.resizeColumnToContents(0)

    def _copy(self) -> None:
        lines = []

        def walk(item, depth=0):
            lines.append("  " * depth + f"{item.text(0)}\t{item.text(1)}".rstrip())
            for i in range(item.childCount()):
                walk(item.child(i), depth + 1)

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
