import React, { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users,
  Cpu,
  Shield,
  FileText,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Lock,
  ExternalLink,
  RefreshCw,
  Radio,
  Sun,
  Moon,
  Circle,
  Loader2,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Badge } from '../../components/ui/Badge';
import { Dialog } from '../../components/ui/Dialog';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { aiService, type AIProviderConfigRequest } from '../../services/ai';
import { normalizeError } from '../../services/client';

export function getFriendlyErrorMessage(errorCode?: string | null, rawMessage?: string): string {
  switch (errorCode) {
    case 'SUCCESS':
      return '✓ Gemini connection successful';
    case 'INVALID_API_KEY':
      return '✕ The Gemini API key is invalid. Please verify your API key and try again.';
    case 'MODEL_UNAVAILABLE':
      return '✕ The selected Gemini model is unavailable.';
    case 'RATE_LIMITED':
      return '⚠ Gemini is temporarily rate limited. Try again later.';
    case 'QUOTA_EXCEEDED':
      return '⚠ Gemini API quota has been exceeded. Check your plan and billing details.';
    case 'PROVIDER_UNREACHABLE':
      return '⚠ Unable to reach Google Gemini. Check your network connection.';
    case 'CONFIGURATION_ERROR':
      return '✕ Configuration error. An API key is required.';
    case 'GENERATION_FAILED':
      return '✕ Generation test failed.';
    default:
      if (rawMessage) {
        return rawMessage.replace(/^\[[A-Z_]+\]\s*/, '');
      }
      return '✕ Connection failed.';
  }
}

type SettingsTab = 'account' | 'ai' | 'investigation' | 'legal';

const PROVIDER_OPTIONS = [
  { value: 'gemini', label: 'Google Gemini (Cloud AI)' },
  { value: 'openai', label: 'OpenAI (Cloud AI)' },
  { value: 'anthropic', label: 'Anthropic Claude (Cloud AI)' },
  { value: 'local_openai', label: 'Local OpenAI Compatible (Ollama / Local Server)' },
  { value: 'local_stub', label: 'Local Deterministic Template Engine (Air-Gapped / Offline)' },
];

const MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  gemini: [
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Recommended)' },
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Fast Reasoning)' },
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Legacy Fast)' },
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Large Context & Deep Analysis)' },
  ],
  openai: [
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini (Fast Reasoning)' },
    { value: 'gpt-4o', label: 'GPT-4o (High Precision Forensic Reasoning)' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  ],
  anthropic: [
    { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet (Forensic Analysis)' },
    { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku (Fast)' },
  ],
  local_openai: [
    { value: 'llama3', label: 'Llama 3 (Local)' },
    { value: 'mistral', label: 'Mistral 7B (Local)' },
    { value: 'qwen2.5', label: 'Qwen 2.5 (Local)' },
  ],
  local_stub: [
    { value: 'adfir-deterministic-engine', label: 'ADFIR Deterministic Template Engine' },
  ],
};

const FORENSIC_AGENTS = [
  {
    name: 'Strategy Agent',
    domain: 'Planning & Hypothesis Generation',
    description: 'Proposes forensic examination plans based on ingested evidence types and case scope.',
    requiresLLM: true,
  },
  {
    name: 'Evidence Intelligence Agent',
    domain: 'File Profiling & Identification',
    description: 'Extracts file headers, entropy levels, MIME signatures, and partition metadata.',
    requiresLLM: false,
  },
  {
    name: 'Malware Agent',
    domain: 'Binary & YARA Analysis',
    description: 'Executes rule-based signatures and correlates detected suspicious patterns.',
    requiresLLM: false,
  },
  {
    name: 'Investigation Orchestrator',
    domain: 'Execution & Dependency Management',
    description: 'Dispatches tool runs in dependency order and collects raw artifacts.',
    requiresLLM: false,
  },
  {
    name: 'Report Synthesizer',
    domain: 'Evidentiary Synthesis & Reporting',
    description: 'Compiles verified findings and custody records into certified markdown and JSON reports.',
    requiresLLM: true,
  },
  {
    name: 'Verification Assistant',
    domain: 'Fact vs. Inference Governance',
    description: 'Enforces taxonomy rules and flags unsupported claims for investigator review.',
    requiresLLM: true,
  },
];

export const SettingsPage: React.FC = () => {
  const { user } = useAuthStore();
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = useMemo<SettingsTab>(() => {
    const tab = searchParams.get('tab');
    if (tab === 'ai' || tab === 'investigation' || tab === 'legal') return tab as SettingsTab;
    return 'account';
  }, [searchParams]);
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && (tab === 'account' || tab === 'ai' || tab === 'investigation' || tab === 'legal')) {
      setActiveTab(tab as SettingsTab);
    }
  }, [searchParams]);

  const handleTabSelect = (tab: SettingsTab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  // AI Configuration State
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-2.5-flash');
  const [endpoint, setEndpoint] = useState<string>('');
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [showRemoveConfirm, setShowRemoveConfirm] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    latency?: number | null;
  } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Queries
  const {
    data: aiConfig,
    isLoading: aiConfigLoading,
    refetch: refetchAiConfig,
  } = useQuery({
    queryKey: ['ai-provider-config'],
    queryFn: aiService.getConfig,
    retry: false,
  });

  const {
    refetch: refetchAiStatus,
  } = useQuery({
    queryKey: ['ai-provider-status'],
    queryFn: aiService.getStatus,
    retry: false,
  });

  const {
    data: dynamicModels,
  } = useQuery({
    queryKey: ['ai-provider-models', selectedProvider],
    queryFn: () => aiService.getModels(selectedProvider),
    staleTime: 60_000,
    retry: false,
  });

  const currentModelOptions = useMemo(() => {
    if (dynamicModels && dynamicModels.length > 0) {
      return dynamicModels.map((m) => ({
        value: m,
        label: m === 'gemini-2.5-flash' ? `${m} (Recommended)` : m,
      }));
    }
    return MODEL_OPTIONS[selectedProvider] || [];
  }, [dynamicModels, selectedProvider]);

  useEffect(() => {
    if (aiConfig) {
      if (aiConfig.provider) setSelectedProvider(aiConfig.provider);
      if (aiConfig.model) setSelectedModel(aiConfig.model);
      if (aiConfig.endpoint) setEndpoint(aiConfig.endpoint);
    }
  }, [aiConfig]);

  // Mutations
  const testMutation = useMutation({
    mutationFn: () =>
      aiService.testConnection({
        provider: selectedProvider,
        model: selectedModel,
        endpoint: endpoint.trim() || undefined,
        api_key: apiKeyInput.trim() || undefined,
      }),
    onSuccess: (res) => {
      setTestResult({
        success: res.success,
        message: getFriendlyErrorMessage(res.error_code, res.status_message),
        latency: res.latency_ms,
      });
      // Do not clear transient apiKeyInput so user can save after testing
    },
    onError: (err) => {
      const errorMsg = normalizeError(err);
      setTestResult({
        success: false,
        message: getFriendlyErrorMessage(undefined, errorMsg),
      });
    },
  });

  const saveMutation = useMutation({
    mutationFn: (payload: AIProviderConfigRequest) => aiService.saveConfig(payload),
    onSuccess: () => {
      setActionSuccess('AI provider configuration securely saved.');
      setActionError(null);
      setApiKeyInput('');
      qc.invalidateQueries({ queryKey: ['ai-provider-config'] });
      qc.invalidateQueries({ queryKey: ['ai-provider-status'] });
      setTimeout(() => setActionSuccess(null), 4000);
    },
    onError: (err) => {
      setActionError(normalizeError(err));
      setActionSuccess(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: aiService.deleteConfig,
    onSuccess: () => {
      setActionSuccess('AI provider configuration removed successfully.');
      setActionError(null);
      setApiKeyInput('');
      setTestResult(null);
      qc.invalidateQueries({ queryKey: ['ai-provider-config'] });
      qc.invalidateQueries({ queryKey: ['ai-provider-status'] });
      setTimeout(() => setActionSuccess(null), 4000);
    },
    onError: (err) => {
      setActionError(normalizeError(err));
      setActionSuccess(null);
    },
  });

  const handleProviderChange = (newProvider: string) => {
    setSelectedProvider(newProvider);
    const available = MODEL_OPTIONS[newProvider];
    if (available && available.length > 0) {
      setSelectedModel(available[0].value);
    }
    setTestResult(null);
    setActionError(null);
  };

  const handleSaveConfig = (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setActionSuccess(null);

    if (selectedProvider !== 'local_stub') {
      const hasExistingKey = Boolean(aiConfig?.has_api_key && aiConfig?.provider === selectedProvider);
      if (!apiKeyInput.trim() && !hasExistingKey) {
        setActionError(`An API key is required to configure ${selectedProvider === 'gemini' ? 'Google Gemini' : selectedProvider}.`);
        return;
      }
    }

    saveMutation.mutate({
      provider: selectedProvider,
      model: selectedModel,
      endpoint: endpoint.trim() || undefined,
      api_key: apiKeyInput.trim() || undefined,
      is_enabled: true,
    });
  };

  const isConfigured = Boolean(aiConfig?.is_enabled && (aiConfig?.has_api_key || aiConfig?.provider === 'local_stub'));

  const renderConnectionStatus = () => {
    if (testMutation.isPending) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
          <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
          Testing...
        </span>
      );
    }
    if (testResult) {
      if (testResult.success) {
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Connected {testResult.latency !== undefined && testResult.latency !== null ? `(${testResult.latency}ms)` : ''}
          </span>
        );
      }
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 border border-red-200">
          <AlertCircle className="w-3 h-3 text-red-600" />
          Connection failed
        </span>
      );
    }
    if (aiConfig?.is_enabled && (aiConfig?.has_api_key || aiConfig?.provider === 'local_stub')) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          Configured: {aiConfig.provider.toUpperCase()}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium bg-stone-100 text-stone-600 border border-stone-200">
        <Circle className="w-2.5 h-2.5 fill-stone-300 text-stone-300" />
        Not configured
      </span>
    );
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="border-b border-stone-200/80 pb-4">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Workstation Settings</h1>
        <p className="text-xs text-slate-500 mt-1">
          Configure investigator credentials, AI reasoning runtimes, forensic handling policies, and compliance disclosures.
        </p>
      </div>

      {/* Navigation Tabs — Exactly 4 Tabs */}
      <div className="flex items-center gap-1 border-b border-stone-200 text-xs font-medium">
        <button
          onClick={() => handleTabSelect('account')}
          className={`px-4 py-2 border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === 'account'
              ? 'border-slate-900 text-slate-900 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>Account & Security</span>
        </button>

        <button
          onClick={() => handleTabSelect('ai')}
          className={`px-4 py-2 border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === 'ai'
              ? 'border-slate-900 text-slate-900 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          <span>AI & Models</span>
        </button>

        <button
          onClick={() => handleTabSelect('investigation')}
          className={`px-4 py-2 border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === 'investigation'
              ? 'border-slate-900 text-slate-900 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Shield className="w-3.5 h-3.5" />
          <span>Investigation Policy</span>
        </button>

        <button
          onClick={() => handleTabSelect('legal')}
          className={`px-4 py-2 border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === 'legal'
              ? 'border-slate-900 text-slate-900 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Legal & Compliance</span>
        </button>
      </div>

      {/* TAB 1: AI & MODELS */}
      {activeTab === 'ai' && (
        <div className="space-y-6">
          {/* Active Provider Overview Card */}
          <Card className="bg-white border-stone-200">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 pb-3 mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Current AI Reasoning Runtime</h3>
                <p className="text-xs text-slate-500">
                  Orchestrates reasoning, tool selection proposals, and report synthesis.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {renderConnectionStatus()}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    refetchAiConfig();
                    refetchAiStatus();
                  }}
                  icon={<RefreshCw className="w-3 h-3" />}
                  title="Refresh configuration"
                />
              </div>
            </div>

            {aiConfigLoading ? (
              <div className="py-4 text-center text-xs text-slate-400">Loading AI configuration...</div>
            ) : aiConfig ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                <div>
                  <span className="text-slate-400 block mb-0.5">Provider</span>
                  <span className="font-semibold text-slate-800 uppercase">{aiConfig.provider}</span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Assigned Model</span>
                  <span className="font-semibold text-slate-800">{aiConfig.model}</span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Credential State</span>
                  <span className="text-slate-800">
                    {aiConfig.has_api_key ? (
                      <span className="text-emerald-700 font-sans font-medium flex items-center gap-1">
                        <Lock className="w-3 h-3 text-emerald-600" />
                        {aiConfig.masked_api_key || 'Encrypted (AES-GCM)'}
                      </span>
                    ) : (
                      'None (Local / Free)'
                    )}
                  </span>
                </div>
                <div className="flex items-center sm:justify-end">
                  <Button
                    variant="danger"
                    size="sm"
                    loading={deleteMutation.isPending}
                    onClick={() => setShowRemoveConfirm(true)}
                    icon={<Trash2 className="w-3 h-3" />}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ) : (
              <div className="p-3 bg-amber-50/70 border border-amber-200/80 rounded-lg text-xs text-amber-800">
                <p className="font-semibold mb-1">AI Reasoning runtime is currently unconfigured.</p>
                <p>
                  ADFIP will execute deterministic forensic tools locally, but AI hypothesis formulation and automated report synthesis require a configured provider below.
                </p>
              </div>
            )}
          </Card>

          {/* Provider Configuration Form */}
          <Card className="bg-white border-stone-200">
            <SectionHeader
              title="Configure AI Provider"
              description="Configure Google Gemini, OpenAI, Anthropic, or an on-premise local model endpoint. API keys are encrypted at rest with AES-GCM on the backend and never stored in the browser."
              size="sm"
            />

            {actionSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md text-xs mb-4 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{actionSuccess}</span>
              </div>
            )}

            {actionError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-800 rounded-md text-xs mb-4 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            <form onSubmit={handleSaveConfig} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Select
                  label="Provider"
                  value={selectedProvider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  options={PROVIDER_OPTIONS}
                  disabled={saveMutation.isPending || testMutation.isPending}
                />

                <Select
                  label="Model"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  options={currentModelOptions}
                  disabled={saveMutation.isPending || testMutation.isPending}
                />
              </div>

              {selectedProvider !== 'local_stub' && (
                <div className="space-y-3">
                  <Input
                    label="API Key / Secret Token"
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder={
                      aiConfig?.has_api_key && aiConfig.provider === selectedProvider
                        ? '•••••••••••••••• (Leave blank to keep current key)'
                        : 'Enter provider API key'
                    }
                    helper="Submitted credentials are encrypted on the backend using AES-GCM. Plaintext keys are never stored in the client."
                    disabled={saveMutation.isPending || testMutation.isPending}
                  />

                  {(selectedProvider === 'local_openai' || selectedProvider === 'openai') && (
                    <Input
                      label="Custom Endpoint URL (Optional)"
                      type="url"
                      value={endpoint}
                      onChange={(e) => setEndpoint(e.target.value)}
                      placeholder={
                        selectedProvider === 'local_openai'
                          ? 'http://localhost:11434/v1'
                          : 'https://api.openai.com/v1'
                      }
                      helper="Provide custom base URL if using an air-gapped proxy, vLLM, or Ollama endpoint."
                      disabled={saveMutation.isPending || testMutation.isPending}
                    />
                  )}
                </div>
              )}

              {/* Connection Test Output Banner */}
              {testResult && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-start gap-2 ${
                    testResult.success
                      ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                      : 'bg-red-50 border border-red-200 text-red-800'
                  }`}
                >
                  {testResult.success ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  )}
                  <div className="min-w-0">
                    <p className="font-semibold">{testResult.message}</p>
                    {testResult.latency !== undefined && testResult.latency !== null && (
                      <p className="text-[11px] font-mono mt-0.5">Response latency: {testResult.latency}ms</p>
                    )}
                  </div>
                </div>
              )}

              {/* Form Buttons */}
              <div className="flex items-center justify-between pt-2 border-t border-stone-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  loading={testMutation.isPending}
                  disabled={saveMutation.isPending}
                  onClick={() => testMutation.mutate()}
                  icon={<Radio className="w-3.5 h-3.5" />}
                >
                  Test Connection
                </Button>

                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={saveMutation.isPending}
                  disabled={testMutation.isPending}
                >
                  Save Configuration
                </Button>
              </div>
            </form>
          </Card>

          {/* Remove Configuration Confirmation Dialog */}
          <Dialog
            open={showRemoveConfirm}
            onClose={() => setShowRemoveConfirm(false)}
            title="Remove AI Provider Configuration?"
            description="This will remove the saved AI credential and configuration from ADFIP."
            size="sm"
          >
            <div className="space-y-4 pt-2">
              <p className="text-xs text-slate-600">
                Are you sure you want to remove the current configuration for{' '}
                <span className="font-semibold text-slate-800 uppercase">{aiConfig?.provider || selectedProvider}</span>?
                External AI features will be disabled until reconfigured.
              </p>
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-stone-100">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowRemoveConfirm(false)}
                  disabled={deleteMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  loading={deleteMutation.isPending}
                  onClick={() => {
                    deleteMutation.mutate(undefined, {
                      onSettled: () => setShowRemoveConfirm(false),
                    });
                  }}
                >
                  Remove
                </Button>
              </div>
            </div>
          </Dialog>

          {/* Agent-to-LLM Relationship Matrix */}
          <Card className="bg-white border-stone-200">
            <SectionHeader
              title="Forensic Agent System Architecture"
              description="ADFIP multi-agent coordination matrix. The LLM functions strictly as a downstream reasoning runtime; deterministic tool execution remains the authoritative forensic source of truth."
              size="sm"
            />

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200 text-slate-500 font-medium">
                    <th className="py-2.5 px-3">Agent Name</th>
                    <th className="py-2.5 px-3">Forensic Domain</th>
                    <th className="py-2.5 px-3">Reasoning Runtime</th>
                    <th className="py-2.5 px-3">Operational State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {FORENSIC_AGENTS.map((agent) => (
                    <tr key={agent.name} className="hover:bg-stone-50/50">
                      <td className="py-2.5 px-3 font-medium text-slate-900">
                        {agent.name}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600">
                        {agent.domain}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500">
                        {agent.requiresLLM
                          ? isConfigured
                            ? `${aiConfig?.provider.toUpperCase()} (${aiConfig?.model})`
                            : 'AI Provider Required'
                          : 'Deterministic Tool Engine'}
                      </td>
                      <td className="py-2.5 px-3">
                        {agent.requiresLLM ? (
                          isConfigured ? (
                            <Badge tone="success">Ready</Badge>
                          ) : (
                            <Badge tone="warning">AI Provider Required</Badge>
                          )
                        ) : (
                          <Badge tone="info">Active (Tool Engine)</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 2: ACCOUNT & SECURITY */}
      {activeTab === 'account' && (
        <div className="space-y-6">
          <Card className="bg-white border-stone-200 space-y-4">
            <SectionHeader
              title="Investigator Profile"
              description="Authenticated session information and organization credentials."
              size="sm"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
              <div className="p-3 bg-stone-50 rounded-lg">
                <span className="text-slate-400 block font-sans text-[11px]">Full Name</span>
                <span className="font-semibold text-slate-800 text-sm font-sans">{user?.name || 'Investigator'}</span>
              </div>
              <div className="p-3 bg-stone-50 rounded-lg">
                <span className="text-slate-400 block font-sans text-[11px]">Work Email</span>
                <span className="font-semibold text-slate-800 text-sm font-sans">{user?.email || 'N/A'}</span>
              </div>
              <div className="p-3 bg-stone-50 rounded-lg">
                <span className="text-slate-400 block font-sans text-[11px]">Agency / Organization</span>
                <span className="font-semibold text-slate-800 font-sans">{user?.organization || 'Not specified'}</span>
              </div>
              <div className="p-3 bg-stone-50 rounded-lg">
                <span className="text-slate-400 block font-sans text-[11px]">Assigned Role</span>
                <span className="font-semibold text-slate-800 font-sans">{user?.role || 'INVESTIGATOR'}</span>
              </div>
            </div>
          </Card>

          <Card className="bg-white border-stone-200 space-y-3">
            <SectionHeader
              title="Session & Credential Security"
              description="Cryptographic token lifecycle and token revocation policies."
              size="sm"
            />
            <div className="space-y-2 text-xs text-slate-600 leading-relaxed">
              <p>
                • <strong>In-Memory Token Isolation:</strong> Bearer access tokens are held exclusively in volatile browser session storage and cleared immediately upon logout.
              </p>
              <p>
                • <strong>Token Revocation Registry:</strong> When you sign out, the active token JTI is recorded in the backend revoked token table to prevent replay attacks.
              </p>
              <p>
                • <strong>No Plaintext Storage:</strong> ADFIP never writes user passwords or raw API keys to persistent local storage, IndexedDB, cookies, or debug logs.
              </p>
            </div>
          </Card>

          <Card className="bg-white border-stone-200 space-y-4">
            <SectionHeader
              title="Appearance & Theme"
              description="Customize workstation visual theme for long forensic examination sessions."
              size="sm"
            />
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`flex-1 p-3 rounded-lg border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  theme === 'light'
                    ? 'bg-stone-100 border-slate-700 text-slate-900 font-semibold ring-1 ring-slate-700'
                    : 'bg-white border-stone-200 text-slate-600 hover:bg-stone-50'
                }`}
              >
                <Sun className="w-4 h-4 text-amber-500 shrink-0" />
                <span>Light Theme (Standard Cream / Glass)</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`flex-1 p-3 rounded-lg border text-xs font-medium flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  theme === 'dark'
                    ? 'bg-slate-800 border-slate-600 text-white font-semibold ring-1 ring-slate-400'
                    : 'bg-white border-stone-200 text-slate-600 hover:bg-stone-50'
                }`}
              >
                <Moon className="w-4 h-4 text-slate-400 shrink-0" />
                <span>Dark Theme (Night / Low Light)</span>
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 3: INVESTIGATION POLICY */}
      {activeTab === 'investigation' && (
        <div className="space-y-6">
          <Card className="bg-white border-stone-200 space-y-4">
            <SectionHeader
              title="Forensic Preservation & Integrity Policies"
              description="Global digital evidence handling standards enforced across all cases."
              size="sm"
            />

            <div className="space-y-3 text-xs text-slate-700">
              <div className="p-3.5 border border-stone-200 rounded-lg bg-stone-50/50">
                <p className="font-semibold text-slate-900 mb-1">ISO/IEC 27037 Compliance Mode</p>
                <p className="text-slate-600 leading-relaxed">
                  Strict determinism is enabled platform-wide. Evidence files are ingested in read-only mode, and hashes (SHA-256 and MD5) are generated before any parsing or analysis begins.
                </p>
              </div>

              <div className="p-3.5 border border-stone-200 rounded-lg bg-stone-50/50">
                <p className="font-semibold text-slate-900 mb-1">Chain of Custody Immutability</p>
                <p className="text-slate-600 leading-relaxed">
                  Every evidence access, verification check, artifact extraction, and report export action generates an immutable audit entry tied to the authenticated investigator ID.
                </p>
              </div>

              <div className="p-3.5 border border-stone-200 rounded-lg bg-stone-50/50">
                <p className="font-semibold text-slate-900 mb-1">Human-in-the-Loop Certification</p>
                <p className="text-slate-600 leading-relaxed">
                  AI hypotheses and tool findings are categorized as INFERENCE until an investigator explicitly certifies them. Unverified claims cannot be presented as forensic facts in court-ready reports.
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 4: LEGAL & COMPLIANCE */}
      {activeTab === 'legal' && (
        <div className="space-y-6">
          <Card className="bg-white border-stone-200 space-y-4">
            <SectionHeader
              title="Legal Documents & Operational Compliance"
              description="Review ADFIP terms of service, evidence handling policies, and data privacy disclosures."
              size="sm"
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 border border-stone-200 rounded-lg bg-stone-50/50 space-y-2">
                <h4 className="text-sm font-semibold text-slate-900">Terms of Service</h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Defines acceptable evidence examination standards, RBAC privileges, tool determinism, and investigator certification responsibilities.
                </p>
                <Link to="/terms" target="_blank" className="inline-block pt-1">
                  <Button variant="outline" size="sm" icon={<ExternalLink className="w-3.5 h-3.5" />}>
                    Open Terms of Service
                  </Button>
                </Link>
              </div>

              <div className="p-4 border border-stone-200 rounded-lg bg-stone-50/50 space-y-2">
                <h4 className="text-sm font-semibold text-slate-900">Privacy Policy</h4>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Explains evidence confidentiality, network egress controls, credential AES-GCM encryption, and audit log data protection.
                </p>
                <Link to="/privacy" target="_blank" className="inline-block pt-1">
                  <Button variant="outline" size="sm" icon={<ExternalLink className="w-3.5 h-3.5" />}>
                    Open Privacy Policy
                  </Button>
                </Link>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
