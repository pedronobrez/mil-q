"""
One question — *what is this spectrum?* — asked of every route at once.

`explain` has four ways of answering it and until now the analyst picked one
by hand: a LIPID MAPS record found at the precursor, a name looked up in the
standards table, a formula typed in, a drawing loaded off the disk. Picking
is the part nobody can do well. The routes do not answer the same question
with different confidence, they answer *different* questions — a drawing
enumerates cleavages, a formula enumerates only losses, a database record is
a drawing somebody else made — and which of them has anything to say about
the spectrum in front of you is not knowable until each has been asked.

So this asks all of them, with whatever inputs exist, and reports every
answer with its route beside it. `best` is the one that explains the most of
the spectrum, and where two explain the same the tie is broken by a stated
rule rather than by the order they happened to run in:

1. **the explained share**, which is what `explain` has always ranked by;
2. **a drawing beats a formula** at equal share, because a formula has no
   bonds to cut and reached that share with a shorter list of predictions —
   a route that offered more ways to be wrong and was not is better evidence;
3. **a database record whose precursor sits inside the written precision
   beats one outside**, which is `chemistry.identify_adduct`'s own gate and
   the same one `explain.adduct_gate` uses: an adduct that has to be named
   needs the mass to name it;
4. the order above, so the answer does not depend on a dictionary's.

Nothing is derived twice. The adduct identification — which is a survey
read, an isotope pattern scored and a list of adducts measured against the
written precursor — is done once per labelled formula and handed to every
route that asks for it, so a name and a formula that come to the same
composition cost one identification and not two. The database route needs
none: `rank_candidates` carries each candidate's own adduct and its own
gate.

What this does **not** do is decide anything. Every route that produced an
answer stays in the list with its share, its ions found of ions predicted,
and how far the written precursor sits from it; the caller shows all of
them. A best-of that hid the rest would be exactly the machinery this
program spends its docstrings arguing against — several candidates usually
explain the same peaks, and the ones a route leaves unexplained are the
honest half of the answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .explain import (TOLERANCE_PPM, Explanation, adduct_gate, explain_formula,
                      explain_structure, rank_candidates, resolve_name,
                      significant_peaks)

#: a compound written by name — the standards table, then LIPID MAPS, then
#: the lipid shorthand, which is `explain.resolve_name`
ROUTE_NAME = "name"
#: every curated structure the precursor could be, at every adduct the
#: polarity allows
ROUTE_DATABASE = "LIPID MAPS"
#: a formula and its neutral losses, which is all a formula can say
ROUTE_FORMULA = "formula"
#: a drawing of one's own: cleavages as well as losses
ROUTE_DRAWING = "drawing"

#: the order the routes are asked in, which is also the order they are listed
#: and the last tie-break. Name first because it is the one that can bring a
#: drawing *and* a label count with it from three sources at once.
ROUTES = (ROUTE_NAME, ROUTE_DATABASE, ROUTE_FORMULA, ROUTE_DRAWING)

#: how many bonds a structure route may cut, and how many neutral losses it
#: may take, for **every** structure route including the database one.
#:
#: They are shared on purpose. The share is a fraction of the same spectrum
#: either way, so two routes enumerated to different limits cannot be put in
#: one table and ranked: the one allowed two cuts would win a comparison it
#: was handed. Two cuts because a steroid cut once is still in one piece,
#: three losses because a trihydroxy bile acid sheds three waters and the
#: three-water ion is its base peak.
MAX_CUTS = 2
MAX_LOSSES = 3


@dataclass(frozen=True)
class RouteResult:
    """What one route made of the spectrum."""

    route: str
    explanation: Explanation
    #: the sentence naming the route, for the line under the table
    basis: str
    #: why this precursor is this adduct, from `chemistry`, where a route had
    #: to work the adduct out. Empty for the database route, whose candidates
    #: each carry their own and say so per row.
    reason: str = ""
    #: was this enumerated from a structure? The second tie-break.
    drawn: bool = False
    #: does the written precursor sit inside the precision it was written
    #: with? The third. False where nothing was measured against it.
    inside: bool = False
    #: where the route resolved its subject, in words, for a tooltip
    source: str = ""
    #: every candidate this route produced, best first. One for all but the
    #: database route, which answers with the whole ranked list.
    ranked: tuple[Explanation, ...] = ()

    @property
    def adduct(self) -> str:
        return self.explanation.adduct

    @property
    def share(self) -> float:
        return self.explanation.share

    @property
    def matched(self) -> int:
        return self.explanation.matched

    @property
    def predicted(self) -> int:
        return self.explanation.predicted

    @property
    def precursor_ppm(self) -> float | None:
        return self.explanation.precursor_ppm

    @property
    def name(self) -> str:
        return self.explanation.name

    @property
    def ions(self) -> str:
        """`n of m`, the count with the thing it is a share of."""
        return f"{self.matched} of {self.predicted}"


@dataclass(frozen=True)
class Skipped:
    """A route that was not run, and why — which is part of the answer."""

    route: str
    why: str


@dataclass
class AnyExplanation:
    """Every route's answer, and which of them explains the most."""

    precursor: float | None = None
    polarity: str = ""
    results: list[RouteResult] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    #: peaks above the noise share that were there to be explained
    considered: int = 0
    #: what the survey said about each candidate adduct, where one was read —
    #: `chemistry.adduct_evidence`, for the caller's provenance line. Empty
    #: when no survey was handed over, which is not the same as a survey that
    #: showed nothing.
    evidence: tuple = ()

    @property
    def best(self) -> RouteResult | None:
        return self.results[0] if self.results else None

    @property
    def others(self) -> list[RouteResult]:
        return self.results[1:]

    def result(self, route: str) -> RouteResult | None:
        return next((r for r in self.results if r.route == route), None)

    def why_skipped(self, route: str) -> str:
        return next((s.why for s in self.skipped if s.route == route), "")

    @property
    def summary(self) -> str:
        """The answer in one line, naming the route that gave it."""
        best = self.best
        if best is None:
            return "Nothing could be explained: " + "; ".join(
                f"{s.route} — {s.why}" for s in self.skipped)
        close = [r for r in self.others if best.share - r.share < 0.05]
        tie = (f" {len(close)} other route(s) explain it about as well."
               if close else "")
        return (f"{best.name}: {best.share * 100:.1f}% of the spectrum "
                f"{best.basis}; {best.ions} predicted ion(s) matched."
                + tie)


# --------------------------------------------------------------------------- #
# the adduct, identified once
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Choice:
    """One adduct identification, kept so no route asks for it twice."""

    adduct: object | None
    reason: str
    ppm: float | None = None
    inside: bool = False
    evidence: tuple = ()


class _Adducts:
    """
    `chemistry.identify_adduct`, memoised on the labelled formula.

    Which adduct a written precursor is depends on the composition and on
    nothing else about the route that proposed it, so a name and a formula
    that come to `C24H36D4O5` are one question asked once — including the
    survey read and the isotope pattern scored, which are the expensive part.
    """

    def __init__(self, precursor: float | None, polarity: str, survey) -> None:
        self.precursor = precursor
        self.polarity = polarity or None
        self.survey = survey
        self._seen: dict[str, _Choice] = {}
        #: what the survey said, for the caller's provenance line
        self.evidence: tuple = ()

    def labelled(self, formula: str, deuterium: int) -> str:
        """The formula with the labels the name declares folded into it."""
        from .chemistry import format_formula, parse_formula

        counts = dict(parse_formula(formula))
        if deuterium:
            counts["D"] = counts.get("D", 0) + deuterium
            counts["H"] = counts.get("H", 0) - deuterium
        return format_formula(counts)

    def choose(self, formula: str, deuterium: int = 0) -> _Choice:
        from .chemistry import identify_adduct

        if self.precursor is None:
            return _Choice(None, "no precursor is written, so nothing says "
                                 "which adduct to score this as")
        key = self.labelled(formula, deuterium)
        found = self._seen.get(key)
        if found is not None:
            return found
        choice = identify_adduct(key, self.precursor, self.polarity,
                                 survey=self.survey)
        ppm, inside = None, False
        if choice.adduct is not None:
            match = next((m for m in choice.matches
                          if m.name == choice.adduct.name), None)
            if match is not None:
                ppm, inside = match.error_ppm, match.within
        made = _Choice(choice.adduct, choice.reason, ppm, inside,
                       tuple(choice.evidence))
        if choice.evidence:
            self.evidence = tuple(choice.evidence)
        self._seen[key] = made
        return made


def _declared_labels(deuterium: int, name: str, formula: str) -> int:
    """
    How many labels this subject carries that nothing has placed.

    Given outright it is taken as given. Otherwise it is read off the name,
    which is the only place a component table has for it — a d4 standard is
    bought, named and filed as `CA-d4` and the formula beside it is the
    unlabelled one, and without this the arithmetic is out by 4.025 Da and no
    adduct fits the written precursor at all. The rule is
    `infusion_report.labelled_formula`'s: a formula that already spells its
    labels out has said what it is.

    It is asked **per route**, not once for the spectrum, and that is the
    point. PubChem's cholic acid-d4 places its four in an `M  ISO` block, so
    the drawing route needs none while the `C24H40O5` in the component table
    beside it needs all four; a single count for the whole call skipped the
    formula route on every real CA-d4 file, with the true statement that
    430.35 is no adduct of the unlabelled molecule.
    """
    from .chemistry import FormulaError, parse_formula, split_labels

    if deuterium:
        return int(deuterium)
    _stem, declared = split_labels(str(name or ""))
    if not declared:
        return 0
    if not formula:
        return declared
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return 0
    if counts.get("D") or counts.get("H", 0) < declared:
        return 0
    return declared


def _inside_written(precursor: float | None, ppm: float | None) -> bool:
    """
    Does a candidate found at `ppm` sit inside the precision the precursor
    was written with?

    The same gate `explain.adduct_gate` applies to a database candidate found
    at an adduct other than the proton one, read back out of the ppm the row
    carries so that the database route and the routes that identify their own
    adduct are judged by one rule.
    """
    if precursor is None or ppm is None:
        return False
    theoretical = float(precursor) / (1.0 + ppm / 1e6)
    return abs(float(precursor) - theoretical) <= adduct_gate(float(precursor))


# --------------------------------------------------------------------------- #
# the routes
# --------------------------------------------------------------------------- #
def explain_any(peaks_mz, peaks_intensity, precursor: float | None,
                polarity: str = "", *, name: str = "", formula: str = "",
                molecule=None, deuterium: int = 0, survey=None,
                database=None, tolerance_ppm: float = TOLERANCE_PPM,
                max_cuts: int = MAX_CUTS, max_losses: int = MAX_LOSSES,
                limit: int = 12) -> AnyExplanation:
    """
    Every route this program has, run on one spectrum, best first.

    Only where the inputs exist: a route with nothing to work from is not a
    failure and is not run, it is listed in `skipped` with the sentence that
    says what it wanted. A panel with an empty Name box and no database
    installed should say those two things, not raise.

    `database` is a `LipidDatabase` or None; None asks for the installed one
    and, where there is none, skips the database route and looks a name up in
    the standards table and the shorthand alone.
    """
    from . import lipidmaps
    from .chemistry import FormulaError
    from .explain import placed_labels
    from .matching import PRECURSOR_MATCH_DA

    out = AnyExplanation(precursor=precursor, polarity=str(polarity or ""))
    typed = str(formula or "").strip()
    written = str(name or "").strip()
    peaks = significant_peaks(peaks_mz, peaks_intensity)
    out.considered = len(peaks)
    if not peaks:
        out.skipped = [Skipped(route, "there is no peak above the noise share "
                                      "to explain") for route in ROUTES]
        return out
    if database is None:
        database = lipidmaps.database()
    adducts = _Adducts(precursor, out.polarity, survey)
    results: list[RouteResult] = []
    skipped: list[Skipped] = []
    # what a formula-only enumeration has already been run on, so that a name
    # that resolved to a formula and a formula typed by hand — the ordinary
    # case, since the component table carries both — are not the same list of
    # ions scored twice under two headings
    flat: set[str] = set()

    def structure_result(route, molecule, name_text, choice, labels, basis,
                         source=""):
        explanation = explain_structure(
            molecule, peaks, name=name_text, adduct=choice.adduct,
            deuterium=labels, max_cuts=max_cuts, max_losses=max_losses,
            tolerance_ppm=tolerance_ppm)
        # the ppm belongs on the row: a drawing scored as an adduct that is
        # 30 ppm from the written precursor is a different claim from one at 2
        explanation.precursor_ppm = choice.ppm
        return RouteResult(route=route, explanation=explanation, basis=basis,
                           reason=choice.reason, drawn=True,
                           inside=choice.inside, source=source,
                           ranked=(explanation,))

    def formula_result(route, formula_text, name_text, choice, labels, basis,
                       source=""):
        explanation = explain_formula(
            formula_text, choice.adduct.name, peaks, name=name_text,
            deuterium=labels, tolerance_ppm=tolerance_ppm,
            max_losses=max_losses)
        explanation.precursor_ppm = choice.ppm
        return RouteResult(route=route, explanation=explanation, basis=basis,
                           reason=choice.reason, drawn=False,
                           inside=choice.inside, source=source,
                           ranked=(explanation,))

    # -- the name ---------------------------------------------------------- #
    if not written:
        skipped.append(Skipped(ROUTE_NAME, "no name was given"))
    else:
        resolved = resolve_name(written, database=database,
                                use_installed=False)
        if resolved is None:
            skipped.append(Skipped(
                ROUTE_NAME, f"“{written}” is not in the standards "
                            f"table, in LIPID MAPS or in the lipid shorthand"))
        else:
            labels = _declared_labels(deuterium or resolved.labels,
                                      written, resolved.formula)
            try:
                choice = adducts.choose(resolved.formula, labels)
            except (FormulaError, ValueError):
                choice = _Choice(None, f"“{resolved.formula}” is not "
                                       f"a formula this can read")
            if choice.adduct is None:
                skipped.append(Skipped(ROUTE_NAME, choice.reason))
            else:
                drawing = resolved.molecule()
                lm_id = getattr(resolved.record, "lm_id", "") or ""
                target = lm_id or resolved.formula
                where = ("" if lm_id else f" ({resolved.source})")
                basis = (f"from the name {written} → {target}{where} "
                         f"as {choice.adduct.name}")
                source = resolved.source + (f", drawn as {lm_id}"
                                            if drawing is not None and lm_id
                                            else "")
                if drawing is not None:
                    results.append(structure_result(
                        ROUTE_NAME, drawing, written, choice, labels, basis,
                        source))
                else:
                    flat.add(adducts.labelled(resolved.formula, labels))
                    results.append(formula_result(
                        ROUTE_NAME, resolved.formula, written, choice, labels,
                        basis, source))

    # -- the database ------------------------------------------------------ #
    if database is None:
        skipped.append(Skipped(ROUTE_DATABASE,
                               "the LIPID MAPS database is not installed"))
    elif precursor is None:
        skipped.append(Skipped(ROUTE_DATABASE,
                               "no precursor is written to look up"))
    else:
        ranked = rank_candidates(database, float(precursor), peaks,
                                 adduct=None, tolerance=PRECURSOR_MATCH_DA,
                                 unit="Da", max_cuts=max_cuts,
                                 max_losses=max_losses, limit=limit,
                                 polarity=out.polarity or None)
        if not ranked:
            skipped.append(Skipped(
                ROUTE_DATABASE,
                f"no curated structure sits within ±"
                f"{PRECURSOR_MATCH_DA:g} Da of {float(precursor):.4f} at any "
                f"adduct of this polarity"))
        else:
            top = ranked[0]
            results.append(RouteResult(
                route=ROUTE_DATABASE, explanation=top,
                basis=(f"from LIPID MAPS at {float(precursor):g} → "
                       f"{top.record.lm_id or top.name} as {top.adduct}"),
                drawn=True,
                inside=_inside_written(precursor, top.precursor_ppm),
                source=f"{len(ranked)} candidate(s) at that precursor",
                ranked=tuple(ranked)))

    # -- the formula ------------------------------------------------------- #
    if not typed:
        skipped.append(Skipped(ROUTE_FORMULA, "no formula was given"))
    else:
        labels = _declared_labels(deuterium, written, typed)
        try:
            choice = adducts.choose(typed, labels)
            key = adducts.labelled(typed, labels)
        except (FormulaError, ValueError):
            choice, key = _Choice(None, f"“{typed}” is not a formula "
                                        f"this can read"), ""
        if choice.adduct is None:
            skipped.append(Skipped(ROUTE_FORMULA, choice.reason))
        elif key in flat:
            skipped.append(Skipped(
                ROUTE_FORMULA, f"{key} is what the name already resolved to, "
                               f"and a formula has one enumeration"))
        else:
            flat.add(key)
            results.append(formula_result(
                ROUTE_FORMULA, typed, written or typed, choice, labels,
                f"from the formula {typed} as {choice.adduct.name} and its "
                f"neutral losses — a formula has no bonds to cut"))

    # -- the drawing ------------------------------------------------------- #
    if molecule is None:
        skipped.append(Skipped(ROUTE_DRAWING, "no structure was loaded"))
    else:
        # a drawing that places its own labels needs none added: the
        # cleavages come out with the right masses by themselves, and adding
        # four more would put every fragment 4.025 Da past the spectrum
        labels = (0 if placed_labels(molecule)
                  else _declared_labels(deuterium, written, molecule.formula))
        try:
            choice = adducts.choose(molecule.formula, labels)
        except (FormulaError, ValueError):
            choice = _Choice(None, f"“{molecule.formula}” is not a "
                                   f"formula this can read")
        if choice.adduct is None:
            skipped.append(Skipped(ROUTE_DRAWING, choice.reason))
        else:
            results.append(structure_result(
                ROUTE_DRAWING, molecule, written or molecule.formula, choice,
                labels,
                f"from the drawing {molecule.formula} as {choice.adduct.name}"))

    results.sort(key=_rank)
    out.results = results
    out.skipped = skipped
    out.evidence = adducts.evidence
    return out


def _rank(result: RouteResult) -> tuple:
    """
    The share, then the stated tie rules, then the order the routes are in.

    Rounded to a tenth of a per cent before the tie rules are reached,
    because two routes that predict the same ion at the same mass explain the
    same peaks and differ in the last bits of a float — and a tie rule that
    never fires is not a rule.
    """
    return (-round(result.share, 4),
            0 if result.drawn else 1,
            0 if result.inside else 1,
            ROUTES.index(result.route))
