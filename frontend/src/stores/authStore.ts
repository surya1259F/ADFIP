import { create } from 'zustand';
import type { UserProfile } from '../types';
import { authService } from '../services/auth';
import { setUnauthorizedHandler } from '../services/client';

export type AuthStatus = 'RESTORING' | 'AUTHENTICATED' | 'UNAUTHENTICATED';

interface AuthState {
  status: AuthStatus;
  user: UserProfile | null;
  token: string | null;
  login: (token: string, user: UserProfile) => void;
  updateUser: (user: UserProfile) => void;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
  handleUnauthorized: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'RESTORING',
  user: null,
  token: null,

  login: (token: string, user: UserProfile) => {
    sessionStorage.setItem('adfip_token', token);
    set({ status: 'AUTHENTICATED', token, user });
  },

  updateUser: (user: UserProfile) => {
    set({ user });
  },

  logout: async () => {
    await authService.logout();
    set({ status: 'UNAUTHENTICATED', user: null, token: null });
  },

  restore: async () => {
    const token = sessionStorage.getItem('adfip_token');
    if (!token) {
      set({ status: 'UNAUTHENTICATED' });
      return;
    }
    try {
      const user = await authService.me();
      set({ status: 'AUTHENTICATED', user, token });
    } catch {
      sessionStorage.removeItem('adfip_token');
      set({ status: 'UNAUTHENTICATED', user: null, token: null });
    }
  },

  handleUnauthorized: () => {
    set({ status: 'UNAUTHENTICATED', user: null, token: null });
  },
}));

setUnauthorizedHandler(() => {
  useAuthStore.getState().handleUnauthorized();
});
