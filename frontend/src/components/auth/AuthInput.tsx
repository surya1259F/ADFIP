import React from 'react';
import { cn } from '../../lib/utils';

export interface AuthInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
  error?: string;
}

export const AuthInput: React.FC<AuthInputProps> = ({
  icon,
  error,
  className,
  ...props
}) => (
  <div className="w-full text-left">
    <div className="relative flex items-center">
      {icon && (
        <span className="absolute left-3.5 flex items-center justify-center text-gray-400 pointer-events-none">
          {icon}
        </span>
      )}
      <input
        className={cn(
          'w-full h-[42px] rounded-[14px] bg-[#f8f9fb] border border-[#e5e7eb] text-sm text-gray-900 placeholder:text-gray-400 transition-colors focus:outline-none focus:border-slate-500 focus:bg-white focus:ring-2 focus:ring-slate-200/60',
          icon ? 'pl-10 pr-3.5' : 'px-3.5',
          error && 'border-red-400 bg-red-50/20 focus:border-red-500 focus:ring-red-100',
          className
        )}
        {...props}
      />
    </div>
    {error && (
      <p className="text-[12px] text-red-600 mt-1 pl-1 font-medium">{error}</p>
    )}
  </div>
);
