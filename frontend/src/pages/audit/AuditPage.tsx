import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Shield } from 'lucide-react';
import { auditService } from '../../services/audit';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { SkeletonRow } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { HashDisplay } from '../../components/ui/HashDisplay';
import { formatTimestamp } from '../../lib/utils';
import type { AuditEvent } from '../../types';

export const AuditPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  const { data: events, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'audit'],
    queryFn: () => auditService.listByCase(caseId!),
    enabled: !!caseId,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <SectionHeader
        title="Audit Trail"
        description="Immutable record of all investigation actions and system events"
      />

      <div className="text-[10px] text-slate-500 bg-amber-50 border border-amber-200 rounded px-3 py-1.5">
        Audit records are cryptographically verified and read-only. Investigation actions cannot be altered or deleted.
      </div>

      {isError && <ErrorState message={normalizeError(error)} onRetry={refetch} />}

      {isLoading && (
        <Card padding={false}>
          {[1, 2, 3, 4, 5].map((i) => (
            <SkeletonRow key={i} cols={5} />
          ))}
        </Card>
      )}

      {!isLoading && !isError && (events?.length ?? 0) === 0 && (
        <EmptyState
          icon={<Shield className="w-8 h-8" />}
          title="No audit activity"
          description="Investigation actions will appear here as they occur."
        />
      )}

      {!isLoading && !isError && events && events.length > 0 && (
        <Card padding={false}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-100 bg-stone-50/50">
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Timestamp</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Actor</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Action</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Resource</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Result</th>
                <th className="text-left px-4 py-2.5 text-slate-500 font-medium">Hash</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev: AuditEvent) => (
                <tr key={ev.id} className="border-b border-stone-50">
                  <td className="px-4 py-2 font-mono text-[10px] text-slate-500 whitespace-nowrap">
                    {formatTimestamp(ev.timestamp)}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{ev.actor || ev.actor_name || '—'}</td>
                  <td className="px-4 py-2 font-medium text-slate-700">{ev.action || ev.event_type}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {ev.resource_type
                      ? `${ev.resource_type}${ev.resource_id ? ':' + ev.resource_id.slice(0, 6) : ''}`
                      : '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{ev.result || '—'}</td>
                  <td className="px-4 py-2">
                    {ev.sha256_hash || ev.event_hash ? (
                      <HashDisplay hash={ev.sha256_hash || ev.event_hash || ''} chars={4} />
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
};
