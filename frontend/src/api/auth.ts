import http from './http'
import type { AuthUser, LoginPayload, RegisterPayload, RegisterResponse, TokenResponse } from '@/types/auth'

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const { data } = await http.post<TokenResponse>('/api/v1/auth/login', payload)
  return data
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  const { data } = await http.post<RegisterResponse>('/api/v1/auth/register', payload)
  return data
}

export async function getCurrentUser(): Promise<AuthUser> {
  const { data } = await http.get<AuthUser>('/api/v1/auth/me')
  return data
}
