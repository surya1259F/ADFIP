"""ADFIP Canonical Evidence Classification and Compatibility Layer.

Provides authoritative evidence-type normalization, distinguishes scan targets from rule
definitions, and defines a single compatibility standard for forensic agents and tools.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EvidenceRole(str, Enum):
    """Forensic role of an evidence or ingested asset."""
    TARGET_EVIDENCE = "TARGET_EVIDENCE"  # Physical/digital object to be inspected or scanned
    RULE_RESOURCE = "RULE_RESOURCE"      # Rule definition/configuration (must NOT be scanned as target)
    METADATA_ONLY = "METADATA_ONLY"      # Informational reference or metadata artifact


class CanonicalEvidenceClass(str, Enum):
    """Canonical classification of forensic evidence items."""
    # Binary and Executable Samples (Scannable Targets)
    PE_EXECUTABLE = "PE_EXECUTABLE"
    ELF_EXECUTABLE = "ELF_EXECUTABLE"
    MACHO_EXECUTABLE = "MACHO_EXECUTABLE"
    GENERIC_BINARY = "GENERIC_BINARY"
    MALWARE_SAMPLE = "MALWARE_SAMPLE"

    # Rule Definitions / Configs (RULE_RESOURCE - NOT Target Evidence)
    YARA_RULE = "YARA_RULE"

    # Filesystem, Storage, and Memory
    DISK_IMAGE = "DISK_IMAGE"
    MEMORY_DUMP = "MEMORY_DUMP"

    # Event Logs and Databases
    WINDOWS_EVENT_LOG = "WINDOWS_EVENT_LOG"
    GENERIC_LOG = "GENERIC_LOG"
    BROWSER_DATABASE = "BROWSER_DATABASE"

    # Files and Documents
    DOCUMENT = "DOCUMENT"
    ARCHIVE = "ARCHIVE"
    TEXT = "TEXT"
    GENERIC_FILE = "GENERIC_FILE"

    # Unidentified
    UNKNOWN = "UNKNOWN"


# Mapping from raw/alias classifications to canonical class and metadata
_CLASSIFICATION_MAP: Dict[str, Tuple[CanonicalEvidenceClass, EvidenceRole, Dict[str, Any]]] = {
    # Rules - NOT scan targets
    "yara_rule": (
        CanonicalEvidenceClass.YARA_RULE,
        EvidenceRole.RULE_RESOURCE,
        {"category": "detection_rule", "is_rule_resource": True, "description": "YARA Detection Rule Definition"}
    ),
    "yara": (
        CanonicalEvidenceClass.YARA_RULE,
        EvidenceRole.RULE_RESOURCE,
        {"category": "detection_rule", "is_rule_resource": True, "description": "YARA Detection Rule Definition"}
    ),
    "yar": (
        CanonicalEvidenceClass.YARA_RULE,
        EvidenceRole.RULE_RESOURCE,
        {"category": "detection_rule", "is_rule_resource": True, "description": "YARA Detection Rule Definition"}
    ),
    "yara_rule_file": (
        CanonicalEvidenceClass.YARA_RULE,
        EvidenceRole.RULE_RESOURCE,
        {"category": "detection_rule", "is_rule_resource": True, "description": "YARA Rule File Structure"}
    ),

    # Suspicious binary / malware sample aliases -> canonical MALWARE_SAMPLE
    "suspicious_binary": (
        CanonicalEvidenceClass.MALWARE_SAMPLE,
        EvidenceRole.TARGET_EVIDENCE,
        {
            "category": "binary_analysis",
            "is_alias": True,
            "normalized_from": "SUSPICIOUS_BINARY",
            "target_canonical_class": "MALWARE_SAMPLE",
            "description": "Suspicious binary payload requiring malware inspection"
        }
    ),
    "generic_suspicious_binary": (
        CanonicalEvidenceClass.MALWARE_SAMPLE,
        EvidenceRole.TARGET_EVIDENCE,
        {
            "category": "binary_analysis",
            "is_alias": True,
            "normalized_from": "GENERIC_SUSPICIOUS_BINARY",
            "target_canonical_class": "MALWARE_SAMPLE"
        }
    ),
    "malware_sample": (
        CanonicalEvidenceClass.MALWARE_SAMPLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "description": "Malware sample binary"}
    ),
    "malware": (
        CanonicalEvidenceClass.MALWARE_SAMPLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "description": "Malware candidate"}
    ),
    "suspicious_file": (
        CanonicalEvidenceClass.MALWARE_SAMPLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "Suspicious file"}
    ),

    # Executables -> Specific canonical classes
    "pe_executable": (
        CanonicalEvidenceClass.PE_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "description": "Windows Portable Executable (PE32/PE64)"}
    ),
    "executable": (
        CanonicalEvidenceClass.PE_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "Executable Binary"}
    ),
    "exe": (
        CanonicalEvidenceClass.PE_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "Windows Executable"}
    ),
    "dll": (
        CanonicalEvidenceClass.PE_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "Dynamic Link Library"}
    ),
    "elf_executable": (
        CanonicalEvidenceClass.ELF_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "description": "Linux ELF Executable"}
    ),
    "elf": (
        CanonicalEvidenceClass.ELF_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "Linux ELF Binary"}
    ),
    "macho_executable": (
        CanonicalEvidenceClass.MACHO_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "description": "macOS Mach-O Executable"}
    ),
    "macho": (
        CanonicalEvidenceClass.MACHO_EXECUTABLE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "macOS Mach-O Binary"}
    ),

    # Generic Binary
    "generic_binary": (
        CanonicalEvidenceClass.GENERIC_BINARY,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "description": "Generic Binary Stream"}
    ),
    "binary": (
        CanonicalEvidenceClass.GENERIC_BINARY,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "binary_analysis", "is_alias": True, "description": "Binary Data"}
    ),

    # Storage and Memory
    "disk_image": (
        CanonicalEvidenceClass.DISK_IMAGE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "filesystem", "description": "Forensic Disk Image"}
    ),
    "filesystem_image": (
        CanonicalEvidenceClass.DISK_IMAGE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "filesystem", "is_alias": True}
    ),
    "memory_dump": (
        CanonicalEvidenceClass.MEMORY_DUMP,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "memory", "description": "RAM Memory Dump"}
    ),
    "raw_memory": (
        CanonicalEvidenceClass.MEMORY_DUMP,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "memory", "is_alias": True}
    ),
    "minidump": (
        CanonicalEvidenceClass.MEMORY_DUMP,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "memory", "is_alias": True}
    ),

    # Logs
    "windows_event_log": (
        CanonicalEvidenceClass.WINDOWS_EVENT_LOG,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "event_log", "description": "Windows Event Log (.evtx)"}
    ),
    "evtx": (
        CanonicalEvidenceClass.WINDOWS_EVENT_LOG,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "event_log", "is_alias": True}
    ),
    "event_log": (
        CanonicalEvidenceClass.WINDOWS_EVENT_LOG,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "event_log", "is_alias": True}
    ),
    "log": (
        CanonicalEvidenceClass.GENERIC_LOG,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "log", "description": "Structured / Plaintext Log"}
    ),
    "system_log": (
        CanonicalEvidenceClass.GENERIC_LOG,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "log", "is_alias": True}
    ),

    # Browser
    "browser_db": (
        CanonicalEvidenceClass.BROWSER_DATABASE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "browser", "description": "Browser SQLite Database"}
    ),
    "browser_artifact": (
        CanonicalEvidenceClass.BROWSER_DATABASE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "browser", "is_alias": True}
    ),
    "sqlite_database": (
        CanonicalEvidenceClass.BROWSER_DATABASE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "database", "is_alias": True}
    ),

    # Files / Documents / Text
    "document": (
        CanonicalEvidenceClass.DOCUMENT,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "document", "description": "Office or PDF Document"}
    ),
    "archive": (
        CanonicalEvidenceClass.ARCHIVE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "archive", "description": "Compressed Archive"}
    ),
    "text": (
        CanonicalEvidenceClass.TEXT,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "text", "description": "Plaintext File"}
    ),
    "file": (
        CanonicalEvidenceClass.GENERIC_FILE,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "file", "description": "Generic File"}
    ),
    "unknown": (
        CanonicalEvidenceClass.UNKNOWN,
        EvidenceRole.TARGET_EVIDENCE,
        {"category": "unknown", "description": "Unclassified Data"}
    ),
}


def normalize_evidence_type(evidence_type: Optional[str]) -> Tuple[CanonicalEvidenceClass, EvidenceRole, Dict[str, Any]]:
    """
    Normalizes any evidence type string into its canonical class, role, and provenance metadata.
    
    Returns:
        (CanonicalEvidenceClass, EvidenceRole, metadata_dict)
    """
    if not evidence_type or not isinstance(evidence_type, str):
        return (CanonicalEvidenceClass.UNKNOWN, EvidenceRole.TARGET_EVIDENCE, {"original_classification": "UNKNOWN"})

    cleaned = evidence_type.strip().lower()
    cleaned = cleaned.replace(" ", "_").replace("-", "_")

    if cleaned in _CLASSIFICATION_MAP:
        canonical_class, role, meta = _CLASSIFICATION_MAP[cleaned]
        info = dict(meta)
        info["original_classification"] = evidence_type
        return canonical_class, role, info

    # Heuristic substring detection for compound strings
    if "rule" in cleaned:
        return (
            CanonicalEvidenceClass.YARA_RULE,
            EvidenceRole.RULE_RESOURCE,
            {"original_classification": evidence_type, "is_rule_resource": True}
        )
    if "suspicious" in cleaned and ("binary" in cleaned or "payload" in cleaned):
        return (
            CanonicalEvidenceClass.MALWARE_SAMPLE,
            EvidenceRole.TARGET_EVIDENCE,
            {
                "original_classification": evidence_type,
                "is_alias": True,
                "target_canonical_class": "MALWARE_SAMPLE",
                "normalized_from": cleaned
            }
        )
    if "pe" in cleaned or "exe" in cleaned:
        return (
            CanonicalEvidenceClass.PE_EXECUTABLE,
            EvidenceRole.TARGET_EVIDENCE,
            {"original_classification": evidence_type}
        )
    if "elf" in cleaned:
        return (
            CanonicalEvidenceClass.ELF_EXECUTABLE,
            EvidenceRole.TARGET_EVIDENCE,
            {"original_classification": evidence_type}
        )
    if "macho" in cleaned:
        return (
            CanonicalEvidenceClass.MACHO_EXECUTABLE,
            EvidenceRole.TARGET_EVIDENCE,
            {"original_classification": evidence_type}
        )
    if "mem" in cleaned:
        return (
            CanonicalEvidenceClass.MEMORY_DUMP,
            EvidenceRole.TARGET_EVIDENCE,
            {"original_classification": evidence_type}
        )
    if "evtx" in cleaned or "event" in cleaned:
        return (
            CanonicalEvidenceClass.WINDOWS_EVENT_LOG,
            EvidenceRole.TARGET_EVIDENCE,
            {"original_classification": evidence_type}
        )
    if "disk" in cleaned:
        return (
            CanonicalEvidenceClass.DISK_IMAGE,
            EvidenceRole.TARGET_EVIDENCE,
            {"original_classification": evidence_type}
        )

    return (
        CanonicalEvidenceClass.UNKNOWN,
        EvidenceRole.TARGET_EVIDENCE,
        {"original_classification": evidence_type}
    )


def is_rule_resource(evidence_type: Optional[str]) -> bool:
    """
    Returns True if the evidence type is a rule definition/configuration object (e.g. YARA_RULE)
    that should NOT itself be scanned as an evidence target.
    """
    _, role, _ = normalize_evidence_type(evidence_type)
    return role == EvidenceRole.RULE_RESOURCE


def is_scannable_target(evidence_type: Optional[str]) -> bool:
    """Returns True if the evidence type represents a real target object that can be scanned."""
    _, role, _ = normalize_evidence_type(evidence_type)
    return role == EvidenceRole.TARGET_EVIDENCE


def is_compatible_with_malware_analysis(evidence_type: Optional[str]) -> bool:
    """
    Authoritative single compatibility function for Malware Forensics / YARA scanning.

    Rejects RULE_RESOURCE definitions (e.g., YARA_RULE cannot be scanned as evidence).
    Accepts real target binaries, dropped files, memory artifacts, documents, and disk images.
    """
    if not evidence_type or not isinstance(evidence_type, str):
        return False

    canonical_class, role, _ = normalize_evidence_type(evidence_type)

    # RULE_RESOURCE must NEVER be scanned as malware target evidence
    if role == EvidenceRole.RULE_RESOURCE:
        return False

    compatible_classes = {
        CanonicalEvidenceClass.PE_EXECUTABLE,
        CanonicalEvidenceClass.ELF_EXECUTABLE,
        CanonicalEvidenceClass.MACHO_EXECUTABLE,
        CanonicalEvidenceClass.GENERIC_BINARY,
        CanonicalEvidenceClass.MALWARE_SAMPLE,
        CanonicalEvidenceClass.GENERIC_FILE,
        CanonicalEvidenceClass.DOCUMENT,
        CanonicalEvidenceClass.ARCHIVE,
        CanonicalEvidenceClass.TEXT,
        CanonicalEvidenceClass.DISK_IMAGE,
        CanonicalEvidenceClass.MEMORY_DUMP,
        CanonicalEvidenceClass.WINDOWS_EVENT_LOG,
        CanonicalEvidenceClass.GENERIC_LOG,
        CanonicalEvidenceClass.BROWSER_DATABASE,
    }
    return canonical_class in compatible_classes


def calculate_yara_match_confidence(
    match_count: int = 1,
    string_count: int = 1,
    rule_valid: bool = True,
    source_integrity: float = 1.0,
    contradictory_evidence: bool = False,
    independent_corroboration: bool = False,
    has_authoritative_signature: bool = False,
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculates deterministic, reproducible confidence score for a YARA pattern hit.

    Uses the mathematical formulation from backend.app.services.findings:
        Confidence = 0.35 * source_integrity
                   + 0.30 * artifact_confidence
                   + 0.25 * identifier_match_confidence
                   + 0.10 * min(1.0, supporting_source_count / 2)
                   - (0.30 if contradictory_evidence else 0.0)

    Never returns a hardcoded 0.85 without transparent inputs.
    """
    # 1. Source integrity (verified vault hash)
    src_int = max(0.0, min(1.0, source_integrity))

    # 2. Artifact confidence based on rule validity and string matches
    if not rule_valid:
        art_conf = 0.20
    elif string_count >= 5:
        art_conf = 0.95
    elif string_count >= 2:
        art_conf = 0.85
    elif string_count == 1:
        art_conf = 0.70
    else:
        art_conf = 0.50

    # 3. Match identifier confidence (authoritative confirmed feed vs pattern heuristic)
    if has_authoritative_signature:
        ident_conf = 1.0
    elif independent_corroboration:
        ident_conf = 0.90
    elif match_count > 1:
        ident_conf = 0.80
    else:
        ident_conf = 0.70

    # 4. Supporting sources
    supporting_sources = (2 if independent_corroboration else 1) + (1 if has_authoritative_signature else 0)

    # Deterministic formula
    base = (
        0.35 * src_int +
        0.30 * art_conf +
        0.25 * ident_conf +
        0.10 * min(1.0, supporting_sources / 2.0)
    )
    if contradictory_evidence:
        base -= 0.30

    clamped = round(max(0.0, min(1.0, base)), 4)

    inputs = {
        "source_integrity": round(src_int, 4),
        "artifact_confidence": round(art_conf, 4),
        "identifier_match_confidence": round(ident_conf, 4),
        "supporting_source_count": supporting_sources,
        "contradictory_evidence": contradictory_evidence,
        "string_matches_count": string_count,
        "rule_matches_count": match_count,
        "independent_corroboration": independent_corroboration,
        "has_authoritative_signature": has_authoritative_signature,
        "rule_syntax_valid": rule_valid,
    }
    return clamped, inputs


def get_recommended_capabilities_for_evidence(
    evidence_type: Optional[str],
    finding_type: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Provides deterministic capability recommendations based on evidence type and finding context,
    preventing blind defaults to YARA_SCAN.
    """
    canonical_class, _, _ = normalize_evidence_type(evidence_type)

    if canonical_class in (
        CanonicalEvidenceClass.PE_EXECUTABLE,
        CanonicalEvidenceClass.ELF_EXECUTABLE,
        CanonicalEvidenceClass.MACHO_EXECUTABLE,
        CanonicalEvidenceClass.MALWARE_SAMPLE,
    ):
        return [
            {"id": "STATIC_MALWARE_ANALYSIS", "label": "Static Binary & PE Header Inspection", "rationale": "Inspect executable headers, exports/imports, and embedded indicators."},
            {"id": "YARA_SCAN", "label": "YARA Rule Signature Scan", "rationale": "Scan target binary against approved YARA threat patterns."},
            {"id": "STRINGS_ANALYSIS", "label": "Printable Strings & IOC Extraction", "rationale": "Extract ASCII/Unicode strings and search for embedded C2 IPs, paths, and URLs."},
            {"id": "FILE_HASH_ANALYSIS", "label": "Cryptographic Hash & Threat Feed Query", "rationale": "Correlate SHA-256 against known threat database."},
            {"id": "METADATA_EXTRACTION", "label": "Binary Metadata & Section Header Extraction", "rationale": "Extract file metadata, timestamp, and section attributes."},
        ]

    if canonical_class == CanonicalEvidenceClass.MEMORY_DUMP:
        return [
            {"id": "MEMORY_ANALYSIS", "label": "Volatility 3 Process Enumeration (pslist/pstree)", "rationale": "Extract active and terminated kernel process trees."},
            {"id": "NETWORK_CONNECTION_ANALYSIS", "label": "Volatility 3 Active Sockets (netscan)", "rationale": "Correlate processes to external TCP/UDP connections."},
            {"id": "YARA_SCAN", "label": "YARA Memory Signature Scan", "rationale": "Scan raw memory segments for injected payloads."},
        ]

    if canonical_class == CanonicalEvidenceClass.WINDOWS_EVENT_LOG:
        return [
            {"id": "EVENT_LOG_ANALYSIS", "label": "EVTX Structured Security Event Parsing", "rationale": "Parse logon/logoff, process creation (Event ID 4688), and privilege use."},
            {"id": "TIMELINE_ANALYSIS", "label": "Authentication & Lateral Movement Timeline", "rationale": "Reconstruct chronological event sequences."},
        ]

    if canonical_class == CanonicalEvidenceClass.DISK_IMAGE:
        return [
            {"id": "FILESYSTEM_ANALYSIS", "label": "SleuthKit Volume & Filesystem Parsing (fls)", "rationale": "Enumerate directories, active files, and partition tables."},
            {"id": "DELETED_FILE_ANALYSIS", "label": "Unallocated Cluster & Deleted File Carving", "rationale": "Recover deleted forensic artifacts from unallocated sectors."},
            {"id": "TIMELINE_ANALYSIS", "label": "Filesystem MACB Metadata Timeline", "rationale": "Correlate file modification, access, creation, and birth timestamps."},
        ]

    if canonical_class == CanonicalEvidenceClass.BROWSER_DATABASE:
        return [
            {"id": "BROWSER_ARTIFACT_ANALYSIS", "label": "Browser History & Downloads Inspection", "rationale": "Query navigation history, cached URLs, and download records."},
            {"id": "SQLITE_QUERY", "label": "SQLite Database Table Analysis", "rationale": "Extract structured SQLite records and deleted freelist pages."},
        ]

    # Default fallback for generic files
    return [
        {"id": "FILE_METADATA_ANALYSIS", "label": "ExifTool Comprehensive Metadata Extraction", "rationale": "Extract file timestamps, author, and MIME metadata."},
        {"id": "FILE_HASH_ANALYSIS", "label": "Cryptographic Hash Calculation", "rationale": "Compute SHA-256 hash for forensic verification."},
        {"id": "YARA_SCAN", "label": "YARA Pattern & String Search", "rationale": "Scan strings and known indicators in the file."},
    ]


def calculate_deterministic_confidence(
    source_integrity: float = 1.0,
    artifact_confidence: float = 1.0,
    identifier_match_confidence: float = 1.0,
    supporting_source_count: int = 1,
    contradictory_evidence: bool = False,
    temporal_confidence: Optional[float] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculates deterministic, reproducible confidence score in [0.0, 1.0].
    
    Formula:
        Confidence = 0.35 * source_integrity
                   + 0.30 * artifact_confidence
                   + 0.25 * identifier_match_confidence
                   + 0.10 * min(1.0, supporting_source_count / 2)
                   - (0.30 if contradictory_evidence else 0.0)
    """
    base_score = (
        0.35 * max(0.0, min(1.0, source_integrity)) +
        0.30 * max(0.0, min(1.0, artifact_confidence)) +
        0.25 * max(0.0, min(1.0, identifier_match_confidence)) +
        0.10 * min(1.0, max(0.0, supporting_source_count) / 2.0)
    )
    if contradictory_evidence:
        base_score -= 0.30

    clamped = max(0.0, min(1.0, base_score))
    final_score = round(clamped, 4)

    inputs: Dict[str, Any] = {
        "source_integrity": round(source_integrity, 4),
        "artifact_confidence": round(artifact_confidence, 4),
        "identifier_match_confidence": round(identifier_match_confidence, 4),
        "supporting_source_count": supporting_source_count,
        "contradictory_evidence": contradictory_evidence,
    }
    if temporal_confidence is not None:
        inputs["temporal_confidence"] = round(temporal_confidence, 4)

    return final_score, inputs

