from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import uuid

from backend.app.core.database import get_db
from backend.app.models.models import Case, EvidenceItem, Finding, InvestigationPlan, Report
from backend.app.schemas.schemas import InvestigationPlanResponse, FindingCreate, FindingResponse
from investigation.planner.planner_engine import InvestigationPlanner
from investigation.correlation.correlation_engine import EvidenceCorrelationEngine
from investigation.verification.verification_engine import VerificationEngine
from agents.report.report_synthesizer import ReportSynthesizer

router = APIRouter()
planner_engine = InvestigationPlanner()
correlation_engine = EvidenceCorrelationEngine()
verification_engine = VerificationEngine()
report_synthesizer = ReportSynthesizer()

@router.post("/plan/{case_id}", response_model=InvestigationPlanResponse)
def generate_plan(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
    ev_dicts = [
        {
            "id": e.id,
            "file_name": e.file_name,
            "file_path": e.file_path,
            "evidence_type": e.evidence_type,
            "sha256_hash": e.sha256_hash
        } for e in evidence_items
    ]

    plan_data = planner_engine.plan_investigation(case_id=case_id, evidence_list=ev_dicts)
    plan_id = str(uuid.uuid4())

    new_plan = InvestigationPlan(
        id=plan_id,
        case_id=case_id,
        strategy=plan_data,
        status="READY"
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)

    return InvestigationPlanResponse(
        id=new_plan.id,
        case_id=case_id,
        strategy_summary=plan_data["strategy_summary"],
        identified_evidence=plan_data["identified_evidence"],
        planned_tasks=plan_data["planned_tasks"],
        execution_order=plan_data["execution_order"],
        status="READY",
        created_at=new_plan.created_at
    )

@router.post("/findings", response_model=FindingResponse)
def record_finding(finding_in: FindingCreate, db: Session = Depends(get_db)):
    finding_dict = finding_in.model_dump()
    if "id" not in finding_dict or not finding_dict["id"]:
        finding_dict["id"] = str(uuid.uuid4())
    finding = Finding(**finding_dict)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding

@router.get("/findings/{case_id}", response_model=List[FindingResponse])
def get_findings_for_case(case_id: str, db: Session = Depends(get_db)):
    return db.query(Finding).filter(Finding.case_id == case_id).all()

@router.post("/correlate/{case_id}")
def correlate_case_evidence(case_id: str, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.case_id == case_id).all()
    finding_dicts = [
        {
            "id": f.id,
            "title": f.title,
            "source_tool": f.source_tool,
            "category": f.category,
            "details": f.details,
            "confidence_score": f.confidence_score
        } for f in findings
    ]
    correlated_events = correlation_engine.correlate(finding_dicts)
    return {"case_id": case_id, "correlated_events": correlated_events}

@router.post("/verify/{case_id}")
def verify_case_findings(case_id: str, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.case_id == case_id).all()
    finding_dicts = [
        {
            "id": f.id,
            "title": f.title,
            "source_tool": f.source_tool,
            "details": f.details,
            "confidence_score": f.confidence_score
        } for f in findings
    ]
    verified = verification_engine.verify_findings(finding_dicts)
    return {"case_id": case_id, "verification_results": verified}
