import React, { useState } from 'react';
import { PageContainer } from '../components/PageContainer';
import { EmptyState } from '../components/EmptyState';
import { InvestigationStrategyView } from '../components/InvestigationStrategyView';
import { useInvestigationStore } from '../stores/investigationStore';
import {
  Activity,
  StopCircle,
  AlertCircle,
  Terminal,
  BrainCircuit,
  Cpu
} from 'lucide-react';

export const InvestigationProcessPage: React.FC = () => {
  const {
    activeInvestigation,
    evidenceList,
    currentPlan,
    generatePlan,
    toolExecutionTracker,
    cancelActiveExecution,
    executeDiskAnalysis,
    executeMemoryAnalysis,
    executeMalwareAnalysis,
    executeLogAnalysis,
    loading,
    error
  } = useInvestigationStore();

  const [pageMode, setPageMode] = useState<'strategy' | 'execution'>('strategy');
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string>('');
  const [selectedTool, setSelectedTool] = useState<'disk' | 'memory' | 'malware' | 'log'>('disk');
  const [volatilityPlugin, setVolatilityPlugin] = useState<string>('windows.pslist');
  const [yaraRule, setYaraRule] = useState<string>('adfir_webshell_indicators');
  const [maxEvtxRecords, setMaxEvtxRecords] = useState<number>(5000);

  if (!activeInvestigation) {
    return (
      <PageContainer title="Investigation Execution">
        <EmptyState
          icon={AlertCircle}
          title="No Active Case Selected"
          description="Select or initialize an investigation case before launching the forensic execution engine."
        />
      </PageContainer>
    );
  }

  const handleRunSelected = async () => {
    const evId = selectedEvidenceId || (evidenceList.length > 0 ? evidenceList[0].id : '');
    if (!evId) return;

    if (selectedTool === 'disk') {
      await executeDiskAnalysis(evId);
    } else if (selectedTool === 'memory') {
      await executeMemoryAnalysis(evId, volatilityPlugin);
    } else if (selectedTool === 'malware') {
      await executeMalwareAnalysis(evId, yaraRule);
    } else if (selectedTool === 'log') {
      await executeLogAnalysis(evId, maxEvtxRecords);
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'RUNNING':
        return <span className="text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded text-[10px] font-mono animate-pulse">● RUNNING</span>;
      case 'PLANNING':
        return <span className="text-indigo-400 bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 rounded text-[10px] font-mono animate-pulse">● PLANNING DAG</span>;
      case 'QUEUED':
        return <span className="text-blue-400 bg-blue-500/10 border border-blue-500/30 px-2 py-0.5 rounded text-[10px] font-mono">QUEUED</span>;
      case 'COMPLETED':
        return <span className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded text-[10px] font-mono">✓ COMPLETED</span>;
      case 'FAILED':
        return <span className="text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded text-[10px] font-mono">✗ FAILED</span>;
      case 'CANCELLED':
        return <span className="text-slate-400 bg-slate-800 border border-slate-700 px-2 py-0.5 rounded text-[10px] font-mono">CANCELLED</span>;
      default:
        return <span className="text-slate-500 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded text-[10px] font-mono">NOT_STARTED</span>;
    }
  };

  const planSteps = currentPlan?.tasks || currentPlan?.steps || [];

  return (
    <PageContainer
      title="Investigation Strategy & Execution Orchestrator"
      subtitle={`Case: ${activeInvestigation.name} | Executable DAG strategy planning, tool requirement resolution, and execution telemetry.`}
      actions={
        <div className="flex items-center gap-2 font-mono text-xs">
          <div className="bg-slate-900 border border-slate-800 p-1 rounded-lg flex items-center gap-1">
            <button
              onClick={() => setPageMode('strategy')}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-md transition-all ${
                pageMode === 'strategy' ? 'bg-indigo-600 text-white font-bold shadow-md' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BrainCircuit className="w-3.5 h-3.5" />
              <span>Strategy Engine</span>
            </button>
            <button
              onClick={() => setPageMode('execution')}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-md transition-all ${
                pageMode === 'execution' ? 'bg-indigo-600 text-white font-bold shadow-md' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>Execution Control</span>
            </button>
          </div>

          {toolExecutionTracker.status === 'RUNNING' && (
            <button
              onClick={cancelActiveExecution}
              className="flex items-center gap-1 px-3 py-2 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-mono font-medium transition-colors"
            >
              <StopCircle className="w-3.5 h-3.5" />
              <span>Cancel Process</span>
            </button>
          )}
        </div>
      }
    >
      <div className="space-y-6">
        {pageMode === 'strategy' ? (
          <InvestigationStrategyView caseItem={activeInvestigation} />
        ) : (
          <>
            {error && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs rounded-lg flex items-center gap-2 font-mono">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Execution State Banner */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-slate-950 rounded-lg border border-slate-800">
                <Activity className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-mono text-sm font-bold text-slate-100">Process State:</h3>
                  {getStatusBadge(toolExecutionTracker.status)}
                </div>
                <p className="text-xs text-slate-400 mt-0.5 font-mono">
                  Active Subprocess: {toolExecutionTracker.activeTool || 'None (Idle)'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
              <div>
                <span className="text-slate-500 text-[10px] block uppercase">Evidence Items</span>
                <span>{evidenceList.length} Registered</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] block uppercase">Plan Status</span>
                <span className="text-slate-200">{currentPlan?.status || 'No Plan'}</span>
              </div>
            </div>
          </div>

          {/* Autonomous DAG Plan Display */}
          {currentPlan ? (
            <div className="space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="text-indigo-400 uppercase font-semibold text-[11px] block">
                  Autonomous Task Graph (DAG) — {planSteps.length} Tasks Scheduled
                </span>
                <span className="text-slate-400 text-[10px]">Version {currentPlan.version || 1}</span>
              </div>
              <p className="text-slate-300 text-[11px] leading-relaxed">{currentPlan.strategy_summary}</p>
              <div className="space-y-2 pt-2">
                {planSteps.map((s: any, idx: number) => {
                  const step = s || {};
                  const isCompleted = step.status === 'COMPLETED';
                  const isFailed = step.status === 'FAILED';
                  const isRunning = step.status === 'RUNNING';
                  const isCancelled = step.status === 'CANCELLED';
                  const stepId = step.step_id || step.task_key || `step-${idx}`;
                  const prio = step.priority || step.priority_level || 'MEDIUM';
                  const agentStr = step.agent || step.agent_name || 'SpecialistAgent';
                  const toolStr = step.tool || step.selected_tool_id || 'ForensicTool';
                  const actionStr = step.action || step.capability_id || 'CAPABILITY';

                  return (
                    <div
                      key={stepId}
                      className={`p-3 bg-slate-950 rounded-lg border ${
                        isFailed
                          ? 'border-rose-800/60 bg-rose-950/10'
                          : isCompleted
                          ? 'border-emerald-800/60 bg-emerald-950/10'
                          : isRunning
                          ? 'border-amber-800/60 bg-amber-950/10'
                          : 'border-slate-800'
                      } flex flex-col sm:flex-row sm:items-center justify-between gap-2`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-slate-500 font-mono">#{prio}</span>
                          <span className="text-indigo-300 font-semibold">{agentStr}</span>
                          <span className="text-slate-500">&rarr;</span>
                          <span className="text-slate-300 font-medium">{toolStr}</span>
                          <span className="text-[10px] text-slate-400">({actionStr})</span>
                          {step.evidence_name && (
                            <span className="text-[10px] bg-slate-900 text-slate-400 px-1.5 py-0.5 rounded border border-slate-800">
                              Evidence: {step.evidence_name}
                            </span>
                          )}
                        </div>
                        {(step.reason || step.rationale?.selection_reason) && (
                          <p className="text-[10px] text-slate-400 pl-4">{step.reason || step.rationale?.selection_reason}</p>
                        )}
                        {(step.error_message || step.blocking_reason) && (
                          <p className="text-[10px] text-rose-400 pl-4 font-mono">Notice: {step.error_message || step.blocking_reason}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                        {isCompleted && (
                          <div className="flex items-center gap-2 text-[10px] font-mono">
                            <span className="text-cyan-400">{step.artifacts_count || 0} artifacts</span>
                            <span className="text-slate-600">|</span>
                            <span className="text-amber-400">{step.findings_count || 0} findings</span>
                          </div>
                        )}
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                            isCompleted
                              ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                              : isFailed
                              ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                              : isRunning
                              ? 'text-amber-400 bg-amber-500/10 border-amber-500/30 animate-pulse'
                              : isCancelled
                              ? 'text-slate-500 bg-slate-900 border-slate-800'
                              : 'text-indigo-400 bg-indigo-500/10 border-indigo-500/30'
                          }`}
                        >
                          {step.status || (step.tool_available ? 'PLANNED' : 'UNAVAILABLE')}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 text-xs text-slate-400 font-mono flex items-center justify-between">
              <span>No autonomous execution plan constructed yet.</span>
              <button
                onClick={() => generatePlan(activeInvestigation.id)}
                className="text-indigo-400 hover:text-indigo-300 font-semibold underline"
              >
                Construct Plan &rarr;
              </button>
            </div>
          )}
        </div>

        {/* Manual Tool Execution Station */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-xs font-mono uppercase text-slate-200 font-bold flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            Direct Specialist Tool Dispatch
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            {/* Target Evidence Selection */}
            <div>
              <label className="block text-slate-400 mb-1">1. Select Evidence Target</label>
              <select
                value={selectedEvidenceId || (evidenceList[0]?.id || '')}
                onChange={(e) => setSelectedEvidenceId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                {evidenceList.map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.name} ({ev.evidence_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Specialist Engine Selection */}
            <div>
              <label className="block text-slate-400 mb-1">2. Select Specialist Tool</label>
              <select
                value={selectedTool}
                onChange={(e) => setSelectedTool(e.target.value as any)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="disk">The Sleuth Kit (DiskAgent - fls)</option>
                <option value="memory">Volatility 3 (MemoryAgent)</option>
                <option value="malware">YARA Pattern Engine (MalwareAgent)</option>
                <option value="log">python-evtx (LogAgent)</option>
              </select>
            </div>

            {/* Parameter Selection */}
            <div>
              <label className="block text-slate-400 mb-1">3. Execution Parameter</label>
              {selectedTool === 'disk' && (
                <div className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-400">
                  Recursive Inode Traversal (`-r -p`)
                </div>
              )}
              {selectedTool === 'memory' && (
                <select
                  value={volatilityPlugin}
                  onChange={(e) => setVolatilityPlugin(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="windows.pslist">windows.pslist</option>
                  <option value="windows.pstree">windows.pstree</option>
                  <option value="windows.netscan">windows.netscan</option>
                  <option value="windows.malfind">windows.malfind</option>
                </select>
              )}
              {selectedTool === 'malware' && (
                <select
                  value={yaraRule}
                  onChange={(e) => setYaraRule(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="adfir_webshell_indicators">adfir_webshell_indicators</option>
                  <option value="adfir_suspicious_commands">adfir_suspicious_commands</option>
                </select>
              )}
              {selectedTool === 'log' && (
                <input
                  type="number"
                  value={maxEvtxRecords}
                  onChange={(e) => setMaxEvtxRecords(parseInt(e.target.value) || 5000)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                  placeholder="Max Records (e.g. 5000)"
                />
              )}
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              onClick={handleRunSelected}
              disabled={loading || evidenceList.length === 0}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-mono font-medium rounded-lg text-xs shadow-md shadow-indigo-500/20"
            >
              {loading ? 'Executing Specialist Engine...' : 'Execute Selected Tool'}
            </button>
          </div>
        </div>

        {/* Real-time Subprocess Output Logs */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3 font-mono">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2 text-slate-200 text-xs font-bold uppercase">
              <Terminal className="w-4 h-4 text-emerald-400" />
              Subprocess Telemetry & Output Log
            </div>
            <span className="text-[10px] text-slate-500">File-backed execution logs</span>
          </div>

          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80 font-mono text-xs text-slate-300 space-y-1.5 max-h-[220px] overflow-y-auto">
            {toolExecutionTracker.toolOutputLog.length === 0 ? (
              <p className="text-slate-600">Subprocess log is quiet. Ready for execution commands.</p>
            ) : (
              toolExecutionTracker.toolOutputLog.map((line, idx) => (
                <div key={idx} className="leading-relaxed">
                  <span className="text-slate-500 mr-2">[{new Date().toLocaleTimeString()}]</span>
                  <span className={line.includes('[ERROR]') ? 'text-rose-400' : line.includes('[SUCCESS]') ? 'text-emerald-400' : 'text-slate-300'}>
                    {line}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
          </>
        )}
      </div>
    </PageContainer>
  );
};
