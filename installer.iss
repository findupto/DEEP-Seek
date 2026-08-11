; Inno Setup installer for the built MK Pizza & Ice Bar POS EXE.
#define MyAppName "MK Pizza & Ice Bar POS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MK Pizza & Ice Bar"
#define MyAppExeName "MK_Pizza_Ice_Bar_POS.exe"

[Setup]
AppId={{7D6A4E91-5B9A-4C86-9B7D-202608100001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\MK Pizza & Ice Bar POS
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=MK-Pizza-Ice-Bar-POS-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\mk_pizza.ico
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source="dist\{#MyAppExeName}"; DestDir="{app}"; Flags: ignoreversion

[Icons]
Name="{autodesktop}\{#MyAppName}"; Filename="{app}\{#MyAppExeName}"; WorkingDir="{app}"; IconFilename="{app}\{#MyAppExeName}"
Name="{group}\{#MyAppName}"; Filename="{app}\{#MyAppExeName}"; WorkingDir="{app}"; IconFilename="{app}\{#MyAppExeName}"

[Run]
Filename="{app}\{#MyAppExeName}"; Description="Launch {#MyAppName}"; Flags=nowait postinstall skipifsilent
