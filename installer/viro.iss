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

[UninstallDelete]
Type: filesandordirs; Name: "{app}\viro-env"
Type: filesandordirs; Name: "{app}"

[Code]

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // ── Run environment setup (visible window so user sees progress) ─────────
    if not Exec('powershell.exe',
      '-ExecutionPolicy Bypass -NoProfile -Command "& \"' + ExpandConstant('{app}') + '\setup_install.ps1\" \"' + ExpandConstant('{app}') + '\"; if ($LASTEXITCODE -ne 0) { Write-Host \"Setup failed. Press any key...\"; $null = $Host.UI.RawUI.ReadKey(\"NoEcho,IncludeKeyDown\") }"',
      ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      MsgBox('Failed to launch setup script.' + #13#10 + SysErrorMessage(ResultCode), mbError, MB_OK);
      Exit;
    end;

    if ResultCode <> 0 then
      MsgBox('Environment setup failed (exit code ' + IntToStr(ResultCode) + ').' + #13#10 +
             'Please check the output window for details.', mbError, MB_OK);

    // ── Refresh desktop shortcut icon ────────────────────────────────────────
    Exec('powershell.exe',
      '-NoProfile -WindowStyle Hidden -Command "$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut([Environment]::GetFolderPath(''Desktop'')+''\Viro.lnk''); $sc.TargetPath=[System.Environment]::SystemDirectory+''\wscript.exe''; $sc.Arguments=chr(34)+''' + ExpandConstant('{app}') + '\launch.vbs''+chr(34); $sc.WorkingDirectory=''' + ExpandConstant('{app}') + '''; $sc.IconLocation=''' + ExpandConstant('{app}') + '\viro.ico,0''; $sc.Save(); ie4uinit.exe -show"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
