#define MyAppName "Media Downloader"
#define MyAppVersion GetVersionNumbersString("..\dist\MediaDownloader\MediaDownloader.exe")
#define MyAppPublisher "Media Downloader Project"
#define MyAppExeName "MediaDownloader.exe"

[Setup]
AppId={{A98BEB7E-C0D3-45D0-A438-9FC70E63BF2A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Media Downloader
DefaultGroupName=Media Downloader
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=MediaDownloader-Setup-x64
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\MediaDownloader.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
LicenseFile=..\licenses\APPLICATION_LICENSE.txt
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce
Name: "startmenuicon"; Description: "Criar atalho no Menu Iniciar"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
Source: "..\dist\MediaDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Media Downloader"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autoprograms}\Media Downloader\Media Downloader"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{autoprograms}\Media Downloader\Desinstalar Media Downloader"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar Media Downloader"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserData: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    if (not UninstallSilent) and
      (MsgBox('Deseja também remover configurações, logs e histórico pessoais?'#13#10#13#10 +
      'Escolha Não para preservar seus dados.', mbConfirmation, MB_YESNO) = IDYES) then
    begin
      UserData := ExpandConstant('{localappdata}\Media Downloader Project\MediaDownloader');
      DelTree(UserData, True, True, True);
      UserData := ExpandConstant('{localappdata}\MediaDownloader');
      DelTree(UserData, True, True, True);
      Exec(ExpandConstant('{sys}\cmdkey.exe'), '/delete:MediaDownloader/SpotifyOAuth',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;
