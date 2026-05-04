import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { KillSwitch } from '@/components/KillSwitch'
import { useAuthStore } from '@/stores/authStore'

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: '#0f0f1a', color: '#e5e7eb' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', background: '#1a1a2e', borderBottom: '1px solid #2d2d4a',
      }}>
        <nav style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
          <Link to="/" style={{ color: '#60a5fa', fontWeight: 700, textDecoration: 'none', fontSize: 18 }}>
            📈 TradingBot
          </Link>
          <Link to="/strategies" style={{ color: '#e5e7eb', textDecoration: 'none' }}>Strategies</Link>
          <Link to="/portfolio" style={{ color: '#e5e7eb', textDecoration: 'none' }}>Portfolio</Link>
          <Link to="/options" style={{ color: '#e5e7eb', textDecoration: 'none' }}>Options</Link>
          {user?.role === 'admin' && (
            <Link to="/admin" style={{ color: '#fbbf24', textDecoration: 'none' }}>Admin</Link>
          )}
        </nav>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <KillSwitch compact />
          <span style={{ fontSize: 13, color: '#9ca3af' }}>{user?.username}</span>
          <button onClick={handleLogout} style={{ background: 'none', border: '1px solid #555', color: '#e5e7eb', borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>
            Logout
          </button>
        </div>
      </header>
      <main style={{ flex: 1, padding: 24 }}>{children}</main>
    </div>
  )
}
