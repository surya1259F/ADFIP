import React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../../lib/utils';

export interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ items, className }) => (
  <nav className={cn('flex items-center gap-1 text-xs text-slate-500', className)} aria-label="Breadcrumb">
    {items.map((item, i) => (
      <React.Fragment key={i}>
        {i > 0 && <span className="text-stone-300">/</span>}
        {item.path && i < items.length - 1 ? (
          <Link to={item.path} className="hover:text-slate-700 transition-colors">{item.label}</Link>
        ) : (
          <span className={i === items.length - 1 ? 'text-slate-700 font-medium' : ''}>{item.label}</span>
        )}
      </React.Fragment>
    ))}
  </nav>
);
