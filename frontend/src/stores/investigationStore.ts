import { create } from 'zustand';
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
import { api } from '../services/api';

interface InvestigationState {
  investigations: Investigation[];
  activeInvestigation: Investigation | null;
  evidenceList: Evidence[];
  selectedEvidence: Evidence | null;
  custodyEvents: CustodyRecord[];
  findings: Finding[];
  currentPlan: InvestigationPlan | null;
  correlatedGroups: CorrelatedGroup[];
  verificationResults: VerificationResult[];
  activeReport: Report | null;
  systemStatus: SystemStatus | null;
  loading: boolean;
  error: string | null;

  fetchSystemStatus: () => Promise<void>;
  fetchInvestigations: () => Promise<void>;
  setActiveInvestigation: (inv: Investigation) => Promise<void>;
  createInvestigation: (name: string, description?: string) => Promise<Investigation>;
  intakeEvidence: (path: string, notes?: string) => Promise<Evidence>;
  fetchEvidence: (invId: string) => Promise<void>;
  fetchCustody: (invId: string) => Promise<void>;
  setSelectedEvidence: (ev: Evidence | null) => void;
  generatePlan: (invId: string) => Promise<void>;
  fetchFindings: (invId: string) => Promise<void>;
  correlateAndVerify: (invId: string) => Promise<void>;
  generateReport: (invId: string) => Promise<void>;
}

export const useInvestigationStore = create<InvestigationState>((set, get) => ({
  investigations: [],
  activeInvestigation: null,
  evidenceList: [],
  selectedEvidence: null,
  custodyEvents: [],
  findings: [],
  currentPlan: null,
  correlatedGroups: [],
  verificationResults: [],
  activeReport: null,
  systemStatus: null,
  loading: false,
  error: null,

  fetchSystemStatus: async () => {
    try {
      const status = await api.getSystemStatus();
      set({ systemStatus: status });
    } catch (e: any) {
      console.warn('Backend offline or initializing:', e.message);
    }
  },

  fetchInvestigations: async () => {
    set({ loading: true, error: null });
    try {
      const list = await api.getInvestigations();
      set({ investigations: list, loading: false });
      if (list.length > 0 && !get().activeInvestigation) {
        await get().setActiveInvestigation(list[0]);
      }
    } catch (e: any) {
      set({ error: e.message || 'Failed to fetch investigations', loading: false });
    }
  },

  setActiveInvestigation: async (inv: Investigation) => {
    set({ activeInvestigation: inv, loading: true, selectedEvidence: null });
    try {
      await Promise.all([
        get().fetchEvidence(inv.id),
        get().fetchCustody(inv.id),
        get().fetchFindings(inv.id),
      ]);
    } finally {
      set({ loading: false });
    }
  },

  createInvestigation: async (name: string, description?: string) => {
    set({ loading: true, error: null });
    try {
      const newInv = await api.createInvestigation({ name, description });
      set((state) => ({
        investigations: [newInv, ...state.investigations],
        activeInvestigation: newInv,
        loading: false
      }));
      return newInv;
    } catch (e: any) {
      set({ error: e.message || 'Failed to create investigation', loading: false });
      throw e;
    }
  },

  intakeEvidence: async (path: string, notes?: string) => {
    const active = get().activeInvestigation;
    if (!active) throw new Error("No active investigation");
    set({ loading: true, error: null });
    try {
      const ev = await api.intakeEvidence(active.id, path, notes);
      set((state) => ({ evidenceList: [ev, ...state.evidenceList], loading: false }));
      await get().fetchCustody(active.id);
      return ev;
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Evidence intake failed';
      set({ error: msg, loading: false });
      throw new Error(msg);
    }
  },

  fetchEvidence: async (invId: string) => {
    try {
      const list = await api.getEvidence(invId);
      set({ evidenceList: list });
    } catch (e: any) {
      console.error('Error fetching evidence:', e);
    }
  },

  fetchCustody: async (invId: string) => {
    try {
      const list = await api.getCustodyEvents(invId);
      set({ custodyEvents: list });
    } catch (e: any) {
      console.error('Error fetching custody events:', e);
    }
  },

  setSelectedEvidence: (ev: Evidence | null) => {
    set({ selectedEvidence: ev });
  },

  generatePlan: async (invId: string) => {
    set({ loading: true, error: null });
    try {
      const plan = await api.planInvestigation(invId);
      set({ currentPlan: plan, loading: false });
    } catch (e: any) {
      set({ error: e.message || 'Failed to plan investigation', loading: false });
    }
  },

  fetchFindings: async (invId: string) => {
    try {
      const list = await api.getFindings(invId);
      set({ findings: list });
    } catch (e: any) {
      console.error('Error fetching findings:', e);
    }
  },

  correlateAndVerify: async (invId: string) => {
    set({ loading: true, error: null });
    try {
      const [corr, ver] = await Promise.all([
        api.correlateFindings(invId),
        api.verifyFindings(invId),
      ]);
      set({ correlatedGroups: corr, verificationResults: ver, loading: false });
      await get().fetchFindings(invId);
    } catch (e: any) {
      set({ error: e.message || 'Correlation and verification failed', loading: false });
    }
  },

  generateReport: async (invId: string) => {
    set({ loading: true, error: null });
    try {
      const rep = await api.generateReport(invId);
      set({ activeReport: rep, loading: false });
    } catch (e: any) {
      set({ error: e.message || 'Report generation failed', loading: false });
    }
  },
}));
