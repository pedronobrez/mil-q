"""
The 26-injection sphingolipid batch: 141 components, 11 internal standards.

This is the batch nearly every quantitative figure in `CLAUDE.md` was measured
on — the one point per peak, the schedule, the formulas, the lock mass, the
control charts. It is somebody else's unpublished method, so neither the
folder nor the project is named here: `data.py` finds them by environment
variable.

Where a figure has moved since it was written the *current* one is asserted
and the old one is recorded in the docstring, because a number nobody can
reproduce is worse than a number that changed.
"""

from __future__ import annotations

import dataclasses
import os
import time
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pytest

from milq import api, batches, compare, processing, qc, quantify, recalibrate, suggest
from milq.components import fill_formulas, precursor_repairs
from milq.health import check_method, survey_coverage
from milq.mass_drift import mass_drift
from milq.sampling import sampling_report
from milq.schedule import build_schedule, suggested_cycle

from . import data

SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _open() -> "api.Batch":
    """The project, with its raw files. Skips when either is absent."""
    project = data.project()
    data.batch_files()          # the acquisitions the project points at
    batch = api.Batch.from_project(project)
    if batch.missing:
        pytest.skip(f"the project's raw files have moved: {batch.missing[0]}")
    return batch


@pytest.fixture(scope="module")
def batch():
    """Opened and processed once: every read-only test shares it."""
    held = _open()
    held.process()
    yield held
    held.close()


@pytest.fixture
def fresh():
    """A batch of its own, for a test that changes the method."""
    held = _open()
    yield held
    held.close()


# --------------------------------------------------------------------------- #
# what the batch is
# --------------------------------------------------------------------------- #
def test_the_batch_is_26_injections_of_141_components(batch):
    """
    `measured-facts.md`: "a batch of 26 injections of a scheduled sphingolipid
    method of 141 components and 11 internal standards, sampled every 14.6 s."
    """
    assert len(batch.samples) == 26
    assert len(batch.components) == 141
    assert len(batch.session.method.internal_standards) == 11


def test_3666_rows_of_which_2638_carry_a_peak(batch):
    """
    CLAUDE.md, the incremental bullet: "3,666 rows × 36 fields"; the algorithm
    bullet: "400 of 2,638 rows fitted". 26 × 141 = 3,666, and the valley walk
    finds a peak in 2,638 of them — reprocessing the project from the files
    reproduces what the project was saved with, row for row.
    """
    rows = batch.session.results
    assert len(rows) == 3666
    assert sum(1 for row in rows if row.found) == 2638
    assert len({row.component for row in rows if row.found}) == 139


def test_the_signal_to_noise_is_measurable_for_a_quarter_of_the_peaks(batch):
    """
    CLAUDE.md: "on that batch the S/N was measurable for 23% of the peaks
    found." 593 of 2,638 — the rest are traces the instrument reports as exact
    zeros, where there is no baseline to measure.
    """
    found = [row for row in batch.session.results if row.found]
    measured = [row for row in found if row.snr is not None]
    assert len(measured) == 593
    assert len(measured) / len(found) == pytest.approx(0.225, abs=0.005)


# --------------------------------------------------------------------------- #
# one point per peak
# --------------------------------------------------------------------------- #
def test_the_batch_is_one_point_per_peak(batch):
    """
    CLAUDE.md: "one scan every 14.6 s, a median of **one** point on the peak,
    129 of 139 components typically under the three a fit needs, and 2,206 of
    2,638 peaks (84%) with one point above half height."
    """
    session = batch.session
    report = sampling_report(session.results, session.entries, session.method)
    assert report.median_cycle == pytest.approx(14.609, abs=0.001)
    assert report.median_points == 1.0
    assert len(report.measured) == 139
    assert len(report.sparse) == 129
    assert report.unmeasured == 2206
    assert report.unmeasured / 2638 == pytest.approx(0.84, abs=0.005)
    assert report.median_width == pytest.approx(14.61, abs=0.01)


def test_the_cycle_the_batch_suggests_is_an_upper_bound(batch):
    """
    CLAUDE.md: the method report "prints 12.4 s (from `suggested_cycle`, the
    batch's measured width)", and it says so — the peaks it was measured on
    were the wider ones, the rest being narrower than a cycle.
    """
    session = batch.session
    report = sampling_report(session.results, session.entries, session.method)
    cycle, note = suggested_cycle(report)
    assert cycle == pytest.approx(12.4, abs=0.05)
    assert "upper bound" in note
    assert "2,206 peaks were narrower than a cycle" in note


def test_the_schedule_is_59_transitions_and_24_at_once(batch):
    """
    CLAUDE.md: "59 transitions scheduled, 82 left out for having no time, at
    most 24 at once at 4.70 min, and a cycle of 3 s still leaves 120 ms of
    dwell — against the 14.6 s the batch was acquired at."
    """
    schedule = build_schedule(batch.session.method, 3.0)
    assert len(schedule.slots) == 59
    assert len(schedule.unscheduled) == 82
    assert schedule.busiest == 24
    assert schedule.busiest_at == pytest.approx(4.70, abs=0.005)
    assert schedule.dwell_ms == pytest.approx(120.0, abs=0.5)
    assert schedule.feasible


# --------------------------------------------------------------------------- #
# what the method will fail at
# --------------------------------------------------------------------------- #
def test_check_method_finds_three_serious_and_four_warnings(batch):
    """
    CLAUDE.md, the method report: "3 serious findings and 4 warnings touching
    all 141 rows… 72 precursors outside the 50–700 survey."

    The counts are asserted per check rather than in total: a finding that
    silently stopped naming half its components would still add up to seven.
    """
    session = batch.session
    health = check_method(session.method, session.entries)
    assert len(health.serious) == 3
    assert len(health.warnings) == 4
    counts = {finding.check: finding.count for finding in health.findings}
    assert counts == {
        "shared transition": 35,
        "internal standard without a time": 2,
        "internal standard without a response floor": 10,
        "internal standard without a formula": 11,
        "no retention time": 82,
        "window too narrow": 59,
        "precursor outside the survey scan": 72,
    }


def test_72_of_141_precursors_are_outside_the_survey(batch):
    """
    CLAUDE.md: "On the real method 72 of 141 lie outside the 50–700 survey;
    the accurate mass, the annotation and the mass drift are not measurable
    for them."
    """
    session = batch.session
    outside, ranges = survey_coverage(session.method.components, session.entries)
    assert len(outside) == 72
    assert ranges == ["50–700"]


# --------------------------------------------------------------------------- #
# formulas and the precursors they contradict
# --------------------------------------------------------------------------- #
def test_125_formulas_are_derivable_and_16_refused(batch):
    """
    CLAUDE.md: "On the real method: 125 of 141 components and 10 of 11
    standards, and 13 of the 16 refusals were the written precursor typed to
    fewer places (`dHCer(d18:0/12:0)` 15 ppm out), three a whole 1, 2 or
    100 Da out."

    The method as the project holds it carries no formula at all, which is why
    this can be run on it directly.
    """
    components = [dataclasses.replace(c) for c in batch.session.method.components]
    assert not any(c.formula for c in components)
    fill = fill_formulas(components)
    assert len(fill.filled) == 125
    assert len(fill.refused) == 16
    assert sum(1 for c in components
               if c.is_internal_standard and c.formula) == 10

    repairs = precursor_repairs(components)
    assert len(repairs) == 16
    assert sum(1 for r in repairs if not r.whole_dalton) == 13
    assert sum(1 for r in repairs if r.whole_dalton) == 3
    assert sum(1 for r in repairs if r.offered) == 13
    named = {r.component.name: r for r in repairs}
    assert named["dHCer(d18:0/12:0)"].error_ppm == pytest.approx(15.3, abs=0.1)


def test_the_13_repairs_buy_formulas_and_change_no_number(fresh):
    """
    CLAUDE.md: "Applying the 13 sub-dalton ones and reprocessing left 338 of
    338 rows identical… What the 13 bought was formulas: 125 → 138 of 141,
    11 of 11 standards with a lock-mass candidate."

    338 is 13 components over 26 injections. Every field of every one of them
    is identical **except the fingerprint**, which is the digest of the
    component that produced the row and is supposed to change: it is what
    makes the next incremental run integrate them again rather than keep a row
    written under a different precursor.
    """
    session = fresh.session
    fresh.process()
    before = {(r.sample_key, r.component): r for r in session.results}

    components = [dataclasses.replace(c) for c in session.method.components]
    fill_formulas(components)
    assert sum(1 for c in components if c.formula) == 125
    repairs = {r.component.name: r for r in precursor_repairs(components) if r.offered}
    assert len(repairs) == 13
    repaired = [repairs[c.name].repaired if c.name in repairs else c
                for c in components]
    assert sum(1 for c in repaired if c.formula) == 138
    assert sum(1 for c in repaired if c.is_internal_standard and c.formula) == 11

    session.set_components(repaired)
    fresh.process()
    after = {(r.sample_key, r.component): r for r in session.results}
    touched = [key for key in before if key[1] in repairs]
    assert len(touched) == 338
    fields = [f.name for f in dataclasses.fields(next(iter(before.values())))]
    assert len(fields) == 36
    for key in touched:
        one, other = before[key], after[key]
        for field in fields:
            if field == "fingerprint":
                assert getattr(one, field) != getattr(other, field)
            else:
                assert getattr(one, field) == getattr(other, field), (key, field)
    assert sum(1 for row in after.values() if row.found) == 2638


# --------------------------------------------------------------------------- #
# the three algorithms
# --------------------------------------------------------------------------- #
def test_the_three_algorithms_on_the_batch(batch):
    """
    `measured-facts.md`: "valley 2,638 rows found; summation 857; Gaussian
    2,638 with 2,238 fallen back, 2,169 because the peak was fewer than three
    points wide. Where fitted, the fit's area was a median 0.977 of the
    trapezoid's."
    """
    session = batch.session
    assert processing.ALGORITHMS == ("valley", "summation", "gaussian")
    runs = {}
    for algorithm in processing.ALGORITHMS:
        method = compare.with_algorithm(session.method, algorithm)
        runs[algorithm] = quantify.process(session.entries, method, session.cache)
    found = {name: [r for r in rows if r.found] for name, rows in runs.items()}
    assert len(found["valley"]) == 2638
    assert len(found["summation"]) == 857
    assert len(found["gaussian"]) == 2638

    fitted = [r for r in found["gaussian"] if not (r.note or "")]
    assert len(fitted) == 400
    assert len(found["gaussian"]) - len(fitted) == 2238
    too_narrow = sum(1 for r in found["gaussian"]
                     if "point(s) above the baseline" in (r.note or "")
                     or "narrower than the sampling" in (r.note or ""))
    assert too_narrow == 2169

    trapezoid = {(r.sample_key, r.component): r for r in found["valley"]}
    ratios = [r.area / trapezoid[(r.sample_key, r.component)].area
              for r in fitted
              if trapezoid.get((r.sample_key, r.component))
              and trapezoid[(r.sample_key, r.component)].area]
    assert len(ratios) == 400
    assert float(np.median(ratios)) == pytest.approx(0.977, abs=0.002)


# --------------------------------------------------------------------------- #
# the incremental run
# --------------------------------------------------------------------------- #
def test_an_incremental_run_keeps_every_row_and_is_identical(batch):
    """
    CLAUDE.md: "identical to a full run over 3,666 rows × 36 fields", and
    "adding one injection went from 2.4 s to 0.06 s".

    Nothing has changed between the two runs here, so the honest form of that
    claim is: every row is kept, none re-integrated, and every field of every
    row equals what a full run gives. The timing is asserted only as an order
    of magnitude — this machine varies threefold under load.
    """
    session = batch.session
    full = quantify.process(session.entries, session.method, session.cache)
    start = time.time()
    again, report = quantify.process_incremental(session.entries, session.method,
                                                 full, session.cache)
    incremental_seconds = time.time() - start
    assert report.total == 3666
    assert report.kept == 3666
    assert report.integrated == 0

    fields = [f.name for f in dataclasses.fields(next(iter(full)))]
    assert len(fields) == 36
    by_key = {(r.sample_key, r.component): r for r in full}
    for row in again:
        other = by_key[(row.sample_key, row.component)]
        assert all(getattr(row, f) == getattr(other, f) for f in fields)

    start = time.time()
    quantify.process(session.entries, session.method, session.cache)
    assert incremental_seconds < (time.time() - start)


# --------------------------------------------------------------------------- #
# the mass axis
# --------------------------------------------------------------------------- #
def test_one_standard_of_eleven_measures_the_same_ion_through_the_run(batch):
    """
    CLAUDE.md: "`SM(d18:1/12:0)`, the one standard strong enough in a 50–700
    survey, held to −4.0 ppm across the run with a 16 ppm spread; nine others
    cannot be measured; no index, since fewer than three standards qualify."

    Current: the spread is 16.1 ppm and the error −4.8 ppm. `−4.0` was
    measured before the formulas were filled from the names, and the error is
    against the formula's mass, so it moved when the formula did; the spread,
    which is what `same_ion` gates on, has not.

    The tenth standard has no survey coverage at all (`LacCER(d18:1/12:0)` at
    806.5, outside 50–700), which is why nine "cannot be measured" and not
    ten.
    """
    session = batch.session
    drift = mass_drift(session.entries, session.method)
    assert drift.injections == 26 and drift.ordered
    assert len(drift.trends) == 11
    trends = {t.component: t for t in drift.trends}
    same = [t for t in drift.trends if t.same_ion and t.points]
    assert [t.component for t in same] == ["SM(d18:1/12:0)"]
    assert trends["SM(d18:1/12:0)"].spread_ppm == pytest.approx(16.1, abs=0.2)
    assert len(trends["SM(d18:1/12:0)"].points) == 25
    assert trends["LacCER(d18:1/12:0)"].note == "no survey scan covers this mass"
    assert drift.index is None


def test_the_batch_as_it_ships_has_no_lock_mass(batch):
    """
    CLAUDE.md: "On the 26-injection batch as it ships there is no lock mass —
    no standard carries a formula — and every injection reads 'left as
    measured'."
    """
    session = batch.session
    corrections = recalibrate.fit_batch(session,
                                        mass_drift(session.entries, session.method))
    assert len(corrections) == 26
    assert not any(c.usable for c in corrections.values())
    assert "No lock mass in any of 26" in recalibrate.describe(corrections)


def test_with_the_formulas_filled_25_of_26_injections_correct_by_48_ppm(fresh):
    """
    CLAUDE.md: "Given the one formula that can be looked up: one lock mass,
    offset only, in 25 of 26 injections, median +4.8 ppm with a 16.1 ppm
    spread."

    And the other half of the gate, `MAX_LOCK_ERROR_PPM`: "On the batch it
    names five standards and changes no number." It names **six** now — the
    thirteen repairs give an eleventh standard a formula, and that one is 234
    ppm from the ion its window holds. `C17:0_Ceramide`'s 237 ppm, the near
    miss CLAUDE.md names, is still there.
    """
    session = fresh.session
    components = [dataclasses.replace(c) for c in session.method.components]
    fill_formulas(components)
    repairs = {r.component.name: r for r in precursor_repairs(components) if r.offered}
    session.set_components([repairs[c.name].repaired if c.name in repairs else c
                            for c in components])

    drift = mass_drift(session.entries, session.method)
    trends = {t.component: t for t in drift.trends}
    assert trends["SM(d18:1/12:0)"].error_ppm == pytest.approx(-4.8, abs=0.1)

    corrections = recalibrate.fit_batch(session, drift)
    usable = {key: c for key, c in corrections.items() if c.usable}
    assert len(corrections) == 26
    assert len(usable) == 25
    offsets = [c.ppm_at(647.5) for c in usable.values()]
    assert float(np.median(offsets)) == pytest.approx(4.8, abs=0.05)
    assert max(offsets) - min(offsets) == pytest.approx(16.1, abs=0.2)
    assert all(not c.linear for c in usable.values())

    refusals = [recalibrate.lock_mass_refusal(t) for t in drift.trends]
    named = [r for r in refusals if r]
    assert len(named) == 6
    assert any("237 ppm from its formula" in r for r in named)


# --------------------------------------------------------------------------- #
# quality control
# --------------------------------------------------------------------------- #
def test_five_of_eleven_charts_cannot_normalise_anything(batch):
    """
    CLAUDE.md: "when a third of a chart is out, `unusable` reports the chart
    rather than the injections — seventeen bad injections out of twenty-six is
    not a list of outliers, it is a standard that cannot normalise anything."

    That standard is `Sphinganine C17:0`, and it still reads seventeen.
    """
    session = batch.session
    report = qc.batch_qc(session.results, session.entries, session.method)
    assert len(report.charts) == 11
    assert len(report.unusable) == 5
    charts = {c.component: c for c in report.charts}
    assert len(charts["Sphinganine C17:0"].out) == 17
    assert charts["Sphinganine C17:0"].unusable
    assert not charts["SM(d18:1/12:0)"].unusable


def test_the_response_index_separates_the_injection_from_the_compound(batch):
    """
    CLAUDE.md: "the standards taken separately scattered between 32% and 228%
    and looked hopeless; taken together the injections sat within ±18% with
    three exceptions, one of them at 0.08 where every standard had gone at
    once."

    **This is the figure that has moved most.** On the batch as it now
    reprocesses, the index spans 0.437 to 2.081 and flags four injections, not
    three, and nothing sits at 0.08. What still stands is the shape of the
    claim: one index over all eleven standards, every injection on it, and the
    injections it flags are flagged for being far out rather than for being
    unusual — which is what `ALWAYS_OUT_PERCENT` is for.
    """
    session = batch.session
    report = qc.batch_qc(session.results, session.entries, session.method)
    index = report.index
    assert index is not None
    assert len(index.injections) == 26
    values = [point.value for point in index.injections]
    assert min(values) == pytest.approx(0.437, abs=0.002)
    assert max(values) == pytest.approx(2.081, abs=0.002)
    out = [point for point in index.injections if point.out]
    assert len(out) == 4
    assert all(abs(point.percent) >= qc.OUT_PERCENT for point in out)


def test_the_floors_the_batch_proposes_are_half_its_medians(batch):
    """
    CLAUDE.md: "On the real batch that is 5,240 for the one usable standard
    and 2–25 counts for the others — which is what their medians are, and the
    dialog shows the median so nobody accepts a floor of 3 by mistake"; the
    manual adds "522 and 566 for the two at about a thousand counts."

    The smallest is now 1.22 rather than 2 — `C17:0_Ceramide`, which was found
    in six injections and kept in three, and is the one row the dialog does
    not pre-tick.
    """
    session = batch.session
    proposals = {p.component: p for p in qc.suggest_floors(
        session.results, session.entries, session.method)}
    assert len(proposals) == 11
    assert proposals["SM(d18:1/12:0)"].proposed == pytest.approx(5240.0)
    assert proposals["Sphingosine C17:0"].proposed == pytest.approx(522.0)
    assert proposals["Sphinganine C17:0"].proposed == pytest.approx(566.0)
    for proposal in proposals.values():
        assert proposal.proposed == pytest.approx(proposal.median / 2, rel=0.005)
    rest = [p.proposed for name, p in proposals.items()
            if name not in ("SM(d18:1/12:0)", "Sphingosine C17:0",
                            "Sphinganine C17:0")]
    assert max(rest) == pytest.approx(25.3, abs=0.1)
    assert min(rest) == pytest.approx(1.22, abs=0.01)
    assert not proposals["C17:0_Ceramide"].confident
    assert proposals["C17:0_Ceramide"].used == 3


# --------------------------------------------------------------------------- #
# the detection margin, and what the estimator will not promise
# --------------------------------------------------------------------------- #
def test_the_detection_margin_is_what_finds_most_of_the_peaks(fresh):
    """
    CLAUDE.md: "On that batch it took the rows with a peak from 1,771 to 2,665
    and the components with any peak at all from 89 to 139 of 141."

    Current, on the batch as it now reads: **1,647 → 2,638 rows and 84 → 139
    components**. The two ends were measured at different times — 2,665 was
    before the batch was reprocessed under the corrected method — and the
    finding is the same either way: without the margin a ±0.5 min window at
    14.6 s holds four scans, and `detect_peaks` returns nothing under five.
    """
    session = fresh.session
    was = quantify.MARGIN_SCANS
    try:
        quantify.MARGIN_SCANS = 0
        rows = quantify.process(session.entries, session.method, session.cache)
    finally:
        quantify.MARGIN_SCANS = was
    found = [r for r in rows if r.found]
    assert len(found) == 1647
    assert len({r.component for r in found}) == 84

    session.cache.clear()
    rows = quantify.process(session.entries, session.method, session.cache)
    found = [r for r in rows if r.found]
    assert len(found) == 2638
    assert len({r.component for r in found}) == 139


def test_nothing_the_estimator_offers_is_pre_ticked(batch):
    """
    CLAUDE.md: "On the real method it was 88% above ten thousand counts and
    45% below a hundred, and because nothing offered was above ten thousand,
    **nothing was pre-ticked**."

    The bands have moved with the batch — 33%, 36%, 53% and 71% now, over
    18, 11, 17 and 7 components — but the conclusion has not, and it is the
    conclusion that matters: the tallest peak among the 33 components with no
    declared time is 198 counts, three orders below the band where the
    estimator proved itself, so nothing is offered with confidence.
    """
    session = batch.session
    proposals = suggest.suggest_times(session.method, session.entries)
    assert len(proposals.estimates) == 141
    assert len(proposals.offered) == 33
    assert len(proposals.missing) == 82
    bands = [(band.components, round(band.within * 100, 1))
             for band in proposals.bands]
    assert bands == [(18, 33.3), (11, 36.4), (17, 52.9), (7, 71.4)]
    assert max(estimate.height for estimate in proposals.offered) < 10_000


# --------------------------------------------------------------------------- #
# a record of one's own, read back and searched
# --------------------------------------------------------------------------- #
def test_fourteen_records_read_back_and_find_themselves(batch, tmp_path):
    """
    CLAUDE.md: "14 records from injection 01 read back within 5·10⁻⁶ Da;
    injection 02 put the right record first 14 of 14 times at reverse 45–96,
    every other record at most 42."

    The records here are written straight off the api — every peak at or above
    1% of the base, up to 200 — where the measured ones came from the Explorer
    at the pane's label floor, seven to eighty-two peaks each. So the spread
    of the scores is this construction's own (reverse 45.0–88.5, best wrong
    22.3) and what carries across is what the figure was for: the round trip
    is lossless to the rounding of the text, every channel finds its own
    record first, and no other record comes close.
    """
    runs = batch.acquisitions()
    first, second = runs[0], runs[1]

    def average(run, index):
        channel = run.channels[index]
        rt = channel.tic().rt
        return channel.average(float(rt[0]), float(rt[-1])).centroid()

    path = tmp_path / "own.msp"
    library = api.Library.open(path, create=True)
    for index in range(1, 15):
        library.add(average(first, index), name=f"record {index}",
                    precursor=first.channels[index].precursor)
    assert len(library) == 14

    reread = api.Library.open(path)
    assert len(reread) == 14
    for written, read in zip(library.entries, reread.entries, strict=True):
        assert np.max(np.abs(np.asarray(written.mz) - np.asarray(read.mz))) < 5e-6
        one = np.asarray(written.intensity, float)
        other = np.asarray(read.intensity, float)
        assert np.max(np.abs(one / one.max() - other / other.max())) < 5e-7

    firsts, reverses, wrong = 0, [], []
    for index in range(1, 15):
        spectrum = average(second, index)
        hits = reread.search((spectrum.mz, spectrum.intensity), top=20)
        assert hits, index
        if hits[0].name == f"record {index}":
            firsts += 1
            reverses.append(hits[0].reverse * 100)
        wrong += [hit.score * 100 for hit in hits
                  if hit.name != f"record {index}"]
    assert firsts == 14
    assert min(reverses) == pytest.approx(45.0, abs=0.5)
    assert max(reverses) == pytest.approx(88.5, abs=0.5)
    assert max(wrong) == pytest.approx(22.3, abs=0.5)
    assert max(wrong) < min(reverses)


# --------------------------------------------------------------------------- #
# reading the batch back out
# --------------------------------------------------------------------------- #
def test_the_batch_compared_against_its_own_project_is_identical(batch):
    """
    CLAUDE.md: "`batches.read_project` builds a snapshot from the JSON alone,
    so a batch whose acquisitions moved to another disk still compares."

    The gain it reproduced — 2,607 rows to 2,638 and the standards' median %CV
    101.8 to 87.7 — needs the project as it stood *before* the two retention
    times were corrected, and that project is not kept. What can be asserted
    without it is the harder half of the claim: the snapshot read from the
    JSON and the snapshot of the reprocessed session agree on every total,
    including the 87.7% that side of the comparison ends at.
    """
    session = batch.session
    reference = batches.read_project(data.project())
    comparison = batches.compare_batches(batches.snapshot(session, "reprocessed"),
                                         reference)
    before, after = comparison.totals()
    assert before == after
    assert after["rows"] == 3666 and after["found"] == 2638
    assert after["components_found"] == 139
    assert after["median_points"] == 1.0
    assert after["precise_components"] == 11
    assert after["median_precision"] == pytest.approx(87.7, abs=0.05)
    assert comparison.moved == []
    assert len(comparison.rows) == 141


def test_the_workbook_is_five_sheets_excel_will_open(batch, tmp_path):
    """
    CLAUDE.md: "an `.xlsx` is a zip of XML and the failure is silent…
    Verified by reading back in the suite, by `openpyxl` out of repo, by macOS
    Quick Look, and by Microsoft Excel for Mac itself (the batch's five
    sheets, the header, a row and a numeric cell read back)."

    This is that read-back on the real batch: every part well-formed, the five
    sheets named, and the results sheet carrying a header and all 3,666 rows.
    """
    path = batch.export_xlsx(tmp_path / "batch.xlsx")
    with zipfile.ZipFile(path) as book:
        for part in book.namelist():
            if part.endswith((".xml", ".rels")):
                ET.fromstring(book.read(part))       # raises if it is not
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = [sheet.get("name") for sheet in workbook.iter(f"{SHEET}sheet")]
        assert sheets == ["Results", "Statistics", "Batch QC", "Method", "Samples"]
        counts = []
        for index in range(1, len(sheets) + 1):
            data_sheet = ET.fromstring(book.read(f"xl/worksheets/sheet{index}.xml"))
            counts.append(len(list(data_sheet.iter(f"{SHEET}row"))))
    assert counts == [3667, 142, 13, 142, 27]
    assert os.path.getsize(path) > 100_000
