#!/usr/bin/env bash
# Build MIL-Q.app and wrap it in a disk image.
#
# The image is unsigned. That is not what makes macOS complain: Gatekeeper
# reacts to the com.apple.quarantine attribute, which is attached by whatever
# downloads a file, not by whatever builds it. An image built here and mounted
# here opens with no dialog at all. One that travels — mail, AirDrop, a
# browser — will ask, and the reader can right-click Open once, or run
#     xattr -dr com.apple.quarantine /Applications/MIL-Q.app
#
# Apple Silicon does insist on *some* signature or the binary will not start;
# the ad-hoc one PyInstaller applies is enough and costs nothing.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"
dist="${1:-$root/dist}"
version="$(python3 -c "import re,pathlib;print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('$root/milq/__init__.py').read_text()).group(1))")"
dmg="$dist/MIL-Q-$version-macos-$(uname -m).dmg"

app="$dist/MIL-Q.app"
if [ -d "$app" ]; then
    echo "==> using the application already in $dist"
else
    echo "==> building the application"
    python3 -m PyInstaller "$here/milq.spec" --noconfirm \
        --distpath "$dist" --workpath "$dist/.build"
fi

[ -d "$app" ] || { echo "no $app was produced" >&2; exit 1; }

echo "==> checking it runs before shipping it"
"$app/Contents/MacOS/MIL-Q" --selftest

echo "==> staging"
stage="$dist/.dmg"
rm -rf "$stage" "$dmg"
mkdir -p "$stage"
cp -R "$app" "$stage/"
ln -s /Applications "$stage/Applications"

echo "==> creating $dmg"
hdiutil create -volname "MIL-Q $version" -srcfolder "$stage" \
    -ov -format UDZO "$dmg" >/dev/null
rm -rf "$stage"

echo
echo "$dmg"
du -h "$dmg" | cut -f1 | xargs echo "size:"
