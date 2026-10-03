import React from 'react';
import { NavLink, useParams, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderKanban,
  Inbox,
  Globe,
  Blocks,
  Terminal,
  Activity,
  ShieldCheck,
  FileText,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Hash,
  ChevronDown,
  Wrench,
  Shield,
} from 'lucide-react';
import { useUIStore } from '../../stores/uiStore';
import { useAuthStore } from '../../stores/authStore';
import { Tooltip } from '../ui/Tooltip';
import { cn } from '../../lib/utils';
import { useQuery } from '@tanstack/react-query';
import { casesService } from '../../services/cases';

const CASE_NAV = [
  { id: 'evidence', label: 'Evidence', icon: Inbox, path: 'evidence' },
  { id: 'intelligence', label: 'Intelligence', icon: Globe, path: 'intelligence' },
  { id: 'strategy', label: 'Strategy', icon: Blocks, path: 'strategy' },
  { id: 'execution', label: 'Execution', icon: Terminal, path: 'execution' },
] as const;

const RESULTS_NAV = [
  { id: 'findings', label: 'Findings', icon: Activity, path: 'findings' },
  { id: 'verification', label: 'Verification', icon: ShieldCheck, path: 'verification' },
  { id: 'report', label: 'Reports', icon: FileText, path: 'report' },
] as const;

const OPERATIONS_NAV = [
  { id: 'audit', label: 'Audit', icon: Shield, path: 'audit' },
] as const;

const SYSTEM_NAV = [
  { id: 'tools', label: 'Tools & Agents', icon: Wrench, path: '/tools' },
  { id: 'settings', label: 'Settings', icon: Settings, path: '/settings' },
] as const;

interface NavItemProps {
  to: string;
  icon: React.ElementType;
  label: string;
  collapsed: boolean;
  end?: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ to, icon: Icon, label, collapsed, end }) => {
  const item = (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors group select-none',
          collapsed ? 'justify-center' : '',
          isActive
            ? 'bg-slate-900 text-white shadow-xs'
            : 'text-slate-600 hover:text-slate-900 hover:bg-stone-200/70'
        )
      }
    >
      <Icon className="w-4 h-4 shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  );

  if (collapsed) {
    return <Tooltip content={label} side="right">{item}</Tooltip>;
  }
  return item;
};

export const Sidebar: React.FC = () => {
  const { caseId } = useParams<{ caseId?: string }>();
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const { logout, user } = useAuthStore();
  const navigate = useNavigate();

  // Load active case details if currently in case context
  const { data: activeCase } = useQuery({
    queryKey: ['cases', caseId],
    queryFn: () => casesService.get(caseId!),
    enabled: !!caseId,
    staleTime: 60_000,
  });

  const handleLogout = async () => {
    await logout();
    navigate('/signin');
  };

  const resolvedCaseId = caseId;

  return (
    <aside
      className={cn(
        'bg-[#fbfbf9] border-r border-stone-200 flex flex-col shrink-0 transition-all duration-200 select-none z-10',
        collapsed ? 'w-14' : 'w-56'
      )}
    >
      {/* Brand Header */}
      <div className={cn('px-3 py-3 flex items-center border-b border-stone-200/80', collapsed ? 'justify-center' : 'gap-2.5')}>
        <div className="p-1.5 bg-slate-900 rounded-md shrink-0 shadow-xs">
          <Shield className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-900 tracking-tight leading-none">ADFIP</p>
            <p className="text-[10px] text-slate-500 leading-tight mt-0.5 font-medium">Digital Forensics</p>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className={cn('text-slate-400 hover:text-slate-600 transition-colors rounded p-1 cursor-pointer', collapsed ? '' : 'ml-auto')}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          type="button"
        >
          {collapsed
            ? <PanelLeftOpen className="w-3.5 h-3.5" />
            : <PanelLeftClose className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-0.5 px-2">
        {/* Global Navigation */}
        <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" collapsed={collapsed} end />
        <NavItem to="/cases" icon={FolderKanban} label="Cases" collapsed={collapsed} end />

        {/* Current Case Context */}
        {resolvedCaseId && (
          <div className="pt-2">
            {!collapsed && (
              <div className="pt-2 pb-1">
                <div className="flex items-center gap-1 px-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  <Hash className="w-3 h-3" />
                  <span>Active Investigation</span>
                </div>
                <button
                  onClick={() => navigate('/cases')}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 bg-white border border-stone-200 rounded-md hover:bg-stone-50 transition-colors shadow-2xs text-left cursor-pointer"
                  type="button"
                  title="Switch case"
                >
                  <div className="min-w-0 pr-1">
                    <p className="text-[10px] font-mono text-slate-400 leading-none mb-0.5">
                      {resolvedCaseId.slice(0, 8).toUpperCase()}
                    </p>
                    <p className="text-xs font-medium text-slate-800 truncate leading-tight">
                      {activeCase?.title || 'Loading case...'}
                    </p>
                  </div>
                  <ChevronDown className="w-3 h-3 text-slate-400 shrink-0" />
                </button>
              </div>
            )}

            {!collapsed && (
              <p className="px-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider pt-2.5 pb-0.5">
                Investigation
              </p>
            )}
            {CASE_NAV.map((item) => (
              <NavItem
                key={item.id}
                to={`/cases/${resolvedCaseId}/${item.path}`}
                icon={item.icon}
                label={item.label}
                collapsed={collapsed}
              />
            ))}

            {!collapsed && (
              <p className="px-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider pt-3 pb-0.5">
                Results
              </p>
            )}
            {RESULTS_NAV.map((item) => (
              <NavItem
                key={item.id}
                to={`/cases/${resolvedCaseId}/${item.path}`}
                icon={item.icon}
                label={item.label}
                collapsed={collapsed}
              />
            ))}

            {!collapsed && (
              <p className="px-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider pt-3 pb-0.5">
                Governance
              </p>
            )}
            {OPERATIONS_NAV.map((item) => (
              <NavItem
                key={item.id}
                to={`/cases/${resolvedCaseId}/${item.path}`}
                icon={item.icon}
                label={item.label}
                collapsed={collapsed}
              />
            ))}
          </div>
        )}

        {/* Platform System Operations */}
        <div className="pt-3">
          {!collapsed && (
            <p className="px-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider pb-0.5">
              Operations
            </p>
          )}
          {SYSTEM_NAV.map((item) => (
            <NavItem key={item.id} to={item.path} icon={item.icon} label={item.label} collapsed={collapsed} />
          ))}
        </div>
      </nav>

      {/* Footer / Account */}
      <div className="border-t border-stone-200/80 p-2">
        {!collapsed && user && (
          <div className="px-2 py-1.5 mb-1 bg-stone-100/60 rounded-md">
            <p className="text-xs font-semibold text-slate-800 truncate">{user.name || user.email}</p>
            <p className="text-[10px] text-slate-500 truncate font-mono uppercase">
              {user.role || 'INVESTIGATOR'}
            </p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className={cn(
            'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-slate-600 hover:text-red-700 hover:bg-red-50/80 transition-colors cursor-pointer',
            collapsed ? 'justify-center' : ''
          )}
          title="Sign out of ADFIP"
          type="button"
        >
          <LogOut className="w-3.5 h-3.5 shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  );
};
