# ADFIP — Acceptance Test Expected Results (Section T)
**Date:** 2026-11-09  
**Specification:** Master Implementation Prompt V5.0 Section T  
**Status:** Defined Prior to End-to-End Acceptance Execution

---

## 1. Controlled Evidence Set Inventory

| Evidence Name | Category | Exact Size | Independent SHA-256 Sum | Known Embedded Contents |
|---|---|---|---|---|
| `controlled_system.log` | Log / Text | 310 bytes | `3d1f753d96cd0ec95534dcd6cef4d0a08ac56fd2d48b55accc2d1283520f5ace` | Planted IP `10.0.0.15`, Process `cmd.exe PID 4102`, Destination IP `198.51.100.42:443`, Alert `Potential unauthorized exfiltration beacon` |
| `controlled_browser.db` | SQLite Database | 12,288 bytes | `c5fab4e9cdee05923718001e38376653117b0c73401ad3806dc52d2689cec7d1` | Table `history`: 2 rows (`https://example.com/login`, `https://malicious-domain.test/dropper.exe`); Table `downloads`: 1 row (`dropper.exe`, hash `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`) |
| `controlled_artifact.bin` | Executable / Binary | 54 bytes | `620c48c3915a4ed81332b8712174fc5974580985477553c73201cff54d99d521` | MZ/PE header bytes `4D 5A 90 00`, embedded signature `ADFIP_CONTROLLED_BINARY_SIGNATURE_2026` |
| `synthetic_disk.img` | FAT32 Disk Image | 1,048,576 bytes | `37921adc4cceb9cf91eee34cdd5bba6d9c818fe1424fd7669e175b706d350533` | Directory entries: `NORMAL.TXT` (inode 3), deleted file `_VIL.BAT` (inode 4, deleted flag `*`), `REPORT.DOC` (inode 5) |

---

## 2. Expected Execution & Verification Checklist (26 Steps)

1. **Step 1 — Launch Desktop App:** Backend lifecycle bootstraps on localhost `127.0.0.1` with dynamic port and bootstrap secret.
2. **Step 2 — Authenticate:** Investigator logs in with valid JWT token issuance.
3. **Step 3 — Create Case:** Case created with unique UUID, case number `CASE-YYYYMMDD-XXXX`, status `ACTIVE`.
4. **Step 4 — Set Objective:** Objective registered as "Unauthorized Access & Data Exfiltration Investigation".
5. **Step 5 — Import Evidence:** 14-step intake stages evidence into protected read-only vault (`data/vault/`).
6. **Step 6 — Verify SHA-256 vs `sha256sum`:** Computed intake hash MUST exactly match the independent SHA-256 values recorded in Section 1.
7. **Step 7 — Confirm Vault Preservation:** Original evidence file permissions set to read-only (`0o444` / `0o555`), never altered.
8. **Step 8 — View Custody:** Cryptographic custody chain created with genesis block hash and event hash chaining.
9. **Step 9 — View Intelligence:** Magic bytes identified (e.g. `SQLite format 3`, `DOS/MBR boot sector`, `ASCII text`), entropy calculated, separated into Observed Facts, Interpretations, and Assumptions.
10. **Step 10 — View Generated Questions:** Deterministic questions generated without assuming malicious compromise.
11. **Step 11 — View Strategy:** Proposed operations map required capabilities strictly to verified available tools.
12. **Step 12 — Confirm Only AVAILABLE Tools Chosen:** Missing tools (`volatility3`, `yara`, `exiftool`) NOT selected for autonomous execution; available tools (`sleuthkit`, `sqlite3`, `strings`, `python-evtx`) selected.
13. **Step 13 — Governance Step:** Governance approval recorded prior to execution dispatch.
14. **Step 14 — Run Executions:** Real tools executed in read-only sandbox with OS PID, execution start time, bounded timeout, and real stdout/stderr captured.
15. **Step 15 — Inspect Raw Outputs:** Raw stdout/stderr files stored with independent SHA-256 hashes.
16. **Step 16 — Inspect Parsed Artifacts:** Real parsed artifacts created:
    - SleuthKit `fls` parses `NORMAL.TXT`, `_VIL.BAT`, `REPORT.DOC`.
    - SQLite parses `history` (2 rows) and `downloads` (1 row).
    - Strings extracts `ADFIP_CONTROLLED_BINARY_SIGNATURE_2026`.
17. **Step 17 — View Correlations:** Deterministic entity correlation links IP `198.51.100.42` or hash across artifacts.
18. **Step 18 — View Findings:** Findings created with `confidence = None` for single-source facts, extraction quality recorded.
19. **Step 19 — Request Gemini Explanation:** AI-assisted narrative generated strictly grounded in cited record IDs.
20. **Step 20 — Confirm Validation of AI Output:** Validation agent checks that all cited record IDs exist and no ungrounded claims are accepted.
21. **Step 21 — Investigator Decision:** Investigator accepts one finding and challenges/rejects another with documented rationale.
22. **Step 22 — Deliberate Failing Execution:** One deliberately failing task executed (e.g., bad arguments or invalid filesystem); verify it fails with exit code != 0 and produces ZERO artifacts and ZERO findings.
23. **Step 23 — Generate Report:** 14-gate report readiness passes; 16-section report generated with PDF and JSON manifest.
24. **Step 24 — Verify Report vs DB:** All referenced IDs in the report exist in the database; zero orphaned or synthetic claims.
25. **Step 25 — Inspect Audit Trail:** Complete audit trail verified with unbroken SHA-256 chain.
26. **Step 26 — Restart App & Confirm Persistence:** Backend restart; verify all cases, evidence, custody, artifacts, findings, decisions, and reports persist intact.
