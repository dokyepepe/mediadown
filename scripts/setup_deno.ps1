$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ResourceRoot = Join-Path $ProjectRoot 'resources\deno'
$DenoExe = Join-Path $ResourceRoot 'deno.exe'
if ((Test-Path $DenoExe) -and (Test-Path (Join-Path $ResourceRoot 'DENO-LICENSE.md'))) {
    Write-Host "Deno já está disponível em resources\deno."
    exit 0
}
$DownloadRoot = Join-Path $ProjectRoot '.build\deno-download'
New-Item -ItemType Directory -Force -Path $DownloadRoot | Out-Null
$Archive = Join-Path $DownloadRoot 'deno-x86_64-pc-windows-msvc.zip'
$ChecksumFile = "$Archive.sha256sum"
$BaseUrl = 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip'
if (-not (Test-Path $Archive) -or -not (Test-Path $ChecksumFile)) {
    Invoke-WebRequest -Uri $BaseUrl -OutFile $Archive -UseBasicParsing
    Invoke-WebRequest -Uri "$BaseUrl.sha256sum" -OutFile $ChecksumFile -UseBasicParsing
}
$Expected = [regex]::Match((Get-Content -Raw $ChecksumFile), '[A-Fa-f0-9]{64}').Value.ToLowerInvariant()
if (-not $Expected) { throw 'A fonte não forneceu um SHA-256 reconhecível para o Deno.' }
$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) { throw 'Falha na verificação SHA-256 do Deno.' }
$Extracted = Join-Path $DownloadRoot 'extracted'
if (Test-Path $Extracted) { Remove-Item -LiteralPath $Extracted -Recurse -Force }
Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted
if (-not (Test-Path (Join-Path $Extracted 'deno.exe'))) { throw 'Estrutura inesperada no pacote Deno.' }
New-Item -ItemType Directory -Force -Path $ResourceRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $Extracted 'deno.exe') -Destination $DenoExe
Copy-Item -LiteralPath $ChecksumFile -Destination (Join-Path $ResourceRoot 'SOURCE.sha256sum')
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/denoland/deno/main/LICENSE.md' -OutFile (Join-Path $ResourceRoot 'DENO-LICENSE.md') -UseBasicParsing
@"
Deno obtido da release oficial em https://github.com/denoland/deno/releases
Pacote: deno-x86_64-pc-windows-msvc.zip
SHA-256: $Actual
"@ | Set-Content -Encoding UTF8 (Join-Path $ResourceRoot 'SOURCE.txt')
Write-Host "Deno verificado e instalado em resources\deno."
