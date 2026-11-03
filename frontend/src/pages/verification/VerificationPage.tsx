import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, HardDrive } from 'lucide-react';
import { apiClient, normalizeError } from '../../services/client';
import { evidenceService } from '../../services/evidence';
import { InvestigatorFinalAuthorization } from '../../components/verification/InvestigatorFinalAuthorization';
import { Card } from '../../components/ui/Card';
import { StatusBadge, Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { Textarea } from '../../components/ui/Textarea';
import { Dialog } from '../../components/ui/Dialog';
import { formatConfidence } from '../../lib/utils';
import type {
  ReviewItemsResponse,
  ReviewFindingItem,
  InvestigatorDecisionType,
  StorageBudgetResponse,
  ResourceEstimationResponse,
  ChallengeResolutionResponse,
} from '../../types';

const DECISIONS: {
  value: InvestigatorDecisionType;
  label: string;
  activeClass: string;
}[] = [
  {
    value: 'ACCEPT',
    label: 'Accept',
    activeClass: 'border-emerald-600 bg-emerald-50 text-emerald-700',
  },
  {
    value: 'CHALLENGE',
    label: 'Challenge',
    activeClass: 'border-amber-600 bg-amber-50 text-amber-700',
  },
  {
    value: 'REJECT',
    label: 'Reject',
    activeClass: 'border-red-600 bg-red-50 text-red-700',
  },
  {
    value: 'REQUEST_MORE_EVIDENCE',
    label: 'Request More Evidence',
    activeClass: 'border-blue-600 bg-blue-50 text-blue-700',
  },
];

const CHALLENGE_CATEGORIES = [
  { value: 'EVIDENCE_ASSOCIATION', label: 'Evidence Association' },
  { value: 'TOOL_RESULT', label: 'Tool Result Anomaly' },
  { value: 'RULE_RELEVANCE', label: 'Rule Relevance' },
  { value: 'ARTIFACT_INTERPRETATION', label: 'Artifact Interpretation' },
  { value: 'CLASSIFICATION', label: 'Evidence / Fact Classification' },
  { value: 'CONFIDENCE', label: 'Confidence Score Discrepancy' },
  { value: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient Supporting Evidence' },
  { value: 'CONTRADICTORY_EVIDENCE', label: 'Contradictory Evidence Identified' },
  { value: 'TIMELINE', label: 'Timeline Inconsistency' },
  { value: 'PROVENANCE', label: 'Provenance Lineage Defect' },
  { value: 'AI_INFERENCE', label: 'Unsupported AI Inference' },
  { value: 'OTHER', label: 'Other Methodological Challenge' },
];

const RESOLUTION_CAPABILITIES = [
  { value: 'YARA_SCAN', label: 'YARA_SCAN — Static Byte Signature & Rule Scanning' },
  { value: 'STRINGS_ANALYSIS', label: 'STRINGS_ANALYSIS — ASCII & Unicode String Carving' },
  { value: 'TSK_FLS', label: 'TSK_FLS — Filesystem Inode & Directory Structure' },
  { value: 'VOLATILITY_PSLIST', label: 'VOLATILITY_PSLIST — Volatility3 Memory Process Enumeration' },
  { value: 'METADATA_EXTRACTION', label: 'METADATA_EXTRACTION — Structural File Metadata Parsing' },
  { value: 'HASHING', label: 'HASHING — Cryptographic SHA-256 Byte Verification' },
];

const ReviewFindingRow: React.FC<{
  finding: ReviewFindingItem;
  caseId: string;
  onOpenResolution: (finding: ReviewFindingItem) => void;
}> = ({ finding, caseId, onOpenResolution }) => {
  const [reviewOpen, setReviewOpen] = useState(false);
  const [decision, setDecision] = useState<InvestigatorDecisionType>('ACCEPT');
  const [challengeCategory, setChallengeCategory] = useState<string>('EVIDENCE_ASSOCIATION');
  const [comment, setComment] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/cases/${caseId}/review/decisions`, {
        target_type: 'FINDING',
        target_id: finding.id,
        decision,
        challenge_category: decision === 'CHALLENGE' ? challengeCategory : undefined,
        comment: comment.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'review'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'findings'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'reports'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId] });
      setReviewOpen(false);
      setComment('');
      setErr(null);
    },
    onError: (e) => setErr(normalizeError(e)),
  });

  const latestDecision = finding.latest_decision;
  const isChallenged = latestDecision === 'CHALLENGE';

  return (
    <>
      <tr className="border-b border-stone-50 hover:bg-stone-50">
        <td className="px-4 py-2.5">
          <p className="text-sm font-medium text-slate-800">{finding.title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-mono text-slate-400">
              {finding.id.slice(0, 8)}
            </span>
            {finding.lifecycle_state && (
              <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded">
                {finding.lifecycle_state}
              </span>
            )}
          </div>
        </td>
        <td className="px-4 py-2.5 text-xs text-slate-600">
          {formatConfidence(finding.confidence ?? null)}
        </td>
        <td className="px-4 py-2.5">
          {latestDecision ? (
            <StatusBadge status={latestDecision} />
          ) : (
            <Badge tone="warning">Pending Review</Badge>
          )}
        </td>
        <td className="px-4 py-2.5 text-right space-x-2">
          {isChallenged && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onOpenResolution(finding)}
            >
              Resolve
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setReviewOpen(true)}
          >
            Review
          </Button>
        </td>
      </tr>

      <Dialog
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        title="Review Finding"
        description={finding.title}
        size="md"
      >
        <div className="space-y-4">
          {err && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {err}
            </p>
          )}
          <div>
            <p className="text-xs text-slate-700 font-medium mb-2">
              Investigator Decision
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DECISIONS.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  className={`px-3 py-2 border rounded-md text-xs font-medium transition-colors text-left ${
                    decision === d.value
                      ? d.activeClass
                      : 'border-stone-200 text-slate-600 hover:border-stone-300 hover:bg-stone-50'
                  }`}
                  onClick={() => setDecision(d.value)}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {decision === 'CHALLENGE' && (
            <div>
              <label className="text-xs text-slate-700 font-medium block mb-1.5">
                Challenge Category
              </label>
              <select
                value={challengeCategory}
                onChange={(e) => setChallengeCategory(e.target.value)}
                className="w-full text-xs bg-white border border-stone-200 rounded-md p-2 text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                {CHALLENGE_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <Textarea
            label="Comment (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Provide rationale for your decision..."
            rows={3}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setReviewOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Submit Decision
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
};

export const VerificationPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const qc = useQueryClient();

  // Resolution Modal State
  const [resolutionTarget, setResolutionTarget] = useState<ReviewFindingItem | null>(null);
  const [resolutionCapability, setResolutionCapability] = useState<string>('YARA_SCAN');
  const [resolutionGap, setResolutionGap] = useState<string>('');
  const [resolutionJustification, setResolutionJustification] = useState<string>('');
  const [resolutionErr, setResolutionErr] = useState<string | null>(null);

  // Queries
  const { data: reviewItems, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'review'],
    queryFn: async () => {
      const res = await apiClient.get<ReviewItemsResponse>(
        `/cases/${caseId}/review/items`
      );
      return res.data;
    },
    enabled: !!caseId,
  });

  const { data: storageBudget } = useQuery({
    queryKey: ['cases', caseId, 'storage-budget'],
    queryFn: async () => {
      const res = await apiClient.get<StorageBudgetResponse>(
        `/cases/${caseId}/storage/budget`
      );
      return res.data;
    },
    enabled: !!caseId,
  });

  const { data: storageEstimate } = useQuery({
    queryKey: ['cases', caseId, 'storage-estimate', resolutionCapability, resolutionTarget?.id],
    queryFn: async () => {
      if (!resolutionTarget) return null;
      const res = await apiClient.post<ResourceEstimationResponse>(
        `/cases/${caseId}/storage/estimate`,
        {
          capability: resolutionCapability,
          evidence_id: resolutionTarget.supporting_evidence_ids?.[0] || null,
        }
      );
      return res.data;
    },
    enabled: !!caseId && !!resolutionTarget,
  });

  const { data: evidenceList } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  // Challenge Resolution Mutation
  const resolveMutation = useMutation({
    mutationFn: async () => {
      if (!resolutionTarget) return;
      const res = await apiClient.post<ChallengeResolutionResponse>(
        `/cases/${caseId}/review/challenge/resolve`,
        {
          finding_id: resolutionTarget.id,
          disputed_claim: resolutionTarget.title,
          evidentiary_gap: resolutionGap.trim(),
          selected_capability: resolutionCapability,
          evidence_id: resolutionTarget.supporting_evidence_ids?.[0] || null,
          justification: resolutionJustification.trim(),
        }
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'review'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'storage-budget'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId] });
      setResolutionTarget(null);
      setResolutionGap('');
      setResolutionJustification('');
      setResolutionErr(null);
    },
    onError: (e) => setResolutionErr(normalizeError(e)),
  });

  const allFindings = reviewItems?.deterministic_findings || [];
  const pendingFindings = allFindings.filter((f) => !f.latest_decision);
  const reviewedFindings = allFindings.filter((f) => !!f.latest_decision);
  const findingIds = allFindings.map((f) => f.id);
  const evidenceIds = (evidenceList || []).map((e) => e.id);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <SectionHeader
        title="Investigator Review & Authorization"
        description="Two-tier governance: verify granular forensic findings, resolve challenged claims, and sign the final release authorization (Gate 14)."
      />

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}
      {isLoading && <Skeleton className="h-48" />}

      {!isLoading && !isError && reviewItems && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <p className="text-lg font-bold text-slate-900">
                {reviewItems.total_reviewable_claims}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">Reviewable Claims</p>
            </Card>
            <Card>
              <p className="text-lg font-bold text-amber-600">
                {reviewItems.pending_claims_count}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">Pending Review</p>
            </Card>
            <Card>
              <p className="text-lg font-bold text-emerald-600">
                {reviewItems.reviewed_claims_count}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">Reviewed</p>
            </Card>
          </div>

          {/* Storage Budget & Safety Reserve Card */}
          {storageBudget && (
            <Card>
              <div className="flex items-center justify-between pb-3 border-b border-stone-100">
                <div className="flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-slate-600" />
                  <span className="text-xs font-semibold text-slate-800">
                    Host Storage Budget &amp; Safety Reserve
                  </span>
                </div>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                    storageBudget.status === 'SAFE'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : storageBudget.status === 'WARNING'
                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                      : 'bg-red-50 text-red-700 border-red-200'
                  }`}
                >
                  {storageBudget.status}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-4 pt-3 text-xs">
                <div>
                  <p className="text-[10px] text-slate-400 font-mono">SAFE HEADROOM</p>
                  <p className="text-sm font-bold text-slate-800">{storageBudget.safe_available_mb} MB</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 font-mono">SAFETY RESERVE</p>
                  <p className="text-sm font-bold text-slate-600">{storageBudget.safety_reserve_mb} MB</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 font-mono">WORKSPACE USED</p>
                  <p className="text-sm font-semibold text-slate-700">{storageBudget.workspace_used_mb} MB</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 font-mono">VAULT EVIDENCE</p>
                  <p className="text-sm font-semibold text-slate-700">{storageBudget.vault_used_mb} MB</p>
                </div>
              </div>
            </Card>
          )}

          {/* Tier 1: Granular Finding Review */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-stone-200 pb-2">
              <div>
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Tier 1: Ground Truth Finding Review
                </h3>
                <p className="text-[11px] text-slate-500">
                  Assess and verify individual findings (ACCEPT / CHALLENGE / REJECT / REQUEST MORE EVIDENCE).
                </p>
              </div>
            </div>

            {allFindings.length === 0 && (
              <EmptyState
                icon={<ShieldCheck className="w-8 h-8" />}
                title="No findings to review"
                description="Findings will appear here after forensic analysis completes."
              />
            )}

            {pendingFindings.length > 0 && (
              <Card padding={false}>
                <div className="px-4 py-2.5 border-b border-stone-100 flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-600">
                    Pending Review
                  </p>
                  <Badge tone="warning">{pendingFindings.length}</Badge>
                </div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-stone-100">
                      <th className="text-left px-4 py-2 text-slate-500 font-medium">
                        Finding
                      </th>
                      <th className="text-left px-4 py-2 text-slate-500 font-medium">
                        Confidence
                      </th>
                      <th className="text-left px-4 py-2 text-slate-500 font-medium">
                        Decision
                      </th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {pendingFindings.map((f) => (
                      <ReviewFindingRow
                        key={f.id}
                        finding={f}
                        caseId={caseId!}
                        onOpenResolution={(target) => setResolutionTarget(target)}
                      />
                    ))}
                  </tbody>
                </table>
              </Card>
            )}

            {reviewedFindings.length > 0 && (
              <Card padding={false}>
                <div className="px-4 py-2.5 border-b border-stone-100 flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-600">
                    Reviewed
                  </p>
                  <Badge tone="success">{reviewedFindings.length}</Badge>
                </div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-stone-100">
                      <th className="text-left px-4 py-2 text-slate-500 font-medium">
                        Finding
                      </th>
                      <th className="text-left px-4 py-2 text-slate-500 font-medium">
                        Confidence
                      </th>
                      <th className="text-left px-4 py-2 text-slate-500 font-medium">
                        Decision
                      </th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {reviewedFindings.map((f) => (
                      <ReviewFindingRow
                        key={f.id}
                        finding={f}
                        caseId={caseId!}
                        onOpenResolution={(target) => setResolutionTarget(target)}
                      />
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>

          {/* Tier 2: Dedicated Case-Level Release Authorization (G14 Gate) */}
          <div className="pt-2">
            <InvestigatorFinalAuthorization
              caseId={caseId!}
              findingIds={findingIds}
              evidenceIds={evidenceIds}
            />
          </div>

          {/* Challenge Resolution Dialog */}
          {resolutionTarget && (
            <Dialog
              open={!!resolutionTarget}
              onClose={() => setResolutionTarget(null)}
              title="Resolve Challenged Finding"
              description={`Empirically settle dispute for "${resolutionTarget.title}"`}
              size="lg"
            >
              <div className="space-y-4">
                {resolutionErr && (
                  <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
                    {resolutionErr}
                  </p>
                )}

                <div>
                  <label className="text-xs text-slate-700 font-medium block mb-1">
                    Select Forensic Resolution Capability
                  </label>
                  <select
                    value={resolutionCapability}
                    onChange={(e) => setResolutionCapability(e.target.value)}
                    className="w-full text-xs bg-white border border-stone-200 rounded-md p-2 text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-400"
                  >
                    {RESOLUTION_CAPABILITIES.map((cap) => (
                      <option key={cap.value} value={cap.value}>
                        {cap.label}
                      </option>
                    ))}
                  </select>
                </div>

                {storageEstimate && (
                  <div className="p-3 bg-stone-50 rounded border border-stone-200 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500 font-medium">Storage Pre-Flight Check:</span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                          storageEstimate.status === 'SAFE'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : storageEstimate.status === 'WARNING'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-red-50 text-red-700 border-red-200'
                        }`}
                      >
                        {storageEstimate.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-slate-600 pt-1">
                      <div>Est. Expansion: <strong>{storageEstimate.estimated_artifact_mb} MB</strong></div>
                      <div>Safe Available: <strong>{storageEstimate.safe_available_mb} MB</strong></div>
                    </div>
                    {storageEstimate.warning_message && (
                      <p className="text-amber-600 text-[11px] pt-1">{storageEstimate.warning_message}</p>
                    )}
                  </div>
                )}

                <div>
                  <Textarea
                    label="Identified Evidentiary Gap (Mandatory)"
                    value={resolutionGap}
                    onChange={(e) => setResolutionGap(e.target.value)}
                    placeholder="Describe what corroborating evidence is missing or contradicted..."
                    rows={2}
                  />
                </div>

                <div>
                  <Textarea
                    label="Resolution Justification (Mandatory)"
                    value={resolutionJustification}
                    onChange={(e) => setResolutionJustification(e.target.value)}
                    placeholder="Explain why this capability will definitively settle the challenge..."
                    rows={2}
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setResolutionTarget(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={!resolutionGap.trim() || !resolutionJustification.trim() || (storageEstimate ? !storageEstimate.is_admissible : false)}
                    loading={resolveMutation.isPending}
                    onClick={() => resolveMutation.mutate()}
                  >
                    Queue Resolution Task
                  </Button>
                </div>
              </div>
            </Dialog>
          )}
        </>
      )}
    </div>
  );
};
