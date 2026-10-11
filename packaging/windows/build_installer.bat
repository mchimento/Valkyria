@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

set "VENV_PY=%REPO_ROOT%\.env\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo No build environment found at "%REPO_ROOT%\.env" — setting one up automatically...

    set "BOOTSTRAP_PY="
    where py >nul 2>&1
    if !errorlevel!==0 (
        py -3 -c "print(1)" >nul 2>&1
        if !errorlevel!==0 set "BOOTSTRAP_PY=py -3"
    )
    if "!BOOTSTRAP_PY!"=="" (
        where python >nul 2>&1
        if !errorlevel!==0 (
            python -c "print(1)" >nul 2>&1
            if !errorlevel!==0 set "BOOTSTRAP_PY=python"
        )
    )
    if "!BOOTSTRAP_PY!"=="" (
        echo Error: no working Python interpreter found on PATH.
        echo Install Python 3.10+ from https://www.python.org/downloads/windows/
        echo ^(check "Add python.exe to PATH" during install^), then re-run this script.
        exit /b 1
    )

    !BOOTSTRAP_PY! -m venv "%REPO_ROOT%\.env"
    if errorlevel 1 (
        echo Error: failed to create the virtual environment.
        exit /b 1
    )
    if not exist "%VENV_PY%" (
        echo Error: virtual environment created but %VENV_PY% is missing.
        exit /b 1
    )

    echo Installing dependencies from requirements.txt ^(this may take a few minutes the first time^)...
    "%VENV_PY%" -m pip install --upgrade pip >nul
    "%VENV_PY%" -m pip install -r "%REPO_ROOT%\requirements.txt"
    if errorlevel 1 (
        echo Error: failed to install dependencies from requirements.txt.
        exit /b 1
    )
    echo Build environment ready.
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
) else if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" (
    REM per-user install location used by `winget install JRSoftware.InnoSetup`
    set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
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
