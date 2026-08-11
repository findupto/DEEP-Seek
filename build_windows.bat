@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo   MK Pizza ^& Ice Bar - Windows EXE Builder
echo ===============================================

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

python build_icon.py
if errorlevel 1 exit /b 1

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo Building windowed EXE with MK icon...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "MK Pizza & Ice Bar" --icon "assets\mk_pizza.ico" --add-data "assets;assets" run_pos.py
if errorlevel 1 exit /b 1

rem Keep compatibility with the existing Inno Setup script filename.
copy /y "dist\MK Pizza & Ice Bar.exe" "dist\MK_Pizza_Ice_Bar_POS.exe" >nul

if not exist "dist\MK_Pizza_Ice_Bar_POS.exe" (
  echo ERROR: EXE was not created.
  exit /b 1
)

echo.
echo EXE created:
echo   dist\MK Pizza ^& Ice Bar.exe
echo.
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
  echo Building installer...
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
  echo Building installer...
  "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
) else (
  echo Inno Setup 6 was not found.
  echo The EXE is ready. Install Inno Setup 6 to create the installable setup EXE.
)

endlocal
