import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("ADFIR_AUDIT")
logger.setLevel(logging.INFO)

# File handler for security audit events
audit_log_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "security_audit.log"
audit_log_path.parent.mkdir(parents=True, exist_ok=True)
handler = logging.FileHandler(str(audit_log_path))
handler.setFormatter(logging.Formatter('[%(asctime)s UTC] [%(levelname)s] %(message)s'))
logger.addHandler(handler)

class SecurityValidator:
    """
    Core security validation routines to guarantee evidence safety and platform hardening.
    """

    @staticmethod
    def validate_and_canonicalize_path(untrusted_path: str) -> Path:
        """
        Validates that a path is safe and points to a real file.
        Rejects path traversal, null bytes, and non-existent paths.
        """
        if not untrusted_path or not isinstance(untrusted_path, str):
            AuditLogger.log_event("INVALID_PATH_REJECTED", {"path": str(untrusted_path), "reason": "Empty or non-string path"})
            raise ValueError("Path must be a non-empty string.")

        # Reject null bytes
        if "\0" in untrusted_path:
            AuditLogger.log_event("INVALID_PATH_REJECTED", {"path": untrusted_path, "reason": "Null byte detected"})
            raise ValueError("Invalid character in path.")

        # Reject path traversal patterns
        if ".." in untrusted_path.split(os.sep) or untrusted_path.startswith(".."):
            AuditLogger.log_event("INVALID_PATH_REJECTED", {"path": untrusted_path, "reason": "Path traversal attempt detected"})
            raise ValueError("Path traversal patterns ('..') are prohibited.")

        # Canonicalize path
        try:
            canonical = Path(os.path.realpath(untrusted_path))
        except Exception as e:
            AuditLogger.log_event("INVALID_PATH_REJECTED", {"path": untrusted_path, "reason": str(e)})
            raise ValueError(f"Failed to canonicalize path: {str(e)}")

        if not canonical.exists():
            AuditLogger.log_event("INVALID_PATH_REJECTED", {"path": str(canonical), "reason": "File does not exist"})
            raise FileNotFoundError(f"Path does not exist: {canonical}")

        if not canonical.is_file():
            AuditLogger.log_event("INVALID_PATH_REJECTED", {"path": str(canonical), "reason": "Target is not a regular file"})
            raise ValueError(f"Path is not a regular file: {canonical}")

        return canonical

    @staticmethod
    def detect_evidence_type(path: Path) -> str:
        """
        Maps file extensions to standard forensic evidence categories.
        """
        ext = path.suffix.lower()
        name = path.name.lower()

        if ext in [".e01", ".e02", ".dd", ".img", ".raw", ".vmdk", ".vhd", ".qcow2"]:
            if "mem" in name:
                return "memory_dump"
            return "disk_image"
        elif ext in [".dmp", ".vmem"] or ("mem" in name and ext in [".bin", ".raw"]):
            return "memory_dump"
        elif ext in [".pcap", ".pcapng", ".cap"]:
            return "network_capture"
        elif ext in [".evtx", ".log", ".txt", ".csv", ".json", ".audit"] or "syslog" in name:
            return "log"
        elif ext in [".zip", ".tar", ".gz", ".7z", ".bz2"]:
            return "archive"
        elif ext in [".pdf", ".docx", ".xlsx", ".pptx", ".odt"]:
            return "document"
        elif path.is_dir():
            return "directory"
        return "unknown"

class AuditLogger:
    """
    Immutable structured audit logging for forensic actions and security events.
    """

    @staticmethod
    def log_event(event_type: str, details: Dict[str, Any], actor: str = "local-user"):
        now_utc = datetime.now(timezone.utc).isoformat()
        log_msg = f"EVENT={event_type} | ACTOR={actor} | DETAILS={details}"
        logger.info(log_msg)
