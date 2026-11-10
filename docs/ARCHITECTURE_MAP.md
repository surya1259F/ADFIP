# ADFIP — Architecture Map (Phase 0)
**Date:** 2026-11-09  
**Branch:** `feature/frontend-rebuild`  
**HEAD SHA:** `a744ced6d8754adfce0f24366d002f0c7430637c`  
**Database Backup:** `data/backups/pre-work-20261109-131300.db` (SHA-256: `f45bf95e277ddbcfb5ef86c1046cdbc70404f44cae80fc3f0366e4009d2c3885`)

---

## 1. Executive Architecture Overview

ADFIP (Autonomous Digital Forensic Investigation Platform) is a desktop-oriented, multi-agent digital forensics application.
- **Backend:** FastAPI, Python 3.14 / Pydantic v2, SQLAlchemy ORM with SQLite, Alembic migrations.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Router v7. Designed with a professional light stone/cream visual direction (`bg-stone-50`).
- **Desktop Subsystem:** Tauri v2 with Rust backend manager (`frontend/src-tauri`), sidecar lifecycle management, dynamic port allocation, bootstrap secret authentication.
- **Forensic Pipeline:** Platform-aware forensic tool registry, deterministic evidence hashing, cryptographic vault storage, immutable chain of custody, multi-agent coordination, unified timeline reconstruction, deterministic finding generation, and grounded Gemini AI analysis.

---

## 2. Authoritative Subsystems vs. Duplicates

Per Section A3 #13 and Section B10, each core forensic responsibility has ONE authoritative implementation.

| Responsibility | Authoritative Implementation | Secondary / Duplicate / Legacy Shims | Status |
|---|---|---|---|
| **1. Decision Engine** | `backend/app/services/decision_engine.py` & `backend/app/services/strategy_engine.py` | `investigation/planner/planner.py`, `planner_engine.py` | IMPLEMENTED AND VERIFIED |
| **2. Execution Engine** | `investigation/orchestrator/orchestrator.py` & `investigation/scheduler/scheduler.py` | `backend/app/services/orchestration.py`, `backend/app/services/execution.py` (facades) | IMPLEMENTED AND VERIFIED |
| **3. Tool Registry** | `forensic_tools/registry.py` (`PlatformAwareToolRegistry`) | `backend/app/services/tool_selector.py` (capability selector) | IMPLEMENTED AND VERIFIED |
| **4. Evidence Repository / Vault** | `backend/app/services/vault.py` (`stage_evidence_to_vault`, read-only enforcement) | `backend/app/services/acquisition.py` (HTTP intake pipeline) | IMPLEMENTED AND VERIFIED |
| **5. Findings Service** | `backend/app/services/findings.py` | Direct agent finding emissions (now normalized through `findings.py`) | IMPLEMENTED AND VERIFIED |
| **6. Audit & Custody** | `backend/app/services/audit.py` & `backend/app/services/custody.py` | `backend/app/api/endpoints/audit.py` (legacy router) | IMPLEMENTED AND VERIFIED |
| **7. Report Generator** | `backend/app/services/final_report.py` (`FinalForensicReportService`) | `investigation/reporting/generator.py` (legacy stub) | IMPLEMENTED AND VERIFIED |
| **8. AI Provider** | `backend/app/services/ai_provider.py` (`GeminiProvider`, `AIProviderFactory`) | `backend/app/services/llm.py` (compatibility wrapper) | IMPLEMENTED AND VERIFIED |

---

## 3. Backend Component Inventory

### 3.1 Entry Point & Configuration
- **Location:** `backend/app/main.py`
  - **What it does:** Initializes FastAPI app, registers lifespan (DB migrations, directory creation, column guarantees), registers CORS, correlation ID middleware, desktop bootstrap secret trust boundary middleware, global security exception handlers, mounts `/api/v1` and legacy `/api` routers.
  - **Dependencies:** FastAPI, Uvicorn, SQLAlchemy, Alembic.
  - **Status:** IMPLEMENTED AND VERIFIED

- **Location:** `backend/app/core/config.py`
  - **What it does:** Defines `Settings` class via Pydantic BaseSettings. Resolves data directories (`DATA_DIR`, `EVIDENCE_DIR`, `CASES_DIR`, `REPORTS_DIR`, `LOGS_DIR`), database URL (`sqlite:///adfir.db`), secret keys, and port binding.
  - **Status:** IMPLEMENTED AND VERIFIED

- **Location:** `backend/app/core/database.py`
  - **What it does:** SQLAlchemy SQLite engine initialization with WAL mode, foreign keys pragma, scoped session factory (`SessionLocal`).
  - **Status:** IMPLEMENTED AND VERIFIED

- **Location:** `backend/app/core/security.py`
  - **What it does:** Password hashing (bcrypt), JWT creation & decoding, token revocation checks.
  - **Status:** IMPLEMENTED AND VERIFIED (PROTECTED AUTH SUBSYSTEM)

### 3.2 Database Models
- **Location:** `backend/app/models/models.py`
  - **What it does:** Defines 48 SQLAlchemy tables: `User`, `Case`, `EvidenceItem`, `ChainOfCustodyEvent`, `AuditEvent`, `InvestigationPlan`, `ToolExecution`, `ExecutionArtifact`, `Finding`, `InvestigatorDecision`, `Report`, `AIProviderConfig`, etc.
  - **Status:** IMPLEMENTED AND VERIFIED

### 3.3 API Routers (`backend/app/api/v1/endpoints/`)
- `auth.py`: User registration, login, token refresh, logout, profile. (PROTECTED)
- `users.py`: User administration, RBAC role management. (PROTECTED)
- `cases.py`: Case lifecycle (create, list, detail, update, legal closure, reopen).
- `evidence.py`: Evidence upload, vault intake, list, detail, intelligence.
- `investigation.py`: Investigation workspace, objective setting, question tracking.
- `strategy.py`: Strategy generation, capability matching, operation proposals.
- `scheduler.py`: Bounded task scheduling, resource allocation, concurrency controls.
- `executions.py`: Tool execution status, stdout/stderr streams, cancellation.
- `raw_outputs.py`: Raw tool stdout/stderr file retrieval and hash checking.
- `artifacts.py`: Parsed forensic artifacts retrieval and provenance inspection.
- `normalization.py`: Artifact normalization across heterogeneous tools.
- `timeline.py`: Unified chronological timeline with UTC conversion and timezone preservation.
- `correlation.py`: Cross-artifact correlation based on deterministic matching (hashes, IPs).
- `findings.py`: Finding creation, fact vs. interpretation separation, provenance tracking.
- `agents.py`: Specialist multi-agent subsystem management.
- `governance.py`: Investigator governance decision recording.
- `ai.py`: Gemini provider configuration, model discovery, grounded copilot queries.
- `review.py`: Investigator review, challenge categories, finding validation.
- `reports.py`: 14-gate report readiness validation, PDF & JSON generation.
- `audit.py`: Cryptographically chained audit event trail and verification.
- `tools.py`: Tool registry query, dynamic version verification, installation status.
- `recovery.py`: Stale execution startup reconciliation and case recovery.
- `system.py`: System health, disk storage budget, background worker status.
- **Status:** ALL IMPLEMENTED AND VERIFIED

---

## 4. Frontend Component Inventory

### 4.1 Architecture & Layout
- **Entry Point:** `frontend/src/main.tsx` -> renders `frontend/src/app/App.tsx`.
- **Router:** `frontend/src/app/routes.tsx` using `createBrowserRouter` (React Router v7).
- **Layout:** `frontend/src/components/layout/AppLayout.tsx`:
  - Visual theme: Light forensic workstation theme (`bg-stone-50`, `text-stone-900`, `border-stone-200`).
  - Navigation: `frontend/src/components/layout/Sidebar.tsx` and `TopBar.tsx`.
- **API Client:** `frontend/src/services/client.ts` (Axios instance configured with baseURL `/api/v1`, bearer token, desktop bootstrap secret, request ID).
- **State Stores:**
  - `authStore.ts`: Authenticated session, user profile, token in sessionStorage. (PROTECTED)
  - `investigationStore.ts`: Active case, evidence list, background worker status.

### 4.2 Page Matrix
| Page Path | Component File | Key Features | APIs Called | Status |
|---|---|---|---|---|
| `/dashboard` | `pages/dashboard/DashboardPage.tsx` | Total cases, active investigations, tools status, recent audit activity | `/cases`, `/tools`, `/audit` | IMPLEMENTED AND VERIFIED |
| `/cases` | `pages/cases/CasesPage.tsx` | Case list, filtering, search, case creation modal | `/cases` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId` | `pages/cases/CaseOverviewPage.tsx` | Case details, objectives, evidence summary, legal closure action | `/cases/:id`, `/cases/:id/evidence` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/evidence` | `pages/evidence/EvidencePage.tsx` | Evidence list, native file intake, integrity badge, hash verification | `/evidence/intake`, `/evidence` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/evidence/:evidenceId` | `pages/evidence/EvidenceDetailPage.tsx` | Hex view, magic bytes, custody log, intelligence facts | `/evidence/:id`, `/evidence/:id/custody` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/intelligence` | `pages/intelligence/IntelligencePage.tsx` | Observed facts, interpretations, unverified assumptions | `/evidence/:id/intelligence` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/strategy` | `pages/strategy/StrategyPage.tsx` | Proposed operations, capability matching, execution planner | `/investigation/strategy` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/execution` | `pages/execution/ExecutionPage.tsx` | Live tasks, stdout/stderr console, process telemetry, cancellation | `/executions`, `/executions/:id/output` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/findings` | `pages/findings/FindingsPage.tsx` | Fact vs inference breakdown, artifact links, acceptance/challenge | `/findings`, `/review` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/verification` | `pages/verification/VerificationPage.tsx` | Grounding check, AI explanation review, finding validation | `/review`, `/ai/explain` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/report` | `pages/reports/ReportsPage.tsx` | 14 readiness gates, PDF preview, JSON manifest export, hash verification | `/reports/generate`, `/reports/readiness` | IMPLEMENTED AND VERIFIED |
| `/cases/:caseId/audit` | `pages/audit/AuditPage.tsx` | Cryptographic hash-chained audit log, verification walker | `/audit`, `/audit/verify` | IMPLEMENTED AND VERIFIED |
| `/tools` | `pages/tools/ToolsPage.tsx` | Tool matrix: Registered, Installed, Verified, Available; "Verify Now" | `/tools`, `/tools/verify` | IMPLEMENTED AND VERIFIED |
| `/settings` | `pages/settings/SettingsPage.tsx` | Gemini API key configuration, model discovery, connection test | `/ai/test-provider`, `/ai/models` | IMPLEMENTED AND VERIFIED |
| `/account` | `pages/account/AccountPage.tsx` | User profile, password update, session revocation | `/auth/me`, `/auth/password` | IMPLEMENTED AND VERIFIED |
| `/signin`, `/signup` | `pages/auth/SignInPage.tsx`, `SignUpPage.tsx` | Email/password login, Google OAuth button, OIDC callback | `/auth/login`, `/auth/register` | IMPLEMENTED AND VERIFIED (PROTECTED) |

---

## 5. Desktop Application Subsystem

- **Framework:** Tauri v2 (`frontend/src-tauri`).
- **Rust Backend Manager:** `frontend/src-tauri/src/backend_manager.rs`.
  - Dynamically discovers free port on localhost (`127.0.0.1`).
  - Generates cryptographically secure internal bootstrap secret (`X-ADFIR-Bootstrap-Secret`).
  - Spawns backend process (or PyInstaller sidecar `dist/adfir-backend/adfir-backend`).
  - Monitors backend health via `/api/health`.
  - Injects dynamic port and secret into webview frontend.
  - Handles clean termination of backend on application window close (no orphan processes).
- **Packaging:** PyInstaller spec (`backend/adfir-backend.spec`) packages backend into self-contained executable.

---

## 6. Multi-Agent Ecosystem

Defined in `agents/`:
1. `CaseContextAgent`: Tracks case background and constraints.
2. `EvidenceIntelligenceAgent`: Analyzes raw files, magic bytes, and entropy.
3. `StrategyAgent`: Generates structured investigation strategy.
4. `QuestionAgent`: Generates deterministic investigation questions.
5. `ToolSelectionAgent`: Matches capabilities to verified tools.
6. `ExecutionPlanningAgent`: Orders tasks with dependency resolution.
7. `GovernanceAgent`: Enforces approval boundaries and safety policies.
8. `ForensicExecutionAgent`: Executes verified tools in read-only sandbox.
9. `ArtifactAnalysisAgent`: Parses stdout/stderr into structured records.
10. `TimelineAnalysisAgent`: Reconstructs normalized UTC timeline.
11. `CorrelationAgent`: Correlates entities across heterogeneous artifacts.
12. `FindingValidationAgent`: Re-verifies facts against primary artifacts.
13. `AIExplanationAgent`: Calls Gemini with grounded context.
14. `ReportGenerationAgent`: Assembles authoritative 16-section report.
