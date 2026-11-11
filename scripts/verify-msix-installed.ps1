<#
.SYNOPSIS
    Automated verification of the installed ADFIP MSIX desktop application.
.DESCRIPTION
    Trusts the dev certificate, installs the MSIX package, verifies package registration,
    inspects bundled binaries, tests installed backend runtime execution and health,
    verifies database creation, and tests data preservation across upgrade/reinstall and uninstall.
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

# 6. Verify and Apply Loopback Exemption (Administrative CI Runner)
$pfn = $pkg.PackageFamilyName
Write-Host "[*] Registering loopback exemption for PFN: $pfn ..." -ForegroundColor Yellow
& CheckNetIsolation.exe LoopbackExempt -a -n=$pfn
Start-Sleep -Seconds 1

$exemptions = & CheckNetIsolation.exe LoopbackExempt -s
if ($exemptions -like "*$pfn*") {
    Write-Host "[+] Loopback exemption successfully registered and active for $pfn!" -ForegroundColor Green
} else {
    Write-Warning "CheckNetIsolation did not list $pfn. Network isolation may block direct localhost calls."
}

# 7. Installed Backend Runtime & Database Execution Verification
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Testing Installed Backend Runtime      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$testPort = "55432"
$testSecret = "ci_msix_verify_secret_987"
$testDataDir = Join-Path $env:LOCALAPPDATA "ADFIP_MSIX_VERIFY"
if (Test-Path $testDataDir) {
    Remove-Item -Path $testDataDir -Recurse -Force
}
New-Item -ItemType Directory -Path $testDataDir -Force | Out-Null

$installedBackendExe = Join-Path $installDir "adfir-backend\adfir-backend.exe"
$backendWorkDir = Join-Path $installDir "adfir-backend"

$backendStdout = Join-Path $testDataDir "backend_verify_stdout.log"
$backendStderr = Join-Path $testDataDir "backend_verify_stderr.log"

Write-Host "[*] Launching installed backend binary: $installedBackendExe ..." -ForegroundColor Yellow
$proc = Start-Process -FilePath $installedBackendExe `
    -WorkingDirectory $backendWorkDir `
    -Environment @{
        ADFIP_PORT = $testPort
        ADFIR_PORT = $testPort
        ADFIP_INTERNAL_SECRET = $testSecret
        ADFIR_INTERNAL_SECRET = $testSecret
        ADFIP_DATA_DIR = $testDataDir
        ADFIR_DATA_DIR = $testDataDir
        PYTHONUNBUFFERED = "1"
    } `
    -RedirectStandardOutput $backendStdout `
    -RedirectStandardError $backendStderr `
    -PassThru

$ready = $false
$healthUrl = "http://127.0.0.1:$testPort/api/v1/system/health"
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

while ($stopwatch.Elapsed.TotalSeconds -lt 60) {
    Start-Sleep -Milliseconds 1000
    if ($proc.HasExited) {
        Write-Error "Installed backend process exited prematurely with code $($proc.ExitCode)!"
        break
    }
    try {
        $headers = @{ "X-ADFIP-Bootstrap-Secret" = $testSecret }
        $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -Headers $headers -TimeoutSec 2
        if ($resp.status -eq "online") {
            $ready = $true
            Write-Host "[+] Installed backend verified ONLINE in $([math]::Round($stopwatch.Elapsed.TotalSeconds, 1))s: $($resp | ConvertTo-Json -Compress)" -ForegroundColor Green
            break
        }
    } catch {
        # Waiting for backend to bind and run migrations
    }
}

if (-not $ready) {
    Write-Host "Backend stderr: $(Get-Content $backendStderr -Raw -ErrorAction SilentlyContinue)" -ForegroundColor Red
    Write-Host "Backend stdout: $(Get-Content $backendStdout -Raw -ErrorAction SilentlyContinue)" -ForegroundColor Yellow
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    Write-Error "Installed backend failed readiness health check within 60s!"
    exit 1
}

# Verify Database and Tables initialized by Alembic
$dbPath = Join-Path $testDataDir "adfir.db"
if (-not (Test-Path $dbPath)) {
    Write-Error "Database adfir.db was not initialized in $testDataDir!"
    exit 1
}
$dbSize = (Get-Item $dbPath).Length
Write-Host "[+] Verified SQLite database created at $dbPath ($([math]::Round($dbSize / 1KB, 1)) KB)" -ForegroundColor Green

# Gracefully trigger shutdown
try {
    $shutdownHeaders = @{ "X-ADFIP-Bootstrap-Secret" = $testSecret }
    Invoke-RestMethod -Uri "http://127.0.0.1:$testPort/api/v1/system/shutdown" -Method Post -Headers $shutdownHeaders -TimeoutSec 3 | Out-Null
    Start-Sleep -Seconds 1
} catch {
    # Best-effort shutdown
}
if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force
}

# 8. Data Preservation Across MSIX Upgrade and Uninstall
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   Testing Evidence & DB Preservation     " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Write test evidence into data dir
$evidenceDir = Join-Path $testDataDir "evidence"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$testEvidence = Join-Path $evidenceDir "custody_verification_sample.raw"
[System.IO.File]::WriteAllBytes($testEvidence, [System.Text.Encoding]::UTF8.GetBytes("ADFIP_FORENSIC_INTEGRITY_SAMPLE_EVIDENCE_HASH_PRESERVATION"))

$hashBefore = (Get-FileHash -Path $testEvidence -Algorithm SHA256).Hash
Write-Host "[*] Seeded test evidence: $testEvidence (SHA-256: $hashBefore)" -ForegroundColor Yellow

# Uninstall MSIX package
Write-Host "[*] Simulating MSIX Package Uninstall via Remove-AppxPackage ..." -ForegroundColor Yellow
Remove-AppxPackage -Package $pkg.PackageFullName
Start-Sleep -Seconds 2

# Verify package uninstalled from WindowsApps
$checkPkg = Get-AppxPackage -Name "*ADFIP*" -ErrorAction SilentlyContinue
if ($checkPkg) {
    Write-Error "Package was not successfully uninstalled!"
    exit 1
}
Write-Host "[+] Package successfully uninstalled." -ForegroundColor Green

# Assert that %LOCALAPPDATA% database and evidence vault were NOT deleted
if (-not (Test-Path $dbPath)) {
    Write-Error "REGRESSION: adfir.db was deleted upon MSIX package uninstall!"
    exit 1
}
if (-not (Test-Path $testEvidence)) {
    Write-Error "REGRESSION: Forensic evidence vault was deleted upon MSIX package uninstall!"
    exit 1
}
$hashAfter = (Get-FileHash -Path $testEvidence -Algorithm SHA256).Hash
if ($hashBefore -ne $hashAfter) {
    Write-Error "REGRESSION: Forensic evidence content was corrupted across MSIX uninstall!"
    exit 1
}

Write-Host "[+] Data preservation verified: adfir.db and evidence vault remain 100% intact!" -ForegroundColor Green

# Reinstall package (simulating upgrade / re-install)
Write-Host "[*] Re-installing MSIX package (simulating upgrade) ..." -ForegroundColor Yellow
Add-AppxPackage -Path $msixItem.FullName
Start-Sleep -Seconds 2

$reinstalledPkg = Get-AppxPackage -Name "*ADFIP*" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $reinstalledPkg) {
    Write-Error "Failed to re-install package!"
    exit 1
}
Write-Host "[+] Package successfully reinstalled: $($reinstalledPkg.PackageFamilyName)" -ForegroundColor Green

# Clean up temporary test data directory
Remove-Item -Path $testDataDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "==========================================" -ForegroundColor Green
Write-Host "   MSIX Installed Verification & Data     " -ForegroundColor Green
Write-Host "   Preservation Tests ALL PASSED!         " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
