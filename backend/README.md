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
The v0.4 release gate has been verified; the next Agent milestone remains
deferred.

## Run tests

```powershell
pytest
```

The current bootstrap tests cover OpenAPI, health routing, system information,
development CORS, database primitives, and infrastructure adapters. Integration
tests use the local Compose services; unit tests use test adapters where
appropriate.
