"""ADFIR — Investigation Recovery & Case Closure REST API Endpoints (Final Backend Completion)

Provides endpoints to:
- Recover case state, stale runs, and interrupted tasks deterministically
- Preserve valid forensic outputs without duplicate re-execution
- Validate and execute formal case closure with pre-closure verification gates
- Retrieve case closure status and sealed closure digest
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_active_user
from backend.app.models.models import User
from backend.app.schemas.schemas import (
    RecoveryRequest,
    RecoveryResponse,
    CaseClosureRequest,
    CaseClosureResponse
)
from backend.app.services.authorization import get_authorized_case, require_case_admin
from backend.app.services.recovery import InvestigationRecoveryService
from backend.app.services.case_closure import CaseClosureService

logger = logging.getLogger("ADFIR_RECOVERY_API")

router = APIRouter()


@router.post(
    "/cases/{case_id}/recover",
    response_model=RecoveryResponse,
    status_code=status.HTTP_200_OK
)
def recover_case(
    case_id: str,
    recovery_req: Optional[RecoveryRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Scans persistent storage, recovers interrupted runs and tasks safely,
    preserves completed executions whose output hashes remain intact,
    and ensures still-running processes are not duplicated.
    """
    case = get_authorized_case(case_id, db, current_user)
    force = recovery_req.force if recovery_req else False
    safe_reset = recovery_req.safe_reset_stale_tasks if recovery_req else True

    return InvestigationRecoveryService.recover_case(
        db=db,
        case_id=case.id,
        user=current_user,
        force=force,
        safe_reset_stale_tasks=safe_reset
    )


@router.post(
    "/cases/{case_id}/close",
    response_model=CaseClosureResponse,
    status_code=status.HTTP_200_OK
)
def close_case(
    case_id: str,
    closure_req: CaseClosureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Executes formal case closure with mandatory pre-closure verification gates:
    - Evidence integrity verified
    - Cryptographic audit chain verified
    - Official final forensic report verified
    - No active investigation tasks/runs
    - Generates immutable closure digest and permanently seals case
    """
    case = get_authorized_case(case_id, db, current_user)
    return CaseClosureService.validate_and_close_case(
        db=db,
        case_id=case.id,
        user=current_user,
        request_data=closure_req
    )


@router.get(
    "/cases/{case_id}/closure-status",
    status_code=status.HTTP_200_OK
)
def get_closure_status(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves the case closure status, sealing timestamp, and closure hash.
    """
    case = get_authorized_case(case_id, db, current_user)
    return {
        "case_id": case.id,
        "case_number": case.case_number,
        "status": case.status,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        "closure_hash": case.closure_hash,
        "is_immutable": case.status in ("CLOSED", "ARCHIVED")
    }
