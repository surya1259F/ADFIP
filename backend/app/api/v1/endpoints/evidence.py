from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import uuid

from backend.app.core.database import get_db
from backend.app.models.models import Case, EvidenceItem
from backend.app.schemas.schemas import EvidenceIntakeRequest, EvidenceResponse
from evidence.integrity.hasher import EvidenceIntegrityEngine

router = APIRouter()

@router.post("/intake", response_model=EvidenceResponse)
def intake_evidence(payload: EvidenceIntakeRequest, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    file_p = Path(payload.file_path)
    if not file_p.exists():
        raise HTTPException(status_code=400, detail=f"Evidence file not found on disk: {payload.file_path}")

    # 1. Deterministic hashing
    try:
        sha256_hash, md5_hash, size_bytes = EvidenceIntegrityEngine.calculate_hashes(payload.file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate hashes: {str(e)}")

    # 2. Evidence type auto-detection if needed
    ev_type = payload.evidence_type
    if not ev_type or ev_type == "AUTO_DETECT":
        ev_type = EvidenceIntegrityEngine.detect_evidence_type(payload.file_path)

    # 3. Chain of custody initialization
    custody_entry = EvidenceIntegrityEngine.create_custody_entry(
        action="EVIDENCE_INTAKE",
        actor=case.investigator,
        hash_val=sha256_hash,
        notes=payload.acquisition_notes or "Initial evidence ingestion into ADFIR workspace"
    )

    new_evidence = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=payload.case_id,
        file_name=file_p.name,
        file_path=str(file_p.resolve()),
        evidence_type=ev_type,
        size_bytes=size_bytes,
        sha256_hash=sha256_hash,
        md5_hash=md5_hash,
        chain_of_custody_log=[custody_entry],
        metadata_info={"extension": file_p.suffix, "is_read_only": True}
    )
    db.add(new_evidence)
    db.commit()
    db.refresh(new_evidence)
    return new_evidence

@router.get("/case/{case_id}", response_model=List[EvidenceResponse])
def list_evidence_for_case(case_id: str, db: Session = Depends(get_db)):
    return db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
