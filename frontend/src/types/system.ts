export interface SystemInfo {
  name: string
  version: string
  environment: string
}

export interface ServiceHealth {
  status: string
  latency_ms: number | null
  error: string | null
}

export interface HealthResponse {
  status: 'healthy' | 'degraded'
  timestamp: string
  services: Record<string, ServiceHealth>
}
