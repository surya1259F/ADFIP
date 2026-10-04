import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Blocks, RefreshCw, Terminal, CheckCircle2, AlertTriangle } from 'lucide-react';
import { evidenceService } from '../../services/evidence';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge, StatusBadge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';

export const StrategyPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: evidence, isLoading: evLoading, isError: isEvError, error: evError, refetch: refetchEv } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  const { data: plan, isLoading: planLoading, isError: isPlanError, error: planError, refetch: refetchPlan } = useQuery({
    queryKey: ['cases', caseId, 'plan'],
    queryFn: () => casesService.getPlan(caseId!),
    enabled: !!caseId,
  });

  const generateMutation = useMutation({
    mutationFn: () => casesService.generatePlan(caseId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
    },
  });

  if (isEvError) return <ErrorState message={normalizeError(evError)} onRetry={refetchEv} />;

  const tasks = plan?.tasks || [];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <SectionHeader
        title="Investigation Strategy"
        description="Evidence-driven investigation planning and capability tool selection"
        action={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              loading={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Regenerate Plan
            </Button>
            <Button
              size="sm"
              variant="primary"
              onClick={() => navigate(`/cases/${caseId}/execution`)}
              icon={<Terminal className="w-3.5 h-3.5" />}
            >
              Open Execution
            </Button>
          </div>
        }
      />

      {/* Strategy Summary */}
      {plan?.strategy_summary && (
        <Card className="bg-slate-900 text-white border-slate-800">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-slate-800 rounded-md shrink-0">
              <Blocks className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-1">
                Forensic Strategy Summary
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                {plan.strategy_summary}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Investigation Plan Tasks */}
      <Card padding={false}>
        <div className="p-4 border-b border-stone-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Planned Forensic Tasks</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Deterministic sequence generated from available evidence and verified platform capabilities
            </p>
          </div>
          <Badge tone={tasks.length > 0 ? 'active' : 'neutral'}>
            {tasks.length} {tasks.length === 1 ? 'Task' : 'Tasks'}
          </Badge>
        </div>

        {planLoading && (
          <div className="p-4 space-y-2">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        )}

        {isPlanError && (
          <div className="p-4">
            <ErrorState message={normalizeError(planError)} onRetry={refetchPlan} />
          </div>
        )}

        {!planLoading && !isPlanError && tasks.length === 0 && (
          <div className="p-8">
            <EmptyState
              icon={<Blocks className="w-8 h-8" />}
              title="No tasks planned"
              description="Register evidence items to generate an autonomous forensic analysis plan."
            />
          </div>
        )}

        {!planLoading && !isPlanError && tasks.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-stone-100 bg-stone-50/50">
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Task / Step</th>
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Agent</th>
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Tool</th>
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Action</th>
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Reason</th>
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Priority</th>
                  <th className="text-left px-4 py-2 text-slate-500 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task: any, idx: number) => (
                  <tr key={task.step_id || idx} className="border-b border-stone-50 hover:bg-stone-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600 whitespace-nowrap">
                      {task.step_id || `task-${idx + 1}`}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800 whitespace-nowrap">
                      {task.agent || 'ForensicAgent'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5 font-medium text-slate-700">
                        {task.tool_available ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                        )}
                        {task.tool}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap font-mono text-[11px]">
                      {task.action}
                    </td>
                    <td className="px-4 py-3 text-slate-600 max-w-xs truncate" title={task.reason}>
                      {task.reason || 'Forensic analysis'}
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      #{task.priority ?? 1}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge status={task.status || 'PLANNED'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Evidence Inventory */}
      <Card>
        <SectionHeader
          title="Evidence Basis"
          size="sm"
          description="Registered evidence items evaluated for this strategy"
        />
        {evLoading && <Skeleton className="h-16" />}
        {!evLoading && (!evidence || evidence.length === 0) && (
          <EmptyState
            icon={<Blocks className="w-6 h-6" />}
            title="No evidence registered"
            description="Strategy cannot be determined without registered evidence. Register evidence first."
          />
        )}
        {!evLoading && evidence && evidence.length > 0 && (
          <div className="space-y-2">
            {evidence.map((ev) => (
              <div
                key={ev.id}
                className="flex items-center justify-between py-2 border-b border-stone-50 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-slate-800">{ev.name}</p>
                  <p className="text-xs text-slate-500">{ev.evidence_type}</p>
                </div>
                <StatusBadge status={ev.integrity_status || ev.status || 'INGESTED'} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

