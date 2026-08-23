import React from 'react';
import { useInvestigationStore } from '../stores/investigationStore';
import { ShieldCheck, User, AlertCircle, Cpu } from 'lucide-react';

export const TopBar: React.FC = () => {
  const { activeInvestigation, systemStatus } = useInvestigationStore();

  return (
    <header className="h-14 bg-slate-900/80 backdrop-blur border-b border-slate-800 px-6 flex items-center justify-between text-xs font-mono select-none">
      <div className="flex items-center gap-3">
        {activeInvestigation ? (
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-medium">ACTIVE CASE:</span>
            <span className="font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
              {activeInvestigation.name}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-amber-400">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>NO INVESTIGATION ACTIVE</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded border border-emerald-500/20">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>EVIDENCE IMMUTABLE</span>
        </div>

        <div className="flex items-center gap-1.5 text-slate-400">
          <Cpu className="w-3.5 h-3.5 text-slate-500" />
          <span>{systemStatus?.logical_cpus || 2} Cores | {systemStatus?.platform || 'Linux'}</span>
        </div>

        <div className="flex items-center gap-1.5 text-slate-400">
          <User className="w-3.5 h-3.5 text-slate-500" />
          <span>local-user</span>
        </div>
      </div>
    </header>
  );
};
