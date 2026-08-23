import uuid
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.models import Investigation, Evidence, ChainOfCustodyEvent, Finding
from backend.app.schemas.schemas import (
    InvestigationCreate,
    InvestigationResponse,
    EvidenceIntakeRequest,
    EvidenceResponse,
    CustodyRecord,
    FindingCreate,
    FindingResponse,
    InvestigationPlanResponse,
    CorrelatedGroupResponse,
    VerificationResultResponse,
    ReportResponse
)
from backend.app.core.security import SecurityValidator, AuditLogger
from backend.app.services.integrity import calculate_sha256
from investigation.planner.planner import InvestigationPlanner
from investigation.correlation.engine import CorrelationEngine
from investigation.verification.engine import VerificationEngine
from investigation.reporting.generator import ReportGenerator

router = APIRouter()
planner_service = InvestigationPlanner()
correlation_service = CorrelationEngine()
verification_service = VerificationEngine()
report_generator_service = ReportGenerator()

@router.post("/", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
def create_investigation(payload: InvestigationCreate, db: Session = Depends(get_db)):
    inv = Investigation(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        status="OPEN"
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    AuditLogger.log_event("INVESTIGATION_CREATED", {"id": inv.id, "name": inv.name})
    return inv

@router.get("/", response_model=List[InvestigationResponse])
def list_investigations(db: Session = Depends(get_db)):
    investigations = db.query(Investigation).all()
    results = []
    for inv in investigations:
        ev_count = db.query(Evidence).filter(Evidence.investigation_id == inv.id).count()
        find_count = db.query(Finding).filter(Finding.investigation_id == inv.id).count()
        results.append(InvestigationResponse(
            id=inv.id,
            name=inv.name,
            description=inv.description,
            status=inv.status,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
            evidence_count=ev_count,
            findings_count=find_count
        ))
    return results

@router.get("/{id}", response_model=InvestigationResponse)
def get_investigation(id: str, db: Session = Depends(get_db)):
    inv = db.query(Investigation).filter(Investigation.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{id}' not found.")
    ev_count = db.query(Evidence).filter(Evidence.investigation_id == inv.id).count()
    find_count = db.query(Finding).filter(Finding.investigation_id == inv.id).count()
    return InvestigationResponse(
        id=inv.id,
        name=inv.name,
        description=inv.description,
        status=inv.status,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        evidence_count=ev_count,
        findings_count=find_count
    )

@router.post("/{id}/evidence/intake", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def intake_evidence(id: str, payload: EvidenceIntakeRequest, db: Session = Depends(get_db)):
    inv = db.query(Investigation).filter(Investigation.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Investigation '{id}' not found.")

    # 1. Path validation & canonicalization (Security control: Path traversal rejection)
    try:
        canonical_path = SecurityValidator.validate_and_canonicalize_path(payload.path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. SHA-256 calculation (Streaming in 8 MiB chunks, evidence immutability preserved)
    try:
        sha256_hash, total_bytes = calculate_sha256(str(canonical_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate cryptographic hash: {str(e)}")

    # 3. Detect evidence type
    ev_type = SecurityValidator.detect_evidence_type(canonical_path)

    # 4. Create Evidence record
    stat_info = canonical_path.stat()
    evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    evidence = Evidence(
        id=evidence_id,
        investigation_id=id,
        name=canonical_path.name,
        original_path=str(canonical_path),
        evidence_type=ev_type,
        size_bytes=float(total_bytes),
        sha256=sha256_hash,
        mime_type="application/octet-stream",
        created_at=now,
        modified_at=datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc),
        intake_status="INTAKE_COMPLETE",
        integrity_status="VERIFIED",
        read_only_verified=not os.access(canonical_path, os.W_OK), # verify read-only
        notes=payload.notes,
        created_by="local-user"
    )
    db.add(evidence)

    # 5. Chain of Custody Event
    custody_event = ChainOfCustodyEvent(
        id=str(uuid.uuid4()),
        evidence_id=evidence_id,
        event_type="EVIDENCE_REGISTERED",
        timestamp=now,
        actor="local-user",
        description=f"Evidence '{canonical_path.name}' registered into investigation '{inv.name}'.",
        source_path=str(canonical_path),
        sha256=sha256_hash,
        metadata_json={"notes": payload.notes, "size_bytes": total_bytes}
    )
    db.add(custody_event)
    db.commit()
    db.refresh(evidence)

    AuditLogger.log_event("EVIDENCE_REGISTERED", {"evidence_id": evidence.id, "sha256": sha256_hash, "investigation_id": id})
    return evidence

@router.get("/{id}/evidence", response_model=List[EvidenceResponse])
def list_evidence(id: str, db: Session = Depends(get_db)):
    return db.query(Evidence).filter(Evidence.investigation_id == id).all()

@router.get("/{id}/custody", response_model=List[CustodyRecord])
def get_custody_events(id: str, db: Session = Depends(get_db)):
    ev_ids = [e.id for e in db.query(Evidence.id).filter(Evidence.investigation_id == id).all()]
    return db.query(ChainOfCustodyEvent).filter(ChainOfCustodyEvent.evidence_id.in_(ev_ids)).order_by(ChainOfCustodyEvent.timestamp.asc()).all()

@router.post("/{id}/plan", response_model=InvestigationPlanResponse)
def plan_investigation(id: str, db: Session = Depends(get_db)):
    inv = db.query(Investigation).filter(Investigation.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    evidence_items = db.query(Evidence).filter(Evidence.investigation_id == id).all()
    ev_dicts = [
        {"id": e.id, "name": e.name, "evidence_type": e.evidence_type, "original_path": e.original_path}
        for e in evidence_items
    ]

    plan_result = planner_service.plan(investigation_id=id, evidence_items=ev_dicts)
    return plan_result

@router.post("/{id}/findings", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
def record_finding(id: str, payload: FindingCreate, db: Session = Depends(get_db)):
    inv = db.query(Investigation).filter(Investigation.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    finding = Finding(
        id=str(uuid.uuid4()),
        investigation_id=id,
        evidence_id=payload.evidence_id,
        agent=payload.agent,
        tool=payload.tool,
        finding_type=payload.finding_type,
        title=payload.title,
        description=payload.description,
        confidence=payload.confidence,
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        evidence_reference=payload.evidence_reference,
        raw_output_reference=payload.raw_output_reference,
        verification_status="UNVERIFIED"
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding

@router.get("/{id}/findings", response_model=List[FindingResponse])
def list_findings(id: str, db: Session = Depends(get_db)):
    return db.query(Finding).filter(Finding.investigation_id == id).all()

@router.post("/{id}/correlate", response_model=List[CorrelatedGroupResponse])
def correlate_findings(id: str, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.investigation_id == id).all()
    finding_dicts = [
        {
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "evidence_reference": f.evidence_reference,
            "tool": f.tool,
            "agent": f.agent
        } for f in findings
    ]
    return correlation_service.correlate_findings(finding_dicts)

@router.post("/{id}/verify", response_model=List[VerificationResultResponse])
def verify_findings(id: str, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.investigation_id == id).all()
    finding_dicts = [
        {
            "id": f.id,
            "tool": f.tool,
            "description": f.description,
            "evidence_reference": f.evidence_reference,
            "confidence": f.confidence
        } for f in findings
    ]
    results = verification_service.verify_findings(finding_dicts)

    # Update database verification statuses
    status_map = {r["finding_id"]: r["verification_status"] for r in results if r.get("finding_id")}
    for f in findings:
        if f.id in status_map:
            f.verification_status = status_map[f.id]
    db.commit()

    return results

@router.post("/{id}/report", response_model=ReportResponse)
def generate_report(id: str, db: Session = Depends(get_db)):
    inv = db.query(Investigation).filter(Investigation.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    evidence_items = db.query(Evidence).filter(Evidence.investigation_id == id).all()
    custody_events = db.query(ChainOfCustodyEvent).filter(
        ChainOfCustodyEvent.evidence_id.in_([e.id for e in evidence_items])
    ).all()
    findings = db.query(Finding).filter(Finding.investigation_id == id).all()

    inv_dict = {"id": inv.id, "name": inv.name, "description": inv.description, "status": inv.status}
    ev_dicts = [{"id": e.id, "name": e.name, "evidence_type": e.evidence_type, "size_bytes": e.size_bytes, "sha256": e.sha256, "integrity_status": e.integrity_status} for e in evidence_items]
    custody_dicts = [{"timestamp": c.timestamp.isoformat(), "event_type": c.event_type, "actor": c.actor, "description": c.description, "sha256": c.sha256} for c in custody_events]
    finding_dicts = [{"id": f.id, "title": f.title, "agent": f.agent, "tool": f.tool, "finding_type": f.finding_type, "description": f.description, "confidence": f.confidence, "evidence_reference": f.evidence_reference, "verification_status": f.verification_status, "created_at": f.created_at.isoformat()} for f in findings]
    
    correlated = correlation_service.correlate_findings([
        {"id": f.id, "title": f.title, "description": f.description, "evidence_reference": f.evidence_reference, "tool": f.tool, "agent": f.agent}
        for f in findings
    ])

    return report_generator_service.generate_report(
        investigation=inv_dict,
        evidence_items=ev_dicts,
        custody_events=custody_dicts,
        findings=finding_dicts,
        correlated_events=correlated
    )
