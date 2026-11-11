# ADFIP — Microsoft Store MSIX Deployment & Submission Guide

This guide describes the Microsoft Store submission, packaging architecture, and production validation for **ADFIP (Autonomous Digital Forensic Investigation Platform)**.

---

## 1. Application Architecture in MSIX

ADFIP operates on Windows 10/11 using a desktop bridge architecture:

- **Frontend Container:** Tauri v2 with Microsoft Edge WebView2 rendering React + TypeScript + Vite.
- **Backend Service:** Standalone PyInstaller one-folder executable (`adfir-backend.exe` with bundled Python runtime, FastAPI, SQLite engine, and Alembic migrations).
- **Execution Mode:** `Windows.FullTrustApplication` under the Desktop Bridge (`rescap:runFullTrust`).
- **Data Isolation:** All mutable data (forensic case databases, evidence vault, chain-of-custody records, logs, and generated PDF/DOCX reports) is stored in the user's writable data folder (`%LOCALAPPDATA%\ADFIP`), leaving the MSIX package directory strictly read-only.
- **Inter-Process Security:** The frontend discovers the backend dynamically on an ephemeral loopback port and authenticates every request using a cryptographically random 256-bit bootstrap secret passed via `X-ADFIP-Bootstrap-Secret` and `X-ADFIR-Bootstrap-Secret` HTTP headers.

---

## 2. Package Manifest Configuration (`msix/AppxManifest.xml`)

The MSIX package manifest is located at `msix/AppxManifest.xml`.

```xml
<?xml version="1.0" encoding="utf-8"?>
<Package
    xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
    xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
    xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
    IgnorableNamespaces="uap rescap">

  <Identity
      Name="ADFIP.AutonomousForensicPlatform"
      Publisher="CN=ADFIPDev, O=ADFIP, C=US"
      Version="0.1.0.0"
      ProcessorArchitecture="x64" />

  <Properties>
    <DisplayName>ADFIP - Autonomous Digital Forensic Investigation Platform</DisplayName>
    <PublisherDisplayName>ADFIP Team</PublisherDisplayName>
    <Description>Autonomous Digital Forensic Investigation, AI Assessment, Specialist Agent Orchestration and Professional Reporting Platform.</Description>
    <Logo>Assets\StoreLogo.png</Logo>
  </Properties>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.22621.0" />
  </Dependencies>

  <Resources>
    <Resource Language="en-us" />
  </Resources>

  <Applications>
    <Application Id="ADFIP" Executable="ADFIP.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
          DisplayName="ADFIP"
          Description="Autonomous Digital Forensic Investigation Platform"
          Square150x150Logo="Assets\Square150x150Logo.png"
          Square44x44Logo="Assets\Square44x44Logo.png"
          BackgroundColor="transparent">
        <uap:DefaultTile Wide310x150Logo="Assets\Wide310x150Logo.png" Square71x71Logo="Assets\Square71x71Logo.png">
          <uap:ShowNameOnTiles>
            <uap:ShowOn Tile="square150x150Logo" />
            <uap:ShowOn Tile="wide310x150Logo" />
          </uap:ShowNameOnTiles>
        </uap:DefaultTile>
        <uap:SplashScreen Image="Assets\SplashScreen.png" />
      </uap:VisualElements>
    </Application>
  </Applications>

  <Capabilities>
    <!-- Full trust capability required for packaged desktop application with bundled Python backend execution -->
    <rescap:Capability Name="runFullTrust" />
    <Capability Name="internetClient" />
    <Capability Name="internetClientServer" />
    <Capability Name="privateNetworkClientServer" />
  </Capabilities>
</Package>
```

---

## 3. Microsoft Partner Center Setup

### 3.1. Account & App Reservation
1. Sign in to the [Microsoft Partner Center](https://partner.microsoft.com/dashboard).
2. Under **Windows & Xbox**, select **Overview** > **Create a new app**.
3. Reserve your application product name (e.g. `ADFIP` or `ADFIP - Autonomous Digital Forensic Investigation Platform`).

### 3.2. Updating Identity for Production Submission
Once the app name is reserved in Partner Center:
1. Navigate to **App management** > **App identity**.
2. Note down:
   - **Package/Identity/Name**
   - **Package/Identity/Publisher** (e.g. `CN=12345678-ABCD-EF01-...`)
   - **Package/Properties/PublisherDisplayName**
3. Update `msix/AppxManifest.xml` and `msix/winapp.yaml` with these exact values prior to final release build.

---

## 4. Capability Justification Templates for Microsoft Store Review

When submitting an app utilizing restricted capabilities (`runFullTrust`), Partner Center prompts for a justification description. Use the following text:

### `runFullTrust` Justification:
> "ADFIP (Autonomous Digital Forensic Investigation Platform) is a digital forensic analysis workstation designed for legal, corporate, and law enforcement forensic investigators. The application bundles an isolated local Python forensic processing engine that performs SHA-256 evidence integrity hashing, forensic disk and memory image parsing, metadata extraction, timeline reconstruction, and cryptographic report generation. The `runFullTrust` capability is necessary to spawn the packaged companion backend service on an ephemeral loopback socket, access investigator-selected disk evidence files via standard Windows file pickers, and execute certified forensic analysis modules."

### Network Capabilities (`internetClient`, `privateNetworkClientServer`):
> "The network capabilities are required for authenticated inter-process loopback communication between the application's desktop presentation layer and its local forensic processing engine on 127.0.0.1, as well as connecting to secure cloud AI intelligence providers (such as Google Gemini API) when explicitly requested by the investigator."

---

## 5. Automated Build and Sideload Verification

### 5.1. Building via GitHub Actions CI
The repository includes `.github/workflows/windows-desktop-release.yml`, which runs on `windows-latest`:
- Compiles backend with PyInstaller into `dist/adfir-backend/`
- Runs 22 backend deployment and security tests
- Compiles frontend Vite assets and runs 36 frontend tests
- Compiles Tauri desktop binary
- Generates required MSIX visual assets via `python scripts/prepare_msix_assets.py`
- Packages the MSIX using `scripts/package-msix.ps1`
- Installs and verifies the MSIX using `scripts/verify-msix-installed.ps1`
- Uploads the signed `.msix` alongside NSIS and MSI installers

### 5.2. Local Windows Build Instructions
From PowerShell (Administrator recommended for local cert installation):
```powershell
# 1. Prepare MSIX visual assets
python scripts/prepare_msix_assets.py

# 2. Package and sign MSIX
powershell -ExecutionPolicy Bypass -File scripts/package-msix.ps1 -Version "0.1.0.0"

# 3. Sideload install and verify loopback exemption
powershell -ExecutionPolicy Bypass -File scripts/verify-msix-installed.ps1
```

---

## 6. Sideloading and Loopback Exemption

When testing sideloaded MSIX packages on Windows:
1. Double-click the generated developer certificate `build/msix_staging/devcert.pfx` (password: `TestPassword123!`), install to **Local Machine** > **Trusted Root Certification Authorities** and **Trusted People**.
2. Install the package:
   ```powershell
   Add-AppxPackage -Path dist/ADFIP_0.1.0.0_x64.msix
   ```
3. Grant loopback exemption (built into `scripts/verify-msix-installed.ps1`):
   ```powershell
   CheckNetIsolation.exe LoopbackExempt -a -n=(Get-AppxPackage -Name *ADFIP*).PackageFamilyName
   ```

*Note: For packages downloaded directly from the Microsoft Store by end users, Microsoft Store automatically manages signing, and the application includes self-registration for loopback exemptions on startup.*

---

## 7. Submission Checklist

- [x] Tested clean startup without requiring manual `uvicorn` invocation.
- [x] Verified database migrations execute cleanly inside `%LOCALAPPDATA%\ADFIP\adfir.db`.
- [x] Verified frontend dynamic port discovery and cryptographic bootstrap handshake.
- [x] MSIX AppxManifest contains correct `TargetDeviceFamily`, `runFullTrust`, and network capabilities.
- [x] All 7 MSIX visual assets verified (logos, splash screen, wide tile).
- [x] Windows App Certification Kit (WACK) compatible.
- [x] Privacy policy provided in application and Partner Center listing.
- [x] Zero API keys, test passwords, or private evidence committed to the repository.
