"""
The peptide screen's acceptance test on real data: a peptide the person
expects in their own IDA acquisitions must be found at q < 0.01, and the
scorer is not tuned on it.

Which peptide, which protein and which files are not written here — the
acquisitions belong to somebody's unpublished study. They come from
`tests/real/data.local.json` (untracked) or the environment:

    "screen_peptide": "pGlu-…",          MILQ_TEST_PEPTIDE
    "screen_protein": "P…",              MILQ_TEST_PROTEIN
    "screen_charge":  2                  (optional)
    plus MILQ_TEST_WIFF / "ida_wiff" and MILQ_TEST_FASTA / "fasta"

The figures it was written against are in `NOTES.local.md`.
"""

from __future__ import annotations

import os

import pytest

from milq import contract, peptides as pep

from . import data


def _setting(name: str, variable: str) -> str:
    value = os.environ.get(variable) or data._local().get(name)
    if not value:
        pytest.skip(f"no {name}: set {variable} or {name} in {data.LOCAL}")
    return str(value)


def test_the_expected_peptide_is_found_at_one_percent():
    sequence = _setting("screen_peptide", "MILQ_TEST_PEPTIDE")
    protein = _setting("screen_protein", "MILQ_TEST_PROTEIN")
    charge = int(data._local().get("screen_charge") or 2)
    wanted = pep.parse(sequence)
    proteins = pep.read_fasta(data.fasta(), [protein])
    try:
        result = pep.screen([data.ida_wiff()], proteins, (4, 40),
                            ["pyroglu-q", "phospho-st", "ox-m"], 3, ppm=15)
    finally:
        contract.close_all()
    rows = [r for r in result.peptides()
            if r["peptide"] == pep.format_peptide(wanted) and r["charge"] == charge]
    if not rows:
        pytest.fail(f"{sequence} {charge}+ was not matched at all")
    assert rows[0]["q_value"] < 0.01
    assert rows[0]["mz"] == pytest.approx(wanted.mz(charge), abs=1e-6)
