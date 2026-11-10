# ADFIP — Known Limitations and Operational Boundaries

This document defines the technical boundaries, environmental prerequisites, and operational limitations of the Autonomous Digital Forensic Investigation Platform (ADFIP). Forensic practitioners and system administrators must consult these specifications to ensure valid deployment and legally defensible forensic workflows.

---

## 1. Forensic Tool Execution and Environment Dependencies

### 1.1 Tool Presence Policy (Strict Tool Reality)
ADFIP does **not** simulate tool execution. If an external forensic binary is absent from the host operating system:
- Pre-flight validation immediately marks the tool as `NOT_INSTALLED`.
- The corresponding agent execution request fails with status `UNSUPPORTED_EVIDENCE_TYPE` or `EXECUTION_FAILED`.
- Zero synthetic artifacts or speculative findings are generated.

### 1.2 Linux Host Environment Status
As of current host verification (`/usr/bin` inspection):
- **SleuthKit (`fls` v4.12.1)**: Available and verified. Supports raw DD images, FAT12/16/32, NTFS, EXT2/3/4. Does not natively support proprietary encrypted container formats (BitLocker, FileVault, LUKS) without external pre-decryption.
- **SQLite3 (`sqlite3` v3.46.1)**: Available and verified. Parses standard SQLite database schemas (Chromium history/cookies/downloads, Firefox places, chat databases). Corrupt databases require manual recovery via `.recover` or raw hex carving.
- **GNU Strings (`strings` v2.44)**: Available and verified. Extracts 7-bit ASCII and 16-bit Unicode (little-endian and big-endian) strings. Does not perform automatic unpacking of compressed binaries.
- **YARA (`yara-python` v4.3.x in-process library)**: Available and verified. Compiles and executes YARA rules against target artifacts and disk extractions.
- **Volatility 3 (`vol.py`)**: `NOT_INSTALLED` on current deployment. Volatility memory analysis operations are rejected truthfully at pre-flight.
- **ExifTool (`exiftool`)**: `NOT_INSTALLED` on current deployment. Image/document metadata extraction via ExifTool is rejected at pre-flight.

---

## 2. Evidence Support and Processing Boundaries

### 2.1 Supported Evidence Types
1. **Raw Disk Images**: Raw DD (`.dd`, `.raw`, `.img`), split raw, standard FAT/EXT/NTFS filesystems.
2. **Database Evidence**: Unencrypted SQLite3 database files (`.db`, `.sqlite`, `.sqlite3`).
3. **Log Evidence**: Plaintext log streams, syslog, auth.log, audit.log, Windows EVTX (when converted to JSON/XML).
4. **Binary & Memory Artifacts**: Raw PE/ELF binaries, carved memory dumps, process dumps for string and YARA inspection.

### 2.2 Unsupported / Blocked Evidence Types
1. **Encrypted Volumes**: BitLocker, LUKS, APFS encrypted, FileVault without pre-supplied decryption keys.
2. **Proprietary Virtual Disk Formats (Without NBD/Qemu Mounting)**: Raw multi-tier VMDK with snapshots, dynamically allocated VHDX without block mapping.
3. **Live System Direct Device Access**: Accessing `/dev/sda` or `\\.\PhysicalDrive0` directly requires elevated root/administrator privileges; ADFIP standard runtime enforces read-only access to files mounted or copied into the Evidence Vault.

---

## 3. Memory Forensics Limitations

1. **Symbol Table Dependency (Volatility 3)**:
   - Modern Windows 10/11 and Linux kernel memory analysis requires intermediate symbol tables (ISF json files).
   - If offline, Volatility cannot download missing PDB symbols from Microsoft Symbol Server. Users must pre-seed the symbol directory (`volatility3/symbols/windows/`).
2. **Carved Artifact Reliability**:
   - Carving executable structures from unmapped memory heaps carries high entropy and potential false positives.
   - ADFIP strictly assigns empirical confidence based on pattern matching and does not assert maliciousness without corroborating IOCs or investigator review.

---

## 4. Malware Analysis Scope and Safety

1. **Static Heuristic & Signature Analysis Only**:
   - Current malware agent capabilities encompass static analysis: cryptographic hashing (MD5, SHA-1, SHA-256), section entropy calculation, import table analysis, GNU strings extraction, and YARA rule matching.
2. **No Dynamic Detonation / Sandbox Execution**:
   - ADFIP does not execute live malware samples within the host operating system.
   - No automated execution inside Windows sandbox, Cuckoo, or QEMU hypervisor is included in this build.
   - Dynamic detonation must be performed off-band in an isolated laboratory network.

---

## 5. AI Reasoning & Offline Graceful Degradation

1. **Gemini API Network Dependency**:
   - Synthetic intelligence explanation and cross-evidence natural language summarization utilize Google Gemini 1.5 Pro / 2.0 Flash via HTTPS.
   - Requires valid `GEMINI_API_KEY` and outbound internet connectivity to Google APIs.
2. **Deterministic Offline Operation**:
   - When offline or when the Gemini API is unreachable:
     - All deterministic forensic tools (SleuthKit, SQLite, Strings, YARA) execute identically.
     - All artifacts, findings, correlations, and audit logs are created and persisted without degradation.
     - Case reports generate with a prominent notice: `[AI Intelligence Offline — Report Generated Deterministically]`.
     - Zero fallback hallucination: The system never fabricates AI summaries or injects boilerplate text disguised as AI analysis.

---

## 6. Desktop Application & Operating System Boundaries

1. **Tauri v2 Desktop Shell**:
   - The desktop shell operates on Linux (GTK3/WebKitGTK) and Windows 10/11 (WebView2).
   - The backend runs as a local loopback HTTP service (`http://127.0.0.1:8001`) spawned by the Tauri desktop process.
2. **Filesystem Permissions**:
   - The evidence vault directory must reside on a filesystem that permits read-only locking (POSIX `chmod 444` or Windows ACL read-only inheritance).
   - Temporary file carving directories require sufficient storage capacity (minimum 3x the size of the target disk image for full uncompressed file extraction).

---

## 7. Investigator Authority and Governance

1. **Mandatory Human-in-the-Loop**:
   - Automated agents cannot close cases or publish official forensic reports autonomously.
   - All 14 report readiness gates require human investigator action:
     - Review and accept/challenge automated findings.
     - Set case confidence scores.
     - Authorize official report publication via an explicit `InvestigatorDecision(decision="CONFIRM")`.
2. **Audit Hash Chain Immutability**:
   - Audit logs are SHA-256 chained from genesis. Modifying or deleting an audit entry breaks the cryptographic chain and triggers tamper alerts across the platform.
