import React, { useState } from 'react';
import { PageContainer } from '../components/PageContainer';
import { EmptyState } from '../components/EmptyState';
import { CreateCaseWizard } from '../components/CreateCaseWizard';
import { useInvestigationStore } from '../stores/investigationStore';
import {
  FolderDot,
  Plus,
  HardDrive,
  Cpu,
  FileText,
  Clock,
  ArrowRight,
  AlertCircle,
  FolderCheck
} from 'lucide-react';
import type { Case } from '../types';

export const HomePage: React.FC = () => {
  const {
    investigations,
    activeInvestigation,
    setActiveInvestigation,
    setCurrentTab,
    fetchInvestigations,
    evidenceList,
    findings,
    artifacts,
    error
  } = useInvestigationStore();

  const [showWizard, setShowWizard] = useState(false);

  const handleCaseCreated = async (newCase: Case) => {
    await fetchInvestigations();
    await setActiveInvestigation(newCase);
    setCurrentTab('investigation');
  };

  return (
    <PageContainer
      title="Digital Forensic Investigation Workstation"
      subtitle="Deterministic forensic tool execution, chain of custody integrity, and evidence-grounded incident response."
      actions={
        <button
          onClick={() => setShowWizard(true)}
          className="flex items-center gap-1.5 px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-cyan-900/20 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>+ Create New Case</span>
        </button>
      }
    >
      <div className="space-y-6">
        {error && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs rounded-xl flex items-center gap-2 font-mono">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Quick Action Station */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button
            onClick={() => setShowWizard(true)}
            className="p-4 bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 rounded-xl text-left transition-all group"
          >
            <div className="flex items-center justify-between mb-2">
              <FolderDot className="w-5 h-5 text-cyan-400 group-hover:scale-105 transition-transform" />
              <Plus className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <span className="font-semibold text-xs text-slate-200 block">Create Case</span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Initialize case workspace wizard</span>
          </button>

          <button
            onClick={() => setCurrentTab('evidence')}
            className="p-4 bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 rounded-xl text-left transition-all group"
          >
            <div className="flex items-center justify-between mb-2">
              <HardDrive className="w-5 h-5 text-cyan-400 group-hover:scale-105 transition-transform" />
              <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <span className="font-semibold text-xs text-slate-200 block">Ingest Evidence</span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Compute SHA-256 &amp; register</span>
          </button>

          <button
            onClick={() => setCurrentTab('analysis')}
            className="p-4 bg-slate-900/80 border border-slate-800 hover:border-purple-500/40 rounded-xl text-left transition-all group"
          >
            <div className="flex items-center justify-between mb-2">
              <Cpu className="w-5 h-5 text-purple-400 group-hover:scale-105 transition-transform" />
              <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <span className="font-semibold text-xs text-slate-200 block">Run Analysis</span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">TSK, Volatility, YARA, EVTX</span>
          </button>

          <button
            onClick={() => setCurrentTab('reports')}
            className="p-4 bg-slate-900/80 border border-slate-800 hover:border-emerald-500/40 rounded-xl text-left transition-all group"
          >
            <div className="flex items-center justify-between mb-2">
              <FileText className="w-5 h-5 text-emerald-400 group-hover:scale-105 transition-transform" />
              <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <span className="font-semibold text-xs text-slate-200 block">Synthesize Report</span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Court-ready DFIR document</span>
          </button>
        </div>

        {/* Active Investigation Context Banner */}
        {activeInvestigation ? (
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4 shadow-xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[10px] font-mono text-cyan-400 uppercase font-bold bg-cyan-500/10 px-2.5 py-0.5 rounded-full border border-cyan-500/20">
                    Active Case Workspace
                  </span>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                    {activeInvestigation.status}
                  </span>
                  {activeInvestigation.priority && (
                    <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2.5 py-0.5 rounded-full border border-amber-500/20">
                      {activeInvestigation.priority}
                    </span>
                  )}
                  {activeInvestigation.workspace_state === 'READY' && (
                    <span className="text-[10px] font-mono text-emerald-300 flex items-center gap-1 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                      <FolderCheck className="w-3 h-3 text-emerald-400" /> Workspace Ready
                    </span>
                  )}
                </div>
                <h3 className="text-base font-bold text-slate-100 font-mono">
                  {activeInvestigation.case_number ? `[${activeInvestigation.case_number}] ` : ''}
                  {activeInvestigation.name}
                </h3>
                {activeInvestigation.objective && (
                  <p className="text-xs text-cyan-300/80 mt-1 italic">
                    Objective: &ldquo;{activeInvestigation.objective}&rdquo;
                  </p>
                )}
                <p className="text-xs text-slate-400 mt-1">{activeInvestigation.description || 'No description provided.'}</p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setCurrentTab('investigation')}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-xl border border-cyan-500/30 transition-colors shadow-lg shadow-cyan-900/20"
                >
                  Open Case Workspace &rarr;
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block uppercase">Case ID</span>
                <span className="text-slate-300 truncate block font-mono">{activeInvestigation.id}</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block uppercase">Evidence Items</span>
                <span className="text-slate-300">{evidenceList.length} Ingested</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block uppercase font-medium">Extracted Artifacts</span>
                <span className="text-cyan-400">{artifacts.length} Stored</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block uppercase">Candidate Findings</span>
                <span className="text-amber-400">{findings.length} Generated</span>
              </div>
            </div>
          </div>
        ) : null}

        {/* Recent Cases Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase text-slate-400 font-semibold flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" /> Recent Investigations ({investigations.length})
            </h3>
            {investigations.length > 0 && (
              <button
                onClick={() => setCurrentTab('cases')}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300"
              >
                View All Cases &rarr;
              </button>
            )}
          </div>

          {investigations.length === 0 ? (
            <EmptyState
              icon={FolderDot}
              title="No cases yet"
              description="Create your first digital forensic investigation to begin evidence intake and analysis."
              actionLabel="+ Create New Case"
              onAction={() => setShowWizard(true)}
            />
          ) : (
            <div className="overflow-x-auto bg-slate-900/60 border border-slate-800 rounded-xl">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950 text-slate-400 text-[10px] uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-4">Case Details</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Workspace</th>
                    <th className="py-2.5 px-4">Created Date</th>
                    <th className="py-2.5 px-4">Metrics</th>
                    <th className="py-2.5 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-[11px]">
                  {investigations.slice(0, 5).map((inv) => (
                    <tr
                      key={inv.id}
                      onClick={() => setActiveInvestigation(inv)}
                      className="hover:bg-slate-800/30 cursor-pointer text-slate-300"
                    >
                      <td className="py-3 px-4">
                        <span className="font-semibold text-slate-100 block">
                          {inv.case_number ? `[${inv.case_number}] ` : ''}
                          {inv.name}
                        </span>
                        <span className="text-[10px] text-slate-500">{inv.id.substring(0, 8)}...</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          {inv.status}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                          inv.workspace_state === 'READY'
                            ? 'text-emerald-300 bg-emerald-950/60 border-emerald-800'
                            : 'text-amber-400 bg-amber-950/60 border-amber-800'
                        }`}>
                          {inv.workspace_state || 'NOT_INITIALIZED'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {new Date(inv.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {inv.evidence_count || 0} Ev | {inv.findings_count || 0} Findings
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveInvestigation(inv);
                            setCurrentTab('investigation');
                          }}
                          className="px-2.5 py-1 bg-cyan-900/40 hover:bg-cyan-800/60 text-cyan-300 border border-cyan-700/50 rounded text-[10px] transition-colors"
                        >
                          Select
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Case Creation Wizard Modal */}
      <CreateCaseWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        onCaseCreated={handleCaseCreated}
      />
    </PageContainer>
  );
};
