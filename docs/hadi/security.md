# Hadi: security notes (mocks, services, e2e)

Judges score behaviour under risk. Core JWT/RBAC/audit/consent live in `/backend` (Basit); this covers my pieces and how they must behave next to his.

## Threat model

| Threat | Where | Control |
|---|---|---|
| Mock mistaken for a real service | `mocks/app/main.py` | `"simulated": true` on **every** response, including 404, 422, 500, 504 (custom handlers) |
| Real personal data in the repo | `mocks/scripts/generate_data.py` | Fake CNICs `00000...`, invented names, fictional "Sahara Relief Programme"; a test asserts 13 digits and the prefix |
| Double payment on retry or double click | `POST /payments/disburse` | Idempotency key (header or body); same key returns the same `payment_ref` with `duplicate: true`; tested. The backend also stores the key before the call |
| Mock moves money without approval | mocks | It cannot decide anything: it only records a simulated payout when the backend, after officer approval, calls it. No money moves |
| Chaos Panel abused on a public deploy | mocks `/chaos*`, `/reset` | Optional `CHAOS_TOKEN` (`X-Chaos-Token`, constant-time compare) on all writes; `slow_network_ms` capped at 10 s; admin-only in the UI |
| Mock failure becomes a raw 500 for the citizen | mocks + backend | Structured errors from mocks (`{"error", "simulated"}`); backend turns `MockUnavailable` into `with_officer` with notes |
| Bad input crashes or leaks internals | mocks | Pydantic validation returns a calm 422 listing field names only, no tracebacks (tested) |
| Notification without consent | `services/notifications/service.py` | Default-deny: no consent record means `blocked`; checked before every send; withdrawal blocks the very next send; logged and audited |
| Untrusted caller drives services | `services/main.py` | `X-Service-Key` (constant-time compare) on every endpoint except `/health`; CNIC validated as 13 digits; secrets never listed after creation |
| Forged or replayed webhook | `services/webhooks` | HMAC-SHA256 over the raw body with a per-subscription secret, signed timestamp, constant-time compare, receivers reject old timestamps |
| Webhook SSRF | `services/webhooks` | http/https only; no loopback/private targets unless `WEBHOOKS_ALLOW_LOCAL=1` (demo only) |
| Retry storm | job runner | Max attempts, capped exponential backoff, dead-letter for a human |
| Secrets committed | all | Only from env (`.env.example`, fake values); webhook secrets generated per subscription |
| e2e bypasses security | `e2e/` | Public API only, real tokens per role, includes negative tests (citizen cannot approve, auditor cannot write) |
| Digital Twin touches live data | `services/digital_twin` | Read-only through the public API; output kept separate |

## Rules my code keeps (root `CLAUDE.md`)
1. Mocks return `simulated: true` on every response.
2. Consent before any call touching a person's data: the backend gates `identity`, `payments`, `complaints`; notifications gate `notifications` too.
3. Any payment step needs officer approval: the backend enforces it, mocks only record the approved payout.
4. Failures are structured and safe; no stack traces or paths.
5. Every event my services emit is audit-logged through the backend API, never by writing its DB.
6. No real data.

## Where the controls live
- Backend side (Basit): `require_role`, consent service, audit append-only trigger, rate limiting.
- My side: chaos token, idempotent disburse, validation handler, HMAC webhooks, consent-aware notifier, e2e negative tests.

## Try to break my parts
- Switch on `error_500` / `timeout` / `missing_record`: case reaches an officer with notes, no error page.
- `duplicate_payment`, `lookalike_sender`: red flag, never auto-approved.
- Call `/payments/disburse` twice with one key: one payout. Send `amount_pkr: -5`: calm 422.
- Set `CHAOS_TOKEN`, call `POST /chaos` without the header: 403.
- Withdraw `notifications`: no SMS in the log.
- Change one byte of a webhook body or replay an old one: verification fails.
- `POST /reset`: back to normal.

## Known limits
- Services keep consent in their own memory, fed by `POST /notifications/consent`. It fails closed, but the backend must push grants/withdrawals (not wired yet), and a restart forgets them.
- `SERVICES_API_KEY` has a fake dev default; set a real one on any shared deployment.
- Webhook SSRF check does not cover DNS rebinding.
- Chaos state and idempotency keys are in memory: a restart clears them and several workers would not share them. Run one worker.
- Mocks have no user auth by design (they model external systems); protection is network placement plus the optional chaos token.
