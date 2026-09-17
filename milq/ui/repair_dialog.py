"""
The written precursors a formula contradicts, and the repair of them.

`components.fill_formulas` refuses a formula whose mass disagrees with the
precursor the method already carries, and `health.check_method` reports the
disagreement as serious — both of them stop at saying that one of the two
numbers is wrong. On the method this was written against, all sixteen
refusals were the *precursor*: masses typed to one decimal, one dropped
digit, two rows a whole dalton out.

This is the other way out of that stand-off. It lists each disagreement with
both masses, the difference in Da and in ppm, and what the extraction window
does, and writes the formula and the precursor together for the rows that are
ticked — each one an entry in the audit trail. Nothing else is touched,
and a row that is not ticked is not touched at all.

The pre-ticking is the whole argument of the dialog: a sub-dalton difference
is one compound written down two ways and the repair is arithmetic, so it is
offered ready to apply; a whole dalton is two different compounds and no
amount of arithmetic says which one the instrument acquired, so it is offered
unticked and somebody has to say.

A whole-dalton row has a third answer, and on the real method it is the right
one: **rename it**. The instrument acquired the mass that was written — that
number is the channel — so where the two disagree by a whole dalton it is the
name that is wrong, and the *Rename to* column offers the names whose formula
does match that mass, its own class first. Choosing one writes the name and
its formula and leaves every number alone, so nothing is reprocessed and no
result goes stale: what it buys is a row whose formula agrees with its own
mass, which is what a lock mass is made of.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..audit import NAME_RENAMED, PRECURSOR_REPAIRED
from ..chemistry import NameSuggestion
from ..components import WHOLE_DALTON, Component, PrecursorRepair
from ..matching import PRECURSOR_MATCH_DA
from ..session import Session
from .help_window import describe, open_manual

HELP_PAGE = "method-workspace"

#: how wide the *Rename to* column is, in pixels. Fixed rather than fitted:
#: a combo asks for the width of its longest entry, and a name with its
#: formula and its error is a hundred characters — left to fit, the column
#: took two thirds of the table and pushed the note off the far side, which
#: is what rendering it showed. The chosen entry is elided and its whole text
#: is the combo's tooltip.
RENAME_WIDTH = 300
#: and how many characters of a name the combo asks to be able to show
RENAME_CHARACTERS = 22

#: what the combo says when nothing is chosen, which is how every row starts
KEEP_THE_NAME = "— keep the name —"
#: and what it says where the class has nothing at that mass
NOTHING_OFFERED = "— no name at this mass —"


def _window(bounds: tuple[float, float]) -> str:
    return f"{bounds[0]:,.4f}–{bounds[1]:,.4f}"


def suggestion_label(suggestion: NameSuggestion) -> str:
    """
    One name as the combo shows it: the name, its formula, its error.

    The error is what makes the row reviewable. A name offered for a mass
    written to four decimals may match it exactly or may only match the
    integer — those are different claims, and the ppm is where the difference
    shows.
    """
    said = (f"{suggestion.name} · {suggestion.formula}, "
            f"{suggestion.error_ppm:+,.1f} ppm")
    if not suggestion.in_class:
        said += f" · {suggestion.source}, another class"
    return said


class RepairPrecursorsDialog(QtWidgets.QDialog):
    """Tick the precursors to take from the formula, then apply."""

    COLUMNS = ["Use", "Component", "Written", "From the formula", "Formula",
               "Δ mDa", "Δ ppm", "Rename to", "Window now", "Window after",
               "Note"]

    def __init__(self, session: Session, repairs: list[PrecursorRepair],
                 components: list[Component] | None = None, parent=None,
                 database=None):
        super().__init__(parent)
        self.session = session
        self.repairs = list(repairs)
        #: the table the workspace is holding, written back whole when a
        #: repair is applied; None means the method's own list is already the
        #: one being repaired
        self._components = components
        self.applied: list[PrecursorRepair] = []
        #: the rows renamed instead, as (repair, name chosen, name before)
        self.renamed: list[tuple[PrecursorRepair, NameSuggestion, str]] = []
        #: the names offered per row, by row number
        self.suggestions: dict[int, list[NameSuggestion]] = {}
        self._combos: dict[int, QtWidgets.QComboBox] = {}
        self.setWindowTitle("Repair precursors from formulas")
        self.resize(1240, 480)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            f"Each row's formula gives a mass that its written precursor "
            f"contradicts. Applying a row writes <b>both</b> the formula and "
            f"the precursor, and records the change. Rows under "
            f"{WHOLE_DALTON:g} Da apart are the same compound written to "
            f"fewer places and are ticked; a row a whole dalton or more out "
            f"is a different compound or a mistyped digit — which of the name "
            f"and the mass is wrong is not something arithmetic can settle, "
            f"so it is offered unticked, and <b>Rename to</b> is the other "
            f"answer for it: the mass is what the instrument acquired, so the "
            f"name may be the mistake, and the column offers the names whose "
            f"formula matches that mass. A precursor is what "
            f"picks the acquisition channel, within ±{PRECURSOR_MATCH_DA:g} Da "
            f"of the channel's own, and — where the row has no fragment — what "
            f"the extraction window is built from: process the batch again "
            f"afterwards. A rename moves no number and needs no reprocessing.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.table = QtWidgets.QTableWidget(len(self.repairs), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            len(self.COLUMNS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # the Note column holds a sentence: elided it says nothing, so it
        # wraps and the row grows to fit it (see the folder dialog, where the
        # same thing was found by rendering rather than by reading)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        rename = self.COLUMNS.index("Rename to")
        for row, repair in enumerate(self.repairs):
            tick = QtWidgets.QTableWidgetItem()
            tick.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                          | QtCore.Qt.ItemFlag.ItemIsEnabled)
            tick.setCheckState(QtCore.Qt.CheckState.Checked if repair.offered
                               else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, tick)
            ppm = repair.error_ppm
            cells = [
                repair.component.name,
                f"{repair.written:,.4f}",
                f"{repair.theoretical:,.4f}",
                repair.formula,
                f"{repair.difference * 1000:+,.1f}",
                "—" if ppm is None else f"{ppm:+,.1f}",
                None,                       # the rename column, filled below
                _window(repair.window_before),
                _window(repair.window_after),
                repair.note,
            ]
            for column, text in enumerate(cells, start=1):
                if text is None:
                    continue
                item = QtWidgets.QTableWidgetItem(text)
                if column == len(self.COLUMNS) - 1:
                    item.setToolTip(text)
                if column in (2, 3, 5, 6):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
            self._offer_names(row, repair, rename, database)
        for column in range(len(self.COLUMNS) - 1):
            self.table.resizeColumnToContents(column)
        self.table.setColumnWidth(rename, RENAME_WIDTH)
        # a tick and a rename are two answers to the same row, so each undoes
        # the other rather than leaving the row saying both
        self.table.itemChanged.connect(self._ticked)
        layout.addWidget(self.table, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        ).setText("Apply the ticked repairs")
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply
                            ).clicked.connect(self.apply_selected)
        layout.addWidget(self.buttons)

    # -- the names offered --------------------------------------------------- #
    def _offer_names(self, row: int, repair: PrecursorRepair, column: int,
                     database) -> None:
        """
        Fill one row's *Rename to* cell.

        Only a whole-dalton row is asked: under half a dalton the two masses
        are one compound and a rename would be answering a question nobody
        asked. A row the search has nothing for says so in words rather than
        opening an empty combo, because an empty combo reads as a thing that
        has not loaded yet.
        """
        if not repair.whole_dalton:
            self.table.setItem(row, column, QtWidgets.QTableWidgetItem(""))
            return
        offered = repair.suggestions(database)
        self.suggestions[row] = offered
        if not offered:
            item = QtWidgets.QTableWidgetItem(NOTHING_OFFERED)
            item.setToolTip(
                "No name in this class, and nothing in LIPID MAPS, has a "
                "formula whose mass is the one written here.")
            self.table.setItem(row, column, item)
            return
        combo = QtWidgets.QComboBox()
        combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(RENAME_CHARACTERS)
        combo.addItem(KEEP_THE_NAME, None)      # nothing is pre-selected
        for index, suggestion in enumerate(offered):
            combo.addItem(suggestion_label(suggestion), index)
        combo.setCurrentIndex(0)
        combo.setToolTip("\n".join(suggestion_label(s) for s in offered))
        combo.currentIndexChanged.connect(
            lambda _index, at=row: self._renamed(at))
        self._combos[row] = combo
        self.table.setCellWidget(row, column, combo)

    def _renamed(self, row: int) -> None:
        """A name chosen is a row that is not having its mass moved."""
        if self.chosen_name(row) is None:
            return
        item = self.table.item(row, 0)
        if item is not None and item.checkState() == QtCore.Qt.CheckState.Checked:
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def _ticked(self, item: QtWidgets.QTableWidgetItem) -> None:
        """And a mass ticked is a row that is not being renamed."""
        if item.column() != 0 or item.checkState() != QtCore.Qt.CheckState.Checked:
            return
        combo = self._combos.get(item.row())
        if combo is not None and combo.currentIndex() > 0:
            combo.setCurrentIndex(0)

    def chosen_name(self, row: int) -> NameSuggestion | None:
        """The name chosen on one row, or None where the name stands."""
        combo = self._combos.get(row)
        if combo is None:
            return None
        index = combo.currentData()
        offered = self.suggestions.get(row, [])
        return offered[index] if index is not None and index < len(offered) else None

    def renames(self) -> list[tuple[int, PrecursorRepair, NameSuggestion]]:
        """Every row with a name chosen, in the order they are shown."""
        out = []
        for row, repair in enumerate(self.repairs):
            suggestion = self.chosen_name(row)
            if suggestion is not None:
                out.append((row, repair, suggestion))
        return out

    def showEvent(self, event):
        """
        Fit the rows once the columns have their real width.

        `resizeRowsToContents` measures a wrapped sentence against the width
        the column has *now*, and until the dialog is shown the stretched
        Note column has no width worth measuring against — the rows come out
        one line tall and the sentence is cut off.
        """
        super().showEvent(event)
        self.table.resizeRowsToContents()

    # -- the rows ---------------------------------------------------------------- #
    def selected(self) -> list[PrecursorRepair]:
        chosen = []
        for row, repair in enumerate(self.repairs):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == QtCore.Qt.CheckState.Checked:
                chosen.append(repair)
        return chosen

    def apply_selected(self) -> int:
        """
        Write the ticked repairs and the chosen names, one audit entry each;
        returns how many rows changed.

        The entries are written before the method is replaced, so that a
        trail read afterwards shows the masses in the order they changed
        rather than a single line saying the table moved.
        """
        chosen = self.selected()
        for repair in chosen:
            before, after = repair.audit_before, repair.audit_after
            repair.apply()
            self.session.record(
                PRECURSOR_REPAIRED, f"{repair.component.name} · precursor",
                before=before, after=after, note=repair.audit_note)
        renamed = []
        for _row, repair, suggestion in self.renames():
            before = repair.component.name
            repair.apply_rename(suggestion)
            self.session.record(
                NAME_RENAMED, f"{before} · name", before=before,
                after=suggestion.name, note=repair.rename_note(suggestion))
            renamed.append((repair, suggestion, before))
        self.applied, self.renamed = chosen, renamed
        if chosen or renamed:
            if self._components is not None:
                self.session.method.replace_all(self._components)
            # the same call the component table makes when a cell is typed
            # in: it drops the conditioned traces, which were extracted
            # through the windows that have just moved
            self.session.notify_method_changed()
        self.accept()
        return len(chosen) + len(renamed)

    # -- what to say afterwards --------------------------------------------------- #
    def summary(self) -> str:
        """One line for the status bar, including what is now out of date."""
        if not self.applied and not self.renamed:
            return "Nothing was changed."
        said = []
        if self.applied:
            said.append(f"{len(self.applied)} precursor(s) repaired from their "
                        f"formulas")
            moved = sum(1 for r in self.applied if r.moves_window)
            if moved:
                said.append(f"{moved} extraction window(s) moved")
        if self.renamed:
            said.append(f"{len(self.renamed)} component(s) renamed to the name "
                        f"their written mass carries, no number changed")
        names = {r.component.name for r in self.applied}
        stale = sum(1 for r in self.session.results if r.component in names)
        if stale:
            said.append(f"{stale} result row(s) were integrated with the old "
                        f"masses — process the batch again")
        # a renamed component leaves its own results behind under the name
        # they were measured under, which is a different staleness: the
        # numbers are right and the label on them is the old one
        old = {before for _repair, _suggestion, before in self.renamed}
        orphaned = sum(1 for r in self.session.results if r.component in old)
        if orphaned:
            said.append(f"{orphaned} result row(s) still carry the old name")
        return ", ".join(said) + "."
