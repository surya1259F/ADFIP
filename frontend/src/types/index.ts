export interface Investigation {
  id: string;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
  evidence_count?: number;
  findings_count?: number;
}

export interface CustodyRecord {
  id: string;
  evidence_id: string;
  event_type: string;
  timestamp: string;
  actor: string;
  description: string;
  source_path?: string;
  destination_path?: string;
  sha256?: string;
  metadata_json: Record<string, any>;
}

export interface Evidence {
  id: string;
  investigation_id: string;
  name: string;
  original_path: string;
  evidence_type: string;
  size_bytes: number;
  sha256: string;
  mime_type?: string;
  created_at: string;
  modified_at: string;
  intake_status: string;
  integrity_status: string;
  read_only_verified: boolean;
  notes?: string;
  created_by: string;
}

export interface Finding {
  id: string;
  investigation_id: string;
  evidence_id?: string;
  agent: string;
  tool: string;
  finding_type: string;
  title: string;
  description: string;
  confidence?: number;
  timestamp?: string;
  evidence_reference?: string;
  verification_status: 'SUPPORTED' | 'UNSUPPORTED' | 'CONFLICTING' | 'UNVERIFIED';
  raw_output_reference?: string;
  created_at: string;
}

export interface PlanStep {
  step_id: string;
  agent: string;
  tool: string;
  tool_available: boolean;
  evidence_id?: string;
  evidence_name?: string;
  action: string;
  priority: number;
  estimated_resource_cost: Record<string, string>;
}

export interface InvestigationPlan {
  investigation_id: string;
  steps: PlanStep[];
  strategy_summary: string;
  total_tasks: number;
  status: string;
}

export interface CorrelatedGroup {
  dimension: string;
  correlated_entity: string;
  title: string;
  description: string;
  tools_involved: string[];
  supporting_finding_ids: string[];
  correlation_confidence: number;
}

export interface VerificationResult {
  finding_id?: string;
  verification_status: string;
  confidence_score: number;
  reason: string;
}

export interface Report {
  title: string;
  investigation_id: string;
  executive_summary: string;
  findings_count: number;
  evidence_count: number;
  full_report_markdown: string;
  generated_at: string;
}

export interface SystemStatus {
  application: string;
  version: string;
  status: string;
  platform: string;
  logical_cpus: number;
  max_concurrent_tasks: number;
  active_tasks: number;
  forensic_tools: Record<string, {
    name: string;
    available: boolean;
    version?: string;
    supported_evidence: string[];
  }>;
}
