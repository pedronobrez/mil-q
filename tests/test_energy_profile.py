"""
A standard's fragmentation across collision energies.

What is tested is the arithmetic and the refusing: that a profile is the
shares of its own total rather than of a base peak that moves rung as the
energy rises, that a rung's share is linear between the two energies that
bracket it, that nothing is extrapolated past the measured range, that two
activations are never interpolated across, that one record of an activation
is reported as one record, and that a record of another precursor filed
under the same compound's name is left out of the profile with the reason.

The interpolation is exercised on synthetic records with a rung that walks
linearly with energy, because the real files cannot exercise it: the nine
bile-acid infusions hold CA-d4 at EAD 12, EAD 22 and 45 eV with the
activation unstated, so within one activation there are two points and no
third to check an interpolated one against. What the real files did settle —
the shares against energy — is the table in the manual page.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from milq.infusion_report import SUMMARY_COLUMNS                # noqa: E402
from milq import library as lib                              # noqa: E402
from milq.library import (SpectralLibrary, entry_from_spectrum,  # noqa: E402
                               format_msp, match_profile, parse_msp,
                               profile_of)

#: cholic acid-d4 as its own records carry it: the formula spells its labels
#: and the adduct says which ion the ladder hangs off
FORMULA = "C24H36D4O5"
ADDUCT = "[M+NH4]+"

#: four rungs of that ladder, as `explain.precursor_ions` predicts them
PRECURSOR = 430.3465
MINUS_1 = 395.3094
MINUS_2 = 377.2988
MINUS_3 = 359.2883
LADDER = np.array([PRECURSOR, MINUS_1, MINUS_2, MINUS_3])


def rung_index(profile, mz: float) -> int:
    """Which rung sits at a mass. The profile's rungs carry the mass the
    formula gives to every decimal it has, and the constants here are the
    same ion written to four — near, never equal."""
    gaps = [abs(rung.mz - mz) for rung in profile.rungs]
    nearest = gaps.index(min(gaps))
    assert gaps[nearest] < 0.01, f"no rung near {mz}"
    return nearest


def a_record(energy: float, heights, activation: str = "EAD",
             compound: str = "CA-d4", mz=None, base: float = 10_000.0,
             formula: str = FORMULA, adduct: str = ADDUCT,
             precursor: float = PRECURSOR):
    """
    One record of one compound at one energy.

    `heights` are relative and are written through `entry_from_spectrum`, so
    what comes back is held relative to the record's own base peak exactly as
    a record read from a file would be.
    """
    mz = LADDER if mz is None else np.asarray(mz, dtype=float)
    name = f"{compound}_TOFMSMS_{activation}_{energy:g}CE_mix1"
    return entry_from_spectrum(
        name, mz, np.asarray(heights, dtype=float) * base,
        precursor=precursor, precursor_type=adduct, formula=formula,
        collision_energy=energy, acquired="2026-09-02T10:00:00",
        comment=f"Mix1 · TOF PI · average of 100 scans · {name}.wiff")


def a_library(records) -> SpectralLibrary:
    """A library from records, through the text so the parser is in the way."""
    return SpectralLibrary(parse_msp(format_msp(list(records))))


#: three energies with one rung walking linearly down the ladder: the
#: precursor's share falls 0.8 → 0.5 → 0.2 and -2H2O's rises to meet it
def a_ladder_walk():
    return a_library([
        a_record(10.0, [0.80, 0.10, 0.05, 0.05]),
        a_record(20.0, [0.50, 0.20, 0.20, 0.10]),
        a_record(30.0, [0.20, 0.30, 0.35, 0.15]),
    ])


# --------------------------------------------------------------------------- #
# what a profile is made of
# --------------------------------------------------------------------------- #
def test_a_profile_is_the_ladder_the_records_own_formula_predicts():
    profile = profile_of(a_ladder_walk(), "CA-d4")
    assert profile.compound == "CA-d4"
    assert profile.predicted_rungs >= 4
    described = [rung.description for rung in profile.rungs if rung.predicted]
    assert any("M+NH4" in text for text in described)
    assert any("-3H2O" in text for text in described)
    # descending m/z, the way the ladder reads
    masses = [rung.mz for rung in profile.rungs]
    assert masses == sorted(masses, reverse=True)


def test_the_shares_are_of_the_profiles_total_not_of_the_base_peak():
    """
    The point of the whole module: on the real infusions the base peak moves
    from the precursor to `[M+H-2H2O]+` to `[M+H-3H2O]+` as the energy rises,
    so a vector held relative to the base peak jumps when its own denominator
    changes rung. Here the base peak is the precursor at 10 eV and -2H2O at
    30 eV, and the shares still sum to one at both.
    """
    profile = profile_of(a_ladder_walk(), "CA-d4")
    for point in profile.points:
        assert sum(point.shares) == pytest.approx(1.0)
    low = profile.series("EAD")[0]
    high = profile.series("EAD")[-1]
    index = rung_index(profile, PRECURSOR)
    assert low.shares[index] == pytest.approx(0.80, abs=0.01)
    assert high.shares[index] == pytest.approx(0.20, abs=0.01)


def test_a_record_with_no_collision_energy_is_left_out_saying_so():
    records = [a_record(10.0, [0.8, 0.1, 0.05, 0.05]),
               a_record(20.0, [0.5, 0.2, 0.2, 0.1])]
    nameless = a_record(30.0, [0.2, 0.3, 0.35, 0.15])
    nameless.fields = {k: v for k, v in nameless.fields.items()
                       if k != "Collision_energy"}
    profile = profile_of(a_library(records + [nameless]), "CA-d4")
    assert profile.energies("EAD") == (10.0, 20.0)
    assert any("no collision energy" in reason for reason in profile.left_out)


def test_a_record_of_another_precursor_under_the_same_name_is_left_out():
    """
    The rule that keeps the two `CA-d4` infusions that isolated 839.56 out of
    CA-d4's profile. Nothing parses a file name: a record that holds fewer
    than `MIN_MATCHED` of the ladder's ions is not a spectrum of this
    precursor, and that is measured.
    """
    other = a_record(22.0, [0.9, 0.5, 0.3, 0.2],
                     mz=[800.11, 700.22, 600.33, 500.44])
    profile = profile_of(a_library([*a_ladder_walk().entries, other]), "CA-d4")
    assert [point.energy for point in profile.series("EAD")] == [10.0, 20.0, 30.0]
    assert any("fewer than" in reason for reason in profile.left_out)


def test_a_profile_is_not_written_into_the_records():
    """It is computed from the records present — see `EnergyProfile`. A
    record that carried a profile id would be making a claim about the other
    records that stopped being true the next time one was appended."""
    library = a_ladder_walk()
    profile_of(library, "CA-d4")
    for entry in library.entries:
        assert not any("profile" in str(key).lower() for key in entry.fields)
    assert "profile" not in format_msp(library.entries).lower()


# --------------------------------------------------------------------------- #
# interpolating, and refusing to
# --------------------------------------------------------------------------- #
def test_a_rungs_share_is_linear_between_the_two_energies_that_bracket_it():
    profile = profile_of(a_ladder_walk(), "CA-d4")
    index = rung_index(profile, PRECURSOR)
    at_15 = profile.at(15.0, "EAD")
    at_25 = profile.at(25.0, "EAD")
    assert at_15[index] == pytest.approx((0.80 + 0.50) / 2, abs=0.01)
    assert at_25[index] == pytest.approx((0.50 + 0.20) / 2, abs=0.01)
    # and the ends are the records themselves
    assert profile.at(10.0, "EAD") == profile.series("EAD")[0].shares
    assert profile.at(30.0, "EAD") == profile.series("EAD")[-1].shares


def test_nothing_is_extrapolated_past_the_measured_range():
    profile = profile_of(a_ladder_walk(), "CA-d4")
    assert profile.span("EAD") == (10.0, 30.0)
    assert profile.at(9.9, "EAD") is None
    assert profile.at(30.1, "EAD") is None
    assert profile.at(45.0, "EAD") is None


def test_two_activations_are_never_interpolated_across():
    """
    A record at 22 eV EAD and one at 45 eV in a collision cell are not two
    points on one curve — the same rule `standard_history` cuts its series
    on. Asked for an energy between them, the EAD profile says nothing.
    """
    library = a_library([a_record(12.0, [0.9, 0.05, 0.03, 0.02]),
                         a_record(22.0, [0.3, 0.2, 0.4, 0.1]),
                         a_record(45.0, [0.02, 0.05, 0.13, 0.80],
                                  activation="CID")])
    profile = profile_of(library, "CA-d4")
    assert set(profile.activations()) == {"EAD", "CID"}
    assert profile.energies("EAD") == (12.0, 22.0)
    assert profile.energies("CID") == (45.0,)
    # 30 eV lies between the EAD records and the CID one, and neither series
    # holds it
    assert profile.at(30.0, "EAD") is None
    assert profile.at(30.0, "CID") is None
    assert profile.at(22.0, "CID") is None


def test_an_activation_with_no_records_says_nothing():
    profile = profile_of(a_ladder_walk(), "CA-d4")
    assert profile.at(20.0, "UVPD") is None
    assert profile.series("UVPD") == []


# --------------------------------------------------------------------------- #
# what a spectrum is told
# --------------------------------------------------------------------------- #
def test_the_sweep_finds_the_energy_a_record_was_measured_at():
    library = a_ladder_walk()
    profile = profile_of(library, "CA-d4")
    query = library.entries[1]                    # the 20 eV record
    found = [one for one in match_profile(profile, query.mz, query.intensity)
             if one.activation == "EAD"]
    assert len(found) == 1
    assert found[0].energy == pytest.approx(20.0, abs=lib.ENERGY_STEP_EV)
    assert found[0].score > 0.99


def test_the_sweep_lands_between_two_records_for_a_spectrum_between_them():
    """
    The whole point: a spectrum measured at an energy nobody recorded is
    still placed, because each rung's share is interpolated. Halfway between
    the 10 and 20 eV records in share terms, the answer is ~15 eV and it is
    marked as interpolated rather than measured.
    """
    library = a_ladder_walk()
    profile = profile_of(library, "CA-d4")
    low = np.asarray(profile.at(10.0, "EAD"))
    high = np.asarray(profile.at(20.0, "EAD"))
    rungs = np.array([rung.mz for rung in profile.rungs])
    found = [one for one in match_profile(profile, rungs, (low + high) / 2)
             if one.activation == "EAD"][0]
    assert 13.0 <= found.energy <= 17.0
    assert found.interpolated
    assert "~" in found.line() and "compatible with CA-d4 EAD" in found.line()


def test_one_record_of_an_activation_says_one_energy_on_file():
    library = a_library([a_record(22.0, [0.3, 0.2, 0.4, 0.1])])
    profile = profile_of(library, "CA-d4")
    found = match_profile(profile, library.entries[0].mz,
                          library.entries[0].intensity)
    assert len(found) == 1
    assert found[0].energy is None
    assert "one energy on file" in found[0].note
    assert "22 eV" in found[0].note
    assert "no profile" in found[0].line()


def test_the_edge_of_the_measured_range_is_reported_as_the_edge():
    """
    A spectrum measured past the highest energy on file can only be placed at
    that highest energy, and `at_edge` says the records ran out there. On the
    real infusions the 45 eV record fitted CA-d4's EAD profile best at 22 eV,
    the top of its range, at 0.56.
    """
    library = a_library([a_record(10.0, [0.80, 0.10, 0.05, 0.05]),
                         a_record(20.0, [0.50, 0.20, 0.20, 0.10])])
    profile = profile_of(library, "CA-d4")
    beyond = a_record(40.0, [0.02, 0.08, 0.20, 0.70])
    found = [one for one in match_profile(profile, beyond.mz, beyond.intensity)
             if one.activation == "EAD"][0]
    assert found.energy == pytest.approx(20.0, abs=lib.ENERGY_STEP_EV)
    assert found.at_edge == "high"
    assert not found.interpolated


def test_a_spectrum_holding_none_of_the_profiles_ions_is_told_so():
    profile = profile_of(a_ladder_walk(), "CA-d4")
    found = [one for one in
             match_profile(profile, np.array([800.1, 700.2, 600.3]),
                           np.array([100.0, 50.0, 25.0]))
             if one.activation == "EAD"]
    assert found and found[0].energy is None
    assert "are in this spectrum" in found[0].note


# --------------------------------------------------------------------------- #
# through the library's own door
# --------------------------------------------------------------------------- #
def test_search_energy_leaves_the_ordinary_hit_list_alone():
    library = a_ladder_walk()
    query = library.entries[1]
    hits = library.search(query.mz, query.intensity, PRECURSOR)
    found = library.search_energy(query.mz, query.intensity, PRECURSOR)
    assert [hit.entry.name for hit in hits] == [
        hit.entry.name for hit in library.search(query.mz, query.intensity,
                                                 PRECURSOR)]
    assert found and found[0].compound == "CA-d4"
    assert found[0].energy == pytest.approx(20.0, abs=lib.ENERGY_STEP_EV)


def test_search_energy_says_nothing_about_a_compound_the_precursor_excludes():
    library = a_library([*a_ladder_walk().entries,
                         a_record(22.0, [0.4, 0.3, 0.2, 0.1],
                                  compound="DCA-d4", formula="C24H36D4O4",
                                  precursor=414.3516,
                                  mz=[414.3516, 379.3145, 361.3039, 343.2933])])
    query = library.entries[1]
    names = {one.compound
             for one in library.search_energy(query.mz, query.intensity,
                                              PRECURSOR)}
    assert names == {"CA-d4"}


def test_a_profile_is_cached_on_the_library_and_not_on_the_records():
    library = a_ladder_walk()
    first = library.profile("CA-d4")
    assert library.profile("CA-d4") is first
    assert profile_of(library, "CA-d4") is not first


def test_the_table_has_one_row_per_rung_and_one_column_per_record():
    profile = profile_of(a_ladder_walk(), "CA-d4")
    rows = profile.table()
    assert rows[0][:2] == ["Ion", "m/z"]
    assert len(rows[0]) == 2 + len(profile.points)
    assert len(rows) == 1 + len(profile.rungs)
    assert all(cell.endswith("%") for cell in rows[1][2:])
    assert "EAD 10 eV" in rows[0]


def test_the_summary_names_the_energies_and_the_records_left_out():
    other = a_record(22.0, [0.9, 0.5, 0.3, 0.2],
                     mz=[800.11, 700.22, 600.33, 500.44])
    profile = profile_of(a_library([*a_ladder_walk().entries, other]), "CA-d4")
    said = profile.summary()
    assert "CA-d4" in said and "EAD at 10, 20 and 30 eV" in said
    assert "1 record(s) left out" in said


def test_a_compound_with_no_records_profiles_to_nothing():
    profile = profile_of(a_ladder_walk(), "nothing at all")
    assert profile.rungs == () and profile.points == ()
    assert "no record" in profile.note
    assert match_profile(profile, LADDER, np.ones(4)) == []


# --------------------------------------------------------------------------- #
# the Infusions tab's own-record cell
# --------------------------------------------------------------------------- #
def an_infusion_row(record_score: float, reverse: float, profile_score: float,
                    energy: float | None = 18.0):
    """One summary row with a record and a profile match, both invented."""
    from milq.infusion_report import InfusionReport, InfusionRow

    library = a_ladder_walk()
    hit = library.search(library.entries[1].mz, library.entries[1].intensity,
                         PRECURSOR)[0]
    hit = type(hit)(hit.entry, record_score, reverse, hit.pairs,
                    hit.of_library, hit.of_query)
    report = InfusionReport(sample="sample", file="CA-d4.wiff")
    report.hit = hit
    return InfusionRow(report=report, energy=lib.EnergyMatch(
        compound="CA-d4", activation="EAD", energy=energy,
        score=profile_score, over_all=0.2, matched=8, of_profile=12,
        measured=(12.0, 22.0)))


def test_the_record_cell_mentions_the_profile_only_when_it_beats_the_record():
    beaten = an_infusion_row(0.29, 0.56, 0.81)
    assert "EAD ~18 eV, 0.81" in beaten.record
    assert beaten.record.startswith("CA-d4_TOFMSMS")
    # equal is not beaten: on the real infusions the profile lands on one of
    # the two records and scores exactly what that record scored
    tied = an_infusion_row(0.29, 0.56, 0.56)
    assert "eV" not in tied.record
    assert tied.record == tied.report.hit.entry.name
    # and neither is beaten by floating-point noise, which is what the two
    # scores actually differ by when the sweep lands on the record itself
    noise = an_infusion_row(1.0, 1.0, 0.9999999999998277)
    assert noise.record == noise.report.hit.entry.name
    just_under = an_infusion_row(0.29, 0.56, 0.56 + lib.PROFILE_BETTER_BY / 2)
    assert "eV" not in just_under.record


def test_the_record_cell_says_nothing_extra_where_there_is_no_profile():
    none_at_all = an_infusion_row(0.29, 0.10, 0.0, energy=None)
    assert none_at_all.record == none_at_all.report.hit.entry.name
    assert none_at_all.cells()[SUMMARY_COLUMNS.index("Library record")] == none_at_all.record
    assert none_at_all.report_cells()[8].startswith(none_at_all.record)
