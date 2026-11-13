; Universal Remote - Internal unsigned Windows x64 installer.
; This is a development preview, NOT a signed/verified public release.
#define Product "Universal Remote"
#define Release "1.0.0-rc5.1-dev"
#define PackageRoot "..\evidence\qa\public-portable-prototype"

[Setup]
AppId={{D1E2CF25-D0C1-4C63-90A6-7D2C40AAAD3B}
AppName={#Product}
AppVersion={#Release}
AppVerName={#Product} {#Release} (Pré-visualização)
AppPublisher=Universal Remote Project (pré-visualização)
AppComments=Versão interna de desenvolvimento; não certificada para distribuição pública
DefaultDirName={localappdata}\Programs\UniversalRemote
DefaultGroupName=Universal Remote
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes
OutputDir=..\evidence\qa\installer-build
OutputBaseFilename=UniversalRemote-1.0.0-rc5.1-x64-PREVIEW-UNSIGNED
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallDisplayName=Universal Remote (Pré-visualização)
UninstallDisplayIcon={app}\GUI\UniversalRemote-Preview.exe
MinVersion=10.0.19041
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
DisableWelcomePage=no
DisableReadyPage=no
AlwaysShowDirOnReadyPage=yes
DisableFinishedPage=no
ShowLanguageDialog=yes
ChangesEnvironment=no
AllowCancelDuringInstall=yes
UsePreviousAppDir=yes
DirExistsWarning=auto
VersionInfoDescription=Universal Remote - Preview sem assinatura
VersionInfoProductName=Universal Remote Preview
VersionInfoVersion=1.0.0.51
VersionInfoProductVersion=1.0.0.51

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
portuguese.URProcessesMustClose=O Universal Remote ainda está em execução. Fecha a interface e desliga a ligação privada (Bridge/Túnel), depois volta a iniciar o instalador. Nenhum ficheiro foi alterado nesta tentativa.
english.URProcessesMustClose=Universal Remote is still running. Close the GUI and disconnect the private Bridge/Tunnel, then run Setup again. No files were changed by this attempt.
portuguese.URProcessCheckFailed=Não foi possível verificar se o Universal Remote está em execução. Por segurança, a atualização foi interrompida antes de alterar ficheiros. Verifica o serviço WMI e volta a tentar.
english.URProcessCheckFailed=Unable to verify whether Universal Remote is running. For safety, the update stopped before changing files. Check the Windows WMI service and retry.

[Tasks]
Name: "desktopicon"; Description: "Criar atalho no Ambiente de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "{#PackageRoot}\UniversalRemote-Preview\*"; DestDir: "{app}\GUI"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageRoot}\UniversalRemoteAgent-Preview\*"; DestDir: "{app}\Agent"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageRoot}\UniversalRemoteBridge-Preview\*"; DestDir: "{app}\Bridge"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageRoot}\UniversalRemoteUpdater-Preview\*"; DestDir: "{app}\Updater"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageRoot}\UniversalRemoteTunnel-Preview\*"; DestDir: "{app}\Tunnel"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\bin\tunnel-client.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\cloudflared.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\cloudflared-manifest.json"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\tunnel-client-origin.json"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\LICENSE"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\NOTICE"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\tunnel-client-v0.0.16-windows-amd64-licenses.txt"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\bin\tunnel-client-v0.0.16-windows-amd64.spdx.json"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\scripts\Resolve-PowerShell.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\Prepare-PowerShell.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\Test-Independent-PC.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\PUBLIC_SECURITY_MODEL.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\INSTALLER_AND_UX_SPEC.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\PUBLIC_RELEASE_GATES.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\evidence\qa\public-portable-prototype\UNSIGNED-PREVIEW-NOT-FOR-PUBLICATION.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Universal Remote (Preview)"; Filename: "{app}\GUI\UniversalRemote-Preview.exe"; WorkingDir: "{app}\GUI"
Name: "{autodesktop}\Universal Remote (Preview)"; Filename: "{app}\GUI\UniversalRemote-Preview.exe"; WorkingDir: "{app}\GUI"; Tasks: desktopicon
Name: "{autoprograms}\Desinstalar Universal Remote"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\GUI\UniversalRemote-Preview.exe"; Description: "Abrir Universal Remote"; Flags: nowait postinstall skipifsilent

[Code]
var
  InstallURProtocol: Boolean;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Locator, Service, SetOfProcesses: Variant;
begin
  { Fail closed before [Files] starts: the current GUI or private bridge may be
    holding installed EXEs open. Restart Manager can detect these but may not
    be allowed to close them for a lowest-privilege setup. Never silently
    skip locked binaries or install a mixture of old and new components. }
  Result := '';
  NeedsRestart := False;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2', '', '');
    SetOfProcesses := Service.ExecQuery(
      'SELECT Name FROM Win32_Process WHERE ' +
      'Name="UniversalRemote-Preview.exe" OR ' +
      'Name="UniversalRemoteAgent-Preview.exe" OR ' +
      'Name="UniversalRemoteBridge-Preview.exe" OR ' +
      'Name="UniversalRemoteTunnel-Preview.exe" OR ' +
      'Name="UniversalRemoteUpdater-Preview.exe"');
    if SetOfProcesses.Count > 0 then
      Result := CustomMessage('URProcessesMustClose');
  except
    Result := CustomMessage('URProcessCheckFailed');
  end;
end;

function InitializeSetup(): Boolean;
begin
  { Before setup chooses the directory, do not expand the application path.
    Do not overwrite any existing user protocol association. }
  InstallURProtocol := not RegKeyExists(HKCU, 'Software\Classes\universal-remote');
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Key, Command: String;
begin
  if (CurStep = ssPostInstall) and InstallURProtocol then
  begin
    Key := 'Software\Classes\universal-remote';
    Command := '"' + ExpandConstant('{app}\GUI\UniversalRemote-Preview.exe') + '" "%1"';
    RegWriteStringValue(HKCU, Key, '', 'URL:Universal Remote');
    RegWriteStringValue(HKCU, Key, 'URL Protocol', '');
    RegWriteStringValue(HKCU, Key + '\shell\open\command', '', Command);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CurrentValue, ExpectedValue: String;
  Code: Integer;
  Sidecar: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    { Never revoke someone else's protocol registration. }
    if RegQueryStringValue(HKCU,
         'Software\Classes\universal-remote\shell\open\command',
         '', CurrentValue) then
    begin
      ExpectedValue := '"' + ExpandConstant('{app}\GUI\UniversalRemote-Preview.exe') + '" "%1"';
      if CompareText(CurrentValue, ExpectedValue) = 0 then
        RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\universal-remote');
    end;
    Sidecar := ExpandConstant('{app}\Tunnel\UniversalRemoteTunnel-Preview.exe');
    { Ask only this application's tunnel to stop; no process tree or firewall changes. }
    if FileExists(Sidecar) then
      Exec(Sidecar, 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
    ExpectedValue := '"' + Sidecar + '" run';
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run',
                           'UniversalRemoteTunnelPreview', CurrentValue) then
    begin
      if CompareText(CurrentValue, ExpectedValue) = 0 then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run',
                       'UniversalRemoteTunnelPreview');
    end;
  end;
  { Personal workspace, device pairings and private configuration are retained. }
end;
