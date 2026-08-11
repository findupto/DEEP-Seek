@echo off
setlocal EnableExtensions
cd /d "%~dp0..\.."

if errorlevel 1 (
  echo ERROR: Could not enter repository root.
  exit /b 1
)

echo === DEEP-Seek POS: building Windows EXE ===
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher ^(py^) is required. Install Python 3.11+ and try again.
  exit /b 1
)

py -m pip install --upgrade pip
if errorlevel 1 exit /b 1
py -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py -m pip install pyinstaller
if errorlevel 1 exit /b 1

rem IMPORTANT: do NOT delete the repository's build\windows folder because it
rem contains this script and the PyInstaller .spec file. Use a separate temp
rem work directory instead.
if exist build\pyinstaller-temp rmdir /s /q build\pyinstaller-temp
if exist dist rmdir /s /q dist
if exist dist mkdir dist

py -m PyInstaller --clean --noconfirm --workpath build\pyinstaller-temp --distpath dist build\windows\DEEP-Seek.spec
if errorlevel 1 (
  echo.
  echo ERROR: PyInstaller failed. The temporary build files were kept at:
  echo        build\pyinstaller-temp
  exit /b 1
)

if not exist "dist\DEEP-Seek POS.exe" (
  echo ERROR: PyInstaller finished but the EXE was not created.
  exit /b 1
)

echo.
echo ========================================
echo EXE BUILD SUCCESSFUL
echo ========================================
echo.
echo EXE: %CD%\dist\DEEP-Seek POS.exe
echo.
echo Next step:
echo   build\windows\build_installer.bat
endlocal
exit /b 0
