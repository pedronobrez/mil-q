"""The results table follows the component tree, and All components undoes it."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq.components import Component
from milq.quantify import PeakResult, ResultsSet
from milq.samples import SampleEntry
from milq.session import Session
from milq.ui import style
from milq.ui.analytics import ALL_COMPONENTS, ROLE_NAME


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.apply(app)
    yield app


def loaded_entry(name):
    """An entry with a live channel, so the grid has something to extract."""
    from tests.test_quantify import TracedChannel
    from tests.test_matching import Sample

    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([
        TracedChannel(1, 538.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
        TracedChannel(2, 566.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
        TracedChannel(3, 647.5, 50.0, 700.0, 0.0, 10.0, n=200, apex=5.0),
    ])
    return entry


@pytest.fixture
def workspace(qapp):
    from milq.ui.analytics import AnalyticsWorkspace

    session = Session()
    session.set_components([
        Component(name="Cer A", precursor=538.5, fragment=264.2686, group="Cer"),
        Component(name="Cer B", precursor=566.5, fragment=264.2686, group="Cer"),
        Component(name="SM A", precursor=647.5, fragment=184.0733, group="SM"),
    ])
    session.entries = [loaded_entry(f"S{i}") for i in range(4)]
    results = ResultsSet()
    for entry in session.entries:
        for component in session.method.components:
            results.results.append(PeakResult(
                sample_key=entry.key, sample_name=entry.name,
                component=component.name, group=component.group,
                area=1000.0, height=100.0))
    session.results = results
    widget = AnalyticsWorkspace(session)
    widget.resize(1400, 800)
    yield widget
    widget.close()


def select(workspace, name):
    it = QtWidgets.QTreeWidgetItemIterator(workspace.component_tree)
    while it.value():
        if it.value().data(0, ROLE_NAME) == name:
            workspace.component_tree.setCurrentItem(it.value())
            return True
        it += 1
    return False


# -- the tree entry --------------------------------------------------------------- #
def test_all_components_is_the_first_entry(qapp, workspace):
    first = workspace.component_tree.topLevelItem(0)
    assert first.data(0, ROLE_NAME) == ALL_COMPONENTS
    assert first.text(0) == "All components"


def test_it_is_what_a_fresh_workspace_shows(qapp, workspace):
    assert workspace._all_components
    assert workspace.results.proxy.component == ""


# -- the filter ------------------------------------------------------------------- #
def test_choosing_a_component_narrows_the_table(qapp, workspace):
    assert workspace.results.proxy.rowCount() == 12
    assert select(workspace, "Cer B")
    assert workspace.results.proxy.rowCount() == 4
    rows = [workspace.results.model.result_at(
                workspace.results.proxy.mapToSource(
                    workspace.results.proxy.index(r, 0)).row()).component
            for r in range(workspace.results.proxy.rowCount())]
    assert set(rows) == {"Cer B"}


def test_the_summary_names_the_component_it_is_showing(qapp, workspace):
    select(workspace, "Cer B")
    assert workspace.results.summary.text().startswith("Cer B · 4 row(s)")


def test_going_back_to_all_components_restores_the_table(qapp, workspace):
    select(workspace, "Cer B")
    assert select(workspace, ALL_COMPONENTS)
    assert workspace.results.proxy.rowCount() == 12
    assert workspace.results.proxy.component == ""


def test_the_text_filter_still_applies_on_top(qapp, workspace):
    select(workspace, "Cer B")
    workspace.results.filter_edit.setText("S2")
    assert workspace.results.proxy.rowCount() == 1


# -- the grid --------------------------------------------------------------------- #
def test_all_components_covers_every_peak(qapp, workspace):
    select(workspace, ALL_COMPONENTS)
    assert workspace.grid.item_count == 3 * 4


def test_only_the_page_in_view_is_built(qapp, workspace):
    built = []
    original = workspace._grid_item
    workspace._grid_item = lambda c, e: built.append((c.name, e.key)) or original(c, e)
    select(workspace, ALL_COMPONENTS)
    # a real batch is 141 components across 26 samples; building all of them to
    # show nine is a hundred seconds of work
    assert len(built) <= workspace.grid.page_size


def test_one_component_still_shows_every_sample(qapp, workspace):
    select(workspace, "SM A")
    assert workspace.grid.item_count == 4


# -- stacked chromatograms -------------------------------------------------------- #
@pytest.fixture
def area(qapp):
    import numpy as np
    from milq.ui.chrom_area import ChromatogramArea
    from milq.ui.plots import Trace, colour

    host = QtWidgets.QWidget()
    host.setFixedSize(1000, 900)
    box = QtWidgets.QVBoxLayout(host)
    box.setContentsMargins(0, 0, 0, 0)
    widget = ChromatogramArea()
    box.addWidget(widget)
    host.show()
    x = np.linspace(0, 22, 400)
    widget._host = host          # keep it alive for the duration of the test
    widget._make = lambda n: [
        Trace(f"t{i}", f"{i:02d}", x, np.exp(-((x - 11) ** 2)) * 1e6, colour(i))
        for i in range(n)]
    yield widget
    host.close()


def test_a_few_stacked_panes_share_the_height(qapp, area):
    area.set_traces(area._make(3))
    area.set_stacked(True)
    qapp.processEvents()
    assert not area.scroll.verticalScrollBar().maximum()


def test_many_stacked_panes_scroll_instead_of_shrinking(qapp, area):
    from milq.ui.chrom_area import MIN_STACKED_PANE

    area.set_traces(area._make(26))
    area.set_stacked(True)
    qapp.processEvents()
    # twenty-six panes in one plot's height is thirty pixels each: one tick
    # label, no axis, the trace a smear
    assert min(v.height() for v in area.views) >= MIN_STACKED_PANE - 2
    assert area.scroll.verticalScrollBar().maximum() > 0


def test_unstacking_gives_the_height_back(qapp, area):
    area.set_traces(area._make(26))
    area.set_stacked(True)
    qapp.processEvents()
    area.set_stacked(False)
    qapp.processEvents()
    assert len(area.views) == 1
    assert area.views[0].height() == pytest.approx(area.height(), abs=2)
    assert not area.scroll.verticalScrollBar().maximum()


# -- the channel tree -------------------------------------------------------- #
def test_collapse_all_folds_the_samples_but_keeps_the_files(qapp):
    from milq.session import Session
    from milq.ui.explorer import ExplorerWorkspace

    workspace = ExplorerWorkspace(Session())
    tree = workspace.tree
    wiff = QtWidgets.QTreeWidgetItem(tree, ["a.wiff"])
    sample = QtWidgets.QTreeWidgetItem(wiff, ["01"])
    QtWidgets.QTreeWidgetItem(sample, ["TOF MS"])
    tree.expandAll()
    assert sample.isExpanded()

    workspace.collapse_samples()
    # eighty channels per injection buries the list; the file names stay
    assert not sample.isExpanded()
    assert wiff.isExpanded()
    workspace.close()


# -- getting a closed panel back --------------------------------------------- #


def test_the_side_panels_can_be_reopened_from_the_menu(qapp):
    """
    A dock has a close button and, until this, nothing that undid it.

    Qt offers the list in a context menu on the toolbar, which is not
    somewhere anyone looks: closing the tree of samples and channels left the
    workspace looking broken with no way back.
    """
    from milq.ui.explorer import ExplorerWorkspace

    workspace = ExplorerWorkspace(Session())
    workspace.show()          # a dock of a hidden window is never "visible"
    qapp.processEvents()
    actions = workspace.build_actions()["View"]
    by_text = {a.text(): a for a in actions if not a.isSeparator()}

    assert "Samples and channels" in by_text
    assert "Side panels" in by_text

    for dock, action in ((workspace.dock_tree, by_text["Samples and channels"]),
                         (workspace.dock_side, by_text["Side panels"])):
        assert action.isCheckable()
        dock.setVisible(False)
        qapp.processEvents()
        assert not action.isChecked(), "the menu should show the dock as hidden"
        action.trigger()
        qapp.processEvents()
        assert dock.isVisible(), "triggering the action should bring it back"

    workspace.close()


def test_the_reopen_actions_work_without_the_menu_open(qapp):
    """They carry shortcuts, which only fire if the window owns the action."""
    from milq.ui.explorer import ExplorerWorkspace

    workspace = ExplorerWorkspace(Session())
    owned = {a.text() for a in workspace.actions()}
    assert {"Samples and channels", "Side panels"} <= owned
    workspace.close()


def test_the_workspace_does_not_grow_a_status_bar_of_its_own(qapp):
    """
    It is a QMainWindow inside a tab, and calling statusBar() on one creates
    the bar. Every message was then printed twice: once in the strip inside
    the tab, once in the shell's own at the bottom of the window.
    """
    from milq.ui.explorer import ExplorerWorkspace

    workspace = ExplorerWorkspace(Session())
    seen = []
    workspace.sigStatus.connect(seen.append)
    workspace._update_status("hello")
    qapp.processEvents()

    assert seen == ["hello"]
    assert workspace.findChild(QtWidgets.QStatusBar) is None
    workspace.close()
