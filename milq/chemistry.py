"""
Elemental composition tools: formula parsing, exact masses, isotope patterns,
mass accuracy, formula finding, and the lipid shorthand read both ways — a
name into a formula (`formula_from_name`) and a mass back into the names that
carry it (`names_for_mass`).

Masses are monoisotopic unless stated otherwise. Abundances come from the
IUPAC 2013 representative isotopic compositions.

An adduct here is more than an offset. It also says what becomes of the
charge when the ion breaks up, because that is what decides which masses a
product spectrum can hold, and getting it wrong is not a rounding error — it
moves every predicted fragment by 17 Da:

- **A proton adduct** (`[M+H]+`, `[M-H]-`, `[M+2H]2+`) keeps its charge on
  whichever piece holds it. The fragments are the protonated — or
  deprotonated — pieces, which is what the enumerator already assumes.
- **A labile adduct** (`[M+NH4]+`, and in negative mode `[M+HCOO]-`,
  `[M+CH3COO]-`, `[M+Cl]-`) is held by hydrogen bonds and nothing stronger.
  It leaves as a neutral — ammonia, formic acid, acetic acid, hydrogen
  chloride — and hands over a proton on the way, so the ion that fragments
  is `[M+H]+` (or `[M-H]-`) and every fragment carries that, not the adduct.
  This is why an ammoniated precursor at 430.35 shows a ladder starting at
  413.32 and nothing at all 17 Da higher: `[M+NH4-H2O]+` is not a species,
  because the ammonia is long gone before a hydroxyl leaves.
- **A metal adduct** (`[M+Na]+`, `[M+K]+`) is a coordinate bond, and the
  metal stays on the piece that keeps the coordinating site — which the
  arithmetic cannot know. Both are therefore offered, `[piece+Na]+` and
  `[piece+H]+`, and each ion says which was assumed.

`identify_adduct` runs this backwards: given a formula and the precursor the
method was written with, it says which adduct that number *is*, with the
error, and refuses rather than guessing when nothing fits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

ELECTRON_MASS = 0.000548579909
PROTON_MASS = 1.007276466879

#: element -> [(isotope mass, natural abundance), ...], most abundant first
ISOTOPES: dict[str, list[tuple[float, float]]] = {
    "H": [(1.00782503207, 0.999885), (2.01410177785, 0.000115)],
    "D": [(2.01410177785, 1.0)],
    "C": [(12.0, 0.9893), (13.00335483778, 0.0107)],
    "N": [(14.0030740048, 0.99636), (15.0001088982, 0.00364)],
    "O": [(15.9949146196, 0.99757), (16.9991317012, 0.00038), (17.9991596129, 0.00205)],
    "F": [(18.99840322, 1.0)],
    "Na": [(22.9897692809, 1.0)],
    "Si": [(27.9769265325, 0.92223), (28.976494700, 0.04685), (29.973770171, 0.03092)],
    "P": [(30.97376163, 1.0)],
    "S": [(31.97207100, 0.9499), (32.97145876, 0.0075), (33.96786690, 0.0425),
          (35.96708076, 0.0001)],
    "Cl": [(34.96885268, 0.7576), (36.96590259, 0.2424)],
    "K": [(38.96370668, 0.932581), (39.96399848, 0.000117), (40.96182576, 0.067302)],
    "Br": [(78.9183371, 0.5069), (80.9162906, 0.4931)],
    "I": [(126.904473, 1.0)],
    "Se": [(79.9165213, 0.4961), (77.9173091, 0.2377), (81.9166994, 0.0873),
           (76.919914, 0.0763), (75.9192134, 0.0937), (73.9224764, 0.0089)],
}

#: valence used for the ring-plus-double-bond equivalent
VALENCE: dict[str, int] = {
    "H": 1, "D": 1, "F": 1, "Cl": 1, "Br": 1, "I": 1, "Na": 1, "K": 1,
    "O": 2, "S": 2, "Se": 2,
    "N": 3, "P": 3,
    "C": 4, "Si": 4,
}

# An isotope written as [13C] or [2H]; D is accepted as shorthand for [2H].
_TOKEN = re.compile(r"(\[\d+[A-Z][a-z]?\]|[A-Z][a-z]?)(\d*)")
_BRACKET = re.compile(r"\[(\d+)([A-Z][a-z]?)\]")


class FormulaError(ValueError):
    """Raised for a formula that cannot be parsed or uses unknown elements."""


def _resolve_isotope(token: str) -> str:
    """Turn `[13C]` into a key of ISOTOPES, adding it on first use."""
    match = _BRACKET.fullmatch(token)
    if match is None:
        return token
    nucleons, element = int(match.group(1)), match.group(2)
    if element not in ISOTOPES:
        raise FormulaError(f"unknown element: {element}")
    for mass, _abundance in ISOTOPES[element]:
        if round(mass) == nucleons:
            ISOTOPES.setdefault(token, [(mass, 1.0)])
            VALENCE.setdefault(token, VALENCE.get(element, 0))
            return token
    raise FormulaError(f"{element} has no isotope with mass number {nucleons}")


def parse_formula(formula: str) -> dict[str, int]:
    """
    Parse a molecular formula into element counts.

    Handles nested groups and multipliers, `C18H32O3`, `Ca(NO3)2`, and single
    isotopes written in brackets: `[13C]` or `D` for deuterium. Counts of zero
    are dropped.
    """
    text = formula.strip().replace(" ", "")
    if not text:
        return {}
    counts, stack = {}, []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            stack.append(counts)
            counts = {}
            index += 1
            continue
        if char == ")":
            if not stack:
                raise FormulaError("unbalanced parentheses")
            index += 1
            digits = ""
            while index < len(text) and text[index].isdigit():
                digits += text[index]
                index += 1
            multiplier = int(digits) if digits else 1
            inner, counts = counts, stack.pop()
            for element, number in inner.items():
                counts[element] = counts.get(element, 0) + number * multiplier
            continue
        match = _TOKEN.match(text, index)
        if match is None:
            raise FormulaError(f"cannot read {formula!r} at position {index}")
        token, digits = match.group(1), match.group(2)
        element = _resolve_isotope(token)
        if element not in ISOTOPES:
            raise FormulaError(f"unknown element: {element}")
        counts[element] = counts.get(element, 0) + (int(digits) if digits else 1)
        index = match.end()
    if stack:
        raise FormulaError("unbalanced parentheses")
    return {element: n for element, n in counts.items() if n}


def format_formula(counts: dict[str, int]) -> str:
    """Render element counts in Hill order (C, H, then alphabetical)."""
    remaining = dict(counts)
    parts = []
    for element in ("C", "H"):
        if remaining.pop(element, 0):
            n = counts[element]
            parts.append(element if n == 1 else f"{element}{n}")
    for element in sorted(remaining):
        n = remaining[element]
        if n:
            parts.append(element if n == 1 else f"{element}{n}")
    return "".join(parts)


def monoisotopic_mass(counts: dict[str, int]) -> float:
    """Mass built from the most abundant isotope of each element."""
    return sum(ISOTOPES[element][0][0] * n for element, n in counts.items())


def average_mass(counts: dict[str, int]) -> float:
    """Mass weighted by natural abundance, as used for large molecules."""
    total = 0.0
    for element, n in counts.items():
        isotopes = ISOTOPES[element]
        weight = sum(abundance for _mass, abundance in isotopes) or 1.0
        total += n * sum(mass * abundance for mass, abundance in isotopes) / weight
    return total


def rdbe(counts: dict[str, int]) -> float:
    """
    Rings plus double bonds. Half-integer values mean an odd-electron species,
    which for an even-electron ion signals an impossible formula.
    """
    total = 2.0
    for element, n in counts.items():
        total += n * (VALENCE.get(element, 2) - 2)
    return total / 2.0


# --------------------------------------------------------------------------- #
# lipid shorthand -> formula
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LipidClass:
    """
    How a class's formula is built from its chains.

    Every lipid in the shorthand is a head group plus one, two or three
    chains, and the arithmetic is the same for all of them: the chains
    contribute their carbons, and every double bond takes two hydrogens
    away. So a class needs only what its head group adds —

        C = chain carbons + `carbons`
        H = 2 x chain carbons - 2 x double bonds + `hydrogens`

    — and the fixed atoms of that head group. A hydroxyl replaces a hydrogen
    with an OH, so it moves the oxygen count and leaves C and H alone, which
    is why the sphingoid base's hydroxyls are counted apart from `atoms`:
    `d` (two), `t` (three) and `m` (one) change the oxygens and nothing else.
    """

    name: str
    #: how many chains the shorthand names — 1 for a lyso species or a
    #: sphingoid base, 2 for a diacyl or a ceramide, 3 for a triacylglycerol
    chains: int
    #: carbons the head group adds
    carbons: int = 0
    #: the hydrogen offset above
    hydrogens: int = 0
    #: everything else the head group carries, its oxygens included
    atoms: dict[str, int] = field(default_factory=dict)
    #: whether the first chain is a sphingoid base, whose hydroxyls are
    #: written as the `d`/`t`/`m` prefix and default to two
    sphingoid: bool = False


#: hydroxyls each sphingoid base prefix stands for
_BASE_HYDROXYLS = {"m": 1, "d": 2, "t": 3}
DEFAULT_BASE_HYDROXYLS = 2

#: the classes the shorthand is understood for. Every one was checked against
#: a published exact mass before it was written down.
LIPID_CLASSES: dict[str, LipidClass] = {
    c.name: c for c in [
        LipidClass("FA", 1, 0, 0, {"O": 2}),
        LipidClass("MG", 1, 3, 6, {"O": 4}),
        LipidClass("DG", 2, 3, 4, {"O": 5}),
        LipidClass("TG", 3, 3, 2, {"O": 6}),
        LipidClass("CE", 1, 27, 44, {"O": 2}),
        LipidClass("PA", 2, 3, 5, {"O": 8, "P": 1}),
        LipidClass("PC", 2, 8, 16, {"N": 1, "O": 8, "P": 1}),
        LipidClass("PE", 2, 5, 10, {"N": 1, "O": 8, "P": 1}),
        LipidClass("PG", 2, 6, 11, {"O": 10, "P": 1}),
        LipidClass("PI", 2, 9, 15, {"O": 13, "P": 1}),
        LipidClass("PS", 2, 6, 10, {"N": 1, "O": 10, "P": 1}),
        LipidClass("LPA", 1, 3, 7, {"O": 7, "P": 1}),
        LipidClass("LPC", 1, 8, 18, {"N": 1, "O": 7, "P": 1}),
        LipidClass("LPE", 1, 5, 12, {"N": 1, "O": 7, "P": 1}),
        LipidClass("LPG", 1, 6, 13, {"O": 9, "P": 1}),
        LipidClass("LPI", 1, 9, 17, {"O": 12, "P": 1}),
        LipidClass("LPS", 1, 6, 12, {"N": 1, "O": 9, "P": 1}),
        LipidClass("Cer", 2, 0, 1, {"N": 1, "O": 1}, sphingoid=True),
        LipidClass("SM", 2, 5, 13, {"N": 2, "O": 4, "P": 1}, sphingoid=True),
        LipidClass("HexCer", 2, 6, 11, {"N": 1, "O": 6}, sphingoid=True),
        LipidClass("Hex2Cer", 2, 12, 21, {"N": 1, "O": 11}, sphingoid=True),
        LipidClass("CerP", 2, 0, 2, {"N": 1, "O": 4, "P": 1}, sphingoid=True),
        LipidClass("SPB", 1, 0, 3, {"N": 1}, sphingoid=True),
        LipidClass("SPBP", 1, 0, 4, {"N": 1, "O": 3, "P": 1}, sphingoid=True),
    ]
}

#: what a name may call a class, and the double bonds that class's own base
#: carries when the number does not say. `Sphingosine C17:0` is the d17:1
#: base and `Sphinganine C17:0` the d17:0 one: the trailing `:0` counts the
#: carbons of a chain that is the base itself, and sphingosine's double bond
#: is in the word rather than in the number. The written precursor is what
#: decides whether that reading was right.
LIPID_ALIASES: dict[str, tuple[str, int | None]] = {
    "fa": ("FA", None), "fattyacid": ("FA", None),
    "mg": ("MG", None), "mag": ("MG", None),
    "dg": ("DG", None), "dag": ("DG", None),
    "tg": ("TG", None), "tag": ("TG", None),
    "ce": ("CE", None), "cholesterylester": ("CE", None),
    "pa": ("PA", None), "pc": ("PC", None), "pe": ("PE", None),
    "pg": ("PG", None), "pi": ("PI", None), "ps": ("PS", None),
    "lpa": ("LPA", None), "lpc": ("LPC", None), "lpe": ("LPE", None),
    "lpg": ("LPG", None), "lpi": ("LPI", None), "lps": ("LPS", None),
    "cer": ("Cer", None), "ceramide": ("Cer", None),
    "dhcer": ("Cer", None), "dihydroceramide": ("Cer", None),
    "sm": ("SM", None), "sphingomyelin": ("SM", None),
    "hexcer": ("HexCer", None), "glccer": ("HexCer", None),
    "galcer": ("HexCer", None),
    "glucosylceramide": ("HexCer", None),
    "galactosylceramide": ("HexCer", None),
    "glucosyl ceramide": ("HexCer", None),
    "galactosyl ceramide": ("HexCer", None),
    "galact ceramide": ("HexCer", None),
    "hex2cer": ("Hex2Cer", None), "laccer": ("Hex2Cer", None),
    "lactosylceramide": ("Hex2Cer", None),
    "lactosyl ceramide": ("Hex2Cer", None),
    "cerp": ("CerP", None), "cer1p": ("CerP", None),
    "ceramide-1-p": ("CerP", None), "ceramide 1 phosphate": ("CerP", None),
    "spb": ("SPB", None), "sph": ("SPB", 1),
    "sphingosine": ("SPB", 1), "sphinganine": ("SPB", 0),
    "dhsph": ("SPB", 0), "sphingoid base": ("SPB", None),
    "spbp": ("SPBP", None), "s1p": ("SPBP", 1),
    "sphingosine1p": ("SPBP", 1), "sphingosine-1-p": ("SPBP", 1),
    "sphingosine 1 phosphate": ("SPBP", 1),
    "sphinganine1p": ("SPBP", 0), "sphinganine-1-p": ("SPBP", 0),
    "sphinganine 1 phosphate": ("SPBP", 0),
    "dhs1p": ("SPBP", 0),
}

#: the base a two-chain sphingolipid is taken to have when the name writes
#: one chain only — `Cer1P (16:0)`, `C14_SM`. It is much the commonest base,
#: and the written precursor confirms the reading or it is thrown away.
DEFAULT_BASE = (18, 1)

#: a chain: `18:1`, `d18:1`, `h24:0`, and the `C` a method writes in front of
#: one — `C16:0-Ceramide` — which says nothing the number does not
_CHAIN = re.compile(r"(?<![A-Za-z0-9])([dtmhc]?)(\d{1,3}):(\d{1,2})(?![:\d])")
#: a chain written without its double bonds: the `C20` of `C20 Sphinganine`
_BARE_CHAIN = re.compile(r"(?<![A-Za-z0-9:])c?(\d{1,3})(?![:\d])")
#: unplaced deuterium: `-d4`, `d7`, `(d9)`. The digits may not be followed by
#: a colon, which is what keeps the `d18` of `d18:1` a sphingoid base rather
#: than eighteen labels.
_LABEL = re.compile(r"(?<![A-Za-z0-9])d(\d{1,2})(?![:\d])")
#: a double-bond position, `(15Z)`, which says nothing about the composition
_POSITION = re.compile(r"\(\d{1,2}[ez]\)")
#: a hydroxyl written out: `OH`, or `2OH` — where the 2 is the position it
#: sits at and not how many there are, so either is one oxygen
_HYDROXYL = re.compile(r"(?<![A-Za-z0-9])\d?oh(?![a-z])")
#: `;O2`, LIPID MAPS's own way of writing the oxygens
_OXYGENS = re.compile(r";o(\d?)")

#: sanity: a chain outside these is not a chain, it is something else that
#: happened to be written as a number
MIN_CHAIN_CARBONS = 2
MAX_CHAIN_CARBONS = 60
MAX_TOTAL_CARBONS = 100


def _find_class(text: str) -> tuple[LipidClass, int | None, int, int] | None:
    """
    The longest class name in the text, and where it sat.

    Longest wins, so `LacCer` is not read as `Cer`, `HexCer` not as `Cer`,
    and `Sphinganine1P` not as `Sphinganine` followed by a chain of one
    carbon. A match has to be delimited: a class name may end where a digit
    or a bracket begins, never in the middle of a longer word.
    """
    best: tuple[int, str, int | None, int, int] | None = None
    for alias, (class_name, base_double_bonds) in LIPID_ALIASES.items():
        start = text.find(alias)
        while start >= 0:
            end = start + len(alias)
            delimited = ((start == 0 or not text[start - 1].isalnum())
                         and (end == len(text) or not text[end].isalpha()))
            if delimited and (best is None or len(alias) > best[0]):
                best = (len(alias), class_name, base_double_bonds, start, end)
            start = text.find(alias, start + 1)
    if best is None:
        return None
    _length, class_name, base_double_bonds, start, end = best
    return LIPID_CLASSES[class_name], base_double_bonds, start, end


def formulas_from_name(name: str) -> list[str]:
    """
    Every formula a lipid shorthand name can be read as, best guess first.

    There is more than one only where the name is genuinely ambiguous: a
    two-chain sphingolipid written with a single chain is `SM 34:1` in LIPID
    MAPS's own shorthand, where the number is the whole species, and
    `C14_SM` in a method's, where it is the N-acyl and the base is left
    unsaid. Both readings are arithmetic; only the written precursor can say
    which was meant, so both are offered and the caller checks them.
    """
    return _readings(name)


def formula_from_name(name: str) -> str | None:
    """
    The elemental formula a lipid shorthand name implies, or None.

    Understands the forms a method actually carries: `SM(d18:1/12:0)`,
    `Cer(d18:1/16:0)`, `PC 34:1`, `LPC 18:0`, `TG 52:2`, `FA 18:1`, the class
    written after the chain (`C16:0-Ceramide`, `C14_SM`), a hydroxyl written
    as `h24:0`, `(2OH)` or `;O3`, a double-bond position in brackets that
    says nothing about the composition (`24:1(15Z)`), and unplaced deuterium
    as `-d4`, `d7` or `(d9)`.

    **Nothing here is a measurement.** It is what the name says, and a name
    is written by a person: a two-chain sphingolipid given one chain is taken
    to have the d18:1 base, `Sphingosine C17:0` to be the d17:1 base its own
    word names, and either reading can be wrong. So every caller in this
    package checks the answer against the precursor the method already
    carries, to the precision that precursor was written with, and throws the
    formula away when the two disagree — a wrong formula is a wrong lock mass
    for the recalibration, which is worse than no lock mass at all.

    Where a name has more than one reading — see `formulas_from_name` — this
    returns the first, which is the standard shorthand's. Returns None rather
    than guess when there is no class name, no chain, or a count outside what
    a lipid chain can be.
    """
    readings = _readings(name)
    return readings[0] if readings else None


@dataclass(frozen=True)
class Chain:
    """
    One chain as the shorthand wrote it: `18:1`, `d18:1`, `h24:0`.

    `prefix` is what stood in front of the number and is kept as written,
    because it is the part that carries chemistry: `d`/`t`/`m` say how many
    hydroxyls the sphingoid base has, `h` says the acyl chain carries one, and
    `c` says nothing at all — it is the `C` a method writes in front of a
    chain, which is why it is dropped when a chain is written back out.
    """

    prefix: str
    carbons: int
    double_bonds: int

    @property
    def text(self) -> str:
        prefix = "" if self.prefix == "c" else self.prefix
        return f"{prefix}{self.carbons}:{self.double_bonds}"

    @property
    def hydroxylated(self) -> bool:
        return self.prefix == "h"


@dataclass(frozen=True)
class Shorthand:
    """
    A lipid shorthand name taken apart: the class, the chains, the oxygens.

    This is the parse `formulas_from_name` runs on, kept as an object because
    two things need it rather than one. Reading a name into a formula needs
    only the totals; offering a *different* name for the same mass
    (`names_for_mass`) needs to know what the name said chain by chain, so
    that what it proposes differs from what was written by a chain and not by
    a rewrite.
    """

    lipid: LipidClass
    chains: tuple[Chain, ...]
    #: hydroxyls on the sphingoid base — the `d`/`t`/`m` prefix
    base_hydroxyls: int = 0
    #: oxygens the name added other than through a chain's `h` prefix: an
    #: `OH`, a `(2OH)` or a `;O2` on a class that is not a sphingolipid
    extra_oxygens: int = 0
    #: unplaced deuterium, `-d4`
    labels: int = 0
    #: the double bonds the class's own name implies when the number does not
    #: say — `Sphingosine C17:0`
    base_double_bonds: int | None = None
    #: the class as this name wrote it, `LacCER` rather than `Hex2Cer`, so
    #: that a name offered back reads like the one it is offered against
    written_class: str = ""

    @property
    def oxygens(self) -> int:
        """Every oxygen above the class's own, the `h` chains included."""
        return self.extra_oxygens + sum(1 for c in self.chains if c.hydroxylated)

    @property
    def writes_base(self) -> bool:
        """
        Whether the first chain is the sphingoid base, written out.

        A sphingolipid given one chain has not written it: the number is
        either the whole species or the N-acyl alone, and which of those it is
        is what `readings` offers both of.
        """
        return self.lipid.sphingoid and len(self.chains) == self.lipid.chains

    @property
    def text(self) -> str:
        """
        The name written back out, in one shape.

        The class token is the one the name used and the chains are the ones
        it named; everything else about how it was typed — the separator, the
        double-bond positions, the `C` in front of a chain — is not
        reproduced, because two names that differ only in those are the same
        compound and a proposal that differed from the written name only
        there would be noise.
        """
        token = self.written_class or self.lipid.name
        said = f"{token}({'/'.join(chain.text for chain in self.chains)})"
        if self.extra_oxygens:
            said += ";O" if self.extra_oxygens == 1 else f";O{self.extra_oxygens}"
        if self.labels:
            said += f"-d{self.labels}"
        return said

    def readings(self) -> list[tuple[int, int]]:
        """
        (total carbons, total double bonds) per reading, the standard
        shorthand's first — see `formulas_from_name` for why there is ever
        more than one.
        """
        return self.readings_of(sum(chain.carbons for chain in self.chains),
                                sum(chain.double_bonds for chain in self.chains))

    def readings_of(self, carbons: int, double_bonds: int) -> list[tuple[int, int]]:
        """
        The same rule applied to totals that are not this name's own.

        `names_for_mass` needs it: it asks whether a set of totals could weigh
        what the method says *before* it works out how to split them over the
        chains, and the answer has to be the reading rule this name is read
        with rather than a second copy of it.
        """
        if (len(self.chains) == 1 and self.base_double_bonds is not None
                and not double_bonds):
            double_bonds = self.base_double_bonds

        readings = [(carbons, double_bonds)]
        if self.lipid.sphingoid and len(self.chains) < self.lipid.chains:
            # the base was not written. It may have been left out because the
            # number is the whole species (`SM 34:1`) or because the method
            # names the N-acyl alone (`C14_SM`); both are offered.
            readings.append((carbons + DEFAULT_BASE[0],
                             double_bonds + DEFAULT_BASE[1]))
            if carbons < DEFAULT_BASE[0] + MIN_CHAIN_CARBONS:
                readings.pop(0)     # too few carbons to be a whole sphingolipid
        return readings

    def compositions(self) -> list[dict[str, int]]:
        """Element counts per reading."""
        out = []
        for carbons, double_bonds in self.readings():
            counts = composition(self.lipid, carbons, double_bonds,
                                 self.base_hydroxyls, self.oxygens, self.labels)
            if counts is not None:
                out.append(counts)
        return out

    def formulas(self) -> list[str]:
        return [format_formula(counts) for counts in self.compositions()]


def composition(lipid: LipidClass, carbons: int, double_bonds: int,
                base_hydroxyls: int, extra_oxygens: int,
                labels: int = 0) -> dict[str, int] | None:
    """
    Element counts for one class carrying these totals, or None for a total
    outside what a lipid is — see `LipidClass` for the arithmetic.
    """
    if not MIN_CHAIN_CARBONS <= carbons <= MAX_TOTAL_CARBONS:
        return None
    counts = {"C": carbons + lipid.carbons,
              "H": 2 * carbons - 2 * double_bonds + lipid.hydrogens}
    for element, n in lipid.atoms.items():
        counts[element] = counts.get(element, 0) + n
    counts["O"] = counts.get("O", 0) + base_hydroxyls + extra_oxygens
    if counts["H"] < labels:
        return None
    if labels:
        counts["H"] -= labels
        counts["D"] = labels
    return {element: n for element, n in counts.items() if n}


def _as_written(name: str, alias: str) -> str:
    """The class token as the original name spelled it, `LacCER` not `laccer`."""
    pattern = "".join("[ _]" if char == " " else re.escape(char)
                      for char in alias)
    match = re.search(pattern, name, re.IGNORECASE)
    return match.group(0) if match else ""


def parse_shorthand(name: str) -> Shorthand | None:
    """
    Take a lipid shorthand name apart, or None when it is not one.

    None for the same reasons `formula_from_name` returns None: no class
    name, no chain, more chains than the class takes, or a chain outside what
    a chain can be.
    """
    original = " ".join(str(name or "").split())
    text = original.lower().replace("_", " ")
    if not text:
        return None

    labels = sum(int(n) for n in _LABEL.findall(text))
    text = _LABEL.sub(" ", text)
    text = _POSITION.sub(" ", text)

    extra_oxygens = len(_HYDROXYL.findall(text))
    text = _HYDROXYL.sub(" ", text)
    written_oxygens: int | None = None
    for count in _OXYGENS.findall(text):
        written_oxygens = int(count) if count else 1
    text = _OXYGENS.sub(" ", text)

    found = _find_class(text)
    if found is None:
        return None
    lipid, base_double_bonds, start, end = found
    alias, rest = text[start:end], text[:start] + " " + text[end:]

    chains = [Chain(prefix, int(carbons), int(double_bonds))
              for prefix, carbons, double_bonds in _CHAIN.findall(rest)]
    if not chains:
        chains = [Chain("", int(carbons), 0)
                  for carbons in _BARE_CHAIN.findall(rest)]
    if not chains or len(chains) > lipid.chains:
        return None
    if any(not MIN_CHAIN_CARBONS <= chain.carbons <= MAX_CHAIN_CARBONS
           for chain in chains):
        return None

    base_hydroxyls = DEFAULT_BASE_HYDROXYLS if lipid.sphingoid else 0
    for chain in chains:
        if chain.prefix in _BASE_HYDROXYLS:
            base_hydroxyls = _BASE_HYDROXYLS[chain.prefix]
            break
    if written_oxygens is not None:
        if lipid.sphingoid:
            base_hydroxyls = written_oxygens
        else:
            extra_oxygens += written_oxygens

    return Shorthand(lipid=lipid, chains=tuple(chains),
                     base_hydroxyls=base_hydroxyls, extra_oxygens=extra_oxygens,
                     labels=labels, base_double_bonds=base_double_bonds,
                     written_class=_as_written(original, alias))


def _readings(name: str) -> list[str]:
    parsed = parse_shorthand(name)
    return parsed.formulas() if parsed is not None else []


# --------------------------------------------------------------------------- #
# adducts
# --------------------------------------------------------------------------- #
#: an adduct whose charge is a proton the pieces keep or lose between them
PROTON = "proton"
#: an adduct held by hydrogen bonds, which leaves as a neutral and hands the
#: fragmenting ion a proton — see the rule in the module docstring
LABILE = "labile"
#: an adduct that is a coordinated metal, which stays on one piece
METAL = "metal"


@dataclass(frozen=True)
class Adduct:
    """
    An ionisation form: m/z = (M + delta) / |charge|, and what happens to
    the charge when the ion fragments.

    `behaviour` is one of `PROTON`, `LABILE` or `METAL`; `leaves` is the
    neutral a labile adduct departs as; `carrier` is the element a metal
    adduct leaves on the fragment. The fields are what `fragment_adducts`
    reads, and the chemistry behind them is in the module docstring.
    """

    name: str
    charge: int
    delta: float
    #: what the adduct adds, as a formula, for a name that has to be built
    added: str = ""
    behaviour: str = PROTON
    leaves: str = ""
    carrier: str = ""

    def mz(self, neutral_mass: float) -> float:
        return (neutral_mass + self.delta) / abs(self.charge)

    def neutral_mass(self, mz: float) -> float:
        return mz * abs(self.charge) - self.delta

    @property
    def polarity(self) -> int:
        return 1 if self.charge > 0 else -1


#: not an ion: the entry that lets a neutral mass be searched as if it were one
NEUTRAL = "M (neutral)"

ADDUCTS: list[Adduct] = [
    Adduct("[M-H]-", -1, -PROTON_MASS),
    Adduct("[M+Cl]-", -1, 34.96885268 + ELECTRON_MASS, added="Cl",
           behaviour=LABILE, leaves="HCl"),
    Adduct("[M+HCOO]-", -1, 44.99765396, added="CHO2",
           behaviour=LABILE, leaves="HCOOH"),
    Adduct("[M+CH3COO]-", -1, 59.01330402, added="C2H3O2",
           behaviour=LABILE, leaves="CH3COOH"),
    Adduct("[M-2H]2-", -2, -2 * PROTON_MASS),
    Adduct("[M+H]+", 1, PROTON_MASS, added="H"),
    Adduct("[M+NH4]+", 1, 18.03382555, added="NH4",
           behaviour=LABILE, leaves="NH3"),
    Adduct("[M+Na]+", 1, 22.98922421, added="Na",
           behaviour=METAL, carrier="Na"),
    Adduct("[M+K]+", 1, 38.96315810, added="K",
           behaviour=METAL, carrier="K"),
    Adduct("[M+2H]2+", 2, 2 * PROTON_MASS, added="H2"),
    Adduct(NEUTRAL, 1, 0.0),
]

ADDUCTS_BY_NAME = {a.name: a for a in ADDUCTS}

#: what other exporters call the adducts above. A library record spells its
#: adduct the way its author's software does, and the spellings differ more
#: than the ions do: MassBank writes `[M+FA-H]-` where MS-DIAL writes
#: `[M+HCOO]-`, and both mean formate. Keyed on what `_normalise_adduct`
#: produces, so brackets, spaces, case and a `1` before the sign are gone.
_ADDUCT_ALIASES = {
    "M+FA-H": "[M+HCOO]-",
    "M+HCOOH-H": "[M+HCOO]-",
    "M+FORMATE": "[M+HCOO]-",
    "M+OAC": "[M+CH3COO]-",
    "M+AC": "[M+CH3COO]-",
    "M+ACETATE": "[M+CH3COO]-",
    "M+CH3COOH-H": "[M+CH3COO]-",
    "M+NH3+H": "[M+NH4]+",
}

_CHARGE_SUFFIX = re.compile(r"(\d*)\s*([+-])\s*$")
_DECORATION = re.compile(r"[\s\[\]]")


def _normalise_adduct(text: str) -> str:
    """
    An adduct name with the decoration taken off: no brackets, no spaces,
    no charge suffix, upper case. `[M+H]+`, `[M+H]1+` and ` m+h ` all come
    out as `M+H`, which is what the table and the aliases are keyed on.
    """
    body = _DECORATION.sub("", str(text)).upper()
    return _CHARGE_SUFFIX.sub("", body)


def polarity_sign(text) -> int | None:
    """
    The sign an adduct name or an ion-mode word declares: +1, -1 or None.

    Read from the written name rather than from the table, so an adduct
    nobody here models — `[M+2Na-H]+`, `[M+HCOOH-H]-` — still says which
    polarity it belongs to, which is all a polarity filter needs. An ion
    mode written as a word (`Positive`, `NEGATIVE`, `N`) is read too, since
    MGF and several MSP exporters write that where an adduct would go, and
    a channel's polarity arrives as one of those words as well.
    """
    if text is None or isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return 1 if text > 0 else (-1 if text < 0 else None)
    written = str(text).strip()
    if not written:
        return None
    match = _CHARGE_SUFFIX.search(written)
    if match:
        return 1 if match.group(2) == "+" else -1
    word = written.lower()
    if word.startswith("pos") or word == "p":
        return 1
    if word.startswith("neg") or word == "n":
        return -1
    return None


def adduct_from_name(text) -> "Adduct | None":
    """
    The `Adduct` a written name means, or None when it is not one of these.

    Case, spaces, brackets and a `1` before the charge are ignored and the
    aliases above are followed. The neutral entry is not an adduct and is
    never returned; neither is a name whose sign contradicts the table's,
    since `[M+H]-` is not `[M+H]+` with a typo, it is unreadable.
    """
    if not text:
        return None
    key = _normalise_adduct(text)
    if not key:
        return None
    name = _ADDUCT_ALIASES.get(key)
    if name is None:
        for adduct in ADDUCTS:
            if adduct.name != NEUTRAL and _normalise_adduct(adduct.name) == key:
                name = adduct.name
                break
    if name is None:
        return None
    found = ADDUCTS_BY_NAME[name]
    sign = polarity_sign(text)
    if sign is not None and (sign > 0) != (found.charge > 0):
        return None
    return found


def mass_from_formula(formula: str, precursor_type: str) -> float | None:
    """
    The m/z a formula and an adduct give, or None when either is unreadable.

    This is the arithmetic a library record already carries the ingredients
    for but did not do: `library.LibraryEntry.exact_precursor` is this
    applied to the `Formula` and `Precursor_type` fields it was written
    with.
    """
    adduct = adduct_from_name(precursor_type)
    if adduct is None or not formula:
        return None
    try:
        counts = parse_formula(formula)
    except (FormulaError, ValueError):
        return None
    if not counts:
        return None
    return adduct.mz(monoisotopic_mass(counts))


def mass_error_ppm(measured: float, theoretical: float) -> float:
    """Relative mass error in parts per million."""
    if theoretical == 0:
        return 0.0
    return (measured - theoretical) / theoretical * 1e6


def mass_error_mda(measured: float, theoretical: float) -> float:
    """Absolute mass error in millidaltons."""
    return (measured - theoretical) * 1000.0


# --------------------------------------------------------------------------- #
# what the fragments of an adduct carry
# --------------------------------------------------------------------------- #
def core_adduct(adduct: Adduct) -> Adduct:
    """
    The singly-charged form the pieces of this ion actually carry.

    A labile adduct has left by the time anything breaks, so the ion that
    fragments is the protonated or deprotonated molecule; a doubly charged
    precursor gives singly charged fragments. A metal adduct is its own
    core — and its other possibility is the proton form, which is why
    `fragment_adducts` and not this is what a predictor should ask.
    """
    if adduct.behaviour == METAL:
        return adduct
    return ADDUCTS_BY_NAME["[M+H]+" if adduct.charge > 0 else "[M-H]-"]


def fragment_adducts(adduct: Adduct) -> tuple[Adduct, ...]:
    """
    Every charge form the fragments of this ion may carry, likeliest first.

    One form for a proton or a labile adduct; two for a metal, because
    whether the sodium stays with the piece or the piece keeps a proton
    instead depends on where the coordinating oxygens ended up, and the
    arithmetic cannot know. Offering both and saying which was assumed is
    the honest version of a rule nobody can derive.
    """
    proton = ADDUCTS_BY_NAME["[M+H]+" if adduct.charge > 0 else "[M-H]-"]
    if adduct.behaviour == METAL:
        return (adduct, proton)
    return (proton,)


def adducts_of_polarity(polarity=None) -> list[Adduct]:
    """
    Every adduct a channel of this polarity could have produced.

    The neutral entry is never one: it exists so a neutral mass can be
    searched as if it were an ion. `polarity` is the sign the channel was
    acquired at, as a number or as the word a file writes (`Positive`);
    without one every adduct is offered, which is what a spectrum arriving
    with no acquisition behind it deserves.
    """
    sign = polarity_sign(polarity) if polarity is not None else None
    return [a for a in ADDUCTS if a.name != NEUTRAL
            and (sign is None or a.polarity == sign)]


def behaviour_text(adduct: Adduct) -> str:
    """
    What this adduct does when the ion breaks up, in one sentence.

    A list of candidates at several adducts is not readable unless each row
    says what its adduct implies about the fragments: an ammoniated
    triacylglycerol shows a diacylglycerol ion carrying a proton and nothing
    at all 17 Da above it, and a row that only says `[M+NH4]+` has left the
    reader to know that.
    """
    if adduct.behaviour == LABILE:
        return (f"labile: it leaves as {adduct.leaves} and hands over a "
                f"proton, so the fragments carry "
                f"{core_adduct(adduct).name}")
    if adduct.behaviour == METAL:
        return (f"metal: the {adduct.carrier} stays on whichever piece "
                f"coordinates it, so both [piece+{adduct.carrier}]"
                f"{'+' if adduct.charge > 0 else '-'} and the protonated "
                f"piece are offered, each saying which was assumed")
    return "proton: the charge stays on whichever piece keeps it"


# --------------------------------------------------------------------------- #
# which adduct a written precursor is
# --------------------------------------------------------------------------- #
#: how far a written method precursor may sit from an adduct's exact mass and
#: still be that adduct. Measured on nine bile-acid infusions: the worst gap
#: is 0.0117 Da — DCA-d4, written `414.34` for an [M+NH4]+ of 414.3517, the
#: instrument method carrying two decimals and not always rounding them the
#: same way (`430.35` in one file and `430.34` in another for the same
#: 430.3465). 0.05 covers that with room to spare and is still a fiftieth of
#: the smallest gap between two adducts of one molecule that could be
#: confused for each other — ammonium and sodium, 4.955 Da apart.
ADDUCT_MATCH_DA = 0.05


@dataclass(frozen=True)
class AdductMatch:
    """One adduct measured against a written precursor."""

    adduct: Adduct
    mz: float
    error_da: float
    error_ppm: float
    within: bool

    @property
    def name(self) -> str:
        return self.adduct.name


def adducts_matching(formula: str, precursor: float, polarity=None,
                     tolerance: float | None = None) -> list[AdductMatch]:
    """
    Every adduct of `formula`, ranked by how near it sits to `precursor`.

    The list is complete — a miss is as informative as a hit, since a
    precursor that is none of them means the formula is wrong — and each
    entry says whether it is `within` the tolerance. `polarity` is the sign
    the channel was acquired at (+1/-1, or a word the file writes such as
    `Positive`); adducts of the other sign are left out, because a positive
    channel cannot have produced `[M-H]-` and offering it would be inviting
    a mistake, not a choice. The neutral entry is never an answer.

    The tolerance defaults to `ADDUCT_MATCH_DA`, widened to the precision
    the precursor was actually written with when that is coarser: `647.5`
    is known to ±0.05 and nothing closer can be asked of it.
    """
    from .lipidmaps import mass_precision

    try:
        counts = parse_formula(formula)
    except (FormulaError, ValueError):
        return []
    if not counts:
        return []
    mass = monoisotopic_mass(counts)
    sign = polarity_sign(polarity) if polarity is not None else None
    if tolerance is None:
        tolerance = max(ADDUCT_MATCH_DA, mass_precision(float(precursor)))
    out = []
    for adduct in ADDUCTS:
        if adduct.name == NEUTRAL:
            continue
        if sign is not None and adduct.polarity != sign:
            continue
        mz = adduct.mz(mass)
        error = float(precursor) - mz
        out.append(AdductMatch(adduct=adduct, mz=mz, error_da=error,
                               error_ppm=mass_error_ppm(float(precursor), mz),
                               within=abs(error) <= tolerance))
    out.sort(key=lambda m: abs(m.error_da))
    return out


@dataclass(frozen=True)
class AdductChoice:
    """The adduct a written precursor is, and the sentence that says so."""

    adduct: Adduct | None
    reason: str
    matches: tuple[AdductMatch, ...] = ()
    #: what the survey scan said about each candidate, where one was handed
    #: in: `adduct_evidence`, best supported first. Empty when no survey was
    #: read, which is not the same as a survey that showed nothing.
    evidence: tuple["AdductEvidence", ...] = ()
    #: the survey found this ion at the right mass and its isotopes agreed
    confirmed: bool = False

    def __bool__(self) -> bool:
        return self.adduct is not None

    @property
    def read_survey(self) -> bool:
        """Was a survey scan asked at all?"""
        return bool(self.evidence)


def _isolation_da() -> float:
    """How wide a window the quadrupole passed, in daltons."""
    from .matching import PRECURSOR_MATCH_DA

    return float(PRECURSOR_MATCH_DA)


def _survey_rescue(evidence, precursor: float):
    """
    The adduct the survey names when the written precursor names none.

    A method written `538.6` for a ceramide whose `[M+H]+` weighs 538.5194
    is 0.08 Da out, which is eighty times what an adduct is allowed and
    still the ion the quadrupole isolated — `matching.PRECURSOR_MATCH_DA`
    is the 0.7 Da window that says so. Without a survey there is nothing to
    prefer that reading to a typing mistake and the honest answer is to
    refuse; with one, the instrument has already said which ion was there,
    at its own accuracy and with its isotopes. So the survey is allowed to
    answer a question the written number could not, and only inside the
    window the quadrupole actually passed.
    """
    supported = sorted((e for e in evidence if e.present and e.agrees),
                       key=lambda e: -e.score)
    for found in supported:
        error = precursor - found.mz
        if abs(error) <= _isolation_da():
            return found, AdductMatch(adduct=found.adduct, mz=found.mz,
                                      error_da=error,
                                      error_ppm=mass_error_ppm(precursor,
                                                               found.mz),
                                      within=False)
    return None


def identify_adduct(formula: str, precursor: float, polarity=None,
                    tolerance: float | None = None,
                    survey: tuple | None = None) -> AdductChoice:
    """
    Which adduct a method's written precursor is, for this formula, in words.

    The sentence is the point. A user who types a formula and gets back a
    spectrum explaining nothing has been told the arithmetic failed but not
    where, and the answer is nearly always that the channel is an ammonium
    adduct and the drawing was scored as a protonated one. So this says
    which it is, how far off the written number sits, and what the obvious
    alternative would have been — and where nothing fits, it names the
    closest and returns no adduct, so that nothing is explained rather than
    the wrong ion being explained well.

    `survey` is `(mz, intensity)` from the full-scan channel of the same
    acquisition, averaged over the same range as the product spectrum, and
    with it the answer stops being arithmetic on a hand-typed number. The
    written precursor still says which adducts are candidates — the
    quadrupole isolated that mass and not another — and the survey then says
    which of them the instrument actually saw, by the exact mass and by the
    isotope pattern. Where it saw none the written mass still decides and
    the sentence says the survey did not confirm it, because an adduct
    chosen from two decimals is a different claim from one measured.
    """
    from .lipidmaps import mass_precision

    matches = adducts_matching(formula, precursor, polarity, tolerance)
    if not matches:
        return AdductChoice(None, f"{formula!r} is not a formula this can read")
    evidence: tuple[AdductEvidence, ...] = ()
    if survey is not None:
        evidence = tuple(adduct_evidence(
            survey[0], survey[1], formula,
            candidates=[m.adduct for m in matches]))
    written = f"{float(precursor):g}"
    inside = [m for m in matches if m.within]
    if not inside:
        window = (tolerance if tolerance is not None
                  else max(ADDUCT_MATCH_DA, mass_precision(float(precursor))))
        rescued = _survey_rescue(evidence, float(precursor))
        if rescued is not None:
            found, match = rescued
            return AdductChoice(
                match.adduct,
                f"{written} is none of the adducts of "
                f"{format_formula(parse_formula(formula))} within "
                f"±{window:g} Da, but the survey shows {found.name} at "
                f"{found.confirmation} — {abs(match.error_da):.4f} Da from "
                f"the written mass, inside the ±{_isolation_da():g} Da the "
                f"quadrupole passes, so it is read as {found.name}",
                tuple(matches), evidence, True)
        closest = ", ".join(
            f"{m.name} at {m.mz:.4f} ({m.error_da:+.4f} Da)"
            for m in matches[:2])
        seen = adduct_map(list(evidence))
        return AdductChoice(
            None,
            f"{written} is none of the adducts of {format_formula(parse_formula(formula))}"
            f" within ±{window:g} Da — closest {closest}"
            + (f"; the survey shows {seen}" if seen else ""),
            tuple(matches), evidence)
    best = inside[0]
    survey_note = ""
    confirmed = False
    if survey is not None:
        named = {m.name for m in inside}
        supported = sorted((e for e in evidence
                            if e.present and e.name in named),
                           key=lambda e: -e.score)
        if supported:
            found = supported[0]
            best = next(m for m in inside if m.name == found.name)
            # present at the right mass is not the same as confirmed: an ion
            # whose satellites are not its own is something else sitting on
            # the mass, and the sentence has to be able to say so while still
            # reporting what was found
            confirmed = found.pattern is None or found.agrees
            lead = ("confirmed by the survey" if confirmed
                    else "seen in the survey but not confirmed")
            survey_note = f"; {lead}: {found.confirmation}"
            seen = adduct_map([e for e in evidence if e.name != found.name])
            if seen:
                survey_note += f", and the survey also shows {seen}"
        else:
            why = next((e.note for e in evidence if e.name == best.name), "")
            survey_note = ("; the survey does not show it"
                           + (f" ({why})" if why else "")
                           + ", so it is chosen from the written mass alone")
    # the alternative worth printing is the form the *fragments* carry, not
    # the next nearest number: a user who expected a protonated molecule and
    # got an ammoniated one needs to see 413.3199 beside 430.3465, and being
    # shown the sodium adduct instead answers a question nobody asked
    core = core_adduct(best.adduct)
    others = [m for m in matches if m.adduct.name == core.name
              and m.adduct.name != best.name]
    if not others:
        others = [m for m in matches if m is not best][:1]
    tail = ("; " + ", ".join(f"{m.name} would be {m.mz:.4f}" for m in others)
            if others else "")
    return AdductChoice(
        best.adduct,
        f"{written} is {best.name} of "
        f"{format_formula(parse_formula(formula))} "
        f"({best.mz:.4f}, {best.error_ppm:+.1f} ppm){tail}{survey_note}",
        tuple(matches), evidence, confirmed)


# --------------------------------------------------------------------------- #
# what the survey scan says about the adduct
# --------------------------------------------------------------------------- #
#: how many isotope peaks of an ion the survey is asked about: M, M+1, M+2.
#: The first is the mass, the second is about 1.1% per carbon and is what
#: tells an ion from its neighbour's satellite, and the third is where sulfur
#: and chlorine announce themselves. Past that a lipid's peaks are a few per
#: cent of the monoisotopic and a survey averaged over one chromatographic
#: peak carries noise of that size.
SURVEY_ISOTOPES = 3

#: how far apart in m/z two points may be and still be read as the same peak
#: when a height is being looked up. A TOF peak at 650 is about 0.03 Da wide
#: at half height, so 0.02 either side of a theoretical mass lands on it
#: without reaching the next nominal mass.
SURVEY_PEAK_DA = 0.02

#: how far the *nearest* centroid may sit from an adduct's exact mass and
#: still be offered as that ion at all. Wider than the tolerance a match is
#: judged on, because a miss with a number on it — "the nearest peak is 84
#: ppm away" — says more than "nothing found".
SURVEY_WINDOW_DA = 0.05

#: the satellite agreement at or above which the isotopes are called
#: agreeing. Measured on the sphingolipid batch's survey, averaged over each
#: compound's own peak in injection 01 — see `adduct_evidence` for the two
#: tables. The ions that are really there score 0.87, 0.77 and 0.76; the one
#: whose M+1 window holds a neighbour scores 0.55; and the two that are not
#: the ion — a potassium adduct read off a 223-count spike, an ammonium
#: 21 ppm out whose satellites are flat noise — score 0.13 and 0.33. 0.50 is
#: the trough. It decides nothing on its own: `adduct_evidence` ranks by
#: `score`, and this only chooses the wording.
PATTERN_AGREES = 0.50


def survey_tolerance_ppm() -> float:
    """
    How near a survey centroid has to sit to be the adduct's ion.

    `precursor.CONSENSUS_SPREAD_PPM` is the figure the rest of the program
    already holds two measurements to before calling them the same ion, and a
    second number for the same question would be one too many. Fetched
    through a function so that this module keeps its habit of importing
    nothing from the rest of the package at the top.
    """
    from .precursor import CONSENSUS_SPREAD_PPM

    return float(CONSENSUS_SPREAD_PPM)


def pattern_agreement(measured, expected) -> float | None:
    """
    How well a measured isotope pattern agrees with a theoretical one, 0 to 1.

    Both are the satellites as shares of the monoisotopic peak, which is 1.0
    in each by construction and therefore says nothing; the score is built
    from M+1 onwards. Each satellite is scored against the larger of the two
    numbers — so a satellite twice as big as it should be and one half the
    size it should be both cost the same — and the satellites are averaged
    weighted by how much of the theoretical pattern each is, which puts about
    five sixths of the weight on M+1 for a lipid.

    This is not `match_isotope_pattern`, which sums the absolute differences
    over all the satellites. That is the right rule for ranking candidate
    formulas against one spectrum, where every candidate is measured the same
    way and the largest satellite should dominate. It is the wrong rule here,
    because a single contaminated satellite is fatal under it: the C16
    ceramide's own `[M+H]+` in the sphingolipid survey scores 0.43 there,
    since its M+2 window holds the co-eluting dihydroceramide — C34H69NO3 at
    540.5350, 17 ppm from the ceramide's own M+2 at 540.5259 and inside the
    same 0.02 Da — and a rule that calls a compound's true adduct a
    disagreement because its saturated analogue co-elutes will do that on
    every lipid batch there is. Weighted per satellite it scores 0.77.

    None where there is nothing to compare.
    """
    if len(measured) < 2 or len(expected) < 2:
        return None
    total = 0.0
    score = 0.0
    for mine, theirs in zip(measured[1:], expected[1:]):
        weight = float(theirs)
        if weight <= 0:
            continue
        largest = max(float(mine), weight)
        agreement = 1.0 - abs(float(mine) - weight) / largest if largest else 0.0
        score += weight * max(0.0, agreement)
        total += weight
    if total <= 0:
        return None
    return score / total


def ion_composition(counts: dict[str, int],
                    adduct: Adduct) -> dict[str, int] | None:
    """
    The atoms the ion carries: the molecule's, plus what the adduct brings.

    This is what an isotope pattern has to be computed from, and it is not
    the same thing as shifting the neutral's pattern by the adduct's mass.
    `[M+Na]+` and `[M+NH4]+` are 4.955 Da apart and need no pattern to be
    told apart, but the ammonium's nitrogen adds 0.37% to the M+1 and its
    four hydrogens another 0.06%, and `[M+Cl]-` adds a 32% M+2 that the
    molecule does not have. An adduct treated as an offset says those ions
    have their molecule's pattern, which for chloride is wrong by a factor
    of ten.

    Returns None when the adduct's composition is not written down, or when
    it would take away hydrogens the molecule has not got.
    """
    out = dict(counts)
    if adduct.added:
        try:
            for element, n in parse_formula(adduct.added).items():
                out[element] = out.get(element, 0) + n
        except (FormulaError, ValueError):
            return None
    elif adduct.charge < 0:
        # a deprotonated molecule: the only adducts with no `added` are the
        # ones that take protons off, one per unit of negative charge
        lost = abs(adduct.charge)
        if out.get("H", 0) < lost:
            return None
        out["H"] -= lost
    return {element: n for element, n in out.items() if n}


def ion_pattern(formula: str, adduct: Adduct,
                max_peaks: int = SURVEY_ISOTOPES,
                min_abundance: float = 0.0005) -> list[tuple[float, float]]:
    """
    The ion's theoretical isotope pattern as (m/z, abundance), M scaled to 1.

    The adduct's own atoms are in the composition (`ion_composition`) and its
    electrons are in the mass, so a doubly charged ion comes back with its
    satellites half a dalton apart, which is what a spectrum shows.
    """
    try:
        counts = parse_formula(formula)
    except (FormulaError, ValueError):
        return []
    ion = ion_composition(counts, adduct) if counts else None
    if not ion:
        return []
    charge = abs(adduct.charge) or 1
    pattern = isotope_pattern(ion, min_abundance=min_abundance,
                              max_peaks=max_peaks)
    if not pattern:
        return []
    base = pattern[0][1] or 1.0
    return [((mass - adduct.charge * ELECTRON_MASS) / charge, abundance / base)
            for mass, abundance in pattern]


@dataclass
class AdductEvidence:
    """
    One candidate adduct held against a survey scan: the mass and the pattern.

    Two independent questions, kept apart on purpose. `error_ppm` says
    whether anything of the right mass is there at all; `pattern` says
    whether what is there is a monoisotopic ion or somebody else's satellite,
    which is the only question a mass cannot answer.
    """

    adduct: Adduct
    #: what the formula says this ion weighs
    mz: float
    #: the nearest centroid in the survey, and its height
    found_mz: float | None = None
    height: float = 0.0
    error_ppm: float | None = None
    #: M, M+1, M+2 measured, as shares of M
    measured: tuple[float, ...] = ()
    #: the same from the ion's own composition
    expected: tuple[float, ...] = ()
    #: agreement over the satellites alone, 0 to 1, or None where the survey
    #: holds no satellites to compare — a product-ion scan, or an ion too
    #: weak to carry one
    pattern: float | None = None
    #: this ion's height as a share of the strongest adduct the survey shows
    #: for this molecule: the adduct map of the standard
    relative: float = 0.0
    present: bool = False
    tolerance_ppm: float = 0.0
    note: str = ""

    @property
    def name(self) -> str:
        return self.adduct.name

    @property
    def agrees(self) -> bool:
        """Does the isotope pattern support this being the ion it claims?"""
        return self.pattern is not None and self.pattern >= PATTERN_AGREES

    @property
    def score(self) -> float:
        """
        How well the survey supports this adduct, 0 to 1.

        Half the mass and half the pattern where there is a pattern to read,
        and the mass alone where there is not — said rather than assumed,
        since scoring a missing pattern as zero would call every product-ion
        scan a disagreement.
        """
        if not self.present or self.error_ppm is None:
            return 0.0
        tolerance = self.tolerance_ppm or survey_tolerance_ppm()
        mass = max(0.0, 1.0 - abs(self.error_ppm) / tolerance)
        if self.pattern is None:
            return mass
        return 0.5 * mass + 0.5 * float(self.pattern)

    @property
    def isotope_note(self) -> str:
        """The M+1 measured against the M+1 expected, in words."""
        if self.pattern is None or len(self.measured) < 2 \
                or len(self.expected) < 2:
            return "no isotope satellites to compare"
        said = (f"M+1 {self.measured[1]:.2f} measured vs "
                f"{self.expected[1]:.2f} expected")
        return said + ("" if self.agrees else " — the isotopes disagree")

    @property
    def confirmation(self) -> str:
        """What the survey found, for a basis line: mass, ppm, isotopes."""
        if not self.present:
            return self.note or "not found"
        said = f"{self.found_mz:.4f}, {self.error_ppm:+.1f} ppm"
        if self.pattern is None:
            return f"{said}, no isotopes to compare"
        return f"{said}, isotopes {'agree' if self.agrees else 'do not agree'}"

    @property
    def sentence(self) -> str:
        """This candidate in one clause, whether or not it was found."""
        if self.present:
            return (f"{self.name} at {self.found_mz:.4f}, "
                    f"{self.error_ppm:+.1f} ppm, {self.isotope_note}")
        return f"{self.name} at {self.mz:.4f}: {self.note or 'not found'}"


def adduct_evidence(mz, intensity, formula: str, candidates=None,
                    tolerance_ppm: float | None = None, polarity=None,
                    min_intensity: float | None = None
                    ) -> list[AdductEvidence]:
    """
    What a survey scan says about each adduct a formula could have produced.

    `mz` and `intensity` are a spectrum already read — the survey averaged
    over the peak, or over the whole run for an infusion. `candidates` are
    the adducts to weigh: `Adduct`s, `AdductMatch`es as `adducts_matching`
    returns them, names, or None for every adduct of `polarity`.

    Each candidate comes back with the exact mass found (the nearest centroid
    within `SURVEY_WINDOW_DA`, its ppm and its height) and the agreement
    between the ion's own theoretical M / M+1 / M+2 and the measured ones.
    The list is sorted by how well the survey supports the candidate, and
    every candidate is in it: an adduct the survey does not show is a
    measurement too, and the sentence says what was looked for and what was
    there instead.

    Where several adducts of the same molecule are present — `[M+H]+`,
    `[M+NH4]+` and `[M+Na]+` together, which is the ordinary case in positive
    infusion — every one is reported with `relative`, its height as a share
    of the strongest. That is the adduct map of the standard, and it is worth
    more than the single answer: a compound whose sodium adduct is four times
    its protonated one will be quantified on the wrong channel by anyone who
    assumed otherwise.

    Measured on injection 01 of the 26-injection sphingolipid batch
    (TripleTOF 5600, positive, a TOF MS 50–700 survey averaged over the two
    scans across each compound's peak):

    | | exact | found | Δ ppm | height | of the strongest | M+1 meas/exp | pattern |
    |---|---|---|---|---|---|---|---|
    | SM(d18:1/12:0), C35H71N2O6P, written 647.5, at 5.60 min ||||||||
    | `[M+H]+` | 647.5123 | 647.5112 | −1.6 | 51,341 | 100% | 0.37 / 0.40 | 0.87 |
    | `[M+Na]+` | 669.4942 | 669.4956 | +2.1 | 6,443 | 12.5% | 0.53 / 0.40 | 0.76 |
    | `[M+K]+` | 685.4681 | 685.4571 | −16.1 | 223 | 0.4% | 2.76 / 0.40 | 0.13 |
    | `[M+NH4]+` | 664.5388 | — | nearest 69 away | — | — | — | — |
    | Cer(d18:1/16:0), C34H67NO3, written 538.6, at 4.89 min ||||||||
    | `[M+H]+` | 538.5194 | 538.5197 | +0.6 | 7,690 | 100% | 0.33 / 0.38 | 0.77 |
    | `[M+Na]+` | 560.5013 | 560.5071 | +10.4 | 1,025 | 13.3% | 0.67 / 0.38 | 0.55 |
    | `[M+NH4]+` | 555.5459 | 555.5340 | −21.5 | 170 | 2.2% | 1.00 / 0.38 | 0.33 |
    | `[M+K]+` | 576.4753 | — | nearest 60 away | — | — | — | — |

    Two rows there are the argument for asking the pattern at all. The
    ceramide's `[M+NH4]+` is 21.5 ppm out — inside the 25 that says "the same
    ion" — and 170 counts, over the 100 that says "measurable"; its M+1 and
    M+2 come back at 1.00 and 1.00 of its M, which is flat noise and not an
    isotope pattern, and it ranks last. And the sphingomyelin's `[M+K]+` is a
    223-count spike whose neighbour is nearly three times it.

    The nine bile-acid infusions have no survey channel at all, so nothing is
    asked and nothing is claimed: `identify_adduct` says so rather than
    letting a deduction from the written precursor pass for a measurement.
    """
    from .precursor import MIN_INTENSITY, in_spectrum

    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    tolerance = float(tolerance_ppm if tolerance_ppm is not None
                      else survey_tolerance_ppm())
    floor = float(min_intensity if min_intensity is not None else MIN_INTENSITY)

    adducts = _as_adducts(candidates, polarity)
    try:
        counts = parse_formula(formula)
    except (FormulaError, ValueError):
        counts = {}
    if not counts or not adducts:
        return []
    mass = monoisotopic_mass(counts)

    out: list[AdductEvidence] = []
    for adduct in adducts:
        item = AdductEvidence(adduct=adduct, mz=adduct.mz(mass),
                              tolerance_ppm=tolerance)
        pattern = ion_pattern(formula, adduct)
        if pattern:
            item.mz = pattern[0][0]
            item.expected = tuple(round(a, 6) for _m, a in pattern)
        if mz.size == 0:
            item.note = "no survey scan"
            out.append(item)
            continue
        found = in_spectrum(mz, intensity, item.mz, window=SURVEY_WINDOW_DA)
        if found is None:
            item.note = f"nothing within ±{SURVEY_WINDOW_DA:g} Da"
            out.append(item)
            continue
        item.found_mz, item.height = found
        item.error_ppm = mass_error_ppm(item.found_mz, item.mz)
        if item.height < floor:
            item.note = (f"only {item.height:,.0f} counts, under the "
                         f"{floor:,.0f} a mass can be read from")
        elif abs(item.error_ppm) > tolerance:
            item.note = (f"the nearest peak is {item.error_ppm:+.1f} ppm away, "
                         f"past ±{tolerance:g}")
        else:
            item.present = True
            item.measured = measured_ratios(mz, intensity, pattern)
            if has_isotope_satellites(mz, intensity, item.found_mz,
                                      adduct.charge, tolerance=SURVEY_PEAK_DA):
                item.pattern = pattern_agreement(item.measured, item.expected)
            else:
                # a product-ion scan, where Q1 kept the monoisotopic ion and
                # threw its satellites away. Nothing to compare is not a
                # disagreement, and the score says so by falling back to the
                # mass alone
                item.note = "no isotope satellites in this spectrum"
        out.append(item)

    strongest = max((i.height for i in out if i.present), default=0.0)
    if strongest > 0:
        for item in out:
            item.relative = item.height / strongest if item.present else 0.0
    out.sort(key=lambda i: (-i.score, abs(i.error_ppm or 1e9)))
    return out


def _as_adducts(candidates, polarity=None) -> list[Adduct]:
    """`candidates` as `Adduct`s, or every adduct of a polarity."""
    if candidates is None:
        sign = polarity_sign(polarity) if polarity is not None else None
        return [a for a in ADDUCTS if a.name != NEUTRAL
                and (sign is None or a.polarity == sign)]
    out: list[Adduct] = []
    for candidate in candidates:
        if isinstance(candidate, Adduct):
            out.append(candidate)
        elif isinstance(candidate, AdductMatch):
            out.append(candidate.adduct)
        else:
            found = adduct_from_name(candidate)
            if found is not None:
                out.append(found)
    return out


def measured_ratios(mz: np.ndarray, intensity: np.ndarray,
                    pattern: list[tuple[float, float]],
                    window: float = SURVEY_PEAK_DA) -> tuple[float, ...]:
    """
    The heights at the pattern's masses, as shares of the first.

    Public because the same reading is wanted of a *fragment* on a
    product-ion spectrum (`explain.isotope_evidence`), and two functions
    reading a satellite two ways would be one too many. `window` is how far
    either side of each mass a height may be taken from: `SURVEY_PEAK_DA` is
    right for a survey, where the neighbours are whole nominal masses apart,
    and too wide for a labelled fragment, whose own `-1D` rung sits 2.9 mDa
    from where its M+1 belongs.
    """
    heights = []
    for target, _abundance in pattern:
        inside = (mz >= target - window) & (mz <= target + window)
        heights.append(float(intensity[inside].max()) if inside.any() else 0.0)
    if not heights or heights[0] <= 0:
        return ()
    return tuple(round(h / heights[0], 6) for h in heights)


def adduct_map(evidence: list[AdductEvidence]) -> str:
    """
    The adducts the survey actually shows, with their relative heights.

    Empty when it shows none, which is a sentence the caller writes rather
    than a phrase to be pasted into one.
    """
    present = [e for e in evidence if e.present]
    present.sort(key=lambda e: -e.height)
    return ", ".join(f"{e.name} {e.relative * 100:.0f}%" for e in present)


def _reason(formula: str, written: str, match: AdductMatch,
            matches: list[AdductMatch]) -> str:
    """
    One adduct measured against a written precursor, in words.

    The alternative worth printing is the form the *fragments* carry, not
    the next nearest number: a user who expected a protonated molecule and
    got an ammoniated one needs to see 413.3199 beside 430.3465, and being
    shown the sodium adduct instead answers a question nobody asked.
    """
    core = core_adduct(match.adduct)
    others = [m for m in matches if m.adduct.name == core.name
              and m.adduct.name != match.name]
    if not others:
        others = [m for m in matches if m is not match][:1]
    tail = ("; " + ", ".join(f"{m.name} would be {m.mz:.4f}" for m in others)
            if others else "")
    written_formula = format_formula(parse_formula(formula))
    if not match.within:
        # a candidate the isolation window let through is not one the mass
        # names, and saying "538.6 is [M+H]+ of C27H56NO7P" about a number
        # 396 ppm away would be asserting the very thing in doubt
        return (f"{written} sits {match.error_ppm:+.1f} ppm from the "
                f"{match.name} of {written_formula} ({match.mz:.4f}), "
                f"further than an adduct is named within{tail}")
    return (f"{written} is {match.name} of {written_formula} "
            f"({match.mz:.4f}, {match.error_ppm:+.1f} ppm){tail}")


def adduct_reason(formula: str, precursor: float, adduct, polarity=None,
                  tolerance: float | None = None) -> str:
    """
    Why this precursor is *this* adduct of this formula, in the same sentence
    `identify_adduct` writes when it works the adduct out for itself.

    A candidate found in the database at one adduct already knows which; what
    it does not know is how far the written precursor sits from it, and a row
    of candidates each found at a different adduct is unreadable without that.
    Sharing the sentence is the point: the record path and the own-structure
    path say the same thing about the same number, because they say it with
    the same code.
    """
    name = adduct if isinstance(adduct, str) else getattr(adduct, "name", "")
    matches = adducts_matching(formula, precursor, polarity, tolerance)
    found = next((m for m in matches if m.name == name), None)
    if found is None:
        return ""
    return _reason(formula, f"{float(precursor):g}", found, matches)


# --------------------------------------------------------------------------- #
# standards that are bought by their trivial names
# --------------------------------------------------------------------------- #
#: bile acids and their conjugates, by the abbreviation and the trivial name a
#: vendor's bottle carries, to the neutral formula and the name LIPID MAPS
#: files them under. LMSD holds every one of these — with a structure — but
#: under its own spelling, and nothing in it answers to `TDCA`. The table is
#: therefore an index into LIPID MAPS rather than a second database: the
#: formula here is the fallback for a machine with no LMSD installed, and the
#: `lipidmaps` name is what fetches the drawing when there is one.
#:
#: It stops at bile acids on purpose. These are the compounds this was built
#: against and every entry was checked against LMSD; a table that grew by
#: guesswork would be a list of formulas nobody measured.
STANDARDS: dict[str, tuple[str, str]] = {
    "cholic acid": ("C24H40O5", "Cholic acid"),
    "deoxycholic acid": ("C24H40O4", "Deoxycholic acid"),
    "chenodeoxycholic acid": ("C24H40O4", "Chenodeoxycholic Acid"),
    "ursodeoxycholic acid": ("C24H40O4", "Ursodeoxycholic acid"),
    "hyodeoxycholic acid": ("C24H40O4", "Hyodeoxycholic acid"),
    "lithocholic acid": ("C24H40O3", "Lithocholic acid"),
    "glycocholic acid": ("C26H43NO6", "Glycocholic Acid"),
    "glycodeoxycholic acid": ("C26H43NO5", "glycodeoxycholic acid"),
    "glycochenodeoxycholic acid": ("C26H43NO5", "Glycochenodeoxycholic acid"),
    "glycoursodeoxycholic acid": ("C26H43NO5", "Glycoursodeoxycholic acid"),
    "glycolithocholic acid": ("C26H43NO4", "Glycolithocholic Acid"),
    "taurocholic acid": ("C26H45NO7S", "Taurocholic acid"),
    "taurodeoxycholic acid": ("C26H45NO6S", "Taurodeoxycholic acid"),
    "taurochenodeoxycholic acid": ("C26H45NO6S", "Taurochenodeoxycholic acid"),
    "tauroursodeoxycholic acid": ("C26H45NO6S", "Tauroursodeoxycholic acid"),
    "taurolithocholic acid": ("C26H45NO5S", "Taurolithocholic acid"),
}

#: what the bottle is actually labelled. `CA-d4` is what the sample is called
#: and `cholic acid-d4` is what it is; both have to resolve to the same thing.
STANDARD_ALIASES: dict[str, str] = {
    "ca": "cholic acid",
    "dca": "deoxycholic acid",
    "cdca": "chenodeoxycholic acid",
    "udca": "ursodeoxycholic acid",
    "hdca": "hyodeoxycholic acid",
    "lca": "lithocholic acid",
    "gca": "glycocholic acid",
    "gdca": "glycodeoxycholic acid",
    "gcdca": "glycochenodeoxycholic acid",
    "gudca": "glycoursodeoxycholic acid",
    "glca": "glycolithocholic acid",
    "tca": "taurocholic acid",
    "tdca": "taurodeoxycholic acid",
    "tcdca": "taurochenodeoxycholic acid",
    "tudca": "tauroursodeoxycholic acid",
    "tlca": "taurolithocholic acid",
}

#: a label count written on the end of a name: `-d4`, `_d5`, ` d4`, `(d4)`.
#: Anchored to the end so that the `d18:1` inside a sphingoid shorthand — or
#: the `d` of `DCA` — cannot be read as one.
_STANDARD_LABEL = re.compile(r"[-_ (]?d(\d{1,2})\)?\s*$", re.IGNORECASE)


def split_labels(name: str) -> tuple[str, int]:
    """
    A written name split into the compound and the deuterium count on it.

    `cholic acid-d4` is cholic acid with four labels the name does not
    place, which is exactly what `explain.with_labels` enumerates. A name
    with no such suffix comes back with a count of zero.
    """
    text = str(name or "").strip()
    match = _STANDARD_LABEL.search(text)
    if match is None:
        return text, 0
    return text[:match.start()].strip(), int(match.group(1))


def standard_named(name: str) -> tuple[str, str] | None:
    """
    The (formula, LIPID MAPS name) of a standard written by name or
    abbreviation, or None when the table does not hold it. The label suffix
    is `split_labels`'s business, not this one's.
    """
    key = " ".join(str(name or "").strip().lower().split())
    if not key:
        return None
    key = STANDARD_ALIASES.get(key.replace(" ", ""), key)
    if key in STANDARDS:
        return STANDARDS[key]
    if not key.endswith(" acid") and f"{key} acid" in STANDARDS:
        return STANDARDS[f"{key} acid"]
    return None


# --------------------------------------------------------------------------- #
# the name for a mass: when the mass is right and the name is wrong
# --------------------------------------------------------------------------- #
#: how far a proposed name may sit from the written one. A name is wrong by a
#: chain, not by a rewrite: a transposed digit, a double bond counted on the
#: wrong side of the slash, a `d` typed for a `t`. Four carbons is two
#: methylenes either way and three double bonds covers a polyunsaturated acyl
#: written as a saturated one; past that the proposal stops being a correction
#: of this name and becomes a different compound that happens to weigh the
#: same, which is what the database list is for.
NAME_SEARCH_CARBONS = 4
NAME_SEARCH_DOUBLE_BONDS = 3

#: how many of a name's chains may differ from what was written. Two, for the
#: same reason as above and for one more: three chains each free to move over
#: their own range is the product of three ranges, and a triacylglycerol took
#: 13 seconds to enumerate before this was here — measured — against 0.1 s for
#: a two-chain class. A proposal that changes every chain of a name is not a
#: correction of it.
NAME_SEARCH_CHAINS = 2

#: how far a name's mass may sit from the written one, in Da, when the caller
#: does not say. Half a dalton: the same *nominal* mass, and no more.
#:
#: This is deliberately not the precision the mass was written to. A name is
#: only searched for when the written precursor already contradicts the name's
#: own formula by a whole dalton, which says where the digits came from — the
#: fraction was computed for the compound the name got wrong. The real method
#: shows it: `LacCER(d18:1/18:1(9Z))` is written 886.6407, its formula gives
#: 888.6407, and the difference is exactly 2.0000 — a nominal shift, where a
#: real double bond is 2.0157. Matching that fraction to its four written
#: decimals answers nothing at all; matching the nominal mass answers the
#: isomer, 15.7 mDa away. So the search is nominal and every row carries its
#: own Δ ppm, which is what separates a name that fits the mass exactly from
#: one that only fits the integer.
NAME_MASS_TOLERANCE = 0.5

#: most names offered from the class, and from the database
MAX_NAME_SUGGESTIONS = 25
MAX_DATABASE_SUGGESTIONS = 10

#: the base prefix each hydroxyl count is written with
_BASE_PREFIX = {n: prefix for prefix, n in _BASE_HYDROXYLS.items()}


@dataclass(frozen=True)
class NameSuggestion:
    """
    A name whose formula matches a mass the written name does not.

    `in_class` is the whole of the ranking: a name built from the written
    one's own class is a correction of it — same head group, same base, same
    number of chains, a chain or a double bond different — and a name out of
    the database is another compound entirely that happens to weigh the same.
    Both are offered; only the first is a proposal about *this* row.
    """

    name: str
    formula: str
    #: the m/z the formula gives through the adduct asked for
    mz: float
    #: the mass it was matched against — the precursor the method carries
    written: float
    in_class: bool = True
    #: where it came from, for the row that says so
    source: str = "the class"
    #: how many chains, hydroxyls or oxygens differ from the written name
    changes: int = 0
    #: characters of difference from the written name
    distance: int = 0

    @property
    def difference(self) -> float:
        return self.mz - self.written

    @property
    def error_ppm(self) -> float:
        """
        How far the formula's mass sits from the written one, in ppm.

        The same convention as `components.FormulaProposal`: the formula is
        the true mass and the written value is the measurement of it being
        judged, so the formula is the denominator.
        """
        return self.difference / self.mz * 1e6 if self.mz else 0.0


def _name_key(name: str) -> str:
    """
    A name reduced to what it says about the composition.

    Double-bond positions, spacing, brackets and case are how a name was typed
    rather than what it names, and two proposals that differ only there are
    the same proposal. Comparing the keys is what keeps `(9Z)` from making
    every proposal look four edits away from the name it corrects — and what
    stops `TG 52:2` being offered `TG(52:2)`, which is the same name with the
    brackets this module writes.
    """
    text = " ".join(str(name or "").split()).lower()
    text = _POSITION.sub("", text)
    return text.translate(str.maketrans("", "", " ()[]_"))


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance, iterative and over short strings only."""
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def _chain_options(chain: Chain, is_base: bool) -> list[tuple[int, int, bool]]:
    """
    Every (carbons, double bonds, hydroxylated) one chain may be instead.

    Two chains are excluded rather than offered: one with more than one double
    bond per two carbons, which is not a fatty chain, and — on the sphingoid
    base — a hydroxyl written as `h`, since the base's hydroxyls are the
    `d`/`t`/`m` prefix and are varied there.
    """
    carbons = [c for c in range(chain.carbons - NAME_SEARCH_CARBONS,
                                chain.carbons + NAME_SEARCH_CARBONS + 1)
               if MIN_CHAIN_CARBONS <= c <= MAX_CHAIN_CARBONS]
    double_bonds = [d for d in range(
        max(0, chain.double_bonds - NAME_SEARCH_DOUBLE_BONDS),
        chain.double_bonds + NAME_SEARCH_DOUBLE_BONDS + 1)]
    if is_base or chain.prefix not in ("", "c", "h"):
        hydroxyls = (chain.hydroxylated,)
    else:
        hydroxyls = (False, True)
    return [(c, d, h) for c in carbons for d in double_bonds
            if 2 * d <= c for h in hydroxyls]


def _distributions(options: list[list[tuple[int, int, bool]]],
                   written: list[tuple[int, int, bool]],
                   carbons: int, double_bonds: int, hydroxyls: int,
                   max_changed: int = NAME_SEARCH_CHAINS):
    """
    Every way of splitting these totals over the chains, each chain within its
    own options and at most `max_changed` of them different from what the name
    wrote. Bounded by what the remaining chains can still reach, which is what
    keeps a three-chain class from walking its whole product.
    """
    n = len(options)
    reach = [(0, 0, 0, 0)] * (n + 1)        # min/max carbons, min/max dbs
    hydroxyl_reach = [0] * (n + 1)
    for index in range(n - 1, -1, -1):
        low_c, high_c, low_d, high_d = reach[index + 1]
        reach[index] = (low_c + min(c for c, _d, _h in options[index]),
                        high_c + max(c for c, _d, _h in options[index]),
                        low_d + min(d for _c, d, _h in options[index]),
                        high_d + max(d for _c, d, _h in options[index]))
        hydroxyl_reach[index] = hydroxyl_reach[index + 1] + (
            1 if any(h for _c, _d, h in options[index]) else 0)

    def walk(index, left_c, left_d, left_h, left_changes, picked):
        if index == n:
            if left_c == 0 and left_d == 0 and left_h == 0:
                yield tuple(picked)
            return
        for option in options[index]:
            changed = int(option != written[index])
            if changed > left_changes:
                continue
            c, d, h = option
            rest_c, rest_d, rest_h = left_c - c, left_d - d, left_h - int(h)
            low_c, high_c, low_d, high_d = reach[index + 1]
            if not low_c <= rest_c <= high_c or not low_d <= rest_d <= high_d:
                continue
            if not 0 <= rest_h <= hydroxyl_reach[index + 1]:
                continue
            picked.append(option)
            yield from walk(index + 1, rest_c, rest_d, rest_h,
                            left_changes - changed, picked)
            picked.pop()

    yield from walk(0, carbons, double_bonds, hydroxyls, max_changed, [])


def _candidates(parsed: Shorthand, weighs) -> list[Shorthand]:
    """
    Every name in this one's class within the search's reach that weighs the
    right amount.

    Totals first, their distribution over the chains second, and `weighs` —
    which takes the hydroxyls, the oxygens and the totals — asked in between.
    That order is the whole of the performance: a lipid's mass is fixed by its
    totals, so a set of totals that cannot weigh what the method says has no
    name worth writing out, and only a few sets of totals ever match. Asking
    afterwards instead took a triacylglycerol from 0.05 s to 3.9 s, because
    the chains of a name that cannot be right were still being split every
    possible way.
    """
    chains = parsed.chains
    options = [_chain_options(chain, parsed.writes_base and index == 0)
               for index, chain in enumerate(chains)]
    written_chains = [(chain.carbons, chain.double_bonds, chain.hydroxylated)
                      for chain in chains]
    written_carbons = sum(chain.carbons for chain in chains)
    written_double_bonds = sum(chain.double_bonds for chain in chains)
    reach = len(chains)

    base_options = ([1, 2, 3] if parsed.writes_base
                    else [parsed.base_hydroxyls])
    extra_options = ([parsed.extra_oxygens] if parsed.lipid.sphingoid else
                     sorted({max(0, parsed.extra_oxygens + delta)
                             for delta in (-1, 0, 1)}))

    out: list[Shorthand] = []
    seen: set[str] = set()
    carbon_range = range(max(MIN_CHAIN_CARBONS,
                             written_carbons - NAME_SEARCH_CARBONS * reach),
                         written_carbons + NAME_SEARCH_CARBONS * reach + 1)
    double_bond_range = range(
        max(0, written_double_bonds - NAME_SEARCH_DOUBLE_BONDS * reach),
        written_double_bonds + NAME_SEARCH_DOUBLE_BONDS * reach + 1)
    hydroxyl_counts = range(sum(1 for chain_options in options
                                if any(h for _c, _d, h in chain_options)) + 1)

    for base_hydroxyls in base_options:
        for extra_oxygens in extra_options:
            for hydroxylated in hydroxyl_counts:
                for carbons in carbon_range:
                    for double_bonds in double_bond_range:
                        if not weighs(base_hydroxyls,
                                      extra_oxygens + hydroxylated,
                                      carbons, double_bonds):
                            continue
                        for picked in _distributions(
                                options, written_chains, carbons,
                                double_bonds, hydroxylated):
                            candidate = _rebuild(parsed, picked, base_hydroxyls,
                                                 extra_oxygens)
                            key = _name_key(candidate.text)
                            if key in seen:
                                continue
                            seen.add(key)
                            out.append(candidate)
    return out


def _rebuild(parsed: Shorthand, picked: tuple[tuple[int, int, bool], ...],
             base_hydroxyls: int, extra_oxygens: int) -> Shorthand:
    """One enumerated composition written back as a name in the same shape."""
    chains = []
    for index, (carbons, double_bonds, hydroxylated) in enumerate(picked):
        written = parsed.chains[index]
        if parsed.writes_base and index == 0:
            # the base says its hydroxyls in its prefix, and says nothing
            # where it has the usual two and the written name said nothing
            prefix = ("" if (base_hydroxyls == DEFAULT_BASE_HYDROXYLS
                             and written.prefix not in _BASE_HYDROXYLS)
                      else _BASE_PREFIX[base_hydroxyls])
        elif hydroxylated:
            prefix = "h"
        else:
            prefix = "" if written.prefix in ("c", "h") else written.prefix
        chains.append(Chain(prefix, carbons, double_bonds))
    return Shorthand(lipid=parsed.lipid, chains=tuple(chains),
                     base_hydroxyls=base_hydroxyls, extra_oxygens=extra_oxygens,
                     labels=parsed.labels,
                     base_double_bonds=parsed.base_double_bonds,
                     written_class=parsed.written_class)


def _changes(parsed: Shorthand, candidate: Shorthand) -> int:
    """How many things the proposal changes about the written name."""
    changed = sum(1 for written, offered in zip(parsed.chains, candidate.chains)
                  if (written.carbons, written.double_bonds,
                      written.hydroxylated) != (offered.carbons,
                                                offered.double_bonds,
                                                offered.hydroxylated))
    changed += int(parsed.base_hydroxyls != candidate.base_hydroxyls)
    changed += int(parsed.extra_oxygens != candidate.extra_oxygens)
    return changed


def names_for_mass(mz: float, adduct: str | Adduct = "[M+H]+",
                   like: str = "", tolerance: float | None = None,
                   database=None,
                   max_results: int = MAX_NAME_SUGGESTIONS,
                   max_database: int = MAX_DATABASE_SUGGESTIONS,
                   ) -> list[NameSuggestion]:
    """
    Names whose formula matches this mass, for when the name is the mistake.

    `components.precursor_repairs` finds a written precursor its name's
    formula contradicts and offers to overwrite the mass. Where the two are a
    whole dalton or more apart that is the wrong repair: the instrument
    acquired the mass that was written, so it is the *name* that is wrong, and
    this is what says what it might have been.

    Two lists come back, the class's first and the database's after it, every
    row carrying `in_class` to say which it is:

    - names built out of the written name's own class — same head group, same
      base, the same number of chains — with the chains moved within
      `NAME_SEARCH_CARBONS` and `NAME_SEARCH_DOUBLE_BONDS`, the hydroxyls
      moved, and the sphingoid base's `d`/`t`/`m` varied. These are ranked by
      how little of the written name they change, nearest first: a name that
      differs by one double bond is a correction, and one that differs by
      three chains and a hydroxyl is a coincidence.
    - what LIPID MAPS holds at the same mass, which is where a name outside
      the class comes from. Grouped by species, because a mass search answers
      a species and never a compound.

    `tolerance` is in Da and defaults to `NAME_MASS_TOLERANCE`, which is the
    nominal mass and not the written one — see the constant for why. Nothing
    is offered that the mass does not support, so an empty list is a real
    answer, and on the real method it is the commonest one: a disagreement of
    a whole odd dalton cannot be a chain at all. A chain moves the mass by
    14 Da, a double bond by 2 and a hydroxyl by 16, so nothing this class can
    be reaches a mass 1 Da away — the name is not off by a chain, the number
    is off by a digit, and the class has nothing to say about it.
    """
    form = ADDUCTS_BY_NAME.get(adduct) if isinstance(adduct, str) else adduct
    if form is None or not mz or mz <= 0:
        return []
    tolerance = NAME_MASS_TOLERANCE if tolerance is None else tolerance
    parsed = parse_shorthand(like)
    written_key = _name_key(like)
    suggestions: list[NameSuggestion] = []
    if parsed is not None:
        def weighs(base_hydroxyls, oxygens, carbons, double_bonds) -> bool:
            """Could a name with these totals weigh what was written?"""
            for total_c, total_db in parsed.readings_of(carbons, double_bonds):
                counts = composition(parsed.lipid, total_c, total_db,
                                     base_hydroxyls, oxygens, parsed.labels)
                if counts is None:
                    continue
                if abs(form.mz(monoisotopic_mass(counts)) - mz) <= tolerance:
                    return True
            return False

        for candidate in _candidates(parsed, weighs):
            if _name_key(candidate.text) == written_key:
                continue
            for counts in candidate.compositions():
                offered = form.mz(monoisotopic_mass(counts))
                if abs(offered - mz) > tolerance:
                    continue
                suggestions.append(NameSuggestion(
                    name=candidate.text, formula=format_formula(counts),
                    mz=offered, written=mz, in_class=True, source="the class",
                    changes=_changes(parsed, candidate),
                    distance=_edit_distance(_name_key(candidate.text),
                                            written_key)))
                break
        suggestions.sort(key=lambda s: (s.distance, s.changes,
                                        abs(s.error_ppm), s.name))
        suggestions = suggestions[:max_results]

    found = (database() if callable(database) else database) if database else None
    if found is not None:
        # a database name is judged on its mass alone — there is no written
        # name for it to be a correction of — so it gets the precision the
        # written value actually carries and not the nominal search above.
        # The same limit `fill_formulas` used to refuse the formula in the
        # first place; a call, not an import cycle, since components imports
        # this module and never the other way round.
        from .components import written_tolerance
        from .lipidmaps import group_by_species

        exact = written_tolerance(mz)
        taken = {_name_key(s.name) for s in suggestions} | {written_key}
        for species in group_by_species(found.search_mz(mz, form, exact)):
            name = species.species
            if _name_key(name) in taken:
                continue
            taken.add(_name_key(name))
            record = species.records[0] if species.records else None
            suggestions.append(NameSuggestion(
                name=name, formula=species.formula, mz=species.theoretical,
                written=mz, in_class=False,
                source=f"LIPID MAPS {record.lm_id}" if record else "LIPID MAPS",
                changes=0,
                distance=_edit_distance(_name_key(name), written_key)))
            if sum(1 for s in suggestions if not s.in_class) >= max_database:
                break
    return suggestions
# --------------------------------------------------------------------------- #
# isotope patterns
# --------------------------------------------------------------------------- #
def _convolve(a: list[tuple[float, float]], b: list[tuple[float, float]],
              prune: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for mass_a, abundance_a in a:
        for mass_b, abundance_b in b:
            abundance = abundance_a * abundance_b
            if abundance >= prune:
                out.append((mass_a + mass_b, abundance))
    return out


def _merge(peaks: list[tuple[float, float]],
           tolerance: float) -> list[tuple[float, float]]:
    """Collapse peaks closer than `tolerance` into their weighted centroid."""
    if not peaks:
        return []
    peaks = sorted(peaks)
    merged = [list(peaks[0])]
    for mass, abundance in peaks[1:]:
        last = merged[-1]
        if mass - last[0] <= tolerance:
            total = last[1] + abundance
            last[0] = (last[0] * last[1] + mass * abundance) / total if total else mass
            last[1] = total
        else:
            merged.append([mass, abundance])
    return [(mass, abundance) for mass, abundance in merged]


def isotope_pattern(counts: dict[str, int], adduct: Adduct | None = None,
                    min_abundance: float = 0.001, max_peaks: int = 12,
                    merge_tolerance: float = 0.01) -> list[tuple[float, float]]:
    """
    Theoretical isotope pattern as (m/z, relative abundance), the base peak
    scaled to 1.0.

    `merge_tolerance` collapses the fine structure that a given resolving power
    cannot separate: at 0.01 Da the 13C and 15N peaks of the same nominal mass
    come out as one, which is what a TOF instrument actually records.
    """
    if not counts:
        return []
    prune = min_abundance * 1e-3
    distribution: list[tuple[float, float]] = [(0.0, 1.0)]
    for element, n in counts.items():
        isotopes = ISOTOPES[element]
        if len(isotopes) == 1:
            distribution = [(mass + isotopes[0][0] * n, abundance)
                            for mass, abundance in distribution]
            continue
        total = sum(abundance for _m, abundance in isotopes)
        normalised = [(mass, abundance / total) for mass, abundance in isotopes]
        power = normalised
        remaining = n
        base = normalised
        result: list[tuple[float, float]] = [(0.0, 1.0)]
        while remaining:  # binary exponentiation keeps big counts affordable
            if remaining & 1:
                result = _merge(_convolve(result, power, prune), merge_tolerance / 4)
            remaining >>= 1
            if remaining:
                power = _merge(_convolve(power, power, prune), merge_tolerance / 4)
        del base
        distribution = _merge(_convolve(distribution, result, prune),
                              merge_tolerance / 4)

    peaks = _merge(distribution, merge_tolerance)
    top = max(abundance for _m, abundance in peaks)
    peaks = [(mass, abundance / top) for mass, abundance in peaks
             if abundance / top >= min_abundance]
    peaks.sort()
    peaks = peaks[:max_peaks]
    if adduct is not None:
        peaks = [(adduct.mz(mass), abundance) for mass, abundance in peaks]
    return peaks


def match_isotope_pattern(mz: np.ndarray, intensity: np.ndarray,
                          pattern: list[tuple[float, float]],
                          tolerance: float = 0.02) -> float:
    """
    Score a theoretical pattern against a measured spectrum, from 0 to 1.

    Both patterns are put on the same scale by dividing through their
    monoisotopic peak, and the score is then built only from the satellites
    (M+1, M+2, ...):

        score = 1 - sum|measured - theoretical| / sum(theoretical)

    Scoring the satellites alone is the point. The monoisotopic peak is the one
    the search matched on, so it always agrees; including it in the sum would
    dilute every disagreement and push unrelated candidates to the same high
    number. Measured against the satellites, a formula whose M+1 is absent
    scores 0, which is the honest answer.
    """
    if mz.size == 0 or len(pattern) < 2:
        return 0.0
    measured = []
    for target, _abundance in pattern:
        window = (mz >= target - tolerance) & (mz <= target + tolerance)
        measured.append(float(intensity[window].max()) if window.any() else 0.0)
    if measured[0] <= 0:
        return 0.0

    theoretical = [abundance for _mz, abundance in pattern]
    if theoretical[0] <= 0:
        return 0.0
    measured = [value / measured[0] for value in measured]
    theoretical = [value / theoretical[0] for value in theoretical]

    weight = sum(theoretical[1:])
    if weight <= 0:
        return 0.0
    difference = sum(abs(a - b) for a, b in zip(measured[1:], theoretical[1:]))
    return max(0.0, 1.0 - difference / weight)


#: 13C - 12C, the spacing between consecutive isotope peaks of an organic ion
NEUTRON_SPACING = 1.0033548378


def has_isotope_satellites(mz: np.ndarray, intensity: np.ndarray,
                           base_mz: float, charge: int = 1,
                           tolerance: float = 0.02,
                           min_relative: float = 0.005) -> bool:
    """
    Does the spectrum actually carry an isotope pattern for this ion?

    Any organic molecule shows an M+1 of roughly 1.1% per carbon, so anything
    below `min_relative` means the satellites are not there. That is the normal
    situation in a product-ion scan, where Q1 isolates the monoisotopic
    precursor and its satellites never reach the detector — scoring candidates
    against that spectrum only measures noise.
    """
    if mz.size == 0 or base_mz <= 0:
        return False
    window = (mz >= base_mz - tolerance) & (mz <= base_mz + tolerance)
    if not window.any():
        return False
    base = float(intensity[window].max())
    if base <= 0:
        return False
    satellite_mz = base_mz + NEUTRON_SPACING / max(abs(charge), 1)
    window = (mz >= satellite_mz - tolerance) & (mz <= satellite_mz + tolerance)
    if not window.any():
        return False
    return float(intensity[window].max()) / base >= min_relative


# --------------------------------------------------------------------------- #
# formula finder
# --------------------------------------------------------------------------- #
@dataclass
class FormulaHit:
    """One candidate composition for a measured mass."""

    counts: dict[str, int]
    neutral_mass: float
    mz: float
    error_mda: float
    error_ppm: float
    rdbe: float
    isotope_score: float = 0.0
    formula: str = field(default="", init=False)

    def __post_init__(self):
        self.formula = format_formula(self.counts)


#: default search ranges, chosen for small molecules such as lipid mediators
DEFAULT_RANGES: dict[str, tuple[int, int]] = {
    "C": (0, 60),
    "H": (0, 120),
    "N": (0, 4),
    "O": (0, 12),
    "S": (0, 2),
    "P": (0, 2),
}


def passes_golden_rules(counts: dict[str, int]) -> bool:
    """
    Element-ratio checks from the "Seven Golden Rules" (Kind & Fiehn, 2007),
    which throw away compositions that are arithmetically valid but chemically
    implausible.
    """
    carbon = counts.get("C", 0)
    hydrogen = counts.get("H", 0) + counts.get("D", 0)
    if carbon == 0:
        return hydrogen == 0 or not counts
    ratios = {
        "H": (0.1, 3.1),
        "N": (0.0, 1.3),
        "O": (0.0, 1.2),
        "P": (0.0, 0.3),
        "S": (0.0, 0.8),
    }
    for element, (low, high) in ratios.items():
        n = hydrogen if element == "H" else counts.get(element, 0)
        ratio = n / carbon
        if not low <= ratio <= high:
            return False
    return True


def find_formulas(neutral_mass: float, tolerance: float, unit: str = "ppm",
                  ranges: dict[str, tuple[int, int]] | None = None,
                  rdbe_range: tuple[float, float] = (-0.5, 40.0),
                  even_electron: bool = True, golden_rules: bool = True,
                  max_results: int = 100) -> list[FormulaHit]:
    """
    All elemental compositions whose monoisotopic mass matches `neutral_mass`.

    The search walks the elements from heaviest to lightest, bounding each
    count by the mass still unassigned, so the tree stays small. `even_electron`
    keeps only integer RDBE values, which is what a closed-shell molecule has.
    """
    ranges = ranges or DEFAULT_RANGES
    elements = [e for e in ranges if ranges[e][1] > 0]
    if not elements or neutral_mass <= 0:
        return []
    for element in elements:
        if element not in ISOTOPES:
            raise FormulaError(f"unknown element: {element}")

    half_width = (neutral_mass * tolerance * 1e-6 if unit.lower() == "ppm"
                  else tolerance)
    lo, hi = neutral_mass - half_width, neutral_mass + half_width

    masses = {e: ISOTOPES[e][0][0] for e in elements}
    order = sorted(elements, key=lambda e: masses[e], reverse=True)
    hits: list[FormulaHit] = []

    def recurse(index: int, remaining_lo: float, remaining_hi: float,
                counts: dict[str, int]) -> None:
        if len(hits) >= max_results:
            return
        if index == len(order):
            if remaining_lo <= 0.0 <= remaining_hi:
                _accept(counts)
            return
        element = order[index]
        mass = masses[element]
        low, high = ranges[element]
        start = max(low, 0)
        stop = min(high, int(remaining_hi // mass))
        for n in range(start, stop + 1):
            counts[element] = n
            recurse(index + 1, remaining_lo - n * mass, remaining_hi - n * mass,
                    counts)
            if len(hits) >= max_results:
                break
        counts.pop(element, None)

    def _accept(counts: dict[str, int]) -> None:
        clean = {e: n for e, n in counts.items() if n}
        if not clean:
            return
        value = rdbe(clean)
        if not rdbe_range[0] <= value <= rdbe_range[1]:
            return
        if even_electron and abs(value - round(value)) > 1e-9:
            return
        if golden_rules and not passes_golden_rules(clean):
            return
        mass = monoisotopic_mass(clean)
        hits.append(
            FormulaHit(
                counts=clean,
                neutral_mass=mass,
                mz=mass,
                error_mda=mass_error_mda(neutral_mass, mass),
                error_ppm=mass_error_ppm(neutral_mass, mass),
                rdbe=value,
            )
        )

    recurse(0, lo, hi, {})
    hits.sort(key=lambda hit: abs(hit.error_ppm))
    return hits


def rank_by_isotope_pattern(hits: list[FormulaHit], mz: np.ndarray,
                            intensity: np.ndarray, adduct: Adduct,
                            tolerance: float = 0.02) -> list[FormulaHit]:
    """
    Score each candidate against the measured isotope pattern and re-rank.

    Exact mass alone rarely separates candidates above a few hundred daltons;
    the relative heights of the M+1 and M+2 peaks usually do.
    """
    for hit in hits:
        pattern = isotope_pattern(hit.counts, adduct, min_abundance=0.01,
                                  max_peaks=5)
        hit.mz = adduct.mz(hit.neutral_mass)
        hit.isotope_score = match_isotope_pattern(mz, intensity, pattern,
                                                  tolerance)
    hits.sort(key=lambda hit: (-hit.isotope_score, abs(hit.error_ppm)))
    return hits
