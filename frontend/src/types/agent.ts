export type AgentToolName = 'knowledge_search' | 'calculator' | 'sql_query' | 'web_search'

export interface Agent {
  id: string
  user_id: string
  knowledge_base_id: string | null
  name: string
  description: string | null
  system_prompt: string | null
  model_name: string
  max_steps: number
  timeout_seconds: number
  tool_names: AgentToolName[]
  created_at: string
  updated_at: string
}

export interface AgentCreatePayload {
  name: string
  description?: string | null
  system_prompt?: string | null
  knowledge_base_id?: string | null
  model_name?: string
  max_steps?: number
  timeout_seconds?: number
  tool_names: AgentToolName[]
}

export interface ToolCallRecord {
  id: string
  call_id: string
  tool_name: string
  status: string
  arguments: Record<string, unknown> | null
  result: unknown
  error_code: string | null
  error_message: string | null
  duration_ms: number | null
  created_at: string
  finished_at: string | null
}

export interface AgentRun {
  id: string
  agent_id: string
  conversation_id: string | null
  knowledge_base_id: string | null
  input_text: string
  status: string
  step_count: number
  max_steps: number
  timeout_seconds: number
  answer: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  tool_calls: ToolCallRecord[]
}

export interface AgentRunListResponse {
  items: AgentRun[]
}
