import axios, { type AxiosInstance, type AxiosError } from 'axios';

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

let currentBaseUrl = DEFAULT_BASE_URL;
let unauthorizedHandler: (() => void) | null = null;

export const apiClient: AxiosInstance = axios.create({
  baseURL: currentBaseUrl,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export function setApiBaseUrl(url: string): void {
  currentBaseUrl = url;
  apiClient.defaults.baseURL = url;
}

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler;
}

let currentBootstrapSecret: string | null = null;
export function setBootstrapSecret(secret: string | null): void {
  currentBootstrapSecret = secret;
}

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('adfip_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (currentBootstrapSecret) {
    config.headers['X-ADFIR-Bootstrap-Secret'] = currentBootstrapSecret;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem('adfip_token');
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return Promise.reject(error);
  }
);

export function normalizeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as Record<string, unknown>)?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d: unknown) => (d as Record<string, unknown>)?.msg || String(d)).join(', ');
    return error.message || 'An error occurred';
  }
  if (error instanceof Error) return error.message;
  return 'An unknown error occurred';
}
