"""
ADFIP — Challenge Resolution Engine

Orchestrates human-in-the-loop dispute resolution:
Disputed Finding -> Evidentiary Gap -> Capability Matching -> Storage Budget Check
-> Governance Gate -> Scheduler Pipeline -> Verification -> Review
"""

import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Case,
    User,
    DeterministicFinding,
    Finding,
    EvidenceItem,
    InvestigationPlan,
    AnalysisRequest,
    InvestigatorReviewRecord
)
from backend.app.schemas.schemas import (
    ChallengeResolutionRequest,
    ChallengeResolutionResponse,
    FindingLifecycleState,
    InvestigatorReviewCreateRequest
)
from backend.app.services.storage_budget import StorageBudgetService, StorageBudgetStatus
from backend.app.services.governance import GovernanceGateService, GovernanceDecisionType
from backend.app.services.scheduler import ResourceAwareScheduler
from backend.app.services.investigator_review import InvestigatorReviewService

logger = logging.getLogger("ADFIP_CHALLENGE_RESOLUTION")


class ChallengeResolutionService:
    """
    Engine for resolving challenged findings and empirical evidentiary disputes.
    """

    @classmethod
    def resolve_challenge(
        cls,
        db: Session,
        case: Case,
        user: User,
        payload: ChallengeResolutionRequest
    ) -> ChallengeResolutionResponse:
        """
        Processes a challenge resolution request:
        1. Validates target finding in case.
        2. Resolves target evidence item.
        3. Validates storage budget against capability expansion.
        4. Passes through Governance Gate.
        5. Inserts AnalysisRequest and triggers Scheduler.
        6. Writes InvestigatorReviewRecord linking workflow.
        7. Returns ChallengeResolutionResponse.
        """
        # 1. Locate finding
        finding = db.query(DeterministicFinding).filter(
            DeterministicFinding.id == payload.finding_id,
            DeterministicFinding.case_id == case.id
        ).first()

        specialist_finding = None
        if not finding:
            specialist_finding = db.query(Finding).filter(
                Finding.id == payload.finding_id,
                Finding.case_id == case.id
            ).first()

        if not finding and not specialist_finding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target finding '{payload.finding_id}' not found in case '{case.id}'."
            )

        # 2. Locate target evidence item
        evidence_id = payload.evidence_id
        if not evidence_id:
            if finding and finding.supporting_evidence_ids:
                evidence_id = finding.supporting_evidence_ids[0]
            elif specialist_finding and specialist_finding.evidence_id:
                evidence_id = specialist_finding.evidence_id
            elif case.evidence_items:
                evidence_id = case.evidence_items[0].id

        if not evidence_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No associated evidence item found to execute resolution capability '{payload.selected_capability}' on."
            )

        evidence = db.query(EvidenceItem).filter(
            EvidenceItem.id == evidence_id,
            EvidenceItem.case_id == case.id
        ).first()

        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target evidence item '{evidence_id}' not found in case '{case.id}'."
            )

        evidence_size = evidence.size_bytes or (10 * 1024 * 1024)

        # 3. Storage Budget Check
        storage_est = StorageBudgetService.estimate_capability_storage(
            capability=payload.selected_capability,
            evidence_size_bytes=evidence_size,
            case_id=case.id,
            db=db
        )

        if not storage_est.is_admissible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Storage budget violation: {storage_est.warning_message} "
                    f"(Estimated needed: {storage_est.estimated_artifact_mb} MB, "
                    f"Safe available: {storage_est.safe_available_mb} MB)."
                )
            )

        # 4. Governance Gate Check
        gov_decision = GovernanceGateService.evaluate_governance(
            db=db,
            case_id=case.id,
            action_type="CHALLENGE_RESOLUTION",
            requesting_agent="INVESTIGATOR_REVIEW",
            target_resource_type="EVIDENCE",
            target_resource_id=evidence.id,
            parameters={
                "finding_id": payload.finding_id,
                "capability": payload.selected_capability,
                "evidentiary_gap": payload.evidentiary_gap,
                "justification": payload.justification,
                **payload.parameters
            },
            input_references={
                "finding_id": payload.finding_id,
                "evidence_id": evidence.id,
                "disputed_claim": payload.disputed_claim
            },
            user=user
        )

        if gov_decision.decision == GovernanceDecisionType.BLOCKED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Governance gate blocked challenge resolution: {gov_decision.reason}"
            )

        # 5. Locate or create active InvestigationPlan
        plan = db.query(InvestigationPlan).filter(
            InvestigationPlan.case_id == case.id
        ).order_by(InvestigationPlan.created_at.desc()).first()

        if not plan:
            plan = InvestigationPlan(
                id=str(uuid.uuid4()),
                case_id=case.id,
                title=f"Resolution Plan - Case {case.name}",
                objectives=["Empirical challenge dispute resolution and artifact verification"],
                status="PLANNED",
                created_by=user.id
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)

        # 6. Create AnalysisRequest with dynamic resource requirements
        task_key = f"RES_CHALLENGE_{payload.selected_capability.upper()}_{uuid.uuid4().hex[:6]}"
        req_disk_mb = max(100.0, storage_est.estimated_artifact_mb)
        analysis_request = AnalysisRequest(
            id=str(uuid.uuid4()),
            case_id=case.id,
            plan_id=plan.id,
            task_key=task_key,
            evidence_id=evidence.id,
            capability_id=payload.selected_capability,
            selected_tool_id=payload.selected_capability.lower(),
            resource_requirements={
                "cpu_cores": 1,
                "ram_mb": 512,
                "disk_mb": req_disk_mb
            },
            priority_level="CRITICAL",
            priority_score=0.95,
            timeout_seconds=300,
            retry_policy={"max_retries": 2, "retry_count": 0, "retry_delay_seconds": 30, "is_retryable": True},
            dependencies=[],
            scheduler_status="QUEUED"
        )
        db.add(analysis_request)
        db.commit()
        db.refresh(analysis_request)

        # Trigger scheduler evaluation loop
        try:
            ResourceAwareScheduler.evaluate_queue(db, plan_id=plan.id)
        except Exception as exc:
            logger.warning(f"Scheduler queue evaluation notice: {exc}")

        # 7. Record review state
        comment = (
            f"CHALLENGE RESOLUTION QUEUED | Gap: {payload.evidentiary_gap} | "
            f"Capability: {payload.selected_capability} | Justification: {payload.justification}"
        )
        review_req = InvestigatorReviewCreateRequest(
            target_type="FINDING",
            target_id=payload.finding_id,
            decision="CHALLENGE",
            challenge_category=payload.challenge_category or "EVIDENCE_ASSOCIATION",
            comment=comment,
            supporting_references=[evidence.id, analysis_request.id]
        )

        review = InvestigatorReviewService.submit_decision(
            db=db,
            case=case,
            user=user,
            payload=review_req,
            action_reference_id=analysis_request.id
        )

        # Update review record workflow action to RESOLUTION_QUEUED
        rec = db.query(InvestigatorReviewRecord).filter(InvestigatorReviewRecord.id == review.id).first()
        if rec:
            rec.resulting_workflow_action = "RESOLUTION_QUEUED"
            db.commit()

        return ChallengeResolutionResponse(
            finding_id=payload.finding_id,
            lifecycle_state=FindingLifecycleState.RESOLUTION_PENDING,
            challenge_review_id=review.id,
            governance_decision_id=gov_decision.id if hasattr(gov_decision, "id") else None,
            analysis_request_id=analysis_request.id,
            storage_budget_status=storage_est.status,
            estimated_storage_mb=storage_est.estimated_artifact_mb,
            workflow_status="QUEUED",
            message=f"Challenge resolution for finding '{payload.finding_id}' queued successfully via capability '{payload.selected_capability}'."
        )
