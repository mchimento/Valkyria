#!/usr/bin/env bash
# Builds dist/Valkyria with PyInstaller and packages it into a portable
# Valkyria-<version>-x86_64.AppImage, in one step — always a fresh build
# from the current source, never repackaging a stale dist/Valkyria left
# over from an earlier run (that silently baked in an old version once).
# Requires appimagetool on PATH — get it from
# https://github.com/AppImage/AppImageKit/releases (download the
# appimagetool-x86_64.AppImage, chmod +x it, and put it on your PATH,
# e.g. as /usr/local/bin/appimagetool) and re-run this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BINARY="$REPO_ROOT/dist/Valkyria"
APPDIR="$SCRIPT_DIR/build/Valkyria.AppDir"
ICON="$REPO_ROOT/assets/icon-small.png"
VENV_PY="$REPO_ROOT/.env/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "Error: $VENV_PY not found." >&2
    echo "Create the venv first, e.g.:" >&2
    echo "    python3 -m venv .env && .env/bin/pip install -r requirements.txt" >&2
    exit 1
fi

if ! command -v appimagetool >/dev/null 2>&1; then
    echo "Error: appimagetool not found on PATH." >&2
    echo "Get it from https://github.com/AppImage/AppImageKit/releases" >&2
    echo "(download appimagetool-x86_64.AppImage, chmod +x it, and put it on your PATH)." >&2
    exit 1
fi

if ! "$VENV_PY" -m pip show pyinstaller >/dev/null 2>&1; then
    echo "Installing PyInstaller into .env..."
    "$VENV_PY" -m pip install pyinstaller
fi

echo "Building $BINARY with PyInstaller..."
(cd "$REPO_ROOT" && "$VENV_PY" -m PyInstaller main.spec)

VERSION="$(cd "$REPO_ROOT" && "$VENV_PY" -c "from app.version import __version__; print(__version__)")"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp "$BINARY" "$APPDIR/usr/bin/Valkyria"
cp "$SCRIPT_DIR/valkyria.desktop" "$APPDIR/valkyria.desktop"
cp "$ICON" "$APPDIR/valkyria.png"
ln -sf valkyria.png "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/Valkyria" "$@"
EOF
chmod +x "$APPDIR/AppRun"

mkdir -p "$REPO_ROOT/dist"
OUTPUT="$REPO_ROOT/dist/Valkyria-$VERSION-x86_64.AppImage"
appimagetool "$APPDIR" "$OUTPUT"

# Copied alongside the AppImage (not just left in packaging/) so the
# three can be zipped up and handed to end users as a ready-to-run set —
# see install_appimage.sh's own docstring for how it finds its match.
cp "$SCRIPT_DIR/install_appimage.sh" "$REPO_ROOT/dist/install_appimage.sh"
cp "$SCRIPT_DIR/uninstall_appimage.sh" "$REPO_ROOT/dist/uninstall_appimage.sh"

echo "Built $OUTPUT"
echo "Copied install_appimage.sh and uninstall_appimage.sh next to it — distribute all three together."
