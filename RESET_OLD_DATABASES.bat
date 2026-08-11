@echo off
setlocal EnableExtensions

cd /d "%~dp0"

title DEEP-Seek - RESET OLD DATABASES

color 0E

echo.
echo ============================================================
echo   DEEP-Seek POS - RESET OLD DATABASES
 echo ============================================================
echo.
echo WARNING: This utility permanently removes OLD LOCAL POS
 echo database files. This cannot be undone.
echo.
echo It is intended for an administrator starting with a clean
 echo database after testing or after migrating to a new database.
echo.
echo Cloud/PostgreSQL databases are NOT deleted by this script.
echo Backups are NOT deleted.
echo.
set /p "CONFIRM=Type RESET to continue: "
if /I not "%CONFIRM%"=="RESET" (
    echo.
    echo Cancelled. No database was removed.
    pause
    exit /b 0
)

echo.
echo Closing POS processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1

set "BACKUP_DIR=database_reset_backup"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "TODAY=%%c-%%a-%%b"
for /f "tokens=1-2 delims=:" %%a in ('time /t') do set "NOW=%%a%%b"
set "STAMP=%TODAY%_%NOW%"
set "STAMP=%STAMP:/=-%"
set "STAMP=%STAMP::=-%"

set "FOUND=0"

call :backup_and_delete "pos.db"
call :backup_and_delete "pos_app.db"
call :backup_and_delete "database.db"
call :backup_and_delete "deepseek.db"
call :backup_and_delete "store.db"

rem Remove only local SQLite database files from the common data folders.
for %%D in (data db databases) do (
    if exist "%%D" (
        for %%F in ("%%D\*.db" "%%D\*.sqlite" "%%D\*.sqlite3") do (
            if exist "%%~fF" call :backup_and_delete "%%~fF"
        )
    )
)

if "%FOUND%"=="0" (
    echo.
    echo No known local database files were found.
) else (
    echo.
    echo Old local databases were removed.
    echo Safety copies were placed in:
    echo   %CD%\%BACKUP_DIR%
    echo.
    echo IMPORTANT: Review the backup before deleting it.
)

echo.
echo The POS will create/use a fresh local database on next launch.
echo.
pause
exit /b 0

:backup_and_delete
set "TARGET=%~1"
if not exist "%TARGET%" exit /b 0

set "FOUND=1"
set "NAME=%~nx1"
set "SAFE=%BACKUP_DIR%\%NAME%.%STAMP%.bak"

echo Backing up: %TARGET%
copy /Y "%TARGET%" "%SAFE%" >nul
if errorlevel 1 (
    echo ERROR: Could not create safety copy. NOT deleting %TARGET%.
    exit /b 0
)

echo Removing: %TARGET%
del /F /Q "%TARGET%" >nul
if exist "%TARGET%" echo ERROR: Could not remove %TARGET%.
exit /b 0
