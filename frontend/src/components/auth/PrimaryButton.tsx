import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface PrimaryButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

export const PrimaryButton: React.FC<PrimaryButtonProps> = ({
  loading = false,
  children,
  className,
  disabled,
  ...props
}) => (
  <button
    className={cn(
      'w-full h-[48px] rounded-[14px] bg-gradient-to-b from-[#2d3748] to-[#111827] text-white text-[16px] font-semibold flex items-center justify-center gap-2 shadow-sm hover:from-[#374151] hover:to-[#1f2937] active:scale-[0.99] transition-all focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100 cursor-pointer',
      className
    )}
    disabled={disabled || loading}
    {...props}
  >
    {loading && <Loader2 className="w-4 h-4 animate-spin text-white" />}
    <span>{children}</span>
  </button>
);
