; Inno Setup installer for MK Pizza & Ice Bar POS
#define MyAppName "MK Pizza & Ice Bar"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MK Pizza & Ice Bar"
#define MyAppExeName "MK Pizza & Ice Bar.exe"

[Setup]
AppId={{7D6A4E91-5B9A-4C86-9B7D-202608100001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=MK-Pizza-Ice-Bar-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\assets\mk_pizza.ico
SetupIconFile=assets\mk_pizza.ico
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source="dist\{#MyAppExeName}"; DestDir="{app}"; Flags: ignoreversion
Source="assets\mk_pizza.ico"; DestDir="{app}\assets"; Flags: ignoreversion

[Icons]
Name="{autodesktop}\{#MyAppName}"; Filename="{app}\{#MyAppExeName}"; WorkingDir="{app}"; IconFilename="{app}\assets\mk_pizza.ico"
Name="{group}\{#MyAppName}"; Filename="{app}\{#MyAppExeName}"; WorkingDir="{app}"; IconFilename="{app}\assets\mk_pizza.ico"

[Run]
Filename="{app}\{#MyAppExeName}"; Description="Launch {#MyAppName}"; Flags=nowait postinstall skipifsilent
