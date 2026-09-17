"""
Tests for matching a component to an acquisition channel.

Uses stub channels so the scheduled-method logic can be exercised without a
.wiff file. The layout mirrors a real TripleTOF MRM-HR method, where the same
precursor is acquired in two periods.
"""

from dataclasses import dataclass

import numpy as np
import pytest

from milq.components import Component
from milq.matching import components_from_sample, covers_rt, match_channel


@dataclass
class Info:
    index: int
    precursor: float | None
    start_mass: float
    end_mass: float

    @property
    def is_ms1(self) -> bool:
        return self.precursor is None

    @property
    def name(self) -> str:
        return "TOF MS" if self.is_ms1 else "TOF PI"

    @property
    def short_label(self) -> str:
        return self.name if self.is_ms1 else f"{self.name} {self.precursor:.2f}"

    @property
    def label(self) -> str:
        return f"{self.short_label}  {self.start_mass:.0f}-{self.end_mass:.0f}"


class Channel:
    def __init__(self, index, precursor, start_mass, end_mass, rt0, rt1, n=100):
        self.index = index
        self.info = Info(index, precursor, start_mass, end_mass)
        self.rt = np.linspace(rt0, rt1, n)


class Sample:
    def __init__(self, channels):
        self.channels = channels


@pytest.fixture
def scheduled():
    """Survey scan plus 313.24 in two periods, as in the real method."""
    return Sample([
        Channel(0, None, 100.0, 2000.0, 0.0, 12.94),
        Channel(43, 313.24, 50.0, 350.0, 0.04, 12.94),
        Channel(80, 313.24, 50.0, 320.0, 12.97, 21.47),
        Channel(65, 325.20, 50.0, 330.0, 12.97, 21.47),
    ])


def test_retention_time_picks_the_right_period(scheduled):
    """The heart of it: precursor alone would take the first channel."""
    late = Component("late", 313.2384, 183.1391, rt=14.7)
    early = Component("early", 313.2384, 183.1391, rt=5.0)
    assert match_channel(scheduled, late).index == 80
    assert match_channel(scheduled, early).index == 43


def test_without_a_retention_time_the_first_match_is_used(scheduled):
    component = Component("any", 313.2384, 183.1391)
    assert match_channel(scheduled, component).index == 43


def test_retention_time_outside_every_period_still_matches_on_precursor(scheduled):
    component = Component("far", 313.2384, 183.1391, rt=40.0)
    assert match_channel(scheduled, component).index in (43, 80)


def test_fragment_outside_the_mass_range_is_rejected(scheduled):
    """At 14.7 min only channel 80 is live, and it stops at m/z 320."""
    component = Component("x", 313.2384, 340.0, rt=14.7)
    assert match_channel(scheduled, component).index == 43  # the wider period


def test_falls_back_to_the_survey_scan(scheduled):
    component = Component("no channel", 295.2279, 195.1391, rt=5.0)
    assert match_channel(scheduled, component).index == 0


def test_returns_none_when_nothing_fits():
    sample = Sample([Channel(1, 500.0, 400.0, 520.0, 0.0, 10.0)])
    assert match_channel(sample, Component("x", 100.0, 50.0)) is None


def test_precursor_tolerance_is_respected(scheduled):
    near = Component("near", 313.5, 183.1391, rt=14.7)   # 0.26 Da away
    far = Component("far", 315.0, 183.1391, rt=14.7)     # 1.76 Da away
    assert match_channel(scheduled, near).index == 80
    assert match_channel(scheduled, far).info.is_ms1     # fell back to survey


def test_closest_precursor_wins():
    sample = Sample([
        Channel(1, 313.20, 50.0, 350.0, 0.0, 20.0),
        Channel(2, 313.24, 50.0, 350.0, 0.0, 20.0),
    ])
    assert match_channel(sample, Component("x", 313.2384, 183.0)).index == 2


def test_covers_rt():
    channel = Channel(1, 300.0, 50.0, 350.0, 5.0, 10.0)
    assert covers_rt(channel, 7.0)
    assert not covers_rt(channel, 2.0)
    assert covers_rt(channel, None)


def test_components_from_sample_skips_survey_and_dedupes(scheduled):
    components = components_from_sample(scheduled)
    names = [c.name for c in components]
    assert "313.24" in names and "325.20" in names
    # 313.24 appears in two periods, so it yields two entries, not one
    assert names.count("313.24") == 2
    assert all(c.precursor > 0 and c.rt is None for c in components)


def test_components_from_sample_on_a_survey_only_method():
    assert components_from_sample(Sample([Channel(0, None, 100.0, 2000.0, 0, 10)])) == []
