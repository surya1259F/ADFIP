import React from 'react';
import type { Evidence } from '../types';
import { StatusIndicator } from './StatusIndicator';

interface EvidenceDetailProps {
  evidence: Evidence;
}

export const EvidenceDetail: React.FC<EvidenceDetailProps> = ({ evidence }) => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-xl space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-200">{evidence.name}</h3>
        <StatusIndicator status={evidence.integrity_status} />
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800">
          <span className="text-slate-500 block text-[10px]">CATEGORY</span>
          <span className="text-slate-300">{evidence.evidence_type}</span>
        </div>
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800">
          <span className="text-slate-500 block text-[10px]">FILE SIZE</span>
          <span className="text-slate-300">{(evidence.size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
        </div>
      </div>

      <div className="bg-slate-950 p-3 rounded border border-slate-800 font-mono text-xs space-y-1">
        <span className="text-slate-500 block text-[10px]">CRYPTOGRAPHIC SHA-256 HASH</span>
        <span className="text-indigo-400 break-all">{evidence.sha256}</span>
      </div>

      <div className="bg-slate-950 p-3 rounded border border-slate-800 font-mono text-xs space-y-1">
        <span className="text-slate-500 block text-[10px]">ORIGINAL EVIDENCE PATH</span>
        <span className="text-slate-300 break-all">{evidence.original_path}</span>
      </div>

      {evidence.notes && (
        <div className="text-xs text-slate-400 bg-slate-950/60 p-3 rounded border border-slate-800/60">
          <span className="text-slate-500 block text-[10px] font-mono mb-1">NOTES</span>
          {evidence.notes}
        </div>
      )}
    </div>
  );
};
