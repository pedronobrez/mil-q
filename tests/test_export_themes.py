"""
The print themes: paper, black and white, dark.

A theme is a claim about where the thing is going — a journal that prints in
no colour, a slide with a dark ground — so the assertions here are made off
the pixels and off the contrast arithmetic rather than off the palette's own
fields. Three questions, and each is asked of a rendering:

* are the two black-and-white traces still two traces once the picture is
  greyscale, and does the dash pattern survive the halving a journal does to
  a figure;
* does every colour a dark drawing uses clear the 3:1 that WCAG asks of a
  line carrying meaning, on the ground it is drawn on;
* is a black-and-white report actually black and white on the printed page —
  no tinted row, nothing with a hue in it at all.

The label placement is deliberately not re-measured per theme: `paint` takes
its geometry from the fonts and the data and never from the palette, so the
existing measurement holds — but the picture is checked in all three anyway,
because that is the assertion that would catch a palette reaching into the
geometry. The one thing a palette does move is a label above a stick that
has grown a head, since a head is ink; that is measured below rather than
assumed away.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtWidgets              # noqa: E402

from milq import report                            # noqa: E402
from milq import spectra_compare as sc             # noqa: E402
from milq.ui import export_theme                   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# --------------------------------------------------------------------------- #
# the pictures
# --------------------------------------------------------------------------- #
def profile(peaks, lo=100.0, hi=800.0, step=0.005, width=0.012):
    mz = np.arange(lo, hi, step)
    y = np.zeros(mz.size)
    for centre, height in peaks:
        y += height * np.exp(-0.5 * ((mz - centre) / width) ** 2)
    return mz, y


def comparison(centroid: bool = False):
    """Two spectra, head to tail, the way a comparison is exported."""
    a = profile([(184.0733, 100000), (301.1, 32000), (430.35, 51000),
                 (703.5749, 41000)])
    b = profile([(184.0733, 61000), (301.1, 12000), (359.287, 88000),
                 (731.6062, 52000)])
    return sc.SpectrumComparison(
        traces=[sc.SpectrumTrace("QC01 · scan 12", *a, "#234b8c"),
                sc.SpectrumTrace("QC02 · scan 14", *b, "#e08a1e")],
        title="QC01 against QC02", normalise=True, mirror=True,
        centroid=centroid)


def greyscale(image) -> np.ndarray:
    """The image as one L value per pixel, rows by columns."""
    converted = image.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
    bits = converted.constBits()
    bits.setsize(converted.sizeInBytes())
    flat = np.frombuffer(bits, np.uint8).reshape(converted.height(),
                                                 converted.bytesPerLine())
    return flat[:, :converted.width()].astype(np.int16)


def _without_labels(image, layout, scale):
    """The greyscale picture with the label text painted out.

    A label is ink too, and in black and white it is the same black as the
    first trace: measuring a trace's tone means measuring the trace.
    """
    grey = greyscale(image)
    for label in layout.placed:
        x0, y0 = int(label.x * scale), int(label.y * scale)
        x1 = int((label.x + label.width) * scale) + 1
        y1 = int((label.y + label.height) * scale) + 1
        grey[max(y0, 0):y1, max(x0, 0):x1] = 255
    return grey


def _halves(grey):
    """The ink above and below the zero line, which is the row with most of
    it — every trace's baseline and the axis lie along it."""
    dark = grey < 200
    zero = int(np.argmax(dark.sum(axis=1)))
    upper, lower = grey[:zero - 3], grey[zero + 4:]
    return upper[upper < 200], lower[lower < 200]


def test_every_palette_draws_the_comparison_on_its_own_ground(qapp, tmp_path):
    for palette in (sc.PAPER, sc.MONO, sc.DARK):
        path = sc.render_png(comparison(), tmp_path / f"{palette.name}.png",
                             palette=palette)
        image = QtGui.QImage(path)
        assert not image.isNull()
        assert (image.width(), image.height()) == (
            int(sc.DEFAULT_WIDTH * sc.PRINT_SCALE),
            int(sc.DEFAULT_HEIGHT * sc.PRINT_SCALE))
        corner = image.pixelColor(2, 2)
        assert corner == QtGui.QColor(palette.background), (
            f"{palette.name} did not paint its own ground")
    for palette in (sc.PAPER, sc.MONO, sc.DARK):
        written = sc.render_svg(comparison(), tmp_path / f"{palette.name}.svg",
                                palette=palette)
        assert os.path.getsize(written) > 1000


def test_the_two_black_and_white_traces_differ_in_greyscale(qapp):
    """
    Measured off the pixels of a greyscale conversion, which is what a
    press does to a colour figure: the upper trace's ink is black and the
    lower's is the palette's grey, #666666, which converts to L 102.
    Rendered on the real CA-d4 pair the two halves came out at a median
    L of 0 and 102 with the label text masked; the synthetic pair below is
    the same measurement with no raw file to hand.
    """
    scale = sc.PRINT_SCALE
    image, layout = sc._draw(comparison(), sc.DEFAULT_WIDTH, sc.DEFAULT_HEIGHT,
                             scale, sc.MONO)
    upper, lower = _halves(_without_labels(image, layout, scale))
    assert upper.size > 500 and lower.size > 500, "nothing was drawn to measure"
    assert int(np.median(upper)) < 40, "the first trace is not black"
    # the median of the masked lower half is 102 on macOS and Linux and read
    # 60 on the Windows runner — which turned out not to be antialiasing but
    # a renderer with no fonts at all, drawing every label as a box of ink;
    # `api.offscreen_fonts` gives the offscreen platform %WINDIR%\Fonts and
    # a Windows 11 machine then measures 102 like the others. The bound
    # stays wide until a runner confirms that, and it is not what the test
    # rests on: the count of pixels at exactly 102 below is what says the
    # grey belongs to the second trace
    assert 40 < int(np.median(lower)) < 130, "the second trace is not the grey"
    assert int(np.median(lower)) - int(np.median(upper)) > 50, (
        "the two traces are the same tone once the colour is gone")
    # and the grey is the second trace's alone: on the real CA-d4 pair it is
    # the commonest tone in the lower half of the picture and appears nowhere
    # in the upper one, and on this sparser pair the second half of that
    # still holds
    assert int(np.bincount(np.clip(upper, 0, 255)).argmax()) == 0
    # the palette's grey converts to exactly 102, and that value belongs to
    # the second trace: the antialiasing of black ink lands on it a few
    # dozen times a picture, and the second trace lands on it thousands
    here, elsewhere = int((lower == 102).sum()), int((upper == 102).sum())
    assert here > 1000, f"the grey trace is barely drawn: {here} pixels"
    assert here > elsewhere * 10, (
        f"L 102 is as common above the line ({elsewhere}) as below ({here}), "
        f"so it is not the second trace's own tone")


def test_the_dash_survives_the_figure_being_halved(qapp):
    """
    A journal prints a figure at half the size it was given. The pen is
    measured where it draws one straight uninterrupted run that nothing
    else is drawn over — the legend's own line, 18 points of the very pen
    the trace is drawn with — at print scale and again at half of it.
    """
    def runs(image, index):
        grey = greyscale(image)
        scale = image.width() / sc.DEFAULT_WIDTH
        row = int(round((sc.MARGIN_TOP + sc.TITLE_HEIGHT
                         + index * sc.LEGEND_ROW + sc.LEGEND_ROW / 2) * scale))
        x0 = int(round(sc.MARGIN_LEFT * scale))
        strip = grey[row, x0:int(round((sc.MARGIN_LEFT + 18) * scale))]
        ink = strip < 200
        return int(np.sum(ink[1:] != ink[:-1])) + 1, ink

    full = sc.render_image(comparison(), scale=sc.PRINT_SCALE, palette=sc.MONO)
    half = full.scaled(full.width() // 2, full.height() // 2,
                       QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                       QtCore.Qt.TransformationMode.SmoothTransformation)
    for image, what in ((full, "at print scale"), (half, "halved")):
        solid, solid_ink = runs(image, 0)
        dashed, dashed_ink = runs(image, 1)
        assert solid == 1 and solid_ink.all(), f"the first trace is dashed {what}"
        assert dashed >= 3, f"the dash did not survive {what}"
        assert dashed_ink.any() and not dashed_ink.all(), (
            f"the second trace has no gaps {what}")


def test_every_dark_trace_colour_clears_three_to_one_on_the_dark_ground(qapp):
    """
    Three to one is what WCAG asks of a graphic that carries meaning, and
    the measurement is the ratio itself, not a promise about a hex value.
    Every colour the interface hands a trace is put through the palette on
    its own ground.
    """
    wanted = ("#234b8c", "#e08a1e", "#6f9be0", "#e0a844", "#2f9e6a",
              "#b03030", "#1a1d21", "#e6e8eb")
    for palette in (sc.PAPER, sc.MONO, sc.DARK):
        for index, colour in enumerate(wanted):
            drawn = palette.colour(index, colour).name()
            ratio = palette.contrast(drawn)
            assert ratio >= sc.MIN_CONTRAST, (
                f"{palette.name}: {colour} drawn as {drawn} is only "
                f"{ratio:.2f}:1 on {palette.background}")


def test_the_measured_dark_figures_are_the_ones_the_manual_prints(qapp):
    """The numbers written in `report.md` and in the manual's Portuguese
    twin, so that changing a palette changes the page as well."""
    measured = {"#234b8c": ("#336ecd", 3.28), "#e08a1e": ("#e08a1e", 6.03),
                "#6f9be0": ("#6f9be0", 5.73)}
    for wanted, (expected, ratio) in measured.items():
        drawn = sc.DARK.colour(0, wanted)
        assert drawn.name() == expected
        assert round(sc.DARK.contrast(drawn.name()), 2) == ratio
    assert round(sc.MONO.contrast("#666666"), 2) == 5.74
    assert round(sc.MONO.contrast("#000000"), 2) == 21.0


def _trace_ink(colour) -> bool:
    """Is this pixel a trace? Everything else in the drawing is neutral."""
    channels = (colour.red(), colour.green(), colour.blue())
    return max(channels) - min(channels) > 40


def _hued(palette):
    """
    The same palette with its traces given a hue.

    `MONO` draws its traces in the same black as its label text, so a pixel
    cannot say which it is. Colour enters no part of the placement — the
    geometry comes from the fonts and the data — so a palette differing only
    in the two trace colours draws exactly the same ink, and the ink can then
    be told from the text. Nothing else is changed: the dashes and the heads,
    which do move the ink, are the palette's own.
    """
    import dataclasses

    if not palette.traces:
        return palette
    return dataclasses.replace(palette, traces=("#c02020", "#2020c0"))


@pytest.mark.parametrize("name", ["paper", "mono", "dark"])
def test_a_label_is_never_drawn_over_a_trace_in_any_theme(qapp, name):
    palette = sc.PALETTES[name]
    image, layout = sc._draw(comparison(), sc.DEFAULT_WIDTH,
                             sc.DEFAULT_HEIGHT, 1.0, _hued(palette))
    assert layout.drawn > 5, "nothing was drawn to check"
    over = []
    for label in layout.placed:
        x0, y0 = int(label.x) + 1, int(label.y) + 1
        x1, y1 = int(label.x + label.width) - 1, int(label.y + label.height) - 1
        if any(_trace_ink(image.pixelColor(x, y))
               for y in range(y0, y1) for x in range(x0, x1)):
            over.append(label.text)
    assert not over, f"{name}: drawn over the trace: {over}"


def test_the_geometry_is_the_same_in_every_theme(qapp):
    """A palette is colour and line style, so a profile drawing puts the
    same labels in the same places in all three."""
    layouts = {name: sc.label_layout(comparison(), palette=sc.PALETTES[name])
               for name in ("paper", "mono", "dark")}
    reference = [(p.text, round(p.x, 3), round(p.y, 3))
                 for p in layouts["paper"].placed]
    assert len(reference) > 5, "nothing was drawn to compare"
    for name in ("mono", "dark"):
        assert [(p.text, round(p.x, 3), round(p.y, 3))
                for p in layouts[name].placed] == reference


def _sticks():
    """The same comparison as centroids, thinned to its real peaks."""
    sticks = comparison(centroid=True)
    for trace in sticks.traces:
        keep = trace.intensity > trace.intensity.max() * 0.01
        trace.mz, trace.intensity = trace.mz[keep], trace.intensity[keep]
    return sticks


def test_a_head_is_ink_and_the_label_above_it_moves(qapp):
    """
    The one way a palette reaches the placement, measured rather than
    assumed away: a head drawn on a stick is ink, and a label clears ink.
    The same masses are named — nothing is lost and nothing new is drawn —
    and every label over a headed stick sits a row further out with a
    leader. On the two averaged CA-d4 spectra as centroids: 32 named and 1
    dropped in both, 14 lifted on paper against 28 in black and white.
    """
    sticks = _sticks()
    paper = sc.label_layout(sticks, palette=sc.PAPER)
    mono = sc.label_layout(sticks, palette=sc.MONO)
    assert [p.text for p in paper.placed] == [p.text for p in mono.placed]
    assert paper.dropped == mono.dropped
    assert mono.lifted > paper.lifted, "the heads moved no label"
    assert all(p.leader for p in mono.placed if p.lift)


def test_a_stick_gets_a_head_where_a_dash_cannot_show(qapp):
    """
    A centroid drawing is sticks one point wide and a dash pattern on one
    of those is invisible, so black and white marks the tall sticks
    instead: filled for the first trace, hollow for the second, and the
    legend carries the head rather than a dash so the two can be matched.
    """
    sticks = _sticks()
    plain = sc.render_image(sticks, scale=1.0, palette=sc.PAPER)
    marked = sc.render_image(sticks, scale=1.0, palette=sc.MONO)
    assert sc.MONO.head(0) == "filled" and sc.MONO.head(1) == "hollow"
    # the heads are ink the paper drawing does not have
    grey_plain = greyscale(plain)
    grey_marked = greyscale(marked)
    assert (grey_marked < 200).sum() > (grey_plain < 200).sum(), (
        "the heads drew nothing")


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
def _session(qapp):
    from milq.components import Component
    from milq.samples import SampleEntry
    from milq.session import Session

    session = Session()
    session.entries = [
        SampleEntry("/d/STD_L1.wiff", 0, "STD_L1", "Standard", 5.0, 1.0, ""),
        SampleEntry("/d/QC01.wiff", 0, "QC01", "Quality Control", 75.0, 2.0,
                    "spiked")]
    session.set_components([
        Component(name="PC 34:1", precursor=760.5851, fragment=184.0733,
                  rt=11.42, rt_halfwidth=0.6, tolerance=0.02),
        Component(name="PC 34:1 (d7)", precursor=767.6289, fragment=184.0733,
                  rt=11.40, rt_halfwidth=0.6, tolerance=0.02,
                  is_internal_standard=True)])
    return session


def test_the_three_styles_are_offered_and_paper_is_what_it_was(qapp):
    assert set(report.THEMES) == {"paper", "mono", "dark"}
    assert report.style_for("paper") == report._STYLE
    assert report.style_for("nonsense") == report._STYLE
    assert report.theme_named(None) == "paper"
    session = _session(qapp)
    assert report.build_html(session) == report.build_html(session,
                                                           theme="paper")
    for theme in report.THEMES:
        document = report.build_html(session, theme=theme)
        assert document.startswith("<!DOCTYPE html>")
        assert report.style_for(theme) in document
        assert "Samples</h2>" in document


def test_black_and_white_tints_nothing(qapp):
    """
    The style sheet first: a tint is a `background`, and there is not one
    in it — striped rows and shaded heading cells become rules, because a
    4% tint reproduces as either nothing or a smudge.
    """
    assert "background" not in report.style_for("mono")
    assert "background" in report.style_for("paper")
    assert "tr.alt td" in report.style_for("paper")
    assert "tr.alt td" not in report.style_for("mono")


def test_a_dark_report_is_for_the_screen_and_says_so(qapp, tmp_path):
    session = _session(qapp)
    assert "dark" not in report.PRINTABLE_THEMES
    with pytest.raises(ValueError) as raised:
        report.write_pdf(session, tmp_path / "dark.pdf", theme="dark")
    assert "screen" in str(raised.value)
    # the web page is where it belongs, and it is written
    path = report.write_html(session, tmp_path / "dark.html", theme="dark")
    assert "#1e2124" in open(path, encoding="utf-8").read()


def _pixels(image) -> np.ndarray:
    # `frombuffer` views the converted image's memory, and the converted
    # image is a local: returned as a view it dangled, and Windows reused the
    # memory before the assertion read it (an access violation in CI where
    # macOS and Linux read the freed bytes without noticing). Copied while
    # the image is alive.
    image = image.convertToFormat(QtGui.QImage.Format.Format_RGB32)
    bits = image.constBits()
    bits.setsize(image.sizeInBytes())
    view = np.frombuffer(bits, np.uint8).reshape(
        image.height(), image.bytesPerLine() // 4, 4)[:, :image.width(), :3]
    return view.copy()


#: coloured pixels a renderer may leave on a page drawn without colour
#: (Ubuntu 24.04's QtPdf: 8 of 1,144,800); a tinted cell is thousands
MONO_STRAY_PIXELS = 100


def test_the_printed_black_and_white_page_has_no_colour_on_it(qapp, tmp_path):
    """
    Measured on the page rather than in the style sheet: a page rendered
    from the PDF must be neutral everywhere — every pixel's red, green and
    blue within a point of one another — while the same report on paper is
    not, because its headings and its heading cells carry the project's
    blue. That is the tinted rows and the coloured type in one assertion.

    "Neutral" is measured, not zero: Ubuntu's PDF renderer leaves 8 pixels
    with a spread above 2 on the mono page (macOS leaves none), where the
    paper page measures 313,697 and one tinted heading cell alone is
    thousands, so `MONO_STRAY_PIXELS` is the floor under the renderer and
    not under the theme.
    """
    pdf = pytest.importorskip("PyQt6.QtPdf")

    session = _session(qapp)
    paths = {theme: report.write_pdf(session, tmp_path / f"{theme}.pdf",
                                     title="A batch", theme=theme)
             for theme in ("paper", "mono")}
    spread = {}
    for theme, path in paths.items():
        document = pdf.QPdfDocument(None)
        document.load(path)
        image = document.render(0, QtCore.QSize(900, 1272))
        assert not image.isNull()
        pixels = _pixels(image).astype(int)
        spread[theme] = int((pixels.max(axis=2) - pixels.min(axis=2)).max())
        if theme == "mono":
            coloured = int(((pixels.max(axis=2)
                             - pixels.min(axis=2)) > 2).sum())
            assert coloured <= MONO_STRAY_PIXELS, \
                f"{coloured} coloured pixels on a mono page"
    assert spread["paper"] > 20, "the paper report lost its colour"


def test_a_black_and_white_report_draws_its_pictures_in_black_and_white(qapp):
    """A report is one document: a black and white report holding a
    four-colour spectrum is not a black and white report."""
    session = _session(qapp)
    session.spectra_comparison = comparison()
    assert report.picture_palette("mono") is sc.MONO
    assert report.picture_palette("paper") is sc.PAPER
    assert report.picture_palette("anything else") is sc.PAPER
    plain = report.build_html(session, sections=("spectra",))
    mono = report.build_html(session, sections=("spectra",), theme="mono")
    assert 'src="data:image/png;base64,' in mono
    assert plain != mono, "the picture did not follow the theme"


# --------------------------------------------------------------------------- #
# the choice, and where it is kept
# --------------------------------------------------------------------------- #
def test_the_theme_chosen_for_an_export_is_remembered(qapp):
    from milq.ui.settings import settings

    store = settings()
    try:
        export_theme.remember("mono", store)
        assert store.value(export_theme.SETTING, "", type=str) == "mono"
        assert export_theme.remembered(store) == "mono"
        # a theme a dialog cannot offer falls back without disturbing it
        assert export_theme.remembered(
            store, allowed=report.PRINTABLE_THEMES) == "mono"
        export_theme.remember("dark", store)
        assert export_theme.remembered(
            store, allowed=report.PRINTABLE_THEMES) == "paper"
        assert export_theme.remembered(store) == "dark"
        export_theme.remember("nonsense", store)
        assert export_theme.remembered(store) == "paper"
    finally:
        store.remove(export_theme.SETTING)


def test_the_chooser_offers_what_the_dialog_allows(qapp):
    from milq.ui.settings import settings

    store = settings()
    try:
        export_theme.remember("mono", store)
        dialog = QtWidgets.QFileDialog()
        box = export_theme.add_theme_box(dialog, store)
        assert [box.itemData(i) for i in range(box.count())] == \
            list(export_theme.THEMES)
        assert export_theme.chosen_theme(box) == "mono"
        box.setCurrentIndex(box.findData("dark"))
        assert export_theme.chosen_theme(box) == "dark"

        printed = QtWidgets.QFileDialog()
        limited = export_theme.add_theme_box(printed, store,
                                             allowed=report.PRINTABLE_THEMES)
        assert [limited.itemData(i) for i in range(limited.count())] == \
            list(report.PRINTABLE_THEMES)
        assert limited.itemText(1) == "Black and white"
        dialog.deleteLater()
        printed.deleteLater()
    finally:
        store.remove(export_theme.SETTING)
