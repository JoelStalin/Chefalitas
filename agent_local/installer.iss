
; Inno Setup Script for Local Printer Agent
; This script creates a professional installer for the agent.

#define MyAppName "Local Printer Agent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Company"
#define MyAppURL "https://www.yourcompany.com"
#define MyAppExeName "LocalPrinterAgent.exe"

[Setup]
AppId={{C6BA5655-23A2-4AF8-A1E4-741275987A2E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=LocalPrinterAgent-Setup
OutputDir=./
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Source path is relative to the location of this .iss script
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Add a shortcut to the common startup folder to run the agent on login
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Add an uninstaller shortcut in the Start Menu
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

[Run]
; Launch the application after the installation is complete
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
