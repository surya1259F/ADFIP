import { apiClient } from './client';
import type { Evidence, CustodyEvent, EvidenceIntelligence } from '../types';

export interface EvidenceIntakePayload {
  name: string;
  evidence_type?: string;
  source_path?: string;
  file_path?: string;
  notes?: string;
  case_id?: string;
  file?: File;
  metadata?: Record<string, unknown>;
}

export const evidenceService = {
  listByCase: async (caseId: string): Promise<Evidence[]> => {
    const res = await apiClient.get<Evidence[]>(`/evidence/case/${caseId}`);
    return res.data;
  },

  get: async (evidenceId: string): Promise<Evidence> => {
    const res = await apiClient.get<Evidence>(`/evidence/${evidenceId}`);
    return res.data;
  },

  intake: async (caseId: string, payload: EvidenceIntakePayload): Promise<Evidence> => {
    if (payload.file) {
      const formData = new FormData();
      formData.append('file', payload.file, payload.name || payload.file.name);
      formData.append('case_id', caseId);
      if (payload.name) formData.append('name', payload.name);
      if (payload.evidence_type) formData.append('evidence_type', payload.evidence_type);
      if (payload.notes) formData.append('notes', payload.notes);
      const targetPath = payload.file_path || payload.source_path;
      if (targetPath) formData.append('source_path', targetPath);

      const res = await apiClient.post<Evidence>(`/cases/${caseId}/evidence/intake`, formData, {
        headers: {
          'Content-Type': undefined,
        },
      });
      return res.data;
    }

    const targetPath = payload.file_path || payload.source_path || payload.name;
    const res = await apiClient.post<Evidence>(`/cases/${caseId}/evidence/intake`, {
      case_id: caseId,
      file_path: targetPath,
      path: targetPath,
      evidence_type: payload.evidence_type,
      notes: payload.notes,
      name: payload.name,
    });
    return res.data;
  },

  verify: async (evidenceId: string): Promise<unknown> => {
    const res = await apiClient.post(`/evidence/${evidenceId}/verify`);
    return res.data;
  },

  getCustody: async (evidenceId: string): Promise<CustodyEvent[]> => {
    const res = await apiClient.get<CustodyEvent[]>(`/evidence/${evidenceId}/custody`);
    return res.data;
  },

  getIntelligence: async (evidenceId: string): Promise<EvidenceIntelligence> => {
    const res = await apiClient.get<EvidenceIntelligence>(`/evidence/${evidenceId}/intelligence`);
    return res.data;
  },

  extractIntelligence: async (evidenceId: string): Promise<EvidenceIntelligence> => {
    const res = await apiClient.post<EvidenceIntelligence>(`/evidence/${evidenceId}/intelligence`);
    return res.data;
  },
};
