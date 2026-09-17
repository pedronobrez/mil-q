# PyInstaller build, shared by all three systems.
#
# Two things are not obvious and both fail late — the bundle builds, and then
# the first .wiff will not open:
#
#   * SCIEX's Clearcore2 assemblies ship as package data inside alpharaw, in
#     alpharaw/ext/sciex. PyInstaller follows imports, not data directories, so
#     without collecting them explicitly the .NET side has nothing to load.
#   * pythonnet needs its own runtime shim (clr_loader) and the clr module,
#     neither of which is reachable by static analysis.
#
# Everything alpharaw drags in for file formats we never touch is excluded.
# numba and llvmlite are named among them: nothing reaches them any more (see
# bootstrap._load_clearcore), and they were 123 MB of a 247 MB bundle, so the
# exclusion is here to make sure an import cannot creep back in unnoticed.
#
# Build:  pyinstaller packaging/milq.spec --noconfirm

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

MACOS = sys.platform == "darwin"
WINDOWS = sys.platform.startswith("win")

# the suite's mark, drawn by OpenDIAL's generator through packaging/make_icon.py and committed
# here so a build needs nothing from the other repository; .icns for the bundle, .ico for Windows
ICONS = Path(SPECPATH) / "icons"
ICON = str(ICONS / ("MIL-Q.ico" if WINDOWS else "MIL-Q.icns")) if (ICONS / "MIL-Q.icns").is_file() else None

# read rather than repeat: a version written here as well as in the package
# is a version that will disagree with itself at the first bump
VERSION = re.search(
    r'__version__ = "([^"]+)"',
    (Path(SPECPATH).parent / "milq" / "__init__.py").read_text(),
).group(1)

# the vendor assemblies, kept at the same relative path the code expects.
# Only SCIEX: alpharaw also ships Bruker and Thermo readers this app has no
# way to use, and they are 17 MB of the bundle.
vendor = [
    (source, dest)
    for source, dest in collect_data_files("alpharaw", subdir="ext",
                                           include_py_files=False)
    if "bruker" not in dest and "thermo" not in dest.lower()
]

# the manual: Markdown pages read at run time from next to the package.
# The whole tree goes, so the translations — help/pages/pt — travel with the
# originals; naming the directory rather than a glob is what makes that true,
# and a bundle without them is a manual whose language switch shows English.
vendor.append((str(Path(SPECPATH).parent / "milq" / "help" / "pages"),
               "milq/help/pages"))
vendor.append((str(Path(SPECPATH).parent / "milq" / "icon.png"), "milq"))

hidden = [
    "clr_loader",
    "clr_loader.util",
    "pythonnet",
    *collect_submodules("clr_loader"),
]

# alpharaw declares these for readers this app does not use. Confirmed by
# importing the SCIEX reader and watching what actually loads.
excluded = [
    "numba", "llvmlite",
    "pandas", "h5py", "alphabase", "pyteomics", "lxml", "pyzstd",
    "matplotlib", "IPython", "jupyter", "notebook", "pytest", "tkinter",
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.Qt3DCore",
    "PyQt6.QtBluetooth", "PyQt6.QtMultimedia", "PyQt6.QtQuick", "PyQt6.QtQml",
]

analysis = Analysis(
    ["../run.py"],
    pathex=[str(Path(SPECPATH).parent)],
    binaries=[],
    datas=vendor,
    hiddenimports=hidden,
    excludes=excluded,
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MIL-Q",
    console=False,
    # an unsigned arm64 binary will not start at all; ad-hoc is enough and
    # costs nothing, and is what a locally built app gets anyway
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="MIL-Q",
)

if MACOS:
    app = BUNDLE(
        collection,
        name="MIL-Q.app",
        icon=ICON,
        bundle_identifier="io.github.pedronobrez.milq",
        info_plist={
            "CFBundleName": "MIL-Q",
            "CFBundleDisplayName": "MIL-Q",
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            # the window follows the system light or dark setting
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "SCIEX raw data",
                    "CFBundleTypeExtensions": ["wiff"],
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeName": "MIL-Q project",
                    "CFBundleTypeExtensions": ["oqproj"],
                    "CFBundleTypeRole": "Editor",
                },
            ],
        },
    )
