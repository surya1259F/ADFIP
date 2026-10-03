import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  FolderKanban,
  Activity,
  Plus,
  ArrowRight,
  Clock,
  ShieldCheck,
  FileText,
} from 'lucide-react';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { Skeleton, SkeletonRow } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';
import { EmptyState } from '../../components/ui/EmptyState';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { Button } from '../../components/ui/Button';
import { formatTimestamp } from '../../lib/utils';
import type { Case } from '../../types';

export const DashboardPage: React.FC = () => {
  const {
    data: cases,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['cases'],
    queryFn: casesService.list,
  });

  const activeCases = cases?.filter(
    (c) => c.status === 'OPEN' || c.status === 'ACTIVE' || c.status === 'open'
  ) || [];

  const closedCases = cases?.filter(
    (c) => c.status === 'CLOSED' || c.status === 'ARCHIVED' || c.status === 'closed'
  ) || [];

  const recentCases = [...(cases || [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-stone-200/80 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Forensic Command Dashboard</h1>
          <p className="text-xs text-slate-500 mt-1">
            Active digital forensic investigations, evidence integrity, and investigator review queue.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Link to="/cases">
            <Button variant="primary" size="sm" icon={<Plus className="w-3.5 h-3.5" />}>
              New Investigation
            </Button>
          </Link>
        </div>
      </div>

      {/* Investigation Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="bg-white border-stone-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500">Active Investigations</p>
              {isLoading ? (
                <Skeleton className="h-7 w-12 mt-1" />
              ) : (
                <p className="text-2xl font-bold text-slate-900 mt-1">{activeCases.length}</p>
              )}
            </div>
            <div className="p-2.5 bg-blue-50 text-blue-700 rounded-lg">
              <Activity className="w-5 h-5" />
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            {activeCases.length === 1 ? '1 case in active analysis' : `${activeCases.length} cases in active analysis`}
          </p>
        </Card>

        <Card className="bg-white border-stone-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500">Total Cases Registered</p>
              {isLoading ? (
                <Skeleton className="h-7 w-12 mt-1" />
              ) : (
                <p className="text-2xl font-bold text-slate-900 mt-1">{cases?.length ?? 0}</p>
              )}
            </div>
            <div className="p-2.5 bg-stone-100 text-slate-700 rounded-lg">
              <FolderKanban className="w-5 h-5" />
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            {closedCases.length} closed or archived
          </p>
        </Card>

        <Card className="bg-white border-stone-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500">Governance & Review</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                {isLoading ? '…' : activeCases.length > 0 ? 'Active' : 'Standby'}
              </p>
            </div>
            <div className="p-2.5 bg-emerald-50 text-emerald-700 rounded-lg">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            Strict ISO/IEC 27037 verification
          </p>
        </Card>
      </div>

      {/* Active Investigations Section */}
      <div className="space-y-3">
        <SectionHeader
          title="Active Investigations"
          description="Cases currently undergoing artifact extraction, hypothesis strategy, and verification."
          action={
            cases && cases.length > 0 ? (
              <Link to="/cases" className="text-xs font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1">
                <span>View all cases</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            ) : null
          }
        />

        {isError && (
          <ErrorState message={normalizeError(error)} onRetry={refetch} />
        )}

        {isLoading && (
          <Card padding={false}>
            {[1, 2, 3].map((i) => (
              <SkeletonRow key={i} cols={4} />
            ))}
          </Card>
        )}

        {!isLoading && !isError && cases?.length === 0 && (
          <EmptyState
            icon={<FolderKanban className="w-10 h-10" />}
            title="No investigations registered yet"
            description="Create your first case to register evidence and begin automated forensic analysis."
            action={
              <Link to="/cases">
                <Button variant="primary" size="sm" icon={<Plus className="w-3.5 h-3.5" />}>
                  Create Investigation
                </Button>
              </Link>
            }
          />
        )}

        {!isLoading && !isError && cases && cases.length > 0 && (
          <Card padding={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="bg-stone-50/80 border-b border-stone-200/80 text-slate-500 font-medium">
                    <th className="py-2.5 px-4">Case Number / Identifier</th>
                    <th className="py-2.5 px-4">Case Title</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Created Date</th>
                    <th className="py-2.5 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {recentCases.map((c: Case) => (
                    <tr key={c.id} className="hover:bg-stone-50/50 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-slate-700">
                        {c.case_number || c.id.slice(0, 8).toUpperCase()}
                      </td>
                      <td className="py-3 px-4">
                        <Link
                          to={`/cases/${c.id}`}
                          className="font-medium text-slate-900 hover:underline"
                        >
                          {c.title}
                        </Link>
                        {c.description && (
                          <p className="text-[11px] text-slate-400 truncate max-w-sm mt-0.5">
                            {c.description}
                          </p>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                        {formatTimestamp(c.created_at)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link to={`/cases/${c.id}`}>
                          <Button variant="secondary" size="sm">
                            Open Workspace
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      {/* Investigation Quick Action / Guidance */}
      {!isLoading && !isError && cases && cases.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <Card className="bg-white border-stone-200 p-4 space-y-2">
            <div className="flex items-center gap-2 text-slate-900 font-semibold text-xs">
              <Clock className="w-4 h-4 text-slate-500" />
              <span>Evidence Integrity Protocol</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Before running analytical tools, verify SHA-256 cryptographic hashes on ingested evidence files in the Evidence registry.
            </p>
          </Card>

          <Card className="bg-white border-stone-200 p-4 space-y-2">
            <div className="flex items-center gap-2 text-slate-900 font-semibold text-xs">
              <FileText className="w-4 h-4 text-slate-500" />
              <span>Human-in-the-Loop Verification</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Automated AI findings and hypothesis correlations remain in pending review status until certified by an investigator in the Verification view.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
};
