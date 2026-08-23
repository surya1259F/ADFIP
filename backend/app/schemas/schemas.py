from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

# Health & System Status
class HealthResponse(BaseModel):
    status: str = "ok"
    application: str = "ADFIR"
    version: str = "0.1.0"

class SystemStatusResponse(BaseModel):
    application: str
    version: str
    status: str
    platform: str
    logical_cpus: int
    max_concurrent_tasks: int
    active_tasks: int
    forensic_tools: Dict[str, Dict[str, Any]]

# Investigation Schemas
class InvestigationCreate(BaseModel):
    name: str
    description: Optional[str] = None

class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    evidence_count: Optional[int] = 0
    findings_count: Optional[int] = 0

# Evidence Intake Schemas
class EvidenceIntakeRequest(BaseModel):
    path: str
    notes: Optional[str] = None

class CustodyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_id: str
    event_type: str
    timestamp: datetime
    actor: str
    description: str
    source_path: Optional[str] = None
    destination_path: Optional[str] = None
    sha256: Optional[str] = None
    metadata_json: Dict[str, Any] = {}

class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    name: str
    original_path: str
    evidence_type: str
    size_bytes: float
    sha256: str
    mime_type: Optional[str] = "application/octet-stream"
    created_at: datetime
    modified_at: datetime
    intake_status: str
    integrity_status: str
    read_only_verified: bool
    notes: Optional[str] = None
    created_by: str

# Finding Schemas
class FindingCreate(BaseModel):
    evidence_id: Optional[str] = None
    agent: str
    tool: str
    finding_type: str
    title: str
    description: str
    confidence: Optional[float] = None
    timestamp: Optional[datetime] = None
    evidence_reference: Optional[str] = None
    raw_output_reference: Optional[str] = None

class FindingResponse(FindingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    verification_status: str
    created_at: datetime

# Planning, Correlation, Verification Schemas
class PlanTaskStep(BaseModel):
    step_id: str
    agent: str
    tool: str
    tool_available: bool
    evidence_id: Optional[str] = None
    evidence_name: Optional[str] = None
    action: str
    priority: int
    estimated_resource_cost: Dict[str, str] = {}

class InvestigationPlanResponse(BaseModel):
    investigation_id: str
    steps: List[PlanTaskStep]
    strategy_summary: str
    total_tasks: int
    status: str

class CorrelatedGroupResponse(BaseModel):
    dimension: str
    correlated_entity: str
    title: str
    description: str
    tools_involved: List[str]
    supporting_finding_ids: List[str]
    correlation_confidence: float

class VerificationResultResponse(BaseModel):
    finding_id: Optional[str] = None
    verification_status: str
    confidence_score: float
    reason: str

# Report Schema
class ReportResponse(BaseModel):
    title: str
    investigation_id: str
    executive_summary: str
    findings_count: int
    evidence_count: int
    full_report_markdown: str
    generated_at: str
