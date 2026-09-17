"""
Tests for measuring a precursor's accurate mass from the survey scan.

Stub channels stand in for the instrument: a full-scan channel carrying a
synthetic spectrum, and a product-ion channel carrying the surviving precursor.
"""

import numpy as np
import pytest

from milq import precursor
from milq.components import Component
from milq.samples import SampleEntry
from tests.test_matching import Channel, Sample


def gaussian(x, centre, sigma, height):
    return height * np.exp(-((x - centre) ** 2) / (2 * sigma**2))


class SpectrumChannel(Channel):
    """A channel whose spectra hold given ions and whose XIC tracks a peak."""

    def __init__(self, *args, ions=(), apex=13.1, height=10_000.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.ions = list(ions)          # [(m/z, relative height), ...]
        self.apex = apex
        self.height = height

    def xic_range(self, mz_lo, mz_hi):
        inside = [h for mz, h in self.ions if mz_lo <= mz <= mz_hi]
        scale = max(inside) if inside else 0.0
        return self.rt, gaussian(self.rt, self.apex, 0.05, self.height * scale)

    def tic(self):
        return self.rt, gaussian(self.rt, self.apex, 0.05, self.height)

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        # a narrow profile peak around each ion, so centroiding has something
        # to refine
        mz = np.sort(np.concatenate([
            np.linspace(centre - 0.02, centre + 0.02, 21) for centre, _ in self.ions
        ])) if self.ions else np.zeros(0)
        intensity = np.zeros_like(mz)
        for centre, relative in self.ions:
            intensity += gaussian(mz, centre, 0.005, self.height * relative)
        return mz, intensity


def build(nominal=325.20, survey_mz=325.1887, product_mz=325.1889,
          survey_height=10_000.0, apex=13.1, name="QC"):
    survey = SpectrumChannel(0, None, 100.0, 2000.0, 12.0, 14.0, n=200,
                             ions=[(survey_mz, 1.0)], apex=apex,
                             height=survey_height)
    product = SpectrumChannel(1, nominal, 50.0, 350.0, 12.0, 14.0, n=200,
                              ions=[(183.0, 1.0), (product_mz, 0.4)], apex=apex)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([survey, product])
    return entry


COMPONENT = Component("325.20", 325.20, 183.0, rt=13.1, rt_halfwidth=0.5)


# --- picking the survey channel ------------------------------------------------ #
def test_survey_channel_respects_the_period():
    early = Channel(0, None, 100.0, 2000.0, 0.0, 12.9)
    late = Channel(1, None, 100.0, 2000.0, 13.0, 21.0)
    sample = Sample([early, late])
    assert precursor.survey_channel(sample, 325.2, 5.0) is early
    assert precursor.survey_channel(sample, 325.2, 15.0) is late


def test_survey_channel_needs_the_mass_in_range():
    sample = Sample([Channel(0, None, 400.0, 2000.0, 0.0, 20.0)])
    assert precursor.survey_channel(sample, 325.2, 5.0) is None


# --- one measurement ------------------------------------------------------------ #
def test_measures_the_accurate_mass():
    result = precursor.measure(build(), COMPONENT)
    assert result.found
    assert result.measured == pytest.approx(325.1887, abs=0.002)
    assert result.error_ppm == pytest.approx(-35, abs=10)   # vs the written 325.20


def test_reads_the_surviving_precursor_too():
    result = precursor.measure(build(), COMPONENT)
    assert result.product_mz == pytest.approx(325.1889, abs=0.002)
    assert result.corroborated
    assert abs(result.agreement_ppm) < 10


def test_disagreement_between_the_two_scans_is_flagged():
    """The survey window caught an interference the product-ion scan denies."""
    entry = build(survey_mz=325.2200, product_mz=325.1889)
    result = precursor.measure(entry, COMPONENT)
    assert result.found
    assert not result.corroborated
    assert "differ by" in result.note


def test_a_weak_survey_peak_is_refused():
    result = precursor.measure(build(survey_height=10.0), COMPONENT)
    assert not result.found
    assert "too weak" in result.note


def test_an_unopened_sample_is_refused():
    entry = SampleEntry("/d/x.wiff", 0, "x")
    result = precursor.measure(entry, COMPONENT)
    assert not result.found
    assert result.note == "sample not open"


def test_a_component_with_no_precursor_is_refused():
    result = precursor.measure(build(), Component("x", 0.0))
    assert not result.found
    assert result.note == "no precursor mass"


def test_no_peak_in_the_product_channel_means_no_anchor():
    """
    Without a retention time, a transition carrying only noise must not send
    the survey search to an arbitrary moment.
    """
    entry = build()
    entry.sample.channels[1].height = 0.0        # the transition shows nothing
    unanchored = Component("325.20", 325.20, 183.0)   # and no expected RT
    result = precursor.measure(entry, unanchored)
    assert not result.found
    assert "anchor" in result.note


# --- across the batch ------------------------------------------------------------ #
def test_consensus_is_weighted_by_intensity():
    strong = build(survey_mz=325.1890, survey_height=100_000.0, name="A")
    weak = build(survey_mz=325.1900, survey_height=1_000.0, name="B")
    consensus = precursor.measure_across([strong, weak], COMPONENT)
    assert consensus.found
    # the strong sample dominates, so the answer sits near its value
    assert consensus.measured == pytest.approx(325.1890, abs=0.0004)


def test_wide_spread_is_not_reliable():
    entries = [build(survey_mz=325.1887, name="A"),
               build(survey_mz=325.2400, name="B")]
    consensus = precursor.measure_across(entries, COMPONENT)
    assert consensus.spread_ppm > precursor.CONSENSUS_SPREAD_PPM
    assert not consensus.is_reliable
    assert "disagree" in consensus.note


def test_agreeing_samples_are_reliable():
    entries = [build(survey_mz=325.1887, name="A"),
               build(survey_mz=325.1889, name="B"),
               build(survey_mz=325.1885, name="C")]
    consensus = precursor.measure_across(entries, COMPONENT)
    assert consensus.is_reliable
    assert consensus.corroborated == 3
    assert "confirmed by the product-ion scan" in consensus.note


def test_uncorroborated_measurement_is_not_reliable():
    entries = [build(survey_mz=325.2200, product_mz=325.1889, name=n)
               for n in "AB"]
    consensus = precursor.measure_across(entries, COMPONENT)
    assert consensus.found
    assert not consensus.is_reliable
    assert "does not confirm" in consensus.note


def test_nothing_measured_reports_why():
    entries = [build(survey_height=1.0, name="A")]
    consensus = precursor.measure_across(entries, COMPONENT)
    assert not consensus.found
    assert "too weak" in consensus.note


def test_measure_all_covers_every_component():
    entries = [build(name="A"), build(name="B")]
    components = [COMPONENT, Component("339.20", 339.20, 183.0, rt=13.1)]
    out = precursor.measure_all(entries, components)
    assert set(out) == {"325.20", "339.20"}


def test_measure_all_can_be_cancelled():
    entries = [build(name="A")]
    components = [COMPONENT, Component("b", 339.20, 183.0, rt=13.1),
                  Component("c", 349.20, 183.0, rt=13.1)]
    out = precursor.measure_all(entries, components,
                                progress=lambda done, total: done < 2)
    assert len(out) == 2


# --- how the measurement changes the annotation ---------------------------------- #
def test_a_measured_mass_narrows_the_search_window(monkeypatch):
    """
    The point of the whole exercise: a written mass is searched loose, a
    measured one at the instrument's accuracy.
    """
    from milq.ui import annotate_dialog as ad

    class FakeDatabase:
        def __init__(self):
            self.windows = []

        def search_mz(self, mz, adduct, window, unit):
            self.windows.append((mz, window))
            return []

    fake = FakeDatabase()
    monkeypatch.setattr(ad.lipidmaps, "database", lambda: fake)

    ad.propose([COMPONENT], measured=None)
    written_mass, written_window = fake.windows[-1]

    consensus = precursor.measure_across([build(name="A"), build(name="B")],
                                         COMPONENT)
    assert consensus.is_reliable
    ad.propose([COMPONENT], measured={COMPONENT.name: consensus})
    measured_mass, measured_window = fake.windows[-1]

    assert written_mass == COMPONENT.precursor
    assert measured_mass == pytest.approx(consensus.measured)
    assert measured_window < written_window / 5


def test_an_unreliable_measurement_falls_back_to_the_written_mass(monkeypatch):
    from milq.ui import annotate_dialog as ad

    seen = []

    class FakeDatabase:
        def search_mz(self, mz, adduct, window, unit):
            seen.append(mz)
            return []

    monkeypatch.setattr(ad.lipidmaps, "database", lambda: FakeDatabase())
    consensus = precursor.measure_across(
        [build(survey_mz=325.1887, name="A"), build(survey_mz=325.2400, name="B")],
        COMPONENT)
    assert not consensus.is_reliable

    [proposal] = ad.propose([COMPONENT], measured={COMPONENT.name: consensus})
    assert proposal.source == ad.WRITTEN
    assert seen[-1] == COMPONENT.precursor


# --- the survey confirming the adduct -------------------------------------- #
def test_the_adduct_tolerance_is_the_consensus_spread_and_not_a_fourth_number():
    """One figure for "these two measurements are of the same ion", used by
    the consensus, the mass drift and now the adduct."""
    from milq import chemistry

    assert chemistry.survey_tolerance_ppm() == precursor.CONSENSUS_SPREAD_PPM


def test_the_survey_channel_confirms_the_adduct_of_a_written_precursor():
    """The survey found the way the rest of this module finds it — the
    full-scan channel covering the mass at that time — read for the adduct
    rather than for the precursor alone."""
    from milq import chemistry

    formula = "C24H36D4O5"
    pattern = chemistry.ion_pattern(
        formula, chemistry.ADDUCTS_BY_NAME["[M+NH4]+"], max_peaks=3)
    sodium = chemistry.ion_pattern(
        formula, chemistry.ADDUCTS_BY_NAME["[M+Na]+"], max_peaks=3)
    ions = [(mz, a) for mz, a in pattern] + [(mz, 0.2 * a) for mz, a in sodium]
    survey = SpectrumChannel(0, None, 100.0, 700.0, 12.0, 14.0, n=200,
                             ions=ions, apex=13.1, height=50_000.0)
    product = SpectrumChannel(1, 430.35, 50.0, 450.0, 12.0, 14.0, n=200,
                              ions=[(183.0, 1.0)], apex=13.1)
    entry = SampleEntry("/d/CA-d4.wiff", 0, "CA-d4")
    entry.sample = Sample([survey, product])

    found = precursor.survey_channel(entry.sample, 430.35, 13.1)
    assert found is survey
    choice = chemistry.identify_adduct(
        formula, 430.35, "Positive",
        survey=found.spectrum_rt_range(13.0, 13.2))

    assert choice.adduct is chemistry.ADDUCTS_BY_NAME["[M+NH4]+"]
    assert choice.confirmed
    assert "confirmed by the survey" in choice.reason
    assert "[M+Na]+ 20%" in choice.reason


def test_an_acquisition_with_no_survey_offers_nothing_to_confirm_with():
    """Nine real bile-acid infusions have no full-scan channel at all, so
    there is no spectrum to hand in and the adduct stays what the written
    precursor makes it."""
    from milq import chemistry

    product = SpectrumChannel(0, 430.35, 50.0, 450.0, 12.0, 14.0, n=200,
                              ions=[(183.0, 1.0)], apex=13.1)
    entry = SampleEntry("/d/CA-d4.wiff", 0, "CA-d4")
    entry.sample = Sample([product])

    assert precursor.survey_channel(entry.sample, 430.35, 13.1) is None
    choice = chemistry.identify_adduct("C24H36D4O5", 430.35, "Positive")
    assert choice.adduct is chemistry.ADDUCTS_BY_NAME["[M+NH4]+"]
    assert not choice.confirmed and not choice.read_survey
    assert "survey" not in choice.reason
