import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { truncateHash } from '../../lib/utils';

interface HashDisplayProps {
  hash: string;
  label?: string;
  chars?: number;
}

export const HashDisplay: React.FC<HashDisplayProps> = ({ hash, label, chars = 4 }) => {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable
    }
  };

  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs text-slate-600">
      {label && <span className="text-slate-400 font-sans text-[10px]">{label}</span>}
      <span title={hash}>{truncateHash(hash, chars)}</span>
      <button
        onClick={copy}
        className="text-slate-400 hover:text-slate-600 transition-colors"
        aria-label="Copy hash"
        type="button"
      >
        {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
      </button>
    </span>
  );
};
