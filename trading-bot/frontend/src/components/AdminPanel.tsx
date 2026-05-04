/**
 * AdminPanel — user management for admins.
 */
import React, { useEffect, useState } from 'react'
import { usersApi } from '@/api'
import type { User } from '@/types'
import toast from 'react-hot-toast'

export const AdminPanel: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])

  useEffect(() => {
    usersApi.list().then(r => setUsers(r.data)).catch(() => toast.error('Failed to load users'))
  }, [])

  const handleDeactivate = async (id: string, username: string) => {
    await usersApi.deactivate(id)
    setUsers(u => u.filter(x => x.id !== id))
    toast.success(`User ${username} deactivated`)
  }

  return (
    <div>
      <h2>Admin Panel — Users</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #333' }}>
            <th style={{ padding: 10, textAlign: 'left' }}>Username</th>
            <th>Email</th>
            <th>Role</th>
            <th>Active</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id} style={{ borderBottom: '1px solid #1a1a2e' }}>
              <td style={{ padding: 10 }}>{u.username}</td>
              <td>{u.email}</td>
              <td><span style={{ color: u.role === 'admin' ? '#fbbf24' : '#9ca3af' }}>{u.role}</span></td>
              <td style={{ color: u.is_active ? '#34d399' : '#f87171' }}>{u.is_active ? 'Yes' : 'No'}</td>
              <td>
                {u.is_active && (
                  <button
                    onClick={() => handleDeactivate(u.id, u.username)}
                    style={{ background: '#7f1d1d', color: '#fff', border: 'none', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}
                  >
                    Deactivate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
