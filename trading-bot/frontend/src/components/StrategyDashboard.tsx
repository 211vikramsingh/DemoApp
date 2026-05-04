/**
 * StrategyDashboard — lists strategies with activate/deactivate toggle.
 */
import React, { useEffect } from 'react'
import { useStrategyStore } from '@/stores/strategyStore'
import type { Strategy } from '@/types'
import toast from 'react-hot-toast'

export const StrategyDashboard: React.FC = () => {
  const { strategies, isLoading, fetch, toggle, remove } = useStrategyStore()

  useEffect(() => { void fetch() }, [fetch])

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
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => (
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
          ))}
        </tbody>
      </table>
    </div>
  )
}
