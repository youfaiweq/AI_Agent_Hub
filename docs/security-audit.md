# v1.0 Security Audit Checklist

- [x] `.env`, certificates, private keys, uploads, and local database files are ignored.
- [x] No API keys, JWT secrets, passwords, Tool arguments, or Tool results are emitted by telemetry.
- [x] Protected APIs require JWT authentication and user ownership checks.
- [x] SQL Tool is read-only, validates AST, enforces table whitelist, timeout, and row limit.
- [x] Production Compose keeps databases on a private network and publishes only Nginx.
- [x] Production deployment requires explicit database passwords and JWT secret variables.
- [x] Backend and Nginx images have health checks and the backend runs migrations before startup.
- [x] Failure drills cover invalid authentication, request validation, and dependency health.

Run the repository checks with:

```powershell
./scripts/security_audit.ps1
./scripts/error_drills.ps1
```

The error drills require a running backend URL and intentionally use invalid
requests only; they do not create or delete business data.
