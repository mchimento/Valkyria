#!/usr/bin/env bash
# Installs the .desktop launcher for a build already produced by
# `pyinstaller main.spec` — run this after building, not instead of it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DESKTOP_FILE="$SCRIPT_DIR/valkyria.desktop"
BINARY="$REPO_ROOT/dist/Valkyria"
APPLICATIONS_DIR="$HOME/.local/share/applications"

if [ ! -f "$BINARY" ]; then
    echo "Warning: $BINARY not found — build it first with:" >&2
    echo "    pyinstaller main.spec" >&2
fi

mkdir -p "$APPLICATIONS_DIR"
cp "$DESKTOP_FILE" "$APPLICATIONS_DIR/"
echo "Installed $APPLICATIONS_DIR/valkyria.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR"
    echo "Refreshed desktop database"
else
    echo "update-desktop-database not found — skipping cache refresh (usually not required)"
fi

echo "Done. Launch Valkyria from your application menu/search, not by running the binary directly, for the icon to resolve correctly."
