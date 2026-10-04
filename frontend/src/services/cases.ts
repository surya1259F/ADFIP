import { apiClient } from './client';
import type { Case, CaseCreateRequest, ExecutionRecord } from '../types';

export const casesService = {
  list: async (): Promise<Case[]> => {
    const res = await apiClient.get<Case[]>('/cases');
    return res.data;
  },

  get: async (caseId: string): Promise<Case> => {
    const res = await apiClient.get<Case>(`/cases/${caseId}`);
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
};
