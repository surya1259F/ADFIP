"""
ADFIP — Storage Budget & Resource-Aware Execution Service

Enforces forensic integrity and host stability by monitoring physical storage,
accounting for the mandatory 2048 MB (2 GB) ADFIP Safety Reserve, calculating
capability-specific artifact expansion multipliers, and categorizing storage health
into SAFE, WARNING, and INSUFFICIENT statuses.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.models import Case, EvidenceItem, AnalysisRequest
from backend.app.schemas.schemas import (
    StorageBudgetStatus,
    StorageBudgetResponse,
    ResourceEstimationResponse
)

logger = logging.getLogger("ADFIP_STORAGE_BUDGET")

# Mandatory Safety Reserve: 2048 MB (2 GB) reserved for OS, DB journals, and forensic swap
SAFETY_RESERVE_BYTES = 2048 * 1024 * 1024
SAFETY_RESERVE_MB = 2048.0

# Capability artifact expansion multipliers (relative to target evidence size)
CAPABILITY_MULTIPLIERS: Dict[str, float] = {
    # Filesystem structure & carving
    "TSK_FLS": 0.10,
    "FILESYSTEM_STRUCTURE_EXTRACTION": 0.10,
    "SLEUTHKIT": 0.10,
    "TSK_RECOVER": 1.20,
    "DELETED_FILE_CARVING": 1.20,
    # Memory analysis
    "VOLATILITY_PSLIST": 0.20,
    "VOLATILITY3": 0.20,
    "PROCESS_ENUMERATION": 0.20,
    "MEMORY_ANALYSIS": 0.20,
    # Signatures, Strings & Malware
    "YARA_SCAN": 0.05,
    "SIGNATURE_SCAN": 0.05,
    "STRINGS_ANALYSIS": 0.05,
    "STRINGS_EXTRACTION": 0.05,
    "FILE_ANALYSIS": 0.05,
    "MALWARE_ANALYSIS": 0.10,
    # Archives & Decompression
    "ARCHIVE_EXTRACTION": 2.50,
    "DECOMPRESS": 2.50,
    # Metadata & Integrity
    "METADATA_EXTRACTION": 0.02,
    "EXIFTOOL": 0.02,
    "HASHING": 0.01,
    "INTEGRITY_CHECK": 0.01,
    # Default fallback
    "DEFAULT": 0.10,
}


def get_capability_multiplier(capability: str) -> float:
    """Returns the artifact expansion multiplier for a given capability name."""
    if not capability:
        return CAPABILITY_MULTIPLIERS["DEFAULT"]

    cap_clean = capability.strip().upper().replace(" ", "_").replace("-", "_")
    if cap_clean in CAPABILITY_MULTIPLIERS:
        return CAPABILITY_MULTIPLIERS[cap_clean]

    # Partial / substring match
    for key, mult in CAPABILITY_MULTIPLIERS.items():
        if key in cap_clean or cap_clean in key:
            return mult

    return CAPABILITY_MULTIPLIERS["DEFAULT"]


def get_directory_size_bytes(path: Path) -> int:
    """Calculates total byte size of a directory recursively, ignoring missing/broken links."""
    if not path or not path.exists():
        return 0
    total = 0
    try:
        if path.is_file():
            return path.stat().st_size
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except OSError:
                    continue
    except OSError:
        pass
    return total


class StorageBudgetService:
    """
    Authoritative storage budget accounting engine for ADFIP investigations.
    """

    @classmethod
    def get_storage_budget(cls, db: Session, case_id: str) -> StorageBudgetResponse:
        """
        Computes real physical free disk, subtracts ADFIP safety reserve (2 GB),
        tallies workspace and vault consumption, and returns the authoritative budget.
        """
        # Determine target partition path
        storage_root = Path(settings.DATA_DIR)
        if not storage_root.exists():
            try:
                storage_root.mkdir(parents=True, exist_ok=True)
            except OSError:
                storage_root = Path.cwd()

        # 1. Physical Free Disk
        try:
            disk_stat = shutil.disk_usage(storage_root)
            physical_free_bytes = disk_stat.free
        except OSError:
            physical_free_bytes = 0

        physical_free_mb = round(physical_free_bytes / (1024 * 1024), 2)

        # 2. Safety Reserve (2048 MB)
        safety_reserve_bytes = SAFETY_RESERVE_BYTES
        safety_reserve_mb = SAFETY_RESERVE_MB

        # 3. Safe Available Disk = max(0, physical_free - safety_reserve)
        safe_available_bytes = max(0, physical_free_bytes - safety_reserve_bytes)
        safe_available_mb = round(safe_available_bytes / (1024 * 1024), 2)

        # 4. Case Workspace Used Bytes
        case_dir = storage_root / "cases" / case_id
        workspace_used_bytes = get_directory_size_bytes(case_dir)
        workspace_used_mb = round(workspace_used_bytes / (1024 * 1024), 2)

        # 5. Case Vault Used Bytes
        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
        vault_used_bytes = sum(ev.size_bytes or 0 for ev in evidence_items)
        vault_used_mb = round(vault_used_bytes / (1024 * 1024), 2)

        # 6. Projected Pending Executions
        pending_requests = db.query(AnalysisRequest).filter(
            AnalysisRequest.case_id == case_id,
            AnalysisRequest.scheduler_status.in_(["QUEUED", "READY", "RUNNING"])
        ).all()
        total_projected_bytes = 0
        for pr in pending_requests:
            reqs = pr.resource_requirements or {}
            disk_req_mb = reqs.get("disk_mb", 100)
            total_projected_bytes += int(disk_req_mb * 1024 * 1024)
        total_projected_mb = round(total_projected_bytes / (1024 * 1024), 2)

        # 7. Status Evaluation
        if physical_free_bytes <= safety_reserve_bytes or safe_available_bytes <= total_projected_bytes:
            status = StorageBudgetStatus.INSUFFICIENT
        elif safe_available_bytes < (1024 * 1024 * 1024) or safe_available_bytes < (total_projected_bytes * 2):
            status = StorageBudgetStatus.WARNING
        else:
            status = StorageBudgetStatus.SAFE

        thresholds = {
            "safety_reserve_mb": safety_reserve_mb,
            "warning_threshold_mb": 1024.0,
            "insufficient_threshold_mb": 0.0,
        }

        details = {
            "data_root": str(storage_root),
            "evidence_items_count": len(evidence_items),
            "pending_analysis_requests_count": len(pending_requests),
            "status_rationale": (
                "Sufficient safe storage available above 2 GB reserve"
                if status == StorageBudgetStatus.SAFE
                else "Tight safe disk headroom remaining"
                if status == StorageBudgetStatus.WARNING
                else "Insufficient disk space: physical disk free has penetrated or reached the 2 GB safety reserve"
            )
        }

        return StorageBudgetResponse(
            case_id=case_id,
            physical_free_bytes=physical_free_bytes,
            physical_free_mb=physical_free_mb,
            safety_reserve_bytes=safety_reserve_bytes,
            safety_reserve_mb=safety_reserve_mb,
            safe_available_bytes=safe_available_bytes,
            safe_available_mb=safe_available_mb,
            workspace_used_bytes=workspace_used_bytes,
            workspace_used_mb=workspace_used_mb,
            vault_used_bytes=vault_used_bytes,
            vault_used_mb=vault_used_mb,
            total_projected_bytes=total_projected_bytes,
            total_projected_mb=total_projected_mb,
            status=status,
            thresholds=thresholds,
            details=details
        )

    @classmethod
    def estimate_capability_storage(
        cls,
        capability: str,
        evidence_size_bytes: int,
        case_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> ResourceEstimationResponse:
        """
        Estimates output artifact footprint using capability multipliers,
        verifies against safe available storage, and returns admissibility verdict.
        """
        multiplier = get_capability_multiplier(capability)
        # Ensure minimum 1 MB artifact projection
        estimated_artifact_bytes = max(1024 * 1024, int(evidence_size_bytes * multiplier))
        estimated_artifact_mb = round(estimated_artifact_bytes / (1024 * 1024), 2)

        storage_root = Path(settings.DATA_DIR)
        try:
            disk_stat = shutil.disk_usage(storage_root if storage_root.exists() else Path.cwd())
            physical_free_bytes = disk_stat.free
        except OSError:
            physical_free_bytes = 0

        safe_available_bytes = max(0, physical_free_bytes - SAFETY_RESERVE_BYTES)
        safe_available_mb = round(safe_available_bytes / (1024 * 1024), 2)

        if safe_available_bytes < estimated_artifact_bytes or safe_available_bytes == 0:
            status = StorageBudgetStatus.INSUFFICIENT
            is_admissible = False
            warning_message = (
                f"Execution rejected: Estimated artifact size ({estimated_artifact_mb} MB) "
                f"exceeds safe available disk space ({safe_available_mb} MB) above the 2 GB safety reserve."
            )
        elif safe_available_bytes < (estimated_artifact_bytes * 2):
            status = StorageBudgetStatus.WARNING
            is_admissible = True
            warning_message = (
                f"Storage warning: Estimated artifact size ({estimated_artifact_mb} MB) "
                f"consumes a substantial portion of safe available disk ({safe_available_mb} MB)."
            )
        else:
            status = StorageBudgetStatus.SAFE
            is_admissible = True
            warning_message = None

        return ResourceEstimationResponse(
            capability=capability,
            evidence_size_bytes=evidence_size_bytes,
            multiplier=multiplier,
            estimated_artifact_bytes=estimated_artifact_bytes,
            estimated_artifact_mb=estimated_artifact_mb,
            safe_available_bytes=safe_available_bytes,
            safe_available_mb=safe_available_mb,
            status=status,
            is_admissible=is_admissible,
            warning_message=warning_message
        )
