# services/: notifications, webhooks, Digital Twin

**Owner:** Hadi. **Depends on:** `/contracts` only. **Depended on by:** `/backend` (may call these), `/e2e`.
Read the root `CLAUDE.md` first.

## Contract
- Notifications use the mock `POST /notify` -> `{message_id}` (consent scope `notifications` is required first).
- Webhooks: signed (HMAC) POSTs on case events; payloads use `contracts/schemas.py` models.
- Digital Twin: simulate a population of citizens/helpers/scammers against the platform to show behaviour at scale. Outputs go through the public API only.

## Rules
- Respect consent before notifying. Everything simulated; no real SMS or HTTP to real services.
- Audit-log every event emitted (via the backend API, not by writing its DB).
- No real personal data.

## Tasks
- [x] `notifications/`: templates (ur/en), retry, consent-aware (default deny).
- [x] `webhooks/`: subscription, HMAC signatures, retry/backoff, delivery log. TODO(Hadi): backend `events.emit()` must POST to `/events` (Basit's file).
- [x] `digital_twin/`: rule preview (read-only), synthetic history, scam wave, JSON report. See its README.

## Run / test
```
PYTHONPATH=. python -m uvicorn services.main:app --port 8002   # from the repo root; MOCKS_URL=http://localhost:8001, WEBHOOKS_ALLOW_LOCAL=1 for local demos
PYTHONPATH=. python -m pytest services -q
```
