"""
The whole direct-infusion path, run once, with the cross-module agreements
asserted rather than the values.

Every other infusion test here takes one module and checks what it answers.
This one runs the path a folder of standards actually goes through — the
folder check, the verdict, the spray mask, the average, the noise floor, the
isolation verdict, the mass axis, the explanation, the record, the component,
the energy, the report, the cover, the exports, the comparison and the API —
and asks a different question of it: **do two modules that answer the same
question give the same answer?**

That is not what a per-module test can see. `library.records_from_summary`
wrote the run's scan count where the report's header wrote the averaged one,
and both were right about their own number; `axis_subject` folded a d4
standard's labels in twice and every module it did not touch stayed green;
`api.infusion_average` averaged the whole run where the application masked
it. Each of those was found by running the path end to end on nine real
acquisitions and putting the numbers side by side, and each is asserted
below on data made here.

The fixture carries a **spray burst on purpose**. Without one the mask
excludes nothing, `average_stable` hands back the reader's own average, and
half of what follows would pass on a build that had never heard of a mask.
`test_the_fixture_loses_scans` is the guard on that.

The figures the nine real acquisitions gave are in the manual's
`integration` page; nothing here asserts them, because they are a
measurement of somebody's instrument and these are a property of the code.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import (api, chemistry, energy, folder,  # noqa: E402
                       infusion, infusion_compare, infusion_cover,
                       infusion_quant, infusion_report as ir, library as lib,
                       margin, mzml, standard_history, standards,
                       unexplained)
from milq.components import Component  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

#: a bile-acid standard whose name the standards table knows, carrying four
#: labels its name declares and does not place — which is the case
#: `axis_subject` folded twice
COMPOUND = "TDCA-d4"
UNLABELLED = "C26H45NO6S"
LABELLED = "C26H41D4NO6S"
ADDUCT = "[M+H]+"
PRECURSOR = chemistry.mass_from_formula(LABELLED, ADDUCT)
#: as a method writes it: two decimals, which is all a channel carries
WRITTEN = round(PRECURSOR, 2)

SCANS = 200
#: where the spray drops out, and to what share of its own level. A drop
#: rather than a spike so the flatness reference — the 99th-percentile scan
#: — is untouched and the run still reads as an infusion
BURST = (88, 89, 90)
BURST_SHARE = 0.2


def _cluster(centre: float, height: float, points: int = 7,
             step: float = 0.004):
    offsets = (np.arange(points) - points // 2) * step
    return centre + offsets, height * np.exp(-0.5 * (offsets / (1.5 * step)) ** 2)


def _spectrum(ions):
    mz = np.concatenate([_cluster(m, h)[0] for m, h in ions])
    intensity = np.concatenate([_cluster(m, h)[1] for m, h in ions])
    order = np.argsort(mz)
    return mz[order], intensity[order]


class _Channel:
    """Enough of the reader's channel for `mzml.write_mzml`."""

    def __init__(self, index, info, times, spectra):
        self.index, self.info = index, info
        self._times = np.asarray(times, dtype=float)
        self._spectra = spectra

    def tic(self):
        return self._times, np.array([float(s[1].sum())
                                      for s in self._spectra])

    @property
    def rt(self):
        return self._times

    def spectrum(self, scan, add_zeros=True):
        return self._spectra[int(scan)]


class _Sample:
    instrument = "ZenoTOF 7600"
    acquisition_time = "2026-09-10T09:00:00Z"

    def __init__(self, name, channels):
        self.name, self.channels = name, channels


def _write_infusion(path, energy_ev: float = 25.0, precursor=PRECURSOR,
                    burst=BURST):
    """
    One infused standard: the same spectrum every scan, with the spray
    dropping out for three of them part way through.

    The ions are the precursor and two of the water losses its formula
    predicts, so the component table's formula explains it and the ladder
    `recalibrate.fit_infusion` looks for is there to be found.
    """
    times = np.arange(SCANS) * 0.005
    water = chemistry.monoisotopic_mass({"H": 2, "O": 1})
    ions = [(precursor, 1000.0), (precursor - water, 620.0),
            (precursor - 2 * water, 240.0), (124.0063, 700.0)]
    spectra = []
    for scan in range(SCANS):
        share = BURST_SHARE if scan in burst else 1.0
        spectra.append(_spectrum([(m, h * share) for m, h in ions]))
    info = ChannelInfo(0, "TOF PI", "Product Ion", "Positive",
                       round(precursor, 2), 100.0, 600.0, SCANS, energy_ev)
    mzml.write_mzml(_Sample("infused", [_Channel(0, info, times, spectra)]),
                    path)
    return str(path)


#: a second compound, present for one reason: `samples.shorten_names` strips
#: the prefix every open sample shares, so a folder of one compound has its
#: compound stripped out of every name and `compound_of` proposes whatever is
#: left. Two compounds share no prefix and the names stand.
OTHER = "CA-d4"
OTHER_UNLABELLED = "C24H40O5"
OTHER_LABELLED = "C24H36D4O5"
OTHER_ADDUCT = "[M+NH4]+"
OTHER_PRECURSOR = chemistry.mass_from_formula(OTHER_LABELLED, OTHER_ADDUCT)


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    """Two infusions of one standard at two energies, and one of another."""
    home = tmp_path_factory.mktemp("integration-path")
    names = ((f"{COMPOUND}_TOFMSMS_EAD_25CE_mix1", 25.0, PRECURSOR),
             (f"{COMPOUND}_TOFMSMS_CID_40CE_mix1", 40.0, PRECURSOR),
             (f"{OTHER}_TOFMSMS_CID_40CE_mix1", 40.0, OTHER_PRECURSOR))
    paths = [_write_infusion(home / f"{name}.mzML", energy_ev=ev,
                             precursor=mass)
             for name, ev, mass in names]
    return {"folder": str(home), "paths": paths}


@pytest.fixture(scope="module")
def opened(data):
    """The session, the summary and the own library — the path, run once."""
    session = Session()
    for path in data["paths"]:
        session.open_file(path)
    session.method = ProcessingMethod()
    session.method.replace_all([
        Component(name=COMPOUND, precursor=WRITTEN, formula=UNLABELLED,
                  adduct=ADDUCT),
        Component(name=OTHER, precursor=round(OTHER_PRECURSOR, 2),
                  formula=OTHER_UNLABELLED, adduct=OTHER_ADDUCT)])
    first = ir.summarise(session)
    made = lib.records_from_summary(first.rows[:1])
    msp = os.path.join(data["folder"], "own.msp")
    lib.write_msp(made.entries, msp)
    own = lib.load_library(msp)
    summary = ir.summarise(session, library=own)
    session.infusion_summary = summary
    yield {"session": session, "summary": summary, "own": own,
           "records": made, "msp": msp, "folder": data["folder"],
           "paths": data["paths"]}
    session.close_all()


def _first(opened):
    """The first row, its report, its entry and its channel."""
    row = opened["summary"].rows[0]
    entry = opened["session"].entries[0]
    return row, row.report, entry, infusion.strongest_channel(entry.sample)


# --------------------------------------------------------------------------- #
# the fixture is worth testing against
# --------------------------------------------------------------------------- #
def test_the_fixture_loses_scans(opened):
    """
    The guard on everything below.

    A mask that excludes nothing makes `average_stable` hand back the
    reader's own average untouched, and then the masked and unmasked routes
    agree for the wrong reason — which is exactly how three of these
    disagreements survived until they were run on a real spray.
    """
    _row, report, _entry, _channel = _first(opened)
    mask = report.mask
    assert mask is not None and mask.excluded, \
        "the fixture's spray never faltered, so nothing below is a test"
    assert mask.kept == mask.n_scans - mask.excluded
    assert report.verdict and report.verdict.infusion, \
        "the burst must not cost the run its infusion verdict"


def test_the_whole_path_runs_and_every_row_is_a_report(opened):
    summary = opened["summary"]
    assert len(summary) == len(opened["paths"])
    assert set(summary.compounds) == {COMPOUND, OTHER}
    for row in summary.rows:
        assert row.report is row.report, "a row is its own report"
        assert row.report.spectrum is not None
        assert row.report.explanation is not None, row.explanation_note


# --------------------------------------------------------------------------- #
# one average
# --------------------------------------------------------------------------- #
def test_the_api_averages_what_the_application_averages(opened):
    """
    `api.Acquisition.infusion_average` says it is the Explorer's view and has
    to be it. Averaging the whole run instead moved the base peak by up to
    2.9% on the real acquisitions and reported the run's scan count beside
    it, so a script and the window disagreed about one spectrum.
    """
    _row, report, entry, channel = _first(opened)
    mine = infusion.average_stable(channel, infusion.mask_for(entry.sample,
                                                              channel))
    run = api.open(opened["paths"][0])
    try:
        theirs = run.infusion_average()
        assert theirs is not None
        assert np.allclose(theirs.mz, mine[0])
        assert np.allclose(theirs.intensity, mine[1])
        assert theirs.scans == report.scans_averaged()
        assert theirs.scans != report.scans, \
            "the fixture loses scans, so these two must differ"
    finally:
        run.close()


def test_infusion_quantitation_reads_the_masked_average(opened):
    """
    A response and the height printed beside it on the page come off one
    spectrum. `centroids_of` averaged the whole run, so a ratio carried the
    spray burst of whichever vial had one.
    """
    _row, _report, entry, channel = _first(opened)
    from milq.processing import centroid_spectrum

    masked = infusion_quant.centroids_of(channel, entry.sample)
    whole = infusion_quant.centroids_of(channel)
    expected = centroid_spectrum(
        *infusion.average_stable(channel,
                                 infusion.mask_for(entry.sample, channel)))
    assert np.allclose(masked[0], expected[0])
    assert np.allclose(masked[1], expected[1])
    assert not np.isclose(masked[1].max(), whole[1].max()), \
        "the burst has to move the base peak, or this proves nothing"


# --------------------------------------------------------------------------- #
# one count of scans
# --------------------------------------------------------------------------- #
def test_every_account_of_the_average_counts_the_same_scans(opened):
    """
    The pane's title, the report's header, the tab's *Scans* column and the
    comment on a record of one's own are four accounts of one average. The
    record used to carry the run's count, so it claimed scans the spray had
    faltered on.
    """
    _row, report, _entry, _channel = _first(opened)
    averaged = report.scans_averaged()
    assert averaged < report.scans, "the fixture must lose scans"

    assert report.scans_cell() == f"{averaged:,} of {report.scans:,}"
    assert f"{averaged:,} averaged" in report.scans_line()

    entry = opened["records"].entries[0]
    provenance = lib.provenance_of(entry)
    assert provenance.scans == averaged, (
        f"the record says {provenance.scans} scans where the report says "
        f"{averaged}")
    assert f"average of {averaged:,} scans" in entry.fields.get("Comment", "")


# --------------------------------------------------------------------------- #
# one formula
# --------------------------------------------------------------------------- #
def test_the_mass_axis_and_the_isolation_verdict_name_one_formula(opened):
    """
    `labelled_formula` returns a formula with its labels already folded in
    *and* how many it folded. Taking both made every d4 standard a d8 one in
    `axis_subject` alone: the ladder then looked for masses 4 Da away, found
    nothing, and every infusion refused its own axis while the isolation
    verdict on the same page named the compound correctly.
    """
    _row, report, entry, channel = _first(opened)
    subject = ir.axis_subject(opened["session"], report.compound,
                              report.written_precursor, report.polarity)
    assert subject, subject.why
    assert subject.formula == LABELLED, (
        f"the axis is built from {subject.formula}, not {LABELLED} — the "
        f"labels were folded in twice")
    assert subject.adduct == ADDUCT

    # the explanation reached the same formula by its own route. Its
    # *record* carries the unlabelled one with the label count beside it,
    # because that is the pair `explain_formula` wants — so what has to
    # agree is the formula a reader is shown and the one a record is
    # written with, both of which fold the labels in exactly once
    assert LABELLED in report.basis, report.basis
    assert lib.identity_of(report)[0] == LABELLED

    # and so did the isolation verdict, which reads the same component
    # table. The report's own is used rather than a second call, because the
    # proposal comes from the *entry's* name and not from the sample's —
    # a manual acquisition calls its sample `sample`
    isolation = report.isolation
    assert isolation is not None and isolation.agrees, \
        (isolation.sentence() if isolation else "no verdict")
    assert isolation.formula == LABELLED, isolation.formula
    assert ir.what_the_method_isolates(
        entry.sample, opened["session"].method.components,
        name=entry.name).formula == LABELLED

    # with one formula the ladder has something to look for
    assert report.correction is not None
    assert report.correction.usable, report.correction.verdict


def test_a_component_written_from_the_row_carries_that_same_formula(opened):
    row, _report, _entry, _channel = _first(opened)
    component = standards.component_from_infusion(row)
    assert component is not None
    assert component.formula == LABELLED
    assert component.adduct == ADDUCT
    assert component.precursor == pytest.approx(PRECURSOR, abs=1e-6)


# --------------------------------------------------------------------------- #
# one noise floor per answer
# --------------------------------------------------------------------------- #
def test_the_floor_a_report_gates_on_is_the_floor_it_prints(opened):
    """
    There are two measured floors — the channel's whole-run one, which the
    Explorer shows, and the report's, taken off the masked average with the
    count of scans in it. Which is which is a decision; a page gating its
    peaks on one and printing the other is not.
    """
    _row, report, _entry, channel = _first(opened)
    assert report.noise_floor is not None
    assert report.floor == pytest.approx(report.noise_floor.value)
    assert report.noise_floor.describe()

    # the report's floor is taken over the scans it averaged, not the run's
    assert report.noise_floor.scans == report.scans_averaged()

    # the channel's own is a separate measurement over a different count of
    # scans, which is the whole reason there are two of them
    whole = infusion.noise_floor_for(channel)
    assert whole.scans == report.scans, whole.scans
    assert whole.scans != report.noise_floor.scans


def test_the_unexplained_peaks_are_held_to_the_printed_floor(opened):
    _row, report, _entry, _channel = _first(opened)
    for _mz, height in report.unexplained():
        assert height >= report.floor
    rows = report.annotations(most=10)
    assert unexplained.tally(rows).sentence() is not None


# --------------------------------------------------------------------------- #
# one verdict about the precursor
# --------------------------------------------------------------------------- #
def test_the_row_the_report_and_the_cover_agree_about_the_precursor(opened):
    """
    Three places count confirmed precursors: the tab's summary line, the
    report's sentence and the folder cover's paragraph. They read one
    property or they are three opinions.
    """
    summary = opened["summary"]
    confirmed = [row for row in summary.rows if row.confirmed]
    written = [row for row in summary.rows if row.report.written_precursor]
    assert f"{len(confirmed)} of {len(written)} precursor(s) confirmed" \
        in summary.summary()
    assert f"{len(confirmed)} of {len(written)} precursor(s) confirmed" \
        in infusion_cover.verdict(summary)

    for row in summary.rows:
        error = row.report.error_ppm()
        said = " ".join(row.report.sentences())
        if row.confirmed:
            assert f"confirmed at {error:+.1f} ppm" in said
        elif error is not None:
            assert "not confirmed" in said


def test_the_cover_names_an_isolated_mass_before_it_names_a_ppm(opened):
    """
    A row whose method targets a mass the compound's other runs do not is a
    different ion, not an instrument out of calibration. Asking for the error
    first made `isolated_precursors` unreachable as soon as the measured
    noise floor let those windows report one.
    """
    class _Row:
        def __init__(self, compound, written, confirmed, error):
            self.compound, self.confirmed = compound, confirmed
            self.sample = f"{compound}-{written}"
            self.precursor_note = ""
            self.report = type("R", (), {
                "written_precursor": written,
                "survivor_note": "",
                "error_ppm": staticmethod(lambda e=error: e)})()

    rows = [_Row(COMPOUND, WRITTEN, True, 4.0),
            _Row(COMPOUND, WRITTEN, True, 6.0),
            _Row(COMPOUND, 839.56, False, -43.0),
            _Row(COMPOUND, 839.56, False, -42.9)]
    said = infusion_cover._precursor_sentence(rows)
    assert "2 whose method isolates 839.56" in said, said
    assert "-43.0" not in said, \
        "a mass the method never meant to isolate is not a mass error"


# --------------------------------------------------------------------------- #
# the folder check reads names, and only the names somebody made
# --------------------------------------------------------------------------- #
def test_the_folder_check_ignores_what_the_operating_system_left(opened,
                                                                 tmp_path):
    """
    macOS writes `._X` beside every `X` on a volume that is not APFS, which
    is where instrument data travels. `._run.wiff.scan` ends in `.scan` and
    belongs to no `.wiff`, so it was reported as a stray; `._run.wiff` would
    have been opened.
    """
    (tmp_path / "run.wiff").write_bytes(b"")
    (tmp_path / "run.wiff.scan").write_bytes(b"")
    (tmp_path / "._run.wiff.scan").write_bytes(b"")
    (tmp_path / "._run.wiff").write_bytes(b"")
    (tmp_path / ".DS_Store").write_bytes(b"")

    report = folder.check_files([str(tmp_path)])
    assert [os.path.basename(p) for p in report.paths] == ["run.wiff"]
    assert report.of_kind(folder.STRAY_SCAN) == []
    assert report.of_kind(folder.MISSING_SCAN) == []

    # a dot-file named outright was meant, and still goes through
    named = folder.check_files([str(tmp_path / "._run.wiff")])
    assert len(named.paths) == 1


# --------------------------------------------------------------------------- #
# the rest of the path still runs on what the rest of the path made
# --------------------------------------------------------------------------- #
def test_the_record_is_found_again_with_every_one_of_its_peaks(opened):
    """
    A record made from a run is matched by that run on **every peak it
    carries** — the reverse score and the *N of N* count, which is what
    proves the round trip. The forward score need not be 100: the record is
    written at one per cent of the base peak and the search reads every
    centroid, so the query may hold peaks the record was never given.
    """
    row, report, _entry, _channel = _first(opened)
    hit = report.hit
    assert hit is not None, row.library_note
    assert hit.entry.name == COMPOUND
    assert len(hit.pairs) == hit.entry.peaks, \
        "a record must find every one of its own peaks in its own run"
    assert hit.reverse == pytest.approx(1.0, abs=1e-6)
    assert 0.0 < hit.score <= 1.0


def test_the_margin_and_the_row_report_one_number(opened):
    row, report, _entry, _channel = _first(opened)
    if report.margin is None or not report.margin.measured:
        pytest.skip("no LIPID MAPS database installed to raise an impostor")
    assert row.margin == report.margin.column()
    fresh = margin.cross_validate(*ir._sticks(report), report.explanation,
                                  report.written_precursor, report.polarity)
    assert fresh.share == pytest.approx(report.margin.share)


def test_the_history_the_energy_and_the_exports_read_the_same_rows(opened,
                                                                   tmp_path):
    summary, own = opened["summary"], opened["own"]

    history = standard_history.history_of(own)
    assert history.compounds == [COMPOUND]

    recommendations = energy.recommend(summary)
    assert {r.compound for r in recommendations} == {COMPOUND, OTHER}
    measured = {c.energy for r in recommendations for c in r.considered}
    written = {row.report.collision_energy for row in summary.rows}
    assert measured <= written, \
        "the energies recommended over are the energies the channels state"

    path = ir.write_summary_csv(summary, tmp_path / "summary.csv")
    lines = open(path, encoding="utf-8").read().strip().splitlines()
    assert len(lines) == len(summary.rows) + 1


def test_a_project_round_trip_compares_against_itself_without_a_file(opened,
                                                                     tmp_path):
    """
    The reference day is read from the project's JSON alone, so it must
    reproduce the summary it was written from without opening an
    acquisition.
    """
    session, summary = opened["session"], opened["summary"]
    project = tmp_path / "day.oqproj"
    session.save_project(str(project))

    stored = infusion_compare.read_summary(project)
    assert stored is not None and len(stored) == len(summary)

    comparison = infusion_compare.compare_infusions(summary, stored)
    assert comparison.same_ion == len(summary.rows)
    assert comparison.moved == []
    assert comparison.median_score == pytest.approx(100.0, abs=1e-4)
