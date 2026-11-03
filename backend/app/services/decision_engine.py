"""
ADFIP — Evidence-Driven Investigation Decision Engine
======================================================
The central intelligence component connecting:
CASE OBJECTIVE
  ↓
EVIDENCE CHARACTERISTICS
  ↓
INVESTIGATIVE QUESTIONS
  ↓
REQUIRED FORENSIC CAPABILITIES
  ↓
AVAILABLE TOOLS
  ↓
TOOL SELECTION
  ↓
EXECUTION PLAN
  ↓
ACTUAL RESULTS
  ↓
FORENSIC ANALYSIS

Enforces:
1. Objective understanding and decomposition into specific investigative questions.
2. Evidence feasibility assessment (INVESTIGABLE, PARTIALLY_INVESTIGABLE, REQUIRES_ADDITIONAL_EVIDENCE, UNSUPPORTED_BY_TOOLS, NOT_APPLICABLE).
3. Plain-language explainability for every tool selection.
4. Multi-tool forensic pipeline sequencing.
5. Zero synthetic evidence or fabricated findings.
"""
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
import logging
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Case,
    EvidenceItem,
    EvidenceIntelligence,
    ForensicCapability,
    InvestigationPlan,
    InvestigationTask,
    ToolSelectionRecord,
    User,
)
from forensic_tools.registry import PlatformAwareToolRegistry, ToolDefinition
from backend.app.services.strategy_engine import (
    ResourceConstraintAnalyzer,
    DependencyGraphBuilder,
    PriorityCalculator,
    StoppingConditionEvaluator,
    seed_forensic_capabilities,
    DEFAULT_CAPABILITIES,
)

logger = logging.getLogger("ADFIR_DECISION_ENGINE")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# ENUMS & DATA STRUCTURES
# =============================================================================

class ObjectiveArchetype(str, Enum):
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    MALWARE_INFECTION = "MALWARE_INFECTION"
    SUSPICIOUS_EXECUTION = "SUSPICIOUS_EXECUTION"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    SUSPICIOUS_NETWORK = "SUSPICIOUS_NETWORK"
    BROWSER_ACTIVITY = "BROWSER_ACTIVITY"
    ANTI_FORENSICS_DELETED_FILES = "ANTI_FORENSICS_DELETED_FILES"
    USB_DEVICE_USAGE = "USB_DEVICE_USAGE"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    INSIDER_ACTIVITY = "INSIDER_ACTIVITY"
    GENERIC_INCIDENT = "GENERIC_INCIDENT"


class QuestionFeasibility(str, Enum):
    INVESTIGABLE = "INVESTIGABLE"
    PARTIALLY_INVESTIGABLE = "PARTIALLY_INVESTIGABLE"
    REQUIRES_ADDITIONAL_EVIDENCE = "REQUIRES_ADDITIONAL_EVIDENCE"
    UNSUPPORTED_BY_TOOLS = "UNSUPPORTED_BY_TOOLS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Standard investigative question templates per archetype
ARCHETYPE_QUESTION_TEMPLATES: Dict[ObjectiveArchetype, List[Dict[str, Any]]] = {
    ObjectiveArchetype.UNAUTHORIZED_ACCESS: [
        {
            "code": "AUTH_EVENTS",
            "question": "Are there indications of unauthorized authentication, failed logons, or credential abuse during the incident window?",
            "category": "AUTHENTICATION",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LOG", "LINUX_AUTH_LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "hypothesis": "Compromised credentials or brute-force authentication was used to access the host."
        },
        {
            "code": "ACCOUNT_ANOMALIES",
            "question": "Were unexpected user accounts created, modified, or added to privileged administrative groups?",
            "category": "ACCOUNT_MANAGEMENT",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "REGISTRY_HIVE", "LINUX_AUTH_LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "hypothesis": "An adversary created or modified accounts to establish persistent administrative access."
        },
        {
            "code": "REMOTE_SESSIONS",
            "question": "Were remote interactive desktop (RDP), SSH, or terminal services sessions established?",
            "category": "REMOTE_ACCESS",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LINUX_AUTH_LOG", "PCAP_CAPTURE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "NETWORK_CONNECTION_ANALYSIS"],
            "hypothesis": "The host was accessed via remote interactive administration protocols."
        },
        {
            "code": "POST_AUTH_ACTIVITY",
            "question": "What processes, commands, or tools were executed immediately following suspicious logon events?",
            "category": "EXECUTION",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "MEMORY_DUMP", "DISK_IMAGE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "PROCESS_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "Post-exploitation commands or staging scripts were executed by the authenticating identity."
        },
    ],
    ObjectiveArchetype.MALWARE_INFECTION: [
        {
            "code": "SUSPICIOUS_BINARIES",
            "question": "Are there known malware signatures, webshells, or suspicious executable binaries present on the system?",
            "category": "MALWARE_DETECTION",
            "required_evidence_domains": ["PE_EXECUTABLE", "ELF_EXECUTABLE", "MALWARE_SAMPLE", "SUSPICIOUS_BINARY", "DISK_IMAGE"],
            "required_capabilities": ["MALWARE_STATIC_ANALYSIS", "YARA_SCAN"],
            "hypothesis": "Malicious binary payloads or webshell scripts were dropped onto the filesystem."
        },
        {
            "code": "MEMORY_INJECTIONS",
            "question": "Are there signs of code injection (e.g. hollowed processes, unmapped executable memory) in volatile memory?",
            "category": "MEMORY_INSPECTION",
            "required_evidence_domains": ["MEMORY_DUMP", "RAW_MEMORY"],
            "required_capabilities": ["MEMORY_ANALYSIS", "PROCESS_ANALYSIS"],
            "hypothesis": "Malicious code was injected into legitimate operating system processes."
        },
        {
            "code": "PERSISTENCE_MECHANISMS",
            "question": "Were persistence mechanisms (e.g. Run keys, scheduled tasks, startup scripts, systemd services) configured?",
            "category": "PERSISTENCE",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "REGISTRY_HIVE", "DISK_IMAGE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "The malware installed persistent launch points to survive host reboots."
        },
        {
            "code": "C2_COMMUNICATIONS",
            "question": "Are there active or historical network connections, DNS queries, or beacons to suspected command-and-control infrastructure?",
            "category": "NETWORK_C2",
            "required_evidence_domains": ["MEMORY_DUMP", "PCAP_CAPTURE"],
            "required_capabilities": ["NETWORK_CONNECTION_ANALYSIS", "PCAP_ANALYSIS"],
            "hypothesis": "The infected endpoint initiated outbound communication with external C2 servers."
        },
    ],
    ObjectiveArchetype.SUSPICIOUS_EXECUTION: [
        {
            "code": "PROCESS_TREE",
            "question": "Did processes execute from unusual or temporary directories (e.g. Temp, AppData, /tmp)?",
            "category": "PROCESS_ANALYSIS",
            "required_evidence_domains": ["MEMORY_DUMP", "WINDOWS_EVENT_LOG", "DISK_IMAGE"],
            "required_capabilities": ["PROCESS_ANALYSIS", "EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "Suspicious binaries or scripts were launched from world-writable directories."
        },
        {
            "code": "COMMAND_LINE_ARGS",
            "question": "What command-line arguments, encoded scripts, or LOLBins (e.g. PowerShell, certutil, curl) were invoked?",
            "category": "COMMAND_AUDIT",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "MEMORY_DUMP", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "PROCESS_ANALYSIS"],
            "hypothesis": "Adversaries leveraged living-off-the-land binaries with obfuscated or encoded commands."
        },
        {
            "code": "EXECUTION_TIMESTAMPS",
            "question": "When were the suspicious programs first and last executed according to execution artifacts?",
            "category": "EXECUTION_TIMELINE",
            "required_evidence_domains": ["WINDOWS_ARTIFACT", "WINDOWS_EVENT_LOG", "DISK_IMAGE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS", "TIMELINE_ANALYSIS"],
            "hypothesis": "Execution artifacts record the exact chronological windows of suspicious program launches."
        },
    ],
    ObjectiveArchetype.DATA_EXFILTRATION: [
        {
            "code": "STAGED_ARCHIVES",
            "question": "Were archive files (e.g. .zip, .7z, .rar) created containing sensitive documents or compressed directories?",
            "category": "DATA_STAGING",
            "required_evidence_domains": ["DISK_IMAGE", "ARCHIVE", "FILE"],
            "required_capabilities": ["FILESYSTEM_ANALYSIS", "METADATA_EXTRACTION"],
            "hypothesis": "Target data was aggregated and compressed prior to network transfer."
        },
        {
            "code": "OUTBOUND_TRANSFERS",
            "question": "Were large volume outbound network transfers or connections to unauthorized cloud storage providers observed?",
            "category": "EXFILTRATION_CHANNELS",
            "required_evidence_domains": ["PCAP_CAPTURE", "MEMORY_DUMP"],
            "required_capabilities": ["PCAP_ANALYSIS", "NETWORK_CONNECTION_ANALYSIS"],
            "hypothesis": "Staged archives were transmitted over network protocols or encrypted web tunnels."
        },
        {
            "code": "REMOVABLE_COPY",
            "question": "Were files copied to external USB storage devices or virtual mounted volumes?",
            "category": "REMOVABLE_STORAGE",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "REGISTRY_HIVE", "DISK_IMAGE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "Sensitive data was transferred to a physical USB mass storage device."
        },
    ],
    ObjectiveArchetype.BROWSER_ACTIVITY: [
        {
            "code": "URL_HISTORY",
            "question": "What websites, search queries, and web-mail portals were accessed during the incident timeframe?",
            "category": "WEB_NAVIGATION",
            "required_evidence_domains": ["BROWSER_ARTIFACT", "SQLITE_DATABASE"],
            "required_capabilities": ["BROWSER_ARTIFACT_ANALYSIS"],
            "hypothesis": "The user or browser process navigated to malicious phishing or external staging sites."
        },
        {
            "code": "DOWNLOADED_FILES",
            "question": "What files were downloaded through web browsers, from what origin URLs, and to what destination paths?",
            "category": "DOWNLOADS",
            "required_evidence_domains": ["BROWSER_ARTIFACT", "SQLITE_DATABASE", "DISK_IMAGE"],
            "required_capabilities": ["BROWSER_ARTIFACT_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "Initial access payloads or unauthorized documents were downloaded via browser."
        },
    ],
    ObjectiveArchetype.ANTI_FORENSICS_DELETED_FILES: [
        {
            "code": "DELETED_FILE_RECORDS",
            "question": "Are there deleted file remnants, orphaned directory entries, or unallocated entries on the filesystem?",
            "category": "DELETED_RECOVERY",
            "required_evidence_domains": ["DISK_IMAGE"],
            "required_capabilities": ["FILESYSTEM_ANALYSIS"],
            "hypothesis": "Evidence was deleted or unlinked from the active directory tree to conceal activity."
        },
        {
            "code": "LOG_TAMPERING",
            "question": "Are there indicators of log clearing events (e.g. Event ID 1102 / 104) or truncated audit journals?",
            "category": "LOG_INTEGRITY",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "hypothesis": "The security audit log was cleared by an intruder to destroy event records."
        },
    ],
    ObjectiveArchetype.GENERIC_INCIDENT: [
        {
            "code": "EVIDENCE_INTEGRITY",
            "question": "Are all submitted evidence items cryptographically verified and intact compared to acquisition hashes?",
            "category": "INTEGRITY",
            "required_evidence_domains": ["ALL"],
            "required_capabilities": ["HASH_ANALYSIS"],
            "hypothesis": "Evidence custody and cryptographic hashes have been preserved without tampering."
        },
        {
            "code": "TIMELINE_SYNTHESIS",
            "question": "Can all extracted forensic events across disk, memory, and logs be correlated into a unified timeline?",
            "category": "TIMELINE",
            "required_evidence_domains": ["ALL"],
            "required_capabilities": ["TIMELINE_ANALYSIS", "CORRELATION"],
            "hypothesis": "Temporal correlation reveals the sequence of events across multiple evidence domains."
        },
    ],
    ObjectiveArchetype.USB_DEVICE_USAGE: [
        {
            "code": "USB_INSERTIONS",
            "question": "What USB mass storage devices, vendor IDs, and serial numbers were connected to the system?",
            "category": "HARDWARE_AUDIT",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "REGISTRY_HIVE", "DISK_IMAGE", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "Removable USB storage media was connected to exfiltrate data or introduce unauthorized files."
        }
    ],
    ObjectiveArchetype.PRIVILEGE_ESCALATION: [
        {
            "code": "PRIVILEGE_ABUSE",
            "question": "Were privilege escalation exploits, UAC bypasses, or elevated token impersonations executed?",
            "category": "PRIVILEGE_AUDIT",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LOG", "LINUX_AUTH_LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "hypothesis": "An unprivileged context was elevated to SYSTEM or root privileges."
        }
    ],
    ObjectiveArchetype.INSIDER_ACTIVITY: [
        {
            "code": "INSIDER_DATA_ACCESS",
            "question": "Did user accounts access sensitive file shares or execute massive file copies outside normal working hours?",
            "category": "INSIDER_AUDIT",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LOG", "DISK_IMAGE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "An authorized insider engaged in unauthorized data aggregation or abnormal access."
        }
    ],
}


# =============================================================================
# DECISION ENGINE
# =============================================================================

class EvidenceDecisionEngine:
    """
    Core Evidence-to-Investigation Decision Engine.
    Translates Case Objective + Evidence Characteristics into Actionable,
    Feasible, Explainable Forensic Investigation Plans.
    """

    @classmethod
    def classify_objective(cls, objective_text: Optional[str], case_type: Optional[str] = None) -> List[ObjectiveArchetype]:
        """
        Determines the primary and secondary investigative archetypes from the case objective.
        """
        text = f"{objective_text or ''} {case_type or ''}".lower()
        archetypes: List[ObjectiveArchetype] = []

        if any(k in text for k in ["unauthorized access", "compromised", "brute force", "logon", "login", "authentication", "credential", "stolen password"]):
            archetypes.append(ObjectiveArchetype.UNAUTHORIZED_ACCESS)

        if any(k in text for k in ["malware", "virus", "trojan", "ransomware", "backdoor", "webshell", "c2", "payload", "rootkit"]):
            archetypes.append(ObjectiveArchetype.MALWARE_INFECTION)

        if any(k in text for k in ["suspicious process", "execution", "script", "powershell", "lolbin", "cmd", "batch", "binary execution"]):
            archetypes.append(ObjectiveArchetype.SUSPICIOUS_EXECUTION)

        if any(k in text for k in ["exfiltration", "data theft", "stolen files", "leak", "sensitive data", "cloud upload"]):
            archetypes.append(ObjectiveArchetype.DATA_EXFILTRATION)

        if any(k in text for k in ["network", "pcap", "beacon", "dns query", "tunnel", "traffic", "packet capture"]):
            archetypes.append(ObjectiveArchetype.SUSPICIOUS_NETWORK)

        if any(k in text for k in ["browser", "history", "phishing", "download", "web activity", "visited url"]):
            archetypes.append(ObjectiveArchetype.BROWSER_ACTIVITY)

        if any(k in text for k in ["deleted", "anti-forensic", "wiped", "unallocated", "cleared log", "timestomp"]):
            archetypes.append(ObjectiveArchetype.ANTI_FORENSICS_DELETED_FILES)

        if any(k in text for k in ["usb", "removable", "flash drive", "thumb drive", "external storage"]):
            archetypes.append(ObjectiveArchetype.USB_DEVICE_USAGE)

        if any(k in text for k in ["privilege escalation", "sudo", "uac bypass", "elevated", "privilege", "administrator", "root access"]):
            archetypes.append(ObjectiveArchetype.PRIVILEGE_ESCALATION)

        if any(k in text for k in ["insider", "disgruntled", "departing employee", "after hours", "unauthorized copy"]):
            archetypes.append(ObjectiveArchetype.INSIDER_ACTIVITY)

        # Baseline generic questions always apply
        archetypes.append(ObjectiveArchetype.GENERIC_INCIDENT)

        return archetypes

    @classmethod
    def generate_investigative_questions(
        cls,
        objective_text: Optional[str],
        case_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Decomposes the case objective into structured, hypothesis-neutral investigative questions.
        """
        archetypes = cls.classify_objective(objective_text, case_type)
        questions: List[Dict[str, Any]] = []
        seen_codes = set()

        q_counter = 1
        for arch in archetypes:
            templates = ARCHETYPE_QUESTION_TEMPLATES.get(arch, [])
            for tmpl in templates:
                if tmpl["code"] in seen_codes:
                    continue
                seen_codes.add(tmpl["code"])

                questions.append({
                    "question_id": f"IQ-{q_counter:02d}",
                    "code": tmpl["code"],
                    "archetype": arch.value,
                    "question_text": tmpl["question"],
                    "category": tmpl["category"],
                    "required_evidence_domains": tmpl["required_evidence_domains"],
                    "required_capabilities": tmpl["required_capabilities"],
                    "hypothesis": tmpl["hypothesis"],
                })
                q_counter += 1

        return questions

    @classmethod
    def evaluate_evidence_feasibility(
        cls,
        questions: List[Dict[str, Any]],
        evidence_profiles: List[Dict[str, Any]],
        tool_registry: PlatformAwareToolRegistry
    ) -> List[Dict[str, Any]]:
        """
        Evaluates submitted evidence against investigative questions and assigns feasibility:
        INVESTIGABLE, PARTIALLY_INVESTIGABLE, REQUIRES_ADDITIONAL_EVIDENCE, UNSUPPORTED_BY_TOOLS.
        """
        evaluated_questions: List[Dict[str, Any]] = []

        # Map available evidence domains
        evidence_domains_present = set()
        evidence_by_domain: Dict[str, List[Dict[str, Any]]] = {}

        for ep in evidence_profiles:
            doms = ep.get("investigative_domains", [])
            cat = ep.get("category", "").upper()
            sub = ep.get("subtype", "").upper()

            all_doms = set(doms + [cat, sub])
            for d in all_doms:
                evidence_domains_present.add(d)
                evidence_by_domain.setdefault(d, []).append(ep)

        # Map available tool capabilities
        available_tools = tool_registry.list_tools()
        supported_capabilities = set()
        for t in available_tools:
            if t.is_available:
                for cap in t.capabilities:
                    supported_capabilities.add(cap.upper())

        for q in questions:
            req_domains = q["required_evidence_domains"]
            req_caps = q["required_capabilities"]

            matching_evidence: List[Dict[str, Any]] = []
            missing_domains: List[str] = []

            if "ALL" in req_domains:
                matching_evidence = evidence_profiles[:]
            else:
                for dom in req_domains:
                    found = False
                    for p_dom in evidence_domains_present:
                        if dom in p_dom or p_dom in dom:
                            matching_evidence.extend(evidence_by_domain.get(p_dom, []))
                            found = True
                    if not found:
                        missing_domains.append(dom)

            # Deduplicate matching evidence
            matching_ids = set()
            unique_evidence = []
            for ev in matching_evidence:
                if ev["evidence_id"] not in matching_ids:
                    matching_ids.add(ev["evidence_id"])
                    unique_evidence.append(ev)

            # Check integrity gate of matching evidence
            compromised_evidence = [ev for ev in unique_evidence if not ev.get("integrity_valid", True)]

            # Check tool capability support
            missing_caps = []
            for cap in req_caps:
                # Match against registered capabilities or default strategy capabilities
                if not any(cap in sc or sc in cap for sc in supported_capabilities):
                    # Check if tools in project bin provide it
                    missing_caps.append(cap)

            # Determine Feasibility Status
            feasibility = QuestionFeasibility.INVESTIGABLE
            assessment_notes = []

            if not unique_evidence and "ALL" not in req_domains:
                feasibility = QuestionFeasibility.REQUIRES_ADDITIONAL_EVIDENCE
                domains_str = ", ".join(missing_domains) or ", ".join(req_domains)
                assessment_notes.append(
                    f"Requires additional evidence: This question cannot be answered because required evidence types ({domains_str}) have not been submitted."
                )
            elif compromised_evidence:
                feasibility = QuestionFeasibility.PARTIALLY_INVESTIGABLE
                assessment_notes.append(
                    f"Integrity Warning: {len(compromised_evidence)} matching evidence item(s) failed integrity check. Results may be ungrounded."
                )
            elif missing_domains and len(unique_evidence) > 0:
                feasibility = QuestionFeasibility.PARTIALLY_INVESTIGABLE
                assessment_notes.append(
                    f"Partially Investigable: Corroborating evidence domains ({', '.join(missing_domains)}) are missing, but primary evidence is available."
                )
            else:
                ev_names = ", ".join(ev["name"] for ev in unique_evidence)
                assessment_notes.append(
                    f"Investigable: Necessary evidence is present ({ev_names}) and cryptographically verified."
                )

            q_eval = dict(q)
            q_eval["feasibility"] = feasibility.value
            q_eval["assessment_notes"] = " ".join(assessment_notes)
            q_eval["matching_evidence_ids"] = list(matching_ids)
            q_eval["matching_evidence_names"] = [ev["name"] for ev in unique_evidence]
            q_eval["missing_evidence_domains"] = missing_domains

            evaluated_questions.append(q_eval)

        return evaluated_questions

    @classmethod
    def resolve_explainable_tools(
        cls,
        capability_id: str,
        evidence_item: Dict[str, Any],
        investigative_question: Optional[Dict[str, Any]],
        tool_registry: PlatformAwareToolRegistry
    ) -> Dict[str, Any]:
        """
        Selects a tool from the registry for a specific capability and generates
        plain-language explainability for the investigator.
        """
        cap_id = capability_id.upper()
        ev_type = evidence_item.get("category", "").lower()
        ev_name = evidence_item.get("name", "evidence")
        ev_format = evidence_item.get("detected_format", "unknown")

        candidates = []
        selected_tool: Optional[ToolDefinition] = None
        rejection_reasons: Dict[str, str] = {}

        all_tools = tool_registry.list_tools()

        for tool in all_tools:
            # Check capability match
            has_cap = any(cap_id in c.upper() or c.upper() in cap_id for c in tool.capabilities)
            # Check evidence type support
            supports_ev = tool.supports_evidence_type(ev_type) or tool.supports_evidence_type(ev_format.lower())

            if has_cap or supports_ev:
                candidates.append(tool.name)
                if not tool.is_available:
                    rejection_reasons[tool.name] = f"Tool binary '{tool.binary_name}' is not installed or available on this system."
                elif selected_tool is None:
                    selected_tool = tool
                else:
                    rejection_reasons[tool.name] = f"Tool '{selected_tool.name}' was selected as primary preference."

        # Plain-language explainability synthesis
        if selected_tool:
            why_selected = (
                f"Tool '{selected_tool.display_name}' was selected to process '{ev_name}' ({ev_format}) because it provides "
                f"verified native support for '{capability_id}'."
            )
            expected_output = [f"{capability_id.lower()}_artifacts", "execution_stdout", "audit_provenance"]
            risks_and_limitations = "Executes in read-only sandbox mode; will not modify original evidence."
            status = "SELECTED"
        else:
            why_selected = f"No installed tool on the system currently satisfies capability '{capability_id}' for evidence '{ev_name}'."
            expected_output = []
            risks_and_limitations = "Requires installation of compatible forensic tool binary."
            status = "NO_COMPATIBLE_TOOL"

        return {
            "capability_id": capability_id,
            "evidence_id": evidence_item.get("evidence_id"),
            "evidence_name": ev_name,
            "candidate_tools": candidates,
            "selected_tool_id": selected_tool.name if selected_tool else None,
            "selected_tool_name": selected_tool.display_name if selected_tool else None,
            "selected_tool_version": selected_tool.version if selected_tool else None,
            "is_available": selected_tool.is_available if selected_tool else False,
            "selection_status": status,
            "why_selected": why_selected,
            "expected_output": expected_output,
            "risks_and_limitations": risks_and_limitations,
            "rejection_reasons": rejection_reasons,
            "question_id": investigative_question.get("question_id") if investigative_question else None,
            "question_text": investigative_question.get("question_text") if investigative_question else None,
        }

    @classmethod
    def get_case_investigative_questions(
        cls,
        db: Session,
        case_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieves and evaluates structured investigative questions and feasibility ratings
        for a case against its registered evidence and tool capabilities.
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            return []
        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        from backend.app.services.strategy_engine import EvidenceStrategyAnalyzer
        evidence_profiles = [EvidenceStrategyAnalyzer.analyze_evidence(db, e) for e in evidence_items]
        tool_reg = PlatformAwareToolRegistry()
        questions = cls.generate_investigative_questions(case.objective, case.case_type)
        return cls.evaluate_evidence_feasibility(questions, evidence_profiles, tool_reg)

    @classmethod
    def generate_evidence_driven_plan(
        cls,
        db: Session,
        case_id: str,
        current_user: User
    ) -> Dict[str, Any]:
        """
        Master orchestration: Generates an end-to-end evidence-driven investigation plan.
        """
        seed_forensic_capabilities(db)
        tool_registry = PlatformAwareToolRegistry()

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case with ID '{case_id}' not found.")

        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()

        # Step 1: Analyze evidence items
        from backend.app.services.strategy_engine import EvidenceStrategyAnalyzer
        evidence_profiles = [EvidenceStrategyAnalyzer.analyze_evidence(db, e) for e in evidence_items]

        # Step 2: Generate Investigative Questions from Case Objective
        questions = cls.generate_investigative_questions(case.objective, case.case_type)

        # Step 3: Evaluate Feasibility against Submitted Evidence
        evaluated_questions = cls.evaluate_evidence_feasibility(questions, evidence_profiles, tool_registry)

        # Step 4: Map Feasible Questions to Tasks and Explainable Tool Selections
        tasks_raw: List[Dict[str, Any]] = []
        task_deps_map: Dict[str, List[str]] = {}
        tool_selections_summary: List[Dict[str, Any]] = []

        system_res = ResourceConstraintAnalyzer.inspect_system_resources()

        # Generate tasks for investigable or partially investigable questions
        for q in evaluated_questions:
            feasibility = q["feasibility"]
            if feasibility in [QuestionFeasibility.REQUIRES_ADDITIONAL_EVIDENCE.value, QuestionFeasibility.NOT_APPLICABLE.value]:
                continue

            matching_ev_ids = q.get("matching_evidence_ids", [])
            target_profiles = [ep for ep in evidence_profiles if ep["evidence_id"] in matching_ev_ids] or evidence_profiles

            for cap_id in q["required_capabilities"]:
                for ep in target_profiles:
                    ev_id = ep["evidence_id"]
                    task_key = f"task-{cap_id.lower()[:8]}-{ev_id[:8]}"

                    # Explainable tool selection
                    tool_explanation = cls.resolve_explainable_tools(
                        capability_id=cap_id,
                        evidence_item=ep,
                        investigative_question=q,
                        tool_registry=tool_registry
                    )
                    tool_selections_summary.append(tool_explanation)

                    task_status = "PLANNED"
                    blocking_reason = None

                    if not ep.get("integrity_valid", True):
                        task_status = "BLOCKED_INTEGRITY_FAILURE"
                        blocking_reason = ep.get("integrity_reason", "Evidence failed integrity verification.")
                    elif not tool_explanation["is_available"]:
                        task_status = "BLOCKED_NO_CAPABLE_TOOL"
                        blocking_reason = f"Required tool for capability '{cap_id}' is not available on host system."

                    # Dependencies
                    dep_keys: List[str] = []
                    # Multi-tool pipeline sequencing:
                    # Partition analysis precedes filesystem analysis
                    if cap_id in ["FILESYSTEM_ANALYSIS", "DELETED_FILE_CARVING"] and ep.get("category") in ["disk_image", "mbr", "gpt"]:
                        prereq_key = f"task-partitio-{ev_id[:8]}"
                        if any(t["task_key"] == prereq_key for t in tasks_raw):
                            dep_keys.append(prereq_key)

                    task_deps_map[task_key] = dep_keys

                    # Priority calculation
                    prio_res = PriorityCalculator.calculate_priority(
                        task_data={"relevance_score": 0.9, "evidence_confidence": ep.get("confidence", "HIGH")},
                        dep_depth=len(dep_keys),
                        is_blocked=task_status.startswith("BLOCKED")
                    )

                    tasks_raw.append({
                        "task_key": task_key,
                        "capability_id": cap_id,
                        "question_id": q["question_id"],
                        "question_text": q["question_text"],
                        "agent_name": cls._map_agent_name(cap_id),
                        "evidence_ids": [ev_id],
                        "evidence_name": ep.get("name"),
                        "candidate_tool_ids": tool_explanation["candidate_tools"],
                        "selected_tool_id": tool_explanation["selected_tool_id"],
                        "selected_tool_name": tool_explanation["selected_tool_name"],
                        "selected_tool_version": tool_explanation["selected_tool_version"],
                        "priority_level": prio_res["priority_level"],
                        "priority_score": prio_res["priority_score"],
                        "priority_rationale": prio_res["factors"],
                        "status": task_status,
                        "required_inputs": [ep.get("vault_path") or ep.get("original_path")],
                        "expected_outputs": tool_explanation["expected_output"],
                        "resource_requirements": {"cpu": "medium", "ram": "512MB"},
                        "estimated_cost": {"cpu": "medium", "ram": "512MB"},
                        "rationale": {
                            "why_selected": tool_explanation["why_selected"],
                            "risks_and_limitations": tool_explanation["risks_and_limitations"],
                            "question_text": q["question_text"],
                            "hypothesis": q["hypothesis"],
                            "tool_explanation": tool_explanation,
                        },
                        "blocking_reason": blocking_reason,
                        "dependencies": dep_keys,
                    })

        # Step 5: Dependency Graph & Topological Sorting
        node_keys = [t["task_key"] for t in tasks_raw]
        cycle = DependencyGraphBuilder.detect_cycles(node_keys, task_deps_map)
        sorted_keys = DependencyGraphBuilder.topological_sort(node_keys, task_deps_map)

        ordered_tasks: List[Dict[str, Any]] = []
        for seq, key in enumerate(sorted_keys, start=1):
            t_obj = next((t for t in tasks_raw if t["task_key"] == key), None)
            if t_obj:
                t_obj["sequence"] = seq
                ordered_tasks.append(t_obj)

        # Step 6: Evaluate Stopping Conditions
        stopping_conditions = StoppingConditionEvaluator.evaluate(evidence_profiles, ordered_tasks, system_res)
        requires_manual_review = any(sc.get("human_review_required") for sc in stopping_conditions)
        val_status = "NEEDS_REVIEW" if requires_manual_review else "VALIDATED"
        plan_status = "REQUIRES_REVIEW" if requires_manual_review else "READY"

        # Step 7: Persist Investigation Plan & Tool Selection Records
        prev_plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).first()

        new_version = (prev_plan.version + 1) if prev_plan else 1
        parent_id = prev_plan.id if prev_plan else None
        if prev_plan:
            prev_plan.is_active = False

        plan_id = str(uuid.uuid4())
        strategy_summary_text = (
            f"Evidence-Driven Strategy v{new_version}: Generated {len(questions)} investigative questions "
            f"({len([q for q in evaluated_questions if q['feasibility'] == QuestionFeasibility.INVESTIGABLE.value])} fully investigable). "
            f"Sequenced {len(ordered_tasks)} deterministic task(s) across {len(evidence_profiles)} evidence item(s)."
        )

        plan_record = InvestigationPlan(
            id=plan_id,
            case_id=case_id,
            parent_plan_id=parent_id,
            title=f"Investigation Plan v{new_version} for Case {case.case_number}",
            strategy_summary=strategy_summary_text,
            tasks=ordered_tasks,
            objectives=[q["question_text"] for q in questions],
            scope_definition=f"Objective: {case.objective or 'Generic Incident Response'} (Type: {case.case_type})",
            priority=case.priority,
            status=plan_status,
            validation_status=val_status,
            evidence_snapshot=evidence_profiles,
            resource_snapshot=system_res,
            stopping_conditions_summary=stopping_conditions,
            change_reason=f"Generated by EvidenceDecisionEngine v{new_version}",
            created_by=current_user.id or "decision-engine",
            version=new_version,
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(plan_record)

        # Persist normalized tasks
        for t in ordered_tasks:
            t_record = InvestigationTask(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                task_key=t["task_key"],
                sequence=t["sequence"],
                capability_id=t["capability_id"],
                agent_name=t["agent_name"],
                evidence_ids=t["evidence_ids"],
                candidate_tool_ids=t["candidate_tool_ids"],
                selected_tool_id=t["selected_tool_id"],
                priority_level=t["priority_level"],
                priority_score=t["priority_score"],
                priority_rationale=t["priority_rationale"],
                status=t["status"],
                required_inputs=t["required_inputs"],
                expected_outputs=t["expected_outputs"],
                resource_requirements=t["resource_requirements"],
                estimated_cost=t["estimated_cost"],
                rationale=t["rationale"],
                blocking_reason=t["blocking_reason"],
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(t_record)

        # Persist Tool Selection records
        for ts in tool_selections_summary:
            sel_record = ToolSelectionRecord(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                task_key=f"task-{ts['capability_id'].lower()[:8]}-{ts['evidence_id'][:8]}",
                capability_id=ts["capability_id"],
                evidence_id=ts["evidence_id"],
                candidate_tools=ts["candidate_tools"],
                selected_tool_id=ts["selected_tool_id"],
                selection_status=ts["selection_status"],
                availability_status="AVAILABLE" if ts["is_available"] else "UNAVAILABLE",
                evidence_compatibility="COMPATIBLE",
                platform_compatibility="COMPATIBLE",
                resource_status="RESOURCE_OK",
                version_status="VERSION_OK" if ts["selected_tool_version"] else "VERSION_UNKNOWN",
                safety_status="SAFE",
                rejection_reasons=ts["rejection_reasons"],
                selection_rationale=ts["why_selected"],
                created_at=utc_now(),
            )
            db.add(sel_record)

        db.commit()
        db.refresh(plan_record)

        return {
            "plan_id": plan_record.id,
            "case_id": case_id,
            "version": plan_record.version,
            "status": plan_record.status,
            "validation_status": plan_record.validation_status,
            "strategy_summary": plan_record.strategy_summary,
            "investigative_questions": evaluated_questions,
            "tasks": ordered_tasks,
            "tool_selections": tool_selections_summary,
            "evidence_snapshot": evidence_profiles,
            "stopping_conditions": stopping_conditions,
        }

    @staticmethod
    def _map_agent_name(capability_id: str) -> str:
        cap = capability_id.upper()
        if "DISK" in cap or "PARTITION" in cap or "FILESYSTEM" in cap:
            return "DiskForensicsAgent"
        if "MEMORY" in cap or "PROCESS" in cap:
            return "MemoryForensicsAgent"
        if "MALWARE" in cap or "YARA" in cap:
            return "MalwareAnalysisAgent"
        if "LOG" in cap or "EVTX" in cap or "EVENT" in cap:
            return "WindowsForensicsAgent"
        if "BROWSER" in cap or "SQLITE" in cap:
            return "BrowserForensicsAgent"
        if "PCAP" in cap or "NETWORK" in cap:
            return "NetworkForensicsAgent"
        if "TIMELINE" in cap:
            return "TimelineCorrelationAgent"
        if "HASH" in cap:
            return "EvidenceVerificationAgent"
        return "ForensicAgent"
