import axios, { type AxiosInstance, type AxiosError } from 'axios';

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001/api/v1';

let currentBaseUrl = DEFAULT_BASE_URL;
let unauthorizedHandler: (() => void) | null = null;

export const apiClient: AxiosInstance = axios.create({
  baseURL: currentBaseUrl,
  timeout: 30000,
});

export function setApiBaseUrl(url: string): void {
  let normalizedUrl = url.trim().replace('localhost', '127.0.0.1');
  if (normalizedUrl.endsWith('/api')) {
    normalizedUrl = `${normalizedUrl}/v1`;
  } else if (!normalizedUrl.includes('/api')) {
    normalizedUrl = normalizedUrl.replace(/\/+$/, '') + '/api/v1';
  }
  currentBaseUrl = normalizedUrl;
  apiClient.defaults.baseURL = normalizedUrl;
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
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (config.headers && typeof config.headers.delete === 'function') {
      config.headers.delete('Content-Type');
      config.headers.delete('content-type');
    } else if (config.headers) {
      delete config.headers['Content-Type'];
      delete config.headers['content-type'];
    }
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
    const data = error.response?.data as Record<string, unknown> | undefined;
    const detail = data?.detail;
    const reqId = (data?.request_id as string) || (error.response?.headers?.['x-request-id'] as string) || (error.response?.headers?.['x-correlation-id'] as string);
    const statusCode = error.response?.status;
    let baseMsg = 'An error occurred';

    if (typeof detail === 'string') {
      baseMsg = detail;
    } else if (Array.isArray(detail)) {
      baseMsg = detail.map((d: unknown) => (d as Record<string, unknown>)?.msg || String(d)).join(', ');
    } else if (error.message) {
      baseMsg = error.message;
    }

    if (reqId) {
      return `${baseMsg} (Request ID: ${reqId}${statusCode ? `, HTTP ${statusCode}` : ''})`;
    } else if (statusCode) {
      return `${baseMsg} (HTTP ${statusCode})`;
    }
    return baseMsg;
  }
  if (error instanceof Error) return error.message;
  return 'An unknown error occurred';
}
