import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText,
  Download,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileDown,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { reportsService } from '../../services/reports';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge, Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton, SkeletonRow } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { HashDisplay } from '../../components/ui/HashDisplay';
import { Dialog } from '../../components/ui/Dialog';
import { Tooltip } from '../../components/ui/Tooltip';
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
              <StatusBadge status={report.status || 'OFFICIAL_FINAL'} />
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
  const [showGateDetails, setShowGateDetails] = useState(false);

  const {
    data: readiness,
    isLoading: readinessLoading,
  } = useQuery({
    queryKey: ['cases', caseId, 'reports', 'readiness'],
    queryFn: () => reportsService.getReadiness(caseId!),
    enabled: !!caseId,
    staleTime: 10_000,
  });

  const { data: reports, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'reports'],
    queryFn: () => reportsService.list(caseId!),
    enabled: !!caseId,
  });

  const generateMutation = useMutation({
    mutationFn: () => reportsService.generate(caseId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'reports'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'reports', 'readiness'] });
      setGenerateErr(null);
    },
    onError: (e) => setGenerateErr(normalizeError(e)),
  });

  const workingExportMutation = useMutation({
    mutationFn: () => reportsService.generateWorkingExport(caseId!),
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

  const isReady = readiness?.ready ?? false;
  const passedGates = readiness?.passed_gates ?? 0;
  const totalGates = readiness?.total_gates ?? 14;
  const blockingReasons = readiness?.blocking_reasons ?? [];

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Header and Action Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <SectionHeader
          title="Reports Studio"
          description="Authoritative forensic reporting with 14-gate verification and provenance tracking"
        />
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="secondary"
            size="sm"
            icon={<FileDown className="w-3.5 h-3.5" />}
            loading={workingExportMutation.isPending}
            onClick={() => workingExportMutation.mutate()}
            title="Export a working draft report for operational review before final certification"
          >
            Export Working Draft
          </Button>

          {isReady ? (
            <Button
              variant="primary"
              size="sm"
              icon={<ShieldCheck className="w-3.5 h-3.5" />}
              loading={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              Generate Official Final Report
            </Button>
          ) : (
            <Tooltip
              content={`Blocked: ${totalGates - passedGates} mandatory forensic gates pending before official final report can be released.`}
              side="bottom"
            >
              <div>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<ShieldAlert className="w-3.5 h-3.5" />}
                  disabled={true}
                >
                  Generate Official Final Report
                </Button>
              </div>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Forensic Report Readiness Status Banner */}
      {readinessLoading ? (
        <Skeleton className="h-16 w-full rounded-lg" />
      ) : readiness ? (
        <Card
          className={`border ${
            isReady
              ? 'bg-emerald-50/70 border-emerald-200'
              : 'bg-amber-50/70 border-amber-200'
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 shrink-0">
                {isReady ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                )}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-800">
                    {isReady
                      ? 'Forensic Readiness Verified'
                      : `Forensic Readiness Check: ${passedGates} of ${totalGates} Gates Passed`}
                  </span>
                  <Badge tone={isReady ? 'success' : 'warning'}>
                    {isReady ? 'OFFICIAL REPORT READY' : 'OFFICIAL FINAL BLOCKED'}
                  </Badge>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {isReady
                    ? 'All 14 mandatory forensic gates have passed. The investigation is verified, all findings have been reviewed, and the case is certified for official final report release.'
                    : 'The case has pending forensic requirements. Working drafts can be exported at any time, but an Official Final Report requires all 14 gates to pass.'}
                </p>
              </div>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowGateDetails(!showGateDetails)}
              icon={showGateDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            >
              {showGateDetails ? 'Hide Gates' : 'Inspect Gates'}
            </Button>
          </div>

          {/* Itemized Blocking Reasons or Full Gate List */}
          {showGateDetails && (
            <div className="mt-4 pt-3 border-t border-amber-200/60 space-y-2 text-xs">
              {blockingReasons.length > 0 && (
                <div className="mb-3 space-y-1">
                  <p className="font-semibold text-amber-900 text-xs">Blocking Issues Requiring Resolution:</p>
                  <ul className="list-disc list-inside space-y-0.5 text-slate-700 pl-1">
                    {blockingReasons.map((br, idx) => (
                      <li key={idx}>
                        <span className="font-mono text-[11px] text-amber-800 font-medium">[{br.code}]</span>{' '}
                        {br.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="font-semibold text-slate-800 text-xs">14 Mandatory Forensic Verification Gates:</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 pt-1">
                {readiness.gates.map((g) => (
                  <div
                    key={g.gate_number}
                    className={`flex items-start gap-2 p-1.5 rounded text-[11px] ${
                      g.passed ? 'bg-emerald-100/50 text-slate-700' : 'bg-amber-100/60 text-amber-900 font-medium'
                    }`}
                  >
                    <span className="shrink-0 mt-0.5">
                      {g.passed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="leading-tight">
                        <span className="font-mono">G{g.gate_number}:</span> {g.name}
                      </p>
                      {!g.passed && g.blocking_reason && (
                        <p className="text-[10px] text-amber-700 mt-0.5 font-normal">
                          {g.blocking_reason.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      ) : null}

      {generateErr && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-md">
          <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <p className="text-xs text-red-700 leading-relaxed">{generateErr}</p>
        </div>
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
          title="No reports generated yet"
          description="Export a Working Draft at any stage of investigation, or generate an Official Final Report once all 14 forensic readiness gates are fulfilled."
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={<FileDown className="w-3.5 h-3.5" />}
                onClick={() => workingExportMutation.mutate()}
                loading={workingExportMutation.isPending}
              >
                Export Working Draft
              </Button>
              {isReady && (
                <Button
                  variant="primary"
                  size="sm"
                  icon={<ShieldCheck className="w-3.5 h-3.5" />}
                  onClick={() => generateMutation.mutate()}
                  loading={generateMutation.isPending}
                >
                  Generate Official Report
                </Button>
              )}
            </div>
          }
        />
      )}

      {!isLoading && !isError && reports && reports.length > 0 && (
        <Card padding={false}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-100 bg-stone-50/50">
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Report Reference</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Version</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Lifecycle Status</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Integrity Status</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Generated Date</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r: ForensicReportVersionItem) => {
                const isWorkingDraft = r.status === 'WORKING_EXPORT' || r.status === 'WORKING_DRAFT';
                return (
                  <tr key={r.id} className="border-b border-stone-50 hover:bg-stone-50/60 transition-colors">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-slate-800">{r.title || `Report v${r.version}`}</p>
                      <p className="font-mono text-[10px] text-slate-400">{r.id.slice(0, 8)}</p>
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 font-mono">v{r.version}</td>
                    <td className="px-4 py-2.5">
                      {isWorkingDraft ? (
                        <Badge tone="warning">WORKING EXPORT</Badge>
                      ) : (
                        <Badge tone="success">OFFICIAL FINAL</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={r.integrity_status} />
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 font-mono text-[11px]">
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
                          title="Download Markdown format"
                        >
                          MD
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<Download className="w-3 h-3" />}
                          onClick={() => handleExport(r.id, 'json')}
                          title="Download JSON structured format"
                        >
                          JSON
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
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
