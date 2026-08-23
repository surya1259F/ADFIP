import React, { useState } from 'react';
import { PageContainer } from '../components/PageContainer';
import { InvestigationHeader } from '../components/InvestigationHeader';
import { EmptyState } from '../components/EmptyState';
import { useInvestigationStore } from '../stores/investigationStore';
import { Plus, FolderDot, Play, CheckCircle2 } from 'lucide-react';

export const InvestigationPage: React.FC = () => {
  const {
    investigations,
    activeInvestigation,
    createInvestigation,
    setActiveInvestigation,
    currentPlan,
    generatePlan,
    loading
  } = useInvestigationStore();

  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;
    await createInvestigation(name, description);
    setShowModal(false);
    setName('');
    setDescription('');
  };

  return (
    <PageContainer
      title="Investigation Management"
      subtitle="Initialize, switch, and formulate autonomous multi-agent investigation plans."
      actions={
        <div className="flex items-center gap-3">
          {activeInvestigation && (
            <button
              onClick={() => generatePlan(activeInvestigation.id)}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono border border-slate-700 transition-colors"
            >
              <Play className="w-3.5 h-3.5 text-indigo-400" />
              <span>Generate Plan</span>
            </button>
          )}
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-mono font-medium shadow-md shadow-indigo-500/20 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Investigation</span>
          </button>
        </div>
      }
    >
      <div className="space-y-6">
        {activeInvestigation && <InvestigationHeader investigation={activeInvestigation} />}

        {/* Investigation List */}
        <div>
          <h3 className="text-xs font-mono text-slate-400 uppercase font-semibold mb-3">
            Investigation Workspaces ({investigations.length})
          </h3>
          {investigations.length === 0 ? (
            <EmptyState
              icon={FolderDot}
              title="No Investigations Found"
              description="Create your first digital forensic investigation workspace to begin."
              actionLabel="Create Investigation"
              onAction={() => setShowModal(true)}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {investigations.map((inv) => {
                const isActive = activeInvestigation?.id === inv.id;
                return (
                  <div
                    key={inv.id}
                    onClick={() => setActiveInvestigation(inv)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isActive
                        ? 'bg-slate-900 border-indigo-500/60 shadow-lg shadow-indigo-500/10'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-bold text-xs text-slate-200">{inv.name}</h4>
                        <span className="text-[10px] font-mono text-slate-500">ID: {inv.id}</span>
                      </div>
                      {isActive && (
                        <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" /> ACTIVE
                        </span>
                      )}
                    </div>
                    {inv.description && (
                      <p className="text-xs text-slate-400 mt-2 line-clamp-2">{inv.description}</p>
                    )}
                    <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
                      <span>{new Date(inv.created_at).toLocaleDateString()}</span>
                      <span className="text-indigo-400">
                        {inv.evidence_count || 0} Ev | {inv.findings_count || 0} Findings
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Investigation Plan View */}
        {currentPlan && (
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase text-slate-200 font-bold">
                Investigation Strategy Plan ({currentPlan.total_tasks} Tasks)
              </h3>
              <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                {currentPlan.status}
              </span>
            </div>
            <p className="text-xs text-slate-300 font-mono bg-slate-950 p-3 rounded border border-slate-800/80">
              {currentPlan.strategy_summary}
            </p>
            <div className="space-y-2">
              {currentPlan.steps.map((step) => (
                <div
                  key={step.step_id}
                  className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 font-mono text-[10px] flex items-center justify-center font-bold">
                      {step.priority}
                    </span>
                    <div>
                      <span className="font-semibold text-slate-200">{step.agent}</span>
                      <span className="text-slate-500 text-xs font-mono"> &rarr; {step.tool}</span>
                      <span className="text-slate-400 block text-[11px]">{step.action}</span>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    Target: {step.evidence_name || step.evidence_id || 'N/A'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-100 font-mono uppercase">Initialize Investigation Case</h3>
            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-400 mb-1">Investigation Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Incident 2026-08 - Workstation Compromise"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 font-sans"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-400 mb-1">Scope & Incident Description</label>
                <textarea
                  rows={3}
                  placeholder="Initial incident scope and parameters..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 font-sans"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageContainer>
  );
};
