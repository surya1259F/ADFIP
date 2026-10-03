import React from 'react';
import { cn } from '../../lib/utils';

export const Skeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('animate-pulse bg-stone-200 rounded', className)} />
);

export const SkeletonRow: React.FC<{ cols?: number }> = ({ cols = 4 }) => (
  <div className="flex gap-4 py-3 border-b border-stone-100">
    {Array.from({ length: cols }).map((_, i) => (
      <Skeleton key={i} className="h-4 flex-1" />
    ))}
  </div>
);
