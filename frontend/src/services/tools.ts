import { apiClient } from './client';
import type { ToolInfo, AgentInfo, SystemHealth } from '../types';

export const toolsService = {
  list: async (): Promise<ToolInfo[]> => {
    try {
      const res = await apiClient.get<ToolInfo[] | { tools?: ToolInfo[] }>('/tools');
      if (Array.isArray(res.data)) return res.data;
      return (res.data as { tools?: ToolInfo[] }).tools || [];
    } catch {
      return [];
    }
  },

  listAgents: async (): Promise<AgentInfo[]> => {
    try {
      const res = await apiClient.get<AgentInfo[] | { agents?: AgentInfo[] }>('/agents');
      if (Array.isArray(res.data)) return res.data;
      return (res.data as { agents?: AgentInfo[] }).agents || [];
    } catch {
      return [];
    }
  },

  getHealth: async (): Promise<SystemHealth> => {
    const res = await apiClient.get<SystemHealth>('/health');
    return res.data;
  },
};
