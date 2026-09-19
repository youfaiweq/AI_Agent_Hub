import http from './http'
import type {
  Agent,
  AgentCreatePayload,
  AgentRun,
  AgentRunListResponse,
} from '@/types/agent'

export async function listAgents(): Promise<Agent[]> {
  const { data } = await http.get<Agent[]>('/api/v1/agents')
  return data
}

export async function getAgent(id: string): Promise<Agent> {
  const { data } = await http.get<Agent>(`/api/v1/agents/${id}`)
  return data
}

export async function createAgent(payload: AgentCreatePayload): Promise<Agent> {
  const { data } = await http.post<Agent>('/api/v1/agents', payload)
  return data
}

export async function deleteAgent(id: string): Promise<void> {
  await http.delete(`/api/v1/agents/${id}`)
}

export async function runAgent(
  id: string,
  message: string,
): Promise<AgentRun> {
  const { data } = await http.post<AgentRun>(`/api/v1/agents/${id}/runs`, { message })
  return data
}

export async function listAgentRuns(id: string): Promise<AgentRunListResponse> {
  const { data } = await http.get<AgentRunListResponse>(`/api/v1/agents/${id}/runs`)
  return data
}
