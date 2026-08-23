import React, { useEffect, useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { WelcomePage } from '../pages/WelcomePage';
import { InvestigationPage } from '../pages/InvestigationPage';
import { EvidencePage } from '../pages/EvidencePage';
import { FindingsPage } from '../pages/FindingsPage';
import { ReportsPage } from '../pages/ReportsPage';
import { useInvestigationStore } from '../stores/investigationStore';

export const AppShell: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('welcome');
  const { fetchInvestigations, fetchSystemStatus } = useInvestigationStore();

  useEffect(() => {
    fetchSystemStatus();
    fetchInvestigations();
  }, []);

  const renderPage = () => {
    switch (currentTab) {
      case 'welcome':
        return <WelcomePage onNavigate={setCurrentTab} />;
      case 'investigation':
        return <InvestigationPage />;
      case 'evidence':
        return <EvidencePage />;
      case 'findings':
        return <FindingsPage />;
      case 'reports':
        return <ReportsPage />;
      default:
        return <WelcomePage onNavigate={setCurrentTab} />;
    }
  };

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden select-none">
      <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-slate-950">
        <TopBar />
        <main className="flex-1 p-6 overflow-y-auto bg-slate-950">
          {renderPage()}
        </main>
      </div>
    </div>
  );
};
