import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

interface SpinnerProps { className?: string; size?: 'sm' | 'md' | 'lg'; }

export const Spinner: React.FC<SpinnerProps> = ({ className, size = 'md' }) => {
  const sizes = { sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-7 h-7' };
  return <Loader2 className={cn('animate-spin text-slate-400', sizes[size], className)} />;
};
