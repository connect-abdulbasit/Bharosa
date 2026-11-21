# Architecture

```mermaid
flowchart LR
  subgraph Client
    FE[Frontend PWA<br/>Next.js, offline, read-aloud]
  end
  subgraph Platform
    BE[Backend API<br/>FastAPI, JWT + RBAC]
    AI[ai package<br/>bharosa_ai<br/>classify, match, OCR, extract, decide, explain]
    DB[(Postgres<br/>Alembic migrations)]
  end
  subgraph Simulated public rails
    MK[Mocks<br/>identity, ledger, complaints,<br/>senders, notify, chaos]
  end
  SV[services<br/>notifications, webhooks, digital twin]
  FE -->|REST + JWT| BE
  BE --> AI
  BE --> DB
  BE -->|consent checked first| MK
  SV --> BE
  SV --> MK
  C[(contracts)] -.shared types and fixtures.- FE
  C -.- BE
  C -.- AI
  C -.- MK
```

- **Frontend** (`/frontend`): mobile-first PWA for citizen, helper, officer, admin and auditor. Read-aloud, Urdu/English, progress saved to IndexedDB. In `fixtures` mode it runs with no backend.
- **Backend** (`/backend`): the single trusted entry point. Authenticates (JWT), authorises (server-side RBAC), manages cases, runs the claim pipeline (resumable steps), versions rules, manages consent, writes the audit log, issues API keys, and exposes Swagger.
- **AI package** (`/ai`): pure functions behind a typed interface. Every output has `confidence` and `model_version`. `AI_MODE=stub|real` swaps implementations without changing callers.
- **Mocks** (`/mocks`): simulated NADRA/Raast/complaints/SMS with deterministic seed data and in-memory chaos switches (timeout, 500, missing record, duplicate payment, lookalike sender, slow network). Everything returns `simulated: true`.
- **Postgres**: cases, claims, decisions, rules and versions, consent, audit log, API keys. Alembic migrations.
- **Services** (`/services`): notifications, webhooks and the Digital Twin simulation. They use the public API.
- **Contracts** (`/contracts`): enums, Pydantic schemas, AI interface, OpenAPI lists and fixtures that let four people build in parallel.
- **Claim pipeline**: consent check -> extract claim -> read document -> identity match -> ledger lookup -> decide -> explain -> persist and audit. If a mock fails, the case goes to `with_officer` with notes.


## Backend internals

```mermaid
flowchart TB
  C[Client or partner] -->|JWT or X-API-Key| MW[Middleware: CORS, request id + JSON log, gzip, rate limit, ETag]
  MW --> R[Routers + require_role / public_access]
  R -->|row-level checks| S[Services: cases, consent, rules, scam, payments]
  R -->|202 + job row| J[(jobs table)]
  W[Worker thread] -->|atomic claim| J
  W --> P[Pipeline: extract, ID photo, identity, ledger, match, decide, explain, notify]
  P --> AI[bharosa_ai]
  P -->|consent.require first| MK[Mocks or fake client]
  S --> DB[(Postgres)]
  P --> DB
  S -->|every change| AU[audit_log: append-only, DB trigger]
  S -->|status change| EV[events.emit - webhook hook]
```

- **Request path**: every request gets an id (`X-Request-ID`), one JSON access-log line (role, latency) and one error format. Polled GETs support `ETag`; responses are gzipped and omit empty fields for weak connections.
- **Claim agent**: `POST /claims` only saves the input and queues a job (202); the worker runs the steps, saving each one so `resume` continues where it stopped. A mock failure, missing consent or crash pauses the case with an officer note; it never becomes a 500.
- **Payments**: the officer's approval stores an idempotency key on the decision before calling the rail, so retries cannot pay twice.
- **Public API**: scoped, hashed, revocable keys; every use audited; per-key rate limits.
- **Operations**: `/health` checks the database and mocks, optional Sentry, config in env vars, `backend/render.yaml` for deploy.
