#!/bin/sh
# Registers the unpacked MIL-Q with the desktop: a launcher entry and its
# icon, for the current user only, nothing under /usr. The application runs
# from wherever this folder was unpacked; move the folder and run this again.
#
#     tar xzf MIL-Q-<version>-linux-x86_64.tar.gz
#     ./MIL-Q/install.sh
#
# Undo with:  ./MIL-Q/install.sh --remove
set -e
here=$(cd "$(dirname "$0")" && pwd)
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
if [ "$1" = "--remove" ]; then
    rm -f "$apps/milq.desktop" "$icons/milq.png"
    echo "launcher entry and icon removed"
    exit 0
fi
[ -x "$here/MIL-Q" ] || { echo "MIL-Q binary not found beside this script" >&2; exit 1; }
mkdir -p "$apps" "$icons"
sed "s|INSTALLDIR|$here|g" "$here/milq.desktop" > "$apps/milq.desktop"
cp "$here/milq.png" "$icons/milq.png"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "${icons%/256x256/apps}" 2>/dev/null || true
echo "MIL-Q registered: $apps/milq.desktop -> $here/MIL-Q"
