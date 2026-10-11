; Inno Setup script for Valkyria. Compile with ISCC.exe (Inno Setup's
; compiler, Windows-only) after building dist\Valkyria.exe via
; `pyinstaller main.spec`. Output goes to dist\installer\.
;
; MyAppVersion must be bumped by hand alongside app/version.py at release
; time — Inno Setup scripts can't read it from the Python source.
#define MyAppName "Valkyria"
#define MyAppVersion "0.2.1"
#define MyAppPublisher "Jesus Mauricio Chimento"
#define MyAppExeName "Valkyria.exe"

[Setup]
; Fixed, never change across releases — Inno Setup uses this (not the
; version) to recognize "this is an upgrade of the same app" and offer to
; replace an existing install rather than doing a side-by-side one.
AppId={{ABD7E82A-3EE3-4147-BC16-853A32C8B310}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\..\dist\installer
OutputBaseFilename=ValkyriaSetup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
LicenseFile=..\..\LICENSE
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
