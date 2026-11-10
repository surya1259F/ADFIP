import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  HelpCircle,
  AlertTriangle,
  FileQuestion,
  CheckCircle2,
  Edit3,
  MessageSquare,
  Search,
  XCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Select } from '../ui/Select';
import { Textarea } from '../ui/Textarea';
import { formatTimestamp } from '../../lib/utils';
import type {
  ForensicAssessment,
  AssessmentDecisionType,
  AttackClassification,
} from '../../types';

interface ForensicAssessmentCardProps {
  assessment: ForensicAssessment;
  onRecordDecision: (payload: {
    decision: AssessmentDecisionType;
    rationale: string;
    edited_classification?: string;
    additional_analysis_requested?: string;
  }) => Promise<void>;
  isSubmitting?: boolean;
}

const classificationConfig: Record<
  AttackClassification,
  { label: string; badge: string; icon: React.ReactNode; desc: string }
> = {
  CONFIRMED_ATTACK: {
    label: 'Confirmed Attack',
    badge: 'bg-red-100 text-red-800 border-red-300',
    icon: <ShieldAlert className="w-5 h-5 text-red-600" />,
    desc: 'Empirically supported by corroborated forensic artifacts and verified findings.',
  },
  LIKELY_ATTACK: {
    label: 'Likely Attack',
    badge: 'bg-orange-100 text-orange-800 border-orange-300',
    icon: <AlertTriangle className="w-5 h-5 text-orange-600" />,
    desc: 'Strong observable indicators present with minor corroboration gaps.',
  },
  INCONCLUSIVE: {
    label: 'Inconclusive',
    badge: 'bg-amber-100 text-amber-800 border-amber-300',
    icon: <HelpCircle className="w-5 h-5 text-amber-600" />,
    desc: 'Ambiguous or contradictory artifacts observed; further analysis required.',
  },
  NO_ATTACK_OBSERVED: {
    label: 'No Attack Observed',
    badge: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    icon: <ShieldCheck className="w-5 h-5 text-emerald-600" />,
    desc: 'Exhaustive tool analysis of targeted evidence revealed no malicious indicators.',
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Insufficient Evidence',
    badge: 'bg-slate-100 text-slate-800 border-slate-300',
    icon: <FileQuestion className="w-5 h-5 text-slate-600" />,
    desc: 'Submitted evidence volume or execution depth is inadequate to form a conclusion.',
  },
};

const decisionConfig: Record<
  AssessmentDecisionType,
  { label: string; badge: string }
> = {
  ACCEPT: { label: 'Accepted by Investigator', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  EDIT: { label: 'Edited by Investigator', badge: 'bg-blue-50 text-blue-700 border-blue-200' },
  CHALLENGE: { label: 'Challenged by Investigator', badge: 'bg-amber-50 text-amber-700 border-amber-200' },
  REQUEST_MORE_EVIDENCE: { label: 'Additional Evidence Requested', badge: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  REJECT: { label: 'Rejected by Investigator', badge: 'bg-rose-50 text-rose-700 border-rose-200' },
};

export const ForensicAssessmentCard: React.FC<ForensicAssessmentCardProps> = ({
  assessment,
  onRecordDecision,
  isSubmitting = false,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [activeDecisionType, setActiveDecisionType] = useState<AssessmentDecisionType>('ACCEPT');
  const [rationale, setRationale] = useState('');
  const [editedClassification, setEditedClassification] = useState<string>(
    assessment.classification
  );
  const [additionalAnalysis, setAdditionalAnalysis] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const currentClass = classificationConfig[assessment.classification] || classificationConfig.INSUFFICIENT_EVIDENCE;
  const score = assessment.evidence_strength_score;

  const openDecisionModal = (type: AssessmentDecisionType) => {
    setActiveDecisionType(type);
    setRationale('');
    setErrorMsg('');
    setDialogOpen(true);
  };

  const handleConfirmDecision = async () => {
    if (!rationale.trim()) {
      setErrorMsg('An investigator rationale is strictly required to record this authority decision.');
      return;
    }
    try {
      await onRecordDecision({
        decision: activeDecisionType,
        rationale: rationale.trim(),
        edited_classification: activeDecisionType === 'EDIT' ? editedClassification : undefined,
        additional_analysis_requested: activeDecisionType === 'REQUEST_MORE_EVIDENCE' ? additionalAnalysis.trim() : undefined,
      });
      setDialogOpen(false);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Failed to record decision');
    }
  };

  return (
    <Card className="border-stone-300 shadow-sm overflow-hidden mb-6">
      <div className="bg-gradient-to-r from-stone-900 via-slate-800 to-stone-900 text-white p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/10 rounded-lg backdrop-blur-sm">
              {currentClass.icon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase tracking-wider text-slate-300 font-medium">
                  Forensic Assessment (AI Synthesis)
                </span>
                <span className="text-[10px] bg-slate-700 px-2 py-0.5 rounded text-slate-300">
                  Methodology v{assessment.methodology_version}
                </span>
              </div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
                {currentClass.label}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <span className="text-[11px] text-slate-300 uppercase tracking-wide block">
                Evidence-Strength Score
              </span>
              <div className="flex items-baseline justify-end gap-1">
                <span className="text-2xl font-black text-white">{score.toFixed(1)}</span>
                <span className="text-xs text-slate-400">/ 100</span>
              </div>
            </div>

            <div className="w-16 h-16 rounded-full border-4 border-slate-700 flex items-center justify-center bg-slate-800 relative">
              <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 36 36">
                <path
                  className="text-slate-700"
                  strokeWidth="3.5"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className={score >= 60 ? 'text-rose-500' : score >= 30 ? 'text-amber-400' : 'text-emerald-400'}
                  strokeDasharray={`${Math.min(100, Math.max(0, score))}, 100`}
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="absolute text-[11px] font-bold text-white">
                {Math.round(score)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Investigator Decision Status Banner */}
      <div className="bg-stone-50 border-b border-stone-200 px-5 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold text-slate-700">Investigator Authority Decision:</span>
          {assessment.investigator_decision ? (
            <span
              className={`px-2 py-0.5 rounded border text-[11px] font-bold ${
                decisionConfig[assessment.investigator_decision]?.badge || 'bg-slate-100'
              }`}
            >
              {decisionConfig[assessment.investigator_decision]?.label || assessment.investigator_decision}
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded border border-amber-300 bg-amber-50 text-amber-800 text-[11px] font-medium">
              Pending Investigator Review
            </span>
          )}
          {assessment.decided_at && (
            <span className="text-slate-400 text-[11px]">
              • {formatTimestamp(assessment.decided_at)}
            </span>
          )}
        </div>

        {/* Action buttons for investigator */}
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7 text-emerald-700 border-emerald-300 hover:bg-emerald-50"
            onClick={() => openDecisionModal('ACCEPT')}
          >
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
            Accept
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7 text-blue-700 border-blue-300 hover:bg-blue-50"
            onClick={() => openDecisionModal('EDIT')}
          >
            <Edit3 className="w-3.5 h-3.5 mr-1" />
            Edit
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7 text-amber-700 border-amber-300 hover:bg-amber-50"
            onClick={() => openDecisionModal('CHALLENGE')}
          >
            <MessageSquare className="w-3.5 h-3.5 mr-1" />
            Challenge
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7 text-indigo-700 border-indigo-300 hover:bg-indigo-50"
            onClick={() => openDecisionModal('REQUEST_MORE_EVIDENCE')}
          >
            <Search className="w-3.5 h-3.5 mr-1" />
            Request More Evidence
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs h-7 text-rose-700 border-rose-300 hover:bg-rose-50"
            onClick={() => openDecisionModal('REJECT')}
          >
            <XCircle className="w-3.5 h-3.5 mr-1" />
            Reject
          </Button>
        </div>
      </div>

      {assessment.investigator_rationale && (
        <div className="px-5 py-2.5 bg-white border-b border-stone-200 text-xs">
          <span className="font-semibold text-slate-700">Investigator Rationale: </span>
          <span className="text-slate-600 italic">{assessment.investigator_rationale}</span>
        </div>
      )}

      {/* Main Breakdown Section */}
      <div className="p-5 space-y-4">
        {/* Score Breakdown Bars */}
        <div>
          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2.5">
            Deterministic Evidence-Strength Factors
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Relevance', val: assessment.score_breakdown.relevance, max: 20 },
              { label: 'Source Reliability', val: assessment.score_breakdown.source_reliability, max: 15 },
              { label: 'Directness', val: assessment.score_breakdown.directness, max: 15 },
              { label: 'Corroboration', val: assessment.score_breakdown.corroboration, max: 15 },
              { label: 'Timeline Consistency', val: assessment.score_breakdown.timeline_consistency, max: 10 },
              { label: 'Evidence Integrity', val: assessment.score_breakdown.evidence_integrity, max: 10 },
              { label: 'Investigation Coverage', val: assessment.score_breakdown.investigation_coverage, max: 15 },
              { label: 'Penalties Deducted', val: -assessment.score_breakdown.penalties, max: 20, isPenalty: true },
            ].map((f) => (
              <div key={f.label} className="bg-stone-50 border border-stone-200 rounded p-2.5 text-xs">
                <div className="flex justify-between items-center text-[11px] mb-1">
                  <span className="text-slate-600 font-medium">{f.label}</span>
                  <span className={`font-mono font-bold ${f.isPenalty && f.val < 0 ? 'text-rose-600' : 'text-slate-800'}`}>
                    {f.val > 0 ? `+${f.val.toFixed(1)}` : f.val.toFixed(1)}
                  </span>
                </div>
                <div className="w-full bg-stone-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${f.isPenalty ? 'bg-rose-500' : 'bg-slate-700'}`}
                    style={{ width: `${Math.min(100, (Math.abs(f.val) / f.max) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Investigation Completeness */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3.5 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="text-xs space-y-1">
            <span className="font-bold text-slate-800">Investigation Completeness Metrics:</span>
            <div className="flex flex-wrap items-center gap-3 text-slate-600">
              <span>Total Requirements: <strong className="text-slate-900">{assessment.investigation_completeness.total_requirements}</strong></span>
              <span>Answered: <strong className="text-emerald-700">{assessment.investigation_completeness.completed_requirements}</strong></span>
              <span>Partial: <strong className="text-amber-700">{assessment.investigation_completeness.partially_completed_requirements}</strong></span>
              <span>Unanswered: <strong className="text-rose-700">{assessment.investigation_completeness.unanswered_requirements}</strong></span>
              {assessment.investigation_completeness.failed_tasks > 0 && (
                <span className="text-rose-600 font-bold">Failed Tasks: {assessment.investigation_completeness.failed_tasks}</span>
              )}
            </div>
          </div>
          <div className="text-right">
            <span className="text-xs text-slate-500 block">Overall Coverage</span>
            <span className="text-lg font-black text-slate-800">
              {assessment.investigation_completeness.percentage.toFixed(0)}%
            </span>
          </div>
        </div>

        {/* Toggleable Grounded Details & Limitations */}
        <div className="pt-2">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
          >
            {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            {showDetails ? 'Hide Detailed Observations & Limitations' : 'View Grounded Observations & Limitations'}
          </button>

          {showDetails && (
            <div className="mt-3 space-y-3 text-xs bg-stone-50 border border-stone-200 rounded-lg p-4">
              {assessment.ai_synthesis && (
                <div>
                  <h5 className="font-bold text-slate-700 mb-1">AI Synthesis & Hypothesis</h5>
                  <p className="text-slate-600 leading-relaxed bg-white border border-stone-200 p-3 rounded">
                    {assessment.ai_synthesis}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h5 className="font-bold text-emerald-800 mb-1 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Supporting Grounded Observations ({assessment.supporting_observations.length})
                  </h5>
                  {assessment.supporting_observations.length === 0 ? (
                    <p className="text-slate-400 italic">No direct malicious indicators found in current evidence.</p>
                  ) : (
                    <ul className="space-y-1 text-slate-600">
                      {assessment.supporting_observations.map((obs, idx) => (
                        <li key={idx} className="bg-white p-2 rounded border border-stone-200">
                          <strong className="text-slate-800">{obs.title || obs.id}</strong>: {obs.description}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <h5 className="font-bold text-amber-800 mb-1 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> Contradictory Observations & Limitations
                  </h5>
                  {assessment.contradictory_observations.length === 0 && assessment.investigation_limitations.length === 0 ? (
                    <p className="text-slate-400 italic">No contradictory evidence or known limitations identified.</p>
                  ) : (
                    <div className="space-y-2">
                      {assessment.contradictory_observations.map((obs, idx) => (
                        <div key={idx} className="bg-amber-50 text-amber-800 p-2 rounded border border-amber-200">
                          <strong>{obs.title}</strong>: {obs.description}
                        </div>
                      ))}
                      {assessment.investigation_limitations.map((lim, idx) => (
                        <div key={idx} className="bg-stone-100 text-stone-700 p-2 rounded border border-stone-200">
                          {lim}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Decision Recording Modal */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={`Record Authority Decision: ${decisionConfig[activeDecisionType]?.label}`}
        description="Every investigative decision is cryptographically logged to the case audit ledger to preserve investigator authority."
      >
        <div className="space-y-4 text-xs">
          {errorMsg && (
            <div className="p-2.5 rounded bg-rose-50 border border-rose-200 text-rose-700">
              {errorMsg}
            </div>
          )}

          {activeDecisionType === 'EDIT' && (
            <div>
              <label className="block font-medium text-slate-700 mb-1">
                New Attack Classification
              </label>
              <Select
                value={editedClassification}
                onChange={(e) => setEditedClassification(e.target.value)}
                options={[
                  { value: 'CONFIRMED_ATTACK', label: 'Confirmed Attack' },
                  { value: 'LIKELY_ATTACK', label: 'Likely Attack' },
                  { value: 'INCONCLUSIVE', label: 'Inconclusive' },
                  { value: 'NO_ATTACK_OBSERVED', label: 'No Attack Observed' },
                  { value: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient Evidence' },
                ]}
              />
            </div>
          )}

          {activeDecisionType === 'REQUEST_MORE_EVIDENCE' && (
            <div>
              <label className="block font-medium text-slate-700 mb-1">
                Additional Analysis / Evidence Scope Requested
              </label>
              <Textarea
                rows={3}
                placeholder="Specify memory dumps, PCAP captures, or targeted forensic plugins..."
                value={additionalAnalysis}
                onChange={(e) => setAdditionalAnalysis(e.target.value)}
              />
            </div>
          )}

          <div>
            <label className="block font-medium text-slate-700 mb-1">
              Investigator Rationale (Strictly Required)
            </label>
            <Textarea
              rows={4}
              placeholder="State your forensic justification for this decision..."
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDialogOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleConfirmDecision}
              disabled={isSubmitting || !rationale.trim()}
            >
              {isSubmitting ? 'Recording...' : 'Commit Decision to Audit Trail'}
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  );
};
