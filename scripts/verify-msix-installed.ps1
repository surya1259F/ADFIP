<#
.SYNOPSIS
    Automated verification of the installed ADFIP MSIX desktop application.
.DESCRIPTION
    Trusts the dev certificate, installs the MSIX package, verifies package registration,
    inspects bundled binaries, and registers/tests loopback exemption.
#>

[CmdletBinding()]
param(
    [string]$MsixPath = "dist/ADFIP_0.1.0.0_x64.msix",
    [string]$CertPath = "build/msix_staging/devcert.pfx",
    [string]$CertPassword = "TestPassword123!"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   ADFIP MSIX Installed Verification      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Resolve MSIX path
if (-not (Test-Path $MsixPath)) {
    $altMsix = Get-ChildItem -Path "dist/*.msix" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($altMsix) {
        $MsixPath = $altMsix.FullName
    } else {
        Write-Error "MSIX package not found at $MsixPath!"
        exit 1
    }
}
$msixItem = Get-Item $MsixPath
Write-Host "[+] Found MSIX package: $($msixItem.FullName) ($([math]::Round($msixItem.Length / 1MB, 2)) MB)" -ForegroundColor Green

# 2. Trust Developer Certificate (required for Sideloading in CI)
if ($CertPath -and (Test-Path $CertPath)) {
    Write-Host "[*] Importing developer certificate to Trusted Root & Trusted People ..." -ForegroundColor Yellow
    $securePass = ConvertTo-SecureString -String $CertPassword -Force -AsPlainText
    Import-PfxCertificate -FilePath $CertPath -CertStoreLocation "Cert:\LocalMachine\Root" -Password $securePass | Out-Null
    Import-PfxCertificate -FilePath $CertPath -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" -Password $securePass | Out-Null
    Write-Host "[+] Developer certificate installed into machine trust stores." -ForegroundColor Green
}

# 3. Sideload Install MSIX
Write-Host "[*] Installing MSIX via Add-AppxPackage ..." -ForegroundColor Cyan
Add-AppxPackage -Path $msixItem.FullName -ForceApplicationShutdown
Start-Sleep -Seconds 2

# 4. Verify Package Registration
$pkg = Get-AppxPackage -Name "*ADFIP*" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pkg) {
    Write-Error "Package '*ADFIP*' was not found in installed AppX packages!"
    exit 1
}

Write-Host "[+] Package successfully installed and registered!" -ForegroundColor Green
Write-Host "    - Name:               $($pkg.Name)"
Write-Host "    - Publisher:          $($pkg.Publisher)"
Write-Host "    - Version:            $($pkg.Version)"
Write-Host "    - Architecture:       $($pkg.Architecture)"
Write-Host "    - PackageFamilyName:  $($pkg.PackageFamilyName)"
Write-Host "    - InstallLocation:    $($pkg.InstallLocation)"

# 5. Verify Package Content Integrity
$installDir = $pkg.InstallLocation
$expectedFiles = @(
    "ADFIP.exe",
    "AppxManifest.xml",
    "Assets\Square150x150Logo.png",
    "Assets\Square44x44Logo.png",
    "adfir-backend\adfir-backend.exe"
)

$allFound = $true
foreach ($rel in $expectedFiles) {
    $full = Join-Path $installDir $rel
    if (Test-Path $full) {
        $fi = Get-Item $full
        Write-Host "    [✓] Found: $rel ($([math]::Round($fi.Length / 1KB, 1)) KB)" -ForegroundColor Green
    } else {
        Write-Host "    [✗] Missing: $rel" -ForegroundColor Red
        $allFound = $false
    }
}

if (-not $allFound) {
    Write-Error "One or more required files missing from installed MSIX directory: $installDir"
    exit 1
}

# 6. Verify and Apply Loopback Exemption
$pfn = $pkg.PackageFamilyName
Write-Host "[*] Registering loopback exemption for PFN: $pfn ..." -ForegroundColor Yellow
& CheckNetIsolation.exe LoopbackExempt -a -n=$pfn
Start-Sleep -Seconds 1

$exemptions = & CheckNetIsolation.exe LoopbackExempt -s
if ($exemptions -like "*$pfn*") {
    Write-Host "[+] Loopback exemption successfully registered and active for $pfn!" -ForegroundColor Green
} else {
    Write-Warning "CheckNetIsolation did not list $pfn. Network isolation may block localhost calls."
}

Write-Host "==========================================" -ForegroundColor Green
Write-Host "   MSIX Installed Verification PASSED!    " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
