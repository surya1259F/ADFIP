import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users } from 'lucide-react';
import { authService } from '../../services/auth';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { Skeleton } from '../../components/ui/Skeleton';
import { ErrorState } from '../../components/ui/ErrorState';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { formatTimestamp } from '../../lib/utils';

export const AccountPage: React.FC = () => {
  const {
    data: user,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => authService.me(),
    staleTime: 120_000,
  });

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <SectionHeader
        title="Account"
        description="Your investigator profile and account information"
      />

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      )}
      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {user && (
        <Card>
          <div className="flex items-center gap-4 mb-4">
            <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center">
              <Users className="w-5 h-5 text-slate-500" />
            </div>
            <div>
              <p className="text-base font-semibold text-slate-900">
                {user.name || user.email}
              </p>
              <p className="text-xs text-slate-500">{user.email}</p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-slate-400 mb-0.5">Role</dt>
              <dd>
                <StatusBadge status={user.role || 'investigator'} />
              </dd>
            </div>
            <div>
              <dt className="text-slate-400 mb-0.5">Status</dt>
              <dd>
                <StatusBadge status={user.is_active ? 'ACTIVE' : 'INACTIVE'} />
              </dd>
            </div>
            {user.badge_id && (
              <div>
                <dt className="text-slate-400 mb-0.5">Badge ID</dt>
                <dd className="font-mono text-slate-700">{user.badge_id}</dd>
              </div>
            )}
            {user.organization && (
              <div>
                <dt className="text-slate-400 mb-0.5">Organization</dt>
                <dd className="text-slate-700">{user.organization}</dd>
              </div>
            )}
            {user.created_at && (
              <div>
                <dt className="text-slate-400 mb-0.5">Member since</dt>
                <dd className="text-slate-700">
                  {formatTimestamp(user.created_at)}
                </dd>
              </div>
            )}
          </dl>
        </Card>
      )}
    </div>
  );
};

