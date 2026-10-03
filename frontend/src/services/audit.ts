import { apiClient } from './client';
import type { AuditEvent } from '../types';

export const auditService = {
  listByCase: async (caseId: string): Promise<AuditEvent[]> => {
    const res = await apiClient.get<AuditEvent[]>(`/cases/${caseId}/audit`);
    return res.data;
  },
};
