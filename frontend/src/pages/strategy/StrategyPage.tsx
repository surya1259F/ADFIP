import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Blocks,
  RefreshCw,
  Terminal,
  ChevronDown,
  ChevronRight,
  HelpCircle,
  ShieldCheck,
  ShieldAlert,
  Layers,
  Info,
  Plus,
  Edit2,
  Check,
  X,
  Ban,
  Target,
  FileSearch,
  Trash2,
  Sliders,
  CheckSquare,
  Square,
  BookOpen,
  Sparkles,
  Save,
  CheckCircle,
} from 'lucide-react';
import { evidenceService } from '../../services/evidence';
import { casesService } from '../../services/cases';
import { normalizeError } from '../../services/client';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge, StatusBadge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { SectionHeader } from '../../components/ui/SectionHeader';
import { Dialog } from '../../components/ui/Dialog';
import { Input } from '../../components/ui/Input';
import { Textarea } from '../../components/ui/Textarea';
import { Select } from '../../components/ui/Select';
import type {
  InvestigativeQuestion,
  InvestigationRequirementItem,
  InvestigationRequirementTemplate,
  InvestigationScope,
} from '../../types';

const CATEGORY_OPTIONS = [
  { value: 'AUTH_ANALYSIS', label: 'Authentication & Logons (AUTH_ANALYSIS)' },
  { value: 'PROCESS_ANALYSIS', label: 'Process & Memory (PROCESS_ANALYSIS)' },
  { value: 'MALWARE_DETECTION', label: 'Malware & Signatures (MALWARE_DETECTION)' },
  { value: 'FILE_SYSTEM_RECOVERY', label: 'File System & Deleted Files (FILE_SYSTEM_RECOVERY)' },
  { value: 'TIMELINE_CORRELATION', label: 'Timeline & Activity (TIMELINE_CORRELATION)' },
  { value: 'NETWORK_ANALYSIS', label: 'Network & Exfiltration (NETWORK_ANALYSIS)' },
  { value: 'METADATA_ANALYSIS', label: 'Metadata & Anti-Forensics (METADATA_ANALYSIS)' },
  { value: 'CUSTOM', label: 'Custom Investigation Inquiry (CUSTOM)' },
];

const STANDARD_OUTPUT_FORMATS = [
  'EVIDENCE_ARTIFACTS',
  'TIMELINE_EVENTS',
  'EXTRACTED_STRINGS',
  'DISK_FILE_LISTING',
  'YARA_MATCH_RECORDS',
  'EVENT_LOG_RECORDS',
  'MEMORY_PROCESS_TREE',
];

export const StrategyPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});

  // Objective edit state
  const [isEditingObjective, setIsEditingObjective] = useState(false);
  const [objectiveInput, setObjectiveInput] = useState('');

  // Template Picker Dialog
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);

  // Requirement Dialog State (Add / Edit)
  const [reqDialogOpen, setReqDialogOpen] = useState(false);
  const [editingReq, setEditingReq] = useState<InvestigationRequirementItem | null>(null);
  const [reqTitle, setReqTitle] = useState('');
  const [reqCategory, setReqCategory] = useState('CUSTOM');
  const [reqDescription, setReqDescription] = useState('');
  const [reqSelectedEvidenceIds, setReqSelectedEvidenceIds] = useState<string[]>([]);
  const [reqExpectedOutputs, setReqExpectedOutputs] = useState<string[]>(['EVIDENCE_ARTIFACTS']);
  const [reqTimeStart, setReqTimeStart] = useState('');
  const [reqTimeEnd, setReqTimeEnd] = useState('');
  const [reqUsers, setReqUsers] = useState('');
  const [reqHosts, setReqHosts] = useState('');
  const [reqProcesses, setReqProcesses] = useState('');
  const [reqDialogError, setReqDialogError] = useState<string | null>(null);

  // Investigative Questions (Legacy / Complementary)
  const [addQDialogOpen, setAddQDialogOpen] = useState(false);
  const [newQuestionText, setNewQuestionText] = useState('');
  const [newQCategory, setNewQCategory] = useState('INVESTIGATOR_INQUIRY');
  const [newHypothesis, setNewHypothesis] = useState('');

  const [editQDialogOpen, setEditQDialogOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<InvestigativeQuestion | null>(null);
  const [editQuestionText, setEditQuestionText] = useState('');
  const [editHypothesis, setEditHypothesis] = useState('');
  const [qDialogError, setQDialogError] = useState<string | null>(null);

  const toggleTaskExpanded = (taskKey: string) => {
    setExpandedTasks((prev) => ({
      ...prev,
      [taskKey]: !prev[taskKey],
    }));
  };

  // Queries
  const {
    data: evidenceItems = [],
    isError: isEvError,
    error: evError,
    refetch: refetchEv,
  } = useQuery({
    queryKey: ['cases', caseId, 'evidence'],
    queryFn: () => evidenceService.listByCase(caseId!),
    enabled: !!caseId,
  });

  const {
    data: reqsData,
    isLoading: reqsLoading,
    isError: isReqsError,
    error: reqsError,
    refetch: refetchReqs,
  } = useQuery({
    queryKey: ['cases', caseId, 'requirements'],
    queryFn: () => casesService.getRequirements(caseId!),
    enabled: !!caseId,
  });

  const {
    data: plan,
    isLoading: planLoading,
    isError: isPlanError,
    error: planError,
    refetch: refetchPlan,
  } = useQuery({
    queryKey: ['cases', caseId, 'plan'],
    queryFn: () => casesService.getPlan(caseId!),
    enabled: !!caseId,
  });

  const {
    data: questionsData,
    isLoading: qLoading,
    isError: isQError,
    error: qError,
    refetch: refetchQ,
  } = useQuery({
    queryKey: ['cases', caseId, 'investigative-questions'],
    queryFn: () => casesService.getInvestigativeQuestions(caseId!),
    enabled: !!caseId,
  });

  // Sync objective input
  useEffect(() => {
    if (reqsData?.objective) {
      setObjectiveInput(reqsData.objective);
    }
  }, [reqsData?.objective]);

  // Mutations
  const generatePlanMutation = useMutation({
    mutationFn: () => casesService.generatePlanFromRequirements(caseId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'requirements'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'investigative-questions'] });
    },
  });

  const saveObjectiveMutation = useMutation({
    mutationFn: (newObjective: string) =>
      casesService.saveRequirements(caseId!, {
        requirements: reqsData?.requirements || [],
        objective: newObjective,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'requirements'] });
      setIsEditingObjective(false);
    },
  });

  const addRequirementMutation = useMutation({
    mutationFn: (payload: any) => casesService.addRequirement(caseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'requirements'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
      setReqDialogOpen(false);
      resetReqForm();
    },
    onError: (err) => setReqDialogError(normalizeError(err)),
  });

  const updateRequirementMutation = useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      casesService.updateRequirement(caseId!, vars.id, vars.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'requirements'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
      setReqDialogOpen(false);
      resetReqForm();
    },
    onError: (err) => setReqDialogError(normalizeError(err)),
  });

  const deleteRequirementMutation = useMutation({
    mutationFn: (id: string) => casesService.deleteRequirement(caseId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'requirements'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
    },
  });

  const approveAllRequirementsMutation = useMutation({
    mutationFn: async () => {
      const allReqs = (reqsData?.requirements || []).map((r) => ({
        ...r,
        approval_status: 'APPROVED' as const,
      }));
      return casesService.saveRequirements(caseId!, { requirements: allReqs });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'requirements'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
    },
  });

  // Question mutations (Legacy / Complementary)
  const addQuestionMutation = useMutation({
    mutationFn: (data: { question_text: string; category?: string; hypothesis?: string }) =>
      casesService.addInvestigativeQuestion(caseId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'investigative-questions'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
      setAddQDialogOpen(false);
      setNewQuestionText('');
      setNewHypothesis('');
      setQDialogError(null);
    },
    onError: (err) => setQDialogError(normalizeError(err)),
  });

  const updateQuestionMutation = useMutation({
    mutationFn: (vars: {
      questionId: string;
      data: { question_text?: string; hypothesis?: string; approval_status?: 'APPROVED' | 'REJECTED' | 'PENDING' };
    }) => casesService.updateInvestigativeQuestion(caseId!, vars.questionId, vars.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'investigative-questions'] });
      queryClient.invalidateQueries({ queryKey: ['cases', caseId, 'plan'] });
      setEditQDialogOpen(false);
      setEditingQuestion(null);
      setQDialogError(null);
    },
    onError: (err) => setQDialogError(normalizeError(err)),
  });

  // Helper Form Handlers
  const resetReqForm = () => {
    setEditingReq(null);
    setReqTitle('');
    setReqCategory('CUSTOM');
    setReqDescription('');
    setReqSelectedEvidenceIds([]);
    setReqExpectedOutputs(['EVIDENCE_ARTIFACTS']);
    setReqTimeStart('');
    setReqTimeEnd('');
    setReqUsers('');
    setReqHosts('');
    setReqProcesses('');
    setReqDialogError(null);
  };

  const handleOpenAddRequirement = () => {
    resetReqForm();
    // Default select all evidence in case if any
    const allEvIds = evidenceItems.map((e) => e.id);
    setReqSelectedEvidenceIds(allEvIds);
    setReqDialogOpen(true);
  };

  const handleSelectTemplate = (template: InvestigationRequirementTemplate) => {
    resetReqForm();
    setReqTitle(template.title);
    setReqCategory(template.category);
    setReqDescription(template.description);
    setReqExpectedOutputs(template.expected_outputs || ['EVIDENCE_ARTIFACTS']);
    // Auto-select relevant evidence items
    const allEvIds = evidenceItems.map((e) => e.id);
    setReqSelectedEvidenceIds(allEvIds);
    setTemplatePickerOpen(false);
    setReqDialogOpen(true);
  };

  const handleOpenEditRequirement = (req: InvestigationRequirementItem) => {
    setEditingReq(req);
    setReqTitle(req.title);
    setReqCategory(req.category);
    setReqDescription(req.description || '');
    setReqSelectedEvidenceIds(req.selected_evidence_ids || []);
    setReqExpectedOutputs(req.expected_outputs || ['EVIDENCE_ARTIFACTS']);
    setReqTimeStart(req.scope?.time_range_start || '');
    setReqTimeEnd(req.scope?.time_range_end || '');
    setReqUsers((req.scope?.relevant_users || []).join(', '));
    setReqHosts((req.scope?.relevant_hosts || []).join(', '));
    setReqProcesses((req.scope?.relevant_processes || []).join(', '));
    setReqDialogError(null);
    setReqDialogOpen(true);
  };

  const handleSaveRequirement = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reqTitle.trim()) {
      setReqDialogError('Requirement title cannot be empty.');
      return;
    }

    const scopeObj: InvestigationScope = {
      time_range_start: reqTimeStart.trim() || undefined,
      time_range_end: reqTimeEnd.trim() || undefined,
      relevant_users: reqUsers.split(',').map((u) => u.trim()).filter(Boolean),
      relevant_hosts: reqHosts.split(',').map((h) => h.trim()).filter(Boolean),
      relevant_processes: reqProcesses.split(',').map((p) => p.trim()).filter(Boolean),
    };

    const payload = {
      title: reqTitle.trim(),
      category: reqCategory,
      description: reqDescription.trim(),
      selected_evidence_ids: reqSelectedEvidenceIds,
      expected_outputs: reqExpectedOutputs.length > 0 ? reqExpectedOutputs : ['EVIDENCE_ARTIFACTS'],
      scope: scopeObj,
      approval_status: editingReq?.approval_status || 'APPROVED',
    };

    if (editingReq) {
      updateRequirementMutation.mutate({ id: editingReq.id, data: payload });
    } else {
      addRequirementMutation.mutate(payload);
    }
  };

  const handleToggleRequirementApproval = (req: InvestigationRequirementItem) => {
    const nextStatus = req.approval_status === 'APPROVED' ? 'REJECTED' : 'APPROVED';
    updateRequirementMutation.mutate({
      id: req.id,
      data: { approval_status: nextStatus },
    });
  };

  const toggleEvidenceSelection = (evId: string) => {
    setReqSelectedEvidenceIds((prev) =>
      prev.includes(evId) ? prev.filter((id) => id !== evId) : [...prev, evId]
    );
  };

  const toggleOutputFormat = (fmt: string) => {
    setReqExpectedOutputs((prev) =>
      prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt]
    );
  };

  if (isEvError) return <ErrorState message={normalizeError(evError)} onRetry={refetchEv} />;

  const tasks = plan?.tasks || [];
  const requirements: InvestigationRequirementItem[] = reqsData?.requirements || [];
  const questions: InvestigativeQuestion[] =
    questionsData?.questions || plan?.investigative_questions || [];
  const templates: InvestigationRequirementTemplate[] = reqsData?.available_templates || [];

  const approvedReqCount = requirements.filter((r) => r.approval_status === 'APPROVED').length;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <SectionHeader
        title="Investigation Strategy & Requirements"
        description="Evidence-driven discovery requirements, specialist agent mapping, explainable tool selection, and investigator governance"
        action={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              loading={generatePlanMutation.isPending}
              onClick={() => generatePlanMutation.mutate()}
              icon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Regenerate Plan
            </Button>
            <Button
              size="sm"
              variant="primary"
              onClick={() => navigate(`/cases/${caseId}/execution`)}
              icon={<Terminal className="w-3.5 h-3.5" />}
            >
              Open Execution
            </Button>
          </div>
        }
      />

      {/* 1. Investigation Objective Definition Card */}
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1">
            <div className="p-2 bg-blue-50 text-blue-700 rounded-md shrink-0 mt-0.5">
              <Target className="w-4 h-4" />
            </div>
            <div className="flex-1 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Case Investigation Objective
                </span>
                <Badge tone="info">Forensic Goal</Badge>
              </div>

              {isEditingObjective ? (
                <div className="space-y-2 pt-1">
                  <Textarea
                    value={objectiveInput}
                    onChange={(e) => setObjectiveInput(e.target.value)}
                    rows={2}
                    placeholder="Enter the primary investigative objective for this digital forensic case..."
                  />
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="primary"
                      icon={<Save className="w-3.5 h-3.5" />}
                      loading={saveObjectiveMutation.isPending}
                      onClick={() => saveObjectiveMutation.mutate(objectiveInput)}
                    >
                      Save Objective
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setObjectiveInput(reqsData?.objective || '');
                        setIsEditingObjective(false);
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm font-medium text-slate-900 leading-relaxed">
                  {reqsData?.objective || 'Investigate digital forensic incident and determine root cause.'}
                </p>
              )}
            </div>
          </div>

          {!isEditingObjective && (
            <Button
              size="sm"
              variant="ghost"
              icon={<Edit2 className="w-3.5 h-3.5 text-slate-600" />}
              onClick={() => setIsEditingObjective(true)}
            >
              Edit Objective
            </Button>
          )}
        </div>
      </Card>

      {/* Forensic Strategy Summary Banner */}
      {plan?.strategy_summary && (
        <Card className="bg-slate-900 text-white border-slate-800">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-slate-800 rounded-md shrink-0">
              <Blocks className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-1">
                Forensic Strategy Summary
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                {plan.strategy_summary}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* 2. Investigation Requirements & Discovery Definition (Part 6 & 7) */}
      <Card padding={false}>
        <div className="p-4 border-b border-stone-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FileSearch className="w-4 h-4 text-emerald-600 shrink-0" />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-800">
                  Investigation Discovery Requirements
                </h2>
                <Badge tone={approvedReqCount > 0 ? 'success' : 'neutral'}>
                  {approvedReqCount} Approved of {requirements.length}
                </Badge>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Investigator-defined discovery requirements, scope constraints, and target outputs
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              size="sm"
              variant="outline"
              icon={<BookOpen className="w-3.5 h-3.5 text-blue-600" />}
              onClick={() => setTemplatePickerOpen(true)}
            >
              Choose Template
            </Button>
            <Button
              size="sm"
              variant="secondary"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={handleOpenAddRequirement}
            >
              Add Requirement
            </Button>
            {requirements.some((r) => r.approval_status !== 'APPROVED') && (
              <Button
                size="sm"
                variant="ghost"
                icon={<CheckCircle className="w-3.5 h-3.5 text-emerald-600" />}
                loading={approveAllRequirementsMutation.isPending}
                onClick={() => approveAllRequirementsMutation.mutate()}
                title="Approve all requirements"
              >
                Approve All
              </Button>
            )}
          </div>
        </div>

        {reqsLoading && (
          <div className="p-4 space-y-3">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        )}

        {isReqsError && (
          <div className="p-4">
            <ErrorState message={normalizeError(reqsError)} onRetry={refetchReqs} />
          </div>
        )}

        {!reqsLoading && !isReqsError && requirements.length === 0 && (
          <div className="p-8">
            <EmptyState
              icon={<FileSearch className="w-8 h-8" />}
              title="No discovery requirements configured"
              description="Define what you want to discover or pick from the 13 standard forensic templates."
              action={
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    icon={<BookOpen className="w-3.5 h-3.5" />}
                    onClick={() => setTemplatePickerOpen(true)}
                  >
                    Select Template
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    icon={<Plus className="w-3.5 h-3.5" />}
                    onClick={handleOpenAddRequirement}
                  >
                    Custom Requirement
                  </Button>
                </div>
              }
            />
          </div>
        )}

        {!reqsLoading && !isReqsError && requirements.length > 0 && (
          <div className="divide-y divide-stone-100">
            {requirements.map((req) => {
              const isApproved = req.approval_status === 'APPROVED';
              const isExcluded = req.approval_status === 'REJECTED';
              const scope = req.scope || {};
              const hasScope =
                scope.time_range_start ||
                scope.time_range_end ||
                (scope.relevant_users && scope.relevant_users.length > 0) ||
                (scope.relevant_hosts && scope.relevant_hosts.length > 0) ||
                (scope.relevant_processes && scope.relevant_processes.length > 0);

              return (
                <div
                  key={req.id}
                  className={`p-4 transition-colors ${
                    isExcluded ? 'bg-red-50/20 opacity-70' : 'hover:bg-stone-50/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                          {req.id}
                        </span>
                        <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                          {req.category}
                        </span>
                        {req.assigned_agent && (
                          <span className="text-[11px] font-mono text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
                            {req.assigned_agent}
                          </span>
                        )}

                        {/* Approval State Badges */}
                        {isApproved && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                            <Check className="w-3 h-3" />
                            Approved
                          </span>
                        )}
                        {isExcluded && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200">
                            <Ban className="w-3 h-3" />
                            Excluded
                          </span>
                        )}
                      </div>

                      <p
                        className={`text-sm font-semibold leading-snug ${
                          isExcluded ? 'text-slate-500 line-through' : 'text-slate-900'
                        }`}
                      >
                        {req.title}
                      </p>

                      {req.description && (
                        <p className="text-xs text-slate-600 leading-relaxed">
                          {req.description}
                        </p>
                      )}

                      {/* Scope Summary */}
                      {hasScope && (
                        <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200/80 rounded px-2.5 py-1.5 flex items-center gap-2 flex-wrap mt-1">
                          <span className="font-semibold text-slate-700">Scope:</span>
                          {scope.time_range_start && (
                            <span className="font-mono text-[11px] text-slate-600">
                              From: {scope.time_range_start}
                            </span>
                          )}
                          {scope.time_range_end && (
                            <span className="font-mono text-[11px] text-slate-600">
                              To: {scope.time_range_end}
                            </span>
                          )}
                          {scope.relevant_users && scope.relevant_users.length > 0 && (
                            <span className="text-[11px] text-slate-700">
                              Users: <span className="font-mono">{scope.relevant_users.join(', ')}</span>
                            </span>
                          )}
                          {scope.relevant_hosts && scope.relevant_hosts.length > 0 && (
                            <span className="text-[11px] text-slate-700">
                              Hosts/IPs: <span className="font-mono">{scope.relevant_hosts.join(', ')}</span>
                            </span>
                          )}
                          {scope.relevant_processes && scope.relevant_processes.length > 0 && (
                            <span className="text-[11px] text-slate-700">
                              Processes: <span className="font-mono">{scope.relevant_processes.join(', ')}</span>
                            </span>
                          )}
                        </div>
                      )}

                      {/* Attached Evidence & Expected Outputs */}
                      <div className="flex items-center gap-4 flex-wrap text-xs pt-1.5">
                        {req.selected_evidence_names && req.selected_evidence_names.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-slate-500 font-medium">Evidence:</span>
                            {req.selected_evidence_names.map((evName, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 bg-stone-100 text-slate-800 border border-stone-200 px-2 py-0.5 rounded text-[11px] font-mono"
                              >
                                {evName}
                              </span>
                            ))}
                          </div>
                        )}

                        {req.expected_outputs && req.expected_outputs.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-slate-500 font-medium">Outputs:</span>
                            {req.expected_outputs.map((outFmt, idx) => (
                              <span
                                key={idx}
                                className="bg-emerald-50 text-emerald-800 border border-emerald-200 px-1.5 py-0.2 rounded text-[10px] font-mono font-medium"
                              >
                                {outFmt}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Action Controls */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Edit2 className="w-3.5 h-3.5 text-slate-600" />}
                        onClick={() => handleOpenEditRequirement(req)}
                        title="Edit requirement and scope"
                      >
                        Edit
                      </Button>

                      <Button
                        size="sm"
                        variant={isApproved ? 'ghost' : 'outline'}
                        icon={
                          isApproved ? (
                            <X className="w-3.5 h-3.5 text-red-500" />
                          ) : (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          )
                        }
                        loading={updateRequirementMutation.isPending}
                        onClick={() => handleToggleRequirementApproval(req)}
                        title={isApproved ? 'Exclude requirement' : 'Approve requirement'}
                      >
                        {isApproved ? 'Exclude' : 'Approve'}
                      </Button>

                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Trash2 className="w-3.5 h-3.5 text-stone-400 hover:text-red-600" />}
                        loading={deleteRequirementMutation.isPending}
                        onClick={() => {
                          if (window.confirm(`Delete requirement "${req.title}"?`)) {
                            deleteRequirementMutation.mutate(req.id);
                          }
                        }}
                        title="Delete requirement"
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* 3. Explainable Investigation Execution Plan (Part 7 & 8) */}
      <Card padding={false}>
        <div className="p-4 border-b border-stone-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              Explainable Forensic Execution Plan
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Deterministic sequence mapped to requirements with selection rationale, candidate evaluations, and risk boundaries
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              loading={generatePlanMutation.isPending}
              onClick={() => generatePlanMutation.mutate()}
              icon={<Sparkles className="w-3.5 h-3.5 text-emerald-600" />}
            >
              Generate from Requirements
            </Button>
            <Badge tone={tasks.length > 0 ? 'active' : 'neutral'}>
              {tasks.length} {tasks.length === 1 ? 'Task' : 'Tasks'}
            </Badge>
          </div>
        </div>

        {planLoading && (
          <div className="p-4 space-y-2">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        )}

        {isPlanError && (
          <div className="p-4">
            <ErrorState message={normalizeError(planError)} onRetry={refetchPlan} />
          </div>
        )}

        {!planLoading && !isPlanError && tasks.length === 0 && (
          <div className="p-8">
            <EmptyState
              icon={<Blocks className="w-8 h-8" />}
              title="No execution tasks planned"
              description="Click 'Generate from Requirements' to create an autonomous forensic execution plan."
              action={
                <Button
                  size="sm"
                  variant="primary"
                  loading={generatePlanMutation.isPending}
                  onClick={() => generatePlanMutation.mutate()}
                  icon={<Sparkles className="w-3.5 h-3.5" />}
                >
                  Generate Plan
                </Button>
              }
            />
          </div>
        )}

        {!planLoading && !isPlanError && tasks.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-stone-50 border-b border-stone-200 text-slate-600 font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-3">Req / Task</th>
                  <th className="py-2.5 px-3">Evidence</th>
                  <th className="py-2.5 px-3">Specialist Agent</th>
                  <th className="py-2.5 px-3">Forensic Tool</th>
                  <th className="py-2.5 px-3">Expected Output</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {tasks.map((task: any, idx: number) => {
                  const taskKey = task.task_key || task.step_id || `task-${idx + 1}`;
                  const isExpanded = !!expandedTasks[taskKey];
                  const rationale = task.rationale || {};
                  const toolExplanation = rationale.tool_explanation || {};
                  const whySelected =
                    rationale.why_selected ||
                    rationale.selection_reason ||
                    task.reason ||
                    'Standard forensic capability execution.';
                  const risks = rationale.risks_and_limitations;
                  const expectedOutputs: string[] =
                    task.expected_outputs || toolExplanation.expected_output || [];
                  const candidates: string[] =
                    task.candidate_tool_ids || toolExplanation.candidate_tools || [];
                  const isToolAvailable =
                    task.tool_available !== false &&
                    task.selected_tool_id !== null &&
                    !task.status?.startsWith('BLOCKED');
                  const blockingReason = task.blocking_reason;
                  const toolName =
                    task.selected_tool_name ||
                    task.selected_tool_id ||
                    task.tool ||
                    'Automated Tool';
                  const agentName = task.agent_name || task.agent || 'ForensicAgent';
                  const reqTitleDisplay =
                    task.requirement_title ||
                    rationale.requirement_title ||
                    task.capability_id ||
                    task.action ||
                    'Forensic Task';
                  const evidenceName =
                    task.evidence_name ||
                    (task.evidence_ids && task.evidence_ids[0]) ||
                    'All Evidence';

                  return (
                    <React.Fragment key={taskKey}>
                      <tr className="hover:bg-stone-50/60 transition-colors">
                        <td className="py-3 px-3">
                          <div className="font-semibold text-slate-900">{reqTitleDisplay}</div>
                          <div className="font-mono text-[11px] text-slate-500">{taskKey}</div>
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-mono text-[11px] text-slate-700 bg-stone-100 px-1.5 py-0.5 rounded">
                            {evidenceName}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-medium text-slate-800">{agentName}</span>
                        </td>
                        <td className="py-3 px-3">
                          {isToolAvailable ? (
                            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded font-mono font-medium">
                              <ShieldCheck className="w-3 h-3 text-emerald-600" />
                              {toolName}
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded font-mono font-medium"
                              title={blockingReason || 'Tool not available on host'}
                            >
                              <ShieldAlert className="w-3 h-3 text-amber-600" />
                              BLOCKED
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-1 flex-wrap">
                            {expectedOutputs.slice(0, 2).map((outKey, oIdx) => (
                              <span
                                key={oIdx}
                                className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-mono text-[10px]"
                              >
                                {outKey}
                              </span>
                            ))}
                            {expectedOutputs.length > 2 && (
                              <span className="text-slate-400 text-[10px]">
                                +{expectedOutputs.length - 2}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <StatusBadge status={task.status || 'PLANNED'} />
                        </td>
                        <td className="py-3 px-3 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => toggleTaskExpanded(taskKey)}
                            icon={
                              isExpanded ? (
                                <ChevronDown className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronRight className="w-3.5 h-3.5" />
                              )
                            }
                          >
                            Rationale
                          </Button>
                        </td>
                      </tr>

                      {/* Expandable Rationale Details Row */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={7} className="p-0">
                            <div className="px-6 py-4 bg-stone-50 border-t border-b border-stone-200 space-y-3 text-xs">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="bg-white p-3 rounded border border-stone-200 space-y-1.5">
                                  <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                                    <Layers className="w-3.5 h-3.5 text-blue-600" />
                                    <span>Selection Rationale</span>
                                  </div>
                                  <p className="text-slate-600 leading-relaxed">{whySelected}</p>
                                  {candidates.length > 0 && (
                                    <div className="pt-1">
                                      <span className="text-slate-500 font-medium">
                                        Evaluated Candidates:{' '}
                                      </span>
                                      <span className="font-mono text-slate-700">
                                        {candidates.join(', ')}
                                      </span>
                                    </div>
                                  )}
                                </div>

                                <div className="bg-white p-3 rounded border border-stone-200 space-y-1.5">
                                  <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                                    <Info className="w-3.5 h-3.5 text-emerald-600" />
                                    <span>Risk Controls & Expected Artifacts</span>
                                  </div>
                                  <p className="text-slate-600 leading-relaxed">
                                    {risks ||
                                      'Standard deterministic execution within read-only cryptographic sandbox.'}
                                  </p>
                                  {expectedOutputs.length > 0 && (
                                    <div className="pt-1 flex items-center gap-1.5 flex-wrap">
                                      <span className="text-slate-500 font-medium">Outputs:</span>
                                      {expectedOutputs.map((outKey, oIdx) => (
                                        <span
                                          key={oIdx}
                                          className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-mono text-[10px]"
                                        >
                                          {outKey}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 4. Investigative Questions & Feasibility Assessment (Complementary Inquiries) */}
      <Card padding={false}>
        <div className="p-4 border-b border-stone-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-blue-600 shrink-0" />
            <div>
              <h2 className="text-sm font-semibold text-slate-800">
                Case Inquiry Hypotheses & Evidence Feasibility
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Dynamic forensic hypotheses evaluated against submitted evidence domains
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => {
                setQDialogError(null);
                setAddQDialogOpen(true);
              }}
            >
              Add Custom Inquiry
            </Button>
            <Badge tone={questions.length > 0 ? 'active' : 'neutral'}>
              {questions.length} {questions.length === 1 ? 'Inquiry' : 'Inquiries'}
            </Badge>
          </div>
        </div>

        {qLoading && (
          <div className="p-4 space-y-3">
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        )}

        {isQError && (
          <div className="p-4">
            <ErrorState message={normalizeError(qError)} onRetry={refetchQ} />
          </div>
        )}

        {!qLoading && !isQError && questions.length === 0 && (
          <div className="p-8">
            <EmptyState
              icon={<HelpCircle className="w-8 h-8" />}
              title="No investigative questions generated"
              description="Define the case objective or add custom questions to guide the forensic analysis."
              action={
                <Button
                  size="sm"
                  variant="primary"
                  icon={<Plus className="w-3.5 h-3.5" />}
                  onClick={() => setAddQDialogOpen(true)}
                >
                  Add Custom Inquiry
                </Button>
              }
            />
          </div>
        )}

        {!qLoading && !isQError && questions.length > 0 && (
          <div className="divide-y divide-stone-100">
            {questions.map((q) => {
              const isRejected = q.approval_status === 'REJECTED';
              const isApproved = q.approval_status === 'APPROVED' || !q.approval_status;

              return (
                <div
                  key={q.question_id || q.code}
                  className={`p-4 transition-colors ${
                    isRejected ? 'bg-red-50/30 opacity-75' : 'hover:bg-stone-50/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                          {q.question_id || q.code}
                        </span>
                        <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                          {q.category}
                        </span>
                        {q.archetype && (
                          <span className="text-[11px] font-mono text-slate-400">
                            [{q.archetype}]
                          </span>
                        )}

                        {isApproved && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                            <Check className="w-3 h-3" />
                            Approved
                          </span>
                        )}
                        {isRejected && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200">
                            <Ban className="w-3 h-3" />
                            Excluded
                          </span>
                        )}

                        {q.is_custom && (
                          <span className="text-[10px] font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            Custom Inquiry
                          </span>
                        )}
                      </div>

                      <p
                        className={`text-sm font-medium leading-snug ${
                          isRejected ? 'text-slate-500 line-through' : 'text-slate-900'
                        }`}
                      >
                        {q.question_text}
                      </p>

                      {q.hypothesis && (
                        <div className="text-xs text-slate-600 bg-blue-50/60 border border-blue-100/80 rounded px-2.5 py-1.5 flex items-start gap-1.5">
                          <span className="font-semibold text-blue-800 shrink-0">Working Hypothesis:</span>
                          <span>{q.hypothesis}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<Edit2 className="w-3.5 h-3.5 text-slate-600" />}
                        onClick={() => {
                          setEditingQuestion(q);
                          setEditQuestionText(q.question_text);
                          setEditHypothesis(q.hypothesis || '');
                          setQDialogError(null);
                          setEditQDialogOpen(true);
                        }}
                      >
                        Edit
                      </Button>

                      {isRejected ? (
                        <Button
                          size="sm"
                          variant="outline"
                          icon={<Check className="w-3.5 h-3.5 text-emerald-600" />}
                          loading={updateQuestionMutation.isPending}
                          onClick={() =>
                            updateQuestionMutation.mutate({
                              questionId: q.question_id || q.code,
                              data: { approval_status: 'APPROVED' },
                            })
                          }
                        >
                          Approve
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<X className="w-3.5 h-3.5 text-red-500" />}
                          loading={updateQuestionMutation.isPending}
                          onClick={() =>
                            updateQuestionMutation.mutate({
                              questionId: q.question_id || q.code,
                              data: { approval_status: 'REJECTED' },
                            })
                          }
                        >
                          Reject
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* DIALOG 1: Template Picker Dialog */}
      <Dialog
        open={templatePickerOpen}
        onClose={() => setTemplatePickerOpen(false)}
        title="Forensic Discovery Requirement Templates"
        description="Select a standard investigation template to pre-fill discovery goals, capability requirements, and expected outputs."
        size="lg"
      >
        <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
          {templates.map((tpl, idx) => (
            <div
              key={idx}
              onClick={() => handleSelectTemplate(tpl)}
              className="p-3 rounded-lg border border-stone-200 hover:border-blue-400 hover:bg-blue-50/30 cursor-pointer transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm text-slate-900">{tpl.title}</span>
                <span className="text-[10px] font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
                  {tpl.recommended_agent}
                </span>
              </div>
              <p className="text-xs text-slate-600">{tpl.description}</p>
              <div className="flex items-center gap-1.5 flex-wrap pt-1">
                <span className="text-[10px] uppercase font-bold text-slate-500">{tpl.category}</span>
                <span className="text-slate-300">•</span>
                {tpl.expected_outputs.map((outFmt, oIdx) => (
                  <span
                    key={oIdx}
                    className="bg-stone-100 text-slate-700 text-[10px] font-mono px-1.5 py-0.2 rounded"
                  >
                    {outFmt}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Dialog>

      {/* DIALOG 2: Add / Edit Investigation Requirement Dialog */}
      <Dialog
        open={reqDialogOpen}
        onClose={() => setReqDialogOpen(false)}
        title={editingReq ? `Edit Requirement ${editingReq.id}` : 'Add Investigation Requirement'}
        description="Define investigative inquiries, attach evidence, specify target outputs, and set scope boundaries."
        size="lg"
      >
        <form onSubmit={handleSaveRequirement} className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          {reqDialogError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {reqDialogError}
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Requirement Title"
              value={reqTitle}
              onChange={(e) => setReqTitle(e.target.value)}
              placeholder="e.g. Identify unauthorized remote logons"
              required
            />

            <Select
              label="Inquiry Category"
              value={reqCategory}
              onChange={(e) => setReqCategory(e.target.value)}
              options={CATEGORY_OPTIONS}
            />
          </div>

          <Textarea
            label="Requirement Description"
            value={reqDescription}
            onChange={(e) => setReqDescription(e.target.value)}
            placeholder="Detailed description of what the examiner seeks to uncover..."
            rows={2}
          />

          {/* Evidence Multi-select */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-700">Target Evidence</label>
            {evidenceItems.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No evidence registered in case yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 border border-stone-200 rounded p-2.5 bg-stone-50/50">
                {evidenceItems.map((ev) => {
                  const isChecked = reqSelectedEvidenceIds.includes(ev.id);
                  return (
                    <div
                      key={ev.id}
                      onClick={() => toggleEvidenceSelection(ev.id)}
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer border text-xs transition-colors ${
                        isChecked
                          ? 'bg-blue-50 border-blue-300 text-blue-900 font-medium'
                          : 'bg-white border-stone-200 text-slate-700 hover:bg-stone-50'
                      }`}
                    >
                      {isChecked ? (
                        <CheckSquare className="w-4 h-4 text-blue-600 shrink-0" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-400 shrink-0" />
                      )}
                      <div className="truncate">
                        <div className="truncate font-semibold">{ev.name}</div>
                        <div className="font-mono text-[10px] text-slate-400">{ev.evidence_type}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Expected Outputs Checkboxes */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-700">Expected Forensic Outputs</label>
            <div className="flex flex-wrap gap-2">
              {STANDARD_OUTPUT_FORMATS.map((fmt) => {
                const isSelected = reqExpectedOutputs.includes(fmt);
                return (
                  <button
                    type="button"
                    key={fmt}
                    onClick={() => toggleOutputFormat(fmt)}
                    className={`text-[11px] font-mono px-2 py-1 rounded border transition-colors ${
                      isSelected
                        ? 'bg-emerald-50 border-emerald-400 text-emerald-800 font-semibold'
                        : 'bg-white border-stone-200 text-slate-600 hover:bg-stone-50'
                    }`}
                  >
                    {fmt}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Scope Constraints */}
          <div className="pt-2 border-t border-stone-100 space-y-2">
            <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-slate-500" />
              Scope Boundaries & Filtering Constraints (Optional)
            </span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                label="Time Range Start (ISO / UTC)"
                value={reqTimeStart}
                onChange={(e) => setReqTimeStart(e.target.value)}
                placeholder="2026-01-01T00:00:00Z"
              />
              <Input
                label="Time Range End (ISO / UTC)"
                value={reqTimeEnd}
                onChange={(e) => setReqTimeEnd(e.target.value)}
                placeholder="2026-01-02T23:59:59Z"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Input
                label="Relevant Users (comma-sep)"
                value={reqUsers}
                onChange={(e) => setReqUsers(e.target.value)}
                placeholder="Administrator, jdoe"
              />
              <Input
                label="Relevant Hosts/IPs"
                value={reqHosts}
                onChange={(e) => setReqHosts(e.target.value)}
                placeholder="192.168.1.10, DC01"
              />
              <Input
                label="Relevant Processes"
                value={reqProcesses}
                onChange={(e) => setReqProcesses(e.target.value)}
                placeholder="powershell.exe, cmd.exe"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-stone-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setReqDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={addRequirementMutation.isPending || updateRequirementMutation.isPending}
            >
              {editingReq ? 'Save Requirement' : 'Add Requirement'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* DIALOG 3: Add Custom Question Dialog (Legacy / Complementary) */}
      <Dialog
        open={addQDialogOpen}
        onClose={() => setAddQDialogOpen(false)}
        title="Add Custom Forensic Inquiry"
        description="Introduce a targeted hypothesis to guide investigative analysis."
        size="md"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!newQuestionText.trim()) {
              setQDialogError('Question text is required.');
              return;
            }
            addQuestionMutation.mutate({
              question_text: newQuestionText.trim(),
              category: newQCategory.trim() || 'INVESTIGATOR_INQUIRY',
              hypothesis: newHypothesis.trim() || undefined,
            });
          }}
          className="space-y-4"
        >
          {qDialogError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {qDialogError}
            </p>
          )}

          <Input
            label="Inquiry Question"
            value={newQuestionText}
            onChange={(e) => setNewQuestionText(e.target.value)}
            placeholder="e.g. Did the user connect an unauthorized USB mass storage device?"
            required
          />

          <Input
            label="Inquiry Category"
            value={newQCategory}
            onChange={(e) => setNewQCategory(e.target.value)}
            placeholder="e.g. USB_ARTIFACTS, CREDENTIAL_ACCESS"
          />

          <Textarea
            label="Working Hypothesis (Optional)"
            value={newHypothesis}
            onChange={(e) => setNewHypothesis(e.target.value)}
            placeholder="e.g. External media was mounted during the incident window..."
            rows={2}
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setAddQDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={addQuestionMutation.isPending}
            >
              Add Inquiry
            </Button>
          </div>
        </form>
      </Dialog>

      {/* DIALOG 4: Edit Question Dialog */}
      <Dialog
        open={editQDialogOpen}
        onClose={() => setEditQDialogOpen(false)}
        title={`Edit Inquiry ${editingQuestion?.question_id || ''}`}
        description="Modify inquiry phrasing or update the forensic working hypothesis."
        size="md"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!editingQuestion) return;
            if (!editQuestionText.trim()) {
              setQDialogError('Question text cannot be empty.');
              return;
            }
            updateQuestionMutation.mutate({
              questionId: editingQuestion.question_id || editingQuestion.code,
              data: {
                question_text: editQuestionText.trim(),
                hypothesis: editHypothesis.trim(),
              },
            });
          }}
          className="space-y-4"
        >
          {qDialogError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {qDialogError}
            </p>
          )}

          <Input
            label="Inquiry Question"
            value={editQuestionText}
            onChange={(e) => setEditQuestionText(e.target.value)}
            required
          />

          <Textarea
            label="Working Hypothesis"
            value={editHypothesis}
            onChange={(e) => setEditHypothesis(e.target.value)}
            rows={3}
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditQDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={updateQuestionMutation.isPending}
            >
              Save Changes
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
};
