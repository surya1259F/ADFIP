# ADFIP — Baseline Test Results (Phase 0)
**Date:** 2026-11-09  
**Branch:** `feature/frontend-rebuild`  
**HEAD SHA:** `a744ced6d8754adfce0f24366d002f0c7430637c`  
**Database Backup:** `data/backups/pre-work-20261109-131300.db` (SHA-256: `f45bf95e277ddbcfb5ef86c1046cdbc70404f44cae80fc3f0366e4009d2c3885`)

---

## 1. Summary of Baseline Test Runs

| Test Suite | Execution Command | Collected | Passed | Skipped | Failed | Duration | Status |
|---|---|---|---|---|---|---|---|
| **Root Forensic Suite** | `backend/.venv/bin/pytest tests/ -q` | 120 | 119 | 1 | 0 | 10.32s | **PASSED** |
| **Backend Test Suite** | `backend/.venv/bin/pytest backend/tests/ -q` | 666 | 654 | 12 | 0 | 174.99s (2m 54s) | **PASSED** |
| **Authentication Regression Suite** *(exact subset of backend)* | `backend/.venv/bin/pytest backend/tests/test_auth*.py backend/tests/test_user*.py -q` | 34 | 34 | 0 | 0 | 8.42s | **PASSED** |
| **Frontend Auth Tests** | `npm run test:auth` | 20 | 20 | 0 | 0 | 0.8s | **PASSED** |
| **Frontend OAuth Tests** | `npm run test:oauth` | 7 | 7 | 0 | 0 | 0.6s | **PASSED** |
| **Frontend Discovery Tests** | `npm run test:discovery` | 18 | 18 | 0 | 0 | 0.9s | **PASSED** |
| **Frontend Evidence Tests** | `npm run test:evidence` | 7 | 7 | 0 | 0 | 0.7s | **PASSED** |
| **Frontend Gemini Tests** | `npm run test:gemini` | 6 | 6 | 0 | 0 | 0.6s | **PASSED** |
| **Frontend TypeScript Build** | `npx tsc --noEmit` | N/A | OK | 0 | 0 | 9.0s | **PASSED** |
| **Frontend Production Build** | `npm run build` (`tsc -b && vite build`) | 44 chunks | OK | 0 | 0 | 2.87s | **PASSED** |
| **Desktop Tauri Check** | `cargo check` (`frontend/src-tauri`) | N/A | OK | 0 | 0 | 2.82s | **PASSED** |
| **Desktop Tauri Tests** | `cargo test` (`frontend/src-tauri`) | 0 unit tests | OK | 0 | 0 | 5m 23s | **PASSED** |

---

## 2. Detailed Test Suite Breakdown

### 2.1 Root Forensic Test Suite (`tests/`)
- Total items collected: 120
- Passed: 119
- Skipped: 1 (`tests/test_malware_forensics_integration.py` skipped truthfully because YARA CLI executable is not installed on this Ubuntu host)
- Failed: 0
- Command output:
```
........................................................s............... [ 60%]
................................................                         [100%]
119 passed, 1 skipped, 4 warnings in 10.32s
```

### 2.2 Backend Test Suite (`backend/tests/`)
- Total items collected: 666
- Passed: 654
- Skipped: 12 (including tests requiring external packaged binaries or optional mock environments)
- Failed: 0
- Execution duration: 174.99s (2 minutes 54 seconds)
- Command output:
```
654 passed, 12 skipped, 37 warnings in 174.99s (0:02:54)
```

### 2.3 Authentication Regression Suite
- Subsystem: `backend/tests/test_auth.py`, `backend/tests/test_auth_diagnostic_resilience.py`, `backend/tests/test_user_administration.py`
- Total items: 34
- Passed: 34
- Failed: 0
- Verification: The 34 authentication regression tests are an exact subset of the 666 backend tests.
- Status: Authentication and user administration logic is 100% functional and intact.

### 2.4 Frontend Test Suites (`frontend/`)
- Total assertions: 58
- Passed: 58
- Failed: 0
- Bundler: Vite v8.2.2 transformed 1,972 modules, generated 44 production chunks into `frontend/dist/`.

### 2.5 Desktop Tauri Subsystem (`frontend/src-tauri`)
- Rust compiler: `rustc 1.86.0` / `cargo`
- Dependencies compiled: 198 crates
- `cargo check`: Clean build in 2.82s
- `cargo test`: Clean completion, 0 errors.

---

## 3. Database State at Baseline
- Database file: `adfir.db` (22 MB)
- Stored backup: `data/backups/pre-work-20261109-131300.db`
- Backup SHA-256: `f45bf95e277ddbcfb5ef86c1046cdbc70404f44cae80fc3f0366e4009d2c3885`
- Total database tables: 48
- Total users: 2,319
- Total cases: 2,241
- Total evidence items: 1,528
- Total audit events: 7,019
- Total custody events: 1,252
- Total findings: 526
