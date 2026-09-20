# v1.0 Screenshots

The v1.0 walkthrough captures the following local demo views at
`http://127.0.0.1:5173` after running `scripts/seed_demo.py`:

1. **Dashboard** — v1.0 badge, runtime summary, infrastructure health, and
   responsive mobile shell.
2. **Agents** — the seeded Demo Research Agent, bounded step/timeout limits,
   and configured read-only tools.
3. **Long-term Memory** — explicit extraction UI and the confirmed demo
   preference.

These screenshots were captured during the v1.0 UI verification turn. To
recreate them locally:

```powershell
$env:DEMO_USER_PASSWORD = 'use-a-local-demo-password'
python scripts/seed_demo.py
Set-Location backend
python -m uvicorn app.main:app --reload
Set-Location ..\frontend
npm run dev -- --host 127.0.0.1
```

Use the demo account, open Dashboard, Agents, and Memory, and capture the
viewport at the same responsive breakpoint. No production credentials or
private data are used in the demo views.
