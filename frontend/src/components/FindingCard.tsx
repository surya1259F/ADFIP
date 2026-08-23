import React from 'react';
import type { Finding } from '../types';
import { StatusIndicator } from './StatusIndicator';

interface FindingCardProps {
  finding: Finding;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding }) => {
  return (
    <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-[10px] font-mono text-indigo-400 uppercase bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
            {finding.agent} &rarr; {finding.tool}
          </span>
          <h4 className="font-semibold text-xs text-slate-200 mt-2">{finding.title}</h4>
        </div>
        <StatusIndicator status={finding.verification_status} />
      </div>

      <p className="text-xs text-slate-400 leading-relaxed">{finding.description}</p>

      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[11px] font-mono text-slate-500">
        <span>Ref: {finding.evidence_reference || 'N/A'}</span>
        <span>Confidence: {finding.confidence !== undefined && finding.confidence !== null ? `${(finding.confidence * 100).toFixed(0)}%` : 'Unscored'}</span>
      </div>
    </div>
  );
};
