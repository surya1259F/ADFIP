import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Download, RefreshCw } from 'lucide-react';
import { reportsService } from '../../services/reports';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton, SkeletonRow } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { HashDisplay } from '../../components/ui/HashDisplay';
import { Dialog } from '../../components/ui/Dialog';
import { formatTimestamp } from '../../lib/utils';
import type { ForensicReportVersionItem } from '../../types';

const ReportPreviewDialog: React.FC<{
  reportId: string;
  caseId: string;
  open: boolean;
  onClose: () => void;
}> = ({ reportId, caseId, open, onClose }) => {
  const { data: report, isLoading, isError, error } = useQuery({
    queryKey: ['cases', caseId, 'reports', reportId],
    queryFn: () => reportsService.get(caseId, reportId),
    enabled: open && !!reportId,
  });

  return (
    <Dialog open={open} onClose={onClose} title="Report Preview" size="lg">
      {isLoading && <Skeleton className="h-64" />}
      {isError && <p className="text-xs text-red-600">{normalizeError(error)}</p>}
      {report && (
        <div className="space-y-3 text-xs max-h-[60vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-slate-400">Status</p>
              <StatusBadge status={report.status} />
            </div>
            <div>
              <p className="text-slate-400">Version</p>
              <p className="text-slate-700">v{report.version}</p>
            </div>
            <div>
              <p className="text-slate-400">Generated</p>
              <p className="text-slate-700">{formatTimestamp(report.generated_at)}</p>
            </div>
            <div>
              <p className="text-slate-400">Integrity</p>
              <StatusBadge status={report.integrity_status} />
            </div>
            {(report.sha256_hash || report.report_hash) && (
              <div className="col-span-2">
                <p className="text-slate-400">Report Hash</p>
                <HashDisplay hash={report.sha256_hash || report.report_hash || ''} chars={8} />
              </div>
            )}
          </div>
          <div>
            <p className="text-slate-600 font-medium mb-1">Executive Summary</p>
            <p className="text-slate-700 leading-relaxed whitespace-pre-line">{report.executive_summary}</p>
          </div>
          {report.full_report_markdown && (
            <div>
              <p className="text-slate-600 font-medium mb-1">Full Report</p>
              <pre className="bg-stone-50 border border-stone-200 rounded p-3 text-[10px] whitespace-pre-wrap overflow-x-auto font-mono">
                {report.full_report_markdown}
              </pre>
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
};

export const ReportsPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const qc = useQueryClient();
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [generateErr, setGenerateErr] = useState<string | null>(null);

  const { data: reports, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'reports'],
    queryFn: () => reportsService.list(caseId!),
    enabled: !!caseId,
  });

  const generateMutation = useMutation({
    mutationFn: () => reportsService.generate(caseId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'reports'] });
      setGenerateErr(null);
    },
    onError: (e) => setGenerateErr(normalizeError(e)),
  });

  const handleExport = async (reportId: string, format: 'markdown' | 'json') => {
    try {
      const { data, filename } = await reportsService.export(caseId!, reportId, format);
      const blob = new Blob([data], { type: format === 'json' ? 'application/json' : 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export failed:', e);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-start justify-between">
        <SectionHeader
          title="Reports Studio"
          description="Forensic investigation reports with provenance and integrity verification"
        />
        <Button
          variant="primary"
          size="sm"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          loading={generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
        >
          Generate Report
        </Button>
      </div>

      {generateErr && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
          {generateErr}
        </p>
      )}
      {isError && <ErrorState message={normalizeError(error)} onRetry={refetch} />}

      {isLoading && (
        <Card padding={false}>
          {[1, 2].map((i) => (
            <SkeletonRow key={i} cols={5} />
          ))}
        </Card>
      )}

      {!isLoading && !isError && (reports?.length ?? 0) === 0 && (
        <EmptyState
          icon={<FileText className="w-8 h-8" />}
          title="No reports generated"
          description="Generate a forensic report to document the investigation findings and evidence."
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => generateMutation.mutate()}
              loading={generateMutation.isPending}
            >
              Generate Report
            </Button>
          }
        />
      )}

      {!isLoading && !isError && reports && reports.length > 0 && (
        <Card padding={false}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-100">
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Report</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Version</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Status</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Integrity</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Generated</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {reports.map((r: ForensicReportVersionItem) => (
                <tr key={r.id} className="border-b border-stone-50 hover:bg-stone-50">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-slate-800">{r.title}</p>
                    <p className="font-mono text-[10px] text-slate-400">{r.id.slice(0, 8)}</p>
                  </td>
                  <td className="px-4 py-2.5 text-slate-600">v{r.version}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={r.integrity_status} />
                  </td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {formatTimestamp(r.generated_at)}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1 justify-end">
                      <Button size="sm" variant="ghost" onClick={() => setPreviewId(r.id)}>
                        Preview
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Download className="w-3 h-3" />}
                        onClick={() => handleExport(r.id, 'markdown')}
                      >
                        MD
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Download className="w-3 h-3" />}
                        onClick={() => handleExport(r.id, 'json')}
                      >
                        JSON
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {previewId && (
        <ReportPreviewDialog
          reportId={previewId}
          caseId={caseId!}
          open={!!previewId}
          onClose={() => setPreviewId(null)}
        />
      )}
    </div>
  );
};

