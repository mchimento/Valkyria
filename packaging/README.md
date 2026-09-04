# Packaging

All platforms start from the same PyInstaller build:

```bash
./.env/bin/pip install pyinstaller   # once, if not already installed
./.env/bin/pyinstaller main.spec
```

This must run on the target OS — a Linux machine produces `dist/Valkyria`,
a Windows machine produces `dist\Valkyria.exe`. PyInstaller doesn't
cross-compile between platforms.

## Windows: installer (Inno Setup)

Requires [Inno Setup](https://jrsoftware.org/isinfo.php) installed on the
Windows machine building the app. Bump `MyAppVersion` in
`packaging\windows\valkyria.iss` to match `app/version.py` first (Inno
Setup can't read the Python source directly), then run:

```
packaging\windows\build_installer.bat
```

This builds `dist\Valkyria.exe` with PyInstaller (installing PyInstaller
into `.env` first if it isn't already there) and compiles the installer
in one step — no need to run PyInstaller separately first. It looks for
`ISCC.exe` on `PATH` and in Inno Setup's default install locations under
Program Files.

Output: `dist\installer\ValkyriaSetup-<version>.exe` — a normal installer
wizard with Start Menu shortcut, optional desktop icon, and an uninstaller
registered in Add/Remove Programs.

## Linux: AppImage (portable, no install step for end users)

Requires `appimagetool` on `PATH` — download
`appimagetool-x86_64.AppImage` from the
[AppImageKit releases page](https://github.com/AppImage/AppImageKit/releases),
`chmod +x` it, and put it somewhere on `PATH` (e.g.
`/usr/local/bin/appimagetool`).

```bash
packaging/linux/appimage/build_appimage.sh
```

Output: `dist/Valkyria-<version>-x86_64.AppImage`, alongside copies of
`install_appimage.sh` and `uninstall_appimage.sh` placed next to it
automatically (version read automatically from `app/version.py`). That
AppImage is a single file that runs on most distros without root or a
package manager. Running it launches the app directly with **no install
step** — that's normal AppImage behavior, not a bug. It won't appear in
the app menu/taskbar on its own.

The three files in `dist/` are meant to be distributed together — zip up
`dist/` (or just those three files) and hand it to end users. Whoever
downloads it runs:

```bash
./install_appimage.sh [-y|--yes]
```

which finds the AppImage sitting next to itself (errors out, listing
candidates, if more than one is present — pass a path explicitly to
disambiguate). It works standalone: no dependency on this repo being
checked out, only the files sitting next to it. It prints what it's
about to do and asks for confirmation before touching anything;
`-y`/`--yes` skips the prompt for scripted/automated use. It copies the
AppImage to `~/.local/bin/Valkyria.AppImage`, extracts its icon (no
dependency on `assets/`), and registers a `.desktop` entry — re-running
it after a new build just overwrites all three.

To remove everything `install_appimage.sh` wrote:

```bash
./uninstall_appimage.sh [-y|--yes]
```

Same confirm-before-acting/`-y` behavior; reports "nothing to remove" if
it's not installed rather than erroring.

## Linux: raw binary + desktop entry (for this dev machine / manual use)

What was already being used before the AppImage existed — installs a
`.desktop` launcher pointing at the already-built `dist/Valkyria`, rather
than producing a separate distributable artifact:

```bash
packaging/linux/install_linux.sh
```

See `packaging/linux/valkyria.desktop`.
