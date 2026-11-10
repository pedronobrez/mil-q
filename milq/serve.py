"""
`milq serve`: keep files open and answer requests — JSON lines on stdin
(`--stdio`), or a watched folder (`--inbox DIR`).

The inbox is how an agent in a Linux VM that sees the user's folders, but
cannot type into a macOS terminal, runs commands on the Mac. The person
starts it once:

    milq serve --inbox ~/Documents/mil-jobs --allow-root ~/Documents/MIL-data

and the agent writes `inbox/<id>.json` (as `<id>.json.tmp`, then a rename):

    {"schema": "mil-cli/1", "id": "<id>", "command": "xic",
     "args": {"file": "...", "mz": [627.8457], "source": "gated:627.8457"},
     "format": "json", "timeout_s": 1800}

or `{"batch": [ ...requests... ]}` to run several in order. The answer is
`outbox/<id>.json`, byte for byte the document `milq <command>` prints, and
the request moves to `outbox/<id>.request.json` — or both to `failed/` with
the error document. Large outputs (a `--trace`, a TSV, an MSP) are files
under `outbox/<id>/`, listed in the answer.

**An allow-list, not a shell.** Only the contract's subcommands and
`peptide …` run, in this process, through `cli.run` — no shell, no
subprocess, no `eval`. Every path a request names, read or written, must
resolve (symlinks followed) inside an `--allow-root` or inside the inbox
folder; anything else is `path_outside_roots`. Nothing is ever deleted or
overwritten outside `outbox/`. One job at a time by default; a job past its
`timeout_s` is answered `timeout` and abandoned (its thread is a daemon and
its result is dropped). `STATUS.json` is rewritten on every change and
`log.jsonl` gets one line per job; neither holds file contents. `STOP`
(or Ctrl-C, or `--idle-exit MIN` with nothing to do) ends the server after
the current job. Files found in `running/` at start were interrupted and go
to `failed/` as `interrupted`.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
import threading
import time

from . import __version__
from .contract import SCHEMA, ContractError

ALLOWED = ("selftest", "info", "scans", "xic", "spectrum", "isotopes",
           "batch-xic", "convert", "peptide")
#: argument names that hold a path to read, and those that name one to write
READ_KEYS = ("file", "files", "paths", "items", "fasta", "from", "from_",
             "spectrum", "library", "screen")
WRITE_KEYS = ("out", "msp", "tsv", "components")
POLL_S = 0.5


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _peak_rss_mb() -> float | None:
    """
    The process's peak resident memory in MB, or None where it cannot be
    read. `resource` is POSIX only — imported here, not at the top, because
    importing it made `milq serve` (and its tests) fail outright on Windows.
    """
    if sys.platform == "win32":
        return _peak_working_set_mb()
    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # bytes on macOS, kilobytes on Linux
    return round(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024, 1)


def _peak_working_set_mb() -> float | None:
    """Windows' peak working set, through psapi, without a new dependency."""
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
                process, ctypes.byref(counters), counters.cb):
            return None
        return round(counters.PeakWorkingSetSize / (1024 * 1024), 1)
    except Exception:
        return None


def _atomic_write(path: str, text: str) -> None:
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temporary, path)


class Server:
    def __init__(self, inbox: str, roots=(), timeout: float = 1800.0,
                 idle_exit: float = 0.0, max_jobs: int = 1):
        self.root = os.path.realpath(os.path.expanduser(inbox))
        self.roots = [os.path.realpath(os.path.expanduser(r)) for r in roots] + [self.root]
        self.timeout = float(timeout)
        self.idle_exit = float(idle_exit or 0.0)
        self.max_jobs = max(1, int(max_jobs))
        self.started = _now()
        self.current: dict | None = None
        self.last_error: str | None = None
        self.done = 0
        for name in ("inbox", "running", "outbox", "failed"):
            os.makedirs(os.path.join(self.root, name), exist_ok=True)
        self._recover()
        self.status()

    # -- folders -------------------------------------------------------------- #
    def path(self, *parts) -> str:
        return os.path.join(self.root, *parts)

    def _recover(self) -> None:
        for name in sorted(os.listdir(self.path("running"))):
            if not name.endswith(".json"):
                continue
            ident = name[:-5]
            shutil.move(self.path("running", name),
                        self.path("failed", f"{ident}.request.json"))
            _atomic_write(self.path("failed", f"{ident}.json"), json.dumps(
                {"schema": SCHEMA, "id": ident, "error": "interrupted",
                 "message": "the server stopped while this job was running"}) + "\n")

    def pending(self) -> list[str]:
        return sorted(n for n in os.listdir(self.path("inbox"))
                      if n.endswith(".json") and not n.endswith(".tmp"))

    def status(self) -> None:
        current = None
        if self.current:
            current = {**self.current,
                       "elapsed_s": round(time.time() - self.current["t0"], 1)}
            current.pop("t0", None)
        _atomic_write(self.path("STATUS.json"), json.dumps({
            "schema": SCHEMA, "tool": "milq", "version": __version__,
            "pid": os.getpid(), "started": self.started, "inbox": self.root,
            "roots": self.roots, "current": current,
            "queue": len(self.pending()), "done": self.done,
            "last_error": self.last_error}, indent=1) + "\n")

    def log(self, entry: dict) -> None:
        with open(self.path("log.jsonl"), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    # -- checks --------------------------------------------------------------- #
    def _inside(self, path: str) -> bool:
        real = os.path.realpath(os.path.expanduser(str(path)))
        return any(real == r or real.startswith(r.rstrip(os.sep) + os.sep)
                   for r in self.roots)

    def check(self, command: str, args: dict, ident: str) -> dict:
        if command not in ALLOWED:
            raise ContractError("not_allowed", f"{command!r} is not a command "
                                f"this server runs ({', '.join(ALLOWED)})")
        args = dict(args or {})
        for key in READ_KEYS:
            values = args.get(key)
            for value in (values if isinstance(values, list) else [values]):
                if value and not self._inside(value):
                    raise ContractError("path_outside_roots",
                                        f"{key}: {value} is outside the allowed roots")
        out_dir = self.path("outbox", ident)
        for key in WRITE_KEYS:
            value = args.get(key)
            if not value:
                continue
            if not os.path.isabs(os.path.expanduser(str(value))):
                # a bare name is written under this job's outbox folder
                os.makedirs(out_dir, exist_ok=True)
                args[key] = os.path.join(out_dir, os.path.basename(str(value)))
            target = os.path.realpath(os.path.expanduser(str(args[key])))
            inside_outbox = target.startswith(self.path("outbox") + os.sep)
            if not inside_outbox and not self._inside(target):
                raise ContractError("path_outside_roots",
                                    f"{key}: {value} is outside the allowed roots")
            if os.path.exists(target) and not inside_outbox:
                raise ContractError("path_outside_roots",
                                    f"{key}: {value} exists, and nothing outside "
                                    f"outbox/ is overwritten")
        return args

    # -- one request ---------------------------------------------------------- #
    def answer(self, request: dict, ident: str) -> tuple[dict, list[str]]:
        """The document for one request, and the large files written for it."""
        from .cli import run, tsv

        command = str(request.get("command", ""))
        args = self.check(command, request.get("args") or {}, ident)
        files: list[str] = []
        timeout = float(request.get("timeout_s", self.timeout))
        result: dict = {}

        def work():
            try:
                result["doc"] = run(command, args)
            except BaseException as exc:            # noqa: BLE001
                result["error"] = exc

        thread = threading.Thread(target=work, name=f"job-{ident}", daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            raise ContractError("timeout", f"the job ran past {timeout:g} s and "
                                "was abandoned", 5)
        if "error" in result:
            raise result["error"]
        document = result["doc"]
        out_dir = self.path("outbox", ident)
        if "traces" in document:
            os.makedirs(out_dir, exist_ok=True)
            target = os.path.join(out_dir, "traces.json")
            _atomic_write(target, json.dumps(document.pop("traces")) + "\n")
            files.append(target)
        if request.get("format") == "tsv":
            os.makedirs(out_dir, exist_ok=True)
            target = os.path.join(out_dir, f"{command.replace(' ', '-')}.tsv")
            _atomic_write(target, tsv(document))
            files.append(target)
        for key in ("msp", "out"):
            value = document.get(key)
            if isinstance(value, str) and os.path.exists(value):
                files.append(value)
        if files:
            document["files"] = files
        return document, files

    def handle(self, name: str) -> None:
        from .cli import dumps, error_document

        ident = name[:-5]
        running = self.path("running", name)
        try:
            shutil.move(self.path("inbox", name), running)
        except OSError:
            return
        t0 = time.time()
        try:
            with open(running, encoding="utf-8") as handle:
                request = json.load(handle)
        except (OSError, ValueError) as exc:
            request = None
            failure = ContractError("bad_arguments", f"unreadable request: {exc}")
        requests = []
        if isinstance(request, dict):
            ident = str(request.get("id") or ident)
            requests = request.get("batch") or [request]
        self.current = {"id": ident, "command": ",".join(
            str(r.get("command", "")) for r in requests), "t0": t0}
        self.status()
        documents, files, error = [], [], None
        try:
            if request is None:
                raise failure
            for index, item in enumerate(requests):
                sub = ident if len(requests) == 1 else f"{ident}-{index + 1}"
                doc, written = self.answer(item, sub)
                documents.append(doc)
                files += written
        except ContractError as exc:
            error = error_document(exc.code, exc.message)
        except Exception as exc:
            error = error_document("internal", f"{type(exc).__name__}: {exc}")
        where = "failed" if error else "outbox"
        body = error if error else (documents[0] if len(documents) == 1
                                    else {"schema": SCHEMA, "batch": documents})
        if error:
            body = {**body, "id": ident}
            self.last_error = f"{ident}: {error['error']}"
        _atomic_write(self.path(where, f"{ident}.json"), dumps(body))
        shutil.move(running, self.path(where, f"{ident}.request.json"))
        self.done += 1
        self.log({"id": ident, "command": self.current["command"],
                  "args": [r.get("args") for r in requests],
                  "start": datetime.datetime.fromtimestamp(t0).astimezone()
                  .isoformat(timespec="seconds"), "end": _now(),
                  "seconds": round(time.time() - t0, 3),
                  "exit": 0 if not error else error["error"],
                  "outputs": files, "peak_rss_mb": _peak_rss_mb()})
        self.current = None
        self.status()

    # -- the loop ------------------------------------------------------------- #
    def serve(self) -> int:
        idle_since = time.time()
        try:
            while True:
                if os.path.exists(self.path("STOP")):
                    os.remove(self.path("STOP"))
                    return 0
                waiting = self.pending()
                if waiting:
                    self.handle(waiting[0])
                    idle_since = time.time()
                    continue
                if self.idle_exit and time.time() - idle_since > self.idle_exit * 60:
                    return 0
                time.sleep(POLL_S)
        except KeyboardInterrupt:
            return 0
        finally:
            from .contract import close_all

            close_all()
            self.current = None
            self.status()


def stdio(stream_in=None, stream_out=None) -> int:
    """One JSON request per line in, one document per line out."""
    from .cli import dumps, error_document, run

    stream_in = stream_in or sys.stdin
    stream_out = stream_out or sys.stdout
    for line in stream_in:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            command = str(request.get("command", ""))
            if command not in ALLOWED:
                raise ContractError("not_allowed", f"{command!r} is not allowed")
            document = run(command, request.get("args") or {})
            if request.get("id") is not None:
                document = {**document, "id": request["id"]}
        except ContractError as exc:
            document = error_document(exc.code, exc.message)
        except Exception as exc:
            document = error_document("internal", f"{type(exc).__name__}: {exc}")
        stream_out.write(dumps(document))
        stream_out.flush()
    return 0


def main(args: dict) -> int:
    if args.get("cache"):
        from . import sidecar

        sidecar.configure(args["cache"])
    if args.get("stdio"):
        return stdio()
    server = Server(args["inbox"], args.get("allow_root") or [],
                    timeout=args.get("timeout", 1800.0),
                    idle_exit=args.get("idle_exit", 0.0),
                    max_jobs=args.get("max_jobs", 1))
    if not args.get("quiet"):
        sys.stderr.write(f"milq serve: watching {server.path('inbox')} "
                         f"(roots: {', '.join(server.roots)})\n")
    return server.serve()
