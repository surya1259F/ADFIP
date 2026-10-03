import React from 'react';
import { cn } from '../../lib/utils';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action, className }) => (
  <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
    {icon && <div className="mb-4 text-stone-300">{icon}</div>}
    <h3 className="text-sm font-semibold text-slate-700 mb-1">{title}</h3>
    {description && <p className="text-xs text-slate-500 max-w-sm mb-4">{description}</p>}
    {action}
  </div>
);
