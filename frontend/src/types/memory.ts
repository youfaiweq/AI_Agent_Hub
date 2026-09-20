export type MemoryType = 'fact' | 'preference' | 'instruction' | 'metric'
export type MemorySource = 'explicit_user' | 'user_confirmed'

export interface LongTermMemory {
  id: string
  user_id: string
  content: string
  memory_type: MemoryType
  source: MemorySource
  confidence: number
  created_at: string
  updated_at: string
}

export interface MemoryListResponse {
  items: LongTermMemory[]
  total: number
  page: number
  page_size: number
}

export interface MemoryPayload {
  content: string
  memory_type: MemoryType
  source?: MemorySource
  confidence?: number
}

export interface MemoryCandidate {
  content: string
  memory_type: MemoryType
  source: MemorySource
  confidence: number
}

export interface MemoryExtractResponse {
  candidates: MemoryCandidate[]
  requires_confirmation: boolean
}
