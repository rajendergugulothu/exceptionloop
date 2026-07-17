# ExceptionLoop

> Operational control plane for AI agent exceptions.

When AI agents escalate cases they cannot handle, those cases land in generic queues with no context, inconsistent ownership, and no systematic learning. ExceptionLoop captures complete context, classifies the exception, retrieves similar resolved cases, recommends a resolution, and converts recurring patterns into automation proposals.

**Status:** Sprint 1 complete — workspace management, exception intake (full API + Zendesk webhook), 11-table schema with pgvector.

---

## The problem

50% of enterprises have 10+ agents in production (IDC 2025). Each agent creates its own exception category. Exception handling headcount grows with agent deployment. Human resolutions — the most valuable training signal — disappear into unstructured ticket histories.

> *"My engineers ask me what the agent should handle next. I have no data. I have vibes."* — AI Product Manager, Series C SaaS

---

## How it works

```
Exception received (webhook / API)
        ↓
Classify + retrieve similar cases
        ↓
Generate recommendation (after retrieval, citing source cases)
        ↓
Specialist resolves in Zendesk sidebar (no tab switch)
        ↓
Quality gate (usefulness rating → adjudication if low)
        ↓
Clustering + purity scoring → readiness scoring
        ↓
Workflow spec generated → exception pipeline view
```

---

## Quick start

```bash
# 1. Start PostgreSQL with pgvector
docker compose up db

# 2. Set up backend
cd backend
cp .env.example .env       # fill in API keys
pip install -r requirements.txt
uvicorn main:app --reload  # http://localhost:8000/docs

# 3. Start frontend (Sprint 2+)
cd frontend && npm install && npm run dev
```

**Requires PostgreSQL with pgvector extension.** Docker image `pgvector/pgvector:pg16` has it pre-installed.

---

## Project structure

```
exceptionloop/
├── backend/
│   ├── main.py                   FastAPI app, 7 Sprint 1 routes
│   ├── database.py               Async SQLAlchemy + pgvector init
│   ├── models/                   11 ORM tables
│   │   ├── workspace.py
│   │   ├── exception_case.py     Vector(1536) embedding column
│   │   ├── resolution.py         entered_pipeline flag (quality gate)
│   │   ├── cluster.py            ExceptionCluster, ReadinessScore, WorkflowSpec
│   │   └── audit.py              Append-only AuditLog
│   ├── schemas/                  Pydantic v2 request/response models
│   └── routers/
│       ├── workspaces.py         POST / GET / GET /{id}
│       └── intake.py             Full API + Zendesk webhook + case list/get
└── frontend/                     Next.js 14 (Sprint 2+)
```

---

## API endpoints (Sprint 1)

```
POST   /workspaces/                     Create workspace
GET    /workspaces/                     List workspaces
GET    /workspaces/{id}                 Get workspace

POST   /intake/full                     Structured intake from instrumented agent
POST   /webhooks/zendesk/{workspace_id} Minimal intake from Zendesk webhook
GET    /workspaces/{id}/cases           List exception cases
GET    /cases/{id}                      Get case

GET    /health
```

---

## Two intake modes

| Mode | Source | Fields | Value |
|------|--------|--------|-------|
| Full | Agent API | 6 fields: trigger, context, actions, missing info, policy ref, risk | 100% |
| Minimal | Zendesk webhook | Customer message + escalation reason | ~60% |

The minimal intake mode removes the adoption blocker: specialists who don't control their agent stack can start using ExceptionLoop without any engineering work. The Zendesk webhook fires automatically when the agent creates a ticket. ExceptionLoop enriches it.

---

## Key design decisions

**`resolutions.entered_pipeline` is a data-layer constraint.** Low-usefulness rejections (rating ≤ 2) set this to false and route to quality review. The clustering pipeline queries `WHERE entered_pipeline = true`. No UI-level bypass is possible.

**`workflow_specs.steps` is JSONB with `source_case_ids` per step.** Each generated step links to the real human resolutions that produced it. This is the automation engineer's trust condition: abstract steps without evidence are unusable.

**Embedding column is `Vector(1536)` via pgvector.** Using text-embedding-3-small (OpenAI). Stored in the same PostgreSQL instance as all other data — no additional infrastructure needed in Phase 1.

**Zendesk webhook signature validation is per-workspace.** Each workspace can have its own `zendesk_webhook_secret`. The validation uses HMAC-SHA256. Workspaces without a secret skip validation (for development).

---

## Sprint roadmap

| Sprint | Scope | Status |
|--------|-------|--------|
| 1 | Setup, 11-table schema, intake (full + webhook) | ✅ Done |
| 2 | Classifier, embedding service, similar-case retrieval, recommendation generator | ⬜ Next |
| 3 | Zendesk sidebar app, specialist resolution capture, quality gate | ⬜ |
| 4 | Clustering pipeline, purity scoring, readiness scoring | ⬜ |
| 5 | Workflow spec generator, exception pipeline view | ⬜ |
| 6 | End-to-end demo with Maya Okonkwo (Nexagen) | ⬜ |
