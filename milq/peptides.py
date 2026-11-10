"""
Peptides without a window: masses, fragments, annotation, digestion and a
screen of data-dependent MS2 with a target–decoy false discovery rate.

Written for endogenous peptides in HILIC ESI+ IDA data, and nothing in it
is specific to one sample type or protein. Every number
is monoisotopic.

Sequence syntax (`parse`):

    QPLAPVHNPISV            plain residues; I and L are isobaric
    pE-PLAPVHNPISV          `pE` is a pyroglutamate residue (from Q or E,
    pEPLAPVHNPISV           111.032028 either way)
    [pyroGlu]QPLAPVHNPISV   pyroGlu on the N-terminal Q (−17.026549) or E
    pGlu-QPLAPVHNPISV       (−18.010565); `pGlu-` is the same
    S[Phospho]              on S, T or Y: +79.966331
    M[Oxidation]            +15.994915
    …V[Amidated]            C-terminal amide: −0.984016
    [Acetyl]-PEPTIDE        N-terminal acetyl: +42.010565
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field

import numpy as np

PROTON = 1.007276466812
H2O = 18.0105646863
NH3 = 17.0265491015
CO = 27.9949146221
NEUTRON = 1.0033548378

RESIDUES = {
    "G": 57.02146372, "A": 71.03711379, "S": 87.03202841, "P": 97.05276385,
    "V": 99.06841391, "T": 101.04767847, "C": 103.00918448, "L": 113.08406398,
    "I": 113.08406398, "N": 114.04292744, "D": 115.02694303, "Q": 128.05857751,
    "K": 128.09496302, "E": 129.04259309, "M": 131.04048461, "H": 137.05891186,
    "F": 147.06841391, "R": 156.10111103, "Y": 163.06332853, "W": 186.07931295,
}
PYROGLU_RESIDUE = RESIDUES["Q"] - NH3          # 111.032028, = E − H2O

#: name → (mass shift, where: residues it may sit on, or "N"/"C" terminus)
MODIFICATIONS = {
    "pyroglu": (None, "NQE"),                   # depends on the residue
    "phospho": (79.966331, "STY"),
    "oxidation": (15.994915, "M"),
    "amidated": (-0.984016, "C"),
    "acetyl": (42.010565, "N"),
}
_ALIASES = {"pyroglu": "pyroglu", "pglu": "pyroglu", "pe": "pyroglu",
            "phospho": "phospho", "p": "phospho", "oxidation": "oxidation",
            "ox": "oxidation", "amidated": "amidated", "amide": "amidated",
            "nh2": "amidated", "acetyl": "acetyl", "ac": "acetyl"}
#: the digest option names
DIGEST_MODS = {"pyroglu-q": ("pyroglu", "Q"), "pyroglu-e": ("pyroglu", "E"),
               "phospho-st": ("phospho", "ST"), "phospho-sty": ("phospho", "STY"),
               "ox-m": ("oxidation", "M"), "amidated": ("amidated", ""),
               "acetyl": ("acetyl", "")}


class PeptideError(ValueError):
    pass


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Peptide:
    """A sequence with its modifications, as residue masses."""

    residues: tuple[str, ...]           # one letter each ("pE" for pyroGlu)
    masses: tuple[float, ...]           # residue masses, modifications included
    mods: tuple[tuple[int, str], ...] = ()   # (position, name); -1 N-term, n C-term
    n_term: float = 0.0
    c_term: float = 0.0

    @property
    def sequence(self) -> str:
        return "".join("Q" if r == "pE" else r for r in self.residues)

    @property
    def neutral_mass(self) -> float:
        return float(sum(self.masses)) + H2O + self.n_term + self.c_term

    def mz(self, charge: int) -> float:
        return (self.neutral_mass + charge * PROTON) / charge

    def __str__(self) -> str:
        return format_peptide(self)

    @property
    def mod_text(self) -> str:
        return ";".join(f"{name}@{'N-term' if pos < 0 else 'C-term' if pos >= len(self.residues) else self.residues[pos] + str(pos + 1)}"
                        for pos, name in self.mods)


def _apply(name: str, position: int, residues, masses, n_c) -> tuple[int, str]:
    """Put one modification on a residue (or terminus); returns the record."""
    if name == "pyroglu":
        if position != 0 or not residues:
            raise PeptideError("pyroGlu sits only on the N-terminal residue")
        first = residues[0]
        if first in ("Q", "pE"):
            masses[0] = PYROGLU_RESIDUE
        elif first == "E":
            masses[0] = RESIDUES["E"] - H2O
        else:
            raise PeptideError(f"pyroGlu needs an N-terminal Q or E, not {first}")
        residues[0] = "pE" if first != "E" else "E"
        return (0, "pyroGlu")
    shift, where = MODIFICATIONS[name]
    if name == "acetyl":
        n_c[0] += shift
        return (-1, "Acetyl")
    if name == "amidated":
        n_c[1] += shift
        return (len(residues), "Amidated")
    if residues[position] not in where:
        raise PeptideError(f"{name} cannot sit on {residues[position]}")
    masses[position] += shift
    return (position, name.capitalize())


def parse(text: str) -> Peptide:
    """A peptide from the syntax in the module docstring."""
    source = str(text).strip()
    if not source:
        raise PeptideError("empty sequence")
    residues: list[str] = []
    masses: list[float] = []
    pending_n: list[str] = []
    mods: list[tuple[int, str]] = []
    n_c = [0.0, 0.0]
    i = 0
    if source.startswith("pGlu-") or source.startswith("pGlu"):
        pending_n.append("pyroglu")
        i = 5 if source.startswith("pGlu-") else 4
    while i < len(source):
        ch = source[i]
        if source.startswith("pE", i) and not residues:
            residues.append("pE")
            masses.append(PYROGLU_RESIDUE)
            mods.append((0, "pyroGlu"))
            i += 2
            continue
        if ch == "[":
            close = source.find("]", i)
            if close < 0:
                raise PeptideError(f"unclosed [ in {source!r}")
            name = _ALIASES.get(source[i + 1:close].strip().lower().replace("-", ""))
            if name is None:
                raise PeptideError(f"unknown modification {source[i + 1:close]!r}")
            if name in ("pyroglu", "acetyl") and not residues:
                pending_n.append(name)
            elif name == "amidated":
                pending_n.append("__amidated__")
            else:
                if not residues:
                    raise PeptideError(f"{name} needs a residue before it")
                mods.append(_apply(name, len(residues) - 1, residues, masses, n_c))
            i = close + 1
            continue
        if ch in "-. ":
            i += 1
            continue
        if ch.upper() in RESIDUES and ch.isupper():
            residues.append(ch)
            masses.append(RESIDUES[ch])
            i += 1
            continue
        raise PeptideError(f"not a residue: {ch!r} in {source!r}")
    if not residues:
        raise PeptideError("no residues")
    for name in pending_n:
        if name == "__amidated__":
            mods.append(_apply("amidated", 0, residues, masses, n_c))
        else:
            mods.append(_apply(name, 0, residues, masses, n_c))
    return Peptide(tuple(residues), tuple(masses), tuple(sorted(set(mods))),
                   n_c[0], n_c[1])


def format_peptide(peptide: Peptide) -> str:
    out = []
    names = {}
    for pos, name in peptide.mods:
        names.setdefault(pos, []).append(name)
    if any(n == "Acetyl" for n in names.get(-1, [])):
        out.append("[Acetyl]-")
    for index, residue in enumerate(peptide.residues):
        if index == 0 and "pyroGlu" in names.get(0, []):
            out.append("pE" if residue == "pE" else "[pyroGlu]" + residue)
        else:
            out.append(residue)
        for name in names.get(index, []):
            if name != "pyroGlu":
                out.append(f"[{name}]")
    if any(n == "Amidated" for n in names.get(len(peptide.residues), [])):
        out.append("[Amidated]")
    return "".join(out)


def mass(text: str, charges=(1, 2, 3, 4)) -> dict:
    """`peptide mass`: monoisotopic mass and m/z for each charge."""
    peptide = parse(text)
    return {"peptide": format_peptide(peptide), "sequence": peptide.sequence,
            "modifications": peptide.mod_text,
            "monoisotopic_mass": round(peptide.neutral_mass, 6),
            "mz": [{"charge": z, "mz": round(peptide.mz(z), 6)} for z in charges],
            "isobaric": "I and L are isobaric (113.084064)"
            if any(r in "IL" for r in peptide.residues) else ""}


# --------------------------------------------------------------------------- #
# fragments
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Ion:
    name: str            # b3, y5, a2, b3-H2O, y4-NH3, int-PLA, imm-H
    series: str          # b, a, y, b-H2O, y-NH3, internal, immonium
    index: int           # cleavage number (b/a/y), start for internal
    charge: int
    mz: float


def fragments(peptide: Peptide | str, charges=(1, 2, 3), internal: bool = True,
              immonium: bool = True, neutral_losses: bool = True) -> list[Ion]:
    """b, a, y (and b−H2O, y−NH3, internal b-type, immonium) ions, by name."""
    if isinstance(peptide, str):
        peptide = parse(peptide)
    m = np.asarray(peptide.masses, dtype=float)
    n = m.size
    prefix = np.cumsum(m) + peptide.n_term
    suffix = np.cumsum(m[::-1]) + peptide.c_term + H2O
    ions: list[Ion] = []
    for z in charges:
        for k in range(1, n):
            b = prefix[k - 1]
            y = suffix[k - 1]
            ions.append(Ion(f"b{k}" + ("+" * (z - 1)), "b", k, z, (b + z * PROTON) / z))
            ions.append(Ion(f"a{k}" + ("+" * (z - 1)), "a", k, z, (b - CO + z * PROTON) / z))
            ions.append(Ion(f"y{k}" + ("+" * (z - 1)), "y", k, z, (y + z * PROTON) / z))
            if neutral_losses:
                ions.append(Ion(f"b{k}-H2O" + ("+" * (z - 1)), "b-H2O", k, z,
                                (b - H2O + z * PROTON) / z))
                ions.append(Ion(f"y{k}-NH3" + ("+" * (z - 1)), "y-NH3", k, z,
                                (y - NH3 + z * PROTON) / z))
    if internal:
        # internal b-type ions: residues i..j with neither terminus, singly charged
        for i in range(1, n - 1):
            total = 0.0
            for j in range(i, n - 1):
                total += m[j]
                if j - i < 1:
                    continue
                label = "".join(peptide.residues[i:j + 1])
                ions.append(Ion(f"int-{label}", "internal", i + 1, 1, total + PROTON))
    if immonium:
        seen = set()
        for residue, value in zip(peptide.residues, peptide.masses):
            key = round(value, 4)
            if key in seen:
                continue
            seen.add(key)
            ions.append(Ion(f"imm-{residue}", "immonium", 0, 1, value - CO + PROTON))
    ions.sort(key=lambda ion: ion.mz)
    return ions


# --------------------------------------------------------------------------- #
# annotation
# --------------------------------------------------------------------------- #
@dataclass
class Annotation:
    peptide: str
    charge: int
    tol_ppm: float
    matches: list[dict]
    coverage: str
    explained: float
    unexplained: list[dict]
    n_peaks: int


def match_peaks(mz, intensity, ions: list[Ion], tol_ppm: float):
    """Each peak's best ion within the tolerance: (peak index, ion, ppm)."""
    mz = np.asarray(mz, dtype=float)
    theory = np.array([ion.mz for ion in ions], dtype=float)
    found = []
    if theory.size == 0:
        return found
    for index, value in enumerate(mz):
        where = np.searchsorted(theory, value)
        best = None
        for j in (where - 1, where, where + 1):
            if 0 <= j < theory.size:
                ppm = (value - theory[j]) / theory[j] * 1e6
                if abs(ppm) <= tol_ppm and (best is None or abs(ppm) < abs(best[2])):
                    best = (index, ions[j], ppm)
        if best is not None:
            found.append(best)
    return found


def annotate(mz, intensity, peptide: Peptide | str, charge: int = 2,
             tol_ppm: float = 20.0, top_unexplained: int = 10) -> Annotation:
    """Matched ions with ppm, the coverage map, the share explained."""
    if isinstance(peptide, str):
        peptide = parse(peptide)
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    ions = fragments(peptide, charges=tuple(range(1, max(1, min(int(charge), 3)) + 1)))
    precursor = [Ion(f"[M+{z}H]{z}+", "precursor", 0, z, peptide.mz(z))
                 for z in range(1, int(charge) + 1)]
    ions = sorted(ions + precursor, key=lambda ion: ion.mz)
    found = match_peaks(mz, intensity, ions, tol_ppm)
    total = float(intensity.sum()) or 1.0
    used = {index for index, _ion, _ppm in found}
    matches = [{"mz": round(float(mz[i]), 4), "intensity": float(intensity[i]),
                "ion": ion.name, "series": ion.series, "charge": ion.charge,
                "theoretical_mz": round(ion.mz, 6), "ppm": round(ppm, 2)}
               for i, ion, ppm in found]
    n = len(peptide.residues)
    b_cut = {ion.index for _i, ion, _p in found if ion.series in ("b", "a", "b-H2O")}
    y_cut = {n - ion.index for _i, ion, _p in found if ion.series in ("y", "y-NH3")}
    # one character per bond between residues: b, y, both (|) or none (.)
    bonds = []
    for k in range(1, n):
        bonds.append("|" if k in b_cut and k in y_cut else "b" if k in b_cut
                     else "y" if k in y_cut else ".")
    coverage = peptide.residues[0] + "".join(
        f"{bond}{residue}" for bond, residue in zip(bonds, peptide.residues[1:]))
    rest = [i for i in np.argsort(intensity)[::-1] if i not in used][:top_unexplained]
    unexplained = [{"mz": round(float(mz[i]), 4), "intensity": float(intensity[i]),
                    "relative": round(100.0 * float(intensity[i]) / float(intensity.max()), 2)}
                   for i in rest]
    return Annotation(format_peptide(peptide), int(charge), float(tol_ppm), matches,
                      coverage, round(sum(intensity[i] for i in used) / total, 4),
                      unexplained, int(mz.size))


def read_spectrum_file(path: str) -> tuple[np.ndarray, np.ndarray, float | None]:
    """A peak list from a TSV (m/z, intensity), an MSP (first record) or a
    milq `spectrum` JSON document. Returns (mz, intensity, precursor)."""
    import json

    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    lower = path.lower()
    if lower.endswith(".json"):
        doc = json.loads(text)
        peaks = doc.get("peaks", [])
        return (np.array([p["mz"] for p in peaks], dtype=float),
                np.array([p["intensity"] for p in peaks], dtype=float),
                doc.get("parent_mz"))
    if lower.endswith(".msp"):
        from .library import parse_msp

        entries = parse_msp(text, os.path.basename(path))
        if not entries:
            raise PeptideError(f"no record in {path}")
        first = entries[0]
        return (np.asarray(first.mz, dtype=float), np.asarray(first.intensity, dtype=float),
                first.precursor)
    mz, height = [], []
    for line in text.splitlines():
        parts = re.split(r"[\t,; ]+", line.strip())
        if len(parts) < 2:
            continue
        try:
            mz.append(float(parts[0]))
            height.append(float(parts[1]))
        except ValueError:
            continue                       # a header
    return np.array(mz), np.array(height), None


# --------------------------------------------------------------------------- #
# FASTA and digestion
# --------------------------------------------------------------------------- #
def read_fasta(path: str, accessions=None) -> dict[str, str]:
    """Accession → sequence; `accessions` restricts to those (UniProt or bare)."""
    wanted = {a.strip() for a in (accessions or []) if a.strip()}
    out: dict[str, str] = {}
    name, chunks = None, []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith(">"):
                if name is not None and (not wanted or name in wanted):
                    out[name] = "".join(chunks)
                header = line[1:].split()[0]
                parts = header.split("|")
                name = parts[1] if len(parts) >= 3 else header
                chunks = []
            elif line:
                chunks.append(line)
    if name is not None and (not wanted or name in wanted):
        out[name] = "".join(chunks)
    missing = wanted - set(out)
    if missing:
        raise PeptideError(f"not in {os.path.basename(path)}: {', '.join(sorted(missing))}")
    return out


@dataclass(frozen=True)
class Candidate:
    peptide: Peptide
    protein: str
    start: int            # 1-based
    end: int
    decoy: bool = False


def _variants(sequence: str, mods: list[str], max_mods: int):
    """Every modified form of a sequence the options allow, up to max_mods."""
    sites = []
    for option in mods:
        if option not in DIGEST_MODS:
            raise PeptideError(f"unknown digest modification {option!r} "
                               f"({', '.join(DIGEST_MODS)})")
        name, residues = DIGEST_MODS[option]
        if name == "pyroglu":
            if sequence[0] in residues:
                sites.append((0, "pyroglu"))
        elif name in ("amidated", "acetyl"):
            sites.append((0 if name == "acetyl" else len(sequence) - 1, name))
        else:
            sites.extend((i, name) for i, r in enumerate(sequence) if r in residues)
    from itertools import combinations

    for k in range(0, min(max_mods, len(sites)) + 1):
        for chosen in combinations(sites, k):
            residues = list(sequence)
            masses = [RESIDUES[r] for r in residues]
            n_c = [0.0, 0.0]
            records = []
            try:
                for position, name in chosen:
                    records.append(_apply(name, position, residues, masses, n_c))
            except PeptideError:
                continue
            yield Peptide(tuple(residues), tuple(masses), tuple(sorted(records)),
                          n_c[0], n_c[1])


def digest(proteins: dict[str, str], nonspecific: bool = True, length=(4, 40),
           mods=(), max_mods: int = 3, decoy: bool = False) -> list[Candidate]:
    """Every sub-sequence (non-specific) of each protein, with its variants.
    `decoy` reverses each protein first (target–decoy)."""
    if not nonspecific:
        raise PeptideError("only --nonspecific is implemented")
    lo, hi = int(length[0]), int(length[1])
    out: list[Candidate] = []
    for accession, sequence in proteins.items():
        source = sequence[::-1] if decoy else sequence
        clean = "".join(r for r in source if r in RESIDUES)
        for start in range(len(clean)):
            for size in range(lo, hi + 1):
                if start + size > len(clean):
                    break
                piece = clean[start:start + size]
                for peptide in _variants(piece, list(mods), max_mods):
                    out.append(Candidate(peptide, ("DECOY_" if decoy else "") + accession,
                                         start + 1, start + size, decoy))
    return out


def parse_charges(text) -> tuple[int, ...]:
    if isinstance(text, (list, tuple)):
        return tuple(int(t) for t in text)
    text = str(text or "1-4")
    if "-" in text:
        a, b = text.split("-", 1)
        return tuple(range(int(a), int(b) + 1))
    return tuple(int(t) for t in text.replace(",", " ").split())


# --------------------------------------------------------------------------- #
# the screen
# --------------------------------------------------------------------------- #
#: the series a screen scores; internal and immonium ions explain, they do
#: not identify
SCORED = ("b", "y", "a", "b-H2O", "y-NH3")


@dataclass
class Psm:
    """One spectrum's best candidate."""

    candidate: Candidate
    charge: int
    path: str
    channel: int
    scan: int
    rt: float
    parent_mz: float
    measured_mz: float
    isotope_error: int
    ppm: float
    matched: int
    explained: float
    longest: int
    hyperscore: float
    q_value: float = 1.0
    mz: np.ndarray = field(default=None, repr=False)
    intensity: np.ndarray = field(default=None, repr=False)
    matches: list = field(default_factory=list, repr=False)


def score(mz, intensity, peptide: Peptide, charge: int, tol_ppm: float):
    """(matched, explained share, longest series, hyperscore, matches)."""
    ions = [ion for ion in fragments(peptide, charges=tuple(range(1, min(charge, 2) + 1)),
                                     internal=False, immonium=False)
            if ion.series in SCORED]
    found = match_peaks(mz, intensity, ions, tol_ppm)
    if not found:
        return 0, 0.0, 0, 0.0, []
    total = float(np.sum(intensity)) or 1.0
    peaks = {i for i, _ion, _p in found}
    explained = sum(float(intensity[i]) for i in peaks) / total
    b = sorted({ion.index for _i, ion, _p in found if ion.series == "b"})
    y = sorted({ion.index for _i, ion, _p in found if ion.series == "y"})

    def longest(indices):
        best = run = 0
        previous = None
        for k in indices:
            run = run + 1 if previous is not None and k == previous + 1 else 1
            best = max(best, run)
            previous = k
        return best

    matched_intensity = sum(float(intensity[i]) for i, ion, _p in found
                            if ion.series in ("b", "y"))
    # X!Tandem's hyperscore: log of the dot product times the factorials of
    # the b and y counts
    hyper = (math.log10(max(matched_intensity, 1.0))
             + math.log10(math.factorial(len(b))) + math.log10(math.factorial(len(y))))
    return len(peaks), explained, max(longest(b), longest(y)), hyper, found


def q_values(psms: list[Psm]) -> None:
    """Target–decoy q-values over the best match per spectrum, in place."""
    ordered = sorted(psms, key=lambda p: -p.hyperscore)
    decoys = targets = 0
    fdr = []
    for psm in ordered:
        if psm.candidate.decoy:
            decoys += 1
        else:
            targets += 1
        fdr.append(decoys / max(targets, 1))
    running = 1.0
    for index in range(len(ordered) - 1, -1, -1):
        running = min(running, fdr[index])
        ordered[index].q_value = running


@dataclass
class ScreenResult:
    psms: list[Psm]                 # the best candidate of every spectrum scored
    spectra: int                    # MS2 scans looked at
    candidates: int                 # target candidates in the search space
    skipped: list[dict]
    fdr: float

    @property
    def accepted(self) -> list[Psm]:
        return [p for p in self.psms if not p.candidate.decoy and p.q_value <= self.fdr]

    def peptides(self) -> list[dict]:
        """One row per peptide and charge, its best spectrum, ranked."""
        groups: dict[tuple, list[Psm]] = {}
        for psm in self.psms:
            if psm.candidate.decoy:
                continue
            key = (str(psm.candidate.peptide), psm.charge)
            groups.setdefault(key, []).append(psm)
        rows = []
        for (text, charge), members in groups.items():
            best = max(members, key=lambda p: p.hyperscore)
            c = best.candidate
            rows.append({
                "peptide": text, "sequence": c.peptide.sequence,
                "modifications": c.peptide.mod_text, "protein": c.protein,
                "start": c.start, "end": c.end, "charge": charge,
                "mz": round(c.peptide.mz(charge), 6),
                "rt": round(best.rt, 4), "ppm": round(float(best.ppm), 2),
                "isotope_error": best.isotope_error,
                "matched": best.matched, "longest_series": best.longest,
                "explained": round(best.explained, 4),
                "score": round(best.hyperscore, 3),
                "q_value": round(min(p.q_value for p in members), 6),
                "scans": len(members),
                "files": ";".join(sorted({os.path.basename(p.path) for p in members})),
                "fragment": best_fragment(best),
            })
        rows.sort(key=lambda r: (r["q_value"], -r["score"]))
        return rows


def _index(candidates: list[Candidate]):
    masses = np.array([c.peptide.neutral_mass for c in candidates], dtype=float)
    order = np.argsort(masses)
    return masses[order], [candidates[i] for i in order]


def _survey_mass(sample, parent: float, rt: float, cache: dict) -> float | None:
    """The precursor as the survey measured it at that time, or None."""
    from .precursor import in_spectrum

    surveys = [c for c in sample.channels if c.info.is_ms1
               and c.info.start_mass <= parent <= c.info.end_mass]
    if not surveys:
        return None
    survey = surveys[0]
    scan = survey.scan_at_rt(rt)
    key = (survey.index, scan)
    if key not in cache:
        try:
            cache[key] = survey.spectrum(scan, add_zeros=False)
        except Exception:
            cache[key] = (np.zeros(0), np.zeros(0))
        if len(cache) > 64:
            cache.pop(next(iter(cache)))
    mz, height = cache[key]
    near = np.abs(mz - parent) <= 0.06
    if not near.any():
        return None
    found = in_spectrum(mz[near], height[near], parent, 0.05)
    return None if found is None else float(found[0])


def screen(paths, proteins: dict[str, str], length=(4, 40), mods=(),
           max_mods: int = 3, charges=(1, 2, 3, 4), ppm: float = 15.0,
           fragment_ppm: float = 20.0, decoy: bool = True,
           isotope_errors=(-1, 0, 1), fdr: float = 0.01, top_peaks: int = 150,
           min_matched: int = 4, open_file=None, progress=None) -> ScreenResult:
    """
    Every MS2 scan of every file, matched by its own precursor (refined
    from the survey at that time, isotope errors −1/0/+1 allowed) against
    the digest, scored by its fragments, and judged by reversed decoys.
    """
    from . import centroiding
    from .contract import open_file as default_open

    open_file = open_file or default_open
    targets = digest(proteins, True, length, mods, max_mods)
    pool = targets + (digest(proteins, True, length, mods, max_mods, decoy=True)
                      if decoy else [])
    masses, ordered = _index(pool)
    psms: list[Psm] = []
    skipped: list[dict] = []
    spectra = 0
    for path in paths:
        try:
            reader = open_file(path)
        except Exception as exc:
            skipped.append({"path": str(path), "reason": str(getattr(exc, "message", exc))})
            continue
        for s_index in range(len(reader.sample_names)):
            sample = reader.sample(s_index)
            survey_cache: dict = {}
            for channel in sample.channels:
                if channel.info.is_ms1:
                    continue
                details = channel.scan_details()
                times = channel.rt
                for scan in np.nonzero(np.isfinite(details.parent_mz))[0]:
                    spectra += 1
                    parent = float(details.parent_mz[scan])
                    rt = float(times[scan]) if scan < len(times) else 0.0
                    measured = _survey_mass(sample, parent, rt, survey_cache) or parent
                    stated = int(details.charge[scan]) if scan < len(details.charge) else 0
                    tried = (stated,) if stated > 0 else tuple(charges)
                    hits = []
                    for z in tried:
                        neutral = measured * z - z * PROTON
                        for iso in isotope_errors:
                            target = neutral - iso * NEUTRON
                            tol = target * ppm * 1e-6
                            lo = np.searchsorted(masses, target - tol)
                            hi = np.searchsorted(masses, target + tol, side="right")
                            for k in range(lo, hi):
                                hits.append((ordered[k], z, iso,
                                             (target - masses[k]) / masses[k] * 1e6))
                    if not hits:
                        continue
                    profile = channel.spectrum(int(scan), add_zeros=False)
                    mz, height, _how = centroiding.centroids(
                        channel, profile[0], profile[1], scan=int(scan))
                    if len(mz) > top_peaks:
                        keep = np.sort(np.argsort(height)[::-1][:top_peaks])
                        mz, height = mz[keep], height[keep]
                    best = None
                    for candidate, z, iso, error in hits:
                        matched, explained, longest, hyper, found = score(
                            mz, height, candidate.peptide, z, fragment_ppm)
                        if matched < min_matched:
                            continue
                        if best is None or hyper > best.hyperscore:
                            best = Psm(candidate, z, str(path), int(channel.index),
                                       int(scan), rt, parent, measured, iso, error,
                                       matched, explained, longest, hyper,
                                       mz=mz, intensity=height, matches=found)
                    if best is not None:
                        psms.append(best)
                if progress is not None:
                    progress(str(path), int(channel.index), spectra)
    q_values(psms)
    return ScreenResult(psms, spectra, len(targets), skipped, float(fdr))


def best_fragment(psm: Psm) -> float | None:
    """The theoretical m/z of the strongest matched b or y ion."""
    best = None
    for index, ion, _ppm in psm.matches:
        if ion.series not in ("b", "y"):
            continue
        height = float(psm.intensity[index])
        if best is None or height > best[0]:
            best = (height, ion.mz)
    return None if best is None else round(float(best[1]), 6)


def components(rows: list[dict], fdr: float = 0.01):
    """
    The accepted peptides as MIL-Q components (rows of `ScreenResult.
    peptides()`, or the screen's TSV read back): the precursor at its
    charge in the survey, the strongest matched fragment, the retention
    time, so a batch can be quantified by the ordinary path.
    """
    from .components import Component

    out = []
    for row in rows:
        if float(row["q_value"]) > fdr:
            continue
        charge = int(row["charge"])
        fragment = row.get("fragment")
        out.append(Component(
            name=f"{row['peptide']} {charge}+", precursor=float(row["mz"]),
            fragment=float(fragment) if fragment not in (None, "") else None,
            rt=float(row["rt"]), group="peptide",
            adduct=f"[M+{charge}H]{charge}+"))
    return out
