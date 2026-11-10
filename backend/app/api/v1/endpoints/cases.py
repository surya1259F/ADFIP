import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_active_user
from backend.app.models.models import (
    Case,
    CaseMember,
    EvidenceItem,
    Finding,
    ExecutionArtifact,
    ToolExecution,
    EvidenceIntelligence,
    CorrelationGroup,
    AIReasoningRecord,
    InvestigatorDecision,
    InvestigatorReviewRecord,
    Report,
    AuditEvent,
    User,
)
from backend.app.schemas.schemas import (
    CaseCreate,
    CaseUpdate,
    CaseResponse,
    EvidenceResponse,
    CaseMemberCreateRequest,
    CaseMemberUpdateRequest,
    CaseMemberResponse,
    CaseClosureResponse,
    CasePermissionUpdateRequest,
    WorkspaceInitResponse,
    InvestigatorDecisionCreate,
    InvestigatorDecisionResponse,
    EvidenceVerificationResponse,
    DashboardAnalyticsResponse,
    CaseDashboardStats,
    WorkflowStageMetric,
    DashboardCaseActivity,
    DashboardAuditEvent,
)
from backend.app.services.authorization import (
    get_authorized_case,
    get_user_cases,
    ensure_case_member,
    is_case_admin,
    require_case_admin,
    validate_case_member_role,
)
from backend.app.services.workspace import initialize_case_workspace, get_workspace_status
from backend.app.services.audit import log_audit_event

router = APIRouter()

DEFAULT_CASE_PERMISSIONS = {
    "view_case": True,
    "edit_case_details": True,
    "manage_members": True,
    "manage_case_settings": True,
    "add_evidence": True,
    "run_investigation": True,
    "view_findings": True,
    "export_report": True,
}


def _build_case_response(c: Case, db: Session) -> CaseResponse:
    ev_count = db.query(EvidenceItem).filter(EvidenceItem.case_id == c.id).count()
    findings_count = db.query(Finding).filter(Finding.case_id == c.id).count()
    artifacts_count = db.query(ExecutionArtifact).filter(ExecutionArtifact.case_id == c.id).count()
    members_count = db.query(CaseMember).filter(CaseMember.case_id == c.id).count()

    return CaseResponse(
        id=c.id,
        case_number=c.case_number,
        name=c.name,
        title=c.name,
        description=c.description,
        objective=c.objective,
        case_type=c.case_type or "GENERAL_INVESTIGATION",
        priority=c.priority or "MEDIUM",
        status=c.status or "OPEN",
        workspace_state=c.workspace_state or "NOT_INITIALIZED",
        workspace_path=c.workspace_path,
        case_permissions=c.case_permissions or DEFAULT_CASE_PERMISSIONS,
        owner_id=c.owner_id,
        created_by=c.created_by,
        investigator=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
        closed_at=c.closed_at,
        evidence_count=ev_count,
        findings_count=findings_count,
        artifacts_count=artifacts_count,
        members_count=members_count,
    )


@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    case_in: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if case_in.case_number:
        db_case = db.query(Case).filter(Case.case_number == case_in.case_number).first()
        if db_case:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case number already exists")

    case_num = case_in.case_number or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    case_name = case_in.title or case_in.name or f"Case {case_num}"
    perms = case_in.case_permissions or DEFAULT_CASE_PERMISSIONS

    new_case = Case(
        id=str(uuid.uuid4()),
        case_number=case_num,
        name=case_name,
        description=case_in.description,
        objective=case_in.objective,
        case_type=case_in.case_type or "GENERAL_INVESTIGATION",
        priority=case_in.priority or "MEDIUM",
        owner_id=current_user.id,
        created_by=current_user.email,
        status="OPEN",
        workspace_state="NOT_INITIALIZED",
        case_permissions=perms,
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    # Automatically add case creator as Primary Investigator CaseMember
    ensure_case_member(case_id=new_case.id, user_id=current_user.id, db=db, role="PRIMARY_INVESTIGATOR")

    # Add initial members if provided
    if case_in.members:
        for m_req in case_in.members:
            m_user = None
            if m_req.user_id:
                m_user = db.query(User).filter(User.id == m_req.user_id).first()
            elif m_req.email:
                m_user = db.query(User).filter(User.email == m_req.email).first()
            if m_user and m_user.id != current_user.id:
                ensure_case_member(case_id=new_case.id, user_id=m_user.id, db=db, role=m_req.role)

    # Initialize workspace automatically
    initialize_case_workspace(new_case, db=db, actor_id=current_user.id, actor_name=current_user.name or current_user.email)

    # Audit log
    log_audit_event(
        db=db,
        event_type="CASE_CREATED",
        details=f"Case '{new_case.case_number}' ({new_case.name}) created by {current_user.email}",
        case_id=new_case.id,
        actor_id=current_user.id,
        actor_name=current_user.name or current_user.email,
        metadata_json={
            "case_number": new_case.case_number,
            "case_type": new_case.case_type,
            "priority": new_case.priority,
            "workspace_path": new_case.workspace_path
        }
    )

    return _build_case_response(new_case, db)


@router.get("/", response_model=List[CaseResponse])
@router.get("", response_model=List[CaseResponse])
def list_cases(
    filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    cases = get_user_cases(db, current_user)
    filter_name = (filter or "all").strip().lower()
    if filter_name not in {"all", "active", "completed", "pending", "failed", "attention"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid case filter. Expected all, active, completed, pending, failed, or attention.",
        )

    if filter_name != "all":
        case_ids = [case.id for case in cases]
        failed_execution_case_ids = set()
        unreviewed_finding_case_ids = set()
        if case_ids:
            failed_execution_case_ids = {
                row[0]
                for row in db.query(ToolExecution.case_id)
                .filter(
                    ToolExecution.case_id.in_(case_ids),
                    ToolExecution.status == "FAILED",
                )
                .distinct()
                .all()
            }
            unreviewed_finding_case_ids = {
                row[0]
                for row in db.query(Finding.case_id)
                .filter(
                    Finding.case_id.in_(case_ids),
                    Finding.verification_status.in_(
                        ["PENDING_REVIEW", "REQUIRES_REVIEW", "PROPOSED", "UNVERIFIED"]
                    ),
                )
                .distinct()
                .all()
            }

        def matches(case: Case) -> bool:
            status_norm = (case.status or "").upper().strip()
            if filter_name == "active":
                return status_norm in {"OPEN", "ACTIVE", "IN_PROGRESS"}
            if filter_name == "completed":
                return status_norm in {"CLOSED", "ARCHIVED"}
            if filter_name == "pending":
                return status_norm in {"DRAFT", "PENDING"}
            if filter_name == "failed":
                return status_norm == "FAILED" or case.id in failed_execution_case_ids
            return (
                status_norm == "FAILED"
                or case.id in failed_execution_case_ids
                or case.id in unreviewed_finding_case_ids
            )

        cases = [case for case in cases if matches(case)]
    return [_build_case_response(c, db) for c in cases]


@router.get("/dashboard/stats", response_model=DashboardAnalyticsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns live database-driven statistics, 10-stage workflow progress,
    investigation activities, and actionable cryptographically verified audit events.
    """
    from backend.app.services.audit import compute_audit_hash, compute_legacy_audit_hash, canonical_timestamp_iso, GENESIS_HASH

    cases = get_user_cases(db, current_user)
    case_ids = [c.id for c in cases]
    total_cases = len(cases)

    # 1. Real database-driven case statistics
    completed_count = 0
    active_count = 0
    pending_count = 0
    failed_cases_set = set()
    attention_cases_set = set()

    for c in cases:
        status_norm = (c.status or "").upper().strip()
        if status_norm in ("CLOSED", "ARCHIVED"):
            completed_count += 1
        elif status_norm in ("OPEN", "ACTIVE", "IN_PROGRESS"):
            active_count += 1
        elif status_norm in ("DRAFT", "PENDING"):
            pending_count += 1
        elif status_norm == "FAILED":
            failed_cases_set.add(c.id)

    # Check for failed tool executions across user cases
    if case_ids:
        failed_execs = db.query(ToolExecution.case_id).filter(
            ToolExecution.case_id.in_(case_ids),
            ToolExecution.status == "FAILED"
        ).distinct().all()
        for row in failed_execs:
            failed_cases_set.add(row[0])
            attention_cases_set.add(row[0])

        # Check for unreviewed findings across user cases
        unreviewed_findings = db.query(Finding.case_id).filter(
            Finding.case_id.in_(case_ids),
            Finding.verification_status.in_(["PENDING_REVIEW", "REQUIRES_REVIEW", "PROPOSED", "UNVERIFIED"])
        ).distinct().all()
        for row in unreviewed_findings:
            attention_cases_set.add(row[0])

    # 2. 10-Stage Workflow Progress Indicator
    evidence_counts = dict(
        db.query(EvidenceItem.case_id, func.count(EvidenceItem.id))
        .filter(EvidenceItem.case_id.in_(case_ids))
        .group_by(EvidenceItem.case_id).all()
    ) if case_ids else {}

    artifact_counts = dict(
        db.query(ExecutionArtifact.case_id, func.count(ExecutionArtifact.id))
        .filter(ExecutionArtifact.case_id.in_(case_ids))
        .group_by(ExecutionArtifact.case_id).all()
    ) if case_ids else {}

    execution_counts = dict(
        db.query(ToolExecution.case_id, func.count(ToolExecution.id))
        .filter(ToolExecution.case_id.in_(case_ids))
        .group_by(ToolExecution.case_id).all()
    ) if case_ids else {}

    carving_cases = set(
        r[0] for r in (
            db.query(ToolExecution.case_id)
            .filter(
                ToolExecution.case_id.in_(case_ids),
                or_(
                    ToolExecution.tool_id.ilike("%carv%"),
                    ToolExecution.tool_id.ilike("%foremost%"),
                    ToolExecution.tool_id.ilike("%scalpel%"),
                    ToolExecution.tool_id.ilike("%bulk_extractor%")
                )
            ).distinct().all()
        )
    ) if case_ids else set()

    strings_cases = set(
        r[0] for r in (
            db.query(ToolExecution.case_id)
            .filter(
                ToolExecution.case_id.in_(case_ids),
                or_(
                    ToolExecution.tool_id.ilike("%string%"),
                    ToolExecution.tool_id.ilike("%grep%"),
                    ToolExecution.tool_id.ilike("%pattern%")
                )
            ).distinct().all()
        )
    ) if case_ids else set()

    intelligence_cases = set(
        r[0] for r in (
            db.query(EvidenceIntelligence.evidence_id)
            .join(EvidenceItem, EvidenceItem.id == EvidenceIntelligence.evidence_id)
            .filter(EvidenceItem.case_id.in_(case_ids))
            .distinct().all()
        )
    ) if case_ids else set()

    correlation_counts = dict(
        db.query(CorrelationGroup.case_id, func.count(CorrelationGroup.id))
        .filter(CorrelationGroup.case_id.in_(case_ids))
        .group_by(CorrelationGroup.case_id).all()
    ) if case_ids else {}

    ai_reasoning_cases = set(
        r[0] for r in (
            db.query(AIReasoningRecord.case_id)
            .filter(AIReasoningRecord.case_id.in_(case_ids))
            .distinct().all()
        )
    ) if case_ids else set()

    review_cases = set(
        r[0] for r in (
            db.query(InvestigatorReviewRecord.case_id)
            .filter(InvestigatorReviewRecord.case_id.in_(case_ids))
            .distinct().all()
        )
    ) if case_ids else set()
    decision_cases = set(
        r[0] for r in (
            db.query(InvestigatorDecision.case_id)
            .filter(InvestigatorDecision.case_id.in_(case_ids))
            .distinct().all()
        )
    ) if case_ids else set()
    all_review_cases = review_cases | decision_cases

    report_counts = dict(
        db.query(Report.case_id, func.count(Report.id))
        .filter(Report.case_id.in_(case_ids))
        .group_by(Report.case_id).all()
    ) if case_ids else {}

    findings_counts = dict(
        db.query(Finding.case_id, func.count(Finding.id))
        .filter(Finding.case_id.in_(case_ids))
        .group_by(Finding.case_id).all()
    ) if case_ids else {}

    s1_cases = sum(1 for cid in case_ids if evidence_counts.get(cid, 0) > 0)
    s2_cases = sum(1 for cid in case_ids if artifact_counts.get(cid, 0) > 0 or execution_counts.get(cid, 0) > 0)
    s3_cases = sum(1 for cid in case_ids if cid in intelligence_cases or artifact_counts.get(cid, 0) > 0)
    s4_cases = sum(1 for cid in case_ids if cid in carving_cases)
    s5_cases = sum(1 for cid in case_ids if cid in strings_cases)
    s6_cases = sum(1 for cid in case_ids if correlation_counts.get(cid, 0) > 0)
    s7_cases = sum(1 for cid in case_ids if cid in ai_reasoning_cases)
    s8_cases = sum(1 for cid in case_ids if cid in all_review_cases)
    s9_cases = sum(1 for cid in case_ids if report_counts.get(cid, 0) > 0)
    s10_cases = sum(1 for c in cases if (c.status or "").upper() in ("CLOSED", "ARCHIVED"))

    calc_pct = lambda count: round((count / total_cases * 100.0), 1) if total_cases > 0 else 0.0

    workflow_stages = [
        WorkflowStageMetric(stage_number=1, stage_key="INGESTION", label="Evidence Intake & Vault", cases_completed=s1_cases, percentage=calc_pct(s1_cases)),
        WorkflowStageMetric(stage_number=2, stage_key="EXTRACTION", label="Forensic Tool Extraction", cases_completed=s2_cases, percentage=calc_pct(s2_cases)),
        WorkflowStageMetric(stage_number=3, stage_key="METADATA_ANALYSIS", label="Metadata & Entropy Analysis", cases_completed=s3_cases, percentage=calc_pct(s3_cases)),
        WorkflowStageMetric(stage_number=4, stage_key="CARVING", label="File & Data Carving", cases_completed=s4_cases, percentage=calc_pct(s4_cases)),
        WorkflowStageMetric(stage_number=5, stage_key="STRING_SEARCH", label="GNU Strings & Pattern Search", cases_completed=s5_cases, percentage=calc_pct(s5_cases)),
        WorkflowStageMetric(stage_number=6, stage_key="CORRELATION", label="Cross-Domain Correlation", cases_completed=s6_cases, percentage=calc_pct(s6_cases)),
        WorkflowStageMetric(stage_number=7, stage_key="AGENT_REASONING", label="Multi-Agent AI Reasoning", cases_completed=s7_cases, percentage=calc_pct(s7_cases)),
        WorkflowStageMetric(stage_number=8, stage_key="INVESTIGATOR_REVIEW", label="Human-in-the-Loop Review", cases_completed=s8_cases, percentage=calc_pct(s8_cases)),
        WorkflowStageMetric(stage_number=9, stage_key="REPORT_GENERATION", label="Authoritative Report Generation", cases_completed=s9_cases, percentage=calc_pct(s9_cases)),
        WorkflowStageMetric(stage_number=10, stage_key="ARCHIVAL", label="Evidence Sealed & Case Closure", cases_completed=s10_cases, percentage=calc_pct(s10_cases)),
    ]

    # 3. Investigation Activity List (top 10 recent cases)
    recent_activity = []
    case_map = {c.id: c.case_number for c in cases}
    for c in cases[:10]:
        if (c.status or "").upper() in ("CLOSED", "ARCHIVED"):
            c_stage = "ARCHIVAL (CLOSED)"
        elif report_counts.get(c.id, 0) > 0:
            c_stage = "REPORT_GENERATION"
        elif c.id in all_review_cases:
            c_stage = "INVESTIGATOR_REVIEW"
        elif c.id in ai_reasoning_cases:
            c_stage = "AGENT_REASONING"
        elif correlation_counts.get(c.id, 0) > 0:
            c_stage = "CORRELATION"
        elif c.id in strings_cases:
            c_stage = "STRING_SEARCH"
        elif c.id in carving_cases:
            c_stage = "CARVING"
        elif c.id in intelligence_cases:
            c_stage = "METADATA_ANALYSIS"
        elif artifact_counts.get(c.id, 0) > 0 or execution_counts.get(c.id, 0) > 0:
            c_stage = "EXTRACTION"
        elif evidence_counts.get(c.id, 0) > 0:
            c_stage = "INGESTION"
        else:
            c_stage = "WORKSPACE_INITIALIZED"

        investigator = c.created_by or c.owner_id or "Investigator"
        recent_activity.append(
            DashboardCaseActivity(
                id=c.id,
                case_number=c.case_number,
                title=c.name or c.case_number,
                name=c.name or c.case_number,
                status=c.status,
                current_stage=c_stage,
                assigned_investigator=investigator,
                created_at=c.created_at,
                updated_at=c.updated_at,
                evidence_count=evidence_counts.get(c.id, 0),
                findings_count=findings_counts.get(c.id, 0),
            )
        )

    # 4. Actionable Audit Event Stream (last 15 events)
    recent_audit_events = []
    audit_query = db.query(AuditEvent)
    if case_ids:
        audit_query = audit_query.filter(or_(AuditEvent.case_id.in_(case_ids), AuditEvent.case_id.is_(None)))
    else:
        audit_query = audit_query.filter(AuditEvent.case_id.is_(None))

    audit_records = audit_query.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).limit(15).all()

    for ev in audit_records:
        is_valid = True
        if ev.event_hash:
            try:
                expected_hash = compute_audit_hash(
                    chain_index=ev.chain_index or 0,
                    previous_hash=ev.previous_hash or GENESIS_HASH,
                    timestamp_iso=canonical_timestamp_iso(ev.timestamp),
                    event_type=ev.event_type,
                    case_id=ev.case_id,
                    actor_name=ev.actor_name,
                    details=ev.details,
                    metadata_json=ev.metadata_json or {},
                    provenance_context=ev.provenance_context or {}
                )
                if ev.event_hash != expected_hash:
                    legacy_hash = compute_legacy_audit_hash(
                        timestamp_iso=canonical_timestamp_iso(ev.timestamp),
                        event_type=ev.event_type,
                        case_id=ev.case_id,
                        actor_name=ev.actor_name,
                        details=ev.details,
                        metadata_json=ev.metadata_json or {}
                    )
                    is_valid = (ev.event_hash == legacy_hash)
            except Exception:
                is_valid = False

        recent_audit_events.append(
            DashboardAuditEvent(
                id=ev.id,
                case_id=ev.case_id,
                case_number=case_map.get(ev.case_id) if ev.case_id else None,
                actor_name=ev.actor_name,
                event_type=ev.event_type,
                details=ev.details,
                timestamp=ev.timestamp,
                event_hash=ev.event_hash,
                chain_index=ev.chain_index,
                is_hash_valid=is_valid,
            )
        )

    return DashboardAnalyticsResponse(
        stats=CaseDashboardStats(
            total=total_cases,
            completed=completed_count,
            active=active_count,
            pending=pending_count,
            failed=len(failed_cases_set),
            attention_required=len(attention_cases_set),
        ),
        workflow_stages=workflow_stages,
        recent_activity=recent_activity,
        audit_events=recent_audit_events,
    )


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    return _build_case_response(case, db)


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    case_in: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed, CaseClosureService
    from backend.app.schemas.schemas import CaseClosureRequest
    check_case_not_closed(case)

    changes = []
    if case_in.name is not None or case_in.title is not None:
        new_name = case_in.title or case_in.name
        case.name = new_name
        changes.append("name")
    if case_in.description is not None:
        case.description = case_in.description
        changes.append("description")
    if case_in.objective is not None:
        case.objective = case_in.objective
        changes.append("objective")
    if case_in.case_type is not None:
        case.case_type = case_in.case_type
        changes.append("case_type")
    if case_in.priority is not None:
        case.priority = case_in.priority
        changes.append("priority")
    if case_in.case_permissions is not None:
        updated_perms = dict(case.case_permissions or DEFAULT_CASE_PERMISSIONS)
        updated_perms.update(case_in.case_permissions)
        case.case_permissions = updated_perms
        changes.append("case_permissions")

    if case_in.status is not None:
        new_status = case_in.status.upper().strip()
        valid_statuses = {"DRAFT", "OPEN", "CLOSED", "ARCHIVED"}
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid case status '{case_in.status}'. Valid statuses: {sorted(list(valid_statuses))}"
            )
        if new_status == "CLOSED":
            # Delegate directly to authoritative CaseClosureService
            CaseClosureService.validate_and_close_case(
                db=db,
                case_id=case.id,
                user=current_user,
                request_data=CaseClosureRequest(rationale=f"Case closed by {current_user.email} via case management API")
            )
            return _build_case_response(case, db)
        elif new_status == "ARCHIVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active cases cannot be directly archived. The case must first be formally closed."
            )
        else:
            old_status = case.status
            case.status = new_status
            changes.append(f"status({old_status}->{new_status})")

    case.updated_at = datetime.now(timezone.utc)
    db.add(case)
    db.commit()
    db.refresh(case)

    if changes:
        log_audit_event(
            db=db,
            event_type="CASE_UPDATED",
            details=f"Case '{case.case_number}' updated by {current_user.email}: {', '.join(changes)}",
            case_id=case.id,
            actor_id=current_user.id,
            actor_name=current_user.email,
            metadata_json={"changed_fields": changes}
        )

    return _build_case_response(case, db)


@router.post("/{case_id}/workspace/initialize", response_model=WorkspaceInitResponse)
def initialize_workspace_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)
    res = initialize_case_workspace(case, db, actor_id=current_user.id, actor_name=current_user.email)
    return WorkspaceInitResponse(
        case_id=res["case_id"],
        workspace_state=res["workspace_state"],
        workspace_path=res["workspace_path"],
        subdirectories=res["subdirectories"],
        initialized_at=res["initialized_at"]
    )


@router.get("/{case_id}/workspace/status")
def get_workspace_status_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    return get_workspace_status(case)


@router.get("/{case_id}/members", response_model=List[CaseMemberResponse])
def list_case_members(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    members = db.query(CaseMember).filter(CaseMember.case_id == case.id).all()
    results = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        results.append(CaseMemberResponse(
            id=m.id,
            case_id=m.case_id,
            user_id=m.user_id,
            role=m.role,
            added_at=m.added_at,
            email=u.email if u else None,
            name=u.name if u else None
        ))
    return results


@router.post("/{case_id}/members", response_model=CaseMemberResponse, status_code=status.HTTP_201_CREATED)
def add_case_member(
    case_id: str,
    member_in: CaseMemberCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    target_user = None
    if member_in.user_id:
        target_user = db.query(User).filter(User.id == member_in.user_id).first()
    elif member_in.email:
        target_user = db.query(User).filter(User.email == member_in.email).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check for existing membership
    existing = db.query(CaseMember).filter(
        CaseMember.case_id == case.id,
        CaseMember.user_id == target_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{target_user.email}' is already a member of this case."
        )

    clean_role = validate_case_member_role(member_in.role)
    new_member = ensure_case_member(case_id=case.id, user_id=target_user.id, db=db, role=clean_role)

    log_audit_event(
        db=db,
        event_type="CASE_MEMBER_ADDED",
        details=f"User '{target_user.email}' added to case '{case.case_number}' as role '{clean_role}' by {current_user.email}",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={"added_user_id": target_user.id, "added_user_email": target_user.email, "role": clean_role}
    )

    return CaseMemberResponse(
        id=new_member.id,
        case_id=new_member.case_id,
        user_id=new_member.user_id,
        role=new_member.role,
        added_at=new_member.added_at,
        email=target_user.email,
        name=target_user.name
    )


@router.patch("/{case_id}/members/{user_id}", response_model=CaseMemberResponse)
def update_case_member(
    case_id: str,
    user_id: str,
    member_in: CaseMemberUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    member = db.query(CaseMember).filter(
        CaseMember.case_id == case.id,
        CaseMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case member not found.")

    clean_role = validate_case_member_role(member_in.role)
    member.role = clean_role
    db.commit()
    db.refresh(member)

    target_user = db.query(User).filter(User.id == user_id).first()

    log_audit_event(
        db=db,
        event_type="CASE_MEMBER_UPDATED",
        details=f"Role for user '{target_user.email if target_user else user_id}' updated to '{clean_role}' in case '{case.case_number}'",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email
    )

    return CaseMemberResponse(
        id=member.id,
        case_id=member.case_id,
        user_id=member.user_id,
        role=member.role,
        added_at=member.added_at,
        email=target_user.email if target_user else None,
        name=target_user.name if target_user else None
    )


@router.delete("/{case_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def remove_case_member(
    case_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    if case.owner_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the owner of the case."
        )

    member = db.query(CaseMember).filter(
        CaseMember.case_id == case.id,
        CaseMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case member not found.")

    target_user = db.query(User).filter(User.id == user_id).first()
    target_email = target_user.email if target_user else user_id

    db.delete(member)
    db.commit()

    log_audit_event(
        db=db,
        event_type="CASE_MEMBER_REMOVED",
        details=f"User '{target_email}' removed from case '{case.case_number}' by {current_user.email}",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={"removed_user_id": user_id, "removed_user_email": target_email}
    )

    return {"detail": f"User '{target_email}' successfully removed from case."}


@router.get("/{case_id}/permissions")
def get_case_permissions(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    return case.case_permissions or DEFAULT_CASE_PERMISSIONS


@router.patch("/{case_id}/permissions")
def update_case_permissions(
    case_id: str,
    perms_in: CasePermissionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    current_perms = dict(case.case_permissions or DEFAULT_CASE_PERMISSIONS)
    current_perms.update(perms_in.permissions)
    case.case_permissions = current_perms
    db.commit()

    log_audit_event(
        db=db,
        event_type="CASE_PERMISSIONS_UPDATED",
        details=f"Case permissions updated for case '{case.case_number}' by {current_user.email}",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={"updated_permissions": perms_in.permissions}
    )

    return case.case_permissions


@router.get("/{case_id}/evidence", response_model=List[EvidenceResponse])
def get_case_evidence_items(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    return db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all()


@router.post("/{case_id}/evidence/intake", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def intake_case_evidence(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file_upload = form.get("file")
        file_stream = file_upload.file if hasattr(file_upload, "file") else None
        filename = getattr(file_upload, "filename", None) or form.get("name")
        source_path = form.get("file_path") or form.get("source_path") or form.get("path")
        evidence_type = form.get("evidence_type")
        notes = form.get("notes") or form.get("acquisition_notes")
        name = form.get("name") or filename
    else:
        payload = await request.json()
        file_stream = None
        source_path = payload.get("file_path") or payload.get("path")
        evidence_type = payload.get("evidence_type")
        notes = payload.get("notes") or payload.get("acquisition_notes")
        name = payload.get("name")
        filename = name

    from backend.app.api.v1.endpoints.evidence import process_evidence_intake
    return process_evidence_intake(
        db=db,
        current_user=current_user,
        case_id=case.id,
        file_stream=file_stream,
        filename=str(name or filename) if (name or filename) else None,
        source_path=str(source_path) if source_path else None,
        evidence_type=str(evidence_type) if evidence_type else None,
        notes=str(notes) if notes else None,
    )


@router.post("/{case_id}/evidence/{evidence_id}/verify", response_model=EvidenceVerificationResponse)
@router.post("/{case_id}/evidence/{evidence_id}/verify-integrity", response_model=EvidenceVerificationResponse)
def verify_case_evidence_endpoint(
    case_id: str,
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    from backend.app.api.v1.endpoints.evidence import verify_evidence
    return verify_evidence(evidence_id=evidence_id, db=db, current_user=current_user)


@router.post("/{case_id}/verify")
def verify_case_findings_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    from backend.app.api.v1.endpoints.investigation import verify_case_findings
    return verify_case_findings(case_id=case_id, db=db, current_user=current_user)


@router.post("/{case_id}/close", response_model=CaseClosureResponse)
def close_case_endpoint(
    case_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    from backend.app.services.case_closure import CaseClosureService
    from backend.app.schemas.schemas import CaseClosureRequest
    rationale = (payload or {}).get("rationale") or f"Case closed by {current_user.email} via case management API"
    return CaseClosureService.validate_and_close_case(
        db=db,
        case_id=case.id,
        user=current_user,
        request_data=CaseClosureRequest(rationale=rationale)
    )


@router.post("/{case_id}/archive", response_model=CaseResponse)
def archive_case_endpoint(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    require_case_admin(case, db, current_user)
    if case.status != "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active cases cannot be directly archived. The case must first be formally closed."
        )
    case.status = "ARCHIVED"
    case.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)

    log_audit_event(
        db=db,
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        event_type="CASE_ARCHIVED",
        details=f"Case '{case.name}' moved to immutable long-term archive."
    )
    return _build_case_response(case, db)


# -----------------------------------------------------------------------------
# Case Decisions & Execution Compatibility Routes
# -----------------------------------------------------------------------------

@router.post("/{case_id}/decisions", response_model=InvestigatorDecisionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/{case_id}/decision", response_model=InvestigatorDecisionResponse, status_code=status.HTTP_201_CREATED)
def record_case_decision_compat(
    case_id: str,
    dec_in: InvestigatorDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from backend.app.models.models import InvestigatorDecision
    from backend.app.services.case_closure import check_case_not_closed

    case = get_authorized_case(case_id, db, current_user)
    check_case_not_closed(case)

    investigator_name = current_user.name or current_user.email

    decision = InvestigatorDecision(
        case_id=case.id,
        investigator_id=current_user.id,
        investigator_name=investigator_name,
        decision=dec_in.decision,
        rationale=dec_in.rationale,
        finding_ids=dec_in.finding_ids,
        evidence_ids=dec_in.evidence_ids
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    log_audit_event(
        db=db,
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=investigator_name,
        event_type="DECISION_RECORDED",
        details=f"Official decision '{decision.decision}' signed by investigator '{investigator_name}'. Rationale: {decision.rationale}"
    )
    return decision


@router.get("/{case_id}/decisions", response_model=List[InvestigatorDecisionResponse])
def get_case_decisions_compat(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from backend.app.models.models import InvestigatorDecision
    case = get_authorized_case(case_id, db, current_user)
    return db.query(InvestigatorDecision).filter(InvestigatorDecision.case_id == case.id).order_by(InvestigatorDecision.timestamp.desc()).all()


def _resolve_tool_and_agent(tool_raw: str):
    from forensic_tools.registry import tool_registry
    tool_def = tool_registry.get_tool(tool_raw)
    tool_display = tool_def.display_name if tool_def else (tool_raw or "Specialist Tool")
    if tool_def:
        caps = tool_def.capabilities or []
        if any(c in caps for c in ["filesystem_structure_extraction", "metadata_extraction", "filesystem_analysis"]):
            agent_name = "DiskAgent"
        elif "signature_scan" in caps:
            agent_name = "MalwareAgent"
        elif "security_log_parsing" in caps:
            agent_name = "LogAgent"
        elif any(c in caps for c in ["process_enumeration", "network_socket_extraction"]):
            agent_name = "MemoryAgent"
        else:
            agent_name = "ForensicAgent"
    else:
        agent_name = "ForensicAgent"
    return tool_display, agent_name


@router.get("/{case_id}/executions")
def list_case_executions_compat(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from backend.app.models.models import ToolExecution, ForensicExecution, ExecutionArtifact, Finding
    case = get_authorized_case(case_id, db, current_user)

    results = []

    # Map ForensicExecution records
    fe_list = (
        db.query(ForensicExecution)
        .filter(ForensicExecution.case_id == case.id)
        .order_by(ForensicExecution.created_at.desc())
        .all()
    )
    for fe in fe_list:
        art_count = db.query(ExecutionArtifact).filter(ExecutionArtifact.execution_id == fe.id).count()
        f_count = db.query(Finding).filter(Finding.execution_id == fe.id).count()
        status_norm = getattr(fe, "execution_status", "COMPLETED")
        tool_raw = str(fe.tool_id or "")
        tool_display, agent_name = _resolve_tool_and_agent(tool_raw)
        results.append({
            "id": fe.id,
            "case_id": fe.case_id,
            "evidence_id": fe.evidence_id,
            "agent": agent_name,
            "tool": tool_display,
            "status": status_norm,
            "progress": 100 if status_norm == "COMPLETED" else (0 if status_norm in ["QUEUED", "STARTING"] else 50),
            "started_at": fe.started_at.isoformat() if hasattr(fe, "started_at") and fe.started_at else (fe.created_at.isoformat() if hasattr(fe, "created_at") and fe.created_at else None),
            "completed_at": fe.completed_at.isoformat() if hasattr(fe, "completed_at") and fe.completed_at else None,
            "duration_ms": getattr(fe, "execution_time_ms", None),
            "error": getattr(fe, "failure_reason", None) or getattr(fe, "error_message", None),
            "artifacts_count": art_count,
            "findings_count": f_count,
            "metadata": fe.resource_allocation or {}
        })

    # Map ToolExecution records
    te_list = (
        db.query(ToolExecution)
        .filter(ToolExecution.case_id == case.id)
        .order_by(ToolExecution.created_at.desc())
        .all()
    )
    for te in te_list:
        if any(r["id"] == te.id for r in results):
            continue
        tool_raw = str(te.tool_id or "")
        tool_display, agent_name = _resolve_tool_and_agent(tool_raw)
        art_count = db.query(ExecutionArtifact).filter(ExecutionArtifact.execution_id == te.id).count()
        f_count = db.query(Finding).filter(Finding.execution_id == te.id).count()
        status_norm = te.status or "COMPLETED"
        results.append({
            "id": te.id,
            "case_id": te.case_id,
            "evidence_id": te.evidence_id,
            "agent": agent_name,
            "tool": tool_display,
            "status": status_norm,
            "progress": 100 if status_norm == "COMPLETED" else (0 if status_norm in ["QUEUED", "STARTING"] else 50),
            "started_at": te.started_at.isoformat() if te.started_at else (te.created_at.isoformat() if te.created_at else None),
            "completed_at": te.completed_at.isoformat() if te.completed_at else None,
            "duration_ms": te.execution_time_ms,
            "error": te.error_message,
            "artifacts_count": art_count,
            "findings_count": f_count,
            "metadata": {"command_args": te.command_args}
        })

    return results


@router.get("/{case_id}/executions/{execution_id}")
def get_case_execution_compat(
    case_id: str,
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from backend.app.models.models import ToolExecution, ForensicExecution
    case = get_authorized_case(case_id, db, current_user)
    fe = (
        db.query(ForensicExecution)
        .filter(ForensicExecution.id == execution_id, ForensicExecution.case_id == case.id)
        .first()
    )
    if fe:
        return fe
    exec_rec = (
        db.query(ToolExecution)
        .filter(ToolExecution.id == execution_id, ToolExecution.case_id == case.id)
        .first()
    )
    if not exec_rec:
        raise HTTPException(status_code=404, detail="Execution record not found.")
    return exec_rec


@router.post("/{case_id}/plan")
def create_case_plan_compat(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    from backend.app.api.endpoints.investigations import planner_service
    from backend.app.models.models import InvestigationPlan, EvidenceItem

    evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all()
    ev_dicts = [
        {
            "id": e.id,
            "name": e.name,
            "evidence_type": e.evidence_type,
            "source_kind": getattr(e, "source_kind", None),
            "size_bytes": e.size_bytes,
        }
        for e in evidence_items
    ]
    plan_dict = planner_service.plan(investigation_id=case.id, evidence_items=ev_dicts)

    old_plans = db.query(InvestigationPlan).filter(InvestigationPlan.case_id == case.id).all()
    for op in old_plans:
        op.is_active = False

    new_plan = InvestigationPlan(
        case_id=case.id,
        status="PLANNED",
        strategy_summary=plan_dict.get("strategy_summary"),
        tasks=plan_dict.get("tasks", []),
        is_active=True,
        version=(max([p.version for p in old_plans], default=0) + 1)
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)

    return {
        "id": new_plan.id,
        "case_id": new_plan.case_id,
        "strategy_summary": new_plan.strategy_summary,
        "tasks": new_plan.tasks or [],
        "total_tasks": len(new_plan.tasks or []),
        "status": new_plan.status,
        "version": new_plan.version,
        "created_at": new_plan.created_at.isoformat() if new_plan.created_at else None,
        "completed_at": new_plan.completed_at.isoformat() if new_plan.completed_at else None,
    }


@router.get("/{case_id}/plan")
def get_case_plan_compat(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    from backend.app.models.models import InvestigationPlan

    plan = (
        db.query(InvestigationPlan)
        .filter(InvestigationPlan.case_id == case.id, InvestigationPlan.is_active == True)
        .order_by(InvestigationPlan.created_at.desc())
        .first()
    )
    if not plan:
        return create_case_plan_compat(case_id=case_id, db=db, current_user=current_user)

    return {
        "id": plan.id,
        "case_id": plan.case_id,
        "strategy_summary": plan.strategy_summary,
        "tasks": plan.tasks or [],
        "total_tasks": len(plan.tasks or []),
        "status": plan.status,
        "version": plan.version,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
    }


@router.post("/{case_id}/plan/execute")
def execute_case_plan_compat(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(case_id, db, current_user)
    from backend.app.services.case_closure import check_case_not_closed
    check_case_not_closed(case)

    from backend.app.api.endpoints.investigations import orchestrator_service
    try:
        return orchestrator_service.execute_plan(case_id=case.id, db=db)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
