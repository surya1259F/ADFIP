# ADFIP — Final Product Engineering Baseline & Architectural Audit

**Document:** `docs/review/FINAL_PRODUCT_BASELINE.md`  
**Version:** 1.0.0  
**Timestamp:** 2026-10-30T19:24:00+05:30  
**Repository:** `surya1259F/ADFIP`  
**Local Workspace:** `/home/nandireddy/ADFIP-1`  
**Target Delivery Branch:** `feature/frontend-rebuild`  
**Author:** Senior Forensic Systems Architect, QA Engineer & Release Auditor  

---

## 1. Executive Summary & Repository Baseline

This document provides a comprehensive, ground-truth audit of the entire ADFIP codebase, its components, dependencies, interfaces, and runtime execution guarantees prior to final product hardening.

ADFIP (Autonomous Digital Forensic Investigation Platform) is a forensic workstation combining a React 19 frontend, an asynchronous FastAPI backend, a canonical SQLite database with Alembic schema management, an isolated forensic evidence vault with cryptographic chain-of-custody tracking, a resource-aware execution engine with host storage budget protection, and specialist forensic AI agents operating in an advisory capacity behind strict investigator governance gates.

### 1.1 Git Working Tree & Reference Matrix

| Metric | Recorded Value | Notes |
| :--- | :--- | :--- |
| **Current Branch** | `feature/investigation-resolution-resource-ai` | Synchronized at same commit as target |
| **Target Branch** | `feature/frontend-rebuild` | Delivery target branch |
| **Local HEAD SHA** | `64931c92a86251f054b2b2222e5b4850b6289404` | `feat(forensics): production forensic workflow repair...` |
| **Remote Tracking** | `origin/feature/frontend-rebuild` | SHA: `e31184448ecb3836653797f6f47c83bbf966b007` (1 commit behind local) |
| **Remote Master** | `origin/master` | SHA: `929c872e123dfd412f5872ab6135d8f75a9ecbdc` (24 commits behind) |
| **Working Tree** | Clean diff hygiene, 0 whitespace errors | Preserved working modifications |

---

## 2. Complete Architectural Audit

### 2.1 Backend Architecture (FastAPI & Core)
* **Entrypoints:**
  - `backend/app/main.py`: Root FastAPI application instance with lifespan context manager.
  - `backend/entrypoint.py`: Standalone CLI wrapper supporting PyInstaller desktop distribution.
* **Database & ORM:**
  - `backend/app/core/database.py`: SQLAlchemy engine bound to `sqlite:////home/nandireddy/ADFIP-1/adfir.db`.
  - Concurrency: `connect_args={"check_same_thread": False}`.
  - Session Management: Standard `get_db()` yield generator ensuring transactional cleanup.
  - Schema Migrations: Auto-invoked during FastAPI startup via `run_db_migrations(engine)` in `backend/app/core/migrations.py`.
* **Security & Authentication:**
  - `backend/app/core/security.py`: Password hashing with PBKDF2-SHA256 (`passlib`), HMAC-SHA256 JWT generation with 60-minute expiration, in-memory token revocation cache (`REVOKED_TOKENS`), and constant-time dummy password verification for unknown users to eliminate timing attacks and user enumeration.
  - `backend/app/services/google_oauth.py`: OIDC identity verification, PKCE challenge/verifier generation, state single-use validation, mandatory nonce validation, and rejection of account auto-creation on `SIGN_IN`.
* **Middleware Stack:**
  - `correlation_id_middleware`: Injects and propagates `X-Request-ID` and `X-Correlation-ID` across all HTTP transactions.
  - `desktop_bootstrap_middleware`: Evaluates `X-ADFIR-Bootstrap-Secret` when running under desktop host boundary.
  - `CORSMiddleware`: Explicitly configured for `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:8001`, `tauri://localhost`.

### 2.2 Frontend Architecture (React 19 & Client)
* **Framework & Bundler:** React 19.2.8 with TypeScript 6.0.2 and Vite 8.2.2.
* **Routing:** React Router v7 (`createBrowserRouter`) in `frontend/src/app/routes.tsx` featuring lazy-loaded page modules with `PageSuspense` fallbacks.
* **State Management:**
  - `authStore.ts`: Memory-only session token retention (`currentUser`, `token`, `status: RESTORING | AUTHENTICATED | UNAUTHENTICATED`), session wipe on 401.
  - `caseStore.ts`: Case context, active case selection, investigator assignment.
  - `investigationStore.ts`: Step-by-step forensic investigation state, active strategy, tool selections, and timeline.
  - `aiStore.ts`: AI provider configuration, model discovery, model selection, reasoning history.
* **Network Client:** Axios instance in `frontend/src/services/client.ts` configured for `http://127.0.0.1:8001/api/v1` with request interceptor (Authorization Bearer injection) and response interceptor (automatic 401 handling).

### 2.3 Evidence Intake, Vault & Chain of Custody
* **Storage Structure:** `data/evidence/` and `data/cases/{case_id}/evidence/`.
* **Immutability Guarantee:** Once ingested, original evidence files are set to read-only permissions (`0o444`), copied into vault storage, and hashed with SHA-256.
* **Chain of Custody:** `backend/app/models/models.py` defines `ChainOfCustodyEvent` recording every access, copy, hashing, and capability execution with cryptographic hash chain continuity (`previous_event_hash` -> `event_hash`).
* **Integrity Gate:** Pre-execution verification in `verify_integrity_gate()` recalculates SHA-256 before any forensic tool receives read access.

### 2.4 Forensic Specialist Agents
The codebase defines 12 specialist agents in `agents/`:
1. `DiskAgent` (`agents/disk/disk_agent.py`): Filesystem structure, carve coordination, partition analysis.
2. `LogAgent` (`agents/log/log_agent.py`): EVTX, syslog, auditd log parsing and event sequence analysis.
3. `MalwareAgent` (`agents/malware/malware_agent.py`): YARA signature scanning, PE header inspection, suspicious string classification.
4. `MemoryAgent` (`agents/memory/memory_agent.py`): Memory dump analysis, Volatility 3 plugin coordination (pslist, pstree, netscan).
5. `WindowsAgent` (`agents/windows/windows_agent.py`): Registry hives, LNK shortcuts, Prefetch, JumpLists.
6. `LinuxAgent` (`agents/linux/linux_agent.py`): `/etc` configuration, shell history, cron jobs, systemd unit inspection.
7. `NetworkAgent` (`agents/network/network_agent.py`): PCAP metadata, packet stream extraction, DNS queries.
8. `BrowserAgent` (`agents/browser/browser_agent.py`): Chromium/Firefox SQLite history, downloads, cookies.
9. `PlannerAgent` (`agents/planner/planner_agent.py`): Translation of case objectives into capability sequences.
10. `CorrelationAgent` (`agents/correlation/correlation_agent.py`): Cross-evidence temporal and identity correlation.
11. `VerificationAgent` (`agents/verification/verification_agent.py`): Verification and empirical sanity checks on findings.
12. `ReportAgent` (`agents/report/report_agent.py`): Synthesis of final investigation reports.

### 2.5 Execution Engine & Resource Governance
* **Service:** `backend/app/services/scheduler.py` (`ResourceAwareScheduler`).
* **Storage Budget & Safety Reserve:** `backend/app/services/storage_budget.py` enforces a mandatory **2048 MB (2 GB) Safety Reserve** for host OS and database stability.
* **Multiplier Accounting:** Pre-flight expansion estimation (e.g., Carving: 1.2x, Archives: 2.5x, Memory: 0.2x, YARA: 0.05x). Capabilities exceeding safe available storage are rejected before execution.
* **Governance Gate:** `backend/app/services/governance.py` validates that every capability execution has an explicit human investigator decision (`ACCEPT`, `APPROVE`) before transition from `QUEUED` to `RUNNING`.

### 2.6 Investigator Review & Challenge Resolution
* **Review States:** `ACCEPT`, `REJECT`, `CHALLENGE`, `REQUEST_MORE_EVIDENCE`.
* **Lifecycle Enum:** `FindingLifecycleState` (`CANDIDATE`, `ACCEPTED`, `REJECTED`, `CHALLENGED`, `EVIDENCE_REQUESTED`, `RESOLUTION_PENDING`, `RESOLUTION_RUNNING`, `RESOLVED`).
* **Challenge Categories:** `EVIDENCE_ASSOCIATION`, `TOOL_RESULT`, `AI_INFERENCE`, `FACTUAL_ACCURACY`, `TEMPORAL_SEQUENCE`, `CONFIDENCE_SCORE`, `OTHER`.
* **Service:** `backend/app/services/challenge_resolution.py` allows investigators to dispute a finding, queue a deeper forensic capability, check storage budget admissibility, and log the resolution audit trail.

### 2.7 Final Forensic Reporting Subsystem
* **Readiness Gating:** `backend/app/services/report_readiness.py` evaluates **12 strict forensic readiness gates** (case open, objectives defined, evidence verified, no running tasks, correlation executed, all findings reviewed, etc.).
* **8 Mandatory Report Sections:**
  1. Executive Summary & Case Metadata
  2. Evidence Intake & Custody Verification
  3. Examination Methodology & Tool Inventory
  4. Forensic Execution Audit Trail
  5. Extracted Forensic Artifacts
  6. Empirical Findings & Corroboration
  7. Cross-Domain Correlation & Timeline Analysis
  8. Investigator Dispositions, Limitations & Certification
* **Tamper Sealing:** Every finalized report generates an immutable SHA-256 signature recorded in `reports` table.

---

## 3. Authoritative API Endpoint Inventory

| Endpoint Path | Method | Functionality | Status |
| :--- | :---: | :--- | :---: |
| `/api/v1/auth/signup` | POST | Investigator registration with PBKDF2 password hashing | Verified |
| `/api/v1/auth/login` | POST | Session authentication and JWT issuance | Verified |
| `/api/v1/auth/google/status` | GET | Google OAuth configuration and readiness check | Verified |
| `/api/v1/auth/google/login` | GET | Generates Google OAuth authorization URL with PKCE | Verified |
| `/api/v1/auth/google/callback` | GET | Handles Google callback and exchanges authorization code | Verified |
| `/api/v1/auth/google/exchange` | POST | Consumes single-use exchange ticket for session token | Verified |
| `/api/v1/cases` | GET/POST | Case listing and creation with objective definitions | Verified |
| `/api/v1/cases/{id}` | GET/PATCH | Case overview and status updates | Verified |
| `/api/v1/cases/{id}/evidence` | GET/POST | Evidence registration, file intake, SHA-256 verification | Verified |
| `/api/v1/cases/{id}/intelligence` | GET/POST | Forensic capability recommendations based on evidence types | Verified |
| `/api/v1/cases/{id}/strategy` | GET/POST | Investigation planning, task sequencing, dependency mapping | Verified |
| `/api/v1/cases/{id}/scheduler/queue` | GET/POST | Resource-aware execution queue and task dispatching | Verified |
| `/api/v1/cases/{id}/artifacts` | GET | Normalized forensic artifacts categorized by type | Verified |
| `/api/v1/cases/{id}/correlations` | GET/POST | Cross-evidence correlation clustering and timeline | Verified |
| `/api/v1/cases/{id}/findings` | GET/POST | Deterministic findings linked to source artifacts | Verified |
| `/api/v1/cases/{id}/review` | GET/POST | Investigator review decisions (ACCEPT/REJECT/CHALLENGE) | Verified |
| `/api/v1/cases/{id}/review/challenge/resolve` | POST | Human-in-the-loop dispute resolution and task queueing | Verified |
| `/api/v1/cases/{id}/storage/budget` | GET | Physical disk headroom and 2048 MB Safety Reserve status | Verified |
| `/api/v1/cases/{id}/reports/readiness`| GET | Evaluates 12 mandatory report readiness gates | Verified |
| `/api/v1/cases/{id}/reports/generate` | POST | Synthesizes 8-section final report with tamper sealing | Verified |
| `/api/v1/audit` | GET | Cryptographic audit trail with SHA-256 hash chaining | Verified |

---

## 4. Current Test Suite Baseline

* **Backend Test Suite (`backend/tests/`):**
  - Total Tests: **635**
  - Passed: **626**
  - Skipped: **9** (environment-specific packaging checks)
  - Failed: **0**
  - Total Runtime: **329.59s** (5 min 29 sec)
* **Agent & Tool Integration Suite (`tests/`):**
  - Total Tests: **99**
  - Passed: **99**
  - Failed: **0**
  - Total Runtime: **10.67s**
* **Frontend Unit Test Suite (`frontend/src/__tests__/`):**
  - Total Tests: **46** (auth, oauth, discovery, evidence, gemini)
  - Passed: **46**
  - Failed: **0**
* **Frontend Production Build (`npm run build`):**
  - TypeScript Compilation (`tsc -b`): **0 errors**
  - Vite Bundler: **Built in 5.73s**, all 43 chunks generated cleanly in `dist/assets/`.

---

*Baseline established and certified with zero test failures across all 771 unit and integration tests.*

