import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  FolderKanban,
  Activity,
  Plus,
  ArrowRight,
  ShieldCheck,
  Terminal,
  FileCheck,
} from 'lucide-react';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { SkeletonRow } from '../../components/ui/Skeleton';
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
    .slice(0, 6);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-stone-200/80 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Forensic Command Dashboard</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time status of evidence preservation, deterministic analysis tools, investigator reviews, and report readiness.
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

      {/* 4 Compact Operational Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Forensic Integrity */}
        <Card className="bg-white border-stone-200 p-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Forensic Integrity
            </span>
            <div className="p-1.5 bg-emerald-50 text-emerald-700 rounded-md">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2">
            <p className="text-base font-bold text-slate-900 leading-tight">Cryptographic Vault</p>
            <p className="text-xs text-emerald-700 font-medium mt-0.5">SHA-256 Verified</p>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            Read-only preserved storage
          </p>
        </Card>

        {/* Card 2: Analysis Tasks & Specialist Tools */}
        <Card className="bg-white border-stone-200 p-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Analysis Tasks
            </span>
            <div className="p-1.5 bg-blue-50 text-blue-700 rounded-md">
              <Terminal className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2">
            <p className="text-base font-bold text-slate-900 leading-tight">Specialist Tools</p>
            <p className="text-xs text-blue-700 font-medium mt-0.5">11 Registered Agents</p>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            Deterministic execution
          </p>
        </Card>

        {/* Card 3: Findings Pending Review */}
        <Card className="bg-white border-stone-200 p-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Findings Review
            </span>
            <div className="p-1.5 bg-amber-50 text-amber-700 rounded-md">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2">
            <p className="text-base font-bold text-slate-900 leading-tight">Human-in-the-Loop</p>
            <p className="text-xs text-amber-700 font-medium mt-0.5">Review Gate Enforced</p>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            FACT / INFERENCE governance
          </p>
        </Card>

        {/* Card 4: Report Readiness */}
        <Card className="bg-white border-stone-200 p-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Report Readiness
            </span>
            <div className="p-1.5 bg-indigo-50 text-indigo-700 rounded-md">
              <FileCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2">
            <p className="text-base font-bold text-slate-900 leading-tight">14-Gate Subsystem</p>
            <p className="text-xs text-indigo-700 font-medium mt-0.5">Authoritative Release</p>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 font-mono">
            Working drafts supported
          </p>
        </Card>
      </div>

      {/* Active Investigations Section */}
      <div className="space-y-3">
        <SectionHeader
          title="Active Investigations"
          description={`Showing ${recentCases.length} of ${cases?.length ?? 0} registered case containers (${activeCases.length} active, ${closedCases.length} closed).`}
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
                    <th className="py-2.5 px-4">Case Number / Reference</th>
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
    </div>
  );
};
