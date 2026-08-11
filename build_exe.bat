@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   MK Pizza ^& Ice Bar POS - Windows EXE Build
echo ================================================

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

python -m PyInstaller --clean --noconfirm MK_Pizza_POS.spec
if errorlevel 1 goto :error

echo.
echo BUILD COMPLETE:
echo   dist\MK_Pizza_Ice_Bar_POS.exe
echo.
echo Run that EXE to test the standalone POS.
pause
exit /b 0

:error
echo.
echo BUILD FAILED. Check the error above.
pause
exit /b 1
