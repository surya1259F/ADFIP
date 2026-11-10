# ADFIP — Agent Responsibility Matrix
**Autonomous Digital Forensic Investigation Platform Using Multi-Agent AI**

- **Product:** ADFIP Desktop Workstation
- **Status:** **PENDING REVIEW**

---

## 1. Multi-Agent System Overview

In ADFIP, agents are concrete, traceable software services responsible for executing specific forensic phases. Every agent operates under strict boundaries:
- Deterministic tasks (hashing, tool dispatch, parsing, custody chaining, readiness gating) use **100% deterministic code**.
- AI reasoning (Gemini) is confined strictly to explanation, summarization, and hypothesis suggestion over verified, persisted forensic artifacts.
- No agent has permission to alter original evidence or approve its own findings.

---

## 2. 14-Agent Responsibility Matrix

| # | Agent Role | Implementation Module | Primary Input | Output Schema / Record | Deterministic vs AI | Failure Mode |
|---|---|---|---|---|---|---|
| **1** | **Case Context Agent** | `backend/app/services/case.py` | Case metadata, scope, category, assigned investigators | `Case` database record | Deterministic | Rejects invalid scope; persists error |
| **2** | **Evidence Intelligence Agent** | `backend/app/services/intelligence.py`<br>(`EvidenceIntelligenceEngine`) | Staged evidence file path, intake metadata | `EvidenceIntelligence` profile (MIME, magic, format, tool recommendations) | Deterministic | Labels `UNKNOWN` or `MISMATCH`; flags warnings |
| **3** | **Investigation Strategy Agent** | `backend/app/services/strategy_engine.py` | Investigation objective, intelligence profiles | Structured investigation strategy | Deterministic (Rule-based) | Degrades to exploratory mode; requests evidence |
| **4** | **Investigation Question Agent** | `investigation/planner/planner.py` | Objective category, detected formats | Structured `InvestigationQuestion` list | Deterministic + Optional AI | Returns general examination questions |
| **5** | **Tool Selection Agent** | `forensic_tools/registry.py`<br>(`PlatformAwareToolRegistry`) | Required capabilities, evidence format | Tool ID, verified executable path, argument templates | Deterministic | Rejects unavailable tools with `TOOL_UNAVAILABLE` |
| **6** | **Execution Planning Agent** | `investigation/scheduler/scheduler.py`<br>(`TaskScheduler`) | Selected tools, questions, dependencies | Ordered task dependency graph | Deterministic | Blocks invalid DAGs; identifies missing prereqs |
| **7** | **Governance Agent** | `backend/app/services/governance.py`<br>`report_readiness.py` | Planned tasks, human review decisions | Authorization token / Gate evaluation | Deterministic | Enforces approval; halts unapproved execution |
| **8** | **Forensic Execution Agent** | `investigation/orchestrator/orchestrator.py`<br>(`InvestigationOrchestrator`) | Task payload, vault evidence path | `ToolExecution` record (exit code, PID, stdout, stderr) | Deterministic | Records `FAILED` on non-zero exit; 0 artifacts |
| **9** | **Artifact Analysis Agent** | `backend/app/services/artifact_extraction.py`<br>`artifact_normalization.py` | Raw tool stdout file | Normalized `ExecutionArtifact` records | Deterministic (Regex / JSON / XML) | Records `PARSE_FAILED`; preserves raw output |
| **10** | **Timeline Analysis Agent** | `backend/app/services/timeline.py` | Normalized artifacts with timestamps | Unified chronological `TimelineEvent` records | Deterministic | Flags unnormalized timezones; never invents dates |
| **11** | **Correlation Agent** | `backend/app/services/correlation.py`<br>(`CrossDomainCorrelationService`) | Artifacts, timeline events, entity profiles | `ForensicCorrelationGroup` clusters | Deterministic (Identifier matching) | Returns 0 groups if no rules match |
| **12** | **Finding Validation Agent** | `backend/app/services/findings.py`<br>(`DeterministicFindingsService`) | Correlation groups, extracted artifacts | `Finding` records (`FACT`, `INFERENCE`, `UNVERIFIED`) | Deterministic | Assigns `confidence=None` for single-source facts |
| **13** | **AI Explanation Agent** | `backend/app/services/ai_copilot.py`<br>(`AICopilotService`) | Verified finding IDs, artifact payloads | Grounded natural language interpretation | AI (Gemini 3.8 Flash) | Rejects responses with unverified citations |
| **14** | **Report Generation Agent** | `backend/app/services/final_report.py`<br>(`FinalForensicReportService`) | Case records, findings, decisions, audit | Versioned Final Report (PDF / Canonical JSON) | Deterministic | Blocked by 14 readiness gates if unready |

---

## 3. Specialist Execution Adapters

The platform orchestrates four specialist domain execution adapters located in `agents/`:

### 1. `DiskAgent` (`agents/disk/disk_agent.py`)
- **Supported Formats:** `raw_image`, `disk_image`, `expert_witness`, `filesystem_image`.
- **Primary Tool:** The Sleuth Kit (`fls`, `mmls`, `fsstat`).
- **Enforcement:** Verifies evidence is a filesystem container; rejects log files with `UNSUPPORTED_EVIDENCE_TYPE`.
- **Parsing:** Converts raw `fls` output into file listings, identifying deleted files marked with `*` and extracting inode pointers.

### 2. `MemoryAgent` (`agents/memory/memory_agent.py`)
- **Supported Formats:** `memory_dump`, `crash_dump`, `raw_memory`.
- **Primary Tool:** Volatility 3 (`windows.pslist`, `windows.pstree`, `windows.malfind`).
- **Enforcement:** Validates OS symbol table compatibility before dispatch. If Volatility 3 is not installed, execution is cleanly rejected with `TOOL_UNAVAILABLE`.

### 3. `MalwareAgent` (`agents/malware/malware_agent.py`)
- **Supported Formats:** `pe_executable`, `elf_executable`, `generic_binary`, `file`.
- **Primary Tool:** YARA (Library & CLI adapter).
- **Enforcement:** Enforces strict separation between rule files and target evidence, preventing rule files from being parsed as evidence.

### 4. `LogAgent` (`agents/log/log_agent.py`)
- **Supported Formats:** `windows_event_log` (`.evtx`), `linux_syslog`, `sqlite_database` (`browser_history`).
- **Primary Tool:** Python-EVTX and SQLite3.
- **Enforcement:** Implements bounded streaming windows (`max_records`) to prevent out-of-memory errors on multi-gigabyte log files.

---

## 4. Agent Error Handling & Anti-Hallucination Guarantees

1. **No Synthetic Filler:** If an agent encounters a missing tool, unsupported evidence format, or corrupt data, it transitions its status to `FAILED` or `UNSUPPORTED` with a detailed diagnostic error. It is prohibited from generating simulated artifacts or placeholder findings.
2. **Provenance Traceability:** Every artifact and finding output by any agent contains foreign keys linking back to the `ExecutionId`, `EvidenceId`, and `CaseId`.
3. **Idempotency & Loop Prevention:** Task execution keys are generated using a deterministic SHA-256 hash of `(CaseId + EvidenceId + Tool + Arguments)`. Duplicate execution requests within the same plan run are detected and skipped.
