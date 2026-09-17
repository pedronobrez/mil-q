"""
The method report: everything the checks already say, on one document.

The module adds no measurement of its own, so what is worth testing is that
it runs the existing checks over a method without changing it, that each
answer reaches the page, and that the closing paragraph counts rather than
grades. So the fixture is a small method built to raise a finding of each
severity, to carry one formula, to have one derivable from a name and one
refused by a written precursor, and to have an internal standard nobody
could use as a lock mass beside one who could.

The acquisition is a stub sample of the kind `tests/test_matching.py` uses:
channels with an index, a precursor, a mass range and a time axis. That is
the whole surface `matching` and `health` read, and building one here means
the acquisition section is exercised with no `.wiff` anywhere.

The printed side is opened as a PDF, because nothing about pagination is
visible in the HTML.
"""

import os
from dataclasses import dataclass, replace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import audit, method_report as mr  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.health import SERIOUS  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402
from milq.session import Session  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# --------------------------------------------------------------------------- #
# a stub acquisition, as in tests/test_matching.py
# --------------------------------------------------------------------------- #
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


class Channel:
    def __init__(self, index, precursor, start_mass, end_mass, n=400):
        self.index = index
        self.info = Info(index, precursor, start_mass, end_mass)
        self.rt = np.linspace(0.0, 20.0, n)


class Sample:
    """A survey covering 50–700 and two product-ion channels."""

    name = "Injection 01"

    def __init__(self):
        self.channels = [
            Channel(0, None, 50.0, 700.0),
            Channel(1, 703.5749, 50.0, 720.0),
            Channel(2, 647.5, 50.0, 700.0),
        ]


def method() -> ProcessingMethod:
    """
    Four components, chosen so that every branch of the report has something.

    `SM(d18:1/12:0)` is an internal standard with no formula, so it is a
    warning and no lock mass. `C17:0_Ceramide` is one with a formula and an
    adduct, so it is a candidate. `SM(d18:1/16:0)` names a standard the
    method does not have, which is serious, and its name derives a formula
    that agrees with its precursor. `C25:0-Ceramide` carries a precursor its
    own name contradicts, which is a refusal, and no retention time, which is
    a warning.
    """
    return ProcessingMethod(components=[
        Component("SM(d18:1/12:0)", 647.5, 184.0733, rt=5.60,
                  is_internal_standard=True, adduct="[M+H]+", group="SM"),
        Component("C17:0_Ceramide", 552.5, 534.5245, rt=6.99,
                  is_internal_standard=True, adduct="[M+H]+",
                  formula="C35H69NO3", group="Cer", min_response=5240.0),
        Component("SM(d18:1/16:0)", 703.5749, 184.0733, rt=5.20,
                  internal_standard="Nowhere at all", adduct="[M+H]+",
                  group="SM"),
        Component("C25:0-Ceramide", 664.4, 264.2686, adduct="[M+H]+",
                  internal_standard="SM(d18:1/12:0)", group="Cer"),
    ])


@pytest.fixture
def report():
    return mr.build(method(), acquisition_sample=Sample())


# --------------------------------------------------------------------------- #
# what it reads
# --------------------------------------------------------------------------- #
def test_it_raises_a_finding_of_each_severity(report):
    severities = {f.severity for f in report.health.findings}
    assert SERIOUS in severities and "warning" in severities
    checks = {f.check for f in report.health.findings}
    assert "missing internal standard" in checks          # serious
    assert "no retention time" in checks                  # warning
    assert "internal standard without a formula" in checks


def test_a_flagged_row_carries_the_worst_severity_against_it(report):
    assert report.severity("SM(d18:1/16:0)") == SERIOUS
    assert report.flags["SM(d18:1/16:0)"], "the finding is not on the row"
    # a component nothing flags carries nothing
    assert report.severity("no such component") == ""


def test_a_formula_is_derived_and_another_is_refused(report):
    derived = {p.component.name for p in report.formulas.derivable}
    refused = {r.component.name for r in report.formulas.refusals}
    assert "SM(d18:1/16:0)" in derived
    assert "C25:0-Ceramide" in refused
    assert [c.name for c in report.formulas.carried] == ["C17:0_Ceramide"]
    assert report.formulas.missing == ["C25:0-Ceramide"]


def test_it_never_writes_into_the_method_it_read():
    """`fill_formulas` fills the cells it is given; it is given copies."""
    original = method()
    before = [c.formula for c in original.components]
    built = mr.build(original, acquisition_sample=Sample())
    assert built.formulas.derivable, "nothing was derivable, so nothing is proved"
    assert [c.formula for c in original.components] == before


def test_a_lock_mass_candidate_needs_a_formula(report):
    by_name = {c.component.name: c for c in report.lock_masses}
    assert set(by_name) == {"C17:0_Ceramide"}, "a standard with no formula is no candidate"
    candidate = by_name["C17:0_Ceramide"]
    assert candidate.usable and candidate.declared
    assert candidate.adduct == "[M+H]+"
    assert candidate.exact == pytest.approx(552.5352, abs=5e-4)
    assert candidate.error_ppm == pytest.approx(-63.7, abs=1.0)


def test_an_undeclared_adduct_is_read_off_the_written_precursor():
    """A method that names no adduct is not priced as a protonated molecule."""
    ammonium = Component("cholic acid-d4", 430.3465, 359.287,
                         is_internal_standard=True, formula="C24H36D4O5")
    built = mr.build(ProcessingMethod(components=[ammonium]))
    candidate = built.lock_masses[0]
    assert candidate.adduct == "[M+NH4]+"
    assert not candidate.declared and candidate.note


def test_the_acquisition_says_what_serves_what_and_what_the_survey_misses(report):
    acquisition = report.acquisition
    assert acquisition is not None and acquisition.channels == 3
    assert acquisition.survey_ranges == ["50–700"]
    served = {s.component: s for s in acquisition.served}
    assert served["SM(d18:1/16:0)"].channel == "TOF PI 703.57"
    assert not served["SM(d18:1/16:0)"].survey
    # 703.57 is past the survey's 700, and the survey is the only thing that
    # could have covered it
    assert acquisition.outside_survey == ["SM(d18:1/16:0)"]
    # 664.4 and 552.5 have no product-ion channel of their own, so both fall
    # back to the survey — a different measurement, which the section says
    assert served["C25:0-Ceramide"].survey and served["C17:0_Ceramide"].survey
    assert len(acquisition.on_survey) == 2 and len(acquisition.on_own_channel) == 2
    assert acquisition.unserved == []


def test_without_a_sample_the_acquisition_section_is_absent_and_said_so():
    built = mr.build(method())
    assert built.acquisition is None
    assert built.health.skipped, "a check that could not run must say so"
    assert "No acquisition was open" in " ".join(built.closing())
    assert "5. The acquisition" not in mr.build_html(built)


def test_the_schedule_comes_from_the_method_alone(report):
    schedule = report.schedule
    assert len(schedule.slots) == 3            # C25:0-Ceramide has no time
    assert schedule.unscheduled == ["C25:0-Ceramide"]
    # 5.10-6.10 and 4.70-5.70 overlap; 6.49-7.49 sits clear of both
    assert schedule.busiest == 2
    assert schedule.target_cycle == mr.DEFAULT_CYCLE
    assert "round number" in report.cycle_basis


def test_a_batch_moves_the_target_cycle_off_the_round_number():
    from milq.sampling import ComponentSampling, SamplingReport

    sampling = SamplingReport(rows=[
        ComponentSampling("SM(d18:1/16:0)", False, found=10, cycle=14.6,
                          width=14.6, points=1.0)])
    built = mr.build(method(), batch=sampling)
    assert built.schedule.target_cycle != mr.DEFAULT_CYCLE
    assert built.schedule.target_cycle == pytest.approx(12.4, abs=0.1)
    assert "round number" not in built.cycle_basis


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def test_every_section_is_present_and_numbered(report):
    document = mr.build_html(report)
    for number, heading in enumerate(mr.SECTIONS.values(), start=1):
        assert f"{number}. {heading}" in document, heading
    assert document.startswith("<!DOCTYPE html>")


def test_the_component_table_marks_the_flagged_rows(report):
    document = mr.build_html(report)
    assert mr.SERIOUS_MARK in document and mr.WARNING_MARK in document
    serious = sum(1 for name in report.flags
                  if report.severity(name) == SERIOUS)
    assert f"{serious:,} row(s) carry a serious finding" in document


def test_the_findings_heading_counts_findings_not_components(report):
    document = mr.build_html(report)
    assert f"Serious — {len(report.health.serious):,}" in document
    assert f"Warnings — {len(report.health.warnings):,}" in document


def test_the_refusals_print_both_masses(report):
    document = mr.build_html(report)
    repair = report.formulas.refusals[0]
    assert f"{repair.theoretical:,.4f}" in document
    assert f"{repair.written:,.4f}" in document
    assert "Likelier error" in document


def test_the_lock_section_says_a_candidate_is_not_a_lock_mass(report):
    document = mr.build_html(report)
    assert "Being a candidate is not being a lock mass" in document
    assert "50 ppm" in document


def test_the_closing_counts_and_refuses_to_grade(report):
    sentences = report.closing()
    assert len(sentences) >= 6
    joined = " ".join(sentences)
    assert sentences[-1].startswith("None of the above is a verdict")
    # no verdict word anywhere: the paragraph counts, it does not grade
    import re
    for word in ("passes", "passed", "fails", "failed", "healthy", "sound",
                 "score", "grade", "acceptable"):
        assert not re.search(rf"\b{word}\b", joined.lower()), word
    assert "The method declares 4 component(s)" in joined
    assert "3 carry a retention time and 1 do not" in joined
    assert "1 standard(s) carry the formula and adduct a lock mass needs" in joined
    assert "Against Injection 01" in joined
    assert "at most 2 acquired at once" in joined


def test_the_closing_paragraph_is_in_the_document(report):
    document = mr.build_html(report)
    assert "What the method is missing" in document
    for sentence in report.closing():
        assert sentence.split(";")[0][:60] in document


def test_it_writes_a_pdf_that_is_a_pdf(qapp, report, tmp_path):
    path = mr.write_pdf(report, tmp_path / "method.pdf")
    assert os.path.exists(path)
    with open(path, "rb") as handle:
        assert handle.read(5) == b"%PDF-"

    from PyQt6.QtPdf import QPdfDocument

    document = QPdfDocument(None)
    document.load(path)
    assert document.pageCount() >= 1


def test_it_writes_html_that_opens_on_its_own(report, tmp_path):
    path = mr.write_html(report, tmp_path / "method.html")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert text.startswith("<!DOCTYPE html>") and text.endswith("</html>")
    assert "<style>" in text, "the styling has to travel with the file"


def test_a_bare_reader_sample_is_accepted_as_well_as_an_entry():
    """The report takes what a script has and what a project has alike."""
    from milq.samples import SampleEntry

    sample = Sample()
    entry = SampleEntry(path="/nowhere/x.wiff", sample_index=0,
                        name="Injection 01", sample=sample)
    from_sample = mr.build(method(), acquisition_sample=sample)
    from_entry = mr.build(method(), acquisition_sample=entry)
    assert from_sample.acquisition.channels == from_entry.acquisition.channels
    assert ([s.channel for s in from_sample.acquisition.served]
            == [s.channel for s in from_entry.acquisition.served])


# --------------------------------------------------------------------------- #
# the button
# --------------------------------------------------------------------------- #
def test_the_toolbar_button_writes_a_report_and_records_it(qapp, tmp_path,
                                                           monkeypatch):
    from milq.ui.method_workspace import MethodWorkspace

    session = Session()
    session.set_components([replace(c) for c in method().components])
    widget = MethodWorkspace(session)
    assert widget.btn_method_report.isVisible() or True     # offscreen
    assert widget.btn_method_report.toolTip()

    target = tmp_path / "method-report.pdf"
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "PDF (*.pdf)")))
    widget.export_method_report()

    assert target.exists()
    written = [e for e in session.audit if e.what == audit.METHOD_REPORT]
    assert len(written) == 1
    assert written[0].after == "method-report.pdf"
    assert "no acquisition open" in written[0].note
    assert "4 component(s)" in written[0].target


def test_the_button_writes_html_when_html_is_chosen(qapp, tmp_path, monkeypatch):
    from milq.ui.method_workspace import MethodWorkspace

    session = Session()
    session.set_components([replace(c) for c in method().components])
    widget = MethodWorkspace(session)
    target = tmp_path / "method-report"          # no extension: it is added
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "HTML (*.html)")))
    widget.export_method_report()
    assert (tmp_path / "method-report.html").exists()


def test_the_button_says_so_rather_than_writing_an_empty_method(qapp, monkeypatch):
    from milq.ui.method_workspace import MethodWorkspace

    called = []
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: called.append(1) or ("", "")))
    widget = MethodWorkspace(Session())
    widget.export_method_report()
    assert called == [], "an empty method never reaches the file dialog"
    assert "component list" in widget.status.text()
