# AgentHub Backend

## Requirements

- Python 3.11 or newer
- Docker Desktop is required for the infrastructure services in the repository root

## Local setup

From the `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Copy the repository root `.env.example` to `backend/.env` when local overrides are needed. The backend has safe development defaults for the API-only bootstrap.

## Start the API

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- System info: `http://127.0.0.1:8000/api/v1/system/info`
- Register: `POST http://127.0.0.1:8000/api/v1/auth/register`
- Login: `POST http://127.0.0.1:8000/api/v1/auth/login`
- Current user: `GET http://127.0.0.1:8000/api/v1/auth/me`
- Knowledge bases: `GET/POST http://127.0.0.1:8000/api/v1/knowledge-bases`
- Knowledge base detail: `GET/PATCH/DELETE http://127.0.0.1:8000/api/v1/knowledge-bases/{id}`
- Documents: `POST/GET http://127.0.0.1:8000/api/v1/knowledge-bases/{id}/documents`
- Document detail: `GET/DELETE http://127.0.0.1:8000/api/v1/knowledge-bases/{id}/documents/{document_id}`
- Process document: `POST http://127.0.0.1:8000/api/v1/knowledge-bases/{id}/documents/{document_id}/process`

Authentication uses Argon2 password hashes and JWT access tokens. Configure
`JWT_SECRET_KEY` through the local `.env` before non-development deployment.

The document slice accepts PDF, TXT, and Markdown uploads and stores original
objects in MinIO. F2-T1 provides page-aware Parser, Cleaner, and Chunker
contracts with TXT, Markdown, and PDF implementations. F2-T2 adds synchronous
ingestion, idempotent status transitions, failure persistence, and chunk-count
metadata. F2-T3 adds the EmbeddingProvider contract, an explicit local hash
baseline, and Qdrant upsert/search/delete adapters; retrieval orchestration
and semantic provider quality remain deferred. F2-T4 adds DenseRetriever,
token-budgeted ContextBuilder, and traceable Citation output. F2-T5 adds
Conversation/Message persistence, an OpenAI-compatible LLM adapter, and the
retrieval-grounded Chat API. F3-T1 adds a PostgreSQL `document_chunks` snapshot,
GIN-backed full-text search, and the `SparseRetriever` adapter sharing the
same result contract as dense retrieval. F3-T2 adds `HybridRetriever` and an
independent RRF fusion adapter with candidate sizing, score normalization, and
duplicate chunk handling. Conversation endpoints are under
`/api/v1/conversations`. F3-T3 adds a Cohere-compatible `BaseReranker` adapter
with timeout handling, configured Top-K, and explicit passthrough fallback.
Configure `LLM_API_KEY` and `RERANKER_API_KEY` before using real external
Providers. F3-T4 adds authenticated Retrieval Debug endpoints for dense,
sparse, hybrid, and rerank inspection, plus versioned request-scoped
Evaluation Dataset metrics for initial retrieval recall and citation correctness.
The v0.4 release gate has been verified. F4-T1 adds LangGraph Agent Runtime
state/contracts, AgentRun and
ToolCallRecord persistence, and bounded max-step, timeout, and cancellation
controls. F4-T2 adds the provider-neutral Tool Registry with input validation,
structured errors, timeouts, execution logging, and ToolCallRecord
persistence. F4-T3 adds `knowledge_search`, AST-safe `calculator`, whitelisted
read-only `sql_query`, and Provider-adapted `web_search`. F4-T4 adds Agent
configuration CRUD, non-streaming Agent runs, run history, and Tool Call
records. F5-T1 adds bounded short-term Conversation memory, F5-T2 adds
explicit long-term Memory, and F5-T3 adds the Approval Runtime.
The default two-level model setup uses `AGENT_ROUTER_MODEL=qwen-flash` for
tool selection and `LLM_MODEL=qwen-plus`/Agent model configuration for final
answers. `CHAT_HISTORY_MAX_MESSAGES`, `CHAT_CONTEXT_TOKEN_BUDGET`,
`AGENT_HISTORY_MAX_MESSAGES`, `AGENT_CONTEXT_TOKEN_BUDGET`, and
`AGENT_TOOL_RESULTS_MAX` bound repeated context tokens. F5-T1 adds a reusable
short-term memory policy that loads the newest contiguous history within those
limits. Chat persists its existing user/assistant turns, and Agent runs persist
user/assistant turns when a `conversation_id` is provided. This task reuses the
existing conversation/message schema and requires no new migration.

Long-term Memory is stored in `long_term_memories` after Migration `0010`. The
`/api/v1/memories/extract` endpoint only returns candidates for explicit
remember instructions; saving requires a separate user action. The Memory API
and UI support user-scoped search, edit, and delete operations. Ordinary chat
history is never copied into long-term Memory.

Approval Runtime state is stored in `agent_approvals` after Migration `0011`.
Tools opt into approval through `BaseTool.requires_approval`; approved runs
resume the pending tool call, while rejected or expired requests become failed
terminal runs. The current configured tools remain read-only.
The v0.6 release gate has passed with full backend/frontend, Docker health,
Migration, and sensitive-file verification.

F6-T1 adds optional Langfuse OTLP observability. Set `LANGFUSE_ENABLED=true`
and provide the Langfuse public/secret credentials through local environment
configuration to enable export. Events are fail-open and contain only trace
metadata, latency, model, token usage, and error fields; message bodies and
Tool arguments/results are not exported. No new migration is required.

F6-T2 extends the versioned Retrieval Evaluation Dataset with deterministic
Recall, Answer Relevance, Faithfulness, Citation Correctness, and dataset/result
fingerprints. Answer metrics use lexical proxy scoring without an LLM call, so
the same dataset and retrieval configuration produce repeatable results.
The v0.7 release gate has passed with complete trace-path, repeatability,
backend/frontend, Docker health, Migration, and sensitive-file verification.

For the containerized v1.0 deployment, the backend image runs `alembic upgrade
head` before Uvicorn. The production Compose runbook is in the repository
`docs/production.md`; do not copy development credentials into production.
The v1.0 demo seed is `scripts/seed_demo.py`; it creates only user-owned demo
configuration and never prints or persists the password.

## Run tests

```powershell
pytest
```

The current bootstrap tests cover OpenAPI, health routing, system information,
development CORS, database primitives, and infrastructure adapters. Integration
tests use the local Compose services; unit tests use test adapters where
appropriate.
