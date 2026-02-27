import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type { User } from '@/types/models'

export async function listUsers() {
  return api.get<ApiResponse<User[]>>('/auth/users')
}

export async function updateUserRole(userId: string, role: string) {
  return api.put<ApiResponse<User>>(`/auth/users/${userId}/role`, { role })
}

export async function createUser(data: { email: string; password: string; full_name: string; role: string }) {
  return api.post<ApiResponse<User>>('/auth/users', data)
}

export async function updateUser(userId: string, data: { email?: string; password?: string; full_name?: string }) {
  return api.put<ApiResponse<User>>(`/auth/users/${userId}`, data)
}

export async function deactivateUser(userId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/auth/users/${userId}`)
}

export async function updateProfile(data: { full_name?: string; password?: string }) {
  return api.put<ApiResponse<User>>('/auth/me', data)
}

export async function getSystemStats() {
  return api.get<ApiResponse<{
    document_count: number
    storage_used: number
    user_count: number
    pending_approvals: number
  }>>('/system/stats')
}
