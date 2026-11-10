# ADFIP — Windows Forensic Tool Compatibility & Dependency Manifest

**Document Version:** 1.0.0
**Target Platform:** Windows 10 / Windows 11 x64 (AMD64)
**Application Architecture:** Tauri v2 Native Desktop Shell + PyInstaller Bundled Backend
**Registry Reference:** `forensic_tools/registry.py`
**Tool Boundary Enforcement:** Strict authenticity inspection, safe non-destructive version handshakes, PID-based process lifetime tracking, and zero synthetic mocks.

---

## 1. Executive Summary

ADFIP (Autonomous Digital Forensic Investigation Platform) integrates native digital forensic utilities and library adapters into an evidence-driven, explainable investigation system. Under Windows 10/11 x64, tools are discovered authoritatively through:
1. System `%PATH%`
2. Per-user tools repository: `%LOCALAPPDATA%\ADFIP\tools\bin`
3. Standard Windows program locations (`C:\Program Files\The Sleuth Kit\bin`, `C:\Program Files\Wireshark`, `C:\ProgramData\chocolatey\bin`, `C:\tools`)
4. Dedicated Python environment scripts directory (`volatility-env\Scripts\vol.exe`, `backend\.venv\Scripts`)
5. In-process pure Python library adapters (`python-evtx`)

ADFIP guarantees that **no tool is marked available merely because an adapter exists**, and **no mock implementations or synthetic outputs are substituted**. If a native binary is not installed or fails its version probe, its real availability is reported as unavailable, preventing ungrounded claims.

---

## 2. Tool-by-Tool Windows Matrix

| Tool ID | Display Name | Windows Executable / Adapter | Arch | Windows Native Availability | Minimum Tested Version | Required Host Dependencies | Detection Command & Expected Handshake | Supported Evidence Types |
|---|---|---|---|---|---|---|---|---|
| `sleuthkit` | The Sleuth Kit (fls) | `fls.exe` | x64 | **Available** (Chocolatey / Official Win64 release) | >= 4.10.0 | Visual C++ 2015-2022 Redistributable | `fls.exe -V` -> `The Sleuth Kit ver X.X.X` | `disk_image`, `filesystem_image` |
| `mmls` | SleuthKit mmls | `mmls.exe` | x64 | **Available** (Sleuth Kit bundle) | >= 4.10.0 | Visual C++ 2015-2022 Redistributable | `mmls.exe -V` -> `The Sleuth Kit ver X.X.X` | `disk_image`, `filesystem_image`, `raw`, `dd`, `e01` |
| `fsstat` | SleuthKit fsstat | `fsstat.exe` | x64 | **Available** (Sleuth Kit bundle) | >= 4.10.0 | Visual C++ 2015-2022 Redistributable | `fsstat.exe -V` -> `The Sleuth Kit ver X.X.X` | `disk_image`, `filesystem_image`, `raw`, `dd` |
| `istat` | SleuthKit istat | `istat.exe` | x64 | **Available** (Sleuth Kit bundle) | >= 4.10.0 | Visual C++ 2015-2022 Redistributable | `istat.exe -V` -> `The Sleuth Kit ver X.X.X` | `disk_image`, `filesystem_image`, `raw`, `dd` |
| `icat` | SleuthKit icat | `icat.exe` | x64 | **Available** (Sleuth Kit bundle) | >= 4.10.0 | Visual C++ 2015-2022 Redistributable | `icat.exe -V` -> `The Sleuth Kit ver X.X.X` | `disk_image`, `filesystem_image`, `raw`, `dd` |
| `yara` | YARA Scanner | `yara.exe` / `yara-python` | x64 | **Available** (Official VirusTotal Win64 / pip wheel) | >= 4.2.0 | Visual C++ 2015-2022 Redistributable | `yara.exe --version` -> `4.x.x` | `executable`, `malware`, `suspicious_file`, `pe_executable`, `binary` |
| `exiftool` | ExifTool Metadata Extractor | `exiftool.exe` | x64 | **Available** (Phil Harvey standalone Windows executable) | >= 12.00 | None (self-contained Perl runtime) | `exiftool.exe -ver` -> `12.xx` | `image`, `document`, `archive`, `audio`, `video`, `file`, `metadata` |
| `volatility3` | Volatility 3 Memory Forensics | `vol.exe` / Python module | x64 | **Available** (pip wheel / PyInstaller vol.exe) | >= 2.4.0 | Python 3.10-3.12 x64 (`pefile`, `capstone`) | `vol.exe -h` -> `Volatility 3 Framework` | `memory_dump`, `raw_memory`, `vmem`, `dmp` |
| `python-evtx` | python-evtx Parser | In-Process Adapter (`import Evtx`) | Any | **Available** (Bundled in backend PyInstaller package) | >= 0.7.4 | Python runtime | Dynamic module import validation | `log`, `event_log`, `evtx`, `system_log` |
| `sqlite3` | SQLite3 CLI | `sqlite3.exe` | x64 | **Available** (sqlite.org official tools bundle) | >= 3.35.0 | None (statically linked) | `sqlite3.exe --version` -> `3.xx.x` | `sqlite_database`, `browser_artifact`, `history`, `mobile_database` |
| `strings` | GNU Strings / Sysinternals | `strings.exe` | x64 | **Available** (MinGW64 or Sysinternals strings64.exe) | >= 2.30 | None | `strings.exe -v` or `--version` | `binary`, `executable`, `memory_dump`, `raw`, `pe_executable` |
| `file` | File (libmagic) | `file.exe` | x64 | **Available** (GnuWin32 / Git for Windows `usr\bin\file.exe`) | >= 5.0 | `magic.mgc` database file | `file.exe --version` -> `file-5.xx` | `file`, `binary`, `disk_image`, `memory_dump` |
| `tcpdump` | WinDump / Packet Analyzer | `windump.exe` or `tcpdump.exe` | x64 | **Conditional** (Requires Npcap / WinPcap driver) | >= 4.9.0 | Npcap driver installed with WinPcap compatibility | `windump.exe --version` -> `tcpdump version 4.x` | `pcap_capture`, `pcap`, `network_capture` |
| `tshark` | TShark (Wireshark CLI) | `tshark.exe` | x64 | **Available** (Official Wireshark Win64 Installer) | >= 4.0.0 | Npcap driver | `tshark.exe --version` -> `TShark (Wireshark) 4.x` | `pcap_capture`, `pcap`, `network_capture` |

---

## 3. Windows Dependency Installation & Provisioning

For automated deployments or investigator workstations, tools can be provisioned using standard package managers.

### 3.1 Chocolatey (Automated PowerShell Installation)

Run from an elevated PowerShell terminal:

```powershell
# Core Package Manager Setup
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Visual C++ 2015-2022 Runtime (Prerequisite for SleuthKit, YARA, Python)
choco install vcredist140 -y

# Digital Forensic Tooling
choco install sleuthkit -y          # fls, mmls, fsstat, istat, icat
choco install exiftool -y           # ExifTool standalone executable
choco install yara -y               # Official YARA x64 binary
choco install sqlite-tools.commandline -y  # sqlite3.exe
choco install wireshark -y          # tshark.exe and Npcap driver
choco install sysinternals -y       # strings.exe
```

### 3.2 Winget (Microsoft Windows Package Manager)

```cmd
winget install Microsoft.VCRedist.2015+.x64
winget install WiresharkFoundation.Wireshark
winget install PhilHarvey.ExifTool
winget install SQLite.SQLite
```

### 3.3 Standalone Zip Deployment (Per-User Safe Location)

Investigators without local administrative rights can place portable 64-bit binaries into:
`%LOCALAPPDATA%\ADFIP\tools\bin\`

ADFIP automatically discovers binaries placed in this folder upon startup.
Example structure:
```text
%LOCALAPPDATA%\ADFIP\tools\bin\
├── fls.exe
├── mmls.exe
├── fsstat.exe
├── istat.exe
├── icat.exe
├── yara.exe
├── exiftool.exe
├── sqlite3.exe
└── strings.exe
```

---

## 4. Volatility 3 Memory Forensics on Windows

Volatility 3 can run in two approved configurations on Windows:

1. **Virtualenv Subprocess (Recommended):**
   - Installed inside `%LOCALAPPDATA%\ADFIP\volatility-env` or `<AppRoot>\volatility-env`.
   - Executable path: `<AppRoot>\volatility-env\Scripts\vol.exe` (or `vol.py` invoked via `Scripts\python.exe`).
   - Pip installation:
     ```cmd
     python -m venv volatility-env
     volatility-env\Scripts\python.exe -m pip install --upgrade pip
     volatility-env\Scripts\pip.exe install volatility3
     ```
2. **PyInstaller Packaged Binary:**
   - Pre-compiled standalone `vol.exe` placed in `%LOCALAPPDATA%\ADFIP\tools\bin\vol.exe`.

---

## 5. Security & Isolation Controls

1. **Disallowed Dangerous Binaries:**
   The following shells and interpreters are strictly banned from execution via the tool runner:
   `cmd.exe`, `powershell.exe`, `pwsh.exe`, `bash.exe`, `python.exe` (except approved virtualenv launcher for Volatility).
2. **Strict Non-Elevated Execution:**
   All tools are launched with standard user privileges. Raw physical drive access (`\\.\PhysicalDrive0`) on Windows requires elevation; if required, investigator is prompted through an explicit elevation gate rather than elevating the entire application.
3. **Subprocess Lifetime Tracking:**
   Process creation time is captured using the Win32 `GetProcessTimes` API (`OpenProcess` with `PROCESS_QUERY_LIMITED_INFORMATION`). If a tool execution times out or is cancelled, process identity is verified to prevent PID collision before issuing `proc.kill()` and `taskkill /F /T /PID <pid>`.
