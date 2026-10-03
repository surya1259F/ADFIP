import React from 'react';
import { cn } from '../../lib/utils';

export interface AuthCardProps {
  children: React.ReactNode;
  className?: string;
}

export const AuthCard: React.FC<AuthCardProps> = ({ children, className }) => (
  <div
    className={cn(
      'w-full max-w-[430px] p-8 sm:p-[36px] rounded-[28px] border border-[#dbeafe] bg-gradient-to-b from-[#f8fbff] to-[#ffffff] shadow-[0_20px_40px_rgba(0,0,0,0.10)] text-center transition-all my-auto',
      className
    )}
  >
    {children}
  </div>
);
