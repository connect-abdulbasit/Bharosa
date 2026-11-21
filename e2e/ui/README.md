# Browser walkthrough (Playwright, mobile viewport, live mode)

Walks the live frontend against the running stack and saves a screenshot per step to `docs/screenshots/`.
19 steps: landing, login as each role, scam check, claim (202 + polling), "Did my payment arrive?", consent withdraw/correct,
helper switch + PIN, officer approve + ID photo, Digital Twin, rule publish, Chaos pause -> Try again, auditor, Scam Map / eval, banner on 16 pages.

```bash
# stack: docker compose up --build   (+ frontend: NEXT_PUBLIC_API_MODE=live ... npm run build && npm run start -- -p 3100)
# the backend must allow the frontend origin: CORS_ORIGINS=http://localhost:3000,http://localhost:3100 docker compose up -d backend
mkdir -p /tmp/bharosa-ui && cp e2e/ui/* /tmp/bharosa-ui/ && cp ai/data/sample_id_specimen.jpg /tmp/bharosa-ui/id.jpg && cd /tmp/bharosa-ui
npm init -y && npm i playwright@1.57.0
FE=http://localhost:3100 node walkthrough.mjs                      # edit lib.mjs if your Chromium path differs (EXE)
```
Expects a freshly reset demo (`make demo-reset`). Uses only public interfaces. Owner: Basit (written during integration), hand over to Hadi.
