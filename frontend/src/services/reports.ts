import { apiClient } from './client';
import type { ForensicReportResponse, ForensicReportVersionItem, ForensicReportGenerateRequest, ForensicReportIntegrityResponse } from '../types';

export const reportsService = {
  list: async (caseId: string): Promise<ForensicReportVersionItem[]> => {
    const res = await apiClient.get<ForensicReportVersionItem[]>(`/cases/${caseId}/reports`);
    return res.data;
  },

  get: async (caseId: string, reportId: string): Promise<ForensicReportResponse> => {
    const res = await apiClient.get<ForensicReportResponse>(`/cases/${caseId}/reports/${reportId}`);
    return res.data;
  },

  getLatest: async (caseId: string): Promise<ForensicReportResponse> => {
    const res = await apiClient.get<ForensicReportResponse>(`/cases/${caseId}/reports/latest`);
    return res.data;
  },

  generate: async (caseId: string, data?: ForensicReportGenerateRequest): Promise<ForensicReportResponse> => {
    const res = await apiClient.post<ForensicReportResponse>(`/cases/${caseId}/reports/generate`, data || {});
    return res.data;
  },

  verifyIntegrity: async (caseId: string, reportId: string): Promise<ForensicReportIntegrityResponse> => {
    const res = await apiClient.get<ForensicReportIntegrityResponse>(`/cases/${caseId}/reports/${reportId}/integrity`);
    return res.data;
  },

  export: async (caseId: string, reportId: string, format: 'markdown' | 'json' = 'markdown'): Promise<{ data: string; filename: string }> => {
    const res = await apiClient.get(`/cases/${caseId}/reports/${reportId}/export`, {
      params: { format },
      responseType: format === 'json' ? 'json' : 'text',
    });
    const disposition = String(res.headers['content-disposition'] || '');
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `report_${reportId}.${format === 'json' ? 'json' : 'md'}`;
    return { data: typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2), filename };
  },
};
