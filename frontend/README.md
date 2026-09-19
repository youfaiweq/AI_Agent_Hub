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

The current shell contains only the Dashboard and backend connectivity status. Authentication, knowledge-base, chat, and agent screens are intentionally deferred to later milestones.
