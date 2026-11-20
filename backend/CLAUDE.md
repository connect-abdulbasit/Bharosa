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

## Status
Database step and agent step are done. Alembic: `0001` schema, `0002` PIN / consent confirmation / document owner / checked messages, `0003` Postgres trigger that blocks UPDATE/DELETE/TRUNCATE on `audit_log` (skipped on SQLite).
Still fixtures: only `/eval`.

### Claim pipeline (`services/pipeline.py`)
`POST /claims` -> `extract_claim -> read_document -> identity_lookup -> ledger_lookup -> match_person -> decide -> explain -> notify`.
- State lives in `claims.data["pipeline"]` and `cases.current_step`; every step commits, so `POST /claims/{id}/resume` continues without redoing finished steps. Finished claims resume as a no-op.
- `consent.require` runs before each identity/ledger call. Missing consent, a mock error/timeout, or an unexpected bug => progress saved, status `with_officer`, a case note, a `send_to_human` decision by `agent`, and a normal 200 response (never a 500).
- Audit per step: `ai.<step>` (actor_type `ai`) or `agent.<step>` (actor_type `agent`) with input summary, output, confidence, model_version.
- Mapping (`map_decision`): auto_handle -> `approved` only when no payment is needed (otherwise `with_officer`: a payment always needs an officer); ask_more -> `needs_more_proof` (+ list of needs); send_to_human -> `with_officer`.
- The agent only looks up the ACCOUNT's own CNIC (never one supplied by the caller). Flags counted are those in the active rule's `red_flags`; `duplicate_claim` (open claim for the same month) always goes to an officer.
- Stub AI caveat: `extract_claim` always returns the name "Mohammad Aslam" and confidence 0.81, so with `AI_MODE=stub` most claims end `needs_more_proof`/`with_officer`; only Aslam's name matches. Tests patch `bharosa_ai` functions to reach other paths.

### Other behaviour
- Rules: `services/jsonlogic.py` validates structure, variables and behaviour (must always return an action, never auto_handle with red flags or confidence <= 0.3) before a version is saved; invalid => 422 with a clear message + `rule.rejected` audit. Every decision stores `rule_id` + `rule_version`.
- Officer `decide`: `reason` (or `note`) required; approve with a payment calls mocks `/complaints` (needs `complaints` consent), records ticket in the decision trace + `payment.release` audit; failure => 503 and nothing changes.
- Scam check (`services/scam.py`): AI verdict + official sender list from mocks; look-alike senders (9O9O) are scams; unofficial senders are never "genuine"; each check stored in `checked_messages` (hash only).
- Helper rule: GRANTING consent for a citizen needs the citizen's 4-digit PIN (`users.pin_hash`, seed PIN from `DEMO_CITIZEN_PIN`); event stores `actor_id = helper`, `confirmed_by = citizen`; 5 wrong PINs in 15 min => 429. Citizens set it with `POST /me/pin`.
- Documents: `POST /documents` (multipart) stores the file in `UPLOAD_DIR`, sniffs PNG/JPEG/WebP, runs OCR + blur check, returns `retake_needed`.

Conventions:
- Pass the request's `db` session to `audit.log(...)`; it only `add()`s, so the entry commits atomically with the change. When the request will fail afterwards (login failure, blocked consent) commit first, then raise.
- Auditors are read-only: enforced centrally in `require_role` (any non-GET method is 403).
- Row-level access lives in `services/access.py`; objects a user may not see answer 404.
- Status changes go through `services/cases.change_status` (validates transitions, always audits).
- JSON columns are not change-tracked: assign a NEW (deep-copied) object, never mutate in place.
- Extra columns beyond the original spec: `users.username`, `users.cnic` (fake), `users.pin_hash`, `api_keys.prefix`, `consent_events.confirmed_by`, `documents.owner_id` (+ nullable `case_id`).

## Tasks
- [x] Models, migrations, seed, auth + RBAC, audit (+ Postgres trigger), cases, consent (+ helper PIN rule).
- [x] Claim pipeline with resume, versioned/validated rules, scam check, documents, officer decide + payment, queue, helper families.
- [ ] TODO(Basit): `/eval` from `ai/eval_results.json`.
- [ ] TODO(Basit): API-key authentication (`X-API-Key` + scopes) and per-key rate limiting; general rate limiting.
- [ ] TODO(Basit): background/queued pipeline runs for slow mocks (today the request waits, mocks timeout is 5 s per call).
- [ ] TODO(Basit): logs, deploy (Render/Railway + Supabase Postgres), deployed URL in README.

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
