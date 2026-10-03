import React from 'react';
import { cn } from '../../lib/utils';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className, padding = true }) => (
  <div className={cn(
    'bg-white border border-stone-200 rounded-lg shadow-sm',
    padding && 'p-4',
    className
  )}>
    {children}
  </div>
);
