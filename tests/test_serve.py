"""
`milq serve --inbox`: the file queue an agent in a VM uses to run commands
on the Mac — and `--stdio`. The contract's second test: a valid request, a
path outside the roots, an unknown command, one that times out.
"""

import io
import json
import os
import threading
import time

import pytest

from milq import cli, contract, serve
from tests.test_cli import FRAGMENT, ida  # noqa: F401  (the fixture)


def _request(server, ident, command, args, **extra):
    body = {"schema": "mil-cli/1", "id": ident, "command": command,
            "args": args, "format": "json", **extra}
    path = server.path("inbox", f"{ident}.json")
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(body, handle)
    os.replace(path + ".tmp", path)


def _drain(server):
    while server.pending():
        server.handle(server.pending()[0])


@pytest.fixture
def server(tmp_path, ida):  # noqa: F811
    made = serve.Server(str(tmp_path / "jobs"), [os.path.dirname(ida)], timeout=60)
    yield made
    contract.close_all()


def test_four_requests_land_where_they_should(server, ida, tmp_path, monkeypatch):  # noqa: F811
    _request(server, "a-valid", "xic", {"file": ida, "mz": [FRAGMENT],
                                        "source": "gated:627.8457"})
    outside = tmp_path.parent / "elsewhere.mzML"
    _request(server, "b-outside", "info", {"file": str(outside)})
    _request(server, "c-unknown", "rm", {"file": ida})
    real_run = cli.run

    def slow(command, args):
        if args.get("slow"):
            time.sleep(2)
        return real_run(command, args)

    monkeypatch.setattr(cli, "run", slow)
    _request(server, "d-slow", "info", {"file": ida, "slow": True}, timeout_s=0.2)
    _drain(server)

    answer = server.path("outbox", "a-valid.json")
    assert os.path.exists(answer)
    assert os.path.exists(server.path("outbox", "a-valid.request.json"))
    # byte for byte what the command line prints for the same call
    monkeypatch.setattr(cli, "run", real_run)
    printed = cli.dumps(cli.run("xic", {"file": ida, "mz": [FRAGMENT],
                                        "source": "gated:627.8457"}))
    with open(answer, encoding="utf-8") as handle:
        assert handle.read() == printed

    def failed(ident):
        with open(server.path("failed", f"{ident}.json"), encoding="utf-8") as h:
            return json.load(h)

    assert failed("b-outside")["error"] == "path_outside_roots"
    assert failed("c-unknown")["error"] == "not_allowed"
    assert failed("d-slow")["error"] == "timeout"
    for ident in ("b-outside", "c-unknown", "d-slow"):
        assert os.path.exists(server.path("failed", f"{ident}.request.json"))

    with open(server.path("log.jsonl"), encoding="utf-8") as handle:
        log = [json.loads(line) for line in handle]
    assert [e["id"] for e in log] == ["a-valid", "b-outside", "c-unknown", "d-slow"]
    assert log[0]["exit"] == 0 and log[3]["exit"] == "timeout"
    assert all("peak_rss_mb" in e for e in log)
    with open(server.path("STATUS.json"), encoding="utf-8") as handle:
        status = json.load(handle)
    assert status["done"] == 4 and status["queue"] == 0 and status["current"] is None
    assert status["last_error"] == "d-slow: timeout"
    assert not server.pending()


def test_outputs_go_under_the_jobs_outbox_and_nothing_is_overwritten(server, ida):  # noqa: F811
    _request(server, "msp", "spectrum", {"file": ida, "source": "gated:627.8457",
                                         "rt": "0:1", "centroid": "none",
                                         "msp": "made.msp"})
    _request(server, "clobber", "convert", {"file": ida, "out": ida})
    _drain(server)
    with open(server.path("outbox", "msp.json"), encoding="utf-8") as handle:
        answer = json.load(handle)
    assert answer["msp"] == server.path("outbox", "msp", "made.msp")
    assert answer["files"] == [answer["msp"]]
    with open(server.path("failed", "clobber.json"), encoding="utf-8") as handle:
        assert json.load(handle)["error"] == "path_outside_roots"


def test_a_trace_and_a_tsv_are_files(server, ida):  # noqa: F811
    _request(server, "t", "xic", {"file": ida, "mz": [FRAGMENT], "trace": True,
                                  "source": "ms2-all"}, format="tsv")
    _drain(server)
    with open(server.path("outbox", "t.json"), encoding="utf-8") as handle:
        answer = json.load(handle)
    assert "traces" not in answer
    assert {os.path.basename(f) for f in answer["files"]} == {"traces.json", "xic.tsv"}


def test_a_batch_runs_in_order_in_one_file(server, ida):  # noqa: F811
    path = server.path("inbox", "both.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"id": "both", "batch": [
            {"command": "info", "args": {"file": ida}},
            {"command": "scans", "args": {"file": ida, "count": True}}]}, handle)
    _drain(server)
    with open(server.path("outbox", "both.json"), encoding="utf-8") as handle:
        answer = json.load(handle)
    assert [d["command"] for d in answer["batch"]] == ["info", "scans"]


def test_stale_running_jobs_fail_as_interrupted(tmp_path):
    root = tmp_path / "jobs"
    (root / "running").mkdir(parents=True)
    (root / "running" / "old.json").write_text("{}")
    made = serve.Server(str(root))
    assert not (root / "running" / "old.json").exists()
    assert json.loads((root / "failed" / "old.json").read_text())["error"] == "interrupted"
    assert made.pending() == []


def test_stop_ends_the_loop_and_is_removed(tmp_path):
    made = serve.Server(str(tmp_path / "jobs"))
    (tmp_path / "jobs" / "STOP").write_text("")
    result = {}
    thread = threading.Thread(target=lambda: result.setdefault("code", made.serve()))
    thread.start()
    thread.join(10)
    assert result.get("code") == 0
    assert not (tmp_path / "jobs" / "STOP").exists()


def test_stdio_answers_one_line_per_request(ida):  # noqa: F811
    requests = io.StringIO(
        json.dumps({"id": 1, "command": "info", "args": {"file": ida}}) + "\n"
        + json.dumps({"id": 2, "command": "shell", "args": {}}) + "\n")
    out = io.StringIO()
    assert serve.stdio(requests, out) == 0
    first, second = [json.loads(line) for line in out.getvalue().splitlines()]
    assert first["command"] == "info" and first["id"] == 1
    assert second["error"] == "not_allowed"


def test_serve_imports_nothing_posix_only_at_the_top():
    """`import resource` at module level broke `milq serve` on Windows."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(serve))
    top = {alias.name.split(".")[0] for node in tree.body
           if isinstance(node, (ast.Import, ast.ImportFrom))
           for alias in node.names}
    assert not top & {"resource", "fcntl", "pwd", "grp", "termios"}
    value = serve._peak_rss_mb()
    assert value is None or value > 0
