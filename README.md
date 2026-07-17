# ExceptionLoop

> Operational control plane for AI agent exceptions.

**Live: [exceptionloop.vercel.app](https://exceptionloop.vercel.app) &nbsp;·&nbsp; [API docs](https://exceptionloop.onrender.com/docs)**

---

When AI agents escalate cases they cannot handle, those cases land in generic queues with no context, no ownership, and no way to learn from them. ExceptionLoop captures complete context at escalation time, retrieves similar resolved cases via vector search, generates a resolution recommendation, and converts recurring patterns into automation proposals.

---

## Screenshots

### Workspace list
![Workspace list](docs/workspaces.png)

Each workspace monitors one AI agent deployment. The QuickCommerce Returns Agent has 9 exceptions in flight — visible from the moment the workspace loads.

### Exception queue and dashboard
![Exception queue](docs/dashboard.png)

Volume by severity, open / critical / resolved counts, and the live exception queue with real customer messages and exception type tags. Specialists see actual customer language — not category labels.

---

## The problem

50% of enterprises have 10+ agents in production (IDC 2025). Each new agent creates a new exception category. Exception handling headcount grows with agent deployment. Human resolutions — the most valuable training signal an organization has — disappear into unstructured ticket histories.

> *"My engineers ask me what the agent should handle next. I have no data. I have vibes."*
> — AI Product Manager, Series C SaaS (discovery interview)

> *"I solve the same problems every week. But every time I see one, I start from scratch."*
> — Exception Operations Specialist (design partner)

---

## How it works

```
Exception received (API or Zendesk webhook)
        ↓
Classify + embed + retrieve similar resolved cases (pgvector)
        ↓
Generate recommendation citing source cases
        ↓
Specialist resolves in Zendesk sidebar — no tab switch required
        ↓
Quality gate: usefulness rating → adjudication if low
        ↓
Clustering + purity scoring (≥80% agreement required)
        ↓
8-dimension readiness scoring → workflow spec generated
        ↓
Exception pipeline: candidates → approved → in development → shipped
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, App Router |
| Auth | Clerk v5 |
| Backend | FastAPI, SQLAlchemy 2.0 async, asyncpg |
| Database | PostgreSQL + pgvector hosted on Neon |
| Embeddings | OpenAI text-embedding-3-small (1536d) |
| LLM | Anthropic Claude (classification, recommendations, readiness scoring) |
| Backend hosting | Render |
| Frontend hosting | Vercel |

---

## Key design decisions

**Recommendation generated after retrieval — always.** The recommendation service receives similar cases as a parameter and cannot run without them. This prevents anchoring bias: specialists read similar cases before the AI output, not after. Confirmed as a hard requirement in the first design partner working session.

**`entered_pipeline` is a data-layer constraint.** Low-usefulness rejections (rating ≤ 2) set this to `false` and route to manager adjudication. The clustering pipeline queries `WHERE entered_pipeline = true`. No UI-level bypass is possible — bad feedback cannot contaminate the learning pipeline regardless of how the API is called.

**`workflow_specs.steps` is JSONB with `source_case_ids` per step.** Each generated automation step links to the real human resolutions that produced it. Abstract steps without evidence citations are unusable by automation engineers — this is enforced in the data model.

**Cluster purity ≥ 80% before readiness scoring.** Prevents readiness scoring from being applied to heterogeneous clusters with hidden variance. A cluster that scores 90% ready but contains 30% different root patterns creates silent automation failures after deployment.

**Usefulness rating measures retrieval quality, not recommendation quality.** When rejecting a recommendation, specialists rate whether the similar cases shown were relevant (1–5) — not whether the recommendation was good. This is the signal the embedding/retrieval system can actually improve on.

---

## Two intake modes

| Mode | Source | Context | Value |
|------|--------|---------|-------|
| Full | Instrumented agent API | 6 fields: trigger, context, attempted actions, missing info, policy ref, risk level | 100% |
| Minimal | Zendesk webhook (fires automatically on ticket creation) | Customer message + escalation reason | ~60% |

The minimal intake mode removes the adoption blocker for teams that don't control their agent stack. Any Zendesk customer can start using ExceptionLoop without filing an engineering ticket.

---

## Automation-readiness model (8 dimensions)

| Dimension | Question |
|-----------|----------|
| Frequency | Does this exception occur often enough to justify automation? |
| Resolution consistency | Do humans solve it with the same steps? |
| Data completeness | Are required inputs reliably available? |
| Risk | What is the consequence of an incorrect automated action? |
| Reversibility | Can the action be undone quickly? |
| Policy clarity | Is the expected behavior explicitly defined? |
| Integration stability | Are required systems dependable? |
| Evaluation feasibility | Can correct outcomes be measured objectively? |

---

## API endpoints

```
GET    /health

POST   /workspaces/
GET    /workspaces/
GET    /workspaces/{id}

POST   /intake/full                        Structured intake (6 fields)
POST   /webhooks/zendesk/{workspace_id}    Minimal intake via Zendesk webhook
GET    /workspaces/{id}/cases
GET    /cases/{id}

POST   /cases/{id}/resolve
POST   /cases/{id}/flag-new-pattern        One-click new pattern flag → AI PM queue
GET    /workspaces/{id}/quality-reviews
POST   /quality-reviews/{id}/adjudicate

POST   /workspaces/{id}/cluster            Run clustering pipeline
GET    /workspaces/{id}/clusters
POST   /clusters/{id}/purity-review        Human purity assessment
POST   /clusters/{id}/score-readiness      8-dimension readiness scoring
POST   /clusters/{id}/generate-spec        Generate workflow specification
POST   /specs/{id}/advance                 Advance pipeline stage
GET    /workspaces/{id}/pipeline           Exception pipeline kanban view
```

---

## Sprint roadmap

| Sprint | Scope | Status |
|--------|-------|--------|
| 1 | Schema (11 tables + pgvector), intake API + Zendesk webhook | ✅ |
| 2 | Classifier, embedding service, similar-case retrieval, recommendation generator | ✅ |
| 3 | Zendesk sidebar, resolution capture, quality gate, clustering pipeline | ✅ |
| 4 | Purity scoring, readiness scoring, workflow spec generator, pipeline view | ✅ |
| 5 | Auth (Clerk), deployment (Neon + Render + Vercel) | ✅ |
| 6 | End-to-end demo with real agent data | ⬜ |

---

## Portfolio context

ExceptionLoop is the second project in an AI operations portfolio. The first, [PolicyLens AI](https://github.com/rajendergugulothu/policylens-ai), tests agents against policy before deployment. ExceptionLoop manages what breaks after deployment.

Together they cover the full AI agent operations lifecycle:

| | PolicyLens AI | ExceptionLoop |
|--|--------------|---------------|
| **When** | Before deployment | After deployment |
| **What** | Tests agents against policy | Manages escalations + learns from them |
| **Output** | Launch-readiness report | Automation pipeline |
| **North Star** | % decisions proven safe before prod | % recurring exceptions converted to automation |

Phase 0 discovery included 8 synthetic user research interviews and a manual concierge test on 47 real exception cases from a production returns agent. The concierge test found that 40% of all escalations over a 2-week period were a single recurring pattern — the loyalty points refund split — that had been present for 4 months without being identified or automated.

---

## License

MIT
