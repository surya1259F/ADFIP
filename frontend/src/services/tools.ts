import { apiClient } from './client';
import type { ToolInfo, AgentInfo, SystemHealth } from '../types';

export const toolsService = {
  list: async (): Promise<ToolInfo[]> => {
    const res = await apiClient.get<ToolInfo[] | { tools?: ToolInfo[] }>('/tools');
    if (Array.isArray(res.data)) return res.data;
    return (res.data as { tools?: ToolInfo[] }).tools || [];
  },

  listAgents: async (): Promise<AgentInfo[]> => {
    const res = await apiClient.get<AgentInfo[] | { agents?: AgentInfo[] }>('/agents');
    if (Array.isArray(res.data)) return res.data;
    return (res.data as { agents?: AgentInfo[] }).agents || [];
  },

  getHealth: async (): Promise<SystemHealth> => {
    const res = await apiClient.get<SystemHealth>('/health');
    return res.data;
  },
};
