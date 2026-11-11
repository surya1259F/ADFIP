import React, { useEffect, useState, useCallback } from 'react';
import { RouterProvider } from 'react-router-dom';
import { Providers } from './providers';
import { router } from './routes';
import { useAuthStore } from '../stores/authStore';
import { setApiBaseUrl, setBootstrapSecret, validateDiscoveredBackendUrl } from '../services/api';
import { Loader2, ShieldAlert } from 'lucide-react';

type DesktopBackendState = 'DISCOVERING' | 'READY' | 'ERROR';

const isTauriEnv = (): boolean => {
  return typeof window !== 'undefined' &&
    (('__TAURI__' in window) || ('__TAURI_INTERNALS__' in window));
};

const AppInit: React.FC = () => {
  const restore = useAuthStore((s) => s.restore);
  const isDesktop = isTauriEnv();
  const [backendState, setBackendState] = useState<DesktopBackendState>(
    isDesktop ? 'DISCOVERING' : 'DISCOVERING'
  );
  const [backendError, setBackendError] = useState<string | null>(null);

  const initBackend = useCallback(async () => {
    if (!isTauriEnv()) {
      try {
        await restore();
      } finally {
        setBackendState('READY');
      }
      return;
    }

    setBackendState('DISCOVERING');
    setBackendError(null);

    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const config = await invoke<{ port: number; url: string; bootstrap_secret?: string }>('get_backend_config');

      if (!config || typeof config.url !== 'string') {
        throw new Error('Invalid backend configuration received from desktop manager.');
      }

      const isValid = validateDiscoveredBackendUrl(config.url, config.port);
      if (!isValid) {
        throw new Error(`Discovered backend URL '${config.url}' failed loopback security validation.`);
      }

      if (config.bootstrap_secret) {
        setBootstrapSecret(config.bootstrap_secret);
      }
      setApiBaseUrl(config.url);

      await restore();
      setBackendState('READY');
    } catch (err: unknown) {
      console.error('[ADFIP Desktop] Backend initialization error:', err);
      const msg = err instanceof Error ? err.message : String(err);
      setBackendError(msg);
      setBackendState('ERROR');
    }
  }, [restore]);

  useEffect(() => {
    initBackend();
  }, [initBackend]);

  if (backendState === 'DISCOVERING') {
    return (
      <div className="h-screen w-screen bg-stone-950 text-stone-100 flex flex-col items-center justify-center p-6 select-none font-sans">
        <div className="flex flex-col items-center max-w-sm text-center space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-semibold tracking-wider text-stone-200 uppercase">ADFIP Forensic Workstation</h2>
            <p className="text-xs text-stone-400">Initializing desktop backend and verifying forensic services...</p>
          </div>
        </div>
      </div>
    );
  }

  if (backendState === 'ERROR') {
    return (
      <div className="h-screen w-screen bg-stone-950 text-stone-100 flex flex-col items-center justify-center p-6 select-none font-sans">
        <div className="flex flex-col items-center max-w-md text-center space-y-4 p-8 bg-stone-900/60 border border-red-500/20 rounded-2xl shadow-2xl">
          <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-semibold tracking-wider text-stone-200 uppercase">Backend Service Unavailable</h2>
            <p className="text-xs text-red-400">{backendError || 'Failed to start or connect to local ADFIP desktop service.'}</p>
          </div>
          <button
            onClick={() => initBackend()}
            className="mt-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return <RouterProvider router={router} />;
};

export const App: React.FC = () => (
  <Providers>
    <AppInit />
  </Providers>
);

export default App;
