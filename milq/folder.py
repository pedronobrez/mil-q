"""
What is about to be opened, looked at before anything opens it.

Opening a file is where a folder's problems are found today, and by then
the answer is already wrong: a `.wiff` whose `.wiff.scan` is not beside it
opens and draws its chromatograms, a `.wiff2` looks like data and is not
read here, a file picked twice becomes two entries of one injection. None
of that needs a reader. The names in the folder say it, and this module
reads names, sizes nothing and opens nothing — `check_files` touches the
file system only through `listdir`, `exists` and `access`.

Everything it finds is a `Finding`: what was seen, in plain words, and
what to do about it. The one repair it can propose is a rename, because
the ordinary way a SCIEX pair comes apart is a companion renamed by hand
(`name.wiff_mix1.scan` beside `name_mix1.wiff`), and the file the reader
needs is then in the folder under the wrong name. Which stray belongs to
which `.wiff` cannot be *known* from outside the files — the sizes say
nothing, both are large — so the pairing is by the names alone and is
reported as a guess. `apply_rename` never overwrites.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import raw
from .wiff import scan_file_of

# -- kinds of finding, for the dialog and for the tests --------------------- #
#: a `.wiff` with no `.wiff.scan` beside it
MISSING_SCAN = "missing scan"
#: a `.scan` belonging to no `.wiff` in its folder
STRAY_SCAN = "stray scan"
#: a file of a format this build does not read, found beside ones it does
IGNORED = "ignored"
#: a file named outright whose extension has no reader
UNSUPPORTED = "unsupported"
#: a path that is already open, or was given twice
DUPLICATE = "duplicate"
#: a file or folder that cannot be read
UNREADABLE = "unreadable"
#: a path that is not there at all
ABSENT = "absent"

#: extensions of other instrument formats. Not read here; msconvert writes
#: mzML from all of them. `.wiff2` is the one that turns up beside the files
#: this does read, so it has an answer of its own — and the answer is
#: measured rather than assumed. Clearcore2's own `CheckDataFileIntegrity`
#: calls all nine `.wiff2` of the ZenoTOF folder `NotWiffFile`, and its
#: `Clearcore2.Data.Wiff2` assembly declares the container's whole schema:
#: seven tables — header, sample, method, device_method, device_descriptor,
#: device_identifier, method_parameters_info — with no column for a
#: spectrum, a peak, an intensity or a chromatogram. The header table holds
#: `wiff_hash`, `scan_hash` and `scan_size`, which is what the file is for:
#: it records the identity of the `.wiff` and `.wiff.scan` beside it. So
#: "nothing is lost" is a measurement, not a hope.
OTHER_FORMATS = {
    ".raw": "Thermo",
    ".d": "Agilent or Bruker",
    ".tdf": "Bruker timsTOF",
    ".tsf": "Bruker timsTOF",
    ".baf": "Bruker",
    ".yep": "Bruker",
    ".lcd": "Shimadzu",
    ".qgd": "Shimadzu",
    ".cdf": "netCDF",
    ".mzxml": "mzXML",
    ".mzdata": "mzData",
}

WIFF2 = ".wiff2"


@dataclass(frozen=True)
class Finding:
    """One thing worth saying about a path, with what to do about it."""

    path: str
    kind: str
    finding: str
    action: str
    #: for a rename that would repair the finding: the file, and its new name
    rename_from: str = ""
    rename_to: str = ""

    @property
    def name(self) -> str:
        return os.path.basename(self.path) or self.path

    @property
    def renameable(self) -> bool:
        return bool(self.rename_from and self.rename_to)


@dataclass
class FolderReport:
    """What was asked for, what would be opened, and what to look at first."""

    requested: list[str] = field(default_factory=list)
    #: the files that would be opened, in the order they would be
    paths: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    #: the folders looked in
    folders: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """True when there is something to say. `paths` may still be full."""
        return bool(self.findings)

    @property
    def renames(self) -> list[Finding]:
        return [f for f in self.findings if f.renameable]

    def of_kind(self, kind: str) -> list[Finding]:
        return [f for f in self.findings if f.kind == kind]

    def summary(self) -> str:
        files = f"{len(self.paths)} file{'' if len(self.paths) == 1 else 's'}"
        if not self.findings:
            return f"{files} to open; nothing to report."
        count = len(self.findings)
        return (f"{files} to open; {count} thing{'' if count == 1 else 's'} "
                f"to look at.")


# -- pairing a stray .scan with a .wiff -------------------------------------- #
def _affinity(a: str, b: str) -> tuple[int, int]:
    """
    How alike two file names are: the common prefix, then the common suffix.

    Nothing outside the files can settle which `.scan` belongs to which
    `.wiff` — both are large and neither name is inside the other — so
    this is the whole of the evidence, and it is why the pairing is
    offered as a guess rather than done.
    """
    a, b = a.lower(), b.lower()
    prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix += 1
    suffix = 0
    for x, y in zip(reversed(a), reversed(b)):
        if x != y:
            break
        suffix += 1
    shortest = min(len(a), len(b))
    if prefix + suffix > shortest:  # the same name twice; not a case that arises
        return shortest, 0
    return prefix, suffix


def guess_owner(stray: str, wiffs) -> str:
    """
    The `.wiff` a stray `.scan` most likely belongs to, or "".

    Each candidate is compared against the companion it wants rather than
    against its own name, so that the `.scan` both names end in counts. A
    guess needs at least one character of common prefix; ties go to the
    first name in order, so one folder always gives one answer.
    """
    best, score = "", (0, 0)
    for wiff in sorted(wiffs):
        wanted = os.path.basename(scan_file_of(wiff))
        rank = _affinity(os.path.basename(stray), wanted)
        if rank[0] >= 1 and rank > score:
            best, score = wiff, rank
    return best


def apply_rename(finding: Finding) -> str:
    """
    Carry out the rename a finding proposes; returns the new path.

    Refuses to write over anything: a `.wiff.scan` already there is either
    the right one, in which case the stray belongs to something else, or
    the wrong one, and neither is worth losing to a guess.
    """
    if not finding.renameable:
        raise ValueError("this finding proposes no rename")
    if os.path.exists(finding.rename_to):
        raise FileExistsError(
            f"{os.path.basename(finding.rename_to)} is already there; "
            f"nothing was renamed")
    os.rename(finding.rename_from, finding.rename_to)
    return finding.rename_to


# -- the check ---------------------------------------------------------------- #
def _key(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def _listdir(path: str) -> list[str] | None:
    """
    What a folder holds, without the metadata the operating system keeps in it.

    Names beginning with a dot are left out, and the one that matters is
    macOS's `._name`: on any volume that is not HFS+ or APFS — an exFAT
    memory stick, an SMB share, which is where instrument data actually
    travels — the Finder writes a `._X` resource fork beside every `X` it
    touches. Reading the nine ZenoTOF infusions off an external drive made
    `._CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1.wiff.scan`, which ends in
    `.scan` and whose stem is in no folder, so the check reported it as a
    stray scan belonging to no `.wiff` — a finding about a file the user
    never made and cannot act on. A `._X.wiff` is worse: `raw.is_supported`
    says yes and it would have gone into `paths` to be opened.

    This is the only place the module lists a folder, so leaving them out
    here covers the candidates, the companion check, the strays and the
    `.wiff2` count at once. A dot-file named outright on the command line
    still goes through, because a path that was given was meant.
    """
    try:
        return sorted(n for n in os.listdir(path) if not n.startswith("."))
    except OSError:
        return None


def _some(names: list[str], limit: int = 3) -> str:
    shown = ", ".join(names[:limit])
    return shown if len(names) <= limit else f"{shown} and {len(names) - limit} more"


def check_files(paths, open_paths=()) -> FolderReport:
    """
    Look over the paths about to be opened, without opening any of them.

    `paths` are files or folders; a folder contributes the supported files
    directly inside it, not below it — an acquisition folder is flat.
    `open_paths` are the files already in the session, so that adding one
    twice is a finding rather than a second copy of every sample.

    The folder-wide findings — the files of other formats sitting beside
    the data — are raised for a folder that was *given*, since somebody
    who picked two files by hand has already said what they want. A stray
    `.scan` is raised either way once a `.wiff` in that folder is missing
    its companion, because that is the case the rename repairs.
    """
    report = FolderReport(requested=[str(p) for p in paths])
    already = {_key(p) for p in open_paths}
    seen: set[str] = set()
    candidates: list[str] = []
    given_folders: list[str] = []
    folders: list[str] = []

    for given in report.requested:
        path = os.path.abspath(given)
        if os.path.isdir(path):
            names = _listdir(path)
            if names is None:
                report.findings.append(Finding(
                    path, UNREADABLE,
                    f"the folder {os.path.basename(path)} cannot be read",
                    "check who owns it and what it is set to; nothing in it "
                    "can be opened until it can be listed"))
                continue
            given_folders.append(path)
            if path not in folders:
                folders.append(path)
            for name in names:
                child = os.path.join(path, name)
                if raw.is_supported(child) and os.path.isfile(child):
                    candidates.append(child)
            continue
        if not os.path.exists(path):
            report.findings.append(Finding(
                path, ABSENT, f"{os.path.basename(path)} is not there",
                "the file moved or was renamed; add it again from where it "
                "is now"))
            continue
        if not raw.is_supported(path):
            extension = os.path.splitext(path)[1].lower()
            vendor = OTHER_FORMATS.get(extension) or (
                "SCIEX, a different container" if extension == WIFF2 else "")
            what = f" — {vendor} data" if vendor else ""
            report.findings.append(Finding(
                path, UNSUPPORTED,
                f"{os.path.basename(path)} is a {extension or 'nameless'} "
                f"file{what}, which this build does not read",
                f"this build reads {', '.join(sorted(raw.FORMATS))}; convert "
                f"it to mzML with ProteoWizard's msconvert first"))
            continue
        candidates.append(path)
        parent = os.path.dirname(path)
        if parent not in folders:
            folders.append(parent)

    # -- the files themselves ---------------------------------------------- #
    for path in candidates:
        key = _key(path)
        if key in already:
            report.findings.append(Finding(
                path, DUPLICATE, f"{os.path.basename(path)} is open already",
                "it will not be added a second time; every sample in it is "
                "in the batch already"))
            continue
        if key in seen:
            report.findings.append(Finding(
                path, DUPLICATE, f"{os.path.basename(path)} was given twice",
                "it will be opened once"))
            continue
        seen.add(key)
        if not os.access(path, os.R_OK):
            report.findings.append(Finding(
                path, UNREADABLE, f"{os.path.basename(path)} cannot be read",
                "check its permissions, or copy it somewhere you own"))
            continue
        report.paths.append(path)

    # -- the companion every .wiff needs ------------------------------------ #
    missing: dict[str, list[str]] = {}
    for path in report.paths:
        if os.path.splitext(path)[1].lower() != ".wiff":
            continue
        companion = scan_file_of(path)
        if not os.path.exists(companion):
            missing.setdefault(os.path.dirname(path), []).append(path)
        elif not os.access(companion, os.R_OK):
            report.findings.append(Finding(
                companion, UNREADABLE,
                f"{os.path.basename(companion)} is beside "
                f"{os.path.basename(path)} but cannot be read",
                "the chromatograms will open and the spectra will not; check "
                "its permissions"))

    # -- the folders --------------------------------------------------------- #
    report.folders = folders
    for folder in folders:
        names = _listdir(folder)
        if names is None:
            continue
        lower = {n.lower() for n in names}
        wiffs = [os.path.join(folder, n) for n in names
                 if n.lower().endswith(".wiff")]
        without = [w for w in wiffs
                   if os.path.basename(w).lower() + ".scan" not in lower]
        strays = [n for n in names
                  if n.lower().endswith(".scan") and n[:-5].lower() not in lower]
        owners = {s: guess_owner(os.path.join(folder, s), without)
                  for s in strays}

        for path in missing.get(folder, []):
            companion = os.path.basename(scan_file_of(path))
            theirs = [s for s in strays if owners[s] == path]
            if theirs:
                action = (f"the folder holds {_some(theirs)}, which belongs "
                          f"to no .wiff here; renamed to {companion} it may "
                          f"be the one — the row for it offers the rename")
            else:
                action = (f"copy {companion} in from where the acquisition "
                          f"was written; nothing here can stand in for it")
            report.findings.append(Finding(
                path, MISSING_SCAN,
                f"{os.path.basename(path)} has no {companion} beside it — "
                f"the chromatograms and the method open, the spectra, the "
                f"extracted ion chromatograms and the quantitation do not",
                action))

        if folder in given_folders or folder in missing:
            for stray in strays:
                stray_path = os.path.join(folder, stray)
                owner = owners[stray]
                if owner:
                    wanted = scan_file_of(owner)
                    report.findings.append(Finding(
                        stray_path, STRAY_SCAN,
                        f"{stray} belongs to no .wiff in this folder, and "
                        f"{os.path.basename(owner)} is missing its companion",
                        f"a guess from the two names, which is all there is "
                        f"to go on: renamed to {os.path.basename(wanted)} it "
                        f"may be the one",
                        rename_from=stray_path, rename_to=wanted))
                else:
                    report.findings.append(Finding(
                        stray_path, STRAY_SCAN,
                        f"{stray} belongs to no .wiff in this folder",
                        "its .wiff is elsewhere, or was renamed; put the pair "
                        "back together before opening it"))

        if folder not in given_folders:
            continue
        paired = [n for n in names
                  if n.lower().endswith(WIFF2) and n[:-1].lower() in lower]
        alone = [n for n in names
                 if n.lower().endswith(WIFF2) and n[:-1].lower() not in lower]
        if paired:
            report.findings.append(Finding(
                folder, IGNORED,
                f"{len(paired)} .wiff2 file{'' if len(paired) == 1 else 's'} "
                f"({_some(paired)}): the acquisition's method and file "
                f"hashes, holding no scan data, not read here",
                "nothing is lost — the .wiff of the same name beside each "
                "holds the same acquisition, and that is what is opened"))
        if alone:
            report.findings.append(Finding(
                folder, IGNORED,
                f"{len(alone)} .wiff2 file{'' if len(alone) == 1 else 's'} "
                f"({_some(alone)}) with no .wiff of the same name: the "
                f"method and file hashes, holding no scan data, not read "
                f"here",
                "those acquisitions will not be opened, and the .wiff2 "
                "cannot stand in — it holds no spectra; fetch their .wiff, "
                "or convert them to mzML"))
        others: dict[str, list[str]] = {}
        for name in names:
            extension = os.path.splitext(name)[1].lower()
            if extension in OTHER_FORMATS:
                others.setdefault(extension, []).append(name)
        for extension, group in sorted(others.items()):
            report.findings.append(Finding(
                folder, IGNORED,
                f"{len(group)} {extension} file{'' if len(group) == 1 else 's'}"
                f" ({_some(group)}): {OTHER_FORMATS[extension]} data, not read "
                f"here",
                "convert them to mzML with ProteoWizard's msconvert and open "
                "the mzML"))
    return report
