# IntelliPlant — Web Dashboard

Next.js 15 (App Router, TypeScript) frontend for the IntelliPlant platform.

## Run

```powershell
npm install
npm run dev
```

Opens on **http://localhost:3000**. Expects the backend on
**http://localhost:8000** (override with `NEXT_PUBLIC_API_BASE`).

Login: `engineer@intelliplant.io` / `demo123`

## Pages

| Route | Purpose |
|---|---|
| `/login` | JWT login (demo credentials shown on the card) |
| `/` | Dashboard: KPIs, equipment health grid, active alerts |
| `/copilot` | RAG chat with citations, confidence badges, follow-up pills, filters |
| `/documents` | Upload + ingestion progress polling, indexed library, entity drawer |
| `/equipment` | Searchable equipment grid |
| `/equipment/[id]` | Profile, maintenance timeline, alerts, documents, RCA assistant |
| `/compliance` | Regulation×department matrix, gaps, expiring certs, scan trigger |
| `/incidents` | Proactive warnings, incident log, report form, lessons learned |
| `/analytics` | Query volume, knowledge gaps, top topics, query history |

No UI libraries — one global CSS design system (`app/globals.css`), tiny
dependency-free markdown renderer, shared typed API client (`lib/api.ts`).
