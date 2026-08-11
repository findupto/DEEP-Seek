@echo off
setlocal
cd /d "%~dp0..\.."

if not exist "dist\DEEP-Seek POS.exe" (
  echo EXE not found. Building it first...
  call build\windows\build_exe.bat
  if errorlevel 1 exit /b 1
)

set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not defined ISCC (
  echo Inno Setup 6 was not found.
  echo Install Inno Setup 6 and run this script again.
  exit /b 1
)

if not exist release mkdir release
"%ISCC%" build\windows\DEEP-Seek.iss
if errorlevel 1 exit /b 1

echo.
echo Installer created in release\
endlocal
