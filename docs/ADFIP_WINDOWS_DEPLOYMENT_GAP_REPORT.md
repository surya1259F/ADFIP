# ADFIP — Windows Desktop Deployment Gap Report
**Project:** Autonomous Digital Forensic Investigation Platform (ADFIP)
**Target Environment:** Windows 10/11 x64
**Date:** 2026-11-10
**Repository Branch:** `feature/frontend-rebuild`

---

## 1. Executive Summary

This deployment audit evaluates the entire ADFIP repository against the requirements for native Windows 10/11 x64 execution, PyInstaller backend compilation, Tauri v2 desktop packaging (NSIS EXE & MSI), and Microsoft Store readiness.

---

## 2. Component-by-Component Gap Analysis

### 2.1 Tauri Configuration (`frontend/src-tauri/tauri.conf.json`)
* **Product Identity:** `productName` is set to `"adfir"` instead of `"ADFIP"`. Window title refers to legacy acronym.
* **Packaging Targets:** `bundle.targets` is currently configured as `["deb", "rpm"]` (Linux only). Windows installer targets `["nsis", "msi"]` are missing.
* **Installer Security & Privilege Elevation:** Missing `bundle.windows.nsis` configuration with `installMode: "currentUser"` to ensure the application installs safely to per-user directories (`%LOCALAPPDATA%\Programs\ADFIP`) without requiring Administrator UAC elevation.
* **Resource Bundle Layout:** The resources path `../../dist/adfir-backend/**/*` must match the Windows PyInstaller directory layout containing `adfir-backend.exe` and its runtime dependencies.

### 2.2 Backend Dependencies (`backend/requirements.txt`)
* **Incompatible Unix Dependency:** `uvloop==0.23.0` is declared without platform guards. `uvloop` does not support Windows and crashes during `pip install` on Windows.
  - *Fix:* Guard with environment marker: `uvloop==0.23.0; sys_platform != 'win32'`.
* **Missing Core Dependencies:**
  - `reportlab>=4.0.0` (required for PDF report generation)
  - `python-docx>=1.0.0` (required for DOCX report generation)
  - `python-evtx>=0.7.4` (required for Windows Event Log artifact parsing)
  - `yara-python>=4.5.0` (required for binary signature analysis)
  - `pyinstaller>=6.5.0` (required for Windows executable compilation)

### 2.3 Backend Packaging Spec (`backend/adfir-backend.spec`)
* **Missing Hidden Imports:** The PyInstaller analysis list lacks newly added modules:
  - `backend.app.services.document_generators`
  - `backend.app.services.entropy`
  - `backend.app.services.decision_engine`
  - `backend.app.services.final_report`
  - `backend.app.api.v1.endpoints.strategy`
  - `reportlab`, `reportlab.lib`, `reportlab.platypus`, `reportlab.pdfgen`
  - `docx`, `docx.oxml`, `docx.shared`
  - `yara`
  - `Evtx`
  - `alembic`, `alembic.config`, `alembic.command`, `alembic.runtime.migration`
* **Static Data Assets:** Alembic migration scripts and configuration must be guaranteed to bundle properly across cross-platform Path separators.

### 2.4 Data Directory & Path Safety (`config.py` & `backend_manager.rs`)
* **User Data Storage:**
  - On Windows, `get_user_data_dir()` resolves `%LOCALAPPDATA%\adfir`. This should be updated to `%LOCALAPPDATA%\ADFIP` with fallback to preserve existing data.
  - Mutable databases (`adfir.db`), evidence vaults, logs, and generated reports correctly reside in user data, never in `Program Files`.
* **Virtual Environment Directory Structure:**
  - `config.py` lines 116-121 hardcode `volatility-env/bin/python` and `volatility-env/bin/vol`.
  - On Windows, virtual environments use `Scripts\python.exe` and `Scripts\vol.exe`.
  - Must use platform-aware path resolution.

### 2.5 Forensic Tool Registry (`forensic_tools/registry.py`)
* **Windows Binaries:**
  - SleuthKit: `fls.exe`, `mmls.exe`, `fsstat.exe`
  - Volatility 3: `vol.exe` in `Scripts\` or `volatility3` module
  - YARA: `yara.exe` or in-process `yara-python`
  - python-evtx: 100% platform-independent pure Python library adapter
* **Execution Safety:** Tool registry strictly validates paths, checks for synthetic markers, enforces `shell=False`, and handles `.exe` suffixes cleanly on Windows.

### 2.6 Tauri Backend Manager (`backend_manager.rs`)
* **Process Lifecycle:**
  - `GetProcessTimes` Win32 API is already implemented via FFI to track process start time on Windows.
  - Graceful shutdown via authenticated HTTP `POST /api/v1/system/shutdown` is preserved.
  - Process tree kill on Windows should utilize `taskkill /F /T /PID <pid>` fallback when the child process does not exit cleanly.

### 2.7 CI/CD Automation
* No Windows GitHub Actions workflow exists to build `adfir-backend.exe` and the Tauri NSIS/MSI installers.
* Needs `.github/workflows/windows-desktop-release.yml` with `windows-latest` runner.

---

## 3. Deployment Action Plan
1. **Phase 2:** Update PyInstaller `.spec` and `entrypoint.py` for comprehensive Windows x64 bundling. Fix `requirements.txt` platform markers.
2. **Phase 3:** Verify forensic tool registry paths for Windows executables and virtual environment layouts.
3. **Phase 4:** Configure `tauri.conf.json` for product name `ADFIP`, NSIS and MSI bundle targets, and robust Windows sidecar/resource resolution. Enhance `backend_manager.rs` for Windows process tree termination.
4. **Phase 5 & 6:** Ensure user data isolation in `%LOCALAPPDATA%\ADFIP` and loopback security.
5. **Phase 7:** Add automated test coverage for Windows path resolution, backend packaging spec, and desktop lifecycle.
6. **Phase 8:** Author the Windows GitHub Actions workflow for automated x64 packaging.
7. **Phase 9:** Prepare Microsoft Store assets and manifest configurations.
