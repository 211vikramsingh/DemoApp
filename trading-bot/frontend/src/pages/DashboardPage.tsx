import React, { useCallback } from 'react'
import { StrategyDashboard } from '@/components/StrategyDashboard'
import { MultiLegBuilder } from '@/components/MultiLegBuilder'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAuthStore } from '@/stores/authStore'
import { useStrategyStore } from '@/stores/strategyStore'
import type { WSMessage } from '@/types'

export const DashboardPage: React.FC = () => {
  const user = useAuthStore((s) => s.user)
  const handleWsMessage = useStrategyStore((s) => s.handleWsMessage)

  // Wire WebSocket messages into the strategy store
  const onMessage = useCallback((msg: WSMessage) => {
    try {
      const inner = typeof msg.data === 'string' ? JSON.parse(msg.data) : msg.data
      handleWsMessage(msg.channel, inner)
    } catch {
      // ignore malformed messages
    }
  }, [handleWsMessage])

  useWebSocket(user?.id ?? null, onMessage)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
      <StrategyDashboard />
      <MultiLegBuilder />
    </div>
  )
}
