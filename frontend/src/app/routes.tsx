import React, { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { SignInPage } from '../pages/auth/SignInPage';
import { SignUpPage } from '../pages/auth/SignUpPage';
import { useAuthStore } from '../stores/authStore';
import { Spinner } from '../components/ui/Spinner';

// Lazy load pages for better performance
const DashboardPage = lazy(() => import('../pages/dashboard/DashboardPage').then(m => ({ default: m.DashboardPage })));
const CasesPage = lazy(() => import('../pages/cases/CasesPage').then(m => ({ default: m.CasesPage })));
const CaseOverviewPage = lazy(() => import('../pages/cases/CaseOverviewPage').then(m => ({ default: m.CaseOverviewPage })));
const EvidencePage = lazy(() => import('../pages/evidence/EvidencePage').then(m => ({ default: m.EvidencePage })));
const EvidenceDetailPage = lazy(() => import('../pages/evidence/EvidenceDetailPage').then(m => ({ default: m.EvidenceDetailPage })));
const IntelligencePage = lazy(() => import('../pages/intelligence/IntelligencePage').then(m => ({ default: m.IntelligencePage })));
const StrategyPage = lazy(() => import('../pages/strategy/StrategyPage').then(m => ({ default: m.StrategyPage })));
const ExecutionPage = lazy(() => import('../pages/execution/ExecutionPage').then(m => ({ default: m.ExecutionPage })));
const FindingsPage = lazy(() => import('../pages/findings/FindingsPage').then(m => ({ default: m.FindingsPage })));
const VerificationPage = lazy(() => import('../pages/verification/VerificationPage').then(m => ({ default: m.VerificationPage })));
const ReportsPage = lazy(() => import('../pages/reports/ReportsPage').then(m => ({ default: m.ReportsPage })));
const AuditPage = lazy(() => import('../pages/audit/AuditPage').then(m => ({ default: m.AuditPage })));
const ToolsPage = lazy(() => import('../pages/tools/ToolsPage').then(m => ({ default: m.ToolsPage })));
const AccountPage = lazy(() => import('../pages/account/AccountPage').then(m => ({ default: m.AccountPage })));
const SettingsPage = lazy(() => import('../pages/settings/SettingsPage').then(m => ({ default: m.SettingsPage })));
const TermsPage = lazy(() => import('../pages/legal/TermsPage').then(m => ({ default: m.TermsPage })));
const PrivacyPage = lazy(() => import('../pages/legal/PrivacyPage').then(m => ({ default: m.PrivacyPage })));
const NotFoundPage = lazy(() => import('../pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));

const PageSuspense: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Suspense fallback={
    <div className="flex items-center justify-center h-full">
      <Spinner size="lg" />
    </div>
  }>
    {children}
  </Suspense>
);

const ProtectedRoute: React.FC = () => {
  const status = useAuthStore((s) => s.status);
  if (status === 'RESTORING') {
    return (
      <div className="flex items-center justify-center h-screen bg-stone-50">
        <Spinner size="lg" />
      </div>
    );
  }
  if (status === 'UNAUTHENTICATED') {
    return <Navigate to="/signin" replace />;
  }
  return <Outlet />;
};

export const router = createBrowserRouter([
  // Public auth & legal routes
  { path: '/signin', element: <SignInPage /> },
  { path: '/signup', element: <SignUpPage /> },
  { path: '/login', element: <Navigate to="/signin" replace /> },
  { path: '/terms', element: <PageSuspense><TermsPage /></PageSuspense> },
  { path: '/privacy', element: <PageSuspense><PrivacyPage /></PageSuspense> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <Navigate to="/dashboard" replace /> },
          { path: '/dashboard', element: <PageSuspense><DashboardPage /></PageSuspense> },
          { path: '/cases', element: <PageSuspense><CasesPage /></PageSuspense> },
          { path: '/cases/:caseId', element: <PageSuspense><CaseOverviewPage /></PageSuspense> },
          { path: '/cases/:caseId/evidence', element: <PageSuspense><EvidencePage /></PageSuspense> },
          { path: '/cases/:caseId/evidence/:evidenceId', element: <PageSuspense><EvidenceDetailPage /></PageSuspense> },
          { path: '/cases/:caseId/intelligence', element: <PageSuspense><IntelligencePage /></PageSuspense> },
          { path: '/cases/:caseId/strategy', element: <PageSuspense><StrategyPage /></PageSuspense> },
          { path: '/cases/:caseId/execution', element: <PageSuspense><ExecutionPage /></PageSuspense> },
          { path: '/cases/:caseId/findings', element: <PageSuspense><FindingsPage /></PageSuspense> },
          { path: '/cases/:caseId/verification', element: <PageSuspense><VerificationPage /></PageSuspense> },
          { path: '/cases/:caseId/report', element: <PageSuspense><ReportsPage /></PageSuspense> },
          { path: '/cases/:caseId/audit', element: <PageSuspense><AuditPage /></PageSuspense> },
          { path: '/tools', element: <PageSuspense><ToolsPage /></PageSuspense> },
          { path: '/account', element: <PageSuspense><AccountPage /></PageSuspense> },
          { path: '/settings', element: <PageSuspense><SettingsPage /></PageSuspense> },
          { path: '*', element: <PageSuspense><NotFoundPage /></PageSuspense> },
        ],
      },
    ],
  },
]);
