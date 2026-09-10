; Triada Network Windows installer
#define MyAppName "Triada Network"
#define MyAppVersion "2.3.0"
#define MyAppPublisher "Triada Network"
#define MyAppExeName "TriadaNetwork.exe"
#define MyAppReleaseLabel "2.3.0-rc.1"

[Setup]
AppId={{B2A4B89B-3C9C-4A16-9AA1-1600002A0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Triada Network
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist\installer
OutputBaseFilename=TriadaNetwork-Setup-{#MyAppReleaseLabel}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
Uninstallable=yes
WizardStyle=modern
SetupIconFile=..\assets\triada.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\..\dist\TriadaNetwork\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Icons]
Name: "{group}\Triada Network"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\Triada Network"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Triada Network"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Never delete %LOCALAPPDATA%\Triada Network\ data here. User data survives upgrades/uninstall.
Type: filesandordirs; Name: "{app}"
