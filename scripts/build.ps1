$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) { throw 'Ambiente não configurado. Execute scripts\setup_dev.ps1.' }
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
$env:QT_QPA_PLATFORM = 'offscreen'
$SmokeProcess = Start-Process -FilePath $Exe -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
if ($SmokeProcess.ExitCode -ne 0) { throw "O executável empacotado falhou no smoke test (código $($SmokeProcess.ExitCode))." }
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
Write-Host "Build concluído: $Exe"
