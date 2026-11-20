# mocks/: simulated government services

**Owner:** Hadi. **Depends on:** nothing (self-contained; tests validate against `/contracts`). **Depended on by:** `/backend` (over HTTP via `MOCKS_URL`), `/e2e`, Chaos Panel.
Read the root `CLAUDE.md` first.

## Contract (`contracts/openapi-mocks.yaml`, `contracts/schemas.py`)
- `GET /identity/{cnic}` -> PersonRecord
- `GET /ledger/{cnic}` -> `{cnic, payments: [Payment]}` (Payment: payment_id, amount_pkr, date, agent_id, programme)
- `POST /complaints` -> `{ticket_id}`
- `GET /senders` -> `{senders: [official codes]}`
- `POST /notify` -> `{message_id}`
- `GET /chaos`, `POST /chaos`, `POST /chaos/reset`
- **Every response includes `"simulated": true`**, including errors.

## Rules
- **Deterministic seed data** in `app/data/` (5 records each, fake CNICs `00000...`, fictional Sahara Relief Programme, official sender `9090`).
- **Chaos switches live in memory with reset** (`app/chaos.py`): `timeout`, `error_500`, `missing_record`, `duplicate_payment`, `lookalike_sender`, `slow_network_ms`.
- **No dependency on other folders** at runtime.
- Never use real names, real programme names, or real CNICs.

## Tasks
- [ ] TODO(Hadi): grow synthetic data (more people, messy name variants, short/duplicate payments, lookalike senders).
- [ ] TODO(Hadi): Chaos Panel backend polish (presets like "bad day", scheduled failures) coordinating with Hani's UI.
- [ ] TODO(Hadi): realistic delays/jitter and partial failures.
- [ ] TODO(Hadi): contract tests for every endpoint x every chaos switch.

## Run / test
```
cd mocks && ../.venv/bin/python -m pytest -q
cd mocks && ../.venv/bin/python -m uvicorn app.main:app --port 8001 --reload     # http://localhost:8001/docs
```
