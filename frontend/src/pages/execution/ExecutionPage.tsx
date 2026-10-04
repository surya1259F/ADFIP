import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Terminal, Play } from 'lucide-react';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { SkeletonRow } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { Button } from '../../components/ui/Button';
import { formatTimestamp } from '../../lib/utils';
import type { ExecutionRecord } from '../../types';

export const ExecutionPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const qc = useQueryClient();

  const { data: executions, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'executions'],
    queryFn: () => casesService.getExecutions(caseId!),
    enabled: !!caseId,
    refetchInterval: (query) => {
      const data = query.state.data as ExecutionRecord[] | undefined;
      const hasRunning = data?.some(
        (e) => e.status === 'RUNNING' || e.status === 'QUEUED'
      );
      return hasRunning ? 5000 : false;
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => casesService.executePlan(caseId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'executions'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'findings'] });
    },
  });

  const runningExecutions =
    executions?.filter(
      (e) => e.status === 'RUNNING' || e.status === 'QUEUED'
    ) || [];
  const completedExecutions =
    executions?.filter(
      (e) => e.status !== 'RUNNING' && e.status !== 'QUEUED'
    ) || [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <SectionHeader
          title="Execution"
          description="Forensic pipeline execution and tool operation monitoring"
        />
        <Button
          variant="primary"
          size="sm"
          icon={<Play className="w-3.5 h-3.5" />}
          onClick={() => executeMutation.mutate()}
          loading={executeMutation.isPending}
          disabled={runningExecutions.length > 0}
        >
          Execute Analysis
        </Button>
      </div>

      {executeMutation.isError && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
          {normalizeError(executeMutation.error)}
        </p>
      )}

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {/* Active executions */}
      {runningExecutions.length > 0 && (
        <Card>
          <SectionHeader title="Active Execution" size="sm" />
          {runningExecutions.map((ex: ExecutionRecord) => (
            <div key={ex.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800">
                    {ex.agent ? (ex.tool ? `${ex.agent} — ${ex.tool}` : ex.agent) : (ex.tool || 'Forensic Pipeline')}
                  </p>
                  <p className="font-mono text-[10px] text-slate-400">
                    {ex.id.slice(0, 8)}
                  </p>
                </div>
                <StatusBadge status={ex.status} />
              </div>
              {ex.progress != null && (
                <div>
                  <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                    <span>Progress</span>
                    <span>{ex.progress}%</span>
                  </div>
                  <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all"
                      style={{ width: `${ex.progress}%` }}
                    />
                  </div>
                </div>
              )}
              {ex.started_at && (
                <p className="text-xs text-slate-500">
                  Started: {formatTimestamp(ex.started_at)}
                </p>
              )}
            </div>
          ))}
        </Card>
      )}

      {/* Execution history */}
      {isLoading && (
        <Card padding={false}>
          {[1, 2, 3].map((i) => (
            <SkeletonRow key={i} cols={5} />
          ))}
        </Card>
      )}

      {!isLoading && !isError && (executions?.length ?? 0) === 0 && (
        <EmptyState
          icon={<Terminal className="w-8 h-8" />}
          title="No executions yet"
          description="Start forensic analysis to create execution records. Use the Execute Analysis button above."
        />
      )}

      {!isLoading && completedExecutions.length > 0 && (
        <Card padding={false}>
          <div className="px-4 py-2.5 border-b border-stone-100">
            <p className="text-xs font-semibold text-slate-600">
              Execution History
            </p>
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-100">
                <th className="text-left px-4 py-2 text-slate-500 font-medium">
                  ID
                </th>
                <th className="text-left px-4 py-2 text-slate-500 font-medium">
                  Agent / Tool
                </th>
                <th className="text-left px-4 py-2 text-slate-500 font-medium">
                  Status
                </th>
                <th className="text-left px-4 py-2 text-slate-500 font-medium">
                  Started
                </th>
                <th className="text-left px-4 py-2 text-slate-500 font-medium">
                  Artifacts
                </th>
                <th className="text-left px-4 py-2 text-slate-500 font-medium">
                  Findings
                </th>
              </tr>
            </thead>
            <tbody>
              {completedExecutions.map((ex: ExecutionRecord) => (
                <tr
                  key={ex.id}
                  className="border-b border-stone-50 hover:bg-stone-50"
                >
                  <td className="px-4 py-2.5 font-mono text-[10px] text-slate-500">
                    {ex.id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">
                    <span className="font-medium">{ex.agent || ex.tool || '—'}</span>
                    {ex.agent && ex.tool && (
                      <span className="text-[10px] text-slate-400 font-mono block">
                        Tool: {ex.tool}
                      </span>
                    )}
                    {ex.error && (
                      <span className="text-[10px] text-red-600 block mt-0.5 max-w-md truncate" title={ex.error}>
                        Error: {ex.error}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={ex.status} />
                  </td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {ex.started_at ? formatTimestamp(ex.started_at) : '—'}
                    {ex.duration_ms != null && (
                      <span className="text-[10px] text-slate-400 block font-mono">
                        {(ex.duration_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-slate-600">
                    {ex.artifacts_count ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-slate-600">
                    {ex.findings_count ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
};

