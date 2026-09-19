import http from './http'
import type {
  DocumentItem,
  DocumentListResponse,
  KnowledgeBase,
  KnowledgeBaseListResponse,
  KnowledgeBasePayload,
} from '@/types/knowledge'

export async function listKnowledgeBases(): Promise<KnowledgeBaseListResponse> {
  const { data } = await http.get<KnowledgeBaseListResponse>('/api/v1/knowledge-bases')
  return data
}

export async function createKnowledgeBase(payload: KnowledgeBasePayload): Promise<KnowledgeBase> {
  const { data } = await http.post<KnowledgeBase>('/api/v1/knowledge-bases', payload)
  return data
}

export async function getKnowledgeBase(id: string): Promise<KnowledgeBase> {
  const { data } = await http.get<KnowledgeBase>(`/api/v1/knowledge-bases/${id}`)
  return data
}

export async function updateKnowledgeBase(
  id: string,
  payload: Partial<KnowledgeBasePayload>,
): Promise<KnowledgeBase> {
  const { data } = await http.patch<KnowledgeBase>(`/api/v1/knowledge-bases/${id}`, payload)
  return data
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  await http.delete(`/api/v1/knowledge-bases/${id}`)
}

export async function listDocuments(id: string): Promise<DocumentListResponse> {
  const { data } = await http.get<DocumentListResponse>(
    `/api/v1/knowledge-bases/${id}/documents`,
  )
  return data
}

export async function uploadDocument(id: string, file: File): Promise<DocumentItem> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post<DocumentItem>(
    `/api/v1/knowledge-bases/${id}/documents`,
    formData,
  )
  return data
}

export async function deleteDocument(knowledgeBaseId: string, documentId: string): Promise<void> {
  await http.delete(`/api/v1/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`)
}
