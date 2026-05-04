/**
 * PortfolioDashboard
 * Shows P&L chart (Recharts) and per-strategy performance summary.
 */
import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'

interface PnLPoint { date: string; pnl: number; cumulative: number }

interface PortfolioDashboardProps {
  pnlData: PnLPoint[]
  totalPnl: number
  winRate: number
  maxDrawdown: number
}

export const PortfolioDashboard: React.FC<PortfolioDashboardProps> = ({
  pnlData, totalPnl, winRate, maxDrawdown,
}) => {
  const color = totalPnl >= 0 ? '#34d399' : '#f87171'

  return (
    <div>
      <h2>Portfolio</h2>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24 }}>
        {[
          { label: 'Total P&L', value: `₹${totalPnl.toLocaleString()}`, color },
          { label: 'Win Rate', value: `${(winRate * 100).toFixed(1)}%`, color: '#60a5fa' },
          { label: 'Max Drawdown', value: `${(maxDrawdown * 100).toFixed(1)}%`, color: '#f87171' },
        ].map((m) => (
          <div key={m.label} style={{
            background: '#1a1a2e', border: '1px solid #2d2d4a',
            borderRadius: 8, padding: '16px 24px', minWidth: 160,
          }}>
            <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 4 }}>{m.label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: m.color }}>{m.value}</div>
          </div>
        ))}
      </div>

      <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 20 }}>
        <h3 style={{ marginTop: 0 }}>Cumulative P&L</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={pnlData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d2d4a" />
            <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 12 }} />
            <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: '#1a1a2e', border: '1px solid #374151', borderRadius: 6 }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="4" />
            <Legend />
            <Line type="monotone" dataKey="cumulative" stroke="#60a5fa" dot={false} strokeWidth={2} name="Cumulative P&L" />
            <Line type="monotone" dataKey="pnl" stroke="#34d399" dot={false} strokeWidth={1.5} name="Daily P&L" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
