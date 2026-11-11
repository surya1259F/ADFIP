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

$ErrorActionPreference = "Continue"
$root = (Get-Item $PSScriptRoot).Parent.FullName

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   ADFIP Windows MSIX Packaging Pipeline  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Locate Tauri Executable
$tauriCandidates = @(
    (Join-Path $root "frontend\src-tauri\target\release\ADFIP.exe"),
    (Join-Path $root "frontend\src-tauri\target\release\app.exe"),
    (Join-Path $root "src-tauri\target\release\ADFIP.exe"),
    (Join-Path $root "src-tauri\target\release\app.exe")
)
$tauriExe = $null
foreach ($cand in $tauriCandidates) {
    if (Test-Path $cand) {
        $tauriExe = (Get-Item $cand).FullName
        break
    }
}

if (-not $tauriExe) {
    $searchDirs = @(
        (Join-Path $root "frontend\src-tauri\target\release"),
        (Join-Path $root "src-tauri\target\release")
    )
    foreach ($sDir in $searchDirs) {
        if (Test-Path $sDir) {
            $foundExes = Get-ChildItem -Path $sDir -Filter "*.exe" -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notlike "*build*" -and $_.Name -notlike "*test*" }
            if ($foundExes) {
                $tauriExe = ($foundExes | Sort-Object Length -Descending | Select-Object -First 1).FullName
                break
            }
        }
    }
}

if (-not $tauriExe) {
    Write-Error "Tauri release executable not found! Checked: $($tauriCandidates -join ', ')"
    exit 1
}
Write-Host "[+] Found Tauri executable: $tauriExe" -ForegroundColor Green

# 2. Locate Backend Distribution Directory
$backendDir = Join-Path $root "dist\adfir-backend"
if (-not (Test-Path (Join-Path $backendDir "adfir-backend.exe"))) {
    Write-Error "Backend executable missing at $backendDir\adfir-backend.exe!"
    exit 1
}
Write-Host "[+] Found PyInstaller backend: $backendDir" -ForegroundColor Green

# 3. Verify Manifest and Assets
$manifestSrc = Join-Path $root "msix\AppxManifest.xml"
$assetsSrc = Join-Path $root "msix\Assets"
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

# Copy Backend one-folder distribution contents into adfir-backend\
$stageBackendDir = Join-Path $stagePath "adfir-backend"
New-Item -ItemType Directory -Path $stageBackendDir -Force | Out-Null
Copy-Item -Path "$backendDir\*" -Destination $stageBackendDir -Recurse -Force

# Copy Manifest and Assets
Copy-Item -Path $manifestSrc -Destination (Join-Path $stagePath "AppxManifest.xml") -Force

$stageAssetsDir = Join-Path $stagePath "Assets"
New-Item -ItemType Directory -Path $stageAssetsDir -Force | Out-Null
Copy-Item -Path "$assetsSrc\*" -Destination $stageAssetsDir -Recurse -Force

# Verify Staging Directory Content
$requiredStaged = @(
    "ADFIP.exe",
    "AppxManifest.xml",
    "Assets\StoreLogo.png",
    "Assets\Square150x150Logo.png",
    "Assets\Square44x44Logo.png",
    "Assets\SplashScreen.png",
    "adfir-backend\adfir-backend.exe"
)
foreach ($req in $requiredStaged) {
    $fullReq = Join-Path $stagePath $req
    if (-not (Test-Path $fullReq)) {
        Write-Error "Staging verification failed: Missing required file $req at $fullReq"
        exit 1
    }
    Write-Host "    [✓] Staged verified: $req" -ForegroundColor Green
}

$msixFile = Join-Path $outPath "ADFIP_$Version`_x64.msix"
if (Test-Path $msixFile) {
    Remove-Item $msixFile -Force
}

# 5. Locate Packaging Tools (Windows SDK MakeAppx.exe or WinApp CLI)
function Find-WindowsSdkTool([string]$toolName) {
    # 1. Direct command lookup if already in PATH
    $cmd = Get-Command $toolName -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    # 2. Check versioned subdirectories of Windows Kits 10
    $searchRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        "C:\Program Files\Windows Kits\10\bin"
    )
    foreach ($basePath in $searchRoots) {
        if (Test-Path $basePath) {
            $dirs = Get-ChildItem -Path $basePath -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending
            foreach ($d in $dirs) {
                $cand = Join-Path $d.FullName "x64\$toolName"
                if (Test-Path $cand) {
                    return $cand
                }
            }
            # Also check direct x64 subfolder
            $directCand = Join-Path $basePath "x64\$toolName"
            if (Test-Path $directCand) {
                return $directCand
            }
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

# Direct, deterministic packaging with Windows SDK MakeAppx
if (-not $makeAppx -or -not (Test-Path $makeAppx)) {
    Write-Error "MakeAppx.exe not found in Windows Kits! Cannot package MSIX."
    exit 1
}

Write-Host "[*] Packaging with MakeAppx: $makeAppx ..." -ForegroundColor Cyan
Write-Host "    Source directory: $stagePath"
Write-Host "    Output MSIX:      $msixFile"

$makeAppxOut = & "$makeAppx" pack /d "$stagePath" /p "$msixFile" /o /v /nv 2>&1
$ec = $LASTEXITCODE

Write-Host "[*] MakeAppx completed with exit code: $ec"
if ($ec -eq 0 -and (Test-Path $msixFile)) {
    $packaged = $true
    $f = Get-Item $msixFile
    Write-Host "[+] MakeAppx successfully produced: $msixFile ($([math]::Round($f.Length / 1MB, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "         MakeAppx Packaging Failed        " -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    $makeAppxOut | ForEach-Object { Write-Host "MakeAppx: $_" -ForegroundColor Red }
    $errLines = ($makeAppxOut | Where-Object { $_ -match "error|fail|0x|invalid" } | Select-Object -First 5) -join " -- "
    $lastFew = (($makeAppxOut | Select-Object -Last 10) -join " -- ")
    if ($errLines) {
        Write-Host "::error title=MakeAppx Error Details::$errLines"
    } else {
        Write-Host "::error title=MakeAppx Failure Tail::$lastFew"
    }
    Write-Error "Failed to package MSIX with MakeAppx! Exit code: $ec"
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
    & "$signTool" sign /fd SHA256 /f "$CertPath" /p "$CertPassword" "$msixFile"
    $signEc = $LASTEXITCODE
    if ($signEc -eq 0) {
        Write-Host "[+] Successfully signed MSIX package!" -ForegroundColor Green
    } else {
        Write-Warning "SignTool exited with code $signEc. Package is unsigned (acceptable for Store submission)."
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
