"""
When a file's name and its acquisition method disagree about the compound.

A `.wiff` written by a manual acquisition calls its own sample `sample` and
names its method `Untitled 1.msm`; nothing in it, `TargetedCompoundInfo`
included, says what was sprayed. The compound is in the file name and only
there — which makes the name a proposal, and the precursor the method
isolates the one measurement of the same question the file actually holds.

So this is arithmetic between two numbers that were both written down before
the vial was sprayed, and the tests are arithmetic too: a formula resolved
from a name, every adduct of it against a written precursor, and the same
precursor offered to the component table and to a library when the name does
not fit. Nothing here reads a spectrum, which is why the fixtures do not
bother to have one worth reading.

The four answers a verdict is allowed to give — agrees, fits another
compound, fits nothing, could not be checked — each get a test, because the
last two are different findings and a program that confuses them is worse
than one that says neither.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from milq import infusion_report as ir  # noqa: E402
from milq.components import Component  # noqa: E402
from milq.library import LibraryEntry, SpectralLibrary  # noqa: E402
from milq.samples import SampleEntry  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

#: cholic acid-d4 as `[M+NH4]+`, which is what the real files' 430.34 and
#: 430.35 both are — the method carries two decimals and does not always
#: round them the same way
CA_D4_NH4 = 430.3465
#: deoxycholic acid-d4 as `[M+NH4]+`: a different bile acid, so a file named
#: for one whose method isolates this is naming the wrong compound
DCA_D4_NH4 = 414.3516
#: the sodiated dimer of *unlabelled* cholic acid — the one thing in this
#: chemistry that fits the 839.56 the two real `_TESTEARTIGO` acquisitions
#: isolate, and it fits at −5.2 ppm
CHOLIC_DIMER_NA = 839.5644


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FakeChannel:
    """Enough of `wiff.Channel` for the verdict: an info block and a flat TIC."""

    def __init__(self, index: int, precursor=None, start=100.0, end=1000.0,
                 polarity="Positive", energy=22.0, n=200, name="TOF PI"):
        self.index = index
        self._rt = np.linspace(0.0, 1.5, n)
        self._y = np.full(n, 50_000.0)
        self.info = ChannelInfo(
            index=index, name=name,
            experiment_type="Product" if precursor else "TOF MS",
            polarity=polarity, precursor=precursor,
            start_mass=start, end_mass=end, n_scans=n,
            collision_energy=energy if precursor else None)

    def tic(self):
        return self._rt, self._y

    @property
    def rt(self):
        return self._rt

    def bpc(self, *args, **kwargs):
        return self._rt, self._y

    # a spectrum only so that the report has something to average: the
    # verdict never reads one, and one peak at the isolated precursor is
    # enough for every block that draws
    def _spectrum(self):
        centre = self.info.precursor or self.info.start_mass
        mz = np.arange(centre - 0.1, centre + 0.1, 0.005)
        return mz, 5_000.0 * np.exp(-0.5 * ((mz - centre) / 0.008) ** 2)

    def spectrum(self, scan, add_zeros=True):
        return self._spectrum()

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        return self._spectrum()

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self._rt - rt)))

    def rt_at_scan(self, scan):
        return float(self._rt[int(np.clip(scan, 0, self._rt.size - 1))])

    def scans_in_range(self, rt_start, rt_end):
        return 0, self._rt.size - 1

    def xic(self, mz, tolerance=0.02, unit="Da"):
        return self._rt, self._y

    def xic_range(self, mz_lo, mz_hi):
        return self._rt, self._y

    def parameters(self):
        """The acquisition parameters Clearcore2 exposes, and no compound
        among them — which is the whole reason the verdict exists. The four
        the real ZenoTOF files carry, to the value they carry."""
        return {"DP": "44", "CE": f"{self.info.collision_energy:g}",
                "DPS": "0", "CES": "0"}


class FakeSample:
    """A manually acquired sample: named `sample`, like the real ones."""

    instrument = "ZenoTOF 7600 System"
    problem = None

    def __init__(self, channels, name="sample"):
        self.channels = list(channels)
        self.name = name

    def tic(self):
        rt = self.channels[0].rt
        return rt, np.sum([c.tic()[1] for c in self.channels], axis=0)

    def metadata(self):
        return {"Sample": self.name,
                "Method": r"D:\SCIEX OS Data\Acquisition Methods\Untitled 1.msm"}


def _entry(name: str, precursor, start=100.0, end=1000.0, polarity="Positive"):
    """One infused file, named `name`, whose method isolates `precursor`."""
    channel = FakeChannel(0, precursor=precursor, start=start, end=end,
                          polarity=polarity)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = FakeSample([channel])
    return entry


def _components():
    """A small method table: one bile acid with a formula, one without."""
    return [
        Component(name="DCA-d4", precursor=414.34, formula="C24H40O4",
                  adduct="[M+NH4]+"),
        Component(name="C17:0_Ceramide", precursor=552.5, formula=""),
    ]


def _library():
    """A library of one's own holding the sodiated cholic-acid dimer."""
    entry = LibraryEntry(name="Cholic acid dimer", precursor=839.56,
                         precursor_type="[M+Na]+", formula="C48H80O10",
                         mz=np.array([100.0, 200.0]),
                         intensity=np.array([1.0, 0.5]))
    return SpectralLibrary([entry], path="/d/own.msp")


# --------------------------------------------------------------------------- #
# the four answers
# --------------------------------------------------------------------------- #
def test_a_name_the_method_confirms_agrees_and_names_the_adduct():
    entry = _entry("CA-d4_TOFMSMS_EAD_22CE_mix1", CA_D4_NH4, 50.0, 500.0)
    verdict = ir.what_the_method_isolates(entry.sample, name=entry.name)

    assert verdict.judged and verdict.agrees and not verdict.disagrees
    # the labels the name declares and the standards table's formula does not
    assert verdict.formula == "C24H36D4O5"
    assert verdict.labels == 4
    assert verdict.resolved_from == "the standards table"
    fit = verdict.isolations[0].named[0]
    assert fit.adduct == "[M+NH4]+"
    assert fit.mz == pytest.approx(CA_D4_NH4, abs=1e-3)
    said = verdict.sentence()
    assert "is named CA-d4 and the method isolates" in said
    assert "[M+NH4]+ of C24H36D4O5" in said
    assert verdict.fit is None                  # nothing else needed asking


def test_a_written_precursor_is_taken_at_the_precision_it_was_typed_with():
    """`430.35` and `430.34` are the same channel written twice: the method
    carries two decimals, so a tolerance tighter than that asks for digits
    the instrument was never given."""
    for written in (430.35, 430.34):
        entry = _entry("CA-d4_TOFMSMS_Mix1", written, 50.0, 450.0)
        verdict = ir.what_the_method_isolates(entry.sample, name=entry.name)
        assert verdict.agrees, written
        assert verdict.isolations[0].tolerance == pytest.approx(0.05)


def test_a_method_isolating_another_component_says_which_one():
    entry = _entry("CA-d4_TOFMSMS_EAD_22CE_mix1", DCA_D4_NH4, 50.0, 500.0)
    verdict = ir.what_the_method_isolates(entry.sample, _components(),
                                          name=entry.name)

    assert verdict.disagrees
    fit = verdict.fit
    assert fit is not None
    assert fit.name == "DCA-d4"
    assert fit.adduct == "[M+NH4]+"
    assert fit.source == "the component table"
    # the component's formula is the unlabelled one and its name says d4:
    # without the labels nothing would have fitted
    assert fit.formula == "C24H36D4O4"
    said = verdict.sentence()
    assert "is named CA-d4 but the method isolates" in said
    assert "no adduct of C24H36D4O5" in said
    assert "DCA-d4 [M+NH4]+" in said
    assert "from the component table" in said


def test_a_record_of_your_own_can_be_what_the_method_isolates():
    entry = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", 839.56)
    verdict = ir.what_the_method_isolates(entry.sample, (), _library(),
                                          name=entry.name)

    assert verdict.disagrees
    fit = verdict.fit
    assert fit is not None and fit.source == "your library"
    assert fit.name == "Cholic acid dimer"
    # the record's formula and adduct, not the number its author typed:
    # `839.56` is what was written and 839.5644 is what the ion weighs
    assert fit.mz == pytest.approx(CHOLIC_DIMER_NA, abs=1e-3)
    assert fit.error_ppm == pytest.approx(-5.2, abs=0.2)


def test_a_precursor_nothing_fits_says_that_nothing_fits():
    entry = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", 839.56)
    verdict = ir.what_the_method_isolates(entry.sample, _components(),
                                          name=entry.name)

    assert verdict.judged and verdict.disagrees
    assert verdict.fit is None
    said = verdict.sentence()
    assert "839.56 over 100–1000" in said
    assert "no adduct of C24H36D4O5 within ±0.05 Da" in said
    assert "fits nothing in the component table or the library" in said
    assert "no adduct of C24H36D4O5, nothing fits" in verdict.column()


# --------------------------------------------------------------------------- #
# when it refuses to judge, and why that matters more than judging
# --------------------------------------------------------------------------- #
def test_a_name_nothing_recognises_is_not_a_disagreement():
    entry = _entry("mix1_TOFMSMS_22CE", 839.56)
    verdict = ir.what_the_method_isolates(entry.sample, name=entry.name)

    assert not verdict.judged
    assert not verdict.disagrees and not verdict.agrees
    assert "nothing knows the name mix1 exactly" in verdict.note
    assert verdict.sentence() == verdict.note
    # the cell gets the short form, written rather than cut out of the long
    # one at whatever punctuation happened to come first
    assert verdict.column() == "mix1 is not a compound this knows"


@pytest.mark.parametrize("name", ["PC", "CE", "Cer", "TESTOL"])
def test_a_name_that_is_merely_a_substring_of_a_lipid_is_refused(name):
    """
    `lipidmaps.find_by_name` is a substring search, which is right for a
    person typing into a box and wrong for a check that fires on every file
    opened: measured against the installed LMSD, `PC` answers *PCTR3*, `CE`
    answers *cedrol*, `Cer` answers *Cerasin* and `TESTOL` answers
    *testolactone*. Four sample names of the most ordinary kind, and each
    would then have contradicted whatever its method isolated.

    Skipped where LIPID MAPS is not installed: with no database none of them
    resolves at all and the test would pass for the wrong reason.
    """
    from milq import lipidmaps

    if not lipidmaps.is_installed():
        pytest.skip("LIPID MAPS is not installed on this machine")
    entry = _entry(f"{name}_TOFMSMS_22CE", 839.56)
    verdict = ir.what_the_method_isolates(entry.sample, name=entry.name)

    assert not verdict.judged
    assert "exactly" in verdict.note


def test_an_acquisition_with_no_product_ion_channel_is_not_judged():
    channel = FakeChannel(0, precursor=None, name="TOF MS")
    entry = SampleEntry("/d/CA-d4_survey.wiff", 0, "CA-d4_survey")
    entry.sample = FakeSample([channel])
    verdict = ir.what_the_method_isolates(entry.sample, name=entry.name)

    assert not verdict.judged and not verdict.disagrees
    assert verdict.formula == "C24H36D4O5"      # the name still resolved
    assert "no product-ion channel" in verdict.note
    assert verdict.column() == "nothing is isolated"


def test_polarity_gates_the_adducts_offered():
    """A positive channel cannot have produced `[M-H]-`, and a check that
    offered it would be inviting a mistake rather than making one."""
    negative = _entry("CA-d4_neg", CA_D4_NH4, 50.0, 500.0, polarity="Negative")
    verdict = ir.what_the_method_isolates(negative.sample, name=negative.name)

    assert verdict.disagrees
    assert not verdict.isolations[0].named


# --------------------------------------------------------------------------- #
# the row and the report
# --------------------------------------------------------------------------- #
def _summary(entries, components=(), library=None):
    from milq.session import Session

    session = Session()
    session.entries.extend(entries)
    session.method.replace_all(list(components))
    return ir.summarise(session, library=library)


def test_the_row_carries_an_isolated_column_and_flags_the_name(qapp):
    good = _entry("CA-d4_TOFMSMS_Mix1", 430.35, 50.0, 450.0)
    bad = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", 839.56)
    summary = _summary([good, bad], _components())
    rows = {row.sample: row for row in summary.rows}
    assert set(rows) == {good.name, bad.name}

    column = ir.SUMMARY_COLUMNS.index("Isolated")
    compound = ir.SUMMARY_COLUMNS.index("Compound")

    agreed = rows[good.name]
    assert agreed.cells()[column] == "430.35 = [M+NH4]+ of CA-d4"
    assert agreed.cells()[compound] == "CA-d4"

    disagreed = rows[bad.name]
    assert "nothing fits" in disagreed.cells()[column]
    # the name overruled: the cell says the method does not confirm it
    assert disagreed.cells()[compound] == "not CA-d4"
    assert disagreed.report_cells()[0] == "not CA-d4"
    # and grouping is still by the file name's proposal, so the two are
    # scored against each other — which is how the pair was found at all
    assert disagreed.compound == "CA-d4" == agreed.compound
    assert [label for label, *_ in disagreed.others] == [good.name]


def test_a_fitted_compound_replaces_the_name_in_the_cell(qapp):
    bad = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", DCA_D4_NH4)
    summary = _summary([bad], _components())
    row = summary.rows[0]

    assert row.cells()[ir.SUMMARY_COLUMNS.index("Compound")] == \
        "DCA-d4, not CA-d4"


def test_every_sort_key_still_lands_on_its_own_column(qapp):
    """`keys()` used to hold the positions written out, and inserting a
    column in the middle moved every one of them onto the cell next door
    with nothing failing."""
    entry = _entry("CA-d4_TOFMSMS_Mix1", 430.35, 50.0, 450.0)
    row = _summary([entry]).rows[0]
    keys, cells = row.keys(), row.cells()

    assert len(keys) == len(cells) == len(ir.SUMMARY_COLUMNS)
    for name in ir._SORT_KEYS:
        assert isinstance(keys[ir.SUMMARY_COLUMNS.index(name)], float), name
    for name in ("Compound", "Sample", "Isolated", "Mode", "File"):
        assert isinstance(keys[ir.SUMMARY_COLUMNS.index(name)], str), name


def test_the_report_header_and_verdict_carry_the_disagreement(qapp):
    bad = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", 839.56)
    report = ir.report_for(bad, bad.sample.channels[0],
                           components=_components(),
                           measure_precursor=False)

    assert report.isolation is not None and report.isolation.disagrees
    assert report.named_compound == "not CA-d4"
    # first sentence, because it is the one check that can invalidate the rest
    assert "but the method isolates" in report.sentences()[0]

    document = ir.build_html(report)
    assert "Isolated" in document and "Named" in document
    assert "no adduct of C24H36D4O5" in document


def test_a_report_that_agrees_does_not_spend_a_sentence_saying_so(qapp):
    good = _entry("CA-d4_TOFMSMS_Mix1", 430.35, 50.0, 450.0)
    report = ir.report_for(good, good.sample.channels[0],
                           measure_precursor=False)

    assert report.isolation is not None and report.isolation.agrees
    assert report.named_compound == "CA-d4"
    assert not [s for s in report.sentences() if "the method isolates" in s]
    # but the header cell says it, since that is where the name is printed
    assert "430.35 = [M+NH4]+ of CA-d4" in ir.build_html(report)


# --------------------------------------------------------------------------- #
# the warning when a file is opened
# --------------------------------------------------------------------------- #
def test_only_a_disagreeing_infusion_is_warned_about():
    good = _entry("CA-d4_TOFMSMS_Mix1", 430.35, 50.0, 450.0)
    bad = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", 839.56)
    unknown = _entry("mix1_TOFMSMS_22CE", 839.56)

    said = ir.name_disagreements([good, bad, unknown], _components())
    assert len(said) == 1
    assert said[0].startswith(f"{bad.name}: ")
    assert "but the method isolates" in said[0]


def test_the_shell_warns_once_per_file_without_a_dialog(qapp, monkeypatch):
    """
    The same seam `load_file` uses, called directly: a modal `QMessageBox`
    offscreen blocks the suite rather than failing it, so the wording is
    read off `file_warnings` and the dialog is left to the one line that
    puts it up.
    """
    from milq.ui.shell import MainShell

    shell = MainShell()
    try:
        bad = _entry("CA-d4_TOFMSMS_EAD_12CE_TESTEARTIGO", 839.56)
        bad.problem = ""
        other = _entry("CA-d4_TOFMSMS_Mix1", 430.35, 50.0, 450.0)
        shell.session.entries.extend([bad, other])
        shell.session.method.replace_all(_components())

        problems, disagreements = shell.file_warnings(bad.path)
        assert problems == []
        assert len(disagreements) == 1
        assert "no adduct of C24H36D4O5" in disagreements[0]

        # a different file's entries are not this file's warning
        assert shell.file_warnings(other.path)[1] == []

        shown = []
        monkeypatch.setattr(QtWidgets.QMessageBox, "warning",
                            lambda *args, **kwargs: shown.append(args[1:3]))
        shell.warn_about(bad.path)
        assert len(shown) == 1
        assert shown[0][0] == "The name and the method disagree"
    finally:
        shell.close()
        shell.deleteLater()
