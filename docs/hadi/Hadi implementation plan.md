# Hadi: implementation plan

**Scope:** `/mocks`, `/services` (`notifications`, `webhooks`, `digital_twin`), `/e2e`, and the demo kit in `/docs`.
**Sources:** *Bharosa - Tasks Per Person* (Hadi section and timeline), root `CLAUDE.md`, and the existing code. Build closes **Sun 22 Nov 2026, 6:00 PM PKT**.
**Rules:** edit only my folders (plus additive `/docs` and `/contracts`); every mock response says `"simulated": true`; fake CNICs start `00000`; commits are `area: what changed` with no AI trailer.

## Where my work plugs into the repo (verified in the code)

| My piece | Plugs into | Existing hook |
|---|---|---|
| Mock app | `backend/app/services/mocks_client.py` (`MocksClient`, picks real mocks if `MOCKS_URL` is set and `/health` answers, else `fake_mocks_client.py`) | endpoints it calls: `/identity`, `/ledger`, `/complaints`, `/senders`, `/notify`, **`/payments/disburse`** |
| Demo people | `contracts/fixtures/demo_people.json` (shared with `backend/app/demo_data.py`) | `fake_mocks_client.py` had `TODO(Hadi)`: mocks must serve the same 7 scenario people |
| Webhooks | `backend/app/services/events.py` `emit(name, payload, db)` | `TODO(Hadi)`: real signed delivery; keep call sites unchanged |
| Notifications | pipeline step `notify` in `backend/app/services/pipeline.py` (checks scope `notifications` first, then `mocks.notify`) | template, queue and retry live in `services/notifications` |
| Chaos | mocks `/chaos*` (Hani's admin UI) and the backend's own `POST /admin/demo/chaos` (fake client only) | I own the mocks one |
| e2e | `e2e/README.md` (5 scenarios), `backend/scripts/run_scenarios.py` (7 scenarios, exists) | reuse its login/seed conventions |
| Demo | `docs/demo-script.md`, `docs/judge-checklist.md`, `make demo-reset` | fill the `TODO(Hadi)` rows |
| CI | `.github/workflows/ci.yml` (matrix `ai, backend, mocks`) | e2e/services are not in CI yet |

## Handover

| Deliverable | To | Deadline |
|---|---|---|
| Mock services URL | Basit, Hani | Sat 2 PM |
| Synthetic data + `labels.json` | Ali, Basit | Sat, hour three |
| e2e pointed at live API | all | Sat 8 PM |
| Demo script + judge checklist | all | Sun 1 PM |
| Demo video (public Drive link) | all | Sun 4 PM |

## Phase 1: Mock services and synthetic data (Sat) [code done, URL pending]
Goal: the fake government world, deployable, with messy realistic data.
- [x] Mock FastAPI app: identity, ledger, complaints, senders, notify, chaos (scaffold from the repo).
- [x] `mocks/scripts/generate_data.py`: seeded and reproducible; writes `mocks/app/data/{identity,ledger,senders,labels}.json`. First 5 original people unchanged.
- [x] 93 fake people: 5 original, 75 generated (Muhammad/Mohammad/Muhammed/Mohd variants, Urdu aliases, stray spaces, missing father name/DOB), 6 duplicate identities, 4 wrong records, 7 demo-scenario people merged from `contracts/fixtures/demo_people.json`.
- [x] Ledger: normal payments, short payments by bad agents `agent-044`, `agent-058`, `agent-099` (099 matches demo scenario 3), duplicate payments, people with no payment.
- [x] Senders: official `9090` family from the shared fixture plus lookalikes (`9O9O`, `SAHARA-lNFO`, ...).
- [x] `labels.json` ground truth for Ali's evaluation.
- [x] `POST /payments/disburse`: idempotent simulated payout the backend already calls (`Idempotency-Key` header or body field; repeat returns same `payment_ref` with `duplicate: true`).
- [x] `POST /reset` (chaos, complaints, notifications, payment keys) and chaos presets `POST /chaos/preset/{normal|identity_down|bad_day|slow_network|scam_wave}`.
- [x] Optional `CHAOS_TOKEN` guard for public deployments; 422 errors also carry `simulated: true`.
- [x] Tests: data quality, every endpoint x every switch, presets, token, disburse (46 pass).
- [ ] Deploy the mocks and share the URL (Render/Railway, uses `mocks/Dockerfile`; set `MOCKS_URL` on the backend, `CHAOS_TOKEN` on mocks).
- [ ] Announce additive contract changes (presets, `/payments/disburse`, `/reset`) and add them to `contracts/openapi-mocks.yaml`.
- [ ] Point `fake_mocks_client.py` at the same 93 people: ask Basit (his folder), or leave as is; the real mocks now cover the demo scenarios.
**Done when:** `make dev` runs the backend against the mocks, `make demo-scenarios` passes with `MOCKS_URL` set, and the URL is shared.

## Phase 2: Notifications, webhooks, retry runner [code done, backend wiring pending]
App: `services/main.py` (port 8002, `PYTHONPATH=. uvicorn services.main:app --port 8002`). Shared retry + audit in `services/common.py`.
- [x] `services/notifications/service.py`: Urdu + English templates (`case_approved`, `needs_more_proof`, `with_officer`, `scam_warning`), in-app/SMS log, consent **default-deny** (no record means blocked), sends through the mock `POST /notify`, retries.
- [x] `services/webhooks/service.py`: subscriptions (secret shown once), HMAC-SHA256 over `timestamp.body`, `verify()` for receivers (tamper, wrong secret, replay), SSRF-safe URLs, retry 1/5/30 s then dead-letter, delivery log.
- [x] Job runner (`common.retry`): bounded retries, ends `done` or `dead`; `GET /jobs` shows jobs and audit.
- [x] `POST /events`: the target for the backend's `events.emit()`; fans out in the background so retries never block the caller.
- [x] Service key (`X-Service-Key`, `SERVICES_API_KEY`) on every endpoint except `/health`.
- [x] Tests: 23 pass (key, consent, retry bounds, signing, replay, SSRF, fan-out). Live run verified: signed delivery accepted by a receiver, dead-letter after 4 attempts, consent blocked then sent in Urdu.
- [ ] Wire the backend (Basit's `backend/app/services/events.py`): in `emit()` add `httpx.post(SERVICES_URL + "/events", json=event, headers={"X-Service-Key": ...})` wrapped in try/except so a services outage never breaks a case. Also have consent grant/withdraw call `POST /notifications/consent`. Both need his OK.
- [ ] Forward `common.audit` to the backend audit API once it has an ingest endpoint (today the audit trail is in-process, `GET /jobs`).
**Done when:** a case status change in the live backend produces a signed webhook; withdrawn consent yields zero notifications (service side verified; backend side pending).

## Phase 3: End-to-end tests [done, verified against the live stack]
Files: `e2e/conftest.py` (harness, skips when the stack is down), `e2e/test_scenarios.py`, run notes in `e2e/README.md`.
- [x] Harness: httpx, login cache per role, wait-for-pipeline helper, reset of mocks (`POST /reset`) and backend (`/admin/demo/reset`) before every test and at the end.
- [x] The five scenarios: happy path (officer approval, one `POST /payments/disburse`, double approval 409), misspelled name, identity failure (`error_500`, `timeout`, `missing_record`, then resume), consent withdrawn (no `GET /ledger` reached the mocks, proven by the new mocks `GET /calls`), rule changed live (old decision keeps v1, next uses v2).
- [x] Extras: duplicate payment is flagged not closed; RBAC negatives (403/401/404); services consent default-deny; webhook signature and tamper check.
- [ ] Add `e2e` to CI (needs the stack started in the workflow; `ci.yml` is shared, so coordinate), Playwright smoke test only if time allows.
**Done when:** all pass against the live deployment (passes locally; the deployed URL is pending Basit).

## Phase 4: Digital Twin [done, verified live]
Code: `services/digital_twin/twin.py` (CLI + `Twin` class), tests in `services/tests/test_twin.py`, e2e test 10.
- [x] Replays past AI decisions under a proposed rule through the backend's `POST /rules/{id}/simulate` (it re-runs only `decide`), then `assess()` turns it into a verdict: `REVIEW BEFORE PUBLISHING` (cases lose human oversight), `TIGHTER` (extra officer workload), `SAFE on history`, or `NO DATA` (never "safe" when nothing was replayed).
- [x] Synthetic history (`--seed-history`, opt-in): one claim per demo citizen so there are decisions with stored inputs.
- [x] Scam-wave scenario (`--scam-wave`): 10 fictional messages through `POST /messages/check`; reports caught / unsure / missed / genuine blocked by mistake.
- [x] Read-only proof: rule stays v1, zero `rule.publish` audit rows, only `rule.simulate`.
- Live result (stub AI): `auto_handle >= 0.80` -> 3 of 5 replayed cases `ask_more -> auto_handle`, verdict REVIEW; `0.95/0.85` -> 3 cases `ask_more -> send_to_human`, verdict TIGHTER.
**Done when:** the twin prints "N of M decisions would change" without touching live data. (Met.)

## Phase 5: Demo and judging kit (Sun 10 AM to 4 PM)
- [ ] Fill `docs/demo-script.md` (my slot: Chaos, 3:00 to 3:45) and extend `docs/judge-checklist.md`.
- [ ] Rehearsal script: reset everything, then run; use the 7 demo logins (`s1-clean` ... `s7-autohandle`).
- [ ] Record the video, upload to a public Drive link.
**Done when:** two full rehearsals with no dead time.

## Risks and fallbacks
| Risk | Fallback |
|---|---|
| Mocks deploy slips | Backend auto-falls back to `fake_mocks_client.py`; share a local URL meanwhile |
| Webhook wiring needs `events.py` | Run the webhook service as a poller of the backend's audit `event.*` entries instead |
| Behind schedule | Cut Digital Twin, then webhooks (per the PDF); never cut chaos, e2e, demo |
| Stuck 15 minutes | Fake the value, `TODO(Hadi)`, post it, move on |
