param(
    [string]$PythonExe
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonExe) { $PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw 'Ambiente não configurado. Execute scripts\setup_dev.ps1 ou informe -PythonExe.'
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
if (-not (Test-Path (Join-Path $ProjectRoot 'resources\ffmpeg\ffmpeg.exe'))) {
    & (Join-Path $PSScriptRoot 'setup_ffmpeg.ps1')
}
if (-not (Test-Path (Join-Path $ProjectRoot 'resources\deno\deno.exe'))) {
    & (Join-Path $PSScriptRoot 'setup_deno.ps1')
}
& $PythonExe (Join-Path $ProjectRoot 'scripts\make_icons.py')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar os ícones.' }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
& $PythonExe -m pytest (Join-Path $ProjectRoot 'tests') -q
if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam; o build foi interrompido.' }
& $PythonExe -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot 'MediaDownloader.spec')
if ($LASTEXITCODE -ne 0) { throw 'O PyInstaller falhou.' }
$Exe = Join-Path $ProjectRoot 'dist\MediaDownloader\MediaDownloader.exe'
if (-not (Test-Path $Exe)) { throw 'O executável esperado não foi gerado.' }
$SmokeRoot = Join-Path $ProjectRoot '.build'
$SmokeData = Join-Path $SmokeRoot ("smoke-data-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $SmokeData | Out-Null
$PreviousDataDir = $env:MEDIA_DOWNLOADER_DATA_DIR
$PreviousQtPlatform = $env:QT_QPA_PLATFORM
try {
    $env:MEDIA_DOWNLOADER_DATA_DIR = $SmokeData
    $env:QT_QPA_PLATFORM = 'offscreen'
    $SmokeProcess = Start-Process -FilePath $Exe -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
    if ($SmokeProcess.ExitCode -ne 0) { throw "O executável empacotado falhou no smoke test (código $($SmokeProcess.ExitCode))." }
}
finally {
    if ($null -eq $PreviousDataDir) { Remove-Item Env:\MEDIA_DOWNLOADER_DATA_DIR -ErrorAction SilentlyContinue }
    else { $env:MEDIA_DOWNLOADER_DATA_DIR = $PreviousDataDir }
    if ($null -eq $PreviousQtPlatform) { Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
    else { $env:QT_QPA_PLATFORM = $PreviousQtPlatform }
    Remove-Item -LiteralPath $SmokeData -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "Build concluído: $Exe"
