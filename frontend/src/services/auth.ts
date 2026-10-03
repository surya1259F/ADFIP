import { apiClient } from './client';
import type { UserProfile, TokenResponse, UserLoginRequest, UserRegisterRequest } from '../types';

export const authService = {
  login: async (credentials: UserLoginRequest): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/auth/login', credentials);
    return res.data;
  },

  signup: async (data: UserRegisterRequest): Promise<unknown> => {
    const res = await apiClient.post('/auth/signup', data);
    return res.data;
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // best effort
    } finally {
      sessionStorage.removeItem('adfip_token');
    }
  },

  me: async (token?: string): Promise<UserProfile> => {
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
    const res = await apiClient.get<UserProfile>('/auth/me', { headers });
    return res.data;
  },

  getHealth: async (): Promise<{ status: string; version?: string }> => {
    const res = await apiClient.get<{ status: string; version?: string }>('/health');
    return res.data;
  },
};
