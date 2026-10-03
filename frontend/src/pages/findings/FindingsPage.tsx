import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Activity, X } from 'lucide-react';
import { findingsService } from '../../services/findings';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { SkeletonRow } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { HashDisplay } from '../../components/ui/HashDisplay';
import { formatTimestamp, formatConfidence } from '../../lib/utils';
import type { FindingItem } from '../../types';

const classificationStyles: Record<string, string> = {
  FACT: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  INFERENCE: 'bg-blue-50 text-blue-700 border-blue-200',
  UNVERIFIED: 'bg-amber-50 text-amber-700 border-amber-200',
};

const FindingDetailPanel: React.FC<{
  finding: FindingItem;
  onClose: () => void;
}> = ({ finding, onClose }) => (
  <div
    className="fixed inset-0 z-50 flex justify-end"
    onClick={onClose}
    aria-modal="true"
    role="dialog"
  >
    <div
      className="w-full max-w-lg bg-white border-l border-stone-200 h-full shadow-xl overflow-y-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="sticky top-0 bg-white border-b border-stone-100 px-5 py-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">
          Finding Detail
        </h2>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 transition-colors"
          aria-label="Close panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="p-5 space-y-4 text-xs">
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            {finding.classification && (
              <span
                className={`px-2 py-0.5 rounded border text-[10px] font-medium ${
                  classificationStyles[finding.classification] ||
                  classificationStyles.UNVERIFIED
                }`}
              >
                {finding.classification}
              </span>
            )}
            {finding.severity && (
              <StatusBadge status={finding.severity} />
            )}
            <StatusBadge
              status={finding.verification_status || 'UNVERIFIED'}
            />
          </div>
          <h3 className="text-sm font-bold text-slate-900">{finding.title}</h3>
          <p className="text-slate-600 mt-1 leading-relaxed">
            {finding.description}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 bg-stone-50 rounded-md p-3">
          <div>
            <p className="text-slate-400 mb-0.5">Confidence</p>
            <p className="text-slate-700 font-medium">
              {formatConfidence(finding.confidence ?? null)}
            </p>
          </div>
          {finding.source_tool && (
            <div>
              <p className="text-slate-400 mb-0.5">Tool</p>
              <p className="text-slate-700">{finding.source_tool}</p>
            </div>
          )}
          {finding.source_agent && (
            <div>
              <p className="text-slate-400 mb-0.5">Agent</p>
              <p className="text-slate-700">{finding.source_agent}</p>
            </div>
          )}
          <div className="col-span-2">
            <p className="text-slate-400 mb-0.5">Detected</p>
            <p className="text-slate-700">
              {formatTimestamp(finding.created_at)}
            </p>
          </div>
        </div>

        {finding.evidence_reference && (
          <div>
            <p className="text-slate-400 font-medium mb-1">
              Evidence Reference
            </p>
            <p className="text-slate-600">{finding.evidence_reference}</p>
          </div>
        )}

        {(finding.supporting_evidence_ids?.length ?? 0) > 0 && (
          <div>
            <p className="text-slate-400 font-medium mb-1">
              Supporting Evidence
            </p>
            {finding.supporting_evidence_ids!.map((id) => (
              <p
                key={id}
                className="font-mono text-[10px] text-slate-600 bg-stone-50 px-2 py-0.5 rounded mb-1"
              >
                {id}
              </p>
            ))}
          </div>
        )}

        {(finding.supporting_artifact_ids?.length ?? 0) > 0 && (
          <div>
            <p className="text-slate-400 font-medium mb-1">
              Supporting Artifacts
            </p>
            {finding.supporting_artifact_ids!.map((id) => (
              <p
                key={id}
                className="font-mono text-[10px] text-slate-600 bg-stone-50 px-2 py-0.5 rounded mb-1"
              >
                {id}
              </p>
            ))}
          </div>
        )}

        {(finding.mitre_techniques?.length ?? 0) > 0 && (
          <div>
            <p className="text-slate-400 font-medium mb-1">
              MITRE ATT&CK Techniques
            </p>
            <div className="flex flex-wrap gap-1">
              {finding.mitre_techniques!.map((t) => (
                <span
                  key={t}
                  className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-mono text-[10px]"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {finding.sha256_hash && (
          <div>
            <p className="text-slate-400 font-medium mb-1">Finding Hash</p>
            <HashDisplay hash={finding.sha256_hash} chars={6} />
          </div>
        )}
      </div>
    </div>
  </div>
);

export const FindingsPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const [selected, setSelected] = useState<FindingItem | null>(null);

  const { data: findings, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'findings'],
    queryFn: () => findingsService.listByCase(caseId!),
    enabled: !!caseId,
  });

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <SectionHeader
        title="Findings"
        description="Forensic findings detected during investigation analysis"
      />

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {isLoading && (
        <Card padding={false}>
          {[1, 2, 3].map((i) => (
            <SkeletonRow key={i} cols={6} />
          ))}
        </Card>
      )}

      {!isLoading && !isError && (findings?.length ?? 0) === 0 && (
        <EmptyState
          icon={<Activity className="w-8 h-8" />}
          title="No findings available"
          description="Findings will appear after forensic analysis produces reviewable results."
        />
      )}

      {!isLoading && !isError && findings && findings.length > 0 && (
        <Card padding={false}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-100">
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">
                  Finding
                </th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">
                  Classification
                </th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">
                  Severity
                </th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">
                  Confidence
                </th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">
                  Verification
                </th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {findings.map((f: FindingItem) => (
                <tr
                  key={f.id}
                  className="border-b border-stone-50 hover:bg-stone-50 transition-colors cursor-pointer"
                  onClick={() => setSelected(f)}
                >
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-slate-800 text-sm line-clamp-1">
                      {f.title}
                    </p>
                    <p className="text-[10px] text-slate-400 font-mono">
                      {f.id.slice(0, 8)}
                    </p>
                  </td>
                  <td className="px-4 py-2.5">
                    {f.classification ? (
                      <span
                        className={`px-2 py-0.5 rounded border text-[10px] font-medium ${
                          classificationStyles[f.classification] ||
                          classificationStyles.UNVERIFIED
                        }`}
                      >
                        {f.classification}
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {f.severity ? (
                      <StatusBadge status={f.severity} />
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-slate-600">
                    {formatConfidence(f.confidence ?? null)}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge
                      status={f.verification_status || 'UNVERIFIED'}
                    />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button className="text-slate-400 hover:text-slate-700 text-[11px]">
                      Detail →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {selected && (
        <FindingDetailPanel
          finding={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
};

