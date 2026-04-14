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

[Run]
; Refresh desktop shortcut icon cache after install
Filename: "powershell.exe"; Parameters: "-NoProfile -WindowStyle Hidden -Command ""$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Viro.lnk'); $sc.TargetPath=[System.Environment]::SystemDirectory+'\wscript.exe'; $sc.Arguments=chr(34)+'{app}\launch.vbs'+chr(34); $sc.WorkingDirectory='{app}'; $sc.IconLocation='{app}\viro.ico,0'; $sc.Save(); ie4uinit.exe -show"""; Flags: runhidden postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}\viro-env"
Type: filesandordirs; Name: "{app}"

[Code]

var
  AuthPage:   TInputOptionWizardPage;
  ApiKeyPage: TInputQueryWizardPage;
  VertexPage: TInputQueryWizardPage;

// Read a value from an existing config.json
function ReadJsonValue(const JsonFile, Key: string): string;
var
  Content: string;
  Search: string;
  Pos1, Pos2: Integer;
begin
  Result := '';
  if not LoadStringFromFile(JsonFile, Content) then Exit;
  Search := '"' + Key + '": "';
  Pos1 := Pos(Search, Content);
  if Pos1 = 0 then Exit;
  Pos1 := Pos1 + Length(Search);
  Pos2 := Pos('"', Copy(Content, Pos1, MaxInt));
  if Pos2 = 0 then Exit;
  Result := Copy(Content, Pos1, Pos2 - 1);
end;

procedure InitializeWizard;
var
  CfgFile: string;
  ExistingApiKey, ExistingProject, ExistingLocation: string;
begin
  CfgFile := GetEnv('USERPROFILE') + '\.viro\config.json';
  ExistingApiKey   := ReadJsonValue(CfgFile, 'gemini_api_key');
  ExistingProject  := ReadJsonValue(CfgFile, 'google_cloud_project');
  ExistingLocation := ReadJsonValue(CfgFile, 'llm_location');

  // Page 1: Auth method
  AuthPage := CreateInputOptionPage(wpSelectDir,
    'Authentication',
    'How will Viro connect to the Gemini AI model?',
    'You can change this later from the settings panel inside the app.',
    True, False);
  AuthPage.Add('Gemini API Key  (get a free key at aistudio.google.com/apikey)');
  AuthPage.Add('Google Cloud / Vertex AI');
  if ExistingProject <> '' then
    AuthPage.Values[1] := True
  else
    AuthPage.Values[0] := True;

  // Page 2a: API Key
  ApiKeyPage := CreateInputQueryPage(AuthPage.ID,
    'Gemini API Key',
    'Enter your Gemini API key',
    'You can get a free key at: https://aistudio.google.com/apikey');
  ApiKeyPage.Add('API Key:', False);
  ApiKeyPage.Values[0] := ExistingApiKey;

  // Page 2b: Vertex AI
  VertexPage := CreateInputQueryPage(AuthPage.ID,
    'Google Cloud / Vertex AI',
    'Enter your Google Cloud project details',
    'Make sure the Vertex AI API is enabled in your project.');
  VertexPage.Add('Project ID:', False);
  VertexPage.Add('LLM Region (e.g. europe-west3):', False);
  VertexPage.Values[0] := ExistingProject;
  VertexPage.Values[1] := ExistingLocation;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = ApiKeyPage.ID then Result := AuthPage.Values[1];
  if PageID = VertexPage.ID then Result := AuthPage.Values[0];
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = ApiKeyPage.ID) and (Trim(ApiKeyPage.Values[0]) = '') then
  begin
    MsgBox('Please enter your Gemini API Key.', mbError, MB_OK);
    Result := False;
  end;
  if (CurPageID = VertexPage.ID) then
  begin
    if Trim(VertexPage.Values[0]) = '' then
    begin
      MsgBox('Please enter your Google Cloud Project ID.', mbError, MB_OK);
      Result := False; Exit;
    end;
    if Trim(VertexPage.Values[1]) = '' then
    begin
      MsgBox('Please enter the LLM Region.', mbError, MB_OK);
      Result := False; Exit;
    end;
  end;
end;

// Write config.json and run setup after files are copied
procedure CurStepChanged(CurStep: TSetupStep);
var
  CfgContent, CfgFile, CfgDir: string;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // ── Write ~/.viro/config.json ────────────────────────────────────────────
    CfgDir  := GetEnv('USERPROFILE') + '\.viro';
    CfgFile := CfgDir + '\config.json';
    ForceDirectories(CfgDir);

    if AuthPage.Values[0] then  // API Key
      CfgContent :=
        '{' + #13#10 +
        '  "gemini_model": "gemini-2.0-flash",' + #13#10 +
        '  "gemini_api_key": "' + Trim(ApiKeyPage.Values[0]) + '"' + #13#10 +
        '}'
    else                        // Vertex AI
      CfgContent :=
        '{' + #13#10 +
        '  "gemini_model": "gemini-2.0-flash",' + #13#10 +
        '  "google_cloud_project": "' + Trim(VertexPage.Values[0]) + '",' + #13#10 +
        '  "llm_location": "' + Trim(VertexPage.Values[1]) + '"' + #13#10 +
        '}';

    if not SaveStringToFile(CfgFile, CfgContent, False) then
    begin
      MsgBox('Failed to write configuration file.', mbError, MB_OK);
      Exit;
    end;

    // ── Run environment setup ────────────────────────────────────────────────
    if not Exec('powershell.exe',
      '-ExecutionPolicy Bypass -NoProfile -Command "& \""' + ExpandConstant('{app}') + '\setup_install.ps1"\" \""' + ExpandConstant('{app}') + '\""; if ($LASTEXITCODE -ne 0) { Write-Host \"Press any key...\"; $null = $Host.UI.RawUI.ReadKey(\"NoEcho,IncludeKeyDown\") }"',
      ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      MsgBox('Failed to launch setup script.' + #13#10 + SysErrorMessage(ResultCode), mbError, MB_OK);
      Exit;
    end;

    if ResultCode <> 0 then
      MsgBox('Environment setup failed (exit code ' + IntToStr(ResultCode) + ').' + #13#10 +
             'Please check the output window for details.', mbError, MB_OK);
  end;
end;
