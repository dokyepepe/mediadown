param(
    [ValidateSet("Debug", "Release")]
    [string]$Variant = "Debug",
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $repoRoot "android"
$gradleWrapper = Join-Path $androidRoot "gradlew.bat"
$sdkRoot = Join-Path $repoRoot ".android-sdk"
$adb = Join-Path $sdkRoot "platform-tools\adb.exe"
$env:JAVA_HOME = "C:\Program Files\Java\jdk-17"
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot

if (-not (Test-Path -LiteralPath $gradleWrapper)) {
    throw "Gradle Wrapper ausente. Execute scripts/setup_android.ps1 primeiro."
}
if (-not (Test-Path -LiteralPath (Join-Path $sdkRoot "platforms\android-36\android.jar"))) {
    throw "Android SDK ausente. Execute scripts/setup_android.ps1 -AcceptSdkLicenses."
}

$task = "assemble$Variant"
Push-Location $androidRoot
try {
    & $gradleWrapper --no-daemon --stacktrace $task
    if ($LASTEXITCODE -ne 0) {
        throw "Build Android terminou com código $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$variantFolder = $Variant.ToLowerInvariant()
$sourceApk = Join-Path $androidRoot "app\build\outputs\apk\$variantFolder\app-$variantFolder.apk"
if (-not (Test-Path -LiteralPath $sourceApk)) {
    throw "APK esperado não foi encontrado em $sourceApk"
}

$releaseRoot = Join-Path $repoRoot "release"
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
$destinationApk = Join-Path $releaseRoot "MediaDownloader-android-$variantFolder.apk"
Copy-Item -LiteralPath $sourceApk -Destination $destinationApk -Force
$hash = (Get-FileHash -LiteralPath $destinationApk -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "APK: $destinationApk"
Write-Host "SHA-256: $hash"

if ($Install) {
    if (-not (Test-Path -LiteralPath $adb)) {
        throw "adb não encontrado em $adb"
    }
    & $adb install -r $destinationApk
    if ($LASTEXITCODE -ne 0) {
        throw "adb install terminou com código $LASTEXITCODE"
    }
}
