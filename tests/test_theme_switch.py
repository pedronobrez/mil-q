"""Following the system theme, and the folding panels under the component list."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtWidgets

from milq.components import Component
from milq.session import Session
from milq.ui import style, theme
from milq.ui.collapsible import CollapsibleGroup


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def light(qapp):
    palette = qapp.palette()
    palette.setColor(QtGui.QPalette.ColorRole.Window,
                     QtGui.QColor(style.LIGHT["canvas"]))
    qapp.setPalette(palette)
    style.apply(qapp)
    yield qapp


# -- following the system ------------------------------------------------------- #
def test_the_watcher_announces_a_change_once(light, qapp, monkeypatch):
    watcher = style.ThemeWatcher(qapp)
    seen = []
    watcher.sigThemeChanged.connect(lambda: seen.append(style.is_dark()))

    monkeypatch.setattr(style, "is_dark", lambda: True)
    watcher._check()
    watcher._check()          # the same change arriving twice
    assert seen == [True]

    monkeypatch.setattr(style, "is_dark", lambda: False)
    watcher._check()
    assert seen == [True, False]


def test_a_change_reapplies_the_sheet(light, qapp, monkeypatch):
    watcher = style.ThemeWatcher(qapp)
    monkeypatch.setattr(style, "is_dark", lambda: True)
    watcher._check()
    assert style.DARK["canvas"] in qapp.styleSheet()


def test_the_theme_is_read_from_the_style_hints_not_the_palette(light, qapp):
    """
    Applying our own palette makes it explicit, and Qt stops updating it when
    the system switches — so the palette would only ever report our own last
    answer. Where the platform states a scheme, that is what decides.
    """
    scheme = qapp.styleHints().colorScheme()
    if scheme == QtCore.Qt.ColorScheme.Unknown:
        pytest.skip("this platform states no colour scheme")
    assert style.is_dark() == (scheme == QtCore.Qt.ColorScheme.Dark)


def test_a_plot_takes_the_new_colours(light, qapp, monkeypatch):
    from milq.ui.plots import ChromatogramView

    view = ChromatogramView()
    assert view.plot.backgroundBrush().color().name() == style.LIGHT["surface"]
    monkeypatch.setattr(style, "is_dark", lambda: True)
    theme.apply_defaults()
    view.retheme()
    assert view.plot.backgroundBrush().color().name() == style.DARK["surface"]


# -- the folding panels --------------------------------------------------------- #
def test_a_group_hides_its_body_rather_than_disabling_it(qapp):
    group = CollapsibleGroup("Section")
    label = QtWidgets.QLabel("inside")
    QtWidgets.QVBoxLayout(group.body).addWidget(label)
    group.show()
    qapp.processEvents()
    assert group.body.isVisible()
    group.set_expanded(False)
    # a checkable QGroupBox only disables its children, which would leave the
    # space taken by a panel nobody can use
    assert not group.body.isVisible()
    group.set_expanded(True)
    qapp.processEvents()
    # and it comes back usable, not merely visible
    assert group.body.isVisible()
    assert group.body.isEnabled()
    assert label.isEnabled()
    group.close()


def test_the_fold_state_survives_a_restart(qapp, tmp_path):
    settings = QtCore.QSettings(str(tmp_path / "s.ini"),
                                QtCore.QSettings.Format.IniFormat)
    group = CollapsibleGroup("Section")
    group.set_expanded(True)
    group.save(settings, "section")

    reopened = CollapsibleGroup("Section")
    reopened.restore(settings, "section")
    assert reopened.expanded


def test_the_panels_start_folded_so_the_list_has_room(qapp):
    from milq.ui.analytics import AnalyticsWorkspace

    from milq.ui.settings import settings as make_settings

    settings = make_settings()   # the suite's own INI file, never the real store
    settings.remove("analytics/integration_open")
    settings.remove("analytics/acceptance_open")

    session = Session()
    session.set_components([Component(name=f"C{i}", precursor=500.0 + i)
                            for i in range(40)])
    workspace = AnalyticsWorkspace(session)
    workspace.resize(1200, 700)
    workspace.show()
    qapp.processEvents()
    assert not workspace.integration.expanded
    assert not workspace.acceptance.expanded
    folded = workspace.component_tree.height()

    workspace.integration.set_expanded(True)
    qapp.processEvents()
    assert workspace.component_tree.height() < folded
    workspace.close()
