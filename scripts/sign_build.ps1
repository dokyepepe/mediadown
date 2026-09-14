<#
.SYNOPSIS
    Gera (ou reutiliza) um certificado autoassinado de code-signing e assina o
    build do MediaDownloader (exe + DLLs + pyds + opcionalmente o instalador),
    para compatibilidade com PCs que tenham WDAC/Device Guard.

.DESCRIPTION
    Funciona SEM privilégios de administrador (usa o store de certificados do
    usuário). Etapas:
      1. Cria/reutiliza certificado self-signed em CurrentUser\My.
      2. Salva o .cer (chave pública) em certs\MediaDownloaderSigner.cer — é este
         arquivo que deve ser confiado nas máquinas com WDAC.
      3. Assina todos os .exe/.dll/.pyd do build.
      4. Se informado -SetupFile, assina também o instalador.

.PARAMETER SetupFile
    Caminho opcional do instalador (MediaDownloader-Setup-x64.exe) para assinar.

.PARAMETER CertDir
    Pasta para salvar/ler os certificados (padrão: <raiz>\certs).
#>
param(
    [string]$CertSubject = "CN=MediaDownloader, O=MediaDownloader, L=BR",
    [int]$ValidYears     = 3,
    [string]$CertDir     = "$PSScriptRoot\..\certs",
    [string]$BuildDir    = "$PSScriptRoot\..\dist\MediaDownloader",
    [string]$SetupFile   = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
}
$cerPath = Join-Path $CertDir "MediaDownloaderSigner.cer"
$thumbFile = Join-Path $CertDir "thumbprint.txt"

# ── 1. Criar ou reutilizar certificado (CurrentUser\My, não requer admin) ──────
$cert = $null
if (Test-Path $thumbFile) {
    $thumb = (Get-Content $thumbFile -Raw).Trim()
    $cert = Get-ChildItem "Cert:\CurrentUser\My\$thumb" -ErrorAction SilentlyContinue
}
if (-not $cert) {
    $expires = (Get-Date).AddYears($ValidYears)
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $CertSubject `
        -CertStoreLocation Cert:\CurrentUser\My `
        -NotAfter $expires `
        -HashAlgorithm SHA256 `
        -KeyUsage DigitalSignature `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")
    $cert.Thumbprint | Out-File $thumbFile -Encoding ascii -NoNewline
    Write-Host "[OK] Certificado criado: $($cert.Thumbprint) expira $($cert.NotAfter.ToString('yyyy-MM-dd'))"
} else {
    Write-Host "[OK] Reutilizando certificado: $($cert.Thumbprint)"
}

# Exportar a chave pública (.cer) — nunca deve mudar entre builds
if (-not (Test-Path $cerPath) -or (Get-PfxCertificate $cerPath -ErrorAction SilentlyContinue).Thumbprint -ne $cert.Thumbprint) {
    Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null
    Write-Host "[OK] Certificado exportado para $cerPath"
}

# Set-AuthenticodeSignature valida a cadeia — confiar a própria raiz no store do
# usuário (sem admin) para a assinatura funcionar.
$userRoot = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$userRoot.Open("ReadOnly")
$alreadyRoot = $false
try {
    $alreadyRoot = $userRoot.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint } | Select-Object -First 1
} finally {
    $userRoot.Close()
}
if (-not $alreadyRoot) {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
    $store.Open("ReadWrite"); $store.Add($cert); $store.Close()
    Write-Host "[OK] Raiz do certificado confiada no store do usuário (necessário para assinar)."
}

# ── 2. Assinar arquivos do build ──────────────────────────────────────────────
if (Test-Path $BuildDir) {
    $files = Get-ChildItem -Path $BuildDir -Include *.exe, *.dll, *.pyd -Recurse -File
    Write-Host "[INFO] Assinando $($files.Count) binários em $BuildDir ..."

    $signed = 0; $skipped = 0; $failed = 0
    foreach ($file in $files) {
        $existing = Get-AuthenticodeSignature -FilePath $file.FullName -ErrorAction SilentlyContinue
        if ($existing.Status -eq 'Valid' -and $existing.SignerCertificate -and
            $existing.SignerCertificate.Thumbprint -eq $cert.Thumbprint) {
            $skipped++
            continue
        }
        $result = $null
        try {
            $result = Set-AuthenticodeSignature -FilePath $file.FullName -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com" -ErrorAction Stop
        } catch {
            try { $result = Set-AuthenticodeSignature -FilePath $file.FullName -Certificate $cert -HashAlgorithm SHA256 -ErrorAction Stop }
            catch { Write-Warning "Falha ao assinar $($file.Name): $_" ; $failed++; continue }
        }
        if ($result.Status -eq 'Valid') { $signed++ } else { $failed++; Write-Warning "$($result.Status): $($file.Name)" }
    }
    Write-Host "[OK] Build: $signed assinados | $skipped já assinados | $failed falhas"
} else {
    Write-Warning "BuildDir não encontrado: $BuildDir — pulei assinatura do app."
}

# ── 3. Assinar instalador, se informado ───────────────────────────────────────
if ($SetupFile -and (Test-Path $SetupFile)) {
    $existing = Get-AuthenticodeSignature -FilePath $SetupFile -ErrorAction SilentlyContinue
    if ($existing.Status -eq 'Valid' -and $existing.SignerCertificate -and
        $existing.SignerCertificate.Thumbprint -eq $cert.Thumbprint) {
        Write-Host "[OK] Instalador já assinado."
    } else {
        $result = $null
        try { $result = Set-AuthenticodeSignature -FilePath $SetupFile -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com" -ErrorAction Stop }
        catch {
            try { $result = Set-AuthenticodeSignature -FilePath $SetupFile -Certificate $cert -HashAlgorithm SHA256 -ErrorAction Stop }
            catch { Write-Warning "Falha ao assinar instalador: $_" ; exit 1 }
        }
        Write-Host "[OK] Instalador assinado: $SetupFile ($($result.Status))"
    }
}

Write-Host "Certificado público para máquinas-alvo: $cerPath"