# Bharosa mocks (SIMULATED)

Fake identity, ledger, complaints, senders, notify and chaos services. Every response has `"simulated": true`.

## Run / test
```
cd mocks && PYTHONPATH=.. python -m pytest -q
cd mocks && python -m uvicorn app.main:app --port 8001     # http://localhost:8001/docs
python mocks/scripts/generate_data.py                      # regenerate data (deterministic)
```

## Data (`app/data/`)
93 fake people (incl. the 7 demo-scenario people from contracts/fixtures/demo_people.json) (CNICs `00000...`), ledger (PKR 12,000 expected), senders, and `labels.json` (ground truth for Ali's evaluation: name variants, duplicates, wrong records, short/duplicate payments, bad agents 044/058/099, scam senders). The first 5 records never change.

## Chaos
`POST /payments/disburse` (idempotent), `POST /reset`.
`GET/POST /chaos`, `POST /chaos/reset`, `GET /chaos/presets`, `POST /chaos/preset/{normal|identity_down|bad_day|slow_network|scam_wave}`.
Set `CHAOS_TOKEN` on public deployments: writes then need header `X-Chaos-Token`.

## Deploy
`docker build -f mocks/Dockerfile .` (port 8001, single worker: chaos state is in memory).
