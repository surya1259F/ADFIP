import React from 'react';
import {
  ShieldAlert,
  FolderDot,
  HardDrive,
  FileSearch,
  FileText,
  Home
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab }) => {
  const items = [
    { id: 'welcome', label: 'Welcome', icon: Home },
    { id: 'investigation', label: 'Investigation', icon: FolderDot },
    { id: 'evidence', label: 'Evidence', icon: HardDrive },
    { id: 'findings', label: 'Findings', icon: FileSearch },
    { id: 'reports', label: 'Reports', icon: FileText },
  ];

  return (
    <aside className="w-56 bg-slate-900 border-r border-slate-800 flex flex-col justify-between select-none">
      <div>
        <div className="px-5 py-5 flex items-center gap-3 border-b border-slate-800">
          <div className="p-1.5 bg-indigo-600 rounded-lg text-white shadow-md shadow-indigo-500/20">
            <ShieldAlert className="w-5 h-5 text-indigo-100" />
          </div>
          <div>
            <h1 className="font-bold text-sm text-slate-100 tracking-wider">ADFIR</h1>
            <p className="text-[10px] text-slate-500 font-mono">Desktop DFIR</p>
          </div>
        </div>

        <nav className="p-3 space-y-1">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-3 border-t border-slate-800 bg-slate-950/40 text-[10px] font-mono text-slate-500">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span className="text-slate-400 font-bold">Native Desktop Core</span>
        </div>
        <span>ADFIR v0.1.0</span>
      </div>
    </aside>
  );
};
