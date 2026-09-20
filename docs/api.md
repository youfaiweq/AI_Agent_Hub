# API Demo Map

The authoritative interactive contract is generated at `/docs` by FastAPI.
The main v1.0 walkthrough uses:

| Flow | Endpoint |
| --- | --- |
| Register/login | `POST /api/v1/auth/register`, `POST /api/v1/auth/login` |
| Knowledge base | `GET/POST /api/v1/knowledge-bases` |
| Upload/process document | `POST /api/v1/knowledge-bases/{id}/documents`, `POST .../{document_id}/process` |
| Chat | `POST /api/v1/conversations/{id}/chat` |
| Agent run | `POST /api/v1/agents/{id}/runs` |
| Approval | `POST .../runs/{run_id}/approve` or `/reject` |
| Long-term memory | `POST/GET/PATCH/DELETE /api/v1/memories` |
| Retrieval evaluation | `POST /api/v1/knowledge-bases/{id}/retrieval/evaluate` |

All protected endpoints require `Authorization: Bearer <access_token>`. Error
responses use the structured `{ "detail": { "code", "message" } }` contract.
