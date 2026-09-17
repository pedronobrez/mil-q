"""
Windows narrower than the sampling can resolve.

Found by reprocessing a real batch: a scheduled method sampling one
transition every 14.6 s gives a ±0.5 min window four points, and
`detect_peaks` declines below five — so the window returned nothing at all
whatever was in it, and a peak of 44,875 counts came back as "no peak above
noise". Whether a component was integrated depended on whether its window
happened to catch four scans or five, which is set by the channel's start
offset rather than by anything about the chemistry.

The window says where the apex may be. It was being used as the whole of what
the detector may see, which also truncated every peak at the boundary.
"""

import numpy as np
import pytest

from milq.components import Component
from milq.method import ProcessingMethod
from milq.quantify import (MARGIN_SCANS, detection_range,
                                integrate_component)
from milq.samples import SampleEntry
from tests.test_matching import Channel, Sample

#: 14.6 s, the cycle of the acquisition this was found on
STEP = 14.6 / 60.0


class _CoarseChannel(Channel):
    """A channel sampled once every 14.6 s, with one Gaussian peak."""

    def __init__(self, *args, apex=6.41, height=21816.0, width=0.12, **kwargs):
        super().__init__(*args, **kwargs)
        self.apex, self.height, self.width = apex, height, width

    def xic_range(self, mz_lo, mz_hi):
        y = self.height * np.exp(-0.5 * ((self.rt - self.apex) / self.width) ** 2)
        return self.rt, y


def _batch(rt=6.4, halfwidth=0.5, apex=6.41, height=21816.0):
    scans = int(round(12.0 / STEP))
    channel = _CoarseChannel(1, 703.6, 100.0, 800.0, 0.0, 12.0, n=scans,
                             apex=apex, height=height)
    entry = SampleEntry("/d/QC01.wiff", 0, "QC01")
    entry.sample = Sample([channel])
    method = ProcessingMethod()
    method.replace_all([Component("C16_SM", 703.6, 184.0733, rt=rt,
                                  rt_halfwidth=halfwidth)])
    return entry, method


def _points_in_window(entry, component):
    x = entry.sample.channels[0].rt
    lo, hi = component.rt_window()
    return int(np.sum((x >= lo) & (x <= hi)))


# --------------------------------------------------------------------------- #
def test_a_four_point_window_still_finds_an_obvious_peak():
    """The regression. Before this, twenty-one thousand counts read as noise."""
    entry, method = _batch()
    component = method.components[0]
    assert _points_in_window(entry, component) == 4      # the case that failed

    result = integrate_component(entry, component, method)
    assert result.found, result.note
    assert result.rt == pytest.approx(6.41, abs=STEP)
    assert result.area > 0


def test_four_scans_and_five_scans_give_the_same_answer():
    """
    Whether the window caught four points or five was an accident of where
    the channel started, and it decided whether the component existed.
    """
    narrow, method = _batch(halfwidth=0.5)
    wide, _ = _batch(halfwidth=0.62)
    component = method.components[0]
    assert _points_in_window(narrow, component) == 4
    wide_component = Component("C16_SM", 703.6, 184.0733, rt=6.4,
                               rt_halfwidth=0.62)
    assert _points_in_window(wide, wide_component) == 5

    a = integrate_component(narrow, component, method)
    method.replace_all([wide_component])
    b = integrate_component(wide, wide_component, method)
    assert a.found and b.found
    assert a.rt == pytest.approx(b.rt)
    assert a.area == pytest.approx(b.area, rel=0.01)


def test_a_peak_in_the_margin_is_not_the_component():
    """
    The margin is there so the detector can see edges, not so it can pick up
    whatever elutes next door. The apex still has to land in the window.
    """
    entry, method = _batch(rt=6.4, halfwidth=0.5, apex=8.2)   # well outside
    result = integrate_component(entry, method.components[0], method)
    assert not result.found
    assert result.note == "no peak above noise"


def test_the_detector_sees_further_than_the_window():
    x = np.arange(0.0, 12.0, STEP)
    window = (5.9, 6.9)
    mask = (x >= window[0]) & (x <= window[1])
    widened = detection_range(x, mask)
    assert int(mask.sum()) == 4
    assert int(widened.sum()) == 4 + 2 * MARGIN_SCANS


def test_the_margin_does_not_run_off_the_ends_of_the_trace():
    x = np.arange(0.0, 2.0, STEP)
    mask = np.zeros(x.size, dtype=bool)
    mask[:2] = True                       # hard against the start
    widened = detection_range(x, mask)
    assert widened[0] and int(widened.sum()) == 2 + MARGIN_SCANS


def test_an_empty_window_is_returned_untouched():
    x = np.arange(0.0, 2.0, STEP)
    mask = np.zeros(x.size, dtype=bool)
    assert not detection_range(x, mask).any()


def test_a_trace_too_short_to_detect_in_says_that_rather_than_no_peak():
    """
    "No peak above noise" sends somebody looking for signal that is plainly
    there. The reason has to be the actual reason.
    """
    channel = _CoarseChannel(1, 703.6, 100.0, 800.0, 6.0, 6.8, n=4, apex=6.41)
    entry = SampleEntry("/d/QC01.wiff", 0, "QC01")
    entry.sample = Sample([channel])
    method = ProcessingMethod()
    method.replace_all([Component("C16_SM", 703.6, 184.0733, rt=6.4,
                                  rt_halfwidth=0.5)])
    result = integrate_component(entry, method.components[0], method)
    if not result.found:
        assert "narrower than the sampling can resolve" in result.note
