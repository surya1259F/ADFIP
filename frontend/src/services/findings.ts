import { apiClient } from './client';
import type {
  FindingItem,
  ForensicAssessment,
  InvestigatorAssessmentDecisionRequest,
} from '../types';

export const findingsService = {
  listByCase: async (caseId: string): Promise<FindingItem[]> => {
    const res = await apiClient.get<FindingItem[]>(`/cases/${caseId}/findings`);
    return res.data;
  },

  getAssessment: async (caseId: string): Promise<ForensicAssessment> => {
    const res = await apiClient.get<ForensicAssessment>(
      `/cases/${caseId}/findings/assessment`
    );
    return res.data;
  },

  submitAssessmentDecision: async (
    caseId: string,
    payload: InvestigatorAssessmentDecisionRequest
  ): Promise<ForensicAssessment> => {
    const res = await apiClient.post<ForensicAssessment>(
      `/cases/${caseId}/findings/assessment/decision`,
      payload
    );
    return res.data;
  },
};
