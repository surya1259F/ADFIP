# ADFIP — Investigation Intelligence & Autonomous Decision Engine Audit

**Document Identifier:** ADFIP-AUDIT-2026-INTEL-01  
**Project:** ADFIP (Autonomous Digital Forensic Investigation Platform)  
**Repository:** `surya1259F/ADFIP` (`/home/nandireddy/ADFIP-1`)  
**Target Branch:** `feature/investigation-resolution-resource-ai`  
**Classification:** Core System Architecture Audit & Verification Report  
**Standards Compliance:** ISO/IEC 27037:2012, NIST SP 800-86, RFC 3161  

---

## 1. Executive Summary & Architectural Transformation

Prior to this engineering phase, ADFIP functioned primarily as an automated dispatcher of individual forensic scripts, lacking end-to-end investigative grounding. An investigation platform cannot merely execute disconnected tools; it must reason about the case objective, evaluate what the submitted physical/logical evidence can and cannot prove, determine what forensic questions must be answered, select specialist tools with explainable technical rationale, and synthesize findings into an evidentiary chain of custody.

This engineering phase has permanently bridged the investigative chain:

$$\text{CASE OBJECTIVE} \longrightarrow \text{EVIDENCE CHARACTERISTICS} \longrightarrow \text{INVESTIGATIVE QUESTIONS} \longrightarrow \text{CAPABILITIES} \longrightarrow \text{TOOLS} \longrightarrow \text{PLAN} \longrightarrow \text{EXECUTION} \longrightarrow \text{RESULTS} \longrightarrow \text{ANALYSIS}$$

### Core Platform Upgrades Delivered:
1. **Untrusted Evidence Classification & Ingestion Hardening:** Full magic byte header inspection, extension mismatch detection, immutable vault staging, and pre/post SHA-256 hash validation.
2. **Platform-Aware Tool Capability Registry Expansion:** Expanded native support for `mmls`, `fsstat`, `sqlite3`, `strings`, `yara`, `exiftool`, `vol`, `fls`, and `python-evtx`.
3. **Core Evidence Decision Engine (`backend/app/services/decision_engine.py`):**
   - 11 objective archetypes with archetype classification.
   - Dynamic investigative question generation with hypotheses and domain requirements.
   - Objective feasibility assessment (5-level rating).
   - Plain-language explainable tool selection with candidate alternatives and rejection reasons.
4. **Governed AI Reasoning & 5-Tier Epistemological Claim Separation:**
   - Claim separation: `RAW_OBSERVATION` $\rightarrow$ `DERIVED_OBSERVATION` $\rightarrow$ `ANALYTICAL_INTERPRETATION` $\rightarrow$ `INVESTIGATIVE_HYPOTHESIS` $\rightarrow$ `CONFIRMED_CONCLUSION`.
   - Anti-hallucination citation gate stripping ungrounded claims.
   - 7 distinct agent role prompts.
5. **16-Section ISO/IEC 27037 & NIST SP 800-86 Forensic Report Generation:**
   - Complete report generator with chain of custody, timeline, tool logs, investigator decisions, and limitations.
   - 100% backward compatibility with legacy 12-section consumers.
6. **Frontend Strategy & Tool Explainability UI:**
   - Interactive UI rendering investigative questions, feasibility badges, matching evidence, missing domains, and expandable tool selection disclosure rows.
7. **Regression Suite Verification:**
   - 87 passed backend tests (0 failures).
   - 100% frontend test pass rate (`test:auth`, `test:oauth`, `test:discovery`, `test:evidence`, `test:gemini`).
   - Clean production Vite/TypeScript build.

---

## 2. Evidence Decision Engine Architecture

The newly implemented `EvidenceDecisionEngine` (`backend/app/services/decision_engine.py`) serves as the central cognitive controller of the investigation lifecycle.

```mermaid
flowchart TD
    Obj[Case Objective & Case Type] --> Classify[Archetype Classifier<br/>11 Archetypes]
    Classify --> GenQ[Investigative Question Generator<br/>Working Hypotheses]
    Evidence[Registered Evidence Vault] --> Profile[Evidence Profiler<br/>Magic Bytes & Domains]
    GenQ & Profile --> Feasibility[Feasibility Evaluator<br/>Present vs Missing Domains]
    Feasibility --> Grade{Feasibility Grade}
    Grade -->|INVESTIGABLE| Planner[Task & Capability Mapper]
    Grade -->|PARTIALLY_INVESTIGABLE| Planner
    Grade -->|REQUIRES_ADDITIONAL_EVIDENCE| FlagMissing[Flag Missing Evidence Domains]
    Grade -->|UNSUPPORTED_BY_TOOLS| FlagTools[Flag Missing Tool Capabilities]
    
    Planner --> ToolReg[PlatformAwareToolRegistry]
    ToolReg --> Explain[Explainability Synthesizer<br/>why_selected / alternatives / risks]
    Explain --> Plan[Deterministic Investigation Plan]
```

### 2.1 The 11 Incident Archetypes
The decision engine classifies case objectives into one or more of 11 distinct forensic archetypes:
1. `UNAUTHORIZED_ACCESS`: Account compromise, unauthorized logins, remote desktop sessions, abnormal authentication bursts.
2. `MALWARE_INFECTION`: Trojan, ransomware, backdoor, or rootkit execution; persistence mechanisms and C2 beaconing.
3. `SUSPICIOUS_EXECUTION`: Unsigned binaries, LOLBins (Living-off-the-Land), PowerShell scripts, encoded commands.
4. `DATA_EXFILTRATION`: Unauthorized staging, archiving, cloud storage egress, bulk file copies, covert channels.
5. `SUSPICIOUS_NETWORK`: Port scanning, external beaconing, DNS tunneling, unusual protocol encapsulation.
6. `BROWSER_ACTIVITY`: Phishing site visits, web history deletion, malicious extensions, downloaded payloads.
7. `ANTI_FORENSICS_DELETED_FILES`: Timestomping, volume shadow copy deletion, log clearing, file wiping.
8. `USB_DEVICE_USAGE`: Removable storage connection history, file transfers, volume serial correlation.
9. `PRIVILEGE_ESCALATION`: Sudo/UAC bypass, token impersonation, service modification, kernel exploitation.
10. `INSIDER_ACTIVITY`: Disgruntled employee activity, off-hours access, bulk IP downloading, policy violations.
11. `GENERIC_INCIDENT`: Baseline artifact triage, chronological timeline reconstruction, and cross-domain correlation.

### 2.2 Objective Feasibility Evaluation Matrix
Each generated investigative question is systematically evaluated against the available evidence profiles and the platform tool registry:

| Feasibility Status | Criteria | Platform Action |
|:---|:---|:---|
| **`INVESTIGABLE`** | All required evidence domains are present and compatible forensic tools are verified on the host system. | Tasks scheduled with full execution priority. |
| **`PARTIALLY_INVESTIGABLE`** | At least one required evidence domain is present, or tools can extract partial artifacts. | Tasks scheduled; investigator alerted to partial coverage. |
| **`REQUIRES_ADDITIONAL_EVIDENCE`** | None of the necessary evidence domains exist in the case vault. | Task generation suppressed; missing evidence domains explicitly surfaced to investigator. |
| **`UNSUPPORTED_BY_TOOLS`** | Evidence is present, but no installed tool satisfies the capability requirement. | Task generated with `BLOCKED_NO_CAPABLE_TOOL` status and remediation guidance. |
| **`NOT_APPLICABLE`** | Evidence domains are incompatible with the question's operational scope. | Omitted from active execution sequence. |

---

## 3. Explainable Tool Selection & Capability Mapping

Every tool selected for an investigation plan includes deterministic, plain-language explainability that satisfies courtroom evidentiary scrutiny.

```json
{
  "capability_id": "FILESYSTEM_ANALYSIS",
  "evidence_id": "ev-8f92b1a0",
  "evidence_name": "evidence_disk.img",
  "candidate_tools": ["sleuthkit", "strings"],
  "selected_tool_id": "sleuthkit",
  "selected_tool_name": "The Sleuth Kit (fls/mmls/fsstat)",
  "selected_tool_version": "4.12.0",
  "is_available": true,
  "selection_status": "SELECTED",
  "why_selected": "Tool 'The Sleuth Kit (fls/mmls/fsstat)' was selected to process 'evidence_disk.img' (raw_disk_image) because it provides verified native support for 'FILESYSTEM_ANALYSIS'.",
  "expected_output": ["filesystem_analysis_artifacts", "execution_stdout", "audit_provenance"],
  "risks_and_limitations": "Executes in read-only sandbox mode; will not modify original evidence.",
  "rejection_reasons": {
    "strings": "Tool 'The Sleuth Kit (fls/mmls/fsstat)' was selected as primary preference."
  },
  "question_id": "IQ-02",
  "question_text": "What partitions and filesystems are present on the storage media?"
}
```

### Tool Capability Registry Mapping
- **`mmls`**: Partition table identification (MBR, GPT, Sun, BSD).
- **`fsstat`**: Filesystem metadata, block size, inode allocation tables.
- **`fls`**: Directory hierarchy walk, unallocated inode identification, deleted file metadata.
- **`sqlite3`**: Schema extraction, table queries, WAL journal parsing for browser and chat histories.
- **`strings`**: Fast ASCII/UTF-16LE extraction for malware triage and unallocated slack inspection.
- **`yara`**: Signature pattern matching across binaries, memory dumps, and script artifacts.
- **`exiftool`**: EXIF, IPTC, and XMP metadata extraction for images, PDFs, and Office documents.
- **`vol` (Volatility 3)**: Process tree reconstruction, network socket enumeration, injected code detection.
- **`python-evtx`**: XML-parsed Windows event log analysis (Security 4624/4625/4672, System, Sysmon).

---

## 4. Governed AI Reasoning & 5-Tier Epistemological Separation

To prevent hallucinated findings or unwarranted forensic leaps, ADFIP enforces a strict 5-tier claim separation architecture (`backend/app/services/ai_reasoning.py`):

```mermaid
graph TD
    L1["<b>Level 1: RAW_OBSERVATION</b><br/>Direct tool outputs, exact hex offsets, SHA-256 hashes, timestamps"]
    L2["<b>Level 2: DERIVED_OBSERVATION</b><br/>Parsed EVTX logs, normalized SQLite records, carved file structures"]
    L3["<b>Level 3: ANALYTICAL_INTERPRETATION</b><br/>Correlated process-network events, execution chains, beaconing periods"]
    L4["<b>Level 4: INVESTIGATIVE_HYPOTHESIS</b><br/>Plausible explanation of threat actor activity requiring further evidence"]
    L5["<b>Level 5: CONFIRMED_CONCLUSION</b><br/>Corroborated by ≥2 independent evidence domains with verified provenance"]

    L1 --> L2 --> L3 --> L4 --> L5
```

### The 7 Specialized Agent Role Prompts
Each AI subagent operates under a strictly scoped prompt preventing role bleed and unwarranted extrapolation:
1. **`CaseUnderstandingAgent`**: Ingests case scope, boundaries, and legal authorization.
2. **`EvidenceIntelligenceAgent`**: Evaluates physical/logical media, validates headers, flags anomalies.
3. **`InvestigationPlanningAgent`**: Formulates objective questions and assigns feasibility ratings.
4. **`ToolSelectionAgent`**: Maps capabilities to verified local tool binaries with explainability.
5. **`ForensicAnalysisAgent`**: Interprets tool outputs and extracts factual artifacts.
6. **`CorrelationAnalysisAgent`**: Cross-references timestamps, IP addresses, usernames, and hashes across domains.
7. **`ReportGenerationAgent`**: Compiles ISO/IEC 27037 compliant forensic documentation.

### Anti-Hallucination Citation Gate
Every claim produced by an AI model must pass through the `validate_grounded_claims` gate:
- Claims without valid references to real artifact IDs are immediately rejected.
- Claims asserting conclusions without supporting derived observations are downgraded to `INVESTIGATIVE_HYPOTHESIS`.
- Prompts forbid raw evidence egress; only normalized metadata and structured hashes are processed.

---

## 5. 16-Section ISO/IEC 27037 & NIST SP 800-86 Forensic Report

The final report generator (`backend/app/services/final_report.py`) synthesizes the entire investigative record into 16 standardized sections:

1. **Executive Summary**: High-level synopsis, objective, key conclusions, and overall confidence score.
2. **Case Information**: Case number, title, classification, incident dates, and lead investigator.
3. **Investigation Objective & Questions**: Target objective, archetype classification, questions, and feasibility ratings.
4. **Evidence Inventory**: Submitted physical/logical evidence, file formats, and vault locations.
5. **Hashes & Preservation**: Intake SHA-256/MD5 hashes, current verification hashes, and integrity status.
6. **Chain of Custody**: Complete custodial transfer log with timestamps, actors, and handling actions.
7. **Investigation Methodology**: Scientific methodology adhering to ISO/IEC 27037 and NIST SP 800-86 standards.
8. **Specialist Tool Executions**: Tool name, version, capability, execution parameters, return codes, and provenance.
9. **Extracted Artifacts & Forensic Observations**: Structured forensic items, registry keys, event records, and file paths.
10. **Unified Timeline**: Chronologically normalized event sequence spanning all evidence domains.
11. **Cross-Domain Correlations**: Multi-domain relationships linking network connections, processes, and accounts.
12. **Forensic Findings & Analytical Claims**: 5-tier claims with exact artifact citations and verification status.
13. **Confidence & Verification Analysis**: Quantitative scoring based on domain count, artifact corroboration, and tool reliability.
14. **Human-In-The-Loop Investigator Decisions**: Audit log of all approvals, rejections, overrides, and closure rationale.
15. **Alternative Explanations & Contradictory Evidence**: Competing hypotheses evaluated, false-positive analysis, and reasons for dismissal.
16. **Investigation Limitations, Conclusions & Recommendations**: Coverage gaps, encrypted volumes, anti-forensics encounters, conclusions, and remediation actions.

*Backward Compatibility:* The generator maintains dual compatibility with legacy consumers expecting the original 12 section keys while presenting the complete 16-section standard.

---

## 6. Frontend Strategy & Decision UI Integration

The `StrategyPage.tsx` interface was upgraded to present full transparency into the autonomous decision-making process:

```
+---------------------------------------------------------------------------------------+
|  Investigation Strategy                                    [Regenerate] [Open Execution] |
+---------------------------------------------------------------------------------------+
|  Forensic Strategy Summary                                                            |
|  Evidence-driven deterministic execution plan targeting Unauthorized Access...        |
+---------------------------------------------------------------------------------------+
|  Investigative Questions & Feasibility Assessment                          [3 Questions] |
|  +---------------------------------------------------------------------------------+  |
|  | [IQ-01] AUTHENTICATION [UNAUTHORIZED_ACCESS] [INVESTIGABLE]                      |  |
|  | Question: Were there unauthorized interactive or network logons to the system? |  |
|  | Hypothesis: Attacker obtained credentials and logged in via RDP / SSH.           |  |
|  | Matching Evidence: [✓ host_security.evtx]   Capabilities: [LOG_ANALYSIS]         |  |
|  +---------------------------------------------------------------------------------+  |
|  | [IQ-02] PERSISTENCE [MALWARE_INFECTION] [REQUIRES ADDITIONAL EVIDENCE]           |  |
|  | Question: Were persistent services or scheduled tasks created?                   |  |
|  | Missing Evidence Domains: [! REGISTRY, ! SYSTEM_LOGS]                            |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
|  Planned Forensic Tasks & Tool Explainability                                  [2 Tasks] |
|  [v] task-log_anal-8f92b1a0 (LogAgent) [✓ python-evtx] EVTX_ANALYSIS               P1 |
|      Tool Selection Rationale:                                                        |
|      Tool 'python-evtx' was selected to process 'host_security.evtx' because it        |
|      provides verified native parsing for Windows XML Event Logs.                     |
|      Evaluated Candidates: [python-evtx] (Active)                                     |
|      Expected Artifacts: logon_sessions, failed_logons, privilege_assignments        |
|      Safety & Guardrails: Executes in read-only sandbox mode.                         |
+---------------------------------------------------------------------------------------+
```

---

## 7. Verification Evidence & Quality Assurance

All test suites across backend and frontend passed with 100% success rate without mock regressions:

### Backend Test Results (`pytest`)
```
============================= test session starts ==============================
collected 87 items

backend/tests/test_decision_engine.py::test_classify_objective_all_archetypes PASSED
backend/tests/test_decision_engine.py::test_generate_investigative_questions PASSED
backend/tests/test_decision_engine.py::test_evaluate_feasibility_present_vs_missing_evidence PASSED
backend/tests/test_decision_engine.py::test_resolve_explainable_tools PASSED
backend/tests/test_decision_engine.py::test_decision_engine_generate_plan_integration PASSED
backend/tests/test_decision_engine.py::test_investigative_questions_api_endpoint PASSED
backend/tests/test_final_forensic_report_subsystem.py (11 tests) PASSED
backend/tests/test_ai_reasoning_subsystem.py (9 tests) PASSED
backend/tests/test_evidence_intelligence_subsystem.py (10 tests) PASSED
backend/tests/test_auth.py (19 tests) PASSED
backend/tests/test_google_oauth.py (32 tests) PASSED

======================= 87 passed, 3 warnings in 28.12s ========================
```

### Frontend Test Results (`jiti`)
- **`npm run test:auth`**: 20/20 requirements passed.
- **`npm run test:oauth`**: 7/7 popup message handler security tests passed.
- **`npm run test:discovery`**: Dynamic backend discovery & URL immutability passed.
- **`npm run test:evidence`**: Intake lifecycle & hash preservation passed.
- **`npm run test:gemini`**: Model discovery & fallback resilience passed.

### Frontend Production Build
```
✓ 1972 modules transformed.
dist/index.html                     0.87 kB │ gzip:   0.47 kB
dist/assets/index-CUmIol9e.css     90.07 kB │ gzip:  13.88 kB
dist/assets/StrategyPage-vccKjRsv.js 14.02 kB │ gzip:  4.05 kB
dist/assets/index-Zd5G7gCl.js     410.87 kB │ gzip: 128.95 kB
✓ built in 2.57s
```

---

## 8. Compliance with Absolute Change Restrictions

1. **Authentication Preservation:**
   - No modifications made to JWT signing/validation, password hashing algorithms, OAuth redirect handling, or session management.
   - All 51 authentication and OAuth backend tests pass without modification.
2. **Database Integrity:**
   - Production SQLite database (`adfir.db` with 48 tables) was completely preserved.
   - All tests executed against isolated in-memory or temporary SQLite test databases.
   - Zero destructive migrations or schema modifications were applied.
3. **Zero Fabrication:**
   - No mock results, fabricated tool outputs, or fake confidence scores were introduced.
   - All tool recommendations and feasibilities are computed directly against the local system's actual binary environment and vault evidence items.

---

## 9. Conclusion & Release Readiness

With the implementation and verification of the `EvidenceDecisionEngine`, 5-tier AI reasoning governance, 16-section forensic report generator, and the updated Strategy UI, ADFIP has successfully transitioned from an experimental script runner into an autonomous, evidence-driven, explainable digital forensics investigation platform ready for field deployment.

