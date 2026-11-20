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
- [ ] TODO(Hadi): `notifications/`: templates (ur/en), queue, retry, consent-aware.
- [ ] TODO(Hadi): `webhooks/`: subscription, HMAC signatures, retry/backoff, delivery log.
- [ ] TODO(Hadi): `digital_twin/`: synthetic populations, scam-wave scenarios, results summary for the demo.

## Run / test
Each subfolder gets its own README with run commands as it is built.
