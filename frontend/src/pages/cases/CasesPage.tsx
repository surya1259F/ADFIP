import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FolderKanban, Plus } from 'lucide-react';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { SkeletonRow } from '../../components/ui/Skeleton';
import { Dialog } from '../../components/ui/Dialog';
import { Input } from '../../components/ui/Input';
import { Textarea } from '../../components/ui/Textarea';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { formatTimestamp } from '../../lib/utils';
import type { Case } from '../../types';

const CreateCaseDialog: React.FC<{ open: boolean; onClose: () => void }> = ({
  open,
  onClose,
}) => {
  const qc = useQueryClient();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      casesService.create({
        title: title.trim(),
        description: description.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases'] });
      setTitle('');
      setDescription('');
      setError(null);
      onClose();
    },
    onError: (err) => setError(normalizeError(err)),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Case name is required');
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Create Investigation Case"
      description="Start a new forensic investigation case."
      size="sm"
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        {error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </p>
        )}
        <Input
          label="Case name"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Investigation case name"
          required
        />
        <Textarea
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Brief description of the investigation scope"
          rows={3}
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            loading={mutation.isPending}
          >
            Create Case
          </Button>
        </div>
      </form>
    </Dialog>
  );
};

export const CasesPage: React.FC = () => {
  const [createOpen, setCreateOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const currentFilter = (searchParams.get('filter') || 'all').toLowerCase();

  const { data: allCases = [], isLoading: isLoadingAll } = useQuery({
    queryKey: ['cases', 'all'],
    queryFn: () => casesService.list('all'),
  });
  const { data: filteredCases = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ['cases', currentFilter],
    queryFn: () => casesService.list(currentFilter),
  });

  const filterTabs = [
    { key: 'all', label: 'All Cases', count: allCases.length },
    { key: 'active', label: 'Active', count: allCases.filter((c) => ['OPEN', 'ACTIVE', 'IN_PROGRESS'].includes((c.status || '').toUpperCase())).length },
    { key: 'completed', label: 'Completed', count: allCases.filter((c) => ['CLOSED', 'ARCHIVED'].includes((c.status || '').toUpperCase())).length },
    { key: 'pending', label: 'Pending', count: allCases.filter((c) => ['DRAFT', 'PENDING'].includes((c.status || '').toUpperCase())).length },
    { key: 'failed', label: 'Failed', count: allCases.filter((c) => (c.status || '').toUpperCase() === 'FAILED').length },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <SectionHeader
        title="Cases"
        description="Forensic investigation cases managed by this workstation"
        action={
          <Button
            variant="primary"
            size="sm"
            icon={<Plus className="w-3.5 h-3.5" />}
            onClick={() => setCreateOpen(true)}
          >
            New Case
          </Button>
        }
      />

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 border-b border-stone-200 pb-2">
        {filterTabs.map((tab) => {
          const isActive = currentFilter === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setSearchParams({ filter: tab.key })}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1.5 ${
                isActive
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-stone-100'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  isActive ? 'bg-slate-700 text-white' : 'bg-stone-200 text-slate-600'
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {isError && (
        <ErrorState message={normalizeError(error)} onRetry={refetch} />
      )}

      {isLoading && (
        <Card padding={false}>
          {[1, 2, 3, 4].map((i) => (
            <SkeletonRow key={i} cols={5} />
          ))}
        </Card>
      )}

      {!isLoading && !isError && !isLoadingAll && allCases.length === 0 && (
        <EmptyState
          icon={<FolderKanban className="w-8 h-8" />}
          title="No investigations yet"
          description="Create your first case to begin forensic analysis."
          action={
            <Button
              variant="primary"
              size="sm"
              onClick={() => setCreateOpen(true)}
            >
              Create Case
            </Button>
          }
        />
      )}

      {!isLoading && !isError && allCases.length > 0 && filteredCases.length === 0 && (
        <EmptyState
          icon={<FolderKanban className="w-8 h-8" />}
          title={`No ${currentFilter} investigations found`}
          description="Try selecting a different filter above."
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setSearchParams({ filter: 'all' })}
            >
              Show All Cases
            </Button>
          }
        />
      )}

      {!isLoading && !isError && filteredCases.length > 0 && (
        <Card padding={false}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-100">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">
                  Case
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">
                  ID
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">
                  Status
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">
                  Created
                </th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {filteredCases.map((c: Case) => (
                <tr
                  key={c.id}
                  className="border-b border-stone-50 hover:bg-stone-50 transition-colors"
                >
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-slate-800">{c.title || c.name || 'Untitled'}</p>
                    {c.description && (
                      <p className="text-xs text-slate-500 mt-0.5 truncate max-w-xs">
                        {c.description}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="font-mono text-xs text-slate-500">
                      {c.id.slice(0, 8)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">
                    {formatTimestamp(c.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Link to={`/cases/${c.id}`}>
                      <Button size="sm" variant="ghost">
                        Open
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <CreateCaseDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
};
