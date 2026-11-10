import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  FolderKanban,
  Activity,
  Plus,
  ArrowRight,
  AlertTriangle,
  Clock,
  Layers,
  CheckCircle2,
  XCircle,
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
import type { DashboardAnalyticsResponse } from '../../types';

export const DashboardPage: React.FC = () => {

  const {
    data: dashboardData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<DashboardAnalyticsResponse>({
    queryKey: ['cases', 'dashboard-stats'],
    queryFn: casesService.getDashboardStats,
    refetchInterval: 15000,
  });

  const stats = dashboardData?.stats;
  const stages = dashboardData?.workflow_stages || [];
  const activities = dashboardData?.recent_activity || [];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-stone-200/80 pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Forensic Command Dashboard</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time database-driven investigation statistics, active case operations, and 10-stage forensic workflow lifecycle.
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

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {/* 6 Real Database-Driven Case Statistics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Total Cases */}
        <Link
          to="/cases?filter=all"
          className="group block p-3.5 bg-white border border-stone-200 hover:border-blue-400 rounded-lg shadow-sm hover:shadow transition-all"
        >
          <div className="flex items-center justify-between text-slate-400 group-hover:text-blue-600 transition-colors">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Total</span>
            <FolderKanban className="w-4 h-4" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-slate-900 group-hover:text-blue-700">
              {isLoading ? <Skeleton className="w-10 h-7" /> : stats?.total ?? 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">All Investigations</p>
          </div>
        </Link>

        {/* Active Cases */}
        <Link
          to="/cases?filter=active"
          className="group block p-3.5 bg-white border border-stone-200 hover:border-emerald-400 rounded-lg shadow-sm hover:shadow transition-all"
        >
          <div className="flex items-center justify-between text-emerald-600">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 group-hover:text-emerald-700">Active</span>
            <Activity className="w-4 h-4" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-emerald-700">
              {isLoading ? <Skeleton className="w-10 h-7" /> : stats?.active ?? 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Under Analysis</p>
          </div>
        </Link>

        {/* Completed Cases */}
        <Link
          to="/cases?filter=completed"
          className="group block p-3.5 bg-white border border-stone-200 hover:border-indigo-400 rounded-lg shadow-sm hover:shadow transition-all"
        >
          <div className="flex items-center justify-between text-indigo-600">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 group-hover:text-indigo-700">Completed</span>
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-indigo-700">
              {isLoading ? <Skeleton className="w-10 h-7" /> : stats?.completed ?? 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Closed & Archived</p>
          </div>
        </Link>

        {/* Pending Cases */}
        <Link
          to="/cases?filter=pending"
          className="group block p-3.5 bg-white border border-stone-200 hover:border-amber-400 rounded-lg shadow-sm hover:shadow transition-all"
        >
          <div className="flex items-center justify-between text-amber-600">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 group-hover:text-amber-700">Pending</span>
            <Clock className="w-4 h-4" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-amber-700">
              {isLoading ? <Skeleton className="w-10 h-7" /> : stats?.pending ?? 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Awaiting Evidence</p>
          </div>
        </Link>

        {/* Failed Cases */}
        <Link
          to="/cases?filter=failed"
          className="group block p-3.5 bg-white border border-stone-200 hover:border-red-400 rounded-lg shadow-sm hover:shadow transition-all"
        >
          <div className="flex items-center justify-between text-red-600">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 group-hover:text-red-700">Failed</span>
            <XCircle className="w-4 h-4" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-red-700">
              {isLoading ? <Skeleton className="w-10 h-7" /> : stats?.failed ?? 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Execution Errors</p>
          </div>
        </Link>

        {/* Attention Required */}
        <Link
          to="/cases?filter=attention"
          className="group block p-3.5 bg-white border border-stone-200 hover:border-amber-500 rounded-lg shadow-sm hover:shadow transition-all"
        >
          <div className="flex items-center justify-between text-amber-600">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 group-hover:text-amber-800">Review Gate</span>
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-bold text-amber-800">
              {isLoading ? <Skeleton className="w-10 h-7" /> : stats?.attention_required ?? 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Attention Needed</p>
          </div>
        </Link>
      </div>

      {/* 10-Stage Workflow Progress Indicator */}
      <Card className="p-5 border-stone-200">
        <div className="flex items-center justify-between mb-3 border-b border-stone-100 pb-2">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-600" />
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              10-Stage Forensic Analysis Lifecycle
            </h2>
          </div>
          <span className="text-[11px] text-slate-400">
            Real stage distribution across all registered cases
          </span>
        </div>

        {isLoading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2 pt-1">
            {stages.map((stage) => {
              const isZero = stage.cases_completed === 0;
              return (
                <div
                  key={stage.stage_key}
                  className={`p-2.5 rounded border text-center transition-all ${
                    isZero
                      ? 'bg-stone-50/60 border-stone-200/60 text-slate-400'
                      : 'bg-blue-50/50 border-blue-200 text-slate-800'
                  }`}
                >
                  <div className="text-[10px] font-mono font-bold text-slate-400">
                    STAGE {stage.stage_number}
                  </div>
                  <div className="text-xs font-semibold truncate mt-1" title={stage.label}>
                    {stage.stage_key.replace('_', ' ')}
                  </div>
                  <div className="mt-2 flex items-center justify-center gap-1 font-mono text-xs font-bold">
                    <span className={isZero ? 'text-slate-400' : 'text-blue-700'}>
                      {stage.cases_completed}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      ({stage.percentage}%)
                    </span>
                  </div>
                  {/* Miniature progress bar */}
                  <div className="w-full bg-stone-200 rounded-full h-1 mt-1.5 overflow-hidden">
                    <div
                      className={`h-1 rounded-full ${isZero ? 'bg-stone-300' : 'bg-blue-600'}`}
                      style={{ width: `${Math.min(stage.percentage, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Main Grid: Investigation Activity List (Audit stream moved to dedicated /audit page per Section 3.5) */}
      <div className="space-y-3">
        <SectionHeader
          title="Investigation Activity"
          description={`Active investigation records tracked in this workstation (${activities.length} shown).`}
          action={
            <Link to="/cases" className="text-xs font-medium text-slate-600 hover:text-slate-900 flex items-center gap-1">
              <span>View all cases</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          }
        />

        {isLoading && (
          <Card padding={false}>
            {[1, 2, 3].map((i) => (
              <SkeletonRow key={i} cols={4} />
            ))}
          </Card>
        )}

        {!isLoading && activities.length === 0 && (
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

        {!isLoading && activities.length > 0 && (
          <Card padding={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="bg-stone-50/80 border-b border-stone-200/80 text-slate-500 font-medium">
                    <th className="py-2.5 px-3">Case</th>
                    <th className="py-2.5 px-3">Current Stage</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Artifacts</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {activities.map((c) => (
                    <tr key={c.id} className="hover:bg-stone-50/50 transition-colors">
                      <td className="py-3 px-3">
                        <Link
                          to={`/cases/${c.id}`}
                          className="font-semibold text-slate-900 hover:underline flex items-center gap-1.5"
                        >
                          <span>{c.name || c.title}</span>
                        </Link>
                        <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400 font-mono">
                          <span>{c.case_number}</span>
                          <span>•</span>
                          <span className="truncate max-w-[120px]">{c.assigned_investigator}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="font-mono text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-stone-200">
                          {c.current_stage}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3 px-3 text-[11px] text-slate-600 font-mono">
                        <div>{c.evidence_count} evidence</div>
                        <div className="text-slate-400">{c.findings_count} findings</div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link to={`/cases/${c.id}`}>
                          <Button variant="secondary" size="sm">
                            Workspace
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
