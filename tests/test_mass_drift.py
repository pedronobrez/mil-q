"""
Whether the mass axis moved: the same survey measurement, once per
injection, fitted across the run.

Stub channels carry a survey ion whose mass can be walked from injection
to injection. What is tested is that a walk is called a drift and scatter
is not, that the reference is the batch's own median and the exact mass is
an offset apart from it, that the index sees every standard together, and
that too few injections say so rather than judge.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.components import Component  # noqa: E402
from milq.mass_drift import (DRIFT_PPM, MASS_INDEX, MIN_INJECTIONS,  # noqa: E402
                                  mass_drift, mass_trend)
from milq.method import ProcessingMethod  # noqa: E402
from milq.precursor import measure  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from tests.test_matching import Sample  # noqa: E402
from tests.test_precursor import SpectrumChannel  # noqa: E402

#: the exact [M-H]- ion of C18H30O5, so that the fixture's survey ion sits on
#: the formula's mass and the offset test can ask for a small error
EXACT = Component("x", 0.0, formula="C18H30O5", adduct="[M-H]-").precursor


def _entry(name: str, survey_mz: float, nominal: float = 325.20) -> SampleEntry:
    survey = SpectrumChannel(0, None, 100.0, 2000.0, 12.0, 14.0, n=200,
                             ions=[(survey_mz, 1.0)], apex=13.1, height=10_000.0)
    product = SpectrumChannel(1, nominal, 50.0, 350.0, 12.0, 14.0, n=200,
                              ions=[(183.0, 1.0), (survey_mz, 0.4)], apex=13.1)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([survey, product])
    return entry


def _batch(step_ppm: float, n: int = 8, scatter: float = 0.0, seed: int = 1):
    """n injections whose survey ion walks by step_ppm each, plus scatter."""
    rng = np.random.default_rng(seed)
    entries = []
    for i in range(n):
        ppm = i * step_ppm + rng.normal(0.0, scatter)
        entries.append(_entry(f"S{i:02d}", EXACT * (1 + ppm * 1e-6)))
    return entries


def _method(formula: bool = True):
    method = ProcessingMethod()
    method.replace_all([Component(
        "FA 18:3;O3", 325.20, 183.0, rt=13.1, rt_halfwidth=0.5,
        is_internal_standard=True,
        formula="C18H30O5" if formula else "", adduct="[M-H]-" if formula else "")])
    return method


def test_a_mass_that_walks_across_the_run_is_a_drift():
    entries, method = _batch(step_ppm=2.5), _method()
    drift = mass_drift(entries, method)
    trend = drift.trends[0]
    assert trend.measurable and len(trend.points) == 8
    assert trend.change == pytest.approx(2.5 * 7, rel=0.15)
    assert trend.correlation is not None and trend.correlation > 0.9
    assert trend.drifted and drift.drifted == [trend]
    assert abs(trend.points[0].ppm) > 5           # measured against the median


def test_scatter_without_direction_is_not_a_drift():
    entries, method = _batch(step_ppm=0.0, scatter=3.0), _method()
    trend = mass_drift(entries, method).trends[0]
    assert trend.measurable
    assert not trend.drifted
    assert trend.spread_ppm is not None and trend.spread_ppm > 0


def test_the_exact_mass_gives_an_offset_apart_from_the_drift():
    entries = _batch(step_ppm=0.0)
    with_formula = mass_drift(entries, _method(True)).trends[0]
    assert with_formula.exact == pytest.approx(EXACT, abs=0.002)
    assert with_formula.error_ppm is not None and abs(with_formula.error_ppm) < 10
    without = mass_drift(entries, _method(False)).trends[0]
    assert without.exact is None and without.error_ppm is None
    assert without.median == pytest.approx(with_formula.median)


def test_injections_that_did_not_measure_the_same_ion_are_not_judged():
    """
    Measured on a real batch: weak standards came back with spreads of
    hundreds of ppm and one with a "drift" of −351 ppm. That is the search
    window catching a different neighbour each time, not an axis moving.
    """
    entries = _batch(step_ppm=0.0, scatter=60.0)
    trend = mass_drift(entries, _method()).trends[0]
    assert trend.spread_ppm is not None and trend.spread_ppm > 25
    assert not trend.same_ion and not trend.measurable and not trend.drifted
    assert trend.change is None
    assert "not the same ion twice" in trend.note


def test_too_few_injections_say_so_rather_than_judge():
    entries, method = _batch(step_ppm=5.0, n=MIN_INJECTIONS - 1), _method()
    trend = mass_drift(entries, method).trends[0]
    assert not trend.measurable and not trend.drifted
    assert "needed to see a trend" in trend.note
    assert trend.change is None


def test_the_index_takes_every_standard_together():
    method = ProcessingMethod()
    standards = []
    for k, mz in enumerate((325.20, 351.20, 313.24)):
        standards.append(Component(f"IS{k}", mz, 183.0, rt=13.1, rt_halfwidth=0.5,
                                   is_internal_standard=True))
    method.replace_all(standards)
    entries = []
    for i in range(8):
        ppm = i * 3.0
        channels = [SpectrumChannel(0, None, 100.0, 2000.0, 12.0, 14.0, n=200,
                                    ions=[(c.precursor * (1 + ppm * 1e-6), 1.0)
                                          for c in standards], apex=13.1,
                                    height=10_000.0)]
        for k, c in enumerate(standards, start=1):
            channels.append(SpectrumChannel(
                k, c.precursor, 50.0, 400.0, 12.0, 14.0, n=200,
                ions=[(183.0, 1.0), (c.precursor * (1 + ppm * 1e-6), 0.4)],
                apex=13.1))
        entry = SampleEntry(f"/d/S{i:02d}.wiff", 0, f"S{i:02d}")
        entry.sample = Sample(channels)
        entries.append(entry)
    drift = mass_drift(entries, method)
    assert len(drift.trends) == 3 and all(t.drifted for t in drift.trends)
    assert drift.index is not None and drift.index.component == MASS_INDEX
    assert drift.index.drifted
    assert drift.index.change == pytest.approx(21.0, rel=0.2)
    assert len(drift.index.points) == 8
    assert "median over 3 components" in drift.index.note


def test_no_standard_and_no_samples_are_said():
    empty = ProcessingMethod()
    empty.replace_all([Component("A", 325.20, 183.0, rt=13.1)])
    assert "no internal standard" in mass_drift(_batch(0.0), empty).note
    assert "no samples" in mass_drift([], _method()).note


def test_cancelling_returns_nothing():
    calls = []

    def progress(done, total):
        calls.append(done)
        return done < 3

    assert mass_drift(_batch(0.0), _method(), progress=progress) is None
    assert calls[-1] == 3


def test_a_trend_from_measurements_counts_the_unconfirmed():
    component = _method().components[0]
    entries = _batch(0.0)
    measurements = [(entry, measure(entry, component)) for entry in entries]
    trend = mass_trend(component, measurements)
    assert trend.unconfirmed == 0
    assert trend.change is not None and abs(trend.change) < DRIFT_PPM


def test_the_panel_and_the_report_show_a_measurement():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from milq import report
    from milq.session import Session
    from milq.ui.mass_drift_panel import MassDriftPanel

    session = Session()
    session.entries = _batch(step_ppm=2.5)
    session.method = _method()
    panel = MassDriftPanel(session)
    assert panel.table.rowCount() == 0
    assert "Mass drift" not in report.build_html(session, sections=("mass",))
    session.mass_drift = mass_drift(session.entries, session.method)
    panel.reload()
    assert panel.table.rowCount() == 1
    assert "drift" in panel.table.item(0, 8).text()
    assert "drifting" in panel.status.text()
    document = report.build_html(session, sections=("mass",))
    assert "Mass drift" in document and "drift +" in document
    panel.deleteLater()
    app.processEvents()
