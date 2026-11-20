# backend/: Bharosa platform API

**Owner:** Basit. **Depends on:** `/contracts`, and `bharosa_ai` (from `/ai`) via its public functions, plus `/mocks` over HTTP. **Depended on by:** `/frontend` (live mode), `/e2e`.
Read the root `CLAUDE.md` first.

## Contract
Endpoints and models: `contracts/openapi-platform.yaml`, `contracts/schemas.py`, example responses `contracts/fixtures/`.
`/auth/login`, `/me`, `/cases`, `/cases/{id}`, `/cases/{id}/assign|escalate|decide|close`, `/claims`, `/messages/check`, `/documents`, `/rules`, `/rules/{id}/versions`, `/consent`, `/consent/{id}/withdraw`, `/audit`, `/queue`, `/helper/families`, `/apikeys`, `/eval`.
Routers currently return fixtures (marked TODO(Basit)) but already enforce RBAC and write audit entries. Keep response models: they validate fixtures and real data alike.

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

## Status (database step done)
Real, DB-backed (SQLAlchemy 2.0 + Alembic `0001_initial_schema`): users, auth (bcrypt + JWT), `/me`, cases (create/list/get/assign/escalate/decide/close), consent (list/grant/withdraw/correct + `services/consent.require`), audit (`audit.log(db, actor_type, actor_id, action, entity, entity_id, before, after)`, request-id middleware, append-only), rules (list/versions/new version), queue, helper families, API keys (hashed).
Still fixtures (TODO): `/claims` pipeline result, `/messages/check`, `/documents`, `/eval`. `/claims` already enforces consent before returning.

Conventions added in this step:
- Pass the request's `db` session to `audit.log(...)`; it only `add()`s, so the entry commits atomically with the change. When the request will fail afterwards (login failure, blocked consent) commit first, then raise.
- Auditors are read-only: enforced centrally in `require_role` (any non-GET method is 403).
- Row-level access lives in `services/access.py`; objects a user may not see answer 404.
- Status changes go through `services/cases.change_status` (validates transitions, always audits).
- Extra columns beyond the original spec: `users.username` (login id), `users.cnic` (fake), `api_keys.prefix`.

## Tasks
- [x] Models + Alembic migration, seed (`make seed`), auth + RBAC, audit, cases, consent.
- [ ] TODO(Basit): claim pipeline (`services/pipeline.py`) with `bharosa_ai` + mocks client, resumable steps; use `consent.require` before each mock call; mock failure -> `with_officer` with notes.
- [ ] TODO(Basit): documents (OCR, blur -> retake), messages/check via `bharosa_ai`, `/eval` from `ai/eval_results.json`.
- [ ] TODO(Basit): API-key authentication (`X-API-Key` + scopes) and per-key rate limiting; general rate limiting.
- [ ] TODO(Basit): Postgres-level append-only guard for `audit_log` (trigger or revoke UPDATE/DELETE).
- [ ] TODO(Basit): logs, deploy (Render/Railway + Supabase Postgres), deployed URL in README.

## Run / test
```
make test                                    # all folders
cd backend && ../.venv/bin/python -m pytest -q
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000   # PYTHONPATH must include repo root and ai/ (make dev sets it)
make db migrate seed        # postgres in docker (POSTGRES_PORT=5544 make db if 5432 is taken), then migrate + seed
cd backend && alembic revision --autogenerate -m "msg"   # then review the file; needs DATABASE_URL
```
Swagger: http://localhost:8000/docs. Demo logins: username = role name; passwords in `.env.example`.
