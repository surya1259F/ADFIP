import { apiClient } from './client';
import type { FindingItem } from '../types';

export const findingsService = {
  listByCase: async (caseId: string): Promise<FindingItem[]> => {
    const res = await apiClient.get<FindingItem[]>(`/cases/${caseId}/findings`);
    return res.data;
  },
};
