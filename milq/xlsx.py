"""
A spreadsheet, written without a spreadsheet library.

CSV is what one table looks like; a batch is a dozen of them, and handing
somebody twelve files named `results (3).csv` is not handing them a batch.
An `.xlsx` is a zip of XML parts, and the part of the format a report needs
— sheets of typed cells, a bold heading row, column widths — is small
enough to write directly. That keeps the dependencies at numpy, PyQt6 and
pyqtgraph, which is what the installers are built from.

What is written is deliberately the plain subset:

* **Inline strings** (`t="inlineStr"`), so there is no shared-strings table
  to keep in step with the cells that point into it. It costs bytes in a
  file nobody stores by the thousand and removes a whole class of mistake.
* **Numbers stay numbers.** A number written as text is a number that will
  not sum, sort or plot, and that is the one thing a spreadsheet is for.
  `None` is an empty cell — not a zero, and not the string "None".
* **Dates are text.** A real date cell is a serial number counting from an
  epoch the file has to declare, and the only dates here are acquisition
  timestamps that came out of an instrument as text in the first place.
* **No formulas, no charts, no merged cells.** Nothing that has to be
  recalculated to be right.

Every number format below is display only: the value in the cell is the
full one the results carry, so a column shown to three decimals still sums
and plots to all of them.

The zip entries carry a fixed timestamp, so writing the same sheets twice
gives byte-identical files and two builds can be compared the way
`--digest` compares the readers.
"""

from __future__ import annotations

import datetime as _dt
import re
import zipfile
from dataclasses import dataclass, field

#: the sheet-name characters Excel refuses, plus the apostrophe it refuses
#: at either end of a name
_BAD_NAME = re.compile(r"[\[\]:*?/\\]")

#: XML 1.0 has no way to write these at all, escaped or otherwise
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

#: Excel's own limit
MAX_NAME = 31

#: the number formats a sheet may name for a column, as their format codes.
#: `None`, the default, is General: everything the value has, shown as
#: Excel sees fit. These only change what is displayed.
FORMATS: dict[str, str] = {
    "integer": "#,##0",
    "area": "#,##0.0",
    "time": "0.000",
    "mass": "0.0000",
    "decimal": "#,##0.0000",
    "percent": "0.00",
}

#: numFmtId 0-163 are reserved by the format; custom ones start here
_FIRST_FMT_ID = 164

#: style indices into `cellXfs`, in the order `_styles` writes them
_STYLE_DEFAULT = 0
_STYLE_HEADER = 1
_STYLE_FIRST_FORMAT = 2

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_PKG_R = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

#: what every entry in the zip is stamped with, so the same sheets give the
#: same bytes. The earliest a zip can express.
_EPOCH = (1980, 1, 1, 0, 0, 0)


@dataclass
class Sheet:
    """One tab: a heading row, the rows under it, and how wide to draw it."""

    name: str
    header: list[str]
    rows: list[list] = field(default_factory=list)
    #: column widths in characters; None lets the reader decide
    widths: list[float] | None = None
    #: per-column number format, by name from `FORMATS`; None is General.
    #: Shorter than the header is fine — the rest are General.
    formats: list[str | None] | None = None

    @property
    def is_empty(self) -> bool:
        return not self.rows


# --------------------------------------------------------------------------- #
# the small pieces
# --------------------------------------------------------------------------- #
def escape(value: str) -> str:
    """XML text: the three characters that must be escaped, and no others."""
    text = _CONTROL.sub("", value)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def sheet_name(raw: str, taken: set[str] | None = None) -> str:
    """
    A name Excel will open, and one no other sheet in the book has.

    Excel refuses `[ ] : * ? / \\`, an apostrophe at either end, an empty
    name, and anything past thirty-one characters — and refuses the whole
    file rather than the sheet, which is why this is not left to the caller.
    """
    name = _BAD_NAME.sub("-", _CONTROL.sub("", str(raw or ""))).strip()
    name = name.strip("'")
    name = name[:MAX_NAME].strip() or "Sheet"
    if taken is None:
        return name
    if name not in taken:
        taken.add(name)
        return name
    for index in range(2, 1000):
        suffix = f" ({index})"
        candidate = name[:MAX_NAME - len(suffix)].strip() + suffix
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    raise ValueError(f"cannot find a free sheet name for {raw!r}")


def column_letter(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    if index < 0:
        raise ValueError("column indices start at zero")
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _is_number(value) -> bool:
    """
    A number the cell should hold as one.

    `bool` is an `int` in Python and TRUE is not 1 in a spreadsheet anybody
    reads, so it is written as text like any other word.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _cell(reference: str, value, style: int) -> str:
    if value is None or value == "":
        # an empty cell, not a zero and not the word "None". Written anyway
        # when it carries a style, so a formatted column stays formatted.
        return f'<c r="{reference}" s="{style}"/>' if style else ""
    if _is_number(value):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            # a spreadsheet has no way to hold these; say so rather than
            # write a cell no reader can open
            return (f'<c r="{reference}" s="{style}" t="inlineStr">'
                    f"<is><t>{escape(repr(value))}</t></is></c>")
        text = repr(int(value)) if isinstance(value, int) else repr(number)
        return f'<c r="{reference}" s="{style}">' f"<v>{text}</v></c>"
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        value = value.isoformat(sep=" ") if isinstance(value, _dt.datetime) \
            else value.isoformat()
    text = escape(str(value))
    space = ' xml:space="preserve"' if text != text.strip() else ""
    return (f'<c r="{reference}" s="{style}" t="inlineStr">'
            f"<is><t{space}>{text}</t></is></c>")


def _row(index: int, values: list, styles: list[int]) -> str:
    cells = []
    for column, value in enumerate(values):
        style = styles[column] if column < len(styles) else _STYLE_DEFAULT
        cells.append(_cell(f"{column_letter(column)}{index}", value, style))
    return f'<row r="{index}">' + "".join(cells) + "</row>"


def _worksheet(sheet: Sheet, format_style: dict[str, int]) -> str:
    columns = max([len(sheet.header)] + [len(row) for row in sheet.rows] or [0])
    styles = []
    for index in range(columns):
        name = (sheet.formats[index]
                if sheet.formats and index < len(sheet.formats) else None)
        styles.append(format_style.get(name, _STYLE_DEFAULT) if name
                      else _STYLE_DEFAULT)

    body = [_row(1, list(sheet.header), [_STYLE_HEADER] * columns)]
    for offset, row in enumerate(sheet.rows):
        body.append(_row(offset + 2, list(row), styles))

    last = column_letter(max(columns - 1, 0))
    parts = [_DECL,
             f'<worksheet xmlns="{_NS}" xmlns:r="{_NS_R}">',
             f'<dimension ref="A1:{last}{len(sheet.rows) + 1}"/>',
             '<sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
             'state="frozen"/></sheetView></sheetViews>',
             '<sheetFormatPr defaultRowHeight="15"/>']
    if sheet.widths:
        cols = []
        for index, width in enumerate(sheet.widths[:columns]):
            if not width:
                continue
            cols.append(f'<col min="{index + 1}" max="{index + 1}" '
                        f'width="{float(width):.2f}" customWidth="1"/>')
        if cols:
            parts.append("<cols>" + "".join(cols) + "</cols>")
    parts.append("<sheetData>" + "".join(body) + "</sheetData>")
    if sheet.rows:
        parts.append(f'<autoFilter ref="A1:{last}{len(sheet.rows) + 1}"/>')
    parts.append("</worksheet>")
    return "".join(parts)


def _styles(used: list[str]) -> tuple[str, dict[str, int]]:
    """
    The stylesheet, and where each named format landed in `cellXfs`.

    Only the formats a sheet actually names are written, so a workbook of
    plain text carries no number formats at all.
    """
    numbers = {name: _FIRST_FMT_ID + index for index, name in enumerate(used)}
    fmts = "".join(f'<numFmt numFmtId="{fid}" formatCode="{escape(FORMATS[name])}"/>'
                   for name, fid in numbers.items())
    xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>',
           '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" '
           'applyFont="1"/>']
    style_of = {}
    for offset, name in enumerate(used):
        style_of[name] = _STYLE_FIRST_FORMAT + offset
        xfs.append(f'<xf numFmtId="{numbers[name]}" fontId="0" fillId="0" '
                   f'borderId="0" xfId="0" applyNumberFormat="1"/>')
    sheet = (
        f"{_DECL}<styleSheet xmlns=\"{_NS}\">"
        + (f'<numFmts count="{len(numbers)}">{fmts}</numFmts>' if numbers else "")
        + '<fonts count="2">'
          '<font><sz val="11"/><name val="Calibri"/></font>'
          '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        # index 0 must be none and index 1 gray125; Excel rejects a
        # stylesheet whose fills do not start that way
        + '<fills count="2"><fill><patternFill patternType="none"/></fill>'
          '<fill><patternFill patternType="gray125"/></fill></fills>'
        + '<borders count="1"><border><left/><right/><top/><bottom/>'
          "<diagonal/></border></borders>"
        + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
          'borderId="0"/></cellStyleXfs>'
        + f'<cellXfs count="{len(xfs)}">' + "".join(xfs) + "</cellXfs>"
        + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" '
          'builtinId="0"/></cellStyles>'
        + "</styleSheet>")
    return sheet, style_of


def _content_types(count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index + 1}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.'
        f'spreadsheetml.worksheet+xml"/>' for index in range(count))
    return (
        f'{_DECL}<Types xmlns="{_NS_CT}">'
        '<Default Extension="rels" ContentType="application/'
        'vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}"
        '<Override PartName="/xl/styles.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>")


def _workbook(names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index + 1}" '
        f'r:id="rId{index + 1}"/>' for index, name in enumerate(names))
    return (f'{_DECL}<workbook xmlns="{_NS}" xmlns:r="{_NS_R}">'
            f"<sheets>{sheets}</sheets></workbook>")


def _workbook_rels(count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index + 1}" Type="{_NS_R}/worksheet" '
        f'Target="worksheets/sheet{index + 1}.xml"/>' for index in range(count))
    rels += (f'<Relationship Id="rId{count + 1}" Type="{_NS_R}/styles" '
             f'Target="styles.xml"/>')
    return f'{_DECL}<Relationships xmlns="{_NS_PKG_R}">{rels}</Relationships>'


def _root_rels() -> str:
    return (f'{_DECL}<Relationships xmlns="{_NS_PKG_R}">'
            f'<Relationship Id="rId1" Type="{_NS_R}/officeDocument" '
            f'Target="xl/workbook.xml"/></Relationships>')


# --------------------------------------------------------------------------- #
def write_xlsx(path: str, sheets: list[Sheet]) -> str:
    """
    Write the sheets as one `.xlsx`, and return the path written.

    A workbook with no sheet at all is a file Excel will not open, so an
    empty list is refused here rather than at the far end.
    """
    if not sheets:
        raise ValueError("a workbook needs at least one sheet")
    path = str(path)
    if not path.lower().endswith(".xlsx"):
        path += ".xlsx"

    taken: set[str] = set()
    names = [sheet_name(sheet.name, taken) for sheet in sheets]

    used: list[str] = []
    for sheet in sheets:
        for name in sheet.formats or []:
            if name and name in FORMATS and name not in used:
                used.append(name)
    styles, style_of = _styles(used)

    parts = {
        "[Content_Types].xml": _content_types(len(sheets)),
        "_rels/.rels": _root_rels(),
        "xl/workbook.xml": _workbook(names),
        "xl/_rels/workbook.xml.rels": _workbook_rels(len(sheets)),
        "xl/styles.xml": styles,
    }
    for index, sheet in enumerate(sheets):
        parts[f"xl/worksheets/sheet{index + 1}.xml"] = _worksheet(sheet, style_of)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            info = zipfile.ZipInfo(name, date_time=_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, text.encode("utf-8"))
    return path
