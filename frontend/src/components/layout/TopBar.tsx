import React from 'react';
import { useLocation, useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FolderKanban, Sun, Moon } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { casesService } from '../../services/cases';

const ROUTE_LABELS: Record<string, string> = {
  '': 'Home',
  dashboard: 'Dashboard',
  cases: 'Cases',
  evidence: 'Evidence',
  intelligence: 'Intelligence',
  strategy: 'Strategy',
  execution: 'Execution',
  findings: 'Findings',
  verification: 'Verification',
  report: 'Reports',
  audit: 'Audit',
  tools: 'Tools & Agents',
  account: 'Account',
  settings: 'Settings',
  terms: 'Terms of Service',
  privacy: 'Privacy Policy',
};

export const TopBar: React.FC = () => {
  const { user } = useAuthStore();
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);
  const location = useLocation();
  const { caseId } = useParams<{ caseId?: string }>();

  const { data: activeCase } = useQuery({
    queryKey: ['cases', caseId],
    queryFn: () => casesService.get(caseId!),
    enabled: !!caseId,
    staleTime: 60_000,
  });

  // Build breadcrumbs from current path
  const segments = location.pathname.split('/').filter(Boolean);
  const crumbs: { label: string; path: string }[] = [];
  let acc = '';
  for (const seg of segments) {
    acc += '/' + seg;
    const label = seg === caseId
      ? (activeCase?.title || seg.slice(0, 8).toUpperCase())
      : (ROUTE_LABELS[seg] || seg);
    crumbs.push({ label, path: acc });
  }

  return (
    <header className="h-11 bg-white border-b border-stone-200 flex items-center px-4 gap-4 shrink-0">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-slate-500 flex-1 min-w-0" aria-label="Breadcrumb">
        <Link to="/dashboard" className="text-slate-400 hover:text-slate-700 font-semibold transition-colors">
          ADFIP
        </Link>
        {crumbs.map((crumb, i) => (
          <React.Fragment key={crumb.path}>
            <span className="text-stone-300">/</span>
            {i === crumbs.length - 1 ? (
              <span className="text-slate-800 font-medium truncate max-w-[240px]">{crumb.label}</span>
            ) : (
              <Link to={crumb.path} className="hover:text-slate-800 truncate max-w-[180px] transition-colors">
                {crumb.label}
              </Link>
            )}
          </React.Fragment>
        ))}
      </nav>

      {/* Right side contextual items */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Active Case Context Pill if inside a case */}
        {activeCase && (
          <Link
            to={`/cases/${activeCase.id}`}
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 bg-stone-100 hover:bg-stone-200 text-slate-700 rounded-md text-xs font-mono transition-colors"
          >
            <FolderKanban className="w-3.5 h-3.5 text-slate-500" />
            <span className="truncate max-w-[140px] font-sans font-medium">{activeCase.title}</span>
          </Link>
        )}

        {/* Light / Dark Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="p-1.5 text-slate-500 hover:text-slate-800 rounded-md hover:bg-stone-100 transition-colors cursor-pointer"
          aria-label="Toggle light and dark theme"
          title={theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-600" />
          )}
        </button>

        {/* Investigator Account & Avatar */}
        {user && (
          <Link
            to="/account"
            className="flex items-center gap-2 text-xs text-slate-600 hover:text-slate-900 transition-colors pl-1"
          >
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name || 'Investigator Avatar'}
                className="w-6 h-6 rounded-full object-cover border border-stone-300"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
            ) : (
              <div className="w-6 h-6 rounded-full bg-slate-800 text-white text-[10px] font-bold flex items-center justify-center">
                {(user.name || user.email).slice(0, 2).toUpperCase()}
              </div>
            )}
            <span className="hidden md:block truncate max-w-[130px] font-medium">
              {user.name || user.email}
            </span>
          </Link>
        )}
      </div>
    </header>
  );
};
