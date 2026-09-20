# Backup and Recovery Runbook

The PostgreSQL database, Qdrant storage, and MinIO objects are persistent
volumes. Redis is disposable runtime state and is not part of the application
backup set.

## PostgreSQL logical backup

```powershell
New-Item -ItemType Directory -Force .\backup | Out-Null
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres `
  pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB --format=custom > .\backup\agenthub.dump
```

Create the backup directory outside Git and protect it like production data.
Restore into a stopped application stack or a separate recovery database:

```powershell
Get-Content .\backup\agenthub.dump -Raw -Encoding Byte |
  docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres `
  pg_restore -U $env:POSTGRES_USER -d $env:POSTGRES_DB --clean --if-exists
```

For a complete disaster recovery point, snapshot the PostgreSQL, Qdrant, and
MinIO volumes together. After restore, run `alembic upgrade head`, verify
`/health`, and confirm one document retrieval plus one Agent run before
reopening traffic.
