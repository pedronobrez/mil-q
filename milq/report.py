"""
A report of a batch, to print or to hand over.

CSV is what you export to carry on working; a report is what you keep. It has
to answer, on its own and months later, what was measured, against what
method, how the curve was built, which rows passed and which did not — without
the reader having the project open, or this application at all.

The document is HTML because Qt can lay HTML out and print it, and because a
report that also opens in a browser is a report that survives this program.
Nothing here reads a widget: it is built from the session, so it can be
generated with no window on screen, and tested.

Nothing is rounded that a decision depends on. Areas and concentrations keep
the digits the results carry; retention times keep three decimals, which is
better than any chromatography, and percentages two.

The page is A4 portrait, and the styling is deliberately narrow: Qt's rich
text engine understands a small subset of CSS and silently ignores the rest,
so everything here is something that was rendered and looked at. Cell padding
comes from the `cellpadding` attribute and column widths from `width`, because
the CSS spellings of both do nothing.
"""

from __future__ import annotations

import datetime as _dt
import html
import os

from . import __version__
from .audit import COLUMNS as AUDIT_COLUMNS
from .calibration import Calibration
from .health import SERIOUS, check_method
from .method import ProcessingMethod
from .quantify import PeakResult, ResultsSet
from .samples import SampleEntry
from .statistics import GROUP_BY_SAMPLE_TYPE, summarise
from .qc import (ALWAYS_OUT_PERCENT, CV_PERCENT, DRIFT_CORRELATION,
                 DRIFT_PERCENT, MIN_SNR, OUTLIER_SIGMA, OUT_PERCENT,
                 batch_qc)
from .validation import all_detection_limits, carryover
from .xlsx import Sheet, write_xlsx

#: the statuses a row can carry. Matched without regard to case: the results
#: capitalise them and an earlier version of this counted them in lower case,
#: so a batch with twenty-eight passes and two failures reported that no
#: acceptance criteria had been set.
STATUSES = ("pass", "marginal", "fail")

#: the sections, in the order they are printed, with the headings they carry.
#: A caller names them by key; the number in front is added here so that
#: leaving one out does not leave a gap in the numbering.
SECTIONS = {
    "summary": "Summary",
    "samples": "Samples",
    "method": "Method",
    "calibration": "Calibration",
    "limits": "Detection and quantitation limits",
    "carryover": "Carryover",
    "quality": "Batch quality",
    "sampling": "Sampling",
    "mass": "Mass drift",
    "infusions": "Infusions",
    "infusion-comparison": "Infusion comparison",
    "spectra": "Compared spectra",
    "algorithms": "Integration algorithms",
    "batches": "Batch comparison",
    "audit": "Changes made by hand",
    "results": "Results",
    "statistics": "Statistics",
}
ALL_SECTIONS = tuple(SECTIONS)

#: A4 portrait, in millimetres: left, top, right, bottom, then the bands kept
#: clear at the top and bottom of every page for the running furniture.
MARGINS_MM = (18.0, 15.0, 15.0, 15.0)
HEADER_MM = 8.0
FOOTER_MM = 10.0

#: how many times the document may be laid out again to pull a stranded
#: heading onto the page of the thing it introduces. Moving one heading can
#: strand another, and this stops that chasing its own tail.
MAX_REFLOWS = 3

#: what Qt puts in a block's text where an inline object — a picture — sits.
#: It is how `_orphan_headings` tells a block that cannot be split from one
#: that can.
OBJECT_CHARACTER = "￼"

#: markers on a sample's name, explained in a legend under the table that
#: uses them. A column of "yes / no / by hand" costs more width than it earns.
EXCLUDED = "†"
BY_HAND = "‡"


def _escape(value) -> str:
    return html.escape("" if value is None else str(value))


def _number(value, decimals: int = 4) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return _escape(value)


def _table(headers: list[str] | None, rows: list[list[str]],
           right: set[int] = frozenset(), empty: str = "Nothing to show.",
           widths: list[str] | None = None) -> str:
    """
    One table, striped, with a heading row that repeats on every printed page.

    Qt takes the width of a column from the `width` attribute of its cells and
    the space inside a cell from `cellpadding`; the CSS properties of the same
    names are parsed and dropped. Both are given here in per cent and in
    pixels, which is what those attributes mean.

    Columns are wide enough for the longest single word in their heading. A
    heading may wrap at a space — two lines of `Internal standard` reads
    fine — but one that wraps inside a word does not, and `Concentratio/n` is
    what a column that is four points too narrow looks like.

    Headings are optional: a table of names against values has nothing to put
    in them, and an empty heading row is a grey band that means nothing.
    """
    if not rows:
        return f'<p class="empty">{_escape(empty)}</p>'
    head = ""
    if headers:
        cells = []
        for index, heading in enumerate(headers):
            width = f' width="{widths[index]}"' if widths else ""
            align = ' class="num"' if index in right else ""
            cells.append(f"<th{width}{align}>{_escape(heading)}</th>")
        head = f'<thead><tr>{"".join(cells)}</tr></thead>'
    body = []
    for number, row in enumerate(rows):
        stripe = ' class="alt"' if number % 2 else ""
        cells = []
        for index, cell in enumerate(row):
            width = (f' width="{widths[index]}"'
                     if widths and not headers else "")
            cells.append(f'<td class="{"num" if index in right else ""}"'
                         f"{width}>{cell}</td>")
        body.append(f'<tr{stripe}>{"".join(cells)}</tr>')
    return (f'<table width="100%" cellpadding="4" cellspacing="0">{head}'
            f'<tbody>{"".join(body)}</tbody></table>')


def _heading(title: str, breaks: set[str] | None = None) -> str:
    css = ' class="break"' if breaks and title in breaks else ""
    return f"<h2{css}>{_escape(title)}</h2>"


# --------------------------------------------------------------------------- #
# the front of the report
# --------------------------------------------------------------------------- #
def _title_block(title: str, project: str | None, entries, method) -> str:
    """
    What the report is of, on the page rather than in a file name.

    A report is read detached from everything that made it, so the batch it
    describes has to be identifiable from the paper alone.
    """
    when = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    where = os.path.basename(project) if project else "unsaved project"
    standards = sum(1 for e in entries if e.sample_type == "Standard")
    internal = sum(1 for c in method.components if c.is_internal_standard)
    return (
        f'<p class="eyebrow">MIL-Q {_escape(__version__)} · batch report</p>'
        f"<h1>{_escape(title)}</h1>"
        f'<table class="ident" width="100%" cellpadding="4" cellspacing="0">'
        f'<tr><td class="label" width="18%">Project</td><td width="32%">{_escape(where)}</td>'
        f'<td class="label" width="18%">Generated</td><td width="32%">{when}</td></tr>'
        f'<tr><td class="label">Samples</td><td>{len(entries):,}'
        f'{f" ({standards:,} standards)" if standards else ""}</td>'
        f'<td class="label">Components</td><td>{len(method.components):,}'
        f'{f" ({internal:,} internal standards)" if internal else ""}</td></tr>'
        f"</table>"
    )


def _contents(titles: list[str], pages: dict[str, int] | None,
              heading: str = "Contents") -> str:
    """
    The sections, and where they are.

    The page numbers are not known until the document has been laid out, so
    this is built twice: once with the column empty to fix the pagination, and
    again with the numbers found by that first pass. The row heights are the
    same either way, which is what makes the second pass agree with the first.
    """
    if len(titles) < 2:
        return ""
    rows = []
    for number, title in enumerate(titles):
        stripe = ' class="alt"' if number % 2 else ""
        page = "" if not pages else str(pages.get(title, ""))
        cell = (f'<td class="num" width="8%">{page}</td>'
                if pages is not None else "")
        rows.append(f'<tr{stripe}><td>{_escape(title)}</td>{cell}</tr>')
    return (f'<h2 class="plain">{_escape(heading)}</h2>'
            f'<table class="contents" width="60%" cellpadding="3" cellspacing="0">'
            f'{"".join(rows)}</table>')


# --------------------------------------------------------------------------- #
# the sections
# --------------------------------------------------------------------------- #
def _findings(results: ResultsSet, entries: list[SampleEntry],
              method: ProcessingMethod, calibrations) -> str:
    """
    What a reader should not have to find for themselves.

    A summary that only counts things makes the reader hunt through eight
    sections for the two rows that matter. This says what failed and where,
    and says plainly when nothing did — which is not the same as saying
    everything passed, because a batch with no acceptance criteria fails
    nothing at all.
    """
    notes = []

    failed = [row for row in results
              if str(getattr(row, "status", "") or "").strip().lower() == "fail"]
    if failed:
        components = sorted({row.component for row in failed})
        shown = ", ".join(_escape(name) for name in components[:4])
        if len(components) > 4:
            shown += f" and {len(components) - 4} more"
        notes.append(f"{len(failed):,} result(s) outside their acceptance "
                     f"criteria, in {shown}.")

    try:
        found = carryover(results, entries, method)
    except Exception:                                  # a report must still print
        found = None
    if found is not None and found.failures:
        worst = max(found.failures, key=lambda row: row.percent)
        notes.append(f"{len(found.failures)} component(s) over the carryover "
                     f"limit in {_escape(worst.blank)}, the worst "
                     f"{_escape(worst.component)} at {_number(worst.percent, 2)}%.")

    try:
        quality = batch_qc(results, entries, method)
    except Exception:                                  # a report must still print
        quality = None
    if quality is not None:
        if quality.drifted:
            worst = max(quality.drifted, key=lambda c: abs(c.drift))
            notes.append(f"{len(quality.drifted)} internal standard(s) drifted "
                         f"across the run, the worst {_escape(worst.component)} "
                         f"by {_number(worst.drift, 1)}%.")
        if quality.unusable:
            notes.append(f"{len(quality.unusable)} internal standard(s) cannot "
                         f"normalise anything: over a third of the run is more "
                         f"than {_number(ALWAYS_OUT_PERCENT, 0)}% from their "
                         f"centre.")
        if quality.index is not None and quality.index.out:
            notes.append(f"{len(quality.index.out)} injection(s) where every "
                         f"internal standard went together — the injection, "
                         f"not the compound.")
        stray = sum(len(chart.out) for chart in quality.out
                    if not chart.unusable)
        if stray:
            notes.append(f"{stray} injection(s) outside their internal "
                         f"standard's limits.")
        if quality.imprecise:
            worst = max(quality.imprecise, key=lambda r: r.percent_cv)
            notes.append(f"{len(quality.imprecise)} component(s) over "
                         f"{_number(CV_PERCENT, 0)}% CV across the quality "
                         f"controls, the worst {_escape(worst.component)} at "
                         f"{_number(worst.percent_cv, 1)}%.")

    extrapolated = [limits for limits in all_detection_limits(calibrations, method)
                    if limits.extrapolated]
    if extrapolated:
        notes.append(f"{len(extrapolated)} limit(s) of quantitation fall below "
                     f"the lowest standard: extrapolated from the curve, not "
                     f"demonstrated by it.")

    if not notes:
        return ('<p class="empty">Nothing was found outside the limits that '
                'were set. Where no criterion was set, nothing is claimed.</p>')
    items = "".join(f"<li>{note}</li>" for note in notes)
    return f'<ul class="findings">{items}</ul>'


def _summary(title: str, results: ResultsSet, entries: list[SampleEntry],
             method: ProcessingMethod, calibrations,
             breaks: set[str] | None = None) -> str:
    rows = list(results)
    counted = {name: 0 for name in STATUSES}
    integrated = 0
    for row in rows:
        status = str(getattr(row, "status", "") or "").strip().lower()
        if status in counted:
            counted[status] += 1
        if row.area is not None:
            integrated += 1
    excluded = sum(1 for row in rows if not row.used)
    manual = sum(1 for row in rows if row.manual)

    body = [
        ["Rows", f"{len(rows):,}"],
        ["Integrated", f"{integrated:,} of {len(rows):,}"],
        ["Integrated by hand", f"{manual:,}"],
        ["Excluded from statistics", f"{excluded:,}"],
    ]
    if any(counted.values()):
        body.append(["Pass / Marginal / Fail",
                     " / ".join(f"{counted[name]:,}" for name in STATUSES)])
    else:
        body.append(["Acceptance", "no criteria set — no status is reported"])
    return (_heading(title, breaks)
            + _table(None, body, right={1}, widths=["70%", "30%"])
            + _findings(results, entries, method, calibrations))


def _samples(title: str, entries: list[SampleEntry],
             breaks: set[str] | None = None) -> str:
    rows = []
    for entry in entries:
        rows.append([
            _escape(entry.name), _escape(entry.filename),
            _escape(entry.sample_type), _escape(entry.sample_group or "—"),
            _number(entry.actual_concentration, 4)
            if entry.actual_concentration is not None else "—",
            _number(entry.dilution_factor, 4),
            _escape(entry.comment or ""),
        ])
    return _heading(title, breaks) + _table(
        ["Sample", "File", "Type", "Group", "Concentration", "Dilution", "Comment"],
        rows, right={4, 5}, empty="No samples were open.",
        widths=["15%", "23%", "12%", "12%", "14%", "9%", "15%"])


def _method(title: str, method: ProcessingMethod,
            breaks: set[str] | None = None,
            entries: list[SampleEntry] | None = None) -> str:
    rows = []
    for component in method.components:
        role = "internal standard" if component.is_internal_standard else (
            f"qualifier of {component.qualifier_of}" if component.qualifier_of else "")
        rows.append([
            _escape(component.name), _escape(component.group or "—"),
            _number(component.precursor, 4), _number(component.fragment, 4),
            _number(component.rt, 3) if component.rt else "—",
            f"±{_number(component.rt_halfwidth, 2)}",
            f"{_number(component.tolerance, 3)} {_escape(component.unit)}",
            _escape(component.internal_standard or "—"),
            _escape(role),
        ])
    return (_heading(title, breaks) + _health(method, entries) + _table(
        ["Component", "Group", "Precursor", "Fragment", "RT", "Window",
         "Tolerance", "Internal standard", "Role"],
        rows, right={2, 3, 4, 5, 6}, empty="The method has no components.",
        widths=["15%", "13%", "10%", "10%", "7%", "8%", "10%", "15%", "12%"]))


def _health(method: ProcessingMethod, entries: list[SampleEntry]) -> str:
    """
    What the method will fail at, before any of its numbers are read.

    Put in front of the component table rather than after it: a reader who
    learns that a third of the panel shares a transition should learn it
    before they start reading rows.
    """
    try:
        health = check_method(method, entries)
    except Exception:                              # a report must still print
        return ""
    if health.sound and not health.skipped:
        return '<p class="meta">Nothing in the method contradicts itself.</p>'
    parts = []
    for finding in health.findings:
        names = ", ".join(finding.components[:6])
        if finding.count > 6:
            names += f", and {finding.count - 6} more"
        mark = ('<span class="bad">serious</span>' if finding.severity == SERIOUS
                else "warning")
        parts.append(f'<p class="foot">{mark} — {_escape(finding.summary)}. '
                     f"{_escape(finding.detail)} <i>{_escape(names)}</i></p>")
    for note in health.skipped:
        parts.append(f'<p class="foot">not checked: {_escape(note)}</p>')
    return "".join(parts)


def _calibrations(title: str, calibrations: dict[str, Calibration],
                  method: ProcessingMethod,
                  breaks: set[str] | None = None) -> str:
    """
    The curves, with an internal standard's marked as what it is.

    A curve is built for anything with standards behind it, an internal
    standard included — and that one is flat by construction, because the same
    amount is spiked into every sample whatever the analyte's concentration.
    It comes out with an r² near zero, which reads as a failed calibration
    rather than as a meaningless one. Saying which is which costs a word.
    """
    internal = {c.name for c in method.components if c.is_internal_standard}
    fitted = {name: curve for name, curve in calibrations.items()
              if curve is not None and curve.is_fitted}
    rows = []
    for name in sorted(fitted):
        curve = fitted[name]
        label = _escape(name)
        if name in internal:
            label += ' <span class="aside">— internal standard, flat by design</span>'
        rows.append([
            label, _escape(curve.regression), _escape(curve.weighting),
            _escape(curve.equation), _number(curve.r2, 6), _number(curve.r, 6),
            f"{len(curve.used_points)} of {len(curve.points)}",
        ])
    return _heading(title, breaks) + _table(
        ["Component", "Regression", "Weighting", "Equation", "r²", "r", "Points"],
        rows, right={4, 5, 6},
        empty="No curve was built. Mark samples as Standard and give them a "
              "concentration.",
        widths=["19%", "12%", "11%", "26%", "10%", "10%", "12%"])


def _limits(title: str, calibrations, method: ProcessingMethod,
            breaks: set[str] | None = None) -> str:
    rows = []
    for limits in all_detection_limits(calibrations, method):
        if not limits.measurable:
            rows.append([_escape(limits.component), "—", "—", "—", "—",
                         _escape(limits.note or "not derived")])
            continue
        note = limits.note
        if limits.extrapolated:
            warning = (f"below the lowest standard "
                       f"({_number(limits.lowest_standard, 4)}) — extrapolated, "
                       f"not demonstrated")
            note = f"{note}; {warning}" if note else warning
        rows.append([
            _escape(limits.component),
            _number(limits.lod, 4), _number(limits.loq, 4),
            _number(limits.sigma, 6), _number(limits.slope, 6),
            _escape(note),
        ])
    return (_heading(title, breaks)
            + '<p class="meta">3.3&#963;/S and 10&#963;/S, with &#963; the '
              "residual standard deviation of the curve about its own line "
              "(ICH Q2). Internal standards are left out.</p>"
            + _table(["Component", "LOD", "LOQ", "σ", "Slope", "Notes"],
                     rows, right={1, 2, 3, 4},
                     empty="No curve to derive a limit from.",
                     widths=["18%", "11%", "11%", "12%", "12%", "36%"]))


def _carryover(title: str, results: ResultsSet, entries: list[SampleEntry],
               method: ProcessingMethod, breaks: set[str] | None = None) -> str:
    found = carryover(results, entries, method)
    if found.note:
        return (_heading(title, breaks)
                + f'<p class="empty">{_escape(found.note)}</p>')
    rows = []
    for row in sorted(found.rows, key=lambda r: -r.percent):
        verdict = ('<span class="bad">over the limit</span>' if row.fails
                   else "within the limit")
        rows.append([
            _escape(row.component), _number(row.blank_area, 1),
            _number(row.reference_area, 1), _number(row.percent, 2), verdict,
        ])
    first = found.rows[0] if found.rows else None
    heading = ""
    if first is not None:
        heading = (f'<p class="meta">{_escape(first.blank)}, injected after '
                   f"{_escape(first.follows)}, against the response at the "
                   f"lowest calibrated concentration ({_escape(first.reference)}). "
                   f"Limit {_number(first.limit, 0)}%.</p>")
    return (_heading(title, breaks) + heading
            + _table(["Component", "Blank", "At the lowest standard", "%", ""],
                     rows, right={1, 2, 3}, empty="Nothing to compare.",
                     widths=["24%", "16%", "22%", "11%", "27%"]))


def _quality(title: str, results: ResultsSet, entries: list[SampleEntry],
             method: ProcessingMethod, breaks: set[str] | None = None) -> str:
    """
    What the run did between the first injection and the last.

    Per-sample review cannot see a response that falls away across ninety
    injections: every point is inside its limits and the batch is still not
    the batch it started as.
    """
    report = batch_qc(results, entries, method)
    parts = [_heading(title, breaks)]
    if report.note:
        return "".join(parts) + f'<p class="empty">{_escape(report.note)}</p>'

    order = ("in the order the instrument ran them"
             if report.ordered else
             f"in the order the files were opened — {report.timed} of "
             f"{report.injections} injections carry an acquisition time")
    parts.append(
        f'<p class="meta">Internal-standard response {order}. The centre is '
        f"the median and the spread the median absolute deviation, so that "
        f"one bad injection cannot widen the limits meant to catch it. An "
        f"injection is called out when it is both beyond "
        f"{OUTLIER_SIGMA:g}&#963; and at least {OUT_PERCENT:g}% from the "
        f"centre: a batch that repeats itself well has a spread so small "
        f"that three of them is a difference nobody would act on. Drift is "
        f"the fitted change across the whole run, reported when it is at "
        f"least {DRIFT_PERCENT:g}% and goes one way (Spearman's &#961; "
        f"beyond {DRIFT_CORRELATION:g}). A standard whose median "
        f"signal-to-noise is below {MIN_SNR:g} is charted but not flagged: "
        f"below the limit of quantitation a small absolute change is a large "
        f"relative one, and every flag against it would be arithmetic on "
        f"noise.</p>")

    if report.index is not None and report.index.measurable:
        index = report.index
        parts.append("<h3>The injections, taken together</h3>")
        parts.append(
            '<p class="meta">Each internal standard against its own median '
            "across the run, then the median of those per injection. A single "
            "standard cannot tell an injection that failed from a compound "
            "that misbehaved; comparing the standards within an injection "
            "can.</p>")
        rows = []
        for point in index.injections:
            said = ("<span class=\"bad\">every standard went together</span>"
                    if point.out else ("worth a look" if point.warned else ""))
            rows.append([f"{point.order}", _escape(point.sample),
                         _number(point.value, 2), _number(point.percent, 1),
                         said])
        parts.append(_table(["#", "Injection", "Index", "% from normal", ""],
                            rows, right={0, 2, 3},
                            widths=["6%", "34%", "12%", "16%", "32%"]))
    elif report.index is not None and report.index.note:
        parts.append(f'<p class="empty">{_escape(report.index.note)}</p>')

    rows = []
    for chart in report.charts:
        if not chart.measurable:
            rows.append([_escape(chart.component),
                         f"{len(chart.injections):,}", "—", "—",
                         _number(chart.snr, 0) if chart.snr is not None else "—",
                         "—", "—",
                         _escape(chart.note or "not measurable")])
            continue
        verdict = []
        if not chart.quantifiable:
            if chart.floor is not None:
                verdict.append(f"below its floor of {chart.floor:,.0f} — not "
                               f"usable, so not flagged")
            else:
                verdict.append(f"below S/N {MIN_SNR:g} — not quantified, so "
                               f"not flagged")
        elif chart.unusable:
            verdict.append(f'<span class="bad">cannot normalise</span>: '
                           f"{len(chart.out)} of {len(chart.injections)} "
                           f"injections over {ALWAYS_OUT_PERCENT:g}% out")
        if chart.drifted:
            verdict.append('<span class="bad">drift</span>')
        if chart.out and not chart.unusable:
            verdict.append(f'<span class="bad">{len(chart.out)} outside '
                           f"their limits</span>")
        if chart.excess_warnings:
            verdict.append(f"{len(chart.warned)} beyond 2&#963;")
        if chart.quantifiable and chart.below_floor:
            verdict.append(f"{len(chart.below_floor)} injection(s) below the "
                           f"floor of {chart.floor:,.0f}")
        rows.append([
            _escape(chart.component), f"{len(chart.injections):,}",
            _number(chart.centre, 1), _number(chart.sigma, 1),
            _number(chart.snr, 0) if chart.snr is not None else "—",
            _number(chart.drift, 1), _number(chart.correlation, 3),
            "; ".join(verdict) or (_escape(chart.note) if chart.note
                                   else "steady"),
        ])
    parts.append(_table(
        ["Component", "n", "Centre", "Spread", "S/N", "Drift %", "\u03c1",
         "Verdict"],
        rows, right={1, 2, 3, 4, 5, 6}, empty="Nothing to chart.",
        widths=["20%", "6%", "12%", "12%", "9%", "9%", "8%", "24%"]))

    for chart in report.charts:
        for point in (chart.out if not chart.unusable else []):
            parts.append(
                f'<p class="foot">{_escape(chart.component)} — injection '
                f"{point.order}, {_escape(point.sample)}: "
                f"{_number(point.percent, 1)}% from the centre "
                f"({_number(point.sigmas, 1)}&#963;)</p>")

    measured = [row for row in report.precision if row.measurable]
    if measured:
        parts.append("<h3>Precision of the quality controls</h3>")
        rows = []
        for row in sorted(measured, key=lambda r: -(r.percent_cv or 0.0)):
            rows.append([
                _escape(row.component), f"{row.replicates:,}",
                _number(row.mean, 1), _number(row.percent_cv, 2),
                ('<span class="bad">over the limit</span>' if row.fails
                 else "within the limit"),
            ])
        parts.append(_table(["Component", "n", "Mean", "%CV", ""], rows,
                            right={1, 2, 3}, empty="Nothing to summarise.",
                            widths=["30%", "9%", "20%", "13%", "28%"]))
    return "".join(parts)


def _sampling(title: str, results: ResultsSet, entries: list[SampleEntry],
              method: ProcessingMethod, breaks: set[str] | None = None,
              most: int = 60) -> str:
    """
    How many points the acquisition put on each peak.

    The one thing three other sections keep running into — estimates that
    cannot be trusted, floors that cannot be derived, algorithms that change
    nothing — and the one thing no processing can fix. Said here with the
    cycle time the peaks would need, so that the schedule can be changed.
    """
    from .sampling import BASE_POINTS, sampling_report
    from .processing import MIN_FIT_POINTS

    report = sampling_report(results, entries, method)
    parts = [_heading(title, breaks)]
    parts.append(
        f'<p class="meta">For each component, the cycle time of its channel, '
        f"the median width of its peaks at half height, and the median number "
        f"of points on the peak — points at or above one per cent of its "
        f"height, the ones that are the peak rather than its feet. A Gaussian "
        f"fit needs {MIN_FIT_POINTS}; quantitation textbooks ask for about "
        f"{BASE_POINTS} across the base. The last two columns are the cycle "
        f"times that would give each, for peaks of that width. This is a "
        f"property of the acquisition schedule, and nothing in the "
        f"processing substitutes for it. A peak with one point above half "
        f"height has no measurable width — it is narrower than a cycle — and "
        f"is counted in the last column rather than in the width.</p>")
    parts.append(f"<p>{_escape(report.summary())}</p>")
    if report.note or not report.measured:
        return "".join(parts)
    rows = sorted(report.measured, key=lambda r: (r.points, -r.found))
    table = []
    for row in rows[:most]:
        name = _escape(row.component + (" (IS)" if row.is_internal_standard else ""))
        if row.too_sparse:
            name = f'<span class="bad">{name}</span>'
        table.append([
            name, f"{row.found:,}",
            _number(row.cycle, 1), _number(row.width, 1), _number(row.points, 0),
            (f"{row.sparse} ({row.sparse_share:.0%})" if row.found else "—"),
            _number(row.cycle_for_fit, 1), _number(row.cycle_for_base, 1),
            f"{row.unmeasured}",
        ])
    if len(rows) > most:
        parts.append(f"<p>The {most} components with the fewest points, of "
                     f"{len(rows)}:</p>")
    parts.append(_table(
        ["Component", "n", "Cycle (s)", "Width (s)", "Points",
         f"Under {MIN_FIT_POINTS}", "Cycle for a fit (s)",
         f"Cycle for {BASE_POINTS} (s)", "Narrower than a cycle"],
        table, right={1, 2, 3, 4, 5, 6, 7, 8},
        widths=["22%", "5%", "9%", "9%", "8%", "11%", "12%", "12%", "12%"]))
    return "".join(parts)


def _mass(title: str, drift, breaks: set[str] | None = None,
          corrections: dict | None = None, applied: bool = False) -> str:
    """Whether the mass axis moved during the run; printed only when it
    was measured, since measuring is a minute of reading survey spectra."""
    from .mass_drift import DRIFT_PPM, MIN_INJECTIONS
    from .precursor import CONSENSUS_SPREAD_PPM
    from .recalibrate import MAX_LOCK_ERROR_PPM, lock_mass_refusal

    parts = [_heading(title, breaks)]
    if drift.note:
        return "".join(parts) + f'<p class="empty">{_escape(drift.note)}</p>'
    order = ("in the order the instrument ran them" if drift.ordered else
             f"in the order the files were opened — {drift.timed} of "
             f"{drift.injections} injections carry an acquisition time")
    parts.append(
        f'<p class="meta">Each internal standard\u2019s precursor read from '
        f"the survey scan in every injection, {order}, against the "
        f"batch\u2019s own median; the exact mass from formula and adduct "
        f"where the component carries them. A component drifted when the "
        f"change fitted across the run is at least {DRIFT_PPM:g} ppm and goes "
        f"one way (Spearman\u2019s &#961; beyond 0.5); fewer than "
        f"{MIN_INJECTIONS} injections cannot show a trend, and a spread over "
        f"{CONSENSUS_SPREAD_PPM:g} ppm between injections means they did not "
        f"measure the same ion, so no trend is fitted. Injections agreeing "
        f"with each other say nothing about agreeing with the compound, so a "
        f"component measured more than {MAX_LOCK_ERROR_PPM:g} ppm from its "
        f"own formula in most of them is named as measuring a different ion "
        f"and is not used as a lock mass. The index is the "
        f"median over the standards, per injection, of each one\u2019s "
        f"deviation \u2014 what the instrument did rather than any one "
        f"compound.</p>")
    trends = ([drift.index] if drift.index is not None else []) + list(drift.trends)
    rows = []
    for trend in trends:
        is_index = trend.nominal == 0.0 and trend.exact is None
        verdict = _escape(trend.note) if trend.note else "steady"
        if trend.drifted:
            verdict = f'<span class="bad">drift {trend.change:+.1f} ppm</span>'
        refusal = lock_mass_refusal(trend)
        if refusal:
            verdict = (f'{verdict} \u00b7 <span class="bad">'
                       f'{_escape(refusal)}</span>')
        rows.append([
            _escape(trend.component), f"{len(trend.points)}",
            "—" if is_index else _number(trend.median, 4),
            _number(trend.exact, 4), _number(trend.error_ppm, 1),
            _number(trend.spread_ppm, 1), _number(trend.change, 1),
            _number(trend.correlation, 3), verdict])
    parts.append(_table(
        ["Component", "n", "Median m/z", "Exact m/z", "Error ppm", "Spread ppm",
         "Change ppm", "\u03c1", "Verdict"],
        rows, right={1, 2, 3, 4, 5, 6, 7}, empty="Nothing measured.",
        widths=["20%", "5%", "12%", "12%", "9%", "9%", "9%", "7%", "17%"]))
    parts.append(_corrections(corrections, applied))
    return "".join(parts)


def _corrections(corrections: dict | None, applied: bool) -> str:
    """
    The recalibration fitted from the lock masses, while a fit stands.

    Printed under the drift because it is the same measurement asked a
    different question, and left out entirely when nothing has been fitted:
    a table of dashes says less than no table at all.
    """
    from .recalibrate import (MAX_LOCK_ERROR_PPM, MIN_MASS_SPAN,
                              MIN_SLOPE_LOCK_MASSES, describe)

    if not corrections:
        return ""
    parts = [f'<h3>Mass recalibration</h3><p class="meta">'
             f"A lock mass is an internal standard carrying a formula and an "
             f"adduct \u2014 the written precursor is not accurate enough to "
             f"correct towards \u2014 whose measured ion held together across "
             f"the run and sat within {MAX_LOCK_ERROR_PPM:g} ppm of what that "
             f"formula weighs; a standard further out than that is a "
             f"different ion, however steadily it was measured, and is named "
             f"in the table above. Each injection gets the median of its lock masses\u2019 "
             f"errors, sign flipped; a linear term is fitted only where "
             f"{MIN_SLOPE_LOCK_MASSES} or more of them span "
             f"{MIN_MASS_SPAN:,.0f} Da and leave-one-out prediction of a "
             f"held-out lock mass says it helps. A direct infusion has no "
             f"second injection to be read against and is fitted instead "
             f"from its own precursor ladder, which the Source column names. "
             f"The correction moves the extraction "
             f"window, never the reader\u2019s arithmetic. "
             f"{_escape(describe(corrections))}. "
             + ("The results in this report were produced with it applied."
                if applied else
                "It is <b>not</b> applied: the results in this report are the "
                "masses as the instrument read them.")
             + "</p>"]
    rows = []
    for correction in corrections.values():
        rows.append([
            _escape(correction.sample_name), _escape(correction.source),
            f"{len(correction.lock_masses)}",
            _number(correction.offset_ppm if correction.usable else None, 1),
            _number(correction.slope_ppm_per_da * 1000
                    if correction.linear else None, 2),
            _number(correction.median_before, 1),
            _number(correction.median_after, 1),
            _number(correction.worst_after, 1),
            _escape(correction.verdict)])
    parts.append(_table(
        ["Injection", "Source", "Lock masses", "Offset ppm", "Slope ppm/kDa",
         "Median before", "Median after", "Worst after", "Verdict"],
        rows, right={2, 3, 4, 5, 6, 7}, empty="Nothing fitted.",
        widths=["15%", "13%", "7%", "8%", "9%", "10%", "9%", "9%", "20%"]))
    return "".join(parts)


def _infusions(title: str, summary, breaks: set[str] | None = None) -> str:
    """
    Every infused compound on one row, while the measurement stands.

    The summary that comes before the per-compound pages: what was measured
    of each vial and, in the cells that could not be filled, what was not
    there to measure. Printed narrower than the tab shows it, because
    A4 does not hold twenty columns and a table squeezed into it is a table
    nobody reads; `infusion_report.REPORT_COLUMNS` is the same row with the
    precursor, the adduct and the record written as one cell each.
    """
    from .infusion_report import (CONFIRMED_PPM, COUNTED_SCORE,
                                  REPORT_COLUMNS, SCORE_SHARE)

    parts = [_heading(title, breaks)]
    parts.append(
        f'<p class="meta">One row per infused sample, each averaged over its '
        f'whole run. The precursor is the method\u2019s own written value '
        f'measured back off the acquisition, counted as confirmed in the line '
        f'below at {CONFIRMED_PPM:g} ppm; the adduct is the ion that '
        f'written precursor is, with whether the survey scan of the same '
        f'acquisition confirmed it by exact mass and isotope pattern; the '
        f'ions found are of those a '
        f'formula or a structure predicted; the record is the best in the '
        f'library of your own, scored by the same cosine a library search '
        f'takes and counted below at {COUNTED_SCORE * 100:.0f}. The last '
        f'column scores each infusion against the others of the same compound '
        f'over the peaks above {SCORE_SHARE:.0%} of each base peak. A cell '
        f'that could not be filled says why rather than being blank, and '
        f'nothing here passes or fails a compound \u2014 see the per-compound '
        f'report for what a verdict is allowed to claim.</p>')
    parts.append(_table(
        list(REPORT_COLUMNS),
        [[_escape(cell) for cell in row.report_cells()]
         for row in summary.rows],
        right={3, 4, 9}, empty="No infusion is open.",
        widths=["8%", "12%", "8%", "4%", "7%", "12%", "9%", "5%", "12%",
                "4%", "11%", "8%"]))
    parts.append(f'<p class="foot">{_escape(summary.summary())}. '
                 f'Measured {summary.taken.strftime("%Y-%m-%d %H:%M")}.</p>')
    return "".join(parts)


def _infusion_comparison(title: str, comparison,
                         breaks: set[str] | None = None,
                         most: int = 60) -> str:
    """
    Today's infusions against a reference day's, while the comparison stands.

    The same shape as the batch comparison below it, on the other kind of
    batch: the totals, then every compound at every set of conditions, with
    the rows that moved first — since what a reader wants pointed at is the
    standard that no longer looks like itself.
    """
    from .infusion_compare import MOVED_PERCENT, SAME_PEAK_PPM, _ions_cell

    parts = [_heading(title, breaks)]
    parts.append(
        f'<p class="meta">{_escape(comparison.reference)} is the reference, '
        f"read from its project: the figures and the averaged, centroided "
        f"peak list its Infusions tab measured, with no raw file opened. "
        f"{_escape(comparison.current)} is what is open now. Rows are matched "
        f"by compound <em>and</em> by conditions — a spray at one "
        f"collision energy and activation is only ever compared with the "
        f"reference's at the same ones. The score is the cosine of this "
        f"day's peaks against the reference's, the same one a library search "
        f"takes; the reverse asks only whether the reference's peaks are "
        f"still there. A row is marked where the base peak is more than "
        f"{SAME_PEAK_PPM:g} ppm from the reference's — which is a "
        f"different ion and not a mass error — or where its height is "
        f"more than {MOVED_PERCENT:g}% from it.</p>")
    parts.append(f"<p>{_escape(comparison.summary())}</p>")
    ref, cur = comparison.totals()

    def figure(value, decimals=0):
        return _number(value, decimals) if value is not None else "—"

    parts.append(_table(
        ["", _escape(comparison.reference), _escape(comparison.current)],
        [["Infusions", f"{ref['infusions']}", f"{cur['infusions']}"],
         ["Compounds", f"{ref['compounds']}", f"{cur['compounds']}"],
         ["Precursors measured", f"{ref['measured']}", f"{cur['measured']}"],
         ["Median base-peak height", figure(ref["median_height"]),
          figure(cur["median_height"])],
         ["Median peaks stored", figure(ref["median_peaks"]),
          figure(cur["median_peaks"])],
         ["Median own-record score", figure(ref["median_record"]),
          figure(cur["median_record"])]],
        right={1, 2}, widths=["40%", "30%", "30%"]))
    if comparison.only_reference or comparison.only_current:
        parts.append(
            f"<p>{len(comparison.only_reference)} infusion(s) only in the "
            f"reference: "
            f"{_escape(', '.join(s.label for s in comparison.only_reference)) or '—'}. "
            f"{len(comparison.only_current)} only in this day: "
            f"{_escape(', '.join(s.label for s in comparison.only_current)) or '—'}.</p>")

    rows = sorted(comparison.rows, key=lambda r: (not r.moved, r.score))
    table = []
    for row in rows[:most]:
        name = _escape(row.compound)
        if row.moved:
            name = f'<span class="bad">{name}</span>'
        r, c = row.reference, row.current
        table.append([name, _escape(row.conditions),
                      f"{row.score * 100:.0f}", f"{row.reverse * 100:.0f}",
                      f"{row.matched}/{row.of_reference}",
                      figure(row.base_gap_ppm, 1),
                      figure(r.base_height), figure(c.base_height),
                      figure(row.intensity_change, 1),
                      f"{_ions_cell(r) or '—'} → "
                      f"{_ions_cell(c) or '—'}",
                      figure(row.precursor_ppm_change, 1)])
    if len(rows) > most:
        parts.append(f"<p>{most} rows of {len(rows)}: the marked ones first, "
                     f"then the lowest scores.</p>")
    parts.append(_table(
        ["Compound", "Conditions", "Score", "Rev.", "Matched",
         "Base Δ ppm", "Height (ref.)", "Height (now)", "Δ height %",
         "Ions found", "Δ precursor ppm"],
        table, right={2, 3, 4, 5, 6, 7, 8, 10},
        empty="No infusion is in both days at the same conditions.",
        widths=["13%", "12%", "6%", "6%", "8%", "9%", "10%", "10%", "9%",
                "9%", "8%"]))
    for row in comparison.moved:
        parts.append(f'<p class="foot">{_escape(row.label)}: '
                     f'{_escape(row.why)}.</p>')
    return "".join(parts)


#: how wide the compared-spectra picture is printed, in pixels of the ninety-
#: six dots to the inch that Qt's `width` attribute means. The body of an A4
#: page with these margins is 177 mm, which is 669 of them, so this fills the
#: measure with a little to spare. The image itself is rendered at twice the
#: size and scaled down here, which is what makes it print sharp.
IMAGE_WIDTH = 660


def _spectra(title: str, comparison, breaks: set[str] | None = None,
             most: int = 20, theme: str = "paper") -> str:
    """
    The spectra the Explorer was comparing, as a picture and as two tables.

    Printed only while the comparison stands — the Explorer keeps it in step
    with its own spectrum pane and drops it when the pins are cleared, so a
    report either shows what was on screen or does not mention it.

    The picture is drawn here rather than grabbed from the window, so it is
    the same whatever the window was; it is embedded as a data URI, which
    QTextDocument draws as readily as a file path (measured, both work) and
    which keeps an exported HTML report a single file that can be mailed.

    This is the one section that needs Qt's painting to build its HTML — no
    widget, but a QImage and a font. That costs nothing anywhere it can
    happen: a comparison only exists because the Explorer made one.
    """
    from . import spectra_compare

    height = int(round(IMAGE_WIDTH * spectra_compare.DEFAULT_HEIGHT
                       / spectra_compare.DEFAULT_WIDTH))
    parts = [_heading(title, breaks)]
    parts.append(
        f'<p class="meta">The spectra held together in the Explorer, drawn '
        f"again for print rather than copied off the screen. "
        f"{'Each is on its own base peak. ' if comparison.normalise else ''}"
        f"{'Every other one is drawn downwards, head to tail; the intensity beside it is a magnitude, not a negative number. ' if comparison.mirror else ''}"
        f"Peaks are labelled by the same picker the pane labels with, so the "
        f"masses here are the masses that were on screen; one with no room "
        f"to be printed clear of the traces is left out rather than drawn "
        f"over them.</p>")
    parts.append(
        f'<p><img src="'
        f'{spectra_compare.data_uri(comparison, palette=picture_palette(theme))}'
        f'" width="{IMAGE_WIDTH}" height="{height}" /></p>')
    # the picture carries its own title and legend, so there is no caption
    # under it: the same words twice, four lines apart, read as a mistake
    rows = []
    for trace in comparison.traces:
        base = trace.base_peak
        span = trace.mz_range
        peaks = comparison.peaks(trace, most=100_000, min_relative=0.01)
        rows.append([
            _escape(trace.label or "spectrum"),
            _number(base[0], 4) if base else "—",
            _number(base[1], 0) if base else "—",
            f"{len(peaks):,}",
            f"{span[0]:,.2f}–{span[1]:,.2f}" if span else "—"])
    parts.append(_table(
        ["Spectrum", "Base peak m/z", "Base peak", "Peaks", "m/z range"],
        rows, right={1, 2, 3, 4}, empty="Nothing to compare.",
        widths=["40%", "15%", "15%", "10%", "20%"]))
    parts.append('<p class="foot">A spectrum is named by the pane’s title '
                 "at the moment it was pinned — the sample, the channel "
                 "and the scan or the averaged range it came from. Peaks are "
                 "those at or above one per cent of the base peak.</p>")

    shared = spectra_compare.shared_peaks(comparison, most=most)
    parts.append("<h3>Peaks in common</h3>")
    parts.append(
        f'<p class="meta">A mass every one of these spectra holds, within '
        f"{spectra_compare.SHARED_PPM:g} ppm, with its height in each as a "
        f"per cent of that spectrum’s own base peak — the only way "
        f"two spectra of different sizes compare in a table. Shared by all of "
        f"them, not by some: a peak in one and not the other is a difference, "
        f"and the picture is where a difference is read.</p>")
    labels = [t.label or "spectrum" for t in comparison.traces]
    share = max(int(60 / max(len(labels), 1)), 8)
    parts.append(_table(
        ["m/z", "Spread ppm"] + [_escape(name) for name in labels],
        [[_number(peak.mz, 4), _number(peak.spread_ppm, 1)]
         + [f"{height:,.1f}" for height in peak.heights]
         for peak in shared],
        right=set(range(0, 2 + len(labels))),
        empty="No mass is in every one of these spectra.",
        widths=["20%", "20%"] + [f"{share}%"] * len(labels)))
    return "".join(parts)


def _batches(title: str, comparison, breaks: set[str] | None = None,
             most: int = 60) -> str:
    """
    A reference batch against this one, printed only when one was compared.

    The totals first, then the components in the order of how much their
    median area moved, since a schedule or a method edit that changed the
    level of a response is what a reader wants pointed at.
    """
    from .batches import MOVED_PERCENT

    parts = [_heading(title, breaks)]
    parts.append(
        f'<p class="meta">{_escape(comparison.reference)} is the reference, '
        f"read from its project; {_escape(comparison.current)} is this batch. "
        f"Components are matched by name. Points are the points on the peak "
        f"at or above one per cent of its height; %CV is over the rows meant "
        f"to agree \u2014 every spiked injection for an internal standard, the "
        f"quality controls for an analyte. A component whose median area "
        f"moved by more than {MOVED_PERCENT:g}% is marked.</p>")
    parts.append(f"<p>{_escape(comparison.summary())}</p>")
    ref, cur = comparison.totals()

    def figure(value, decimals=0):
        return _number(value, decimals) if value is not None else "\u2014"

    parts.append(_table(
        ["", _escape(comparison.reference), _escape(comparison.current)],
        [["Injections", f"{comparison.reference_injections}",
          f"{comparison.current_injections}"],
         ["Rows found", f"{ref['found']:,}", f"{cur['found']:,}"],
         ["Components with a peak", f"{ref['components_found']}",
          f"{cur['components_found']}"],
         ["Median points on the peak", figure(ref["median_points"]),
          figure(cur["median_points"])],
         ["Median %CV of the replicates", figure(ref["median_precision"], 1),
          figure(cur["median_precision"], 1)]],
        right={1, 2}, widths=["40%", "30%", "30%"]))
    if comparison.only_reference or comparison.only_current:
        parts.append(f"<p>{len(comparison.only_reference)} component(s) only "
                     f"in the reference: {_escape(', '.join(comparison.only_reference))}. "
                     f"{len(comparison.only_current)} only in this batch: "
                     f"{_escape(', '.join(comparison.only_current))}.</p>")

    rows = sorted(comparison.rows,
                  key=lambda r: -(abs(r.area_change) if r.area_change is not None else -1))
    table = []
    for row in rows[:most]:
        name = _escape(row.component + (" (IS)" if row.is_internal_standard else ""))
        if row.moved:
            name = f'<span class="bad">{name}</span>'
        r, c = row.reference, row.current
        table.append([name, f"{r.found}/{r.rows}", f"{c.found}/{c.rows}",
                      figure(r.median_points), figure(c.median_points),
                      figure(r.precision, 1), figure(c.precision, 1),
                      figure(row.area_change, 1), figure(row.rt_shift, 3)])
    if len(rows) > most:
        parts.append(f"<p>The {most} components that moved most, of {len(rows)}:</p>")
    parts.append(_table(
        ["Component", "Found (ref.)", "Found (now)", "Points (ref.)",
         "Points (now)", "%CV (ref.)", "%CV (now)", "\u0394 area %", "\u0394RT"],
        table, right={1, 2, 3, 4, 5, 6, 7, 8}, empty="Nothing to compare.",
        widths=["22%", "10%", "10%", "9%", "9%", "9%", "9%", "11%", "11%"]))
    return "".join(parts)


def _algorithms(title: str, comparison, method: ProcessingMethod,
                breaks: set[str] | None = None, most: int = 40) -> str:
    """
    How much the areas owe to the algorithm that integrated them.

    Printed only when a comparison was run. The totals first, then the
    components whose number moved most between algorithms, because a reader
    defending a result wants to know which ones to look at.
    """
    from .compare import SENSITIVE_PERCENT
    from .processing import ALGORITHM_LABELS

    parts = [_heading(title, breaks)]
    label = {a: ALGORITHM_LABELS.get(a, a) for a in comparison.algorithms}
    reference = label[comparison.reference]
    parts.append(
        f'<p class="meta">The batch was integrated once with each algorithm, '
        f'every run automatic and calibrated on its own results. The '
        f'reference is {_escape(reference.lower())}, which is what the '
        f'method names; the current integration is '
        f'{_escape(label.get(method.defaults.algorithm, method.defaults.algorithm).lower())}. '
        f'&#916; is the median over the rows both algorithms found of '
        f'|area &#8722; reference area| / reference area; a component '
        f'past {SENSITIVE_PERCENT:g}% is one whose number depends on the '
        f'decision as much as on the sample. %CV is the scatter over the '
        f'rows meant to agree &#8212; every spiked injection for an internal '
        f'standard, the quality controls for an analyte &#8212; and is the '
        f'figure that can call an algorithm better rather than different: '
        f'same files, same noise, only the arithmetic changed.</p>')

    rows = []
    for algorithm in comparison.algorithms:
        totals = comparison.totals(algorithm)
        precision = ("—" if totals.median_precision is None else
                     f"{totals.median_precision:,.1f} (n={totals.precise_components})")
        fell = f"{totals.fallbacks:,}"
        if totals.too_sparse:
            fell += f" ({totals.too_sparse:,} too few points)"
        rows.append([_escape(label[algorithm]), f"{totals.found:,}",
                     f"{totals.components_found}", fell,
                     "—" if algorithm == comparison.reference else f"{totals.sensitive}",
                     precision])
    parts.append(_table(
        ["Algorithm", "Rows found", "Components with a peak", "Fell back",
         f"Moved > {SENSITIVE_PERCENT:g}%", "Median %CV"],
        rows, right={1, 2, 3, 4, 5}))
    parts.append(
        '<p class="meta">A fit falls back to the valley area, and says so on '
        'the row, when the peak has fewer than three points above one per '
        'cent of its apex: two points and a width make a Gaussian, and a '
        'third at a fraction of a per cent is the peak\u2019s foot rather '
        'than its flank. That is the sampling\u2019s limit, not the '
        'algorithm\u2019s, and no algorithm gets past it.</p>')

    others = [a for a in comparison.algorithms if a != comparison.reference]
    sensitive = sorted(
        comparison.sensitive,
        key=lambda c: -max((d.median_percent or 0.0) for d in c.deltas.values()))
    if not sensitive:
        parts.append(f'<p class="empty">No component moved by more than '
                     f'{SENSITIVE_PERCENT:g}% between algorithms.</p>')
        return "".join(parts)
    headers = ["Component"] + [f"Δ median % — {label[a]}" for a in others] \
        + [f"Δ max % — {label[a]}" for a in others]
    table = []
    for item in sensitive[:most]:
        row = [_escape(item.component + (" (IS)" if item.is_internal_standard else ""))]
        row += [_number(item.deltas[a].median_percent, 1) for a in others]
        row += [_number(item.deltas[a].max_percent, 1) for a in others]
        table.append(row)
    parts.append(f"<p>{len(sensitive)} component(s) moved by more than "
                 f"{SENSITIVE_PERCENT:g}%"
                 + (f"; the {most} that moved most:" if len(sensitive) > most else ":")
                 + "</p>")
    parts.append(_table(headers, table, right=set(range(1, len(headers)))))
    return "".join(parts)


def _audit(title: str, trail, breaks: set[str] | None = None) -> str:
    """
    What was changed by hand, in the order it was changed.

    A report is read months later by somebody who does not have the project,
    and the one thing the numbers cannot say for themselves is which of them
    a person decided. This says so, and says plainly what it is not: there
    are no accounts and no signatures here, so the trail records what was
    done and not who did it or that nobody altered it afterwards.
    """
    rows = [[_escape(cell) for cell in row] for row in trail.rows()]
    return (_heading(title, breaks)
            + '<p class="meta">Every change made by hand in this project, in '
              "the order it was made: manual integrations, rows excluded, "
              "calibration standards dropped and restored, method and sample "
              "edits, reprocessings and saves. It is a record of what was "
              "done, not an electronic signature: there are no user accounts, "
              "no signing and nothing that would detect the project file "
              "being edited outside the application.</p>"
            + _table(list(AUDIT_COLUMNS), rows,
                     empty="Nothing was changed by hand.",
                     widths=["14%", "14%", "22%", "18%", "18%", "14%"]))


def _results(title: str, results: ResultsSet, method: ProcessingMethod,
             breaks: set[str] | None = None) -> str:
    """
    Every integrated row, by component.

    Twelve columns do not fit an A4 page at a size anybody reads, so the two
    that are almost always empty are not columns: a row that carries a flag,
    a note, an exclusion or a manual integration is marked and written out
    underneath its table. That puts the exceptions where they get noticed
    instead of in a column of blanks.
    """
    by_component: dict[str, list[PeakResult]] = {}
    for row in results:
        by_component.setdefault(row.component, []).append(row)

    if not by_component:
        return (_heading(title, breaks)
                + '<p class="empty">Nothing was integrated.</p>')

    order = [c.name for c in method.components if c.name in by_component]
    order += [name for name in sorted(by_component) if name not in order]

    parts = [_heading(title, breaks)]
    for name in order:
        rows, notes, marked = [], [], False
        for row in sorted(by_component[name], key=lambda r: r.sample_name):
            label = _escape(row.sample_name)
            if not row.used:
                label += f' <span class="mark">{EXCLUDED}</span>'
                marked = True
            elif row.manual:
                label += f' <span class="mark">{BY_HAND}</span>'
                marked = True
            drift = (row.rt - row.expected_rt
                     if row.rt is not None and row.expected_rt else None)
            status = _escape(row.status or "—")
            if str(row.status or "").strip().lower() == "fail":
                status = f'<span class="bad">{status}</span>'
            rows.append([
                label,
                _number(row.rt, 3), _number(drift, 3) if drift is not None else "—",
                _number(row.area, 1), _number(row.height, 1), _number(row.snr, 1),
                _number(row.area_ratio, 4) if row.area_ratio is not None else "—",
                _number(row.calculated_concentration, 4)
                if row.calculated_concentration is not None else "—",
                _number(row.accuracy, 2) if row.accuracy is not None else "—",
                status,
            ])
            said = "; ".join(row.flags) if row.flags else (row.note or "")
            if said:
                notes.append(f"{_escape(row.sample_name)} — {_escape(said)}")
        css = ' class="break"' if breaks and name in breaks else ""
        parts.append(f"<h3{css}>{_escape(name)}</h3>")
        parts.append(_table(
            ["Sample", "RT", "Δ RT", "Area", "Height", "S/N", "Ratio",
             "Concentration", "Accuracy %", "Status"],
            rows, right={1, 2, 3, 4, 5, 6, 7, 8},
            widths=["15%", "7%", "7%", "10%", "10%", "8%", "8%", "13%",
                    "11%", "11%"]))
        if marked:
            parts.append(f'<p class="foot">{EXCLUDED} excluded from the '
                         f"statistics&nbsp;&nbsp;&nbsp;{BY_HAND} integrated by "
                         f"hand</p>")
        for note in notes:
            parts.append(f'<p class="foot">{note}</p>')
    return "".join(parts)


def _statistics(title: str, results: ResultsSet, entries: list[SampleEntry],
                method: ProcessingMethod, grouping: str,
                breaks: set[str] | None = None) -> str:
    try:
        summary = summarise(results, entries, method, grouping, "response")
    except Exception as exc:                      # a report must still print
        return (_heading(title, breaks)
                + f'<p class="empty">Not computed: {_escape(exc)}</p>')
    rows = []
    for row in summary:
        rows.append([
            _escape(row.component), _escape(row.group),
            f"{row.used} of {row.total}",
            _number(row.mean, 4), _number(row.standard_deviation, 4),
            _number(row.percent_cv, 2), _number(row.accuracy, 2),
        ])
    return (_heading(title, breaks)
            + f'<p class="meta">Response, grouped by {_escape(grouping)}.</p>'
            + _table(["Component", "Group", "n", "Mean", "SD", "%CV", "Accuracy %"],
                     rows, right={2, 3, 4, 5, 6}, empty="Nothing to summarise.",
                     widths=["22%", "17%", "10%", "14%", "13%", "11%", "13%"]))


# --------------------------------------------------------------------------- #
# how it looks
# --------------------------------------------------------------------------- #
#: Everything here was rendered and looked at. Qt's rich text engine takes a
#: subset of CSS and drops the rest without a word, so `padding` on a cell,
#: `width` on a table and any selector cleverer than `tag.class` are absent
#: on purpose — the attributes in `_table` do that work instead.
_STYLE = """
@page { size: A4 portrait; margin: 15mm 15mm 15mm 18mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9pt; color: #16181c; }
p.eyebrow { color: #234b8c; font-size: 7.5pt; font-weight: 600;
            letter-spacing: 1px; margin: 0 0 2pt 0; }
h1 { font-size: 19pt; font-weight: 600; color: #16181c; margin: 0 0 7pt 0; }
h2 { font-size: 11.5pt; font-weight: 600; color: #234b8c;
     margin: 18pt 0 5pt 0; border-bottom: 2px solid #234b8c;
     padding-bottom: 2pt; }
h2.plain { border-bottom: 1px solid #c3c9d3; }
h3 { font-size: 9.5pt; font-weight: 600; margin: 12pt 0 3pt 0; color: #16181c; }
h2.break, h3.break { page-break-before: always; }
p { margin: 0 0 4pt 0; }
p.meta { color: #5b6472; font-size: 8pt; margin: 0 0 6pt 0; }
p.empty { color: #5b6472; font-style: italic; margin: 2pt 0 6pt 0; }
p.foot { color: #5b6472; font-size: 7.5pt; margin: 2pt 0 0 0; }
ul.findings { margin: 6pt 0 0 0; }
li { margin: 0 0 2pt 0; }
span.aside { color: #5b6472; font-style: italic; }
span.mark { color: #5b6472; }
span.bad { color: #a4262c; font-weight: 600; }
table { border-collapse: collapse; }
th { font-size: 8pt; text-align: left; background: #e8edf4; color: #234b8c;
     border-bottom: 1.5px solid #234b8c; font-weight: 600; }
th.num { text-align: right; }
td { font-size: 8pt; border-bottom: 1px solid #dfe3e9; vertical-align: top; }
td.num { text-align: right; }
td.label { color: #5b6472; background: #f2f4f7; }
tr.alt td { background: #f7f9fb; }
table.ident td { border-bottom: 1px solid #dfe3e9; }
table.contents td { border-bottom: 1px solid #eef1f5; }
"""

#: black and white, for a journal that prints in no other colour. Two things
#: change and they are the two things a greyscale press flattens: nothing is
#: tinted — the striped rows and the shaded heading cells become rules, since
#: a 4% tint reproduces as either nothing or a smudge — and every colour that
#: carried meaning becomes weight or a rule instead. A failure is bold, not
#: red; a heading is black over a black rule. Rendered and looked at, the
#: same as every rule in `_STYLE`: `background` appears nowhere below, and a
#: page of it rendered out of the PDF came back with **zero** pixels whose
#: red, green and blue differ at all — see
#: `tests/test_export_themes.py`, which measures exactly that, and note that
#: the running furniture had to be themed separately to get there.
_STYLE_MONO = """
@page { size: A4 portrait; margin: 15mm 15mm 15mm 18mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9pt; color: #000000; }
p.eyebrow { color: #000000; font-size: 7.5pt; font-weight: 600;
            letter-spacing: 1px; margin: 0 0 2pt 0; }
h1 { font-size: 19pt; font-weight: 600; color: #000000; margin: 0 0 7pt 0; }
h2 { font-size: 11.5pt; font-weight: 600; color: #000000;
     margin: 18pt 0 5pt 0; border-bottom: 2px solid #000000;
     padding-bottom: 2pt; }
h2.plain { border-bottom: 1px solid #767676; }
h3 { font-size: 9.5pt; font-weight: 600; margin: 12pt 0 3pt 0; color: #000000; }
h2.break, h3.break { page-break-before: always; }
p { margin: 0 0 4pt 0; }
p.meta { color: #3c3c3c; font-size: 8pt; margin: 0 0 6pt 0; }
p.empty { color: #3c3c3c; font-style: italic; margin: 2pt 0 6pt 0; }
p.foot { color: #3c3c3c; font-size: 7.5pt; margin: 2pt 0 0 0; }
ul.findings { margin: 6pt 0 0 0; }
li { margin: 0 0 2pt 0; }
span.aside { color: #3c3c3c; font-style: italic; }
span.mark { color: #3c3c3c; }
span.bad { color: #000000; font-weight: 700; }
table { border-collapse: collapse; }
th { font-size: 8pt; text-align: left; color: #000000;
     border-top: 1px solid #000000; border-bottom: 1.5px solid #000000;
     font-weight: 600; }
th.num { text-align: right; }
td { font-size: 8pt; border-bottom: 1px solid #b8b8b8; vertical-align: top; }
td.num { text-align: right; }
td.label { color: #3c3c3c; }
table.ident td { border-bottom: 1px solid #b8b8b8; }
table.contents td { border-bottom: 1px solid #d7d7d7; }
"""

#: for a screen: the application's own dark ground, and every colour on it
#: lightened to the cast the dark interface already uses. **For the HTML
#: export only.** A PDF is a thing somebody prints, and a dark page prints
#: as a sheet of toner with white letters knocked out of it, so
#: `print_document` refuses this theme rather than write one — see the
#: message it raises.
#:
#: Measured on #1e2124, since a dark page is where type goes thin and grey:
#: the body 13.2:1, the muted asides 6.4:1, the headings' accent 5.7:1, a
#: failure 5.2:1, a heading cell's ink on its own ground 7.4:1, and the
#: muted asides on the striped rows 6.0:1 — every one of them past the
#: 4.5:1 WCAG asks of text, with the failure red the closest to it.
_STYLE_DARK = """
@page { size: A4 portrait; margin: 15mm 15mm 15mm 18mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9pt; color: #e6e8eb; background: #1e2124; }
p.eyebrow { color: #6f9be0; font-size: 7.5pt; font-weight: 600;
            letter-spacing: 1px; margin: 0 0 2pt 0; }
h1 { font-size: 19pt; font-weight: 600; color: #e6e8eb; margin: 0 0 7pt 0; }
h2 { font-size: 11.5pt; font-weight: 600; color: #6f9be0;
     margin: 18pt 0 5pt 0; border-bottom: 2px solid #6f9be0;
     padding-bottom: 2pt; }
h2.plain { border-bottom: 1px solid #3c4148; }
h3 { font-size: 9.5pt; font-weight: 600; margin: 12pt 0 3pt 0; color: #e6e8eb; }
h2.break, h3.break { page-break-before: always; }
p { margin: 0 0 4pt 0; }
p.meta { color: #9ba3ae; font-size: 8pt; margin: 0 0 6pt 0; }
p.empty { color: #9ba3ae; font-style: italic; margin: 2pt 0 6pt 0; }
p.foot { color: #9ba3ae; font-size: 7.5pt; margin: 2pt 0 0 0; }
ul.findings { margin: 6pt 0 0 0; }
li { margin: 0 0 2pt 0; }
span.aside { color: #9ba3ae; font-style: italic; }
span.mark { color: #9ba3ae; }
span.bad { color: #e07070; font-weight: 600; }
table { border-collapse: collapse; }
th { font-size: 8pt; text-align: left; background: #22304a; color: #a8c4ee;
     border-bottom: 1.5px solid #6f9be0; font-weight: 600; }
th.num { text-align: right; }
td { font-size: 8pt; border-bottom: 1px solid #2c3035; vertical-align: top; }
td.num { text-align: right; }
td.label { color: #9ba3ae; background: #232629; }
tr.alt td { background: #232629; }
table.ident td { border-bottom: 1px solid #2c3035; }
table.contents td { border-bottom: 1px solid #2c3035; }
"""

#: the themes by the name a setting or a dialog holds, and what each is
#: called where a person reads it. `paper` is the default everywhere: no
#: saved project, no existing caller and no test moves because this exists.
THEMES = {"paper": _STYLE, "mono": _STYLE_MONO, "dark": _STYLE_DARK}
THEME_NAMES = {"paper": "Paper", "mono": "Black and white", "dark": "Dark"}
#: the themes a printed document may be written in. A dark PDF is not what a
#: printer wants and the export does not offer one.
PRINTABLE_THEMES = ("paper", "mono")

#: the running header and footer's two colours per theme — the hairline and
#: the type. The furniture is painted rather than laid out, so it is the one
#: part of the document the style sheet cannot reach; a black and white page
#: whose footer rule is still the blue-grey #c3c9d3 is not black and white,
#: which is what the printed-page test found by reading its pixels.
FURNITURE = {
    "paper": ("#c3c9d3", "#5b6472"),
    "mono": ("#767676", "#3c3c3c"),
    "dark": ("#3c4148", "#9ba3ae"),
}


def theme_named(theme) -> str:
    """The name of a theme, `paper` for anything this does not have."""
    name = str(theme or "").strip().lower()
    return name if name in THEMES else "paper"


def style_for(theme="paper") -> str:
    """The style sheet of one theme."""
    return THEMES[theme_named(theme)]


def picture_palette(theme):
    """The palette the pictures of a report in this theme are drawn in.

    The report and the figures inside it are one document: a black and
    white report holding a four-colour spectrum is not a black and white
    report.
    """
    from . import spectra_compare

    return spectra_compare.palette_named(theme_named(theme))


# --------------------------------------------------------------------------- #
def build_html(session, title: str = "Batch report",
               grouping: str = GROUP_BY_SAMPLE_TYPE,
               sections: tuple[str, ...] = ALL_SECTIONS,
               contents: dict[str, int] | None = None,
               breaks: set[str] | None = None,
               theme: str = "paper") -> str:
    """
    The whole report as one HTML document.

    Sections are named so a caller can leave out what it does not want — a
    hundred-component method makes a results section nobody prints — and are
    numbered here rather than in the section functions, so that leaving one
    out closes the gap instead of leaving one.

    `theme` names the style sheet and, with it, the palette every picture in
    the document is drawn in — `paper`, `mono` for a journal that prints in
    black and white, `dark` for reading on a screen. It changes how the
    document looks and never what it says.

    `contents` is how the printed version puts page numbers in its table of
    contents: `None` for no page column at all, an empty mapping to reserve
    the column while the numbers are still unknown, and the mapping itself on
    the second pass. `breaks` names the headings that are to start a fresh
    page. Both are worked out by `write_pdf`, which has to lay the document
    out before it can know either.
    """
    entries = list(session.entries)
    method = session.method
    # a comparison is only there when one was run; a section saying so on
    # every report would be a page of nothing
    comparison = getattr(session, "comparison", None)
    drift = getattr(session, "mass_drift", None)
    batches = getattr(session, "batch_comparison", None)
    # likewise the infusion summary: measured on request in the Infusions
    # tab, and printed only while that measurement stands
    infusions = getattr(session, "infusion_summary", None)
    if infusions is not None and not len(infusions.rows):
        infusions = None
    # and the comparison of those infusions against a reference day's,
    # which stands only while somebody has run one
    against = getattr(session, "infusion_comparison", None)
    if against is not None and not (against.rows or against.only_reference
                                    or against.only_current):
        against = None
    # printed while there is a history to print: a section saying nothing was
    # changed by hand would be on every report of a batch nobody touched
    trail = getattr(session, "audit", None)
    # a comparison of spectra stands only while there is more than one of
    # them: the Explorer drops it when the pins are cleared
    spectra = getattr(session, "spectra_comparison", None)
    if spectra is not None and not spectra.stands:
        spectra = None
    order = [key for key in ALL_SECTIONS if key in sections
             and (key != "algorithms" or comparison is not None)
             and (key != "mass" or drift is not None)
             and (key != "infusions" or infusions is not None)
             and (key != "infusion-comparison" or against is not None)
             and (key != "spectra" or spectra is not None)
             and (key != "batches" or batches is not None)
             and (key != "audit" or (trail is not None and len(trail)))]
    titles = {key: f"{number}. {SECTIONS[key]}"
              for number, key in enumerate(order, start=1)}

    parts = ["<!DOCTYPE html>",
             "<html><head><meta charset='utf-8'>",
             f"<title>{_escape(title)}</title>",
             f"<style>{style_for(theme)}</style></head><body>",
             _title_block(title, session.project_path, entries, method),
             _contents(list(titles.values()), contents)]
    for key in order:
        name = titles[key]
        if key == "summary":
            parts.append(_summary(name, session.results, entries, method,
                                  session.calibrations, breaks))
        elif key == "samples":
            parts.append(_samples(name, entries, breaks))
        elif key == "method":
            parts.append(_method(name, method, breaks, entries))
        elif key == "calibration":
            parts.append(_calibrations(name, session.calibrations, method, breaks))
        elif key == "limits":
            parts.append(_limits(name, session.calibrations, method, breaks))
        elif key == "carryover":
            parts.append(_carryover(name, session.results, entries, method,
                                    breaks))
        elif key == "quality":
            parts.append(_quality(name, session.results, entries, method,
                                  breaks))
        elif key == "sampling":
            parts.append(_sampling(name, session.results, entries, method,
                                   breaks))
        elif key == "mass":
            parts.append(_mass(name, drift, breaks,
                                getattr(session, "mass_corrections", None),
                                bool(getattr(session, "recalibrate", False))))
        elif key == "infusions":
            parts.append(_infusions(name, infusions, breaks))
        elif key == "infusion-comparison":
            parts.append(_infusion_comparison(name, against, breaks))
        elif key == "spectra":
            parts.append(_spectra(name, spectra, breaks, theme=theme))
        elif key == "algorithms":
            parts.append(_algorithms(name, comparison, method, breaks))
        elif key == "batches":
            parts.append(_batches(name, batches, breaks))
        elif key == "audit":
            parts.append(_audit(name, trail, breaks))
        elif key == "results":
            parts.append(_results(name, session.results, method, breaks))
        elif key == "statistics":
            parts.append(_statistics(name, session.results, entries, method,
                                     grouping, breaks))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(session, path: str | os.PathLike, **kwargs) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(session, **kwargs))
    return path


# --------------------------------------------------------------------------- #
# the workbook
# --------------------------------------------------------------------------- #
#: the sheets, in the order they are put in the book, with the tab names
#: they carry. A section with nothing in it is left out entirely rather
#: than written as an empty tab.
WORKBOOK_SHEETS = {
    "results": "Results",
    "calibration": "Calibration",
    "statistics": "Statistics",
    "quality": "Batch QC",
    "method": "Method",
    "samples": "Samples",
}
ALL_WORKBOOK_SHEETS = tuple(WORKBOOK_SHEETS)


def _yes(value) -> str:
    """A column of yes and blank, not of yes and no: the exception shows."""
    return "yes" if value else ""


def _slope_intercept(curve) -> tuple[float | None, float | None]:
    """
    The two numbers somebody wants out of a curve, where it has them.

    A quadratic has neither, and inventing them from its first two
    coefficients would be a straight line the curve is not. The equation
    column carries it instead.
    """
    coefficients = list(curve.coefficients or [])
    if len(coefficients) == 2:
        return coefficients[0], coefficients[1]
    if len(coefficients) == 1:
        return coefficients[0], 0.0
    return None, None


def _sheet_results(session) -> Sheet | None:
    """
    Every integrated row, one per line — which is the point of the sheet.

    The report's own results section is grouped by component with the
    exceptions written underneath, because twelve columns do not fit an A4
    page. A spreadsheet has no page, so nothing here is moved into a
    footnote: the flags, the note and the exclusion are columns like any
    other, and the rows can be sorted and filtered on them.
    """
    rows = []
    by_key = {entry.key: entry for entry in session.entries}
    for result in session.results:
        entry = by_key.get(result.sample_key)
        component = session.method.by_name(result.component)
        rows.append([
            result.sample_name,
            entry.sample_type if entry else "",
            entry.sample_group if entry else "",
            result.component,
            result.group or (component.group if component else ""),
            result.channel,
            result.mz or None,
            result.rt if result.found else None,
            result.expected_rt,
            result.rt_delta,
            result.area if result.found else None,
            result.height or None,
            result.width or None,
            result.snr,
            result.points,
            result.algorithm,
            result.internal_standard,
            result.area_ratio,
            result.calculated_concentration,
            result.accuracy,
            result.status,
            _yes(result.used),
            _yes(result.manual),
            "; ".join(result.flags),
            result.note,
        ])
    if not rows:
        return None
    return Sheet(
        WORKBOOK_SHEETS["results"],
        ["Sample", "Sample type", "Sample group", "Component",
         "Component group", "Channel", "m/z", "RT", "Expected RT", "Δ RT",
         "Area", "Height", "Width", "S/N", "Points", "Algorithm",
         "Internal standard", "Ratio to IS", "Concentration", "Accuracy %",
         "Status", "Used", "By hand", "Flags", "Note"],
        rows,
        widths=[22, 14, 14, 24, 18, 20, 11, 9, 11, 8, 13, 13, 9, 10, 8, 11,
                22, 12, 14, 11, 9, 7, 8, 30, 30],
        formats=[None, None, None, None, None, None, "mass", "time", "time",
                 "time", "area", "area", "time", "area", "integer", None,
                 None, None, None, "percent", None, None, None, None, None])


def _sheet_calibration(session) -> Sheet | None:
    internal = {c.name for c in session.method.components
                if c.is_internal_standard}
    rows = []
    for name in sorted(session.calibrations):
        curve = session.calibrations[name]
        if curve is None or not curve.is_fitted:
            continue
        slope, intercept = _slope_intercept(curve)
        rows.append([
            name, _yes(name in internal), curve.regression, curve.weighting,
            curve.equation, slope, intercept, curve.r2, curve.r,
            len(curve.used_points), len(curve.points), curve.note,
        ])
    if not rows:
        return None
    return Sheet(
        WORKBOOK_SHEETS["calibration"],
        ["Component", "Internal standard", "Model", "Weighting", "Equation",
         "Slope", "Intercept", "r²", "r", "Points used", "Points", "Note"],
        rows,
        widths=[24, 16, 12, 11, 30, 14, 14, 10, 10, 11, 8, 26])


def _sheet_statistics(session, grouping: str) -> Sheet | None:
    try:
        summary = summarise(session.results, session.entries, session.method,
                            grouping, "response")
    except Exception:                       # a workbook must still be written
        return None
    rows = [[row.component, row.group, row.used, row.total, row.mean,
             row.standard_deviation, row.percent_cv, row.accuracy]
            for row in summary]
    if not rows:
        return None
    return Sheet(
        WORKBOOK_SHEETS["statistics"],
        ["Component", "Group", "n used", "n", "Mean", "SD", "%CV",
         "Accuracy %"],
        rows,
        widths=[26, 20, 9, 7, 16, 16, 10, 12],
        formats=[None, None, "integer", "integer", None, None, "percent",
                 "percent"])


def _sheet_quality(session) -> Sheet | None:
    """
    One row per control chart, plus the response index where it stands.

    The index is a chart of its own in `qc`, and it goes in the same sheet
    under the component name it already carries, so that a reader sorting
    by the drift column sees it against the standards it was built from.
    """
    try:
        quality = batch_qc(session.results, session.entries, session.method)
    except Exception:                       # a workbook must still be written
        return None
    charts = list(quality.charts)
    if quality.index is not None and quality.index.measurable:
        charts.append(quality.index)
    rows = []
    for chart in charts:
        rows.append([
            chart.component, len(chart.injections), chart.centre, chart.sigma,
            chart.snr, chart.floor, chart.drift, chart.correlation,
            len(chart.out), len(chart.warned),
            _yes(chart.drifted), _yes(chart.unusable),
            _yes(chart.measurable and chart.quantifiable),
            chart.note,
        ])
    if not rows:
        return None
    return Sheet(
        WORKBOOK_SHEETS["quality"],
        ["Component", "n", "Centre", "Spread", "S/N", "Floor", "Drift %",
         "ρ", "Outside limits", "Beyond 2σ", "Drifted", "Cannot normalise",
         "Quantifiable", "Note"],
        rows,
        widths=[26, 7, 15, 15, 10, 14, 10, 9, 14, 11, 10, 16, 13, 34],
        formats=[None, "integer", "area", "area", "area", "area", "percent",
                 None, "integer", "integer", None, None, None, None])


def _sheet_method(session) -> Sheet | None:
    rows = []
    for component in session.method.components:
        role = ("internal standard" if component.is_internal_standard else
                (f"qualifier of {component.qualifier_of}"
                 if component.qualifier_of else ""))
        rows.append([
            component.name, component.group, component.precursor or None,
            component.fragment, component.rt, component.rt_halfwidth,
            component.tolerance, component.unit, component.formula,
            component.adduct, _yes(component.is_internal_standard),
            component.internal_standard, role, component.response,
            component.concentration_unit, component.min_response,
            component.regression, component.weighting, component.lm_id,
        ])
    if not rows:
        return None
    return Sheet(
        WORKBOOK_SHEETS["method"],
        ["Component", "Group", "Precursor", "Fragment", "RT", "± RT",
         "Tolerance", "Unit", "Formula", "Adduct", "IS", "Internal standard",
         "Role", "Response", "Concentration unit", "Min. response",
         "Regression", "Weighting", "LIPID MAPS"],
        rows,
        widths=[26, 18, 12, 12, 9, 8, 10, 7, 16, 12, 6, 22, 20, 14, 18, 14,
                12, 11, 14],
        formats=[None, None, "mass", "mass", "time", "time", None, None,
                 None, None, None, None, None, None, None, "area", None,
                 None, None])


def _sheet_samples(session) -> Sheet | None:
    rows = []
    for entry in session.entries:
        rows.append([
            entry.name, entry.filename, entry.sample_index, entry.sample_type,
            entry.sample_group, entry.actual_concentration,
            entry.dilution_factor, entry.comment, entry.problem,
        ])
    if not rows:
        return None
    return Sheet(
        WORKBOOK_SHEETS["samples"],
        ["Sample", "File", "Index", "Type", "Group", "Concentration",
         "Dilution", "Comment", "Problem"],
        rows,
        widths=[24, 30, 7, 16, 16, 14, 10, 30, 30],
        formats=[None, None, "integer", None, None, None, None, None, None])


def build_workbook(session, grouping: str = GROUP_BY_SAMPLE_TYPE,
                   sheets: tuple[str, ...] = ALL_WORKBOOK_SHEETS) -> list[Sheet]:
    """
    The batch as sheets of typed cells: one sheet per section.

    This is not the report in another wrapper. A report is read; a workbook
    is worked on, so nothing is rounded into a string, nothing is moved into
    a footnote, and no exception is summarised away — every result is a row
    with its flags and its note beside it. The two share their arithmetic
    (`summarise`, `batch_qc`) rather than their formatting, because a number
    turned into text for an A4 page is no longer a number.

    Sections with nothing in them are left out, so a book of a method and
    nothing else is two sheets rather than six, four of them empty.
    """
    builders = {
        "results": lambda: _sheet_results(session),
        "calibration": lambda: _sheet_calibration(session),
        "statistics": lambda: _sheet_statistics(session, grouping),
        "quality": lambda: _sheet_quality(session),
        "method": lambda: _sheet_method(session),
        "samples": lambda: _sheet_samples(session),
    }
    built = []
    for key in ALL_WORKBOOK_SHEETS:
        if key not in sheets:
            continue
        sheet = builders[key]()
        if sheet is not None and not sheet.is_empty:
            built.append(sheet)
    return built


def export_workbook(session, path: str | os.PathLike, **kwargs) -> str:
    """
    Write the batch out as an `.xlsx`, and return the path written.

    A session with nothing in it raises rather than writing a workbook of
    no sheets, which is a file no spreadsheet will open.
    """
    sheets = build_workbook(session, **kwargs)
    if not sheets:
        raise ValueError("there is nothing to export: no method, no samples "
                         "and no results")
    return write_xlsx(str(path), sheets)


# --------------------------------------------------------------------------- #
# printing
# --------------------------------------------------------------------------- #
def _section_pages(document, page_height: float) -> dict[str, int]:
    """
    Which page each heading landed on, once the document has been laid out.

    Qt records the heading level of a block, so the sections can be found
    without matching their text against anything.
    """
    layout = document.documentLayout()
    pages: dict[str, int] = {}
    block = document.begin()
    while block.isValid():
        if block.blockFormat().headingLevel() == 2:
            top = layout.blockBoundingRect(block).top()
            pages.setdefault(block.text().strip(), int(top // page_height) + 1)
        block = block.next()
    return pages


def _orphan_headings(document, page_height: float) -> set[str]:
    """
    Headings left stranded at the foot of a page, their content overleaf.

    Qt has no `keep-with-next`, so the only way to hold a heading to what it
    introduces is to lay the document out, see which headings were separated
    from it, and lay it out again with those pushed to the next page. A
    heading is stranded when the block that follows it starts on a later
    page — which is precisely the test, and says nothing about how much space
    was left underneath.

    There is a second way to be stranded and it took a rendered page to find.
    A picture is one inline object in one block, and Qt will not split it: a
    block holding one that runs past the foot of the page is laid out as
    though it fitted — `blockBoundingRect` puts its top on this page — and is
    then drawn on the next, leaving the heading alone above a third of a page
    of nothing. So a following block that *straddles* a boundary counts as
    stranded too, but only when it carries an object (`OBJECT_CHARACTER`):
    text and tables split across a page perfectly well, and pushing a heading
    over for those would break a document that was right.
    """
    from PyQt6 import QtGui

    before = QtGui.QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore
    layout = document.documentLayout()
    stranded: set[str] = set()
    block = document.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        following = block.next()
        if level in (2, 3) and following.isValid() and block.text().strip():
            here = int(layout.blockBoundingRect(block).top() // page_height)
            next_rect = layout.blockBoundingRect(following)
            there = int(next_rect.top() // page_height)
            # a block already pushed to a fresh page by its own break
            # reports a bounding rect that starts where it would have been
            # without one, so the page test alone misses a heading whose
            # very next block is such a heading
            pushed = bool(following.blockFormat().pageBreakPolicy() & before) \
                and not bool(block.blockFormat().pageBreakPolicy() & before)
            split = (OBJECT_CHARACTER in following.text()
                     and int(next_rect.bottom() // page_height) > there)
            if there > here or pushed or split:
                stranded.add(block.text().strip())
        block = block.next()
    return stranded


def _furniture(painter, writer, page: int, total: int, title: str,
               header: float, footer: float, body,
               strings: dict[str, str] | None = None,
               theme: str = "paper") -> None:
    """
    The running header and footer: what this is, and where the reader is in it.

    Page one carries the title block, so the running header starts on page two;
    the footer is on every page, because a page that comes loose from the
    others has to say what it belongs to.

    `strings` carries the two words the footer writes, for a document that is
    not in English — the manual is printed in whichever language it is being
    read in. Without it the footer is English, which is what a report is.
    """
    from PyQt6 import QtCore, QtGui

    hairline, ink = FURNITURE[theme_named(theme)]
    rule = QtGui.QColor(hairline)
    muted = QtGui.QColor(ink)
    font = QtGui.QFont()
    font.setFamilies(["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"])
    font.setPointSizeF(7.0)
    painter.save()
    painter.setFont(font)
    painter.setPen(muted)

    width = body.width()
    if page > 1:
        band = QtCore.QRectF(0, 0, width, header * 0.62)
        painter.drawText(band, int(QtCore.Qt.AlignmentFlag.AlignLeft
                                   | QtCore.Qt.AlignmentFlag.AlignVCenter), title)
        painter.setPen(QtGui.QPen(rule, writer.resolution() / 1200.0))
        painter.drawLine(QtCore.QPointF(0, header * 0.72),
                         QtCore.QPointF(width, header * 0.72))
        painter.setPen(muted)

    top = header + body.height()
    painter.setPen(QtGui.QPen(rule, writer.resolution() / 1200.0))
    painter.drawLine(QtCore.QPointF(0, top + footer * 0.28),
                     QtCore.QPointF(width, top + footer * 0.28))
    painter.setPen(muted)
    band = QtCore.QRectF(0, top + footer * 0.34, width, footer * 0.66)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    words = strings or {}
    generated = words.get("generated", "generated")
    numbering = words.get("page_of", "Page {page} of {total}")
    painter.drawText(band, int(QtCore.Qt.AlignmentFlag.AlignLeft
                               | QtCore.Qt.AlignmentFlag.AlignTop),
                     f"MIL-Q {__version__} · {generated} {stamp}")
    painter.drawText(band, int(QtCore.Qt.AlignmentFlag.AlignRight
                               | QtCore.Qt.AlignmentFlag.AlignTop),
                     numbering.format(page=page, total=total))
    painter.restore()


def print_document(build, path: str | os.PathLike, title: str,
                   reflows: int = MAX_REFLOWS,
                   strings: dict[str, str] | None = None,
                   theme: str = "paper") -> str:
    """
    Lay an HTML document out on A4 portrait pages and write it as a PDF.

    `build(contents, breaks)` returns the HTML: `contents` is `None` for no
    page column in the table of contents, `{}` to reserve one, and the
    mapping of heading to page on the final pass; `breaks` names the
    headings to start on a fresh page. The report and the manual are both
    printed through here, so the two things below that were bugs are fixed
    in one place. `reflows` is how many times a stranded heading may be
    chased: three is enough for a report, and a forty-page manual with a
    heading every few paragraphs needs more. `strings` translates the
    running footer for a document that is not in English.

    The layout is given the writer as its paint device: without one it
    measures type at the screen's ninety-six dots to the inch while the page
    is sized in the writer's twelve hundred, so every point size comes out
    at a twelfth of itself and the whole document collapses into a corner
    of page one. And it is laid out more than once, because a heading
    stranded at the foot of a page has to be pushed over, and the table of
    contents cannot know a page number until the pages exist.

    `theme` reaches two things. The document's own style is already in the
    HTML the caller's `build` returns; the running header and footer are
    painted here, outside it, so they are given the theme's own two colours
    — a black and white page whose footer rule is still a blue-grey
    hairline is not black and white, which the printed-page test found by
    reading its pixels. And a dark document is refused before it is
    written: a PDF is a thing somebody prints, and a printer handed a dark
    page lays down a whole sheet of toner with the letters knocked out of
    it. The HTML export is where a dark report belongs.
    """
    from PyQt6 import QtCore, QtGui

    if theme_named(theme) not in PRINTABLE_THEMES:
        raise ValueError(
            "a dark theme is for reading on a screen, not for printing: "
            "export the report as a web page for that, or print it in "
            + " or ".join(THEME_NAMES[name] for name in PRINTABLE_THEMES))
    path = str(path)
    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QtGui.QPageLayout.Orientation.Portrait)
    left, top, right, bottom = MARGINS_MM
    writer.setPageMargins(QtCore.QMarginsF(left, top, right, bottom),
                          QtGui.QPageLayout.Unit.Millimeter)
    writer.setTitle(title)
    writer.setCreator(f"MIL-Q {__version__}")

    def millimetres(value: float) -> float:
        return value / 25.4 * writer.resolution()

    header, footer = millimetres(HEADER_MM), millimetres(FOOTER_MM)
    body = QtCore.QSizeF(writer.width(), writer.height() - header - footer)

    def lay_out(contents, breaks=None):
        document = QtGui.QTextDocument()
        document.documentLayout().setPaintDevice(writer)
        document.setHtml(build(contents, breaks))
        document.setPageSize(body)
        return document

    breaks: set[str] = set()
    document = lay_out({})
    for _ in range(reflows):                      # a break can strand another
        stranded = _orphan_headings(document, body.height()) - breaks
        if not stranded:
            break
        breaks |= stranded
        document = lay_out({}, breaks)
    document = lay_out(_section_pages(document, body.height()), breaks)

    painter = QtGui.QPainter(writer)
    try:
        total = document.pageCount()
        for index in range(total):
            if index:
                writer.newPage()
            painter.save()
            painter.translate(0.0, header - index * body.height())
            document.drawContents(painter, QtCore.QRectF(
                0.0, index * body.height(), body.width(), body.height()))
            painter.restore()
            _furniture(painter, writer, index + 1, total, title, header, footer,
                       body, strings, theme)
    finally:
        painter.end()
    return path


def write_pdf(session, path: str | os.PathLike, **kwargs) -> str:
    """
    The report on A4 portrait pages, with page numbers — see `print_document`
    for what the printing has to get right.

    Qt is imported there rather than here so that building the HTML — which
    is what most of the tests exercise — needs no GUI toolkit at all.
    """
    title = kwargs.get("title", "Batch report")
    theme = kwargs.get("theme", "paper")
    return print_document(
        lambda contents, breaks: build_html(session, contents=contents,
                                            breaks=breaks, **kwargs),
        path, title, theme=theme)
