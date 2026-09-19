export interface KnowledgeBase {
  id: string
  user_id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeBasePayload {
  name: string
  description?: string | null
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBase[]
  total: number
  page: number
  page_size: number
}

export type DocumentStatus = 'uploaded' | 'processing' | 'completed' | 'failed'

export interface DocumentItem {
  id: string
  user_id: string
  knowledge_base_id: string
  filename: string
  content_type: string
  size_bytes: number
  storage_key: string
  status: DocumentStatus
  failure_reason: string | null
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  items: DocumentItem[]
  total: number
  page: number
  page_size: number
}
