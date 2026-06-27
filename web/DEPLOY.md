# Compass frontend — Vercel deploy (Git-integrated)

> Owner: Jig. Deployment is **automatic via GitHub ↔ Vercel integration**:
> push to GitHub and Vercel builds it. No CLI deploy step.
> - push/merge to **`main`** → **Production** deploy
> - push to any other branch / open a PR → **Preview** deploy (unique URL)

## Repo shape (why the frontend lives in `web/`)

```
Par-agents/
├── compass/   ← Python backend (run_pipeline, agents, reconciler)  — Ash/P3
├── app/       ← Python Streamlit frontend (other teammate)
├── data/      ← Alpine parquet (gitignored, local only)
└── web/       ← THIS Next.js app  ← Vercel builds from here
```

The Next.js App Router needs `app/`, which the Python side already owns at repo
root — so the frontend is isolated in `web/`. **The single most important Vercel
setting: Root Directory = `web`.** Without it, Vercel builds the repo root and fails.

## One-time setup (do once, after team agrees to deploy)

In the **Vercel dashboard** → New Project → Import `Manasi200801/Par-agents`:

1. **Root Directory:** set to `web` ← critical (monorepo).
2. **Framework Preset:** Next.js (auto-detected).
3. **Production Branch:** `main`.
4. Add environment variables (below) for Production **and** Preview.
5. Create. Vercel now redeploys on every push automatically.

> CLI equivalent if you prefer: `cd web && vercel link` then
> `vercel git connect` — but the dashboard import is the cleaner one-time path
> and is what sets Root Directory + production branch.

## Environment variables (set in Vercel project settings)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | for real pipeline | Claude key (hackathon credits). Server-side only — never `NEXT_PUBLIC_`. |
| `PIPELINE_URL` | optional | Base URL of the Python pipeline service. **Unset → app serves the demo stub.** Set → `/api/analyze` & `/api/commit` proxy to the real `run_pipeline`. |

> Local secrets in `../.env.local` and `.claude/settings.local.json` are gitignored
> and do **not** ship to Vercel — they must be added in the dashboard explicitly.

## Stub vs real data (no UI change between them)

- **No `PIPELINE_URL`** → UI runs on the built-in demo stub (`web/lib/stub.ts`).
  Numbers are illustrative — fine for a frontend-only preview deploy.
- **`PIPELINE_URL` set** → route handlers proxy to the real Python pipeline,
  which must expose `POST /analyze` and `POST /commit` returning the
  `ReconcilerOutput` / `{ decision_id }` shapes (`web/lib/types.ts`). If the
  pipeline is unreachable, the routes fall back to the stub so the demo never
  hard-fails.

## Pre-merge gut check

- [ ] `cd web && npm run build` passes locally
- [ ] Root Directory = `web` is set in Vercel
- [ ] `ANTHROPIC_API_KEY` present in Vercel (Production + Preview)
- [ ] A preview deploy from the `Jig` branch renders before merging to `main`
