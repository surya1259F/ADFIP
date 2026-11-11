import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from 'axios';

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001/api/v1';

let currentBaseUrl = DEFAULT_BASE_URL;
let unauthorizedHandler: (() => void) | null = null;
let currentBootstrapSecret: string | null = null;
let useIpcDirectly = false;

const isTauriEnv = (): boolean => {
  return typeof window !== 'undefined' &&
    (('__TAURI__' in window) || ('__TAURI_INTERNALS__' in window));
};

async function executeViaTauriIpc(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  const { invoke } = await import('@tauri-apps/api/core');

  let path = config.url || '';
  if (path.startsWith('http://') || path.startsWith('https://')) {
    try {
      const parsed = new URL(path);
      path = parsed.pathname;
    } catch {
      // keep original path
    }
  }

  let query: Record<string, string> | undefined = undefined;
  if (config.params) {
    query = {};
    for (const [k, v] of Object.entries(config.params)) {
      if (v !== undefined && v !== null) {
        query[k] = String(v);
      }
    }
  }

  const headers: Record<string, string> = {};
  if (config.headers) {
    const rawHeaders = typeof config.headers.toJSON === 'function' ? config.headers.toJSON() : config.headers;
    for (const [k, v] of Object.entries(rawHeaders)) {
      if (v !== undefined && v !== null) {
        headers[k] = String(v);
      }
    }
  }

  let body: string | undefined = undefined;
  if (config.data !== undefined && config.data !== null) {
    if (typeof config.data === 'string') {
      body = config.data;
    } else if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      const formObj: Record<string, unknown> = {};
      config.data.forEach((value, key) => {
        formObj[key] = value;
      });
      body = JSON.stringify(formObj);
      headers['Content-Type'] = 'application/json';
    } else {
      body = JSON.stringify(config.data);
    }
  }

  const payload = {
    method: (config.method || 'GET').toUpperCase(),
    path,
    query: query || null,
    headers: Object.keys(headers).length > 0 ? headers : null,
    body: body || null,
  };

  const ipcResp = await invoke<{
    status: number;
    status_text: string;
    headers: Record<string, string>;
    data: string;
  }>('execute_backend_request', { request: payload });

  let parsedData: unknown = ipcResp.data;
  if (typeof ipcResp.data === 'string' && ipcResp.data.trim().length > 0) {
    try {
      parsedData = JSON.parse(ipcResp.data);
    } catch {
      // return raw string
    }
  }

  const axiosResponse: AxiosResponse = {
    data: parsedData,
    status: ipcResp.status,
    statusText: ipcResp.status_text,
    headers: ipcResp.headers as any,
    config,
    request: null,
  };

  if (ipcResp.status >= 200 && ipcResp.status < 300) {
    return axiosResponse;
  }

  const axiosError = new axios.AxiosError(
    `Request failed with status code ${ipcResp.status}`,
    ipcResp.status >= 500 ? 'ERR_BAD_RESPONSE' : 'ERR_BAD_REQUEST',
    config,
    null,
    axiosResponse
  );
  return Promise.reject(axiosError);
}

const standardHttpAdapter = axios.getAdapter(['xhr', 'http', 'fetch']);

export const resilientTauriAdapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
  if (!isTauriEnv()) {
    return standardHttpAdapter(config);
  }

  if (useIpcDirectly) {
    return executeViaTauriIpc(config);
  }

  try {
    return await standardHttpAdapter(config);
  } catch (err: unknown) {
    const isNetworkError = !axios.isAxiosError(err) || !err.response || err.code === 'ERR_NETWORK' || err.message?.includes('Network Error');
    if (isNetworkError && isTauriEnv()) {
      useIpcDirectly = true;
      return executeViaTauriIpc(config);
    }
    throw err;
  }
};

export const apiClient: AxiosInstance = axios.create({
  baseURL: currentBaseUrl,
  timeout: 30000,
  adapter: resilientTauriAdapter,
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

export function setBootstrapSecret(secret: string | null): void {
  currentBootstrapSecret = secret;
}

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('adfip_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (currentBootstrapSecret) {
    config.headers['X-ADFIP-Bootstrap-Secret'] = currentBootstrapSecret;
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
