import React from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { Layout } from '@/components/Layout'

export const ProtectedRoute: React.FC = () => {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <Layout><Outlet /></Layout>
}
