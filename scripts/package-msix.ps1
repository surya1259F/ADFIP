<#
.SYNOPSIS
    Packages and signs ADFIP into a Microsoft Store-compatible MSIX package.
.DESCRIPTION
    Stages the Tauri frontend binary, PyInstaller one-folder backend, MSIX manifest,
    and visual assets, then packages them into an MSIX file using WinApp CLI or MakeAppx.
#>

[CmdletBinding()]
param(
    [string]$Version = "0.1.0.0",
    [string]$StagingDir = "build/msix_staging",
    [string]$OutputDir = "dist",
    [string]$CertPath = "",
    [string]$CertPassword = "TestPassword123!",
    [switch]$CreateDevCert = $true
)

$ErrorActionPreference = "Stop"
$root = (Get-Item $PSScriptRoot).Parent.FullName

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   ADFIP Windows MSIX Packaging Pipeline  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Locate Tauri Executable
$tauriExes = @(
    "$root/frontend/src-tauri/target/release/ADFIP.exe",
    "$root/frontend/src-tauri/target/release/app.exe"
)
$tauriExe = $null
foreach ($cand in $tauriExes) {
    if (Test-Path $cand) {
        $tauriExe = (Get-Item $cand).FullName
        break
    }
}

if (-not $tauriExe) {
    Write-Error "Tauri release executable not found! Checked: $($tauriExes -join ', ')"
    exit 1
}
Write-Host "[+] Found Tauri executable: $tauriExe" -ForegroundColor Green

# 2. Locate Backend Distribution Directory
$backendDir = "$root/dist/adfir-backend"
if (-not (Test-Path "$backendDir/adfir-backend.exe")) {
    Write-Error "Backend executable missing at $backendDir/adfir-backend.exe!"
    exit 1
}
Write-Host "[+] Found PyInstaller backend: $backendDir" -ForegroundColor Green

# 3. Verify Manifest and Assets
$manifestSrc = "$root/msix/AppxManifest.xml"
$assetsSrc = "$root/msix/Assets"
if (-not (Test-Path $manifestSrc)) {
    Write-Error "MSIX AppxManifest missing at $manifestSrc!"
    exit 1
}
if (-not (Test-Path $assetsSrc)) {
    Write-Error "MSIX Assets folder missing at $assetsSrc!"
    exit 1
}
Write-Host "[+] Found AppxManifest and Assets" -ForegroundColor Green

# 4. Prepare Staging Directory
$stagePath = [System.IO.Path]::GetFullPath((Join-Path $root $StagingDir))
$outPath = [System.IO.Path]::GetFullPath((Join-Path $root $OutputDir))

if (Test-Path $stagePath) {
    Remove-Item -Path $stagePath -Recurse -Force
}
New-Item -ItemType Directory -Path $stagePath -Force | Out-Null
New-Item -ItemType Directory -Path $outPath -Force | Out-Null

Write-Host "[+] Staging files into $stagePath ..." -ForegroundColor Yellow

# Copy Frontend executable as ADFIP.exe
Copy-Item -Path $tauriExe -Destination (Join-Path $stagePath "ADFIP.exe") -Force

# Copy Backend one-folder distribution
Copy-Item -Path $backendDir -Destination (Join-Path $stagePath "adfir-backend") -Recurse -Force

# Copy Manifest and Assets
Copy-Item -Path $manifestSrc -Destination (Join-Path $stagePath "AppxManifest.xml") -Force
Copy-Item -Path $manifestSrc -Destination (Join-Path $stagePath "Package.appxmanifest") -Force
Copy-Item -Path $assetsSrc -Destination (Join-Path $stagePath "Assets") -Recurse -Force
if (Test-Path "$root/msix/winapp.yaml") {
    Copy-Item -Path "$root/msix/winapp.yaml" -Destination (Join-Path $stagePath "winapp.yaml") -Force
}

$msixFile = Join-Path $outPath "ADFIP_$Version`_x64.msix"
if (Test-Path $msixFile) {
    Remove-Item $msixFile -Force
}

# 5. Locate Packaging Tools (Windows SDK MakeAppx.exe or WinApp CLI)
function Find-WindowsSdkTool([string]$toolName) {
    $cmd = Get-Command $toolName -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $kitsBin = "C:\Program Files (x86)\Windows Kits\10\bin"
    if (Test-Path $kitsBin) {
        $versionDirs = Get-ChildItem -Path $kitsBin -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
            Sort-Object { [version]$_.Name } -Descending

        foreach ($vDir in $versionDirs) {
            $candidate = Join-Path $vDir.FullName "x64\$toolName"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    $fallbacks = @(
        "C:\Program Files (x86)\Windows Kits\10\bin\x64\$toolName",
        "C:\Program Files\Windows Kits\10\bin\x64\$toolName"
    )
    foreach ($cand in $fallbacks) {
        if (Test-Path $cand) {
            return $cand
        }
    }
    return $null
}

$makeAppx = Find-WindowsSdkTool "makeappx.exe"
$signTool = Find-WindowsSdkTool "signtool.exe"
$hasWinApp = [bool](Get-Command winapp -ErrorAction SilentlyContinue)

if ($makeAppx) {
    Write-Host "[+] Discovered Windows SDK MakeAppx: $makeAppx" -ForegroundColor Green
} else {
    Write-Host "[-] MakeAppx.exe not found in Windows Kits" -ForegroundColor Yellow
}
if ($signTool) {
    Write-Host "[+] Discovered Windows SDK SignTool: $signTool" -ForegroundColor Green
} else {
    Write-Host "[-] SignTool.exe not found in Windows Kits" -ForegroundColor Yellow
}

$packaged = $false

# Try MakeAppx first for direct, deterministic packaging
if ($makeAppx -and (Test-Path $makeAppx)) {
    Write-Host "[*] Packaging with MakeAppx: $makeAppx ..." -ForegroundColor Cyan
    $makeAppxOut = & $makeAppx pack /d $stagePath /p $msixFile /nv /o 2>&1
    Write-Host ($makeAppxOut -join "`n")
    if ($LASTEXITCODE -eq 0 -and (Test-Path $msixFile)) {
        $packaged = $true
        Write-Host "[+] MakeAppx successfully produced: $msixFile" -ForegroundColor Green
    } else {
        Write-Warning "MakeAppx failed with exit code $LASTEXITCODE. Trying WinApp CLI..."
    }
}

if (-not $packaged -and $hasWinApp) {
    Write-Host "[*] Packaging with WinApp CLI ..." -ForegroundColor Cyan
    $winappOut = & winapp pack $stagePath --output $msixFile 2>&1
    Write-Host ($winappOut -join "`n")
    if ($LASTEXITCODE -eq 0 -and (Test-Path $msixFile)) {
        $packaged = $true
        Write-Host "[+] WinApp CLI successfully produced: $msixFile" -ForegroundColor Green
    }
}

if (-not $packaged) {
    Write-Error "Failed to package MSIX! Neither MakeAppx nor WinApp CLI succeeded."
    exit 1
}

# 6. Signing (for Local Testing and Sideloading)
if ($CreateDevCert -and (-not $CertPath -or -not (Test-Path $CertPath))) {
    $certOut = Join-Path $stagePath "devcert.pfx"
    Write-Host "[*] Generating self-signed code signing certificate: $certOut ..." -ForegroundColor Yellow
    $securePass = ConvertTo-SecureString -String $CertPassword -Force -AsPlainText
    
    $existingCert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -eq "CN=ADFIPDev, O=ADFIP, C=US" } | Select-Object -First 1
    if (-not $existingCert) {
        $existingCert = New-SelfSignedCertificate `
            -Type Custom `
            -Subject "CN=ADFIPDev, O=ADFIP, C=US" `
            -KeyUsage DigitalSignature `
            -FriendlyName "ADFIP Development Signing Certificate" `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")
    }

    Export-PfxCertificate -Cert $existingCert -FilePath $certOut -Password $securePass | Out-Null
    $CertPath = $certOut
    Write-Host "[+] Ephemeral signing key generated at $CertPath for CI build signing only (PRIVATE KEY NOT DISTRIBUTED)" -ForegroundColor Green

    # Export PUBLIC certificate only (contains NO private keys, safe for developer trust installation)
    $publicCert = Join-Path $outPath "ADFIP_Dev_Public.cer"
    Export-Certificate -Cert $existingCert -FilePath $publicCert | Out-Null
    Write-Host "[+] Public certificate exported to $publicCert (NO private keys)" -ForegroundColor Green
}

if ($CertPath -and (Test-Path $CertPath) -and $signTool) {
    Write-Host "[*] Signing MSIX with SignTool: $signTool ..." -ForegroundColor Cyan
    $signOut = & $signTool sign /fd SHA256 /f $CertPath /p $CertPassword $msixFile 2>&1
    Write-Host ($signOut -join "`n")
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[+] Successfully signed MSIX package!" -ForegroundColor Green
    } else {
        Write-Warning "SignTool exited with code $LASTEXITCODE. Package is unsigned (acceptable for Store submission)."
    }
} else {
    Write-Host "[i] Skipping SignTool signing (Store ingestion will sign the package)." -ForegroundColor DarkGray
}

$finalMsix = Get-Item $msixFile
Write-Host "==========================================" -ForegroundColor Green
Write-Host "   MSIX Packaging Succeeded!              " -ForegroundColor Green
Write-Host "   Artifact: $($finalMsix.FullName)" -ForegroundColor Green
Write-Host "   Size:     $([math]::Round($finalMsix.Length / 1MB, 2)) MB" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
