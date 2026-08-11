param([switch]$SkipFFmpeg)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvPath = Join-Path $ProjectRoot '.venv'
if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath
}
$PythonExe = Join-Path $VenvPath 'Scripts\python.exe'
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Falha ao atualizar pip.' }
& $PythonExe -m pip install -r (Join-Path $ProjectRoot 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências.' }
& $PythonExe (Join-Path $ProjectRoot 'scripts\make_icons.py')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar ícones.' }
if (-not $SkipFFmpeg) {
    & (Join-Path $PSScriptRoot 'setup_ffmpeg.ps1')
    & (Join-Path $PSScriptRoot 'setup_deno.ps1')
}
Write-Host "Ambiente pronto. Execute .\scripts\run_dev.ps1"
