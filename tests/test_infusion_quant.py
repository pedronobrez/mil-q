"""
Quantitation without a column: an analyte against its deuterated standard.

The real files this was written against hold the **standards only**, so the
analyte/standard ratio itself cannot be measured on them — what they gave is
the response of a standard against itself, the size of the cross-talk term
and, unexpectedly, the finding that a product-ion acquisition has no isotope
envelope at all to leak. So the ratio, the correction and the curve are
exercised here on spectra built from the same chemistry with the answer
known: `C24H40O5` as `[M+NH4]+`, its d4 form 4.0251 Da up, and a five-level
series whose ratios are 1, 2, 5, 10 and 20.

Two things are worth stating about the fixtures. The spectra are built as
**centroids** wherever the arithmetic is what is under test, because a
profile hump 8 mDa wide would merge peaks that are 2.9 mDa apart and the
whole point of several of these tests is that they are not merged. And the
isotope envelope is built from `chemistry.isotope_pattern` rather than typed
in, so a test of the correction is a test of the correction and not a second
copy of the pattern.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import audit  # noqa: E402
from milq import infusion_quant as iq  # noqa: E402
from milq.calibration import LINEAR, CalibrationPoint  # noqa: E402
from milq.calibration import fit as fit_curve  # noqa: E402
from milq.chemistry import (NEUTRON_SPACING,  # noqa: E402
                                 adduct_from_name, isotope_pattern,
                                 monoisotopic_mass, parse_formula)
from milq.components import Component  # noqa: E402
from milq.explain import precursor_ions  # noqa: E402
from milq.quantify import PeakResult  # noqa: E402
from milq.samples import STANDARD, SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from tests.test_infusion_report import (FakeChannel,  # noqa: E402
                                        FakeSample, _grid)

FORMULA = "C24H40O5"          # cholic acid
ADDUCT = "[M+NH4]+"
LABELS = 4

#: the two intact ions, from the formula rather than typed
_ADD = adduct_from_name(ADDUCT)
D0_MZ = _ADD.mz(monoisotopic_mass(parse_formula(FORMULA)))
_D4 = dict(parse_formula(FORMULA))
_D4["D"], _D4["H"] = LABELS, _D4["H"] - LABELS
D4_MZ = _ADD.mz(monoisotopic_mass(_D4))


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def analyte(**kwargs) -> Component:
    return Component(name="Cholic acid", formula=FORMULA, precursor=D0_MZ,
                     internal_standard="CA-d4", **kwargs)


def standard(**kwargs) -> Component:
    return Component(name="CA-d4", formula=FORMULA, precursor=D4_MZ,
                     is_internal_standard=True, **kwargs)


# --------------------------------------------------------------------------- #
# spectra built from the chemistry, not typed
# --------------------------------------------------------------------------- #
def rungs(deuterium: int) -> list:
    """The water-loss ladder one compound gives, as PredictedIons."""
    return [ion for ion in precursor_ions(FORMULA, _ADD, deuterium)
            if all(loss == "H2O" for loss in ion.losses)]


def ion_counts(ion) -> dict:
    counts = dict(parse_formula(ion.formula))
    for element, n in parse_formula(_ADD.added).items():
        counts[element] = counts.get(element, 0) + n
    return counts


def ladder_peaks(deuterium: int, scale: float,
                 envelope: bool = True) -> list[tuple[float, float]]:
    """
    Every rung at `scale` counts, each with its own isotope envelope.

    `envelope=False` is a product-ion acquisition whose precursor was
    isolated: the monoisotopic ion and nothing above it, which is what the
    real infusions measure.
    """
    out = []
    for ion in rungs(deuterium):
        if not envelope:
            out.append((float(ion.mz), scale))
            continue
        pattern = isotope_pattern(ion_counts(ion), None, min_abundance=1e-6,
                                  max_peaks=80, merge_tolerance=0.001)
        base = pattern[0][0]
        for mass, abundance in pattern:
            out.append((float(ion.mz + (mass - base)), scale * abundance))
    return out


def centroids(peaks) -> tuple[np.ndarray, np.ndarray]:
    mz = np.asarray([p[0] for p in peaks], dtype=float)
    intensity = np.asarray([p[1] for p in peaks], dtype=float)
    order = np.argsort(mz)
    return mz[order], intensity[order]


def mixture(analyte_scale: float, standard_scale: float = 2_000.0,
            envelope: bool = True):
    return centroids(ladder_peaks(0, analyte_scale, envelope)
                     + ladder_peaks(LABELS, standard_scale, envelope))


# --------------------------------------------------------------------------- #
# reading one compound out of one spectrum
# --------------------------------------------------------------------------- #
def test_responses_measures_all_three_bases():
    mz, intensity = mixture(1_000.0)
    measured = iq.responses(mz, intensity, standard(), polarity="Positive")

    assert measured.adduct == ADDUCT
    assert measured.deuterium == LABELS
    assert measured.precursor is not None
    assert measured.precursor.mz == pytest.approx(D4_MZ, abs=1e-4)
    assert measured.response(iq.ON_PRECURSOR) == pytest.approx(2_000.0, rel=1e-6)
    # every rung is there, and the ladder is their sum
    assert measured.rungs_found() == len(measured.ladder)
    assert measured.response(iq.ON_LADDER) == pytest.approx(
        sum(rung.response for rung in measured.ladder))
    # each rung is at least what was put there. It is more than that on the
    # rungs a neighbour's satellite reaches: a d4 ladder's rungs sit
    # 1.00628 Da apart and a carbon-13 satellite 1.00335 above its own ion,
    # so 2.9 mDa separates them and a 10 ppm window at m/z 356 does not.
    assert all(rung.response >= 2_000.0 - 1e-6 for rung in measured.ladder)
    assert measured.response(iq.ON_LADDER) > 2_000.0 * len(measured.ladder)
    # the fragment, with nothing written, is the strongest predicted ion —
    # and says that it was chosen by height
    assert measured.fragment is not None
    assert measured.response(iq.ON_FRAGMENT) == pytest.approx(
        max(rung.response for rung in measured.ladder))
    assert "chosen by height" in measured.notes[iq.ON_FRAGMENT]


def test_the_written_fragment_is_the_one_measured():
    """A fragment in the component table fixes the basis to one ion."""
    mz, intensity = mixture(1_000.0)
    rung = sorted(rungs(LABELS), key=lambda i: i.mz)[0]
    component = standard(fragment=float(rung.mz))
    measured = iq.responses(mz, intensity, component, polarity="Positive")

    assert measured.fragment.mz == pytest.approx(rung.mz, abs=1e-6)
    assert "as written" in measured.fragment.description
    # and it recovered the rung's composition, which is what lets the
    # cross-talk be computed rather than merely bounded
    assert measured.fragment.counts is not None


def test_the_isotope_envelope_is_read_beside_every_ion():
    mz, intensity = mixture(1_000.0)
    measured = iq.responses(mz, intensity, standard(), polarity="Positive")
    satellites = measured.precursor.satellite_share()

    assert len(measured.precursor.intensities) == iq.ENVELOPE_PEAKS
    # a C24 ion: M+1 is about a quarter of M, M+2 a twentieth
    assert satellites[0] == pytest.approx(0.266, abs=0.01)
    assert satellites[1] == pytest.approx(0.045, abs=0.01)


def test_a_component_with_no_formula_says_so_on_two_bases():
    mz, intensity = mixture(1_000.0)
    bare = Component(name="Mystery", precursor=D4_MZ)
    measured = iq.responses(mz, intensity, bare)

    assert measured.response(iq.ON_PRECURSOR) is None
    assert measured.response(iq.ON_LADDER) is None
    assert "carries no formula" in measured.notes[iq.ON_PRECURSOR]
    # the fragment still has an answer, because a base peak needs no formula
    assert measured.response(iq.ON_FRAGMENT) > 0
    assert "composition is unknown" in measured.notes[iq.ON_FRAGMENT]


def test_an_empty_spectrum_refuses_every_basis():
    measured = iq.responses(np.zeros(0), np.zeros(0), standard())
    assert all(measured.response(basis) is None for basis in iq.BASES)


def test_peak_at_sums_the_window_and_reports_the_tallest_position():
    """Two centroids inside one tolerance are one measurement — which is
    what keeps the reading and the correction describing the same thing."""
    mz = np.array([400.0000, 400.0020])
    intensity = np.array([100.0, 300.0])
    found = iq.peak_at(mz, intensity, 400.0010, tolerance_ppm=10.0)

    assert found[0] == pytest.approx(400.0020)
    assert found[1] == pytest.approx(400.0)
    assert iq.peak_at(mz, intensity, 401.0, tolerance_ppm=10.0) is None


# --------------------------------------------------------------------------- #
# the cross-talk
# --------------------------------------------------------------------------- #
def test_contribution_against_a_pattern_worked_by_hand():
    """Ten carbons: M+1 is 10 · 0.0107/0.9893 of M, and nothing else is."""
    counts = parse_formula("C10")
    mass = monoisotopic_mass(counts)
    fraction, step, _gap = iq.contribution(counts, mass,
                                           mass + NEUTRON_SPACING, 10.0)

    assert fraction == pytest.approx(10 * 0.0107 / 0.9893, rel=1e-3)
    assert step == 1


def test_the_analyte_reaches_the_standard_and_the_standard_reaches_nothing():
    """
    The direction is the whole finding: the light compound climbs into the
    heavy one's ions and the heavy one climbs away from everything.

    And how far it climbs is the tolerance's business. The analyte's M+4 is
    4.0134 Da up, the standard's M is 4.0251 up, so they are 0.0117 Da — 27
    ppm at m/z 430 — apart: separated at 10 ppm and merged at a unit window.
    """
    d0 = dict(parse_formula(FORMULA))
    for element, n in parse_formula(_ADD.added).items():
        d0[element] = d0.get(element, 0) + n
    d4 = dict(d0)
    d4["D"], d4["H"] = LABELS, d4["H"] - LABELS

    assert D4_MZ - D0_MZ == pytest.approx(4.0251, abs=1e-3)
    assert iq.contribution(d0, D0_MZ, D4_MZ, 10.0)[0] == 0.0
    wide = iq.contribution(d0, D0_MZ, D4_MZ, 1160.0)     # a unit window
    assert wide[0] == pytest.approx(0.00058, rel=0.1)
    assert wide[1] == 4                                   # it is the M+4
    # and never the other way
    for tolerance in (10.0, 30.0, 50.0, 1160.0):
        assert iq.contribution(d4, D4_MZ, D0_MZ, tolerance)[0] == 0.0


def test_crosstalk_is_taken_off_the_standard_and_the_ratio_says_so():
    mz, intensity = mixture(1_000.0)
    a = iq.responses(mz, intensity, analyte(), polarity="Positive")
    s = iq.responses(mz, intensity, standard(), polarity="Positive")
    result = iq.ratio(a, s, iq.ON_LADDER)

    assert result.value is not None
    assert result.into_analyte == 0.0             # the heavy one leaks nothing
    assert result.into_standard > 0.0
    assert result.corrected
    assert result.corrected_standard == pytest.approx(
        result.standard - result.into_standard)
    assert result.value > result.raw              # a smaller denominator
    assert result.leaks and all(leak.step >= 1 for leak in result.leaks)
    assert "counts taken off the standard" in result.describe()


def test_the_leak_is_the_fully_dehydrated_rung_two_point_nine_millidaltons_away():
    """
    The one place a d4 pair overlaps closely: the standard's rung that shed
    three labels with three waters keeps one deuterium and sits 1.00628 Da
    above the analyte's own rung, while the analyte's carbon-13 satellite of
    that rung sits 1.00335 above it — 2.9 mDa apart.
    """
    mz, intensity = mixture(1_000.0)
    a = iq.responses(mz, intensity, analyte(), polarity="Positive")
    s = iq.responses(mz, intensity, standard(), polarity="Positive")
    leaks = iq.crosstalk(a, s, iq.ON_LADDER, tolerance_ppm=10.0)

    close = [leak for leak in leaks if leak.step == 1]
    assert len(close) == 1
    leak = close[0]
    assert abs(leak.gap_mda) == pytest.approx(2.92, abs=0.1)
    # a carbon-13 satellite of a C24 ion, so about a quarter of the rung
    assert leak.fraction == pytest.approx(0.265, abs=0.01)
    assert leak.intensity == pytest.approx(265.0, rel=0.05)
    # every other leak is a higher satellite reaching a rung further up, and
    # all of them are far smaller
    assert all(other.fraction < leak.fraction / 50 for other in leaks
               if other is not leak)


def test_a_shared_ion_is_refused_rather_than_divided():
    """An analyte and its standard measured on the same ion measure their
    sum, and a sum over part of itself is not a ratio."""
    mz, intensity = mixture(1_000.0)
    shared = sorted(rungs(0), key=lambda i: i.mz)[0].mz
    a = iq.responses(mz, intensity, analyte(fragment=float(shared)),
                     polarity="Positive")
    s = iq.responses(mz, intensity, standard(fragment=float(shared)),
                     polarity="Positive")
    result = iq.ratio(a, s, iq.ON_FRAGMENT)

    assert result.refused
    assert result.value is None
    assert "share an ion" in result.note
    assert "share an ion" in result.describe()


def test_no_correction_where_the_instrument_removed_the_envelope():
    """
    A product-ion acquisition isolates its precursor, so the satellites never
    reached the collision cell and there is nothing to take off. Measured on
    the real infusions at 0.00 – 1.44% of the predicted M+1; here the
    envelope is simply absent.
    """
    mz, intensity = mixture(1_000.0, envelope=False)
    a = iq.responses(mz, intensity, analyte(), polarity="Positive")
    s = iq.responses(mz, intensity, standard(), polarity="Positive")

    assert a.transmission is not None
    assert a.transmission < iq.ISOTOPES_TRANSMITTED
    assert "predicts an M+1" in a.transmission_basis

    result = iq.ratio(a, s, iq.ON_LADDER)
    assert result.into_standard == 0.0
    assert not result.corrected
    assert "no isotope envelope in this spectrum" in result.correction_note
    assert result.value == pytest.approx(result.raw)


def test_a_full_envelope_is_transmission_one():
    mz, intensity = mixture(1_000.0)
    s = iq.responses(mz, intensity, standard(), polarity="Positive")
    # not exactly one: the reference ion's M+1 window also holds a little of
    # a neighbouring rung's envelope, which is the same 2.9 mDa overlap
    assert s.transmission == pytest.approx(1.0, abs=0.15)
    assert s.transmission > iq.ISOTOPES_TRANSMITTED


# --------------------------------------------------------------------------- #
# the curve
# --------------------------------------------------------------------------- #
LEVELS = (1.0, 2.0, 5.0, 10.0, 20.0)


def _series(basis: str) -> list[CalibrationPoint]:
    points = []
    for level in LEVELS:
        mz, intensity = mixture(1_000.0 * level)
        a = iq.responses(mz, intensity, analyte(), polarity="Positive")
        s = iq.responses(mz, intensity, standard(), polarity="Positive")
        points.append(CalibrationPoint(f"S{level:g}", f"S{level:g}", level,
                                       iq.ratio(a, s, basis).value))
    return points


@pytest.mark.parametrize("basis", [iq.ON_PRECURSOR, iq.ON_LADDER])
def test_the_curve_recovers_every_level_of_a_known_series(basis):
    points = _series(basis)
    curve = fit_curve(points, LINEAR, "1", "Cholic acid")

    assert curve.is_fitted
    assert curve.r2 == pytest.approx(1.0, abs=1e-6)
    for point in points:
        back = curve.concentration_at(point.response)
        assert back == pytest.approx(point.concentration, rel=1e-6)


def test_a_fragment_chosen_by_height_is_not_the_same_ion_at_every_level():
    """
    The reason `ladder` is the default and the reason the rows say so: left
    to take the tallest peak, the basis moves as the analyte grows against
    the standard, and a curve then fits different ions at different levels.
    """
    points = _series(iq.ON_FRAGMENT)
    curve = fit_curve(points, LINEAR, "1", "Cholic acid")
    assert curve.r2 < 0.99


# --------------------------------------------------------------------------- #
# rows the rest of the program reads
# --------------------------------------------------------------------------- #
def _row(level: float = 4.0, key: str = "/d/a.wiff|0") -> iq.InfusionResult:
    mz, intensity = mixture(1_000.0 * level)
    a = iq.responses(mz, intensity, analyte(), polarity="Positive")
    s = iq.responses(mz, intensity, standard(), polarity="Positive")
    return iq.InfusionResult(
        sample_key=key, sample_name="infusion A", analyte="Cholic acid",
        standard="CA-d4", analyte_response=a, standard_response=s,
        result=iq.ratio(a, s, iq.ON_LADDER), actual_concentration=level)


def test_a_row_is_a_peak_result_with_no_time_on_it():
    row = _row()
    peak = row.to_peak_result()

    assert isinstance(peak, PeakResult)
    assert peak.algorithm == iq.INFUSION
    assert peak.rt == 0.0 and peak.width == 0.0
    assert peak.expected_rt is None and peak.rt_delta is None
    assert peak.snr is None and peak.points is None
    assert peak.found                       # the response went into `area`
    assert peak.area == pytest.approx(row.response)
    assert peak.internal_standard == "CA-d4"
    assert peak.area_ratio == pytest.approx(row.ratio)
    assert peak.response("ratio") == pytest.approx(row.ratio)
    assert "quantified on the ladder" in peak.note
    # and it survives being saved and read back, which a subclass would not
    assert PeakResult.from_dict(peak.to_dict()) == peak


def test_results_set_carries_a_row_for_the_standard_too():
    rows = [_row()]
    results = iq.results_set(rows)

    assert len(results) == 2
    names = {r.component for r in results}
    assert names == {"Cholic acid", "CA-d4"}
    assert all(r.algorithm == iq.INFUSION for r in results)


def test_the_results_table_shows_an_infusion_row_unchanged(qapp):
    """
    The least invasive way to reach the Results table is to *be* a
    `PeakResult`: the model reads every column off one by name, so a row
    with no retention time and no width needs no new column, no new branch
    and no isinstance anywhere. This is that claim, driven.
    """
    from milq.ui.results_table import COLUMNS, FIELD_INDEX, ResultsTable

    session = _session()
    session.results = iq.results_set([_row()])
    table = ResultsTable(session)
    table.reload()
    model = table.model

    assert model.rowCount() == 2
    def cell(row, field):
        index = model.index(row, FIELD_INDEX[field])
        return model.data(index)

    row = next(i for i in range(2) if cell(i, "component") == "Cholic acid")
    assert cell(row, "algorithm") == iq.INFUSION
    assert cell(row, "internal_standard") == "CA-d4"
    assert float(str(cell(row, "area")).replace(",", "")) > 0
    # the time columns are empty rather than a made-up number
    assert cell(row, "expected_rt") in ("", "—", None)
    assert cell(row, "rt_delta") in ("", "—", None)
    assert cell(row, "snr") in ("", "—", None)
    # and every column answers something rather than raising
    for column in range(len(COLUMNS)):
        model.data(model.index(row, column))
    table.close()


def test_row_cells_fill_every_column():
    cells = iq.row_cells(_row())
    assert len(cells) == len(iq.QUANT_COLUMNS)
    assert cells[1] == "Cholic acid" and cells[2] == "CA-d4"


def test_write_csv_round_trips(tmp_path):
    quantitation = iq.InfusionQuantitation(rows=[_row()])
    path = iq.write_csv(quantitation, tmp_path / "q.csv")
    lines = open(path, encoding="utf-8").read().splitlines()

    assert lines[0].startswith("Sample,Analyte,Standard")
    assert len(lines) == 2


# --------------------------------------------------------------------------- #
# a whole session, and the panel
# --------------------------------------------------------------------------- #
def _entry(name: str, level: float, concentration: float | None = None,
           envelope: bool = False) -> SampleEntry:
    """One infused sample holding both compounds, as a reader would give it."""
    peaks = dict(mixture_pairs(level, envelope))
    mz = _grid(list(peaks))
    channel = FakeChannel(0, mz, peaks, precursor=D4_MZ, collision_energy=20.0)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name,
                        sample_type=STANDARD if concentration else "Unknown",
                        actual_concentration=concentration)
    entry.sample = FakeSample([channel], name=name)
    return entry


def mixture_pairs(level: float, envelope: bool = False):
    """The mixture as {m/z: height}, which is what a FakeChannel takes."""
    out: dict[float, float] = {}
    for mass, height in (ladder_peaks(0, 1_000.0 * level, envelope)
                         + ladder_peaks(LABELS, 2_000.0, envelope)):
        out[mass] = out.get(mass, 0.0) + height
    return out


def _session(*entries) -> Session:
    session = Session()
    session.entries.extend(entries)
    session.method.replace_all([analyte(), standard()])
    return session


def test_pairs_of_finds_the_analyte_and_its_standard():
    session = _session()
    pairs = iq.pairs_of(session.method)
    assert [(a.name, s.name) for a, s in pairs] == [("Cholic acid", "CA-d4")]


def test_quantify_infusions_over_a_session():
    session = _session(_entry("infusion_A", 4.0), _entry("infusion_B", 8.0))
    quantitation = iq.quantify_infusions(session)

    assert len(quantitation) == 2
    assert quantitation.on == iq.ON_LADDER
    ratios = [row.ratio for row in quantitation.rows]
    assert all(r is not None and r > 0 for r in ratios)
    # twice the analyte is twice the ratio
    assert max(ratios) == pytest.approx(2 * min(ratios), rel=1e-6)
    assert "2 pair(s) over 2 infusion(s)" in quantitation.summary()
    assert len(quantitation.results()) == 4


def test_a_session_with_no_internal_standard_says_so():
    session = _session(_entry("infusion_A", 4.0))
    session.method.replace_all([Component(name="Cholic acid",
                                          formula=FORMULA, precursor=D0_MZ)])
    quantitation = iq.quantify_infusions(session)

    assert not quantitation.rows
    assert "names an internal standard" in quantitation.note


def test_a_session_with_no_infusion_says_so():
    session = _session()
    quantitation = iq.quantify_infusions(session)
    assert "reads as a direct infusion" in quantitation.note


def test_the_dialog_measures_writes_and_records(qapp, tmp_path):
    from milq.ui.infusion_quant_dialog import InfusionQuantDialog

    session = _session(_entry("infusion_A", 1.0, concentration=1.0),
                       _entry("infusion_B", 2.0, concentration=2.0),
                       _entry("infusion_C", 5.0, concentration=5.0))
    dialog = InfusionQuantDialog(session)
    quantitation = dialog.measure()

    assert len(quantitation.rows) == 3
    assert dialog.table.rowCount() == 3
    assert dialog.table.columnCount() == len(iq.QUANT_COLUMNS)
    assert dialog.btn_apply.isEnabled()
    # the cross-talk column carries the reason as its tooltip, not the cell
    column = iq.QUANT_COLUMNS.index("Cross-talk")
    assert dialog.table.item(0, column).toolTip()

    written = dialog.apply()
    assert written == len(session.results) == 6
    assert all(r.algorithm == iq.INFUSION for r in session.results)

    # the curve fitted over the three concentrations, and recovers them
    curve = session.calibrations.get("Cholic acid")
    assert curve is not None and curve.is_fitted
    assert curve.r2 == pytest.approx(1.0, abs=1e-6)
    for result in session.results:
        if result.component == "Cholic acid":
            assert result.calculated_concentration == pytest.approx(
                result.actual_concentration, rel=1e-4)

    # one audit entry, naming the pair and the basis
    entries = [e for e in session.audit
               if e.what == audit.INFUSION_QUANTITATION]
    assert len(entries) == 1
    assert "Cholic acid / CA-d4" in entries[0].target
    assert "ladder" in entries[0].after
    assert "ppm" in entries[0].note

    path = dialog.export_csv(str(tmp_path / "ratios.csv"))
    assert os.path.exists(path)
    dialog.close()


def test_the_dialog_offers_the_three_bases_and_uses_the_one_chosen(qapp):
    from milq.ui.infusion_quant_dialog import InfusionQuantDialog

    session = _session(_entry("infusion_A", 4.0))
    dialog = InfusionQuantDialog(session)
    assert [dialog.basis.itemData(i) for i in range(dialog.basis.count())] \
        == list(iq.BASES)
    assert dialog.on == iq.ON_LADDER

    dialog.basis.setCurrentIndex(iq.BASES.index(iq.ON_PRECURSOR))
    quantitation = dialog.measure()
    assert quantitation.on == iq.ON_PRECURSOR
    assert quantitation.rows[0].on == iq.ON_PRECURSOR
    dialog.close()


def test_the_panel_offers_quantify(qapp):
    from milq.ui.infusions_panel import InfusionsPanel

    session = _session(_entry("infusion_A", 4.0))
    panel = InfusionsPanel(session)
    assert panel.btn_quantify.isEnabled()
    assert "internal standard" in panel.btn_quantify.toolTip()
    panel.close()
