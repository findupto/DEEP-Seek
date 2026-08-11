# Windows EXE + Installer

## Requirements

- Windows 10/11 x64
- Python 3.11+ available as `py`
- Inno Setup 6 for the installer

## Build the EXE

From the repository root:

```bat
build\windows\build_exe.bat
```

Output:

```text
dist\DEEP-Seek POS.exe
```

## Build the installer

Run:

```bat
build\windows\build_installer.bat
```

Output:

```text
release\DEEP-Seek-POS-Setup.exe
```

The installer requests Windows administrator/UAC permission and installs the executable under `Program Files`. Writable machine-wide POS data is kept separately under `%ProgramData%\DEEP-Seek POS` so application upgrades do not overwrite the database.

## Data layout

```text
%ProgramFiles%\DEEP-Seek POS\
    DEEP-Seek POS.exe

%ProgramData%\DEEP-Seek POS\
    POS.db
    config\
    backups\
    logs\
    receipts\
    exports\
```

Do not ship a production database inside the installer. The application should create/open its writable database under the ProgramData location. Existing database-reset functionality creates backups before destructive resets.

## Distribution

Give end users only `DEEP-Seek-POS-Setup.exe`. They do not need Python or the source repository.

For production distribution, code-sign the installer and executable with a Windows Authenticode certificate to reduce SmartScreen warnings.
