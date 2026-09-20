# AgentHub v1.0 Production Deployment

The production stack builds the backend and frontend images locally and keeps
PostgreSQL, Redis, Qdrant, and MinIO on a private Docker network. Only the
Nginx frontend port is published by default.

## Start

```powershell
Copy-Item .env.production.example .env.production
# Replace every `replace-with-*` value and provide provider credentials only
# through the deployment secret store or the local ignored env file.
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Open `http://127.0.0.1:8080`. The backend container applies Alembic migrations
before starting Uvicorn. In an internet-facing deployment, terminate TLS at
the hosting load balancer or reverse proxy and restrict the published port to
that proxy.

## Stop and update

```powershell
docker compose --env-file .env.production -f docker-compose.prod.yml down
docker compose --env-file .env.production -f docker-compose.prod.yml pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Do not use `down -v` unless the data volumes have been backed up and their
removal is intentional.
