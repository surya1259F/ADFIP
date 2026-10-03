import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Globe, RefreshCw } from 'lucide-react';
import { evidenceService } from '../../services/evidence';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import type { Evidence } from '../../types';

const EvidenceIntelligencePanel: React.FC<{ evidence: Evidence }> = ({
  evidence,
}) => {
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();

  const { data: intel, isLoading, isError, error } = useQuery({
    queryKey: ['evidence', evidence.id, 'intelligence'],
    queryFn: () => evidenceService.getIntelligence(evidence.id),
    enabled: expanded,
    retry: 1,
  });

  const extractMutation = useMutation({
    mutationFn: () => evidenceService.extractIntelligence(evidence.id),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ['evidence', evidence.id, 'intelligence'],
      }),
  });

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-800">{evidence.name}</p>
          <p className="text-xs text-slate-500">{evidence.evidence_type}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            onClick={() => extractMutation.mutate()}
            loading={extractMutation.isPending}
          >
            Extract
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Collapse' : 'View Intelligence'}
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-stone-100 pt-3">
          {isLoading && <Skeleton className="h-20" />}
          {isError && (
            <p className="text-xs text-slate-500">
              Intelligence not yet available: {normalizeError(error)}
            </p>
          )}
          {extractMutation.isError && (
            <p className="text-xs text-red-600">
              {normalizeError(extractMutation.error)}
            </p>
          )}
          {intel && (
            <dl className="grid grid-cols-2 gap-2 text-xs">
              {intel.mime_type && (
                <div>
                  <dt className="text-slate-400">MIME type</dt>
                  <dd className="text-slate-700 font-mono">{intel.mime_type}</dd>
                </div>
              )}
              {intel.file_signature && (
                <div>
                  <dt className="text-slate-400">File signature</dt>
                  <dd className="text-slate-700 font-mono">
                    {intel.file_signature}
                  </dd>
                </div>
              )}
              {intel.entropy != null && (
                <div>
                  <dt className="text-slate-400">Entropy</dt>
                  <dd className="text-slate-700">{intel.entropy.toFixed(4)}</dd>
                </div>
              )}
              {intel.tags && intel.tags.length > 0 && (
                <div className="col-span-2">
                  <dt className="text-slate-400 mb-1">Tags</dt>
                  <dd className="flex flex-wrap gap-1">
                    {intel.tags.map((t) => (
                      <span
                        key={t}
                        className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px]"
                      >
                        {t}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
              {intel.metadata && Object.keys(intel.metadata).length > 0 && (
                <div className="col-span-2">
                  <dt className="text-slate-400 mb-1">Metadata</dt>
                  <dd className="bg-stone-50 rounded p-2 font-mono text-[10px] whitespace-pre-wrap break-all overflow-auto max-h-40">
                    {JSON.stringify(intel.metadata, null, 2)}
                  </dd>
                </div>
              )}
              {!intel.mime_type &&
                !intel.file_signature &&
                intel.entropy == null &&
                (!intel.metadata || Object.keys(intel.metadata).length === 0) &&
                (!intel.tags || intel.tags.length === 0) && (
                  <div className="col-span-2">
                    <p className="text-xs text-slate-500">
                      No intelligence data available for this evidence item.
                    </p>
                  </div>
                )}
            </dl>
          )}
        </div>
      )}
    </Card>
  );
};

export const IntelligencePage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  const { data: evidence, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <SectionHeader
        title="Evidence Intelligence"
        description="Analysis profiles, metadata, and extracted intelligence for registered evidence"
      />

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      )}
      {!isLoading && !isError && (evidence?.length ?? 0) === 0 && (
        <EmptyState
          icon={<Globe className="w-8 h-8" />}
          title="No evidence available"
          description="Register evidence to begin intelligence extraction."
        />
      )}
      {!isLoading &&
        !isError &&
        evidence &&
        evidence.map((ev) => (
          <EvidenceIntelligencePanel key={ev.id} evidence={ev} />
        ))}
    </div>
  );
};

