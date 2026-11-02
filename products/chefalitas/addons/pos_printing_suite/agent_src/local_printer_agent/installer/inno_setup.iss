; Inno Setup script for POS Printing Suite Local Agent
; Build with: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" inno_setup.iss
; Prerequisite: run PyInstaller first so dist\LocalPrinterAgent exists

#define MyAppName "POS Printing Suite Local Agent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "POS Printing Suite"
#define AgentDir "..\dist\LocalPrinterAgent"

[Setup]
AppId={{POS-Printing-Suite-Agent-1.0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PosPrintingSuite\LocalPrinterAgent
DefaultGroupName=POS Printing Suite
OutputDir=..\dist
OutputBaseFilename=LocalPrinterAgent-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "installservice"; Description: "Install and start as Windows Service"; GroupDescription: "Service"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts"; Flags: unchecked

[Files]
Source: "{#AgentDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{userappdata}\PosPrintingSuite\LocalPrinterAgent\logs"; Permissions: users-full
Name: "{commonappdata}\PosPrintingSuite\LocalPrinterAgent"; Permissions: users-full
Name: "{commonappdata}\PosPrintingSuite\LocalPrinterAgent\logs"; Permissions: users-full

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\LocalPrinterAgent.exe"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\LocalPrinterAgent.exe"; Tasks: desktopicon

[Run]
; Write default config if missing (admin must set token)
Filename: "{cmd}"; Parameters: "/c echo {} > {commonappdata}\PosPrintingSuite\LocalPrinterAgent\config.json"; Flags: runhidden; StatusMsg: "Creating config..."
; Optional: install as service (requires pywin32 and run_agent.py or dedicated service exe)
; Filename: "{app}\LocalPrinterAgent.exe"; Parameters: "install"; Flags: runhidden; Tasks: installservice

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveStringToFile(ExpandConstant('{commonappdata}\PosPrintingSuite\LocalPrinterAgent\config.json'), '{"token":"REPLACE_WITH_DEVICE_TOKEN","host":"127.0.0.1","port":9060}', False);
  end;
end;
