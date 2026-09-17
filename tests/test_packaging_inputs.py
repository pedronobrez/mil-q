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
    assert icon is not None and icon.get("Id") == "MIL-QIcon"
    assert icon.get("SourceFile") == "$(IconFile)"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert 'IconFile="$PWD\\packaging\\icons\\MIL-Q.ico"' in workflow
    assert (ICONS / "MIL-Q.ico").is_file()
    arp = root.find(".//w:Property[@Id='ARPPRODUCTICON']", ns)
    assert arp is not None and arp.get("Value") == "MIL-QIcon"
    shortcut = root.find(".//w:Shortcut", ns)
    assert shortcut.get("Icon") == "MIL-QIcon"


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
