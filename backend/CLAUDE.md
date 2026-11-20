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

## Tasks
- [ ] TODO(Basit): SQLAlchemy models (list in `app/models/__init__.py`) + Alembic migrations + seed (demo users per role).
- [ ] TODO(Basit): replace fixture returns with DB-backed logic, router by router; keep response models unchanged.
- [ ] TODO(Basit): case lifecycle: create/assign/escalate/decide/close with status transitions validated.
- [ ] TODO(Basit): claim pipeline (`services/pipeline.py`) with `bharosa_ai` + mocks, resumable steps.
- [ ] TODO(Basit): consent service (see/share/withdraw/correct) enforced before mock calls.
- [ ] TODO(Basit): rules versioning + `/rules` editor endpoints, active rule lookup.
- [ ] TODO(Basit): audit log table + `/audit` filters.
- [ ] TODO(Basit): API keys (hashed, scoped), rate limiting, Swagger polish.
- [ ] TODO(Basit): `/queue` sorted by risk desc then confidence asc; `/eval` serves `ai/eval_results.json`.
- [ ] TODO(Basit): logs, deploy (Render/Railway + Supabase Postgres), deployed URL in README.

## Run / test
```
make test                                    # all folders
cd backend && ../.venv/bin/python -m pytest -q
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000   # PYTHONPATH must include repo root and ai/ (make dev sets it)
cd backend && alembic revision --autogenerate -m "msg" && alembic upgrade head   # needs DATABASE_URL
```
Swagger: http://localhost:8000/docs. Demo logins: username = role name; passwords in `.env.example`.
