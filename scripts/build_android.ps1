param(
    [ValidateSet("Debug", "Release")]
    [string]$Variant = "Debug",
    [switch]$Install,
    [switch]$SkipChecks,
    [string]$JavaHome = $env:JAVA_HOME
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $repoRoot "android"
$gradleWrapper = Join-Path $androidRoot "gradlew.bat"
$sdkRoot = Join-Path $repoRoot ".android-sdk"
$adb = Join-Path $sdkRoot "platform-tools\adb.exe"
$repoJdk = Get-ChildItem -LiteralPath (Join-Path $repoRoot ".android-jdk") -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "bin\java.exe") } |
    Select-Object -First 1
$defaultJavaHome = if ($repoJdk) { $repoJdk.FullName } else { "C:\Program Files\Java\jdk-17" }
$resolvedJavaHome = if ($JavaHome) { $JavaHome } else { $defaultJavaHome }
if (-not (Test-Path -LiteralPath (Join-Path $resolvedJavaHome "bin\java.exe"))) {
    throw "JDK 17 ausente em $resolvedJavaHome. Forneça o caminho com -JavaHome ou JAVA_HOME."
}
$env:JAVA_HOME = (Resolve-Path -LiteralPath $resolvedJavaHome).Path
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot

if (-not (Test-Path -LiteralPath $gradleWrapper)) {
    throw "Gradle Wrapper ausente. Execute scripts/setup_android.ps1 primeiro."
}
if (-not (Test-Path -LiteralPath (Join-Path $sdkRoot "platforms\android-36\android.jar"))) {
    throw "Android SDK ausente. Execute scripts/setup_android.ps1 -AcceptSdkLicenses."
}

$assembleTask = "assemble$Variant"
$checkTasks = @("test${Variant}UnitTest", "lint$Variant")

$keyProps = Join-Path $androidRoot "key.properties"
if ($Variant -eq "Release" -and -not (Test-Path -LiteralPath $keyProps)) {
    throw "A assinatura de release não está configurada: $keyProps ausente. O assembleRelease assinaria com a chave de debug e o APK não atualizaria uma instalação assinada corretamente. Crie android/key.properties antes de gerar um release (ou use -Variant Debug)."
}
# Native stderr output (e.g. Gradle/SDK warnings) becomes a RemoteException in
# PowerShell 5.1 when stderr is redirected; under "Stop" that aborts the build
# even though the underlying command succeeded. We check $LASTEXITCODE instead.
$oldErrorActionPreference = $ErrorActionPreference
Push-Location $androidRoot
try {
    if (-not $SkipChecks) {
        $ErrorActionPreference = "Continue"
        & $gradleWrapper --no-daemon --stacktrace @checkTasks
        $ErrorActionPreference = $oldErrorActionPreference
        if ($LASTEXITCODE -ne 0) {
            throw "Testes unitários ou lint Android terminaram com código $LASTEXITCODE"
        }
    }

    $ErrorActionPreference = "Continue"
    & $gradleWrapper --no-daemon --stacktrace $assembleTask
    $ErrorActionPreference = $oldErrorActionPreference
    if ($LASTEXITCODE -ne 0) {
        throw "Build Android terminou com código $LASTEXITCODE"
    }
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
    Pop-Location
}

$variantFolder = $Variant.ToLowerInvariant()
$outputDir = Join-Path $androidRoot "app\build\outputs\apk\$variantFolder"
if (-not (Test-Path -LiteralPath $outputDir)) {
    throw "Pasta de saída de APKs ausente: $outputDir"
}
$apks = @(Get-ChildItem -LiteralPath $outputDir -Filter "app-*-$variantFolder.apk" |
    Where-Object { $_.Name -notmatch "-unsigned" } |
    Sort-Object Name)
$unsignedRelease = Join-Path $outputDir "app-release-unsigned.apk"
if ($apks.Count -eq 0) {
    if ($Variant -eq "Release" -and (Test-Path -LiteralPath $unsignedRelease)) {
        throw "O APK release foi gerado sem assinatura em $unsignedRelease. Configure uma signingConfig antes de distribuir."
    }
    throw "Nenhum APK encontrado em $outputDir"
}

$releaseRoot = Join-Path $repoRoot "release"
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
Get-ChildItem -LiteralPath $releaseRoot -Filter "MediaDownloader-android-*.apk" -ErrorAction SilentlyContinue |
    Remove-Item -Force
$copied = @()
foreach ($apk in $apks) {
    $tag = $apk.BaseName
    if ($tag.StartsWith("app-") -and $tag.EndsWith("-$variantFolder")) {
        $tag = $tag.Substring(4, $tag.Length - 4 - $variantFolder.Length - 1)
    } else {
        $tag = ""
    }
    $destName = if ($tag) {
        "MediaDownloader-android-$tag-$variantFolder.apk"
    } else {
        "MediaDownloader-android-$variantFolder.apk"
    }
    $dest = Join-Path $releaseRoot $destName
    Copy-Item -LiteralPath $apk.FullName -Destination $dest -Force
    $copied += $dest
}
foreach ($dest in $copied) {
    $hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "APK: $dest"
    Write-Host "SHA-256: $hash"
}

if ($Variant -eq "Release") {
    Write-Host "Sideload: instale o MediaDownloader-android-universal-release.apk para evitar INSTALL_FAILED_NO_MATCHING_ABIS em aparelhos desconhecidos."
}

$apksigner = Join-Path $sdkRoot "build-tools\36.0.0\apksigner.bat"
$aapt = Join-Path $sdkRoot "build-tools\36.0.0\aapt.exe"
if ($Variant -eq "Release" -and (Test-Path -LiteralPath $apksigner) -and (Test-Path -LiteralPath $aapt)) {
    $verificationReport = @()
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        foreach ($dest in $copied) {
            $verify = & $apksigner verify --print-certs $dest 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Falha na verificacao de assinatura: $dest"
            }
            $verificationReport += "signature OK   : $dest"
        }
        $universal = $copied | Where-Object { $_ -match "universal" } | Select-Object -First 1
        if (-not $universal) { $universal = $copied[0] }
        $badging = & $aapt dump badging $universal 2>&1
        $verificationReport += ""
        $verificationReport += "badging ($(Split-Path -Leaf $universal)):"
        foreach ($line in $badging) {
            if ($line -match "^package:|^sdkVersion:|^targetSdkVersion:|^native-code:|^uses-feature|^permission:|^application-label") {
                $verificationReport += $line
            }
        }
    } finally {
        $ErrorActionPreference = $previousEap
    }
    $installReport = Join-Path $releaseRoot "MediaDownloader-installability.txt"
    $verificationReport | Set-Content -LiteralPath $installReport -Encoding UTF8
    Write-Host "Relatorio de instalabilidade: $installReport"
}

if ($Install) {
    if (-not (Test-Path -LiteralPath $adb)) {
        throw "adb não encontrado em $adb"
    }
    $installApk = $apks | Where-Object { $_.Name -match "universal" } | Select-Object -First 1
    if (-not $installApk) { $installApk = $apks[0] }
    & $adb install -r $installApk.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "adb install terminou com código $LASTEXITCODE"
    }
}
