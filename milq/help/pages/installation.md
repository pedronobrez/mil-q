---
title: Installation
---
MIL-Q is developed and used on macOS, Apple Silicon included. The test
suite and the application start on Linux and Windows in continuous
integration, and installers are built for all three; reading a `.wiff` has
only been verified on macOS, because that path loads SCIEX's .NET assemblies
and the other two platforms are checked only as far as "the assemblies
load". See [[how-wiff-is-read]].

## Installers

Every release on GitHub carries three files; what came in each one is in
[[version-history]]:

| File | Platform | Notes |
|---|---|---|
| `MIL-Q-<version>-macos-arm64.dmg` | macOS on Apple Silicon | drag the application to Applications |
| `MIL-Q-<version>.msi` | Windows 10 1703 or newer | a standard installer |
| `MIL-Q-<version>-linux-x86_64.tar.gz` | Linux | unpack and run `MIL-Q/MIL-Q`; `MIL-Q/install.sh` adds a launcher entry |

The application icon — the suite's mark, a white peak with a blue neighbour —
is on all three: the macOS bundle carries it as `MIL-Q.icns`, the Windows
executable carries it in its resources (checked by reading them back from
the built installer: the same six images as the `.ico`, 16 to 256 pixels)
and the Start menu entry and *Add or remove programs* name it, and the Linux
tarball ships `milq.png` with a `.desktop` entry. The window itself
takes its icon from the same drawing on every platform.

### macOS 26 and the Liquid Glass icon

On macOS 26 a classic `.icns` is only set inside the system's glass frame
and keeps its colours whatever appearance is chosen — which is why, with the
*Clear* or *Tinted* icon style on, every icon turned translucent and this
one stayed blue. From 0.7.8 to 0.10.1 the bundle also carried a layered icon: an
Icon Composer document compiled by Xcode 26's `actool` into `Assets.car`
and named by `CFBundleIconName`, so the Dock and the Finder rendered it in
the chosen style. **1.0.0 ships without one.** The document drew
OpenQuant's two co-eluting peaks and MIL-Q's mark has not been redrawn for
Icon Composer; the `.icns` is what the Dock and the Finder show until it
is, which is what every macOS before 26 was getting anyway. The build step
is still there and says so. The `.icns` stays for macOS 15
and earlier, which ignore the newer key. The build says on its log whether
the layered icon was compiled; a machine without Xcode 26 ships the
`.icns` alone. One more thing was needed, found on the first build that
carried the layered icon: the system drew it in glass, and the Dock kept
showing the blue square for as long as the application ran, because Qt
hands a window icon to the Dock as the application icon and a flat PNG
covered the layered one. Inside the bundle the application no longer sets
a window icon; the bundle owns it.

### Linux: a launcher entry, for one user

The tarball is the application folder as PyInstaller built it, and Linux has
no bundle to give an icon to. `install.sh` inside the folder writes a
`.desktop` entry under `~/.local/share/applications` pointing at the folder
where it was unpacked, and the icon under `~/.local/share/icons`, so the
application appears in the launcher and the dock with its icon; nothing
under `/usr` is touched, and `install.sh --remove` undoes it. Move the
folder and run it again.

### macOS and the quarantine flag

The disk image is unsigned. That is not what makes macOS complain:
Gatekeeper reacts to the `com.apple.quarantine` attribute, which is attached
by whatever downloads a file — a browser, Mail, AirDrop — not by whatever
builds it. Either right-click the application and choose **Open** once, or
clear the flag:

```
xattr -dr com.apple.quarantine /Applications/MIL-Q.app
```

Apple Silicon insists on *some* signature or the binary will not start; the
ad-hoc signature the build applies is enough.

### Windows: 10 1703 or newer, and not under Wine

`Qt6Core.dll` in the PyQt6 wheel imports eighteen `ucnv_*` symbols from
`icuuc.dll`, ICU's converter library, and the wheel ships no ICU of its own
because Windows has provided one in `System32` since that release. Wine and
CrossOver implement neither, so the application stops at import with
*"DLL load failed while importing QtCore: Module not found"*, which reads
like a broken installer and is not one. A stub library that satisfies those
eighteen symbols exists in the source repository under `packaging/wine/`
and is deliberately **not** in the installer: on a real Windows machine an
application-local `icuuc.dll` would be found before the genuine one.

The installer has been built and started on a GitHub Windows runner, and
the Windows build has read a real acquisition under CrossOver with the stub
in place, giving the same numbers as the macOS build. It has not been
installed on a physical Windows machine by the authors; see
[[troubleshooting]] if it misbehaves there.

## From source

```
git clone https://github.com/pedronobrez/mil-q
cd milq
python3 -m pip install -r requirements.txt
python3 -m milq.bootstrap --install
python3 run.py
```

The requirements are numpy, PyQt6, pyqtgraph, alpharaw (which carries the
SCIEX Clearcore2 assemblies), pythonnet and certifi. Python 3.11 or newer.

The bootstrap command is needed once, and only when the machine has no .NET
8 runtime: it downloads Microsoft's `dotnet-install` script and installs a
runtime of about 30 MB into `~/.dotnet`. It also fetches from NuGet the
compatibility assemblies that .NET Core does not ship and Clearcore2 needs
(`System.Configuration.ConfigurationManager` and its dependencies), caching
them under the application's home directory. Without a runtime, mzML files
still open; `.wiff` files report that the SCIEX libraries are unavailable.

## Where things are kept

| What | Where |
|---|---|
| the .NET runtime | `~/.dotnet` |
| downloaded assemblies, the LIPID MAPS index | `~/.milq` (override with the `OPENPEAKVIEW_HOME` environment variable) |
| preferences: window geometry, last folder, folded panels, the start prompt | the platform's settings store, under `MIL-Q/MIL-Q` |
| projects | wherever they were saved: `.oqproj` files, see [[projects-and-files]] |

## LIPID MAPS

The lipid database is not bundled. The first use of the **LIPID MAPS** tab
in the Explorer offers to download it: one 21 MB file from lipidmaps.org
becomes a 45 MB local index of 49,969 curated structures, after which
lookups need no network. See [[lipid-maps]].

## Checking an installation

```
MIL-Q --selftest file.wiff
```

reports the version, the platform, whether the LIPID MAPS index is
installed, whether the SCIEX libraries load and where the .NET runtime was
found, and then opens each file named and prints what was read. See
[[command-line]].
