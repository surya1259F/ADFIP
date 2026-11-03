# ADFIP — Real-World Digital Forensic Investigation Mapping

**Document:** `docs/review/REAL_WORLD_FORENSIC_WORKFLOW_MAPPING.md`  
**Version:** 1.0.0  
**Timestamp:** 2026-10-30T19:25:00+05:30  
**Repository:** `surya1259F/ADFIP`  
**Target Delivery Branch:** `feature/frontend-rebuild`  
**Reference Standards:** NIST SP 800-86, ISO/IEC 27037, NIST SP 800-101, SWGDE Best Practices  

---

## 1. Overview & Methodological Grounding

Digital forensic investigation is a disciplined technical and legal process defined by authoritative international standards (ISO/IEC 27037:2012, NIST SP 800-86). The process mandates that:
1. **Original digital evidence must never be modified.**
2. **Every handling, transfer, analysis, and transformation must be cryptographically recorded in an unbroken Chain of Custody.**
3. **Forensic operations must be repeatable, deterministic, and verifiable by independent examiners.**
4. **AI/ML models must operate strictly as advisory assistive systems; they must never possess executive authority over case findings or final report sign-offs.**

This document maps these real-world investigative requirements directly into ADFIP's 17 established lifecycle stages.

---

## 2. Comprehensive Workflow Stage Mapping

### Stage 1: Investigator Authentication
* **1. Real-World Investigative Activity:**
  Secure identity verification of authorized forensic examiners. Role-based access control (RBAC) ensuring only credentialed investigators, lead examiners, or legal counsel access sensitive case material (ISO/IEC 27037 §6.2).
* **2. Existing ADFIP Implementation:**
  FastAPI endpoint `/api/v1/auth/login` (PBKDF2-SHA256 password verification, constant-time dummy checking against user enumeration), Google OAuth 2.0 OIDC PKCE flow (`/api/v1/auth/google/login`), HMAC-SHA256 JWT generation with in-memory revocation (`REVOKED_TOKENS`).
* **3. Missing or Incomplete Functionality:**
  OAuth-only accounts lacked local password credentials, resulting in HTTP 401 when attempting email/password login without an explicit UI prompt to use Google Sign In or link an account.
* **4. Required Correction:**
  Enhanced safe diagnostic logging on authentication rejections; clear UI messaging guiding OAuth-registered users to their federated sign-in method or account linking.
* **5. Relevant AI Agent Responsibilities:**
  None (Security boundary: AI agents are strictly isolated from credential processing and JWT issuance).
* **6. Required Evidence:**
  Examiner identity records, login audit logs (`audit_events` with `USER_LOGIN_SUCCESSFUL`).
* **7. Validation Criteria:**
  Valid credentials issue signed JWT; invalid credentials return 401; token tampering returns 401; tokens revoked on logout cannot be reused.

---

### Stage 2: Case Management
* **1. Real-World Investigative Activity:**
  Registration of a formal forensic inquiry. Assignment of unique case numbers, incident background, legal authority (search warrant, incident response retainer, court order), scope of investigation, and assignment of primary and secondary examiners (NIST SP 800-86 §3.1).
* **2. Existing ADFIP Implementation:**
  `/api/v1/cases` endpoints, `Case` model with `case_number`, `incident_type`, `legal_authorization`, `status: ACTIVE | CLOSED`, investigator assignment through `case_members`.
* **3. Missing or Incomplete Functionality:**
  Case legal authority status transitions were not consistently surfaced on all case summary views.
* **4. Required Correction:**
  Ensure case detail headers explicitly display legal authority scope and assigned lead investigator.
* **5. Relevant AI Agent Responsibilities:**
  `CaseIntelligenceAgent`: Parses initial incident briefs to highlight potential scope boundaries and suggest initial inquiry directions.
* **6. Required Evidence:**
  Signed engagement letter, search warrant, incident ticket reference.
* **7. Validation Criteria:**
  Cases persist with unique identifiers; cross-case access by unassigned users returns 403 Forbidden.

---

### Stage 3: Evidence Intake
* **1. Real-World Investigative Activity:**
  Intake of physical or logical digital exhibits (disk images, memory dumps, mobile extractions, network PCAPs, system event logs). Recording source location, hardware serial numbers, and initial acquiring officer details (ISO/IEC 27037 §7.2).
* **2. Existing ADFIP Implementation:**
  `/api/v1/cases/{case_id}/evidence` endpoint, native filesystem Browse Evidence dialog, drag-and-drop file upload, file format detection (`forensic_tools/evidence_types.py`).
* **3. Missing or Incomplete Functionality:**
  Manual path entry could allow arbitrary local paths if not restricted to native OS dialogs.
* **4. Required Correction:**
  Strict enforcement of native file dialog browse entry points and elimination of raw text path injection.
* **5. Relevant AI Agent Responsibilities:**
  `EvidenceIntelligenceAgent`: Rapidly inspects file magic bytes (signatures) to identify true format regardless of file extension.
* **6. Required Evidence:**
  Acquisition manifest, exhibit number, native source path.
* **7. Validation Criteria:**
  File intake strictly validates format, file existence, and non-empty byte count before progressing.

---

### Stage 4: Evidence Vault & Preservation
* **1. Real-World Investigative Activity:**
  Physical and cryptographic preservation. Original evidence must be write-blocked or stored read-only. Calculation of cryptographic hashes (SHA-256) at the moment of intake to create an immutable integrity baseline (ISO/IEC 27037 §8.2).
* **2. Existing ADFIP Implementation:**
  `EvidenceVaultService` in `backend/app/services/evidence_vault.py`. Computes SHA-256, copies to `data/evidence/` vault, sets read-only file permissions (`0o444`), and initializes `chain_of_custody_events`.
* **3. Missing or Incomplete Functionality:**
  Storage space pre-checks did not enforce a minimum host safety reserve before copying large disk images into the vault.
* **4. Required Correction:**
  Enforce the mandatory 2048 MB Safety Reserve check before accepting large evidence transfers.
* **5. Relevant AI Agent Responsibilities:**
  None (Integrity boundary: Hashing and filesystem permissions are strictly deterministic system operations).
* **6. Required Evidence:**
  Computed SHA-256 hash, file size in bytes, read-only file mode verification.
* **7. Validation Criteria:**
  Vault copy SHA-256 matches intake SHA-256; attempts to modify vault files fail with Permission Denied; tampering flags `INTEGRITY_VIOLATION`.

---

### Stage 5: Evidence Intelligence
* **1. Real-World Investigative Activity:**
  Pre-analysis triage. Identifying partition layouts, filesystem types (NTFS, EXT4, APFS), operating system signatures, compression containers, and memory profile architectures (NIST SP 800-86 §3.2).
* **2. Existing ADFIP Implementation:**
  `/api/v1/cases/{id}/intelligence` endpoint, `EvidenceIntelligenceProfile` model, dynamic capability recommendation logic matching MIME types and magic headers to supported forensic tools.
* **3. Missing or Incomplete Functionality:**
  Some forensic tool recommendations were static rather than dynamically filtered by detected evidence format.
* **4. Required Correction:**
  Use canonical `forensic_tools/evidence_types.py` mappings to only recommend tools verified compatible with the specific evidence type.
* **5. Relevant AI Agent Responsibilities:**
  `EvidenceIntelligenceAgent`: Analyzes header entropy, detected partition tables, and file structures to propose relevant forensic parsers.
* **6. Required Evidence:**
  Magic bytes, file size, container structures, MIME type.
* **7. Validation Criteria:**
  Only compatible capabilities are recommended; ungrounded tool suggestions are filtered out.

---

### Stage 6: Investigation Objectives
* **1. Real-World Investigative Activity:**
  Formulation of specific, testable investigative questions (e.g., "Determine if unauthorized exfiltration occurred between 02:00 and 04:00 UTC", "Identify source of lateral movement") (NIST SP 800-86 §3.1).
* **2. Existing ADFIP Implementation:**
  Case objectives stored as structured text records in `cases.objectives`.
* **3. Missing or Incomplete Functionality:**
  Objectives were free-form text without explicit linkage to downstream findings.
* **4. Required Correction:**
  Maintain objective references in findings so that every finding answers an approved objective.
* **5. Relevant AI Agent Responsibilities:**
  `CaseIntelligenceAgent`: Deconstructs complex objectives into actionable forensic inquiries.
* **6. Required Evidence:**
  Investigator objective specification, case scope document.
* **7. Validation Criteria:**
  Case cannot proceed to final reporting if zero objectives are defined (Gate 3).

---

### Stage 7: Investigation Strategy
* **1. Real-World Investigative Activity:**
  Developing an examination plan. Establishing which forensic domains to examine first (volatile memory first, followed by system logs, filesystem metadata, then unallocated space carving) according to Order of Volatility (RFC 3227).
* **2. Existing ADFIP Implementation:**
  `/api/v1/cases/{id}/strategy` endpoint, `InvestigationPlan` model, topological dependency ordering for tasks.
* **3. Missing or Incomplete Functionality:**
  Strategy plans allowed arbitrary parallel dispatch without dependency validation.
* **4. Required Correction:**
  Enforce prerequisite task validation (e.g., partition extraction before deleted file carving).
* **5. Relevant AI Agent Responsibilities:**
  `InvestigationPlanningAgent`: Evaluates Order of Volatility and suggests optimal sequence of forensic tasks.
* **6. Required Evidence:**
  Ordered list of planned investigation tasks with dependency graph.
* **7. Validation Criteria:**
  Circular dependencies are rejected; downstream tasks remain blocked until upstream tasks succeed.

---

### Stage 8: Capability Selection
* **1. Real-World Investigative Activity:**
  Selecting validated forensic software and tools for specific artifact extraction (e.g., Volatility 3 for memory, Sleuth Kit for filesystem analysis, YARA for malware indicators) (SWGDE Standards).
* **2. Existing ADFIP Implementation:**
  `forensic_tools/registry.py`, `ToolDefinition` table, `tool_selections` table.
* **3. Missing or Incomplete Functionality:**
  Tools marked as installed when their underlying binaries were missing from the system.
* **4. Required Correction:**
  Real-time binary verification (`shutil.which` / binary existence check); unavailable tools must be explicitly marked `NOT INSTALLED`.
* **5. Relevant AI Agent Responsibilities:**
  `CapabilitySelectionAgent`: Checks tool availability and flags missing prerequisites.
* **6. Required Evidence:**
  Tool binary path, version string, executable permissions.
* **7. Validation Criteria:**
  Selecting an uninstalled tool raises validation error; fake executions are strictly prohibited.

---

### Stage 9: Governance & Approval
* **1. Real-World Investigative Activity:**
  Senior investigator or forensic supervisor approval before executing invasive, high-resource, or destructive operations (SWGDE Guidelines §4).
* **2. Existing ADFIP Implementation:**
  `GovernanceGateService` in `backend/app/services/governance.py`. Records `GovernanceDecision` with examiner ID, timestamp, and rationale.
* **3. Missing or Incomplete Functionality:**
  Certain test harnesses bypassed governance gates during direct execution calls.
* **4. Required Correction:**
  Strict enforcement that no task moves to `RUNNING` status without an approved `GovernanceDecision`.
* **5. Relevant AI Agent Responsibilities:**
  None (Governance boundary: AI agents cannot approve their own execution proposals).
* **6. Required Evidence:**
  Examiner authorization signature, decision timestamp, approved capability parameters.
* **7. Validation Criteria:**
  Tasks with `REJECTED` or missing governance decisions are blocked from execution queue.

---

### Stage 10: Resource-Aware Execution
* **1. Real-World Investigative Activity:**
  Execution of forensic analysis on controlled hardware. Preventing out-of-memory crashes, disk exhaustion, or CPU starvation during heavy operations (disk carving, large memory analysis).
* **2. Existing ADFIP Implementation:**
  `ResourceAwareScheduler` in `backend/app/services/scheduler.py` and `StorageBudgetService` in `backend/app/services/storage_budget.py`.
* **3. Missing or Incomplete Functionality:**
  Pre-flight storage estimation was not exposed directly to the investigator prior to submission.
* **4. Required Correction:**
  Integrated pre-flight storage budget estimation endpoint (`POST /cases/{id}/storage/estimate`) and live UI display in `VerificationPage.tsx`.
* **5. Relevant AI Agent Responsibilities:**
  `ForensicExecutionAgent`: Monitors subprocess execution, tracks resource limits, and captures stdout/stderr.
* **6. Required Evidence:**
  Process exit code, execution runtime, artifact output path, SHA-256 of raw execution output.
* **7. Validation Criteria:**
  Execution respects 2048 MB Safety Reserve; timeouts terminate hung subprocesses cleanly; nonzero exit codes are recorded as failures.

---

### Stage 11: Forensic Artifact Extraction
* **1. Real-World Investigative Activity:**
  Parsing and extraction of raw forensic data (e.g., MFT entries, registry values, memory processes, network streams) into structured forensic artifacts (ISO/IEC 27037 §8.3).
* **2. Existing ADFIP Implementation:**
  `ArtifactExtractionService` in `backend/app/services/artifact_extraction.py`, `ExecutionArtifact` model, artifact normalization in `normalization.py`.
* **3. Missing or Incomplete Functionality:**
  Some parser exceptions resulted in silent data omission without error logging.
* **4. Required Correction:**
  Explicit error logging and partial artifact capture with parser warning flags.
* **5. Relevant AI Agent Responsibilities:**
  `ArtifactAnalysisAgent`: Normalizes disparate tool output schemas into canonical artifact objects.
* **6. Required Evidence:**
  Raw tool stdout/stderr file, extracted JSON/tabular artifact records, execution ID.
* **7. Validation Criteria:**
  Every artifact links to its originating `analysis_request_id` and raw output hash.

---

### Stage 12: Artifact Correlation
* **1. Real-World Investigative Activity:**
  Cross-referencing artifacts across domains (e.g., correlating a memory-resident injected thread with an EVTX process creation event and a network connection timestamp) (NIST SP 800-86 §3.3).
* **2. Existing ADFIP Implementation:**
  `CrossDomainCorrelationService` in `backend/app/services/correlation.py`, `TimelineEvent` aggregation, `correlation_groups` table.
* **3. Missing or Incomplete Functionality:**
  Correlation was treated as optional in early report generation passes.
* **4. Required Correction:**
  Enforce Gate 12: final reporting requires correlation analysis across multi-source cases.
* **5. Relevant AI Agent Responsibilities:**
  `CorrelationAgent`: Groups temporal clusters and flags contradictory timestamps (e.g., timestomping indicators).
* **6. Required Evidence:**
  Correlated artifact IDs, temporal delta, common entity identifiers (IP, PID, User, Hash).
* **7. Validation Criteria:**
  Correlated events preserve individual source artifact references; causality is not falsely claimed based on temporal proximity alone.

---

### Stage 13: Findings & Investigative Review
* **1. Real-World Investigative Activity:**
  Formulating empirical findings based on verified artifacts. Peer review / senior investigator review to accept, challenge, or reject preliminary conclusions (SWGDE Quality Assurance).
* **2. Existing ADFIP Implementation:**
  `InvestigatorReviewService` in `backend/app/services/investigator_review.py`, `ChallengeResolutionService` in `backend/app/services/challenge_resolution.py`.
* **3. Missing or Incomplete Functionality:**
  Challenge resolution dialog was not accessible from the main verification page in frontend.
* **4. Required Correction:**
  Fully integrated Challenge Resolution modal and Storage Budget display into `VerificationPage.tsx`.
* **5. Relevant AI Agent Responsibilities:**
  `InvestigationReviewAgent`: Identifies evidential gaps and suggests corroborating capabilities for challenged findings.
* **6. Required Evidence:**
  Finding statement, supporting artifact IDs, investigator decision (`ACCEPT`, `REJECT`, `CHALLENGE`), rationale.
* **7. Validation Criteria:**
  Every finding has an investigator decision record; challenged findings trigger governed resolution tasks.

---

### Stage 14: Report Readiness
* **1. Real-World Investigative Activity:**
  Pre-publication quality audit. Verifying that all evidence has valid integrity hashes, no executions are currently pending, and all findings have been peer-reviewed (ISO/IEC 27037 §8.4).
* **2. Existing ADFIP Implementation:**
  `ReportReadinessService` in `backend/app/services/report_readiness.py` evaluating 12 forensic gates.
* **3. Missing or Incomplete Functionality:**
  Gate 11 previously had an unimported `AnalysisRequest` defect that crashed during negative suite testing.
* **4. Required Correction:**
  Restored canonical implementation matching verified baseline; 100% of negative suite tests passing.
* **5. Relevant AI Agent Responsibilities:**
  None (Audit boundary: Report readiness gates are strictly deterministic Boolean checks).
* **6. Required Evidence:**
  Case integrity status, task completion status, review coverage percentage.
* **7. Validation Criteria:**
  Report generation returns HTTP 422 with gate failure details if any of the 12 gates fails.

---

### Stage 15: Final Forensic Report
* **1. Real-World Investigative Activity:**
  Compilation of an authoritative, court-admissible forensic report documenting the complete investigation, tool versions, methodology, evidence, findings, and limitations (NIST SP 800-86 §3.4).
* **2. Existing ADFIP Implementation:**
  `FinalForensicReportService` in `backend/app/services/final_forensic_report.py`. Generates all 8 mandatory sections, JSON, Markdown, and PDF.
* **3. Missing or Incomplete Functionality:**
  Section 8 disposition logging needed clear representation of challenged findings.
* **4. Required Correction:**
  Include complete challenge resolution audit logs and examiner dispositions in Section 8.
* **5. Relevant AI Agent Responsibilities:**
  `ReportIntelligenceAgent`: Drafts executive narrative summaries grounded strictly in cited findings without hallucinating facts.
* **6. Required Evidence:**
  Complete case dossier, tool execution logs, finding dispositions.
* **7. Validation Criteria:**
  Report contains all 8 mandatory sections; tampering with report content breaks cryptographic verification.

---

### Stage 16: Investigator Approval
* **1. Real-World Investigative Activity:**
  Final sign-off by the lead investigator. Formal certification that the investigation was conducted in accordance with applicable legal and technical standards (ISO/IEC 27037 §8.5).
* **2. Existing ADFIP Implementation:**
  Report certification record with examiner ID, timestamp, and immutable SHA-256 hash.
* **3. Missing or Incomplete Functionality:**
  Investigator sign-off was implicitly recorded rather than requiring explicit digital certification.
* **4. Required Correction:**
  Record explicit investigator approval signature in report metadata.
* **5. Relevant AI Agent Responsibilities:**
  None (Legal boundary: AI agents cannot sign off on forensic reports).
* **6. Required Evidence:**
  Investigator ID, approval timestamp, report hash.
* **7. Validation Criteria:**
  Unapproved reports are marked `DRAFT`; approved reports are marked `FINAL`.

---

### Stage 17: Case Closure
* **1. Real-World Investigative Activity:**
  Formal closing of the investigation. Evidence retention policy application, write-protection verification, audit log sealing, and transition to read-only archival state (ISO/IEC 27037 §8.6).
* **2. Existing ADFIP Implementation:**
  `CaseClosureService` in `backend/app/services/case_closure.py`. Validates all closure gates before setting `case.status = "CLOSED"`.
* **3. Missing or Incomplete Functionality:**
  Attempts to modify evidence or execute tools on closed cases must be completely blocked across all endpoints.
* **4. Required Correction:**
  Enforce `check_case_not_closed()` across all intake, execution, and review endpoints.
* **5. Relevant AI Agent Responsibilities:**
  None (Closure boundary: Archival and sealing are deterministic administrative operations).
* **6. Required Evidence:**
  Final report SHA-256, sealed audit hash chain root, closure timestamp.
* **7. Validation Criteria:**
  Any mutation request on a `CLOSED` case returns HTTP 422 Unprocessable Content.

---

*Mapping certified against ISO/IEC 27037:2012 and NIST SP 800-86 standards.*

