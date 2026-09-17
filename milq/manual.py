"""
The manual: the pages under `help/pages`, how they link, and how to search.

The pages are Markdown with wiki links — `[[Peak review]]`, or
`[[peak-review|the review grid]]` — the way a note-taking vault links its
notes, so that a page can point at another by name and the reader can go
back the same way: every page ends with the pages that link to it. The
window in `ui.help_window` shows them; `write_pdf` prints the whole set as
one document, in the order below, for reading away from the application.

A page is identified by its file name, without the extension. The order and
the grouping into sections is `INDEX`, here rather than in the files, so
that the table of contents is one thing to edit and a page can be moved
without touching its text.

The manual is written in more than one language. English is the original,
under `help/pages`; every other language is a directory beside those pages
holding the same file names — `help/pages/pt/welcome.md` is the Portuguese
`welcome`. Only the text is translated: the file name is the page's
identity, so a `[[link]]` names the same page in every language and the
renderer shows the target's title in the language being read. A page a
language does not have yet is read from the original and shown with a note
saying so, rather than being left out of the contents.

The Markdown understood is the small, regular subset the pages use:
headings, paragraphs, bullet and numbered lists, tables, fenced code,
quotes, rules, and inline code, emphasis and links. Qt's own Markdown
reader was not used because the rendered HTML has to carry a stylesheet the
window and the printer can both apply, and a converter of a hundred lines
whose output is known is easier to keep to that than one whose output is
not.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__

PAGES_DIR = Path(__file__).parent / "help" / "pages"

#: the languages the manual is written in. The first is the original: its
#: pages sit in `PAGES_DIR` itself and every other language is a directory
#: beside them holding the same file names. The file name is the page's
#: identity, so a translated page is the same page and a `[[link]]` is the
#: same link whatever language it is read in.
LANGUAGES: tuple[str, ...] = ("en", "pt")
DEFAULT_LANGUAGE = "en"

#: what each language calls itself, for the switch in the window
LANGUAGE_NAMES: dict[str, str] = {"en": "English", "pt": "Português"}

#: `INDEX`'s section headings, per language. The three that name a tab of
#: the application keep the English name in brackets, because the tab is
#: still labelled in English: the manual is translated, the software is not.
SECTION_TITLES: dict[str, dict[str, str]] = {
    "pt": {
        "Getting started": "Primeiros passos",
        "Explorer": "Explorer",
        "Chemistry and annotation": "Química e anotação",
        "Samples": "Amostras (Samples)",
        "Method": "Método (Method)",
        "Analytics": "Análise (Analytics)",
        "Reference": "Referência",
    },
}

#: the handful of strings the manual writes around its pages: the contents
#: heading and the running furniture of the printed copy, the note on a page
#: that has not been translated yet, and the backlinks under a page.
#: Everything else in a language is in that language's pages.
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "document_title": "User manual",
        "pdf_title": "user manual",
        "contents": "Contents",
        "page_of": "Page {page} of {total}",
        "generated": "generated",
        "intro": ("Version {version}. Every page of the application's "
                  "built-in help, in the order of its contents. Links "
                  "between pages are kept as links within this document."),
        "linked_from": "Linked from",
        "untranslated": "",
    },
    "pt": {
        "document_title": "Manual do usuário",
        "pdf_title": "manual do usuário",
        "contents": "Sumário",
        "page_of": "Página {page} de {total}",
        "generated": "gerado em",
        "intro": ("Versão {version}. Todas as páginas da ajuda integrada "
                  "do aplicativo, na ordem do sumário. Os links entre as "
                  "páginas continuam sendo links dentro deste documento."),
        "linked_from": "Recebe links de",
        "untranslated": "(esta página ainda está em inglês)",
    },
}


def strings(language: str) -> dict[str, str]:
    """The furniture strings of a language; English for one we do not have."""
    return STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE])


def pages_dir(language: str = DEFAULT_LANGUAGE,
              directory: Path | str = PAGES_DIR) -> Path:
    """Where a language's pages are: the root itself for the original."""
    directory = Path(directory)
    return directory if language == DEFAULT_LANGUAGE else directory / language


#: the manual's order: section heading, then the page ids under it
INDEX: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Getting started", (
        "welcome", "installation", "formats", "checking-files",
        "starting-a-project", "workspaces",
    )),
    ("Explorer", (
        "explorer", "chromatograms-and-spectra", "direct-infusion",
        "infusion-report", "new-standard", "infusion-quantitation",
        "contour-view", "manual-xic",
        "explorer-components-and-results", "sample-information",
    )),
    ("Chemistry and annotation", (
        "mass-calculator", "formula-finder", "lipid-maps", "spectral-library",
        "standard-history", "accurate-precursor",
    )),
    ("Samples", (
        "samples-workspace",
    )),
    ("Method", (
        "method-workspace", "internal-standards-and-qualifiers", "check-method",
        "method-report",
        "suggest-from-data", "annotate-from-lipid-maps", "acquisition-schedule",
        "collision-energy",
    )),
    ("Analytics", (
        "analytics-workspace", "peak-review", "integration-parameters",
        "integration-algorithms", "compare-algorithms", "compare-batches",
        "compare-infusions",
        "signal-to-noise",
        "results-table", "calibration", "acceptance-criteria", "statistics",
        "metric-plot", "batch-qc", "mass-drift", "mass-recalibration",
        "detection-limits-and-carryover",
        "audit-trail", "report",
    )),
    ("Reference", (
        "projects-and-files", "export", "command-line", "python-api",
        "keyboard-shortcuts",
        "how-wiff-is-read", "measured-facts", "integration",
        "design-principles",
        "troubleshooting", "glossary", "version-history",
    )),
)

#: the page the window opens on
HOME = "welcome"

#: the scheme wiki links are rendered under, so the window can tell a page
#: from a web address
SCHEME = "help:"

_WIKI = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_WORD = re.compile(r"[a-z0-9](?:[a-z0-9+/-]|\.(?=[a-z0-9]))*")


@dataclass
class Page:
    id: str
    title: str
    section: str
    markdown: str
    #: the language this page's text is in — which is not always the
    #: language asked for: a page with no translation yet falls back
    language: str = DEFAULT_LANGUAGE
    #: False when the text shown is the original standing in for a
    #: translation that does not exist yet
    translated: bool = True
    #: the title of the English page, so a `[[link]]` written by title
    #: rather than by file name still resolves in a translated manual
    english_title: str = ""
    #: the body as HTML, wiki links resolved to `help:<id>` anchors
    html: str = ""
    #: the body as plain text, for searching and for snippets
    text: str = ""
    links: list[str] = field(default_factory=list)
    backlinks: list[str] = field(default_factory=list)
    #: wiki links whose target is not a page — a test keeps this empty
    unresolved: list[str] = field(default_factory=list)
    words: Counter = field(default_factory=Counter)


@dataclass(frozen=True)
class Hit:
    page: Page
    score: float
    snippet: str


class Manual:
    """Every page, in order, indexed for links and for searching."""

    def __init__(self, pages: dict[str, Page],
                 language: str = DEFAULT_LANGUAGE):
        self.pages = pages
        self.language = language
        self.strings = strings(language)
        self.order: list[str] = [pid for _section, ids in INDEX for pid in ids]
        # a link may name a page by title as well as by file name; the
        # English title answers too, so a page still under translation
        # links the same way it did before it was translated
        self._by_title = {page.english_title.lower(): page.id
                          for page in pages.values() if page.english_title}
        self._by_title.update({page.title.lower(): page.id
                               for page in pages.values()})
        for page in pages.values():
            self._render(page)
        for page in pages.values():
            for target in page.links:
                if page.id not in pages[target].backlinks:
                    pages[target].backlinks.append(page.id)

    # -- lookups ----------------------------------------------------------------- #
    def get(self, key: str) -> Page | None:
        """A page by id or, failing that, by title, case-insensitively."""
        if key in self.pages:
            return self.pages[key]
        return self.pages.get(self._by_title.get(key.strip().lower(), ""))

    def resolve(self, target: str) -> str | None:
        page = self.get(target)
        return page.id if page else None

    def section_of(self, page_id: str) -> str:
        """The section a page is in, by its English name — sections are
        identified the way pages are, and shown the way pages are."""
        for section, ids in INDEX:
            if page_id in ids:
                return section
        return ""

    def section_title(self, section: str) -> str:
        return SECTION_TITLES.get(self.language, {}).get(section, section)

    def sections(self) -> list[tuple[str, list[Page]]]:
        return [(self.section_title(section),
                 [self.pages[pid] for pid in ids if pid in self.pages])
                for section, ids in INDEX]

    @property
    def untranslated(self) -> list[str]:
        """The pages standing in from the original for want of a translation."""
        return [pid for pid in self.order
                if pid in self.pages and not self.pages[pid].translated]

    # -- rendering --------------------------------------------------------------- #
    def _render(self, page: Page) -> None:
        def link(match: re.Match) -> str:
            target, shown = match.group(1).strip(), match.group(2)
            resolved = self.resolve(target)
            if resolved is None:
                page.unresolved.append(target)
                return html.escape(shown or target)
            if resolved not in page.links and resolved != page.id:
                page.links.append(resolved)
            text = shown.strip() if shown else self.pages[resolved].title
            return f'<a href="{SCHEME}{resolved}">{html.escape(text)}</a>'

        body = page.markdown
        # the title is the first heading; the window draws its own
        rendered = render_markdown(body, link)
        # searching and the length check see the page, not the furniture
        page.text = plain_text(rendered)
        page.words = Counter(_WORD.findall(page.text.lower()))
        note = "" if page.translated else self.strings.get("untranslated", "")
        page.html = (f'<p class="untranslated">{html.escape(note)}</p>{rendered}'
                     if note else rendered)

    # -- searching --------------------------------------------------------------- #
    def search(self, query: str, limit: int = 40) -> list[Hit]:
        """
        Pages mentioning every word of the query, best first.

        A word matches by prefix, so `integr` finds integration and
        integrated. A hit in the title counts for far more than one in the
        body, and a page has to contain every word to be listed at all: a
        query of three words that lists every page holding any of them is
        a query that has not narrowed anything.
        """
        terms = _WORD.findall(query.lower())
        if not terms:
            return []
        hits: list[Hit] = []
        for pid in self.order:
            page = self.pages.get(pid)
            if page is None:
                continue
            score = 0.0
            for term in terms:
                in_title = term in page.title.lower()
                count = sum(n for word, n in page.words.items()
                            if word.startswith(term))
                if not count and not in_title:
                    score = 0.0
                    break
                score += count + (25.0 if in_title else 0.0)
            if score > 0:
                hits.append(Hit(page, score, _snippet(page.text, terms)))
        hits.sort(key=lambda hit: -hit.score)
        return hits[:limit]

    # -- whole document ---------------------------------------------------------- #
    def html_document(self, contents: dict[str, int] | None = None,
                      breaks: set[str] | None = None) -> str:
        """
        Every page as one document, for printing.

        Wiki links become anchors within the document. Each page is an
        `h2`, which is what the printer numbers in the table of contents,
        and each section an `h1`, so a reader of the PDF sees the same
        grouping the window's tree shows.
        """
        from .report import _STYLE, _contents, _heading

        words = self.strings
        parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
                 f"<title>MIL-Q manual</title><style>{_STYLE}{_PRINT_STYLE}"
                 "</style></head><body>",
                 '<p class="eyebrow">MILQ</p>',
                 f"<h1>{html.escape(words['document_title'])}</h1>"
                 f'<p class="meta">'
                 f"{html.escape(words['intro'].format(version=__version__))}</p>",
                 _contents([self.pages[pid].title for pid in self.order
                            if pid in self.pages], contents,
                           heading=words["contents"])]
        for number, (section, pages) in enumerate(self.sections()):
            # the first section follows the contents on the same page: a
            # break there leaves a page holding two lines of contents
            kind = "opening" if number == 0 else "section"
            parts.append(f'<h1 class="{kind}">{html.escape(section)}</h1>')
            for page in pages:
                parts.append(f'<a name="{page.id}"></a>')
                parts.append(_heading(page.title, breaks))
                # a page's own headings sit under its title: one level down,
                # so that the printer's contents and orphan rules, which key
                # on h2, see page titles and nothing else at that level
                body = page.html.replace("<h3>", "<h4>").replace("</h3>", "</h4>")
                body = body.replace("<h2>", "<h3>").replace("</h2>", "</h3>")
                parts.append(body.replace(f'href="{SCHEME}', 'href="#'))
        parts.append("</body></html>")
        return "".join(parts)

    #: how many times a heading stranded at the foot of a page may be pushed
    #: over; each push can strand another, and a manual has many headings
    REFLOWS = 12

    def write_pdf(self, path) -> str:
        """The whole manual as one document, in the language it was read in."""
        from .report import print_document
        return print_document(
            self.html_document, path,
            f"MIL-Q {__version__} — {self.strings['pdf_title']}",
            reflows=self.REFLOWS, strings=self.strings)


_PRINT_STYLE = """
h1.section { font-size: 15pt; color: #234b8c; margin: 24pt 0 6pt 0;
             page-break-before: always; }
h1.opening { font-size: 15pt; color: #234b8c; margin: 24pt 0 6pt 0; }
h4 { font-size: 9pt; font-weight: 600; margin: 8pt 0 2pt 0; color: #16181c; }
p { margin: 0 0 5pt 0; }
li { margin: 0 0 3pt 0; }
h3 { color: #234b8c; }
pre { font-family: Menlo, Consolas, "DejaVu Sans Mono", monospace;
      font-size: 7.5pt; background: #f2f4f7; margin: 4pt 0 6pt 0; }
code { font-family: Menlo, Consolas, "DejaVu Sans Mono", monospace;
       font-size: 8pt; }
blockquote { color: #5b6472; margin: 4pt 0 6pt 12pt; }
p.untranslated { color: #5b6472; font-size: 8pt; margin: 0 0 6pt 0; }
"""


def _snippet(text: str, terms: list[str], width: int = 90) -> str:
    lower = text.lower()
    position = -1
    for term in terms:
        position = lower.find(term)
        if position >= 0:
            break
    if position < 0:
        return text[:width * 2].strip()
    start = max(position - width, 0)
    end = min(position + width, len(text))
    piece = text[start:end].strip()
    return ("…" if start else "") + piece + ("…" if end < len(text) else "")


# --------------------------------------------------------------------------- #
# markdown
# --------------------------------------------------------------------------- #
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_TABLE_RULE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _inline(text: str, link) -> str:
    """Inline markup on one run of text; wiki links first, since they may
    carry characters the other rules would take."""
    pieces: list[str] = []
    position = 0
    for match in _WIKI.finditer(text):
        pieces.append(_inline_plain(text[position:match.start()]))
        pieces.append(link(match) if link else html.escape(match.group(2) or match.group(1)))
        position = match.end()
    pieces.append(_inline_plain(text[position:]))
    return "".join(pieces)


def _inline_plain(text: str) -> str:
    # code spans are literal: escape them and keep the rest from touching them
    codes: list[str] = []

    def stash(match: re.Match) -> str:
        codes.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = _INLINE_CODE.sub(stash, text)
    text = html.escape(text, quote=False)
    text = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = _BOLD.sub(r"<b>\1</b>", text)
    text = _ITALIC.sub(r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def render_markdown(source: str, link=None) -> str:
    """
    The subset of Markdown the pages are written in, as HTML.

    `link` renders a wiki-link match; without one the link's text is kept
    and nothing is linked, which is what a page shown outside the manual
    wants.
    """
    lines = source.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    index = 0

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph), link)}</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush()
            index += 1
            continue
        if stripped.startswith("```"):
            flush()
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            index += 1
            out.append(f"<pre>{html.escape(chr(10).join(block))}</pre>")
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2), link)}</h{level}>")
            index += 1
            continue
        if stripped in ("---", "***"):
            flush()
            out.append("<hr/>")
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) \
                and _TABLE_RULE.match(lines[index + 1].strip()):
            flush()
            header = _cells(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_cells(lines[index].strip()))
                index += 1
            head = "".join(f"<th>{_inline(cell, link)}</th>" for cell in header)
            body = "".join(
                ('<tr class="alt">' if n % 2 else "<tr>")
                + "".join(f"<td>{_inline(cell, link)}</td>" for cell in row) + "</tr>"
                for n, row in enumerate(rows))
            out.append(f'<table width="100%" cellpadding="4" cellspacing="0">'
                       f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
            continue
        if stripped.startswith(">"):
            flush()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            out.append(f"<blockquote>{_inline(' '.join(quote), link)}</blockquote>")
            continue
        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            flush()
            ordered = bullet.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while index < len(lines):
                match = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[index])
                if match and (match.group(2)[0].isdigit()) == ordered:
                    items.append(match.group(3))
                    index += 1
                elif lines[index].startswith("  ") and items and lines[index].strip():
                    items[-1] += " " + lines[index].strip()      # continuation
                    index += 1
                else:
                    break
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(item, link)}</li>"
                                            for item in items) + f"</{tag}>")
            continue
        paragraph.append(stripped)
        index += 1
    flush()
    return "\n".join(out)


def _cells(row: str) -> list[str]:
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


_TAGS = re.compile(r"<[^>]+>")


def plain_text(rendered: str) -> str:
    text = rendered.replace("</p>", "\n").replace("</li>", "\n").replace("</tr>", "\n")
    text = text.replace("</h2>", "\n").replace("</h3>", "\n").replace("<br/>", "\n")
    return html.unescape(_TAGS.sub(" ", text)).replace("\xa0", " ")


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def read_page(path: Path, pid: str) -> tuple[str, str]:
    """A page file as its title and its body.

    A page starts with a front matter block carrying its title; anything
    else in the block is ignored, so a page can note what it is for without
    that being shown.
    """
    source = path.read_text(encoding="utf-8")
    title = pid.replace("-", " ").capitalize()
    front = _FRONT.match(source)
    if front:
        for line in front.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "title":
                title = value.strip()
        source = source[front.end():]
    return title, source


def load(directory: Path | str = PAGES_DIR,
         language: str = DEFAULT_LANGUAGE) -> Manual:
    """
    Read every page named in `INDEX`, in the language asked for.

    A language other than the original is a directory of the same file
    names beside the originals. A page it does not have is read from the
    original instead and says so: half a translated manual is more use
    than none of one, and the alternative — hiding the pages nobody has
    translated yet — is a manual with holes in its contents.
    """
    directory = Path(directory)
    folder = pages_dir(language, directory)
    pages: dict[str, Page] = {}
    for section, ids in INDEX:
        for pid in ids:
            original = directory / f"{pid}.md"
            path = folder / f"{pid}.md"
            translated = path != original and path.exists()
            if not translated:
                path = original
            if not path.exists():
                continue
            title, source = read_page(path, pid)
            english = title
            if translated and original.exists():
                english = read_page(original, pid)[0]
            pages[pid] = Page(id=pid, title=title,
                              section=SECTION_TITLES.get(language, {})
                              .get(section, section),
                              markdown=source,
                              language=language if translated else DEFAULT_LANGUAGE,
                              translated=translated or language == DEFAULT_LANGUAGE,
                              english_title=english)
    return Manual(pages, language=language)


_loaded: dict[str, Manual] = {}


def manual(language: str = DEFAULT_LANGUAGE) -> Manual:
    """The manual in a language, read once."""
    if language not in _loaded:
        _loaded[language] = load(language=language)
    return _loaded[language]
