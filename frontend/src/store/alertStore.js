import { create } from 'zustand'

export const useAlertStore = create((set, get) => ({
  unreadCount: 0,
  recentAlerts: [],

  increment: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),

  addAlert: (alert) =>
    set((s) => ({
      unreadCount: s.unreadCount + 1,
      recentAlerts: [alert, ...s.recentAlerts].slice(0, 5),
    })),

  resetCount: () => set({ unreadCount: 0 }),

  setUnreadCount: (n) => set({ unreadCount: n }),
}))
