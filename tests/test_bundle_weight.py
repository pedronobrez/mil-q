"""
Guards on what the packaged application is allowed to drag in.

A frozen bundle contains whatever the import graph reaches, and the import
graph is easy to widen by accident: one convenience import of a module that
happens to sit next to a numba-compiled routine put 123 MB of llvmlite into a
247 MB build, for a function this application never calls. Nothing here tests
behaviour; these are size regressions, which are otherwise only noticed by
someone waiting on a download.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: packages that cost tens of megabytes and that nothing in the app should reach
HEAVY = ("numba", "llvmlite", "pandas", "h5py", "alphabase", "matplotlib")


def test_the_bootstrap_does_not_reach_alpharaws_sciex_reader():
    """
    It was imported only to read a HAS_DOTNET flag off it.

    The module imports a centroiding routine that pulls numba, and swallows
    the reason for any failure into a bare False. bootstrap._load_clearcore
    registers the assemblies itself and keeps the original exception.
    """
    tree = ast.parse((ROOT / "milq" / "bootstrap.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            root = node.module or ""
            imported.add(root)
            imported.update(f"{root}.{alias.name}" for alias in node.names)
    assert not any("pysciexwifffilereader" in name for name in imported), imported
    # the one alpharaw module that is still needed brings up the runtime
    assert "alpharaw.raw_access.clr_utils" in imported


def test_the_spec_excludes_the_heavy_packages():
    spec = (ROOT / "packaging" / "milq.spec").read_text()
    excluded = spec[spec.index("excluded = ["):spec.index("analysis = Analysis")]
    for package in HEAVY:
        assert f'"{package}"' in excluded, f"{package} is not excluded from the bundle"


def test_importing_the_app_stays_clear_of_them():
    """The check that actually holds: what a fresh interpreter ends up loading."""
    code = (
        "import sys, milq, milq.bootstrap, milq.wiff, "
        "milq.processing, milq.lipidmaps, milq.structure, "
        "milq.explain\n"
        "print(sorted({m.split('.')[0] for m in sys.modules} & "
        f"set({HEAVY!r})))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", f"pulled in {result.stdout.strip()}"


def test_the_sciex_bootstrap_stays_clear_of_them():
    """
    The same, after the .NET side has actually been brought up.

    Skipped where there is no runtime to bring up — a machine without .NET
    cannot answer this one, and the import-time check above still stands.
    """
    code = (
        "import sys\n"
        "from milq import bootstrap\n"
        "try:\n"
        "    bootstrap.ensure()\n"
        "except Exception as exc:\n"
        "    print('SKIP', type(exc).__name__)\n"
        "    raise SystemExit(0)\n"
        "print(sorted({m.split('.')[0] for m in sys.modules} & "
        f"set({HEAVY!r})))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    output = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if output.startswith("SKIP"):
        pytest.skip(f"no working .NET runtime here ({output})")
    assert output == "[]", f"pulled in {output}"
