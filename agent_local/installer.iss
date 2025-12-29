[Setup]
AppName=LocalPrinterAgent
AppVersion=1.0.0
DefaultDirName={commonpf}\LocalPrinterAgent
DefaultGroupName=LocalPrinterAgent
PrivilegesRequired=admin
OutputBaseFilename=LocalPrinterAgent-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=no
SetupIconFile=assets\LocalPrinterAgent.ico

[Files]
Source: "LocalPrinterAgent.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "install.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "launch_gui.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "service_install.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "service_remove.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALLATION_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; Icon is optional
Source: "assets\LocalPrinterAgent.ico"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\assets\LocalPrinterAgent.ico'))

[Run]
; Instala dependencias y registra pywin32 (usa el script incluido)
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File \"{app}\install.ps1\""; StatusMsg: "Instalando dependencias..."; Flags: runhidden waituntilterminated

[Icons]
Name: "{group}\LocalPrinterAgent GUI"; Filename: "{app}\launch_gui.bat"; WorkingDir: "{app}"; IconFilename: "{app}\LocalPrinterAgent.ico"; Check: FileExists(ExpandConstant('{app}\launch_gui.bat'))
Name: "{group}\Instalar/Reinstalar Servicio"; Filename: "{app}\service_install.bat"; WorkingDir: "{app}"; IconFilename: "{app}\LocalPrinterAgent.ico"; Check: FileExists(ExpandConstant('{app}\service_install.bat'))
Name: "{group}\Detener/Eliminar Servicio"; Filename: "{app}\service_remove.bat"; WorkingDir: "{app}"; IconFilename: "{app}\LocalPrinterAgent.ico"; Check: FileExists(ExpandConstant('{app}\service_remove.bat'))
Name: "{group}\Desinstalar LocalPrinterAgent"; Filename: "{uninstallexe}"

