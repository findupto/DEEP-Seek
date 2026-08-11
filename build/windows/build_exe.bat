@echo off
setlocal
cd /d "%~dp0..\.."

echo === DEEP-Seek POS: building Windows EXE ===
where py >nul 2>nul || (echo Python is required. Install Python 3.11+ and try again.& exit /b 1)

py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m pip install pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

py -m PyInstaller --clean --noconfirm build\windows\DEEP-Seek.spec
if errorlevel 1 (echo Build failed.& exit /b 1)

echo.
echo EXE created under dist\
echo Next: install Inno Setup, then run build\windows\build_installer.bat
endlocal
