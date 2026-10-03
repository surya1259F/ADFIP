import { apiClient } from './client';

export interface AIProviderConfigResponse {
  id: string;
  provider: string;
  model: string;
  endpoint?: string | null;
  has_api_key: boolean;
  masked_api_key?: string | null;
  is_enabled: boolean;
  status: string;
  last_tested_at?: string | null;
  last_test_status?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AIProviderConfigRequest {
  provider: string;
  model: string;
  endpoint?: string;
  api_key?: string;
  is_enabled?: boolean;
}

export interface AIProviderStatusResponse {
  status: 'CONFIGURED' | 'UNCONFIGURED' | 'ACTIVE' | 'FAILED' | 'READY' | string;
  provider: string;
  model: string;
  is_enabled: boolean;
  has_api_key: boolean;
  last_tested_at?: string | null;
  last_test_status?: string | null;
  fallback_available?: boolean;
}

export interface AIProviderConnectionTestRequest {
  provider?: string;
  model?: string;
  endpoint?: string;
  api_key?: string;
}

export interface AIProviderConnectionTestResponse {
  provider: string;
  model: string;
  success: boolean;
  status_message: string;
  latency_ms?: number | null;
  has_key: boolean;
}

export const aiService = {
  getConfig: async (): Promise<AIProviderConfigResponse | null> => {
    try {
      const res = await apiClient.get<AIProviderConfigResponse>('/ai/provider/config');
      return res.data;
    } catch (err: any) {
      if (err.response?.status === 404) {
        return null;
      }
      throw err;
    }
  },

  saveConfig: async (payload: AIProviderConfigRequest): Promise<AIProviderConfigResponse> => {
    const res = await apiClient.post<AIProviderConfigResponse>('/ai/provider/config', payload);
    return res.data;
  },

  deleteConfig: async (): Promise<{ status: string; message: string }> => {
    const res = await apiClient.delete<{ status: string; message: string }>('/ai/provider/config');
    return res.data;
  },

  getStatus: async (): Promise<AIProviderStatusResponse> => {
    const res = await apiClient.get<AIProviderStatusResponse>('/ai/provider/status');
    return res.data;
  },

  testConnection: async (
    payload?: AIProviderConnectionTestRequest
  ): Promise<AIProviderConnectionTestResponse> => {
    const res = await apiClient.post<AIProviderConnectionTestResponse>(
      '/ai/provider/test-connection',
      payload || {}
    );
    return res.data;
  },
};
