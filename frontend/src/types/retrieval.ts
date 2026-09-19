export type RetrievalMode = 'dense' | 'sparse' | 'hybrid' | 'rerank'

export interface RetrievalDebugRequest {
  query: string
  mode: RetrievalMode
  top_k: number
  candidate_k: number
}

export interface RetrievalDebugItem {
  chunk_id: string
  document_id: string
  filename: string
  page_number: number
  snippet: string
  dense_score: number | null
  sparse_score: number | null
  fusion_score: number | null
  rerank_score: number | null
  final_rank: number
}

export interface RetrievalDebugResponse {
  query: string
  mode: RetrievalMode
  candidate_k: number
  items: RetrievalDebugItem[]
}
