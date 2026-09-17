"""
The cover that goes in front of a folder of infusions.

The cover makes one claim the pages behind it do not: it adds nine reports
up. So most of what follows is that arithmetic — the counts, and the words
each count is reported under — built from rows made by hand, because the
cases worth testing are the ones a fake acquisition cannot easily be made to
produce: a precursor that never survived its collision energy, a method
isolating a mass the compound's other runs do not, a record found at another
energy.

The rest is what a summary must not do. It must not say "nothing was left
out" over a run that left something out, it must not point a contents list at
five pages all called `CA-d4`, and it must not print a cover over a selection
— every number on it is a number about the folder.
"""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import audit  # noqa: E402
from milq import infusion_batch as batch  # noqa: E402
from milq import infusion_cover as cover  # noqa: E402
from milq import infusion_report as ir  # noqa: E402
from milq.folder import Finding  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# --------------------------------------------------------------------------- #
# rows made by hand: the cases a fake acquisition cannot easily produce
# --------------------------------------------------------------------------- #
def _row(compound="CA-d4", sample="CA-d4_mix1", written=430.34, survivor=None,
         survivor_note="", score=None, record="CA-d4 reference (CID)",
         record_energy=None, matched=None, predicted=None, energy=22.0,
         explanation_note=""):
    """One `InfusionRow` with only the fields the cover reads set."""
    report = ir.InfusionReport(
        compound=compound, sample=sample, file=f"{sample}.wiff",
        written_precursor=written, survivor=survivor,
        survivor_note=survivor_note, collision_energy=energy, scans=200,
        polarity="Positive", channel_name="TOF PI")
    if matched is not None:
        report.explanation = type("Explanation", (), {})()
        report.explanation.matched = matched
        report.explanation.predicted = predicted or 0
        report.explanation.name = compound
    if score is not None:
        hit = type("Hit", (), {})()
        hit.score, hit.reverse = score, score
        hit.matched, hit.of_library, hit.delta_ppm = 4, 200, None
        hit.entry = type("Entry", (), {"name": record})()
        # `infusion_report.energy_of` reads the record's own fields, which is
        # where an MSP writes it; an attribute of that name is not consulted
        hit.entry.fields = ({"collision_energy": f"{record_energy:g} eV"}
                            if record_energy is not None else {})
        report.hit = hit
    note = ir._precursor_reason(report)
    return ir.InfusionRow(report=report, precursor_note=note,
                          explanation_note=explanation_note)


def _summary(rows, library="own.msp", seconds=8.0):
    return ir.InfusionSummary(rows=list(rows), library=library,
                              seconds=seconds)


def _result(summary, requested=("/Volumes/DISK/Bileomics",), skipped=(),
            findings=()):
    """
    The run as `infusion_batch` leaves it.

    What was read is the files themselves where files were named, and the
    folder's own acquisitions where a folder was — which is the distinction
    `folder_of` is about, and it cannot be tested with a helper that always
    reads out of the same folder whatever it was asked for.
    """
    requested = list(requested)
    named = [path for path in requested if os.path.splitext(path)[1]]
    read = named or [f"{requested[0]}/{row.report.file}"
                     for row in summary.rows]
    return batch.BatchResult(
        requested=requested, read=read,
        skipped=list(skipped), findings=list(findings), summary=summary)


def _real_folder():
    """The nine-infusion folder in miniature: five of one compound, two of
    another, with the two shapes of failure the real one has."""
    rows = [
        _row(sample="CA-d4_TESTEARTIGO_12", written=839.56, energy=12.0,
             survivor_note="too little of the precursor survives this "
                           "collision energy to measure a mass — at most 9 "
                           "counts within ±0.25 Da of 839.56",
             explanation_note="CA-d4 is written [M+NH4]+, and 839.56 is none "
                              "of the adducts of C24H36D4O5 within ±0.05 Da"),
        _row(sample="CA-d4_mix1_12", written=430.34,
             survivor=(430.3488, 12271.0), energy=12.0, score=0.06,
             record_energy=45.0, matched=3, predicted=56),
        _row(sample="CA-d4_TESTEARTIGO_22", written=839.56, energy=22.0,
             survivor_note="too little of the precursor survives this "
                           "collision energy to measure a mass — at most 17 "
                           "counts within ±0.25 Da of 839.56"),
        _row(sample="CA-d4_mix1_22", written=430.34,
             survivor=(430.3489, 9415.0), score=0.29, record_energy=45.0,
             matched=8, predicted=56),
        _row(sample="CA-d4_Mix1", written=430.35, energy=45.0,
             survivor_note="too little of the precursor survives this "
                           "collision energy to measure a mass — at most 84 "
                           "counts within ±0.25 Da of 430.35",
             score=1.0, matched=2, predicted=56),
        _row(compound="DCA-d4", sample="DCA-d4_mix1", written=414.34,
             survivor=(414.3525, 5000.0), score=0.33, record_energy=40.0,
             record="DCA-d4 reference (CID)", matched=8, predicted=41),
        _row(compound="DCA-d4", sample="DCA-d4_Mix1", written=414.34,
             energy=40.0, survivor=(414.3419, 4000.0), score=0.99,
             record="DCA-d4 reference (CID)", matched=3, predicted=41),
    ]
    return _summary(rows)


# --------------------------------------------------------------------------- #
# what this is
# --------------------------------------------------------------------------- #
def test_the_cover_names_the_folder_the_day_and_the_version(qapp):
    from milq import __version__

    summary = _real_folder()
    html = cover.build_html(_result(summary), summary)

    assert cover.title_for(_result(summary)) == "Bileomics"
    assert "<h1>Bileomics</h1>" in html
    assert f"MIL-Q {__version__}" in html
    assert "/Volumes/DISK/Bileomics" in html
    # the counts, and the summary line the tab shows to the digit
    assert "7 in 2 compound(s)" in html
    assert summary.summary() in html


def test_a_run_given_files_rather_than_a_folder_still_has_a_title(qapp):
    summary = _real_folder()
    result = _result(summary, requested=["/data/runs/one.wiff",
                                         "/data/runs/two.wiff"])

    assert cover.folder_of(result) == "/data/runs"
    assert cover.title_for(result) == "runs"


# --------------------------------------------------------------------------- #
# the table
# --------------------------------------------------------------------------- #
def test_every_infusion_is_a_row_with_its_compound_kept_together(qapp):
    rows = _real_folder().rows
    # acquired interleaved, as a folder off the instrument is
    shuffled = [rows[0], rows[5], rows[1], rows[6], rows[2], rows[3], rows[4]]
    summary = _summary(shuffled)
    html = cover.build_html(_result(summary), summary)

    assert [row.sample for row in cover.grouped(summary.rows)] == [
        "CA-d4_TESTEARTIGO_12", "CA-d4_mix1_12", "CA-d4_TESTEARTIGO_22",
        "CA-d4_mix1_22", "CA-d4_Mix1", "DCA-d4_mix1", "DCA-d4_Mix1"]
    assert html.count("<tr") >= len(summary.rows)
    for row in summary.rows:
        assert row.sample in html
    for column in ir.REPORT_COLUMNS:
        assert "<th" in html and column in html


def test_a_reason_too_long_for_a_cell_is_cut_at_a_word(qapp):
    summary = _real_folder()
    html = cover.build_html(_result(summary), summary)
    note = summary.rows[0].explanation_note

    assert len(note) > cover.CELL_CHARACTERS
    assert note not in html                       # not printed whole here
    assert "CA-d4 is written [M+NH4]+" in html    # cut, not dropped
    assert "…" in html
    # cut at a word: nothing ends in half of one
    body = cover._cell(note)[:-1]                 # what is printed, less the …
    assert note.startswith(body)
    assert not note[len(body)].isalnum()


# --------------------------------------------------------------------------- #
# the verdict, sentence by sentence
# --------------------------------------------------------------------------- #
def test_the_precursors_are_counted_and_the_rest_say_what_they_did(qapp):
    summary = _real_folder()
    said = cover.verdict_sentences(summary)[0]

    assert said.startswith("3 of 7 precursor(s) confirmed within 25 ppm; "
                           "4 not: ")
    # the two files isolating a mass the compound's other runs do not are
    # named by that mass, not lumped in with a fragmented precursor
    assert "2 whose method isolates 839.56" in said
    assert "1 with too little precursor surviving fragmentation" in said
    # and the one that was measured is given as how far out it was
    assert "1 at +30.2 ppm" in said


def test_a_precursor_measured_outside_the_limit_is_given_as_its_error(qapp):
    rows = [_row(sample="A", written=414.34, survivor=(414.3526, 5000.0)),
            _row(sample="B", written=414.34, survivor=(414.3400, 5000.0))]
    said = cover.verdict_sentences(_summary(rows))[0]

    assert said.startswith("1 of 2 precursor(s) confirmed within 25 ppm; "
                           "1 not: 1 at +30.4 ppm")


def test_many_errors_are_given_as_a_range_rather_than_a_list(qapp):
    rows = [_row(sample=f"S{n}", written=400.0,
                 survivor=(400.0 * (1 + (30 + n * 10) / 1e6), 5000.0))
            for n in range(cover.ERRORS_LISTED + 1)]
    said = cover.verdict_sentences(_summary(rows))[0]

    assert "between +30.0 and +60.0 ppm" in said


def test_a_compound_that_never_confirms_names_no_isolated_mass(qapp):
    """The test is within the compound: two masses and neither confirmed is
    a compound that failed, not a method pointing somewhere else."""
    rows = [_row(sample="A", written=430.34, survivor_note="too little"),
            _row(sample="B", written=839.56, survivor_note="too little")]

    assert cover.isolated_precursors(rows) == {}
    assert "isolates" not in cover.verdict_sentences(_summary(rows))[0]


def test_an_infusion_whose_method_writes_no_precursor_is_in_neither_count(qapp):
    rows = [_row(sample="A", written=430.34, survivor=(430.3400, 5000.0)),
            _row(sample="B", written=None)]
    said = cover.verdict_sentences(_summary(rows))[0]

    assert said.startswith("1 of 1 precursor(s) confirmed")
    assert "1 more infusion(s) write no precursor" in said


def test_no_precursor_written_anywhere_says_so_rather_than_zero_of_zero(qapp):
    said = cover.verdict_sentences(_summary([_row(written=None)]))[0]

    assert said == ("No method in this folder writes a precursor, so there "
                    "was nothing to confirm.")


def test_the_own_records_are_counted_above_and_below_with_the_energy(qapp):
    summary = _real_folder()
    said = cover.verdict_sentences(summary)[1]

    assert said.startswith("Own records: 2 above 60, 3 below")
    assert "all across a collision-energy change" in said


def test_some_records_at_another_energy_is_counted_not_generalised(qapp):
    rows = [_row(sample="A", score=0.10, record_energy=45.0),
            _row(sample="B", score=0.20, record_energy=None),
            _row(sample="C", score=0.90)]
    said = cover.verdict_sentences(_summary(rows))[1]

    assert said.startswith("Own records: 1 above 60, 2 below — 1 of them "
                           "across a collision-energy change")


def test_an_infusion_with_no_record_at_all_is_said_and_not_counted_below(qapp):
    rows = [_row(sample="A", score=0.90), _row(sample="B")]
    said = cover.verdict_sentences(_summary(rows))[1]

    assert "Own records: 1 above 60, 0 below" in said
    assert "1 matched no record at all" in said


def test_no_library_of_your_own_says_so_rather_than_counting_nothing(qapp):
    summary = _summary(_real_folder().rows, library="")
    said = cover.verdict_sentences(summary)[1]

    assert said.startswith("No library of your own was searched")


def test_the_predicted_ions_are_summed_over_the_spectra_that_had_them(qapp):
    said = cover.verdict_sentences(_real_folder())[2]

    assert said.startswith("Predicted ions: 24 of 250 found across 5 "
                           "spectrum(s)")
    assert "2 had nothing to predict from" in said


def test_nothing_predicted_anywhere_says_so_rather_than_zero_of_zero(qapp):
    rows = [_row(sample="A"), _row(sample="B")]
    said = cover.verdict_sentences(_summary(rows))[2]

    assert said.startswith("No formula or structure was scored against any "
                           "of these spectra")


def test_the_verdict_is_a_paragraph_of_those_sentences(qapp):
    summary = _real_folder()
    html = cover.build_html(_result(summary), summary)

    assert cover.verdict(summary) == " ".join(cover.verdict_sentences(summary))
    assert "839.56" in cover.verdict(summary)
    assert "What they add up to" in html
    # no overall verdict: the page says why there is none
    assert "no overall pass or fail" in html


def test_every_sentence_reads_as_one_in_the_paragraph(qapp):
    """They are printed run together, so each has to start like a sentence:
    printed and looked at, `…+30.3 ppm. own records: 4 above 60` reads as a
    mistake rather than as the next measurement."""
    for summary in (_real_folder(), _summary([_row(written=None)]),
                    _summary(_real_folder().rows, library="")):
        for said in cover.verdict_sentences(summary):
            assert said[0].isupper() or said[0].isdigit()
            assert said.endswith(".")


def test_no_rows_at_all_carries_the_reason_rather_than_three_zeroes(qapp):
    summary = ir.InfusionSummary(rows=[], note="No file read as a direct "
                                               "infusion.")

    assert cover.verdict_sentences(summary) == ["No file read as a direct "
                                                "infusion."]


# --------------------------------------------------------------------------- #
# what was left out
# --------------------------------------------------------------------------- #
def test_the_skipped_files_and_the_folder_findings_are_both_listed(qapp):
    summary = _real_folder()
    skipped = [batch.Skipped("/d/gradient.wiff", batch.NOT_INFUSION,
                             "shows structure: 0.03 of the total above half"),
               batch.Skipped("/d/alone.wiff", batch.MISSING_SCAN,
                             "alone.wiff has no alone.wiff.scan beside it")]
    findings = [Finding("/d", "ignored", "9 .wiff2 files",
                        "nothing is lost — the .wiff beside each is opened")]
    html = cover.build_html(_result(summary, skipped=skipped,
                                    findings=findings), summary)

    assert "What was left out" in html
    for skip in skipped:
        assert skip.name in html and skip.reason in html
        assert skip.kind in html
    assert "9 .wiff2 files" in html
    assert "nothing is lost" in html


def test_a_run_that_left_nothing_out_says_so_rather_than_showing_nothing(qapp):
    summary = _real_folder()
    html = cover.build_html(_result(summary), summary)

    assert "Nothing was left out: every file given was read." in html
    assert "Nothing to report about the folder itself." in html


# --------------------------------------------------------------------------- #
# the contents
# --------------------------------------------------------------------------- #
def test_the_contents_names_the_sample_because_a_compound_repeats(qapp):
    reports = [row.report for row in _real_folder().rows]
    headings = cover.headings_for(reports)

    assert headings[0] == "1. CA-d4 · CA-d4_TESTEARTIGO_12"
    assert len(set(headings)) == len(headings)


def test_the_contents_carries_the_page_each_section_landed_on(qapp):
    summary = _real_folder()
    headings = cover.headings_for([row.report for row in summary.rows])
    result = _result(summary)

    # no column at all, the column reserved, and the numbers themselves —
    # the three states `report.print_document` builds the document in
    plain = cover.build_html(result, summary, headings=headings)
    reserved = cover.build_html(result, summary, headings=headings,
                                contents={})
    numbered = cover.build_html(result, summary, headings=headings,
                                contents={headings[0]: 3, headings[1]: 8})

    # the assertions are on the contents table alone: the Infusions table
    # above it has right-aligned columns of its own in all three
    def contents_of(html: str) -> str:
        return html.split("The pages that follow", 1)[1]

    assert "The pages that follow" in plain
    assert 'class="num"' not in contents_of(plain)
    assert 'class="num"' in contents_of(reserved)
    assert ">3</td>" not in contents_of(reserved)
    assert ">3</td>" in contents_of(numbered)
    assert ">8</td>" in contents_of(numbered)
    for heading in headings:
        assert heading in numbered


def test_a_cover_with_no_pages_behind_it_lists_none(qapp):
    summary = _real_folder()
    html = cover.build_html(_result(summary), summary)

    assert "The pages that follow" not in html


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def _reports(qapp):
    """Two real reports, built the way the tab and the run build them."""
    from milq.session import Session
    from tests.test_infusion_report import _entry

    session = Session()
    for name in ("TESTOL_infusion_A", "TESTOL_infusion_B"):
        entry, _channel = _entry(name=name)
        session.entries.append(entry)
    summary = ir.summarise(session)
    return summary, ir.prepare_documents(summary.rows)


def test_the_pdf_is_the_cover_and_then_the_pages(qapp, tmp_path):
    summary, reports = _reports(qapp)
    result = _result(summary, requested=[str(tmp_path)])

    plain = ir.write_pdf(reports, str(tmp_path / "plain.pdf"))
    with_cover = cover.write_pdf(result, summary, reports,
                                 str(tmp_path / "cover.pdf"))

    assert os.path.exists(with_cover)
    assert batch._page_count(with_cover) >= 2
    # what the cover did is read off the pages and not off their number: the
    # document it replaces opened on a title-and-contents page of its own, so
    # a covered document is not reliably longer than a plain one
    first = _pdf_text(with_cover, 0)
    for block in ("The infusions", "What they add up to", "What was left out",
                  "The pages that follow"):
        assert block in first
        assert block not in _pdf_text(plain, 0)
    headings = cover.headings_for(reports)
    assert headings[0] in _pdf_text(with_cover, 1)
    assert headings[0] in first                  # listed in the contents


def test_the_cover_can_be_written_on_its_own_for_one_document_per_compound(
        qapp, tmp_path):
    summary, _reports_ = _reports(qapp)
    result = _result(summary, requested=[str(tmp_path)])
    path = cover.write_pdf(result, summary, (), str(tmp_path / "only.pdf"))

    assert batch._page_count(path) >= 1


def test_the_html_document_is_the_cover_and_the_sections(qapp, tmp_path):
    summary, reports = _reports(qapp)
    result = _result(summary, requested=[str(tmp_path)])
    written = cover.write_html(result, summary, reports,
                               str(tmp_path / "cover.html"))
    html = open(written, encoding="utf-8").read()

    assert html.startswith("<!DOCTYPE html>") and html.endswith("</html>")
    assert "What they add up to" in html
    for heading in cover.headings_for(reports):
        assert heading in html
    # every compound starts a page of its own, the first one included
    assert html.count('class="break"') >= len(reports)


# --------------------------------------------------------------------------- #
# the tab
# --------------------------------------------------------------------------- #
def _pdf_text(path: str, page: int = 0) -> str:
    from PyQt6.QtPdf import QPdfDocument

    document = QPdfDocument(None)
    try:
        assert document.load(path) == QPdfDocument.Error.None_
        text = document.getAllText(page).text()
        if not text and sys.platform == "win32":
            # measured on the CI runner: the page has its ink and its count
            # (asserted by the callers) and QtPdf extracts no text from a
            # QPdfWriter document there; the order of the pages cannot be
            # read back on Windows, and is on the other two
            pytest.skip("QtPdf extracts no text from this PDF on Windows")
        return text
    finally:
        document.close()
        document.deleteLater()


def _panel(session):
    from milq.ui.infusions_panel import InfusionsPanel

    return InfusionsPanel(session)


def _measured(qapp):
    from milq.session import Session
    from tests.test_infusion_report import _entry

    session = Session()
    for name in ("TESTOL_infusion_A", "TESTOL_infusion_B"):
        entry, _channel = _entry(name=name)
        session.entries.append(entry)
    panel = _panel(session)
    panel.measure(threaded=False)
    return session, panel


def test_the_whole_table_is_reported_with_a_cover(qapp, tmp_path):
    session, panel = _measured(qapp)

    path = panel.write_report(str(tmp_path / "all.pdf"))
    assert path and os.path.exists(path)
    assert "The infusions" in _pdf_text(path)
    assert "What they add up to" in _pdf_text(path)

    note = session.audit.of(audit.INFUSION_REPORT)[0].note
    assert "no cover" not in note

    panel.deleteLater()
    qapp.processEvents()


def test_a_selection_is_reported_without_one(qapp, tmp_path):
    session, panel = _measured(qapp)
    panel.table.selectRow(0)

    path = panel.write_report(str(tmp_path / "one.pdf"))
    assert path and os.path.exists(path)
    assert "What they add up to" not in _pdf_text(path)

    note = session.audit.of(audit.INFUSION_REPORT)[0].note
    assert "a selection, with no cover" in note

    panel.deleteLater()
    qapp.processEvents()


def test_the_tab_says_what_it_passed_over_rather_than_nothing(qapp):
    """An open sample that is not an infusion is not a row, and the cover
    written from the tab has to say that as plainly as the command line
    does."""
    from milq.samples import SampleEntry
    from tests.test_infusion import gradient_sample

    session, panel = _measured(qapp)
    other = SampleEntry("/d/gradient.wiff", 0, "GRADIENT_run")
    other.sample = gradient_sample()
    session.entries.append(other)
    panel.measure(threaded=False)

    result = panel.batch_result(panel.chosen())
    assert [skip.kind for skip in result.skipped] == [batch.NOT_INFUSION]
    assert "GRADIENT_run" in result.skipped[0].reason
    html = cover.build_html(result, panel.summary)
    assert "Nothing was left out" not in html
    assert "GRADIENT_run" in html

    panel.deleteLater()
    qapp.processEvents()
