import React from 'react'
import { PortfolioDashboard } from '@/components/PortfolioDashboard'

// Placeholder P&L data — in production fetched from /api/trades
const MOCK_PNL = Array.from({ length: 30 }, (_, i) => ({
  date: `2024-${String(i + 1).padStart(2, '0')}`,
  pnl: Math.round((Math.random() - 0.4) * 5000),
  cumulative: 0,
})).map((d, i, arr) => ({
  ...d,
  cumulative: arr.slice(0, i + 1).reduce((s, x) => s + x.pnl, 0),
}))

export const PortfolioPage: React.FC = () => (
  <PortfolioDashboard
    pnlData={MOCK_PNL}
    totalPnl={MOCK_PNL[MOCK_PNL.length - 1].cumulative}
    winRate={0.62}
    maxDrawdown={0.07}
  />
)
