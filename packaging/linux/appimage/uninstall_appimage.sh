#!/usr/bin/env bash
# Removes exactly what install_appimage.sh writes — nothing else on the
# system is touched by that script, so this is a full undo of it.
#
# Usage: uninstall_appimage.sh [-y|--yes]
set -euo pipefail

ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes) ASSUME_YES=1 ;;
    esac
done

INSTALLED_APPIMAGE="$HOME/.local/bin/Valkyria.AppImage"
INSTALLED_ICON="$HOME/.local/share/icons/valkyria.png"
DESKTOP_FILE="$HOME/.local/share/applications/valkyria.desktop"

TARGETS=()
for f in "$INSTALLED_APPIMAGE" "$INSTALLED_ICON" "$DESKTOP_FILE"; do
    [ -e "$f" ] && TARGETS+=("$f")
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
    echo "Nothing to remove — Valkyria doesn't look installed."
    exit 0
fi

echo "This will remove:"
printf '  %s\n' "${TARGETS[@]}"
if [ "$ASSUME_YES" -ne 1 ]; then
    read -r -p "Proceed? [Y/n] " reply
    case "$reply" in
        ""|[Yy]*) ;;
        *) echo "Cancelled."; exit 0 ;;
    esac
fi

rm -f "${TARGETS[@]}"
echo "Removed."

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "Refreshed desktop database"
fi
