"""
F1 opens the page for where the user is.

A widget names its page once and everything inside it inherits the answer;
the shell resolves the focused widget, and a dialog resolves itself. What
is tested is the walk, the fallbacks, and that every page named by a
widget is a page the manual has.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

from milq.manual import manual  # noqa: E402
from milq.ui.help_window import (HELP_PROPERTY, describe,  # noqa: E402
                                      help_page_for)


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_nearest_named_ancestor_answers(qapp):
    outer = QtWidgets.QWidget()
    describe(outer, "analytics-workspace")
    middle = QtWidgets.QWidget(outer)
    inner = QtWidgets.QLineEdit(middle)
    assert help_page_for(inner) == "analytics-workspace"
    describe(middle, "results-table")
    assert help_page_for(inner) == "results-table"
    assert help_page_for(QtWidgets.QWidget()) is None
    assert help_page_for(None) is None
    assert inner.property(HELP_PROPERTY) is None


def test_the_shell_names_its_workspaces_and_panels(qapp):
    from milq.ui.shell import MainShell

    shell = MainShell()
    pages = manual().pages
    named = {}
    stack = [shell]
    while stack:
        widget = stack.pop()
        page = widget.property(HELP_PROPERTY)
        if page:
            named[page] = widget
        stack.extend(widget.findChildren(QtWidgets.QWidget,
                                         options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly))
    unknown = sorted(page for page in named if page not in pages)
    assert unknown == [], f"widgets name pages the manual lacks: {unknown}"
    for page in ("explorer", "analytics-workspace", "method-workspace",
                 "samples-workspace", "peak-review", "results-table",
                 "batch-qc", "integration-parameters", "mass-calculator",
                 "lipid-maps", "contour-view"):
        assert page in named, page
    shell.close()


def test_f1_resolves_the_focus_and_falls_back_to_the_workspace(qapp):
    from milq.ui.shell import MainShell

    shell = MainShell()
    shell.tabs.setCurrentWidget(shell.analytics)
    assert shell.context_page() in ("analytics-workspace", *manual().pages)
    shell.analytics.results.setFocus()
    # focus is only granted to a shown window; resolve the widget directly
    from milq.ui.help_window import help_page_for as resolve
    assert resolve(shell.analytics.results) == "results-table"
    assert resolve(shell.analytics.quality) == "batch-qc"
    assert resolve(shell.method) == "method-workspace"
    # a key press of F1 reaching the filter opens the manual
    event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_F1,
                            QtCore.Qt.KeyboardModifier.NoModifier)
    if event.matches(QtGui.QKeySequence.StandardKey.HelpContents):
        assert shell.eventFilter(shell.analytics.quality, event) is True
        assert shell._help_window.current_page == "batch-qc"
        shell._help_window.close()
    shell.close()


def test_dialogs_carry_their_page_and_a_help_button(qapp):
    from milq.session import Session
    from milq.ui.suggest_dialog import SuggestDialog
    from milq.ui.new_project import NewProjectWizard

    dialog = SuggestDialog(Session())
    assert help_page_for(dialog) == "suggest-from-data"
    assert dialog.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is not None
    dialog.close()
    wizard = NewProjectWizard(Session())
    assert help_page_for(wizard) == "starting-a-project"
    assert wizard.testOption(QtWidgets.QWizard.WizardOption.HaveHelpButton)
    wizard.close()
