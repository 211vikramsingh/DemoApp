/**
 * MultiLegBuilder — visual builder for options spreads and combinations.
 * Renders a payoff diagram via Recharts.
 */
import React, { useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

type StrategyTemplate = 'bull_call_spread' | 'bear_put_spread' | 'iron_condor' | 'straddle' | 'strangle'

export const MultiLegBuilder: React.FC = () => {
  const [template, setTemplate] = useState<StrategyTemplate>('iron_condor')
  const [spot, setSpot] = useState(19_800)

  // Simplified payoff computation for display purposes
  const payoffData = React.useMemo(() => {
    const points = []
    for (let s = spot * 0.9; s <= spot * 1.1; s += spot * 0.005) {
      let pnl = 0
      if (template === 'iron_condor') {
        const shortPut = spot - 300, longPut = spot - 500
        const shortCall = spot + 300, longCall = spot + 500
        const credit = 140
        if (s < longPut) pnl = -(500 - 300) + credit
        else if (s < shortPut) pnl = -(shortPut - s) + credit
        else if (s <= shortCall) pnl = credit
        else if (s <= longCall) pnl = -(s - shortCall) + credit
        else pnl = -(500 - 300) + credit
      } else if (template === 'straddle') {
        const premium = 500
        pnl = Math.abs(s - spot) - premium
      } else if (template === 'bull_call_spread') {
        const longStrike = spot, shortStrike = spot + 300, debit = 120
        pnl = Math.min(Math.max(s - longStrike, 0), shortStrike - longStrike) - debit
      }
      points.push({ spot: Math.round(s), pnl: Math.round(pnl) })
    }
    return points
  }, [template, spot])

  return (
    <div>
      <h2>Multi-Leg Options Builder</h2>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        {(['bull_call_spread', 'bear_put_spread', 'iron_condor', 'straddle', 'strangle'] as StrategyTemplate[]).map((t) => (
          <button
            key={t}
            onClick={() => setTemplate(t)}
            style={{
              background: template === t ? '#3b82f6' : '#374151',
              color: '#fff', border: 'none', borderRadius: 4,
              padding: '6px 14px', cursor: 'pointer', fontSize: 13,
            }}
          >
            {t.replace(/_/g, ' ')}
          </button>
        ))}
        <label style={{ marginLeft: 'auto', fontSize: 13 }}>
          Spot:&nbsp;
          <input
            type="number"
            value={spot}
            onChange={(e) => setSpot(Number(e.target.value))}
            style={{ width: 90, padding: '4px 8px', borderRadius: 4, border: '1px solid #555', background: '#111', color: '#fff' }}
          />
        </label>
      </div>

      <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 20 }}>
        <h3 style={{ marginTop: 0 }}>Payoff at Expiry — {template.replace(/_/g, ' ')}</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={payoffData}>
            <defs>
              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d2d4a" />
            <XAxis dataKey="spot" stroke="#6b7280" tick={{ fontSize: 11 }} />
            <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: '#1a1a2e', border: '1px solid #374151', borderRadius: 6 }}
              formatter={(val: number) => [`₹${val}`, 'P&L']}
            />
            <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="4" />
            <ReferenceLine x={spot} stroke="#fbbf24" strokeDasharray="4" label={{ value: 'Spot', fill: '#fbbf24', fontSize: 12 }} />
            <Area type="monotone" dataKey="pnl" stroke="#3b82f6" fill="url(#pnlGrad)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
