/**
 * StrategyDashboard — lists strategies with activate/deactivate toggle.
 * Shows live signal alerts and trade notifications from the WebSocket.
 */
import React, { useEffect } from 'react'
import { useStrategyStore } from '@/stores/strategyStore'
import type { Strategy } from '@/types'
import toast from 'react-hot-toast'

export const StrategyDashboard: React.FC = () => {
  const { strategies, isLoading, fetch, toggle, remove, pendingSignals, recentTrades } =
    useStrategyStore()

  useEffect(() => { void fetch() }, [fetch])

  // Toast notifications when new signals / trades arrive via WebSocket
  useEffect(() => {
    const keys = Object.keys(pendingSignals)
    if (keys.length === 0) return
    keys.forEach((sid) => {
      const sig = pendingSignals[sid]
      toast(
        `⚠️ Signal: ${sig.instrument} ${sig.direction?.toUpperCase()} — R:R ${sig.rr_ratio?.toFixed(1)}`,
        { duration: 6000 }
      )
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(pendingSignals)])

  useEffect(() => {
    const keys = Object.keys(recentTrades)
    if (keys.length === 0) return
    keys.forEach((sid) => {
      const t = recentTrades[sid]
      toast.success(
        `✅ Trade: ${t.instrument} ${t.direction?.toUpperCase()} ×${t.quantity} @ ${t.entry?.toFixed(2)}`,
        { duration: 5000 }
      )
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(recentTrades)])

  const handleToggle = async (s: Strategy) => {
    await toggle(s.id, !s.is_active)
    toast.success(`Strategy ${s.name} ${!s.is_active ? 'activated' : 'deactivated'}`)
  }

  if (isLoading) return <p>Loading strategies…</p>

  return (
    <div>
      <h2>Strategies</h2>
      {strategies.length === 0 && <p>No strategies yet. Create one to get started.</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #333', textAlign: 'left' }}>
            <th style={{ padding: 10 }}>Name</th>
            <th>Mode</th>
            <th>Wallet</th>
            <th>Sizing</th>
            <th>Status</th>
            <th>Live Signal</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => {
            const signal = pendingSignals[s.id]
            const trade = recentTrades[s.id]
            return (
              <tr key={s.id} style={{ borderBottom: '1px solid #222' }}>
                <td style={{ padding: 10 }}>{s.name}</td>
                <td>{s.automation_mode}</td>
                <td>{s.wallet_type}</td>
                <td>{s.position_sizing_method}</td>
                <td>
                  <span style={{ color: s.is_active ? '#34d399' : '#9ca3af' }}>
                    {s.is_active ? '● Active' : '○ Inactive'}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: '#fbbf24' }}>
                  {signal && (
                    <span title="Pending approval">
                      ⚠️ {signal.instrument} {signal.direction?.toUpperCase()} R:R {signal.rr_ratio?.toFixed(1)}
                    </span>
                  )}
                  {trade && !signal && (
                    <span style={{ color: '#34d399' }} title="Last executed trade">
                      ✅ {trade.instrument} {trade.direction?.toUpperCase()} ×{trade.quantity}
                    </span>
                  )}
                </td>
                <td style={{ display: 'flex', gap: 8, padding: 10 }}>
                  <button
                    onClick={() => handleToggle(s)}
                    style={{
                      background: s.is_active ? '#7f1d1d' : '#065f46',
                      color: '#fff', border: 'none', borderRadius: 4,
                      padding: '4px 12px', cursor: 'pointer',
                    }}
                  >
                    {s.is_active ? 'Stop' : 'Start'}
                  </button>
                  <button
                    onClick={() => remove(s.id)}
                    style={{ background: '#374151', color: '#fff', border: 'none', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
