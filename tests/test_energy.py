"""
Which collision energy and activation explains a standard best.

Three recommendations from one table, and the thing worth testing is that
each is made on the rule it claims and says so. So most of what follows
builds a compound sprayed at three energies with one figure moved, and
reads back which condition was picked and what the reason names.

The rest is the shape: a compound sprayed once, a row the isolation verdict
contradicts, the two-block CSV, the paragraph the report gains, and the
dialog offscreen.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import energy  # noqa: E402
from milq import infusion_report as ir  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Explanation:
    """What `explain.Explanation` is to everything that reads one here."""

    def __init__(self, matched, predicted, share):
        self.matched, self.predicted, self.share = matched, predicted, share
        self.name = "CA-d4"
        self.matches, self.considered = [], 12

    @staticmethod
    def unexplained(_peaks):
        """Everything in these spectra is accounted for, which is the case
        the report's sentence has the least to say about."""
        return []


def _verdict(precursor: float, agrees: bool) -> ir.IsolationVerdict:
    """A real verdict, so the flagging is the program's and not the test's."""
    fit = ir.Fit(name="CA-d4", formula="C24H36D4O5", adduct="[M+NH4]+",
                 mz=precursor, error_ppm=0.0, source="the standards table")
    isolation = ir.Isolation(precursor=precursor, start_mass=50.0,
                             end_mass=500.0, polarity="Positive",
                             tolerance=0.05,
                             named=(fit,) if agrees else ())
    return ir.IsolationVerdict(proposed="CA-d4", formula="C24H36D4O5",
                               resolved_from="the standards table", labels=4,
                               isolations=(isolation,))


def _row(compound="CA-d4", activation="EAD", ce=22.0, sample="",
         precursor=430.35, precursor_height=5000.0,
         fragments=((377.30, 2000.0), (395.31, 500.0), (358.28, 300.0)),
         matched=8, predicted=56, share=0.60, agrees=True, others=()):
    """
    One infusion as the Infusions tab hands it over.

    A real `InfusionRow` around a real `InfusionReport`: what this module
    reads is that contract, and a stub of it would test the stub. The
    activation and the energy are written into the file name where the
    acquisition does not declare them, which is what a folder of infusions
    looks like.
    """
    bits = [compound, "TOFMSMS"]
    if activation:
        bits.append(activation)
    bits.append(f"{ce:g}CE")
    name = "_".join(bits) + (f"_{sample}" if sample else "_mix1")
    peaks = [(precursor, precursor_height)] if precursor_height else []
    peaks += [(mz, height) for mz, height in fragments]
    report = ir.InfusionReport(
        compound=compound, sample=name, file=f"/tray/{name}.wiff",
        polarity="Positive", channel=f"TOF PI {precursor:g}, CE {ce:g}",
        channel_name="TOF PI", written_precursor=precursor,
        collision_energy=ce, scans=300,
        survivor=((precursor, precursor_height) if precursor_height
                  else None),
        explanation=(_Explanation(matched, predicted, share)
                     if matched is not None else None),
        basis="the formula C24H36D4O5 as [M+NH4]+",
        isolation=_verdict(precursor, agrees))
    return ir.InfusionRow(report=report, peaks=peaks, others=list(others))


def _Summary(rows):
    """A real `InfusionSummary`, because the panel reads one and a stub of
    it would test the stub."""
    return ir.InfusionSummary(rows=list(rows))


def _three():
    """One compound at three energies: 12, 22 and 45 eV.

    12 eV barely fragments — the precursor is nearly the whole spectrum, so
    the explained share is highest there and the fragments smallest. 22 eV
    finds the most predicted ions and holds the largest single fragment.
    45 eV has fragmented the precursor away entirely and scattered what is
    left over a long tail, which is what the real 45 eV infusion of this
    standard does: 179 peaks and 13% on the largest of them.
    """
    return _Summary([
        _row(ce=12.0, precursor_height=12000.0, matched=3, share=0.85,
             fragments=((78.05, 600.0), (81.07, 200.0), (94.04, 150.0))),
        _row(ce=22.0, precursor_height=9400.0, matched=8, share=0.64,
             fragments=((377.30, 9600.0), (395.31, 2500.0),
                        (358.28, 2400.0))),
        _row(ce=45.0, activation="", precursor_height=0.0, matched=2,
             share=0.24,
             fragments=((359.29, 5600.0), (217.19, 800.0), (358.28, 700.0))
             + tuple((100.0 + n, 900.0) for n in range(40))),
    ])


# --------------------------------------------------------------------------- #
# the table
# --------------------------------------------------------------------------- #
def test_one_condition_per_activation_and_energy():
    made = energy.recommend(_three())
    assert len(made) == 1
    recommendation = made[0]
    assert recommendation.compound == "CA-d4"
    assert [c.label for c in recommendation.considered] == [
        "45 eV", "EAD 12 eV", "EAD 22 eV"]
    assert recommendation.energies == [12.0, 22.0, 45.0]
    assert all(c.n == 1 for c in recommendation.conditions)


def test_the_two_denominators_are_the_ones_written():
    """The precursor against the base peak; everything else against the sum."""
    made = energy.recommend(_three())
    soft = next(c for c in made[0].conditions if c.energy == 12.0)
    # the precursor is the base peak of that spectrum, so it is all of it
    assert soft.precursor_share == pytest.approx(1.0)
    total = 12000.0 + 600.0 + 200.0 + 150.0
    assert soft.base_share == pytest.approx(12000.0 / total)
    assert soft.top.mz == pytest.approx(78.05)
    assert soft.top.share == pytest.approx(600.0 / total)


def test_the_precursor_is_never_offered_as_a_fragment():
    made = energy.recommend(_three())
    for condition in made[0].considered:
        for fragment in condition.fragments:
            assert condition.precursor_mz is None or abs(
                fragment.mz - condition.precursor_mz) > 0.01


# --------------------------------------------------------------------------- #
# the three rules
# --------------------------------------------------------------------------- #
def _choice(recommendation, purpose):
    return next(c for c in recommendation.choices if c.purpose == purpose)


def test_identification_takes_the_most_ions_with_a_surviving_precursor():
    made = energy.recommend(_three())
    choice = _choice(made[0], energy.IDENTIFICATION)
    assert choice.condition.label == "EAD 22 eV"
    assert "8 of the 56 ions predicted found" in choice.reason
    # and it says the precursor stood, which is the other half of the rule
    assert "precursor surviving at 9,400 counts" in choice.reason


def test_identification_refuses_when_no_precursor_survived():
    """Fragments without a precursor cannot say which ion they came from."""
    rows = _Summary([
        _row(ce=12.0, precursor_height=0.0, matched=3),
        _row(ce=22.0, precursor_height=0.0, matched=8),
    ])
    choice = _choice(energy.recommend(rows)[0], energy.IDENTIFICATION)
    assert choice.condition is None
    assert f"{energy.MIN_PRECURSOR:,.0f} counts" in choice.reason


def test_a_precursor_under_the_floor_does_not_count_as_survival():
    rows = _Summary([
        _row(ce=12.0, precursor_height=energy.MIN_PRECURSOR - 1, matched=9),
        _row(ce=22.0, precursor_height=energy.MIN_PRECURSOR + 1, matched=2),
    ])
    choice = _choice(energy.recommend(rows)[0], energy.IDENTIFICATION)
    assert choice.condition.energy == 22.0
    assert "left out for a precursor under that floor" not in choice.reason


def test_identification_breaks_a_tie_on_the_explained_share_and_says_so():
    rows = _Summary([
        _row(ce=22.0, matched=5, share=0.78),
        _row(ce=30.0, activation="", matched=5, share=0.73),
    ])
    choice = _choice(energy.recommend(rows)[0], energy.IDENTIFICATION)
    assert choice.condition.energy == 22.0
    assert "a tie with 1, taken on the explained share" in choice.reason


def test_quantitation_takes_the_largest_share_on_one_fragment():
    made = energy.recommend(_three())
    choice = _choice(made[0], energy.QUANTITATION)
    assert choice.condition.label == "EAD 22 eV"
    assert "377.3000 holds" in choice.reason
    # and it says the share is one measurement, because it is
    assert "not a repeat" in choice.reason


def test_quantitation_leaves_out_a_fragment_that_does_not_repeat():
    """Two sprays at one condition naming two different strongest masses."""
    rows = _Summary([
        _row(ce=22.0, sample="a", fragments=((377.30, 9000.0),
                                             (200.10, 100.0))),
        _row(ce=22.0, sample="b", fragments=((200.10, 9000.0),
                                             (377.30, 100.0))),
        _row(ce=30.0, activation="", fragments=((468.31, 3000.0),
                                                (467.30, 100.0))),
    ])
    made = energy.recommend(rows)[0]
    assert next(c for c in made.considered if c.energy == 22.0).n == 2
    choice = _choice(made, energy.QUANTITATION)
    assert choice.condition.energy == 30.0
    assert "left out for a strongest fragment that did not repeat" \
        in choice.reason


def test_quantitation_keeps_a_fragment_that_repeats():
    rows = _Summary([
        _row(ce=22.0, sample="a", fragments=((377.30, 9000.0),
                                             (200.10, 100.0))),
        _row(ce=22.0, sample="b", fragments=((377.30, 8800.0),
                                             (200.10, 100.0))),
        _row(ce=30.0, activation="", fragments=((468.31, 2000.0),
                                                (467.30, 900.0))),
    ])
    made = energy.recommend(rows)[0]
    condition = next(c for c in made.considered if c.energy == 22.0)
    stable, spread, why = condition.stability()
    assert stable is True
    assert spread < energy.STABLE_PERCENT
    assert "in all 2 infusions" in why
    assert _choice(made, energy.QUANTITATION).condition.energy == 22.0


def test_quantitation_refuses_when_nothing_but_the_precursor_is_there():
    rows = _Summary([_row(ce=12.0, fragments=()),
                     _row(ce=22.0, fragments=())])
    choice = _choice(energy.recommend(rows)[0], energy.QUANTITATION)
    assert choice.condition is None
    assert "no transition to quantify on" in choice.reason


def test_a_library_record_takes_the_middle_energy_measured():
    made = energy.recommend(_three())
    choice = _choice(made[0], energy.LIBRARY)
    assert choice.condition.energy == 22.0
    assert "the middle of the 3 energies measured (12, 22, 45 eV)" \
        in choice.reason
    # the softest energy has the highest explained share of the three and is
    # still not chosen: the middle comes first and the share only decides
    # among the candidates in the middle
    soft = next(c for c in made[0].considered if c.energy == 12.0)
    assert soft.explained > choice.condition.explained


def test_a_library_record_decides_an_even_count_on_the_explained_share():
    rows = _Summary([_row(ce=12.0, share=0.10), _row(ce=22.0, share=0.70),
                     _row(ce=30.0, share=0.40), _row(ce=45.0, share=0.20)])
    choice = _choice(energy.recommend(rows)[0], energy.LIBRARY)
    assert choice.condition.energy == 22.0
    assert "explaining 70.0% of its intensity against" in choice.reason


def test_no_energy_that_was_not_measured_is_ever_offered():
    made = energy.recommend(_three())
    measured = {c.label for c in made[0].considered}
    for choice in made[0].choices:
        assert choice.condition is None or choice.label in measured


# --------------------------------------------------------------------------- #
# one energy, and a row the method contradicts
# --------------------------------------------------------------------------- #
def test_one_energy_says_there_is_nothing_to_choose_between():
    made = energy.recommend(_Summary([_row(ce=22.0)]))
    assert made[0].note == energy.NOTHING_TO_CHOOSE
    assert made[0].choices == []
    assert energy.NOTHING_TO_CHOOSE in made[0].paragraph()


def test_two_infusions_at_one_condition_are_still_one_energy():
    made = energy.recommend(_Summary([_row(ce=22.0, sample="a"),
                                      _row(ce=22.0, sample="b")]))
    assert len(made[0].considered) == 1
    assert made[0].note == energy.NOTHING_TO_CHOOSE


def test_a_flagged_row_is_in_the_table_and_out_of_the_choice():
    """The two infusions the method contradicts: shown, marked, never picked."""
    rows = _Summary([
        _row(ce=12.0, precursor_height=12000.0, matched=3, share=0.85),
        _row(ce=22.0, precursor_height=9400.0, matched=8, share=0.64),
        _row(ce=45.0, activation="", precursor_height=0.0, matched=2,
             share=0.24),
        _row(ce=12.0, sample="TESTEARTIGO", precursor=839.56, agrees=False,
             matched=None, precursor_height=110.0),
        _row(ce=22.0, sample="TESTEARTIGO", precursor=839.56, agrees=False,
             matched=None, precursor_height=240.0),
    ])
    made = energy.recommend(rows)[0]
    assert len(made.conditions) == 5      # in the table
    assert len(made.considered) == 3      # out of the choice
    assert len(made.marked) == 2
    for choice in made.choices:
        assert choice.condition is None or choice.condition.considered
    # and a marked row never shares a condition with a kept one, which is
    # the whole point of grouping on the verdict as well as on the energy
    for condition in made.conditions:
        assert len({p.considered for p in condition.points}) == 1
    assert "no adduct" in made.rows()[-1][energy.COLUMNS.index("Considered")]


def test_a_flagged_row_does_not_decide_how_alike_the_others_look():
    """The mutual score is taken over the considered rows only."""
    kept = _row(ce=22.0)
    flagged = _row(ce=12.0, sample="TESTEARTIGO", precursor=839.56,
                   agrees=False, matched=None)
    other = _row(ce=45.0, activation="", sample="b")
    kept.others = [(other.report.sample, 0.80, 0.90, 5, 6),
                   (flagged.report.sample, 0.02, 0.05, 1, 40)]
    made = energy.recommend(_Summary([kept, flagged, other]))[0]
    condition = next(c for c in made.considered if c.energy == 22.0)
    assert condition.against_others == pytest.approx(0.80)
    assert condition.points[0].others == 1


def test_every_row_contradicted_leaves_nothing_to_choose():
    rows = _Summary([_row(ce=12.0, precursor=839.56, agrees=False),
                     _row(ce=22.0, precursor=839.56, agrees=False)])
    made = energy.recommend(rows)[0]
    assert made.choices == []
    assert "every infusion of this compound is one the method" in made.note


def test_compounds_are_kept_apart_and_sorted():
    made = energy.recommend(_Summary([
        _row(compound="TDCA-d4", ce=22.0), _row(compound="TDCA-d4", ce=30.0),
        _row(compound="CA-d4", ce=12.0), _row(compound="CA-d4", ce=22.0)]))
    assert [r.compound for r in made] == ["CA-d4", "TDCA-d4"]
    assert all(len(r.considered) == 2 for r in made)


# --------------------------------------------------------------------------- #
# what comes off it
# --------------------------------------------------------------------------- #
def test_the_csv_holds_the_table_and_the_reasons(tmp_path):
    import csv

    made = energy.recommend(_three())
    path = energy.write_csv(made, tmp_path / "energies.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == list(energy.COLUMNS)
    assert len(rows[1]) == len(energy.COLUMNS)
    blank = rows.index([])
    assert blank == 1 + len(made[0].conditions)
    assert rows[blank + 1] == list(energy.CHOICE_COLUMNS)
    reasons = rows[blank + 2:]
    assert [r[1] for r in reasons] == list(energy.PURPOSES)
    assert all(r[3] for r in reasons)          # every pick carries a reason


def test_the_csv_of_one_energy_writes_the_note(tmp_path):
    import csv

    made = energy.recommend(_Summary([_row(ce=22.0)]))
    path = energy.write_csv(made, tmp_path / "one.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[-1][-1] == energy.NOTHING_TO_CHOOSE


def test_the_summary_line_counts_conditions_and_picks():
    said = energy.summary_line(energy.recommend(_three()))
    assert "1 compound(s) over 3 condition(s)" in said
    assert "3 recommendation(s) made" in said


def test_the_paragraph_reaches_the_report_only_with_more_than_one():
    rows = _three().rows
    reports = ir.prepare_documents(rows)
    assert all(r.energy_advice for r in reports)
    assert "For identification" in reports[0].energy_advice
    # the sub-heading and not the words: the identity table at the top of
    # every section already has a *Collision energy* label in it
    section = ir.build_section(reports[0], heading="CA-d4")
    assert "<h3>Collision energy</h3>" in section
    assert "For a library record" in section

    alone = ir.prepare_documents([_row(ce=22.0)])
    assert alone[0].energy_advice == ""
    assert "<h3>Collision energy</h3>" not in ir.build_section(alone[0])


# --------------------------------------------------------------------------- #
# the dialog
# --------------------------------------------------------------------------- #
def test_the_dialog_shows_every_condition_and_writes_a_csv(qapp, tmp_path):
    from milq.ui.energy_dialog import EnergyDialog

    dialog = EnergyDialog(_three())
    assert dialog.table.rowCount() == 3
    assert dialog.table.columnCount() == len(energy.COLUMNS)
    said = dialog.advice.toPlainText()
    for purpose in energy.PURPOSES:
        assert purpose in said
    path = dialog.export_csv(str(tmp_path / "from-dialog.csv"))
    assert os.path.exists(path)
    assert "from-dialog.csv" in dialog.status.text()
    dialog.deleteLater()


def test_the_dialog_greys_a_row_that_is_out_of_the_choice(qapp):
    """The Considered cell is nineteen columns right of the compound, and a
    reader should not have to scroll to it to see that a row is marked."""
    from milq.ui import theme
    from milq.ui.energy_dialog import EnergyDialog

    rows = _three().rows + [_row(ce=12.0, sample="TESTEARTIGO",
                                 precursor=839.56, agrees=False,
                                 matched=None)]
    dialog = EnergyDialog(_Summary(rows))
    muted = theme.muted().lower()
    marked = dialog.table.rowCount() - 1
    assert dialog.table.item(marked, 0).foreground().color().name() == muted
    assert dialog.table.item(0, 0).foreground().color().name() != muted
    dialog.deleteLater()


def test_the_dialog_of_nothing_measured_says_so(qapp):
    from milq.ui.energy_dialog import EnergyDialog

    dialog = EnergyDialog(_Summary([]))
    assert dialog.table.rowCount() == 0
    assert "Measure" in dialog.advice.toPlainText()
    assert dialog.export_csv(str("unused.csv")) == ""
    dialog.deleteLater()


def test_the_button_waits_for_a_measurement(qapp):
    from milq.session import Session
    from milq.ui.infusions_panel import InfusionsPanel

    panel = InfusionsPanel(Session())
    assert not panel.btn_energy.isEnabled()
    assert panel.recommend_energies() is None
    assert "Measure first" in panel.status.text()

    panel.session.infusion_summary = _three()
    panel.reload()
    assert panel.btn_energy.isEnabled()
    dialog = panel.recommend_energies()
    assert dialog is not None and dialog.table.rowCount() == 3
    dialog.deleteLater()
    panel.deleteLater()
