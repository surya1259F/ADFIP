import React from 'react';
import {
  Home,
  FolderDot,
  HardDrive,
  Activity,
  Layers,
  Sparkles,
  ShieldCheck,
  FileText,
  Clock,
  Settings,
  User,
  ShieldAlert,
  LogOut
} from 'lucide-react';
import { useInvestigationStore } from '../stores/investigationStore';

export const Sidebar: React.FC = () => {
  const { currentTab, setCurrentTab, currentDecision } = useInvestigationStore();

  const workflowNav = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'cases', label: 'Cases', icon: FolderDot },
    { id: 'evidence', label: 'Evidence', icon: HardDrive },
    { id: 'process', label: 'Execution Engine', icon: Activity },
    { id: 'results', label: 'Results Matrix', icon: Layers },
    { id: 'ai-analysis', label: 'AI Reasoning', icon: Sparkles },
    { id: 'review', label: 'Decision Gate', icon: ShieldCheck, badge: currentDecision?.decision },
    { id: 'reports', label: 'Reports Studio', icon: FileText },
  ];

  const workstationNav = [
    { id: 'history', label: 'History', icon: Clock },
    { id: 'ai-provider', label: 'AI Provider', icon: Sparkles },
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-60 bg-slate-900 border-r border-slate-800 flex flex-col justify-between select-none shrink-0 font-sans">
      <div className="overflow-y-auto">
        {/* Brand Header */}
        <div className="px-5 py-4 flex items-center gap-3 border-b border-slate-800">
          <div className="p-1.5 bg-indigo-600 rounded-lg text-white shadow-md shadow-indigo-500/20">
            <ShieldAlert className="w-5 h-5 text-indigo-100" />
          </div>
          <div>
            <h1 className="font-bold text-sm text-slate-100 tracking-wider font-mono">ADFIR</h1>
            <p className="text-[10px] text-slate-400 font-mono">Forensic Workstation</p>
          </div>
        </div>

        {/* 16-Step Investigation Workflow Navigation */}
        <div className="p-3 space-y-1">
          <span className="px-3 text-[10px] font-mono text-slate-500 uppercase font-semibold block mb-1">
            Investigation Workflow
          </span>
          {workflowNav.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold ${
                    item.badge === 'CONFIRM' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Workstation Support Navigation */}
        <div className="p-3 pt-1 space-y-1 border-t border-slate-800/60">
          <span className="px-3 text-[10px] font-mono text-slate-500 uppercase font-semibold block mb-1">
            Workstation
          </span>
          {workstationNav.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer Status & Logout */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40 text-[10px] font-mono text-slate-500 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span className="text-slate-400 font-semibold">Deterministic Core</span>
          </div>
          <span>v0.1.0</span>
        </div>
        <button
          onClick={() => useInvestigationStore.getState().logout()}
          className="w-full flex items-center justify-center gap-2 py-1.5 bg-slate-800/80 hover:bg-rose-950/50 hover:text-rose-300 text-slate-400 rounded border border-slate-700/60 hover:border-rose-800/60 transition-colors text-xs"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
