import React from 'react';
import { PageContainer } from '../components/PageContainer';
import { EmptyState } from '../components/EmptyState';
import { useInvestigationStore } from '../stores/investigationStore';
import { FileText, Download, Play, AlertCircle } from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const {
    activeInvestigation,
    activeReport,
    generateReport,
    loading
  } = useInvestigationStore();

  if (!activeInvestigation) {
    return (
      <PageContainer title="Investigation Reports">
        <EmptyState
          icon={AlertCircle}
          title="No Active Investigation"
          description="Please select an investigation first to synthesize reports."
        />
      </PageContainer>
    );
  }

  const handleExport = () => {
    if (!activeReport) return;
    const blob = new Blob([activeReport.full_report_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ADFIR_Report_${activeInvestigation.name.replace(/\s+/g, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <PageContainer
      title="19-Section Court-Ready Report Studio"
      subtitle={`Investigation: ${activeInvestigation.name} | Distinguishes [FACT], [INFERENCE], and [UNVERIFIED].`}
      actions={
        <div className="flex items-center gap-3">
          <button
            onClick={() => generateReport(activeInvestigation.id)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-mono font-medium shadow-md shadow-indigo-500/20"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{activeReport ? 'Regenerate 19-Section Report' : 'Synthesize 19-Section Report'}</span>
          </button>
          {activeReport && (
            <button
              onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono border border-slate-700"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Markdown</span>
            </button>
          )}
        </div>
      }
    >
      <div className="space-y-6">
        {activeReport ? (
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 overflow-y-auto max-h-[750px] space-y-4">
            <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-relaxed">
              {activeReport.full_report_markdown}
            </pre>
          </div>
        ) : (
          <EmptyState
            icon={FileText}
            title="No Report Generated"
            description="Click 'Synthesize 19-Section Report' to generate a formal forensic report from verified findings."
            actionLabel="Synthesize Report"
            onAction={() => generateReport(activeInvestigation.id)}
          />
        )}
      </div>
    </PageContainer>
  );
};
