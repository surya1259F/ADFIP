import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
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

const ReviewFindingRow: React.FC<{
  finding: ReviewFindingItem;
  caseId: string;
}> = ({ finding, caseId }) => {
  const [reviewOpen, setReviewOpen] = useState(false);
  const [decision, setDecision] = useState<InvestigatorDecisionType>('ACCEPT');
  const [comment, setComment] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/cases/${caseId}/review/decisions`, {
        target_type: 'FINDING',
        target_id: finding.id,
        decision,
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

  return (
    <>
      <tr className="border-b border-stone-50 hover:bg-stone-50">
        <td className="px-4 py-2.5">
          <p className="text-sm font-medium text-slate-800">{finding.title}</p>
          <p className="text-[10px] font-mono text-slate-400">
            {finding.id.slice(0, 8)}
          </p>
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
        <td className="px-4 py-2.5 text-right">
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

  const { data: evidenceList } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
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
        description="Two-tier governance: verify granular forensic findings and sign the final case release authorization (G14)."
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
                      <ReviewFindingRow key={f.id} finding={f} caseId={caseId!} />
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
                      <ReviewFindingRow key={f.id} finding={f} caseId={caseId!} />
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
        </>
      )}
    </div>
  );
};

