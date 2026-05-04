import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(username, password, totp || undefined)
      navigate('/')
    } catch {
      toast.error('Invalid credentials or TOTP code')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#0f0f1a' }}>
      <form onSubmit={handleSubmit} style={{
        background: '#1a1a2e', border: '1px solid #2d2d4a', borderRadius: 12,
        padding: 40, width: 360, display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        <h1 style={{ margin: 0, color: '#60a5fa', fontSize: 24 }}>📈 Trading Bot</h1>
        <p style={{ margin: 0, color: '#9ca3af', fontSize: 14 }}>Sign in to your account</p>

        {[
          { label: 'Username', value: username, setter: setUsername, type: 'text' },
          { label: 'Password', value: password, setter: setPassword, type: 'password' },
          { label: '2FA Code (optional)', value: totp, setter: setTotp, type: 'text' },
        ].map(({ label, value, setter, type }) => (
          <div key={label}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, color: '#d1d5db' }}>{label}</label>
            <input
              type={type}
              value={value}
              onChange={(e) => setter(e.target.value)}
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 6,
                border: '1px solid #374151', background: '#111', color: '#e5e7eb',
                fontSize: 15, boxSizing: 'border-box',
              }}
            />
          </div>
        ))}

        <button
          type="submit"
          disabled={loading}
          style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            borderRadius: 6, padding: '12px', fontWeight: 700, fontSize: 16,
            cursor: loading ? 'not-allowed' : 'pointer', marginTop: 8,
          }}
        >
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </div>
  )
}
