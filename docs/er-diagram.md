# AgentHub Data Model

```mermaid
erDiagram
    USERS ||--o{ KNOWLEDGE_BASES : owns
    USERS ||--o{ CONVERSATIONS : owns
    USERS ||--o{ AGENTS : configures
    USERS ||--o{ AGENT_RUNS : starts
    USERS ||--o{ LONG_TERM_MEMORIES : approves
    KNOWLEDGE_BASES ||--o{ DOCUMENTS : contains
    KNOWLEDGE_BASES ||--o{ CONVERSATIONS : scopes
    KNOWLEDGE_BASES ||--o{ DOCUMENT_CHUNKS : indexes
    CONVERSATIONS ||--o{ MESSAGES : contains
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : produces
    AGENTS ||--o{ AGENT_RUNS : executes
    AGENT_RUNS ||--o{ TOOL_CALL_RECORDS : audits
    AGENT_RUNS ||--o{ AGENT_APPROVALS : pauses

    USERS { uuid id PK }
    KNOWLEDGE_BASES { uuid id PK, uuid user_id FK }
    DOCUMENTS { uuid id PK, uuid knowledge_base_id FK, string status }
    DOCUMENT_CHUNKS { uuid id PK, uuid document_id FK, text content }
    CONVERSATIONS { uuid id PK, uuid user_id FK, uuid knowledge_base_id FK }
    MESSAGES { uuid id PK, uuid conversation_id FK, string role, text content }
    AGENTS { uuid id PK, uuid user_id FK, json tool_names }
    AGENT_RUNS { uuid id PK, uuid agent_id FK, string status, json state }
    TOOL_CALL_RECORDS { uuid id PK, uuid agent_run_id FK, string status }
    AGENT_APPROVALS { uuid id PK, uuid agent_run_id FK, string status, datetime expires_at }
    LONG_TERM_MEMORIES { uuid id PK, uuid user_id FK, string memory_type, float confidence }
```
