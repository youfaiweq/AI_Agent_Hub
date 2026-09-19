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

Authentication uses Argon2 password hashes and JWT access tokens. Configure
`JWT_SECRET_KEY` through the local `.env` before non-development deployment.

The document slice accepts PDF, TXT, and Markdown uploads and stores original
objects in MinIO. Parsing and RAG are intentionally deferred to v0.3.

## Run tests

```powershell
pytest
```

The current bootstrap tests cover OpenAPI, health routing, system information,
development CORS, database primitives, and infrastructure adapters. Integration
tests use the local Compose services; unit tests use test adapters where
appropriate.
