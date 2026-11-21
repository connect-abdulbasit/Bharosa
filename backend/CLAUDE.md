# backend/: Bharosa platform API

**Owner:** Basit. **Depends on:** `/contracts`, and `bharosa_ai` (from `/ai`) via its public functions, plus `/mocks` over HTTP. **Depended on by:** `/frontend` (live mode), `/e2e`.
Read the root `CLAUDE.md` first.

## Contract
Endpoints and models: `contracts/openapi-platform.yaml`, `contracts/schemas.py`, example responses `contracts/fixtures/`. Swagger at `/docs` (tagged, with examples and the `X-API-Key` scheme).
Private (JWT): `/auth/login`, `/admin/demo/reset|chaos`, `/scam-map`, `/rules/{id}/simulate`, `/documents/{id}/image`, `/me`, `/me/pin`, `/cases`, `/cases/{id}`, `/cases/{id}/assign|escalate|decide|close`, `/claims`, `/claims/{id}`, `/claims/{id}/progress`, `/claims/{id}/resume`, `/messages/check`, `/documents`, `/rules`, `/rules/{id}/versions`, `/consent`, `/consent/{id}/withdraw|correct`, `/audit`, `/queue`, `/helper/families`, `/apikeys`, `/apikeys/{id}/revoke`, `/eval`.
Public (`X-API-Key` or JWT, read-only, rate limited per key): `GET /public/cases/{id}/status`, `POST /public/messages/check`. Meta: `/health`.

## Rules
- **Every route has `require_role`** (except `/health`, `/auth/login`). Roles come from the server-side user record, not the token claim alone.
- **Every mutation calls `audit.log(actor, action, before, after)`**; AI and agent steps too (`actor_type="ai"|"agent"`). Audit log is append-only.
- **Consent is checked (`services/consent.py`) before any mock call.**
- **Pipeline steps are saved so they resume** (see `services/pipeline.py`).
- **Mock failures lead to `with_officer` with notes, never a 500 to the user.**
- **Rules are versioned json-logic**; versions are immutable; every decision stores `rule_version`.
- Payment steps always require an officer decision.
- Use `get_mocks_client()`: real HTTP when `MOCKS_URL` is set, otherwise `fake_mocks_client.py`.
- Rate limiting and clean error handling (no stack traces to clients).
- No real personal data. Demo users/passwords are fake (`.env.example`).

## Status
Done: DB models + Alembic `0001`-`0004`, seed, auth/RBAC, audit (+ Postgres trigger `0003`), cases, consent (+ helper PIN rule), claim pipeline, versioned/validated rules, scam check, documents, officer decide + idempotent payments, queue, helper families, **background pipeline, public API keys, rate limiting, global error format, low-bandwidth support, `/eval`, events hook, monitoring, deploy config**.
Nothing is deployed: only config (`backend/render.yaml`, `backend/DEPLOY.md`, `Dockerfile`, `start.sh`).

### Claim pipeline (`services/pipeline.py`) and background jobs (`services/jobs.py`)
- `POST /claims` saves case + claim, writes a row in the **`jobs` table** and returns **202** (`case_id`, `claim_id`, `current_step`, `progress_url`). An in-process worker thread (started in the app lifespan; `PIPELINE_MODE=thread`) runs `extract_claim -> read_document -> identity_lookup -> ledger_lookup -> match_person -> decide -> explain -> notify`. `PIPELINE_MODE=inline` runs the job inside the request (tests). Jobs are claimed with one atomic `UPDATE ... WHERE status='queued'`, so several processes are safe; stale `running` jobs are re-queued at start; a queued job survives a restart.
- `GET /claims/{id}/progress` is the cheap poll (ETag/304). `POST /claims/{id}/resume` enqueues a resume job (202), idempotent while one is active or the claim finished.
- State is in `claims.data["pipeline"]` + `cases.current_step`; every step commits, so resume never redoes finished steps.
- `consent.require` before each identity/ledger call. Missing consent, a mock error/timeout, or an unexpected bug => progress saved, `with_officer`, case note, `send_to_human` decision by `agent`, no 500.
- Audit per step: `ai.<step>` / `agent.<step>` with input summary, output, confidence, model_version.
- Mapping (`map_decision`): auto_handle -> `approved` only without a payment (else `with_officer`); ask_more -> `needs_more_proof`; send_to_human -> `with_officer`. One open claim per citizen per month (`duplicate_claim` -> officer). Only the ACCOUNT's own CNIC is ever looked up.
- Stub AI caveat: `extract_claim` always returns "Mohammad Aslam" at confidence 0.81, so most stub-mode claims end `needs_more_proof`/`with_officer`. Tests patch `bharosa_ai` to reach other paths.

### Payments (officer `decide`)
`reason` (or `note`) is required. Approving a case with a shortfall: consent `payments` -> **decision row saved with `idempotency_key = case_id:decision_id` and committed BEFORE** -> `mocks.disburse(...)` (POST `/payments/disburse`; on 404 falls back to the `/complaints` ticket; implemented in `/mocks`, shape in `contracts/openapi-mocks.yaml`) -> `payment_ref` + `payment_status=paid` committed -> status change. Retries/second approvals reuse the same decision and key, so nobody is paid twice; a payment already made is never repeated. The case row is locked (`FOR UPDATE`) against concurrent approvals. Failure => 503, nothing changes.

### Public API, limits, errors, low bandwidth
- API keys: `POST /apikeys` (admin; shown once, sha256 stored; scopes `cases:read`, `messages:check`), list, `POST /apikeys/{id}/revoke`. `auth/apikey.py` `public_access(scope)` accepts `X-API-Key` or a JWT on `/public` routes only; every use is audited (`apikey.use`, denials `apikey.denied`) and updates `last_used_at`. Keys never open private routes.
- Rate limits (slowapi, settings-driven): `LOGIN_RATE_LIMIT` 5/min per IP, `PUBLIC_RATE_LIMIT` 30/min per key, `DEFAULT_RATE_LIMIT` 120/min per IP; `TRUST_PROXY=1` behind a proxy. 429 is JSON with `Retry-After`.
- Errors: `app/errors.py`. Always `{error, message, request_id}` (+ `fields` for 422; `scope`/`citizen_id` for consent). Full errors are logged with the request id; clients never get traces or input values.
- Low bandwidth: gzip, null fields omitted (`CompactRoute`), `ETag`/`If-None-Match` on `/cases/{id}`, `/queue`, `/claims/{id}/progress`, `/public/cases/{id}/status`.
- `/eval`: live numbers from decisions (by action, officer overrides of AI, average confidence), jobs (average pipeline seconds), checked messages, plus `ai/eval/eval_results.json` as `model_eval` when present. Shape: `LiveEvalResults`.
- Events: `services/events.emit("case.status_changed", payload, db)` is called from `change_status`; it writes an audit row and a local list. **TODO(Hadi)**: real webhook delivery.
- Monitoring: JSON logs (`app/logging_setup.py`, access log in `app/middleware.py` with request id, role, latency), optional Sentry (`SENTRY_DSN`), `/health` = database + mocks reachability + worker (503 only when the database is down).

Conventions:
- Pass the request's `db` session to `audit.log(...)`; it only `add()`s, so the entry commits atomically with the change. When the request will fail afterwards (login failure, blocked consent, failed payment) commit first, then raise.
- Auditors are read-only: enforced centrally in `require_role` and `public_access` (any non-GET is 403).
- Row-level access lives in `services/access.py`; objects a user may not see answer 404.
- Status changes go through `services/cases.change_status` (validates transitions, audits, emits the event).
- JSON columns are not change-tracked: assign a NEW (deep-copied) object, never mutate in place.
- Every router uses `route_class=CompactRoute`; give new routes a tag, a summary and (for bodies) `openapi_examples`.
- `Pillow` is a runtime dependency (image processing).
- Tests use a SQLite FILE per test (the worker thread needs its own connections) and `PIPELINE_MODE=inline`; the `mocks` fixture patches `get_mocks_client` in `routers.cases|messages|public` and `services.jobs`.
- Extra columns beyond the original spec: `users.username`, `users.cnic` (fake), `users.pin_hash`, `api_keys.prefix`, `consent_events.confirmed_by`, `documents.owner_id` (+ nullable `case_id`), `decisions.payment_ref|payment_status|idempotency_key`, table `jobs`.

### Payment check (`intent: "payment_check"`)
`POST /claims {"intent": "payment_check", "month": "YYYY-MM"}` is a QUESTION ("did my payment arrive?"): `claim_type = payment_check`, no speech, the draft is built from the account (confidence 1.0, `model_version: structured-input`), no duplicate/contradiction logic, never a payment. Only a CONFIRMED full payment can be `auto_handle` -> case `closed` with a ledger-grounded Urdu/English answer; no payment on record -> `ask_more` (agent override: "file a claim?"); short or duplicate payment -> `send_to_human`. Still consent-gated, rule-versioned and audited. Reason it exists: with the stub AI a *claim* can never reach 0.90, and auto-closing a claim whose ledger says "paid" would hide the bad-agent case, so claims with that contradiction keep going to an officer.

### Config notes
`LOGIN_RATE_LIMIT`: unset = `5/minute`, or `30/minute` while `DEMO_MODE=1`; an explicit value wins (`config.default_login_limit`).

### Photos, demo, Scam Map, simulation, security walk
- **ID photos** (`routers/documents.py`, `services/images.py|documents.py`): uploads (max 10 MB) are validated with Pillow, EXIF rotation applied then EXIF dropped, shrunk to max 1280 px, re-encoded JPEG q80 (max 2 MB, also a DB CHECK) and stored in Postgres `documents_blob` (bytea, separate from `documents`). `DOCUMENT_DISK_CACHE=1` adds an optional local copy; the database is the source of truth. `GET /documents/{id}/image`: citizen owner, linked helper, officer, admin, auditor; others 404; every view audited; `Cache-Control: private, no-store`.
- **Demo** (`app/demo.py`, `app/demo_data.py`, `routers/admin.py`, `scripts/run_scenarios.py`, `docs/demo-scenarios.md`): 7 named scenarios (`s1-clean` ... `s7-autohandle`, user ids `u-demo-1..7`) whose data lives in the SHARED file `contracts/fixtures/demo_people.json` (people, identity, ledger, `agent-099`, sender codes, expected results; validated by `schemas.DemoPeople`) and is served by the **in-process fake mocks** (so the stub AI reliably reaches different outcomes); `POST /admin/demo/reset` (admin, `DEMO_MODE=1`; rules kept unless `include_rules`; audit log never wiped; the reset is audited); `POST /admin/demo/chaos` breaks the fake identity/ledger/payments service AND is forwarded to the real mocks (`identity_down` -> mocks `error_500`, `ledger_down` -> `missing_record`; `payments_down` fails the payout call in `MocksClient.disburse`); `demo.reset` switches them off again. `GET /cases/{id}` carries `image_url` when the claim has an ID photo; `GET /helper/families` carries `citizen_id`. `make demo-reset`, `make demo-scenarios`. `python -m app.seed` seeds the demo layer too (`--no-scenarios` to skip). `/mocks` serves the same people (its data files are generated from demo_people.json), so the scenarios also run against the real mocks.
- **Scam Map** (`services/scam_map.py`): `GET /scam-map` (officer/admin/auditor): counts by area, day, reason; reasons normalised to fixed categories; areas/reasons with < 3 reports folded into `other`; no text/sender/user ids. 60 seeded fake checks.
- **Rule simulation** (`services/simulate.py`): `POST /rules/{id}/simulate` (admin) re-runs only `ai.decide` on the stored pipeline inputs (claims.data) of the latest AI decision per case under a proposed rule; returns totals, from -> to breakdown, up to 20 examples; read-only except one `rule.simulate` audit row. Seeded sample decisions have no stored inputs and are counted as skipped.
- **Integration tests**: `tests/integration` (marker `integration`, deselected by default); `make test-integration` runs them with `AI_MODE=real` and they skip until all six real AI functions exist (TODO(Ali)).
- **Security walk** (`tests/test_security_walk.py`) iterates `app.routes`: every route needs auth (static + runtime), a citizen gets 404/403 for another citizen's ids, an auditor gets 403 on every non-GET, API keys open only `/public`. A new id route must be added to `EXPECT_404`/`EXPECT_403` there.

### Services app, AI report, live demo citizen (final)
- `services/outbound.py`: when `NOTIFICATIONS_URL` / `WEBHOOKS_URL` are set, `events.emit` forwards every event to the services app and, for `case.status_changed` with the citizen's `notifications` consent granted, queues an Urdu + English in-app message (background pool; `PIPELINE_MODE=inline` runs it inline for tests). Any failure is logged, never raised. `GET /me/notifications` (citizen/helper) proxies the caller's own inbox. Tests: `tests/test_outbound_services.py`.
- Startup logs one line `AI startup: ...` (warning when any function is an offline fallback); `/health` has `ai_functions`, `/eval` has `ai_functions` with the reason.
- `demo-live` (`u-demo-8`, scenario 8) is the account for live demos: no open claim, PIN 1234. Chaos: `identity_down` -> mocks `error_500`, `ledger_down` -> mocks `ledger_down` (ledger only), `payments_down` -> backend payout call.

## Tasks
- [x] Everything above.
- [ ] TODO(Basit): deploy (Render/Railway + Supabase) using `backend/render.yaml` + `DEPLOY.md`; put the URL in the README.
- [ ] TODO(Basit): per-key quotas beyond rate limits; deploy (see above).
- [x] Hadi: `/payments/disburse` in `/mocks` (idempotent) and the demo people in `/mocks`. [ ] TODO(Hadi): real webhook delivery behind `events.emit`.
- [x] Hani (done): "Did my payment arrive?" button (`POST /claims {"intent":"payment_check","month":"YYYY-MM"}`); frontend live mode must treat `POST /claims` as 202 + poll `/claims/{id}/progress`, read errors from `message`, show ID photos from `image_url`, and can build the Scam Map from `GET /scam-map` (fixture `scam_map.json`) and the Digital Twin from `POST /rules/{id}/simulate`.

## Run / test
```
make test                                    # all folders
cd backend && ../.venv/bin/python -m pytest -q
TEST_POSTGRES_URL=postgresql+psycopg2://bharosa:bharosa@localhost:5544/bharosa pytest backend/tests/test_pg_audit_trigger.py   # Postgres-only trigger test
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000   # PYTHONPATH must include repo root and ai/ (make dev sets it)
make db migrate seed        # postgres in docker (POSTGRES_PORT=5544 make db if 5432 is taken), then migrate + seed
cd backend && alembic revision --autogenerate -m "msg"   # then review the file; needs DATABASE_URL
```
Swagger: http://localhost:8000/docs. Demo logins: username = role name; passwords in `.env.example`.
