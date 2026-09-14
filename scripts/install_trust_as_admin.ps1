#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Configura a confiança do MediaDownloader numa máquina Windows e contorna
    bloqueios de política de controle de aplicativo (WDAC / Device Guard).

.DESCRIPTION
    Este script DEVE ser executado como Administrador (clique com o botão
    direito > "Executar como administrador").

    Ele:
      1. Instala certs\MediaDownloaderSigner.cer em "Trusted Root Certification
         Authorities" e "Trusted Publishers" (máquina) — livra o SmartScreen de
         reclamar do editor e satisfaz políticas que confiam por editor.
      2. Lista as políticas WDAC ativas.
      3. Se -RemovePolicyId <GUID> for informado E você confirmar, remove a
         política bloqueante (após backup em certs\backup\). Uso típico: quando
         uma política fora do padrão exige assinatura "Enterprise" num PC pessoal.
      4. Opcionalmente desliga Memory Integrity (somente com -DisableMemoryIntegrity).

.EXAMPLE
    install_trust_as_admin.ps1 -RemovePolicyId 0283AC0F-FFF1-49AE-ADA1-8A933130CAD6
#>
param(
    [string]$CertDir          = "$PSScriptRoot\..\certs",
    [string]$RemovePolicyId   = "",
    [switch]$DisableMemoryIntegrity,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).
    IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Execute este script como Administrador."
    exit 1
}

$cerPath = Join-Path $CertDir "MediaDownloaderSigner.cer"
if (-not (Test-Path $cerPath)) {
    Write-Error "Certificado não encontrado: $cerPath`nGere primeiro com: powershell -ExecutionPolicy Bypass -File scripts\sign_build.ps1"
    exit 1
}

# ── 1. Instalar certificado ────────────────────────────────────────────────────
$cert = Get-PfxCertificate $cerPath
foreach ($storeName in @("Root", "TrustedPublisher")) {
    $store = "Cert:\LocalMachine\$storeName"
    $already = Get-ChildItem $store -ErrorAction SilentlyContinue | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if (-not $already) {
        Import-Certificate -FilePath $cerPath -CertStoreLocation $store | Out-Null
        Write-Host "[OK] Certificado instalado em $storeName (máquina)."
    } else {
        Write-Host "[INFO] Certificado já estava em $storeName."
    }
}

# ── 2. Listar políticas WDAC ativas ────────────────────────────────────────────
$activeDir = Join-Path $env:windir "System32\CodeIntegrity\CiPolicies\Active"
Write-Host ""
Write-Host "Políticas WDAC ativas nesta máquina:"
$policies = @()
if (Test-Path $activeDir) {
    $policies = Get-ChildItem $activeDir -Filter "*.cip" -File -ErrorAction SilentlyContinue
    if ($policies) {
        foreach ($p in $policies) {
            Write-Host ("  [0] {0}  ({1:N0} bytes)" -f $p.BaseName, $p.Length)
        }
    } else {
        Write-Host "  (nenhuma)"
    }
} else {
    Write-Host "  (pasta de política não existe — provavelmente sem WDAC)"
}

# ── 3. Remover política bloqueante (somente se o usuário pedir) ───────────────
if ($RemovePolicyId) {
    $id = $RemovePolicyId.ToUpperInvariant() -replace '[{}]', ''
    Write-Host ""
    Write-Warning "Você solicitou remover a política WDAC $id."
    Write-Warning "Em um PC PESSOAL isso é seguro; em um PC da empresa/TI, peça liberação."
    if (-not $Force) {
        $conf = Read-Host "Digite REMOVER para confirmar"
        if ($conf -ne "REMOVER") { Write-Host "Abortado."; exit 2 }
    }
    $backupDir = Join-Path $CertDir "backup"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $target = Join-Path $activeDir "$id.cip"
    if (Test-Path $target) {
        Copy-Item $target (Join-Path $backupDir "$id.cip.bak") -Force | Out-Null
        Remove-Item $target -Force
        Write-Host "[OK] Política $id removida (backup em certs\backup\)."
        Write-Host "     Reinicie o computador para a remoção valer."
    } else {
        Write-Warning "Política $id não encontrada em $activeDir"
    }
}

# ── 4. (Opcional) Desligar Memory Integrity ───────────────────────────────────
if ($DisableMemoryIntegrity) {
    Write-Host ""
    Write-Warning "Desligando Memory Integrity (HVCI). Isso reduz a proteção do kernel."
    if (-not $Force) {
        $conf = Read-Host "Digite DESLIGAR para confirmar"
        if ($conf -ne "DESLIGAR") { Write-Host "Abortado."; exit 2 }
    }
    $hvci = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity"
    if (Test-Path $hvci) { Set-ItemProperty -Path $hvci -Name "Enabled" -Value 0 -Type DWord }
    Write-Host "[OK] Memory Integrity será desligado após reiniciar."
}

Write-Host ""
Write-Host "Aviso: todo instalador baixado da internet leva a marca 'dos', e o
SmartScreen pedirá 'Mais informações > Executar assim mesmo' na primeira vez — é o
comportamento normal para apps sem assinatura comercial."