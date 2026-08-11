; DEEP-Seek POS Windows Installer
#define AppName "DEEP-Seek POS"
#define AppVersion "1.0.0"
#define AppPublisher "Findupto"
#define AppExeName "DEEP-Seek POS.exe"

[Setup]
AppId={{A7F8C6D4-5B7A-4C0F-9A9A-DSPOS2026}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\DEEP-Seek POS
DefaultGroupName={#AppName}
OutputDir=..\..\release
OutputBaseFilename=DEEP-Seek-POS-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#AppName}

[Files]
Source: "..\..\dist\DEEP-Seek POS.exe"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\DEEP-Seek POS"
Name: "{commonappdata}\DEEP-Seek POS\config"
Name: "{commonappdata}\DEEP-Seek POS\backups"
Name: "{commonappdata}\DEEP-Seek POS\logs"
Name: "{commonappdata}\DEEP-Seek POS\receipts"
Name: "{commonappdata}\DEEP-Seek POS\exports"

[Icons]
Name: "{autodesktop}\DEEP-Seek POS"; Filename: "{app}\{#AppExeName}"
Name: "{group}\DEEP-Seek POS"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall DEEP-Seek POS"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch DEEP-Seek POS"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    ForceDirectories(ExpandConstant('{commonappdata}\DEEP-Seek POS\config'));
    ForceDirectories(ExpandConstant('{commonappdata}\DEEP-Seek POS\backups'));
    ForceDirectories(ExpandConstant('{commonappdata}\DEEP-Seek POS\logs'));
    ForceDirectories(ExpandConstant('{commonappdata}\DEEP-Seek POS\receipts'));
    ForceDirectories(ExpandConstant('{commonappdata}\DEEP-Seek POS\exports'));
  end;
end;
