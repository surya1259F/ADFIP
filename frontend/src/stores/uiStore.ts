import { create } from 'zustand';

interface UIState {
  sidebarCollapsed: boolean;
  commandPaletteOpen: boolean;
  activeCaseId: string | null;
  theme: 'light' | 'dark';
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  setActiveCaseId: (id: string | null) => void;
  toggleTheme: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

const initialTheme: 'light' | 'dark' =
  typeof window !== 'undefined' && (localStorage.getItem('adfip_theme') as 'light' | 'dark') === 'dark'
    ? 'dark'
    : 'light';

if (typeof document !== 'undefined') {
  if (initialTheme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  commandPaletteOpen: false,
  activeCaseId: null,
  theme: initialTheme,

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  openCommandPalette: () => set({ commandPaletteOpen: true }),
  closeCommandPalette: () => set({ commandPaletteOpen: false }),
  setActiveCaseId: (id) => set({ activeCaseId: id }),

  toggleTheme: () =>
    set((s) => {
      const next: 'light' | 'dark' = s.theme === 'light' ? 'dark' : 'light';
      localStorage.setItem('adfip_theme', next);
      if (typeof document !== 'undefined') {
        if (next === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }
      return { theme: next };
    }),

  setTheme: (theme: 'light' | 'dark') => {
    localStorage.setItem('adfip_theme', theme);
    if (typeof document !== 'undefined') {
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
    set({ theme });
  },
}));
