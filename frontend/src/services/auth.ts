import { apiClient } from './client';
import type { UserProfile, TokenResponse, UserLoginRequest, UserRegisterRequest, UserProfileUpdateRequest } from '../types';

export interface GoogleStatusResponse {
  google_configured: boolean;
  client_id_configured: boolean;
  redirect_uri: string;
}

export interface GoogleAuthUrlResponse {
  authorization_url: string;
  state: string;
  is_configured: boolean;
}

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

  updateProfile: async (data: UserProfileUpdateRequest): Promise<UserProfile> => {
    const res = await apiClient.patch<UserProfile>('/auth/profile', data);
    return res.data;
  },

  uploadAvatar: async (file: File): Promise<UserProfile> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient.post<UserProfile>('/auth/profile/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  deleteAvatar: async (): Promise<UserProfile> => {
    const res = await apiClient.delete<UserProfile>('/auth/profile/avatar');
    return res.data;
  },

  getHealth: async (): Promise<{ status: string; version?: string }> => {
    const res = await apiClient.get<{ status: string; version?: string }>('/health');
    return res.data;
  },

  getGoogleStatus: async (): Promise<GoogleStatusResponse> => {
    const res = await apiClient.get<GoogleStatusResponse>('/auth/google/status');
    return res.data;
  },

  getGoogleLoginUrl: async (
    redirectUrl?: string,
    intent: 'SIGN_IN' | 'SIGN_UP' = 'SIGN_IN'
  ): Promise<GoogleAuthUrlResponse> => {
    const params: Record<string, string> = { intent };
    if (redirectUrl) params.redirect_url = redirectUrl;
    const res = await apiClient.get<GoogleAuthUrlResponse>('/auth/google/login', {
      params,
    });
    return res.data;
  },

  exchangeGoogleCode: async (code: string): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/auth/google/exchange', { code });
    return res.data;
  },

  getGoogleLinkUrl: async (redirectUrl?: string): Promise<GoogleAuthUrlResponse> => {
    const res = await apiClient.get<GoogleAuthUrlResponse>('/auth/google/link-url', {
      params: redirectUrl ? { redirect_url: redirectUrl } : undefined,
    });
    return res.data;
  },

  linkGoogleAccount: async (data: { exchange_code: string; password: string }): Promise<unknown> => {
    const res = await apiClient.post('/auth/google/link', data);
    return res.data;
  },

  unlinkGoogleAccount: async (): Promise<unknown> => {
    const res = await apiClient.delete('/auth/google/unlink');
    return res.data;
  },

  getExternalIdentities: async (): Promise<Array<{ id: string; provider: string; provider_subject: string; provider_email?: string }>> => {
    const res = await apiClient.get('/auth/external-identities');
    return res.data;
  },
};


