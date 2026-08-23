import axios from 'axios';
import type {
  Investigation,
  Evidence,
  CustodyRecord,
  Finding,
  InvestigationPlan,
  CorrelatedGroup,
  VerificationResult,
  Report,
  SystemStatus
} from '../types';

const API_BASE = 'http://localhost:8000/api';

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  getHealth: async (): Promise<{ status: string; application: string; version: string }> => {
    const res = await client.get('/health');
    return res.data;
  },

  getSystemStatus: async (): Promise<SystemStatus> => {
    const res = await client.get<SystemStatus>('/system/status');
    return res.data;
  },

  getInvestigations: async (): Promise<Investigation[]> => {
    const res = await client.get<Investigation[]>('/investigations/');
    return res.data;
  },

  getInvestigation: async (id: string): Promise<Investigation> => {
    const res = await client.get<Investigation>(`/investigations/${id}`);
    return res.data;
  },

  createInvestigation: async (data: { name: string; description?: string }): Promise<Investigation> => {
    const res = await client.post<Investigation>('/investigations/', data);
    return res.data;
  },

  intakeEvidence: async (investigationId: string, path: string, notes?: string): Promise<Evidence> => {
    const res = await client.post<Evidence>(`/investigations/${investigationId}/evidence/intake`, { path, notes });
    return res.data;
  },

  getEvidence: async (investigationId: string): Promise<Evidence[]> => {
    const res = await client.get<Evidence[]>(`/investigations/${investigationId}/evidence`);
    return res.data;
  },

  getCustodyEvents: async (investigationId: string): Promise<CustodyRecord[]> => {
    const res = await client.get<CustodyRecord[]>(`/investigations/${investigationId}/custody`);
    return res.data;
  },

  planInvestigation: async (investigationId: string): Promise<InvestigationPlan> => {
    const res = await client.post<InvestigationPlan>(`/investigations/${investigationId}/plan`);
    return res.data;
  },

  getFindings: async (investigationId: string): Promise<Finding[]> => {
    const res = await client.get<Finding[]>(`/investigations/${investigationId}/findings`);
    return res.data;
  },

  addFinding: async (investigationId: string, data: Partial<Finding>): Promise<Finding> => {
    const res = await client.post<Finding>(`/investigations/${investigationId}/findings`, data);
    return res.data;
  },

  correlateFindings: async (investigationId: string): Promise<CorrelatedGroup[]> => {
    const res = await client.post<CorrelatedGroup[]>(`/investigations/${investigationId}/correlate`);
    return res.data;
  },

  verifyFindings: async (investigationId: string): Promise<VerificationResult[]> => {
    const res = await client.post<VerificationResult[]>(`/investigations/${investigationId}/verify`);
    return res.data;
  },

  generateReport: async (investigationId: string): Promise<Report> => {
    const res = await client.post<Report>(`/investigations/${investigationId}/report`);
    return res.data;
  },
};
