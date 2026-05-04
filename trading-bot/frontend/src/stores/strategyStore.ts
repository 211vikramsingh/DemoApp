import { create } from 'zustand'
import type { Strategy, Signal, Trade } from '@/types'
import { strategiesApi } from '@/api'

interface LiveUpdate {
  strategy_id: string
  instrument: string
  direction: 'long' | 'short'
  entry?: number
  quantity?: number
  rr_ratio?: number
}

interface StrategyState {
  strategies: Strategy[]
  isLoading: boolean
  pendingSignals: Record<string, LiveUpdate>   // strategy_id → latest pending signal
  recentTrades: Record<string, LiveUpdate>     // strategy_id → latest opened trade
  fetch: () => Promise<void>
  toggle: (id: string, active: boolean) => Promise<void>
  remove: (id: string) => Promise<void>
  // Called by WebSocket handler
  handleWsMessage: (channel: string, data: unknown) => void
}

export const useStrategyStore = create<StrategyState>((set, get) => ({
  strategies: [],
  isLoading: false,
  pendingSignals: {},
  recentTrades: {},

  fetch: async () => {
    set({ isLoading: true })
    try {
      const { data } = await strategiesApi.list()
      set({ strategies: data, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
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

  handleWsMessage: (channel: string, data: unknown) => {
    const payload = typeof data === 'string'
      ? (() => { try { return JSON.parse(data) } catch { return null } })()
      : data
    if (!payload) return

    if (channel === 'signal') {
      // A pending signal is waiting for user approval (semi-auto mode)
      const update = payload as LiveUpdate
      set((s) => ({
        pendingSignals: { ...s.pendingSignals, [update.strategy_id]: update },
      }))
    } else if (channel === 'trade_opened') {
      // A trade was auto-executed
      const update = payload as LiveUpdate
      set((s) => ({
        recentTrades: { ...s.recentTrades, [update.strategy_id]: update },
        // Clear pending signal for this strategy now that it executed
        pendingSignals: Object.fromEntries(
          Object.entries(s.pendingSignals).filter(([k]) => k !== update.strategy_id)
        ),
      }))
    }
  },
}))
