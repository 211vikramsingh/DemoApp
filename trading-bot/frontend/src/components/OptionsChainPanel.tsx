/**
 * OptionsChainPanel
 * Displays options chain with Black-Scholes Greeks.
 * Max Pain strike is highlighted in amber.
 */
import React from 'react'
import type { Greeks } from '@/types'

interface OptionRow {
  strike: number
  call_oi: number
  put_oi: number
  call_greeks?: Greeks
  put_greeks?: Greeks
}

interface OptionsChainPanelProps {
  rows: OptionRow[]
  maxPainStrike: number
  spotPrice: number
}

export const OptionsChainPanel: React.FC<OptionsChainPanelProps> = ({ rows, maxPainStrike, spotPrice }) => {
  return (
    <div>
      <h3>Options Chain — Spot: {spotPrice.toLocaleString()}</h3>
      <p style={{ color: '#fbbf24', fontSize: 13 }}>★ Max Pain: {maxPainStrike}</p>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #333' }}>
            <th style={{ padding: 8 }}>CALL OI</th>
            <th>CALL Δ</th>
            <th>CALL θ</th>
            <th style={{ padding: '8px 16px', background: '#1e3a5f' }}>STRIKE</th>
            <th>PUT θ</th>
            <th>PUT Δ</th>
            <th>PUT OI</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isMaxPain = row.strike === maxPainStrike
            const isATM = Math.abs(row.strike - spotPrice) === Math.min(...rows.map(r => Math.abs(r.strike - spotPrice)))
            return (
              <tr
                key={row.strike}
                style={{
                  borderBottom: '1px solid #1a1a2e',
                  background: isMaxPain ? '#451a03' : isATM ? '#1e3a5f' : undefined,
                }}
              >
                <td style={{ padding: 8, textAlign: 'right' }}>{row.call_oi.toLocaleString()}</td>
                <td style={{ textAlign: 'right', color: '#60a5fa' }}>
                  {row.call_greeks?.delta?.toFixed(3) ?? '-'}
                </td>
                <td style={{ textAlign: 'right', color: '#f87171' }}>
                  {row.call_greeks?.theta?.toFixed(2) ?? '-'}
                </td>
                <td style={{ padding: '8px 16px', textAlign: 'center', fontWeight: 700, color: isMaxPain ? '#fbbf24' : '#e5e7eb' }}>
                  {row.strike.toLocaleString()}
                  {isMaxPain && ' ★'}
                </td>
                <td style={{ textAlign: 'right', color: '#f87171' }}>
                  {row.put_greeks?.theta?.toFixed(2) ?? '-'}
                </td>
                <td style={{ textAlign: 'right', color: '#60a5fa' }}>
                  {row.put_greeks?.delta?.toFixed(3) ?? '-'}
                </td>
                <td style={{ padding: 8, textAlign: 'left' }}>{row.put_oi.toLocaleString()}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
