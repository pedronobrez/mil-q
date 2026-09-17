#!/usr/bin/env bash
# Gives the built application a Liquid Glass icon for macOS 26.
#
# A classic .icns is only set inside the system's glass frame on macOS 26
# and keeps its colours whatever appearance the person chose; an icon that
# follows Clear and Tinted has to be a layered Icon Composer document
# (packaging/icons/MIL-Q.icon: a background fill and glass layers)
# compiled by actool from Xcode 26 into Assets.car, named by
# CFBundleIconName. The .icns stays for macOS 15 and earlier, which
# ignore the newer key. Nothing here is fatal: a machine without Xcode 26
# ships the .icns alone and says so.
#
#     bash packaging/make_liquid_icon.sh dist/MIL-Q.app
set -euo pipefail
app="${1:?path to MIL-Q.app}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
document="$here/icons/MIL-Q.icon"

# 1.0.0 ships without one: OpenQuant's layered document drew two co-eluting
# peaks, and MIL-Q's mark has not been redrawn for Icon Composer yet. The
# .icns from the identity kit is what the Dock and the Finder show until it
# is, which is what every macOS before 26 was getting anyway.
if [ ! -d "$document" ]; then
    echo "liquid icon: no $document; the .icns alone ships"
    exit 0
fi

developer="${DEVELOPER_DIR:-}"
if [ -z "$developer" ]; then
    # the runner's default Xcode is 16; the newest 26 on the disk is wanted
    developer="$(ls -d /Applications/Xcode_26*.app /Applications/Xcode.app 2>/dev/null \
        | sort -V | tail -1 || true)"
    [ -n "$developer" ] && developer="$developer/Contents/Developer"
fi
if [ -z "$developer" ] || ! DEVELOPER_DIR="$developer" xcrun --find actool >/dev/null 2>&1; then
    echo "liquid icon: no Xcode with actool found; the .icns alone ships"
    exit 0
fi
version="$(DEVELOPER_DIR="$developer" xcrun actool --version 2>/dev/null | grep -o 'short-bundle-version = [0-9.]*' | grep -o '[0-9.]*$' || true)"
echo "liquid icon: actool ${version:-?} from $developer"

out="$(mktemp -d)"
if ! DEVELOPER_DIR="$developer" xcrun actool "$document" --compile "$out" \
        --output-format human-readable-text --notices --warnings --errors \
        --output-partial-info-plist "$out/icon.plist" \
        --app-icon MIL-Q --include-all-app-icons \
        --enable-on-demand-resources NO --development-region en \
        --target-device mac --minimum-deployment-target 26.0 --platform macosx; then
    echo "liquid icon: actool refused the document; the .icns alone ships"
    exit 0
fi
[ -f "$out/Assets.car" ] || { echo "liquid icon: no Assets.car produced; the .icns alone ships"; exit 0; }
cp "$out/Assets.car" "$app/Contents/Resources/Assets.car"
/usr/libexec/PlistBuddy -c "Add :CFBundleIconName string MIL-Q" "$app/Contents/Info.plist" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :CFBundleIconName MIL-Q" "$app/Contents/Info.plist"
# a resource added after PyInstaller's ad-hoc signature breaks the seal;
# the same ad-hoc signature, applied again, is what Apple Silicon needs
codesign --force --deep --sign - "$app" 2>&1 | tail -1 || true
echo "liquid icon: Assets.car added ($(du -h "$out/Assets.car" | cut -f1)), CFBundleIconName = MIL-Q"
rm -rf "$out"
