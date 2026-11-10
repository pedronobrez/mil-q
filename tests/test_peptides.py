"""The headless peptide toolkit (`milq/peptides.py`, `milq peptide …`)."""

import json
import os

import numpy as np
import pytest

from milq import contract, mzml, peptides as pep
from milq.wiff import KIND_IDA_SLOT, KIND_MS1, ChannelInfo, ScanDetails

TARGET = "pGlu-QPLAPVHNPISV"


def test_the_beta_casein_peptide_weighs_what_the_brief_says():
    found = pep.mass(TARGET)
    assert found["monoisotopic_mass"] == pytest.approx(1253.676822, abs=1e-5)
    assert [m["mz"] for m in found["mz"]][1] == pytest.approx(627.8457, abs=1e-4)
    assert "isobaric" in found["isobaric"]


@pytest.mark.parametrize("text", ["pEPLAPVHNPISV", "pE-PLAPVHNPISV",
                                  "[pyroGlu]QPLAPVHNPISV", "pGlu-QPLAPVHNPISV"])
def test_every_spelling_of_pyroglu_is_one_peptide(text):
    assert pep.parse(text).neutral_mass == pytest.approx(
        pep.parse(TARGET).neutral_mass, abs=1e-9)


def test_modifications_shift_by_their_masses():
    plain = pep.parse("SPMKE").neutral_mass
    assert pep.parse("S[Phospho]PMKE").neutral_mass - plain == pytest.approx(79.966331)
    assert pep.parse("SPM[Oxidation]KE").neutral_mass - plain == pytest.approx(15.994915)
    assert pep.parse("SPMKE[Amidated]").neutral_mass - plain == pytest.approx(-0.984016)
    assert pep.parse("[Acetyl]-SPMKE").neutral_mass - plain == pytest.approx(42.010565)
    assert (pep.parse("[pyroGlu]EPLA").neutral_mass
            - pep.parse("EPLA").neutral_mass) == pytest.approx(-18.010565, abs=1e-6)
    with pytest.raises(pep.PeptideError):
        pep.parse("A[Phospho]K")
    with pytest.raises(pep.PeptideError):
        pep.parse("[pyroGlu]APLA")


def test_fragments_have_the_textbook_masses():
    ions = {i.name: i.mz for i in pep.fragments("PEPTIDE", charges=(1, 2))}
    assert ions["b2"] == pytest.approx(227.102633, abs=1e-5)
    assert ions["y1"] == pytest.approx(148.060434, abs=1e-5)
    assert ions["y2+"] == pytest.approx((ions["y2"] + pep.PROTON) / 2, abs=1e-9)
    assert ions["a2"] == pytest.approx(ions["b2"] - pep.CO)
    assert "int-EPT" in ions and "imm-P" in ions


def _theory(peptide, charge=2, noise=()):
    ions = [i for i in pep.fragments(peptide, charges=(1,), internal=False,
                                     immonium=False) if i.series in ("b", "y")]
    mz = np.array([i.mz for i in ions] + list(noise), dtype=float)
    height = np.array([1000.0 - 5 * k for k in range(len(ions))]
                      + [50.0] * len(noise), dtype=float)
    order = np.argsort(mz)
    return mz[order], height[order]


def test_annotation_covers_every_bond_and_names_what_is_left():
    mz, height = _theory(TARGET, noise=[333.3333])
    found = pep.annotate(mz, height, TARGET, charge=2, tol_ppm=5)
    assert "." not in found.coverage
    assert found.unexplained[0]["mz"] == pytest.approx(333.3333)
    assert 0.9 < found.explained < 1.0
    assert all(abs(m["ppm"]) < 1e-3 for m in found.matches)


def test_a_digest_enumerates_every_piece_and_variant():
    proteins = {"X": "QSPMKE"}
    plain = pep.digest(proteins, True, (4, 5))
    assert sorted(c.peptide.sequence for c in plain) == sorted(
        ["QSPM", "SPMK", "PMKE", "QSPMK", "SPMKE"])
    modified = pep.digest(proteins, True, (6, 6), ["pyroglu-q", "phospho-st", "ox-m"], 3)
    assert len(modified) == 8                       # every subset of three sites
    decoys = pep.digest(proteins, True, (6, 6), decoy=True)
    assert decoys[0].peptide.sequence == "EKMPSQ" and decoys[0].decoy


def test_q_values_follow_the_decoys():
    def psm(score, decoy):
        candidate = pep.Candidate(pep.parse("PEPTIDE"), "X", 1, 7, decoy)
        return pep.Psm(candidate, 2, "f", 0, 0, 1.0, 400.0, 400.0, 0, 0.0,
                       5, 0.5, 3, score)

    psms = [psm(10, False), psm(9, False), psm(8, True), psm(7, False), psm(6, True)]
    pep.q_values(psms)
    assert [p.q_value for p in psms] == [0.0, 0.0, pytest.approx(1 / 3),
                                         pytest.approx(1 / 3), pytest.approx(2 / 3)]


# --------------------------------------------------------------------------- #
# a synthetic IDA run with the peptide in it
# --------------------------------------------------------------------------- #
PROTEIN = "MKVLILACLVTQPLAPVHNPISVGGKDEERLLSQ"
OTHERS = [612.3011, 455.7788, 701.4123, 528.9901]


class _Channel:
    def __init__(self, index, info, times, spectra, details):
        self.index, self.info = index, info
        self._times = np.asarray(times, dtype=float)
        self._spectra = spectra
        self._details = details

    def tic(self):
        return self._times, np.array([float(np.sum(s[1])) for s in self._spectra])

    @property
    def rt(self):
        return self._times

    def spectrum(self, scan, add_zeros=True):
        return self._spectra[int(scan)]

    def scan_details(self):
        return self._details


class _Sample:
    name = "run"
    instrument = "TripleTOF 5600"
    acquisition_time = ""

    def __init__(self, channels):
        self.channels = channels


def _profile(mz, height, step=0.003):
    """Each stick as a small profile peak with zeros either side."""
    offsets = np.arange(-3, 4) * step
    shape = np.exp(-0.5 * (offsets / (1.2 * step)) ** 2)
    shape[[0, -1]] = 0.0
    x = (np.asarray(mz)[:, None] + offsets[None, :]).ravel()
    y = (np.asarray(height)[:, None] * shape[None, :]).ravel()
    order = np.argsort(x)
    return x[order], y[order]


@pytest.fixture
def run(tmp_path):
    rng = np.random.default_rng(7)
    target = pep.parse(TARGET).mz(2)
    times = [0.1 * k for k in range(1, 13)]
    parents, spectra = [], []
    for k in range(12):
        if k in (4, 5, 6):
            parents.append(target)
            mz, height = _theory(TARGET, noise=rng.uniform(100, 900, 20))
        else:
            parents.append(OTHERS[k % len(OTHERS)])
            mz = np.sort(rng.uniform(100, 900, 40))
            height = rng.uniform(10, 500, 40)
        spectra.append(_profile(mz, height))
    parents = np.array(parents)
    slot = _Channel(1, ChannelInfo(1, "TOF PI", "Product", "Positive", None, 50.0,
                                   1250.0, 12, 35.0, kind=KIND_IDA_SLOT),
                    times, spectra,
                    ScanDetails(parents, np.full(12, 1.0), np.full(12, 35.0),
                                np.full(12, 2, dtype=np.int64)))
    survey_peaks = (np.array([target - 0.004, target, target + 0.004,
                              target + 0.5017]),
                    np.array([300.0, 9000.0, 300.0, 4000.0]))
    survey = _Channel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None, 100.0,
                                     1500.0, 12, None, kind=KIND_MS1),
                      times, [survey_peaks] * 12,
                      ScanDetails.constant(12, None, None, None))
    path = tmp_path / "run.mzML"
    mzml.write_mzml(_Sample([survey, slot]), path)
    fasta = tmp_path / "proteins.fasta"
    fasta.write_text(">sp|P99999|TEST_HUMAN a test\n" + PROTEIN + "\n"
                     ">sp|P88888|OTHER_HUMAN another\nMGGGSSSAAAKKKLLL\n")
    yield str(path), str(fasta)
    contract.close_all()


def test_the_screen_finds_the_peptide_and_no_decoy(run):
    path, fasta = run
    proteins = pep.read_fasta(fasta, ["P99999"])
    result = pep.screen([path], proteins, (4, 30), ["pyroglu-q", "phospho-st"], 2,
                        ppm=15, fdr=0.01)
    rows = result.peptides()
    best = rows[0]
    assert best["peptide"] == "pEPLAPVHNPISV" and best["charge"] == 2
    assert best["q_value"] <= 0.01 and best["scans"] == 3
    assert best["start"] == 12 and best["end"] == 23
    assert best["fragment"] is not None
    assert not any(p.candidate.decoy and p.q_value <= 0.01 for p in result.psms)


def test_the_command_line_screens_writes_and_makes_components(run, tmp_path):
    from tests.test_cli import call

    path, fasta = run
    prefix = tmp_path / "out" / "screen"
    code, out, err = call("peptide", "screen", path, "--fasta", fasta,
                          "--proteins", "P99999", "--nonspecific", "--len", "4:30",
                          "--mods", "pyroglu-q,phospho-st", "--max-mods", "2",
                          "--ppm", "15", "--decoy", "reverse", "--out", prefix)
    assert code == 0, err
    doc = json.loads(out)
    assert doc["command"] == "peptide screen"
    assert doc["accepted_peptides"] >= 1
    assert doc["rows"][0]["peptide"] == "pEPLAPVHNPISV"
    for kind in ("tsv", "json", "msp"):
        assert os.path.exists(doc["outputs"][kind])
    msp = open(doc["outputs"]["msp"], encoding="utf-8").read()
    assert "pEPLAPVHNPISV 2+" in msp and "PrecursorMZ: 627.845687" in msp

    csv_path = tmp_path / "components.csv"
    code, out, err = call("peptide", "components", doc["outputs"]["tsv"],
                          "--out", csv_path)
    assert code == 0, err
    from milq.components import load_components

    made = load_components(str(csv_path))
    assert made[0].precursor == pytest.approx(627.845687)
    assert made[0].fragment is not None and made[0].rt == pytest.approx(0.6, abs=0.2)


def test_the_command_line_annotates_from_the_file(run):
    from tests.test_cli import call

    path, _fasta = run
    code, out, err = call("peptide", "annotate", "--from", path, "--source",
                          "gated:627.8457", "--rt", "0:2", "--seq", TARGET,
                          "--charge", "2", "--centroid", "none")
    assert code == 0, err
    doc = json.loads(out)
    assert doc["input"]["scans_used"] == 3
    assert "." not in doc["coverage"]


def test_mass_fragments_and_digest_on_the_command_line(run, tmp_path):
    from tests.test_cli import call

    _path, fasta = run
    code, out, _ = call("peptide", "mass", TARGET)
    assert json.loads(out)["mz"][1]["mz"] == pytest.approx(627.845687)
    code, out, _ = call("peptide", "fragments", "PEPTIDE", "--charges", "1",
                        "--format", "tsv")
    assert out.splitlines()[0] == "name\tseries\tindex\tcharge\tmz"
    code, out, _ = call("peptide", "digest", fasta, "--proteins", "P88888",
                        "--nonspecific", "--len", "4:4", "--charges", "2")
    doc = json.loads(out)
    assert doc["candidates"] == 13 and "mz_2" in doc["rows"][0]
    code, _out, err = call("peptide", "mass", "XYZ")
    assert code == 2 and json.loads(err)["error"] == "bad_arguments"
