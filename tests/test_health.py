"""
Reading the method before it is run.

Every check here was first found by hand, on a real method, over the course
of a day: components that share a transition with nothing to separate them,
an internal standard for a third of the panel with no retention time,
windows narrower than the sampling can resolve. The point of the module is
that none of that needed a day.
"""

from milq.components import Component
from milq.health import COMFORTABLE_POINTS, SERIOUS, WARNING, check_method
from milq.method import ProcessingMethod
from milq.samples import SampleEntry
from tests.test_matching import Channel, Sample


def _method(components):
    method = ProcessingMethod()
    method.replace_all(components)
    return method


def _finding(health, check):
    return next((f for f in health.findings if f.check == check), None)


def _batch(step=14.6 / 60.0, span=12.0):
    channel = Channel(1, 760.5851, 100.0, 900.0, 0.0, span,
                      n=int(round(span / step)))
    entry = SampleEntry("/d/QC01.wiff", 0, "QC01")
    entry.sample = Sample([channel])
    return [entry]


# --------------------------------------------------------------------------- #
def test_a_sound_method_reports_nothing():
    health = check_method(_method([
        Component("PC 34:1", 760.5851, 184.0733, rt=11.4, rt_halfwidth=0.5,
                  tolerance=0.02),
        Component("PC 36:2", 786.6007, 184.0733, rt=12.1, rt_halfwidth=0.5,
                  tolerance=0.02),
    ]))
    assert health.sound
    assert health.components == 2


def test_two_components_on_one_transition_cannot_be_told_apart():
    """
    Twelve such pairs in the real method. The instrument measures one trace
    for both, so both report the same number and neither is wrong about it.
    """
    health = check_method(_method([
        Component("C23_HexCer", 798.7, 264.2686, tolerance=0.02),
        Component("C22:1_HexCer_2OH", 798.7, 264.2686, tolerance=0.02),
    ]))
    found = _finding(health, "shared transition")
    assert found is not None and found.severity == SERIOUS
    assert sorted(found.components) == ["C22:1_HexCer_2OH", "C23_HexCer"]


def test_a_retention_time_separates_them():
    """Which is the whole point of the finding: it names the fix."""
    health = check_method(_method([
        Component("C23_HexCer", 798.7, 264.2686, rt=7.9, rt_halfwidth=0.3,
                  tolerance=0.02),
        Component("C22:1_HexCer_2OH", 798.7, 264.2686, rt=9.4,
                  rt_halfwidth=0.3, tolerance=0.02),
    ]))
    assert _finding(health, "shared transition") is None


def test_a_different_fragment_is_a_different_measurement():
    health = check_method(_method([
        Component("A", 798.7, 264.2686, tolerance=0.02),
        Component("B", 798.7, 184.0733, tolerance=0.02),
    ]))
    assert _finding(health, "shared transition") is None


def test_an_internal_standard_without_a_time_is_serious_and_says_who_it_serves():
    health = check_method(_method([
        Component("IS", 482.4, 264.2686, is_internal_standard=True),
        Component("A", 500.0, 264.2686, rt=5.0, internal_standard="IS"),
        Component("B", 520.0, 264.2686, rt=6.0, internal_standard="IS"),
    ]))
    found = _finding(health, "internal standard without a time")
    assert found is not None and found.severity == SERIOUS
    assert found.components == ["IS"]
    assert "serves 2" in found.detail


def test_an_internal_standard_nobody_uses_is_not_reported():
    """A spare standard in the method is not a problem with the method."""
    health = check_method(_method([
        Component("IS", 482.4, 264.2686, is_internal_standard=True),
        Component("A", 500.0, 264.2686, rt=5.0),
    ]))
    assert _finding(health, "internal standard without a time") is None


def test_a_component_pointing_at_a_standard_that_does_not_exist():
    health = check_method(_method([
        Component("A", 500.0, 264.2686, rt=5.0,
                  internal_standard="the one nobody added"),
    ]))
    found = _finding(health, "missing internal standard")
    assert found is not None and found.severity == SERIOUS
    assert found.components == ["A"]


def test_components_without_a_retention_time_are_counted():
    health = check_method(_method([
        Component("A", 500.0, 264.2686, rt=5.0),
        Component("B", 520.0, 264.2686),
        Component("C", 540.0, 264.2686),
    ]))
    found = _finding(health, "no retention time")
    assert found is not None and found.severity == WARNING
    assert found.components == ["B", "C"]
    assert "2 of 3" in found.summary


def test_an_internal_standard_without_a_formula_has_no_lock_mass():
    health = check_method(_method([
        Component("SM(d18:1/12:0)", 647.5, 184.0733, rt=5.6, adduct="[M+H]+",
                  formula="C35H71N2O6P", is_internal_standard=True),
        Component("Cer1P (12:0)", 562.4, 264.2686, rt=4.9, adduct="[M+H]+",
                  is_internal_standard=True),
    ]))
    found = _finding(health, "internal standard without a formula")
    assert found is not None and found.severity == WARNING
    assert found.components == ["Cer1P (12:0)"]
    assert "lock mass" in found.detail


def test_a_formula_that_is_not_the_precursor_is_serious():
    """
    One of the two is wrong and they are used for different things: the
    precursor builds the extraction window, the formula is what the
    recalibration corrects towards. `484.465` against a formula worth
    484.4724 is the real method's own typo, 15 ppm out.
    """
    health = check_method(_method([
        Component("dHCer(d18:0/12:0)", 484.465, 284.2948, rt=5.5,
                  adduct="[M+H]+", formula="C30H61NO3"),
        Component("SM(d18:1/12:0)", 647.5, 184.0733, rt=5.6, adduct="[M+H]+",
                  formula="C35H71N2O6P"),
    ]))
    found = _finding(health, "formula against precursor")
    assert found is not None and found.severity == SERIOUS
    assert found.components == ["dHCer(d18:0/12:0)"]
    assert "484.4724" in found.detail


def test_a_whole_dalton_disagreement_says_the_name_may_be_the_error():
    """
    Past half a dalton the mass is the more likely of the two to be right — it
    is what the instrument was set to acquire — so the finding has to point at
    the name and at the column that offers one, rather than at the mass.
    """
    health = check_method(_method([
        Component("LacCER(d18:1/18:1(9Z))", 886.6407, 264.2686, rt=7.0,
                  adduct="[M+H]+", formula="C48H89NO13"),
    ]))
    found = _finding(health, "formula against precursor")
    assert found is not None
    assert "1 of them are a whole dalton or more apart" in found.detail
    assert "makes the *name* the error" in found.detail
    assert "Rename to" in found.detail


def test_a_sub_dalton_disagreement_does_not_talk_about_the_name():
    health = check_method(_method([
        Component("dHCer(d18:0/12:0)", 484.465, 284.2948, rt=5.5,
                  adduct="[M+H]+", formula="C30H61NO3"),
    ]))
    found = _finding(health, "formula against precursor")
    assert found is not None and "Rename to" not in found.detail


def test_a_formula_with_no_adduct_is_not_called_a_disagreement():
    health = check_method(_method([
        Component("A", 500.0, 264.2686, rt=5.0, formula="C30H61NO3"),
    ]))
    assert _finding(health, "formula against precursor") is None


# --------------------------------------------------------------------------- #
# the checks that need a file open
# --------------------------------------------------------------------------- #
def test_a_window_the_sampling_cannot_resolve():
    """
    A ±0.5 min window on a method cycling every 14.6 s holds four scans. That
    is what silently returned nothing at all before the detector was given
    room, and it is worth knowing before a batch is processed rather than
    from the results.
    """
    health = check_method(_method([
        Component("PC 34:1", 760.5851, 184.0733, rt=6.0, rt_halfwidth=0.5,
                  tolerance=0.02),
    ]), _batch())
    found = _finding(health, "window too narrow")
    assert found is not None and found.severity == SERIOUS
    assert found.components == ["PC 34:1"]
    assert str(COMFORTABLE_POINTS) in found.detail


def test_a_window_wide_enough_is_not_reported():
    health = check_method(_method([
        Component("PC 34:1", 760.5851, 184.0733, rt=6.0, rt_halfwidth=1.5,
                  tolerance=0.02),
    ]), _batch())
    assert _finding(health, "window too narrow") is None


def test_the_sampling_check_says_it_was_skipped_without_a_file():
    """Silence would read as a pass."""
    health = check_method(_method([
        Component("PC 34:1", 760.5851, 184.0733, rt=6.0, rt_halfwidth=0.5),
    ]))
    assert _finding(health, "window too narrow") is None
    assert any("points fall in each" in note for note in health.skipped)


def test_an_unloaded_batch_is_the_same_as_no_batch():
    entry = SampleEntry("/d/QC01.wiff", 0, "QC01")     # never opened
    health = check_method(_method([
        Component("PC 34:1", 760.5851, 184.0733, rt=6.0, rt_halfwidth=0.5),
    ]), [entry])
    assert _finding(health, "window too narrow") is None
