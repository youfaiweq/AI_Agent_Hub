# AgentHub Frontend

## Requirements

- Node.js 20 or newer
- AgentHub backend running at `http://127.0.0.1:8000`

## Setup

```powershell
npm install
```

## Development

```powershell
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` and `/health` to the FastAPI backend.

## Verification

```powershell
npm run type-check
npm run build
```

The current frontend includes:

- Login and registration with JWT session persistence
- Protected workspace routes and sign-out
- Knowledge base create, list, edit, detail, and delete flows
- PDF/TXT/Markdown document upload, list, status, and delete flows
- Loading, empty, validation, API error, and delete confirmation states

Chat, RAG, and Agent screens are intentionally deferred to later milestones.
