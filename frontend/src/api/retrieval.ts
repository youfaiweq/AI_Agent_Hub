import http from './http'
import type { RetrievalDebugRequest, RetrievalDebugResponse } from '@/types/retrieval'

export async function debugRetrieval(
  knowledgeBaseId: string,
  payload: RetrievalDebugRequest,
): Promise<RetrievalDebugResponse> {
  const { data } = await http.post<RetrievalDebugResponse>(
    `/api/v1/knowledge-bases/${knowledgeBaseId}/retrieval/debug`,
    payload,
  )
  return data
}
