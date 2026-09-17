"""
The manual: every page present, every link resolving, and the window and
the printed copy built from the same pages.

A manual that names a page which does not exist, or links to one that was
renamed, is the kind of thing nobody notices until a reader does. The
tests here are the reader.

The translated manual is held to the same rules, and to one more: a
translated page is the same page as its original, so it has the same file
name and its links name the same pages. It is checked against whatever
translations exist — the set grows a file at a time, and a test that
needed the set to be complete would fail on every day but the last.
"""

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import manual as manual_module  # noqa: E402
from milq.manual import (DEFAULT_LANGUAGE, HOME, INDEX,  # noqa: E402
                              LANGUAGES, PAGES_DIR, SECTION_TITLES, STRINGS,
                              Manual, load, pages_dir, read_page,
                              render_markdown)

#: every language but the original
TRANSLATIONS = [code for code in LANGUAGES if code != DEFAULT_LANGUAGE]


def translated_slugs(language: str) -> list[str]:
    folder = pages_dir(language)
    return sorted(path.stem for path in folder.glob("*.md")) \
        if folder.is_dir() else []


@pytest.fixture(scope="module")
def manual() -> Manual:
    return load()


@pytest.fixture(scope="module", params=TRANSLATIONS)
def translated(request) -> Manual:
    return load(language=request.param)


def test_every_page_in_the_index_exists(manual):
    wanted = [pid for _section, ids in INDEX for pid in ids]
    missing = [pid for pid in wanted if pid not in manual.pages]
    assert missing == [], f"pages named in INDEX but not written: {missing}"
    on_disk = {path.stem for path in PAGES_DIR.glob("*.md")}
    orphans = on_disk - set(wanted)
    assert orphans == set(), f"pages on disk that the index does not list: {orphans}"


def test_every_page_has_a_title_of_its_own(manual):
    titles = [page.title for page in manual.pages.values()]
    assert len(titles) == len(set(titles)), "two pages share a title"
    assert all(title and title[0].isupper() for title in titles)
    assert HOME in manual.pages


def test_every_wiki_link_resolves(manual):
    broken = {pid: page.unresolved for pid, page in manual.pages.items()
              if page.unresolved}
    assert broken == {}, f"links to pages that do not exist: {broken}"


def test_every_page_is_reachable_by_a_link(manual):
    """A page nobody links to can only be found from the contents tree —
    which is fine for the welcome page and a sign of an island otherwise."""
    unlinked = [pid for pid, page in manual.pages.items()
                if not page.backlinks and pid != HOME]
    assert unlinked == [], f"no page links to: {unlinked}"


def test_links_go_both_ways(manual):
    for pid, page in manual.pages.items():
        for target in page.links:
            assert pid in manual.pages[target].backlinks


def test_pages_are_not_stubs(manual):
    """A page a few lines long is a heading with nothing under it."""
    short = [pid for pid, page in manual.pages.items() if len(page.text) < 600]
    assert short == [], f"pages under six hundred characters: {short}"


def test_search_finds_by_prefix_and_ranks_the_title_first(manual):
    hits = manual.search("integr")
    assert hits, "nothing mentions integration"
    assert hits[0].page.title.lower().find("integr") >= 0
    assert manual.search("") == []
    assert manual.search("zqxjwv") == []


def test_search_needs_every_word(manual):
    both = {hit.page.id for hit in manual.search("calibration weighting")}
    either = {hit.page.id for hit in manual.search("calibration")}
    assert both and both <= either


def test_a_wiki_link_can_carry_its_own_text(manual):
    rendered = render_markdown("See [[welcome|the first page]] and [[Welcome]].",
                               lambda m: f"<a>{m.group(2) or m.group(1)}</a>")
    assert "<a>the first page</a>" in rendered and "<a>Welcome</a>" in rendered


def test_markdown_subset_renders_what_the_pages_use():
    source = ("## Head\n\nA *b* **c** `d<e>` [f](http://g).\n\n"
              "| x | y |\n|---|---|\n| 1 | 2 |\n\n- one\n- two\n\n1. first\n2. second\n\n"
              "> quoted\n\n```\ncode & more\n```\n\n---\n")
    out = render_markdown(source)
    for piece in ("<h2>Head</h2>", "<i>b</i>", "<b>c</b>", "<code>d&lt;e&gt;</code>",
                  '<a href="http://g">f</a>', "<th>x</th>", "<td>2</td>",
                  "<ul><li>one</li><li>two</li></ul>", "<ol><li>first</li>",
                  "<blockquote>quoted</blockquote>", "<pre>code &amp; more</pre>", "<hr/>"):
        assert piece in out, piece


# --------------------------------------------------------------------------- #
# the manual in another language
# --------------------------------------------------------------------------- #
def test_every_language_declares_its_strings_and_its_sections():
    keys = set(STRINGS[DEFAULT_LANGUAGE])
    sections = {section for section, _ids in INDEX}
    for code in LANGUAGES:
        assert code in STRINGS, f"no strings for {code}"
        assert set(STRINGS[code]) == keys, f"strings differ for {code}"
        words = STRINGS[code]
        assert "{page}" in words["page_of"] and "{total}" in words["page_of"]
        assert "{version}" in words["intro"]
        if code == DEFAULT_LANGUAGE:
            continue
        assert set(SECTION_TITLES.get(code, {})) == sections, \
            f"section titles for {code} do not match the index"
        assert words["untranslated"], f"{code} has no note for an untranslated page"


def test_a_translation_is_the_same_pages_under_the_same_names(translated, manual):
    slugs = translated_slugs(translated.language)
    unknown = [pid for pid in slugs if pid not in manual.pages]
    assert unknown == [], \
        f"translated pages the English manual does not have: {unknown}"
    assert set(translated.pages) == set(manual.pages), \
        "a translated manual holds every page, translated or standing in"
    for pid in slugs:
        page = translated.pages[pid]
        assert page.translated and page.language == translated.language
        assert page.english_title == manual.pages[pid].title
    for pid in set(manual.pages) - set(slugs):
        assert not translated.pages[pid].translated


def test_a_translated_page_declares_a_title_of_its_own(translated):
    folder = pages_dir(translated.language)
    for pid in translated_slugs(translated.language):
        path = folder / f"{pid}.md"
        source = path.read_text(encoding="utf-8")
        assert source.startswith("---"), f"{path.name} has no front matter"
        front = source.split("---", 2)[1]
        assert "title:" in front, f"{path.name} declares no title"
        title, _body = read_page(path, pid)
        assert title and title[0].isupper(), f"{path.name}: {title!r}"
    # a title is what a link written by name resolves through, and two
    # pages answering to one title make that a coin toss
    titles = [page.title for page in translated.pages.values()]
    assert len(titles) == len(set(titles)), "two pages share a title"


def test_translated_pages_are_not_stubs(translated):
    short = [pid for pid in translated_slugs(translated.language)
             if len(translated.pages[pid].text) < 600]
    assert short == [], f"translated pages under six hundred characters: {short}"


def test_every_link_in_a_translation_resolves(translated):
    broken = {pid: page.unresolved for pid, page in translated.pages.items()
              if page.unresolved}
    assert broken == {}, f"links to pages that do not exist: {broken}"


def test_a_translation_links_both_ways_and_leaves_no_island(translated):
    for pid, page in translated.pages.items():
        for target in page.links:
            assert pid in translated.pages[target].backlinks
    unlinked = [pid for pid, page in translated.pages.items()
                if not page.backlinks and pid != HOME]
    assert unlinked == [], f"no page links to: {unlinked}"


def test_a_page_with_no_translation_falls_back_and_says_so(translated, manual):
    missing = translated.untranslated
    if not missing:
        pytest.skip(f"every page is translated into {translated.language}")
    page = translated.pages[missing[0]]
    original = manual.pages[page.id]
    assert page.markdown == original.markdown and page.title == original.title
    assert page.language == DEFAULT_LANGUAGE
    note = STRINGS[translated.language]["untranslated"]
    assert note in page.html, "a page standing in for a translation says nothing"
    assert note not in page.text, "the note is furniture, not text to search"


def test_a_translation_shows_its_sections_in_its_own_language(translated):
    table = SECTION_TITLES[translated.language]
    assert [section for section, _pages in translated.sections()] == \
        [table[section] for section, _ids in INDEX]
    # a section is identified in English the way a page is by its file name
    assert translated.section_of(HOME) == INDEX[0][0]
    assert translated.pages[HOME].section == table[INDEX[0][0]]


def test_search_reads_the_language_shown(translated):
    slugs = translated_slugs(translated.language)
    if not slugs:
        pytest.skip(f"nothing is translated into {translated.language} yet")
    for pid in slugs:
        page = translated.pages[pid]
        # a long plain word, so that the query is one term and the term is
        # the whole of it: the index is built with the same tokeniser
        words = re.findall(r"(?<![\w-])[a-z]{7,}(?![\w-])", page.text.lower())
        assert words, f"{pid} has no word to search for"
        # a common word can be on more pages than the search window shows;
        # the question is whether the page is found at all, so ask for all
        hits = translated.search(words[0], limit=len(translated.pages))
        found = {hit.page.id for hit in hits}
        assert pid in found, f"searching {words[0]!r} does not find {pid}"


def test_the_printed_translation_carries_its_own_furniture(translated):
    document = translated.html_document()
    words = STRINGS[translated.language]
    assert words["contents"] in document and words["document_title"] in document
    for section in SECTION_TITLES[translated.language].values():
        assert section in document, section


# --------------------------------------------------------------------------- #
# the window and the printed copy
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_window_opens_on_the_home_page_and_follows_links(qapp, manual):
    from PyQt6 import QtCore
    from milq.ui.help_window import HelpWindow

    window = HelpWindow(manual=manual)
    assert window.current_page == HOME
    target = manual.pages[HOME].links[0]
    window._link_clicked(QtCore.QUrl(f"help:{target}"))
    assert window.current_page == target
    window.back()
    assert window.current_page == HOME
    window.forward()
    assert window.current_page == target
    window.search.setText("calibration")
    assert window.hits.count() > 0
    window.hits.setCurrentRow(0)
    assert window.current_page == window.hits.item(0).data(QtCore.Qt.ItemDataRole.UserRole)
    window.close()


def test_the_shell_opens_the_manual_from_its_help_menu(qapp):
    from milq.ui.shell import MainShell

    shell = MainShell()
    shell.show_manual("peak-review")
    assert shell._help_window.current_page == "peak-review"
    shell._help_window.close()
    shell.close()


def test_the_manual_prints_as_many_pages_with_ink_on_them(qapp, manual, tmp_path):
    pdf = pytest.importorskip("PyQt6.QtPdf")
    from PyQt6 import QtCore

    path = manual.write_pdf(tmp_path / "manual.pdf")
    document = pdf.QPdfDocument(None)
    document.load(path)
    assert document.pageCount() >= 20
    image = document.render(3, QtCore.QSize(600, 848))
    assert not image.isNull()
    lowest = 0
    for y in range(image.height()):
        for x in range(0, image.width(), 3):
            if image.pixelColor(x, y).lightness() < 200:
                lowest = y
                break
    assert lowest > image.height() * 0.6


def test_the_module_level_manual_is_read_once(manual):
    first = manual_module.manual()
    assert manual_module.manual() is first
    for code in TRANSLATIONS:
        other = manual_module.manual(code)
        assert other is manual_module.manual(code) and other is not first
        assert other.language == code


def test_a_translated_manual_prints(qapp, translated, tmp_path):
    """The whole thing, in the language it is being read in."""
    pdf = pytest.importorskip("PyQt6.QtPdf")

    path = translated.write_pdf(tmp_path / f"manual-{translated.language}.pdf")
    document = pdf.QPdfDocument(None)
    document.load(path)
    assert document.pageCount() > 1


def test_the_window_switches_language_keeps_the_page_and_remembers(qapp):
    from milq.ui.help_window import SETTING_LANGUAGE, HelpWindow
    from milq.ui.settings import settings

    if not TRANSLATIONS:
        pytest.skip("the manual has only one language")
    store = settings()
    store.setValue(SETTING_LANGUAGE, DEFAULT_LANGUAGE)
    store.sync()
    window = HelpWindow()
    try:
        assert window.manual.language == DEFAULT_LANGUAGE
        window.show_page("peak-review")
        for code in TRANSLATIONS:
            window.set_language(code)
            assert window.manual.language == code
            assert window.current_page == "peak-review"
            assert window.language.currentData() == code
            sections = {window.tree.topLevelItem(row).text(0)
                        for row in range(window.tree.topLevelItemCount())}
            assert sections == set(SECTION_TITLES[code].values())
            assert settings().value(SETTING_LANGUAGE, type=str) == code
        window.set_language(DEFAULT_LANGUAGE)
        assert window.manual.language == DEFAULT_LANGUAGE
        assert window.current_page == "peak-review"
    finally:
        window.close()
        store = settings()
        store.setValue(SETTING_LANGUAGE, DEFAULT_LANGUAGE)
        store.sync()


def test_a_new_window_opens_in_the_language_last_read(qapp):
    from milq.ui.help_window import SETTING_LANGUAGE, HelpWindow
    from milq.ui.settings import settings

    if not TRANSLATIONS:
        pytest.skip("the manual has only one language")
    code = TRANSLATIONS[0]
    store = settings()
    store.setValue(SETTING_LANGUAGE, code)
    store.sync()
    try:
        window = HelpWindow()
        assert window.manual.language == code
        assert window.language.currentData() == code
        assert window.current_page == HOME
        window.close()
    finally:
        store = settings()
        store.setValue(SETTING_LANGUAGE, DEFAULT_LANGUAGE)
        store.sync()
