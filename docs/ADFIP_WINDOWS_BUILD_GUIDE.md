# ADFIP — Windows Desktop Build & Distribution Guide

This document provides complete, step-by-step engineering instructions for building, bundling, and distributing the Autonomous Digital Forensic Investigation Platform (ADFIP) as a native Windows 10/11 desktop application using Tauri v2, PyInstaller, and NSIS/MSI.

---

## 1. System Architecture on Windows

ADFIP on Windows operates as a unified desktop application comprising three integrated layers:

```
+-------------------------------------------------------------------+
|               Tauri v2 Desktop Shell (Rust x64)                   |
|  - Windowing & WebView2 Host                                      |
|  - Native Windows File Dialog (PowerShell OpenFileDialog)          |
|  - Process Lifecycle & Watchdog (BackendManager)                   |
|  - Windows Process Times Verification (GetProcessTimes API)       |
+---------------------------------+---------------------------------+
                                  | Loopback HTTP (127.0.0.1:EPHEMERAL)
                                  | + Cryptographic Bootstrap Secret
                                  v
+-------------------------------------------------------------------+
|           FastAPI Forensic Backend (Compiled PyInstaller)         |
|  - REST & WebSocket APIs                                          |
|  - Forensic Agent Orchestrator (Disk, Memory, Log, Malware)       |
|  - SQLite Database Storage (%LOCALAPPDATA%\ADFIP\adfir.db)        |
|  - Evidence Vault & SHA-256 Immutability Engine                   |
+---------------------------------+---------------------------------+
                                  | Subprocess Spawning
                                  v
+-------------------------------------------------------------------+
|               Windows Forensic Toolchain (x64)                    |
|  - SleuthKit Windows CLI (fls.exe)                                |
|  - SQLite3 Windows Shell (sqlite3.exe)                            |
|  - Sysinternals / GNU Strings (strings.exe)                       |
|  - YARA Windows x64 (yara64.exe / yara-python dll)                |
|  - Volatility 3 Windows Standalone (vol.exe)                      |
+-------------------------------------------------------------------+
```

---

## 2. Windows Build Prerequisites

### 2.1 Hardware and OS
- Windows 10 (Build 19041+) or Windows 11 64-bit (x64).
- 16 GB RAM minimum (32 GB recommended for forensic memory analysis).
- 50 GB free disk space on SSD/NVMe.

### 2.2 Software Tools
1. **Visual Studio 2022 Build Tools**:
   - Workload: "Desktop development with C++"
   - Windows 10/11 SDK installed.
2. **Rust Toolchain**:
   - Install via `rustup-init.exe`.
   - Ensure default host is `x86_64-pc-windows-msvc`.
3. **Node.js & npm**:
   - Node.js LTS (v20.x or v22.x x64).
4. **Python**:
   - Python 3.11.x or 3.12.x 64-bit from python.org (check "Add Python to PATH").
5. **NSIS (Nullsoft Scriptable Install System)**:
   - NSIS v3.x or WiX Toolset v3.14 (for MSI packages).
6. **Microsoft Edge WebView2**:
   - Pre-installed on Windows 10/11.

---

## 3. Forensic Tools Distribution for Windows

Place verified Windows 64-bit forensic tool binaries in `resources/tools/windows/`:

| Tool | Windows Executable | Official Source | Integrity Verification |
| :--- | :--- | :--- | :--- |
| **SleuthKit** | `fls.exe`, `tsk_recover.exe`, etc. | SleuthKit Official Win64 Release | Verify SHA-256 against GitHub release |
| **SQLite3** | `sqlite3.exe` | sqlite-tools-win-x64.zip | Official SQLite downloads |
| **Strings** | `strings.exe` | Sysinternals / GNU Win32 | Microsoft Sysinternals Authenticode |
| **YARA** | `yara64.exe` | VirusTotal YARA Win64 Release | VirusTotal Release Signatures |
| **Volatility 3** | `vol.exe` | Volatility Foundation Release | PyInstaller-compiled official wheel |

Add `resources/tools/windows` to the backend subprocess PATH search order in `forensic_tools/registry.py`.

---

## 4. Packaging the Backend (PyInstaller)

The FastAPI backend must be compiled into a self-contained Windows executable so users do not need a pre-installed Python interpreter.

### 4.1 Create Windows Build Virtual Environment
```powershell
# In repository root:
python -m venv venv-win
.\venv-win\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

### 4.2 PyInstaller Build Script (`scripts/build_backend_win.py`)
```python
import PyInstaller.__main__
import os
import shutil

dist_dir = os.path.abspath("dist/adfir-backend")
if os.path.exists(dist_dir):
    shutil.rmtree(dist_dir)

PyInstaller.__main__.run([
    "backend/app/main.py",
    "--name=adfir-backend",
    "--onedir",
    "--noconsole",
    "--add-data=backend/app;backend/app",
    "--add-data=forensic_tools;forensic_tools",
    "--add-data=investigation;investigation",
    "--add-data=agents;agents",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.lifespan.on",
    "--hidden-import=aiosqlite",
    "--hidden-import=sqlalchemy.dialects.sqlite",
    "--hidden-import=google.genai",
    f"--distpath=dist",
    f"--workpath=build/pyinstaller",
    "--clean",
])
```

Execute backend build:
```powershell
python scripts/build_backend_win.py
```
This generates `dist/adfir-backend/adfir-backend.exe` alongside its runtime libraries.

---

## 5. Tauri Desktop Build Configuration

### 5.1 Update `frontend/src-tauri/tauri.conf.json` for Windows
Ensure the bundle targets include `nsis`:
```json
{
  "bundle": {
    "active": true,
    "targets": ["nsis", "msi"],
    "resources": [
      "../../dist/adfir-backend/**/*",
      "../../resources/tools/windows/**/*"
    ],
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": "http://timestamp.digicert.com",
      "nsis": {
        "installMode": "currentUser",
        "installerIcon": "icons/icon.ico",
        "languages": ["English"],
        "displayLanguageSelector": false
      }
    }
  }
}
```

### 5.2 Build Desktop Application
```powershell
cd frontend
npm install
npm run build
npm run tauri build
```

The resulting installer is generated at:
`frontend/src-tauri/target/release/bundle/nsis/adfir_0.1.0_x64-setup.exe`

---

## 6. Runtime Paths and Database Storage on Windows

On Windows, user files and forensic data must adhere to standard Windows filesystem conventions:

1. **Active Database**:
   - `%LOCALAPPDATA%\ADFIP\adfir.db` (e.g. `C:\Users\<User>\AppData\Local\ADFIP\adfir.db`)
   - The backend resolves `os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))` to prevent writing inside `Program Files`.
2. **Evidence Vault**:
   - Default: `%LOCALAPPDATA%\ADFIP\Vault`
   - Configurable in Settings: Investigators can select high-capacity dedicated forensic disks (e.g., `D:\EvidenceVault`).
3. **Audit Log Store**:
   - `%LOCALAPPDATA%\ADFIP\Audit\`
   - Protected with standard Windows file ACLs (read-only for non-admin users).

---

## 7. Windows Security, Antivirus, and Code Signing

### 7.1 Administrator Elevation (UAC)
- Forensic acquisition of live physical drives (`\\.\PhysicalDrive0`) requires Administrator elevation.
- Standard artifact analysis of pre-acquired images (`.dd`, `.raw`, `.db`) does **not** require elevation and runs safely in `currentUser` mode.
- If raw disk imaging is enabled, compile the executable with a UAC manifest specifying `<requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>`.

### 7.2 Antivirus False Positives (Windows Defender)
- Digital forensic platforms parse malware signatures, embedded PE binaries, and YARA patterns that frequently trigger heuristic AV alerts.
- **Remediation**:
  1. Sign all binaries (`adfir.exe`, `adfir-backend.exe`, and bundled DLLs) with a trusted Microsoft Authenticode EV (Extended Validation) code signing certificate.
  2. Document recommended Windows Defender folder exclusions for the Evidence Vault directory (`%LOCALAPPDATA%\ADFIP\Vault`).

---

## 8. Verification and Smoke Testing on Windows

After building the installer on a clean Windows machine:

1. **Install Test**:
   - Execute `adfir_0.1.0_x64-setup.exe`.
   - Verify installation completes without UAC errors.
2. **Launch & Backend Handshake**:
   - Launch ADFIP from Start Menu.
   - Verify `BackendManager` spawns `adfir-backend.exe` on an ephemeral port.
   - Verify health check handshake completes at `http://127.0.0.1:<PORT>/api/v1/system/health`.
3. **Forensic Execution Smoke Test**:
   - Load sample FAT32 disk image.
   - Run SleuthKit `fls.exe` analysis.
   - Verify artifacts and timeline are rendered in the UI.
4. **Clean Exit**:
   - Close window; verify background backend process terminates cleanly within 3 seconds.
