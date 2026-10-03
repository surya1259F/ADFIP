import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}

const variants = {
  primary: 'bg-slate-800 text-white hover:bg-slate-700 border border-slate-700 shadow-sm',
  secondary: 'bg-stone-100 text-slate-700 hover:bg-stone-200 border border-stone-200',
  ghost: 'text-slate-600 hover:text-slate-900 hover:bg-stone-100',
  danger: 'bg-red-600 text-white hover:bg-red-700 border border-red-700',
  outline: 'border border-stone-300 text-slate-700 hover:bg-stone-50',
};

const sizes = {
  sm: 'h-7 px-3 text-xs gap-1.5',
  md: 'h-8 px-4 text-sm gap-2',
  lg: 'h-10 px-5 text-sm gap-2',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}) => (
  <button
    className={cn(
      'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50',
      variants[variant],
      sizes[size],
      className
    )}
    disabled={disabled || loading}
    {...props}
  >
    {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : icon}
    {children}
  </button>
);
