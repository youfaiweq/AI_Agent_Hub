# AgentHub

AgentHub is an enterprise AI knowledge and task-agent platform. The current
slice covers authentication, user-owned knowledge bases, document ingestion,
dense retrieval, sparse retrieval, RRF-based hybrid retrieval, and
citation-grounded chat. Reranking is available through a configured external
Provider; Agents and later capabilities remain scheduled for subsequent
milestones.

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
F3-T5 v0.4 release gate is complete. The next Agent milestone remains deferred.

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
