"""
`milq <subcommand>`: the suite's command-line contract (`docs/CLI-CONTRACT.md`).

    milq selftest [FILES...]
    milq info FILE [--sample N|NAME]
    milq scans FILE [--source S] [--rt A:B] [--parent MZ[:TOL]] [--ms-level N] [--count]
    milq xic FILE --mz LIST [--tol 0.01] [--unit Da|ppm] [--source S] [--rt A:B]
             [--smooth N] [--summary|--trace] [--reference MZ@SOURCE]
    milq spectrum FILE [--source S] (--scan N | --rt A:B) [--subtract A:B]...
             [--centroid vendor|local|none] [--top N] [--min-rel 0.01] [--msp PATH]
    milq isotopes FILE --mz MZ [--charge Z] --rt A:B [--formula F]
    milq batch-xic PATHS... --mz LIST [--tol] [--unit] [--source] [--rt-window C±W]
    milq convert FILE [--out PATH] [--centroid vendor|local]
    milq serve (--stdio | --inbox DIR) [--allow-root DIR]... [--max-jobs 1] [--idle-exit MIN]
    milq peptide ...                    (see `milq peptide --help`)

Without a subcommand `milq` is the application (the window, `--selftest`,
`--digest`, `--infusion-report`), as it always was. Nothing on these paths
imports Qt: they run over SSH and in a VM with no display.

Output is one JSON document on stdout (or a TSV table with `--format tsv`),
diagnostics on stderr (none with `--quiet`), errors as JSON on stderr with
the contract's exit codes: 2 bad arguments, 3 unreadable file or missing
`.wiff.scan`, 4 nothing found (only with `--require`), 5 internal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SUBCOMMANDS = ("selftest", "info", "scans", "xic", "spectrum", "isotopes",
               "batch-xic", "convert", "serve", "peptide")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        from .contract import ContractError

        raise ContractError("bad_arguments", message)


def _common(p) -> None:
    p.add_argument("--format", choices=("json", "tsv"), default="json")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--cache", default=None, help="sidecar index directory")
    p.add_argument("--require", action="store_true",
                   help="exit 4 when nothing is found")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="milq", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    p = sub.add_parser("selftest")
    p.add_argument("files", nargs="*")
    _common(p)

    p = sub.add_parser("info")
    p.add_argument("file")
    p.add_argument("--sample")
    _common(p)

    p = sub.add_parser("scans")
    p.add_argument("file")
    p.add_argument("--sample")
    p.add_argument("--source")
    p.add_argument("--rt")
    p.add_argument("--parent")
    p.add_argument("--ms-level", dest="ms_level")
    p.add_argument("--count", action="store_true")
    _common(p)

    p = sub.add_parser("xic")
    p.add_argument("file")
    p.add_argument("--sample")
    p.add_argument("--mz", required=True, nargs="+")
    p.add_argument("--tol", type=float, default=0.01)
    p.add_argument("--unit", default="Da")
    p.add_argument("--source", default="ms1")
    p.add_argument("--rt")
    p.add_argument("--smooth", type=float, default=0.0)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--trace", action="store_true")
    p.add_argument("--reference")
    _common(p)

    p = sub.add_parser("spectrum")
    p.add_argument("file")
    p.add_argument("--sample")
    p.add_argument("--source", default="ms1")
    p.add_argument("--scan", type=int)
    p.add_argument("--rt")
    p.add_argument("--subtract", action="append", default=[])
    p.add_argument("--centroid", default="local")
    p.add_argument("--top", type=int)
    p.add_argument("--min-rel", dest="min_rel", type=float, default=0.01)
    p.add_argument("--msp")
    _common(p)

    p = sub.add_parser("isotopes")
    p.add_argument("file")
    p.add_argument("--sample")
    p.add_argument("--mz", type=float, required=True)
    p.add_argument("--charge", type=int, default=1)
    p.add_argument("--rt", required=True)
    p.add_argument("--formula", default="")
    p.add_argument("--adduct", default="")
    p.add_argument("--tol", type=float, default=0.01)
    p.add_argument("--source", default="ms1")
    _common(p)

    p = sub.add_parser("batch-xic")
    p.add_argument("paths", nargs="+")
    p.add_argument("--mz", required=True, nargs="+")
    p.add_argument("--tol", type=float, default=0.01)
    p.add_argument("--unit", default="Da")
    p.add_argument("--source", default="ms1")
    p.add_argument("--rt")
    p.add_argument("--rt-window", dest="rt_window")
    p.add_argument("--smooth", type=float, default=0.0)
    _common(p)

    p = sub.add_parser("convert")
    p.add_argument("file")
    p.add_argument("--sample")
    p.add_argument("--out")
    p.add_argument("--centroid", choices=("vendor", "local"))
    _common(p)

    p = sub.add_parser("serve")
    how = p.add_mutually_exclusive_group(required=True)
    how.add_argument("--stdio", action="store_true")
    how.add_argument("--inbox")
    p.add_argument("--allow-root", dest="allow_root", action="append", default=[])
    p.add_argument("--max-jobs", dest="max_jobs", type=int, default=1)
    p.add_argument("--idle-exit", dest="idle_exit", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=1800.0)
    _common(p)

    from .peptides_cli import add_parser as add_peptide

    add_peptide(sub, _common)
    return parser


# --------------------------------------------------------------------------- #
def envelope(command: str, input_: dict, body: dict) -> dict:
    from . import __version__
    from .contract import SCHEMA, TOOL

    return {"schema": SCHEMA, "tool": TOOL, "version": __version__,
            "command": command, "input": input_, **body}


def run(command: str, args: dict) -> dict:
    """
    One subcommand, its arguments by the CLI's flag names without dashes,
    to a whole document. What `serve` calls for every request.
    """
    from . import contract
    from .contract import ContractError, input_block

    args = _checked_args(command, dict(args or {}))
    if args.get("cache"):
        from . import sidecar

        sidecar.configure(args["cache"])

    def get(name, default=None):
        value = args.get(name, default)
        return default if value is None else value

    if command == "selftest":
        files = get("files", [])
        return envelope(command, {"paths": [os.path.realpath(f) for f in files]},
                        contract.selftest(files))
    if command == "info":
        body, index = contract.info(args["file"], get("sample"))
        return envelope(command, input_block(args["file"], index), body)
    if command == "scans":
        body, index = contract.scans(args["file"], get("sample"), get("source"),
                                     get("rt"), get("parent"), get("ms_level"),
                                     bool(get("count", False)), get("cache"))
        return envelope(command, input_block(args["file"], index), body)
    if command == "xic":
        body, index = contract.xic(args["file"], args["mz"], float(get("tol", 0.01)),
                                   get("unit", "Da"), get("source", "ms1"),
                                   get("rt"), float(get("smooth", 0.0)),
                                   bool(get("trace", False)), get("reference"),
                                   get("sample"), bool(get("require", False)))
        return envelope(command, input_block(args["file"], index), body)
    if command == "spectrum":
        body, index = contract.spectrum(args["file"], get("source", "ms1"),
                                        get("scan"), get("rt"), get("subtract", []),
                                        get("centroid", "local"), get("top"),
                                        float(get("min_rel", 0.01)), get("msp"),
                                        get("sample"), require=bool(get("require", False)))
        return envelope(command, input_block(args["file"], index), body)
    if command == "isotopes":
        body, index = contract.isotopes(args["file"], float(args["mz"]),
                                        int(get("charge", 1)), args.get("rt"),
                                        get("formula", ""), float(get("tol", 0.01)),
                                        source=get("source", "ms1"),
                                        sample=get("sample"), adduct=get("adduct", ""))
        return envelope(command, input_block(args["file"], index), body)
    if command == "batch-xic":
        paths = args.get("paths") or []
        body = contract.batch_xic(paths, args["mz"], float(get("tol", 0.01)),
                                  get("unit", "Da"), get("source", "ms1"),
                                  get("rt"), get("rt_window"),
                                  float(get("smooth", 0.0)))
        if bool(get("require", False)) and not any(r["found"] for r in body["rows"]):
            raise ContractError("nothing_found", "no signal in any file", 4)
        return envelope(command, {"paths": [os.path.realpath(os.path.expanduser(p))
                                            for p in paths]}, body)
    if command == "convert":
        body, index = contract.convert(args["file"], get("out"), get("centroid"),
                                       get("sample"))
        return envelope(command, input_block(args["file"], index), body)
    if command == "peptide":
        from .peptides_cli import run as run_peptide

        sub = args.get("peptide_command") or args.get("subcommand")
        body, input_ = run_peptide(sub, args)
        return envelope(f"peptide {sub}", input_, body)
    raise ContractError("not_allowed", f"no subcommand {command!r}")


#: other names a request may use for a subcommand's input, as MIL-X accepts
#: them; anything else unknown is refused rather than dropped
_ALIASES = {"batch-xic": {"files": "paths", "file": "paths", "path": "paths"},
            "selftest": {"paths": "files", "file": "files"}}
_SINGLE_FILE = ("info", "scans", "xic", "spectrum", "isotopes", "convert")
_ALWAYS = {"format", "quiet", "cache", "require", "peptide_command", "subcommand",
           "timeout_s"}


def _known(command: str) -> set[str] | None:
    parser = build_parser()
    for action in parser._subparsers._group_actions:
        sub = action.choices.get(command)
        if sub is not None:
            return {a.dest for a in sub._actions if a.dest != "help"}
    return None


def _checked_args(command: str, args: dict) -> dict:
    """
    A request's arguments under the CLI's names. A request through `serve`
    that named its input `files` used to be answered with zero rows and
    exit 0 — the name was dropped silently (the cross-check, MIL-Q #6).
    Aliases are mapped; an unknown name is `bad_arguments`.
    """
    from .contract import ContractError

    aliases = dict(_ALIASES.get(command, {}))
    if command in _SINGLE_FILE:
        aliases.update({"path": "file", "files": "file"})
    for old, new in aliases.items():
        if old in args and new not in args:
            value = args.pop(old)
            if new == "file" and isinstance(value, list):
                if len(value) != 1:
                    raise ContractError("bad_arguments", f"{command} reads one file")
                value = value[0]
            if new in ("paths", "files") and isinstance(value, str):
                value = [value]
            args[new] = value
    known = _known(command)
    if known is not None:
        unknown = sorted(set(args) - known - _ALWAYS)
        if unknown:
            raise ContractError("bad_arguments",
                                f"{command} has no argument {', '.join(unknown)}")
    if command == "batch-xic" and not args.get("paths"):
        raise ContractError("bad_arguments", "batch-xic needs paths (files or folders)")
    return args


# --------------------------------------------------------------------------- #
_TABLES = {"info": "channels", "scans": "scans", "xic": "summary",
           "spectrum": "peaks", "isotopes": "envelope", "batch-xic": "rows",
           "selftest": "files"}


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return ";".join(_cell(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\t", " ").replace("\n", " ")


def _flatten(row: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in row.items():
        if isinstance(value, dict):
            out.update(_flatten(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def tsv(document: dict) -> str:
    """The document's main table as tab-separated text (header first)."""
    command = document.get("command", "")
    key = _TABLES.get(command)
    if key is None and command.startswith("peptide"):
        key = document.get("table")
    rows = document.get(key) if key else None
    if rows is None and command == "scans":
        rows = document.get("channels")
    if not isinstance(rows, list):
        rows = [{k: v for k, v in document.items()
                 if not isinstance(v, (list, dict))}]
    flat = [_flatten(r) for r in rows]
    columns: list[str] = []
    for row in flat:
        for name in row:
            if name not in columns:
                columns.append(name)
    lines = ["\t".join(columns)]
    lines += ["\t".join(_cell(row.get(c)) for c in columns) for row in flat]
    return "\n".join(lines) + "\n"


def dumps(document: dict) -> str:
    return json.dumps(document, ensure_ascii=True, allow_nan=False) + "\n"


def error_document(code: str, message: str) -> dict:
    from .contract import SCHEMA

    return {"schema": SCHEMA, "error": code, "message": message}


def _ensure_streams() -> None:
    """
    A windowed PyInstaller program on Windows starts with `sys.stdout` and
    `sys.stderr` set to None; writing the document would raise and the
    error could not even be reported. Point them at the null device so the
    command at least exits with its code. (The installed MIL-Q.exe is
    windowed: the command line on Windows is `pip install`.)
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in SUBCOMMANDS:
        _ensure_streams()
    if not argv or argv[0] not in SUBCOMMANDS:
        # the application, as before: Qt is imported only on this path
        from .app import main as app_main

        return app_main(argv)
    from .contract import ContractError, close_all

    quiet = "--quiet" in argv
    try:
        args = vars(build_parser().parse_args(argv))
        command = args.pop("command")
        if command == "serve":
            from .serve import main as serve_main

            return serve_main(args)
        document = run(command, args)
        if args.get("format") == "tsv":
            sys.stdout.write(tsv(document))
        else:
            sys.stdout.write(dumps(document))
        return 0
    except ContractError as exc:
        sys.stderr.write(dumps(error_document(exc.code, exc.message)))
        return exc.exit_code
    except SystemExit as exc:            # --help
        return int(exc.code or 0)
    except Exception as exc:
        if not quiet:
            import traceback

            traceback.print_exc(file=sys.stderr)
        sys.stderr.write(dumps(error_document("internal", f"{type(exc).__name__}: {exc}")))
        return 5
    finally:
        close_all()


if __name__ == "__main__":
    sys.exit(main())
