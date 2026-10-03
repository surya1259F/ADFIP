import React from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Inbox,
  Globe,
  Blocks,
  Terminal,
  Activity,
  ShieldCheck,
  FileText,
  Shield,
} from 'lucide-react';
import { casesService } from '../../services/cases';
import { evidenceService } from '../../services/evidence';
import { findingsService } from '../../services/findings';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { Button } from '../../components/ui/Button';
import { formatTimestamp } from '../../lib/utils';

const CaseNavCard: React.FC<{
  to: string;
  icon: React.ElementType;
  title: string;
  description: string;
}> = ({ to, icon: Icon, title, description }) => (
  <Link to={to}>
    <Card className="flex items-center gap-3 hover:border-slate-300 hover:shadow-md transition-all cursor-pointer group">
      <div className="p-2 bg-stone-100 rounded-md group-hover:bg-slate-100 transition-colors">
        <Icon className="w-4 h-4 text-slate-600" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-800">{title}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
    </Card>
  </Link>
);

export const CaseOverviewPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  const {
    data: caseData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['cases', caseId],
    queryFn: () => casesService.get(caseId!),
    enabled: !!caseId,
  });

  const { data: evidence } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  const { data: findings } = useQuery({
    queryKey: ['cases', caseId, 'findings'],
    queryFn: () => findingsService.listByCase(caseId!),
    enabled: !!caseId,
  });

  if (!caseId) return <Navigate to="/cases" replace />;

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    const msg = normalizeError(error);
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <h1 className="text-base font-semibold text-slate-800 mb-2">
            Case not found
          </h1>
          <p className="text-sm text-slate-500 mb-4">
            This case does not exist or is no longer available.
          </p>
          <Link to="/cases">
            <Button variant="secondary">Return to Cases</Button>
          </Link>
        </div>
      );
    }
    return <ErrorState message={msg} onRetry={refetch} />;
  }

  const c = caseData!;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Case header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[11px] text-slate-400">
              {c.id.slice(0, 8).toUpperCase()}
            </span>
            <StatusBadge status={c.status} />
          </div>
          <h1 className="text-xl font-bold text-slate-900">{c.title || c.name || 'Untitled Case'}</h1>
          {c.description && (
            <p className="text-sm text-slate-500 mt-1">{c.description}</p>
          )}
        </div>
      </div>

      {/* Case metadata */}
      <Card>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <p className="text-slate-400 mb-0.5">Status</p>
            <StatusBadge status={c.status} />
          </div>
          <div>
            <p className="text-slate-400 mb-0.5">Created</p>
            <p className="text-slate-700 font-medium">
              {formatTimestamp(c.created_at)}
            </p>
          </div>
          <div>
            <p className="text-slate-400 mb-0.5">Evidence</p>
            <p className="text-slate-700 font-medium">
              {evidence?.length ?? '—'} items
            </p>
          </div>
          <div>
            <p className="text-slate-400 mb-0.5">Findings</p>
            <p className="text-slate-700 font-medium">
              {findings?.length ?? '—'} items
            </p>
          </div>
        </div>
      </Card>

      {/* Investigation workspace navigation */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">
          Investigation Workspace
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <CaseNavCard
            to={`/cases/${caseId}/evidence`}
            icon={Inbox}
            title="Evidence"
            description="Register and manage forensic evidence"
          />
          <CaseNavCard
            to={`/cases/${caseId}/intelligence`}
            icon={Globe}
            title="Intelligence"
            description="Evidence analysis and artifact extraction"
          />
          <CaseNavCard
            to={`/cases/${caseId}/strategy`}
            icon={Blocks}
            title="Strategy"
            description="Investigation planning and tool selection"
          />
          <CaseNavCard
            to={`/cases/${caseId}/execution`}
            icon={Terminal}
            title="Execution"
            description="Forensic pipeline execution and monitoring"
          />
          <CaseNavCard
            to={`/cases/${caseId}/findings`}
            icon={Activity}
            title="Findings"
            description="Detected forensic findings and evidence"
          />
          <CaseNavCard
            to={`/cases/${caseId}/verification`}
            icon={ShieldCheck}
            title="Verification"
            description="Investigator review and decision"
          />
          <CaseNavCard
            to={`/cases/${caseId}/report`}
            icon={FileText}
            title="Reports"
            description="Generate and export forensic reports"
          />
          <CaseNavCard
            to={`/cases/${caseId}/audit`}
            icon={Shield}
            title="Audit"
            description="Complete investigation audit trail"
          />
        </div>
      </div>
    </div>
  );
};
