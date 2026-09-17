"""
The files the installers are built from are only ever read by a build machine.

A mistake in one of them surfaces minutes into a release run, on a system the
author may not have, as an error about something else — WiX reports a stray
double hyphen in a comment as "not a valid source file". These read them here
instead.
"""

import os
import re
import pytest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WXS = ROOT / "packaging" / "milq.wxs"


def test_the_windows_installer_source_is_valid_xml():
    ET.parse(WXS)


def test_the_windows_installer_pins_its_toolset():
    """WiX 7 will not build without accepting a paid maintenance-fee EULA."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    install = [line for line in workflow.splitlines()
               if "dotnet tool install" in line and "wix" in line]
    assert install, "the workflow no longer installs WiX"
    assert all(re.search(r"--version\s+5\.", line) for line in install), install


def test_the_spec_and_the_package_agree_on_the_version():
    import milq

    spec = (ROOT / "packaging" / "milq.spec").read_text()
    assert "__version__" in spec, "the spec should read the version, not repeat it"
    assert milq.__version__ not in spec, "the spec has a version written into it"


def test_the_wine_shim_stays_out_of_the_installer():
    """
    It must never be packaged.

    On real Windows an application-local icuuc.dll is found before the one in
    System32, so shipping the stub would replace working ICU with a stub for
    every user who has the real thing. It exists to be copied into a Wine
    prefix by hand.
    """
    stub = ROOT / "packaging" / "wine" / "icuuc_stub.c"
    assert stub.exists(), "the shim's source is gone but its guard is still here"

    spec = (ROOT / "packaging" / "milq.spec").read_text()
    wxs = WXS.read_text()
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for name, text in (("spec", spec), ("wxs", wxs), ("workflow", workflow)):
        assert "icuuc" not in text.lower(), f"the {name} references the ICU shim"

    # and nothing built by PyInstaller may carry one either
    built = ROOT / "dist"
    if built.is_dir():
        found = [p for p in built.rglob("icuuc*") if p.is_file()]
        assert not found, f"an ICU shim reached the build: {found}"


# -- the icon reaches every platform ---------------------------------------- #
ICONS = ROOT / "packaging" / "icons"
LINUX = ROOT / "packaging" / "linux"
SPEC = (ROOT / "packaging" / "milq.spec").read_text()


def test_the_bundle_icon_exists_in_every_form_the_builds_need():
    assert (ICONS / "MIL-Q.icns").is_file()          # macOS bundle
    assert (ICONS / "MIL-Q.ico").is_file()           # Windows executable
    assert (ICONS / "MIL-Q.iconset" / "icon_256x256.png").is_file()  # Linux launcher
    assert (ROOT / "milq" / "icon.png").is_file()   # the window, everywhere
    assert "icon=ICON" in SPEC


def test_the_windows_installer_names_the_icon_for_the_shortcut_and_the_programs_list():
    root = ET.parse(WXS).getroot()
    ns = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
    icon = root.find(".//w:Icon", ns)
    assert icon is not None and icon.get("Id") == "MilqIcon"
    assert icon.get("SourceFile") == "$(IconFile)"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert 'IconFile="$PWD\\packaging\\icons\\MIL-Q.ico"' in workflow
    assert (ICONS / "MIL-Q.ico").is_file()
    arp = root.find(".//w:Property[@Id='ARPPRODUCTICON']", ns)
    assert arp is not None and arp.get("Value") == "MilqIcon"
    shortcut = root.find(".//w:Shortcut", ns)
    assert shortcut.get("Icon") == "MilqIcon"


def test_the_linux_launcher_entry_is_complete_and_travels_with_the_tarball():
    desktop = (LINUX / "milq.desktop").read_text()
    keys = dict(line.split("=", 1) for line in desktop.splitlines() if "=" in line)
    assert keys["Type"] == "Application" and keys["Name"] == "MIL-Q"
    assert keys["Exec"].startswith("INSTALLDIR/MIL-Q") and keys["Icon"] == "milq"
    install = LINUX / "install.sh"
    if os.name != "nt":   # Windows has no execute bit; git carries the mode
        assert install.stat().st_mode & 0o111, "install.sh is not executable"
    script = install.read_text()
    assert "INSTALLDIR" in script and "milq.png" in script and "--remove" in script
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "packaging/linux/milq.desktop" in workflow
    assert "icon_256x256.png dist/MIL-Q/milq.png" in workflow


# -- the layered icon for macOS 26 ----------------------------------------- #
ICON_DOCUMENT = ICONS / "MIL-Q.icon"


def test_the_icon_composer_document_is_complete():
    """
    Skipped while there is no document: 1.0.0 ships without one.

    The rename took the layered icon with it — OpenQuant's drew two
    co-eluting peaks and MIL-Q's mark has not been redrawn for Icon
    Composer — so the .icns is what the Dock shows, as it did on every
    macOS before 26. The moment somebody adds the document back this
    starts checking it again, which is why it is a skip and not a deletion.
    """
    import json
    if not ICON_DOCUMENT.is_dir():
        pytest.skip(f"no layered icon document at {ICON_DOCUMENT}")
    manifest = json.loads((ICON_DOCUMENT / "icon.json").read_text())
    assert manifest["supported-platforms"] == {"squares": "shared"}
    assert manifest["fill"]["solid"].startswith("srgb:")
    layers = [layer for group in manifest["groups"] for layer in group["layers"]]
    assert [layer["name"] for layer in layers] == ["neighbour", "peak"]
    for layer in layers:
        assert (ICON_DOCUMENT / "Assets" / layer["image-name"]).is_file()
        assert layer["glass"] is True
    for image in (ICON_DOCUMENT / "Assets").glob("*.svg"):
        ET.parse(image)   # an SVG actool cannot read fails the whole compile


def test_the_liquid_icon_step_runs_on_the_mac_build_and_never_fails_it():
    script = (ROOT / "packaging" / "make_liquid_icon.sh").read_text()
    assert "actool" in script and "CFBundleIconName" in script
    assert script.count("exit 0") >= 3, "a missing Xcode must not fail the build"
    assert "no $document" in script, "a missing document must not fail it either"
    assert "codesign --force --deep --sign -" in script
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    build = workflow.index("name: Build\n")
    icon = workflow.index("name: Liquid Glass icon")
    works = workflow.index("name: The bundle works")
    assert build < icon < works, "the re-signed bundle is what the self-test must run"


def test_the_bundle_keeps_the_dock_icon_to_itself(monkeypatch):
    """Qt's window icon becomes the Dock icon on macOS and would cover the
    layered one; the bundle leaves the Dock to the bundle."""
    import sys
    from milq import app as app_module
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app_module._bundled_on_macos()
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert not app_module._bundled_on_macos()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert not app_module._bundled_on_macos()


def test_every_identifier_in_the_installer_is_one_wix_will_accept():
    """
    An `Id` is not a name, and the rename did not know the difference.

    `OpenQuantIcon` became `MIL-QIcon` in the pass that renamed everything,
    and WiX takes A-Za-z0-9 with underscores and periods and nothing else:
    the v1.0.0 tag built two installers of three and said
    "'MIL-QIcon' is not a legal identifier" on the Windows runner, minutes
    into a release. The test above asserts the identifier *by name*, so it
    was renamed along with the file and agreed with it. This asserts the
    shape instead, which no rename can satisfy by accident.
    """
    legal = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
    root = ET.parse(ROOT / "packaging" / "milq.wxs").getroot()
    bad = [(element.tag.rsplit("}", 1)[-1], value)
           for element in root.iter()
           for attribute, value in element.attrib.items()
           if attribute in ("Id", "Icon", "Directory", "WorkingDirectory")
           and not legal.match(value)]
    assert not bad, f"WiX will refuse these: {bad}"


# -- what a release serves -------------------------------------------------- #
def test_an_intel_mac_gets_a_build_of_its_own():
    """
    A bundle is the interpreter and every compiled extension for the machine
    that built it, and there is no cross compilation for this — so an Intel
    Mac needs its own runner. `macos-15-intel` is the Intel one;
    `macos-latest` is Apple Silicon. GitHub does not refuse a label it no
    longer has — `macos-13` was retired and a job asking for it sat queued
    for forty minutes — so the label is asserted against the list of the
    ones that exist today, not merely for looking like an Intel one.
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    package = workflow.index("  package:")
    matrix = workflow.index("os: [", package)
    line = workflow[matrix:workflow.index("\n", matrix)]
    intel = {"macos-15-intel", "macos-26-intel"}       # actions/runner-images, 2026-09
    assert any(label in line for label in intel), f"no Intel runner in {line}"
    assert "macos-13" not in line, "macos-13 is retired and queues forever"
    assert "macos-latest" in line, line
    assert "windows-latest" in line and "ubuntu-latest" in line, line
    # the disk image is named from `uname -m`, which is what keeps the two
    # macOS builds from overwriting each other on the release
    assert "$(uname -m)" in (ROOT / "packaging" / "make_dmg.sh").read_text()


def test_two_mac_runners_do_not_share_one_artefact_name():
    """`runner.os` is "macOS" on both of them, so the runner is what names it."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "name: milq-${{ matrix.os }}" in workflow
    assert "name: milq-${{ runner.os }}" not in workflow


def test_the_release_carries_a_list_of_checksums():
    """
    Published beside the installers, and taken over what the release serves
    rather than over what the build produced: the same bytes, but only one of
    them is what a person downloads.
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "\n  checksums:\n" in workflow, "no job publishes the sums"
    job = workflow[workflow.index("\n  checksums:\n"):]
    assert "needs: package" in job, "the sums must wait for every installer"
    assert "gh release download" in job, "sum what the release serves"
    assert "sha256sum MIL-Q-*" in job, "a glob would sum the file being written"
    assert "gh release upload" in job and "SHA256SUMS" in job


def test_windows_gets_a_portable_archive_as_well_as_an_installer():
    """
    A shared machine whose administrator will not run an installer can still
    be given the application: the archive is the same folder the MSI wraps.
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "name: Portable archive" in workflow
    step = workflow[workflow.index("name: Portable archive"):]
    assert "Compress-Archive" in step[:600]
    assert "windows-x64.zip" in step[:600]
    # and it has to travel with the rest: the emptiness check, the artefact,
    # the release upload and the checksums all have to know the extension
    for listing in ("built=(dist/*.dmg dist/*.msi dist/*.zip dist/*.tar.gz)",
                    "dist/*.zip", "--pattern '*.zip'"):
        assert listing in workflow, f"the archive is missing from: {listing}"
    assert workflow.count("built=(dist/*.dmg dist/*.msi dist/*.zip"
                          " dist/*.tar.gz)") == 2


def test_the_build_installs_alpharaw_without_its_dependencies():
    """
    numba stopped publishing x86_64 wheels for macOS, and the Intel build
    of v1.0.2 died trying to compile llvmlite for a package this
    application never imports. alpharaw carries the SCIEX assemblies and
    one small module that finds them; its declared dependencies serve
    readers the spec has excluded since the first release.
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    package = workflow[workflow.index("  package:"):]
    install = package[package.index("name: Install"):package.index("name: Build")]
    assert "pip install --no-deps alpharaw" in install
    assert "pip install --no-deps -e ." in install, (
        "without --no-deps on the package, pip walks alpharaw's requirements again")
    # the application's own dependencies, named in full: what pyproject
    # declares minus alpharaw, plus the packager
    for name in ("numpy", "PyQt6", "pyqtgraph", "pythonnet", "certifi", "pyinstaller"):
        assert name in install, f"{name} is no longer installed for the build"
    spec = (ROOT / "packaging" / "milq.spec").read_text()
    assert '"numba", "llvmlite"' in spec, "the bundle should still exclude them"
