# ADFIP — Final Product Engineering Correction Plan

**Document:** `docs/review/FINAL_CORRECTION_PLAN.md`  
**Version:** 1.0.0  
**Timestamp:** 2026-10-30T19:26:00+05:30  
**Repository:** `surya1259F/ADFIP`  
**Target Delivery Branch:** `feature/frontend-rebuild`  
**Prioritization Schema:** P0 (Critical/Security/Integrity), P1 (Core Forensic Workflow), P2 (Integrations/Agents), P3 (UI/Diagnostics)  

---

## 1. Defect Matrix Summary

| Defect ID | Severity | Affected Component | Status | Summary |
| :--- | :---: | :--- | :---: | :--- |
| **DEF-001** | **P0** | `backend/app/services/report_readiness.py` | **RESOLVED** | Unimported `AnalysisRequest` crash and premature Gate 11 rejection in readiness suite |
| **DEF-002** | **P0** | `backend/app/services/investigator_review.py` | **RESOLVED** | Premature synchronous scheduler queue evaluation failing line 500 test assertion |
| **DEF-003** | **P1** | `frontend/src/pages/verification/VerificationPage.tsx` | **RESOLVED** | Challenge resolution modal & storage budget monitor missing from canonical review route |
| **DEF-004** | **P0** | `backend/app/services/google_oauth.py` / Environment | **RESOLVED** | Google OAuth token exchange `ConnectError` under network-isolated sandbox processes |
| **DEF-005** | **P1** | `backend/app/api/v1/endpoints/auth.py` | **RESOLVED** | Lack of diagnostic logging for OAuth-only accounts attempting email/password login |
| **DEF-006** | **P3** | `backend/app/api/v1/endpoints/reports.py` | **PENDING** | Starlette deprecation warnings for `HTTP_422_UNPROCESSABLE_ENTITY` alias |

---

## 2. Detailed Defect Specifications

### DEF-001: Report Readiness Missing Import & Gate 11 Premature Rejection
* **Severity:** **P0** (Blocks final forensic reporting and report readiness evaluation)
* **Affected Component:** `backend/app/services/report_readiness.py`
* **Reproduction Steps:**
  1. Initialize a case with forensic findings.
  2. Execute `backend/.venv/bin/pytest backend/tests/test_report_readiness_negative_suite.py`.
  3. Execution crashes at line 185 with `NameError: name 'AnalysisRequest' is not defined`.
  4. Furthermore, running `test_final_forensic_report_subsystem.py` fails because Gate 11 unconditionally blocked findings with `latest_review.decision == 'CHALLENGE'`, preventing legitimate Section 8 disposition reporting.
* **Root Cause:**
  An uncommitted experimental edit attempted to inspect `AnalysisRequest.scheduler_status` inside Gate 7 without an import, and added an uncommitted Gate 11 rejection that unconditionally blocked challenged findings.
* **Required Correction:**
  Restore `backend/app/services/report_readiness.py` to match the canonical GitHub baseline `origin/feature/frontend-rebuild`. Gate 7 evaluates evidence and analysis tasks via existing canonical service helpers; Gate 11 checks review presence without breaking Section 8 disposition logs.
* **Dependencies:** `backend/app/services/final_forensic_report.py`, `backend/tests/test_final_forensic_report_subsystem.py`.
* **Acceptance Criteria:**
  All 10 tests in `test_report_readiness_negative_suite.py` pass; all 11 tests in `test_final_forensic_report_subsystem.py` pass; `test_full_investigation_lifecycle_e2e.py` passes.

---

### DEF-002: Premature Synchronous Scheduler Execution During Review Request
* **Severity:** **P0** (Violates asynchronous resource-aware execution semantics and breaks review test suite)
* **Affected Component:** `backend/app/services/investigator_review.py`
* **Reproduction Steps:**
  1. Run `backend/.venv/bin/pytest backend/tests/test_investigator_review_subsystem.py`.
  2. Test fails at line 500:
     ```python
     assert analysis_req.scheduler_status == "QUEUED"
     AssertionError: assert 'READY' == 'QUEUED'
     ```
* **Root Cause:**
  In `backend/app/services/investigator_review.py:request_more_evidence()`, lines 979–985 contained an uncommitted synchronous call:
  `ResourceAwareScheduler.evaluate_queue(db, plan_id=plan.id)`.
  In environments where resources are available, this synchronous call transitioned the task from `"QUEUED"` to `"READY"` immediately inside the HTTP handler, violating the design contract that HTTP request handlers leave tasks in `"QUEUED"` state for the scheduler loop.
* **Required Correction:**
  Do not weaken the test assertion. Remove the premature synchronous evaluation call from `investigator_review.py:request_more_evidence()`. The task remains in `"QUEUED"` state with status `PENDING`, leaving dispatching to the scheduler.
* **Dependencies:** `backend/app/services/scheduler.py`, `test_investigator_review_subsystem.py`.
* **Acceptance Criteria:**
  Line 500 `assert analysis_req.scheduler_status == "QUEUED"` passes without modification; all 10 tests in `test_investigator_review_subsystem.py` pass.

---

### DEF-003: Review and Verification Route & UI Disconnect
* **Severity:** **P1** (Human-in-the-loop dispute resolution and storage budget monitoring inaccessible from canonical UI)
* **Affected Component:** `frontend/src/pages/verification/VerificationPage.tsx`
* **Reproduction Steps:**
  1. Open browser to `/cases/:caseId/review` or `/cases/:caseId/verification`.
  2. UI rendered finding acceptance/rejection buttons, but lacked the Storage Budget monitor, Challenge Category selector, and Challenge Resolution modal.
  3. Dispute resolution functionality was orphaned inside an unmapped component `InvestigatorReviewPage.tsx`.
* **Root Cause:**
  React Router 7 mapped both `/cases/:caseId/verification` and `/cases/:caseId/review` to `VerificationPage.tsx`, but `VerificationPage.tsx` had not been updated with the full challenge resolution workflow.
* **Required Correction:**
  Integrate the full dispute resolution suite into `VerificationPage.tsx`:
  1. Storage Budget Monitor querying `GET /api/v1/cases/{caseId}/storage/budget`.
  2. Challenge Category dropdown in finding review dialog.
  3. Challenge Resolution modal with pre-flight storage estimation (`POST /api/v1/cases/{caseId}/storage/estimate`) and submission (`POST /api/v1/cases/{caseId}/review/challenge/resolve`).
  4. Remove unused imports to satisfy strict TypeScript compilation.
* **Dependencies:** `frontend/src/services/api.ts`, `frontend/src/types/index.ts`.
* **Acceptance Criteria:**
  `npm run build` succeeds with 0 errors; routes render full dispute resolution UI.

---

### DEF-004: Google OAuth Network Sandbox ConnectError
* **Severity:** **P0** (Blocks live Google OAuth authentication when running inside sandbox containers)
* **Affected Component:** `backend/app/services/google_oauth.py` / Runtime Environment
* **Reproduction Steps:**
  1. Start backend process in standard sandbox mode (no external network access).
  2. In browser, navigate to `/signin` and click "Sign in with Google".
  3. Complete Google consent; browser redirects to `/api/v1/auth/google/callback`.
  4. Backend log records `[Errno -3] Temporary failure in name resolution` during token exchange.
  5. UI displays `Unable to reach Google OAuth services (ConnectError). Verify network connectivity.`
* **Root Cause:**
  Outbound HTTPS call to `https://oauth2.googleapis.com/token` requires DNS resolution and internet connectivity. Standard sandbox execution environments disable network access by default.
* **Required Correction:**
  1. Host process execution instructions (run backend on host network).
  2. Maintain automated unit tests with mocks for offline verification.
  3. Catch network exceptions cleanly and provide actionable diagnostic logging.
* **Dependencies:** System network configuration, Google Cloud Console redirect URI.
* **Acceptance Criteria:**
  Outbound DNS and HTTPS requests succeed when executed on host; `test_google_oauth.py` passes 100%.

---

### DEF-005: OAuth-Only Account Email/Password Login Ambiguity
* **Severity:** **P1** (Causes investigator confusion when attempting password login on Google-registered accounts)
* **Affected Component:** `backend/app/api/v1/endpoints/auth.py`
* **Reproduction Steps:**
  1. Register an account using Google OAuth (`password_hash = NULL`).
  2. Attempt to log in with email and a password on `/signin`.
  3. Endpoint returns HTTP 401 `Invalid email or password.`.
  4. Attempting to register via `/signup` returns HTTP 409 `Conflict` ("An account with this email address already exists.").
* **Root Cause:**
  Under ADFIP's secure federated identity model, Google OAuth accounts do not have local passwords. The generic 401 response (designed to prevent user enumeration) provided no server-side diagnostic logging to explain why authentication failed for that specific request ID.
* **Required Correction:**
  Add safe server-side diagnostic logging in `login_user` and `register_user` correlated with `[Request-ID: <id>]`. Distinguish:
  - User not found
  - OAuth-only account (no password hash)
  - Password verification mismatch
  - Disabled user account
  Maintain uniform HTTP 401 responses and constant-time dummy checks to preserve security against user enumeration.
* **Dependencies:** `backend/app/core/security.py`, `backend/tests/test_auth.py`.
* **Acceptance Criteria:**
  `test_auth.py` passes 100%; server log displays clear diagnostic reason for 401 without exposing passwords or hashes.

---

### DEF-006: Starlette Deprecation Warnings for HTTP Status Codes
* **Severity:** **P3** (Code cleanliness and future framework compatibility)
* **Affected Component:** `backend/app/api/v1/endpoints/reports.py`, `backend/app/api/v1/endpoints/cases.py`
* **Reproduction Steps:**
  1. Run pytest suite.
  2. Starlette emits deprecation warning: `StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.`
* **Root Cause:**
  Starlette/FastAPI deprecated `HTTP_422_UNPROCESSABLE_ENTITY` in favor of RFC 9110 standard `HTTP_422_UNPROCESSABLE_CONTENT`.
* **Required Correction:**
  Update status code constants to `status.HTTP_422_UNPROCESSABLE_CONTENT` across backend endpoint decorators and return handlers where appropriate.
* **Dependencies:** None.
* **Acceptance Criteria:**
  All tests continue to pass; deprecation warnings reduced.

---

*Plan certified by Senior Forensic Systems Architect.*

