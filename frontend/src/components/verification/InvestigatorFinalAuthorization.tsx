import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldCheck,
  ShieldAlert,
  Clock,
  User,
  FileCheck2,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Database,
  HelpCircle
} from 'lucide-react';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Textarea } from '../ui/Textarea';
import { Dialog } from '../ui/Dialog';
import { Skeleton } from '../ui/Skeleton';
import { formatTimestamp } from '../../lib/utils';
import type { InvestigatorDecision } from '../../types';

export type FinalDecisionOption =
  | 'CONFIRM'
  | 'REJECT'
  | 'INCONCLUSIVE'
  | 'REQUEST_MORE_EVIDENCE';

interface FinalOptionConfig {
  value: FinalDecisionOption;
  label: string;
  description: string;
  activeBorder: string;
  activeBg: string;
  activeText: string;
  badgeTone: 'success' | 'danger' | 'warning' | 'info';
}

const FINAL_OPTIONS: FinalOptionConfig[] = [
  {
    value: 'CONFIRM',
    label: 'CONFIRM',
    description: 'Confirm findings and authorize official report release',
    activeBorder: 'border-emerald-600 ring-2 ring-emerald-500/20',
    activeBg: 'bg-emerald-50/80',
    activeText: 'text-emerald-900',
    badgeTone: 'success',
  },
  {
    value: 'REJECT',
    label: 'REJECT',
    description: 'Reject the case findings for official release',
    activeBorder: 'border-rose-600 ring-2 ring-rose-500/20',
    activeBg: 'bg-rose-50/80',
    activeText: 'text-rose-900',
    badgeTone: 'danger',
  },
  {
    value: 'INCONCLUSIVE',
    label: 'INCONCLUSIVE',
    description: 'Record that the investigation does not support a definitive conclusion',
    activeBorder: 'border-amber-600 ring-2 ring-amber-500/20',
    activeBg: 'bg-amber-50/80',
    activeText: 'text-amber-900',
    badgeTone: 'warning',
  },
  {
    value: 'REQUEST_MORE_EVIDENCE',
    label: 'REQUEST MORE EVIDENCE',
    description: 'Additional evidence is required before final determination',
    activeBorder: 'border-sky-600 ring-2 ring-sky-500/20',
    activeBg: 'bg-sky-50/80',
    activeText: 'text-sky-900',
    badgeTone: 'info',
  },
];

interface InvestigatorFinalAuthorizationProps {
  caseId: string;
  findingIds?: string[];
  evidenceIds?: string[];
  onDecisionSuccess?: (decision: InvestigatorDecision) => void;
}

export const InvestigatorFinalAuthorization: React.FC<InvestigatorFinalAuthorizationProps> = ({
  caseId,
  findingIds = [],
  evidenceIds = [],
  onDecisionSuccess,
}) => {
  const qc = useQueryClient();
  const [selectedDecision, setSelectedDecision] = useState<FinalDecisionOption | null>(null);
  const [rationale, setRationale] = useState('');
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  // 1. Authoritative case decisions query
  const {
    data: decisions,
    isLoading: decisionsLoading,
    isError: decisionsError,
    error: decisionsFetchError,
  } = useQuery({
    queryKey: ['cases', caseId, 'decisions'],
    queryFn: () => casesService.getDecisions(caseId),
    enabled: !!caseId,
    staleTime: 5000,
  });

  const latestDecision = decisions && decisions.length > 0 ? decisions[0] : null;

  // 2. Authoritative decision mutation
  const recordMutation = useMutation({
    mutationFn: async () => {
      return casesService.recordDecision(caseId, {
        decision: selectedDecision!,
        rationale: rationale.trim(),
        finding_ids: findingIds,
        evidence_ids: evidenceIds,
      });
    },
    onSuccess: (newDecision) => {
      // Invalidate relevant queries per Section 11
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'decisions'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'reports', 'readiness'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'reports'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId] });

      setConfirmModalOpen(false);
      setRationale('');
      setSelectedDecision(null);
      setValidationError(null);

      setSuccessNotice(
        `Official case authorization '${newDecision.decision}' has been successfully recorded and signed.`
      );
      setTimeout(() => setSuccessNotice(null), 8000);

      if (onDecisionSuccess) {
        onDecisionSuccess(newDecision);
      }
    },
    onError: (err) => {
      setConfirmModalOpen(false);
      setValidationError(normalizeError(err));
    },
  });

  const handleOpenConfirm = () => {
    setValidationError(null);
    if (!selectedDecision) {
      setValidationError('Please select a final authorization decision.');
      return;
    }
    const cleanRationale = rationale.trim();
    if (!cleanRationale || cleanRationale.length < 3) {
      setValidationError('Mandatory rationale must be at least 3 characters in length.');
      return;
    }
    setConfirmModalOpen(true);
  };

  const handleConfirmSubmit = () => {
    if (!selectedDecision || rationale.trim().length < 3) return;
    recordMutation.mutate();
  };

  return (
    <Card className="bg-stone-50/70 border-stone-200/90 shadow-sm p-5 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-stone-200/80 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-slate-800 text-white rounded-md shadow-xs">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              Investigator Final Authorization
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Review the complete investigation and record the final human decision required for
            official forensic report release.
          </p>
        </div>

        {/* Current G14 Release Status Badge */}
        <div className="flex items-center gap-2 self-start">
          {decisionsLoading ? (
            <Skeleton className="h-6 w-28" />
          ) : latestDecision?.decision === 'CONFIRM' ? (
            <Badge tone="success" className="px-2.5 py-1 text-xs font-semibold gap-1.5 shadow-xs">
              <CheckCircle2 className="w-3.5 h-3.5" />
              G14 AUTHORIZED
            </Badge>
          ) : (
            <Badge tone="warning" className="px-2.5 py-1 text-xs font-semibold gap-1.5 shadow-xs">
              <ShieldAlert className="w-3.5 h-3.5" />
              G14 PENDING
            </Badge>
          )}
        </div>
      </div>

      {/* Success Notification */}
      {successNotice && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-start gap-2.5 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{successNotice}</div>
        </div>
      )}

      {/* Section A: Current Official Case Decision */}
      <div className="space-y-2">
        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          Current Recorded Case Decision
        </p>

        {decisionsLoading && <Skeleton className="h-20 w-full rounded-lg" />}

        {decisionsError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            {normalizeError(decisionsFetchError)}
          </div>
        )}

        {!decisionsLoading && !decisionsError && (
          <div className="bg-white border border-stone-200/90 rounded-lg p-3.5 space-y-3">
            {latestDecision ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-100 pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Decision:</span>
                    <Badge
                      tone={
                        latestDecision.decision === 'CONFIRM'
                          ? 'success'
                          : latestDecision.decision === 'REJECT'
                          ? 'danger'
                          : latestDecision.decision === 'INCONCLUSIVE'
                          ? 'warning'
                          : 'info'
                      }
                      className="font-bold text-xs px-2 py-0.5 font-mono"
                    >
                      {latestDecision.decision}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-4 text-[11px] text-slate-500">
                    <div className="flex items-center gap-1">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span className="font-medium text-slate-700">
                        {latestDecision.investigator_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 font-mono">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>{formatTimestamp(latestDecision.timestamp)}</span>
                    </div>
                  </div>
                </div>

                {/* Rationale */}
                <div className="text-xs">
                  <span className="text-slate-400 block text-[11px] mb-0.5">Official Rationale:</span>
                  <p className="text-slate-800 bg-stone-50 p-2.5 rounded border border-stone-150 leading-relaxed whitespace-pre-wrap">
                    {latestDecision.rationale}
                  </p>
                </div>

                {/* Associated Scope IDs */}
                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500 pt-1 border-t border-stone-100">
                  <div className="flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    <span>Associated Findings:</span>
                    <span className="font-mono font-medium text-slate-700">
                      {latestDecision.finding_ids?.length ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Database className="w-3.5 h-3.5 text-slate-400" />
                    <span>Associated Evidence:</span>
                    <span className="font-mono font-medium text-slate-700">
                      {latestDecision.evidence_ids?.length ?? 0}
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="py-3 px-2 flex items-center justify-between text-xs text-slate-600">
                <div className="flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-amber-500 shrink-0" />
                  <span>
                    Decision: <strong className="text-slate-800">NOT YET RECORDED</strong>
                  </span>
                </div>
                <span className="text-[11px] text-slate-400">
                  Case decision is currently 'NONE'. G14 report release gate requires 'CONFIRM'.
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Section B: Record New Official Decision */}
      <div className="space-y-3 pt-2 border-t border-stone-200/80">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Record New Final Authorization
          </p>
          <span className="text-[11px] text-slate-400">
            Finding review is separate; this decision governs full case release.
          </span>
        </div>

        {/* 4 Decision Option Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {FINAL_OPTIONS.map((opt) => {
            const isSelected = selectedDecision === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  setSelectedDecision(opt.value);
                  setValidationError(null);
                }}
                className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                  isSelected
                    ? `${opt.activeBorder} ${opt.activeBg}`
                    : 'bg-white border-stone-200 hover:border-stone-300 hover:bg-stone-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`text-xs font-bold font-mono tracking-tight ${
                      isSelected ? opt.activeText : 'text-slate-800'
                    }`}
                  >
                    {opt.label}
                  </span>
                  <Badge tone={opt.badgeTone} className="text-[10px] py-0 px-1.5">
                    {opt.value}
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500 leading-snug">{opt.description}</p>
              </button>
            );
          })}
        </div>

        {/* Mandatory Rationale Field */}
        <div className="space-y-1 pt-1">
          <Textarea
            label="Investigator Rationale (Mandatory, minimum 3 characters)"
            placeholder="Explain the basis for your final investigative decision..."
            value={rationale}
            onChange={(e) => {
              setRationale(e.target.value);
              if (validationError) setValidationError(null);
            }}
            rows={3}
            error={validationError || undefined}
          />
        </div>

        {/* Submit Action */}
        <div className="flex items-center justify-between pt-2">
          <div className="text-[11px] text-slate-500">
            {findingIds.length > 0 && (
              <span>Attaching {findingIds.length} finding(s) and {evidenceIds.length} evidence item(s).</span>
            )}
          </div>
          <Button
            type="button"
            variant="primary"
            size="md"
            icon={<FileCheck2 className="w-4 h-4" />}
            onClick={handleOpenConfirm}
            disabled={!selectedDecision || rationale.trim().length < 3 || recordMutation.isPending}
          >
            Sign & Record Final Decision
          </Button>
        </div>
      </div>

      {/* Confirmation Modal */}
      <Dialog
        open={confirmModalOpen}
        onClose={() => setConfirmModalOpen(false)}
        title="Confirm Final Investigator Authorization"
        size="md"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2.5 text-amber-900">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold">
                You are about to record: <span className="font-mono">{selectedDecision}</span>
              </p>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                This decision will be stored as the official case-level investigator decision and will
                be used by the forensic report release gate (G14).
              </p>
              <p className="text-[10px] text-amber-700 italic">
                This action cannot be silently undone or replaced by the system.
              </p>
            </div>
          </div>

          <div className="bg-stone-50 p-3 rounded border border-stone-200 space-y-2">
            <div>
              <span className="text-slate-400 block text-[11px]">Proposed Decision:</span>
              <span className="font-bold font-mono text-slate-800 text-sm">
                {selectedDecision}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Rationale:</span>
              <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                {rationale.trim()}
              </p>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConfirmModalOpen(false)}
              disabled={recordMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant={selectedDecision === 'CONFIRM' ? 'primary' : 'danger'}
              size="sm"
              loading={recordMutation.isPending}
              onClick={handleConfirmSubmit}
            >
              Confirm & Record
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  );
};

