from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.core.database import get_db
from backend.app.models.models import Case, EvidenceItem, Finding, Report
from backend.app.schemas.schemas import ReportResponse
from investigation.correlation.correlation_engine import EvidenceCorrelationEngine
from agents.report.report_synthesizer import ReportSynthesizer

router = APIRouter()
correlation_engine = EvidenceCorrelationEngine()
report_synthesizer = ReportSynthesizer()

@router.post("/generate/{case_id}", response_model=ReportResponse)
def generate_case_report(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case_id).all()
    findings = db.query(Finding).filter(Finding.case_id == case_id).all()

    ev_dicts = [{"file_name": e.file_name, "evidence_type": e.evidence_type, "sha256_hash": e.sha256_hash} for e in evidence_items]
    finding_dicts = [{"id": f.id, "title": f.title, "source_tool": f.source_tool, "category": f.category, "details": f.details, "confidence_score": f.confidence_score, "mitre_techniques": f.mitre_techniques, "timestamp": f.timestamp} for f in findings]
    
    correlated = correlation_engine.correlate(finding_dicts)
    case_info = {"title": case.title, "case_number": case.case_number, "investigator": case.investigator}

    report_data = report_synthesizer.generate_report(
        case_info=case_info,
        evidence_list=ev_dicts,
        findings=finding_dicts,
        correlated_groups=correlated
    )

    new_report = Report(
        id=str(uuid.uuid4()),
        case_id=case_id,
        title=report_data["title"],
        executive_summary=report_data["executive_summary"],
        attack_summary=report_data["attack_summary"],
        timeline_events=report_data["timeline_events"],
        indicators_of_compromise=report_data["indicators_of_compromise"],
        remediation_recommendations=report_data["remediation_recommendations"],
        full_report_markdown=report_data["full_report_markdown"]
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@router.get("/case/{case_id}", response_model=ReportResponse)
def get_latest_report(case_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.generated_at.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report generated yet for this case")
    return report
