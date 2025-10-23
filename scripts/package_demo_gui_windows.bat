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
echo Copying Python runtime files...

for /f "usebackq delims=" %%i in (`python -c "import sys, pathlib; dll_name=f'python{sys.version_info.major}{sys.version_info.minor}.dll'; print(pathlib.Path(sys.base_prefix)/dll_name)"`) do set "PY_DLL=%%i"
if not defined PY_DLL goto :noPythonDll

if exist "%PY_DLL%" (
    copy /y "%PY_DLL%" "dist\jx3calc_windows\" >nul
) else (
    echo [WARN] Could not find %PY_DLL%. The packaged app may fail to start.
)

for /f "usebackq delims=" %%i in (`python -c "import sys, pathlib; base=pathlib.Path(sys.base_prefix); matches=sorted(base.glob('vcruntime*.dll')); print(matches[-1] if matches else '')"`) do set "VC_DLL=%%i"
if defined VC_DLL if exist "%VC_DLL%" (
    copy /y "%VC_DLL%" "dist\jx3calc_windows\" >nul
) else (
    if defined VC_DLL (
        echo [WARN] Could not find Microsoft VC runtime DLL. Ensure VC redistributable is installed on target machines.
    ) else (
        echo [WARN] No vcruntime*.dll detected in the interpreter prefix. Target machines may require the VC++ redistributable.
    )
)

echo Build finished. The executable is located in dist\jx3calc_windows\jx3calc_windows.exe

echo You must ship the entire dist\jx3calc_windows directory (including the _internal folder).
echo The script also copies the Python DLL and VC runtime beside the executable for reliability.

echo.
popd
endlocal
goto :eof

:noPythonDll
echo [ERROR] Unable to locate the interpreter's pythonXY.dll. Ensure you are using a CPython interpreter.
popd
endlocal
exit /b 1
