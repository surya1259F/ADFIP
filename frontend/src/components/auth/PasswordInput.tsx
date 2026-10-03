import React, { useState } from 'react';
import { Lock, Eye, EyeOff } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface PasswordInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  error?: string;
  showIcon?: boolean;
}

export const PasswordInput: React.FC<PasswordInputProps> = ({
  error,
  className,
  showIcon = true,
  placeholder = 'Password',
  ...props
}) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="w-full text-left">
      <div className="relative flex items-center">
        {showIcon && (
          <span className="absolute left-3.5 flex items-center justify-center text-gray-400 pointer-events-none">
            <Lock className="w-4 h-4" />
          </span>
        )}
        <input
          type={showPassword ? 'text' : 'password'}
          placeholder={placeholder}
          className={cn(
            'w-full h-[42px] rounded-[14px] bg-[#f8f9fb] border border-[#e5e7eb] text-sm text-gray-900 placeholder:text-gray-400 transition-colors focus:outline-none focus:border-slate-500 focus:bg-white focus:ring-2 focus:ring-slate-200/60',
            showIcon ? 'pl-10 pr-10' : 'pl-3.5 pr-10',
            error && 'border-red-400 bg-red-50/20 focus:border-red-500 focus:ring-red-100',
            className
          )}
          {...props}
        />
        <button
          type="button"
          onClick={() => setShowPassword((prev) => !prev)}
          className="absolute right-3.5 text-gray-400 hover:text-gray-600 transition-colors focus:outline-none p-0.5 rounded cursor-pointer"
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          tabIndex={-1}
        >
          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      {error && (
        <p className="text-[12px] text-red-600 mt-1 pl-1 font-medium">{error}</p>
      )}
    </div>
  );
};
