import { create } from 'zustand'
import type { Strategy } from '@/types'
import { strategiesApi } from '@/api'

interface StrategyState {
  strategies: Strategy[]
  isLoading: boolean
  fetch: () => Promise<void>
  toggle: (id: string, active: boolean) => Promise<void>
  remove: (id: string) => Promise<void>
}

export const useStrategyStore = create<StrategyState>((set, get) => ({
  strategies: [],
  isLoading: false,

  fetch: async () => {
    set({ isLoading: true })
    const { data } = await strategiesApi.list()
    set({ strategies: data, isLoading: false })
  },

  toggle: async (id, active) => {
    await strategiesApi.toggle(id, active)
    set((s) => ({
      strategies: s.strategies.map((st) =>
        st.id === id ? { ...st, is_active: active } : st
      ),
    }))
  },

  remove: async (id) => {
    await strategiesApi.delete(id)
    set((s) => ({ strategies: s.strategies.filter((st) => st.id !== id) }))
  },
}))
