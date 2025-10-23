@echo off
setlocal enabledelayedexpansion

REM Package the Tkinter demo GUI into a standalone Windows executable using PyInstaller.
REM Usage: double-click or run from a Developer Command Prompt after installing pyinstaller.

set ROOT=%~dp0..\
pushd "%ROOT%"

if not exist "%ROOT%example\simulator\gui.py" (
    echo [ERROR] Could not locate example\simulator\gui.py relative to this script.
    exit /b 1
)

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller is not installed or not on PATH.
    echo         Run: pip install pyinstaller
    popd
    exit /b 1
)

echo Packaging Tkinter GUI...
pyinstaller ^
  --noconsole ^
  --clean ^
  --name jx3calc_windows ^
  --add-data "example\simulator\data;example/simulator/data" ^
  example\simulator\gui.py

if errorlevel 1 (
    echo [ERROR] PyInstaller reported a failure.
    popd
    exit /b 1
)

echo.
echo Build finished. The executable is located in dist\jx3calc_windows\jx3calc_windows.exe

echo You can copy the entire dist\jx3calc_windows directory to another machine.
echo The data subdirectory is bundled automatically so the simulator can load presets.

echo.
popd
endlocal
