import React from 'react'
import { StrategyDashboard } from '@/components/StrategyDashboard'
import { MultiLegBuilder } from '@/components/MultiLegBuilder'

export const DashboardPage: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 40 }}>
    <StrategyDashboard />
    <MultiLegBuilder />
  </div>
)
