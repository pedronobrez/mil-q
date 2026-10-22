"""
Which sample a point is.

The Batch QC charts draw one circle per injection, and a circle that is out
is useless until it has a name. Hovering one names it, says where it sits
in the run, what it measured and whether — and on which rule — the chart
calls it out; and draws it larger, so the text is visibly about that point.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from milq.components import Component  # noqa: E402
from milq.mass_drift import MassDrift, MassPoint, MassTrend  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.quantify import PeakResult, ResultsSet  # noqa: E402
from milq.samples import QC, SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.ui.mass_drift_panel import MassDriftPanel  # noqa: E402
from milq.ui.metric_plot import MetricPlotPanel  # noqa: E402
from milq.ui.point_hover import HOVER_SIZE  # noqa: E402
from milq.ui.qc_panel import QualityPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


class _Sample:
    def __init__(self, when):
        self.acquisition_time = when


class _Hover:
    """What pyqtgraph's scene hands an item: a position in its coordinates."""

    def __init__(self, x, y, leaving=False):
        self._pos = QtCore.QPointF(x, y)
        self.exit = leaving

    def pos(self):
        return self._pos

    def screenPos(self):
        return QtCore.QPointF(10, 10)


def _session():
    session = Session()
    entries = []
    for n in range(12):
        entry = SampleEntry(f"/d/S{n:02d}.wiff", 0, f"S{n:02d}", QC,
                            sample_group="pool" if n % 2 else "")
        entry.sample = _Sample(f"2026-01-15T09:{n:02d}:00")
        entries.append(entry)
    session.entries = entries
    method = ProcessingMethod()
    method.replace_all([Component(name="IS", precursor=2.0, fragment=1.0,
                                  rt=1.0, is_internal_standard=True)])
    session.method = method
    results = ResultsSet.from_list([])
    # eleven that repeat within a per cent, and S07 at a fifth of them
    areas = [1000.0 + (n % 3) * 5 for n in range(12)]
    areas[7] = 200.0
    for entry, area in zip(entries, areas):
        row = PeakResult(sample_key=entry.key, sample_name=entry.name,
                         component="IS")
        row.area = area
        results.replace(row)
    session.results = results
    return session


def _spot(scatter, name, panel_names):
    """The spot drawn for a sample, through its `data`."""
    for spot in scatter.points():
        if panel_names(spot.data()) == name:
            return spot
    raise AssertionError(f"{name} is not drawn")


# -- the control chart -------------------------------------------------------- #
@pytest.fixture
def quality(qapp):
    panel = QualityPanel(_session())
    panel.resize(800, 600)
    panel.reload()
    panel.component.setCurrentText("IS")
    yield panel
    panel.deleteLater()


def test_a_control_chart_point_says_whose_it_is(quality):
    chart = quality._chart
    names = lambda index: chart.injections[index].sample  # noqa: E731
    spot = _spot(quality._scatter, "S07", names)
    text = quality.describe_point(spot.data())
    assert text.splitlines()[0] == "S07"
    assert f"{QC} · group pool" in text
    assert "Point 8 of 12" in text
    assert "Area 200" in text
    assert "OUT:" in text and "from the centre" in text


def test_a_point_within_limits_says_so(quality):
    chart = quality._chart
    names = lambda index: chart.injections[index].sample  # noqa: E731
    text = quality.describe_point(_spot(quality._scatter, "S02", names).data())
    assert text.startswith(f"S02\n{QC}\n")      # no group: none printed
    assert "Within limits" in text and "OUT" not in text


def test_hovering_a_point_shows_its_name_and_enlarges_it(quality):
    scatter = quality._scatter
    point = quality._chart.injections[7]
    quality.show()
    quality.plot.grab()                       # spots are sized when painted
    scatter.hoverEvent(_Hover(point.order, point.value))
    assert quality.hover.text.startswith("S07")
    view = quality.plot.getPlotItem().getViewBox()
    assert view.toolTip().startswith("S07")
    hovered = [s for s in scatter.points() if s.data() == 7]
    assert hovered and scatter.data["hovered"][7]
    assert scatter.opts["hoverSize"] == HOVER_SIZE

    scatter.hoverEvent(_Hover(0, 0, leaving=True))
    assert quality.hover.text == ""
    assert view.toolTip() == ""
    assert not scatter.data["hovered"].any()


def test_clicking_a_point_still_activates_its_sample(quality):
    seen = []
    quality.sigSampleActivated.connect(seen.append)
    spot = [s for s in quality._scatter.points() if s.data() == 7]
    quality._on_point_clicked(quality._scatter, spot)
    assert seen == [quality.session.entries[7].key]


def test_a_redrawn_chart_forgets_the_hover(quality):
    quality.hover._on_hovered(quality._scatter,
                              [s for s in quality._scatter.points()
                               if s.data() == 7])
    assert quality.hover.text.startswith("S07")
    quality._draw_selected()
    assert quality.hover.text == ""


# -- the metric plot ---------------------------------------------------------- #
def test_a_metric_plot_point_names_sample_component_and_value(qapp):
    session = _session()
    session.results.results[3].flags = ["S/N 4"]
    panel = MetricPlotPanel(session)
    panel.y_combo.setCurrentText("Area")
    panel.component_combo.setCurrentText("IS")
    texts = [panel.describe_point(spot.data())
             for scatter in panel._scatters for spot in scatter.points()]
    s07 = next(t for t in texts if t.startswith("S07"))
    assert "IS" in s07.splitlines()
    assert "Injection 8 of 12" in s07
    assert "Area 200" in s07
    s03 = next(t for t in texts if t.startswith("S03"))
    assert "Flagged: S/N 4" in s03
    panel.x_combo.setCurrentText("RT")
    texts = [panel.describe_point(spot.data())
             for scatter in panel._scatters for spot in scatter.points()]
    assert any("RT 0.000 min" in t for t in texts)
    panel.deleteLater()


def test_two_scatters_do_not_clear_each_other(qapp):
    session = _session()
    panel = MetricPlotPanel(session)
    panel.component_combo.setCurrentText("IS")
    first, second = panel._scatters[:2]
    panel.hover._on_hovered(first, [first.points()[0]])
    shown = panel.hover.text
    assert shown
    # the other scatter has nothing under the cursor: the text stands
    panel.hover._on_hovered(second, [])
    assert panel.hover.text == shown
    panel.hover._on_hovered(first, [])
    assert panel.hover.text == ""
    panel.deleteLater()


# -- the mass drift chart ----------------------------------------------------- #
def test_a_mass_drift_point_names_its_injection(qapp):
    session = _session()
    points = [MassPoint(order=n + 1, sample=f"S{n:02d}", when="",
                        mz=500.0 + n * 1e-4, ppm=(n - 5) * 2.5,
                        intensity=1000.0, key=session.entries[n].key)
              for n in range(12)]
    session.mass_drift = MassDrift(
        trends=[MassTrend(component="IS", nominal=500.0, points=points,
                          median=500.0005)],
        injections=12, timed=12)
    panel = MassDriftPanel(session)
    panel.reload()
    panel.component.setCurrentText("IS")
    by_name = {panel.describe_point(s.data()).splitlines()[0]:
               panel.describe_point(s.data()) for s in panel._scatter.points()}
    assert "Point 12 of 12" in by_name["S11"]
    assert "+15.0 ppm" in by_name["S11"] and "OUT:" in by_name["S11"]
    assert "Within" in by_name["S05"]
    seen = []
    panel.sigSampleActivated.connect(seen.append)
    spot = [s for s in panel._scatter.points() if s.data() == 11]
    panel._on_point_clicked(panel._scatter, spot)
    assert seen == [session.entries[11].key]
    panel.deleteLater()
