"""
The nine ZenoTOF 7600 bile-acid infusions: CA-d4, DCA-d4, TDCA-d4.

Positive mode, no survey scan, product-ion channels only, 146 to 473 scans
each — and two of the nine that turned out not to be what their names say.
Nearly every figure in `CLAUDE.md`'s infusion bullets was measured on these:
the flatness that decides an infusion is one, the spray mask, the noise floor,
the ladder that recalibrates an axis with no lock mass, the margin against the
impostors, and the isotopic purity that refuses to be measured.

`milq/infusion.py` names this folder in its own docstring, so `data.py`
defaults to it and the tests skip themselves when the drive is not mounted.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from milq import api, energy, infusion, infusion_compare, infusion_report
from milq import margin as _margin
from milq import mzml, purity
from milq.processing import centroid_spectrum
from milq.raw import open_raw

from . import data

CA_D4_EAD_22 = "CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1"
#: the two files named for CA-d4 whose method isolates 839.56 instead
TESTEARTIGO = "TESTEARTIGO"


@pytest.fixture(scope="module")
def files():
    return data.infusion_files()


@pytest.fixture(scope="module")
def session(files):
    """A session with all nine open, and a Qt application for what renders."""
    from milq.session import Session

    with api.headless():
        held = Session()
        for path in files:
            held.open_file(path)
        yield held
        held.close_all()


@pytest.fixture(scope="module")
def summary(session, tmp_path_factory):
    """
    `infusion_report.summarise` over the nine, with an own library built from
    the three CID runs — the measurement the Infusions tab makes.
    """
    path = tmp_path_factory.mktemp("own") / "bile.msp"
    own = api.Library.open(path, create=True)
    for entry in session.entries:
        if entry.name.endswith("TOFMSMS_Mix1"):
            channel = infusion.strongest_channel(entry.sample)
            averaged = infusion_report.average_spectrum(channel)
            mz, intensity = centroid_spectrum(np.asarray(averaged[0], float),
                                              np.asarray(averaged[1], float))
            own.add((mz, intensity), name=entry.name.split("_")[0],
                    precursor=channel.info.precursor,
                    collision_energy=channel.info.collision_energy)
    assert len(own) == 3
    with api.headless():
        yield infusion_report.summarise(session, library=own._library)


def _averaged_centroids(entry):
    channel = infusion.strongest_channel(entry.sample)
    averaged = infusion_report.average_spectrum(channel)
    return channel, centroid_spectrum(np.asarray(averaged[0], float),
                                      np.asarray(averaged[1], float))


# --------------------------------------------------------------------------- #
# an infusion is flat twice
# --------------------------------------------------------------------------- #
def test_all_nine_read_as_infusions_and_none_is_marginal(files):
    """
    `milq/infusion.py`'s measured table: the nine measure 0.9936 – 1.0000
    on both figures, against `FLAT_FRACTION` of 0.75 — 0.244 of margin.

    CLAUDE.md quotes 0.9937 – 1.0000, which is the same nine *without* the
    settling window; dropping a second off the front costs 0.002 and buys the
    short-run cases. The chromatographic half of that measurement — never past
    0.1148 — is in `test_eics.py` and `test_sphingolipids.py`'s files.
    """
    totals, channels = [], []
    for path in files:
        handle = open_raw(path)
        try:
            verdict = infusion.is_infusion(handle.sample(0))
            assert verdict.infusion, os.path.basename(path)
            totals.append(verdict.above_half)
            channels.append(verdict.channel_above_half)
        finally:
            handle.close()
    assert len(totals) == 9
    assert min(totals) == pytest.approx(0.9936, abs=0.0002)
    assert max(totals) == pytest.approx(1.0)
    assert min(channels) == pytest.approx(0.9936, abs=0.0002)
    assert min(min(totals), min(channels)) > infusion.FLAT_FRACTION


def test_three_of_nine_lose_scans_to_the_spray(files):
    """
    CLAUDE.md: "Three of nine files lose 1, 1 and 9 scans (0.6–2.8% of the ion
    current, base peak −0.6 to −2.9%)." The nine belongs to `DCA-d4_TOFMSMS_Mix1`,
    whose bursts at 1.07–1.10 min are what set `STABILITY_WINDOW`.
    """
    excluded = {}
    for path in files:
        handle = open_raw(path)
        try:
            sample = handle.sample(0)
            mask = infusion.mask_for(sample, infusion.strongest_channel(sample))
            excluded[os.path.basename(path)] = mask.excluded
        finally:
            handle.close()
    lost = {name: count for name, count in excluded.items() if count}
    assert sorted(lost.values()) == [1, 1, 9]
    assert lost["DCA-d4_TOFMSMS_Mix1.wiff"] == 9


def test_the_noise_floor_is_a_hundredth_of_the_constant(files):
    """
    CLAUDE.md: "Measured: 0.068–3.53 counts on the nine infusions, 28–1,500×
    quieter than the constant, (a) larger on nine of nine."

    `precursor.MIN_INTENSITY` is 100, written for a TripleTOF survey scan. On
    these nine the empty mass regions of the average measure between 0.068 and
    3.53 counts, and the empty-region reading is the larger of the two ways
    every time — which is what `noise_floor` keeps.
    """
    floors = {}
    for path in files:
        handle = open_raw(path)
        try:
            sample = handle.sample(0)
            measured = infusion.noise_floor(infusion.strongest_channel(sample))
            assert measured is not None, path
            assert measured.basis.startswith("the empty regions")
            floors[os.path.basename(path)] = measured.value
        finally:
            handle.close()
    assert len(floors) == 9
    assert min(floors.values()) == pytest.approx(0.068, abs=0.001)
    assert max(floors.values()) == pytest.approx(3.53, abs=0.01)
    assert 100.0 / max(floors.values()) == pytest.approx(28, abs=1)
    assert 100.0 / min(floors.values()) == pytest.approx(1470, abs=30)


# --------------------------------------------------------------------------- #
# an infusion recalibrates on its own precursor
# --------------------------------------------------------------------------- #
def test_seven_of_nine_correct_on_their_own_ladder(session):
    """
    CLAUDE.md: "On the nine bile-acid infusions 7 of 9 corrected, 3–8 rungs,
    −8.6 to +6.2 ppm (EAD high, CID low — per acquisition)."

    The top of that range now reads **+6.6 ppm** (`DCA-d4_TOFMSMS_Mix1`); the
    bottom, the rung counts and the count of corrected files are unchanged.
    The two that are not corrected are the pair whose method isolates 839.56,
    where no adduct of the compound's formula fits and there is no ladder to
    build.
    """
    corrections = {}
    for entry in session.entries:
        channel = infusion.strongest_channel(entry.sample)
        corrections[entry.name] = infusion_report.fit_axis(session, entry, channel)
    assert len(corrections) == 9
    usable = {name: c for name, c in corrections.items()
              if c is not None and c.usable}
    assert len(usable) == 7
    assert all(TESTEARTIGO not in name for name in usable)

    rungs = [len(c.lock_masses) for c in usable.values()]
    assert (min(rungs), max(rungs)) == (3, 8)
    offsets = [c.ppm_at(430.0) for c in usable.values()]
    assert min(offsets) == pytest.approx(-8.6, abs=0.1)
    assert max(offsets) == pytest.approx(6.6, abs=0.1)
    assert all(not c.linear for c in usable.values())


def test_the_correction_takes_ca_d4_from_14_per_cent_to_63(session):
    """
    CLAUDE.md, twice over. The adduct: "a formula alone on CA-d4 EAD 22 eV
    went from 1 of 31 ions and 21.7% to 8 of 56 and 63.6%, the whole ladder
    with a −1D rung beside each". The correction: "at 5 ppm CA-d4 EAD 22 eV
    goes 5 of 56 and 14.0% → 8 of 56 and 63.6%".

    Both reproduce exactly. The 5 ppm reading on the axis as measured is the
    point of the bullet: "Those spectra sit +4–7 ppm high on their own axis,
    so the panel's 5 ppm default gives 5 of 56."
    """
    entry = next(e for e in session.entries
                 if e.name == CA_D4_EAD_22)
    channel, (mz, intensity) = _averaged_centroids(entry)
    subject = infusion_report.axis_subject(session, "CA-d4",
                                           channel.info.precursor,
                                           channel.info.polarity)
    assert subject.formula == "C24H36D4O5"
    assert subject.adduct == "[M+NH4]+"

    correction = infusion_report.fit_axis(session, entry, channel)
    assert correction.usable

    def explained(masses, tolerance):
        said = api.explain((masses, intensity), formula=subject.formula,
                           adduct=subject.adduct, tolerance_ppm=tolerance)
        return said.matched, said.predicted, round(said.share * 100, 1)

    assert explained(mz, 5.0) == (5, 56, 14.0)
    assert explained(correction.apply(mz), 5.0) == (8, 56, 63.6)
    # at 20 ppm the axis does not have to be corrected to see the same ions
    assert explained(mz, 20.0) == (8, 56, 63.6)


# --------------------------------------------------------------------------- #
# a share is not evidence until something else has been scored beside it
# --------------------------------------------------------------------------- #
def test_the_margin_against_the_impostors(session):
    """
    CLAUDE.md: "`THIN_MARGIN` = 10 points, the one gap in eleven real spectra
    (−3.0 2.1 2.1 6.1 | 13.9 … 71.2); what falls below is a Cer at 538.6…
    and TDCA-d4 at 78.4% against a sodiated lysoPC at 72.3% — known from the
    bottle, not from its spectrum."

    Measured here on the seven with an adduct: CA-d4 at 22 eV clears its best
    rival by **41.9 points** (63.6% against a triacylglycerol's 21.7%),
    DCA-d4 at 22 eV by 13.9, and TDCA-d4 at 22 eV by only 6.1 — the thin one,
    against `PC O-16:0/0:0` at 72.3%.
    """
    margins = {}
    for entry in session.entries:
        channel, (mz, intensity) = _averaged_centroids(entry)
        subject = infusion_report.axis_subject(session,
                                               infusion_report.compound_of(entry.name),
                                               channel.info.precursor,
                                               channel.info.polarity)
        if not subject.adduct:
            continue
        explanation, _ = api._explanation((mz, intensity), formula=subject.formula,
                                          adduct=subject.adduct, tolerance_ppm=20.0)
        margins[entry.name] = _margin.cross_validate(
            mz, intensity, explanation, channel.info.precursor,
            channel.info.polarity)
    assert len(margins) == 7

    best = margins[CA_D4_EAD_22]
    assert best.share * 100 == pytest.approx(63.6, abs=0.1)
    assert best.points == pytest.approx(41.9, abs=0.2)
    assert best.best.share * 100 == pytest.approx(21.7, abs=0.2)

    thin = margins["TDCA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1"]
    assert thin.share * 100 == pytest.approx(78.4, abs=0.1)
    assert thin.points == pytest.approx(6.1, abs=0.2)
    assert thin.points < _margin.THIN_MARGIN
    assert thin.best.name == "PC O-16:0/0:0"
    assert thin.best.share * 100 == pytest.approx(72.3, abs=0.2)

    assert margins["DCA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1"].points == \
        pytest.approx(13.9, abs=0.2)
    assert max(m.points for m in margins.values()) == pytest.approx(71.2, abs=0.2)


# --------------------------------------------------------------------------- #
# the purity a product-ion scan cannot supply
# --------------------------------------------------------------------------- #
def test_the_isotopic_purity_refuses_itself_on_all_seven(session):
    """
    CLAUDE.md: "The measurement vetoes itself (`SATELLITE_SHARE`) when the
    fully-labelled ion's M+1 is under a quarter of what the formula demands —
    on all seven real infusions it is 0.006–0.206% against 26.5–30.0%: the
    quadrupole took the satellites."

    The demanded satellite reproduces to the decimal (26.5, 26.6 and 30.0%),
    every one of the seven is refused, and the two files with no adduct are
    not attempted at all — a refusal and a non-attempt being different things.
    """
    attempted, refused, demanded = 0, 0, []
    for entry in session.entries:
        channel, (mz, intensity) = _averaged_centroids(entry)
        subject = infusion_report.axis_subject(session,
                                               infusion_report.compound_of(entry.name),
                                               channel.info.precursor,
                                               channel.info.polarity)
        if not subject.adduct:
            assert TESTEARTIGO in entry.name
            continue
        floor = infusion.noise_floor(channel)
        measured = purity.isotopic_purity(
            mz, intensity, subject.formula, subject.adduct, n_labels=0,
            floor=None if floor is None else floor.value)
        attempted += 1
        refused += 0 if measured.usable else 1
        assert "M+1 satellite" in measured.reason
        demanded.append(round(measured.natural[1] * 100, 1))
    assert attempted == 7 and refused == 7
    assert min(demanded) == pytest.approx(26.5, abs=0.1)
    assert max(demanded) == pytest.approx(30.0, abs=0.1)


# --------------------------------------------------------------------------- #
# the summary of many
# --------------------------------------------------------------------------- #
def test_nine_rows_and_four_precursors_within_25_ppm(summary):
    """
    CLAUDE.md: "Measured on the nine ZenoTOF bile-acid infusions with the
    three CID runs as an own library… 4 of 9 precursors within 25 ppm, all the
    softer activations (the CID runs left 33 and 84 counts and the cell says
    so)."
    """
    assert len(summary) == 9
    assert summary.compounds == ["CA-d4", "DCA-d4", "TDCA-d4"]
    assert len(summary.confirmed) == 4
    assert "4 of 9 precursor(s) confirmed within 25 ppm" in summary.summary()


def test_the_two_teste_artigo_files_isolate_839_56(summary):
    """
    CLAUDE.md: "the two files named `CA-d4_…TESTEARTIGO` target **839.56**, not
    430.35 — no record within ±0.02 Da, 0 of 31 ions, 73 against each other and
    5–10 against the real CA-d4 files."

    Current: **73.5** against each other, and 0.0 – 8.6 against the three real
    CA-d4 runs — the same finding (CLAUDE.md's "5–10" is the pair of readings
    where anything at all was shared; two of the four share no peak). The
    reason the pair is visible at all is that they are still grouped and
    scored as CA-d4.
    """
    rows = {row.sample: row for row in summary.rows}
    pair = [name for name in rows if TESTEARTIGO in name]
    assert len(pair) == 2
    against_real = []
    for name in pair:
        row = rows[name]
        assert row.report.written_precursor == pytest.approx(839.56)
        assert row.report.hit is None
        assert row.report.isolation is None or not row.report.isolation.agrees
        others = {other[0]: other[1] * 100 for other in row.others}
        assert others[[n for n in pair if n != name][0]] == pytest.approx(73.5,
                                                                         abs=0.5)
        against_real += [score for other, score in others.items()
                         if other not in pair]
    assert len(against_real) == 6
    assert max(against_real) == pytest.approx(8.6, abs=0.3)
    assert max(against_real) < 73.5 / 8


def test_a_record_does_not_travel_between_activations(summary):
    """
    CLAUDE.md: "records from the CID infusions of CA-d4, DCA-d4 and TDCA-d4
    searched by the same compounds under EAD 22 eV put their own record first
    at 29.2, 33.3 and 61.5 against a best wrong record of 14.1; a record does
    not travel between activations (CA-d4 at 12 eV scores 6.4 against the CID
    record)."

    Current: 29.1, 33.1 and 61.4 — a tenth of a point, the records here being
    written from the api rather than from the Explorer — and 6.4 at 12 eV,
    exactly.
    """
    scores = {row.sample: (row.report.hit.entry.name,
                           row.report.hit.score * 100)
              for row in summary.rows if row.report.hit is not None}
    assert scores[CA_D4_EAD_22][1] == pytest.approx(29.1, abs=0.2)
    assert scores["DCA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1"][1] == \
        pytest.approx(33.1, abs=0.2)
    assert scores["TDCA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1"][1] == \
        pytest.approx(61.4, abs=0.2)
    assert scores["CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_mix1"][1] == \
        pytest.approx(6.4, abs=0.2)
    # every record finds its own vial's CID run at essentially 100
    for name in ("CA-d4_TOFMSMS_Mix1", "DCA-d4_TOFMSMS_Mix1",
                 "TDCA-d4_TOFMSMS_Mix1"):
        assert scores[name][1] > 98.0
        assert scores[name][0] == name.split("_")[0]


def test_the_energies_recommended_for_three_purposes(summary):
    """
    CLAUDE.md: "On the nine bile-acid infusions EAD 22 eV takes all three for
    CA-d4 and DCA-d4; TDCA-d4 splits — EAD 22 eV identifies it, 30 eV
    quantifies it at 63% of the intensity on 468.3071."

    Two of the three purposes are asserted here. **Identification recommends
    nothing** on this run, and that is not a regression: it needs a predicted
    ion count, which comes from the compound being a component of the method,
    and the session these files are opened into carries no component table.
    The figures that made the finding — the middle energy for a record, and
    TDCA-d4's 63% on 468.3071 — are all here.
    """
    picks = {rec.compound: {c.purpose: c for c in rec.choices}
             for rec in energy.recommend(summary)}
    assert sorted(picks) == ["CA-d4", "DCA-d4", "TDCA-d4"]
    for compound in ("CA-d4", "DCA-d4"):
        for purpose in ("quantitation", "a library record"):
            condition = picks[compound][purpose].condition
            assert (condition.activation, condition.energy) == ("EAD", 22.0)
    assert picks["TDCA-d4"]["a library record"].condition.energy == 22.0
    assert picks["TDCA-d4"]["quantitation"].condition.energy == 30.0
    assert "468.3071" in picks["TDCA-d4"]["quantitation"].sentence()
    assert "63%" in picks["TDCA-d4"]["quantitation"].sentence()
    assert all(picks[c]["identification"].condition is None for c in picks)


def test_a_summary_compared_with_itself_moves_nothing(summary):
    """
    CLAUDE.md: `infusion_compare` "marks *moved* on `standard_history`'s two
    rules only (base peak past `SAME_PEAK_PPM`, height past `qc.OUT_PERCENT`)
    and never on the cosine (two days are two points)."

    The identity: the same nine against themselves are nine matched rows, a
    median score of 100, the same base-peak ion in 9 of 9, and nothing moved.
    """
    comparison = infusion_compare.compare_infusions(summary, summary,
                                                    "today", "today")
    assert len(comparison.rows) == 9
    assert comparison.only_current == [] and comparison.only_reference == []
    assert comparison.median_score == pytest.approx(100.0)
    assert comparison.moved == []
    for row in comparison.rows:
        assert row.same_base_peak
        assert row.base_gap_ppm == pytest.approx(0.0, abs=1e-9)
        assert row.intensity_change == pytest.approx(0.0, abs=1e-9)
    assert "9 of 9" in comparison.summary()


# --------------------------------------------------------------------------- #
# the document, and the format
# --------------------------------------------------------------------------- #
def test_the_folder_reports_nine_infusions(tmp_path):
    """
    CLAUDE.md: "On the nine bile-acid infusions the CLI gives 9 read, 0
    skipped." Written here as HTML rather than as the 48-page PDF, which is
    the same document without seventeen seconds of Qt layout.
    """
    with api.headless():
        document = api.infusion_report(data.infusions(), tmp_path / "nine.html")
    assert len(document) == 9
    assert os.path.getsize(document.path) > 100_000
    assert sorted({line.compound for line in document}) == ["CA-d4", "DCA-d4",
                                                            "TDCA-d4"]
    measured = [line for line in document
                if line.delta_ppm is not None and abs(line.delta_ppm) <= 25]
    assert len(measured) == 4
    # every one of them read its precursor off the product-ion average: these
    # acquisitions have no survey scan at all
    assert {line.precursor_from for line in document} == {"survivor"}


def test_an_mzml_average_reproduces_the_vendors(tmp_path):
    """
    CLAUDE.md: "against SCIEX's own average of the same 146 scans, 220,222 of
    221,847 masses higher, total 3.31×, 670 centroids against 424.
    Accumulating reproduces the vendor to max |Δ| 0.0."

    The 146 scans are `CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1`, its one
    channel. Interpolating onto the union of two TOF axes is what gave the
    3.31×; accumulating gives the vendor's own numbers back, to the last bit
    of the intensity and to 2·10⁻¹³ Da of the mass.
    """
    source = next(path for path in data.infusion_files()
                  if CA_D4_EAD_22 in path)
    handle = open_raw(source)
    try:
        sample = handle.sample(0)
        assert len(sample.channels) == 1
        path = tmp_path / "one.mzML"
        mzml.write_mzml(sample, path)
        back = open_raw(path)
        try:
            channel = sample.channels[0]
            x, _ = channel.tic()
            assert len(x) == 146
            mine = back.sample(0).channels[0].spectrum_rt_range(float(x[0]),
                                                                float(x[-1]))
            theirs = channel.spectrum_rt_range(float(x[0]), float(x[-1]), False)
            assert len(theirs[0]) == len(mine[0]) == 221_847
            assert float(np.max(np.abs(theirs[1] - mine[1]))) == 0.0
            assert float(np.max(np.abs(theirs[0] - mine[0]))) < 1e-12
        finally:
            back.close()
    finally:
        handle.close()
