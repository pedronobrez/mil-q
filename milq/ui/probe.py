"""
The window as a script sees it: what it shows, written to a file, and
commands read from a file beside it.

An agent driving the GUI should not have to work from pixels. With
`MILQ_UI_PROBE=/path/probe.json` the window writes what it is showing —
workspace, open samples, active channel, extracted ion chromatograms, the
time range, the spectrum's title, the project — to that file whenever it
changes, and runs the commands it finds in `/path/probe.json.commands`
through the same code the menus and buttons use. Nothing here runs unless
the variable is set. It is MIL-X's `MILX_UI_PROBE`, with the same file
protocol: a command file holds one JSON object or a list of them, each with
an `id` and an `action`; the file is deleted once read, and the probe's
`last_command` says `{id, action, ok, message, completed_at}`.

The other variables, read once at start:

    MILQ_OPEN            a project (.oqproj) to open
    MILQ_OPEN_RAW        a raw file, or a folder of them, to open
    MILQ_SNAPSHOT        write the window to this PNG after
    MILQ_SNAPSHOT_DELAY  seconds (default 10), on workspace
    MILQ_SNAPSHOT_TAB    0–3 or a name; then quit unless a probe is set

Commands (`action` and its fields):

    select-workspace   name (explorer, analytics, method, samples) or index
    open-file          path — a raw file or a project
    select-channel     sample (key, name or index), channel (index; omit for TIC)
    add-xic            mz (list or "a, b"), tol, unit (Da/ppm), source
                       (channel, ms1, ms2-all, gated:MZ[:TOL])
    clear-xics
    set-rt-range       start, end (minutes)
    show-scan          scan (0-based); average  start, end
    export-chart       path, chart (chromatogram, spectrum, contour),
                       format, scale, theme, background, type_size
    save-project       path (optional once the project has one)
"""

from __future__ import annotations

import datetime
import json
import os

from PyQt6 import QtCore, QtWidgets

ENV_PROBE = "MILQ_UI_PROBE"
WORKSPACES = ("explorer", "analytics", "method", "samples")
POLL_MS = 400


class CommandError(ValueError):
    """A command that cannot be carried out, with the reason."""


class UiProbe(QtCore.QObject):
    def __init__(self, shell, path: str):
        super().__init__(shell)
        self.shell = shell
        self.path = os.path.abspath(path)
        self.last_command: dict | None = None
        self._written = ""
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self.tick)
        self._timer.start()
        self.tick()

    @property
    def command_path(self) -> str:
        return self.path + ".commands"

    # -- what the window shows ------------------------------------------------ #
    def snapshot(self) -> dict:
        shell = self.shell
        session = shell.session
        explorer = shell.explorer
        active = explorer.active_ref
        channel = getattr(active, "channel", None)
        info = getattr(channel, "info", None)
        views = list(getattr(explorer.chrom, "views", []) or [])
        x_range = None
        if views:
            (lo, hi), _y = views[0].plot.getViewBox().viewRange()
            x_range = [round(float(lo), 4), round(float(hi), 4)]
        return {
            "schema": "milq-ui-probe/1",
            "title": shell.windowTitle(),
            "workspace": WORKSPACES[shell.tabs.currentIndex()]
            if 0 <= shell.tabs.currentIndex() < len(WORKSPACES) else "",
            "project": {"path": session.project_path, "dirty": bool(session.dirty)},
            "samples": [
                {"key": e.key, "name": e.name, "path": e.path,
                 "channels": len(getattr(e.sample, "channels", []) or []),
                 "problem": e.problem or ""}
                for e in session.entries],
            "active": None if active is None else {
                "key": active.key, "label": active.label,
                "kind": getattr(info, "kind", ""),
                "precursor": getattr(info, "precursor", None)},
            "checked": [r.key for r in explorer._checked_refs()],
            "xics": [d["label"] for d in explorer.xic_defs],
            "rt_range": x_range,
            "spectrum": explorer.spectrum.title,
            "status": shell.statusBar().currentMessage(),
            "last_command": self.last_command,
        }

    def write(self) -> None:
        text = json.dumps(self.snapshot(), indent=1, default=str)
        if text == self._written:
            return
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, self.path)
        self._written = text

    # -- commands ------------------------------------------------------------- #
    def tick(self) -> None:
        if os.path.exists(self.command_path):
            try:
                with open(self.command_path, encoding="utf-8") as handle:
                    text = handle.read()
                os.remove(self.command_path)
            except OSError:
                return                      # still being written; next tick
            try:
                document = json.loads(text)
            except ValueError as exc:
                self._done({}, False, f"unreadable command file: {exc}")
            else:
                for command in (document if isinstance(document, list) else [document]):
                    self.run(command)
        try:
            self.write()
        except OSError:
            pass

    def run(self, command: dict) -> None:
        action = str(command.get("action", ""))
        try:
            handler = getattr(self, "_do_" + action.replace("-", "_"), None)
            if handler is None:
                raise CommandError(f"unknown action {action!r}")
            message = handler(command) or "done"
            ok = True
        except Exception as exc:          # every failure is the command's answer
            message, ok = str(exc), False
        self._done(command, ok, message)

    def _done(self, command: dict, ok: bool, message: str) -> None:
        self.last_command = {
            "id": str(command.get("id", "")), "action": command.get("action", ""),
            "ok": ok, "message": message,
            "completed_at": datetime.datetime.now().isoformat(timespec="seconds")}
        QtWidgets.QApplication.processEvents()
        self.write()

    # the actions -------------------------------------------------------------- #
    def _do_select_workspace(self, command) -> str:
        name = command.get("name", command.get("index"))
        if isinstance(name, int) or str(name).isdigit():
            index = int(name)
        elif str(name).lower() in WORKSPACES:
            index = WORKSPACES.index(str(name).lower())
        else:
            raise CommandError(f"no workspace {name!r}")
        self.shell.tabs.setCurrentIndex(index)
        return WORKSPACES[index]

    def _do_open_file(self, command) -> str:
        path = os.path.abspath(os.path.expanduser(str(command["path"])))
        if not os.path.exists(path):
            raise CommandError(f"not there: {path}")
        if path.lower().endswith((".oqproj", ".opvproj")):
            if not self.shell.load_project_file(path):
                raise CommandError(f"the project did not open: {path}")
            return f"project {path}"
        session = self.shell.session
        before = len(session.entries)
        opened = session.open_file(path)
        problems = [e.problem for e in session.entries[before:] if e.problem]
        return (f"opened {opened.filename}: {len(session.entries) - before} sample(s)"
                + (f" — {problems[0]}" if problems else ""))

    def _entry(self, which):
        entries = self.shell.session.entries
        if not entries:
            raise CommandError("no sample is open")
        if which is None:
            return entries[0]
        for entry in entries:
            if which in (entry.key, entry.name):
                return entry
        if isinstance(which, int) or str(which).isdigit():
            index = int(which)
            if 0 <= index < len(entries):
                return entries[index]
        raise CommandError(f"no sample {which!r}")

    def _do_select_channel(self, command) -> str:
        entry = self._entry(command.get("sample"))
        channel = command.get("channel")
        key = f"{entry.key}|{'TIC' if channel is None else int(channel)}"
        self.shell.tabs.setCurrentIndex(0)
        self.shell.explorer.select_channel(key)
        return key

    def _do_add_xic(self, command) -> str:
        explorer = self.shell.explorer
        masses = command.get("mz", [])
        if isinstance(masses, (int, float)):
            masses = [masses]
        if isinstance(masses, str):
            text = masses
        else:
            text = ", ".join(f"{float(m):.6f}" for m in masses)
        explorer.xic_mz.setText(text)
        if "tol" in command:
            explorer.xic_tol.setValue(float(command["tol"]))
        if "unit" in command:
            explorer.xic_unit.setCurrentText(str(command["unit"]))
        explorer.set_xic_source(str(command.get("source", "channel")))
        before = len(explorer.xic_defs)
        explorer._extract_from_form()
        return f"{len(explorer.xic_defs) - before} XIC(s) added"

    def _do_clear_xics(self, _command) -> str:
        self.shell.explorer._clear_xics()
        return "cleared"

    def _do_set_rt_range(self, command) -> str:
        lo, hi = float(command["start"]), float(command["end"])
        self.shell.explorer.chrom.set_x_range(min(lo, hi), max(lo, hi))
        return f"{min(lo, hi):g}–{max(lo, hi):g} min"

    def _do_show_scan(self, command) -> str:
        self.shell.explorer._show_scan(int(command["scan"]))
        return self.shell.explorer.spectrum.title

    def _do_average(self, command) -> str:
        self.shell.explorer._show_average(float(command["start"]), float(command["end"]))
        return self.shell.explorer.spectrum.title

    def _do_export_chart(self, command) -> str:
        from .chart_export import ExportOptions, export

        explorer = self.shell.explorer
        which = str(command.get("chart", "chromatogram")).lower()
        charts = {"chromatogram": explorer.chrom.active_view,
                  "spectrum": explorer.spectrum,
                  "contour": explorer.contour_view.plot}
        if which not in charts:
            raise CommandError(f"no chart {which!r} (chromatogram, spectrum, contour)")
        path = os.path.abspath(os.path.expanduser(str(command["path"])))
        suffix = os.path.splitext(path)[1].lstrip(".").lower()
        options = ExportOptions(
            str(command.get("format", suffix if suffix in ("png", "svg") else "png")),
            float(command.get("scale", 3)), str(command.get("theme", "light")),
            str(command.get("background", "paper")),
            float(command.get("type_size", 1.0))).clamped()
        return export(charts[which], path, options)

    def _do_save_project(self, command) -> str:
        session = self.shell.session
        path = command.get("path") or session.project_path
        if not path:
            raise CommandError("the project has no file yet: give a path")
        session.save_project(os.path.abspath(os.path.expanduser(str(path))))
        return session.project_path


# --------------------------------------------------------------------------- #
def start_from_environment(shell, app) -> UiProbe | None:
    """Open, snapshot and probe as the environment asks. Returns the probe."""
    env = os.environ
    opened = False
    project = env.get("MILQ_OPEN")
    if project:
        shell.load_project_file(os.path.expanduser(project))
        opened = True
    raw = env.get("MILQ_OPEN_RAW")
    if raw:
        raw = os.path.expanduser(raw)
        paths = ([os.path.join(raw, n) for n in sorted(os.listdir(raw))
                  if n.lower().endswith((".wiff", ".mzml"))]
                 if os.path.isdir(raw) else [raw])
        for path in paths:
            shell.load_file(path)
        if paths:
            shell.tabs.setCurrentIndex(0)
        opened = True
    probe = UiProbe(shell, env[ENV_PROBE]) if env.get(ENV_PROBE) else None
    target = env.get("MILQ_SNAPSHOT")
    if target:
        delay = float(env.get("MILQ_SNAPSHOT_DELAY", "10") or 10)
        tab = env.get("MILQ_SNAPSHOT_TAB", "")

        def snap():
            if tab:
                index = (int(tab) if tab.isdigit()
                         else WORKSPACES.index(tab.lower()) if tab.lower() in WORKSPACES
                         else shell.tabs.currentIndex())
                shell.tabs.setCurrentIndex(index)
                QtWidgets.QApplication.processEvents()
            shell.grab().save(os.path.expanduser(target))
            if probe is None:
                app.quit()

        QtCore.QTimer.singleShot(int(delay * 1000), snap)
    shell._scripted_start = opened
    return probe
