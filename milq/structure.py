"""
Molecular structures, and the fragments a bond cleavage would leave.

A molfile is a plain connection table with 2D coordinates: atoms, bonds, and
where to draw them. That is everything needed to enumerate cleavages and to
picture one, so no chemistry toolkit is involved — the coordinates are already
laid out by whoever drew the structure, and the graph work is a few lines.

Hydrogens are implicit in these files. They are counted from the valence left
over on each atom, and the total is checked against the molecular formula the
database publishes: a structure whose hydrogens do not add up is marked
unreliable rather than allowed to produce fragment masses that look exact and
are wrong.

What this does *not* do is say which cleavages actually happen. Enumerating
bonds is arithmetic; predicting a spectrum is not. Treat the list as the set of
masses worth looking for, and confirm it against a measured product spectrum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, combinations_with_replacement

from .chemistry import ELECTRON_MASS, format_formula, monoisotopic_mass, parse_formula

#: how many bonds a neutral atom of each element normally makes. Where an
#: element has several, the smallest that covers the bonds actually drawn wins.
VALENCES: dict[str, tuple[int, ...]] = {
    "C": (4,), "N": (3, 5), "O": (2,), "P": (3, 5), "S": (2, 4, 6),
    "H": (1,), "F": (1,), "Cl": (1,), "Br": (1,), "I": (1,), "Se": (2, 4, 6),
    "B": (3,), "Si": (4,), "As": (3, 5), "D": (1,),
}

#: bonds beyond this many cut at once are not enumerated. Two is what a ring
#: needs to come apart; three is a combinatorial explosion of pieces nobody
#: would look for.
MAX_CUTS = 2

#: small neutrals a piece sheds after the bond breaks. Cutting bonds alone does
#: not reach the ions a spectrum actually shows — the sphingoid base of a
#: ceramide is seen at 264.2686, which is the backbone minus two waters, and no
#: single cleavage produces it. Each entry names the atoms it takes with it, so
#: a loss is only allowed from a piece that has them.
NEUTRAL_LOSSES: dict[str, str] = {
    "H2O": "H2O",
    "NH3": "NH3",
    "CO": "CO",
    "CO2": "CO2",
    "HCOOH": "CH2O2",
}

#: the group a piece must actually carry for the loss to be possible, and how
#: many of them a repeated loss needs. Counting elements is not enough: a
#: ceramide has three oxygens and no carboxyl anywhere, and was being offered a
#: carbon dioxide loss it has no way to make.
LOSS_REQUIRES: dict[str, str] = {
    "H2O": "hydroxyl",
    "NH3": "amine",
    "CO": "carbonyl",
    "CO2": "carboxyl",
    "HCOOH": "carboxyl",
}


@dataclass(frozen=True)
class Atom:
    element: str
    x: float
    y: float
    charge: int = 0
    hydrogens: int = 0
    #: heavy hydrogens the atom carries, once its explicit ones are folded in
    deuterium: int = 0


@dataclass(frozen=True)
class Bond:
    a: int          # index into Structure.atoms
    b: int
    order: int = 1

    def other(self, atom: int) -> int:
        return self.b if atom == self.a else self.a


@dataclass
class Structure:
    """Heavy atoms, their bonds, and the 2D layout they were drawn with."""

    atoms: list[Atom]
    bonds: list[Bond]
    #: the hydrogen count adds up to the published formula
    reliable: bool = True
    #: bonds that lie on a ring, and so do not split the molecule on their own
    ring_bonds: frozenset[int] = field(default_factory=frozenset)

    def __len__(self) -> int:
        return len(self.atoms)

    @property
    def formula(self) -> str:
        return format_formula(self.composition(range(len(self.atoms))))

    def composition(self, atoms) -> dict[str, int]:
        counts: dict[str, int] = {}
        for index in atoms:
            atom = self.atoms[index]
            counts[atom.element] = counts.get(atom.element, 0) + 1
            if atom.hydrogens:
                counts["H"] = counts.get("H", 0) + atom.hydrogens
            if atom.deuterium:
                counts["D"] = counts.get("D", 0) + atom.deuterium
        return counts

    def neighbours(self, atom: int) -> list[int]:
        return [b.other(atom) for b in self.bonds if atom in (b.a, b.b)]

    def bonded(self, atom: int) -> list[tuple[int, int]]:
        """(neighbour, bond order) pairs, for reading a functional group off."""
        return [(b.other(atom), b.order) for b in self.bonds
                if atom in (b.a, b.b)]

    def functional_groups(self, atoms) -> dict[str, int]:
        """
        How many of each group a set of atoms carries.

        Only what a neutral loss needs to be possible: an alcohol to lose
        water, an amine to lose ammonia, a carbonyl to lose carbon monoxide,
        a carboxyl for carbon dioxide or formic acid.
        """
        inside = set(atoms)
        counts = {"hydroxyl": 0, "amine": 0, "carbonyl": 0, "carboxyl": 0}
        for index in inside:
            atom = self.atoms[index]
            if atom.element == "O" and atom.hydrogens:
                counts["hydroxyl"] += 1
            elif atom.element == "N" and atom.hydrogens:
                counts["amine"] += 1
            elif atom.element == "C":
                oxygens = [(n, order) for n, order in self.bonded(index)
                           if n in inside and self.atoms[n].element == "O"]
                if len(oxygens) >= 2:
                    counts["carboxyl"] += 1
                if any(order >= 2 for _n, order in oxygens):
                    counts["carbonyl"] += 1
        return counts

    # -- storage ---------------------------------------------------------------- #
    def to_compact(self) -> dict:
        """
        A form small enough to keep for every structure in the database.

        Coordinates are hundredths: the molfile carries four decimals, and two
        is finer than any screen the picture is drawn on.
        """
        compact = {
            "e": " ".join(a.element for a in self.atoms),
            "p": [v for a in self.atoms
                  for v in (round(a.x * 100), round(a.y * 100))],
            "b": [v for b in self.bonds for v in (b.a, b.b, b.order)],
        }
        charged = [(i, a.charge) for i, a in enumerate(self.atoms) if a.charge]
        if charged:
            compact["q"] = [v for pair in charged for v in pair]
        if not self.reliable:
            compact["bad"] = 1
        return compact

    @classmethod
    def from_compact(cls, data: dict) -> "Structure":
        elements = data["e"].split()
        points = data["p"]
        charges = dict(zip(data.get("q", [])[0::2], data.get("q", [])[1::2]))
        flat = data["b"]
        bonds = [Bond(a=flat[i], b=flat[i + 1], order=flat[i + 2])
                 for i in range(0, len(flat), 3)]
        atoms = [Atom(element=element, x=points[2 * i] / 100.0,
                      y=points[2 * i + 1] / 100.0, charge=charges.get(i, 0))
                 for i, element in enumerate(elements)]
        return cls(atoms=_with_hydrogens(atoms, bonds), bonds=bonds,
                   reliable=not data.get("bad"))


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #
def parse_molblock(text: str, formula: str = "",
                   rings: bool = False) -> Structure | None:
    """
    Read a V2000 molblock. `formula`, when given, checks the hydrogen count.

    Ring detection is off by default: enumerating cleavages does not need it,
    and paying for it on all fifty thousand structures at index time would be
    minutes of work nothing reads.

    Returns None for anything that is not a usable connection table, rather
    than a half-read molecule.
    """
    lines = text.splitlines()
    if len(lines) < 4:
        return None
    counts = lines[3]
    try:
        n_atoms = int(counts[0:3])
        n_bonds = int(counts[3:6])
    except ValueError:
        return None
    if n_atoms <= 0 or len(lines) < 4 + n_atoms + n_bonds:
        return None

    atoms: list[Atom] = []
    for line in lines[4:4 + n_atoms]:
        try:
            x, y = float(line[0:10]), float(line[10:20])
        except ValueError:
            return None
        element = line[31:34].strip() or line[30:33].strip()
        if not element:
            return None
        atoms.append(Atom(element=element, x=x, y=y))

    bonds: list[Bond] = []
    for line in lines[4 + n_atoms:4 + n_atoms + n_bonds]:
        try:
            a = int(line[0:3]) - 1
            b = int(line[3:6]) - 1
            order = int(line[6:9])
        except ValueError:
            return None
        if not (0 <= a < n_atoms and 0 <= b < n_atoms) or a == b:
            return None
        # an aromatic bond is drawn as 4; counted as 1 it would misplace a
        # hydrogen, which the formula check downstream will catch
        bonds.append(Bond(a=a, b=b, order=1 if order == 4 else min(order, 3)))

    tail = lines[4 + n_atoms + n_bonds:]
    charges = _charges(tail, n_atoms)
    labels = _isotopes(tail, n_atoms)
    atoms = [
        Atom(element=(isotope_label(a.element, labels[i]) if i in labels
                      else a.element),
             x=a.x, y=a.y, charge=charges.get(i, 0))
        for i, a in enumerate(atoms)
    ]
    structure = Structure(atoms=_with_hydrogens(atoms, bonds), bonds=bonds)
    if rings:
        structure.ring_bonds = ring_bonds(structure)
    if formula:
        structure.reliable = _hydrogens_agree(structure, formula)
    return structure


def suppress_hydrogens(structure: Structure) -> Structure:
    """
    Fold explicit hydrogens into the atoms that carry them.

    PubChem writes every hydrogen out; LIPID MAPS writes the ones a
    stereocentre needs. Either way a hydrogen is not a piece anybody looks
    for, and leaving them in the connection table means enumerating the
    cleavage of forty C–H bonds: forty fragments differing from the whole
    molecule by one hydrogen, which is what a hydrogen shift already covers,
    and thousands of candidate masses that match a spectrum by accident.

    The formula is unchanged — a suppressed hydrogen is still counted — and
    so is the geometry of what is left. A drawing that places deuterium keeps
    it, on the atom it was drawn on.
    """
    heavy = [i for i, a in enumerate(structure.atoms)
             if a.element not in ("H", "D")]
    if len(heavy) == len(structure.atoms) or not heavy:
        return structure
    position = {old: new for new, old in enumerate(heavy)}
    light = {i: structure.atoms[i].element for i in range(len(structure.atoms))
             if i not in position}
    gained_h = {i: 0 for i in heavy}
    gained_d = {i: 0 for i in heavy}
    for bond in structure.bonds:
        for a, b in ((bond.a, bond.b), (bond.b, bond.a)):
            if a in light and b in position:
                if light[a] == "D":
                    gained_d[b] += 1
                else:
                    gained_h[b] += 1
    atoms = [Atom(element=structure.atoms[i].element, x=structure.atoms[i].x,
                  y=structure.atoms[i].y, charge=structure.atoms[i].charge,
                  hydrogens=structure.atoms[i].hydrogens + gained_h[i],
                  deuterium=structure.atoms[i].deuterium + gained_d[i])
             for i in heavy]
    bonds = [Bond(a=position[b.a], b=position[b.b], order=b.order)
             for b in structure.bonds
             if b.a in position and b.b in position]
    return Structure(atoms=atoms, bonds=bonds, reliable=structure.reliable)


def _charges(tail: list[str], n_atoms: int) -> dict[int, int]:
    """`M  CHG` lines, which is where a phosphate anion is recorded."""
    found: dict[int, int] = {}
    for line in tail:
        if not line.startswith("M  CHG"):
            continue
        parts = line.split()[3:]
        for index, charge in zip(parts[0::2], parts[1::2]):
            try:
                atom = int(index) - 1
                if 0 <= atom < n_atoms:
                    found[atom] = int(charge)
            except ValueError:
                continue
    return found


def _isotopes(tail: list[str], n_atoms: int) -> dict[int, str]:
    """
    `M  ISO` lines, which is how a labelled standard is written.

    A deuterated oxylipin is drawn with ordinary hydrogens and one of these
    lines; read as ordinary hydrogen the mass comes out a nucleon short per
    label, which for a d5 standard is five.
    """
    found: dict[int, str] = {}
    for line in tail:
        if not line.startswith("M  ISO"):
            continue
        parts = line.split()[3:]
        for index, nucleons in zip(parts[0::2], parts[1::2]):
            try:
                atom, mass = int(index) - 1, int(nucleons)
            except ValueError:
                continue
            if 0 <= atom < n_atoms:
                found[atom] = mass
    return found


def isotope_label(element: str, nucleons: int) -> str:
    """`D` for heavy hydrogen, `[13C]` for the rest: what the formulas use."""
    if element == "H" and nucleons == 2:
        return "D"
    return f"[{nucleons}{element}]"


def _with_hydrogens(atoms: list[Atom], bonds: list[Bond]) -> list[Atom]:
    used = [0] * len(atoms)
    for bond in bonds:
        used[bond.a] += bond.order
        used[bond.b] += bond.order
    filled = []
    for atom, taken in zip(atoms, used):
        filled.append(Atom(element=atom.element, x=atom.x, y=atom.y,
                           charge=atom.charge,
                           hydrogens=implicit_hydrogens(atom.element, taken,
                                                        atom.charge)))
    return filled


def implicit_hydrogens(element: str, bond_orders: int, charge: int = 0) -> int:
    """
    Hydrogens the drawing leaves off: the valence not spoken for by bonds.

    A cation on nitrogen makes room for one more bond, an anion on oxygen for
    one fewer, which is the whole of what the charge does here.
    """
    options = VALENCES.get(element)
    if options is None:
        return 0
    if element in ("C", "Si"):
        available = [options[0] - abs(charge)]
    else:
        available = [v + charge for v in options]
    for valence in available:
        if valence >= bond_orders:
            return max(valence - bond_orders, 0)
    return 0


def _hydrogens_agree(structure: Structure, formula: str) -> bool:
    try:
        published = parse_formula(formula)
    except ValueError:
        return False
    counted = structure.composition(range(len(structure.atoms)))
    return counted.get("H", 0) == published.get("H", 0)


def ring_bonds(structure: Structure) -> frozenset[int]:
    """Bonds whose removal leaves the molecule in one piece."""
    edges = _adjacency(structure)
    whole = len(_reachable(structure, 0, (), edges))
    on_ring = set()
    for index in range(len(structure.bonds)):
        if len(_reachable(structure, structure.bonds[index].a,
                          (index,), edges)) == whole:
            on_ring.add(index)
    return frozenset(on_ring)


def _adjacency(structure: Structure) -> list[list[tuple[int, int]]]:
    """For each atom, its (neighbour, bond index) pairs — built once."""
    edges: list[list[tuple[int, int]]] = [[] for _ in structure.atoms]
    for index, bond in enumerate(structure.bonds):
        edges[bond.a].append((bond.b, index))
        edges[bond.b].append((bond.a, index))
    return edges


def _reachable(structure: Structure, start: int, skip,
               edges: list[list[tuple[int, int]]] | None = None) -> set[int]:
    if edges is None:
        edges = _adjacency(structure)
    seen = {start}
    stack = [start]
    while stack:
        atom = stack.pop()
        for neighbour, bond in edges[atom]:
            if bond in skip or neighbour in seen:
                continue
            seen.add(neighbour)
            stack.append(neighbour)
    return seen


# --------------------------------------------------------------------------- #
# cleavage
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fragment:
    """One piece a set of bond cleavages would leave behind."""

    atoms: frozenset[int]
    formula: str
    mass: float                      # neutral, as drawn, before any H transfer
    cuts: tuple[int, ...]            # indices into Structure.bonds

    @property
    def cut_count(self) -> int:
        return len(self.cuts)

    def mz(self, charge: int = 1, hydrogens: int = 0) -> float:
        """
        Where the piece would appear, after gaining or losing hydrogens.

        A homolytic count is never what a spectrum shows: the bond that broke
        took a hydrogen with it or left one behind, so the mass worth looking
        for is this one shifted by a proton or two.
        """
        mass = self.mass + hydrogens * _HYDROGEN
        if charge == 0:
            return mass
        return (mass - charge * ELECTRON_MASS) / abs(charge)


_HYDROGEN = monoisotopic_mass({"H": 1})


@dataclass(frozen=True)
class PredictedIon:
    """A piece, the hydrogens it took or left, and what it then shed."""

    fragment: Fragment
    mz: float
    charge: int
    hydrogens: int
    losses: tuple[str, ...] = ()
    #: other routes that reach the same mass, described the same way
    alternatives: tuple[str, ...] = ()
    #: deuterium labels this piece is assumed to carry, when the structure
    #: was drawn unlabelled and the labels' positions are not known
    labels: int = 0
    #: the element whose cation carries the charge, when it is not a proton.
    #: A sodiated fragment is the neutral piece plus Na+, not the piece plus
    #: a hydrogen, and the two are 21.98 apart.
    carrier: str = ""
    #: the ion written as a form of the precursor — `[M+NH4]+`,
    #: `[M+H]+ (-NH3)`, `[M+H-3H2O]+` — for the ions that are one. A piece
    #: is not: it is written as what is left and how it got there, which is
    #: the only description a cleavage has. Set, this replaces that.
    form: str = ""

    @property
    def formula(self) -> str:
        return self.fragment.formula

    @property
    def description(self) -> str:
        if self.form:
            parts = [self.form]
        else:
            parts = [self.fragment.formula]
            if self.hydrogens:
                parts.append(f"{self.hydrogens:+d}H")
            parts.extend(f"-{loss}" for loss in self.losses)
            if self.carrier:
                parts.append(f"+{self.carrier}")
        if self.labels:
            parts.append(f"+{self.labels}D")
        return " ".join(parts)

    @property
    def simplicity(self) -> tuple[int, int, int]:
        """How little has to be assumed: fewer cuts, losses and H moved."""
        return (self.fragment.cut_count, len(self.losses), abs(self.hydrogens))


def predict(structure: Structure, charge: int = 1, max_cuts: int = MAX_CUTS,
            hydrogen_shifts: tuple[int, ...] = (-2, -1, 0, 1, 2),
            max_losses: int = 2, min_mz: float = 50.0,
            carrier: str = "") -> list[PredictedIon]:
    """
    Masses worth looking for, from cleavages plus small neutral losses.

    Where two routes reach the same mass the simpler one is kept, because the
    list is read to decide what to extract, not to enumerate mechanisms. This
    says nothing about which cleavages are likely — confirm against a measured
    product spectrum.

    The charge is a proton by default and the hydrogen shifts are what carry
    it: a piece written `+1H` is the protonated piece, one written `-1H` in
    negative mode the deprotonated one. `carrier` names an element whose
    cation carries it instead — `Na`, `K` — for a metal adduct, whose pieces
    keep the metal rather than a proton; the hydrogen shifts then say only
    what the cleavage itself moved.
    """
    losses = _loss_combinations(max_losses)
    # the composition each combination takes away, worked out once: doing it
    # per candidate meant parsing "H2O" a hundred thousand times
    taken = {combination: _combined_loss(combination) for combination in losses}
    needs = {combination: _required_groups(combination)
             for combination in losses}
    added = monoisotopic_mass({carrier: 1}) if carrier else 0.0
    routes: dict[int, list[PredictedIon]] = {}
    for fragment in fragments(structure, max_cuts):
        counts = parse_formula(fragment.formula)
        groups = structure.functional_groups(fragment.atoms)
        for combination in losses:
            if any(groups.get(group, 0) < number
                   for group, number in needs[combination].items()):
                continue
            for shift in hydrogen_shifts:
                remainder = _after_losses(counts, shift, taken[combination])
                if remainder is None:
                    continue
                mass = monoisotopic_mass(remainder) + added
                mz = (mass - charge * ELECTRON_MASS) / abs(charge or 1)
                if mz < min_mz:
                    continue
                routes.setdefault(round(mz, 4), []).append(
                    PredictedIon(fragment=fragment, mz=mz, charge=charge,
                                 hydrogens=shift, losses=combination,
                                 carrier=carrier))

    out: list[PredictedIon] = []
    for candidates in routes.values():
        candidates.sort(key=lambda i: i.simplicity)
        head = candidates[0]
        # the runners-up are kept rather than dropped: two routes to one mass
        # are a question for the spectrum, and collapsing them hides it
        # the same route reached by symmetric cuts is one route, not two
        others = tuple(name for name in
                       dict.fromkeys(i.description for i in candidates[1:])
                       if name != head.description)
        out.append(PredictedIon(
            fragment=head.fragment, mz=head.mz, charge=head.charge,
            hydrogens=head.hydrogens, losses=head.losses, alternatives=others,
            carrier=head.carrier))
    return sorted(out, key=lambda i: i.mz)


def _required_groups(losses: tuple[str, ...]) -> dict[str, int]:
    """How many of each functional group a combination of losses needs."""
    needed: dict[str, int] = {}
    for loss in losses:
        group = LOSS_REQUIRES.get(loss)
        if group:
            needed[group] = needed.get(group, 0) + 1
    return needed


def _loss_combinations(most: int) -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = [()]
    names = list(NEUTRAL_LOSSES)
    for size in range(1, most + 1):
        out.extend(combinations_with_replacement(names, size))
    return out


def _combined_loss(losses: tuple[str, ...]) -> dict[str, int]:
    total: dict[str, int] = {}
    for loss in losses:
        for element, number in parse_formula(NEUTRAL_LOSSES[loss]).items():
            total[element] = total.get(element, 0) + number
    return total


def _after_losses(counts: dict[str, int], hydrogens: int,
                  taken: dict[str, int]) -> dict[str, int] | None:
    """The composition left over, or None when a piece has nothing to lose."""
    left = dict(counts)
    left["H"] = left.get("H", 0) + hydrogens
    for element, number in taken.items():
        left[element] = left.get(element, 0) - number
    remaining = {}
    for element, number in left.items():
        if number < 0:
            return None
        if number:
            remaining[element] = number
    return remaining or None


def fragments(structure: Structure, max_cuts: int = MAX_CUTS,
              min_atoms: int = 2) -> list[Fragment]:
    """
    Every piece one or two bond cleavages would leave, largest first.

    One cut splits a chain; a ring stays whole until two of its bonds go, which
    is why a steroid needs pairs. Pieces are deduplicated by the atoms they
    contain, so the same fragment reached by different cuts is listed once,
    keeping the fewest cuts that produce it.
    """
    if not structure.bonds:
        return []
    best: dict[frozenset[int], Fragment] = {}

    def record(atoms: set[int], cuts: tuple[int, ...]) -> None:
        if len(atoms) < min_atoms:
            return
        key = frozenset(atoms)
        previous = best.get(key)
        if previous is not None and previous.cut_count <= len(cuts):
            return
        counts = structure.composition(key)
        best[key] = Fragment(atoms=key, formula=format_formula(counts),
                             mass=monoisotopic_mass(counts), cuts=cuts)

    edges = _adjacency(structure)

    # the molecule itself, cut nowhere: the losses a precursor sheds on its own
    # are ions in every spectrum, and a bile acid is mostly seen that way
    record(set(range(len(structure.atoms))), ())

    for index in range(len(structure.bonds)):
        _split(structure, (index,), record, edges)

    if max_cuts >= 2:
        # every pair, not only ring bonds: a piece in the middle of a chain is
        # held at both ends, so two cuts free it with no ring in sight
        for pair in combinations(range(len(structure.bonds)), 2):
            _split(structure, pair, record, edges)

    return sorted(best.values(), key=lambda f: (-len(f.atoms), f.mass))


def _split(structure: Structure, cuts: tuple[int, ...], record,
           edges: list[list[tuple[int, int]]] | None = None) -> None:
    skip = frozenset(cuts)
    remaining = set(range(len(structure.atoms)))
    while remaining:
        start = next(iter(remaining))
        piece = _reachable(structure, start, skip, edges)
        remaining -= piece
        record(piece, cuts)
