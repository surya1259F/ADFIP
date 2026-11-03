# ADFIP — Investigation Intelligence & Decision Engine Gap Analysis

**Date:** 2026-11-01  
**Project:** Autonomous Digital Forensic Investigation Platform (ADFIP)  
**Repository:** `surya1259F/ADFIP` (`/home/nandireddy/ADFIP-1`)  
**Target Branch:** `feature/investigation-resolution-resource-ai`  
**Document Purpose:** Comprehensive architectural audit and gap analysis of the existing platform to establish the implementation roadmap for the Evidence-Driven Investigation Decision Engine and operational forensic intelligence workflow.

---

## 1. Executive Architectural Audit

### 1.1 Existing Backend Architecture
* **Framework:** FastAPI (`backend/app/main.py`) with asynchronous lifecycle event management, CORS configuration, and structured request tracking (`Request-ID`).
* **Database & ORM:** SQLAlchemy ORM with SQLite database at `/home/nandireddy/ADFIP-1/adfir.db` (48 tables), version-controlled via 26 deterministic Alembic migrations (`alembic/versions/`).
* **Security & Auth:** JWT HMAC-SHA256 tokens with dynamic file-based secret generation, PBKDF2-SHA256 password hashing, OIDC Google OAuth 2.0 with PKCE and single-use state/nonce validation, token revocation table (`revoked_tokens`), and constant-time dummy verify on failed logins. **Authentication is verified, frozen, and protected.**
* **Core Subsystems:**
  1. *Acquisition & Vault:* Evidence registration, SHA-256 integrity verification, immutable read-only storage (`vault.py`, `integrity.py`).
  2. *Evidence Intelligence:* Magic header inspection, MIME detection, format identification, resource requirement estimation (`intelligence.py`).
  3. *Strategy Engine:* Capability registry seeding, evidence-to-domain mapping, topological dependency graph sorting, stopping condition evaluation (`strategy_engine.py`).
  4. *Tool Selection & Scheduler:* Capability-to-tool resolution, system resource introspection, queued `analysis_requests` lifecycle (`scheduler.py`).
  5. *Secure Execution Engine:* Subprocess execution with process limit enforcement, timeout handling, strict argv sanitization, isolated workspace directories (`execution.py`).
  6. *Raw Outputs & Extraction:* Standard output/error capture, parser registry (`fls`, `evtx`, `yara`, `pslist`, `netscan`, `exiftool`, generic text) (`raw_outputs.py`, `artifact_extraction.py`).
  7. *Artifact Normalization:* Entity mapping (`PROCESS`, `NETWORK_CONNECTION`, `FILE`, `USER_ACCOUNT`), canonical JSON hashing, identity hashing (`normalization.py`).
  8. *Unified Timeline:* ISO 8601 normalization, time-zone offsets, chronological timeline generation (`timeline.py`).
  9. *Cross-Domain Correlation:* Shared identifier matching (IP, hash, username, PID), temporal proximity clustering, bipartite graph construction (`correlation.py`).
  10. *Deterministic Findings:* Rule-based candidate evaluation, confidence calculation, provenance linkage (`findings.py`).
  11. *AI Copilot & Reasoning:* Encrypted multi-provider config (Gemini, OpenAI, Anthropic, Local), prompt injection detection, deterministic fallback (`ai_provider.py`, `ai_reasoning.py`).
  12. *Investigator Review & Governance:* Human-in-the-loop decisions (`ACCEPT`, `REJECT`, `CHALLENGE` with challenge categories, `REQUEST_MORE_EVIDENCE`) (`investigator_review.py`, `governance.py`).
  13. *Forensic Reporting:* Case synthesis, section rendering, report provenance hash chain (`final_report.py`, `report_readiness.py`).

### 1.2 Existing Frontend Architecture
* **Tech Stack:** React 19, TypeScript 6, Vite 8.2.2, TailwindCSS, TanStack React Query v5, Zustand state management.
* **Routing & Pages:**
  * Clean route structure in `frontend/src/app/routes.tsx` with lazy-loading and protected route wrappers.
  * Dedicated pages: Cases (`CasesPage.tsx`, `CaseOverviewPage.tsx`), Evidence (`EvidencePage.tsx`, `EvidenceDetailPage.tsx`), Intelligence (`IntelligencePage.tsx`), Strategy (`StrategyPage.tsx`), Execution (`ExecutionPage.tsx`), Findings (`FindingsPage.tsx`), Verification & Review (`VerificationPage.tsx`, `InvestigatorReviewPage.tsx`), Reports (`ReportsPage.tsx`), Tools (`ToolsPage.tsx`), Audit (`AuditPage.tsx`).
* **Design Language:** Modern, professional forensic workstation UI with responsive layout, zero mock indicators, and strict state synchronization with the backend API (`/api/v1/*`).

### 1.3 Forensic Tool Realities on Host
* **Installed System Binaries:**
  * The Sleuth Kit (TSK) v4.12.1 (`/usr/bin/fls`, `/usr/bin/mmls`, `/usr/bin/fsstat`, `/usr/bin/img_stat`, `/usr/bin/istat`, `/usr/bin/tsk_loaddb`, `/usr/bin/tsk_recover`) is fully installed and functional.
  * SQLite3 CLI (`/usr/bin/sqlite3`) is installed and functional.
  * Linux GNU text utilities (`/usr/bin/strings`, `/usr/bin/file`, etc.) are installed.
* **Installed Python Forensic Libraries:**
  * `python-evtx` (`Evtx` v0.7.4) is installed in the virtual environment.
* **Currently Uninstalled Tools:**
  * `yara`, `exiftool`, `volatility3`, `tshark`, `zeek`, `bulk_extractor`, `binwalk` are not installed as standalone host binaries.
  * *Critical Rule:* The platform must never simulate tool execution or invent fake findings for missing tools. It must accurately detect tool availability, attempt python-native fallback adapters where feasible (e.g. built-in SQLite parsing, pure-Python EVTX parsing, regex/string scanners), or transparently report `BLOCKED_NO_CAPABLE_TOOL` with explicit missing dependency disclosure.

---

## 2. Identified Functional & Architectural Gaps

```
CASE OBJECTIVE
      ↓  [GAP 1: No formal Objective-to-Question translation]
INVESTIGATIVE QUESTIONS
      ↓  [GAP 2: No Question-to-Evidence feasibility classification]
EVIDENCE CHARACTERISTICS & CLASSIFICATION
      ↓  [GAP 3: Signatures limited; untrusted evidence handling needs hardening]
REQUIRED FORENSIC CAPABILITIES
      ↓  [GAP 4: Static keyword capability selection; missing explainability]
AVAILABLE TOOLS (Tool Registry)
      ↓  [GAP 5: Missing binary handling; missing multi-tool pipeline logic]
EXECUTION PLAN (DAG & Governance)
      ↓  [GAP 6: Real execution exists, but needs question-driven sequencing]
ACTUAL RESULTS & ARTIFACT EXTRACTION
      ↓  [GAP 7: Correlation lacks deep temporal timezone conflict checks]
EVIDENCE-GROUNDED AI REASONING
      ↓  [GAP 8: Single-prompt AI call lacks multi-agent specialization & claims separation]
INVESTIGATOR REVIEW & GOVERNANCE
      ↓  [GAP 9: Review exists, but challenge resolution loop needs tightening]
FINAL FORENSIC REPORTING
         [GAP 10: Needs strict 16-section ISO/NIST structure with zero ungrounded claims]
```

### Gap 1: Missing Objective-to-Question Translation
* **Current State:** `Case.objective` is stored as an arbitrary text field. In `strategy_engine.py:449`, it is queried only with rudimentary string checks (e.g. `"malware" in objective_text`).
* **Required State:** The system must parse and understand case objectives across standard forensic archetypes (e.g., Unauthorized Access, Malware Infection, Data Exfiltration, Suspicious Process Execution, Web/Browser Activity, Anti-Forensics / File Deletion, Insider Threat). It must decompose the objective into concrete, hypothesis-neutral **Investigative Questions** (e.g., *"Are there indications of unauthorized authentication during the incident window?"*, *"Did suspicious processes spawn from temporary folders?"*).

### Gap 2: Missing Question-to-Evidence Feasibility Assessment
* **Current State:** Strategy engine maps capabilities directly to evidence categories without evaluating whether the questions can actually be answered by the uploaded evidence.
* **Required State:** The engine must classify each investigative question against the available evidence into one of five rigorous statuses:
  1. `INVESTIGABLE` — Necessary evidence items are present and verified.
  2. `PARTIALLY_INVESTIGABLE` — Some relevant evidence exists, but corroborating sources are missing.
  3. `REQUIRES_ADDITIONAL_EVIDENCE` — Answering the question requires evidence types not yet submitted (e.g., memory dump required for process injection).
  4. `UNSUPPORTED_BY_TOOLS` — Evidence exists but compatible tool binaries or parsers are unavailable.
  5. `NOT_APPLICABLE` — Question is out of scope for the current case profile.

### Gap 3: Evidence Classification & Untrusted Intake Pipeline
* **Current State:** `intelligence.py` uses magic numbers for a limited set of formats. It does not validate compound forensic formats (e.g., Android backups, partitioned disk images, complex memory structures, corrupted files).
* **Required State:** A hardened classification pipeline that uses signature validation, header verification, format corruption checks, and platform hints without executing untrusted code. All evidence must be treated as untrusted data.

### Gap 4: Capability-Based Tool Selection with Plain-Language Explainability
* **Current State:** `ToolRequirementResolver` chooses the first tool mapped to a capability without recording an investigator-facing justification.
* **Required State:** Every tool selection must generate a structured, auditable explanation including:
  * Associated investigative question.
  * Required capability.
  * Selected tool and version.
  * Plain-language rationale explaining *why* this tool was selected for this evidence.
  * Expected forensic output.
  * Execution prerequisites, dependencies, and risks.
  * Potential alternative tools or graceful degradation path.

### Gap 5: Multi-Tool Forensic Pipelines
* **Current State:** Tasks are executed as isolated, single-step operations.
* **Required State:** Support multi-stage tool pipelines where output from one tool feeds the next (e.g., SleuthKit `fls` extracts directory tree $\rightarrow$ targeted executable extraction $\rightarrow$ YARA / static analysis; or EVTX parsing $\rightarrow$ targeted logon event filtering $\rightarrow$ correlation).

### Gap 6: Structured Evidence-Grounded AI Reasoning (Claim Categorization)
* **Current State:** `ai_reasoning.py` generates a single reasoning record with raw LLM output and deterministic fallback.
* **Required State:** The reasoning engine must strictly enforce claim classification into 5 distinct epistemological tiers:
  1. **Raw Observation:** Directly extracted artifact text/data (e.g., *"Event ID 4625 recorded at 2026-10-12 04:12:00 UTC for account 'Administrator'"*).
  2. **Derived Observation:** Statistically aggregated or normalized metric (e.g., *"45 failed logon attempts within 3 minutes"*).
  3. **Analytical Interpretation:** Expert deductions grounded in observations (e.g., *"The frequency of authentication failures is consistent with a brute-force pattern"*).
  4. **Investigative Hypothesis:** Working theory requiring further validation (e.g., *"Potential lateral movement attempt"*).
  5. **Confirmed Conclusion:** Claim validated by multi-source evidence and approved by the investigator.
  * *Zero Hallucination Rule:* Every claim must carry bidirectional foreign keys to its supporting `artifact_id`, `evidence_id`, and `execution_id`.

### Gap 7: Multi-Agent Specialization in AI Reasoning
* **Current State:** 11 specialist agents exist in the database, but in the AI reasoning layer, only a single context builder prompt is dispatched.
* **Required State:** Distinct AI agent roles with specialized prompts, input boundaries, and validation:
  * *Agent 1: Case Understanding Agent* (objectives, scope, question formulation).
  * *Agent 2: Evidence Intelligence Agent* (format validation, evidence characteristics).
  * *Agent 3: Investigation Planning Agent* (capabilities, execution dependencies).
  * *Agent 4: Tool Selection Agent* (tool suitability, limitation evaluation).
  * *Agent 5: Forensic Analysis Agent* (artifact parsing, observation synthesis).
  * *Agent 6: Correlation Agent* (multi-artifact timeline alignment, conflict detection).
  * *Agent 7: Report Generation Agent* (defensible, evidence-grounded report synthesis).

### Gap 8: Strict 16-Section Final Forensic Report
* **Current State:** `final_report.py` generates basic sections (case, evidence, execution, findings, review).
* **Required State:** Comprehensive report engine implementing the exact 16 sections required by court-admissible standards (ISO/IEC 27037 and NIST SP 800-86), complete with evidence hashes, chain-of-custody log, tool execution provenance, alternative explanations, contradictory evidence, and explicit limitations disclosure.

### Gap 9: Frontend Views & Investigation Workflow
* **Current State:** Frontend has separate pages for Evidence, Strategy, Findings, and Review, but lacks:
  * An **Investigation Questions View** displaying the questions, feasibility, and required evidence.
  * A **Tool Selection Rationale Inspector** showing *why* each tool was chosen.
  * An **Evidence-Grounded Finding Inspector** linking each claim directly to the underlying raw hex/text artifact.

---

## 3. Integration Requirements & Architectural Solution

### 3.1 New Core Engine: `EvidenceDecisionEngine`
We will introduce a dedicated service: `backend/app/services/decision_engine.py`.
It will integrate:
1. `CaseObjectiveAnalyzer`: Analyzes case objectives and extracts standardized incident categories and parameters.
2. `InvestigativeQuestionGenerator`: Decomposes objectives into structured investigative questions.
3. `EvidenceFeasibilityClassifier`: Evaluates submitted evidence against question requirements and classifies feasibility.
4. `CapabilityDecisionMapper`: Maps questions and evidence characteristics to required capabilities.
5. `ExplainableToolSelector`: Resolves installed tools and builds plain-language selection rationales.
6. `ExecutionPlanSynthesizer`: Emits a fully articulated `InvestigationPlan` containing questions, tasks, dependencies, and resource constraints.

### 3.2 Database Schema Compatibility
* The existing schema already possesses `cases.objective`, `evidence_items`, `evidence_intelligence`, `forensic_capabilities`, `investigation_plans`, `investigation_tasks`, `tool_selections`, `analysis_requests`, `deterministic_findings`, `ai_reasoning_records`, `investigator_reviews`, and `reports`.
* All new structures (investigative questions, feasibility classifications, selection rationales) will be stored in the existing JSON-supported fields (`InvestigationPlan.tasks`, `InvestigationPlan.objectives`, `InvestigationTask.rationale`, `ToolSelectionRecord.selection_rationale`, `EvidenceItem.intelligence_json`) or in backward-compatible model columns.
* **No tables will be dropped, no existing records will be modified or deleted, and no destructive migrations will be introduced.**

---

## 4. Implementation Phasing & Roadmap

| Phase | Description | Deliverables | Status |
|---|---|---|---|
| **Phase 1** | Repository Audit & Architectural Gap Analysis | `docs/review/INVESTIGATION_INTELLIGENCE_GAP_ANALYSIS.md` | **COMPLETED** |
| **Phase 2** | Forensic Tool Registry & Real-World Capability Mapping | Enhanced `PlatformAwareToolRegistry`, verified tool runners, pure-Python fallbacks | Planned |
| **Phase 3** | Evidence Classification & Untrusted Intake Hardening | Extended magic/signature classification, corruption detection, platform hints | Planned |
| **Phase 4** | Investigative Question Generation Engine | Structured question templates, archetype analysis, feasibility classification | Planned |
| **Phase 5** | Evidence-Driven Investigation Decision Engine | `backend/app/services/decision_engine.py` connecting Objective $\rightarrow$ Evidence $\rightarrow$ Questions $\rightarrow$ Tools $\rightarrow$ Plan | Planned |
| **Phase 6** | Capability-Based Tool Selection with Explainability | Plain-language rationales, multi-tool pipeline sequences, dependency validation | Planned |
| **Phase 7** | Execution Planning & Resource Governance | DAG generation, topological ordering, cancellation, timeout, and limits | Planned |
| **Phase 8** | Forensic Tool Execution & Real Artifact Extraction | SleuthKit `fls`/`mmls` execution, `python-evtx` log extraction, artifact parsers | Planned |
| **Phase 9** | Real AI Provider & Gemini Integration | Robust Gemini 3.8 Flash caller, quota handling, error categorization, encrypted keys | Planned |
| **Phase 10** | Evidence-Grounded AI Reasoning & 5-Tier Claim Hierarchy | Raw observation vs interpretation, mandatory artifact provenance, no hallucinations | Planned |
| **Phase 11** | Cross-Artifact Temporal & Entity Correlation | Multi-domain timeline alignment, conflict detection, contradiction analysis | Planned |
| **Phase 12** | Complete 16-Section Final Forensic Report Generation | NIST/ISO court-grade report builder, section rendering, audit hash verification | Planned |
| **Phase 13** | Frontend Integration & Investigator Workstation Views | Investigation Questions view, Selection Rationale panel, Grounding Inspector | Planned |
| **Phase 14** | End-to-End Verification, Automated Tests & Final Audit | Comprehensive test suites, real evidence pipeline test, `FINAL_INVESTIGATION_INTELLIGENCE_AUDIT.md` | Planned |

---

## 5. Risk Assessment & Mitigations

1. **Risk:** Uninstalled forensic tool binaries (`yara`, `volatility3`, `tshark`) on host Linux system.
   * *Mitigation:* Explicitly detect availability; gracefully fall back to native Python libraries (`Evtx`, built-in SQLite parsing, string/regex scanners) where possible; mark tasks as `BLOCKED_NO_CAPABLE_TOOL` when dependencies are genuinely missing. **Never fake results.**
2. **Risk:** AI Hallucination or fabricated evidence findings.
   * *Mitigation:* Require strict validation against `StructuredArtifact` and `NormalizedArtifact` database records before any observation or finding is stored; enforce 5-tier claim separation; require explicit investigator approval (`InvestigatorReviewRecord`) before any finding enters the report.
3. **Risk:** Database corruption or schema breakage during tests.
   * *Mitigation:* All tests use isolated SQLite in-memory or temporary files with `StaticPool`; primary `adfir.db` is never dropped or reset.
4. **Risk:** Sandboxed execution blocking external Gemini API calls.
   * *Mitigation:* Verify network routing, handle timeouts gracefully, provide deterministic offline fallback when external network is unavailable.

---

## 6. Audit Certification

This gap analysis establishes the baseline state and complete engineering blueprint for ADFIP. Implementation will proceed according to the strict non-destructive rules and implementation phases outlined above.

