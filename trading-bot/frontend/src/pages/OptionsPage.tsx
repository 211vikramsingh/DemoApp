import React from 'react'
import { OptionsChainPanel } from '@/components/OptionsChainPanel'

// Placeholder data — in production fetched from Kite API
const SPOT = 19_800
const STRIKES = [19_500, 19_600, 19_700, 19_800, 19_900, 20_000, 20_100]
const MOCK_ROWS = STRIKES.map((s) => ({
  strike: s,
  call_oi: Math.round(Math.random() * 100_000),
  put_oi: Math.round(Math.random() * 100_000),
  call_greeks: { delta: Math.random() * 0.5, gamma: 0.001, theta: -5, vega: 2, rho: 0.1, iv: 0.2, intrinsic_value: Math.max(SPOT - s, 0), time_value: 50 },
  put_greeks: { delta: -(Math.random() * 0.5), gamma: 0.001, theta: -5, vega: 2, rho: -0.1, iv: 0.2, intrinsic_value: Math.max(s - SPOT, 0), time_value: 50 },
}))

export const OptionsPage: React.FC = () => (
  <OptionsChainPanel rows={MOCK_ROWS} maxPainStrike={19_700} spotPrice={SPOT} />
)
