#define MyAppName "Zanella Orchestrator"
#define MyAppVersion "0.1.0-rc6"
#define MyAppPublisher "Victor César Zanella"
#define MyAppExeName "Zanella-Orchestrator.exe"

[Setup]
AppId={{C6F7B7E3-CC58-47C4-BE8F-173DAD9113E4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion=0.1.0.10
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Instalador do Zanella Orchestrator Community
VersionInfoCopyright=Copyright 2026 Victor César Zanella
DefaultDirName={localappdata}\Programs\Zanella Orchestrator
DefaultGroupName=Zanella Orchestrator
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Zanella-Orchestrator-Setup-0.1.0-rc6-windows-x64
SetupIconFile=..\assets\branding\zanella-orchestrator-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "..\build\windows-rc6-final\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\site-packages\oauthlib"
Type: filesandordirs; Name: "{app}\site-packages\oauthlib-3.3.1.dist-info"

[Icons]
Name: "{group}\Zanella Orchestrator"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Zanella Orchestrator"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Zanella Orchestrator"; Flags: nowait postinstall skipifsilent
