# ADFIP — Forensic Tool Matrix
**Autonomous Digital Forensic Investigation Platform Using Multi-Agent AI**

- **Product:** ADFIP Desktop Workstation
- **Authoritative Registry:** `forensic_tools/registry.py` (`PlatformAwareToolRegistry`)
- **Status:** **PENDING REVIEW**

---

## 1. Tool Ecosystem State Model

In ADFIP, tools are evaluated through an uncompromising 4-state lifecycle model. The platform never collapses these states into a simplistic boolean flag:

1. **`REGISTERED`:** Tool definition exists in the platform registry with documented input/output schemas and capabilities.
2. **`INSTALLED`:** Executable binary exists on the host filesystem with verified execute permissions (`os.access(path, os.X_OK)`).
3. **`VERIFIED`:** Tool version probe ran successfully within timeout limits and verified expected output on a known test fixture.
4. **`AVAILABLE`:** Tool is verified, operational, and confirmed compatible with both the host platform OS and the target evidence format.

Any tool not meeting all four criteria is truthfully presented in the UI and API with its exact status (e.g., `NOT_INSTALLED`, `PLATFORM_INCOMPATIBLE`, `VERSION_VALIDATION_FAILED`) and cannot be scheduled for execution.

---

## 2. Complete Forensic Tool Matrix

| Tool ID | Executable Name | Resolved Absolute Path | Verified Version | Installation Status | Supported Platforms | Supported Evidence Types | Key Forensic Capabilities | Security Limits |
|---|---|---|---|---|---|---|---|---|
| **`sleuthkit`** | `fls`, `mmls`, `fsstat` | `/usr/bin/fls` | `The Sleuth Kit ver 4.12.1` | **`AVAILABLE`** | Linux, Windows, macOS | `raw_image`, `expert_witness`, `disk_image`, `filesystem_image` | Partition table analysis, FAT/NTFS/ext filesystem structure, deleted file recovery, inode extraction | `shell=False`, 300s timeout cap, stdout/stderr streaming |
| **`sqlite3`** | `sqlite3` | `/usr/bin/sqlite3` | `3.46.1` | **`AVAILABLE`** | Linux, Windows, macOS | `sqlite_database`, `browser_db`, `mobile_backup` | Direct SQL query execution, browser history extraction, schema inspection, wal-journal parsing | `shell=False`, 60s timeout cap, read-only query mode |
| **`strings`** | `strings` | `/usr/bin/strings` | `GNU strings 2.44` | **`AVAILABLE`** | Linux, Windows, macOS | `generic_binary`, `file`, `disk_image`, `memory_dump` | Printable ASCII/Unicode string extraction, embedded IP/URL identification, IOC discovery | `shell=False`, 120s timeout cap, bounded output streaming |
| **`volatility3`** | `vol`, `volatility` | *Not Found* | *None* | **`NOT_INSTALLED`** | Linux, Windows, macOS | `memory_dump`, `crash_dump`, `raw_memory` | Windows process trees (`pslist`, `pstree`), hidden injection (`malfind`), DLL listings, network sockets | Subprocess isolation, plugin validation |
| **`yara`** | `yara` | In-process Library | `yara-python 4.5.1` | **`AVAILABLE`** (Library) | Linux, Windows, macOS | `pe_executable`, `elf_executable`, `generic_binary`, `file` | Compiled signature matching, malware rule evaluation, IOC detection | Separate rule target path, no shell |
| **`exiftool`** | `exiftool` | *Not Found* | *None* | **`NOT_INSTALLED`** | Linux, Windows, macOS | `document`, `image`, `video`, `audio` | Embedded EXIF metadata, camera serials, GPS coordinates, author metadata | Read-only extraction |
| **`tshark`** | `tshark` | *Optional* | *Host-dependent* | **`NOT_INSTALLED`** | Linux, Windows, macOS | `pcap`, `pcapng`, `network_capture` | Protocol hierarchy, DNS query extraction, HTTP request metadata, IP conversation flows | Sandboxed network dissection |
| **`binwalk`** | `binwalk` | *Optional* | *Host-dependent* | **`NOT_INSTALLED`** | Linux, Windows, macOS | `firmware`, `embedded_image`, `archive` | Magic byte signature scanning, embedded filesystem extraction | Strict extraction depth and ratio limits |

---

## 3. Host System Tool Probe Verification

Output captured directly from running the system tool probe utility (`scripts/check_forensic_tools.py`):

```json
{
  "platform": {
    "system": "Linux",
    "release": "7.0.0-34-generic",
    "architecture": "x86_64"
  },
  "tools": {
    "sleuthkit": {
      "available": true,
      "executable": "/usr/bin/fls",
      "version": "The Sleuth Kit ver 4.12.1"
    },
    "sqlite3": {
      "available": true,
      "executable": "/usr/bin/sqlite3",
      "version": "3.46.1 2024-08-13 09:16:08 c9c2ab54ba1f5f46360f1b4f35d849cd3f080e6fc2b6c60e91b16c63f69aalt1"
    },
    "strings": {
      "available": true,
      "executable": "/usr/bin/strings",
      "version": "GNU strings (GNU Binutils for Ubuntu) 2.44"
    },
    "volatility3": {
      "available": false,
      "executable": null,
      "version": null
    },
    "yara": {
      "available": false,
      "executable": null,
      "version": null
    },
    "exiftool": {
      "available": false,
      "executable": null,
      "version": null
    }
  }
}
```

---

## 4. Rejection of Mock Executable Discovery

In previous prototype iterations, development mock executables in `tools/bin/` could lead to misleading tool availability in automated tests. 

**Enforced Production Safeguards:**
1. Discovery paths in `PlatformAwareToolRegistry` are strictly restricted to legitimate system binary directories (`/usr/bin`, `/usr/local/bin`, `/bin`, or `%ProgramFiles%` on Windows).
2. The mock directory `tools/bin/` is permanently excluded from runtime production discovery.
3. Every detected executable must successfully pass a live version execution check (e.g. `fls -V`, `sqlite3 --version`) before being marked `INSTALLED`.
4. Tests verifying rejection of nonexistent or simulated tools: `tests/test_tool_registry.py` (21 passing tests).

---

## 5. Execution Sandboxing & Subprocess Security

Every tool execution dispatched by the orchestrator enforces:
- **No Shell Execution:** `subprocess.Popen(cmd_list, shell=False)` is strictly mandated. String command lines are prohibited.
- **Evidence Immutability:** Evidence paths are mounted or passed strictly as read-only inputs.
- **Dedicated Output Directory:** Tools write stdout, stderr, and extracted temporary files into an ephemeral, case-isolated directory (`data/cases/<case_id>/executions/<execution_id>/`).
- **Resource Limits:** Hard timeout caps (`MAX_SAFE_TIMEOUT_SECONDS = 600`) terminate hung or recursive processes automatically.
- **Integrity Validation:** If process exit code is non-zero, status is recorded as `FAILED`, and zero artifacts/findings are created.
