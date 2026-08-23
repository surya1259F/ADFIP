from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from backend.app.core.database import get_db
from backend.app.models.models import Case, EvidenceItem, Finding
from backend.app.schemas.schemas import CaseCreate, CaseResponse

router = APIRouter()

@router.post("/", response_model=CaseResponse)
def create_case(case_in: CaseCreate, db: Session = Depends(get_db)):
    db_case = db.query(Case).filter(Case.case_number == case_in.case_number).first()
    if db_case:
        raise HTTPException(status_code=400, detail="Case number already exists")

    new_case = Case(
        id=str(uuid.uuid4()),
        case_number=case_in.case_number,
        title=case_in.title,
        description=case_in.description,
        investigator=case_in.investigator,
        status="OPEN"
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case

@router.get("/", response_model=List[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).all()
    results = []
    for c in cases:
        ev_count = db.query(EvidenceItem).filter(EvidenceItem.case_id == c.id).count()
        findings_count = db.query(Finding).filter(Finding.case_id == c.id).count()
        results.append(CaseResponse(
            id=c.id,
            case_number=c.case_number,
            title=c.title,
            description=c.description,
            investigator=c.investigator,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
            evidence_count=ev_count,
            findings_count=findings_count
        ))
    return results

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    ev_count = db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).count()
    findings_count = db.query(Finding).filter(Finding.case_id == case.id).count()
    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        investigator=case.investigator,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        evidence_count=ev_count,
        findings_count=findings_count
    )
