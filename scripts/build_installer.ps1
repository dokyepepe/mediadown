param(
    [string]$PythonExe
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Exe = Join-Path $ProjectRoot 'dist\MediaDownloader\MediaDownloader.exe'
if (-not (Test-Path $Exe)) {
    $BuildArguments = @{}
    if ($PythonExe) { $BuildArguments['PythonExe'] = $PythonExe }
    & (Join-Path $PSScriptRoot 'build.ps1') @BuildArguments
}
$Candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
) | Where-Object { $_ -and (Test-Path $_) }
$Iscc = $Candidates | Select-Object -First 1
if (-not $Iscc) {
    throw 'Inno Setup 6 não encontrado. Instale com: winget install --id JRSoftware.InnoSetup -e'
}
& $Iscc (Join-Path $ProjectRoot 'installer\MediaDownloader.iss')
$Setup = Join-Path $ProjectRoot 'release\MediaDownloader-Setup-x64.exe'
if (-not (Test-Path $Setup)) { throw 'O instalador esperado não foi gerado.' }
Write-Host "Instalador concluído: $Setup"
