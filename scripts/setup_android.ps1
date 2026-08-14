param(
    [switch]$AcceptSdkLicenses,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$sdkRoot = Join-Path $repoRoot ".android-sdk"
$downloadRoot = Join-Path $repoRoot ".android-sdk-download"
$archivePath = Join-Path $downloadRoot "commandlinetools-win-15859902_latest.zip"
$archiveUrl = "https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip"
$archiveSha256 = "90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a"
$sdkManager = Join-Path $sdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"

New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null
New-Item -ItemType Directory -Force -Path $sdkRoot | Out-Null

if ($Force -or -not (Test-Path -LiteralPath $archivePath)) {
    Write-Host "Baixando Android SDK Command-line Tools..."
    Invoke-WebRequest -UseBasicParsing -Uri $archiveUrl -OutFile $archivePath
}

$actualSha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $archiveSha256) {
    throw "SHA-256 inválido para Command-line Tools: $actualSha256"
}

if ($Force -or -not (Test-Path -LiteralPath $sdkManager)) {
    $extractRoot = Join-Path $downloadRoot "cmdline-tools-extracted"
    $resolvedRepo = (Resolve-Path -LiteralPath $repoRoot).Path
    $resolvedExtractParent = (Resolve-Path -LiteralPath $downloadRoot).Path
    if (-not $resolvedExtractParent.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Destino temporário fora do repositório: $resolvedExtractParent"
    }
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot -Force

    $latestRoot = Join-Path $sdkRoot "cmdline-tools\latest"
    $latestParent = Split-Path -Parent $latestRoot
    New-Item -ItemType Directory -Force -Path $latestParent | Out-Null
    if (Test-Path -LiteralPath $latestRoot) {
        Remove-Item -LiteralPath $latestRoot -Recurse -Force
    }
    Move-Item -LiteralPath (Join-Path $extractRoot "cmdline-tools") -Destination $latestRoot
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
}

if (-not (Test-Path -LiteralPath $sdkManager)) {
    throw "sdkmanager não foi instalado em $sdkManager"
}

$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:JAVA_HOME = "C:\Program Files\Java\jdk-17"

if ($AcceptSdkLicenses) {
    Write-Host "Aceitando as licenças do Android SDK solicitadas pelo sdkmanager..."
    1..100 | ForEach-Object { "y" } | & $sdkManager --sdk_root=$sdkRoot --licenses | Out-Host
} else {
    Write-Warning "Use -AcceptSdkLicenses para instalar pacotes em uma máquina nova."
}

Write-Host "Instalando Platform Tools, Android 16 (API 36) e Build Tools 35/36..."
& $sdkManager --sdk_root=$sdkRoot "platform-tools" "platforms;android-36" "build-tools;35.0.0" "build-tools;36.0.0"
if ($LASTEXITCODE -ne 0) {
    throw "sdkmanager terminou com código $LASTEXITCODE"
}

$localProperties = Join-Path $repoRoot "android\local.properties"
$escapedSdkRoot = $sdkRoot.Replace("\", "\\").Replace(":", "\:")
Set-Content -LiteralPath $localProperties -Encoding ASCII -Value "sdk.dir=$escapedSdkRoot"

Write-Host "Android SDK pronto em $sdkRoot"
