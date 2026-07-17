# ExceptionLoop

> Operational control plane for AI agent exceptions.

When AI agents escalate cases they cannot handle, those cases land in generic queues with no context, inconsistent ownership, and no systematic learning. ExceptionLoop captures complete context at escalation time, retrieves similar resolved cases via vector search, generates a resolution recommendation, and converts recurring patterns into automation proposals.

**Live:** [exceptionloop.vercel.app](https://exceptionloop.vercel.app) · [API docs](https://exceptionloop.onrender.com/docs)

---

## The problem

50% of enterprises have 10+ agents in production (IDC 2025). Each agent creates its own exception category. Exception handling headcount grows linearly with agent deployment. Human resolutions — the most valuable training signal — disappear into unstructured ticket histories with no way to detect patterns or generate automation from them.

---

## How it works

```
Exception received (API or Zendesk webhook)
        ↓
Classify + embed + retrieve similar resolved cases (pgvector)
        ↓
Generate recommendation citing source cases
        ↓
Specialist resolves in Zendesk sidebar (no tab switch)
        ↓
Quality gate: usefulness rating → adjudication if low
        ↓
Clustering + purity scoring → readiness scoring
        ↓
Workflow spec generated → exception pipeline view
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14.2.5, TypeScript, App Router |
| Auth | Clerk v5 |
| Backend | FastAPI, SQLAlchemy 2.0 async, asyncpg |
| Database | PostgreSQL + pgvector (hosted on Neon) |
| Embeddings | OpenAI text-embedding-3-small (1536d) |
| Backend hosting | Render |
| Frontend hosting | Vercel |

---

## Local development

### Prerequisites

- Docker (for local Postgres with pgvector)
- Python 3.11+
- Node.js 18+
- OpenAI API key
- Clerk publishable key + secret key

### Start the database

```bash
docker compose up db
```

Uses `pgvector/pgvector:pg16` which has the extension pre-installed.

### Backend

```bash
cd backend
cp .env.example .env   # fill in DATABASE_URL, OPENAI_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:3000
```

---

## Environment variables

### Backend (`.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | For embeddings and recommendation generation |
| `ENVIRONMENT` | Set to `production` on Render |

### Frontend (`.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend URL (e.g. `https://exceptionloop.onrender.com`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | From Clerk dashboard |
| `CLERK_SECRET_KEY` | From Clerk dashboard |

---

## Project structure

```
exceptionloop/
├── backend/
│   ├── main.py                   FastAPI app + lifespan (DB init)
│   ├── database.py               Async SQLAlchemy engine, asyncpg SSL handling
│   ├── models/
│   │   ├── workspace.py
│   │   ├── exception_case.py     ExceptionCase with Vector(1536) embedding
│   │   ├── resolution.py         Resolution + entered_pipeline quality gate
│   │   ├── cluster.py            ExceptionCluster, ReadinessScore, WorkflowSpec
│   │   └── audit.py              Append-only AuditLog
│   ├── schemas/                  Pydantic v2 request/response models
│   └── routers/
│       ├── workspaces.py
│       ├── intake.py             Full API + Zendesk webhook
│       ├── resolutions.py
│       ├── clusters.py
│       └── sidebar.py            Zendesk sidebar widget data
└── frontend/
    ├── app/
    │   ├── layout.tsx            ClerkProvider wrapper
    │   ├── page.tsx              Workspace list
    │   ├── sign-in/              Clerk sign-in page
    │   ├── workspace/[id]/       Workspace detail + cases
    │   ├── workspace/[id]/clusters/  Clustering kanban
    │   ├── clusters/[id]/        Cluster detail + readiness scoring
    │   └── sidebar/              Zendesk sidebar widget
    ├── lib/api.ts                Typed API client
    └── middleware.ts             Clerk auth (protects all non-public routes)
```

---

## API endpoints

```
GET    /health

POST   /workspaces/
GET    /workspaces/
GET    /workspaces/{id}

POST   /intake/full                      Structured intake (6 fields)
POST   /webhooks/zendesk/{workspace_id}  Minimal intake via Zendesk webhook
GET    /workspaces/{id}/cases
GET    /cases/{id}

POST   /cases/{id}/resolve
GET    /cases/{id}/resolution

GET    /workspaces/{id}/clusters
GET    /clusters/{id}

GET    /sidebar                          Zendesk sidebar widget data
```

### Two intake modes

| Mode | Source | Context richness |
|------|--------|-----------------|
| Full | Instrumented agent API | 100% — trigger, context, actions taken, missing info, policy ref, risk level |
| Minimal | Zendesk webhook (fires automatically) | ~60% — customer message + escalation reason |

The minimal mode removes the adoption blocker: teams that don't control their agent stack can start without any engineering work on the agent side.

---

## Key design decisions

**`resolutions.entered_pipeline` is a data-layer constraint.** Low-usefulness ratings (≤ 2) set this to `false` and route to quality review. The clustering pipeline queries `WHERE entered_pipeline = true`. No UI-level bypass is possible.

**`workflow_specs.steps` is JSONB with `source_case_ids` per step.** Each generated automation step links to the real human resolutions that produced it — the automation engineer's trust condition.

**Vector column is `Vector(1536)` via pgvector.** Same PostgreSQL instance as all other data. No additional infrastructure required.

**asyncpg + Neon SSL:** `sslmode` and `channel_binding` query params are stripped at runtime; SSL is passed via `connect_args={"ssl": "require"}` in production.

---

## Sprint roadmap

| Sprint | Scope | Status |
|--------|-------|--------|
| 1 | Schema, intake (full + webhook), workspace API | ✅ Done |
| 2 | Classifier, embedding service, similar-case retrieval, recommendation generator | ✅ Done |
| 3 | Zendesk sidebar, resolution capture, quality gate, clustering kanban | ✅ Done |
| 4 | Cluster detail, purity/readiness scoring, workflow spec view | ✅ Done |
| 5 | Auth (Clerk), deployment (Neon + Render + Vercel) | ✅ Done |
| 6 | End-to-end demo with real agent data | ⬜ Next |
