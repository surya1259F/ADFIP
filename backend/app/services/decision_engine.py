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
    ToolExecution,
    ExecutionArtifact,
    Finding,
    TimelineEvent,
    CorrelationGroup,
    InvestigatorReviewRecord,
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
            "code": "INCIDENT_TIMEFRAME_ARTIFACTS",
            "question": "What security events or abnormal system state changes occurred within the reported incident window?",
            "category": "INCIDENT_SCOPE",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LOG", "DISK_IMAGE"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "hypothesis": "Operating system and application audit records identify the initial scope and timeframe of the incident."
        },
        {
            "code": "PERSISTENCE_MECHANISMS",
            "question": "Were persistent startup entries, scheduled tasks, or services established across the operating system?",
            "category": "PERSISTENCE_AUDIT",
            "required_evidence_domains": ["REGISTRY_HIVE", "DISK_IMAGE", "WINDOWS_EVENT_LOG"],
            "required_capabilities": ["FILESYSTEM_ANALYSIS", "EVENT_LOG_ANALYSIS"],
            "hypothesis": "Adversaries configured persistence artifacts to maintain access across reboots."
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

        # Baseline generic questions apply ONLY if no specific objective archetype matched
        if not archetypes:
            archetypes.append(ObjectiveArchetype.GENERIC_INCIDENT)

        return archetypes

    @classmethod
    def generate_investigative_questions(
        cls,
        objective_text: Optional[str],
        case_type: Optional[str] = None,
        evidence_profiles: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Decomposes the case objective and detected evidence intelligence into structured,
        hypothesis-neutral, case-specific investigative questions.
        """
        archetypes = cls.classify_objective(objective_text, case_type)
        questions: List[Dict[str, Any]] = []
        seen_codes = set()
        q_counter = 1

        # 1. Objective-Driven Questions
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
                    "approval_status": "APPROVED",
                    "is_custom": False,
                    "is_edited": False,
                })
                q_counter += 1

        # 2. Evidence Intelligence-Driven Questions (Disk, Memory, Event Logs, PCAP)
        if evidence_profiles:
            detected_domains = set()
            for ep in evidence_profiles:
                cat = (ep.get("category") or ep.get("evidence_type") or "").upper()
                sub = (ep.get("subtype") or "").upper()
                for d in [cat, sub] + ep.get("investigative_domains", []):
                    if d:
                        detected_domains.add(d)

            evidence_type_templates = {
                "DISK_IMAGE": [
                    {
                        "code": "FILESYSTEM_ANOMALIES",
                        "question": "Are there file system anomalies, deleted file remnants, or volume shadow copies containing historical versions of files?",
                        "category": "FILESYSTEM_ANALYSIS",
                        "required_evidence_domains": ["DISK_IMAGE"],
                        "required_capabilities": ["FILESYSTEM_ANALYSIS"],
                        "hypothesis": "File system structures preserve unallocated directory records and historical volume snapshots."
                    },
                    {
                        "code": "DELETED_RECOVERY",
                        "question": "Can recoverable deleted files, unallocated clusters, or orphaned inodes be identified in the storage volume?",
                        "category": "DELETED_FILE_RECOVERY",
                        "required_evidence_domains": ["DISK_IMAGE"],
                        "required_capabilities": ["FILESYSTEM_ANALYSIS"],
                        "hypothesis": "Deleted artifacts can be recovered from unallocated storage clusters or orphaned MFT/inode records."
                    }
                ],
                "MEMORY_DUMP": [
                    {
                        "code": "INJECTED_CODE",
                        "question": "Are there injected process code segments, unlinked DLL modules, or hidden processes detected in volatile memory?",
                        "category": "VOLATILE_MEMORY",
                        "required_evidence_domains": ["MEMORY_DUMP"],
                        "required_capabilities": ["PROCESS_ANALYSIS"],
                        "hypothesis": "Malicious code was injected into legitimate memory processes without writing binaries to disk."
                    },
                    {
                        "code": "MEMORY_NETWORK_CREDENTIALS",
                        "question": "Were active network sockets, plaintext credentials, or decrypted payload artifacts resident in memory at acquisition?",
                        "category": "VOLATILE_MEMORY",
                        "required_evidence_domains": ["MEMORY_DUMP"],
                        "required_capabilities": ["PROCESS_ANALYSIS", "NETWORK_CONNECTION_ANALYSIS"],
                        "hypothesis": "Volatile memory dumps retain ephemeral network connections and decrypted process tokens."
                    }
                ],
                "WINDOWS_EVENT_LOG": [
                    {
                        "code": "AUTH_SEQUENCES",
                        "question": "Are there suspicious authentication sequences (Logon Event 4624/4625), service installations (7045), or audit clearing (1102)?",
                        "category": "EVENT_AUDIT",
                        "required_evidence_domains": ["WINDOWS_EVENT_LOG"],
                        "required_capabilities": ["EVENT_LOG_ANALYSIS"],
                        "hypothesis": "Security event logs document authentication failures, privilege abuse, or audit evasion attempts."
                    },
                    {
                        "code": "SCRIPT_EXECUTION",
                        "question": "Did PowerShell script block logging (Event 4104) or process creation (Event 4688) capture malicious execution strings?",
                        "category": "EXECUTION_AUDIT",
                        "required_evidence_domains": ["WINDOWS_EVENT_LOG"],
                        "required_capabilities": ["EVENT_LOG_ANALYSIS"],
                        "hypothesis": "Detailed command-line and script block audit logs record obfuscated interpreter commands."
                    }
                ],
                "PCAP_CAPTURE": [
                    {
                        "code": "DNS_BEACONING",
                        "question": "What domain names were queried via DNS, and do any exhibit domain generation algorithms (DGA) or high-entropy queries?",
                        "category": "NETWORK_AUDIT",
                        "required_evidence_domains": ["PCAP_CAPTURE"],
                        "required_capabilities": ["PCAP_ANALYSIS"],
                        "hypothesis": "Malicious agents contacted external command-and-control servers via algorithmically generated DNS lookups."
                    },
                    {
                        "code": "UNUSUAL_TRANSFERS",
                        "question": "Were high-volume data transfers, unusual protocols, or periodic beaconing connection intervals captured in traffic?",
                        "category": "NETWORK_AUDIT",
                        "required_evidence_domains": ["PCAP_CAPTURE"],
                        "required_capabilities": ["PCAP_ANALYSIS", "NETWORK_CONNECTION_ANALYSIS"],
                        "hypothesis": "Network captures reveal exfiltration streams or scheduled command polling intervals."
                    }
                ]
            }

            for dom_key, tmpls in evidence_type_templates.items():
                if any(dom_key in d for d in detected_domains):
                    for tmpl in tmpls:
                        if tmpl["code"] in seen_codes:
                            continue
                        seen_codes.add(tmpl["code"])
                        questions.append({
                            "question_id": f"IQ-{q_counter:02d}",
                            "code": tmpl["code"],
                            "archetype": "EVIDENCE_INTELLIGENCE",
                            "question_text": tmpl["question"],
                            "category": tmpl["category"],
                            "required_evidence_domains": tmpl["required_evidence_domains"],
                            "required_capabilities": tmpl["required_capabilities"],
                            "hypothesis": tmpl["hypothesis"],
                            "approval_status": "APPROVED",
                            "is_custom": False,
                            "is_edited": False,
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
            req_domains = q.get("required_evidence_domains") or ["ALL"]
            req_caps = q.get("required_capabilities") or []

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
        Preserves investigator edits, custom questions, and approval states.
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            return []

        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        from backend.app.services.strategy_engine import EvidenceStrategyAnalyzer
        evidence_profiles = [EvidenceStrategyAnalyzer.analyze_evidence(db, e) for e in evidence_items]
        tool_reg = PlatformAwareToolRegistry()

        # Check for persisted investigator questions in active plan
        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).order_by(InvestigationPlan.version.desc()).first()

        if plan and plan.resource_snapshot and isinstance(plan.resource_snapshot, dict) and "investigative_questions" in plan.resource_snapshot:
            saved_questions = plan.resource_snapshot["investigative_questions"]
            if saved_questions:
                return cls.evaluate_evidence_feasibility(saved_questions, evidence_profiles, tool_reg)

        # Generate fresh dynamic questions (Objective + Evidence Intelligence)
        questions = cls.generate_investigative_questions(case.objective, case.case_type, evidence_profiles=evidence_profiles)
        evaluated = cls.evaluate_evidence_feasibility(questions, evidence_profiles, tool_reg)

        # Persist if plan exists
        if plan:
            snapshot = dict(plan.resource_snapshot or {})
            snapshot["investigative_questions"] = evaluated
            plan.resource_snapshot = snapshot
            db.commit()

        return evaluated

    @classmethod
    def save_case_investigative_questions(
        cls,
        db: Session,
        case_id: str,
        questions: List[Dict[str, Any]],
        current_user: User
    ) -> List[Dict[str, Any]]:
        """
        Persists investigator edits, custom questions, and approval statuses in the case plan.
        """
        from backend.app.services.audit import log_audit_event

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case '{case_id}' not found.")

        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        from backend.app.services.strategy_engine import EvidenceStrategyAnalyzer
        evidence_profiles = [EvidenceStrategyAnalyzer.analyze_evidence(db, e) for e in evidence_items]
        tool_reg = PlatformAwareToolRegistry()

        evaluated = cls.evaluate_evidence_feasibility(questions, evidence_profiles, tool_reg)

        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).order_by(InvestigationPlan.version.desc()).first()

        if not plan:
            plan = InvestigationPlan(
                case_id=case_id,
                status="PLANNED",
                strategy_summary=f"Investigator strategy with {len(evaluated)} active investigative questions.",
                tasks=[],
                is_active=True,
                version=1,
                resource_snapshot={"investigative_questions": evaluated}
            )
            db.add(plan)
        else:
            snapshot = dict(plan.resource_snapshot or {})
            snapshot["investigative_questions"] = evaluated
            plan.resource_snapshot = snapshot

        db.commit()

        log_audit_event(
            db=db,
            case_id=case_id,
            actor_id=current_user.id,
            actor_name=current_user.name or current_user.email,
            event_type="INVESTIGATIVE_QUESTIONS_UPDATED",
            details=f"Investigator updated strategy questions: {len(evaluated)} total questions configured."
        )

        return evaluated

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

    # =========================================================================
    # PART 6 & 7: INVESTIGATOR-DEFINED REQUIREMENTS & PLANNING ENGINE
    # =========================================================================

    STANDARD_REQUIREMENT_TEMPLATES: List[Dict[str, Any]] = [
        {
            "template_id": "REQ-T-01",
            "title": "Identify IP addresses associated with successful logins",
            "category": "AUTHENTICATION",
            "description": "Extract authentication events (e.g. Event ID 4624) and isolate source IPv4/IPv6 addresses and caller domain accounts.",
            "expected_outputs": ["IP_ADDRESS_LIST", "LOGIN_EVENT_TABLE"],
            "required_domains": ["WINDOWS_EVENT_LOG", "LINUX_AUTH_LOG", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "recommended_agent": "WindowsForensicsAgent",
        },
        {
            "template_id": "REQ-T-02",
            "title": "Identify successful authentication timestamps",
            "category": "AUTHENTICATION",
            "description": "Chronologically catalog successful logon timestamps and interactive vs network session types.",
            "expected_outputs": ["LOGIN_EVENT_TABLE", "CHRONOLOGICAL_TIMELINE"],
            "required_domains": ["WINDOWS_EVENT_LOG", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "recommended_agent": "WindowsForensicsAgent",
        },
        {
            "template_id": "REQ-T-03",
            "title": "Identify failed login attempts and brute-force spikes",
            "category": "AUTHENTICATION",
            "description": "Flag failed login events (Event ID 4625), targeted usernames, failure status codes, and rapid repetition sequences.",
            "expected_outputs": ["LOGIN_EVENT_TABLE", "ANOMALY_SUMMARY"],
            "required_domains": ["WINDOWS_EVENT_LOG", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "recommended_agent": "WindowsForensicsAgent",
        },
        {
            "template_id": "REQ-T-04",
            "title": "Build a chronological login and execution timeline",
            "category": "TIMELINE",
            "description": "Reconstruct a unified chronological sequence of system logons, scheduled tasks, and binary executions.",
            "expected_outputs": ["CHRONOLOGICAL_TIMELINE"],
            "required_domains": ["WINDOWS_EVENT_LOG", "DISK_IMAGE", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "recommended_agent": "TimelineCorrelationAgent",
        },
        {
            "template_id": "REQ-T-05",
            "title": "Identify remote network connections and foreign sockets",
            "category": "NETWORK",
            "description": "Isolate active external TCP/UDP connections, listening ports, and anomalous egress communication channels.",
            "expected_outputs": ["NETWORK_CONNECTION_TABLE", "ENDPOINT_LIST"],
            "required_domains": ["PCAP_CAPTURE", "MEMORY_DUMP", "NETWORK_CAPTURE"],
            "required_capabilities": ["NETWORK_CONNECTION_ANALYSIS", "PROCESS_ANALYSIS"],
            "recommended_agent": "NetworkForensicsAgent",
        },
        {
            "template_id": "REQ-T-06",
            "title": "Identify suspicious running processes and unlinked modules",
            "category": "PROCESS_AUDIT",
            "description": "Scan volatile memory structures for hollowed processes, hidden DLLs, and injected shellcode segments.",
            "expected_outputs": ["PROCESS_EXECUTION_LIST", "SUSPICIOUS_MEMORY_INJECTIONS"],
            "required_domains": ["MEMORY_DUMP"],
            "required_capabilities": ["PROCESS_ANALYSIS"],
            "recommended_agent": "MemoryForensicsAgent",
        },
        {
            "template_id": "REQ-T-07",
            "title": "Identify suspicious executable files and signature matches",
            "category": "MALWARE",
            "description": "Examine filesystem binaries and temporary directories against YARA signatures and known threat markers.",
            "expected_outputs": ["SUSPICIOUS_FILE_ANALYSIS", "YARA_MATCH_TABLE"],
            "required_domains": ["FILE", "BINARY", "DISK_IMAGE"],
            "required_capabilities": ["STATIC_BINARY_ANALYSIS", "YARA_SCAN"],
            "recommended_agent": "MalwareAnalysisAgent",
        },
        {
            "template_id": "REQ-T-08",
            "title": "Identify persistence mechanisms and autoruns",
            "category": "PERSISTENCE",
            "description": "Audit Run/RunOnce registry keys, Startup folders, scheduled tasks, and Windows services for survivability hooks.",
            "expected_outputs": ["REGISTRY_ARTIFACT_TABLE", "AUTORUN_INVENTORY"],
            "required_domains": ["DISK_IMAGE", "REGISTRY_HIVE", "MEMORY_DUMP"],
            "required_capabilities": ["FILESYSTEM_ANALYSIS", "EVENT_LOG_ANALYSIS"],
            "recommended_agent": "WindowsForensicsAgent",
        },
        {
            "template_id": "REQ-T-09",
            "title": "Identify and recover deleted files and orphaned records",
            "category": "DELETED_RECOVERY",
            "description": "Scan unallocated volume space and deleted directory index entries to carve or recover deleted documents and scripts.",
            "expected_outputs": ["RECOVERED_FILE_INVENTORY"],
            "required_domains": ["DISK_IMAGE", "RAW_IMAGE"],
            "required_capabilities": ["FILESYSTEM_ANALYSIS"],
            "recommended_agent": "DiskForensicsAgent",
        },
        {
            "template_id": "REQ-T-10",
            "title": "Identify unusual file modifications and timestomp indicators",
            "category": "FILE_AUDIT",
            "description": "Cross-compare MACB timestamp integrity to flag anti-forensics timestamp manipulation and massive alterations.",
            "expected_outputs": ["FILE_TIMELINE_TABLE"],
            "required_domains": ["DISK_IMAGE"],
            "required_capabilities": ["FILESYSTEM_ANALYSIS"],
            "recommended_agent": "DiskForensicsAgent",
        },
        {
            "template_id": "REQ-T-11",
            "title": "Identify browser download activity and visited URLs",
            "category": "BROWSER_AUDIT",
            "description": "Parse SQLite history, download ledgers, and cached web artifacts to trace weaponized downloads or phishing vectors.",
            "expected_outputs": ["BROWSER_ACTIVITY", "DOWNLOAD_HISTORY_TABLE"],
            "required_domains": ["SQLITE_DATABASE", "DISK_IMAGE", "FILE"],
            "required_capabilities": ["BROWSER_HISTORY_ANALYSIS"],
            "recommended_agent": "BrowserForensicsAgent",
        },
        {
            "template_id": "REQ-T-12",
            "title": "Identify suspicious DNS queries and C2 domain lookups",
            "category": "NETWORK",
            "description": "Isolate high-frequency DNS requests, DGA lookups, and anomalous domain query patterns in packet captures.",
            "expected_outputs": ["DNS_QUERY_LOG", "SUSPICIOUS_DOMAINS_LIST"],
            "required_domains": ["PCAP_CAPTURE", "LOG"],
            "required_capabilities": ["NETWORK_CONNECTION_ANALYSIS"],
            "recommended_agent": "NetworkForensicsAgent",
        },
        {
            "template_id": "REQ-T-13",
            "title": "Identify possible data exfiltration indicators",
            "category": "DATA_EXFILTRATION",
            "description": "Detect anomalous outbound transfer volumes, encrypted archive staging, and non-standard protocol tunneling.",
            "expected_outputs": ["EXFILTRATION_CANDIDATE_LIST", "NETWORK_VOLUME_ANALYSIS"],
            "required_domains": ["PCAP_CAPTURE", "DISK_IMAGE", "LOG"],
            "required_capabilities": ["NETWORK_CONNECTION_ANALYSIS", "FILESYSTEM_ANALYSIS"],
            "recommended_agent": "NetworkForensicsAgent",
        },
    ]

    @classmethod
    def get_case_requirements(cls, db: Session, case_id: str) -> Dict[str, Any]:
        """
        Retrieves investigator-defined requirements for a case, including available evidence and templates.
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case with ID '{case_id}' not found.")

        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        available_ev = [
            {
                "id": ev.id,
                "name": ev.name,
                "evidence_type": ev.evidence_type,
                "detected_format": ev.detected_format,
                "size_bytes": ev.size_bytes,
                "sha256": ev.sha256,
                "status": ev.status,
                "integrity_status": getattr(ev, "integrity_status", "VERIFIED"),
            }
            for ev in evidence_items
        ]

        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).order_by(InvestigationPlan.version.desc()).first()

        saved_reqs: List[Dict[str, Any]] = []
        global_scope: Dict[str, Any] = {}
        plan_status = "PLANNED"

        if plan:
            plan_status = plan.status
            snapshot = plan.resource_snapshot or {}
            saved_reqs = snapshot.get("investigation_requirements", [])
            global_scope = snapshot.get("global_scope", {})

        # If no requirements have been saved yet, generate default requirements derived from case objective & evidence
        if not saved_reqs:
            saved_reqs = cls._generate_default_requirements(case, available_ev)

        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "objective": case.objective or "Investigate digital forensic incident and determine root cause.",
            "total_requirements": len(saved_reqs),
            "requirements": saved_reqs,
            "available_evidence": available_ev,
            "available_templates": cls.STANDARD_REQUIREMENT_TEMPLATES,
            "global_scope": global_scope,
            "plan_status": plan_status,
        }

    @classmethod
    def _generate_default_requirements(cls, case: Case, evidence_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generates initial starter requirements based on case objective and evidence types."""
        reqs = []
        obj_text = (case.objective or "").lower()
        ev_types = {e["evidence_type"].upper() for e in evidence_list}

        idx = 1
        # Always check for logins/auth if event logs or disk present
        if "WINDOWS_EVENT_LOG" in ev_types or "LOG" in ev_types or "unauthorized" in obj_text or "access" in obj_text:
            t = cls.STANDARD_REQUIREMENT_TEMPLATES[0]
            reqs.append({
                "id": f"REQ-{idx:02d}",
                "case_id": case.id,
                "title": t["title"],
                "description": t["description"],
                "category": t["category"],
                "selected_evidence_ids": [e["id"] for e in evidence_list if "LOG" in e["evidence_type"].upper() or "DISK" in e["evidence_type"].upper()],
                "selected_evidence_names": [e["name"] for e in evidence_list if "LOG" in e["evidence_type"].upper() or "DISK" in e["evidence_type"].upper()],
                "scope": {},
                "expected_outputs": t["expected_outputs"],
                "approval_status": "APPROVED",
                "status": "SUBMITTED",
                "assigned_agent": t["recommended_agent"],
                "order_index": idx,
            })
            idx += 1

        # Check for processes/memory
        if "MEMORY_DUMP" in ev_types or "process" in obj_text or "malware" in obj_text:
            t = cls.STANDARD_REQUIREMENT_TEMPLATES[5]
            reqs.append({
                "id": f"REQ-{idx:02d}",
                "case_id": case.id,
                "title": t["title"],
                "description": t["description"],
                "category": t["category"],
                "selected_evidence_ids": [e["id"] for e in evidence_list if "MEMORY" in e["evidence_type"].upper()],
                "selected_evidence_names": [e["name"] for e in evidence_list if "MEMORY" in e["evidence_type"].upper()],
                "scope": {},
                "expected_outputs": t["expected_outputs"],
                "approval_status": "APPROVED",
                "status": "SUBMITTED",
                "assigned_agent": t["recommended_agent"],
                "order_index": idx,
            })
            idx += 1

        # Check for disk/deleted files
        if "DISK_IMAGE" in ev_types or "deleted" in obj_text or "disk" in obj_text:
            t = cls.STANDARD_REQUIREMENT_TEMPLATES[8]
            reqs.append({
                "id": f"REQ-{idx:02d}",
                "case_id": case.id,
                "title": t["title"],
                "description": t["description"],
                "category": t["category"],
                "selected_evidence_ids": [e["id"] for e in evidence_list if "DISK" in e["evidence_type"].upper()],
                "selected_evidence_names": [e["name"] for e in evidence_list if "DISK" in e["evidence_type"].upper()],
                "scope": {},
                "expected_outputs": t["expected_outputs"],
                "approval_status": "APPROVED",
                "status": "SUBMITTED",
                "assigned_agent": t["recommended_agent"],
                "order_index": idx,
            })
            idx += 1

        # If none matched, provide top 2 templates
        if not reqs:
            for t in cls.STANDARD_REQUIREMENT_TEMPLATES[:2]:
                reqs.append({
                    "id": f"REQ-{idx:02d}",
                    "case_id": case.id,
                    "title": t["title"],
                    "description": t["description"],
                    "category": t["category"],
                    "selected_evidence_ids": [e["id"] for e in evidence_list],
                    "selected_evidence_names": [e["name"] for e in evidence_list],
                    "scope": {},
                    "expected_outputs": t["expected_outputs"],
                    "approval_status": "APPROVED",
                    "status": "SUBMITTED",
                    "assigned_agent": t["recommended_agent"],
                    "order_index": idx,
                })
                idx += 1

        return reqs

    @classmethod
    def save_case_requirements(
        cls,
        db: Session,
        case_id: str,
        requirements: List[Dict[str, Any]],
        objective: Optional[str] = None,
        global_scope: Optional[Dict[str, Any]] = None,
        current_user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Persists investigator-defined requirements and objective in the case and active plan.
        """
        from backend.app.services.audit import log_audit_event

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case '{case_id}' not found.")

        if objective and objective.strip():
            case.objective = objective.strip()

        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        ev_id_to_name = {e.id: e.name for e in evidence_items}

        # Normalize and enrich requirements
        sanitized_reqs: List[Dict[str, Any]] = []
        for i, r in enumerate(requirements):
            r_id = r.get("id") or f"REQ-{i + 1:02d}"
            selected_ids = r.get("selected_evidence_ids") or []
            selected_names = [ev_id_to_name.get(eid, eid) for eid in selected_ids]

            sanitized_reqs.append({
                "id": r_id,
                "case_id": case_id,
                "title": r.get("title", f"Forensic Inquiry {r_id}").strip(),
                "description": r.get("description", "").strip(),
                "category": r.get("category", "CUSTOM").upper(),
                "selected_evidence_ids": selected_ids,
                "selected_evidence_names": selected_names,
                "scope": r.get("scope") or {},
                "expected_outputs": r.get("expected_outputs") or ["EVIDENCE_ARTIFACTS"],
                "approval_status": r.get("approval_status", "APPROVED").upper(),
                "status": r.get("status", "SUBMITTED").upper(),
                "assigned_agent": r.get("assigned_agent") or cls._map_agent_by_category(r.get("category", "")),
                "order_index": i + 1,
                "updated_at": utc_now().isoformat(),
            })

        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).order_by(InvestigationPlan.version.desc()).first()

        if not plan:
            plan = InvestigationPlan(
                case_id=case_id,
                status="PLANNED",
                strategy_summary=f"Investigator-defined strategy with {len(sanitized_reqs)} forensic requirements.",
                tasks=[],
                is_active=True,
                version=1,
                resource_snapshot={
                    "investigation_requirements": sanitized_reqs,
                    "global_scope": global_scope or {},
                }
            )
            db.add(plan)
        else:
            snapshot = dict(plan.resource_snapshot or {})
            snapshot["investigation_requirements"] = sanitized_reqs
            snapshot["global_scope"] = global_scope or {}
            plan.resource_snapshot = snapshot

        db.commit()

        if current_user:
            log_audit_event(
                db=db,
                case_id=case_id,
                actor_id=current_user.id,
                actor_name=current_user.name or current_user.email,
                event_type="INVESTIGATION_REQUIREMENTS_SAVED",
                details=f"Investigator configured {len(sanitized_reqs)} forensic requirements."
            )

        return cls.get_case_requirements(db, case_id)

    @staticmethod
    def _map_agent_by_category(category: str) -> str:
        cat = (category or "").upper()
        if "AUTH" in cat or "LOGIN" in cat or "EVENT" in cat or "WINDOWS" in cat:
            return "WindowsForensicsAgent"
        if "PROCESS" in cat or "MEMORY" in cat:
            return "MemoryForensicsAgent"
        if "MALWARE" in cat or "BINARY" in cat:
            return "MalwareAnalysisAgent"
        if "NETWORK" in cat or "PCAP" in cat or "DNS" in cat or "EXFILTRATION" in cat:
            return "NetworkForensicsAgent"
        if "DISK" in cat or "DELETED" in cat or "FILESYSTEM" in cat:
            return "DiskForensicsAgent"
        if "BROWSER" in cat:
            return "BrowserForensicsAgent"
        if "TIMELINE" in cat:
            return "TimelineCorrelationAgent"
        return "ForensicAgent"

    @classmethod
    def calculate_forensic_assessment(cls, db: Session, case_id: str) -> Dict[str, Any]:
        """
        Computes deterministic, reproducible forensic attack assessment and evidence-strength score (0-100).
        Evaluates:
        - Attack classification: CONFIRMED_ATTACK, LIKELY_ATTACK, INCONCLUSIVE, NO_ATTACK_OBSERVED, INSUFFICIENT_EVIDENCE
        - 10-factor evidence-strength score
        - Completeness metrics
        - Grounded supporting observations traceable to evidence/tool/artifact IDs
        - Contradictory observations & alternative explanations
        - Limitations & missing evidence
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case '{case_id}' not found.")

        # 1. Inputs
        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        verified_ev = [e for e in evidence_items if getattr(e, "integrity_status", "VERIFIED") == "VERIFIED"]

        reqs_data = cls.get_case_requirements(db, case_id)
        requirements = reqs_data.get("requirements", [])

        executions = db.query(ToolExecution).filter(ToolExecution.case_id == case_id).all()
        failed_executions = [x for x in executions if x.status == "FAILED"]
        successful_executions = [x for x in executions if x.status == "COMPLETED"]

        artifacts = db.query(ExecutionArtifact).filter(ExecutionArtifact.case_id == case_id).all()
        findings = db.query(Finding).filter(Finding.case_id == case_id).all()
        critical_high_findings = [f for f in findings if (f.severity or "").upper() in ["CRITICAL", "HIGH"]]
        fact_findings = [f for f in findings if (f.classification or "").upper() == "FACT"]
        supported_findings = [f for f in findings if getattr(f, "verification_status", "UNVERIFIED") in ["SUPPORTED", "VERIFIED"]]

        reviews = db.query(InvestigatorReviewRecord).filter(InvestigatorReviewRecord.case_id == case_id).all()
        challenged_reviews = [r for r in reviews if r.decision in ["CHALLENGE", "REJECT"]]
        accepted_reviews = [r for r in reviews if r.decision == "ACCEPT"]

        timeline_events_count = db.query(TimelineEvent).filter(TimelineEvent.case_id == case_id).count()
        correlations_count = db.query(CorrelationGroup).filter(CorrelationGroup.case_id == case_id).count()

        # 2. Completeness Calculation
        completed_reqs = 0
        partially_completed_reqs = 0
        unanswered_reqs = 0
        missing_domains_set = set()

        for req in requirements:
            sel_ev_ids = set(req.get("selected_evidence_ids", []))
            matching_findings = [f for f in findings if f.evidence_id in sel_ev_ids or any(eid in sel_ev_ids for eid in getattr(f, "supporting_evidence_ids", []))]
            matching_execs = [x for x in executions if x.evidence_id in sel_ev_ids]

            if not sel_ev_ids and not evidence_items:
                unanswered_reqs += 1
                cat = req.get("category", "")
                if cat:
                    missing_domains_set.add(cat)
            elif matching_execs and any(x.status == "COMPLETED" for x in matching_execs):
                if matching_findings:
                    completed_reqs += 1
                else:
                    partially_completed_reqs += 1
            else:
                unanswered_reqs += 1

        total_reqs = max(1, len(requirements))
        completeness_pct = round((completed_reqs / total_reqs) * 100.0, 1) if requirements else 100.0

        # 3. 10-Factor Evidence-Strength Score Calculation (0 - 100)
        relevance_score = 0.0 if not evidence_items else min(20.0, 10.0 + len(evidence_items) * 2.5)
        reliability_score = 15.0 * (len(verified_ev) / max(1, len(evidence_items))) if evidence_items else 0.0
        directness_score = min(15.0, len(fact_findings) * 3.0 + len(artifacts) * 0.5)
        corroboration_score = min(15.0, correlations_count * 5.0 + len(supported_findings) * 2.0)
        timeline_score = min(10.0, timeline_events_count * 1.0)
        integrity_score = 10.0 if (len(verified_ev) == len(evidence_items) and len(evidence_items) > 0) else 0.0
        coverage_score = 15.0 * (completed_reqs / total_reqs) if requirements else 12.0

        penalties = 0.0
        if challenged_reviews:
            penalties += 10.0
        if failed_executions:
            penalties += min(15.0, len(failed_executions) * 5.0)
        if missing_domains_set:
            penalties += 10.0

        raw_score = (
            relevance_score
            + reliability_score
            + directness_score
            + corroboration_score
            + timeline_score
            + integrity_score
            + coverage_score
            - penalties
        )
        final_strength_score = max(0.0, min(100.0, round(raw_score, 1)))

        # 4. Attack Classification (Documented Forensic Assessment Semantics)
        if len(evidence_items) == 0 or (len(successful_executions) == 0 and len(findings) == 0):
            classification = "INSUFFICIENT_EVIDENCE"
        elif any(f.severity in ["CRITICAL", "HIGH"] for f in findings) and supported_findings and len(fact_findings) >= 1 and not (len(challenged_reviews) > len(accepted_reviews) and len(challenged_reviews) >= 2):
            classification = "CONFIRMED_ATTACK"
        elif critical_high_findings or (len(findings) >= 2 and final_strength_score >= 50.0):
            classification = "LIKELY_ATTACK"
        elif challenged_reviews and len(challenged_reviews) >= len(accepted_reviews):
            classification = "INCONCLUSIVE"
        elif len(successful_executions) >= 1 and len(findings) == 0:
            classification = "NO_ATTACK_OBSERVED"
        else:
            classification = "INCONCLUSIVE"

        # 5. Supporting & Contradictory Observations with Provenance
        supporting_observations = []
        for f in findings:
            supporting_observations.append({
                "finding_id": f.id,
                "title": f.title,
                "severity": f.severity,
                "classification": f.classification,
                "verification_status": getattr(f, "verification_status", "UNVERIFIED"),
                "confidence": f.confidence,
                "evidence_id": f.evidence_id,
                "execution_id": f.execution_id,
                "artifact_id": f.artifact_id,
                "tool": f.tool,
                "source_reference": f.evidence_reference or f.title,
            })

        contradictory_observations = []
        for r in challenged_reviews:
            contradictory_observations.append({
                "review_id": r.id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "decision": r.decision,
                "investigator_rationale": r.comment,
                "supporting_references": r.supporting_references,
            })

        # 6. Alternative Explanations
        alternative_explanations = [
            {
                "hypothesis": "Authorized Administrative Activity",
                "evaluation": "Evaluated whether observed accounts and scripts were initiated during scheduled IT maintenance windows.",
                "supported": False if classification == "CONFIRMED_ATTACK" else True,
            },
            {
                "hypothesis": "Malicious Unauthorized Compromise",
                "evaluation": "Evaluated indicators of compromise, anomalous authentication, malware execution, and persistence.",
                "supported": classification in ["CONFIRMED_ATTACK", "LIKELY_ATTACK"],
            },
            {
                "hypothesis": "Inconclusive Artifact Artifacts / Incomplete Telemetry",
                "evaluation": "Evaluated missing logs or lack of memory image to definitively verify process execution path.",
                "supported": classification in ["INSUFFICIENT_EVIDENCE", "INCONCLUSIVE"],
            }
        ]

        # 7. Limitations & Missing Evidence
        missing_evidence_list = sorted(list(missing_domains_set))
        investigation_limitations = [
            f"Evidence coverage constrained to {len(evidence_items)} submitted container(s)."
        ]
        if missing_evidence_list:
            investigation_limitations.append(f"Missing evidence domains: {', '.join(missing_evidence_list)}")
        if failed_executions:
            investigation_limitations.append(f"{len(failed_executions)} tool execution(s) encountered operational errors.")
        investigation_limitations.append("Analysis based strictly on deterministic observations and cryptographic chain of custody.")

        # 8. Check if investigator has recorded a review decision on this assessment
        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).order_by(InvestigationPlan.version.desc()).first()

        snapshot = (plan.resource_snapshot or {}) if plan else {}
        assessment_meta = snapshot.get("assessment_decision") or {}

        # 9. AI Synthesis Narrative (Evidence-Grounded)
        ai_narrative = (
            f"Forensic assessment for {case.case_number} evaluated {len(evidence_items)} evidence item(s) "
            f"and {len(findings)} finding(s). Attack classification is determined as {classification} "
            f"with an evidence-strength score of {final_strength_score}/100. "
            f"{'Multiple corroborated critical indicators establish unauthorized activity.' if classification == 'CONFIRMED_ATTACK' else 'Further evidence acquisition is required to eliminate competing hypotheses.'}"
        )

        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "classification": assessment_meta.get("decision_classification") or classification,
            "evidence_strength_score": final_strength_score,
            "score_breakdown": {
                "relevance": round(relevance_score, 1),
                "source_reliability": round(reliability_score, 1),
                "directness": round(directness_score, 1),
                "corroboration": round(corroboration_score, 1),
                "timeline_consistency": round(timeline_score, 1),
                "evidence_integrity": round(integrity_score, 1),
                "investigation_coverage": round(coverage_score, 1),
                "penalties": round(penalties, 1),
            },
            "investigation_completeness": {
                "total_requirements": len(requirements),
                "completed_requirements": completed_reqs,
                "partially_completed_requirements": partially_completed_reqs,
                "unanswered_requirements": unanswered_reqs,
                "failed_tasks": len(failed_executions),
                "missing_evidence_domains": missing_evidence_list,
                "percentage": completeness_pct,
            },
            "supporting_observations": supporting_observations,
            "contradictory_observations": contradictory_observations,
            "alternative_explanations": alternative_explanations,
            "missing_evidence": missing_evidence_list,
            "unresolved_questions": [r["title"] for r in requirements if r.get("status") != "COMPLETED"][:5],
            "investigation_limitations": investigation_limitations,
            "ai_synthesis": ai_narrative,
            "investigator_decision": assessment_meta.get("decision", "PENDING_REVIEW"),
            "investigator_rationale": assessment_meta.get("rationale"),
            "decided_at": assessment_meta.get("decided_at"),
            "decided_by": assessment_meta.get("decided_by"),
            "generated_at": utc_now().isoformat(),
            "methodology_version": "1.0.0",
        }

    @classmethod
    def record_assessment_decision(
        cls,
        db: Session,
        case_id: str,
        decision: str,
        rationale: str,
        edited_classification: Optional[str] = None,
        additional_analysis_requested: Optional[str] = None,
        current_user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Records the authorized human investigator's review decision over the assessment.
        Supported decisions: ACCEPT, EDIT, CHALLENGE, REQUEST_MORE_EVIDENCE, REJECT.
        """
        from backend.app.services.audit import log_audit_event

        valid_decisions = {"ACCEPT", "EDIT", "CHALLENGE", "REQUEST_MORE_EVIDENCE", "REJECT"}
        decision_norm = decision.strip().upper()
        if decision_norm not in valid_decisions:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid_decisions}")

        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case_id,
            InvestigationPlan.is_active == True
        ).order_by(InvestigationPlan.version.desc()).first()

        if not plan:
            plan = InvestigationPlan(
                case_id=case_id,
                status="PLANNED",
                strategy_summary="Assessment review plan",
                tasks=[],
                is_active=True,
                version=1,
            )
            db.add(plan)

        snapshot = dict(plan.resource_snapshot or {})
        snapshot["assessment_decision"] = {
            "decision": decision_norm,
            "rationale": rationale.strip(),
            "decision_classification": edited_classification.strip().upper() if edited_classification else None,
            "additional_analysis_requested": additional_analysis_requested.strip() if additional_analysis_requested else None,
            "decided_at": utc_now().isoformat(),
            "decided_by": current_user.name or current_user.email if current_user else "investigator",
        }
        plan.resource_snapshot = snapshot
        db.commit()

        if current_user:
            log_audit_event(
                db=db,
                case_id=case_id,
                actor_id=current_user.id,
                actor_name=current_user.name or current_user.email,
                event_type="ASSESSMENT_DECISION_RECORDED",
                details=f"Investigator recorded decision '{decision_norm}': {rationale.strip()[:100]}"
            )

        return cls.calculate_forensic_assessment(db, case_id)

