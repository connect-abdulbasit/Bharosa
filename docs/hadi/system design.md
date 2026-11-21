# Hadi: system design (mocks, services, e2e)

My pieces in the context of `docs/architecture.md`. I own the simulated public rails, the extras around the backend, and the proof.

```mermaid
flowchart LR
  FE[Frontend :3000] -->|/chaos presets| MK
  BE[Backend :8000<br/>services/mocks_client.py] -->|consent first, then HTTP| MK[Mocks :8001<br/>identity, ledger, complaints, senders,<br/>notify, payments/disburse, chaos]
  BE -. MOCKS_URL empty or down .-> FK[fake_mocks_client.py]
  BE -->|events.emit to /events| WH[services/webhooks]
  BE -->|consent + notify| NT[services/notifications]
  NT -->|POST /notify| MK
  WH -->|HMAC-signed POST| EXT[Subscribers]
  JR[Job runner] -->|retries| MK
  DT[services/digital_twin] -->|public API, read-only| BE
  E2E[e2e] -->|public API| BE
  E2E -->|/reset, switches| MK
  DATA[(mocks/app/data)] --- MK
  DEMO[(contracts/fixtures/demo_people.json)] -->|generate_data.py| DATA
  DATA -. labels.json .-> AI[ai/eval]
```

## 1. Folder map

```
mocks/
  app/main.py        endpoints, chaos dependency, error handlers
  app/chaos.py       in-memory switches, presets, reset
  app/data/          identity.json, ledger.json, senders.json, labels.json (generated)
  scripts/generate_data.py   deterministic generator (reads contracts/fixtures/demo_people.json)
  tests/             test_mocks.py, test_data_and_chaos.py
services/
  notifications/     templates (ur/en), queue, consent-aware send
  webhooks/          subscriptions, HMAC signing, retry, delivery log
  digital_twin/      what-if re-run of decisions under a proposed rule
e2e/                 scenarios from e2e/README.md, harness
docs/hadi/           these three files
```

## 2. Mock services (`/mocks`)
Standalone FastAPI app, no runtime imports from other folders. Shapes follow `contracts/schemas.py`.

| Endpoint | Returns | Notes |
|---|---|---|
| `GET /health` | `{status}` | not affected by chaos; the backend probes it |
| `GET /identity/{cnic}` | PersonRecord | 404 `record_not_found` |
| `GET /ledger/{cnic}` | `{cnic, payments[]}` | read-only history |
| `POST /complaints` | `{ticket_id}` | |
| `GET /senders` | `{senders[]}` | official codes; lookalikes only under chaos |
| `POST /notify` | `{message_id}` | appended to an in-memory log |
| `POST /payments/disburse` | `{payment_ref, duplicate}` | idempotent; called by the backend after officer approval |
| `GET/POST /chaos`, `POST /chaos/reset`, `GET /chaos/presets`, `POST /chaos/preset/{name}` | ChaosState | presets replace, not stack |
| `POST /reset` | ChaosState | clears chaos, complaints, notifications, payment keys, call counts |
| `GET /calls` | `{calls}` | per-endpoint call counts since the last reset (e2e uses it to prove a call was not made) |

Every response includes `"simulated": true`. `POST` routes under `/chaos`, `/reset` need `X-Chaos-Token` when `CHAOS_TOKEN` is set.

### Chaos switches
One FastAPI dependency (`apply_chaos`) runs on every data endpoint, not on `/health` or `/chaos`.

| Switch | Effect |
|---|---|
| `slow_network_ms` | delay before answering (cap 10 s) |
| `timeout` | 504 `upstream_timeout` |
| `error_500` | 500 `internal_error` |
| `missing_record` | identity and ledger 404 |
| `duplicate_payment` | ledger returns an extra copy of the first payment |
| `lookalike_sender` | sender registry includes spoofed codes |

Presets: `normal`, `identity_down`, `bad_day` (timeout + 1.5 s), `slow_network` (2 s), `scam_wave`.

### Synthetic data
`generate_data.py` (seed 2026) writes 93 people and their ledger:
- 5 original people (unchanged; backend seeds use them).
- 75 generated people: name variants, Urdu aliases, whitespace, missing father name or DOB.
- 6 duplicate identities (same name and DOB, new CNIC) and 4 wrong records (registry DOB disagrees).
- 7 demo-scenario people merged from the shared fixture, so `s1-clean` ... `s7-autohandle` work against the real mocks.
- Payments: expected PKR 12,000; short payments cluster on `agent-044`, `agent-058`, `agent-099`; duplicates; no-payment people.
- `labels.json`: ground truth for `ai/eval`.

## 3. Services (`/services`, one app on :8002)
Files: `main.py` (routes), `common.py` (retry + audit), `notifications/service.py`, `webhooks/service.py`. Every route except `/health` needs `X-Service-Key`.

| Endpoint | Purpose |
|---|---|
| `POST /notifications/consent` | set `notifications` consent for a CNIC (default is none) |
| `POST /notifications/send` | consent -> template (ur/en) -> mock `POST /notify` -> log; returns `sent`, `blocked`, `failed` or `rejected` |
| `GET /notifications` | in-app inbox + SMS log, optional `cnic` filter |
| `POST/GET/DELETE /webhooks/subscriptions` | subscribe (secret returned once), list (no secrets), remove |
| `POST /events` | backend `events.emit()` target; 202 and fan-out in the background |
| `GET /webhooks/deliveries`, `GET /jobs` | delivery log; jobs and recent audit entries |

- **Notifications**: consent is default-deny and checked inside `send()`, so no caller can skip it. Failures retry then end `failed` with the job `dead`.
- **Webhooks**: `X-Bharosa-Signature: t=<ts>,v1=<hmac_sha256(secret, "ts." + body)>`, fresh timestamp per attempt; receivers call `verify()`. Events: `case.created`, `case.decided`, `case.status_changed` (what the backend emits today), `consent.withdrawn`.
- **Retry (`common.retry`)**: 1 try + delays 1, 5, 30 s = 4 attempts max, then `dead` and an audit entry. Tests set the delays to 0.
- **Digital Twin** (Phase 4): unchanged, see plan.

## 4. End-to-end (`/e2e`)
```
for each scenario: reset (mocks POST /reset, backend demo reset) -> arrange -> act via public API -> assert -> reset
```
Scenarios: happy path (`0000042101002`), misspelled name, identity down, consent withdrawn, rule changed mid-claim. Assertions: case status, audit entries, stored `rule_version`, `simulated: true`, no raw 500.

## 5. Configuration
| Variable | Used by | Meaning |
|---|---|---|
| `MOCKS_URL` (docker: `BACKEND_MOCKS_URL`) | backend, services, e2e | mocks location; empty means the backend's fake client |
| `CHAOS_TOKEN` | mocks | optional guard on chaos and reset writes |
| `WEBHOOKS_ALLOW_LOCAL` | webhooks | allow loopback targets in demos |
| `SERVICES_API_KEY` | services | caller key for `X-Service-Key` (fake dev default) |
| `BASE` | e2e, `make demo-scenarios` | backend URL |

## 6. Failure behaviour
| Failure | Mocks | Platform |
|---|---|---|
| identity down | 500 / 504 | progress saved, `with_officer`, notes |
| record missing | 404 | `ask_more` or human, never a guess |
| duplicate payment | extra ledger row | red flag, `send_to_human` |
| lookalike sender | spoofed code listed | scam check flags it |
| slow network | delay | pipeline resumes from last step |
| consent withdrawn | never called | blocked call in audit log |
| payout retried | same `payment_ref`, `duplicate: true` | one payment only |

## 7. Design decisions
- In-memory chaos and payment keys, one worker: simple and resettable (documented limit).
- Seeded generator, not hand-edited JSON: reproducible for Ali's labels and diff-reviewable.
- Mocks stay dependency-free; the generator (build time only) reads the shared fixture.
- Contract changes are additive and announced.
