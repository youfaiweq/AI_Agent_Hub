import http from './http'
import type { HealthResponse, SystemInfo } from '@/types/system'

export async function getSystemInfo(): Promise<SystemInfo> {
  const { data } = await http.get<SystemInfo>('/api/v1/system/info')
  return data
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}
