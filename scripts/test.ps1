$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) { throw 'Ambiente não configurado. Execute scripts\setup_dev.ps1.' }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
& $PythonExe -m pytest @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
