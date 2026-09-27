import React, { useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { AuthModal } from './AuthModal';
import { HomePage } from '../pages/HomePage';
import { InvestigationPage } from '../pages/InvestigationPage';
import { EvidencePage } from '../pages/EvidencePage';
import { InvestigationProcessPage } from '../pages/InvestigationProcessPage';
import { ResultsPage } from '../pages/ResultsPage';
import { AIAnalysisPage } from '../pages/AIAnalysisPage';
import { InvestigatorReviewPage } from '../pages/InvestigatorReviewPage';
import { ReportsPage } from '../pages/ReportsPage';
import { HistoryPage } from '../pages/HistoryPage';
import { AIProviderPage } from '../pages/AIProviderPage';
import { ProfilePage } from '../pages/ProfilePage';
import { SettingsPage } from '../pages/SettingsPage';
import { useInvestigationStore } from '../stores/investigationStore';
import { ShieldAlert, Loader2 } from 'lucide-react';

export const AppShell: React.FC = () => {
  const {
    currentTab,
    authStatus,
    backendState,
    backendError,
    initializeBackend,
    restoreSession,
    fetchInvestigations,
    fetchSystemStatus,
    setAuthModalOpen
  } = useInvestigationStore();

  useEffect(() => {
    initializeBackend();
  }, [initializeBackend]);

  useEffect(() => {
    if (backendState === 'READY') {
      restoreSession();
    }
  }, [backendState, restoreSession]);

  useEffect(() => {
    if (backendState === 'READY' && authStatus === 'AUTHENTICATED') {
      fetchSystemStatus();
      fetchInvestigations();
    }
  }, [backendState, authStatus, fetchInvestigations, fetchSystemStatus]);

  if (backendState === 'DISCOVERING') {
    return (
      <div className="h-screen w-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center space-y-4 font-mono select-none">
        <div className="p-3 bg-indigo-600/20 border border-indigo-500/30 rounded-2xl text-indigo-400">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
        <div className="text-center space-y-1">
          <h2 className="text-sm font-bold tracking-widest text-slate-200">ADFIR WORKSTATION</h2>
          <p className="text-xs text-slate-400">INITIALIZING DESKTOP BACKEND DISCOVERY...</p>
        </div>
      </div>
    );
  }

  if (backendState === 'STOPPING') {
    return (
      <div className="h-screen w-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center space-y-4 font-mono select-none">
        <div className="p-3 bg-amber-600/20 border border-amber-500/30 rounded-2xl text-amber-400">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
        <div className="text-center space-y-1">
          <h2 className="text-sm font-bold tracking-widest text-slate-200">ADFIR WORKSTATION</h2>
          <p className="text-xs text-amber-400">SHUTTING DOWN DESKTOP SERVICE...</p>
        </div>
      </div>
    );
  }

  if (backendState === 'UNAVAILABLE' || backendState === 'CRASHED') {
    return (
      <div className="h-screen w-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 relative font-mono select-none overflow-hidden">
        <div className="max-w-md w-full text-center space-y-6 z-10">
          <div className="inline-flex p-4 bg-red-950/40 border border-red-800/50 rounded-3xl text-red-400 mb-2">
            <ShieldAlert className="w-10 h-10" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wider text-slate-100">DESKTOP BACKEND SERVICE UNAVAILABLE</h1>
            <p className="text-xs text-red-400 mt-2">{backendError || 'Failed to establish secure communication with local ADFIR backend service.'}</p>
          </div>
          <button
            onClick={() => initializeBackend()}
            className="w-full py-3 bg-red-600 hover:bg-red-500 text-white rounded-xl font-bold tracking-wide shadow-lg shadow-red-500/25 transition-all text-xs"
          >
            RETRY BACKEND DISCOVERY
          </button>
        </div>
      </div>
    );
  }

  if (authStatus === 'RESTORING') {
    return (
      <div className="h-screen w-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center space-y-4 font-mono select-none">
        <div className="p-3 bg-indigo-600/20 border border-indigo-500/30 rounded-2xl text-indigo-400">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
        <div className="text-center space-y-1">
          <h2 className="text-sm font-bold tracking-widest text-slate-200">ADFIR WORKSTATION</h2>
          <p className="text-xs text-slate-400">VERIFYING AUTHENTICATED SESSION...</p>
        </div>
      </div>
    );
  }

  if (authStatus === 'UNAUTHENTICATED') {
    return (
      <div className="h-screen w-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 relative font-mono select-none overflow-hidden">
        <div className="absolute inset-0 bg-radial from-indigo-950/20 via-slate-950 to-slate-950 pointer-events-none" />
        <div className="max-w-md w-full text-center space-y-6 z-10">
          <div className="inline-flex p-4 bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl text-indigo-400 mb-2">
            <ShieldAlert className="w-10 h-10" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wider text-slate-100">ADFIR FORENSIC WORKSTATION</h1>
            <p className="text-xs text-slate-400 mt-1">AUTHENTICATION REQUIRED FOR CASE ACCESS</p>
          </div>
          <button
            onClick={() => setAuthModalOpen(true)}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold tracking-wide shadow-lg shadow-indigo-500/25 transition-all text-xs"
          >
            AUTHENTICATE INVESTIGATOR SESSION
          </button>
        </div>
        <AuthModal />
      </div>
    );
  }

  const renderPage = () => {
    switch (currentTab) {
      case 'home':
        return <HomePage />;
      case 'cases':
        return <InvestigationPage />;
      case 'evidence':
        return <EvidencePage />;
      case 'process':
      case 'investigation':
      case 'analysis':
        return <InvestigationProcessPage />;
      case 'results':
      case 'findings':
        return <ResultsPage />;
      case 'ai-analysis':
        return <AIAnalysisPage />;
      case 'review':
        return <InvestigatorReviewPage />;
      case 'reports':
        return <ReportsPage />;
      case 'history':
        return <HistoryPage />;
      case 'ai-provider':
        return <AIProviderPage />;
      case 'profile':
        return <ProfilePage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <HomePage />;
    }
  };

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden select-none font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-slate-950">
        <TopBar />
        <main className="flex-1 p-6 overflow-y-auto bg-slate-950">
          {renderPage()}
        </main>
      </div>
      <AuthModal />
    </div>
  );
};
