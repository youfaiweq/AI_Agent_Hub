# AgentHub

AgentHub is an enterprise AI knowledge and task-agent platform. The current
release is v0.1, the foundation slice. Authentication, knowledge-base business
logic, RAG, and Agent features are intentionally deferred to later milestones.

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
