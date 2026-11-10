import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Wrench, AlertCircle, CheckCircle } from 'lucide-react';
import { toolsService } from '../../services/tools';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { StatusBadge, Badge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import type { ToolInfo, AgentInfo } from '../../types';

export const ToolsPage: React.FC = () => {
  const {
    data: tools,
    isLoading: toolsLoading,
    isError: toolsError,
    error: toolsErr,
    refetch: refetchTools,
  } = useQuery({
    queryKey: ['tools'],
    queryFn: toolsService.list,
  });

  const {
    data: agents,
    isLoading: agentsLoading,
    isError: agentsError,
  } = useQuery({
    queryKey: ['agents'],
    queryFn: toolsService.listAgents,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <SectionHeader
        title="Tools & Agents"
        description="Registered forensic tools and specialist analysis agents"
      />

      {/* Forensic Tools */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Forensic Tools</h2>
        {toolsError && (
          <ErrorState message={normalizeError(toolsErr)} onRetry={refetchTools} />
        )}
        {toolsLoading && (
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        )}
        {!toolsLoading && !toolsError && (tools?.length ?? 0) === 0 && (
          <EmptyState
            icon={<Wrench className="w-6 h-6" />}
            title="No tools registered"
            description="Forensic tools will appear here once registered with the backend."
          />
        )}
        {!toolsLoading && !toolsError && tools && tools.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {tools.map((tool: ToolInfo) => (
              <Card key={tool.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Wrench className="w-4 h-4 text-slate-500" />
                    <p className="text-sm font-medium text-slate-800">{tool.name}</p>
                  </div>
                  {tool.installed ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-amber-400" />
                  )}
                </div>
                {tool.version && (
                  <p className="text-xs text-slate-500">Version: {tool.version}</p>
                )}
                {tool.path && (
                  <p className="font-mono text-[10px] text-slate-400 truncate">
                    {tool.path}
                  </p>
                )}
                {tool.capabilities && tool.capabilities.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {tool.capabilities.map((cap) => (
                      <span
                        key={cap}
                        className="bg-stone-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px]"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                )}
                {tool.status && !tool.installed && (
                  <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                    {tool.status}
                  </p>
                )}
                {tool.is_library_adapter && (
                  <Badge tone="info">Library Adapter</Badge>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Specialist Agents */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700">Specialist Agents</h2>
          <Badge tone="neutral">Deterministic Subsystem</Badge>
        </div>
        {agentsError && (
          <p className="text-xs text-slate-500">
            Agent information currently unavailable from backend.
          </p>
        )}
        {agentsLoading && (
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        )}
        {!agentsLoading && !agentsError && (agents?.length ?? 0) === 0 && (
          <EmptyState
            title="No agents registered"
            description="Specialist agents will appear here once loaded."
          />
        )}
        {!agentsLoading && !agentsError && agents && agents.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agents.map((agent: AgentInfo) => (
              <Card key={agent.name} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-800">{agent.name}</p>
                  <StatusBadge status={agent.status || 'READY'} />
                </div>
                {agent.domain && (
                  <p className="text-xs text-slate-500 font-mono">Domain: {agent.domain}</p>
                )}
                {agent.description && (
                  <p className="text-xs text-slate-600">{agent.description}</p>
                )}
                <div className="pt-1">
                  <span className="text-[10px] text-slate-500 bg-stone-100 rounded px-1.5 py-0.5">
                    Mode: Deterministic (Tool-Driven)
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

