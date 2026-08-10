@echo off
setlocal
cd /d "%~dp0"

echo === MK Pizza & Ice Bar - Windows EXE Build ===
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo Building windowed EXE with MK icon...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "MK Pizza & Ice Bar" --icon "assets\mk_pizza.ico" --add-data "assets;assets" run_pos.py
if errorlevel 1 exit /b 1

echo.
echo EXE created: dist\MK Pizza & Ice Bar.exe
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
  echo Building installer...
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
  echo Building installer...
  "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
) else (
  echo Inno Setup 6 was not found. The EXE is ready; install Inno Setup to create the desktop-shortcut installer.
)

endlocal
