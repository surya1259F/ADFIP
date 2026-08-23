import React from 'react';
import { PageContainer } from '../components/PageContainer';
import { FindingCard } from '../components/FindingCard';
import { EmptyState } from '../components/EmptyState';
import { useInvestigationStore } from '../stores/investigationStore';
import { FileSearch, RefreshCw, Network, ShieldCheck, AlertCircle } from 'lucide-react';

export const FindingsPage: React.FC = () => {
  const {
    activeInvestigation,
    findings,
    correlatedGroups,
    verificationResults,
    correlateAndVerify,
    loading
  } = useInvestigationStore();

  if (!activeInvestigation) {
    return (
      <PageContainer title="Forensic Findings">
        <EmptyState
          icon={AlertCircle}
          title="No Active Investigation"
          description="Please select an investigation first to review findings."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Structured Findings & Verification Matrix"
      subtitle={`Investigation: ${activeInvestigation.name} | Ground-truth findings extracted via forensic tools.`}
      actions={
        <button
          onClick={() => correlateAndVerify(activeInvestigation.id)}
          disabled={loading || findings.length === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-mono font-medium shadow-md shadow-indigo-500/20"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Execute Correlation & Verification</span>
        </button>
      }
    >
      <div className="space-y-6">
        {/* Findings Grid */}
        <div>
          <h3 className="text-xs font-mono text-slate-400 uppercase font-semibold mb-3">
            Structured Findings ({findings.length})
          </h3>
          {findings.length === 0 ? (
            <EmptyState
              icon={FileSearch}
              title="No Structured Findings"
              description="Execute specialist agents to extract forensic artifacts from ingested evidence."
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {findings.map((f) => (
                <FindingCard key={f.id} finding={f} />
              ))}
            </div>
          )}
        </div>

        {/* Correlation & Verification Split */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3">
            <h3 className="text-xs font-mono uppercase text-slate-200 font-bold flex items-center gap-2">
              <Network className="w-4 h-4 text-cyan-400" />
              Correlated Artifact Chains ({correlatedGroups.length})
            </h3>
            {correlatedGroups.length === 0 ? (
              <p className="text-xs text-slate-500 font-mono">Run correlation to cluster multi-source artifacts.</p>
            ) : (
              <div className="space-y-2">
                {correlatedGroups.map((grp, idx) => (
                  <div key={idx} className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs space-y-1">
                    <div className="flex items-center justify-between font-semibold text-slate-200">
                      <span>{grp.title}</span>
                      <span className="text-[10px] font-mono text-emerald-400">
                        {(grp.correlation_confidence * 100).toFixed(0)}% Match
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px]">{grp.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3">
            <h3 className="text-xs font-mono uppercase text-slate-200 font-bold flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Ground Truth Verification ({verificationResults.length})
            </h3>
            {verificationResults.length === 0 ? (
              <p className="text-xs text-slate-500 font-mono">Run verification to validate evidence references.</p>
            ) : (
              <div className="space-y-2">
                {verificationResults.map((ver, idx) => (
                  <div key={idx} className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs space-y-1">
                    <div className="flex items-center justify-between font-mono font-bold text-slate-300">
                      <span>{ver.verification_status}</span>
                      <span className="text-[10px] text-indigo-400">
                        Confidence: {(ver.confidence_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px]">{ver.reason}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </PageContainer>
  );
};
