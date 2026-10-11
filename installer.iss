#define AppName "AtomLite"
#define AppVersion "1.0.0"
#define AppPublisher "AtomLite"

[Setup]
AppId={{B584CCCB-7A25-4F06-A7AF-8C775394E26A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\AtomLite
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=AtomLite-Setup
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\AtomLite.exe
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{localappdata}\AtomLite"; Flags: uninsneveruninstall

[Files]
Source: "dist\AtomLite\AtomLite.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\AtomLite\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\Atom Lite.exe"
Type: files; Name: "{autoprograms}\Atom Lite.lnk"
Type: files; Name: "{autodesktop}\Atom Lite.lnk"

[Icons]
Name: "{autoprograms}\AtomLite"; Filename: "{app}\AtomLite.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\AtomLite"; Filename: "{app}\AtomLite.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\AtomLite.exe"; Description: "Launch AtomLite"; Flags: postinstall nowait skipifsilent

[Code]
var
  GulpPage: TInputFileWizardPage;
  SelectedGulpPath: string;

procedure InitializeWizard;
begin
  GulpPage := CreateInputFilePage(wpSelectDir,
    'GULP executable',
    'Select the GULP executable for this computer.',
    'AtomLite requires GULP. Browse to the licensed gulp.exe file to continue.');
  GulpPage.Add('GULP executable (gulp.exe):',
    'GULP executable|gulp.exe|Executable files|*.exe|All files|*.*', '.exe');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Candidate: string;
begin
  Result := True;
  if CurPageID = GulpPage.ID then
  begin
    Candidate := Trim(GulpPage.Values[0]);
    if Candidate = '' then
    begin
      MsgBox('Select the licensed gulp.exe file to continue installation.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not FileExists(Candidate) then
    begin
      MsgBox('The selected file does not exist. Browse to the GULP executable (gulp.exe).',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if CompareText(ExtractFileName(Candidate), 'gulp.exe') <> 0 then
    begin
      MsgBox('Select the GULP executable named gulp.exe.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    SelectedGulpPath := Candidate;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsPath: string;
  SettingsContents: string;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsPath := ExpandConstant('{localappdata}\AtomLite\settings.txt');
    SettingsContents := 'GULP_PATH=' + SelectedGulpPath + #13#10;
    if not SaveStringToFile(SettingsPath, SettingsContents, False) then
      RaiseException('Could not save the selected GULP path to ' + SettingsPath);
  end;
end;
