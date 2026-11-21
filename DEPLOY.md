# Deploy checklist (about 30 minutes): Supabase + Render + Vercel

Nothing here has been deployed yet. Do the steps in this order; each one has a check so you know it worked.
All data is FAKE and every response says `simulated: true`. Keep a note of the 4 URLs you collect.

| You need | Where |
|---|---|
| Supabase project (Postgres) | supabase.com, free |
| Render account (3 web services) | render.com, free plan is enough |
| Vercel account (frontend) | vercel.com, free |

## 1. Supabase, the database (5 min)
1. New project, any region, set a database password (write it down).
2. Project Settings > Database > **Connection string > URI, the direct one (port 5432, not the pooler)**.
3. Turn it into a SQLAlchemy URL and add SSL:
   `postgresql+psycopg2://postgres:<PASSWORD>@db.<ref>.supabase.co:5432/postgres?sslmode=require`
   Keep it: this is `DATABASE_URL`.
- Check: nothing to see yet. The backend creates the tables on its first start (it runs `alembic upgrade head`).

## 2. Render, the three services (15 min)
1. Render dashboard > **New > Blueprint** > pick this GitHub repo > set **Blueprint file path** to `backend/render.yaml` > Apply.
   It creates `bharosa-mocks`, `bharosa-services` and `bharosa-backend` (Docker, free plan, build context = repo root).
2. Open `bharosa-services` > Environment: copy the generated **`SERVICES_API_KEY`**.
3. Open `bharosa-backend` > Environment and fill the variables marked "sync: false":
   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase URL from step 1 |
   | `SERVICES_API_KEY` | the value you copied in 2 |
   | `CORS_ORIGINS` | your Vercel origin, e.g. `https://bharosa.vercel.app` (add it after step 3; redeploy once) |
   | `DEMO_ADMIN_PASSWORD`, `DEMO_OFFICER_PASSWORD`, `DEMO_AUDITOR_PASSWORD`, `DEMO_HELPER_PASSWORD`, `DEMO_CITIZEN_PASSWORD` | your own passwords for the judges (the README ones are public) |
   | `MOCKS_URL`, `NOTIFICATIONS_URL`, `WEBHOOKS_URL` | already set to `https://bharosa-mocks.onrender.com` / `https://bharosa-services.onrender.com`. **Change them if Render gave your services different names or URLs** |
4. Deploy all three (Manual Deploy > Deploy latest commit). The backend takes the longest (it installs Tesseract OCR, about 5 min).
- Check: `curl https://bharosa-backend.onrender.com/health` shows `"database":"ok"` and `"mocks":{"mode":"real","reachable":true}`.
  It also lists `ai_functions`: with no LLM key, `extract_claim` says `real_offline_fallback` (that is expected, see "LLM key" below).
- Check: `https://bharosa-backend.onrender.com/docs` opens Swagger.

## 3. Vercel, the frontend (5 min)
1. New Project > import the repo > **Root Directory: `frontend`** (framework: Next.js, default build and output).
2. Environment Variables (both are baked in at build time, so changing them later needs a redeploy):
   - `NEXT_PUBLIC_API_MODE` = `live`
   - `NEXT_PUBLIC_API_URL` = `https://bharosa-backend.onrender.com` (your backend URL, no trailing slash)
3. Deploy. Copy the Vercel URL, put it into the backend's `CORS_ORIGINS` on Render, redeploy the backend.
- Check: open the Vercel URL, log in with the demo **officer**, the queue loads, the yellow "PROTOTYPE - simulated data" banner shows.

## 4. After deploy: reset the demo and run the scenarios (3 min)
```bash
API=https://bharosa-backend.onrender.com
ADM=$(curl -s $API/auth/login -H 'content-type: application/json' -d '{"username":"admin","password":"<your admin password>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -X POST $API/admin/demo/reset -H "Authorization: Bearer $ADM" -H 'content-type: application/json' -d '{"include_rules":true}'
make demo-scenarios BASE=$API        # all 8 should say PASS (needs MOCKS_HOST_URL=https://bharosa-mocks.onrender.com for the outage scenario)
```
The same reset is a button in the app: **Admin > Chaos Panel > Reset demo data**. Run it before every judge session.
Free Render services sleep after about 15 minutes. **Warm up** before a demo: open `/health` of the backend, mocks and services, then wait until all three answer (the first one can take a minute).

## 5. Adding the LLM key later (2 min, no code change)
The system works without a key: `extract_claim` uses the offline parser, lowers its confidence by 0.05 and adds the reason `llm_unavailable`.
When you have a key: Render > `bharosa-backend` > Environment, set
- `LLM_API_KEY` = your key
- `LLM_MODEL` = the provider's model id
- `LLM_BASE_URL` = only if it is not `https://api.x.ai/v1` (https only)
- `AI_MODE` = `real`

Save (Render redeploys) and check `/health`: `extract_claim` now says `real` (and the startup log line "AI startup" says "offline parser + LLM assist").
To switch the LLM off again without removing the key: `AI_USE_LLM=0`.

## 6. Smoke test (3 min)
- [ ] Vercel: landing page, banner, login as each role.
- [ ] Citizen **demo-live** (password = your citizen password): Claim > speak or type "mera naam Samina Parveen hai. Mujhe is mahine ke paisay nahi mile" > result **needs more proof**, no duplicate warning.
- [ ] Citizen home shows **My messages** after the claim (needs the services app to be awake).
- [ ] Officer: queue > open a case > Approve with a reason > the payment shows once.
- [ ] Admin > Chaos Panel: switch **Payment record down**, file a claim, it pauses at the payment-record step; **Reset all**; **Try again** finishes it.
- [ ] Put the three URLs and the video link into the README table.

## Things to know
- ID photos are stored in Postgres (after a resize), so they survive redeploys. The optional disk cache does not.
- Free Postgres on Supabase pauses after a week of no use: open the project to wake it.
- More technical notes (workers, uploads, logs, Railway): [backend/DEPLOY.md](backend/DEPLOY.md).
