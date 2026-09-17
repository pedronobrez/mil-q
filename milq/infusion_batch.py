"""
A folder of infusions, reported without opening one of them in the Explorer.

The per-compound report answers *is this vial what the label says it is?* for
the sample on screen, and the Infusions tab answers it for everything already
open. Both start with somebody opening files. A folder that came off the
instrument this morning has nine acquisitions in it and the question asked of
it is the same nine times, so this asks it with no window and no tree: point
at the folder, get the document.

What it does, in order
----------------------

1. `folder.check_files` looks the paths over before anything is opened — a
   `.wiff` whose `.wiff.scan` is not beside it, a `.wiff2` nothing here
   reads, a file given twice. Every finding is carried through to the caller
   and printed, and **a `.wiff` missing its companion is never opened**: it
   would open, draw its chromatograms and have no spectra, and a report whose
   averaged spectrum is empty is a page that says nothing at length.
2. Each remaining file is opened into a `Session` **of its own**, measured,
   and closed again before the next is opened. A folder of thirty infusions
   would otherwise hold thirty readers, each with a memory-mapped `.wiff.scan`
   behind it; the reports that come out hold arrays and strings and no reader,
   so nothing is lost by closing.
3. Samples that do not read as an infusion are left out with the figures that
   say so — `infusion.verdict_for`'s reason, which is a measurement of the
   run and not a guess from the file name.
4. What is left goes through `infusion_report.summarise` exactly as the tab
   calls it, one file at a time, and the rows are merged. The one thing that
   cannot be done per file is the score of each infusion against the others of
   its compound: three acquisitions of `CA-d4` in three files are three
   sessions of one row each, and each would call itself the only infusion of
   its compound. `_cross_score` puts that back over the merged rows, with the
   same `score_against` `summarise` uses.
5. `infusion_cover` puts the cover in front of those pages, in the same
   document: what was read, the table of every infusion, what the rows add up
   to in sentences, what was left out, and where each compound is. A folder's
   report opens on the folder and not on its first compound.

The component table and the library are the two things a headless run cannot
ask a person for. Both are optional and both are named on the command line:
the components from a project or a components CSV, so the compounds can be
explained from their formulas, and an MSP of one's own to search. Without
either, the rows say why the cell is empty, which is what they do in the tab.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field

from . import folder as _folder
from . import infusion_cover
from .infusion import verdict_for
from .infusion_report import (InfusionSummary, prepare_documents,
                              score_against, summarise, write_html, write_pdf,
                              write_summary_csv)
from .method import ProcessingMethod
from .session import PROJECT_SUFFIXES, Session

#: why a file or a sample was left out. `folder.MISSING_SCAN` is reused as
#: written rather than spelled again here: the check that finds it and the
#: skip that follows from it should say the same words.
MISSING_SCAN = _folder.MISSING_SCAN
#: the file opened and nothing in it reads as a direct infusion
NOT_INFUSION = "not an infusion"
#: the file did not open at all
UNREADABLE = "unreadable"
#: the check refused it before anything opened it — unsupported, absent,
#: already given
NOT_OPENED = "not opened"

#: what a document is written as. The extension follows from it, so a name
#: given without one still lands on the right file.
FORMATS = {"pdf": ".pdf", "html": ".html"}

#: characters allowed in the part of a per-compound file name that comes from
#: the compound. Everything else becomes an underscore: a compound is a label
#: somebody typed and `SM(d18:1/12:0)` holds a slash.
_UNSAFE = re.compile(r"[^A-Za-z0-9_.+-]+")


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", str(name or "").strip()) or "compound"


@dataclass(frozen=True)
class Skipped:
    """One file left out, and why — in words that name the measurement."""

    path: str
    kind: str
    reason: str

    @property
    def name(self) -> str:
        return os.path.basename(self.path) or self.path

    def __str__(self) -> str:
        return f"{self.name}: {self.reason}"


@dataclass
class BatchResult:
    """What the run did: what it read, what it wrote, what it left out."""

    requested: list[str] = field(default_factory=list)
    #: the files opened, in the order they were
    read: list[str] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    #: everything `folder.check_files` had to say, findings and all
    findings: list = field(default_factory=list)
    summary: InfusionSummary | None = None
    #: the documents written, in the order they were written
    documents: list[str] = field(default_factory=list)
    #: pages, where they could be counted — a PDF can be read back, an HTML
    #: document has no pages until a browser gives it some
    pages: int = 0
    csv: str = ""
    seconds: float = 0.0
    #: the progress callback asked for a stop
    cancelled: bool = False

    @property
    def rows(self) -> int:
        return 0 if self.summary is None else len(self.summary.rows)

    @property
    def compounds(self) -> list[str]:
        return [] if self.summary is None else self.summary.compounds

    def line(self) -> str:
        """One line for the command line: counts, and what they cost."""
        if self.cancelled:
            return "Stopped; nothing was written."
        if not self.rows:
            return (f"{len(self.read)} file(s) read, no infusion among them; "
                    f"{len(self.skipped)} skipped.")
        pages = f", {self.pages} page(s)" if self.pages else ""
        written = (f"{len(self.documents)} document(s){pages}"
                   if self.documents else "nothing written")
        return (f"{len(self.compounds)} compound(s) in {self.rows} "
                f"infusion(s) from {len(self.read)} file(s); "
                f"{len(self.skipped)} skipped; {written} in "
                f"{self.seconds:.1f} s.")


# --------------------------------------------------------------------------- #
# what a headless run has to be given
# --------------------------------------------------------------------------- #
def load_components(path: str | os.PathLike) -> ProcessingMethod:
    """
    The component table from a project or from a CSV of components.

    A project is read from its JSON alone — `batches.read_project`'s rule, and
    for the same reason: the formulas and adducts are in the saved method, and
    a project whose acquisitions have moved to another disk still carries
    them. Anything else is read as a components CSV.
    """
    path = str(path)
    if path.lower().endswith(tuple(PROJECT_SUFFIXES)):
        from .batches import read_project

        return read_project(path).method
    method = ProcessingMethod()
    method.import_components(path)
    return method


#: the application object made for a headless run, kept alive here. A
#: QApplication that nothing holds is collected the moment the function
#: that made it returns, and the next call into Qt — laying the document
#: out — dies with `Must construct a QGuiApplication before accessing
#: QFontDatabase`, after every file has been read and before anything is
#: written. Measured on the nine real infusions: nine seconds of reading
#: thrown away at the last step.
_APP = None


def _ensure_app():
    """
    A QApplication, because the document is drawn and printed through Qt.

    The picture is rendered by `spectra_compare` and the PDF laid out by
    `QTextDocument`; neither exists without an application object, and a
    command line has none. Made here rather than demanded of the caller so
    that a script is one import and one call — and reused when a window is
    already up, which is how the dialog reaches the same code.
    """
    global _APP
    from PyQt6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        from .api import offscreen_fonts

        offscreen_fonts()
        app = _APP = QtWidgets.QApplication([""])
    return app


def _page_count(path: str) -> int:
    """Pages in a PDF just written, or 0 if they cannot be counted."""
    try:
        from PyQt6.QtPdf import QPdfDocument
    except ImportError:                              # pragma: no cover
        return 0
    document = QPdfDocument(None)
    try:
        if document.load(path) != QPdfDocument.Error.None_:
            return 0
        return int(document.pageCount())
    finally:
        document.close()
        document.deleteLater()


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #
def _to_open(paths) -> tuple[list[str], list[Skipped], list]:
    """The files worth opening, the ones that are not, and every finding."""
    report = _folder.check_files(paths)
    refused = {}
    for finding in report.findings:
        if finding.kind == _folder.MISSING_SCAN:
            refused[finding.path] = Skipped(
                finding.path, MISSING_SCAN,
                f"{os.path.basename(finding.path)} has no "
                f"{os.path.basename(finding.path)}.scan beside it — its "
                f"spectra cannot be read, and the report is a spectrum")
        elif finding.kind in (_folder.UNSUPPORTED, _folder.ABSENT,
                              _folder.UNREADABLE, _folder.DUPLICATE):
            refused.setdefault(finding.path, Skipped(
                finding.path, NOT_OPENED, finding.finding))
    wanted, skipped = [], []
    for path in report.paths:
        if path in refused:
            skipped.append(refused.pop(path))
        else:
            wanted.append(path)
    # a finding on a path that was never a candidate — an unsupported file
    # named outright, a folder that cannot be listed — is a skip as well
    skipped += [s for s in refused.values() if s.kind != MISSING_SCAN]
    return wanted, skipped, list(report.findings)


def _why_not(session) -> str:
    """Why nothing in this file reads as an infusion, with the figures."""
    reasons = []
    for entry in getattr(session, "entries", []):
        sample = getattr(entry, "sample", None)
        if sample is None:
            continue
        try:
            verdict = verdict_for(sample)
        except Exception as exc:                     # a reader that cannot say
            reasons.append(f"{entry.name}: {type(exc).__name__}: {exc}")
            continue
        reasons.append(
            f"{entry.name}: {verdict.reason} ({verdict.n_scans:,} scans over "
            f"{verdict.length_min:.2f} min, {verdict.above_half * 100:.0f}% of "
            f"the total above half)")
    return "; ".join(reasons) or "no sample in it"


def _cross_score(rows) -> None:
    """
    Every infusion of a compound scored against the others, across files.

    `summarise` does this within one session, and one file at a time each
    session holds one acquisition — so every row comes back calling itself
    the only infusion of its compound. The scores are the same arithmetic on
    the same peaks; only the grouping is wider.
    """
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row.compound, []).append(row)
    for members in groups.values():
        for row in members:
            row.others = []
            row.others_note = ""
            for other in members:
                if other is row:
                    continue
                score, reverse, pairs = score_against(row.peaks, other.peaks)
                row.others.append((other.sample, float(score), float(reverse),
                                   len(pairs), len(other.peaks)))
            if not row.others:
                row.others_note = "the only infusion of this compound"


def _write(reports, rows, out: str, fmt: str, per_compound: bool,
           result: "BatchResult") -> list[str]:
    """
    The document, or one per compound and a cover, and their paths.

    One folder is one document: the cover — what was read, what it adds up
    to, what was left out and where each compound is — and then the pages,
    laid out together so the page numbers in its contents are the pages the
    sections actually landed on. `per_compound` is the one case where they
    are separated, and there the cover is written on its own, since the pages
    it introduces are in files of their own.
    """
    fmt = str(fmt or "pdf").lower()
    if fmt not in FORMATS:
        raise ValueError(f"{fmt}: the formats are {', '.join(sorted(FORMATS))}")
    write = write_pdf if fmt == "pdf" else write_html
    cover = (infusion_cover.write_pdf if fmt == "pdf"
             else infusion_cover.write_html)

    def check(path: str) -> str:
        """
        Check something is there after writing it.

        `QPdfWriter` reports nothing at all when it cannot open its file: a
        run pointed at a folder that does not exist read all nine
        acquisitions, laid the document out, printed `wrote …` and left
        nothing on disk. The HTML path raises like any other `open`, so this
        is for the PDF — and it is checked for both rather than for one.
        """
        if not os.path.exists(path):
            raise OSError(f"{path} was not written — check the folder "
                          f"exists and can be written to")
        return path

    stem, extension = os.path.splitext(str(out))
    if extension.lower() != FORMATS[fmt]:
        stem, extension = str(out), FORMATS[fmt]
    if not per_compound:
        return [check(cover(result, result.summary, reports,
                            stem + extension))]

    groups: dict[str, list] = {}
    for row, report in zip(rows, reports, strict=True):
        groups.setdefault(row.compound, []).append(report)
    written = [check(cover(result, result.summary, (),
                           f"{stem}-cover{extension}"))]
    for compound, made in groups.items():
        written.append(check(write(made, f"{stem}-{_safe(compound)}{extension}",
                                   title=f"{compound} — direct infusion")))
    return written


def run(paths, out, library=None, components=None, fmt: str = "pdf",
        csv=None, progress=None, per_compound: bool = False,
        cache=None) -> BatchResult:
    """
    Report every infusion in the given files and folders, opening no window.

    `paths` are files, folders, or both. `out` is the document to write; with
    `per_compound` the compound's name is put before the extension and one
    document is written for each. `library` is a path to an MSP or MGF of
    one's own, or a `SpectralLibrary` already loaded; `components` a path to a
    project or a components CSV, or a `ProcessingMethod`. `csv` writes the
    summary table beside the document. The document opens with
    `infusion_cover`'s cover; with `per_compound` that cover is a file of its
    own, named `-cover`.

    `progress(done, total, name)` is called once as each file is reached —
    `done` files behind it — and once more when the last is finished, and
    stops the run by returning False, in which case nothing is written and
    `BatchResult.cancelled` says so.

    `cache` is a `spectrum_cache.AverageCache` for the averaged spectra;
    None takes the default directory, which with no project open is the
    system's. A folder reported twice — a library added, an energy
    reconsidered — then reads its scans once. Pass `False` for no cache at
    all, which is what a measurement of the cold cost wants.
    """
    started = time.perf_counter()
    _ensure_app()
    if cache is None:
        from . import spectrum_cache

        cache = spectrum_cache.for_project(None)
    elif cache is False:
        cache = None
    wanted, skipped, findings = _to_open(paths)
    result = BatchResult(requested=[str(p) for p in paths],
                         skipped=skipped, findings=findings)

    if library is not None and not hasattr(library, "search"):
        from .library import load_library

        library = load_library(str(library))
    method = None
    if components is not None:
        method = (components if isinstance(components, ProcessingMethod)
                  else load_components(components))

    rows: list = []
    total = len(wanted)
    for done, path in enumerate(wanted):
        if progress is not None and not progress(done, total,
                                                 os.path.basename(path)):
            result.cancelled = True
            result.seconds = time.perf_counter() - started
            return result
        session = Session()
        if method is not None:
            session.method = method
        try:
            try:
                session.open_file(path)
            except Exception as exc:
                result.skipped.append(Skipped(
                    path, UNREADABLE,
                    f"could not be opened — {type(exc).__name__}: {exc}"))
                continue
            summary = summarise(session, library=library, cache=cache)
            if summary is None or not summary.rows:
                result.skipped.append(
                    Skipped(path, NOT_INFUSION, _why_not(session)))
                continue
            result.read.append(path)
            rows += summary.rows
        finally:
            # one reader at a time: a folder of thirty infusions holds thirty
            # memory-mapped .wiff.scan otherwise, and the rows hold arrays
            session.close_all()

    if progress is not None and not progress(total, total, ""):
        result.cancelled = True
        result.seconds = time.perf_counter() - started
        return result

    _cross_score(rows)
    name = os.path.basename(getattr(library, "path", "") or "") if library \
        else ""
    result.summary = InfusionSummary(
        rows=rows, library=name,
        note="" if rows else "No file read as a direct infusion.",
        seconds=time.perf_counter() - started)
    if rows:
        reports = prepare_documents(rows)
        result.documents = _write(reports, rows, out, fmt,
                                  per_compound, result)
        if str(fmt).lower() == "pdf":
            result.pages = sum(_page_count(p) for p in result.documents)
        if csv:
            result.csv = write_summary_csv(result.summary, csv)
    result.seconds = time.perf_counter() - started
    return result
