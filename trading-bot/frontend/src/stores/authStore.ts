import { create } from 'zustand'
import type { User } from '@/types'
import { authApi, usersApi } from '@/api'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (username: string, password: string, totp?: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isLoading: false,

  login: async (username, password, totp) => {
    set({ isLoading: true })
    const { data } = await authApi.login(username, password, totp)
    localStorage.setItem('access_token', data.access_token)
    set({ token: data.access_token, isLoading: false })
    const me = await usersApi.me()
    set({ user: me.data })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({ user: null, token: null })
  },

  fetchMe: async () => {
    try {
      const { data } = await usersApi.me()
      set({ user: data })
    } catch {
      set({ user: null, token: null })
      localStorage.removeItem('access_token')
    }
  },
}))
