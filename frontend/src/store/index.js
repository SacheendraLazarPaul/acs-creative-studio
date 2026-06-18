import { create } from 'zustand'
import { api } from '../api'

export const useStore = create((set, get) => ({
  status: null,
  statusError: false,
  config: null,
  toasts: [],
  comfyuiStatus: null,
  pendingRef: null,
  setPendingRef: (image, mode = 'i2i') => set({ pendingRef: { image, mode } }),
  clearPendingRef: () => set({ pendingRef: null }),

  toast: (message, kind = 'info') => {
    const id = Date.now() + Math.random()
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }))
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4000)
  },

  fetchStatus: async () => {
    try { set({ status: await api.status(), statusError: false }) }
    catch { set({ statusError: true }) }
  },

  fetchComfyUIStatus: async () => {
    try { set({ comfyuiStatus: await api.comfyuiStatus() }) }
    catch { set({ comfyuiStatus: { connected: false } }) }
  },

  _pollIds: [],
  startPolling: () => {
    const { _pollIds } = get()
    if (_pollIds.length > 0) return        // already running — don't stack
    get().fetchStatus()
    get().fetchComfyUIStatus()
    const ids = [
      setInterval(() => get().fetchStatus(), 5000),
      setInterval(() => get().fetchComfyUIStatus(), 8000),
    ]
    set({ _pollIds: ids })
  },

  loadConfig: async () => {
    try { set({ config: await api.getConfig() }) } catch {}
  },
}))
