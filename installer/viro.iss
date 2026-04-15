#define AppName "Viro"
#define AppVersion "1.0"
#define AppPublisher "Viro"
#define AppExeName "viro.exe"

[Setup]
AppId={{B3F2A1C4-7E5D-4F8A-9B2E-1D6C3A7F0E24}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\{#AppName}
DisableDirPage=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Viro_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayName={#AppName}
SetupIconFile=viro.ico
UninstallDisplayIcon={app}\viro.ico
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs; Excludes: "__pycache__,*.pyc"
Source: "..\run_app.py";     DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt";  DestDir: "{app}"; Flags: ignoreversion
Source: "setup_install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "viro.ico";          DestDir: "{app}"; Flags: ignoreversion
Source: "launch.vbs";        DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";       Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\viro.ico"; Comment: "Launch Viro browser agent"
Name: "{userdesktop}\{#AppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\viro.ico"; Comment: "Launch Viro browser agent"

[InstallDelete]
; Remove stale bytecode from previous installs so Python always runs fresh .py files
Type: filesandordirs; Name: "{app}\app\__pycache__"

[Run]
; Refresh desktop shortcut icon cache after install
Filename: "powershell.exe"; Parameters: "-NoProfile -WindowStyle Hidden -Command ""$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Viro.lnk'); $sc.TargetPath=[System.Environment]::SystemDirectory+'\wscript.exe'; $sc.Arguments=chr(34)+'{app}\launch.vbs'+chr(34); $sc.WorkingDirectory='{app}'; $sc.IconLocation='{app}\viro.ico,0'; $sc.Save(); ie4uinit.exe -show"""; Flags: runhidden postinstall
; Run environment setup
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command ""& '{app}\setup_install.ps1' '{app}'; if ($LASTEXITCODE -ne 0) {{ Read-Host 'Setup failed. Press Enter to close' }}"""; Flags: runhidden postinstall waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}\viro-env"
Type: filesandordirs; Name: "{app}"
