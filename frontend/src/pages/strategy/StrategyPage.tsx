import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Blocks } from 'lucide-react';
import { evidenceService } from '../../services/evidence';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { StatusBadge } from '../../components/ui/Badge';

export const StrategyPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  const { data: evidence, isLoading: evLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  if (isError) return <ErrorState message={normalizeError(error)} onRetry={refetch} />;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <SectionHeader
        title="Investigation Strategy"
        description="Evidence-driven investigation planning and tool selection"
      />

      {/* Evidence inventory (basis for strategy) */}
      <Card>
        <SectionHeader
          title="Evidence Inventory"
          size="sm"
          description="Evidence available for forensic analysis"
        />
        {evLoading && <Skeleton className="h-16" />}
        {!evLoading && (!evidence || evidence.length === 0) && (
          <EmptyState
            icon={<Blocks className="w-6 h-6" />}
            title="No evidence registered"
            description="Strategy cannot be determined without registered evidence. Register evidence first."
          />
        )}
        {!evLoading && evidence && evidence.length > 0 && (
          <div className="space-y-2">
            {evidence.map((ev) => (
              <div
                key={ev.id}
                className="flex items-center justify-between py-1.5 border-b border-stone-50 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-slate-800">{ev.name}</p>
                  <p className="text-xs text-slate-500">{ev.evidence_type}</p>
                </div>
                <StatusBadge status={ev.status || 'INGESTED'} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Investigation plan */}
      <Card>
        <SectionHeader
          title="Investigation Plan"
          size="sm"
          description="Planned forensic analysis workflow"
        />
        <div className="text-center py-8">
          <Blocks className="w-6 h-6 text-stone-300 mx-auto mb-2" />
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Investigation planning is driven by the backend forensic pipeline. Use
            the Execution workspace to initiate forensic analysis based on the
            registered evidence above.
          </p>
        </div>
      </Card>
    </div>
  );
};

