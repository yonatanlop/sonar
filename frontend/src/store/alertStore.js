import { create } from 'zustand'

export const useAlertStore = create((set) => ({
  unreadCount:  0,
  recentAlerts: [],
  inboxCount:   0,

  increment: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),

  addAlert: (alert) =>
    set((s) => ({
      unreadCount:  s.unreadCount + 1,
      recentAlerts: [alert, ...s.recentAlerts].slice(0, 5),
    })),

  incrementInbox: () => set((s) => ({ inboxCount: s.inboxCount + 1 })),

  resetCount:      () => set({ unreadCount: 0 }),
  setUnreadCount:  (n) => set({ unreadCount: n }),
  setInboxCount:   (n) => set({ inboxCount: n }),
}))
