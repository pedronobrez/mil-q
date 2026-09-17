"""
Which peak in the window is the component.

The window is a retention time plus or minus a tolerance, and it does not
always hold one peak. Where it holds two — an isomer, an isobar, a shoulder —
something has to decide, and until now the decision was always "the bigger
one" with no way to say otherwise. These tests are about the two rules giving
different answers on the same data, which is the whole point of having a
choice, and about the choice being visible in the result when it mattered.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.components import Component, IntegrationParams  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.processing import (PEAK_LARGEST, PEAK_NEAREST,  # noqa: E402
                                  choose_peak, detect_peaks)
from milq.quantify import integrate_component  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from tests.test_matching import Channel, Sample  # noqa: E402


def _trace(peaks, start=10.0, end=13.0, points=600):
    """A chromatogram of Gaussians: (retention time, height, width)."""
    x = np.linspace(start, end, points)
    y = np.zeros_like(x)
    for rt, height, width in peaks:
        y += height * np.exp(-0.5 * ((x - rt) / width) ** 2)
    return x, y


def _found(peaks, min_relative=0.05):
    x, y = _trace(peaks)
    return detect_peaks(x, y, min_relative=min_relative, min_snr=3.0)


# --------------------------------------------------------------------------- #
def test_two_co_eluting_species_get_different_answers_from_the_two_rules():
    """
    The case the choice exists for. A method that says 11.42 and a window of
    ±0.6 min contains both this analyte and something 0.2 min later that
    ionises better; whichever peak is right, it is not right by being taller.
    """
    peaks = _found([(11.42, 4000.0, 0.03), (11.62, 9000.0, 0.03)])
    assert len(peaks) == 2

    largest, note = choose_peak(peaks, 11.42, PEAK_LARGEST)
    assert largest.apex_rt == pytest.approx(11.62, abs=0.01)
    assert note == ""

    nearest, note = choose_peak(peaks, 11.42, PEAK_NEAREST)
    assert nearest.apex_rt == pytest.approx(11.42, abs=0.01)
    assert "chosen by proximity" in note
    assert "11.6" in note                # it says what it passed over


def test_the_note_is_silent_when_the_rule_changed_nothing():
    """
    A note on every row is a note nobody reads. It is there to mark the rows
    where the smaller peak was taken, and only those.
    """
    peaks = _found([(11.42, 9000.0, 0.03), (11.62, 4000.0, 0.03)])
    for rule in (PEAK_LARGEST, PEAK_NEAREST):
        peak, note = choose_peak(peaks, 11.42, rule)
        assert peak.apex_rt == pytest.approx(11.42, abs=0.01)
        assert note == ""


def test_nearest_falls_back_and_says_so_without_a_retention_time():
    """A component with no expected RT cannot be near it."""
    peaks = _found([(11.42, 4000.0, 0.03), (11.62, 9000.0, 0.03)])
    peak, note = choose_peak(peaks, None, PEAK_NEAREST)
    assert peak.apex_rt == pytest.approx(11.62, abs=0.01)
    assert "no expected retention time" in note


def test_proximity_chooses_among_peaks_that_already_passed_the_gates():
    """
    The protection against picking noise sitting on the expected time is the
    height and signal-to-noise gates, not the rule. Raise the gate and the
    small peak stops being a candidate at all.
    """
    trace = [(11.42, 300.0, 0.03), (11.62, 9000.0, 0.03)]
    generous = _found(trace, min_relative=0.02)
    assert len(generous) == 2
    assert choose_peak(generous, 11.42, PEAK_NEAREST)[0].apex_rt == \
        pytest.approx(11.42, abs=0.01)

    x, y = _trace(trace)
    strict = detect_peaks(x, y, min_relative=0.20, min_snr=3.0)
    assert len(strict) == 1
    assert choose_peak(strict, 11.42, PEAK_NEAREST)[0].apex_rt == \
        pytest.approx(11.62, abs=0.01)


def test_equally_close_peaks_are_broken_by_size():
    """Proximity has said all it can; something still has to decide."""
    peaks = _found([(11.30, 4000.0, 0.03), (11.54, 9000.0, 0.03)])
    peak, _ = choose_peak(peaks, 11.42, PEAK_NEAREST)
    assert peak.apex_rt == pytest.approx(11.54, abs=0.02)


def test_no_peaks_at_all():
    assert choose_peak([], 11.42, PEAK_NEAREST) == (None, "")


# --------------------------------------------------------------------------- #
# the setting
# --------------------------------------------------------------------------- #
def test_the_default_is_what_it_always_did():
    """
    Existing projects have to come back with the numbers they had. The rule
    is a choice, not a correction.
    """
    assert IntegrationParams().peak_choice == PEAK_LARGEST


def test_an_unknown_rule_falls_back_rather_than_failing():
    assert IntegrationParams(peak_choice="whichever").peak_choice == PEAK_LARGEST


def test_the_rule_survives_a_round_trip_through_a_saved_method():
    """It is a method setting, so it has to come back with the project."""
    method = ProcessingMethod()
    method.replace_all([Component(
        name="PC 34:1", precursor=760.5851, fragment=184.0733, rt=11.42,
        integration=IntegrationParams(peak_choice=PEAK_NEAREST))])
    method.defaults = IntegrationParams(peak_choice=PEAK_NEAREST)

    restored = ProcessingMethod.from_dict(method.to_dict())
    assert restored.defaults.peak_choice == PEAK_NEAREST
    assert restored.components[0].integration.peak_choice == PEAK_NEAREST


# --------------------------------------------------------------------------- #
# through the integration, which is where the wiring can be wrong
# --------------------------------------------------------------------------- #
class _TwoPeakChannel(Channel):
    """A channel whose retention-time window holds the analyte and a taller
    neighbour 0.2 min later — the case the choice exists for."""

    def xic_range(self, mz_lo, mz_hi):
        _, y = _trace([(11.42, 4000.0, 0.02), (11.62, 9000.0, 0.02)],
                      start=11.0, end=12.0, points=500)
        return self.rt, y


def _entry_and_method(rule):
    channel = _TwoPeakChannel(1, 760.5851, 100.0, 800.0, 11.0, 12.0, n=500)
    entry = SampleEntry("/d/QC01.wiff", 0, "QC01")
    entry.sample = Sample([channel])
    method = ProcessingMethod()
    method.replace_all([Component(
        "PC 34:1", 760.5851, 184.0733, rt=11.42, rt_halfwidth=0.5,
        integration=IntegrationParams(peak_choice=rule,
                                      min_relative_height=0.05))])
    return entry, method


def test_the_setting_reaches_the_integration_and_changes_the_area():
    """
    The unit above proves the rule; this proves it is actually consulted —
    the two rules have to come back with different peaks from the same file.
    """
    entry, method = _entry_and_method(PEAK_LARGEST)
    largest = integrate_component(entry, method.components[0], method)
    assert largest.rt == pytest.approx(11.62, abs=0.02)
    assert largest.note == ""

    entry, method = _entry_and_method(PEAK_NEAREST)
    nearest = integrate_component(entry, method.components[0], method)
    assert nearest.rt == pytest.approx(11.42, abs=0.02)
    assert nearest.area < largest.area
    assert "chosen by proximity" in nearest.note
