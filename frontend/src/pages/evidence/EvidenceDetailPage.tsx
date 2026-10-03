import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, Clock } from 'lucide-react';
import { evidenceService } from '../../services/evidence';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge, Badge } from '../../components/ui/Badge';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { Button } from '../../components/ui/Button';
import { HashDisplay } from '../../components/ui/HashDisplay';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatFileSize, formatTimestamp } from '../../lib/utils';
import type { CustodyEvent } from '../../types';

export const EvidenceDetailPage: React.FC = () => {
  const { caseId, evidenceId } = useParams<{
    caseId: string;
    evidenceId: string;
  }>();
  const qc = useQueryClient();

  const {
    data: ev,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['evidence', evidenceId],
    queryFn: () => evidenceService.get(evidenceId!),
    enabled: !!evidenceId,
  });

  const {
    data: custody,
    isLoading: custodyLoading,
  } = useQuery({
    queryKey: ['evidence', evidenceId, 'custody'],
    queryFn: () => evidenceService.getCustody(evidenceId!),
    enabled: !!evidenceId,
  });

  const verifyMutation = useMutation({
    mutationFn: () => evidenceService.verify(evidenceId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['evidence', evidenceId] });
      qc.invalidateQueries({ queryKey: ['evidence', evidenceId, 'custody'] });
      qc.invalidateQueries({ queryKey: ['cases', caseId, 'evidence'] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }
  if (isError) {
    return <ErrorState message={normalizeError(error)} onRetry={refetch} />;
  }
  if (!ev) return null;

  const alreadyVerified = ev.verification_status === 'VERIFIED';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[11px] text-slate-400">
              {ev.id.slice(0, 8).toUpperCase()}
            </span>
            <StatusBadge status={ev.status || 'INGESTED'} />
          </div>
          <h1 className="text-xl font-bold text-slate-900">{ev.name}</h1>
        </div>
        <Button
          variant={alreadyVerified ? 'secondary' : 'primary'}
          size="sm"
          icon={<ShieldCheck className="w-3.5 h-3.5" />}
          onClick={() => verifyMutation.mutate()}
          disabled={alreadyVerified || verifyMutation.isPending}
          loading={verifyMutation.isPending}
        >
          {alreadyVerified ? 'Integrity Verified' : 'Verify Integrity'}
        </Button>
      </div>

      {verifyMutation.isError && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
          {normalizeError(verifyMutation.error)}
        </p>
      )}

      {verifyMutation.isSuccess && !alreadyVerified && (
        <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded p-2">
          Integrity verification submitted successfully.
        </p>
      )}

      {/* Identity */}
      <Card>
        <SectionHeader title="Evidence Identity" size="sm" />
        <dl className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <dt className="text-slate-400 mb-0.5">Evidence ID</dt>
            <dd className="font-mono text-slate-700 break-all">{ev.id}</dd>
          </div>
          <div>
            <dt className="text-slate-400 mb-0.5">Type</dt>
            <dd className="text-slate-700">{ev.evidence_type}</dd>
          </div>
          <div>
            <dt className="text-slate-400 mb-0.5">Size</dt>
            <dd className="text-slate-700">
              {ev.size_bytes != null ? formatFileSize(ev.size_bytes) : 'Unknown'}
            </dd>
          </div>
          <div>
            <dt className="text-slate-400 mb-0.5">Registered</dt>
            <dd className="text-slate-700">{formatTimestamp(ev.created_at)}</dd>
          </div>
          {ev.acquired_at && (
            <div>
              <dt className="text-slate-400 mb-0.5">Acquired</dt>
              <dd className="text-slate-700">
                {formatTimestamp(ev.acquired_at)}
              </dd>
            </div>
          )}
          {ev.vault_path && (
            <div className="col-span-2">
              <dt className="text-slate-400 mb-0.5">Vault Path</dt>
              <dd className="font-mono text-slate-600 text-[10px] break-all">
                {ev.vault_path}
              </dd>
            </div>
          )}
        </dl>
      </Card>

      {/* Integrity */}
      <Card>
        <SectionHeader title="Evidence Integrity" size="sm" />
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div
              className={`w-2 h-2 rounded-full ${
                alreadyVerified ? 'bg-emerald-500' : 'bg-amber-400'
              }`}
            />
            <div>
              <p className="text-sm font-medium text-slate-800">
                {alreadyVerified
                  ? 'Integrity Verified'
                  : 'Verification Required'}
              </p>
              <p className="text-xs text-slate-500">
                {alreadyVerified
                  ? 'Hash has been computed and verified against the original evidence.'
                  : 'Evidence integrity has not been verified against the original acquisition hash.'}
              </p>
            </div>
          </div>
          {(ev.sha256 || ev.sha256_hash) && (
            <div className="bg-stone-50 border border-stone-200 rounded-md p-3">
              <p className="text-[10px] text-slate-400 mb-1 font-medium">
                SHA-256
              </p>
              <HashDisplay hash={ev.sha256 || ev.sha256_hash || ''} chars={8} />
            </div>
          )}
          {(ev.md5 || ev.md5_hash) && (
            <div className="bg-stone-50 border border-stone-200 rounded-md p-3">
              <p className="text-[10px] text-slate-400 mb-1 font-medium">
                MD5
              </p>
              <HashDisplay hash={ev.md5 || ev.md5_hash || ''} chars={8} />
            </div>
          )}
          {!ev.sha256 && !ev.sha256_hash && !ev.md5 && !ev.md5_hash && (
            <Badge tone="warning">No hash recorded</Badge>
          )}
        </div>
      </Card>

      {/* Chain of Custody */}
      <Card>
        <SectionHeader
          title="Chain of Custody"
          size="sm"
          description="Verified sequence of custody events"
        />
        {custodyLoading && <Skeleton className="h-24" />}
        {!custodyLoading && (!custody || custody.length === 0) && (
          <EmptyState
            icon={<Clock className="w-6 h-6" />}
            title="No custody events"
            description="Custody events will appear as investigation actions are performed."
          />
        )}
        {!custodyLoading && custody && custody.length > 0 && (
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-stone-200" />
            <div className="space-y-4">
              {custody.map((event: CustodyEvent) => (
                <div key={event.id} className="flex gap-4 pl-2">
                  <div className="relative z-10 w-5 h-5 rounded-full bg-stone-200 border-2 border-white flex items-center justify-center shrink-0 mt-0.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                  </div>
                  <div className="pb-2 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-xs font-semibold text-slate-700">
                        {event.action || event.event_type}
                      </p>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {formatTimestamp(event.timestamp)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">{event.actor}</p>
                    {(event.hash || event.sha256) && (
                      <div className="mt-1">
                        <HashDisplay
                          hash={event.hash || event.sha256 || ''}
                          label="Chain hash"
                          chars={4}
                        />
                      </div>
                    )}
                    {event.notes && (
                      <p className="text-xs text-slate-600 mt-1">
                        {event.notes}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <div className="pt-2">
        <Link
          to={`/cases/${caseId}/evidence`}
          className="text-xs text-slate-500 hover:text-slate-700"
        >
          ← Back to Evidence
        </Link>
      </div>
    </div>
  );
};
