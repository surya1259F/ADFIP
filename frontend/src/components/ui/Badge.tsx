import React from 'react';
import { cn, getStatusTone } from '../../lib/utils';

type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'active';

const toneClasses: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-600 border-slate-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  danger: 'bg-red-50 text-red-700 border-red-200',
  active: 'bg-blue-50 text-blue-700 border-blue-200',
};

interface BadgeProps {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, tone = 'neutral', className }) => (
  <span
    className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border',
      toneClasses[tone],
      className
    )}
  >
    {children}
  </span>
);

interface StatusBadgeProps {
  status?: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status = 'UNKNOWN', className }) => {
  const displayStatus = status || 'UNKNOWN';
  return (
    <Badge tone={getStatusTone(displayStatus)} className={className}>
      {displayStatus}
    </Badge>
  );
};
