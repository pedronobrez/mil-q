"""
`milq peptide …`: the headless peptide toolkit (`peptides.py`) on the
command line, with the contract's conventions (`mil-cli/1` envelope,
JSON or TSV, the same exit codes).

    milq peptide mass SEQ [--charges 1-4]
    milq peptide fragments SEQ [--charges 1-3]
    milq peptide annotate SPECTRUM.(tsv|msp|json) --seq SEQ --charge Z [--tol-ppm 20]
    milq peptide annotate --from FILE --source gated:MZ --rt A:B --seq SEQ --charge Z
    milq peptide digest FASTA --proteins ACC,… --nonspecific [--len 4:40]
             [--mods pyroglu-q,phospho-st,ox-m] [--max-mods 3] [--charges 1-4]
    milq peptide screen FILES… --fasta F --proteins ACC,… [digest options]
             [--ppm 15] [--fragment-ppm 20] [--decoy reverse] [--fdr 0.01] [--out PREFIX]
    milq peptide components SCREEN.tsv --out COMPONENTS.csv [--fdr 0.01]
"""

from __future__ import annotations

import csv
import json
import os

from .contract import ContractError

SUBCOMMANDS = ("mass", "fragments", "annotate", "digest", "screen", "components")


def add_parser(sub, common) -> None:
    p = sub.add_parser("peptide", help="peptide masses, fragments, annotation, screening")
    p.add_argument("peptide_command", choices=SUBCOMMANDS)
    p.add_argument("items", nargs="*", help="a sequence, a spectrum, a FASTA or files")
    p.add_argument("--charges")
    p.add_argument("--seq")
    p.add_argument("--charge", type=int, default=2)
    p.add_argument("--tol-ppm", dest="tol_ppm", type=float, default=20.0)
    p.add_argument("--from", dest="from_")
    p.add_argument("--source")
    p.add_argument("--rt")
    p.add_argument("--centroid", default="local")
    p.add_argument("--fasta")
    p.add_argument("--proteins", default="")
    p.add_argument("--nonspecific", action="store_true")
    p.add_argument("--len", dest="length", default="4:40")
    p.add_argument("--mods", default="")
    p.add_argument("--max-mods", dest="max_mods", type=int, default=3)
    p.add_argument("--ppm", type=float, default=15.0)
    p.add_argument("--fragment-ppm", dest="fragment_ppm", type=float, default=20.0)
    p.add_argument("--decoy", default="reverse", choices=("reverse", "none"))
    p.add_argument("--fdr", type=float, default=0.01)
    p.add_argument("--min-matched", dest="min_matched", type=int, default=4)
    p.add_argument("--out")
    p.add_argument("--internal", action="store_true", default=True)
    common(p)


def _items(args) -> list[str]:
    items = args.get("items") or []
    return [items] if isinstance(items, str) else list(items)


def _length(text) -> tuple[int, int]:
    if isinstance(text, (list, tuple)):
        return int(text[0]), int(text[1])
    a, _, b = str(text or "4:40").partition(":")
    return int(a), int(b or a)


def _mods(text) -> list[str]:
    if isinstance(text, (list, tuple)):
        return [str(t) for t in text]
    return [t.strip() for t in str(text or "").split(",") if t.strip()]


def _proteins(args) -> list[str]:
    value = args.get("proteins") or ""
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [p.strip() for p in str(value).split(",") if p.strip()]


def run(command: str, args: dict):
    """(body, input) for one peptide subcommand."""
    from . import peptides as pep

    try:
        return _run(pep, command, args)
    except pep.PeptideError as exc:
        raise ContractError("bad_arguments", str(exc)) from exc
    except FileNotFoundError as exc:
        raise ContractError("file_unreadable", str(exc), 3) from exc


def _run(pep, command: str, args: dict):
    items = _items(args)
    if command == "mass":
        sequence = args.get("seq") or (items[0] if items else "")
        body = pep.mass(sequence, pep.parse_charges(args.get("charges") or "1-4"))
        body["table"] = "mz"
        return body, {"sequence": sequence}

    if command == "fragments":
        sequence = args.get("seq") or (items[0] if items else "")
        peptide = pep.parse(sequence)
        ions = pep.fragments(peptide, pep.parse_charges(args.get("charges") or "1-3"))
        return {"peptide": pep.format_peptide(peptide), "table": "ions",
                "ions": [{"name": i.name, "series": i.series, "index": i.index,
                          "charge": i.charge, "mz": round(float(i.mz), 6)}
                         for i in ions]}, {"sequence": sequence}

    if command == "annotate":
        sequence = args.get("seq")
        if not sequence:
            raise ContractError("bad_arguments", "give --seq")
        if args.get("from_") or args.get("from"):
            from .contract import spectrum

            source_file = args.get("from_") or args.get("from")
            doc, index = spectrum(source_file, args.get("source") or "ms1", None,
                                  args.get("rt"), (), args.get("centroid", "local"),
                                  None, 0.0)
            import numpy as np

            mz = np.array([p["mz"] for p in doc["peaks"]], dtype=float)
            height = np.array([p["intensity"] for p in doc["peaks"]], dtype=float)
            where = {"path": os.path.realpath(source_file), "sample": index,
                     "source": doc["source"], "rt": doc["rt_window"],
                     "scans_used": len(doc["scans_used"])}
        else:
            if not items:
                raise ContractError("bad_arguments", "give a spectrum file or --from")
            mz, height, _precursor = pep.read_spectrum_file(items[0])
            where = {"path": os.path.realpath(items[0])}
        found = pep.annotate(mz, height, sequence, int(args.get("charge") or 2),
                             float(args.get("tol_ppm") or 20.0))
        return {"peptide": found.peptide, "charge": found.charge,
                "tol_ppm": found.tol_ppm, "peaks": found.n_peaks,
                "coverage": found.coverage, "explained": found.explained,
                "matched": len(found.matches), "table": "matches",
                "matches": found.matches, "unexplained": found.unexplained}, where

    if command == "digest":
        fasta = args.get("fasta") or (items[0] if items else None)
        if not fasta:
            raise ContractError("bad_arguments", "give the FASTA")
        proteins = pep.read_fasta(fasta, _proteins(args))
        charges = pep.parse_charges(args.get("charges") or "1-4")
        made = pep.digest(proteins, True, _length(args.get("length")),
                          _mods(args.get("mods")), int(args.get("max_mods", 3)))
        rows = [{"peptide": str(c.peptide), "sequence": c.peptide.sequence,
                 "modifications": c.peptide.mod_text, "protein": c.protein,
                 "start": c.start, "end": c.end,
                 "mass": round(c.peptide.neutral_mass, 6),
                 **{f"mz_{z}": round(c.peptide.mz(z), 6) for z in charges}}
                for c in made]
        return {"proteins": sorted(proteins), "candidates": len(rows),
                "table": "rows", "rows": rows}, {"fasta": os.path.realpath(fasta)}

    if command == "screen":
        fasta = args.get("fasta")
        if not fasta:
            raise ContractError("bad_arguments", "give --fasta")
        files = items or args.get("files") or []
        if not files:
            raise ContractError("bad_arguments", "give the files to screen")
        expanded = []
        for path in files:
            path = os.path.expanduser(str(path))
            if os.path.isdir(path):
                expanded += [os.path.join(path, n) for n in sorted(os.listdir(path))
                             if n.lower().endswith((".wiff", ".mzml"))]
            else:
                expanded.append(path)
        proteins = pep.read_fasta(fasta, _proteins(args))
        fdr = float(args.get("fdr") or 0.01)
        result = pep.screen(expanded, proteins, _length(args.get("length")),
                            _mods(args.get("mods")), int(args.get("max_mods", 3)),
                            pep.parse_charges(args.get("charges") or "1-4"),
                            float(args.get("ppm") or 15.0),
                            float(args.get("fragment_ppm") or 20.0),
                            args.get("decoy", "reverse") != "none", fdr=fdr,
                            min_matched=int(args.get("min_matched") or 4))
        rows = result.peptides()
        accepted = [r for r in rows if r["q_value"] <= fdr]
        prefix = args.get("out") or "peptide-screen"
        written = _write_screen(prefix, rows, result, fdr)
        decoys = sum(1 for p in result.psms if p.candidate.decoy)
        return {"spectra": result.spectra, "candidates": result.candidates,
                "psms": len(result.psms), "decoy_psms": decoys,
                "fdr": fdr, "accepted_psms": len(result.accepted),
                "accepted_peptides": len(accepted), "skipped": result.skipped,
                "outputs": written, "table": "rows", "rows": accepted}, {
                "paths": [os.path.realpath(p) for p in expanded],
                "fasta": os.path.realpath(fasta), "proteins": sorted(proteins)}

    if command == "components":
        source = items[0] if items else args.get("screen")
        if not source:
            raise ContractError("bad_arguments", "give the screen's TSV or JSON")
        rows = _read_rows(source)
        fdr = float(args.get("fdr") or 0.01)
        made = pep.components(rows, fdr)
        out = args.get("out") or os.path.splitext(source)[0] + ".components.csv"
        from .components import save_components

        out = os.path.abspath(os.path.expanduser(out))
        save_components(out, made)
        return {"components": len(made), "out": out, "table": "rows",
                "rows": [{"name": c.name, "precursor": c.precursor,
                          "fragment": c.fragment, "rt": c.rt, "adduct": c.adduct}
                         for c in made]}, {"path": os.path.realpath(source)}
    raise ContractError("bad_arguments", f"no peptide subcommand {command!r}")


def _write_screen(prefix: str, rows, result, fdr: float) -> dict:
    """The ranked TSV, the JSON summary and the MSP of accepted spectra."""
    from .library import entry_from_spectrum, write_msp
    from . import peptides as pep

    prefix = os.path.abspath(os.path.expanduser(str(prefix)))
    os.makedirs(os.path.dirname(prefix) or ".", exist_ok=True)
    tsv = prefix + ".tsv"
    columns = list(rows[0]) if rows else ["peptide"]
    with open(tsv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = prefix + ".json"
    with open(summary, "w", encoding="utf-8") as handle:
        json.dump({"spectra": result.spectra, "candidates": result.candidates,
                   "fdr": fdr, "peptides": rows}, handle, indent=1)
    entries = []
    best: dict = {}
    for psm in result.accepted:
        key = (str(psm.candidate.peptide), psm.charge)
        if key not in best or psm.hyperscore > best[key].hyperscore:
            best[key] = psm
    for (text, charge), psm in sorted(best.items()):
        entries.append(entry_from_spectrum(
            f"{text} {charge}+", psm.mz, psm.intensity,
            precursor=round(psm.candidate.peptide.mz(charge), 6),
            precursor_type=f"[M+{charge}H]{charge}+",
            comment=(f"milq peptide screen; {psm.candidate.protein} "
                     f"{psm.candidate.start}-{psm.candidate.end}; "
                     f"{os.path.basename(psm.path)} channel {psm.channel} "
                     f"scan {psm.scan} RT {psm.rt:.4f}; q {psm.q_value:.4g}; "
                     f"hyperscore {psm.hyperscore:.3f}")))
    msp = prefix + ".msp"
    if os.path.exists(msp):
        os.remove(msp)
    if entries:
        write_msp(entries, msp)
    del pep
    return {"tsv": tsv, "json": summary, "msp": msp if entries else None}


def _read_rows(path: str) -> list[dict]:
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        return doc.get("peptides") or doc.get("rows") or []
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))
