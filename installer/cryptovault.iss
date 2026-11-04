; Instalador do CryptoVault Desktop.
;
; Compile com:
;   "C:\Users\<voce>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer\cryptovault.iss
; ou pelo script scripts\build_installer.ps1 (recomendado).
;
; O instalador usa apenas caminhos relativos ao diretório do projeto; nenhum
; caminho absoluto do computador de desenvolvimento é embutido.

#define AppName "CryptoVault Desktop"
#define AppVersion "1.0.0"
#define AppPublisher "Mersfik"
#define AppExeName "CryptoVault.exe"
#define AppUrl "https://github.com/Mersfik/cryptovault-desktop"

[Setup]
AppId={{6D2F9B14-3C7E-4A58-9E21-8B5D0C4A7F63}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador do {#AppName}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
; Instalação por usuário por padrão: não exige privilégios administrativos.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=CryptoVault-Desktop-{#AppVersion}-setup
SetupIconFile=..\cryptovault\resources\logo.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
; Não remove os dados do usuário em %LOCALAPPDATA%\CryptoVault na desinstalação.

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CRYPTOGRAPHY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THREAT_MODEL.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; AppUserModelID: "Mersfik.CryptoVaultDesktop"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; AppUserModelID: "Mersfik.CryptoVaultDesktop"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
