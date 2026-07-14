import { create } from 'zustand';

interface UIState {
  sidebarCollapsed: boolean;
  rightDrawerOpen: boolean;
  selectedSatelliteId: string | null;
  selectedCollisionId: string | null;
  activeSector: string;
  globalSearchOpen: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleRightDrawer: () => void;
  setRightDrawerOpen: (open: boolean) => void;
  setSelectedSatelliteId: (id: string | null) => void;
  setSelectedCollisionId: (id: string | null) => void;
  setActiveSector: (sector: string) => void;
  setGlobalSearchOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  rightDrawerOpen: false,
  selectedSatelliteId: null,   
  selectedCollisionId: null,   
  activeSector: '',
  globalSearchOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleRightDrawer: () => set((state) => ({ rightDrawerOpen: !state.rightDrawerOpen })),
  setRightDrawerOpen: (open) => set({ rightDrawerOpen: open }),
  setSelectedSatelliteId: (id) => set({ selectedSatelliteId: id }),
  setSelectedCollisionId: (id) => set({ selectedCollisionId: id }),
  setActiveSector: (sector) => set({ activeSector: sector }),
  setGlobalSearchOpen: (open) => set({ globalSearchOpen: open }),
}));
