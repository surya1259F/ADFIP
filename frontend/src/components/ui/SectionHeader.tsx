import React from 'react';
import { cn } from '../../lib/utils';

interface SectionHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const titleSizes = { sm: 'text-sm', md: 'text-base', lg: 'text-lg' };

export const SectionHeader: React.FC<SectionHeaderProps> = ({ title, description, action, className, size = 'md' }) => (
  <div className={cn('flex items-start justify-between mb-4', className)}>
    <div>
      <h2 className={cn('font-semibold text-slate-800', titleSizes[size])}>{title}</h2>
      {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);
