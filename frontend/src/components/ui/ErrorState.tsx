import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from './Button';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Unable to load data',
  message,
  onRetry,
}) => (
  <div className="flex flex-col items-center justify-center py-16 text-center">
    <AlertTriangle className="w-8 h-8 text-amber-400 mb-3" />
    <h3 className="text-sm font-semibold text-slate-700 mb-1">{title}</h3>
    <p className="text-xs text-slate-500 max-w-sm mb-4">{message}</p>
    {onRetry && <Button onClick={onRetry} size="sm">Retry</Button>}
  </div>
);
