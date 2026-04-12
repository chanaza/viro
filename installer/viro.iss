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
Source: "..\run_app.py";         DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt";      DestDir: "{app}"; Flags: ignoreversion
Source: "setup_install.ps1";     DestDir: "{app}"; Flags: ignoreversion
Source: "viro.ico";              DestDir: "{app}"; Flags: ignoreversion
Source: "launch.vbs";           DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";       Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\viro.ico"; Comment: "Launch Viro browser agent"
Name: "{userdesktop}\{#AppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launch.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\viro.ico"; Comment: "Launch Viro browser agent"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\viro-env"
Type: filesandordirs; Name: "{app}"

[Code]

// ── Custom pages ─────────────────────────────────────────────────────────────

var
  AuthPage:    TInputOptionWizardPage;
  ApiKeyPage:  TInputQueryWizardPage;
  VertexPage:  TInputQueryWizardPage;
  ModelPage:   TInputQueryWizardPage;

// Read a value from an existing .env file
function ReadEnvValue(const EnvFile, Key: string): string;
var
  Lines: TArrayOfString;
  I: Integer;
  Line, K, V: string;
begin
  Result := '';
  if not LoadStringsFromFile(EnvFile, Lines) then Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    if (Length(Line) = 0) or (Line[1] = '#') then Continue;
    K := Trim(Copy(Line, 1, Pos('=', Line) - 1));
    V := Trim(Copy(Line, Pos('=', Line) + 1, MaxInt));
    if K = Key then begin Result := V; Exit; end;
  end;
end;

procedure InitializeWizard;
var
  EnvFile: string;
  ExistingProject, ExistingLocation, ExistingApiKey, ExistingModel: string;
begin
  // Pre-load existing .env values for reinstall/update
  // WizardDirValue() is safe here (uses DefaultDirName if not yet chosen)
  EnvFile := WizardDirValue + '\.env';
  ExistingApiKey     := ReadEnvValue(EnvFile, 'GEMINI_API_KEY');
  ExistingProject    := ReadEnvValue(EnvFile, 'GOOGLE_CLOUD_PROJECT');
  ExistingLocation   := ReadEnvValue(EnvFile, 'LLM_LOCATION');
  ExistingModel      := ReadEnvValue(EnvFile, 'GEMINI_MODEL');
  if ExistingModel = '' then ExistingModel := 'gemini-2.0-flash';

  // Page 1: Auth method
  AuthPage := CreateInputOptionPage(wpSelectDir,
    'Authentication',
    'How will Viro connect to the Gemini AI model?',
    'Choose one of the following options:',
    True, False);
  AuthPage.Add('Gemini API Key  (recommended — get a free key at aistudio.google.com/apikey)');
  AuthPage.Add('Google Cloud / Vertex AI');
  if ExistingProject <> '' then
    AuthPage.Values[1] := True   // Vertex was previously configured
  else
    AuthPage.Values[0] := True;

  // Page 2a: API Key input
  ApiKeyPage := CreateInputQueryPage(AuthPage.ID,
    'Gemini API Key',
    'Enter your Gemini API key',
    'You can get a free key at: https://aistudio.google.com/apikey');
  ApiKeyPage.Add('API Key:', False);
  ApiKeyPage.Values[0] := ExistingApiKey;

  // Page 2b: Vertex AI inputs
  VertexPage := CreateInputQueryPage(AuthPage.ID,
    'Google Cloud / Vertex AI',
    'Enter your Google Cloud project details',
    'Make sure the Vertex AI API is enabled in your project.');
  VertexPage.Add('Project ID:', False);
  VertexPage.Add('LLM Region (e.g. europe-west3):', False);
  VertexPage.Values[0] := ExistingProject;
  VertexPage.Values[1] := ExistingLocation;

  // Page 3: Model
  ModelPage := CreateInputQueryPage(wpReady,
    'AI Model',
    'Choose which Gemini model to use',
    'Common options: gemini-2.0-flash, gemini-2.5-flash, gemini-1.5-pro');
  ModelPage.Add('Model name:', False);
  ModelPage.Values[0] := ExistingModel;
end;

// Skip the irrelevant auth page
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = ApiKeyPage.ID then Result := AuthPage.Values[1];  // skip API key page if Vertex selected
  if PageID = VertexPage.ID then Result := AuthPage.Values[0];  // skip Vertex page if API key selected
end;

// Validate required fields before proceeding
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
  if (CurPageID = ModelPage.ID) and (Trim(ModelPage.Values[0]) = '') then
  begin
    MsgBox('Please enter a model name.', mbError, MB_OK);
    Result := False;
  end;
end;

// Write .env and run setup script after files are copied
procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvContent, EnvFile: string;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // ── Write .env ───────────────────────────────────────────────────────────
    EnvFile := ExpandConstant('{app}\.env');
    EnvContent := 'GEMINI_MODEL=' + Trim(ModelPage.Values[0]) + #13#10;

    if AuthPage.Values[0] then  // API Key
      EnvContent := EnvContent + 'GEMINI_API_KEY=' + Trim(ApiKeyPage.Values[0]) + #13#10
    else                        // Vertex AI
    begin
      EnvContent := EnvContent + 'GOOGLE_CLOUD_PROJECT=' + Trim(VertexPage.Values[0]) + #13#10;
      EnvContent := EnvContent + 'LLM_LOCATION=' + Trim(VertexPage.Values[1]) + #13#10;
    end;

    if not SaveStringToFile(EnvFile, EnvContent, False) then
    begin
      MsgBox('Failed to write configuration file.', mbError, MB_OK);
      Exit;
    end;

    // ── Run environment setup ─────────────────────────────────────────────────
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
