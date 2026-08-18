#define MyAppName "Pepforge"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Pepforge Project"
#define MyAppExeName "Pepforge.exe"

[Setup]
AppId={{7A8B6BA7-9E5E-4C3B-8B0F-AE10BEE70100}}
AppName=Pepforge
AppVersion=3.0.0
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Pepforge_Setup_v3.0.0
SetupIconFile=..\assets\Pepforge_Icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
RestartIfNeededByRun=no
ArchitecturesInstallIn64BitMode=x64compatible

AppVerName={#MyAppName} {#MyAppVersion}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
CreateUninstallRegKey=yes
AppSupportURL=https://github.com/
AppUpdatesURL=https://github.com/

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to the Pepforge Setup Wizard
WelcomeLabel2=This will install Pepforge, a modified-peptide workbench for hotspot analysis, peptide design, peptide-specific structure generation, SPPS preparation, and external validation setup for tools such as AutoDock Vina and GROMACS.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:";

[Files]
Source: "..\dist\Pepforge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
