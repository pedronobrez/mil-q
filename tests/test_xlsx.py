"""
The spreadsheet written without a spreadsheet library.

An `.xlsx` that will not open is a file nobody finds out about until they
are in front of the person they wrote it for, and the failure is silent:
Excel refuses the whole workbook over one bad sheet name and says nothing
useful about which. So these open every file they write — unzip it, parse
every XML part, and read the cells back — rather than trusting that a zip
of plausible XML is a workbook.

Reading it back is done here, in about thirty lines, and on purpose: the
project depends on numpy, PyQt6 and pyqtgraph, and a test that needed
openpyxl to prove the writer works would put a dependency in the suite that
the installers do not carry. What the reader below checks is the same thing
a spreadsheet checks — the parts named by `[Content_Types].xml` exist, the
relationships point at them, and each cell says what its type is.
"""

import os
import xml.etree.ElementTree as ET
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import report  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.calibration import Calibration, CalibrationPoint  # noqa: E402
from milq.quantify import PeakResult, ResultsSet  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from milq.session import Session  # noqa: E402
from milq.xlsx import (FORMATS, Sheet, column_letter, escape,  # noqa: E402
                            sheet_name, write_xlsx)

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# --------------------------------------------------------------------------- #
# a reader, so the tests read the file rather than the code that wrote it
# --------------------------------------------------------------------------- #
def read_workbook(path) -> dict[str, list[list]]:
    """Every sheet as its rows, in the book's order, values typed."""
    book = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        # the relationship names each sheet's part; the workbook names the tab
        rels = {}
        for node in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")):
            rels[node.attrib["Id"]] = node.attrib["Target"]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rid = "{http://schemas.openxmlformats.org/officeDocument/2006/" \
              "relationships}id"
        for node in workbook.findall("m:sheets/m:sheet", NS):
            part = "xl/" + rels[node.attrib[rid]]
            assert part in names, part
            book[node.attrib["name"]] = _rows(archive.read(part))
    return book


def _column_of(reference: str) -> int:
    """`C7` → 2. An empty cell is simply absent, so the reference is the
    only thing that says which column a cell is in."""
    index = 0
    for character in reference:
        if not character.isalpha():
            break
        index = index * 26 + (ord(character.upper()) - ord("A") + 1)
    return index - 1


def _rows(data: bytes) -> list[list]:
    rows = []
    for row in ET.fromstring(data).findall("m:sheetData/m:row", NS):
        cells: dict[int, object] = {}
        for cell in row.findall("m:c", NS):
            if cell.attrib.get("t") == "inlineStr":
                text = cell.find("m:is/m:t", NS)
                value = "" if text is None else (text.text or "")
            else:
                number = cell.find("m:v", NS)
                value = None if number is None else float(number.text)
            cells[_column_of(cell.attrib["r"])] = value
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(index) for index in range(width)])
    return rows


def styles_of(path) -> list[list[str | None]]:
    """Each sheet's cells as their style indices, to check the header is bold."""
    out = []
    with zipfile.ZipFile(path) as archive:
        index = 1
        while f"xl/worksheets/sheet{index}.xml" in archive.namelist():
            sheet = ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
            out.append([[cell.attrib.get("s")
                         for cell in row.findall("m:c", NS)]
                        for row in sheet.findall("m:sheetData/m:row", NS)])
            index += 1
    return out


def number_formats(path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        styles = ET.fromstring(archive.read("xl/styles.xml"))
    return [node.attrib["formatCode"]
            for node in styles.findall("m:numFmts/m:numFmt", NS)]


# --------------------------------------------------------------------------- #
# the pieces
# --------------------------------------------------------------------------- #
def test_column_letters_carry_past_z():
    assert column_letter(0) == "A"
    assert column_letter(25) == "Z"
    assert column_letter(26) == "AA"
    assert column_letter(27) == "AB"
    assert column_letter(51) == "AZ"
    assert column_letter(702) == "AAA"
    with pytest.raises(ValueError):
        column_letter(-1)


def test_the_three_characters_that_must_be_escaped_are():
    assert escape("a & b < c > d") == "a &amp; b &lt; c &gt; d"
    # quotes are text in an element, and escaping them makes them unreadable
    assert escape('say "so"') == 'say "so"'
    # a control character cannot be written in XML at all, escaped or not
    assert escape("a\x00b\x07c") == "abc"


def test_a_sheet_name_is_one_excel_will_open():
    assert sheet_name("Results") == "Results"
    assert sheet_name("a/b\\c:d*e?f[g]h") == "a-b-c-d-e-f-g-h"
    assert sheet_name("'quoted'") == "quoted"
    assert sheet_name("") == "Sheet"
    assert len(sheet_name("x" * 60)) == 31


def test_two_sheets_cannot_end_up_with_one_name():
    taken: set[str] = set()
    first = sheet_name("Results", taken)
    second = sheet_name("Results", taken)
    third = sheet_name("Results", taken)
    assert [first, second, third] == ["Results", "Results (2)", "Results (3)"]
    long = sheet_name("y" * 40, taken)
    again = sheet_name("y" * 40, taken)
    assert long != again and len(again) <= 31


# --------------------------------------------------------------------------- #
# the file
# --------------------------------------------------------------------------- #
def test_every_part_is_well_formed_xml_and_named_in_the_content_types(tmp_path):
    path = write_xlsx(tmp_path / "book.xlsx",
                      [Sheet("One", ["a"], [[1]]), Sheet("Two", ["b"], [[2]])])
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        for name in names:
            ET.fromstring(archive.read(name))       # every part parses
        types = archive.read("[Content_Types].xml").decode()
    for wanted in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                   "xl/_rels/workbook.xml.rels", "xl/styles.xml",
                   "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
        assert wanted in names, wanted
    assert "/xl/worksheets/sheet2.xml" in types
    assert "/xl/styles.xml" in types


def test_an_extension_is_added_and_an_empty_book_refused(tmp_path):
    path = write_xlsx(tmp_path / "book", [Sheet("One", ["a"], [[1]])])
    assert path.endswith(".xlsx") and os.path.exists(path)
    with pytest.raises(ValueError):
        write_xlsx(tmp_path / "empty.xlsx", [])


def test_numbers_stay_numbers_and_nothing_becomes_the_word_none(tmp_path):
    """
    The one thing a spreadsheet is for is arithmetic on its cells, and a
    number written as text does none. `None` is an empty cell — not a zero,
    which is a measurement, and not "None", which is a word.
    """
    path = write_xlsx(tmp_path / "types.xlsx", [Sheet(
        "Types", ["text", "float", "int", "none", "empty", "bool"],
        [["x", 1.5, 7, None, "", True],
         ["y", -0.000125, 0, None, "", False]])])
    rows = read_workbook(path)["Types"]
    assert rows[0] == ["text", "float", "int", "none", "empty", "bool"]
    # an empty cell is absent from the file; the reader pads it back as None
    assert rows[1] == ["x", 1.5, 7.0, None, None, "True"]
    assert rows[2] == ["y", -0.000125, 0.0, None, None, "False"]


def test_a_number_keeps_every_digit_it_arrived_with(tmp_path):
    """Formats are display; the value in the cell is the measured one."""
    area = 10618.253906251
    path = write_xlsx(tmp_path / "digits.xlsx",
                      [Sheet("A", ["area"], [[area]], formats=["area"])])
    assert read_workbook(path)["A"][1][0] == area
    assert FORMATS["area"] in number_formats(path)


def test_the_header_row_is_bold_and_the_rows_under_it_are_not(tmp_path):
    path = write_xlsx(tmp_path / "bold.xlsx",
                      [Sheet("A", ["h1", "h2"], [["a", "b"]])])
    header, first = styles_of(path)[0]
    assert header == ["1", "1"], "the heading row does not carry the bold style"
    assert set(first) <= {"0", None}


def test_markup_in_a_value_or_a_name_comes_back_as_it_went_in(tmp_path):
    """A component called `PC 34:1 <d7> & co` is a component, not markup."""
    name = "PC 34:1 <d7> & co"
    path = write_xlsx(tmp_path / "escape.xlsx",
                      [Sheet("R&D <all>", ["a & b"], [[name], ["  padded  "]])])
    book = read_workbook(path)
    assert "R&D <all>" in book
    rows = book["R&D <all>"]
    assert rows[0] == ["a & b"]
    assert rows[1] == [name]
    assert rows[2] == ["  padded  "], "leading and trailing spaces were lost"


def test_a_forbidden_sheet_name_is_fixed_rather_than_written(tmp_path):
    path = write_xlsx(tmp_path / "names.xlsx",
                      [Sheet("ceramides/sphingomyelins", ["a"], [[1]]),
                       Sheet("ceramides:sphingomyelins", ["a"], [[2]])])
    names = list(read_workbook(path))
    assert names == ["ceramides-sphingomyelins",
                     "ceramides-sphingomyelins (2)"]


def test_widths_and_the_frozen_heading_are_written(tmp_path):
    path = write_xlsx(tmp_path / "cols.xlsx",
                      [Sheet("A", ["a", "b"], [[1, 2]], widths=[30, 0])])
    with zipfile.ZipFile(path) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert 'width="30.00"' in sheet
    assert 'max="2"' not in sheet, "a width of zero should be left to the reader"
    assert 'state="frozen"' in sheet


def test_writing_the_same_sheets_twice_gives_the_same_bytes(tmp_path):
    """A build that can be compared byte for byte is worth the fixed stamp."""
    sheets = [Sheet("A", ["a"], [["x", 1.0]])]
    first = write_xlsx(tmp_path / "one.xlsx", sheets)
    second = write_xlsx(tmp_path / "two.xlsx", sheets)
    assert open(first, "rb").read() == open(second, "rb").read()


def test_a_book_with_no_formats_carries_no_number_formats(tmp_path):
    path = write_xlsx(tmp_path / "plain.xlsx", [Sheet("A", ["a"], [["x"]])])
    assert number_formats(path) == []


# --------------------------------------------------------------------------- #
# the batch as a workbook
# --------------------------------------------------------------------------- #
def _session() -> Session:
    session = Session()
    session.entries = [
        SampleEntry("/d/STD_L1.wiff", 0, "STD_L1", "Standard", 5.0, 1.0, ""),
        SampleEntry("/d/QC01.wiff", 0, "QC01", "Quality Control", 75.0, 2.0,
                    "spiked", "batch A"),
    ]
    session.set_components([
        Component(name="PC 34:1", precursor=760.5851, fragment=184.0733,
                  rt=11.42, rt_halfwidth=0.6, tolerance=0.02,
                  group="phosphatidylcholines",
                  internal_standard="PC 34:1 (d7)"),
        Component(name="PC 34:1 (d7)", precursor=767.6289, fragment=184.0733,
                  rt=11.40, rt_halfwidth=0.6, tolerance=0.02,
                  is_internal_standard=True, min_response=5240.0),
    ])
    session.results = ResultsSet.from_list([])
    for entry, area in zip(session.entries, (8100.5, 10618.25)):
        name = entry.name
        row = PeakResult(sample_key=entry.key, sample_name=name,
                         component="PC 34:1")
        row.rt, row.expected_rt, row.area = 11.398, 11.42, area
        row.height, row.width, row.snr, row.points = 47020.5, 0.13, None, 3
        row.area_ratio, row.algorithm = 0.4271, "valley"
        row.internal_standard = "PC 34:1 (d7)"
        row.flags, row.note, row.status = ["RT drift"], "checked", "Pass"
        session.results.replace(row)
    curve = Calibration(
        component="PC 34:1", regression="linear", weighting="1/x",
        coefficients=[2.5, 0.75], r2=0.9993, r=0.99965,
        points=[CalibrationPoint(session.entries[0].key, "STD_L1", 5.0, 13.25)])
    session.calibrations = {"PC 34:1": curve}
    return session


def test_a_workbook_holds_a_sheet_per_section_with_content(tmp_path):
    session = _session()
    path = report.export_workbook(session, tmp_path / "batch.xlsx")
    book = read_workbook(path)
    assert list(book) == ["Results", "Calibration", "Statistics", "Batch QC",
                          "Method", "Samples"]
    session.calibrations.clear()
    book = read_workbook(report.export_workbook(session, tmp_path / "b2.xlsx"))
    assert "Calibration" not in book, "an empty section should not be a tab"


def test_the_results_sheet_is_one_row_per_result_with_its_flags(tmp_path):
    """
    The report moves flags and notes into footnotes because an A4 page has
    ten columns in it. A sheet has no page, so they are columns.
    """
    session = _session()
    book = read_workbook(report.export_workbook(session, tmp_path / "b.xlsx"))
    header, *rows = book["Results"]
    assert len(rows) == 2
    row = dict(zip(header, rows[0]))
    assert row["Sample"] == "STD_L1"
    assert row["Sample type"] == "Standard"
    assert row["Component"] == "PC 34:1"
    assert row["Area"] == 8100.5
    assert row["RT"] == 11.398
    assert row["Ratio to IS"] == 0.4271
    assert row["Flags"] == "RT drift"
    assert row["Note"] == "checked"
    assert row["Used"] == "yes"
    # the noise could not be measured, so there is no ratio to report and the
    # cell is empty rather than a zero that would sort like a bad result
    assert "S/N" not in row or row.get("S/N") is None


def test_the_calibration_sheet_carries_the_slope_and_the_intercept(tmp_path):
    session = _session()
    book = read_workbook(report.export_workbook(session, tmp_path / "b.xlsx"))
    header, row = book["Calibration"]
    values = dict(zip(header, row))
    assert values["Component"] == "PC 34:1"
    assert values["Model"] == "linear"
    assert values["Weighting"] == "1/x"
    assert values["Slope"] == 2.5 and values["Intercept"] == 0.75
    assert values["Points used"] == 1.0
    assert values["r²"] == 0.9993


def test_a_quadratic_states_no_slope_rather_than_inventing_one(tmp_path):
    session = _session()
    session.calibrations["PC 34:1"] = Calibration(
        component="PC 34:1", regression="quadratic",
        coefficients=[0.1, 2.0, 0.5], r2=0.999,
        points=[CalibrationPoint("k", "STD_L1", 5.0, 13.25)])
    book = read_workbook(report.export_workbook(session, tmp_path / "b.xlsx"))
    header, row = book["Calibration"]
    values = dict(zip(header, row))
    assert "Slope" not in values or values.get("Slope") is None
    assert "x²" in values["Equation"]


def test_the_method_and_samples_sheets_hold_the_tables(tmp_path):
    session = _session()
    book = read_workbook(report.export_workbook(session, tmp_path / "b.xlsx"))
    header, *rows = book["Method"]
    values = [dict(zip(header, row)) for row in rows]
    assert [v["Component"] for v in values] == ["PC 34:1", "PC 34:1 (d7)"]
    assert values[0]["Precursor"] == 760.5851
    assert values[1]["IS"] == "yes" and values[1]["Min. response"] == 5240.0
    assert values[0].get("IS") is None, "a blank column, not a column of no"

    header, *rows = book["Samples"]
    samples = [dict(zip(header, row)) for row in rows]
    assert [s["Sample"] for s in samples] == ["STD_L1", "QC01"]
    assert samples[1]["Group"] == "batch A"
    assert samples[1]["Dilution"] == 2.0


def test_a_method_on_its_own_is_a_workbook_of_one_sheet(tmp_path):
    session = Session()
    session.set_components([Component(name="PC 34:1", precursor=760.5851)])
    book = read_workbook(report.export_workbook(session, tmp_path / "m.xlsx"))
    assert list(book) == ["Method"]


def test_an_empty_session_says_so_rather_than_writing_a_file(tmp_path):
    """A workbook of no sheets is a file no spreadsheet will open."""
    with pytest.raises(ValueError):
        report.export_workbook(Session(), tmp_path / "nothing.xlsx")
    assert not os.path.exists(tmp_path / "nothing.xlsx")


# --------------------------------------------------------------------------- #
# the menu item that calls it
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_shell_exports_the_open_batch_from_its_file_menu(
        qapp, tmp_path, monkeypatch):
    from PyQt6 import QtWidgets

    from milq.ui.shell import MainShell

    shell = MainShell()
    shell.session.set_components(
        [Component(name="PC 34:1", precursor=760.5851, fragment=184.0733)])
    path = tmp_path / "batch.xlsx"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(path), "")))
    shell.export_workbook()
    assert list(read_workbook(path)) == ["Method"]
    assert "Workbook written" in shell.statusBar().currentMessage()
    # an export is not a save: the session is still unsaved, and closing it
    # would put up the modal that asks about that
    shell.session._mark_clean()
    shell.close()


def test_an_empty_session_is_refused_before_a_dialog_is_shown(qapp, monkeypatch):
    """Nothing to export is a status line, not a file dialog and an error."""
    from PyQt6 import QtWidgets

    from milq.ui.shell import MainShell

    shell = MainShell()

    def refuse(*_args, **_kwargs):
        raise AssertionError("a file dialog was opened for an empty session")

    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        staticmethod(refuse))
    shell.export_workbook()
    assert "before exporting" in shell.statusBar().currentMessage()
    shell.close()
