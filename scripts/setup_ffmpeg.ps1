$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ResourceRoot = Join-Path $ProjectRoot 'resources\ffmpeg'
$FfmpegExe = Join-Path $ResourceRoot 'ffmpeg.exe'
if ((Test-Path $FfmpegExe) -and (Test-Path (Join-Path $ResourceRoot 'FFMPEG-LICENSE.txt'))) {
    Write-Host "FFmpeg já está disponível em resources\ffmpeg."
    exit 0
}
$DownloadRoot = Join-Path $ProjectRoot '.build\ffmpeg-download'
New-Item -ItemType Directory -Force -Path $DownloadRoot | Out-Null
$Archive = Join-Path $DownloadRoot 'ffmpeg-release-essentials.zip'
$ChecksumFile = Join-Path $DownloadRoot 'ffmpeg-release-essentials.zip.sha256'
$BaseUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
if (-not (Test-Path $Archive) -or -not (Test-Path $ChecksumFile)) {
    Invoke-WebRequest -Uri $BaseUrl -OutFile $Archive -UseBasicParsing
    Invoke-WebRequest -Uri "$BaseUrl.sha256" -OutFile $ChecksumFile -UseBasicParsing
}
$ChecksumText = Get-Content -Raw $ChecksumFile
$Expected = [regex]::Match($ChecksumText, '[A-Fa-f0-9]{64}').Value.ToLowerInvariant()
if (-not $Expected) { throw 'A fonte não forneceu um SHA-256 reconhecível para o FFmpeg.' }
$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) { throw 'Falha na verificação SHA-256 do FFmpeg.' }
$Extracted = Join-Path $DownloadRoot 'extracted'
if (Test-Path $Extracted) { Remove-Item -LiteralPath $Extracted -Recurse -Force }
Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted
$Bin = Get-ChildItem -LiteralPath $Extracted -Directory | Select-Object -First 1 | ForEach-Object { Join-Path $_.FullName 'bin' }
if (-not $Bin -or -not (Test-Path (Join-Path $Bin 'ffmpeg.exe'))) { throw 'Estrutura inesperada no pacote FFmpeg.' }
New-Item -ItemType Directory -Force -Path $ResourceRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $Bin 'ffmpeg.exe') -Destination $ResourceRoot
Copy-Item -LiteralPath (Join-Path $Bin 'ffprobe.exe') -Destination $ResourceRoot
Copy-Item -LiteralPath (Join-Path (Split-Path $Bin -Parent) 'LICENSE') -Destination (Join-Path $ResourceRoot 'FFMPEG-LICENSE.txt')
Copy-Item -LiteralPath $ChecksumFile -Destination (Join-Path $ResourceRoot 'SOURCE.sha256')
@"
Build FFmpeg obtido de https://www.gyan.dev/ffmpeg/builds/
Pacote: ffmpeg-release-essentials.zip
SHA-256: $Actual
Consulte licenses/THIRD_PARTY_NOTICES.md.
"@ | Set-Content -Encoding UTF8 (Join-Path $ResourceRoot 'SOURCE.txt')
Write-Host "FFmpeg verificado e instalado em resources\ffmpeg."
