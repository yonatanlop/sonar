import { create } from 'zustand'

export const useAlertStore = create((set) => ({
  unreadCount:  0,
  recentAlerts: [],

  addAlert: (alert) =>
    set((s) => ({
      unreadCount:  s.unreadCount + 1,
      recentAlerts: [alert, ...s.recentAlerts].slice(0, 5),
    })),

  resetCount: () => set({ unreadCount: 0 }),
}))
