# Deploying the backend (config only: nothing here has been deployed)

Target: **Render or Railway** for the API, **Supabase** for Postgres, **Vercel** for the frontend.

## 1. Database (Supabase)
1. Create a project. Copy the **direct** connection string (port 5432) and make it SQLAlchemy-style:
   `postgresql+psycopg2://postgres:<password>@db.<ref>.supabase.co:5432/postgres?sslmode=require`
2. Do not use the transaction pooler for migrations. The container runs `alembic upgrade head` on every start.
3. The `audit_log` trigger (migration `0003`) needs a role allowed to create functions/triggers: the default `postgres` role is fine.

## 2. API on Render
- `backend/render.yaml` is a Blueprint (Docker, build context = repo root, health check `/health`).
- Set the `sync: false` variables in the dashboard: `DATABASE_URL`, `CORS_ORIGINS` (your Vercel origin), optionally `MOCKS_URL`, `SENTRY_DSN`, demo passwords.
- Start command (in the image): `sh start.sh` = `alembic upgrade head` -> optional seed (`SEED_ON_START=1`) -> `uvicorn` on `$PORT` with `--proxy-headers`.
- Set `TRUST_PROXY=1` so rate limits see the real client IP.

## 2b. API on Railway
New project -> Deploy from repo -> Dockerfile path `backend/Dockerfile`, root directory `/` (repo root).
Add the same variables. Railway provides `PORT` and a Postgres plugin (`DATABASE_URL` is then `postgresql://...`: change the scheme to `postgresql+psycopg2://`). Health check path: `/health`.

## 3. Frontend (Vercel)
Root `frontend`, `NEXT_PUBLIC_API_MODE=live`, `NEXT_PUBLIC_API_URL=https://<your-backend>`; add that Vercel origin to `CORS_ORIGINS`.

## Environment variables
See `.env.example` at the repo root. The important ones: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `MOCKS_URL`, `AI_MODE`, `PIPELINE_MODE`, `LOGIN_RATE_LIMIT`, `DEFAULT_RATE_LIMIT`, `PUBLIC_RATE_LIMIT`, `TRUST_PROXY`, `SENTRY_DSN`, `ENVIRONMENT`, `LOG_LEVEL`, `UPLOAD_DIR`, `WEB_CONCURRENCY`.

## Things to know
- **Uploads**: ID photos go to `UPLOAD_DIR`. Free plans have no persistent disk, so files vanish on redeploy (claims already processed keep their OCR fields in the database). Use a disk (paid) or object storage before real use.
- **Workers**: the claim pipeline runs in an in-process worker thread fed by the `jobs` table. `WEB_CONCURRENCY>1` is safe (jobs are claimed atomically); a job left `running` by a crashed process is re-queued at the next start.
- **Demo data/passwords** are fake but public in the README; set your own `DEMO_*_PASSWORD` values for a public URL, and `SEED_ON_START=0` when you stop wanting demo data.
- **Logs**: one JSON object per line on stdout (request id, role, latency). Optional Sentry via `SENTRY_DSN` (needs `sentry-sdk`, included in the image).
- **Smoke test after deploy**: `curl https://<api>/health` (expect `"database":"ok"`), open `/docs`, log in as `officer`.
