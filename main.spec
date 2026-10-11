# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('themes/light.json', 'themes'),
        ('themes/dark.json', 'themes'),
        ('audio/audio_effect_default.json', 'audio'),
        ('audio/audio_effects_config.json', 'audio'),
        ('docs/user_guide.md', 'docs'),
        ('docs/bpm_analysis.md', 'docs'),
        ('assets/app-icon.ico', 'assets'),
        ('assets/logo-no-background.png', 'assets'),
        ('assets/icon-small.png', 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Valkyria',
    icon='assets/app-icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
