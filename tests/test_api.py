"""
The documented Python surface: `milq.api`.

Everything here runs on data made in the test — an mzML written by the
writer, a chromatographic run and a direct infusion — because the point of
the module is that a colleague can script it without a vendor file or a
window. Three things are checked that nothing else checks:

* **the surface itself** — the names, their keyword names, and that
  importing it starts neither Qt nor a session, since a script that only
  reads a chromatogram should not pay for either;
* **the manual's scripts** — extracted from `help/pages/python-api.md` and
  executed against the synthetic data, so a page of ten-line examples
  cannot go stale while the tests stay green. Their paths are substituted
  from a table, and a path in the page that the table does not know fails
  the test rather than being skipped;
* **`headless()`** — one application, however many times it is entered.
"""

import os
import re
import subprocess
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq import api, chemistry, manual, mzml  # noqa: E402
from milq.wiff import ChannelInfo  # noqa: E402

#: the compound the synthetic infusion is of: a bile-acid standard whose
#: name the standards table knows, with four labels its name declares and
#: does not place
INFUSED = "TDCA-d4"
LABELLED = "C26H41D4NO6S"
PRECURSOR = chemistry.mass_from_formula(LABELLED, "[M+H]+")
#: as a method would write it — two decimals, which is all a channel carries
WRITTEN = round(PRECURSOR, 2)

#: the chromatographic run's one transition
ANALYTE_PRECURSOR = 300.2000
ANALYTE_FRAGMENT = 184.0733
STANDARD_FRAGMENT = 200.0700


# --------------------------------------------------------------------------- #
# synthetic files
# --------------------------------------------------------------------------- #
def _cluster(centre: float, height: float, points: int = 7,
             step: float = 0.004):
    """One ion as a profile peak, the way an instrument records it."""
    offsets = (np.arange(points) - points // 2) * step
    return centre + offsets, height * np.exp(-0.5 * (offsets / (1.5 * step)) ** 2)


def _spectrum(ions):
    """Several ions as one spectrum, in mass order."""
    mz = np.concatenate([_cluster(m, h)[0] for m, h in ions])
    intensity = np.concatenate([_cluster(m, h)[1] for m, h in ions])
    order = np.argsort(mz)
    return mz[order], intensity[order]


class _Channel:
    """Enough of the reader's channel for `mzml.write_mzml`."""

    def __init__(self, index, info, times, spectra):
        self.index, self.info = index, info
        self._times = np.asarray(times, dtype=float)
        self._spectra = spectra

    def tic(self):
        return self._times, np.array([float(s[1].sum()) for s in self._spectra])

    @property
    def rt(self):
        return self._times

    def spectrum(self, scan, add_zeros=True):
        return self._spectra[int(scan)]


class _Sample:
    instrument = "TripleTOF 6600"
    acquisition_time = "2026-09-10T09:00:00Z"

    def __init__(self, name, channels):
        self.name, self.channels = name, channels


def _write_infusion(path, scans: int = 150):
    """
    A direct infusion: every scan the same spectrum, for long enough that
    flatness is evidence — see `milq/infusion.py`.
    """
    times = np.arange(scans) * 0.005
    one = _spectrum([(PRECURSOR, 1000.0), (PRECURSOR - 18.0106, 300.0),
                     (124.0063, 700.0)])
    info = ChannelInfo(0, "TOF PI", "Product Ion", "Positive", WRITTEN,
                       100.0, 600.0, scans, 25.0)
    channel = _Channel(0, info, times, [one] * scans)
    mzml.write_mzml(_Sample("infused", [channel]), path)
    return str(path)


def _write_run(path, scale: float = 1.0, scans: int = 40):
    """A chromatogram: one transition with a peak at 2 minutes."""
    times = np.arange(scans) * 0.1
    spectra = []
    for t in times:
        height = 20000.0 * scale * np.exp(-0.5 * ((t - 2.0) / 0.08) ** 2) + 5.0
        spectra.append(_spectrum([
            (ANALYTE_FRAGMENT, height),
            (STANDARD_FRAGMENT, 8000.0 * np.exp(-0.5 * ((t - 2.0) / 0.08) ** 2) + 5.0),
            (ANALYTE_PRECURSOR, height * 0.2),
        ]))
    info = ChannelInfo(0, "TOF PI", "Product Ion", "Positive",
                       ANALYTE_PRECURSOR, 100.0, 400.0, scans, 35.0)
    mzml.write_mzml(_Sample("run", [_Channel(0, info, times, spectra)]), path)
    return str(path)


COMPONENTS_CSV = (
    "name,precursor,fragment,rt,rt_halfwidth,tolerance,unit,"
    "is_internal_standard,internal_standard\n"
    f"Analyte,{ANALYTE_PRECURSOR},{ANALYTE_FRAGMENT},2.0,0.6,0.02,Da,,Standard\n"
    f"Standard,{ANALYTE_PRECURSOR},{STANDARD_FRAGMENT},2.0,0.6,0.02,Da,yes,\n"
)


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    """
    A folder holding two infusions and three chromatographic runs, plus the
    component table and a saved project of the three runs.

    Module-scoped: writing five mzML files and integrating them once is
    enough, and every test here only reads them.
    """
    folder = tmp_path_factory.mktemp("api-data")
    infusions = [_write_infusion(folder / f"{INFUSED}_infusion_{n}.mzML")
                 for n in ("a", "b")]
    runs = [_write_run(folder / f"study_STD{n}.mzML", scale=scale)
            for n, scale in ((1, 1.0), (2, 2.0), (3, 4.0))]
    csv = folder / "components.csv"
    csv.write_text(COMPONENTS_CSV, encoding="utf-8")

    project = folder / "study.oqproj"
    batch = api.Batch(runs, components_csv=csv)
    for entry, concentration in zip(batch.session.entries, (1.0, 2.0, 4.0),
                                    strict=True):
        entry.sample_type = "Standard"
        entry.actual_concentration = concentration
    batch.process()
    batch.save_project(project)
    batch.close()
    return {"folder": folder, "infusions": infusions, "runs": runs,
            "csv": csv, "project": str(project)}


# --------------------------------------------------------------------------- #
# the surface
# --------------------------------------------------------------------------- #
def test_the_version_is_declared_and_every_promised_name_exists():
    assert api.VERSION == 1
    for name in api.__all__:
        assert hasattr(api, name), f"promised but missing: {name}"
    for name in ("open", "explain", "headless", "infusion_report", "Batch",
                 "Library", "Acquisition", "Spectrum", "Results"):
        assert name in api.__all__


def test_importing_it_starts_neither_qt_nor_a_session():
    """
    A script that reads a chromatogram should not pay for the interface.

    In a subprocess, because the suite has already imported both by the time
    anything here runs.
    """
    code = ("import sys; from milq import api; "
            "print('PyQt6' in sys.modules, 'milq.session' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, check=True,
                         cwd=os.path.dirname(os.path.dirname(__file__)))
    assert out.stdout.strip() == "False False"


def test_headless_makes_one_application_however_often_it_is_entered():
    from PyQt6 import QtWidgets

    with api.headless() as first:
        with api.headless() as second:
            assert first is second
        assert QtWidgets.QApplication.instance() is first
    # and it is still there afterwards: one per process, never torn down
    assert QtWidgets.QApplication.instance() is first


# --------------------------------------------------------------------------- #
# one acquisition
# --------------------------------------------------------------------------- #
def test_open_reads_samples_channels_and_traces(data):
    with api.open(data["runs"][0]) as run:
        assert run.samples == [run]
        assert run.name.startswith("study_STD1")
        assert run.compound == "study"          # before the first underscore
        channel = run.channel(0)
        assert channel.n_scans == 40
        assert channel.precursor == pytest.approx(ANALYTE_PRECURSOR)
        assert channel.polarity == "Positive"
        assert not channel.is_ms1

        tic = run.tic()
        assert len(tic) == 40 and tic.apex[0] == pytest.approx(2.0, abs=0.06)
        assert isinstance(tic.rt, np.ndarray)

        xic = run.xic(ANALYTE_FRAGMENT, tolerance=0.02)
        assert len(xic) == 40 and xic.apex[1] > 1000

        spectrum = run.spectrum(channel.scan_at(2.0))
        assert len(spectrum) > 0
        assert spectrum.base_peak[0] == pytest.approx(ANALYTE_FRAGMENT, abs=0.01)
        assert spectrum.precursor == pytest.approx(ANALYTE_PRECURSOR)

        average = run.average(1.8, 2.2)
        assert average.rt_range == (1.8, 2.2)
        assert len(average) > 0


def test_a_chromatogram_is_not_an_infusion_and_says_why(data):
    with api.open(data["runs"][0]) as run:
        assert run.is_infusion is False
        assert run.infusion_reason


def test_an_infusion_reads_as_one_and_averages_its_whole_run(data):
    with api.open(data["infusions"][0]) as run:
        assert run.is_infusion is True
        assert "infusion" in run.infusion_reason
        assert run.compound == INFUSED
        assert run.infusion_channel().precursor == pytest.approx(WRITTEN)

        average = run.infusion_average()
        assert average.precursor == pytest.approx(WRITTEN)
        assert average.polarity == "Positive"
        assert average.rt_range is not None
        assert average.centroided is False


def test_a_profile_spectrum_is_centroided_to_one_stick_per_ion(data):
    with api.open(data["infusions"][0]) as run:
        average = run.infusion_average()
    sticks = average.centroid()
    assert sticks.centroided is True
    assert len(sticks) < len(average)
    assert sticks.centroid() is sticks              # idempotent
    peaks = average.peaks(limit=10)
    assert peaks and peaks[0][0] == pytest.approx(PRECURSOR, abs=0.005)


# --------------------------------------------------------------------------- #
# a batch
# --------------------------------------------------------------------------- #
def test_a_batch_from_files_and_a_csv_processes_to_rows(data):
    batch = api.Batch(data["runs"][:1], components_csv=data["csv"])
    assert batch.components == ["Analyte", "Standard"]
    assert len(batch.samples) == 1

    rows = batch.process()
    assert len(rows) == 2 and len(rows.found) == 2
    analyte = rows.for_component("Analyte")[0]
    assert analyte.area > 0 and analyte.height > 0
    assert analyte.rt == pytest.approx(2.0, abs=0.1)
    assert analyte.internal_standard == "Standard"
    standard = rows.for_component("Standard")[0]
    assert analyte.is_area == pytest.approx(standard.area)
    assert analyte.area_ratio == pytest.approx(analyte.area / standard.area)
    assert analyte.found is True
    assert rows.for_sample(batch.samples[0]).rows == rows.rows
    batch.close()


def test_results_come_back_as_rows_dictionaries_and_a_table(data, tmp_path):
    batch = api.Batch.from_project(data["project"])
    rows = batch.results
    assert len(rows) == 6                     # 3 injections × 2 components

    dictionaries = rows.dicts()
    assert dictionaries[0]["component"] in ("Analyte", "Standard")
    assert "found" in dictionaries[0] and "flags" in dictionaries[0]
    assert isinstance(dictionaries[0]["flags"], list)

    table = rows.table()
    assert table.columns[:2] == ("Sample", "Component")
    assert len(table) == len(rows)
    written = table.to_csv(tmp_path / "rows.csv")
    text = open(written, encoding="utf-8").read()
    assert text.splitlines()[0].startswith("Sample,Component")
    assert len(text.splitlines()) == len(rows) + 1
    batch.close()


def test_a_project_reopens_with_its_samples_and_reprocesses(data):
    batch = api.Batch.from_project(data["project"])
    assert batch.missing == ()
    assert batch.project.endswith(".oqproj")
    assert len(batch.samples) == 3
    before = [r.area for r in batch.results]
    after = [r.area for r in batch.process()]
    assert after == before                    # the same files, the same numbers
    assert [a.name for a in batch.acquisitions()] == batch.samples
    batch.close()


def test_calibrate_fits_a_curve_and_reads_concentrations_back(data):
    batch = api.Batch.from_project(data["project"])
    batch.process()
    curves = batch.calibrate()
    assert set(curves) == {"Analyte", "Standard"}
    curve = curves["Analyte"]
    assert curve.fitted and curve.points == 3 and curve.used == 3
    assert curve.r2 > 0.99
    assert curve.equation.startswith("y = ")
    assert curve.concentration_at(curve.coefficients[-1]) == pytest.approx(0.0,
                                                                           abs=1e-6)
    assert batch.curves["Analyte"].r2 == curve.r2
    read = [r.concentration for r in batch.results.for_component("Analyte")]
    assert all(value is not None for value in read)
    assert read == pytest.approx([1.0, 2.0, 4.0], rel=0.05)
    batch.close()


def test_statistics_come_back_as_a_table(data):
    batch = api.Batch.from_project(data["project"])
    table = batch.statistics(grouping="sample type")
    assert table.columns == ("Component", "Group", "n", "n of", "Mean", "SD",
                             "%CV")
    assert len(table) == 2                    # two components, one group
    assert all(row[1] == "Standard" for row in table.rows)
    batch.close()


def test_only_reruns_the_named_component_and_leaves_the_rest(data):
    batch = api.Batch.from_project(data["project"])
    first = {(r.sample, r.component): r.area for r in batch.process()}
    again = {(r.sample, r.component): r.area
             for r in batch.process(only=["Analyte"])}
    assert again == first
    batch.close()


def test_export_writes_a_workbook_a_report_and_a_project(data, tmp_path):
    batch = api.Batch.from_project(data["project"])
    workbook = batch.export_xlsx(tmp_path / "batch.xlsx")
    assert os.path.getsize(workbook) > 0

    html = batch.report(tmp_path / "batch.html")
    assert "<html" in open(html, encoding="utf-8").read()

    pdf = batch.report(tmp_path / "batch.pdf")
    assert open(pdf, "rb").read(5) == b"%PDF-"

    saved = batch.save_project(tmp_path / "again.oqproj")
    assert api.Batch.from_project(saved).samples == batch.samples
    batch.close()


# --------------------------------------------------------------------------- #
# explaining a spectrum
# --------------------------------------------------------------------------- #
def test_explain_from_a_name_resolves_the_formula_the_adduct_and_the_labels(data):
    with api.open(data["infusions"][0]) as run:
        said = api.explain(run.infusion_average(), name=INFUSED)
    assert said.formula == LABELLED           # the labels the name declares
    assert said.labels == 4
    assert said.adduct == "[M+H]+"            # read off the written precursor
    assert said.matched >= 1 and said.predicted >= 1
    assert 0.0 < said.share <= 1.0
    assert said.basis and not said.note
    assert bool(said) is True
    landed = [f for f in said.fragments
              if abs(f.mz - PRECURSOR) < 0.01]
    assert landed and abs(landed[0].error_ppm) < 20


def test_explain_from_a_formula_takes_the_adduct_it_is_given(data):
    with api.open(data["infusions"][0]) as run:
        said = api.explain(run.infusion_average(), formula=LABELLED,
                           adduct="[M+H]+")
    assert said.adduct == "[M+H]+" and "as given" in said.basis
    assert said.matched >= 1


def test_explain_takes_a_pair_of_arrays_or_a_list_of_peaks():
    peaks = [(PRECURSOR, 1000.0), (100.0, 10.0)]
    arrays = (np.array([p[0] for p in peaks]),
              np.array([p[1] for p in peaks]))
    from_peaks = api.explain(peaks, formula=LABELLED, adduct="[M+H]+")
    from_arrays = api.explain(arrays, formula=LABELLED, adduct="[M+H]+")
    assert from_peaks.matched == from_arrays.matched >= 1


def test_explain_from_a_molfile_cuts_bonds(data):
    molfile = os.path.join(os.path.dirname(__file__), "fixtures",
                           "LMST04010001.mol")
    with api.open(data["infusions"][0]) as run:
        said = api.explain(run.infusion_average(), molfile=molfile,
                           adduct="[M+H]+")
    assert said.formula and "a drawing of your own" in said.basis
    assert said.predicted > 3                 # a structure offers pieces


def test_explain_says_why_when_it_cannot_rather_than_raising(data):
    with api.open(data["infusions"][0]) as run:
        average = run.infusion_average()
    unknown = api.explain(average, name="not a compound anybody sells")
    assert unknown.matched == 0 and not unknown
    assert "nothing knows the name" in unknown.note

    wrong = api.explain(average, formula="C2H6O")     # no adduct fits 504.33
    assert wrong.matched == 0 and wrong.note and not wrong.adduct

    with pytest.raises(ValueError):
        api.explain(average)                          # nothing to look for


# --------------------------------------------------------------------------- #
# a library
# --------------------------------------------------------------------------- #
def test_a_library_is_written_a_record_at_a_time_and_read_back(data, tmp_path):
    path = tmp_path / "own.msp"
    with pytest.raises(FileNotFoundError):
        api.Library.open(path)
    library = api.Library.open(path, create=True)
    assert len(library) == 0 and library.path == str(path)

    with api.open(data["infusions"][0]) as run:
        average = run.infusion_average()
        assert library.add(average, name=run.name, formula=LABELLED,
                           adduct="[M+H]+") == 1
    assert os.path.exists(path)
    assert "Name:" in open(path, encoding="utf-8").read()

    reopened = api.Library.open(path)
    assert len(reopened) == 1
    entry = reopened.entries[0]
    assert entry.precursor == pytest.approx(WRITTEN)
    assert entry.formula == LABELLED
    # a record is centroids, not the profile it was made from
    assert entry.peaks < len(average)


def test_a_search_finds_its_own_record_and_takes_the_query_from_the_spectrum(
        data, tmp_path):
    path = tmp_path / "own.msp"
    library = api.Library.open(path, create=True)
    with api.open(data["infusions"][0]) as run:
        average = run.infusion_average()
        library.add(average, name="mine", formula=LABELLED, adduct="[M+H]+")

    hits = library.search(average)
    assert hits and hits[0].name == "mine"
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].reverse == pytest.approx(1.0)
    assert hits[0].matched == hits[0].of_library
    assert hits[0].delta_ppm is not None and abs(hits[0].delta_ppm) < 100
    assert hits[0].formula == LABELLED

    # a precursor nothing is near excludes every record
    assert library.search(average, precursor=100.0) == []
    # and the other polarity is refused, since the adduct declares a sign
    assert library.search(average, polarity="Negative") == []


def test_a_record_can_be_added_without_writing_a_file(data, tmp_path):
    library = api.Library.open(tmp_path / "unwritten.msp", create=True)
    with api.open(data["infusions"][0]) as run:
        library.add(run.infusion_average(), name="in memory", write=False)
    assert len(library) == 1
    assert not os.path.exists(tmp_path / "unwritten.msp")


# --------------------------------------------------------------------------- #
# the infusion document
# --------------------------------------------------------------------------- #
def test_the_infusion_document_covers_a_folder_and_reports_every_section(
        data, tmp_path):
    document = api.infusion_report(data["folder"], tmp_path / "infusions.pdf")
    assert open(document.path, "rb").read(5) == b"%PDF-"
    assert document.seconds > 0
    # the three chromatographic runs in the same folder are left out
    assert len(document) == 2
    line = document.lines[0]
    assert line.compound == INFUSED
    assert line.polarity == "Positive"
    assert line.precursor_written == pytest.approx(WRITTEN)
    assert line.scans == 150
    assert line.annotation is not None and line.annotation.matched >= 1
    assert line.match is None                 # no library was given


def test_the_infusion_document_takes_a_library_and_a_formula(data, tmp_path):
    library = api.Library.open(tmp_path / "for-document.msp", create=True)
    with api.open(data["infusions"][0]) as run:
        library.add(run.infusion_average(), name="the standard",
                    formula=LABELLED, adduct="[M+H]+")
    document = api.infusion_report(data["infusions"][1],
                                   tmp_path / "one.html",
                                   library=library, formula=LABELLED)
    assert "<html" in open(document.path, encoding="utf-8").read()
    assert len(document) == 1
    line = document.lines[0]
    assert line.match is not None and line.match.name == "the standard"
    assert line.annotation.formula == LABELLED


def test_a_source_with_no_infusion_in_it_refuses_to_write_a_document(
        data, tmp_path):
    with pytest.raises(ValueError, match="direct infusion"):
        api.infusion_report(data["runs"][0], tmp_path / "nothing.pdf")


# --------------------------------------------------------------------------- #
# the manual's scripts
# --------------------------------------------------------------------------- #
PAGE = manual.PAGES_DIR / "python-api.md"

#: what a path in the page is replaced by when it is run here. Every
#: path-like literal in the page must appear as a key, so that changing a
#: script's paths fails this test instead of silently running the old ones.
def _substitutions(data, tmp_path) -> dict[str, str]:
    return {
        '"bile-acids.msp"': repr(str(tmp_path / "bile-acids.msp")),
        '"/Volumes/NOBRE/Cyborg/Bileomics"': repr(str(data["folder"])),
        '"*.wiff"': '"*.mzML"',
        '"/Volumes/NOBRE/Cyborg/Bileomics/CA-d4_TOFMSMS_Mix1.wiff"':
            repr(data["infusions"][0]),
        '"Sphingolipids-reprocessado.oqproj"': repr(data["project"]),
        '"sphingolipids.csv"': repr(str(tmp_path / "out.csv")),
        '"sphingolipids.xlsx"': repr(str(tmp_path / "out.xlsx")),
        '"sphingolipids.pdf"': repr(str(tmp_path / "out.pdf")),
    }


#: a string literal that names a file, a folder or a glob — the only kind
#: the table has to know about. Braces are excluded so that an f-string
#: holding a slash between two fields is not read as a path
_PATHLIKE = re.compile(r'"[^"{}\n]*(?:/|\*\.|\.msp|\.wiff|\.mzML|\.oqproj'
                       r'|\.csv|\.xlsx|\.pdf)[^"{}\n]*"')


def _scripts() -> list[str]:
    """The page's Python blocks, in the order they are written."""
    text = PAGE.read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.S)


def test_the_page_holds_the_three_scripts_it_claims():
    scripts = _scripts()
    assert len(scripts) == 3
    for script in scripts:
        assert "from milq import api" in script
        assert len(script.splitlines()) <= 16, "a ten-line script, roughly"


def test_every_path_in_the_manuals_scripts_is_one_this_test_knows(data,
                                                                  tmp_path):
    known = set(_substitutions(data, tmp_path))
    for script in _scripts():
        for literal in _PATHLIKE.findall(script):
            assert literal in known, (
                f"the page names {literal}, which this test cannot stand in "
                f"for — add it to _substitutions")


def test_the_manuals_scripts_run(data, tmp_path, capsys):
    """
    The page's own scripts, against the synthetic data.

    Run in the order they are written, in one namespace apiece, because the
    third searches the library the first writes.
    """
    substitutions = _substitutions(data, tmp_path)
    for number, script in enumerate(_scripts(), start=1):
        for literal, stand_in in substitutions.items():
            script = script.replace(literal, stand_in)
        exec(compile(script, f"python-api.md script {number}", "exec"), {})

    printed = capsys.readouterr().out
    assert "records written to" in printed          # the first
    assert "with a peak" in printed                 # the second
    assert "records searched" in printed            # the third
    for name in ("bile-acids.msp", "out.csv", "out.xlsx", "out.pdf"):
        assert os.path.exists(tmp_path / name), name


def test_the_offscreen_platform_is_given_fonts_on_windows(tmp_path, monkeypatch):
    """
    Qt's offscreen platform finds no fonts on Windows and draws every
    glyph as a box — measured: a 47-page report with no text in it. The
    system's directory is pointed at, only there, and only where nothing
    else has said where to look.
    """
    import os
    import sys

    (tmp_path / "Fonts").mkdir()
    monkeypatch.setenv("WINDIR", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("QT_QPA_FONTDIR", raising=False)

    monkeypatch.setattr(sys, "platform", "darwin")
    api.offscreen_fonts()
    assert "QT_QPA_FONTDIR" not in os.environ

    monkeypatch.setattr(sys, "platform", "win32")
    api.offscreen_fonts()
    assert os.environ["QT_QPA_FONTDIR"] == str(tmp_path / "Fonts")

    monkeypatch.setenv("QT_QPA_FONTDIR", "elsewhere")
    api.offscreen_fonts()
    assert os.environ["QT_QPA_FONTDIR"] == "elsewhere"

    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")
    monkeypatch.delenv("QT_QPA_FONTDIR")
    api.offscreen_fonts()
    assert "QT_QPA_FONTDIR" not in os.environ
