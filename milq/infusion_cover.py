"""
The cover that goes in front of a folder of infusions.

`infusion_batch.run` reads nine acquisitions and prints nine sections, each
of which answers *is this vial what the label says it is?* for one vial. Read
back a week later, that document opens on page one of compound one: to find
out what the folder as a whole did you page through it and add the sections
up yourself, which is the arithmetic this file does instead.

It is the chromatographic batch report's front matter, done for infusions —
`report._title_block` names the project and counts the samples, `_findings`
says what a reader should not have to hunt for, and `_contents` says where
everything is. The four blocks here are the same four:

1. **What this is.** The folder, the day, the version of the program, and
   the counts. A document is read detached from whatever made it.
2. **The infusions**, one row each, in `infusion_report.REPORT_COLUMNS` —
   the same row the tab shows and the batch report's *Infusions* section
   prints, so the three cannot disagree — with the compound's acquisitions
   kept together.
3. **What they add up to**, in sentences. Each one sums a column of that
   table and says what it counted against; there is no overall verdict for
   the same reason a per-compound report has none. See `verdict_sentences`.
4. **What was left out**, and **the pages that follow** with their page
   numbers, through `report.print_document`'s own contents machinery: the
   numbers do not exist until the document has been laid out, so the build
   function is called again with them.

The whole thing is one PDF — cover then sections — because a cover in a file
of its own is a file that gets separated from what it covers. `--per-compound`
is the exception and it is asked for explicitly: there the cover is written
on its own, since the pages it introduces are in eight other files.

Nothing here reads a raw file. It is given the `BatchResult` and the
`InfusionSummary` the run already made, and every field it reads off a row it
reads with `getattr`: the row is `infusion_report`'s and grows columns.
"""

from __future__ import annotations

import datetime as _dt
import os

from .infusion_report import (CONFIRMED_PPM, COUNTED_SCORE, REFLOWS,
                              REPORT_COLUMNS, SCORE_SHARE, build_section)
from .report import _STYLE, _escape, _heading, _table, print_document

#: how far apart two written precursors have to be before they are two ions
#: rather than one typed to fewer places. Cholic acid-d4 is `430.34` in one
#: file of the real folder and `430.35` in another — the same ammonium adduct
#: written twice — while two more files of the same compound write `839.56`,
#: which is not that ion at all. Half a dalton is what `components`
#: (`WHOLE_DALTON`) already uses to separate a typed decimal from a different
#: compound, and the smallest real gap here is four hundred daltons.
SAME_PRECURSOR_DA = 0.5

#: at most this many measured-but-outside errors are given one by one before
#: the sentence gives their range instead. Three fit in a clause; eight are a
#: column of the table above, printed twice.
ERRORS_LISTED = 3

#: the widths the *Infusions* table is printed at. The same twelve columns as
#: the tab and as the batch report's *Infusions* section — `REPORT_COLUMNS`,
#: one definition, so a column added there appears here — but not the same
#: widths: the section's are set for a table read after thirty-nine others,
#: and this one is the first thing on the document.
#:
#: Two rules, both from rendering the nine real infusions and looking at the
#: page. **No heading wraps inside a word.** At the section's widths
#: `Compound`, `Scans` and `Score` came out as `Compoun/d`, `Scan/s` and
#: `Scor/e`, which is `report._table`'s own complaint about a heading; ten,
#: six and six per cent hold them. **No measurement is split.** *Base peak
#: m/z* at seven per cent broke `839.2316` across two lines as `839.23` and
#: `16`, which is worse than any amount of wrapped prose; nine holds it, and
#: `Base peak m/z` then wraps at its space with the `m/z` intact.
#:
#: What pays for those is the four columns that hold a reason rather than a
#: number — *Sample*, *Ions found*, *Library record*, *Other infusions* —
#: which wrap either way and are cut at `CELL_CHARACTERS` first.
COLUMN_WIDTHS = ["10%", "10%", "7%", "6%", "9%", "11%", "8%", "7%", "10%",
                 "6%", "8%", "8%"]
#: which of those columns are numbers — `report._infusions`'s own set, since
#: they are its columns
RIGHT_COLUMNS = {3, 4, 9}

#: how much of a cell the cover prints before cutting it at a word.
#: A cell here says why it is empty, and most of those reasons are three
#: words; a few are a whole sentence, and one of the real folder's is 214
#: characters — `CA-d4 is written [M+NH4]+, and 839.56 is none of the adducts
#: of C24H36D4O5 …` — which in a column seven per cent of the page wide is
#: thirty lines of six characters and makes the row most of a page. Rendered
#: and looked at, which is the only way this was ever going to be found: at
#: eighty characters four rows filled a page of the nine, and at forty-eight
#: the whole table is a page and a half. The sentence is not lost: it is
#: written out in full on that compound's own page, which is what the
#: contents list points at.
CELL_CHARACTERS = 48


# --------------------------------------------------------------------------- #
# what the folder is called
# --------------------------------------------------------------------------- #
def folder_of(result) -> str:
    """
    The folder this run was of, as a path.

    A run is given files, folders, or both, so there is not always one
    folder: what there always is, is the deepest directory that holds
    everything named. `commonpath` refuses a mixture of absolute and
    relative paths and paths on two Windows drives, and a report is not
    worth failing over its own title, so it falls back to the first.
    """
    # what was read, before what was asked for: those are always files, and
    # their folder is the folder whether or not it is still on this machine.
    # A folder named on the command line is a directory only while the disk
    # is mounted, and a report read back off another one should still know
    # what it was of.
    paths = [str(p) for p in getattr(result, "read", ()) if p]
    paths = paths or [str(p) for p in getattr(result, "requested", ()) if p]
    if not paths:
        return ""
    # dirname as written, so a folder read off another machine keeps its
    # own spelling; abspath only for a bare file name, since on Windows it
    # would put this machine's drive in front of a path that had none
    folders = [p if os.path.isdir(p)
               else (os.path.dirname(p) or os.path.dirname(os.path.abspath(p)))
               for p in paths]
    if len(set(folders)) == 1:
        return folders[0]
    try:
        return os.path.commonpath(folders)
    except ValueError:
        return folders[0]


def title_for(result) -> str:
    """The document's title: the folder's own name, where it has one."""
    folder = folder_of(result).rstrip(os.sep)
    name = os.path.basename(folder)
    return name or folder or "Direct infusion report"


# --------------------------------------------------------------------------- #
# the arithmetic the sentences are made of
# --------------------------------------------------------------------------- #
def _report(row):
    return getattr(row, "report", None)


def _written(row) -> float | None:
    report = _report(row)
    written = getattr(report, "written_precursor", None)
    try:
        return float(written) if written else None
    except (TypeError, ValueError):
        return None


def _confirmed(row) -> bool:
    return bool(getattr(row, "confirmed", False))


def _error_ppm(row) -> float | None:
    report = _report(row)
    error = getattr(report, "error_ppm", None)
    if not callable(error):
        return None
    try:
        value = error()
    except Exception:                                # a row that cannot say
        return None
    return None if value is None else float(value)


def _clusters(masses: list[float]) -> list[list[float]]:
    """The masses cut into groups wherever the gap says another ion."""
    groups: list[list[float]] = []
    for mass in sorted(masses):
        if groups and mass - groups[-1][-1] <= SAME_PRECURSOR_DA:
            groups[-1].append(mass)
        else:
            groups.append([mass])
    return groups


def isolated_precursors(rows) -> dict[str, float]:
    """
    The rows whose method targets a mass the compound's other runs do not.

    Keyed by sample name, which is what identifies an acquisition everywhere
    else in this program. A compound infused five times whose two `…TESTEARTIGO`
    files isolate 839.56 while the other three isolate 430.34 and 430.35 is
    not five measurements of one ion with two failures: it is three of one ion
    and two of another, and the sentence says so with the mass rather than
    calling them all "not measured". Nothing is decided on this — it changes
    the words a count is reported under and not the count.

    The test is within the compound and not across the folder: two compounds
    are expected to isolate different masses. A cluster qualifies when it
    holds no confirmed row and another cluster of the same compound does, so
    a compound that simply never confirmed says nothing here.
    """
    by_compound: dict[str, list] = {}
    for row in rows:
        by_compound.setdefault(str(getattr(row, "compound", "")), []).append(row)
    isolated: dict[str, float] = {}
    for members in by_compound.values():
        masses = {m for m in (_written(row) for row in members) if m}
        if len(masses) < 2:
            continue
        groups = _clusters(list(masses))
        if len(groups) < 2:
            continue
        confirmed = {min(group) for group in groups
                     for row in members
                     if _confirmed(row) and _written(row) in group}
        if not confirmed:
            continue
        for group in groups:
            if min(group) in confirmed:
                continue
            for row in members:
                mass = _written(row)
                if mass in group and not _confirmed(row):
                    isolated[str(getattr(row, "sample", ""))] = mass
    return isolated


#: the three reasons a precursor was not measured at all, as the sentence
#: writes them. The classification is off `InfusionReport.survivor_note`,
#: which is where the reason is made, with the row's own short form as the
#: fallback: the note is a sentence and the cell is an abbreviation of it.
TOO_LITTLE = "with too little precursor surviving fragmentation"
NOTHING_THERE = "with nothing in the window their method isolates"
UNMEASURED = "with no precursor measurement at all"


def _not_measured_reason(row) -> str:
    report = _report(row)
    note = str(getattr(report, "survivor_note", "") or "").lower()
    cell = str(getattr(row, "precursor_note", "") or "").lower()
    if note.startswith("too little") or "counts survive" in cell \
            or cell.startswith("under "):
        return TOO_LITTLE
    if note.startswith("nothing at all") or cell.startswith("nothing within"):
        return NOTHING_THERE
    return UNMEASURED


def _precursor_sentence(rows) -> str:
    """
    How many precursors came back where the method said, and what the rest did.

    Every row with a written precursor is counted, because a denominator that
    quietly leaves out the ones that could not be measured is the figure this
    whole program exists not to print.
    """
    written = [row for row in rows if _written(row) is not None]
    if not written:
        return ("No method in this folder writes a precursor, so there was "
                "nothing to confirm.")
    confirmed = [row for row in written if _confirmed(row)]
    said = (f"{len(confirmed)} of {len(written)} precursor(s) confirmed "
            f"within {CONFIRMED_PPM:g} ppm")
    missed = [row for row in written if not _confirmed(row)]
    if missed:
        isolated = isolated_precursors(rows)
        buckets: dict[str, int] = {}
        errors: list[float] = []
        for row in missed:
            # the isolation is asked **before** the error, because a row whose
            # method targets a mass this compound's other runs do not is not a
            # row with a mass error: its ppm is measured against a precursor
            # the compound never had, and reporting the two `_TESTEARTIGO`
            # acquisitions as "at -43.0 ppm" says the instrument was slightly
            # out where what happened is that the vial is not what the file
            # name says. Asking second made this dead on the files it was
            # written for: once the noise floor was measured off the
            # acquisition instead of fixed at a hundred counts, all five
            # unconfirmed rows had an error to report and no row ever reached
            # the bucket. `isolated_precursors` only answers where the
            # compound has another cluster that *did* confirm, so it cannot
            # swallow an ordinary miss.
            mass = isolated.get(str(getattr(row, "sample", "")))
            if mass is not None:
                phrase = f"whose method isolates {mass:g}"
                buckets[phrase] = buckets.get(phrase, 0) + 1
                continue
            error = _error_ppm(row)
            if error is not None:
                errors.append(error)
                continue
            buckets[_not_measured_reason(row)] = \
                buckets.get(_not_measured_reason(row), 0) + 1
        parts = [f"{count} {phrase}" for phrase, count in
                 sorted(buckets.items(), key=lambda item: (-item[1], item[0]))]
        if errors:
            errors.sort()
            if len(errors) <= ERRORS_LISTED:
                parts.append(f"{len(errors)} at "
                             + " and ".join(f"{e:+.1f}" for e in errors)
                             + " ppm")
            else:
                parts.append(f"{len(errors)} between {errors[0]:+.1f} and "
                             f"{errors[-1]:+.1f} ppm")
        said += f"; {len(missed)} not: " + ", ".join(parts)
    unwritten = len(rows) - len(written)
    if unwritten:
        said += (f". {unwritten} more infusion(s) write no precursor in their "
                 f"method, so they are in neither count")
    return said + "."


def _library_sentence(summary, rows) -> str:
    """What the analyst's own library said, and about how many of them."""
    if not str(getattr(summary, "library", "") or ""):
        return ("No library of your own was searched, so no infusion here "
                "was put against a record of the same compound.")
    scored = [row for row in rows if getattr(row, "score", None) is not None]
    if not scored:
        return (f"No infusion matched a record in "
                f"{getattr(summary, 'library', '')}.")
    # by the number and never by the row: an `InfusionRow` holds arrays,
    # and `row not in above` would compare two of them elementwise and raise
    above = [row for row in scored
             if float(getattr(row, "score", 0.0)) >= COUNTED_SCORE]
    below = [row for row in scored
             if float(getattr(row, "score", 0.0)) < COUNTED_SCORE]
    said = (f"Own records: {len(above)} above {COUNTED_SCORE * 100:.0f}, "
            f"{len(below)} below")
    gapped = [row for row in below if _energy_gap(row) is not None]
    if below and len(gapped) == len(below):
        said += " — all across a collision-energy change"
    elif gapped:
        said += (f" — {len(gapped)} of them across a collision-energy change")
    missing = len(rows) - len(scored)
    if missing:
        said += f"; {missing} matched no record at all"
    return said + "."


def _energy_gap(row):
    report = _report(row)
    gap = getattr(report, "energy_gap", None)
    if not callable(gap):
        return None
    try:
        return gap()
    except Exception:                                # a row that cannot say
        return None


def _explanation_sentence(rows) -> str:
    """The predicted ions found, summed over every spectrum that had any."""
    explained = [row for row in rows
                 if getattr(_report(row), "explanation", None) is not None]
    if not explained:
        return ("No formula or structure was scored against any of these "
                "spectra, so no ion was predicted and none could be found.")
    found = sum(int(getattr(_report(row).explanation, "matched", 0))
                for row in explained)
    offered = sum(int(getattr(_report(row).explanation, "predicted", 0))
                  for row in explained)
    said = (f"Predicted ions: {found} of {offered} found across "
            f"{len(explained)} spectrum(s)" if offered else
            f"Predicted ions: {found} peak(s) accounted for across "
            f"{len(explained)} spectrum(s)")
    silent = len(rows) - len(explained)
    if silent:
        said += (f"; {silent} had nothing to predict from — no formula in the "
                 f"component table for that compound")
    return said + "."


def verdict_sentences(summary) -> list[str]:
    """
    The table above summed, one sentence per column that can be summed.

    Each sentence is a count and what it was counted against, which is the
    rule the per-compound verdict already follows: a line reading "5 failed"
    is a judgement, and a line reading "5 of 9 confirmed within 25 ppm" is a
    measurement. There is no sentence at the end drawing them together,
    because whether a folder of vials is what its labels say is a question
    for the person who filled them.

    Each begins with a capital, unlike the clauses of `InfusionSummary`'s
    one-line summary, because these are read as a paragraph: printed and
    looked at, `…1 at +30.3 ppm. own records: 4 above 60` is a full stop
    followed by a lower-case word, which reads as a typographical mistake
    rather than as the next of three measurements.
    """
    rows = list(getattr(summary, "rows", ()) or ())
    if not rows:
        return [str(getattr(summary, "note", "") or "No infusion was read.")]
    return [_precursor_sentence(rows), _library_sentence(summary, rows),
            _explanation_sentence(rows)]


def verdict(summary) -> str:
    """The sentences as one paragraph, in plain text."""
    return " ".join(verdict_sentences(summary))


# --------------------------------------------------------------------------- #
# the blocks
# --------------------------------------------------------------------------- #
def grouped(rows) -> list:
    """
    The rows with each compound's acquisitions together, compounds in the
    order they were first read.

    A folder comes off the instrument in the order it was acquired, which
    interleaves two vials whenever somebody ran a mix twice. A table meant to
    be read down the Compound column has to put them back together, and the
    order of compounds is still the order of acquisition so the table and the
    pages that follow it run the same way.
    """
    order: dict[str, list] = {}
    for row in rows:
        order.setdefault(str(getattr(row, "compound", "")), []).append(row)
    return [row for members in order.values() for row in members]


def _title_block(result, summary) -> str:
    from . import __version__

    when = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    folder = folder_of(result)
    rows = list(getattr(summary, "rows", ()) or ())
    compounds = list(dict.fromkeys(str(getattr(row, "compound", ""))
                                   for row in rows))
    read = len(list(getattr(result, "read", ()) or ()))
    skipped = len(list(getattr(result, "skipped", ()) or ()))
    # the measurement's own seconds, not the run's: laying a fifty-page
    # document out is most of a run's time and none of its measuring, and
    # `result.seconds` is not final until after this has been written anyway
    seconds = float(getattr(summary, "seconds", 0.0) or
                    getattr(result, "seconds", 0.0) or 0.0)
    library = str(getattr(summary, "library", "") or "")
    cells = [
        ["Folder", _escape(folder or "—"), "Generated", when],
        ["Files read", f"{read:,}" + (f" ({skipped:,} skipped)"
                                      if skipped else ""),
         "Infusions", f"{len(rows):,} in {len(compounds):,} compound(s)"],
        ["Library of your own", _escape(library or "none searched"),
         "Measured in", f"{seconds:.1f} s"],
    ]
    body = []
    for number, row in enumerate(cells):
        stripe = ' class="alt"' if number % 2 else ""
        body.append(
            f'<tr{stripe}><td class="label" width="18%">{row[0]}</td>'
            f'<td width="32%">{row[1]}</td>'
            f'<td class="label" width="18%">{row[2]}</td>'
            f'<td width="32%">{row[3]}</td></tr>')
    return (f'<p class="eyebrow">MIL-Q {_escape(__version__)} · direct '
            f'infusion report</p>'
            f'<h1>{_escape(title_for(result))}</h1>'
            f'<table class="ident" width="100%" cellpadding="4" '
            f'cellspacing="0">{"".join(body)}</table>'
            f'<p class="foot">{_escape(_summary_line(summary))}</p>')


def _summary_line(summary) -> str:
    line = getattr(summary, "summary", None)
    return str(line()) if callable(line) else ""


def _infusions_block(summary, breaks: set[str] | None = None) -> str:
    """Every infusion on one row: `report._infusions`'s table, grouped."""
    rows = grouped(list(getattr(summary, "rows", ()) or ()))
    parts = [_heading("The infusions", breaks)]
    parts.append(
        f'<p class="meta">One row per infused sample, each averaged over its '
        f'whole run and grouped by compound. The precursor is the method’s '
        f'own written value measured back off the acquisition, counted as '
        f'confirmed below at {CONFIRMED_PPM:g} ppm; the adduct is the ion '
        f'that written precursor is, with whether the survey scan of the same '
        f'acquisition confirmed it by exact mass and isotope pattern; the '
        f'ions found are of '
        f'those a formula or a structure predicted; the record is the best in '
        f'the library of your own, counted below at '
        f'{COUNTED_SCORE * 100:.0f}. <em>Other infusions</em> scores each '
        f'infusion against the others of its compound over the peaks above '
        f'{SCORE_SHARE:.0%} of each base peak, and <em>Mass axis</em> is the '
        f'offset the acquisition’s own ladder of known masses measured, where '
        f'there were enough rungs to measure one. '
        f'A cell that could not be '
        f'filled says why rather than being blank, cut at a word where the '
        f'reason is a sentence — the whole of it is on that compound’s own '
        f'page.</p>')
    parts.append(_table(
        list(REPORT_COLUMNS),
        [[_escape(_cell(cell)) for cell in row.report_cells()]
         for row in rows],
        right=RIGHT_COLUMNS, empty="No file read as a direct infusion.",
        widths=COLUMN_WIDTHS))
    return "".join(parts)


def _cell(text: str) -> str:
    """One cell, cut at a word if it is a sentence — see `CELL_CHARACTERS`."""
    text = str(text)
    if len(text) <= CELL_CHARACTERS:
        return text
    cut = text[:CELL_CHARACTERS].rsplit(" ", 1)[0] or text[:CELL_CHARACTERS]
    return cut.rstrip(" ,;") + "\u2026"


def _verdict_block(summary, breaks: set[str] | None = None) -> str:
    parts = [_heading("What they add up to", breaks),
             '<p class="meta">Each sentence sums a column of the table above '
             'and says what it was counted against. There is no overall pass '
             'or fail for the folder, for the same reason there is none for '
             'a compound: what a spectrum is worth depends on what the vial '
             'was supposed to hold.</p>']
    parts.append("<p>" + " ".join(_escape(sentence)
                                  for sentence in verdict_sentences(summary))
                 + "</p>")
    return "".join(parts)


def _left_out_block(result, breaks: set[str] | None = None) -> str:
    """
    The files that were not reported, and what the folder's names said.

    A folder of nine reported as eight with nothing to say which one went is
    the failure that matters here, so this is printed whether or not there is
    anything in it — "nothing was left out" is a measurement too.
    """
    skipped = list(getattr(result, "skipped", ()) or ())
    findings = list(getattr(result, "findings", ()) or ())
    parts = [_heading("What was left out", breaks)]
    parts.append(_table(
        ["File", "Left out as", "Why"],
        [[_escape(getattr(skip, "name", "")),
          _escape(getattr(skip, "kind", "")),
          _escape(getattr(skip, "reason", ""))] for skip in skipped],
        empty="Nothing was left out: every file given was read.",
        widths=["26%", "16%", "58%"]))
    parts.append('<p class="meta">What the folder’s own names said, before '
                 'anything was opened.</p>')
    parts.append(_table(
        ["File", "Finding", "What to do"],
        [[_escape(getattr(finding, "name", "")),
          _escape(getattr(finding, "finding", "")),
          _escape(getattr(finding, "action", ""))] for finding in findings],
        empty="Nothing to report about the folder itself.",
        widths=["26%", "42%", "32%"]))
    return "".join(parts)


def _contents_block(headings: list[str], pages: dict[str, int] | None,
                    breaks: set[str] | None = None) -> str:
    """
    The per-compound pages and where they are.

    `report.print_document` lays the document out once with this column
    reserved and empty, reads the page each heading landed on, and builds it
    again with the numbers — so the row heights are the same on both passes
    and the numbers it prints are the numbers it measured. `pages` is None on
    an HTML document, which has no pages until a browser gives it some.
    """
    if not headings:
        return ""
    rows = []
    for number, heading in enumerate(headings):
        stripe = ' class="alt"' if number % 2 else ""
        page = "" if not pages else str(pages.get(heading, ""))
        cell = (f'<td class="num" width="8%">{page}</td>'
                if pages is not None else "")
        rows.append(f'<tr{stripe}><td>{_escape(heading)}</td>{cell}</tr>')
    css = ' class="break"' if breaks and "The pages that follow" in breaks \
        else ""
    return (f'<h2{css}>The pages that follow</h2>'
            f'<table class="contents" width="60%" cellpadding="3" '
            f'cellspacing="0">{"".join(rows)}</table>')


def build_html(result, summary, headings=(), contents: dict[str, int] | None
               = None, breaks: set[str] | None = None) -> str:
    """
    The cover, as the HTML that goes in front of the per-compound sections.

    A fragment and not a document: it is printed in the same PDF as the pages
    it introduces, and the page numbers in its contents are only true because
    the two were laid out together. `headings` are those pages' headings,
    `contents` the mapping `report.print_document` works out, `breaks` the
    headings it wants on a fresh page.
    """
    return "".join([
        _title_block(result, summary),
        _infusions_block(summary, breaks),
        _verdict_block(summary, breaks),
        _left_out_block(result, breaks),
        _contents_block(list(headings), contents, breaks),
    ])


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def headings_for(reports) -> list[str]:
    """
    One numbered heading per section, in the printed order.

    The sample's name is in it and not only the compound's, because a folder
    is where one compound is infused five times: a contents list reading
    `1. CA-d4 … 5. CA-d4` against five different page numbers sends the
    reader to page 3 to find out whether page 3 is the one they wanted.
    `InfusionReport.title` falls back to the sample when there is no
    compound, so the name is only added where it says something new.
    """
    made = []
    for number, report in enumerate(reports, start=1):
        title = str(getattr(report, "title", "") or "")
        sample = str(getattr(report, "sample", "") or "")
        if sample and sample != title:
            title = f"{title} · {sample}"
        made.append(f"{number}. {title}")
    return made


def build_document(result, summary, reports=(), title: str = "",
                   contents: dict[str, int] | None = None,
                   breaks: set[str] | None = None) -> str:
    """
    Cover then pages, as one HTML document.

    Every compound starts a fresh page — including the first, which
    `infusion_report.build_html` leaves alone because there it follows the
    contents rather than three tables.
    """
    reports = list(reports)
    title = title or title_for(result)
    headings = headings_for(reports)
    breaks = set(breaks or ()) | set(headings)
    parts = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'>",
             f"<title>{_escape(title)}</title>",
             f"<style>{_STYLE}</style></head><body>",
             build_html(result, summary, headings=headings,
                        contents=contents, breaks=breaks)]
    for heading, report in zip(headings, reports, strict=True):
        parts.append(build_section(report, heading, breaks))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(result, summary, reports, path: str | os.PathLike,
               title: str = "") -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_document(result, summary, reports, title=title))
    return path


def write_pdf(result, summary, reports, path: str | os.PathLike,
              title: str = "") -> str:
    """The cover and the pages on A4, through the batch report's printer."""
    title = title or title_for(result)
    return print_document(
        lambda contents, breaks: build_document(
            result, summary, reports, title=title, contents=contents,
            breaks=breaks),
        str(path), title, reflows=REFLOWS)
