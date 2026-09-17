"""
The method as a Skyline transition list.

The file has never been imported into Skyline — there is no copy of it on
the machine this was written on — so what can be tested is what is
claimed: that the headers are the documented ones, spelled exactly, and
that every value in a row is the method's rather than an invention. What
the method cannot supply is left empty and counted, and these check that
too: a blank charge that is reported is a question for the analyst, and a
guessed one is a wrong answer nobody sees.
"""

import csv
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import skyline  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.method import ProcessingMethod  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _method(*components: Component) -> ProcessingMethod:
    method = ProcessingMethod()
    method.replace_all(list(components))
    return method


def _read(path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames), list(reader)


def test_the_headers_are_skylines_own_spelling():
    """
    Skyline matches without regard to case or spaces, but a file a person
    also reads should be spelled the way the documentation spells it.
    """
    assert skyline.HEADER == [
        "Molecule List Name", "Molecule Name", "Precursor m/z",
        "Precursor Charge", "Product m/z", "Product Charge",
        "Explicit Retention Time", "Explicit Retention Time Window", "Note"]


def test_a_transition_carries_the_methods_numbers(tmp_path):
    method = _method(Component(
        name="PC 34:1", precursor=760.5851, fragment=184.0733, rt=11.42,
        rt_halfwidth=0.6, group="phosphatidylcholines", adduct="[M+H]+"))
    path = tmp_path / "transitions.csv"
    listing = skyline.write_transition_list(method, path)
    header, rows = _read(path)

    assert header == skyline.HEADER
    assert len(rows) == 1 and not listing.without_charge
    row = rows[0]
    assert row["Molecule List Name"] == "phosphatidylcholines"
    assert row["Molecule Name"] == "PC 34:1"
    assert row["Precursor m/z"] == "760.5851"
    assert row["Product m/z"] == "184.0733"
    assert row["Explicit Retention Time"] == "11.420"


def test_the_window_written_is_the_whole_width_not_the_half(tmp_path):
    """Skyline's window is the full width; the method carries half of it."""
    method = _method(Component(name="A", precursor=100.0, fragment=50.0,
                               rt=5.0, rt_halfwidth=0.6, adduct="[M-H]-"))
    path = tmp_path / "t.csv"
    skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    assert rows[0]["Explicit Retention Time Window"] == "1.200"


def test_the_charge_is_signed_and_comes_from_the_adduct(tmp_path):
    method = _method(
        Component(name="neg", precursor=100.0, fragment=50.0, adduct="[M-H]-"),
        Component(name="pos", precursor=100.0, fragment=50.0, adduct="[M+H]+"),
        Component(name="two", precursor=100.0, fragment=50.0,
                  adduct="[M-2H]2-"),
    )
    path = tmp_path / "t.csv"
    listing = skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    charges = [(row["Precursor Charge"], row["Product Charge"]) for row in rows]
    assert charges == [("-1", "-1"), ("1", "1"), ("-2", "-1")]
    assert not listing.without_charge
    # a fragment's charge is not in the method: the polarity is the
    # precursor's and the magnitude is one, which is stated, not derived
    assert skyline.product_charge(-2) == -1
    assert skyline.product_charge(None) is None


def test_a_component_with_no_adduct_gets_no_charge_rather_than_a_guess(tmp_path):
    method = _method(Component(name="A", precursor=100.0, fragment=50.0),
                     Component(name="B", precursor=200.0, fragment=60.0,
                               adduct="M (neutral)"))
    path = tmp_path / "t.csv"
    listing = skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    assert [row["Precursor Charge"] for row in rows] == ["", ""]
    assert [row["Product Charge"] for row in rows] == ["", ""]
    assert listing.without_charge == ["A", "B"]
    assert "without a charge" in listing.summary()
    assert skyline.charge_of(Component(name="x", precursor=1.0)) is None


def test_a_component_with_no_fragment_is_written_precursor_to_precursor(tmp_path):
    """The same rule the acquisition schedule uses, and it is counted."""
    method = _method(Component(name="A", precursor=413.2661, adduct="[M-H]-"))
    path = tmp_path / "t.csv"
    listing = skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    assert rows[0]["Product m/z"] == rows[0]["Precursor m/z"] == "413.2661"
    assert listing.without_fragment == ["A"]


def test_a_component_with_no_retention_time_is_written_without_one(tmp_path):
    method = _method(Component(name="A", precursor=100.0, fragment=50.0,
                               adduct="[M-H]-"))
    path = tmp_path / "t.csv"
    listing = skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    assert rows[0]["Explicit Retention Time"] == ""
    assert rows[0]["Explicit Retention Time Window"] == ""
    assert listing.without_time == ["A"]


def test_the_note_says_what_the_columns_cannot(tmp_path):
    method = _method(
        Component(name="IS", precursor=767.6, fragment=184.07,
                  is_internal_standard=True, adduct="[M+H]+"),
        Component(name="A", precursor=760.5, fragment=184.07,
                  internal_standard="IS", adduct="[M+H]+"),
        Component(name="A qual", precursor=760.5, fragment=104.1,
                  qualifier_of="A", adduct="[M+H]+"),
    )
    path = tmp_path / "t.csv"
    skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    notes = {row["Molecule Name"]: row["Note"] for row in rows}
    assert notes["IS"] == skyline.IS_NOTE
    assert notes["A"] == "reported against IS"
    assert notes["A qual"] == "qualifier of A"


def test_a_component_with_no_group_is_filed_under_a_list_all_the_same(tmp_path):
    """Skyline puts every molecule in a list; a blank name makes one
    called nothing, which is worse than a plain default."""
    method = _method(Component(name="A", precursor=100.0, fragment=50.0,
                               adduct="[M-H]-"))
    path = tmp_path / "t.csv"
    skyline.write_transition_list(method, path)
    _header, rows = _read(path)
    assert rows[0]["Molecule List Name"] == skyline.DEFAULT_LIST


def test_an_invalid_component_is_left_out_and_said_to_be(tmp_path):
    method = _method(Component(name="", precursor=0.0),
                     Component(name="A", precursor=100.0, adduct="[M-H]-"))
    path = tmp_path / "t.csv"
    listing = skyline.write_transition_list(method, path)
    assert len(listing.rows) == 1
    assert listing.skipped == ["(unnamed)"]
    assert "1 left out" in listing.summary()


def test_an_empty_method_writes_a_header_and_says_there_was_nothing(tmp_path):
    path = tmp_path / "t.csv"
    listing = skyline.write_transition_list(ProcessingMethod(), path)
    header, rows = _read(path)
    assert header == skyline.HEADER and rows == []
    assert "nothing to write" in listing.summary()


def test_the_extension_is_added_when_it_is_missing(tmp_path):
    method = _method(Component(name="A", precursor=100.0, adduct="[M-H]-"))
    skyline.write_transition_list(method, tmp_path / "transitions")
    assert os.path.exists(tmp_path / "transitions.csv")


# --------------------------------------------------------------------------- #
# the button that calls it
# --------------------------------------------------------------------------- #
def test_the_method_workspace_writes_the_list_and_reports_what_is_missing(
        qapp, tmp_path, monkeypatch):
    """
    Whatever the method could not supply is said in the status line, where
    the analyst is, rather than left for Skyline's import to complain about
    somewhere else entirely.
    """
    from PyQt6 import QtWidgets

    from milq.session import Session
    from milq.ui.method_workspace import MethodWorkspace

    session = Session()
    session.set_components([
        Component(name="PC 34:1", precursor=760.5851, fragment=184.0733,
                  rt=11.42, adduct="[M+H]+"),
        Component(name="no adduct", precursor=700.0, fragment=184.0733),
    ])
    workspace = MethodWorkspace(session)
    said: list[str] = []
    workspace.sigStatus.connect(said.append)
    path = tmp_path / "transitions.csv"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(path), "")))
    workspace.export_skyline()

    header, rows = _read(path)
    assert header == skyline.HEADER and len(rows) == 2
    assert said and "1 without a charge" in said[-1]
    from milq.ui.help_window import help_page_for
    assert help_page_for(workspace.btn_skyline) == "export"
    workspace.close()
