import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { PageContainer } from '../components/PageContainer';
import { useInvestigationStore } from '../stores/investigationStore';
import { aiService, type AIProviderConfigRequest } from '../services/ai';
import { normalizeError } from '../services/client';
import {
  Key,
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  Lock,
  Loader2,
  Globe,
  RefreshCw
} from 'lucide-react';

/** Returns a human-readable label for a Gemini model identifier. */
function geminiModelLabel(modelId: string): string {
  if (modelId === 'gemini-3.8-flash') return `${modelId} — Recommended`;
  if (modelId === 'gemini-3.5-flash-lite') return `${modelId} — Budget`;
  return modelId;
}

export const AIProviderPage: React.FC = () => {
  const {
    updateAIConfig,
  } = useInvestigationStore();

  const [provider, setProvider] = useState<'openai' | 'anthropic' | 'gemini' | 'local_stub'>('gemini');
  const [model, setModel] = useState<string>('gemini-3.8-flash');
  const [apiKey, setApiKey] = useState<string>('');
  const [baseUrl, setBaseUrl] = useState<string>('');
  const [saveStatusMsg, setSaveStatusMsg] = useState<string>('');
  const [dynamicModels, setDynamicModels] = useState<string[]>([]);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{
    status: 'SUCCESS' | 'FAILED';
    provider: string;
    model: string;
    details: string;
    latency_ms?: number | null;
  } | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [backendConfig, setBackendConfig] = useState<any>(null);

  const modelOptions = {
    openai: [
      { id: 'gpt-4o', label: 'GPT-4o (High Reasoning)' },
      { id: 'gpt-4o-mini', label: 'GPT-4o-mini (Fast)' },
      { id: 'o3-mini', label: 'o3-mini (Forensic Logic)' }
    ],
    anthropic: [
      { id: 'claude-3-5-sonnet', label: 'Claude 3.5 Sonnet (Forensic Analysis)' },
      { id: 'claude-3-5-haiku', label: 'Claude 3.5 Haiku (Fast)' },
      { id: 'claude-3-opus', label: 'Claude 3 Opus (Deep Analysis)' }
    ],
    gemini: [
      { id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash — Recommended' },
      { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash-Lite — Budget' }
    ],
    local_stub: [
      { id: 'adfir-deterministic-engine', label: 'Local Deterministic Template Engine (Default)' }
    ]
  };

  // Load existing configuration from backend on mount
  useEffect(() => {
    let active = true;
    const fetchConfig = async () => {
      try {
        const cfg = await aiService.getConfig();
        if (active && cfg) {
          setBackendConfig(cfg);
          const p = cfg.provider === 'google' ? 'gemini' : cfg.provider;
          setProvider(p as any);
          if (cfg.model) setModel(cfg.model);
          if (cfg.endpoint) setBaseUrl(cfg.endpoint);
          updateAIConfig({
            provider: p as any,
            model: cfg.model,
            has_key: cfg.has_api_key,
            is_tested: cfg.last_test_status === 'SUCCESS',
            status: cfg.configured ? 'CONFIGURED' : 'NOT_CONFIGURED',
            last_tested: cfg.last_tested_at || undefined,
          });
        }
      } catch {
        // Unconfigured or error
      }
    };
    fetchConfig();
    return () => { active = false; };
  }, []);

  // Discover models using POST with transient key
  const handleRefreshModels = useCallback(async () => {
    if (isDiscovering) return;
    setIsDiscovering(true);
    setDiscoveryError(null);
    try {
      const effectiveKey = apiKey.trim() || undefined;
      const models = await aiService.discoverModels(provider, effectiveKey, baseUrl.trim() || undefined);
      if (models && models.length > 0) {
        setDynamicModels(models);
        setModel((current) =>
          models.includes(current) ? current : models[0]
        );
      } else {
        setDynamicModels([]);
      }
    } catch (err: any) {
      setDynamicModels([]);
      if (provider === 'gemini' && (apiKey.trim() || backendConfig?.has_api_key)) {
        setDiscoveryError(normalizeError(err));
      }
    } finally {
      setIsDiscovering(false);
    }
  }, [provider, apiKey, baseUrl, backendConfig?.has_api_key, isDiscovering]);

  // Auto-discover models on provider change or when backend config loads
  useEffect(() => {
    let active = true;
    const fetchModels = async () => {
      try {
        setDiscoveryError(null);
        const effectiveKey = apiKey.trim() || undefined;
        const models = await aiService.discoverModels(provider, effectiveKey, baseUrl.trim() || undefined);
        if (active && models && models.length > 0) {
          setDynamicModels(models);
          setModel((current) =>
            models.includes(current) ? current : models[0]
          );
        } else if (active) {
          setDynamicModels([]);
        }
      } catch (err: any) {
        if (active) {
          setDynamicModels([]);
          if (provider === 'gemini' && (apiKey.trim() || backendConfig?.has_api_key)) {
            setDiscoveryError(normalizeError(err));
          }
        }
      }
    };
    fetchModels();
    return () => { active = false; };
  }, [provider, backendConfig?.has_api_key]);

  const handleProviderSelect = (newProvider: 'openai' | 'anthropic' | 'gemini' | 'local_stub') => {
    setProvider(newProvider);
    setDynamicModels([]);
    const defaultOption = modelOptions[newProvider]?.[0]?.id || '';
    setModel(defaultOption);
    setTestResult(null);
    setTestError(null);
    setDiscoveryError(null);
  };

  const activeModelOptions = useMemo(() => {
    if (dynamicModels.length > 0) {
      return dynamicModels.map((m) => ({
        id: m,
        label: provider === 'gemini' ? geminiModelLabel(m) : m
      }));
    }
    return modelOptions[provider as keyof typeof modelOptions] || [];
  }, [dynamicModels, provider]);

  const handleTestConnection = async () => {
    if (isTesting) return;
    setIsTesting(true);
    setTestError(null);
    setTestResult(null);
    try {
      const res = await aiService.testConnection({
        provider,
        model,
        api_key: apiKey.trim() || undefined,
        endpoint: baseUrl.trim() || undefined,
      });
      setTestResult({
        status: res.success ? 'SUCCESS' : 'FAILED',
        provider: res.provider,
        model: res.model,
        details: res.status_message,
        latency_ms: res.latency_ms,
      });
    } catch (err: any) {
      const msg = normalizeError(err);
      setTestError(msg);
      setTestResult({
        status: 'FAILED',
        provider,
        model,
        details: msg,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;
    setIsSaving(true);
    setSaveStatusMsg('');
    setTestError(null);

    try {
      const payload: AIProviderConfigRequest = {
        provider,
        model,
        endpoint: baseUrl.trim() || undefined,
        api_key: apiKey.trim() || undefined,
        is_enabled: true,
      };

      const saved = await aiService.saveConfig(payload);
      setBackendConfig(saved);

      // Clear transient API key input immediately
      setApiKey('');

      updateAIConfig({
        provider: (saved.provider === 'google' ? 'gemini' : saved.provider) as any,
        model: saved.model,
        has_key: saved.has_api_key,
        is_tested: testResult?.status === 'SUCCESS',
        status: saved.configured ? 'CONFIGURED' : 'NOT_CONFIGURED',
        last_tested: new Date().toISOString(),
      });

      setSaveStatusMsg('AI Provider configuration encrypted and persisted to backend successfully.');
      setTimeout(() => setSaveStatusMsg(''), 4000);
    } catch (err) {
      setTestError(normalizeError(err));
    } finally {
      setIsSaving(false);
    }
  };

  const statusLabel = backendConfig?.configured
    ? 'CONFIGURED'
    : (apiKey.trim() || provider === 'local_stub')
      ? 'READY_TO_SAVE'
      : 'NOT_CONFIGURED';

  return (
    <PageContainer
      title="AI Reasoning Provider Configuration"
      subtitle="Configure cloud or local LLM reasoning providers for forensic query analysis and finding explanations."
    >
      <div className="space-y-6 max-w-3xl">
        {/* Forensic Core Invariant Notice */}
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-2 font-mono text-xs">
          <div className="flex items-center gap-2 text-indigo-400 font-bold">
            <ShieldAlert className="w-4 h-4" />
            <span>CRITICAL FORENSIC INVARIANT &amp; CREDENTIAL SECURITY</span>
          </div>
          <p className="text-slate-300 leading-relaxed font-sans text-xs">
            The LLM is <strong>NOT</strong> the source of forensic truth. Forensic tools (TSK, Volatility 3, YARA, python-evtx)
            extract facts and produce artifacts. The backend Verification Layer determines whether findings are supported.
            Your API key is encrypted at rest using authenticated cryptography and stored securely for your ADFIP account.
            The plaintext key is never returned by the backend after saving and is never stored in browser storage.
          </p>
        </div>

        {/* Gemini free-tier advisory */}
        {provider === 'gemini' && (
          <div className="bg-slate-900/50 border border-slate-800/60 p-4 rounded-xl text-xs text-slate-400 font-sans">
            <p className="font-semibold text-slate-300 mb-1">Google Gemini API</p>
            <p>
              Use your Google AI Studio API key. Available models are discovered from Google's API for your key.
              Free-tier availability and quotas are controlled by Google and may vary.
            </p>
          </div>
        )}

        {saveStatusMsg && (
          <div className="p-3 rounded-lg border text-xs font-mono flex items-center gap-2 bg-emerald-500/10 border-emerald-500/30 text-emerald-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{saveStatusMsg}</span>
          </div>
        )}

        {/* Backend Provider Test Error */}
        {testError && (
          <div className="p-3 rounded-lg border text-xs font-mono flex items-center gap-2 bg-rose-500/10 border-rose-500/30 text-rose-300">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Provider Test Failed: {testError}</span>
          </div>
        )}

        {/* Backend Provider Test Response Display */}
        {testResult && (
          <div className={`p-4 rounded-xl border text-xs font-mono space-y-2 ${
            testResult.status === 'SUCCESS'
              ? 'bg-emerald-950/30 border-emerald-800/80 text-emerald-300'
              : 'bg-rose-950/30 border-rose-800/80 text-rose-300'
          }`}>
            <div className="flex items-center justify-between font-bold">
              <div className="flex items-center gap-2">
                {testResult.status === 'SUCCESS' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-400" />
                )}
                <span>Provider Test Result: [{testResult.status}]</span>
                {testResult.latency_ms !== undefined && testResult.latency_ms !== null && (
                  <span className="text-xs font-normal text-slate-400">({testResult.latency_ms} ms)</span>
                )}
              </div>
              <span className="text-[10px] text-slate-400">Provider: {testResult.provider} ({testResult.model})</span>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed font-sans">{testResult.details}</p>
          </div>
        )}

        {/* Configuration Form */}
        <form onSubmit={handleSave} className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-5 text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="font-mono text-slate-200 font-bold uppercase">Provider Credentials &amp; Target</h3>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
              statusLabel === 'CONFIGURED'
                ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                : statusLabel === 'READY_TO_SAVE'
                ? 'text-blue-400 bg-blue-500/10 border-blue-500/20'
                : 'text-amber-400 bg-amber-500/10 border-amber-500/20'
            }`}>
              {statusLabel}
            </span>
          </div>

          <div>
            <label className="block font-mono text-slate-400 mb-1.5 uppercase text-[11px]">Reasoning Provider</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono">
              {[
                { id: 'local_stub', label: 'Local Engine' },
                { id: 'openai', label: 'OpenAI' },
                { id: 'anthropic', label: 'Anthropic' },
                { id: 'gemini', label: 'Google Gemini' }
              ].map((p) => (
                <button
                  type="button"
                  key={p.id}
                  onClick={() => handleProviderSelect(p.id as any)}
                  className={`p-2.5 rounded-lg border text-center transition-all ${
                    provider === p.id
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300 font-bold'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="font-mono text-slate-400 uppercase text-[11px]">Model Target</label>
              {provider === 'gemini' && (
                <button
                  type="button"
                  onClick={handleRefreshModels}
                  disabled={isDiscovering}
                  className="flex items-center gap-1 text-[10px] font-mono text-indigo-400 hover:text-indigo-300 disabled:opacity-50 transition-colors"
                >
                  <RefreshCw className={`w-3 h-3 ${isDiscovering ? 'animate-spin' : ''}`} />
                  <span>{isDiscovering ? 'Discovering...' : 'Refresh available models'}</span>
                </button>
              )}
            </div>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
            >
              {activeModelOptions.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            {discoveryError && provider === 'gemini' && (
              <div className="mt-1.5 p-2 rounded border text-xs font-mono flex items-center gap-2 bg-rose-500/10 border-rose-500/30 text-rose-300">
                <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span>Unable to discover Gemini models: {discoveryError}</span>
              </div>
            )}
            {provider === 'gemini' && !apiKey.trim() && !backendConfig?.has_api_key && (
              <span className="text-[10px] text-slate-500 font-mono mt-1 block">
                Enter API key to discover available Gemini models
              </span>
            )}
          </div>

          {provider !== 'local_stub' && (
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="font-mono text-slate-400 uppercase text-[11px]">
                    API Key {backendConfig?.has_api_key && backendConfig?.provider === provider && (
                      <span className="text-emerald-400 font-normal">
                        (Configured: {backendConfig.masked_api_key || 'Encrypted on Server'})
                      </span>
                    )}
                  </label>
                  <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                    <Lock className="w-3 h-3" /> Encrypted at rest; never stored in browser
                  </span>
                </div>
                <div className="relative">
                  <input
                    type="password"
                    placeholder={
                      backendConfig?.has_api_key && backendConfig?.provider === provider
                        ? 'Enter new API key to replace existing saved key'
                        : 'Enter API key (e.g. AIzaSy...)'
                    }
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                  />
                  <Key className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="font-mono text-slate-400 uppercase text-[11px]">Custom Base URL (Optional)</label>
                  <span className="text-[10px] text-slate-500 font-mono">For local/compatible endpoints</span>
                </div>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="https://generativelanguage.googleapis.com"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                  />
                  <Globe className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800/80 font-mono">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={isTesting}
              className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-lg text-xs transition-colors"
            >
              {isTesting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Testing Connection...</span>
                </>
              ) : (
                <span>Test Connection</span>
              )}
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg text-xs shadow-md shadow-indigo-500/20 transition-colors"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save Configuration</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </PageContainer>
  );
};
