@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0..\.."
if errorlevel 1 (
  echo ERROR: Could not enter repository root.
  exit /b 1
)

echo ========================================================
echo   DEEP-Seek POS - Automatic Windows EXE Builder
echo ========================================================
echo.

rem PyInstaller's Tkinter runtime hook in the current stable toolchain can
rem fail with Python 3.14/Tcl-Tk 9 (_tcl_data missing). For a reproducible
rem Windows build, prefer Python 3.13, whose official Windows distribution
rem uses the Tk layout supported by the stable PyInstaller toolchain.
set "PYEXE="

where py >nul 2>nul
if not errorlevel 1 (
  py -3.13 -c "import sys; print(sys.version)" >nul 2>nul
  if not errorlevel 1 set "PYEXE=py -3.13"
)

if not defined PYEXE (
  echo Python 3.13 was not found. Attempting automatic installation...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo ERROR: winget is unavailable and Python 3.13 is not installed.
    echo Install Python 3.13 from python.org, then rerun this script.
    exit /b 1
  )
  winget install --id Python.Python.3.13 -e --scope user --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo ERROR: Automatic Python 3.13 installation failed.
    exit /b 1
  )
  py -3.13 -c "import sys; print(sys.version)" >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python 3.13 was installed but the py launcher cannot find it yet.
    echo Close this CMD window, open a new CMD, and run this script again.
    exit /b 1
  )
  set "PYEXE=py -3.13"
)

echo Using Python:
%PYEXE% --version

rem Verify Tkinter before installing/building anything.
%PYEXE% -c "import tkinter; r=tkinter.Tk(); print('Tk:', r.tk.call('info','patchlevel')); r.destroy()"
if errorlevel 1 (
  echo ERROR: Tkinter is unavailable in Python 3.13.
  echo Reinstall Python 3.13 with 'tcl/tk and IDLE' enabled.
  exit /b 1
)

rem Create an isolated build environment so global Python packages cannot
rem break the build.
set "VENV=.build-venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo Creating isolated build environment...
  %PYEXE% -m venv "%VENV%"
  if errorlevel 1 exit /b 1
)

set "VENVPY=%CD%\%VENV%\Scripts\python.exe"
"%VENVPY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

if exist requirements.txt (
  "%VENVPY%" -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
)

"%VENVPY%" -m pip install --upgrade "pyinstaller>=6.21,<7"
if errorlevel 1 exit /b 1

rem Never delete build\windows: it contains this script and the spec.
if exist build\pyinstaller-temp rmdir /s /q build\pyinstaller-temp
if exist dist rmdir /s /q dist
mkdir dist >nul 2>nul

rem Clean PyInstaller's user cache as well, preventing stale Tk hooks.
if exist "%LOCALAPPDATA%\pyinstaller" rmdir /s /q "%LOCALAPPDATA%\pyinstaller"

"%VENVPY%" -m PyInstaller --clean --noconfirm --workpath build\pyinstaller-temp --distpath dist build\windows\DEEP-Seek.spec
if errorlevel 1 (
  echo.
  echo ERROR: PyInstaller failed. Build diagnostics remain in:
  echo        build\pyinstaller-temp
  exit /b 1
)

if not exist "dist\DEEP-Seek POS.exe" (
  echo ERROR: PyInstaller finished but the EXE was not created.
  exit /b 1
)

echo.
echo ========================================================
echo   EXE BUILD SUCCESSFUL
 echo ========================================================
echo EXE: %CD%\dist\DEEP-Seek POS.exe
echo.
echo Next:
echo   build\windows\build_installer.bat
endlocal
exit /b 0
