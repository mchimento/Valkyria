@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

set "VENV_PY=%REPO_ROOT%\.env\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo Error: %VENV_PY% not found.
    echo Create the venv first, e.g.:
    echo     python -m venv .env
    echo     .env\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo Ensuring PyInstaller is installed...
"%VENV_PY%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    "%VENV_PY%" -m pip install pyinstaller
    if errorlevel 1 (
        echo Error: failed to install PyInstaller.
        exit /b 1
    )
)

echo Building dist\Valkyria.exe with PyInstaller...
pushd "%REPO_ROOT%"
"%VENV_PY%" -m PyInstaller main.spec
if errorlevel 1 (
    echo Error: PyInstaller build failed.
    popd
    exit /b 1
)
popd

set "ISCC="
where ISCC.exe >nul 2>&1
if %errorlevel%==0 (
    set "ISCC=ISCC.exe"
) else if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo Error: ISCC.exe ^(Inno Setup Compiler^) not found.
    echo Install Inno Setup from https://jrsoftware.org/isinfo.php and re-run this script.
    exit /b 1
)

echo Compiling installer with "%ISCC%"...
"%ISCC%" "%SCRIPT_DIR%valkyria.iss"
if errorlevel 1 (
    echo Error: Inno Setup compilation failed.
    exit /b 1
)

echo.
echo Done. Installer is in dist\installer\
endlocal
