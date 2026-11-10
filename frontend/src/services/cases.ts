import { apiClient } from './client';
import type {
  Case,
  CaseCreateRequest,
  ExecutionRecord,
  InvestigatorDecision,
  InvestigatorDecisionCreateRequest,
  InvestigativeQuestion,
  DashboardAnalyticsResponse,
  InvestigationRequirementsResponse,
  InvestigationRequirementItem,
  InvestigationScope,
} from '../types';

export const casesService = {
  getDashboardStats: async (): Promise<DashboardAnalyticsResponse> => {
    const res = await apiClient.get<DashboardAnalyticsResponse>('/cases/dashboard/stats');
    return res.data;
  },

  list: async (filter = 'all'): Promise<Case[]> => {
    const res = await apiClient.get<Case[]>('/cases', {
      params: filter === 'all' ? undefined : { filter },
    });
    return res.data;
  },

  get: async (caseId: string): Promise<Case> => {
    const res = await apiClient.get<Case>(`/cases/${caseId}`);
    return res.data;
  },

  getInvestigativeQuestions: async (caseId: string): Promise<{
    case_id: string;
    total_questions: number;
    questions: InvestigativeQuestion[];
  }> => {
    const res = await apiClient.get(`/cases/${caseId}/investigative-questions`);
    return res.data;
  },

  addInvestigativeQuestion: async (caseId: string, data: {
    question_text: string;
    category?: string;
    hypothesis?: string;
  }): Promise<unknown> => {
    const res = await apiClient.post(`/cases/${caseId}/investigative-questions`, data);
    return res.data;
  },

  updateInvestigativeQuestion: async (caseId: string, questionId: string, data: {
    question_text?: string;
    hypothesis?: string;
    approval_status?: 'APPROVED' | 'REJECTED' | 'PENDING';
  }): Promise<unknown> => {
    const res = await apiClient.patch(`/cases/${caseId}/investigative-questions/${questionId}`, data);
    return res.data;
  },

  bulkSaveInvestigativeQuestions: async (caseId: string, questions: InvestigativeQuestion[]): Promise<unknown> => {
    const res = await apiClient.put(`/cases/${caseId}/investigative-questions`, { questions });
    return res.data;
  },

  create: async (data: CaseCreateRequest): Promise<Case> => {
    const res = await apiClient.post<Case>('/cases', data);
    return res.data;
  },

  update: async (caseId: string, data: Partial<CaseCreateRequest>): Promise<Case> => {
    const res = await apiClient.patch<Case>(`/cases/${caseId}`, data);
    return res.data;
  },

  close: async (caseId: string): Promise<Case> => {
    const res = await apiClient.post<Case>(`/cases/${caseId}/close`);
    return res.data;
  },

  getExecutions: async (caseId: string): Promise<ExecutionRecord[]> => {
    const res = await apiClient.get<ExecutionRecord[]>(`/cases/${caseId}/executions`);
    return res.data;
  },

  executePlan: async (caseId: string): Promise<unknown> => {
    const res = await apiClient.post(`/cases/${caseId}/plan/execute`);
    return res.data;
  },

  getPlan: async (caseId: string): Promise<any> => {
    const res = await apiClient.get(`/cases/${caseId}/plan`);
    return res.data;
  },

  generatePlan: async (caseId: string): Promise<any> => {
    const res = await apiClient.post(`/cases/${caseId}/plan`);
    return res.data;
  },

  recordDecision: async (caseId: string, data: InvestigatorDecisionCreateRequest): Promise<InvestigatorDecision> => {
    const res = await apiClient.post<InvestigatorDecision>(`/cases/${caseId}/decisions`, data);
    return res.data;
  },

  getDecisions: async (caseId: string): Promise<InvestigatorDecision[]> => {
    const res = await apiClient.get<InvestigatorDecision[]>(`/cases/${caseId}/decisions`);
    return res.data;
  },

  getRequirements: async (caseId: string): Promise<InvestigationRequirementsResponse> => {
    const res = await apiClient.get<InvestigationRequirementsResponse>(`/cases/${caseId}/requirements`);
    return res.data;
  },

  saveRequirements: async (
    caseId: string,
    payload: {
      requirements: InvestigationRequirementItem[];
      objective?: string;
      global_scope?: InvestigationScope;
    }
  ): Promise<InvestigationRequirementsResponse> => {
    const res = await apiClient.put<InvestigationRequirementsResponse>(`/cases/${caseId}/requirements`, payload);
    return res.data;
  },

  addRequirement: async (
    caseId: string,
    data: {
      title: string;
      description?: string;
      category?: string;
      selected_evidence_ids?: string[];
      scope?: InvestigationScope;
      expected_outputs?: string[];
      approval_status?: 'APPROVED' | 'REJECTED' | 'PENDING';
    }
  ): Promise<InvestigationRequirementsResponse> => {
    const res = await apiClient.post<InvestigationRequirementsResponse>(`/cases/${caseId}/requirements`, data);
    return res.data;
  },

  updateRequirement: async (
    caseId: string,
    requirementId: string,
    data: {
      title?: string;
      description?: string;
      category?: string;
      selected_evidence_ids?: string[];
      scope?: InvestigationScope;
      expected_outputs?: string[];
      approval_status?: 'APPROVED' | 'REJECTED' | 'PENDING';
      status?: 'DRAFT' | 'SUBMITTED' | 'IN_PLANNING' | 'COMPLETED';
    }
  ): Promise<InvestigationRequirementsResponse> => {
    const res = await apiClient.patch<InvestigationRequirementsResponse>(
      `/cases/${caseId}/requirements/${requirementId}`,
      data
    );
    return res.data;
  },

  deleteRequirement: async (caseId: string, requirementId: string): Promise<InvestigationRequirementsResponse> => {
    const res = await apiClient.delete<InvestigationRequirementsResponse>(
      `/cases/${caseId}/requirements/${requirementId}`
    );
    return res.data;
  },

  generatePlanFromRequirements: async (caseId: string): Promise<any> => {
    const res = await apiClient.post(`/cases/${caseId}/requirements/generate-plan`);
    return res.data;
  },
};
