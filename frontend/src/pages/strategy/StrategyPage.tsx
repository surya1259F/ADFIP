import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Blocks,
  RefreshCw,
  Terminal,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  HelpCircle,
  ShieldCheck,
  ShieldAlert,
  Layers,
  Info,
} from 'lucide-react';
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
import type { InvestigativeQuestion } from '../../types';

export const StrategyPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});

  const toggleTaskExpanded = (taskKey: string) => {
    setExpandedTasks((prev) => ({
      ...prev,
      [taskKey]: !prev[taskKey],
    }));
  };

  const {
    data: evidence,
    isLoading: evLoading,
    isError: isEvError,
    error: evError,
    refetch: refetchEv,
  } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  const {
    data: plan,
    isLoading: planLoading,
    isError: isPlanError,
    error: planError,
    refetch: refetchPlan,
  } = useQuery({
    queryKey: ['cases', caseId, 'plan'],
    queryFn: () => casesService.getPlan(caseId!),
    enabled: !!caseId,
  });

  const {
    data: questionsData,
    isLoading: qLoading,
    isError: isQError,
    error: qError,
    refetch: refetchQ,
  } = useQuery({
    queryKey: ['cases', caseId, 'investigative-questions'],
    queryFn: () => casesService.getInvestigativeQuestions(caseId!),
    enabled: !!caseId,
  });

  const generateMutation = useMutation({
    mutationFn: () => casesService.generatePlan(caseId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'investigative-questions'] });
    },
  });

  if (isEvError) return <ErrorState message={normalizeError(evError)} onRetry={refetchEv} />;

  const tasks = plan?.tasks || [];
  const questions: InvestigativeQuestion[] =
    questionsData?.questions || plan?.investigative_questions || [];

  const getFeasibilityBadge = (feasibility: string) => {
    switch (feasibility) {
      case 'INVESTIGABLE':
        return <Badge tone="success">Investigable</Badge>;
      case 'PARTIALLY_INVESTIGABLE':
        return <Badge tone="info">Partially Investigable</Badge>;
      case 'REQUIRES_ADDITIONAL_EVIDENCE':
        return <Badge tone="warning">Requires Additional Evidence</Badge>;
      case 'UNSUPPORTED_BY_TOOLS':
        return <Badge tone="danger">Unsupported by Tools</Badge>;
      default:
        return <Badge tone="neutral">{feasibility || 'Unknown'}</Badge>;
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <SectionHeader
        title="Investigation Strategy"
        description="Evidence-driven investigative questions, capability mapping, and explainable tool selection"
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

      {/* Investigative Questions & Feasibility Assessment */}
      <Card padding={false}>
        <div className="p-4 border-b border-stone-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-blue-600" />
            <div>
              <h2 className="text-sm font-semibold text-slate-800">
                Investigative Questions & Feasibility Assessment
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Objective archetypes evaluated against available evidence domains and forensic tool capabilities
              </p>
            </div>
          </div>
          <Badge tone={questions.length > 0 ? 'active' : 'neutral'}>
            {questions.length} {questions.length === 1 ? 'Question' : 'Questions'}
          </Badge>
        </div>

        {qLoading && (
          <div className="p-4 space-y-3">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        )}

        {isQError && (
          <div className="p-4">
            <ErrorState message={normalizeError(qError)} onRetry={refetchQ} />
          </div>
        )}

        {!qLoading && !isQError && questions.length === 0 && (
          <div className="p-8">
            <EmptyState
              icon={<HelpCircle className="w-8 h-8" />}
              title="No investigative questions generated"
              description="Define the case objective or regenerate the strategy plan to derive forensic questions."
            />
          </div>
        )}

        {!qLoading && !isQError && questions.length > 0 && (
          <div className="divide-y divide-stone-100">
            {questions.map((q) => (
              <div key={q.question_id || q.code} className="p-4 hover:bg-stone-50/50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                        {q.question_id || q.code}
                      </span>
                      <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                        {q.category}
                      </span>
                      {q.archetype && (
                        <span className="text-[11px] font-mono text-slate-400">
                          [{q.archetype}]
                        </span>
                      )}
                      {getFeasibilityBadge(q.feasibility)}
                    </div>
                    <p className="text-sm font-medium text-slate-900 leading-snug">
                      {q.question_text}
                    </p>
                    {q.hypothesis && (
                      <div className="text-xs text-slate-600 bg-blue-50/60 border border-blue-100/80 rounded px-2.5 py-1.5 flex items-start gap-1.5">
                        <span className="font-semibold text-blue-800 shrink-0">Working Hypothesis:</span>
                        <span>{q.hypothesis}</span>
                      </div>
                    )}
                    {q.assessment_notes && (
                      <p className="text-xs text-slate-500 italic mt-1">
                        {q.assessment_notes}
                      </p>
                    )}
                  </div>
                </div>

                {/* Evidence matching and requirements badges */}
                <div className="mt-3 flex items-center gap-4 flex-wrap text-xs pt-2 border-t border-stone-100/80">
                  {q.matching_evidence_names && q.matching_evidence_names.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-slate-500 font-medium">Matching Evidence:</span>
                      {q.matching_evidence_names.map((evName, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded text-[11px]"
                        >
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          {evName}
                        </span>
                      ))}
                    </div>
                  )}

                  {q.missing_evidence_domains && q.missing_evidence_domains.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-amber-700 font-medium">Missing Evidence Domains:</span>
                      {q.missing_evidence_domains.map((dom, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded text-[11px]"
                        >
                          <AlertTriangle className="w-3 h-3 text-amber-600" />
                          {dom}
                        </span>
                      ))}
                    </div>
                  )}

                  {q.required_capabilities && q.required_capabilities.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap text-slate-400">
                      <span>Capabilities:</span>
                      <span className="font-mono text-[11px] text-slate-600">
                        {q.required_capabilities.join(', ')}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Investigation Plan Tasks & Tool Selection Explainability */}
      <Card padding={false}>
        <div className="p-4 border-b border-stone-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Planned Forensic Tasks & Tool Explainability</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Deterministic sequence with plain-language selection rationale, candidate evaluations, and risk boundaries
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
          <div className="divide-y divide-stone-100">
            {tasks.map((task: any, idx: number) => {
              const taskKey = task.task_key || task.step_id || `task-${idx + 1}`;
              const isExpanded = !!expandedTasks[taskKey];
              const rationale = task.rationale || {};
              const toolExplanation = rationale.tool_explanation || {};
              const whySelected = rationale.why_selected || task.reason || 'Standard forensic capability execution.';
              const risks = rationale.risks_and_limitations;
              const expectedOutputs: string[] = task.expected_outputs || toolExplanation.expected_output || [];
              const candidates: string[] = task.candidate_tool_ids || toolExplanation.candidate_tools || [];
              const isToolAvailable = task.tool_available !== false && task.selected_tool_id !== null && !task.status?.startsWith('BLOCKED');
              const blockingReason = task.blocking_reason;
              const toolName = task.selected_tool_name || task.selected_tool_id || task.tool || 'Automated Tool';
              const agentName = task.agent_name || task.agent || 'ForensicAgent';
              const actionName = task.capability_id || task.action || 'Execute';

              return (
                <div key={taskKey} className="transition-colors hover:bg-stone-50/40">
                  <div
                    className="p-4 flex items-center justify-between gap-4 cursor-pointer select-none"
                    onClick={() => toggleTaskExpanded(taskKey)}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <button
                        type="button"
                        className="text-slate-400 hover:text-slate-600 p-0.5 focus:outline-none"
                        aria-label="Toggle rationale"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-blue-600" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-slate-400" />
                        )}
                      </button>
                      <div className="space-y-0.5 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-semibold text-slate-700">
                            {taskKey}
                          </span>
                          <span className="text-xs font-medium text-slate-500">
                            ({agentName})
                          </span>
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-800">
                            {isToolAvailable ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                            ) : (
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                            )}
                            {toolName}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 truncate max-w-xl font-mono">
                          {actionName} {task.evidence_name ? `→ ${task.evidence_name}` : ''}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-xs text-slate-400">
                        P{task.sequence ?? (idx + 1)}
                      </span>
                      <StatusBadge status={task.status || 'PLANNED'} />
                    </div>
                  </div>

                  {/* Expanded Tool Selection Rationale & Feasibility Details */}
                  {isExpanded && (
                    <div className="px-10 pb-4 pt-1 bg-stone-50/70 border-t border-stone-100 space-y-3 text-xs">
                      {/* Selection Rationale */}
                      <div className="bg-white p-3 rounded border border-stone-200 space-y-2">
                        <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                          <Info className="w-3.5 h-3.5 text-blue-600" />
                          <span>Tool Selection Rationale</span>
                        </div>
                        <p className="text-slate-700 leading-relaxed">
                          {whySelected}
                        </p>

                        {blockingReason && (
                          <div className="bg-red-50 border border-red-200 text-red-700 p-2 rounded flex items-start gap-1.5">
                            <ShieldAlert className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                            <div>
                              <span className="font-semibold">Execution Blocked: </span>
                              <span>{blockingReason}</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Evaluated Candidates & Expected Outputs */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="bg-white p-3 rounded border border-stone-200 space-y-1.5">
                          <span className="font-semibold text-slate-700 block">Evaluated Tool Candidates</span>
                          {candidates.length > 0 ? (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {candidates.map((c, cIdx) => (
                                <Badge
                                  key={cIdx}
                                  tone={c.toLowerCase() === toolName.toLowerCase() ? 'success' : 'neutral'}
                                >
                                  {c}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <p className="text-slate-500">Dedicated subsystem integration</p>
                          )}
                          {toolExplanation.selected_tool_version && (
                            <p className="text-[11px] text-slate-400 font-mono">
                              Binary version: {toolExplanation.selected_tool_version}
                            </p>
                          )}
                        </div>

                        <div className="bg-white p-3 rounded border border-stone-200 space-y-1.5">
                          <span className="font-semibold text-slate-700 block">Expected Artifact Outputs</span>
                          {expectedOutputs.length > 0 ? (
                            <ul className="list-disc list-inside space-y-0.5 text-slate-600 font-mono text-[11px]">
                              {expectedOutputs.map((out, oIdx) => (
                                <li key={oIdx}>{out}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-slate-500">Extracted metadata and structured findings</p>
                          )}
                        </div>
                      </div>

                      {/* Risks and Sandbox Constraints */}
                      {risks && (
                        <div className="text-slate-500 flex items-start gap-1.5 pt-1">
                          <ShieldCheck className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                          <span>Safety & Guardrails: {risks}</span>
                        </div>
                      )}

                      {/* Dependencies */}
                      {task.dependencies && task.dependencies.length > 0 && (
                        <div className="text-slate-500 flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>Prerequisites: {task.dependencies.join(', ')}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
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
