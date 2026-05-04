import api from './client'
import type { TokenResponse, User, Strategy, Signal, Trade, KillRequest, KillResponse } from '@/types'

export const authApi = {
  login: (username: string, password: string, totp_code?: string) =>
    api.post<TokenResponse>('/auth/login', { username, password, totp_code }),
  setupTotp: () => api.post<{ secret: string; uri: string }>('/auth/totp/setup'),
}

export const usersApi = {
  me: () => api.get<User>('/users/me'),
  list: () => api.get<User[]>('/users/'),
  create: (data: { username: string; email: string; password: string; role: string }) =>
    api.post<User>('/users/', data),
  deactivate: (id: string) => api.delete(`/users/${id}`),
}

export const strategiesApi = {
  list: () => api.get<Strategy[]>('/strategies/'),
  get: (id: string) => api.get<Strategy>(`/strategies/${id}`),
  create: (data: Omit<Strategy, 'id' | 'user_id' | 'is_active'>) =>
    api.post<Strategy>('/strategies/', data),
  toggle: (id: string, is_active: boolean) =>
    api.patch<Strategy>(`/strategies/${id}/toggle`, { is_active }),
  delete: (id: string) => api.delete(`/strategies/${id}`),
}

export const killApi = {
  execute: (data: KillRequest) => api.post<KillResponse>('/kill/', data),
}
