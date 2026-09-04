#!/usr/bin/env bash
# Integrates a Valkyria AppImage into the desktop app menu/taskbar.
# Running the AppImage itself never does this — that's normal AppImage
# behavior (portable, no install step), not a bug — so this is a
# separate, optional step for whoever wants a menu entry too.
#
# Works standalone: doesn't need this repo checked out, only the
# .AppImage file itself (its icon is extracted from the AppImage, not
# read from assets/). Meant to be distributed as a pair with the
# AppImage — with no path argument, it looks for exactly one
# Valkyria*.AppImage sitting next to this script (not in this repo's
# dist/, so it doesn't assume the repo is even present), so dropping both
# files in the same folder and running this one is enough.
#
# Usage: install_appimage.sh [-y|--yes] [/path/to/Valkyria.AppImage]
# -y/--yes skips the confirmation prompt, for scripted/automated use.
set -euo pipefail

ASSUME_YES=0
APPIMAGE=""
for arg in "$@"; do
    case "$arg" in
        -y|--yes) ASSUME_YES=1 ;;
        *) APPIMAGE="$arg" ;;
    esac
done

if [ -z "$APPIMAGE" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    MATCHES=("$SCRIPT_DIR"/Valkyria*.AppImage)
    if [ ! -e "${MATCHES[0]}" ]; then
        echo "Error: no AppImage given and none found next to this script ($SCRIPT_DIR)." >&2
        echo "Usage: $0 [-y|--yes] /path/to/Valkyria.AppImage" >&2
        exit 1
    elif [ "${#MATCHES[@]}" -gt 1 ]; then
        echo "Error: multiple AppImages found next to this script — pass one explicitly:" >&2
        printf '  %s\n' "${MATCHES[@]}" >&2
        exit 1
    fi
    APPIMAGE="${MATCHES[0]}"
fi

if [ ! -f "$APPIMAGE" ]; then
    echo "Error: $APPIMAGE not found." >&2
    exit 1
fi
APPIMAGE="$(cd "$(dirname "$APPIMAGE")" && pwd)/$(basename "$APPIMAGE")"

BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons"
APPLICATIONS_DIR="$HOME/.local/share/applications"
INSTALLED_APPIMAGE="$BIN_DIR/Valkyria.AppImage"
INSTALLED_ICON="$ICON_DIR/valkyria.png"

echo "This will:"
echo "  - Copy $APPIMAGE"
echo "      to $INSTALLED_APPIMAGE"
echo "  - Write an icon to $INSTALLED_ICON"
echo "  - Write a menu entry to $APPLICATIONS_DIR/valkyria.desktop"
if [ "$ASSUME_YES" -ne 1 ]; then
    read -r -p "Proceed? [Y/n] " reply
    case "$reply" in
        ""|[Yy]*) ;;
        *) echo "Cancelled."; exit 0 ;;
    esac
fi

mkdir -p "$BIN_DIR" "$ICON_DIR" "$APPLICATIONS_DIR"
cp "$APPIMAGE" "$INSTALLED_APPIMAGE"
chmod +x "$INSTALLED_APPIMAGE"
echo "Copied to $INSTALLED_APPIMAGE"

EXTRACT_DIR="$(mktemp -d)"
trap 'cd /; rm -rf "$EXTRACT_DIR"' EXIT
ICON_ARG="valkyria"
if (cd "$EXTRACT_DIR" && "$INSTALLED_APPIMAGE" --appimage-extract valkyria.png >/dev/null 2>&1) \
        && [ -f "$EXTRACT_DIR/squashfs-root/valkyria.png" ]; then
    cp "$EXTRACT_DIR/squashfs-root/valkyria.png" "$INSTALLED_ICON"
    ICON_ARG="$INSTALLED_ICON"
    echo "Extracted icon to $INSTALLED_ICON"
else
    echo "Warning: couldn't extract an icon from the AppImage; menu entry will use a generic one." >&2
fi

cat > "$APPLICATIONS_DIR/valkyria.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Valkyria
Comment=Desktop audio player
Exec=$INSTALLED_APPIMAGE
Icon=$ICON_ARG
Terminal=false
Categories=AudioVideo;Audio;Player;Qt;
StartupWMClass=Valkyria
EOF
echo "Installed $APPLICATIONS_DIR/valkyria.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR"
    echo "Refreshed desktop database"
fi

echo "Done. Launch Valkyria from your application menu/search."
