import http from './http'
import type {
  LongTermMemory,
  MemoryExtractResponse,
  MemoryListResponse,
  MemoryPayload,
} from '@/types/memory'

export async function listMemories(query?: string): Promise<MemoryListResponse> {
  const { data } = await http.get<MemoryListResponse>('/api/v1/memories', {
    params: query ? { query } : undefined,
  })
  return data
}

export async function extractMemories(text: string): Promise<MemoryExtractResponse> {
  const { data } = await http.post<MemoryExtractResponse>('/api/v1/memories/extract', { text })
  return data
}

export async function createMemory(payload: MemoryPayload): Promise<LongTermMemory> {
  const { data } = await http.post<LongTermMemory>('/api/v1/memories', payload)
  return data
}

export async function updateMemory(
  id: string,
  payload: Partial<MemoryPayload>,
): Promise<LongTermMemory> {
  const { data } = await http.patch<LongTermMemory>(`/api/v1/memories/${id}`, payload)
  return data
}

export async function deleteMemory(id: string): Promise<void> {
  await http.delete(`/api/v1/memories/${id}`)
}
