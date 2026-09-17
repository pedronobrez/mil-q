"""
What the data proposes.

The estimator is the easy part. What makes a proposal worth acting on is
that it was checked first, against the components of the same method whose
time is already known — so most of what is tested here is the calibration,
and the cases where nothing should be offered at all.
"""

import numpy as np
import pytest

from milq.components import Component
from milq.method import ProcessingMethod
from milq.samples import SampleEntry
from milq.suggest import (estimate_time, suggest_times, suggest_windows)
from tests.test_matching import Channel, Sample

STEP = 14.6 / 60.0


class _PeakChannel(Channel):
    """A channel with one Gaussian, optionally somewhere else each time."""

    def __init__(self, *args, apex=6.0, height=5000.0, width=0.15,
                 noise=0.0, seed=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.apex, self.height, self.width = apex, height, width
        self.noise, self.seed = noise, seed

    def xic_range(self, mz_lo, mz_hi):
        y = self.height * np.exp(-0.5 * ((self.rt - self.apex) / self.width) ** 2)
        if self.noise:
            y = y + np.abs(np.random.default_rng(self.seed).normal(
                0, self.noise, self.rt.size))
        return self.rt, y


def _entries(apexes, height=5000.0, noise=0.0, span=12.0, precursor=760.5851):
    out = []
    for index, apex in enumerate(apexes):
        channel = _PeakChannel(1, precursor, 100.0, 900.0, 0.0, span,
                              n=int(round(span / STEP)), apex=apex,
                              height=height, noise=noise, seed=index)
        entry = SampleEntry(f"/d/S{index:02d}.wiff", 0, f"S{index:02d}")
        entry.sample = Sample([channel])
        out.append(entry)
    return out


def _method(components):
    method = ProcessingMethod()
    method.replace_all(components)
    return method


# --------------------------------------------------------------------------- #
def test_a_time_the_injections_agree_on_is_found():
    component = Component("PC 34:1", 760.5851, 184.0733)
    entries = _entries([6.0] * 8)
    estimate = estimate_time(component, entries, _method([component]))
    assert estimate.found and estimate.agreed
    assert estimate.rt == pytest.approx(6.0, abs=STEP)
    assert estimate.support == 8


def test_a_peak_that_lands_somewhere_different_every_time_is_not_agreed():
    """Which is what a trace with no peak in it looks like."""
    component = Component("PC 34:1", 760.5851, 184.0733)
    entries = _entries([1.5, 4.2, 7.8, 2.1, 9.6, 5.3, 11.0, 3.4])
    estimate = estimate_time(component, entries, _method([component]))
    assert not estimate.agreed


def test_nothing_at_all_says_so():
    component = Component("PC 34:1", 760.5851, 184.0733)
    entries = _entries([6.0] * 6, height=0.0)
    estimate = estimate_time(component, entries, _method([component]))
    assert not estimate.found
    assert "no peak" in estimate.note


def test_the_declared_time_is_carried_so_the_estimate_can_be_checked():
    component = Component("PC 34:1", 760.5851, 184.0733, rt=6.1)
    entries = _entries([6.0] * 8)
    estimate = estimate_time(component, entries, _method([component]))
    assert estimate.declared == 6.1
    assert estimate.error == pytest.approx(estimate.rt - 6.1)


# --------------------------------------------------------------------------- #
# the calibration, which is what makes a proposal worth acting on
# --------------------------------------------------------------------------- #
def test_the_estimator_is_measured_against_the_times_already_known():
    known = Component("known", 760.5851, 184.0733, rt=6.0)
    unknown = Component("unknown", 760.5851, 184.0733)
    found = suggest_times(_method([known, unknown]), _entries([6.0] * 8))
    band = next(b for b in found.bands if b.holds(5000.0))
    assert band.components == 1          # the one that declared a time
    assert band.within == pytest.approx(1.0)
    assert found.step == pytest.approx(STEP, rel=0.05)


def test_a_method_with_no_declared_times_calibrates_against_nothing():
    """
    And has to say so. A confidence with nothing behind it is worse than
    none, because it reads as one that was checked.
    """
    found = suggest_times(_method([Component("A", 760.5851, 184.0733)]),
                          _entries([6.0] * 8))
    assert all(b.components == 0 for b in found.bands)
    assert found.offered


def test_only_components_missing_a_time_are_offered():
    known = Component("known", 760.5851, 184.0733, rt=6.0)
    unknown = Component("unknown", 760.5851, 184.0733)
    found = suggest_times(_method([known, unknown]), _entries([6.0] * 8))
    assert [e.component for e in found.offered] == ["unknown"]


def test_two_components_on_one_trace_are_told_they_are_the_same_peak():
    """
    They share a transition, so they are offered the same time — and
    accepting both writes one answer twice rather than separating them.
    """
    a = Component("C23_HexCer", 798.7, 264.2686, tolerance=0.02)
    b = Component("C22:1_HexCer_2OH", 798.7, 264.2686, tolerance=0.02)
    found = suggest_times(_method([a, b]),
                          _entries([6.0] * 8, precursor=798.7))
    notes = [e.note for e in found.estimates if e.rt is not None]
    assert notes and all("the same trace as" in n for n in notes)
    # both are still offered — somebody may want to set one of them by hand —
    # but neither is put forward as an answer that separates the two
    assert len(found.offered) == 2
    assert all(e.note for e in found.offered)


def test_no_files_open_offers_nothing_and_says_why():
    found = suggest_times(_method([Component("A", 760.5851, 184.0733)]), [])
    assert found.estimates == []
    assert "no files are open" in found.note


# --------------------------------------------------------------------------- #
# windows
# --------------------------------------------------------------------------- #
def test_a_window_too_narrow_gets_a_width_from_the_sampling():
    component = Component("PC 34:1", 760.5851, 184.0733, rt=6.0,
                          rt_halfwidth=0.5, tolerance=0.02)
    found = suggest_windows(_method([component]), _entries([6.0]))
    assert len(found) == 1
    assert found[0].points_now < found[0].points_then
    assert found[0].suggested > 0.5


def test_a_window_already_wide_enough_is_left_alone():
    component = Component("PC 34:1", 760.5851, 184.0733, rt=6.0,
                          rt_halfwidth=2.0, tolerance=0.02)
    assert suggest_windows(_method([component]), _entries([6.0])) == []


def test_a_component_with_no_time_has_no_window_to_widen():
    component = Component("PC 34:1", 760.5851, 184.0733, rt_halfwidth=0.5)
    assert suggest_windows(_method([component]), _entries([6.0])) == []
