# AgentHub

AgentHub is an enterprise AI knowledge and task-agent platform. The current
slice covers authentication, user-owned knowledge bases, document ingestion,
dense retrieval, sparse retrieval, RRF-based hybrid retrieval, and
citation-grounded chat. Reranking is available through a configured external
Provider, the Agent Runtime, Tool Registry, initial read-only tools, and the
first non-streaming Agent API/UI, bounded short-term Conversation memory,
explicit long-term Memory, and the Approval Runtime are now in place. The v0.6
release gate has passed; the Observability Adapter and deterministic Evaluation
Pipeline are now in place. The v0.7 release gate has passed; v1.0 job-ready
work is next.

## Requirements

- Docker Desktop with Compose
- Python 3.11 or newer
- Node.js 20 or newer

## Start infrastructure

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
```

The services use these host ports:

- PostgreSQL: `55432`
- Redis: `6379`
- Qdrant: `6333` and `6334`
- MinIO API/console: `9000` and `9001`

The root `.env` is local-only and is excluded by `.gitignore`.

## Start backend

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item ..\.env .env -ErrorAction SilentlyContinue
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Backend URLs:

- Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- System info: <http://127.0.0.1:8000/api/v1/system/info>
- Register: `POST http://127.0.0.1:8000/api/v1/auth/register`
- Login: `POST http://127.0.0.1:8000/api/v1/auth/login`
- Current user: `GET http://127.0.0.1:8000/api/v1/auth/me`
- Knowledge bases: `GET/POST http://127.0.0.1:8000/api/v1/knowledge-bases`
- Knowledge base detail: `GET/PATCH/DELETE http://127.0.0.1:8000/api/v1/knowledge-bases/{id}`
- Documents: `POST/GET http://127.0.0.1:8000/api/v1/knowledge-bases/{id}/documents`
- Document detail: `GET/DELETE http://127.0.0.1:8000/api/v1/knowledge-bases/{id}/documents/{document_id}`

Authentication uses Argon2 password hashes and short-lived JWT access tokens.
Set `JWT_SECRET_KEY` in the local `.env` before any non-development deployment.

The current document slice accepts PDF, TXT, and Markdown uploads, stores the
original object in MinIO, and persists only metadata plus `storage_key` in
PostgreSQL. F2-T1 adds page-aware Parser, Cleaner, and Chunker contracts;
F2-T2 adds synchronous ingestion, idempotent processing, and failure tracking;
F2-T3 adds the EmbeddingProvider contract and Qdrant vector storage adapter;
F2-T4 adds dense retrieval, token-budgeted context, and citations; LLM-backed
F2-T5 adds Conversation/Message persistence and an OpenAI-compatible Chat API.
F3-T1 adds PostgreSQL-backed sparse retrieval: processed chunks are persisted
in `document_chunks` and searched with PostgreSQL full-text search and a GIN
index. F3-T2 adds parallel Dense/Sparse candidate retrieval and independent
RRF fusion with source-score normalization and duplicate handling. Chat
endpoints are under `/api/v1/conversations`. F3-T3 adds a Cohere-compatible
Reranker Adapter with timeout handling and explicit passthrough fallback. Set
`LLM_API_KEY` and `RERANKER_API_KEY` before using real external Providers.
F3-T4 adds Retrieval Debug API/UI and request-scoped versioned Evaluation
Datasets with initial Retrieval Recall and Citation Correctness metrics; the
F3-T5 v0.4 release gate is complete.
F4-T1 adds bounded LangGraph Agent Runtime contracts, AgentRun/ToolCallRecord
persistence, and max-step/timeout/cancellation controls. F4-T2 adds the
provider-neutral Tool Registry with input validation, structured errors,
timeouts, logging, and ToolCallRecord persistence. Concrete tools remain
F4-T3 adds knowledge search, AST-safe calculator, whitelisted read-only SQL,
and a provider-adapted web search tool. F4-T4 adds Agent configuration, runs,
run history, Tool Call records, and a non-streaming Agents UI. F5-T1 now adds
bounded short-term Conversation memory: Chat and Agent history
are loaded from the existing `messages` table, selected by message count and
transparent token budget, and user/assistant turns are persisted for Agent
runs that provide a `conversation_id`. Configure `AGENT_CONTEXT_TOKEN_BUDGET`
alongside the existing Chat/Agent limits. No new migration is required.
F5-T2 adds user-owned structured long-term memories with explicit extraction,
confirmation, search, edit, and delete flows. The extractor never persists an
ordinary chat line or copies the full conversation history. Agent routing defaults to `qwen-flash`, while final Chat and
Agent answers default to `qwen-plus`; Chat/Agent history and retrieval context
are bounded by environment-configured limits.
F5-T3 adds the provider-neutral dangerous Tool approval contract, durable
approval state with expiry and idempotent approve/reject/resume actions, and
the Agent approval UI. The v0.6 release gate verifies that dangerous Tools are
blocked before approval, can resume after approval, and reach explicit terminal
states after rejection or expiry. No new side-effect Tool is enabled.
F6-T1 adds a fail-open, provider-neutral Observability Adapter with Langfuse
OTLP export for traces, LLM generations, retrieval, reranking, tools, memory,
and Agent runs. It records latency, model, token usage, and errors without
shipping message content or Tool arguments/results. Langfuse is opt-in through
the `LANGFUSE_*` settings and requires no database migration.
F6-T2 extends the versioned retrieval dataset with deterministic Retrieval
Recall, Answer Relevance, Faithfulness, Citation Correctness, and dataset/result
fingerprints. Answer metrics are lexical grounding proxies and do not invoke an
LLM, so repeated evaluation runs remain reproducible.
The v0.7 release gate verifies the complete Agent trace path, fail-open
observability, repeatable evaluation fingerprints, full-stack checks, Docker
health, and sensitive-file safety.

## Start frontend

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` and `/health` to the local
backend.

## Verification

```powershell
Set-Location backend
python -m pytest
ruff check .

Set-Location ..\frontend
npm run type-check
npm run build
```

The frontend build currently reports a non-blocking large-chunk warning from
Element Plus. Code splitting is deferred until a later frontend task.

## Stop infrastructure

From the repository root:

```powershell
docker compose down
```
