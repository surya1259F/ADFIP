# ADFIP — Microsoft Store Submission Preparation Guide

**Document Version:** 1.0.0
**Application Name:** ADFIP (Autonomous Digital Forensic Investigation Platform)
**Package Identifier:** `com.adfip.desktop`
**Publisher:** Registered Microsoft Partner Developer Account
**Distribution Category:** Security & Forensic Utilities / Developer Tools
**Target OS:** Windows 10 (Build 19041+) and Windows 11 x64 (AMD64)

---

## 1. Store Identity & App Package Properties

When creating your application in the [Microsoft Partner Center](https://partner.microsoft.com/dashboard):

| Property | Value | Notes |
|---|---|---|
| **App Name** | ADFIP | Reserved in Partner Center dashboard |
| **Package Name** | `ADFIP` (or assigned GUID) | Assigned by Microsoft Partner Center |
| **Package Display Name**| ADFIP — Autonomous Digital Forensic Investigation Platform | Visible to end users in Store |
| **Publisher ID** | `CN=XXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` | Matches developer signing certificate |
| **Publisher Display Name**| Your Verified Organization or Individual Name | Matches Microsoft Partner identity |
| **Version** | `0.1.0.0` (or current release) | Quad-part version format required (`Major.Minor.Build.Revision`) |
| **Target Architecture** | `x64` | Native 64-bit Windows execution |

---

## 2. Packaging Options for Microsoft Store

Microsoft Store supports distributing Windows desktop apps via two standard channels:

### Option A: Packaged MSIX Application (Recommended for Direct Store Hosting)
MSIX provides clean containerized installation, automatic updates via Windows Store, and zero registry pollution.
To produce an MSIX package:
1. Build the MSI installer using the GitHub Actions workflow or local WiX toolset:
   `npx tauri build --bundles msi`
2. Run the **MSIX Packaging Tool** (available from Microsoft Store on Windows 10/11) to convert the MSI to an MSIX package signed with your Partner Center certificate:
   ```cmd
   MsixPackagingTool.exe create-package --template ADFIP_Template.xml
   ```
3. Declare Desktop Bridge Full Trust Capability in `AppxManifest.xml`:
   ```xml
   <Capabilities>
       <rescap:Capability Name="runFullTrust" />
   </Capabilities>
   ```

### Option B: EXE / MSI Distribution via Store (Direct Win32 Download)
Microsoft Store allows developers to distribute traditional Win32 installers (`.exe` or `.msi`) directly:
1. Provide the NSIS per-user installer (`ADFIP_0.1.0_x64-setup.exe`) or MSI installer (`ADFIP_0.1.0_x64.msi`).
2. Provide silent install arguments:
   - NSIS EXE: `/S`
   - MSI: `/qn /norestart`
3. Provide uninstallation command and URL.

---

## 3. Visual Assets Manifest

All required store logo assets are located in `frontend/src-tauri/icons/`:

| Asset File | Canonical Store Dimension | Purpose | Status in ADFIP |
|---|---|---|---|
| `StoreLogo.png` | 50 x 50 px | Primary Microsoft Store badge | **Available** (`frontend/src-tauri/icons/StoreLogo.png`) |
| `Square44x44Logo.png` | 44 x 44 px | Windows Taskbar and Start list icon | **Available** (`frontend/src-tauri/icons/Square44x44Logo.png`) |
| `Square71x71Logo.png` | 71 x 71 px | Small Start Menu Tile | **Available** (`frontend/src-tauri/icons/Square71x71Logo.png`) |
| `Square150x150Logo.png` | 150 x 150 px | Medium Start Menu Tile / App Icon | **Available** (`frontend/src-tauri/icons/Square150x150Logo.png`) |
| `Square310x310Logo.png` | 310 x 310 px | Large Start Menu Tile / Store Feature | **Available** (`frontend/src-tauri/icons/Square310x310Logo.png`) |
| `icon.ico` | 16x16, 32x32, 48x48, 256x256 | Windows Explorer Shell Icon | **Available** (`frontend/src-tauri/icons/icon.ico`) |

### Store Screenshots Requirement
Before submission, capture 4 high-resolution 16:9 PNG screenshots (minimum `1920 x 1080`):
1. **Case Overview & Digital Evidence Intake:** Demonstrating SHA-256 preservation and custody verification.
2. **Evidence Intelligence & Entropy Distribution:** Showing Shannon entropy heatmap and partition structure.
3. **Investigation Requirements & AI Assessment:** Showing the 5-tier explainable hypothesis assessment.
4. **Professional Forensic Report Generator:** Demonstrating canonical PDF and DOCX export.

---

## 4. Store Listing Metadata & Descriptions

### Short Description (Up to 100 characters)
> Autonomous, evidence-driven digital forensic investigation, AI assessment, and professional reporting.

### Full Product Description
> **ADFIP (Autonomous Digital Forensic Investigation Platform)** is a professional, evidence-driven desktop platform built for digital forensic investigators, incident responders, and law enforcement analysts.
>
> **Key Capabilities:**
> - **Integrity & Custody Verification:** Strict SHA-256 cryptographic hashing, evidence vault preservation, and immutable audit logging.
> - **Evidence Intelligence:** Real Shannon entropy calculation, file signature carving, and metadata extraction.
> - **Investigation Requirements Engine:** Specify incident queries and map requirements to digital artifacts.
> - **Specialist Agent Orchestration:** Explainable, human-governed execution of native forensic tools (The Sleuth Kit, YARA, ExifTool, Volatility 3, python-evtx).
> - **5-Tier AI Assessment:** Correlate findings, timeline events, and artifact relationships to calculate an explainable evidence-strength score.
> - **Professional Reports:** Export canonical court-ready PDF and editable DOCX forensic reports with full chain-of-custody documentation.

### Product Features (Bullet points)
- Autonomous digital forensic analysis with investigator-in-the-loop governance
- Comprehensive support for disk images, memory dumps, Windows Event Logs, and suspicious binaries
- Real-time Shannon entropy calculations and visual file analysis
- Automated timeline reconstruction and cross-domain correlation
- Standalone local execution: investigative data remains entirely on your machine
- One-click court-admissible PDF and DOCX report generation

### Search Keywords
`forensics`, `digital forensics`, `incident response`, `DFIR`, `malware analysis`, `investigation`, `evidence vault`, `sleuthkit`, `yara`, `volatility`

---

## 5. Privacy Policy & Compliance Declarations

### Privacy Policy Template
ADFIP operates with a **Local-First Privacy Architecture**:
- All digital evidence, case databases, artifacts, logs, and generated reports remain strictly within the user's local storage (`%LOCALAPPDATA%\ADFIP`).
- No evidentiary data, file contents, or personal information is transmitted to external servers without explicit investigator configuration of third-party LLM API keys (Google Gemini, OpenRouter).
- When configured, AI queries transmit only the abstracted investigation requirements and normalized metadata necessary for reasoning, never raw disk images or binary payloads.

### Age Rating
- **IARC Rating:** Unrestricted / Suitable for professionals (Contains no objectionable content).

### Windows Capabilities Declarations
- **runFullTrust:** Required for spawning local backend process and executing verified native forensic analysis tools.
