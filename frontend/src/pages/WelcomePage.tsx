import React from 'react';
import { PageContainer } from '../components/PageContainer';
import { useInvestigationStore } from '../stores/investigationStore';
import { ShieldCheck, HardDrive, Cpu, ArrowRight, FolderDot, FileSearch } from 'lucide-react';

export const WelcomePage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const { investigations, activeInvestigation, systemStatus } = useInvestigationStore();

  return (
    <PageContainer
      title="ADFIR — AI-Assisted Digital Forensic Investigation Platform"
      subtitle="Startup-grade, evidence-driven desktop DFIR workspace. Ground truth originates from forensic tools; LLM acts as the reasoning and reporting layer."
    >
      <div className="space-y-6">
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950/30 to-slate-900 border border-slate-800 p-6 rounded-xl space-y-3">
          <div className="flex items-center gap-2 text-indigo-400 font-mono text-xs font-bold">
            <ShieldCheck className="w-4 h-4" />
            <span>GROUND-TRUTH EVIDENCE PRINCIPLE</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            ADFIR strictly forbids the generative LLM from fabricating forensic conclusions or directly manipulating evidence.
            Every conclusion must be rooted in deterministic tools (The Sleuth Kit, YARA, ExifTool, Volatility 3),
            verified through cryptographic SHA-256 chain-of-custody, and correlated across multi-source artifacts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <div className="text-slate-400 text-xs font-mono mb-1 flex items-center justify-between">
              <span>INVESTIGATIONS</span>
              <FolderDot className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-slate-100 font-mono">{investigations.length}</div>
            <p className="text-[11px] text-slate-500 mt-1">{activeInvestigation ? `Active: ${activeInvestigation.name}` : 'None active'}</p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <div className="text-slate-400 text-xs font-mono mb-1 flex items-center justify-between">
              <span>EVIDENCE INGESTION</span>
              <HardDrive className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold text-slate-100 font-mono">
              {activeInvestigation?.evidence_count || 0}
            </div>
            <p className="text-[11px] text-emerald-400 mt-1">Streaming 8MB SHA-256</p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <div className="text-slate-400 text-xs font-mono mb-1 flex items-center justify-between">
              <span>STRUCTURED FINDINGS</span>
              <FileSearch className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-slate-100 font-mono">
              {activeInvestigation?.findings_count || 0}
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Ground-truth verified</p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
            <div className="text-slate-400 text-xs font-mono mb-1 flex items-center justify-between">
              <span>SYSTEM ENGINES</span>
              <Cpu className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-slate-100 font-mono">
              {systemStatus ? Object.keys(systemStatus.forensic_tools).length : 4} Tools
            </div>
            <p className="text-[11px] text-slate-500 mt-1">{systemStatus?.platform || 'Linux'} Platform</p>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-xl space-y-4">
          <h3 className="text-xs font-mono uppercase text-slate-400 font-semibold tracking-wider">
            Standard Investigation Lifecycle
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 flex flex-col justify-between">
              <div>
                <span className="font-mono text-indigo-400 font-bold">1. Cases</span>
                <p className="text-slate-400 text-[11px] mt-1">Create or switch active investigation workspace.</p>
              </div>
              <button
                onClick={() => onNavigate('investigation')}
                className="mt-3 flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-medium font-mono text-[11px]"
              >
                Go to Cases <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 flex flex-col justify-between">
              <div>
                <span className="font-mono text-cyan-400 font-bold">2. Intake & Hash</span>
                <p className="text-slate-400 text-[11px] mt-1">Register disk/memory files & establish chain of custody.</p>
              </div>
              <button
                onClick={() => onNavigate('evidence')}
                className="mt-3 flex items-center gap-1 text-cyan-400 hover:text-cyan-300 font-medium font-mono text-[11px]"
              >
                Go to Evidence <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 flex flex-col justify-between">
              <div>
                <span className="font-mono text-amber-400 font-bold">3. Findings & Verify</span>
                <p className="text-slate-400 text-[11px] mt-1">Extract artifacts and cross-correlate causal events.</p>
              </div>
              <button
                onClick={() => onNavigate('findings')}
                className="mt-3 flex items-center gap-1 text-amber-400 hover:text-amber-300 font-medium font-mono text-[11px]"
              >
                Go to Findings <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800/80 flex flex-col justify-between">
              <div>
                <span className="font-mono text-emerald-400 font-bold">4. 19-Section Report</span>
                <p className="text-slate-400 text-[11px] mt-1">Synthesize court-ready report distinguishing fact vs inference.</p>
              </div>
              <button
                onClick={() => onNavigate('reports')}
                className="mt-3 flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-medium font-mono text-[11px]"
              >
                Go to Reports <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
};
